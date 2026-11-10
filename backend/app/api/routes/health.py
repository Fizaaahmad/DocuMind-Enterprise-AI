import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    pgvector: Literal["ok", "unavailable"]


@router.get("/health", response_model=LivenessResponse)
def health() -> LivenessResponse:
    """Liveness does not depend on external services."""
    return LivenessResponse()


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness(response: Response, db: Annotated[Session, Depends(get_db)]) -> ReadinessResponse:
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
    return ReadinessResponse(
        status="ok" if vector_available else "degraded",
        database="ok",
        pgvector="ok" if vector_available else "unavailable",
    )
