"""SQLAlchemy declarative base, common mixins, and custom column types."""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import DateTime, JSON, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False


class Base(DeclarativeBase):
    """Root DeclarativeBase for all Devora models."""
    pass


class UUIDMixin:
    """Mixin that provides a standard UUID primary key."""
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """Mixin that provides timezone-aware created_at and updated_at fields."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class VectorType(TypeDecorator):
    """Dialect-adaptive vector type.
    Uses pgvector's Vector(dim) on PostgreSQL when available;
    falls back to JSON on SQLite or when pgvector is not installed.
    """
    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 768, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PGVECTOR_AVAILABLE:
            return dialect.type_descriptor(Vector(self.dim))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql" and PGVECTOR_AVAILABLE:
            return value
        return list(value) if hasattr(value, "__iter__") else value

    def process_result_value(self, value, dialect):
        return value
