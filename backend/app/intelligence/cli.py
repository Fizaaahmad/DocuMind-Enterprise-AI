"""Explicit model preparation and resumable local indexing administration."""

import argparse
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import build_engine
from app.intelligence.embeddings import Encoder, get_encoder, profile
from app.intelligence.indexing import enqueue
from app.models import Document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "check", "backfill"])
    parser.add_argument("--organization", type=uuid.UUID)
    args = parser.parse_args()
    settings = get_settings()
    if args.command == "prepare":
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(
            settings.embedding_model,
            revision=settings.embedding_revision,
            device="cpu",
            cache_folder=str(settings.embedding_cache_path),
            trust_remote_code=False,
        )
        Encoder(model, settings.embedding_dimension, settings.embedding_batch_size)
        print("Embedding model cached and dimension verified. Runtime inference is local-only.")
    elif args.command == "check":
        vectors = get_encoder(settings).encode(
            [
                "Employees receive twenty days of annual leave.",
                "How much vacation can employees take?",
                "The database server uses PostgreSQL.",
            ]
        )

        def cosine(a, b):
            return sum(x * y for x, y in zip(a, b, strict=True))

        related, unrelated = cosine(vectors[0], vectors[1]), cosine(vectors[0], vectors[2])
        if related <= unrelated:
            raise SystemExit("Embedding relevance check failed")
        print(f"Local embeddings OK: dimension={len(vectors[0])}; relevance ranking passed.")
    else:
        if not settings.embeddings_enabled:
            raise SystemExit("Set EMBEDDINGS_ENABLED=true first")
        engine = build_engine(str(settings.database_url))
        count = 0
        try:
            with Session(engine) as db:
                query = select(Document.id).where(
                    Document.deleted_at.is_(None),
                    Document.status == "completed",
                )
                if args.organization:
                    query = query.where(Document.organization_id == args.organization)
                ids = list(db.scalars(query))
                db.rollback()
                for document_id in ids:
                    document = db.scalar(
                        select(Document)
                        .where(
                            Document.id == document_id,
                        )
                        .with_for_update()
                    )
                    if not document or (
                        document.index_status == "completed"
                        and document.index_profile == profile(settings)
                    ):
                        db.rollback()
                        continue
                    try:
                        enqueue(db, document, settings)
                        db.commit()
                        count += 1
                    except HTTPException:
                        db.rollback()  # active jobs are never replaced
            print(f"Queued {count} documents. Start the existing document worker to process them.")
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
