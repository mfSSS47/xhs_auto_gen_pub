from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:12]
    )
    direction_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("content_directions.id"), nullable=False
    )
    account_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("accounts.id")
    )
    title: Mapped[str | None] = mapped_column(String(100))
    body: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list | None] = mapped_column(JSON)
    image_urls: Mapped[list | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    ai_model: Mapped[str | None] = mapped_column(String(50))
    generation_time_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, status={self.status})>"


class ReviewRecord(Base):
    __tablename__ = "review_records"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:12]
    )
    post_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("posts.id"), nullable=False
    )
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float | None] = mapped_column()
    issues: Mapped[list | None] = mapped_column(JSON)
    reviewed_by: Mapped[str] = mapped_column(String(20), default="auto")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:
        return f"<ReviewRecord(id={self.id}, result={self.result})>"


class PublishRecord(Base):
    __tablename__ = "publish_records"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:12]
    )
    post_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("posts.id"), nullable=False
    )
    account_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("accounts.id")
    )
    platform_post_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_msg: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self) -> str:
        return f"<PublishRecord(id={self.id}, status={self.status})>"
