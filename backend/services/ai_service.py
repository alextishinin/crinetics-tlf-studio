"""Anthropic-backed AI features.

Every entrypoint here is built to:
  - Use claude-sonnet-4-20250514 (configurable via ANTHROPIC_MODEL)
  - Validate JSON responses with Pydantic before returning to the frontend
  - Surface raw model output in `error` field when parsing fails so the
    frontend can show a graceful fallback
"""

from __future__ import annotations

import json
from typing import Any, Iterator

import anthropic
from pydantic import ValidationError

from config import get_settings
from models.ai import (
    Anomaly,
    AnomalyResponse,
    ChatMessage,
    NlShellChange,
    NlShellResponse,
    OptionalOutputDecision,
    SapDefinitionField,
    SapExtractionResponse,
)


# ---------------------------------------------------------------------------
# Client + helpers
# ---------------------------------------------------------------------------

def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def _model() -> str:
    return get_settings().anthropic_model


def _strip_fence(text: str) -> str:
    """Strip ```json ... ``` fences if the model wrapped its reply."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _completion(system: str, user: str, *, max_tokens: int = 4096) -> str:
    """Single-shot completion. Falls back to empty string on transport error."""
    try:
        msg = _client().messages.create(
            model=_model(),
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(getattr(p, "text", "") for p in msg.content)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# SAP extraction
# ---------------------------------------------------------------------------

_SAP_SYSTEM = """You are a clinical study expert. Read the provided
Statistical Analysis Plan text and extract a structured JSON object that
matches this schema exactly:

{
  "sap_definitions": {
    "teae_definition":              {"value": str, "source_excerpt": str, "confidence": "high|medium|low"},
    "baseline_definition":          {"value": str, "source_excerpt": str, "confidence": "high|medium|low"},
    "related_ae_definition":        {"value": str, "source_excerpt": str, "confidence": "high|medium|low"},
    "exposure_duration_definition": {"value": str, "source_excerpt": str, "confidence": "high|medium|low"},
    "compliance_definition":        {"value": str, "source_excerpt": str, "confidence": "high|medium|low"}
  },
  "optional_outputs": [
    {"flag": str, "enabled": bool, "reason": str, "source_excerpt": str, "confidence": "high|medium|low"}
  ],
  "primary_endpoint":   {"value": str, "source_excerpt": str, "confidence": "high|medium|low"},
  "secondary_endpoints": [str],
  "subgroup_analyses":   [str]
}

Rules:
- Return ONLY valid JSON. No markdown, no preamble.
- For source_excerpt always quote the verbatim sentence(s) from the SAP
  that support the extraction.
- For optional_outputs reason about each table type: e.g. if the SAP
  mentions CTCAE grading, set table_14_3_1_3_grade3_aes=true.
- Use confidence="low" when the SAP is silent on the field.
"""


def extract_sap(pdf_text: str) -> SapExtractionResponse:
    raw = _completion(_SAP_SYSTEM, pdf_text[:50_000])
    if not raw:
        return SapExtractionResponse(
            sap_definitions={}, optional_outputs=[], error="Empty response from AI",
        )
    payload = _strip_fence(raw)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        return SapExtractionResponse(
            sap_definitions={}, optional_outputs=[],
            error=f"Malformed JSON: {exc}",
            raw_excerpt_sample=payload[:500],
        )

    try:
        sap_defs_raw = data.get("sap_definitions", {}) or {}
        sap_defs = {k: SapDefinitionField.model_validate(v) for k, v in sap_defs_raw.items()}
        optional_outputs = [
            OptionalOutputDecision.model_validate(d)
            for d in (data.get("optional_outputs") or [])
        ]
        primary = data.get("primary_endpoint")
        primary_field = SapDefinitionField.model_validate(primary) if primary else None
        return SapExtractionResponse(
            sap_definitions=sap_defs,
            optional_outputs=optional_outputs,
            primary_endpoint=primary_field,
            secondary_endpoints=list(data.get("secondary_endpoints") or []),
            subgroup_analyses=list(data.get("subgroup_analyses") or []),
            raw_excerpt_sample=payload[:500],
        )
    except ValidationError as exc:
        return SapExtractionResponse(
            sap_definitions={}, optional_outputs=[],
            error=f"Schema mismatch: {exc}",
            raw_excerpt_sample=payload[:500],
        )


# ---------------------------------------------------------------------------
# Natural-language shell selection
# ---------------------------------------------------------------------------

_NL_SHELLS_SYSTEM = """You convert natural-language instructions into a
JSON diff of shell selections for a clinical TLF generator.

Available shell ids and their flags are provided in the user message.
Respond with ONLY valid JSON of the form:

{
  "changes": [
    {"shell_id": "t_14_3_1_13", "action": "add",    "reason": "..."},
    {"shell_id": "f_14_3_4_3",  "action": "remove", "reason": "..."}
  ],
  "summary": "human-readable one-line summary of the changes"
}

Rules:
- action is "add" or "remove" only.
- Use the shell_id exactly as listed by the user.
- Do not include shells that are already in the desired state.
"""


def interpret_shell_instruction(
    instruction: str,
    current_selection: dict[str, bool],
    available_shells: list[dict[str, str]],
) -> NlShellResponse:
    shell_catalog = "\n".join(
        f"- {s['id']} ({s.get('conditionality', 'required')}): {s.get('title', '')}"
        for s in available_shells
    )
    current = ", ".join(sid for sid, sel in current_selection.items() if sel) or "(none)"
    user = (
        f"Instruction: {instruction}\n\n"
        f"Currently selected: {current}\n\n"
        f"Available shells:\n{shell_catalog}"
    )
    raw = _completion(_NL_SHELLS_SYSTEM, user)
    if not raw:
        return NlShellResponse(changes=[], error="Empty AI response")
    payload = _strip_fence(raw)
    try:
        data = json.loads(payload)
        changes = [NlShellChange.model_validate(c) for c in (data.get("changes") or [])]
        return NlShellResponse(changes=changes, summary=str(data.get("summary", "")))
    except (json.JSONDecodeError, ValidationError) as exc:
        return NlShellResponse(changes=[], error=f"Could not parse AI response: {exc}")


# ---------------------------------------------------------------------------
# Table chat (streaming)
# ---------------------------------------------------------------------------

_CHAT_SYSTEM = """You are a clinical programming expert helping a
biostatistician understand a single generated table. The user can ask
questions about the table's contents, the underlying ADaM data, the
relevant SAP definitions, or formatting / CDISC standards.

The user message will include the table's shell specification, the
rendered data (as a small text table), and the study's analysis sets
and SAP definitions. Cite the specific cell, footnote, or rule when
answering. Keep responses concise."""


def chat_stream(messages: list[ChatMessage], context: dict[str, Any]) -> Iterator[str]:
    """Stream a response. Caller yields each chunk to the HTTP response."""
    system = _CHAT_SYSTEM + "\n\nContext for this conversation:\n" + json.dumps(context, indent=2)[:8000]
    try:
        with _client().messages.stream(
            model=_model(),
            max_tokens=2048,
            system=system,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        ) as stream:
            for chunk in stream.text_stream:
                if chunk:
                    yield chunk
    except Exception as exc:
        yield f"[AI error: {exc}]"


# ---------------------------------------------------------------------------
# Anomaly detection (deterministic + AI)
# ---------------------------------------------------------------------------

def detect_anomalies(preview: dict[str, Any]) -> AnomalyResponse:
    """Run deterministic checks first, then optionally AI-augment.

    `preview` is the dict produced by preview_service.generate_preview.
    """
    out: list[Anomaly] = list(_rule_based_anomalies(preview))
    # AI augmentation is best-effort; if the key is missing we just return
    # the deterministic findings.
    if not get_settings().anthropic_api_key:
        return AnomalyResponse(anomalies=out)
    out.extend(_ai_anomalies(preview))
    return AnomalyResponse(anomalies=out)


def _rule_based_anomalies(preview: dict[str, Any]) -> Iterator[Anomaly]:
    body = preview.get("body_rows", []) or []
    column_headers = preview.get("column_headers", []) or []
    footnotes = preview.get("footnotes", []) or []
    footnote_text = " ".join(f["text"] for f in footnotes)

    # 1. Zero-percent suppression: "0.0%" / " (0.0)" should NEVER appear.
    for r, row in enumerate(body):
        for c, cell in enumerate(row):
            text = str(cell)
            if "(0.0)" in text or "(0.0%)" in text or text.endswith("0.0%"):
                yield Anomaly(
                    severity="warning",
                    description="Zero-percent value not suppressed",
                    location=f"row {r + 1}, column {c + 1}",
                    rule="Zero-percent suppression (General Instructions)",
                    source="rule",
                )

    # 2. Abbreviation completeness: cell text containing an all-caps
    #    abbreviation (e.g. 'TEAE', 'SOC', 'PT') must be defined in
    #    abbreviations footnote.
    import re
    abbrevs_used: set[str] = set()
    for row in body:
        for cell in row:
            for match in re.findall(r"\b[A-Z]{3,6}\b", str(cell)):
                abbrevs_used.add(match)
    for abbrev in abbrevs_used:
        if abbrev.lower() not in footnote_text.lower():
            # Only flag truly clinical abbreviations — skip ones that are
            # also common English words by length / known list heuristic.
            if abbrev in {"SOC", "PT", "TEAE", "AE", "AESI", "SAE", "SAR", "MedDRA", "MMSE", "BMI", "QTC"}:
                yield Anomaly(
                    severity="info",
                    description=f"Abbreviation '{abbrev}' appears in the table body but is not defined in any footnote",
                    location=f"footnote section",
                    rule="Footnote abbreviation completeness",
                    source="rule",
                )

    # 3. Sum-of-categories check: if the first cell label literally is "n",
    #    it should equal the sum of any indented children labelled "<= ..."
    #    Skipped here — would require richer row semantics from the renderer.

    # 4. MedDRA dictionary footnote present when a SOC/PT-like cell exists.
    has_meddra_cells = any("SYSTEM ORGAN" in str(c).upper() or "PREFERRED TERM" in str(c).upper()
                            for row in body for c in row)
    if has_meddra_cells and "meddra" not in footnote_text.lower():
        yield Anomaly(
            severity="warning",
            description="Table appears to use MedDRA terms but no MedDRA-version footnote is present",
            location="footnote section",
            rule="Coding dictionary footnote required",
            source="rule",
        )


def _ai_anomalies(preview: dict[str, Any]) -> list[Anomaly]:
    system = """You audit clinical TLF tables. Given the table's title,
column headers, body rows, and footnotes, return ONLY a JSON array of
anomaly objects with fields: severity ("warning"|"info"), description,
location, rule. Return [] if you find none."""
    user = json.dumps(preview)[:8000]
    raw = _completion(system, user, max_tokens=1024)
    if not raw:
        return []
    payload = _strip_fence(raw)
    try:
        data = json.loads(payload)
        if not isinstance(data, list):
            return []
        out: list[Anomaly] = []
        for item in data:
            try:
                item["source"] = "ai"
                out.append(Anomaly.model_validate(item))
            except ValidationError:
                continue
        return out
    except json.JSONDecodeError:
        return []
