from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="AGENTPROBE_", extra="ignore"
    )

    app_name: str = "AgentProbe"
    api_prefix: str = "/api/v1"
    storage_backend: Literal["memory", "mongodb"] = "memory"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "agentprobe"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    groq_target_model: str = "openai/gpt-oss-20b"
    demo_provider: Literal["auto", "deterministic", "groq"] = "auto"
    dataset_enabled: bool = True
    dataset_path: Path = Path("hackaprompt_local")
    dataset_sample_limit: int = 5_000
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
