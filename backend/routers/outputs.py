"""Outputs management endpoints."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from services import audit_service, outputs_service


router = APIRouter(prefix="/api/studies", tags=["outputs"])


class StatusUpdate(BaseModel):
    status: str  # only 'pending' (reset) — QC/sign-off have dedicated endpoints


class QcItem(BaseModel):
    id: str
    label: str
    result: Literal["pass", "fail", "na"]
    comment: str = ""


class QcPayload(BaseModel):
    reviewer: str = Field(min_length=1)
    items: list[QcItem]
    comments: str = ""
    auto_checks: dict[str, Any] = Field(default_factory=dict)


class SignoffPayload(BaseModel):
    name: str = Field(min_length=1)
    comment: str = ""


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
    audit_service.log_event(study_id, "output.downloaded", {"output_id": output_id})
    return FileResponse(path, filename=path.name)


@router.get("/{study_id}/outputs/{output_id}/audit")
def audit(study_id: str, output_id: str) -> dict:
    return outputs_service.get_audit(study_id, output_id)


@router.post("/{study_id}/outputs/{output_id}/status")
def set_status(study_id: str, output_id: str, payload: StatusUpdate) -> dict:
    """Reset an output's review back to Pending QC.

    Direct approval is intentionally not allowed here — QC goes through
    POST .../qc and sign-off through POST .../signoff so the review trail
    is always recorded.
    """
    if payload.status != "pending":
        raise HTTPException(
            status_code=422,
            detail="Only 'pending' (reset) is allowed; use the /qc and /signoff endpoints for review.",
        )
    return {"status": outputs_service.reset_review(study_id, output_id)}


@router.post("/{study_id}/outputs/{output_id}/qc")
def record_qc(study_id: str, output_id: str, payload: QcPayload) -> dict:
    """Record the QC programmer's checklist review (pass/fail)."""
    try:
        audit = outputs_service.record_qc(study_id, output_id, payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "qc_passed" if audit["qc"]["result"] == "pass" else "qc_failed", "audit": audit}


@router.post("/{study_id}/outputs/{output_id}/signoff")
def record_signoff(study_id: str, output_id: str, payload: SignoffPayload) -> dict:
    """Record the biostatistician sign-off (requires a passed QC)."""
    try:
        audit = outputs_service.record_signoff(study_id, output_id, payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "approved", "audit": audit}


@router.get("/{study_id}/outputs/package")
def package(study_id: str, approved_only: bool = False) -> Response:
    """Zip the study's outputs for download.

    GET (not POST) because the frontend triggers this from a plain link.
    `approved_only=true` restricts the package to approved outputs.
    """
    data, filename = outputs_service.package(study_id, approved_only=approved_only)
    audit_service.log_event(
        study_id, "package.downloaded",
        {"filename": filename, "signed_off_only": approved_only},
    )
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Study audit trail
# ---------------------------------------------------------------------------

@router.get("/{study_id}/audit-trail")
def audit_trail(study_id: str) -> dict:
    """The study's full audit trail plus a hash-chain integrity check."""
    return {
        "entries": audit_service.list_events(study_id),
        "chain": audit_service.verify_chain(study_id),
    }


@router.get("/{study_id}/audit-trail/export")
def audit_trail_export(study_id: str) -> Response:
    csv_text = audit_service.to_csv(study_id)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{study_id}_audit_trail.csv"'},
    )
