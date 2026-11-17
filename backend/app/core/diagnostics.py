"""Container-local worker health and operator checks. Outputs contain no secrets."""

import argparse
import json
import shutil
import time

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import build_engine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["worker-health", "dependencies", "revoke-sessions"])
    args = parser.parse_args()
    settings = get_settings()
    if args.command == "worker-health":
        try:
            data = json.loads(settings.worker_health_file.read_text())
            if time.time() - data["updated"] > 30:
                raise ValueError()
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            raise SystemExit("Worker heartbeat unavailable") from None
    engine = build_engine(str(settings.database_url))
    try:
        with engine.begin() as connection:
            connection.execute(text("SELECT 1"))
            if args.command == "revoke-sessions":
                changed = connection.execute(
                    text("UPDATE auth_sessions SET revoked_at=now() WHERE revoked_at IS NULL")
                )
                print(f"Revoked {changed.rowcount} sessions after recovery")
            elif args.command == "dependencies":
                print(
                    json.dumps(
                        {
                            "database": "ok",
                            "storage_exists": settings.storage_path.is_dir(),
                            "ocr_enabled": settings.ocr_enabled,
                            "tesseract_available": bool(shutil.which(settings.tesseract_cmd)),
                            "embeddings_enabled": settings.embeddings_enabled,
                            "model_cache_exists": settings.embedding_cache_path.is_dir(),
                        }
                    )
                )
    except Exception:
        raise SystemExit("Operational check failed; verify service configuration") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
