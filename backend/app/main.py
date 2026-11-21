import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.demo import router as demo_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.operations import router as operations_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.structured import router as structured_router
from app.core.body_limit import BodyLimit
from app.core.config import Settings, get_settings
from app.core.observability import configure_logs, log_request
from app.core.security import verify_csrf
from app.db.session import build_engine
from app.documents.limits import UploadLimitMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    configure_logs()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = build_engine(str(config.database_url), demo_pool=config.demo_mode,
                              session_pooler=bool(config.demo_supabase_project_ref))
        app.state.engine = engine
        try:
            if config.demo_mode:
                from sqlalchemy.orm import Session

                from app.core.demo import validate_dataset
                with Session(engine) as db:
                    validate_dataset(db, config)
            yield
        finally:
            engine.dispose()

    app = FastAPI(title=config.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = config
    from app.core.demo import DemoEntryLimiter
    app.state.demo_entry_limiter = DemoEntryLimiter(config.demo_entry_limit)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logging.getLogger("app.http").error("database_request_failed")
        return JSONResponse({"detail": "Database temporarily unavailable; please retry"}, 503)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        if config.demo_mode:
            from app.core.demo import READ_ONLY_MESSAGE, allowed
            if not allowed(request.method, request.url.path):
                return JSONResponse({"detail": READ_ONLY_MESSAGE}, status_code=403,
                                    headers={"Cache-Control": "no-store"})
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            try:
                verify_csrf(request, config)
            except HTTPException as exc:
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith(("/api/v1/auth", "/api/v1/organizations")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Pydantic's default response includes raw input, which can contain passwords.
        errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Accept", "Content-Type", "X-CSRF-Token"],
    )
    app.add_middleware(UploadLimitMiddleware, limit=config.upload_max_bytes)
    app.add_middleware(BodyLimit, limit=config.json_max_bytes)
    if config.allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(demo_router, prefix="/api/v1")
    app.include_router(organizations_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(intelligence_router, prefix="/api/v1")
    app.include_router(structured_router, prefix="/api/v1")
    app.include_router(operations_router, prefix="/api/v1")
    app.middleware("http")(log_request)
    return app
