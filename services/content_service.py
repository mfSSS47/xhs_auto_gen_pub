from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger
from sqlalchemy.orm import Session

from core.exceptions import NotFoundError, ValidationError
from models.content import ContentDirection
from utils.validators import validate_content_direction


class ContentService:

    def create_direction(
        self,
        db: Session,
        topic: str,
        tone: str = "casual",
        target_audience: str = "",
        keywords: list[str] | None = None,
        category: str = "",
        max_length: int = 1000,
        image_count: int = 1,
        extra_context: str = "",
    ) -> ContentDirection:
        validate_content_direction(
            topic=topic,
            tone=tone,
            keywords=keywords,
            max_length=max_length,
            image_count=image_count,
        )
        direction = ContentDirection(
            topic=topic.strip(),
            tone=tone,
            target_audience=target_audience,
            keywords=keywords or [],
            category=category,
            max_length=max_length,
            image_count=image_count,
            extra_context=extra_context,
            status="pending",
        )
        db.add(direction)
        db.commit()
        db.refresh(direction)
        logger.info(f"Created content direction: {direction.id} - {direction.topic}")
        return direction

    def get_direction(self, db: Session, direction_id: str) -> ContentDirection:
        direction = db.query(ContentDirection).filter(
            ContentDirection.id == direction_id
        ).first()
        if not direction:
            raise NotFoundError("ContentDirection", direction_id)
        return direction

    def list_directions(
        self, db: Session, limit: int = 20, offset: int = 0
    ) -> list[ContentDirection]:
        return (
            db.query(ContentDirection)
            .order_by(ContentDirection.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update_status(self, db: Session, direction_id: str, status: str) -> ContentDirection:
        direction = self.get_direction(db, direction_id)
        direction.status = status
        direction.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(direction)
        logger.info(f"Updated direction {direction_id} status to {status}")
        return direction

    def delete_direction(self, db: Session, direction_id: str) -> None:
        direction = self.get_direction(db, direction_id)
        db.delete(direction)
        db.commit()
        logger.info(f"Deleted content direction: {direction_id}")


content_service = ContentService()
