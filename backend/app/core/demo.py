"""Fail-closed public snapshot policy. Normal application mode never uses it."""

import hashlib
import math
import re
import threading
import time
from collections import deque
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, func, select, text

from app.core.security import digest, now
from app.models import AuthSession, Membership, Organization, RefreshToken, User

READ_ONLY_MESSAGE = (
    "This portfolio demo is read-only. This action is available in the full application."
)
UUID = r"[0-9a-fA-F-]{36}"
# Deliberately enumerate endpoints, not HTTP methods alone. New routes default to denied.
READS = [
    r"health(?:/ready)?",
    r"auth/(?:csrf|me)",
    r"demo",
    r"organizations",
    rf"organizations/{UUID}(?:/members)?",
    rf"organizations/{UUID}/documents(?:/(?:config|{UUID}(?:/(?:content|download))?))?",
    rf"organizations/{UUID}/intelligence/(?:status|conversations(?:/{UUID}/messages)?)",
    rf"organizations/{UUID}/structured/(?:templates|obligations|documents/{UUID}/revisions|runs(?:/{UUID}(?:/(?:sections|export))?)?)",
    rf"organizations/{UUID}/operations/(?:summary|items|members|activity|export)",
]
READ_PATTERNS = [re.compile(r"/api/v1/" + path + r"/?$") for path in READS]
AUTH_WRITES = {"/api/v1/demo/enter", "/api/v1/auth/refresh", "/api/v1/auth/logout"}


class DemoEntryLimiter:
    """Bounded process-global entry window, not a claimed per-IP limit."""
    def __init__(self, limit, clock=time.monotonic):
        self.limit, self.clock = limit, clock
        self.entries = deque()
        self.lock = threading.Lock()

    def check(self):
        with self.lock:
            current = self.clock()
            while self.entries and self.entries[0] <= current - 60:
                self.entries.popleft()
            if len(self.entries) >= self.limit:
                delay = max(1, math.ceil(60 - (current - self.entries[0])))
                raise HTTPException(429, "Demo entry is busy; please retry shortly",
                                    headers={"Retry-After": str(delay)})
            self.entries.append(current)


def allowed(method, path):
    if method == "POST":
        return path.rstrip("/") in AUTH_WRITES
    # OPTIONS performs no route execution. CORS middleware handles preflight.
    if method in {"GET", "HEAD", "OPTIONS"}:
        return any(pattern.fullmatch(path) for pattern in READ_PATTERNS) or (
            method == "OPTIONS" and path.rstrip("/") in AUTH_WRITES
        )
    return False


def viewer(db, settings, *, lock=False):
    statement = select(User).where(User.id == settings.demo_viewer_id)
    if lock:
        statement = statement.with_for_update()
    user = db.scalar(statement)
    memberships = db.scalars(
        select(Membership).where(Membership.user_id == settings.demo_viewer_id)
    ).all()
    if (
        not user
        or len(memberships) != 1
        or memberships[0].organization_id != settings.demo_organization_id
        or memberships[0].role != "member"
    ):
        raise HTTPException(503, "Demo dataset is not configured correctly")
    return user


def validate_dataset(db, settings):
    """Reject accidentally pointing a public deployment at another dataset."""
    from app.models import AnalysisRun, Document, DocumentJob

    viewer(db, settings)
    if db.scalar(select(func.count()).select_from(Organization)) != 1:
        raise ValueError("Demo database must contain exactly one fictional organization")
    documents = db.scalars(select(Document)).all()
    if not documents:
        raise ValueError("Demo database has no prepared documents")
    for document in documents:
        if (
            document.organization_id != settings.demo_organization_id
            or document.source_metadata.get("public_demo") is not True
            or document.status != "completed"
            or document.deleted_at
        ):
            raise ValueError("Demo documents must be fictional, completed snapshot records")
        from app.documents.storage import LocalStorage

        path = LocalStorage(settings.storage_path).path(document.organization_id, document.id)
        if not path.is_file():
            raise ValueError("Demo original sample file is missing")
        with path.open("rb") as file:
            if hashlib.file_digest(file, "sha256").hexdigest() != document.checksum:
                raise ValueError("Demo original sample file does not match its stored checksum")
    for model in (DocumentJob, AnalysisRun):
        if db.scalar(
            select(func.count())
            .select_from(model)
            .where(model.state.in_(["pending", "running", "processing"]))
        ):
            raise ValueError("Demo dataset must not contain unfinished jobs")
    if settings.demo_supabase_project_ref:
        from app.demo.bundle import validate_installed_bundle, validate_runtime_role
        validate_runtime_role(db)
        validate_installed_bundle(db, settings)


def session_capacity(db, settings):
    # PostgreSQL advisory transaction lock serializes entry/refresh and cleanup
    # without granting UPDATE on business tables to the runtime role.
    db.execute(text("SELECT pg_advisory_xact_lock(74021963)"))
    ids = db.scalars(
        select(AuthSession.id)
        .where(
            AuthSession.user_id == settings.demo_viewer_id,
            (AuthSession.expires_at <= now()) | (AuthSession.revoked_at.is_not(None)),
        )
        .limit(settings.demo_max_sessions)
    ).all()
    if ids:
        db.execute(delete(AuthSession).where(AuthSession.id.in_(ids)))
    count = db.scalar(
        select(func.count())
        .select_from(AuthSession)
        .where(AuthSession.user_id == settings.demo_viewer_id)
    )
    if count >= settings.demo_max_sessions:
        raise HTTPException(429, "Demo visitor capacity reached; please try again later")


def bound_refresh(db, session, token):
    # Do not throttle replay detection: consumed/unknown tokens must reach rotate().
    record = db.scalar(
        select(RefreshToken).where(
            RefreshToken.session_id == session.id, RefreshToken.token_hash == digest(token)
        )
    )
    if not record or record.consumed_at:
        return
    # Preserve consumed tokens for replay detection, but bound rows per session.
    count = db.scalar(
        select(func.count()).select_from(RefreshToken).where(RefreshToken.session_id == session.id)
    )
    if count >= 24:
        raise HTTPException(
            429, "Demo session refresh limit reached; please sign out and enter again"
        )
    latest = db.scalar(
        select(func.max(RefreshToken.created_at)).where(RefreshToken.session_id == session.id)
    )
    if latest and latest > now() - timedelta(seconds=20):
        raise HTTPException(429, "Please wait before refreshing the demo session again")
