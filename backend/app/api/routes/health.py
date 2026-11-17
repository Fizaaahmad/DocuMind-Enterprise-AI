import logging
import os
from functools import lru_cache
from typing import Annotated, Literal

from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.config import BACKEND_ROOT

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    pgvector: Literal["ok", "unavailable"]
    schema_status: Literal["ok", "unavailable"] | None = Field(default=None, alias="schema")
    storage: Literal["ok", "unavailable"] | None = None


@router.get("/health", response_model=LivenessResponse)
def health() -> LivenessResponse:
    """Liveness does not depend on external services."""
    return LivenessResponse()


@lru_cache
def schema_head():
    return ScriptDirectory(str(BACKEND_ROOT / "alembic")).get_current_head()


@router.get("/health/ready", response_model=ReadinessResponse, response_model_exclude_none=True)
def readiness(
    response: Response, request: Request, db: Annotated[Session, Depends(get_db)]
) -> ReadinessResponse:
    try:
        db.execute(text("SELECT 1"))
        vector_available = db.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
        ).scalar_one()
    except SQLAlchemyError:
        logger.warning("Database readiness check failed", exc_info=False)
        response.status_code = 503
        return ReadinessResponse(status="degraded", database="unavailable", pgvector="unavailable")

    if not vector_available:
        response.status_code = 503
    extra = {}
    if request.app.state.settings.environment == "production":
        config = request.app.state.settings
        storage_ok = config.storage_path.is_dir() and os.access(config.storage_path, os.W_OK)
        try:
            schema_ok = (
                db.execute(text("SELECT version_num FROM alembic_version")).scalar()
                == schema_head()
            )
        except SQLAlchemyError:
            db.rollback()
            schema_ok = False
        extra = {
            "storage": "ok" if storage_ok else "unavailable",
            "schema": "ok" if schema_ok else "unavailable",
        }
        if not storage_ok or not schema_ok:
            response.status_code = 503
    return ReadinessResponse(
        status="ok" if response.status_code != 503 and vector_available else "degraded",
        database="ok",
        pgvector="ok" if vector_available else "unavailable",
        **extra,
    )
