from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_run_id: Mapped[str | None] = mapped_column(String, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=True)
    agent_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    node: Mapped[str] = mapped_column(String, nullable=False)
    input_summary_hash: Mapped[str] = mapped_column(String, nullable=False)
    output_summary_hash: Mapped[str] = mapped_column(String, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
