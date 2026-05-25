"""Document ingestion utilities for candidate material uploaded in the study UI."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


MAX_CV_CHARACTERS = 60_000
SUPPORTED_CV_SUFFIXES = {".pdf", ".txt", ".md"}


def extract_cv_text(filename: str, payload: bytes) -> str:
    """Extract non-empty CV text from a participant upload."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_CV_SUFFIXES:
        raise ValueError("Upload a PDF, TXT, or Markdown CV file.")
    if suffix == ".pdf":
        try:
            pages = PdfReader(BytesIO(payload)).pages
            text = "\n\n".join((page.extract_text() or "").strip() for page in pages)
        except Exception as exc:
            raise ValueError("The uploaded PDF could not be read as a CV document.") from exc
    else:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Uploaded text CV files must use UTF-8 encoding.") from exc
    return validate_cv_text(text)


def validate_cv_text(text: str) -> str:
    """Normalize pasted/uploaded CV text and enforce practical input limits."""
    normalized = "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()
    if not normalized:
        raise ValueError("The CV has no extractable text. Upload a text-based PDF or paste CV text.")
    if len(normalized) > MAX_CV_CHARACTERS:
        raise ValueError(f"The CV exceeds the {MAX_CV_CHARACTERS:,}-character limit.")
    return normalized
