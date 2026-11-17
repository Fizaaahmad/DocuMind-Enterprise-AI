"""Operator-only production initialization, consistent backup, and fresh-target restore.

Uses docker compose/cp for binary files: safe with Windows PowerShell 5 and 7.
Never prints generated secrets, passwords, or rendered application configuration.
"""

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def initialize(directory):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "secrets"
    target.mkdir(mode=0o700, exist_ok=True)
    if any(target.iterdir()):
        raise SystemExit(
            "Secrets already exist; initialization never overwrites credentials"
        )
    tokens = {
        name: secrets.token_urlsafe(48)
        for name in [
            "admin_password",
            "app_password",
            "migration_password",
            "auth_secret",
        ]
    }
    tokens["app_database_url"] = (
        f"postgresql+psycopg://documind_app:{tokens['app_password']}@db:5432/documind"
    )
    tokens["migration_database_url"] = (
        f"postgresql+psycopg://documind_migrator:{tokens['migration_password']}@db:5432/documind"
    )
    for name, value in tokens.items():
        path = target / name
        path.write_text(value, encoding="utf-8")
        # Compose file secrets preserve host ownership. Private parent (0700)
        # protects the host; readonly 0644 mounts support non-root containers.
        path.chmod(0o644)
    example = ROOT / "deploy/.env.production.example"
    if not (directory / ".env.production").exists():
        shutil.copyfile(example, directory / ".env.production")
    (directory / "certs").mkdir(mode=0o700, exist_ok=True)
    print(
        "Initialized private local secrets. Configure production origin and TLS certificates."
    )


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def compose(args, *command, capture=False):
    prefix = [
        "docker",
        "compose",
        "-f",
        str(args.file),
        "--env-file",
        str(args.env_file),
    ]
    if args.project:
        prefix += ["-p", args.project]
    return (
        subprocess.run(
            prefix + list(command), check=True, text=True, capture_output=capture
        ).stdout
        if capture
        else subprocess.run(prefix + list(command), check=True)
    )


def backup(args):
    target = args.directory.resolve()
    target.mkdir(parents=True, mode=0o700, exist_ok=False)
    services = compose(
        args, "ps", "--status", "running", "--services", capture=True
    ).split()
    if "migrate" in services:
        raise SystemExit("Wait for migrations before taking a backup")
    writers = [s for s in ["api", "worker"] if s in services]
    try:
        if writers:
            compose(args, "stop", *writers)
        compose(
            args,
            "exec",
            "-T",
            "db",
            "pg_dump",
            "-U",
            "documind_admin",
            "-d",
            "documind",
            "-Fc",
            "-f",
            "/tmp/documind.dump",
        )
        compose(args, "cp", "db:/tmp/documind.dump", str(target / "database.dump"))
        compose(
            args,
            "run",
            "--rm",
            "--no-deps",
            "--user",
            "0",
            "--cap-add",
            "DAC_OVERRIDE",
            "-v",
            f"{target}:/backup",
            "worker",
            "python",
            "-m",
            "app.core.archive",
            "pack",
            "/backup/documents.tar.gz",
        )
        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "schema_revision": compose(
                args,
                "exec",
                "-T",
                "db",
                "psql",
                "-U",
                "documind_admin",
                "-d",
                "documind",
                "-Atc",
                "SELECT version_num FROM alembic_version",
                capture=True,
            ).strip(),
            "image_ids": compose(args, "images", "-q", capture=True).split(),
            "files": {
                name: digest(target / name)
                for name in ["database.dump", "documents.tar.gz"]
            },
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        print("Consistent database/document backup completed")
    finally:
        try:
            compose(args, "exec", "-T", "db", "rm", "-f", "/tmp/documind.dump")
        finally:
            if writers:
                compose(args, "start", *writers)


def restore(args):
    if not args.confirm_new_target:
        raise SystemExit(
            "Restore requires --confirm-new-target and empty database/document volumes"
        )
    target = args.directory.resolve()
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    for name in ["database.dump", "documents.tar.gz"]:
        if digest(target / name) != manifest["files"].get(name):
            raise SystemExit("Backup checksum verification failed")
    running = compose(
        args, "ps", "--status", "running", "--services", capture=True
    ).split()
    if any(s in running for s in ["api", "worker", "migrate"]):
        raise SystemExit("Stop all writers before restoring")
    empty = compose(
        args,
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        "documind_admin",
        "-d",
        "documind",
        "-Atc",
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'",
        capture=True,
    ).strip()
    if empty != "0":
        raise SystemExit("Restore refuses a nonempty application database")
    compose(
        args,
        "run",
        "--rm",
        "--no-deps",
        "worker",
        "python",
        "-c",
        "from pathlib import Path; import sys; sys.exit(1 if any(Path('/data/documents').iterdir()) else 0)",
    )
    compose(args, "cp", str(target / "database.dump"), "db:/tmp/restore.dump")
    try:
        compose(
            args,
            "exec",
            "-T",
            "db",
            "pg_restore",
            "-U",
            "documind_admin",
            "-d",
            "documind",
            "--exit-on-error",
            "/tmp/restore.dump",
        )
        compose(
            args,
            "run",
            "--rm",
            "--no-deps",
            "--user",
            "0",
            "--cap-add",
            "DAC_OVERRIDE",
            "--cap-add",
            "CHOWN",
            "-v",
            f"{target}:/backup:ro",
            "worker",
            "python",
            "-m",
            "app.core.archive",
            "restore",
            "/backup/documents.tar.gz",
        )
        compose(
            args,
            "run",
            "--rm",
            "--no-deps",
            "api",
            "python",
            "-m",
            "app.core.diagnostics",
            "revoke-sessions",
        )
        print(
            "Restore complete; sessions revoked. Apply forward migrations and verify before starting writers."
        )
    finally:
        compose(args, "exec", "-T", "db", "rm", "-f", "/tmp/restore.dump")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=ROOT / "compose.production.yaml")
    parser.add_argument(
        "--env-file", type=Path, default=ROOT / "deploy/.env.production"
    )
    parser.add_argument("--project")
    parser.add_argument("command", choices=["init", "backup", "restore"])
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--confirm-new-target", action="store_true")
    args = parser.parse_args()
    if args.command == "init":
        initialize(args.directory or ROOT / "deploy")
    elif args.command == "backup":
        args.directory = args.directory or ROOT / "backups" / datetime.now(
            UTC
        ).strftime("%Y%m%dT%H%M%SZ")
        backup(args)
    else:
        if not args.directory:
            parser.error("restore requires --directory")
        restore(args)


if __name__ == "__main__":
    main()
