import codecs
import re
import unicodedata
import zipfile
from pathlib import PurePosixPath
from typing import BinaryIO

from app.core.config import Settings

MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
}


class InvalidDocument(ValueError):
    pass


def safe_filename(value: str) -> tuple[str, str]:
    name = unicodedata.normalize("NFKC", value or "").replace("\\", "/").split("/")[-1]
    name = "".join(c for c in name if not unicodedata.category(c).startswith("C"))
    name = re.sub(r'[<>:"/\\|?*]', "_", name).strip(" .")
    stem, separator, extension = name.rpartition(".")
    extension = extension.lower()
    if not separator or not stem or extension not in MIME_TYPES:
        raise InvalidDocument("Choose a PDF, DOCX, or TXT file")
    if stem.upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *[f"COM{i}" for i in range(1, 10)],
        *[f"LPT{i}" for i in range(1, 10)],
    }:
        stem = "_" + stem
    return f"{stem[:170]}.{extension}", extension


def text_encoding(head: bytes) -> str:
    return "utf-16" if head.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"


def validate_docx(source: BinaryIO, settings: Settings):
    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            names = {item.filename for item in entries}
            if not {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                raise InvalidDocument("File is not a valid DOCX document")
            if (
                len(entries) > 2000
                or sum(i.file_size for i in entries) > settings.docx_max_uncompressed_bytes
            ):
                raise InvalidDocument("DOCX archive exceeds safe extraction limits")
            for item in entries:
                if (
                    item.flag_bits & 1
                    or ".." in PurePosixPath(item.filename).parts
                    or item.filename.startswith(("/", "\\"))
                    or "\\" in item.filename
                    or "vbaproject" in item.filename.lower()
                ):
                    raise InvalidDocument(
                        "Encrypted, unsafe, or macro-enabled DOCX files are not supported"
                    )
    except (zipfile.BadZipFile, KeyError):
        raise InvalidDocument("File is not a valid DOCX document") from None
    finally:
        source.seek(0)


def validate_file(source: BinaryIO, extension: str, content_type: str | None, settings: Settings):
    allowed = {MIME_TYPES[extension], "application/octet-stream"}
    if extension == "docx":
        allowed.add("application/zip")
    if content_type and content_type.split(";")[0].lower() not in allowed:
        raise InvalidDocument("File content type does not match its extension")
    head = source.read(4096)
    source.seek(0)
    if not head:
        raise InvalidDocument("Empty files cannot be uploaded")
    if extension == "pdf" and not head.startswith(b"%PDF-"):
        raise InvalidDocument("File does not have a valid PDF signature")
    if extension == "docx":
        validate_docx(source, settings)
    if extension == "txt":
        try:
            decoded = codecs.getincrementaldecoder(text_encoding(head))().decode(head, final=False)
            if any(ord(c) < 32 and c not in "\n\r\t\f" for c in decoded):
                raise ValueError
        except (UnicodeError, ValueError):
            raise InvalidDocument(
                "TXT files must contain UTF-8 or BOM-marked UTF-16 text"
            ) from None
