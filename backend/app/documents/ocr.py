"""Selective PDF OCR through the native Tesseract CLI; no temporary image files."""

import math
import os
import shutil
import subprocess
import time


class OCRError(ValueError):
    pass


def meaningful_characters(text: str) -> int:
    return sum(character.isalnum() for character in text)


def needs_ocr(page, text: str, threshold: int) -> bool:
    import pymupdf

    count = meaningful_characters(text)
    clean = "\ufffd" not in text and not any(ord(c) < 32 and c not in "\r\n\t\f" for c in text)
    if count >= threshold and clean:
        return False
    # A short native title/cover is legitimate text. Only substantial graphics
    # (a scan behind a small footer, or vector outlines) justify OCR in that case.
    page_area = max(1, page.rect.width * page.rect.height)
    raster_area, paths = 0.0, 0
    for kind, box, *_ in page.get_bboxlog():
        if kind == "fill-image":
            region = (pymupdf.Rect(box) * page.rotation_matrix) & page.rect
            raster_area += max(0, region.width) * max(0, region.height)
        elif kind in {"fill-path", "stroke-path"}:
            paths += 1
    if count > 0 and clean:
        return raster_area / page_area >= 0.25 or paths >= 20
    return raster_area > 0 or paths > 0 or (not clean and bool(text.strip()))


def page_has_ink(page, ignore_native=False) -> bool:
    import pymupdf

    width, height = page.rect.width, page.rect.height
    if not all(math.isfinite(n) and n > 0 for n in (width, height)):
        raise OCRError("PDF page dimensions are invalid")
    scale = min(1, 512 / max(width, height))
    pixmap = page.get_pixmap(
        matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csGRAY, alpha=False, annots=False
    )
    samples = bytearray(pixmap.samples)
    if ignore_native:
        # Native words on an otherwise white scan do not justify OCR. Ignore
        # their thumbnail rectangles, but retain all pixels for actual OCR.
        for kind, box, *_ in page.get_bboxlog():
            if kind not in {"fill-text", "stroke-text"}:
                continue
            rect = pymupdf.Rect(box) * page.rotation_matrix
            left = max(0, math.floor(rect.x0 * scale) - pixmap.x - 1)
            right = min(pixmap.width, math.ceil(rect.x1 * scale) - pixmap.x + 1)
            top = max(0, math.floor(rect.y0 * scale) - pixmap.y - 1)
            bottom = min(pixmap.height, math.ceil(rect.y1 * scale) - pixmap.y + 1)
            if right > left:
                for row in range(top, bottom):
                    offset = row * pixmap.stride
                    samples[offset + left : offset + right] = b"\xff" * (right - left)
    return sum(value < 245 for value in samples) >= 4


class PDFOCR:
    def __init__(self, limits):
        self.limits = limits
        self.started = None
        self.pages = []
        self.executable = None

    def remaining(self) -> float:
        if self.started is None:
            self.started = time.monotonic()
        remaining = self.limits.ocr_document_timeout_seconds - (time.monotonic() - self.started)
        if remaining <= 0:
            raise OCRError(
                "OCR document time budget exceeded; reduce pages/DPI or increase "
                "OCR_DOCUMENT_TIMEOUT_SECONDS"
            )
        return remaining

    def environment(self) -> dict:
        return {**os.environ, "OMP_THREAD_LIMIT": "1", "OMP_NUM_THREADS": "1"}

    def language_args(self) -> list[str]:
        directory = self.limits.ocr_tessdata_dir
        return ["--tessdata-dir", str(directory)] if directory else []

    def check_installation(self):
        executable = shutil.which(self.limits.tesseract_cmd)
        if not executable:
            raise OCRError(
                "Tesseract was not found; install it and configure TESSERACT_CMD, then retry"
            )
        try:
            result = subprocess.run(
                [executable, *self.language_args(), "--list-langs"],
                capture_output=True,
                timeout=min(5, self.remaining()),
                env=self.environment(),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            raise OCRError(
                "Tesseract installation check timed out; verify the executable and language data"
            ) from None
        except OSError:
            raise OCRError(
                "Tesseract could not start; verify TESSERACT_CMD and installation permissions"
            ) from None
        languages = set(result.stdout.decode("utf-8", errors="replace").splitlines())
        if result.returncode or not set(self.limits.ocr_language.split("+")).issubset(languages):
            raise OCRError(
                "Tesseract language data is unavailable; install the language or correct "
                "OCR_TESSDATA_DIR"
            )
        self.executable = executable

    def read_page(self, page, number: int, native_text="") -> str | None:
        self.remaining()
        if not page_has_ink(
            page,
            ignore_native=bool(meaningful_characters(native_text)) and "\ufffd" not in native_text,
        ):
            return None
        if len(self.pages) >= self.limits.ocr_max_pages:
            raise OCRError(
                "PDF exceeds OCR_MAX_PAGES; split the document or increase the OCR page limit"
            )
        import pymupdf

        width = math.ceil(page.rect.width * self.limits.ocr_dpi / 72) + 2
        height = math.ceil(page.rect.height * self.limits.ocr_dpi / 72) + 2
        if width * height > self.limits.ocr_max_pixels:
            raise OCRError(
                f"Page {number} exceeds OCR_MAX_PIXELS; lower OCR_DPI or split/resize the page"
            )
        if self.executable is None:
            self.check_installation()
        pixmap = page.get_pixmap(
            dpi=self.limits.ocr_dpi, colorspace=pymupdf.csGRAY, alpha=False, annots=False
        )
        if pixmap.width * pixmap.height > self.limits.ocr_max_pixels:
            raise OCRError(f"Page {number} exceeds OCR_MAX_PIXELS; lower OCR_DPI")
        image = pixmap.tobytes("png")
        del pixmap
        remaining = self.remaining()
        timeout = min(self.limits.ocr_page_timeout_seconds, remaining)
        try:
            # PNG bytes go over stdin, recognized text over stdout: no persisted raster copies.
            result = subprocess.run(
                [
                    self.executable,
                    "stdin",
                    "stdout",
                    *self.language_args(),
                    "-l",
                    self.limits.ocr_language,
                    "--dpi",
                    str(self.limits.ocr_dpi),
                    "--psm",
                    "3",
                ],
                input=image,
                capture_output=True,
                timeout=timeout,
                env=self.environment(),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            if remaining <= self.limits.ocr_page_timeout_seconds:
                raise OCRError(
                    "OCR document time budget exceeded; reduce pages/DPI or increase "
                    "OCR_DOCUMENT_TIMEOUT_SECONDS"
                ) from None
            raise OCRError(
                f"OCR timed out on page {number}; lower OCR_DPI or increase "
                "OCR_PAGE_TIMEOUT_SECONDS"
            ) from None
        except OSError:
            raise OCRError(
                f"Tesseract could not run on page {number}; verify the installation"
            ) from None
        if result.returncode:
            raise OCRError(
                f"Tesseract failed on page {number}; check scan quality, language and memory limits"
            )
        text = result.stdout.decode("utf-8", errors="replace").strip()
        if not meaningful_characters(text):
            raise OCRError(
                f"OCR found no readable text on page {number}; check language/DPI "
                "or upload a clearer scan"
            )
        self.pages.append(number)
        self.remaining()
        return text

    def metadata(self) -> dict:
        return {
            "ocr_engine": "Tesseract",
            "ocr_language": self.limits.ocr_language,
            "ocr_dpi": self.limits.ocr_dpi,
            "ocr_page_count": len(self.pages),
            "ocr_page_numbers": ", ".join(map(str, self.pages)),
        }
