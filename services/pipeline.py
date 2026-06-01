from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from loguru import logger
from sqlalchemy.orm import Session

from core.exceptions import (
    AIGenerationError,
    AITimeoutError,
    PublishError,
    PublishTimeoutError,
    ReviewRejectedError,
)
from models.content import ContentDirection
from models.database import SessionLocal
from models.post import Post, PublishRecord, ReviewRecord
from services.account_service import account_service
from services.content_service import content_service
from services.generation_service import generation_service
from services.publish_service import publish_service
from services.review_service import review_service
from adapters.ai.claude_adapter import cleanup_claude_files


@dataclass
class PipelineResult:
    direction_id: str
    post_id: str | None = None
    success: bool = False
    stage: str = "init"
    error: str | None = None
    post_title: str | None = None
    post_body: str | None = None
    hashtags: list[str] = field(default_factory=list)
    review_score: float | None = None
    review_issues: list[str] = field(default_factory=list)
    publish_record_id: str | None = None
    platform_post_id: str | None = None


class ContentPipeline:
    """自动化内容生成与发布流水线。

    流程: 创建方向 -> 生成内容 -> 质量审核 -> 自动发布
    """

    async def run_full(
        self,
        topic: str,
        tone: str = "casual",
        target_audience: str = "",
        keywords: list[str] | None = None,
        category: str = "",
        max_length: int = 1000,
        image_count: int = 1,
        extra_context: str = "",
        auto_publish: bool = True,
        account_id: str | None = None,
    ) -> PipelineResult:
        logger.info(f"=== Starting full pipeline for topic: {topic} ===")
        result = PipelineResult(direction_id="")

        db = SessionLocal()
        try:
            direction = await self._stage_create_direction(
                db, result, topic, tone, target_audience, keywords,
                category, max_length, image_count, extra_context,
            )
            if not direction:
                return result

            post = await self._stage_generate(db, result, direction)
            if not post:
                return result

            review_record = await self._stage_review(db, result, post)
            if not review_record:
                return result

            if auto_publish:
                await self._stage_publish(db, result, post, account_id)

            result.success = True
            logger.info(f"=== Pipeline completed successfully: {result.post_id} ===")
            return result

        except Exception as e:
            logger.error(f"Pipeline unexpected error: {e}")
            result.error = str(e)
            result.success = False
            return result
        finally:
            db.close()
            cleanup_claude_files()

    async def _stage_create_direction(
        self,
        db: Session,
        result: PipelineResult,
        topic: str,
        tone: str,
        target_audience: str,
        keywords: list[str] | None,
        category: str,
        max_length: int,
        image_count: int,
        extra_context: str,
    ) -> ContentDirection | None:
        result.stage = "create_direction"
        try:
            direction = content_service.create_direction(
                db=db,
                topic=topic,
                tone=tone,
                target_audience=target_audience,
                keywords=keywords,
                category=category,
                max_length=max_length,
                image_count=image_count,
                extra_context=extra_context,
            )
            result.direction_id = direction.id
            logger.info(f"[Stage 1/4] Content direction created: {direction.id}")
            return direction
        except Exception as e:
            logger.error(f"[Stage 1/4] Failed: {e}")
            result.error = f"create_direction: {e}"
            return None

    async def _stage_generate(
        self,
        db: Session,
        result: PipelineResult,
        direction: ContentDirection,
    ) -> Post | None:
        result.stage = "generate"
        try:
            post = await generation_service.generate_post(db=db, direction=direction)
            result.post_id = post.id
            result.post_title = post.title
            result.post_body = post.body
            result.hashtags = post.hashtags or []
            logger.info(f"[Stage 2/4] Content generated: {post.id} - {post.title}")
            return post
        except (AIGenerationError, AITimeoutError) as e:
            logger.error(f"[Stage 2/4] Generation failed: {e}")
            result.error = f"generate: {e}"
            content_service.update_status(db, direction.id, "generation_failed")
            return None
        except Exception as e:
            logger.error(f"[Stage 2/4] Unexpected error: {e}")
            result.error = f"generate: {e}"
            return None

    async def _stage_review(
        self,
        db: Session,
        result: PipelineResult,
        post: Post,
    ) -> ReviewRecord | None:
        result.stage = "review"
        try:
            record = await review_service.review_post(db=db, post=post)
            result.review_score = record.score
            result.review_issues = record.issues or []
            logger.info(
                f"[Stage 3/4] Review completed: {record.result}, score={record.score}"
            )
            return record
        except ReviewRejectedError as e:
            logger.warning(f"[Stage 3/4] Content rejected: {e}")
            result.error = f"review_rejected: {e}"
            return None
        except Exception as e:
            logger.error(f"[Stage 3/4] Review error: {e}")
            result.error = f"review: {e}"
            return None

    async def _stage_publish(
        self,
        db: Session,
        result: PipelineResult,
        post: Post,
        account_id: str | None,
    ) -> PublishRecord | None:
        result.stage = "publish"
        try:
            record = await publish_service.publish_post(
                db=db, post=post, account_id=account_id,
            )
            result.publish_record_id = record.id
            result.platform_post_id = record.platform_post_id
            logger.info(
                f"[Stage 4/4] Published: platform_id={record.platform_post_id}"
            )
            return record
        except (PublishError, PublishTimeoutError) as e:
            logger.error(f"[Stage 4/4] Publish failed: {e}")
            result.error = f"publish: {e}"
            return None
        except Exception as e:
            logger.error(f"[Stage 4/4] Unexpected error: {e}")
            result.error = f"publish: {e}"
            return None

    async def run_generate_only(
        self,
        topic: str,
        tone: str = "casual",
        target_audience: str = "",
        keywords: list[str] | None = None,
        max_length: int = 1000,
        extra_context: str = "",
    ) -> PipelineResult:
        """仅生成内容，不进行审核和发布。"""
        logger.info(f"=== Generate-only pipeline for topic: {topic} ===")
        result = PipelineResult(direction_id="")

        db = SessionLocal()
        try:
            direction = content_service.create_direction(
                db=db, topic=topic, tone=tone,
                target_audience=target_audience,
                keywords=keywords, max_length=max_length,
                extra_context=extra_context,
            )
            result.direction_id = direction.id

            post = await self._stage_generate(db, result, direction)
            if post:
                result.success = True
            return result
        finally:
            db.close()


content_pipeline = ContentPipeline()
