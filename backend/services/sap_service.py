"""SAP PDF text extraction via pdfplumber."""

from __future__ import annotations

from pathlib import Path


def extract_text(pdf_path: Path) -> str:
    """Concatenate page text from a SAP PDF. Returns the raw string."""
    import pdfplumber

    out: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                out.append(text)
    return "\n\n".join(out)
