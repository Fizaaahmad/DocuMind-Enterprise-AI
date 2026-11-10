import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Membership, Organization, User


def membership(
    db: Session, organization_id: uuid.UUID, user: User, admin: bool = False, lock: bool = False
) -> Membership:
    if lock:
        db.scalar(select(Organization).where(Organization.id == organization_id).with_for_update())
    member = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id, Membership.user_id == user.id
        )
    )
    if not member:
        raise HTTPException(404, "Organization not found")
    if admin and member.role != "admin":
        raise HTTPException(403, "Organization Admin role required")
    return member


def target_member(db: Session, organization_id: uuid.UUID, user_id: uuid.UUID) -> Membership:
    member = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id, Membership.user_id == user_id
        )
    )
    if not member:
        raise HTTPException(404, "Member not found")
    return member


def preserve_admin(db: Session, member: Membership):
    if member.role == "admin":
        count = db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.organization_id == member.organization_id, Membership.role == "admin")
        )
        if count == 1:
            raise HTTPException(409, "An organization must retain at least one Admin")
