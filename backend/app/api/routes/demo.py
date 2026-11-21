from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.api.routes.auth import session_response
from app.core.demo import session_capacity, viewer
from app.core.security import now
from app.services.auth import new_session

router = APIRouter(tags=["demo"])


@router.get("/demo")
def capabilities(request: Request):
    return {
        "demo_mode": request.app.state.settings.demo_mode,
        "generation_enabled": False if request.app.state.settings.demo_mode else None,
    }


@router.post("/demo/enter")
def enter(request: Request, response: Response, db: Session = Depends(get_db)):
    settings = request.app.state.settings
    if not settings.demo_mode:
        raise HTTPException(404, "Not found")
    request.app.state.demo_entry_limiter.check()
    session_capacity(db, settings)
    user = viewer(db, settings)
    session, token = new_session(db, user, settings)
    session.expires_at = now() + timedelta(minutes=settings.demo_session_minutes)
    db.commit()
    session_response(request, response, session, token)
    return {"status": "ok"}
