from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user, get_db
from app.core.security import (
    access_token,
    clear_cookies,
    cookie_name,
    csrf_binding,
    digest,
    make_csrf,
    now,
    session_id,
    set_cookie,
    valid_csrf,
)
from app.models import AuthSession, RefreshToken, User
from app.schemas import LoginInput, RegisterInput, UserOutput
from app.services import auth

router = APIRouter(prefix="/auth", tags=["authentication"])


def session_response(request: Request, response: Response, session: AuthSession, token: str):
    settings = request.app.state.settings
    remaining = max(0, int((session.expires_at - now()).total_seconds()))
    set_cookie(
        response,
        settings,
        "access",
        access_token(settings, session.user_id, session.id),
        settings.access_token_minutes * 60,
    )
    set_cookie(response, settings, "refresh", token, remaining)
    set_cookie(response, settings, "csrf", make_csrf(settings, str(session.id)), 3600)


@router.get("/csrf")
def csrf(request: Request, response: Response):
    settings = request.app.state.settings
    try:
        binding = csrf_binding(request, settings)
    except HTTPException:
        binding = "anonymous"
        clear_cookies(response, settings)
    existing = request.cookies.get(cookie_name(settings, "csrf"), "")
    token = existing if valid_csrf(existing, settings, binding) else make_csrf(settings, binding)
    set_cookie(response, settings, "csrf", token, 3600)
    return {"csrf_token": token}


@router.post("/register", response_model=UserOutput, status_code=201)
def register(
    data: RegisterInput, request: Request, response: Response, db: Session = Depends(get_db)
):
    user = auth.register(db, data)
    session, token = auth.new_session(db, user, request.app.state.settings)
    db.commit()
    session_response(request, response, session, token)
    return user


@router.post("/login", response_model=UserOutput)
def login(data: LoginInput, request: Request, response: Response, db: Session = Depends(get_db)):
    user = auth.authenticate(db, data)
    session, token = auth.new_session(db, user, request.app.state.settings)
    db.commit()
    session_response(request, response, session, token)
    return user


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    token = request.cookies.get(cookie_name(settings, "refresh"), "")
    try:
        session, replacement = auth.rotate(db, token)
    except HTTPException as exc:
        failure = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        clear_cookies(failure, settings)
        return failure
    db.commit()
    session_response(request, response, session, replacement)
    return {"status": "ok"}


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    token = request.cookies.get(cookie_name(settings, "refresh"), "")
    if token:
        sid = session_id(token)
        session = db.scalar(select(AuthSession).where(AuthSession.id == sid).with_for_update())
        known = db.scalar(
            select(RefreshToken.id).where(
                RefreshToken.session_id == sid, RefreshToken.token_hash == digest(token)
            )
        )
        if session and known:
            session.revoked_at = now()
            db.commit()
    response = Response(status_code=204)
    clear_cookies(response, settings)
    return response


@router.get("/me", response_model=UserOutput)
def me(response: Response, user: User = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return user
