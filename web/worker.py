"""Background worker — polls Job queue, AI generates, auto-publishes."""
from __future__ import annotations

import asyncio
import os
import threading
import time
import traceback

from loguru import logger

from core.config import settings
from models.database import SessionLocal
import models.content  # noqa: F401
import models.post     # noqa: F401
import models.user     # noqa: F401
from models.post import Post
from services.content_service import content_service
from services.publish_service import publish_service
from web.ai_client import APIGenerator
from web.models import Job

_worker_started = False
_generator: APIGenerator | None = None


def start_worker() -> None:
    global _worker_started, _generator
    if _worker_started:
        return
    _worker_started = True
    _generator = APIGenerator()
    t = threading.Thread(target=_run, daemon=True, name="pipeline-worker")
    t.start()
    logger.info(f"Worker started (PID={os.getpid()})")


def _run() -> None:
    while True:
        _tick()
        time.sleep(2)


def _tick() -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.status == "queued").order_by(Job.created_at).first()
        publish_only = False
        if not job:
            job = db.query(Job).filter(Job.status == "approved").order_by(Job.updated_at).first()
            publish_only = True
        if not job:
            return
        job.status = "in_progress"
        db.commit()
        job_id = job.id
    finally:
        db.close()
    try:
        _execute(job_id, publish_only)
    except Exception as e:
        logger.error(f"Job {job_id} fatal: {e}\n{traceback.format_exc()}")
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job and job.status not in ("completed", "failed", "awaiting_approval"):
                job.status = "failed"
                job.progress_message = str(e)[:200]
                job.error_message = str(e)
                db.commit()
        except Exception:
            pass
        finally:
            db.close()


def _execute(job_id: str, publish_only: bool = False) -> None:
    asyncio.run(_execute_async(job_id, publish_only))


async def _execute_async(job_id: str, publish_only: bool = False) -> None:
    if publish_only:
        await _stage_publish_only(job_id)
        return

    db = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    is_preview = job.mode == "preview"
    db.close()

    # Stage 1: Create direction
    direction_id = await _stage_create_direction(job_id)
    if not direction_id:
        return

    # Stage 2: AI generate (Anthropic API, no manual interaction)
    post_id = await _stage_generate(job_id, direction_id)
    if not post_id:
        return

    # Stage 3: AI review
    ok = await _stage_review(job_id, post_id)
    if not ok:
        return

    # Inject images
    _inject_images(job_id, post_id)

    if is_preview:
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            job.status = "awaiting_approval"
            job.progress_message = "内容已生成，请审核后点击发布"
            db.commit()
        finally:
            db.close()
        return

    # Direct mode: auto publish
    await _stage_publish_only(job_id)


async def _stage_create_direction(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        _set(db, job, "creating_direction", "创建内容方向...")
        d = content_service.create_direction(db=db, topic=job.title, tone="casual",
                                              extra_context=job.requirements)
        job.direction_id = d.id
        db.commit()
        return d.id
    finally:
        db.close()


async def _stage_generate(job_id: str, direction_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        _set(db, job, "generating", "AI 正在生成内容...")
        g = await _generator.generate_post(
            topic=job.title,
            tone="casual",
            extra_context=job.requirements,
        )
        post = Post(
            direction_id=direction_id, title=g.title, body=g.body,
            hashtags=g.hashtags, image_urls=[], status="pending_review",
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        job.post_id = post.id
        job.post_title = post.title
        job.post_body = post.body
        job.hashtags = post.hashtags
        db.commit()
        return post.id
    finally:
        db.close()


async def _stage_review(job_id: str, post_id: str) -> bool:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        post = db.query(Post).filter(Post.id == post_id).first()
        _set(db, job, "reviewing", "AI 正在审核内容...")
        r = await _generator.review_content(
            title=post.title or "", body=post.body or "",
            hashtags=post.hashtags or [],
        )
        from models.post import ReviewRecord
        db.add(ReviewRecord(
            post_id=post.id,
            result="approved" if r.passed else "rejected",
            score=r.score,
            issues=r.issues if r.issues else None,
            reviewed_by="auto",
        ))
        if r.passed:
            post.status = "approved"
        else:
            post.status = "rejected"
            job.status = "failed"
            job.progress_message = "; ".join(r.issues)
            job.error_message = job.progress_message
            db.commit()
            return False
        job.review_score = r.score
        job.review_issues = r.issues
        db.commit()
        return True
    finally:
        db.close()


def _inject_images(job_id: str, post_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        post = db.query(Post).filter(Post.id == post_id).first()
        if job and job.image_paths and post:
            post.image_urls = job.image_paths
            db.commit()
    finally:
        db.close()


async def _stage_publish_only(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        post = db.query(Post).filter(Post.id == job.post_id).first()
        _set(db, job, "publishing", "正在发布到小红书...")
        pr = await publish_service.publish_post(db=db, post=post)
        job.platform_post_id = pr.platform_post_id
        job.status = "completed"
        job.progress_message = "发布成功！"
        db.commit()
        logger.info(f"Job {job_id} completed: {job.post_title}")
    except Exception as e:
        logger.error(f"Publish failed: {e}")
        try:
            job.status = "failed"
            job.progress_message = str(e)[:200]
            job.error_message = str(e)
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _set(db, job, status, message):
    job.status = status
    job.progress_message = message
    db.commit()
