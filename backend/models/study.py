"""Pydantic models for studies, ADaM metadata, and study config."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StudyStatus(str, Enum):
    """Lifecycle status surfaced on the Study List dashboard."""
    DRAFT = "draft"
    READY = "ready"
    GENERATING = "generating"
    COMPLETE = "complete"


# ---------------------------------------------------------------------------
# Treatment-arm and analysis-set representations
# ---------------------------------------------------------------------------

class TreatmentArm(BaseModel):
    """A single arm; column order in the output matches the array order."""
    label: str
    trtpn: int
    column_header: str
    target_daily_dose_mg: float | None = None


class AnalysisSet(BaseModel):
    """One analysis set (SAF / ITT / EFF / ALL).

    `n` is keyed by stringified trtpn (JSON-safe), e.g. {"54": 84, ...}.
    """
    label: str
    flag_var: str | None = None
    flag_val: str | None = None
    n: dict[str, int | None] = Field(default_factory=dict)


class SapDefinitions(BaseModel):
    """SAP-driven definitions interpolated into footnotes."""
    teae_definition: str = ""
    baseline_definition: str = ""
    related_ae_definition: str = ""
    exposure_duration_definition: str = ""
    compliance_definition: str = ""
    prior_medication_definition: str = ""
    concomitant_medication_definition: str = ""
    primary_endpoint: str = ""
    secondary_endpoints: list[str] = Field(default_factory=list)
    subgroup_analyses: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Study metadata stored alongside study_config.yaml
# ---------------------------------------------------------------------------

class StudyMeta(BaseModel):
    """App-level metadata persisted as study_meta.json."""
    study_id: str
    title: str
    drug: str = ""
    indication: str = ""
    status: StudyStatus = StudyStatus.DRAFT
    created_at: datetime
    updated_at: datetime
    last_generated_at: datetime | None = None


# ---------------------------------------------------------------------------
# API payloads
# ---------------------------------------------------------------------------

class StudyCreate(BaseModel):
    """Request body for POST /studies."""
    title: str
    protocol_number: str = ""
    drug: str = ""
    indication: str = ""


class StudyUpdate(BaseModel):
    """Partial update to study_config.yaml. All fields optional."""
    protocol_number: str | None = None
    protocol_title: str | None = None
    drug: str | None = None
    indication: str | None = None
    data_extract_date: str | None = None
    data_cut_date: str | None = None
    sas_version: str | None = None
    meddra_version: str | None = None
    who_drug_version: str | None = None
    treatment_arms: list[TreatmentArm] | None = None
    pooled_active: bool | None = None
    include_total_column: bool | None = None
    analysis_sets: dict[str, AnalysisSet] | None = None
    sap_definitions: SapDefinitions | None = None
    optional_outputs: dict[str, bool] | None = None
    common_ae_cutoff_pct: float | None = None
    exposure_duration_bins: list[dict[str, Any]] | None = None


class StudySummary(BaseModel):
    """Shape used in the /studies list view."""
    study_id: str
    title: str
    protocol_number: str
    drug: str
    indication: str
    status: StudyStatus
    n_arms: int
    total_n: int
    selected_tables: int
    available_tables: int
    last_generated_at: datetime | None
    updated_at: datetime


class StudyDetail(BaseModel):
    """Full study view: meta + the raw study_config dict."""
    meta: StudyMeta
    config: dict[str, Any]


# ---------------------------------------------------------------------------
# Upload + metadata extraction
# ---------------------------------------------------------------------------

class DomainSummary(BaseModel):
    """Per-file summary returned after /upload."""
    filename: str
    domain: str                              # e.g. 'adsl', 'adae'
    n_rows: int
    n_subjects: int                          # USUBJID.nunique() when present
    columns: list[str]
    notes: list[str] = Field(default_factory=list)


class UploadResult(BaseModel):
    """Aggregate response from /studies/{id}/upload."""
    study_id: str
    domains: list[DomainSummary]
    detected_arms: list[TreatmentArm]
    detected_analysis_sets: dict[str, AnalysisSet]
    visit_schedule: list[str] = Field(default_factory=list)
    available_paramcds: dict[str, list[str]] = Field(default_factory=dict)
    study_id_value: str | None = None        # value of STUDYID from ADSL
