"""Allowlisted operational logs. Never serialize exception values or HTTP inputs."""

import json
import logging
import time
import uuid
from contextvars import ContextVar

request_id = ContextVar("request_id", default=None)


class SafeJSON(logging.Formatter):
    def format(self, record):
        # Application call sites use fixed messages, never request/document content.
        data = {
            "level": record.levelname,
            "logger": record.name,
            "event": record.msg,
            "request_id": request_id.get(),
        }
        for key in (
            "job_id",
            "document_id",
            "organization_id",
            "kind",
            "attempt",
            "duration_ms",
            "status",
            "route",
        ):
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data, default=str)


def configure_logs():
    handler = logging.StreamHandler()
    handler.setFormatter(SafeJSON())
    # Even development access logs must not echo query strings or exception
    # values. Keep one structured, allowlisted stream across server/job logs.
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("app", "uvicorn.error", "sqlalchemy.pool"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False


async def log_request(request, call_next):
    try:
        identifier = uuid.UUID(request.headers.get("x-request-id", "")).hex
    except ValueError:
        identifier = uuid.uuid4().hex
    token = request_id.set(identifier)
    started = time.monotonic()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = identifier
        logging.getLogger("app.http").info(
            "request_complete",
            extra={
                "status": response.status_code,
                "route": getattr(request.scope.get("route"), "path", "unmatched"),
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
        return response
    finally:
        request_id.reset(token)
