from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class ContentDirection(Base):
    __tablename__ = "content_directions"

    id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:12]
    )
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    target_audience: Mapped[str | None] = mapped_column(String(200))
    tone: Mapped[str | None] = mapped_column(String(20), default="casual")
    keywords: Mapped[list | None] = mapped_column(JSON)
    category: Mapped[str | None] = mapped_column(String(50))
    max_length: Mapped[int] = mapped_column(Integer, default=1000)
    image_count: Mapped[int] = mapped_column(Integer, default=1)
    extra_context: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<ContentDirection(id={self.id}, topic={self.topic})>"
