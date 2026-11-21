"""Initialize independent demo secrets without reading or overwriting local .env."""

import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    directory = root / "secrets"
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    if any(directory.iterdir()):
        raise SystemExit("Demo secrets already exist; nothing was overwritten")
    values = {
        name: secrets.token_urlsafe(48)
        for name in (
            "admin_password",
            "app_password",
            "migration_password",
            "auth_secret",
        )
    }
    values["app_database_url"] = (
        f"postgresql+psycopg://documind_demo_app:{values['app_password']}@db:5432/documind_demo"
    )
    values["migration_database_url"] = (
        f"postgresql+psycopg://documind_demo_migrator:{values['migration_password']}@db:5432/documind_demo"
    )
    for name, value in values.items():
        with (directory / name).open("x", encoding="utf-8") as file:
            file.write(value)
        (directory / name).chmod(0o644)
    (root / "certs").mkdir(exist_ok=True)
    print(
        "Independent demo secrets initialized; configure trusted local TLS. No values displayed."
    )


if __name__ == "__main__":
    main()
