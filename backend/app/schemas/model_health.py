"""Model Gateway Health and Resilience schemas (Phase 9 Stage 9.5)."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ModelCircuitBreakerStatus(BaseModel):
    """Detailed status of a specific model/provider circuit breaker."""
    key: str
    provider_name: str
    model_name: str
    state: str = Field(description="CLOSED, OPEN, or HALF_OPEN")
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    recent_failures_in_window: int = 0
    failure_threshold: int
    open_duration_seconds: float
    time_until_probe_seconds: Optional[float] = None
    last_failure_reason: Optional[str] = None
    last_failure_classification: Optional[str] = None
    last_failure_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    total_calls: int = 0
    total_failures: int = 0
    total_probes: int = 0

    model_config = ConfigDict(from_attributes=True)


class ModelGatewayMetrics(BaseModel):
    """Aggregate token and request metrics across the gateway."""
    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_retries: int = 0
    total_fallbacks: int = 0
    last_active_at: Optional[datetime] = None


class ModelGatewayHealthResponse(BaseModel):
    """System-level health and resilience overview of the Model Gateway."""
    status: str = Field(description="HEALTHY, DEGRADED, or UNAVAILABLE")
    circuit_breaker_enabled: bool
    active_primary_provider: str
    active_primary_model: str
    fallback_enabled: bool
    fallback_models: List[str]
    breakers: List[ModelCircuitBreakerStatus]
    metrics: ModelGatewayMetrics
    timestamp: datetime
