import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import current_user, get_db
from app.models import Membership, Organization, User
from app.schemas import (
    MemberInput,
    MemberOutput,
    OrganizationInput,
    OrganizationOutput,
    RoleInput,
)
from app.services.organizations import membership, preserve_admin, target_member

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationOutput])
def list_organizations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Organization, Membership.role)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
        .order_by(Organization.created_at)
    ).all()
    return [OrganizationOutput(id=org.id, name=org.name, role=role) for org, role in rows]


@router.post("", response_model=OrganizationOutput, status_code=201)
def create_organization(
    data: OrganizationInput, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    org = Organization(name=data.name)
    db.add(org)
    db.flush()
    db.add(Membership(organization_id=org.id, user_id=user.id, role="admin"))
    db.commit()
    return OrganizationOutput(id=org.id, name=org.name, role="admin")


@router.get("/{organization_id}", response_model=OrganizationOutput)
def get_organization(
    organization_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    member = membership(db, organization_id, user)
    org = db.get(Organization, organization_id)
    return OrganizationOutput(id=org.id, name=org.name, role=member.role)


@router.get("/{organization_id}/members", response_model=list[MemberOutput])
def list_members(
    organization_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    membership(db, organization_id, user)
    rows = db.execute(
        select(User, Membership.role)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.organization_id == organization_id)
        .order_by(User.name)
    ).all()
    return [MemberOutput(user_id=u.id, email=u.email, name=u.name, role=role) for u, role in rows]


@router.post("/{organization_id}/members", response_model=MemberOutput, status_code=201)
def add_member(
    organization_id: uuid.UUID,
    data: MemberInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user, admin=True, lock=True)
    target = db.scalar(select(User).where(User.email == str(data.email).lower()))
    if not target:
        raise HTTPException(404, "No registered user with that email")
    db.add(Membership(organization_id=organization_id, user_id=target.id, role=data.role))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "User already belongs to this organization") from None
    return MemberOutput(user_id=target.id, name=target.name, email=target.email, role=data.role)


@router.patch("/{organization_id}/members/{user_id}", response_model=MemberOutput)
def change_role(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    data: RoleInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user, admin=True, lock=True)
    target = target_member(db, organization_id, user_id)
    if data.role != "admin":
        preserve_admin(db, target)
    target.role = data.role
    db.commit()
    account = db.get(User, user_id)
    return MemberOutput(user_id=user_id, name=account.name, email=account.email, role=target.role)


@router.delete("/{organization_id}/members/{user_id}", status_code=204)
def remove_member(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user, admin=True, lock=True)
    target = target_member(db, organization_id, user_id)
    preserve_admin(db, target)
    db.delete(target)
    db.commit()
    return Response(status_code=204)
