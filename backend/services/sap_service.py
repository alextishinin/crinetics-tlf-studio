"""Convert SAP documents (PDF or DOCX) to Markdown for AI parsing.

The SAP can arrive as a PDF or a Word (.docx) file. We convert it to a
Markdown string *before* sending it to the model:

  - .docx  -> mammoth (docx -> HTML) -> markdownify (HTML -> Markdown).
             This preserves headings, lists, and tables, which helps the
             model find analysis-set Ns, optional-output lists, etc.
  - .pdf   -> pdfplumber text extraction. Plain text is valid Markdown;
             page breaks are kept as horizontal rules so document
             structure survives.
"""

from __future__ import annotations

from pathlib import Path

SUPPORTED_SUFFIXES = {".pdf", ".docx"}


def extract_markdown(path: Path) -> str:
    """Convert a SAP document to a Markdown string.

    Supports .pdf and .docx. Raises ValueError for any other type.
    """
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_to_markdown(path)
    if suffix == ".docx":
        return _docx_to_markdown(path)
    raise ValueError(
        f"Unsupported SAP file type '{suffix or 'unknown'}'. Upload a .pdf or .docx."
    )


def _pdf_to_markdown(path: Path) -> str:
    """Extract text from a PDF, one block per page separated by a rule."""
    import pdfplumber

    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())
    return "\n\n---\n\n".join(pages)


def _docx_to_markdown(path: Path) -> str:
    """Convert a .docx to Markdown, preserving headings, lists, and tables."""
    import mammoth
    from markdownify import markdownify as html_to_md

    with open(path, "rb") as f:
        html = mammoth.convert_to_html(f).value
    return html_to_md(html, heading_style="ATX").strip()


# Backwards-compatible alias — older callers used extract_text() for PDFs.
def extract_text(path: Path) -> str:
    return extract_markdown(path)
