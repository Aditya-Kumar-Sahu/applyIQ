from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ResumeProfile(Base):
    __tablename__ = "resume_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_resume_profiles_user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    raw_text: Mapped[str] = mapped_column(String)
    parsed_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    resume_embedding: Mapped[list[float]] = mapped_column(JSON, default=list)
    file_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="resume_profile")
