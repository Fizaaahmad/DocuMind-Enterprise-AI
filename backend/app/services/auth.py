import secrets
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import DUMMY_HASH, digest, now, passwords, session_id
from app.models import AuthSession, RefreshToken, User
from app.schemas import LoginInput, RegisterInput


def register(db: Session, data: RegisterInput) -> User:
    user = User(email=str(data.email), name=data.name, password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Unable to register with that email") from None
    return user


def authenticate(db: Session, data: LoginInput) -> User:
    user = db.scalar(select(User).where(User.email == str(data.email)).with_for_update())
    valid = passwords.verify(data.password, user.password_hash if user else DUMMY_HASH)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    if user.locked_until and user.locked_until > now():
        raise HTTPException(429, "Too many login attempts; try again later")
    if not valid:
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= 5:
            user.locked_until = now() + timedelta(minutes=5)
            user.failed_logins = 0
        db.commit()
        raise HTTPException(401, "Invalid email or password")
    user.failed_logins = 0
    user.locked_until = None
    return user


def issue_refresh(db: Session, session: AuthSession) -> str:
    token = f"{session.id}.{secrets.token_urlsafe(48)}"
    db.add(RefreshToken(session_id=session.id, token_hash=digest(token)))
    return token


def new_session(db: Session, user: User, settings: Settings) -> tuple[AuthSession, str]:
    session = AuthSession(user_id=user.id, expires_at=now() + timedelta(days=settings.session_days))
    db.add(session)
    db.flush()
    return session, issue_refresh(db, session)


def rotate(db: Session, token: str) -> tuple[AuthSession, str]:
    # Lock the session family first: simultaneous uses of a token serialize in PostgreSQL.
    session = db.scalar(
        select(AuthSession).where(AuthSession.id == session_id(token)).with_for_update()
    )
    if not session or session.revoked_at or session.expires_at <= now():
        raise HTTPException(401, "Session expired; please log in again")
    record = db.scalar(
        select(RefreshToken).where(
            RefreshToken.session_id == session.id, RefreshToken.token_hash == digest(token)
        )
    )
    if not record:
        raise HTTPException(401, "Invalid refresh token")
    if record.consumed_at:
        session.revoked_at = now()
        db.commit()  # Persist replay revocation even though the response is an error.
        raise HTTPException(401, "Refresh token reuse detected; please log in again")
    record.consumed_at = now()
    return session, issue_refresh(db, session)
