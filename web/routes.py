from __future__ import annotations

import os
import uuid

from flask import Blueprint, current_app, jsonify, render_template, request
from sqlalchemy.orm import Session

from models.content import ContentDirection
from models.database import SessionLocal
import models.content  # noqa: F401
import models.post     # noqa: F401
import models.user     # noqa: F401
from models.post import Post
from web.models import Job

main_bp = Blueprint("main", __name__)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/status/<job_id>")
def status(job_id: str):
    return render_template("status.html", job_id=job_id)


@main_bp.route("/jobs")
def job_list():
    db = SessionLocal()
    try:
        jobs = db.query(Job).order_by(Job.created_at.desc()).limit(30).all()
        return render_template("job_list.html", jobs=jobs)
    finally:
        db.close()


# ── API ──────────────────────────────────────────────

@main_bp.route("/api/jobs", methods=["POST"])
def api_create_job():
    title = request.form.get("title", "").strip()
    requirements = request.form.get("requirements", "").strip()
    mode = request.form.get("mode", "direct").strip()

    if mode not in ("direct", "preview"):
        mode = "direct"

    if not title:
        return jsonify({"error": "标题不能为空"}), 400
    if not requirements:
        return jsonify({"error": "内容要求不能为空"}), 400

    job = Job(title=title, requirements=requirements, mode=mode, status="queued")
    db = SessionLocal()
    try:
        db.add(job)
        db.flush()  # get job.id

        # Save uploaded images
        upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], job.id)
        os.makedirs(upload_dir, exist_ok=True)

        image_paths = []
        files = request.files.getlist("images")
        for f in files:
            if f.filename and _allowed_file(f.filename):
                safe_name = f"{uuid.uuid4().hex[:8]}{os.path.splitext(f.filename)[1]}"
                save_path = os.path.join(upload_dir, safe_name)
                f.save(save_path)
                image_paths.append(os.path.abspath(save_path))

        job.image_paths = image_paths
        db.commit()

        return jsonify({"job_id": job.id, "status": job.status})
    finally:
        db.close()


@main_bp.route("/api/jobs", methods=["GET"])
def api_list_jobs():
    db = SessionLocal()
    try:
        jobs = db.query(Job).order_by(Job.created_at.desc()).limit(30).all()
        return jsonify([
            {
                "id": j.id,
                "title": j.title,
                "status": j.status,
                "progress_message": j.progress_message,
                "created_at": j.created_at.isoformat() if j.created_at else None,
            }
            for j in jobs
        ])
    finally:
        db.close()


@main_bp.route("/api/jobs/<job_id>", methods=["GET"])
def api_get_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return jsonify({"error": "Job not found"}), 404
        return jsonify({
            "id": job.id,
            "title": job.title,
            "requirements": job.requirements,
            "mode": job.mode,
            "image_count": len(job.image_paths or []),
            "status": job.status,
            "progress_message": job.progress_message,
            "error_message": job.error_message,
            "post_title": job.post_title,
            "post_body": job.post_body,
            "hashtags": job.hashtags,
            "review_score": job.review_score,
            "review_issues": job.review_issues,
            "platform_post_id": job.platform_post_id,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        })
    finally:
        db.close()


@main_bp.route("/api/jobs/<job_id>/publish", methods=["POST"])
def api_publish_job(job_id: str):
    """Approve and trigger publish for a preview-mode job."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return jsonify({"error": "Job not found"}), 404
        if job.status != "awaiting_approval":
            return jsonify({"error": f"Job is not awaiting approval (current: {job.status})"}), 400
        job.status = "approved"
        job.progress_message = "User approved, publishing..."
        db.commit()
        return jsonify({"job_id": job.id, "status": "approved"})
    finally:
        db.close()


@main_bp.route("/api/post/<post_id>", methods=["GET"])
def api_get_post(post_id: str):
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return jsonify({"error": "Post not found"}), 404
        return jsonify({
            "id": post.id,
            "title": post.title,
            "body": post.body,
            "hashtags": post.hashtags,
            "status": post.status,
            "created_at": post.created_at.isoformat() if post.created_at else None,
        })
    finally:
        db.close()
