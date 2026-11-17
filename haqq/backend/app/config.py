"""Runtime configuration. Every value can be overridden with an HAQQ_* environment variable."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HAQQ_", env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg2://haqq:haqq@localhost:5432/haqq"
    secret_key: str = "dev-only-change-me-haqq-secret-key-0123456789"
    access_token_minutes: int = 60 * 8
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8090"]

    # Object storage. "local" is an S3-compatible abstraction backed by the filesystem.
    storage_backend: str = "local"
    storage_path: Path = Path(__file__).resolve().parent.parent / "var" / "storage"
    max_upload_mb: int = 50

    # Background processing. "thread" runs the DB-backed job worker inside the API process;
    # "external" expects `python -m app.worker` to run separately; "inline" runs jobs synchronously
    # (tests).
    worker_mode: str = "thread"

    # OCR
    ocr_enabled: bool = True
    ocr_languages: str = "ara+eng"
    ocr_min_chars_per_page: int = 40

    # AI provider. "none" = deterministic engines only (no external model calls).
    llm_provider: str = "none"
    llm_model: str = "claude-opus-5-5"
    llm_effort: str = "medium"
    llm_timeout_seconds: float = 120.0
    llm_max_retries: int = 2
    anthropic_api_key: str | None = None
    embedding_dim: int = 256

    # Email notifications (SMTP). Empty host = in-app notifications only.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "haqq@example.com"

    rate_limit_login_per_minute: int = 10
    rate_limit_api_per_minute: int = 600
    seed_demo: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_production and s.secret_key.startswith("dev-only"):
        raise RuntimeError("HAQQ_SECRET_KEY must be set in production")
    return s
