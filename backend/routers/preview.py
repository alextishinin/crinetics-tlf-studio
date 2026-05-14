"""Preview endpoints — generate a table's data as JSON for the HTML view."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services import preview_service


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
