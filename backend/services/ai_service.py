"""Anthropic-backed AI features.

Every entrypoint here is built to:
  - Use claude-sonnet-4-6 (configurable via ANTHROPIC_MODEL)
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
    CrfCategoryList,
    CrfExtractionResponse,
    ExtractedField,
    NlShellChange,
    NlShellResponse,
    OptionalOutputDecision,
    ProtocolExtractionResponse,
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
# Protocol extraction
# ---------------------------------------------------------------------------

_PROTOCOL_SYSTEM = """You are a clinical study expert. Read the provided
clinical study Protocol text and extract study-level metadata as a JSON
object that matches this schema exactly:

{
  "fields": {
    "protocol_number":    {"value": str, "source_excerpt": str, "confidence": "high|medium|low"},
    "protocol_title":     {"value": str, "source_excerpt": str, "confidence": "high|medium|low"},
    "indication":         {"value": str, "source_excerpt": str, "confidence": "high|medium|low"},
    "phase":              {"value": str, "source_excerpt": str, "confidence": "high|medium|low"},
    "study_design":       {"value": str, "source_excerpt": str, "confidence": "high|medium|low"},
    "primary_objective":  {"value": str, "source_excerpt": str, "confidence": "high|medium|low"},
    "treatment_summary":  {"value": str, "source_excerpt": str, "confidence": "high|medium|low"}
  }
}

Rules:
- Return ONLY valid JSON. No markdown, no preamble.
- source_excerpt must quote the verbatim sentence(s) from the protocol.
- treatment_summary: briefly list the arms and doses (e.g. "Placebo;
  Xanomeline Low Dose 50mg; Xanomeline High Dose 75mg").
- Use confidence="low" and value="" when the protocol is silent.
"""


def extract_protocol(text: str) -> ProtocolExtractionResponse:
    raw = _completion(_PROTOCOL_SYSTEM, text[:50_000])
    if not raw:
        return ProtocolExtractionResponse(error="Empty response from AI")
    payload = _strip_fence(raw)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        return ProtocolExtractionResponse(error=f"Malformed JSON: {exc}", raw_excerpt_sample=payload[:500])
    try:
        fields = {
            k: ExtractedField.model_validate(v)
            for k, v in (data.get("fields", {}) or {}).items()
        }
        return ProtocolExtractionResponse(fields=fields, raw_excerpt_sample=payload[:500])
    except ValidationError as exc:
        return ProtocolExtractionResponse(error=f"Schema mismatch: {exc}", raw_excerpt_sample=payload[:500])


# ---------------------------------------------------------------------------
# CRF extraction
# ---------------------------------------------------------------------------

_CRF_SYSTEM = """You are a clinical data manager. Read the provided Case
Report Form (CRF) text and extract the collected categories (and their CRF
order) for key categorical variables, as JSON matching this schema exactly:

{
  "category_lists": [
    {
      "variable": str,   // ADaM variable name in UPPERCASE: RACE, ETHNIC, DCDECOD, AESEV, SEX
      "label": str,      // human label, e.g. "Race"
      "values": [str],   // the exact category options in the order they appear on the CRF
      "source_excerpt": str,
      "confidence": "high|medium|low"
    }
  ]
}

Map CRF sections to ADaM variables:
- Race options            -> variable "RACE"
- Ethnicity options       -> variable "ETHNIC"
- Reason for discontinuation / end-of-study disposition -> variable "DCDECOD"
- Adverse event severity / intensity scale -> variable "AESEV"
- Sex / gender            -> variable "SEX"

Rules:
- Return ONLY valid JSON. No markdown, no preamble.
- Preserve the CRF's option wording and order exactly in "values".
- source_excerpt must quote the verbatim CRF text listing the options.
- Only include variables actually present on the CRF.
"""


def extract_crf(text: str) -> CrfExtractionResponse:
    raw = _completion(_CRF_SYSTEM, text[:50_000])
    if not raw:
        return CrfExtractionResponse(error="Empty response from AI")
    payload = _strip_fence(raw)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        return CrfExtractionResponse(error=f"Malformed JSON: {exc}", raw_excerpt_sample=payload[:500])
    try:
        lists = [
            CrfCategoryList.model_validate(c)
            for c in (data.get("category_lists", []) or [])
        ]
        return CrfExtractionResponse(category_lists=lists, raw_excerpt_sample=payload[:500])
    except ValidationError as exc:
        return CrfExtractionResponse(error=f"Schema mismatch: {exc}", raw_excerpt_sample=payload[:500])


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
biostatistician understand a generated table AND the underlying study
data. You can answer questions about the table's contents, the SAP
definitions, formatting / CDISC standards, and — using the
`query_dataset` tool — patient-level or any data questions against the
study's ADaM datasets.

When a question needs raw data (e.g. "list the subject IDs who
discontinued due to an adverse event", "how many subjects had a serious
AE", "what is subject 1015's age"), call `query_dataset` instead of
saying the table can't provide it. You may call it multiple times: first
to inspect distinct values of a variable if you're unsure which
column/value to filter on, then again to get the answer.

Notes on this study's ADaM data:
- ADSL is one row per subject; USUBJID is the subject identifier and
  TRT01P / TRT01PN is the planned treatment arm.
- Disposition reasons live in ADSL (e.g. DCDECOD / DCSREAS). Study-level
  vs. treatment-level discontinuation may use different variables — if
  unsure, query distinct values first.
- Report counts using n_matched (the true total), not just the number of
  rows returned (which is capped). Cite the dataset and filter you used.
Keep responses concise."""


def _query_dataset_tool() -> dict[str, Any]:
    return {
        "name": "query_dataset",
        "description": (
            "Query one of this study's ADaM datasets (read-only) to answer "
            "patient-level or any data questions the rendered table cannot. "
            "Filters are combined with AND. Returns matching rows (capped) "
            "plus n_matched (the true total count)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {
                    "type": "string",
                    "description": "Dataset name, e.g. adsl, adae, advs, adlbc.",
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columns to return. Omit to return all columns.",
                },
                "filters": {
                    "type": "array",
                    "description": "Conditions combined with AND.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column": {"type": "string"},
                            "op": {
                                "type": "string",
                                "enum": [
                                    "==", "!=", ">", "<", ">=", "<=",
                                    "in", "not_in", "contains",
                                    "is_null", "not_null",
                                ],
                            },
                            "value": {
                                "description": "Comparison value; array for in/not_in; omit for is_null/not_null.",
                            },
                        },
                        "required": ["column", "op"],
                    },
                },
                "distinct": {
                    "type": "boolean",
                    "description": "Return only distinct rows (useful to inspect a column's values).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return (default 100, max 1000).",
                },
            },
            "required": ["dataset"],
        },
    }


def _run_query_tool(study_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    from services import data_service

    return data_service.query_dataset(
        study_id,
        dataset=tool_input.get("dataset"),
        columns=tool_input.get("columns"),
        filters=tool_input.get("filters"),
        distinct=bool(tool_input.get("distinct", False)),
        limit=tool_input.get("limit"),
    )


def chat_stream(
    messages: list[ChatMessage], context: dict[str, Any], study_id: str
) -> Iterator[str]:
    """Answer a chat turn, using the query_dataset tool when needed.

    Runs an agentic tool-use loop server-side, then yields the final text.
    """
    from services import data_service

    try:
        schemas = data_service.dataset_schemas(study_id)
        schema_text = "\n".join(
            f"- {s['name']} ({s['n_rows']} rows): {', '.join(s['columns'])}"
            for s in schemas
        )
    except Exception:
        schema_text = "(dataset schema unavailable)"

    system = (
        _CHAT_SYSTEM
        + "\n\nRendered table & study context:\n"
        + json.dumps(context, indent=2, default=str)[:6000]
        + "\n\nADaM datasets you can query (name, rows, columns):\n"
        + schema_text
    )

    convo: list[dict[str, Any]] = [
        {"role": m.role, "content": m.content} for m in messages
    ]
    tools = [_query_dataset_tool()]
    client = _client()

    try:
        for _ in range(6):  # cap tool rounds to avoid loops
            resp = client.messages.create(
                model=_model(),
                max_tokens=2048,
                system=system,
                tools=tools,
                messages=convo,
            )
            if resp.stop_reason == "tool_use":
                convo.append({"role": "assistant", "content": resp.content})
                results = []
                for block in resp.content:
                    if getattr(block, "type", None) != "tool_use":
                        continue
                    if block.name == "query_dataset":
                        result = _run_query_tool(study_id, dict(block.input))
                    else:
                        result = {"error": f"Unknown tool '{block.name}'"}
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str)[:20000],
                    })
                convo.append({"role": "user", "content": results})
                continue

            # Final answer.
            text = "".join(
                getattr(b, "text", "") for b in resp.content
                if getattr(b, "type", None) == "text"
            )
            yield text or "(no answer produced)"
            return

        yield "[AI error: too many tool calls without a final answer]"
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
