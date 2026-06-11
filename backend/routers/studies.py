"""Study CRUD + ADaM upload endpoints."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from models.study import (
    StudyCreate,
    StudyDetail,
    StudySummary,
    StudyUpdate,
    UploadResult,
)
from services import adam_service, audit_service, study_service


router = APIRouter(prefix="/api/studies", tags=["studies"])


@router.get("", response_model=list[StudySummary])
def list_studies() -> list[StudySummary]:
    return study_service.list_studies()


@router.post("", response_model=StudyDetail, status_code=201)
def create_study(payload: StudyCreate) -> StudyDetail:
    return study_service.create_study(payload)


@router.get("/{study_id}", response_model=StudyDetail)
def get_study(study_id: str) -> StudyDetail:
    try:
        return study_service.read_detail(study_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{study_id}", response_model=StudyDetail)
def update_study(study_id: str, payload: StudyUpdate) -> StudyDetail:
    try:
        return study_service.update_config(study_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{study_id}", status_code=204)
def delete_study(study_id: str) -> None:
    try:
        study_service.delete_study(study_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{study_id}/upload", response_model=UploadResult)
async def upload_files(study_id: str, files: list[UploadFile] = File(...)) -> UploadResult:
    try:
        path = study_service.study_dir(study_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    data_dir = path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    uploaded: list[dict] = []
    for upload in files:
        target = data_dir / Path(upload.filename or "unknown").name
        contents = await upload.read()
        target.write_bytes(contents)
        uploaded.append({
            "filename": target.name,
            "size_bytes": len(contents),
            "sha256": hashlib.sha256(contents).hexdigest(),
        })

    audit_service.log_event(study_id, "data.uploaded", {"files": uploaded})
    return adam_service.extract_metadata(study_id, data_dir)
