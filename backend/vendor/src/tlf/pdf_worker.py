"""Helper process that asks Microsoft Word to export one RTF as a PDF.

This file is not normally called by table modules directly. pdf.py launches
it as a separate process so the main program can enforce a timeout around
Word automation.

Given an input RTF path and an output PDF path, this worker opens Word in
the background, opens the RTF read-only, exports the document as PDF, then
closes Word as cleanly as possible.
"""

from __future__ import annotations

import sys
from pathlib import Path


# wdExportFormatPDF constant from the Word object model
_WD_EXPORT_FORMAT_PDF = 17


def _convert(rtf_path: Path, pdf_path: Path) -> None:
    """Drive Word through one RTF → PDF conversion. Raises on failure."""
    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()
    word = None
    doc = None
    try:
        word = win32.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False

        doc = word.Documents.Open(
            str(rtf_path),
            ReadOnly=True,
            AddToRecentFiles=False,
        )
        doc.ExportAsFixedFormat(
            OutputFileName=str(pdf_path),
            ExportFormat=_WD_EXPORT_FORMAT_PDF,
            OpenAfterExport=False,
            OptimizeFor=0,    # wdExportOptimizeForPrint
            Range=0,           # wdExportAllDocument
            IncludeDocProps=True,
            KeepIRM=True,
            CreateBookmarks=0,
            DocStructureTags=True,
            BitmapMissingFonts=True,
            UseISO19005_1=False,
        )
    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m tlf.pdf_worker <rtf_path> <pdf_path>", file=sys.stderr)
        return 2
    rtf_path = Path(argv[0]).resolve()
    pdf_path = Path(argv[1]).resolve()
    try:
        _convert(rtf_path, pdf_path)
    except Exception as exc:
        # Print the error so the parent can surface it in its log
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
