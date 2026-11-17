import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, PostgresDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )

    app_name: str = "DocuMind API"
    environment: str = "development"
    database_url: PostgresDsn
    cors_origins: list[str] = ["http://localhost:3000"]
    auth_secret: SecretStr | None = None
    cookie_secure: bool = False
    allowed_hosts: list[str] = ["*"]
    json_max_bytes: int = Field(default=65536, ge=16384, le=1048576)
    worker_health_file: Path | None = None
    organization_max_documents: int = Field(default=10000, ge=1)
    organization_max_storage_bytes: int = Field(default=10 * 1024**3, ge=1024)
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
    analysis_max_characters: int = Field(default=500000, ge=1000, le=2000000)
    analysis_timeout_seconds: int = Field(default=120, ge=10, le=600)
    analysis_max_items: int = Field(default=500, ge=10, le=2000)
    embeddings_enabled: bool = False
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_revision: str = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    embedding_dimension: int = Field(default=384, ge=1, le=4096)
    embedding_cache_path: Path = BACKEND_ROOT / "var" / "models"
    embedding_batch_size: int = Field(default=16, ge=1, le=64)
    embedding_threads: int = Field(default=2, ge=1, le=8)
    indexing_timeout_seconds: int = Field(default=600, ge=30, le=3600)
    retrieval_limit: int = Field(default=6, ge=1, le=20)
    retrieval_min_similarity: float = Field(default=0.3, ge=-1, le=1)
    rag_context_characters: int = Field(default=12000, ge=1000, le=40000)
    llm_provider: str = "disabled"
    llm_model: str = "extractive-mock-v1"
    llm_api_key: SecretStr | None = None
    llm_timeout_seconds: int = Field(default=30, ge=1, le=90)
    llm_max_output_tokens: int = Field(default=1024, ge=64, le=4096)
    llm_temperature: float = Field(default=0, ge=0, le=2)
    ai_daily_requests: int = Field(default=100, ge=1, le=10000)
    ocr_enabled: bool = False
    tesseract_cmd: str = Field(default="tesseract", min_length=1, max_length=2048)
    ocr_tessdata_dir: Path | None = None
    ocr_language: str = Field(
        default="eng",
        pattern=r"^[A-Za-z][A-Za-z0-9_]*(\+[A-Za-z][A-Za-z0-9_]*){0,2}$",
        max_length=128,
    )
    ocr_dpi: int = Field(default=200, ge=72, le=400)
    ocr_min_text_characters: int = Field(default=20, ge=1, le=2000)
    ocr_max_pages: int = Field(default=20, ge=1, le=200)
    ocr_max_pixels: int = Field(default=12_000_000, ge=100_000, le=25_000_000)
    ocr_page_timeout_seconds: int = Field(default=30, ge=1, le=120)
    ocr_document_timeout_seconds: int = Field(default=180, ge=1, le=600)
    ocr_memory_limit_mb: int = Field(default=512, ge=256, le=2048)

    @field_validator("ocr_tessdata_dir", mode="before")
    @classmethod
    def optional_tessdata(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_security(self):
        if not self.embedding_cache_path.is_absolute():
            self.embedding_cache_path = (BACKEND_ROOT / self.embedding_cache_path).resolve()
        if self.llm_provider == "mock" and self.environment != "development":
            raise ValueError("The mock LLM provider is development-only")
        if self.ocr_tessdata_dir and not self.ocr_tessdata_dir.is_absolute():
            self.ocr_tessdata_dir = (BACKEND_ROOT / self.ocr_tessdata_dir).resolve()
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
            if not self.cors_origins or any(
                not origin.startswith("https://") for origin in self.cors_origins
            ):
                raise ValueError("Non-development origins must use HTTPS")
            from urllib.parse import urlsplit

            for origin in self.cors_origins:
                parsed = urlsplit(origin)
                if (
                    not parsed.hostname
                    or parsed.username
                    or parsed.password
                    or parsed.path
                    or parsed.query
                    or parsed.fragment
                    or "*" in origin
                ):
                    raise ValueError("Production CORS origins must be exact HTTPS origins")
            if self.environment == "production" and (
                not self.allowed_hosts or "*" in self.allowed_hosts
            ):
                raise ValueError("Production requires explicit ALLOWED_HOSTS")
            value = self.auth_secret.get_secret_value()
            if not value.strip() or "replace" in value.lower() or "change-me" in value.lower():
                raise ValueError("Production requires a generated AUTH_SECRET")
        return self


def secret_files(keys=("DATABASE_URL", "AUTH_SECRET", "LLM_API_KEY")):
    values = {}
    for key in keys:
        path = os.environ.get(key + "_FILE")
        if path:
            try:
                values[key.lower()] = Path(path).read_text(encoding="utf-8").strip()
            except OSError:
                raise ValueError(f"Cannot read {key}_FILE") from None
    return values


class MigrationSettings(BaseSettings):
    model_config = Settings.model_config
    database_url: PostgresDsn
    migration_statement_timeout_ms: int = Field(default=120000, ge=1000, le=3600000)


@lru_cache
def get_settings() -> Settings:
    return Settings(**secret_files())
