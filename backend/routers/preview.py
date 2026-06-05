"""Preview endpoints — generate a table's data as JSON for the HTML view."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services import generation_service, preview_service


router = APIRouter(prefix="/api/studies", tags=["preview"])


@router.post("/{study_id}/preview/{table_id}")
def preview(study_id: str, table_id: str) -> dict:
    try:
        return preview_service.generate_preview(study_id, table_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Aggregation can fail for many reasons (missing column, empty
        # dataset, etc.). Surface as 422 so the UI can show a friendly
        # message instead of the user seeing a 500.
        raise HTTPException(status_code=422, detail=f"{type(exc).__name__}: {exc}") from exc


@router.get("/{study_id}/preview/{table_id}/rtf")
def download_rtf(study_id: str, table_id: str) -> FileResponse:
    """Generate the shell on demand and return its RTF as a download.

    This always produces a fresh file from the study's current data and
    config, so it works even if the user hasn't run a generation job yet.
    """
    try:
        out_path = Path(generation_service.generate_file(study_id, table_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"{type(exc).__name__}: {exc}") from exc

    if not out_path.exists():
        raise HTTPException(status_code=500, detail="Generation produced no file.")

    media = "application/rtf" if out_path.suffix.lower() == ".rtf" else "application/octet-stream"
    return FileResponse(str(out_path), filename=out_path.name, media_type=media)
