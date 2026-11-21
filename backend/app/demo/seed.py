"""Prepare a NEW isolated demo database using real extraction and analysis code.

No OpenAI calls. Refuses populated databases and never deletes existing files.
"""

import argparse
import hashlib
import io
import json
import secrets
import uuid
from datetime import date
from types import SimpleNamespace

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.datastructures import Headers

from app.core.config import Settings, secret_files
from app.core.security import passwords
from app.db.session import build_engine
from app.models import (
    AnalysisItem,
    AnalysisRun,
    AnalysisTemplate,
    Conversation,
    Document,
    DocumentChunk,
    Membership,
    Message,
    Organization,
    SourceRevision,
    User,
)

ORG = uuid.UUID("d09a0000-0000-4000-8000-000000000001")
VIEWER = uuid.UUID("d09a0000-0000-4000-8000-000000000002")
SNAPSHOT = "2026-11-21"
AGREEMENT = """FICTIONAL PUBLIC PORTFOLIO SAMPLE - NOT A REAL CONTRACT
Customer: Northstar Research
Supplier: Meridian Systems
Contract value: USD 50,000
Effective date: 2026-01-15
Renewal date: 2027-01-15
The annual service fee is USD 50,000, payable within 30 days of invoice.
Meridian Systems shall deliver a security assessment by 2026-10-30.
Meridian Systems must provide quarterly security reviews by 2026-12-15.
Northstar Research shall pay the annual fee by 2027-01-15.
The supplier accepts unlimited liability for service interruptions.
Either party may terminate the agreement with 60 days written notice.
"""
TEMPLATE = {
    "name": "Service agreement review",
    "fields": [
        {"name": "customer", "type": "text", "label": "Customer", "required": True},
        {"name": "supplier", "type": "text", "label": "Supplier", "required": True},
        {"name": "contract_value", "type": "money", "label": "Contract value", "required": True},
        {"name": "effective_date", "type": "date", "label": "Effective date"},
        {"name": "renewal_date", "type": "date", "label": "Renewal date"},
    ],
    "rules": [
        {
            "name": "Unlimited liability review candidate",
            "type": "contains",
            "term": "unlimited liability",
            "severity": "high",
        },
        {
            "name": "Contract value above 40000",
            "type": "threshold",
            "field": "contract_value",
            "threshold": 40000,
            "severity": "medium",
        },
    ],
    "obligations": True,
}


def samples():
    """Small real PDF/DOCX/TXT files; all content is authored fictional data."""
    import fitz
    from docx import Document as WordDocument

    updated = (
        AGREEMENT.replace("50,000", "65,000")
        .replace("60 days", "30 days")
        .replace("unlimited liability", "liability limited to annual fees")
    )
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_textbox(fitz.Rect(40, 40, 550, 800), AGREEMENT, fontsize=10)
    yield "Service Agreement v1.pdf", "application/pdf", pdf.tobytes()
    pdf.close()
    word = WordDocument()
    for line in updated.splitlines():
        word.add_paragraph(line)
    stream = io.BytesIO()
    word.save(stream)
    yield (
        "Service Agreement v2.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        stream.getvalue(),
    )
    for filename, text in [
        ("Service Agreement v1.txt", AGREEMENT),
        (
            "Security policy.txt",
            "FICTIONAL PUBLIC SAMPLE\n"
            "Meridian Systems must review access permissions by 2026-12-01.\n"
            "Customer data must be encrypted at rest and in transit.\n",
        ),
        (
            "Delivery plan.txt",
            "FICTIONAL PUBLIC SAMPLE\nProject: Atlas\n"
            "Meridian Systems shall deliver acceptance reports by 2027-01-10.\n"
            "Northstar Research must approve the delivery by 2027-01-20.\n",
        ),
        (
            "Operations handbook.txt",
            "FICTIONAL PUBLIC SAMPLE\nResponsible party: Operations team\n"
            "The Operations team must review the continuity plan by 2027-02-15.\n"
            "Escalate service incidents to the assigned coordinator.\n",
        ),
    ]:
        yield filename, "text/plain", text.encode()


def seed(engine, settings, *, index=False):
    from app.api.routes.structured import review, submit
    from app.documents.service import upload_document
    from app.documents.worker import run_once
    from app.intelligence.providers import MockProvider
    from app.intelligence.rag import answer
    from app.operations.assignments import assign
    from app.structured.schemas import ReviewInput, RunInput, TemplateInput
    from app.structured.worker import run_analysis_once

    if not engine.url.database.startswith("documind_demo"):
        raise ValueError("Seed requires a separate documind_demo database")
    # Never reuse or clean an existing dataset, even when IDs look familiar.
    with Session(engine) as db:
        for table in (User, Organization, Document):
            if db.scalar(select(func.count()).select_from(table)):
                raise ValueError(
                    "Seed requires an empty migrated database; existing data was preserved"
                )
    if settings.storage_path.exists() and any(settings.storage_path.iterdir()):
        raise ValueError("Seed storage must be empty; existing files were preserved")
    # Offline-only settings; these never enable an external provider.
    config = settings.model_copy(
        update={
            "demo_mode": False,
            "environment": "development",
            "llm_provider": "disabled",
            "llm_real_requests_enabled": False,
            "llm_api_key": None,
            "embeddings_enabled": index,
            "ocr_enabled": False,
        }
    )
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    manifest = {
        "snapshot_date": SNAPSHOT,
        "organization_id": str(ORG),
        "viewer_id": str(VIEWER),
        "fictional": True,
        "answer_provenance": "offline extractive mock; no OpenAI requests",
        "embeddings_prepared": index,
        "documents": [],
    }
    with Session(engine, expire_on_commit=False) as db:
        admin = User(
            name="Jordan Lee (fictional reviewer)",
            email="jordan@example.com",
            password_hash=passwords.hash(secrets.token_urlsafe(48)),
        )
        visitor = User(
            id=VIEWER,
            name="Portfolio visitor",
            email="visitor@example.com",
            password_hash=passwords.hash(secrets.token_urlsafe(48)),
        )
        db.add_all(
            [admin, visitor, Organization(id=ORG, name="Northstar Research · Fictional Demo")]
        )
        db.flush()
        member = Membership(organization_id=ORG, user_id=VIEWER, role="member")
        db.add_all([member, Membership(organization_id=ORG, user_id=admin.id, role="admin")])
        db.commit()
        documents = []
        for filename, mime, content in samples():
            document = upload_document(
                db,
                config,
                ORG,
                admin,
                UploadFile(
                    io.BytesIO(content), filename=filename, headers=Headers({"content-type": mime})
                ),
            )
            # Same bounded worker code, executed offline; no persistent worker.
            for _ in range(3):
                if not run_once(engine, config):
                    break
            db.refresh(document)
            if document.status != "completed" or (index and document.index_status != "completed"):
                raise ValueError("Offline preparation failed; inspect the isolated demo dataset")
            document.source_metadata = {
                **document.source_metadata,
                "public_demo": True,
                "snapshot_date": SNAPSHOT,
            }
            for revision in db.scalars(
                select(SourceRevision).where(SourceRevision.document_id == document.id)
            ):
                revision.provenance = document.source_metadata
            documents.append(document)
            manifest["documents"].append(
                {
                    "id": str(document.id),
                    "filename": filename,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                }
            )
            db.commit()
        template = AnalysisTemplate(
            organization_id=ORG,
            name=TEMPLATE["name"],
            definition=TemplateInput.model_validate(TEMPLATE).model_dump(mode="json"),
        )
        db.add(template)
        db.commit()
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=config)))
        for document in [documents[0], documents[3], documents[4], documents[5]]:
            submit(
                ORG, RunInput(document_id=document.id, template_id=template.id), request, admin, db
            )
            run_analysis_once(engine, config)
        submit(
            ORG,
            RunInput(
                document_id=documents[0].id, other_document_id=documents[1].id, mode="compare"
            ),
            request,
            admin,
            db,
        )
        run_analysis_once(engine, config)
        if db.scalar(
            select(func.count()).select_from(AnalysisRun).where(AnalysisRun.state != "completed")
        ):
            raise ValueError("Offline analysis did not complete")
        item = db.scalar(
            select(AnalysisItem).where(
                AnalysisItem.kind == "field", AnalysisItem.validation == "valid"
            )
        )
        review(
            ORG,
            item.run_id,
            item.id,
            ReviewInput(
                version=item.version,
                action="approve",
                reason="Fictional sample: reviewed against the original source.",
            ),
            admin,
            db,
        )
        obligation = db.scalar(select(AnalysisItem).where(AnalysisItem.kind == "obligation"))
        assign(db, obligation, member, admin, date(2026, 12, 10))
        db.commit()
        chunk = db.scalar(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == documents[0].id)
            .order_by(DocumentChunk.ordinal)
        )
        source = {
            "source_id": str(chunk.id),
            "document_id": str(chunk.document_id),
            "filename": documents[0].filename,
            "page_number": 1,
            "label": "Page 1",
            "text": chunk.text,
            "start_offset": chunk.start_offset,
            "similarity": None,
        }
        question = "What are the service agreement terms?"
        response, citations = answer(MockProvider(), config, question, [], [source])
        conversation = Conversation(
            organization_id=ORG, user_id=VIEWER, title="Service agreement · saved mock preview"
        )
        db.add(conversation)
        db.flush()
        db.add(
            Message(
                conversation_id=conversation.id,
                question=question,
                answer=response,
                state="completed",
                provider="mock",
                is_mock=True,
                citations=citations,
            )
        )
        db.commit()
    manifest_path = settings.storage_path / "demo-manifest.json"
    with manifest_path.open("x", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index",
        action="store_true",
        help="Offline local indexing; requires the already prepared model",
    )
    args = parser.parse_args()
    settings = Settings(
        **secret_files(),
        demo_mode=False,
        llm_provider="disabled",
        llm_real_requests_enabled=False,
        llm_api_key=None,
        embeddings_enabled=False,
        ocr_enabled=False,
    )
    engine = build_engine(str(settings.database_url), statement_timeout_ms=120000)
    try:
        manifest = seed(engine, settings, index=args.index)
        print("Fictional demo prepared. Organization:", manifest["organization_id"])
        print("Viewer:", manifest["viewer_id"], "Documents:", len(manifest["documents"]))
    except Exception:
        raise SystemExit(
            "Demo preparation failed; existing databases/files were not reset. "
            "Check isolated configuration and preparation logs."
        ) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
