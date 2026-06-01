from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session

from adapters.ai.base import BaseAIAdapter, ReviewResult
from adapters.ai.claude_adapter import ClaudeAdapter
from core.exceptions import ReviewRejectedError
from models.post import Post, ReviewRecord
from utils.validators import validate_post_content

REVIEW_PASS_THRESHOLD = 6.0


class ReviewService:

    def __init__(self, ai_adapter: BaseAIAdapter | None = None) -> None:
        self._ai = ai_adapter or ClaudeAdapter()

    async def review_post(self, db: Session, post: Post) -> ReviewRecord:
        logger.info(f"Reviewing post: {post.id}")

        basic_issues = validate_post_content(
            title=post.title or "",
            body=post.body or "",
        )

        ai_result: ReviewResult | None = None
        try:
            ai_result = await self._ai.review_content(
                title=post.title or "",
                body=post.body or "",
                hashtags=post.hashtags or [],
            )
        except Exception as e:
            logger.warning(f"AI review failed, falling back to basic check: {e}")

        all_issues = list(basic_issues)
        total_score = 10.0

        if ai_result:
            all_issues.extend(ai_result.issues)
            total_score = ai_result.score
        elif basic_issues:
            total_score = 3.0
        else:
            total_score = 7.0

        passed = total_score >= REVIEW_PASS_THRESHOLD and not basic_issues

        result = "approved" if passed else "rejected"

        record = ReviewRecord(
            post_id=post.id,
            result=result,
            score=total_score,
            issues=all_issues if all_issues else None,
            reviewed_by="auto",
        )
        db.add(record)

        if passed:
            post.status = "approved"
            logger.info(f"Post {post.id} approved: score={total_score}")
        else:
            post.status = "rejected"
            logger.warning(
                f"Post {post.id} rejected: score={total_score}, issues={all_issues}"
            )

        db.commit()
        db.refresh(record)

        if not passed:
            raise ReviewRejectedError("; ".join(all_issues) if all_issues else "quality score too low")

        return record

    def approve_manually(self, db: Session, post: Post, reviewer: str = "human") -> ReviewRecord:
        logger.info(f"Manual approval of post: {post.id} by {reviewer}")
        record = ReviewRecord(
            post_id=post.id,
            result="approved",
            score=10.0,
            reviewed_by=reviewer,
        )
        post.status = "approved"
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def reject_manually(
        self, db: Session, post: Post, reason: str, reviewer: str = "human"
    ) -> ReviewRecord:
        logger.info(f"Manual rejection of post: {post.id} by {reviewer}: {reason}")
        record = ReviewRecord(
            post_id=post.id,
            result="rejected",
            score=0.0,
            issues=[reason],
            reviewed_by=reviewer,
        )
        post.status = "rejected"
        db.add(record)
        db.commit()
        db.refresh(record)
        return record


review_service = ReviewService()
