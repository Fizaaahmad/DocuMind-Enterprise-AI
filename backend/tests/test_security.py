import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize(
    "overrides",
    [
        {"environment": "production"},
        {"environment": "production", "auth_secret": "x" * 48, "cookie_secure": False},
        {"environment": "production", "auth_secret": "x" * 48, "cookie_secure": True},
        {"auth_secret": "short"},
    {"auth_secret": ""},
    {"cors_origins": ["*"]},
    ],
)
def test_insecure_configuration_is_rejected(overrides):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://test:test@localhost/test",
            **overrides,
        )
