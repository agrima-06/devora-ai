"""Standardized Model Gateway Exception Hierarchy and Failure Taxonomy (Phase 9 Stage 9.5)."""
import re
from typing import Any, Dict, Optional
from app.core.exceptions import DevoraException

API_KEY_REGEX = re.compile(r"AIza[0-9A-Za-z-_]{30,45}")
TOKEN_REGEX = re.compile(r"x-access-token:[a-zA-Z0-9_\-]+@")
BEARER_REGEX = re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{20,}")


def scrub_credentials(text: str) -> str:
    """Scrub API keys and bearer tokens from error strings."""
    if not text:
        return ""
    sanitized = API_KEY_REGEX.sub("[REDACTED_API_KEY]", str(text))
    sanitized = TOKEN_REGEX.sub("x-access-token:[REDACTED]@", sanitized)
    sanitized = BEARER_REGEX.sub("Bearer [REDACTED]", sanitized)
    return sanitized


class LLMGenerationError(DevoraException):
    """Base exception for all LLM and provider generation failures (backward compatibility)."""
    pass


class ModelGatewayException(LLMGenerationError):
    """Base class for all Model Gateway domain exceptions."""

    def __init__(
        self,
        message: str,
        classification: str = "MODEL_PROVIDER_UNAVAILABLE",
        is_retryable: bool = False,
        trips_circuit: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        clean_msg = scrub_credentials(message)
        super().__init__(
            message=clean_msg,
            code=classification,
            status_code=503 if trips_circuit else 500,
            details=details or {},
        )
        self.classification = classification
        self.is_retryable = is_retryable
        self.trips_circuit = trips_circuit


class ProviderConnectionError(ModelGatewayException):
    """Network connection failure, socket reset, or DNS failure."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="PROVIDER_CONNECTION_ERROR",
            is_retryable=True,
            trips_circuit=True,
            details=details,
        )


class ProviderTimeoutError(ModelGatewayException):
    """Connection or read timeout connecting to model provider."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="PROVIDER_TIMEOUT",
            is_retryable=True,
            trips_circuit=True,
            details=details,
        )


class ProviderRateLimitedError(ModelGatewayException):
    """HTTP 429 rate limit or quota exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        det = details or {}
        if retry_after is not None:
            det["retry_after"] = retry_after
        super().__init__(
            message=message,
            classification="PROVIDER_RATE_LIMITED",
            is_retryable=True,
            trips_circuit=False,  # Rate limiting is handled via backoff unless threshold breached
            details=det,
        )
        self.retry_after = retry_after


class ProviderOverloadedError(ModelGatewayException):
    """HTTP 503 model overloaded or temporarily unavailable."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="PROVIDER_OVERLOADED",
            is_retryable=True,
            trips_circuit=True,
            details=details,
        )


class ProviderServerError(ModelGatewayException):
    """HTTP 500 or upstream provider internal crash."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="PROVIDER_SERVER_ERROR",
            is_retryable=True,
            trips_circuit=True,
            details=details,
        )


class ProviderAuthenticationError(ModelGatewayException):
    """HTTP 401/403 invalid API credentials or unauthorized access."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="PROVIDER_AUTHENTICATION_ERROR",
            is_retryable=False,
            trips_circuit=False,
            details=details,
        )


class ModelNotFoundError(ModelGatewayException):
    """HTTP 404 model name unrecognized or deprecated."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="MODEL_NOT_FOUND",
            is_retryable=False,
            trips_circuit=False,
            details=details,
        )


class ModelUnavailableError(ModelGatewayException):
    """Requested model is temporarily offline or unavailable in the target region."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="MODEL_UNAVAILABLE",
            is_retryable=True,
            trips_circuit=True,
            details=details,
        )


class InvalidModelRequestError(ModelGatewayException):
    """Client error: invalid parameters, prompt too long, or unsupported request."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="INVALID_MODEL_REQUEST",
            is_retryable=False,
            trips_circuit=False,
            details=details,
        )


class InvalidStructuredOutputError(ModelGatewayException):
    """Model output failed Pydantic schema validation or JSON decoding."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="INVALID_STRUCTURED_OUTPUT",
            is_retryable=True,  # May succeed on retry with fresh generation
            trips_circuit=False,
            details=details,
        )


class CircuitOpenError(ModelGatewayException):
    """Request rejected because provider/model circuit breaker is in OPEN state."""

    def __init__(
        self,
        provider: str,
        model: str,
        cooldown_remaining_seconds: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ):
        det = details or {}
        det.update({
            "provider": provider,
            "model": model,
            "cooldown_remaining_seconds": round(cooldown_remaining_seconds, 1),
        })
        super().__init__(
            message=f"Circuit breaker for provider '{provider}' and model '{model}' is OPEN. Cooldown remaining: {round(cooldown_remaining_seconds, 1)}s.",
            classification="CIRCUIT_OPEN",
            is_retryable=False,
            trips_circuit=False,
            details=det,
        )
        self.provider = provider
        self.model = model
        self.cooldown_remaining = cooldown_remaining_seconds


class RetryExhaustedError(ModelGatewayException):
    """Maximum retry attempts exceeded for current model."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="RETRY_EXHAUSTED",
            is_retryable=False,
            trips_circuit=False,
            details=details,
        )


class FallbackExhaustedError(ModelGatewayException):
    """All providers and fallback models in chain failed."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="FALLBACK_EXHAUSTED",
            is_retryable=False,
            trips_circuit=False,
            details=details,
        )


class ModelProviderUnavailableError(ModelGatewayException):
    """No viable provider or fallback is available to fulfill request."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="MODEL_PROVIDER_UNAVAILABLE",
            is_retryable=False,
            trips_circuit=True,
            details=details,
        )


class UserCancelledError(ModelGatewayException):
    """Workflow execution was cancelled by developer."""

    def __init__(self, message: str = "Model invocation cancelled.", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            classification="USER_CANCELLED",
            is_retryable=False,
            trips_circuit=False,
            details=details,
        )


def classify_provider_exception(exc: Exception) -> ModelGatewayException:
    """Classify arbitrary upstream or SDK exceptions into standardized ModelGatewayException."""
    if isinstance(exc, ModelGatewayException):
        return exc

    err_str = str(exc).lower()

    # Rate limiting (429)
    if "429" in err_str or "resource_exhausted" in err_str or "rate limit" in err_str or "quota" in err_str:
        retry_after = None
        # Extract possible retry after seconds
        match = re.search(r"retry[- ]after[:\s]+(\d+)", err_str)
        if match:
            try:
                retry_after = float(match.group(1))
            except ValueError:
                pass
        return ProviderRateLimitedError(f"Provider rate limit exceeded: {str(exc)}", retry_after=retry_after)

    # Overloaded / Unavailable (503)
    if "503" in err_str or "overloaded" in err_str or "service unavailable" in err_str:
        return ProviderOverloadedError(f"Provider service overloaded or unavailable: {str(exc)}")

    # Timeouts
    if "timeout" in err_str or "timed out" in err_str or "deadline exceeded" in err_str:
        return ProviderTimeoutError(f"Provider request timed out: {str(exc)}")

    # Connection failures
    if "connection" in err_str or "econnrefused" in err_str or "dns" in err_str or "network unreachable" in err_str:
        return ProviderConnectionError(f"Connection to model provider failed: {str(exc)}")

    # Authentication / Permissions (401, 403)
    if "401" in err_str or "403" in err_str or "unauthenticated" in err_str or "permission_denied" in err_str or "invalid api key" in err_str:
        return ProviderAuthenticationError(f"Provider authentication failed: {str(exc)}")

    # Model not found (404)
    if "404" in err_str or "not found" in err_str or "unsupported model" in err_str:
        return ModelNotFoundError(f"Requested model not found: {str(exc)}")

    # Server errors (500, 502, 504)
    if "500" in err_str or "502" in err_str or "504" in err_str or "internal server error" in err_str:
        return ProviderServerError(f"Provider internal server error: {str(exc)}")

    # Default to generic provider failure
    return ModelProviderUnavailableError(f"Provider failure: {str(exc)}")
