import hashlib
import os
import uuid
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import Settings


class UploadTooLarge(ValueError):
    pass


class Storage(Protocol):
    def save(
        self, org: uuid.UUID, doc: uuid.UUID, source: BinaryIO, limit: int
    ) -> tuple[int, str]: ...
    def open(self, org: uuid.UUID, doc: uuid.UUID) -> BinaryIO: ...
    def delete(self, org: uuid.UUID, doc: uuid.UUID) -> None: ...
    def materialize(self, org: uuid.UUID, doc: uuid.UUID) -> AbstractContextManager[Path]: ...


def get_storage(settings: Settings) -> Storage:
    """Replace this factory with a cloud adapter without changing API use cases."""
    return LocalStorage(settings.storage_path)


class LocalStorage:
    """Opaque UUID-based keys only; caller must authorize before invoking storage."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def path(self, org: uuid.UUID, doc: uuid.UUID) -> Path:
        path = (
            self.root / str(uuid.UUID(str(org))) / str(uuid.UUID(str(doc))) / "original"
        ).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Storage key escapes configured root")
        return path

    def save(self, org: uuid.UUID, doc: uuid.UUID, source: BinaryIO, limit: int) -> tuple[int, str]:
        path = self.path(org, doc)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = path.with_name("upload.part")
        total, checksum = 0, hashlib.sha256()
        try:
            with temporary.open("xb") as destination:
                while block := source.read(64 * 1024):
                    total += len(block)
                    if total > limit:
                        raise UploadTooLarge("File exceeds the configured upload limit")
                    destination.write(block)
                    checksum.update(block)
                destination.flush()
                os.fsync(destination.fileno())
            os.replace(temporary, path)
            return total, checksum.hexdigest()
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def open(self, org: uuid.UUID, doc: uuid.UUID) -> BinaryIO:
        return self.path(org, doc).open("rb")

    @contextmanager
    def materialize(self, org: uuid.UUID, doc: uuid.UUID) -> Iterator[Path]:
        # Local parsing needs no duplicate file in OS temp. A future cloud adapter
        # can stage a managed local file through this context manager instead.
        yield self.path(org, doc)

    def delete(self, org: uuid.UUID, doc: uuid.UUID) -> None:
        path = self.path(org, doc)
        path.unlink(missing_ok=True)
        path.with_name("upload.part").unlink(missing_ok=True)
        if path.parent.exists():
            path.parent.rmdir()
