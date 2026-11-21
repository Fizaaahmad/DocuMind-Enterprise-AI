"""Explicit managed-demo target identity, independent of network access."""

import re

from sqlalchemy.engine import make_url


def validate_supabase_target(database_url, project_ref, role):
    url = make_url(str(database_url))
    if not project_ref or not re.fullmatch(r"[a-z0-9]{20}", project_ref):
        raise ValueError("An explicit Supabase project reference is required")
    if (
        url.drivername != "postgresql+psycopg"
        or url.database != "postgres"
        or not re.fullmatch(r"aws-[0-9]+-[a-z0-9-]+\.pooler\.supabase\.com", url.host or "")
        or url.port != 5432
        or url.username != f"{role}.{project_ref}"
        or not url.password
        or url.query.get("sslmode") != "verify-full"
        or not url.query.get("sslrootcert")
    ):
        raise ValueError(
            "Supabase demo requires the pinned project, exact role and TLS session pooler"
        )
    return url
