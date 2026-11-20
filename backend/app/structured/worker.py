"""Analysis jobs run in the existing document worker, with independent leases."""

import logging
import time
import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.security import now
from app.intelligence.provider_usage import provider_scope
from app.intelligence.providers import ProviderUnavailable
from app.models import AnalysisItem, AnalysisRun, AnalysisTemplate
from app.structured.engine import analyze
from app.structured.sources import check_evidence, live_revisions, sections_for


def run_analysis_once(engine, settings):
    started = time.monotonic()
    with Session(engine) as db:
        run = db.scalar(
            select(AnalysisRun)
            .where(
                AnalysisRun.available_at <= now(),
                or_(
                    AnalysisRun.state == "pending",
                    and_(AnalysisRun.state == "processing", AnalysisRun.lease_until < now()),
                ),
            )
            .order_by(AnalysisRun.available_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not run:
            return False
        if run.attempts >= settings.worker_max_attempts:
            run.state, run.error = "failed", "Analysis interrupted too many times; retry this run"
            run.lease_token = run.lease_until = None
            db.commit()
            return True
        run.state, run.lease_token = "processing", uuid.uuid4()
        run.attempts += 1
        run.lease_until = now() + timedelta(seconds=settings.analysis_timeout_seconds + 30)
        run_id, token = run.id, run.lease_token
        logging.getLogger(__name__).info(
            "analysis_job_started",
            extra={
                "job_id": run_id,
                "organization_id": run.organization_id,
                "attempt": run.attempts,
            },
        )
        db.commit()
    try:
        with Session(engine) as db:
            run = db.get(AnalysisRun, run_id)
            live_revisions(db, run)
            left = sections_for(db, run.left_revision_id, run.organization_id)
            right = (
                sections_for(db, run.right_revision_id, run.organization_id)
                if run.right_revision_id
                else []
            )
            template = db.get(AnalysisTemplate, run.template_id) if run.template_id else None
            definition = template.definition if template else {}
            documents = [r.document_id for r in live_revisions(db, run)[0]]
            with provider_scope(
                engine,
                run.organization_id,
                run.creator_id,
                f"analysis:{run.id}:{run.provider_generation}",
                documents,
            ):
                results, coverage = analyze(left, right, definition, run.mode, run.engine, settings)
        with Session(engine) as db:
            run = db.get(AnalysisRun, run_id)
            # Consistent order with deletion: documents before analysis run.
            live_revisions(db, run, lock=True)
            db.refresh(run, with_for_update=True)
            if run.state != "processing" or run.lease_token != token or run.lease_until <= now():
                return True
            for result in results:
                for reference in result["evidence"]:
                    check_evidence(db, run, reference)
                db.add(AnalysisItem(run_id=run.id, organization_id=run.organization_id, **result))
            run.coverage, run.state, run.error = coverage, "completed", None
            run.lease_token = run.lease_until = None
            db.commit()
    except Exception as exc:
        with Session(engine) as db:
            run = db.scalar(select(AnalysisRun).where(AnalysisRun.id == run_id).with_for_update())
            if not run or run.lease_token != token or run.state != "processing":
                return True
            if isinstance(exc, HTTPException) and exc.status_code == 410:
                run.state, run.error = "unavailable", "Source document unavailable"
            elif isinstance(exc, (ValueError, ProviderUnavailable)):
                run.state, run.error = "failed", str(exc)[:500]
            else:
                run.state = "pending" if run.attempts < settings.worker_max_attempts else "failed"
                run.error = "Analysis failed; check worker configuration and retry"
                run.available_at = now() + timedelta(seconds=min(300, 2**run.attempts))
            run.lease_token = run.lease_until = None
            db.commit()
    logging.getLogger(__name__).info(
        "analysis_job_finished",
        extra={"job_id": run_id, "duration_ms": round((time.monotonic() - started) * 1000)},
    )
    return True
