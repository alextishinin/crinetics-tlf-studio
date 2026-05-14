"""Shell registry + selection endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.shell import ShellListResponse, ShellSelections
from services import shell_service


router = APIRouter(prefix="/api/studies", tags=["shells"])


@router.get("/{study_id}/shells", response_model=ShellListResponse)
def get_shells(study_id: str) -> ShellListResponse:
    try:
        return shell_service.list_for_study(study_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{study_id}/shells")
def put_shells(study_id: str, payload: ShellSelections) -> dict[str, bool]:
    try:
        return shell_service.save_selections(study_id, payload.optional_outputs)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
