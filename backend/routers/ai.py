"""AI endpoints — SAP extraction, NL shells, anomaly detection, chat."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from models.ai import (
    AnomalyRequest,
    AnomalyResponse,
    ChatRequest,
    NlShellRequest,
    NlShellResponse,
    SapExtractionRequest,
    SapExtractionResponse,
)
from services import ai_service, preview_service, sap_service, shell_service, study_service


router = APIRouter(prefix="/api/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# SAP extraction
# ---------------------------------------------------------------------------

@router.post("/sap", response_model=SapExtractionResponse)
async def extract_sap(
    file: UploadFile | None = File(default=None),
    pdf_text: str | None = None,
) -> SapExtractionResponse:
    """Upload a SAP as PDF or DOCX (multipart `file`), or POST raw text.

    The uploaded document is converted to Markdown server-side before it is
    sent to the model.
    """
    if file is None and not pdf_text:
        raise HTTPException(status_code=400, detail="Provide a `file` upload or `pdf_text`.")

    text = pdf_text or ""
    if file is not None:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in sap_service.SUPPORTED_SUFFIXES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{suffix or 'unknown'}'. Upload a .pdf or .docx.",
            )
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        try:
            text = sap_service.extract_markdown(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    if not text.strip():
        raise HTTPException(status_code=422, detail="No extractable text in the document.")
    return ai_service.extract_sap(text)


# ---------------------------------------------------------------------------
# Natural-language shell selection
# ---------------------------------------------------------------------------

@router.post("/shells", response_model=NlShellResponse)
def nl_shells(payload: NlShellRequest) -> NlShellResponse:
    try:
        listing = shell_service.list_for_study(payload.study_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    available: list[dict[str, str]] = []
    for group in listing.groups:
        for s in group.shells:
            available.append(
                {
                    "id": s.id,
                    "title": s.title_line2,
                    "conditionality": s.conditionality.value,
                }
            )
    return ai_service.interpret_shell_instruction(
        payload.instruction, payload.current_selection, available,
    )


# ---------------------------------------------------------------------------
# Table chat (streaming)
# ---------------------------------------------------------------------------

@router.post("/chat")
def chat(payload: ChatRequest):
    try:
        preview = preview_service.generate_preview(payload.study_id, payload.table_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    config = study_service.read_config(payload.study_id)
    context = {
        "table": preview,
        "study": {
            "protocol_number": config.get("protocol_number"),
            "treatment_arms": config.get("treatment_arms"),
            "analysis_sets": config.get("analysis_sets"),
            "sap_definitions": config.get("sap_definitions"),
        },
    }

    def _stream():
        for chunk in ai_service.chat_stream(payload.messages, context):
            yield chunk

    return StreamingResponse(_stream(), media_type="text/plain")


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

@router.post("/anomalies", response_model=AnomalyResponse)
def anomalies(payload: AnomalyRequest) -> AnomalyResponse:
    try:
        preview = preview_service.generate_preview(payload.study_id, payload.table_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ai_service.detect_anomalies(preview)
