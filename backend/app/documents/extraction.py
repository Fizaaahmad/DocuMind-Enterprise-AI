"""Text adapters. PDF parsing must run in a separate process, never API threads."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from app.documents.ocr import PDFOCR, OCRError, needs_ocr
from app.documents.process_limits import ResourceLimitError, apply_memory_limit
from app.documents.validation import InvalidDocument, text_encoding, validate_docx


class ExtractionError(ValueError):
    pass


def extract(path: Path, format: str, limits) -> dict:
    sections, metadata = [], {}
    total = 0

    def add(text: str, label: str, page: int | None = None):
        nonlocal total
        text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
        total += len(text)
        if total > limits.extraction_max_characters:
            raise ExtractionError("Extracted text exceeds the configured character limit")
        sections.append({"text": text, "label": label[:200], "page_number": page})

    try:
        if format == "pdf":
            import pymupdf

            with pymupdf.open(path) as document:
                if document.needs_pass:
                    raise ExtractionError("Password-protected PDFs are not supported")
                if document.page_count > limits.extraction_max_pages:
                    raise ExtractionError("PDF exceeds the configured page limit")
                metadata = {
                    key: str(value)[:500]
                    for key, value in document.metadata.items()
                    if key in {"title", "author", "subject", "creationDate"} and value
                }
                metadata["page_count"] = document.page_count
                ocr = PDFOCR(limits) if getattr(limits, "ocr_enabled", False) else None
                for number, page in enumerate(document, 1):
                    text = page.get_text("text", sort=True)
                    label = f"Page {number}"
                    if ocr:
                        label += " · native"
                        if needs_ocr(page, text, limits.ocr_min_text_characters):
                            recognized = ocr.read_page(page, number, native_text=text)
                            if recognized is not None:
                                text, label = recognized, f"Page {number} · OCR"
                    add(text, label, number)
                if ocr:
                    metadata.update(ocr.metadata())
                    metadata["native_page_count"] = document.page_count - len(ocr.pages)
        elif format == "docx":
            from docx import Document
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            with path.open("rb") as source:
                validate_docx(source, limits)
            document = Document(path)
            metadata = {
                "title": (document.core_properties.title or "")[:500],
                "author": (document.core_properties.author or "")[:500],
            }
            buffer, heading, block_start = [], "Document body", 1
            for index, block in enumerate(document.iter_inner_content(), 1):
                text = (
                    block.text
                    if isinstance(block, Paragraph)
                    else "\n".join("\t".join(cell.text for cell in row.cells) for row in block.rows)
                    if isinstance(block, Table)
                    else ""
                )
                is_heading = isinstance(block, Paragraph) and block.style.name.startswith("Heading")
                if buffer and (is_heading or sum(len(item) for item in buffer) >= 8000):
                    add("\n\n".join(buffer), f"{heading} · blocks {block_start}–{index - 1}")
                    buffer, block_start = [], index
                if is_heading:
                    heading = text[:120] or "Untitled section"
                buffer.append(text)
                # Bound intermediate accumulation even for a single enormous paragraph.
                if total + sum(len(item) for item in buffer) > limits.extraction_max_characters:
                    raise ExtractionError("Extracted text exceeds the configured character limit")
            if buffer:
                add("\n\n".join(buffer), f"{heading} · from block {block_start}")
        elif format == "txt":
            raw = path.read_bytes()
            encoding = text_encoding(raw[:4])
            text = raw.decode(encoding)
            if any(ord(c) < 32 and c not in "\n\r\t\f" for c in text):
                raise ExtractionError("TXT file contains binary control characters")
            metadata = {"encoding": encoding}
            add(text, "Text document")
        else:
            raise ExtractionError("Unsupported document format")
    except (ExtractionError, InvalidDocument, OCRError):
        raise
    except UnicodeError:
        raise ExtractionError("TXT encoding is invalid; use UTF-8 or BOM-marked UTF-16") from None
    except MemoryError:
        raise
    except Exception:
        raise ExtractionError(
            "Document could not be extracted; it may be damaged or unsupported"
        ) from None
    if not any(section["text"].strip() for section in sections):
        if getattr(limits, "ocr_enabled", False) and format == "pdf":
            raise ExtractionError(
                "No readable text found; upload a clearer scan or verify OCR language/DPI"
            )
        raise ExtractionError(
            "No readable text found. Scanned PDFs require OCR, which is not enabled"
        )
    return {"sections": sections, "metadata": metadata, "character_count": total}


if __name__ == "__main__":
    # Only parser limits travel over stdin. No credentials or document text in logs.
    limits = SimpleNamespace(**json.loads(sys.stdin.read()))
    try:
        if getattr(limits, "ocr_enabled", False) and sys.argv[2] == "pdf":
            apply_memory_limit(limits.ocr_memory_limit_mb)
        result = extract(Path(sys.argv[1]), sys.argv[2], limits)
        sys.stdout.write(json.dumps({"result": result}, ensure_ascii=True))
    except (ExtractionError, InvalidDocument, OCRError, ResourceLimitError) as exc:
        sys.stdout.write(json.dumps({"error": str(exc)}))
        raise SystemExit(2)
    except MemoryError:
        sys.stdout.write(
            json.dumps(
                {
                    "error": "OCR parser memory limit reached; lower DPI or increase "
                    "OCR_MEMORY_LIMIT_MB"
                }
            )
        )
        raise SystemExit(2)
