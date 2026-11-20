import csv
import io
import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import current_user, get_db
from app.core.security import now
from app.documents.service import can_manage, find_document
from app.intelligence.provider_usage import usage_for
from app.models import (
    AnalysisItem,
    AnalysisRun,
    AnalysisTemplate,
    ReviewEvent,
    SourceRevision,
    User,
)
from app.operations.permissions import manages, may_review
from app.operations.queries import portfolio
from app.services.organizations import membership
from app.structured.engine import normalize
from app.structured.schemas import ReviewInput, RunInput, TemplateInput
from app.structured.sources import check_evidence, live_revisions, sections_for, snapshot

router = APIRouter(prefix="/organizations/{organization_id}/structured", tags=["structured"])


def run_for(db, org, run_id, manage=None):
    run = db.scalar(
        select(AnalysisRun).where(
            AnalysisRun.id == run_id,
            AnalysisRun.organization_id == org,
        )
    )
    if not run:
        raise HTTPException(404, "Analysis not found")
    revisions, documents = live_revisions(db, run, lock=manage is not None)
    if manage:
        for document in documents:
            can_manage(db, org, manage, document)
    return run, revisions, documents


def template_for(db, org, template_id):
    item = db.scalar(
        select(AnalysisTemplate).where(
            AnalysisTemplate.id == template_id,
            AnalysisTemplate.organization_id == org,
        )
    )
    if not item:
        raise HTTPException(404, "Template not found")
    return item


@router.get("/templates")
def templates(
    organization_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    membership(db, organization_id, user)
    return db.scalars(
        select(AnalysisTemplate)
        .where(
            AnalysisTemplate.organization_id == organization_id,
        )
        .order_by(AnalysisTemplate.created_at.desc())
        .limit(100)
    ).all()


@router.post("/templates", status_code=201)
def create_template(
    organization_id: uuid.UUID,
    body: TemplateInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user, admin=True)
    if body.parent_id:
        template_for(db, organization_id, body.parent_id)
    item = AnalysisTemplate(
        organization_id=organization_id,
        parent_id=body.parent_id,
        name=body.name,
        definition=body.model_dump(mode="json", exclude={"name", "parent_id"}),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/documents/{document_id}/revisions")
def revisions(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    document = find_document(db, organization_id, document_id, lock=True)
    if document.status == "completed":
        snapshot(db, document)  # lazy, idempotent backfill of existing Phase 3/4 documents
        db.commit()
    return db.scalars(
        select(SourceRevision)
        .where(
            SourceRevision.document_id == document_id,
            SourceRevision.organization_id == organization_id,
        )
        .order_by(SourceRevision.created_at.desc())
        .limit(100)
    ).all()


def selected_revision(db, org, doc_id, revision_id, user):
    document = find_document(db, org, doc_id, lock=True)
    can_manage(db, org, user, document)
    if document.status != "completed":
        raise HTTPException(409, "Wait for document processing to complete")
    current = snapshot(db, document)
    if not revision_id:
        return current
    revision = db.scalar(
        select(SourceRevision).where(
            SourceRevision.id == revision_id,
            SourceRevision.document_id == doc_id,
            SourceRevision.organization_id == org,
        )
    )
    if not revision:
        raise HTTPException(404, "Revision not found")
    return revision


@router.post("/runs", status_code=202)
def submit(
    organization_id: uuid.UUID,
    body: RunInput,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    if body.engine == "openai":
        from app.intelligence.providers import ProviderUnavailable, get_provider

        try:
            provider = get_provider(request.app.state.settings)
            if request.app.state.settings.llm_provider != "openai" or provider.is_mock:
                raise ProviderUnavailable("Select and enable the OpenAI provider first")
        except ProviderUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
    if body.engine == "mock" and (
        request.app.state.settings.environment != "development"
        or request.app.state.settings.llm_provider != "mock"
    ):
        raise HTTPException(409, "Structured mock requires development and LLM_PROVIDER=mock")
    # Lock both source documents in UUID order to avoid reversed-comparison deadlocks.
    from app.models import Document

    ids = sorted(
        set([body.document_id] + ([body.other_document_id] if body.other_document_id else []))
    )
    db.scalars(
        select(Document)
        .where(Document.id.in_(ids), Document.organization_id == organization_id)
        .order_by(Document.id)
        .with_for_update()
    ).all()
    left = selected_revision(db, organization_id, body.document_id, body.revision_id, user)
    right = None
    if body.mode == "compare":
        if not body.other_document_id or body.engine not in {"deterministic", "openai"}:
            raise HTTPException(
                422, "Comparison requires a second document and deterministic or OpenAI engine"
            )
        right = selected_revision(
            db, organization_id, body.other_document_id, body.other_revision_id, user
        )
        if right.id == left.id:
            raise HTTPException(422, "Select two different documents or revisions")
    elif not body.template_id:
        raise HTTPException(422, "Extraction requires a template")
    if body.template_id:
        template_for(db, organization_id, body.template_id)
    # Prevent unbounded queues; creator row serializes concurrent reservations.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    from sqlalchemy import func

    pending = db.scalar(
        select(func.count())
        .select_from(AnalysisRun)
        .where(
            AnalysisRun.creator_id == user.id,
            AnalysisRun.state.in_(["pending", "processing"]),
        )
    )
    if pending >= 10:
        raise HTTPException(429, "At most ten pending analyses per user")
    run = AnalysisRun(
        organization_id=organization_id,
        creator_id=user.id,
        left_revision_id=left.id,
        right_revision_id=right.id if right else None,
        template_id=body.template_id,
        mode=body.mode,
        engine=body.engine,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/runs")
def runs(
    organization_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    membership(db, organization_id, user)
    return db.scalars(
        select(AnalysisRun)
        .where(AnalysisRun.organization_id == organization_id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(100)
    ).all()


@router.get("/runs/{run_id}")
def result(
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    run, revisions, documents = run_for(db, organization_id, run_id)
    items = db.scalars(
        select(AnalysisItem)
        .where(AnalysisItem.run_id == run.id)
        .order_by(AnalysisItem.kind, AnalysisItem.name, AnalysisItem.id)
    ).all()
    events = db.scalars(
        select(ReviewEvent)
        .join(AnalysisItem)
        .where(AnalysisItem.run_id == run.id)
        .order_by(ReviewEvent.created_at, ReviewEvent.id)
    ).all()
    member = membership(db, organization_id, user)
    from fastapi.encoders import jsonable_encoder

    rows = portfolio(organization_id)
    active = bool(db.scalar(select(rows.c.is_current).where(rows.c.run_id == run_id).limit(1)))
    manager = manages(member, user, documents)
    encoded_items = [
        {
            **jsonable_encoder(item),
            "can_review": manager or (active and item.assignee_membership_id == member.id),
        }
        for item in items
    ]
    return {
        "run": run,
        "usage": usage_for(db, organization_id, f"analysis:{run.id}:{run.provider_generation}"),
        "items": encoded_items,
        "reviews": events,
        "superseded": any(not r.current for r in revisions)
        or any(d.status != "completed" for d in documents),
        "can_manage": all(d.uploader_id == user.id or member.role == "admin" for d in documents),
        "sources": [
            {
                "revision_id": r.id,
                "document_id": r.document_id,
                "filename": next(d.filename for d in documents if d.id == r.document_id),
            }
            for r in revisions
        ],
    }


@router.get("/runs/{run_id}/sections")
def source_sections(
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    revision_id: uuid.UUID,
    page: int = Query(1, ge=1),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    run, revisions, _ = run_for(db, organization_id, run_id)
    if revision_id not in {r.id for r in revisions}:
        raise HTTPException(404, "Revision not found")
    sections = sections_for(db, revision_id, organization_id)
    return {"items": sections[(page - 1) * 5 : page * 5], "total": len(sections), "page": page}


@router.post("/runs/{run_id}/retry", status_code=202)
def retry(
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    run, _, _ = run_for(db, organization_id, run_id, manage=user)
    db.refresh(run, with_for_update=True)
    if run.state != "failed":
        raise HTTPException(409, "Only failed analyses can be retried")
    run.state, run.error, run.attempts, run.available_at = "pending", None, 0, now()
    run.provider_generation += 1
    run.lease_token = run.lease_until = None
    db.commit()
    return {"state": "pending"}


@router.post("/runs/{run_id}/items/{item_id}/review")
def review(
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ReviewInput,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    member = membership(db, organization_id, user, lock=True)
    run, _, documents = run_for(db, organization_id, run_id)
    live_revisions(db, run, lock=True)
    item = db.scalar(
        select(AnalysisItem)
        .where(AnalysisItem.id == item_id, AnalysisItem.run_id == run_id)
        .with_for_update()
    )
    if not item:
        raise HTTPException(404, "Result not found")
    if not may_review(db, organization_id, member, user, documents, item):
        raise HTTPException(
            403, "Only source managers or the active assigned member may review this result"
        )
    if item.version != body.version:
        raise HTTPException(409, "Result changed; reload before reviewing")
    before = {
        "review_status": item.review_status,
        "corrected": item.corrected,
        "obligation_status": item.obligation_status,
        "version": item.version,
    }
    if body.action == "obligation":
        if item.kind != "obligation" or body.obligation_status is None:
            raise HTTPException(422, "Choose a valid obligation status")
        item.obligation_status = body.obligation_status
    elif body.action == "correct":
        if body.value is None:
            raise HTTPException(422, "Correction value is required")
        refs = (
            [check_evidence(db, run, body.evidence.model_dump(mode="json"))]
            if body.evidence
            else []
        )
        kind = item.original.get("type", "text")
        value, validation = normalize(body.value, kind)
        supported = bool(refs) and body.value in refs[0]["quote"] and validation == "valid"
        item.corrected = {
            "raw": body.value,
            "value": value,
            "evidence": refs,
            "validation": "valid" if supported else "manual_assertion",
        }
        item.review_status = "corrected"
    elif body.action == "approve":
        validation = item.corrected.get("validation") if item.corrected else item.validation
        if validation not in {"valid", "candidate", "coverage_only"}:
            raise HTTPException(422, "Unresolved or unsupported values cannot be approved")
        if validation == "coverage_only" and not run.coverage.get("complete"):
            raise HTTPException(422, "Complete inspected coverage is required")
        item.review_status = "approved"
    else:
        item.review_status = "rejected"
    item.version += 1
    after = {
        "review_status": item.review_status,
        "corrected": item.corrected,
        "obligation_status": item.obligation_status,
        "version": item.version,
    }
    db.add(
        ReviewEvent(
            item_id=item.id,
            actor_id=user.id,
            action=body.action,
            before=before,
            after=after,
            reason=body.reason,
        )
    )
    db.commit()
    return {"version": item.version, "review_status": item.review_status}


@router.get("/obligations")
def obligations(
    organization_id: uuid.UUID,
    status: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    membership(db, organization_id, user)
    query = (
        select(AnalysisItem)
        .join(AnalysisRun)
        .where(
            AnalysisItem.organization_id == organization_id,
            AnalysisItem.kind == "obligation",
            AnalysisRun.state == "completed",
        )
    )
    if status:
        query = query.where(AnalysisItem.obligation_status == status)
    items = db.scalars(query.order_by(AnalysisItem.id).limit(200)).all()
    return items


def csv_safe(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


@router.get("/runs/{run_id}/export")
def export(
    organization_id: uuid.UUID,
    run_id: uuid.UUID,
    format: Literal["json", "csv"] = "json",
    kind: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    data = result(organization_id, run_id, user, db)
    from fastapi.encoders import jsonable_encoder

    encoded = jsonable_encoder(data)
    items = [i for i in encoded["items"] if not kind or i["kind"] == kind]
    if format == "json":
        encoded["items"] = items
        content, media = json.dumps(encoded, ensure_ascii=False), "application/json"
    else:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(
            [
                "kind",
                "name",
                "engine",
                "validation",
                "review_status",
                "obligation_status",
                "original",
                "correction",
                "evidence",
                "superseded",
            ]
        )
        for item in items:
            values = [
                item["kind"],
                item["name"],
                encoded["run"]["engine"],
                item["validation"],
                item["review_status"],
                item["obligation_status"],
                json.dumps(item["original"]),
                json.dumps(item["corrected"]),
                json.dumps(item["evidence"]),
                encoded["superseded"],
            ]
            writer.writerow([csv_safe(v) for v in values])
        content, media = stream.getvalue(), "text/csv"
    return Response(
        content,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="analysis-{run_id}.{format}"',
            "Cache-Control": "no-store",
        },
    )
