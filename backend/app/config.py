"""Application configuration and settings."""
from typing import List, Optional
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "Devora AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Security & Authentication
    SECRET_KEY: str = "devora-development-insecure-secret-key-change-in-production-32bytes"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/devora"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    # External Integrations
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"
    EMBEDDING_DIMENSION: int = 768
    USE_MOCK_LLM: bool = False
    GITHUB_TOKEN: Optional[str] = None

    # Semantic Memory Configuration
    MEMORY_SIMILARITY_THRESHOLD: float = 0.15
    MEMORY_MAX_RETRIEVAL_ITEMS: int = 5
    MEMORY_DEDUPLICATION_THRESHOLD: float = 0.92

    # Workspaces
    WORKSPACE_BASE_DIR: str = "/tmp/devora/repos"

    # Flaky Test Detection & Stability Configuration (Phase 9 Stage 9.2)
    FLAKY_DETECTION_ENABLED: bool = True
    FLAKY_REPEAT_RUNS_DEFAULT: int = 3
    FLAKY_REPEAT_RUNS_MIN: int = 3
    FLAKY_REPEAT_RUNS_MAX: int = 5
    FLAKY_TOTAL_TIMEOUT_SECONDS: int = 180

    # Sandbox Resilience & Dynamic Timeout Configuration (Phase 9 Stage 9.3)
    TEST_BASE_TIMEOUT_SECONDS: int = 60
    TEST_LARGE_SUITE_THRESHOLD: int = 50
    TEST_LARGE_SUITE_MULTIPLIER: float = 1.5
    TEST_MAX_TIMEOUT_SECONDS: int = 300
    TASK_MAX_TOTAL_BUDGET_SECONDS: int = 600
    SANDBOX_CONTAINER_MEMORY_LIMIT: str = "1500m"
    SANDBOX_CONTAINER_CPU_LIMIT: str = "2.0"
    SANDBOX_CONTAINER_PIDS_LIMIT: int = 100

    # Workflow Recovery Manager Configuration (Phase 9 Stage 9.4)
    RECOVERY_ENABLED: bool = True
    RECOVERY_HEARTBEAT_TIMEOUT_SECONDS: int = 120
    RECOVERY_MAX_ATTEMPTS: int = 3
    RECOVERY_LEASE_DURATION_SECONDS: int = 300

    # Model Gateway Circuit Breaker & Fallback Resilience (Phase 9 Stage 9.5)
    CIRCUIT_BREAKER_ENABLED: bool = True
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_FAILURE_WINDOW_SECONDS: int = 60
    CIRCUIT_BREAKER_OPEN_DURATION_SECONDS: int = 30
    CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS: int = 2
    CIRCUIT_BREAKER_SUCCESS_THRESHOLD: int = 2

    # Intelligent Retry Engine
    MODEL_RETRY_ENABLED: bool = True
    MODEL_RETRY_MAX_ATTEMPTS: int = 3
    MODEL_RETRY_BASE_DELAY_SECONDS: float = 1.0
    MODEL_RETRY_MAX_DELAY_SECONDS: float = 15.0
    MODEL_RETRY_MAX_ELAPSED_SECONDS: float = 45.0

    # Model Fallback Configuration
    MODEL_FALLBACK_ENABLED: bool = True
    MODEL_FALLBACK_MODEL: str = "gemini-1.5-flash"


settings = Settings()
