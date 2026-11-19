"""ModelGatewayHealth database model for provider circuit breaker and resilience tracking."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, UUIDMixin


class ModelGatewayHealth(Base, UUIDMixin, TimestampMixin):
    """Tracks circuit state, health metrics, and failure telemetry per (provider, model) pair."""
    __tablename__ = "model_gateway_health"
    __table_args__ = (
        UniqueConstraint("provider_name", "model_name", name="uq_provider_model_health"),
    )

    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    circuit_state: Mapped[str] = mapped_column(String(20), default="CLOSED", nullable=False, index=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_successes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_fallbacks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_failure_classification: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_state_change_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
