"""Pydantic models for the AI-powered endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# SAP extraction
# ---------------------------------------------------------------------------

class SapDefinitionField(BaseModel):
    """One SAP-extracted field with provenance and a confidence indicator."""
    value: str
    source_excerpt: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"


class OptionalOutputDecision(BaseModel):
    flag: str                                  # e.g. 'table_14_3_1_13_ae_by_severity'
    enabled: bool
    reason: str = ""
    source_excerpt: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"


class SapExtractionRequest(BaseModel):
    """Body of POST /api/ai/sap. Either text or a previously-uploaded file path."""
    pdf_text: str | None = None
    study_id: str | None = None
    file_token: str | None = None              # set when the PDF was uploaded


class SapExtractionResponse(BaseModel):
    """Full structured SAP extraction returned to the wizard."""
    sap_definitions: dict[str, SapDefinitionField]
    optional_outputs: list[OptionalOutputDecision]
    primary_endpoint: SapDefinitionField | None = None
    secondary_endpoints: list[str] = Field(default_factory=list)
    subgroup_analyses: list[str] = Field(default_factory=list)
    raw_excerpt_sample: str = ""               # first ~500 chars for sanity
    error: str | None = None                   # set when AI returned malformed JSON


# ---------------------------------------------------------------------------
# Protocol extraction
# ---------------------------------------------------------------------------

class ExtractedField(BaseModel):
    """A single extracted value with provenance and a confidence indicator."""
    value: str = ""
    source_excerpt: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"


class ProtocolExtractionResponse(BaseModel):
    """Study-level metadata extracted from the protocol, for human review.

    `fields` keys are study_config metadata names: protocol_number,
    protocol_title, indication, phase, study_design, primary_objective,
    treatment_summary.
    """
    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    raw_excerpt_sample: str = ""
    error: str | None = None


# ---------------------------------------------------------------------------
# CRF extraction
# ---------------------------------------------------------------------------

class CrfCategoryList(BaseModel):
    """A categorical variable's collected values and CRF order."""
    variable: str                              # ADaM variable, e.g. RACE, DCDECOD
    label: str = ""                            # human label, e.g. "Race"
    values: list[str] = Field(default_factory=list)
    source_excerpt: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"


class CrfExtractionResponse(BaseModel):
    """Category lists/order the CRF defines, for human review then generation."""
    category_lists: list[CrfCategoryList] = Field(default_factory=list)
    raw_excerpt_sample: str = ""
    error: str | None = None


# ---------------------------------------------------------------------------
# Natural-language shell selection
# ---------------------------------------------------------------------------

class NlShellRequest(BaseModel):
    study_id: str
    instruction: str
    current_selection: dict[str, bool] = Field(default_factory=dict)


class NlShellChange(BaseModel):
    shell_id: str
    action: Literal["add", "remove"]
    reason: str = ""


class NlShellResponse(BaseModel):
    changes: list[NlShellChange]
    summary: str = ""
    error: str | None = None


# ---------------------------------------------------------------------------
# Table chat
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    study_id: str
    table_id: str
    messages: list[ChatMessage]


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

class AnomalyRequest(BaseModel):
    study_id: str
    table_id: str


class Anomaly(BaseModel):
    severity: Literal["warning", "info"]
    description: str
    location: str = ""
    rule: str = ""
    source: Literal["rule", "ai"] = "rule"


class AnomalyResponse(BaseModel):
    anomalies: list[Anomaly]
