import hashlib
import hmac
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request, Response
from pwdlib import PasswordHash

from app.core.config import Settings

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))


def now() -> datetime:
    return datetime.now(timezone.utc)


def secret(settings: Settings) -> str:
    if settings.auth_secret is None:
        raise HTTPException(503, "Authentication is not configured; set AUTH_SECRET")
    return settings.auth_secret.get_secret_value()


def cookie_name(settings: Settings, kind: str) -> str:
    return ("__Host-" if settings.cookie_secure else "") + f"dm_{kind}"


def set_cookie(response: Response, settings: Settings, kind: str, value: str, max_age: int):
    response.set_cookie(
        cookie_name(settings, kind),
        value,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def clear_cookies(response: Response, settings: Settings):
    for kind in ("access", "refresh", "csrf"):
        response.delete_cookie(
            cookie_name(settings, kind),
            path="/",
            secure=settings.cookie_secure,
            httponly=True,
            samesite="lax",
        )
    response.headers["Cache-Control"] = "no-store"


def session_id(token: str) -> uuid.UUID:
    try:
        return uuid.UUID(token.split(".", 1)[0])
    except (ValueError, AttributeError):
        raise HTTPException(401, "Session expired; please log in again") from None


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_binding(request: Request, settings: Settings) -> str:
    token = request.cookies.get(cookie_name(settings, "refresh"))
    return str(session_id(token)) if token else "anonymous"


def make_csrf(settings: Settings, binding: str) -> str:
    payload = f"{int(time.time())}.{secrets.token_urlsafe(24)}"
    signature = hmac.new(
        secret(settings).encode(), f"csrf:{binding}:{payload}".encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_csrf(request: Request, settings: Settings):
    if request.headers.get("origin") not in settings.cors_origins:
        raise HTTPException(403, "Untrusted request origin")
    header = request.headers.get("x-csrf-token", "")
    cookie = request.cookies.get(cookie_name(settings, "csrf"), "")
    if not header or not hmac.compare_digest(header.encode(), cookie.encode()):
        raise HTTPException(403, "Missing or invalid CSRF token")
    if not valid_csrf(header, settings, csrf_binding(request, settings)):
        raise HTTPException(403, "CSRF token expired or invalid; please try again")


def valid_csrf(token: str, settings: Settings, binding: str) -> bool:
    try:
        issued, nonce, signature = token.split(".")
        age = time.time() - int(issued)
        expected = hmac.new(
            secret(settings).encode(),
            f"csrf:{binding}:{issued}.{nonce}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if age < 0 or age > 3600 or not hmac.compare_digest(signature.encode(), expected.encode()):
            return False
        return True
    except ValueError:
        return False


def access_token(settings: Settings, user_id: uuid.UUID, sid: uuid.UUID) -> str:
    issued = now()
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": str(sid),
            "iat": issued,
            "exp": issued + timedelta(minutes=settings.access_token_minutes),
            "iss": "documind",
            "aud": "documind-api",
            "type": "access",
        },
        secret(settings),
        algorithm="HS256",
    )


def decode_access(settings: Settings, token: str) -> dict:
    try:
        claims = jwt.decode(
            token,
            secret(settings),
            algorithms=["HS256"],
            issuer="documind",
            audience="documind-api",
            options={"require": ["exp", "iat", "sub", "sid", "iss", "aud", "type"]},
        )
        if claims["type"] != "access":
            raise ValueError
        uuid.UUID(claims["sub"])
        uuid.UUID(claims["sid"])
        return claims
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(401, "Session expired; please log in again") from None
