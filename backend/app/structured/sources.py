import hashlib
import json
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.models import (
    AnalysisItem,
    AnalysisRun,
    Document,
    DocumentSection,
    ReviewEvent,
    RevisionSection,
    SourceRevision,
)


def snapshot(db, document):
    """Caller holds document lock. Archive current extraction without changing Phase 3 tables."""
    sections = db.scalars(
        select(DocumentSection)
        .where(
            DocumentSection.document_id == document.id,
            DocumentSection.organization_id == document.organization_id,
        )
        .order_by(DocumentSection.ordinal)
    ).all()
    payload = [(str(s.id), s.ordinal, s.page_number, s.label, s.text) for s in sections]
    fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()
    existing = db.scalar(
        select(SourceRevision).where(
            SourceRevision.document_id == document.id,
            SourceRevision.fingerprint == fingerprint,
        )
    )
    if existing:
        return existing
    for previous in db.scalars(
        select(SourceRevision).where(
            SourceRevision.document_id == document.id,
            SourceRevision.current.is_(True),
        )
    ):
        previous.current = False
    revision = SourceRevision(
        document_id=document.id,
        organization_id=document.organization_id,
        fingerprint=fingerprint,
        checksum=document.checksum,
        provenance=document.source_metadata,
        current=True,
    )
    db.add(revision)
    db.flush()
    for section in sections:
        db.add(
            RevisionSection(
                revision_id=revision.id,
                organization_id=document.organization_id,
                ordinal=section.ordinal,
                page_number=section.page_number,
                label=section.label,
                text=section.text,
            )
        )
    db.flush()
    return revision


def sections_for(db, revision_id, org):
    return db.scalars(
        select(RevisionSection)
        .where(
            RevisionSection.revision_id == revision_id,
            RevisionSection.organization_id == org,
        )
        .order_by(RevisionSection.ordinal)
    ).all()


def evidence(section, start=0, end=None):
    end = len(section.text) if end is None else end
    return {
        "section_id": str(section.id),
        "revision_id": str(section.revision_id),
        "page_number": section.page_number,
        "label": section.label,
        "start": start,
        "end": end,
        "quote": section.text[start:end],
    }


def check_evidence(db, run, item):
    try:
        section = db.scalar(
            select(RevisionSection).where(
                RevisionSection.id == uuid.UUID(str(item["section_id"])),
                RevisionSection.organization_id == run.organization_id,
                RevisionSection.revision_id.in_(
                    [r for r in [run.left_revision_id, run.right_revision_id] if r]
                ),
            )
        )
        start, end = item["start"], item["end"]
        if (
            not section
            or not isinstance(start, int)
            or not isinstance(end, int)
            or not 0 <= start < end <= len(section.text)
            or section.text[start:end] != item["quote"]
        ):
            raise ValueError()
        return evidence(section, start, end)
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, "Evidence does not match an authorized revision passage") from None


def live_revisions(db, run, lock=False):
    ids = [r for r in [run.left_revision_id, run.right_revision_id] if r]
    expected = 2 if run.mode == "compare" else 1
    if len(ids) != expected:
        raise HTTPException(410, "Source document was deleted")
    revisions = db.scalars(
        select(SourceRevision).where(
            SourceRevision.id.in_(ids),
            SourceRevision.organization_id == run.organization_id,
        )
    ).all()
    query = (
        select(Document)
        .where(
            Document.id.in_([r.document_id for r in revisions]),
            Document.organization_id == run.organization_id,
            Document.deleted_at.is_(None),
        )
        .order_by(Document.id)
    )
    documents = db.scalars(query.with_for_update() if lock else query).all()
    if len(revisions) != expected or len(documents) != len({r.document_id for r in revisions}):
        raise HTTPException(410, "Source document unavailable")
    return revisions, documents


def redact_document(db, document):
    """Preserve IDs/actions/timestamps only; purge source-bearing values and reviewer notes."""
    revision_ids = select(SourceRevision.id).where(SourceRevision.document_id == document.id)
    runs = db.scalars(
        select(AnalysisRun)
        .where(
            AnalysisRun.organization_id == document.organization_id,
            (
                AnalysisRun.left_revision_id.in_(revision_ids)
                | AnalysisRun.right_revision_id.in_(revision_ids)
            ),
        )
        .order_by(AnalysisRun.id)
        .with_for_update()
    ).all()
    for run in runs:
        run.state, run.error, run.coverage = "unavailable", "Source document deleted", {}
        run.lease_token = run.lease_until = None
        items = db.scalars(select(AnalysisItem).where(AnalysisItem.run_id == run.id)).all()
        for item in items:
            item.name, item.original, item.corrected, item.evidence = "Redacted", {}, None, []
            item.validation = "unavailable"
            for event in db.scalars(select(ReviewEvent).where(ReviewEvent.item_id == item.id)):
                event.before = {"version": event.before.get("version")}
                event.after = {"version": event.after.get("version")}
                event.reason = "Source deleted; content redacted"
    db.execute(delete(SourceRevision).where(SourceRevision.document_id == document.id))
