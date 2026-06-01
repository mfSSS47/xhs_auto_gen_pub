from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


def _gen_id() -> str:
    return uuid.uuid4().hex[:12]


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    requirements: Mapped[str | None] = mapped_column(Text, default="")
    image_paths: Mapped[list | None] = mapped_column(JSON, default=list)

    mode: Mapped[str] = mapped_column(String(20), default="direct", index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    progress_message: Mapped[str | None] = mapped_column(String(200), default="")
    error_message: Mapped[str | None] = mapped_column(Text, default="")

    direction_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("content_directions.id"), nullable=True)
    post_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("posts.id"), nullable=True)

    post_title: Mapped[str | None] = mapped_column(String(100), default="")
    post_body: Mapped[str | None] = mapped_column(Text, default="")
    hashtags: Mapped[list | None] = mapped_column(JSON, default=list)
    review_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_issues: Mapped[list | None] = mapped_column(JSON, default=list)
    platform_post_id: Mapped[str | None] = mapped_column(String(100), default="")

    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
