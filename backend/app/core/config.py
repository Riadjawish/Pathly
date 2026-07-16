from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Pathly API"
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://pathly:pathly@localhost:5432/pathly"
    database_echo: bool = False

    secret_key: SecretStr = SecretStr("development-only-change-me-please")
    access_token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    refresh_token_expire_days: int = Field(default=30, ge=1, le=365)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "pathly-api"
    jwt_audience: str = "pathly-web"

    google_client_id: str | None = None
    frontend_base_url: str = "http://localhost:3000"

    gemini_api_key: SecretStr | None = None
    gemini_generation_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-2"
    gemini_embedding_dimensions: int = Field(default=768, ge=128, le=3072)
    gemini_retry_attempts: int = Field(default=5, ge=1, le=8)

    storage_backend: Literal["local", "s3"] = "local"
    local_storage_path: str = "./data/uploads"
    chroma_path: str = "./data/chroma"
    chroma_collection: str = "pathly-chunks"
    max_upload_size_mb: int = Field(default=25, ge=1, le=250)

    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod", "off"}:
                return False
            if normalized in {"development", "dev", "debug", "on"}:
                return True
        return value

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment == "production":
            secret = self.secret_key.get_secret_value()
            if len(secret) < 32 or secret == "development-only-change-me-please":
                raise ValueError("SECRET_KEY must be a unique value of at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
