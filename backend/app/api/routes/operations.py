import csv
import io
import json
import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user, get_db
from app.api.routes.structured import csv_safe, run_for
from app.models import AnalysisItem, AnalysisRun, Document, Membership, ReviewEvent, User
from app.operations.assignments import assign
from app.operations.permissions import manages
from app.operations.queries import Filters, filtered, metric_conditions, portfolio
from app.services.organizations import membership, target_member

router = APIRouter(prefix="/organizations/{organization_id}/operations", tags=["operations"])
Selection = Annotated[Filters, Query()]


@router.get("/diagnostics")
def diagnostics(
    organization_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    from app.core.security import now
    from app.models import DocumentJob

    membership(db, organization_id, user, admin=True)
    jobs = db.execute(
        select(DocumentJob.state, func.count())
        .where(
            DocumentJob.organization_id == organization_id,
        )
        .group_by(DocumentJob.state)
    ).all()
    failed = db.scalars(
        select(DocumentJob)
        .where(
            DocumentJob.organization_id == organization_id,
            DocumentJob.state == "failed",
        )
        .limit(20)
    ).all()
    stale = db.scalar(
        select(func.count())
        .select_from(DocumentJob)
        .where(
            DocumentJob.organization_id == organization_id,
            DocumentJob.state == "running",
            DocumentJob.lease_until < now(),
        )
    )
    analyses = db.execute(
        select(AnalysisRun.state, func.count())
        .where(
            AnalysisRun.organization_id == organization_id,
        )
        .group_by(AnalysisRun.state)
    ).all()
    return {
        "document_jobs": dict(jobs),
        "analysis_jobs": dict(analyses),
        "expired_document_leases": stale,
        "failed_documents": [
            {
                "document_id": item.document_id,
                "kind": item.kind,
                "attempts": item.attempts,
                "error": item.last_error,
            }
            for item in failed
        ],
    }


def count(db, query):
    return db.scalar(select(func.count()).select_from(query.subquery()))


@router.get("/summary")
def summary(
    organization_id: uuid.UUID,
    filters: Selection,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    selected = filtered(organization_id, filters).subquery()
    c = selected.c
    statement = select(
        *[
            func.count().filter(condition).label(name)
            for name, condition in metric_conditions(c, filters.as_of).items()
        ]
    )
    totals = dict(db.execute(statement).mappings().one())
    severities = dict(
        db.execute(
            select(c.severity, func.count()).where(c.kind == "risk").group_by(c.severity)
        ).all()
    )
    # Inventory is deliberately organization-wide, separately labeled from filtered record totals.
    documents = dict(
        db.execute(
            select(Document.status, func.count())
            .where(
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
            )
            .group_by(Document.status)
        ).all()
    )
    analyses = dict(
        db.execute(
            select(AnalysisRun.state, func.count())
            .where(
                AnalysisRun.organization_id == organization_id,
            )
            .group_by(AnalysisRun.state)
        ).all()
    )
    return {
        "totals": totals,
        "severity": severities,
        "inventory": {"documents": documents, "analyses": analyses},
        "filters": filters.model_dump(mode="json"),
        "counting": (
            "Analysis records, not unique business items. Latest successful run per "
            "revision/template family/engine; independent template families may overlap."
        ),
        "date_basis": (
            "UTC deadline reference date, not a historical snapshot; "
            "upcoming includes seven days ahead"
        ),
    }


@router.get("/items")
def items(
    organization_id: uuid.UUID,
    filters: Selection,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    member = membership(db, organization_id, user)
    query = filtered(organization_id, filters)
    total = count(db, query)
    rows = (
        db.execute(
            query.order_by("created_at", "id").offset((page - 1) * page_size).limit(page_size)
        )
        .mappings()
        .all()
    )
    # Assignment delegates actions on this item, without source-management rights.
    docs = {
        doc.id: doc
        for doc in db.scalars(
            select(Document).where(
                Document.id.in_([r["document_id"] for r in rows]),
                Document.organization_id == organization_id,
            )
        )
    }
    output = []
    for row in rows:
        manager = member.role == "admin" or docs[row["document_id"]].uploader_id == user.id
        output.append(
            dict(row)
            | {
                "can_assign": manager and row["is_current"] and not row["is_done"],
                "can_review": manager or (row["assignee_id"] == user.id and row["is_current"]),
            }
        )
    return {
        "items": output,
        "total": total,
        "page": page,
        "page_size": page_size,
        "filters": filters.model_dump(mode="json"),
    }


class Assignment(BaseModel):
    version: int = Field(ge=1)
    assignee_id: uuid.UUID | None = None
    due_date: date | None = None


@router.patch("/items/{item_id}/assignment")
def assignment(
    organization_id: uuid.UUID,
    item_id: uuid.UUID,
    body: Assignment,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    member = membership(db, organization_id, user, lock=True)
    item = db.scalar(
        select(AnalysisItem).where(
            AnalysisItem.id == item_id, AnalysisItem.organization_id == organization_id
        )
    )
    if not item:
        raise HTTPException(404, "Result not found")
    run, _, documents = run_for(db, organization_id, item.run_id, manage=user)
    if not manages(member, user, documents):
        raise HTTPException(403, "Source manager permission required")
    db.refresh(item, with_for_update=True)
    if item.version != body.version:
        raise HTTPException(409, "Result changed; reload before assigning")
    rows = portfolio(organization_id)
    state = db.execute(
        select(rows.c.is_current, rows.c.is_done).where(rows.c.id == item.id)
    ).first()
    if not state or not state.is_current or state.is_done:
        raise HTTPException(409, "Only current, open records may be assigned")
    target = target_member(db, organization_id, body.assignee_id) if body.assignee_id else None
    if (
        item.assignee_membership_id == (target.id if target else None)
        and item.assignment_due_date == body.due_date
    ):
        return {"version": item.version}
    assign(db, item, target, user, body.due_date)
    db.commit()
    return {"version": item.version}


@router.get("/members")
def members(
    organization_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    membership(db, organization_id, user)
    return [
        dict(row)
        for row in db.execute(
            select(User.id, User.name, Membership.role)
            .join(
                Membership,
                Membership.user_id == User.id,
            )
            .where(Membership.organization_id == organization_id)
            .order_by(User.name, User.id)
        ).mappings()
    ]


@router.get("/activity")
def activity(
    organization_id: uuid.UUID,
    page: int = Query(1, ge=1),
    item_id: uuid.UUID | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    query = (
        select(
            ReviewEvent,
            User.name.label("actor_name"),
            AnalysisItem.run_id,
            AnalysisRun.state,
            AnalysisRun.engine,
        )
        .join(
            AnalysisItem,
            AnalysisItem.id == ReviewEvent.item_id,
        )
        .join(AnalysisRun, AnalysisRun.id == AnalysisItem.run_id)
        .outerjoin(User, User.id == ReviewEvent.actor_id)
        .where(
            AnalysisItem.organization_id == organization_id,
            AnalysisRun.organization_id == organization_id,
        )
    )
    if item_id:
        query = query.where(AnalysisItem.id == item_id)
    total = count(db, query)
    rows = db.execute(
        query.order_by(ReviewEvent.created_at.desc(), ReviewEvent.id.desc())
        .offset((page - 1) * 30)
        .limit(30)
    ).all()
    return {
        "items": [
            jsonable_encoder(event)
            | {
                "actor_name": actor_name,
                "run_id": run_id,
                "source_unavailable": state == "unavailable",
                "engine": engine,
            }
            for event, actor_name, run_id, state, engine in rows
        ],
        "total": total,
        "page": page,
    }


@router.get("/export")
def export(
    organization_id: uuid.UUID,
    filters: Selection,
    format: Literal["csv", "json"] = "json",
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    query = filtered(organization_id, filters)
    rows = db.execute(query.order_by("created_at", "id").limit(5001)).mappings().all()
    if len(rows) > 5000:
        raise HTTPException(413, "Export exceeds 5000 records; narrow the filters")
    encoded = jsonable_encoder([dict(row) for row in rows])
    if format == "json":
        content = json.dumps(
            {
                "filters": filters.model_dump(mode="json"),
                "total": len(rows),
                "record_semantics": "Independent template families may overlap",
                "items": encoded,
            },
            ensure_ascii=False,
        )
        media = "application/json"
    else:
        output = io.StringIO(newline="")
        columns = [
            "id",
            "run_id",
            "document_id",
            "filename",
            "revision_id",
            "family_id",
            "template_name",
            "engine",
            "kind",
            "name",
            "severity",
            "review_status",
            "effective_validation",
            "obligation_status",
            "responsible_party",
            "contract_deadline",
            "assignee_id",
            "assignee_name",
            "assignment_due_date",
            "completed_at",
            "is_current",
            "original",
            "corrected",
            "evidence",
        ]
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in encoded:
            writer.writerow(
                [
                    csv_safe(
                        json.dumps(row[key], ensure_ascii=False)
                        if isinstance(row[key], (dict, list))
                        else (row[key] if row[key] is not None else "")
                    )
                    for key in columns
                ]
            )
        content, media = output.getvalue(), "text/csv"
    return Response(
        content,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="operations.{format}"',
            "Cache-Control": "no-store",
        },
    )
