from __future__ import annotations

import time

from loguru import logger
from sqlalchemy.orm import Session

from adapters.ai.base import BaseAIAdapter, GeneratedPost
from adapters.ai.claude_adapter import ClaudeAdapter
from core.exceptions import AIGenerationError
from models.content import ContentDirection
from models.post import Post


class GenerationService:

    def __init__(self, ai_adapter: BaseAIAdapter | None = None) -> None:
        self._ai = ai_adapter or ClaudeAdapter()

    async def generate_post(
        self,
        db: Session,
        direction: ContentDirection,
    ) -> Post:
        logger.info(f"Starting generation for direction: {direction.id}")
        start = time.perf_counter()

        try:
            generated = await self._ai.generate_post(
                topic=direction.topic,
                tone=direction.tone or "casual",
                target_audience=direction.target_audience or "",
                keywords=direction.keywords or [],
                extra_context=direction.extra_context or "",
                max_length=direction.max_length or 1000,
            )
        except AIGenerationError:
            raise
        except Exception as e:
            raise AIGenerationError(str(e))

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        post = Post(
            direction_id=direction.id,
            title=generated.title,
            body=generated.body,
            hashtags=generated.hashtags,
            image_urls=[],
            status="pending_review",
            ai_model=self._ai.__class__.__name__,
            generation_time_ms=elapsed_ms,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        logger.info(f"Generated post: {post.id}, elapsed={elapsed_ms}ms")
        return post

    async def regenerate_post(
        self,
        db: Session,
        post: Post,
        feedback: str = "",
    ) -> Post:
        direction = db.query(ContentDirection).filter(
            ContentDirection.id == post.direction_id
        ).first()
        if not direction:
            direction = ContentDirection(topic="regenerate")

        extra = direction.extra_context or ""
        if feedback:
            extra = f"{extra}\n改进建议：{feedback}"

        logger.info(f"Regenerating post {post.id} with feedback: {feedback}")
        start = time.perf_counter()

        generated = await self._ai.generate_post(
            topic=direction.topic,
            tone=direction.tone or "casual",
            target_audience=direction.target_audience or "",
            keywords=direction.keywords or [],
            extra_context=extra,
            max_length=direction.max_length or 1000,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)

        post.title = generated.title
        post.body = generated.body
        post.hashtags = generated.hashtags
        post.status = "pending_review"
        post.generation_time_ms = elapsed_ms
        db.commit()
        db.refresh(post)
        logger.info(f"Regenerated post: {post.id}, elapsed={elapsed_ms}ms")
        return post


generation_service = GenerationService()
