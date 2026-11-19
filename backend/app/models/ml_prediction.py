"""SQLAlchemy model for ML Bug Classification predictions and audit telemetry."""
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class MLPrediction(Base, UUIDMixin, TimestampMixin):
    """Stores predictions made by the ML Bug Classifier for audit and continuous learning."""
    __tablename__ = "ml_predictions"

    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    input_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    error_sample_preview: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    predicted_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    top_probabilities: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    is_low_confidence: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    inference_time_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    verified_category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    is_correct: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )

    # Relationships
    task = relationship("Task", backref="ml_predictions")
