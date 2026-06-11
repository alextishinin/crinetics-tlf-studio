"""Outputs management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from services import outputs_service


router = APIRouter(prefix="/api/studies", tags=["outputs"])


class StatusUpdate(BaseModel):
    status: str  # 'approved' | 'pending'


@router.get("/{study_id}/outputs")
def list_outputs(study_id: str) -> list[dict]:
    recs = outputs_service.list_outputs(study_id)
    return [
        {
            "output_id": r.output_id,
            "filename": r.filename,
            "table_number": r.table_number,
            "table_id": r.table_id,
            "population": r.population,
            "generated_at": r.generated_at.isoformat(),
            "size_bytes": r.size_bytes,
            "status": r.status,
            "audit_path": r.audit_path,
        }
        for r in recs
    ]


@router.get("/{study_id}/outputs/{output_id}/download")
def download(study_id: str, output_id: str):
    try:
        path = outputs_service.get_path(study_id, output_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, filename=path.name)


@router.get("/{study_id}/outputs/{output_id}/audit")
def audit(study_id: str, output_id: str) -> dict:
    return outputs_service.get_audit(study_id, output_id)


@router.post("/{study_id}/outputs/{output_id}/status")
def set_status(study_id: str, output_id: str, payload: StatusUpdate) -> dict:
    return {"status": outputs_service.set_status(study_id, output_id, payload.status)}


@router.get("/{study_id}/outputs/package")
def package(study_id: str, approved_only: bool = False) -> Response:
    """Zip the study's outputs for download.

    GET (not POST) because the frontend triggers this from a plain link.
    `approved_only=true` restricts the package to approved outputs.
    """
    data, filename = outputs_service.package(study_id, approved_only=approved_only)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
