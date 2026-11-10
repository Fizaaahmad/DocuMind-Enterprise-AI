from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ROOT / ".env", extra="ignore")

    app_name: str = "DocuMind API"
    environment: str = "development"
    database_url: PostgresDsn
    cors_origins: list[str] = ["http://localhost:3000"]
    auth_secret: SecretStr | None = None
    cookie_secure: bool = False
    access_token_minutes: int = Field(default=10, ge=1, le=60)
    session_days: int = Field(default=7, ge=1, le=30)
    storage_path: Path = BACKEND_ROOT / "var" / "documents"
    upload_max_bytes: int = Field(default=20 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024)
    chunk_size: int = Field(default=1200, ge=100, le=10000)
    chunk_overlap: int = Field(default=200, ge=0)
    extraction_max_characters: int = Field(default=2_000_000, ge=1000, le=10_000_000)
    extraction_max_pages: int = Field(default=1000, ge=1, le=10000)
    docx_max_uncompressed_bytes: int = Field(default=40 * 1024 * 1024, ge=1024)
    processing_timeout_seconds: int = Field(default=60, ge=5, le=600)
    worker_poll_seconds: float = Field(default=2, ge=0.1, le=60)
    worker_max_attempts: int = Field(default=3, ge=1, le=10)
    processing_max_chunks: int = Field(default=10000, ge=100, le=100000)

    @model_validator(mode="after")
    def validate_security(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if not self.storage_path.is_absolute():
            self.storage_path = (BACKEND_ROOT / self.storage_path).resolve()
        if self.auth_secret is not None and len(self.auth_secret.get_secret_value().encode()) < 32:
            raise ValueError("AUTH_SECRET must contain at least 32 bytes")
        if "*" in self.cors_origins:
            raise ValueError("Credentialed authentication requires explicit CORS origins")
        if self.environment != "development":
            if not self.auth_secret or not self.cookie_secure:
                raise ValueError(
                    "Non-development environments require AUTH_SECRET and secure cookies"
                )
            if any(not origin.startswith("https://") for origin in self.cors_origins):
                raise ValueError("Non-development origins must use HTTPS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
