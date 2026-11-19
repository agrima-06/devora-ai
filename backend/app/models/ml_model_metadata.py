"""SQLAlchemy model for versioned ML model evaluation metrics and promotion records."""
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class MLModelMetadata(Base, UUIDMixin, TimestampMixin):
    """Tracks trained model artifacts, evaluation benchmarks, and promotion states."""
    __tablename__ = "ml_models"

    version: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    algorithm: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="LogisticRegression",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    accuracy: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    macro_f1: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    weighted_f1: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    metrics: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    training_sample_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    model_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    vectorizer_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    promotion_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
