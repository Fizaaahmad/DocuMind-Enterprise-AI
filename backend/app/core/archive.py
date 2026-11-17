"""Private document volume archives; never extract links or escaping paths."""

import argparse
import os
import tarfile
from pathlib import Path, PurePosixPath


def validate_members(members):
    for member in members:
        path = PurePosixPath(member.name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in member.name
            or not (member.isfile() or member.isdir())
        ):
            raise ValueError("Unsafe document archive")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["pack", "restore"])
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    root = Path("/data/documents")
    if args.command == "pack":
        with tarfile.open(args.archive, "w:gz") as archive:
            for path in root.rglob("*"):
                if path.is_symlink():
                    raise SystemExit("Backup refuses symlinks")
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(root), recursive=False)
    else:
        if any(root.iterdir()):
            raise SystemExit("Restore requires an empty document volume")
        with tarfile.open(args.archive, "r:gz") as archive:
            validate_members(archive.getmembers())
            archive.extractall(root, filter="data")
        if os.getuid() == 0:
            for path in [root, *root.rglob("*")]:
                os.chown(path, 10001, 10001)


if __name__ == "__main__":
    main()
