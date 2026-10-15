"""Environment-based, validated configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FM_", extra="ignore")

    app_name: str = "Future Mirror AI"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./future_mirror.db"
    secret_key: str = Field("dev-insecure-change-me-0123456789abcdef", min_length=16)
    access_token_minutes: int = 480
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # LLM provider abstraction. "none" = rule-based agents only (clearly labelled in the UI).
    llm_provider: Literal["none", "anthropic", "openai", "ollama"] = "none"
    llm_model: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    llm_timeout_seconds: float = 30.0

    # Execution controls
    agent_timeout_seconds: float = 20.0
    pipeline_timeout_seconds: float = 180.0
    presentation_pacing_ms: int = 450  # visible pause between stages; reported separately from compute time
    max_simulation_iterations: int = 20000

    # Automation (n8n). External actions disabled by default.
    n8n_base_url: str = ""
    n8n_api_key: str = ""
    external_actions_enabled: bool = False

    seed_demo_data: bool = True
    demo_password: str = "FutureMirror!2026"

    @field_validator("secret_key")
    @classmethod
    def _no_default_in_prod(cls, v: str, info):  # noqa: ANN001
        env = info.data.get("environment")
        if env == "production" and v.startswith("dev-insecure"):
            raise ValueError("FM_SECRET_KEY must be set in production")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
