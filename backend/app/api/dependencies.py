import uuid
from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import cookie_name, decode_access, now
from app.db.session import session_scope
from app.models import AuthSession, User


def get_db(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.engine)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    settings = request.app.state.settings
    token = request.cookies.get(cookie_name(settings, "access"), "")
    claims = decode_access(settings, token)
    session = db.get(AuthSession, uuid.UUID(claims["sid"]))
    if (
        not session
        or session.revoked_at
        or session.expires_at <= now()
        or str(session.user_id) != claims["sub"]
    ):
        raise HTTPException(401, "Session expired; please log in again")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "User not found")
    return user
