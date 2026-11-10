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

    @model_validator(mode="after")
    def validate_security(self):
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
