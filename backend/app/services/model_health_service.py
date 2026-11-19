"""Model Health Service: persists and queries circuit breaker health states and metrics."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gateway.circuit_breaker import CircuitBreakerRegistry
from app.agents.gateway.gateway import ModelGateway
from app.core.exceptions import NotFoundException
from app.core.logging import get_logger
from app.models.model_gateway_health import ModelGatewayHealth
from app.schemas.model_health import (
    ModelCircuitBreakerStatus,
    ModelGatewayHealthResponse,
    ModelGatewayMetrics,
)

logger = get_logger("model_health_service")


class ModelHealthService:
    """Coordinates persistence, querying, and resets for model provider health."""

    def __init__(self, gateway: Optional[ModelGateway] = None):
        self.gateway = gateway or ModelGateway.get_instance()
        self.registry = CircuitBreakerRegistry.get_instance()

    async def sync_health_to_db(self, db: AsyncSession) -> None:
        """Upsert current in-memory circuit breaker metrics into the database."""
        # Ensure breakers exist for configured primary & fallbacks
        self.gateway.get_health_status()
        breakers = self.registry.list_breakers()

        for b in breakers:
            metrics = b.get_metrics()
            stmt = select(ModelGatewayHealth).where(
                ModelGatewayHealth.provider_name == b.provider_name,
                ModelGatewayHealth.model_name == b.model_name,
            )
            result = await db.execute(stmt)
            record = result.scalar_one_or_none()

            last_fail_at = (
                datetime.fromtimestamp(metrics["last_failure_at"], tz=timezone.utc)
                if metrics.get("last_failure_at")
                else None
            )
            last_succ_at = (
                datetime.fromtimestamp(metrics["last_success_at"], tz=timezone.utc)
                if metrics.get("last_success_at")
                else None
            )
            last_state_at = (
                datetime.fromtimestamp(metrics["last_state_change_at"], tz=timezone.utc)
                if metrics.get("last_state_change_at")
                else datetime.now(timezone.utc)
            )

            if record:
                record.circuit_state = metrics["circuit_state"]
                record.consecutive_failures = metrics["consecutive_failures"]
                record.consecutive_successes = metrics["consecutive_successes"]
                record.total_calls = metrics["total_calls"]
                record.total_failures = metrics["total_failures"]
                record.total_retries = metrics["total_retries"]
                record.total_fallbacks = metrics["total_fallbacks"]
                record.average_latency_ms = metrics["average_latency_ms"]
                record.last_failure_reason = metrics.get("last_failure_reason")
                record.last_failure_classification = metrics.get("last_failure_classification")
                record.last_failure_at = last_fail_at
                record.last_success_at = last_succ_at
                record.last_state_change_at = last_state_at
            else:
                record = ModelGatewayHealth(
                    provider_name=b.provider_name,
                    model_name=b.model_name,
                    circuit_state=metrics["circuit_state"],
                    consecutive_failures=metrics["consecutive_failures"],
                    consecutive_successes=metrics["consecutive_successes"],
                    total_calls=metrics["total_calls"],
                    total_failures=metrics["total_failures"],
                    total_retries=metrics["total_retries"],
                    total_fallbacks=metrics["total_fallbacks"],
                    average_latency_ms=metrics["average_latency_ms"],
                    last_failure_reason=metrics.get("last_failure_reason"),
                    last_failure_classification=metrics.get("last_failure_classification"),
                    last_failure_at=last_fail_at,
                    last_success_at=last_succ_at,
                    last_state_change_at=last_state_at,
                )
                db.add(record)

        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.warning("sync_health_to_db_failed", error=str(e))

    def get_health_overview(self) -> ModelGatewayHealthResponse:
        """Retrieve complete live health overview from ModelGateway."""
        raw_health = self.gateway.get_health_status()
        return ModelGatewayHealthResponse(**raw_health)

    async def reset_breaker(
        self,
        provider_name: str,
        model_name: str,
        db: Optional[AsyncSession] = None,
    ) -> ModelCircuitBreakerStatus:
        """Reset a specific circuit breaker back to CLOSED state."""
        key = f"{provider_name}:{model_name}"
        breaker = self.registry.get_breaker(provider_name, model_name)
        breaker.reset()
        logger.info("circuit_breaker_manually_reset", key=key)

        if db:
            await self.sync_health_to_db(db)

        return ModelCircuitBreakerStatus(**breaker.to_status_dict())
