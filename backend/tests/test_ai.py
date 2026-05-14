"""Tests for AI services: SAP extraction, NL shells, anomaly detection."""

from __future__ import annotations

import json


# ---------------------------------------------------------------------------
# SAP extraction — happy path with mocked AI
# ---------------------------------------------------------------------------

def test_sap_extraction_valid_json(mock_anthropic):
    mock_anthropic.set_text(json.dumps({
        "sap_definitions": {
            "teae_definition": {
                "value": "An AE on or after first dose.",
                "source_excerpt": "TEAEs are defined as adverse events occurring on or after first dose.",
                "confidence": "high",
            },
            "baseline_definition": {
                "value": "Last non-missing assessment on or before first dose.",
                "source_excerpt": "Baseline is the last value before treatment.",
                "confidence": "high",
            },
        },
        "optional_outputs": [
            {"flag": "table_14_3_1_13_ae_by_severity", "enabled": True,
             "reason": "SAP requires AE severity breakdown.", "source_excerpt": "Severity will be summarised.",
             "confidence": "high"},
        ],
        "primary_endpoint": {
            "value": "Change in ADAS-Cog at Week 24.",
            "source_excerpt": "Primary endpoint: change from baseline ADAS-Cog at Week 24.",
            "confidence": "high",
        },
        "secondary_endpoints": ["CIBIC+ at Week 24"],
        "subgroup_analyses": ["age", "sex"],
    }))
    from services import ai_service
    result = ai_service.extract_sap("doesn't matter, AI is mocked")
    assert "teae_definition" in result.sap_definitions
    assert result.sap_definitions["teae_definition"].confidence == "high"
    assert len(result.optional_outputs) == 1
    assert result.primary_endpoint and "ADAS-Cog" in result.primary_endpoint.value
    assert result.error is None


def test_sap_extraction_malformed_json_does_not_crash(mock_anthropic):
    mock_anthropic.set_text("not actually JSON, just prose")
    from services import ai_service
    result = ai_service.extract_sap("input text")
    assert result.error is not None
    assert "Malformed JSON" in result.error
    # Still returns a valid object
    assert result.sap_definitions == {}


def test_sap_extraction_strips_markdown_fence(mock_anthropic):
    payload = '```json\n{"sap_definitions": {}, "optional_outputs": []}\n```'
    mock_anthropic.set_text(payload)
    from services import ai_service
    result = ai_service.extract_sap("input")
    assert result.error is None


# ---------------------------------------------------------------------------
# Natural-language shells
# ---------------------------------------------------------------------------

def test_nl_shells_parses_diff(mock_anthropic):
    mock_anthropic.set_text(json.dumps({
        "changes": [
            {"shell_id": "t_14_3_1_13", "action": "add", "reason": "Severity needed for NDA"},
            {"shell_id": "f_14_3_4_3", "action": "add", "reason": "DILI screening required"},
        ],
        "summary": "Added severity breakdown and DILI plot.",
    }))
    from services.ai_service import interpret_shell_instruction
    result = interpret_shell_instruction(
        "Add severity and DILI plot",
        {"t_14_3_1_13": False, "f_14_3_4_3": False},
        [{"id": "t_14_3_1_13", "title": "Severity", "conditionality": "optional"}],
    )
    assert len(result.changes) == 2
    assert result.changes[0].shell_id == "t_14_3_1_13"
    assert "severity" in result.summary.lower()


def test_nl_shells_malformed_response_returns_error(mock_anthropic):
    mock_anthropic.set_text("not json")
    from services.ai_service import interpret_shell_instruction
    result = interpret_shell_instruction("nonsense", {}, [])
    assert result.error is not None
    assert result.changes == []


# ---------------------------------------------------------------------------
# Anomaly detection (deterministic checks)
# ---------------------------------------------------------------------------

def test_deterministic_catches_zero_percent(monkeypatch):
    # Disable AI so only deterministic rules run.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import config
    config._settings = None

    from services.ai_service import detect_anomalies
    preview = {
        "body_rows": [
            ["Subjects with AE", "5 (10.0)", "0 (0.0)", "1 (1.2)"],
        ],
        "column_headers": ["Label", "A", "B", "C"],
        "footnotes": [],
    }
    res = detect_anomalies(preview)
    descs = [a.description for a in res.anomalies]
    assert any("Zero-percent" in d for d in descs)


def test_deterministic_catches_missing_abbreviation_definition(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import config
    config._settings = None
    from services.ai_service import detect_anomalies
    preview = {
        "body_rows": [["TEAE count", "5", "6", "7"]],
        "column_headers": ["Label", "A", "B", "C"],
        "footnotes": [
            {"kind": "definitions", "text": "Baseline is the last value before treatment."},
        ],
    }
    res = detect_anomalies(preview)
    descs = [a.description for a in res.anomalies]
    assert any("TEAE" in d for d in descs)


def test_deterministic_catches_missing_meddra_footnote(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import config
    config._settings = None
    from services.ai_service import detect_anomalies
    preview = {
        "body_rows": [
            ["System Organ Class", "", "", ""],
            ["Nervous system disorders", "3", "2", "1"],
        ],
        "column_headers": ["Label", "A", "B", "C"],
        "footnotes": [],
    }
    res = detect_anomalies(preview)
    descs = [a.description for a in res.anomalies]
    assert any("MedDRA" in d for d in descs)


def test_deterministic_passes_clean_table(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    import config
    config._settings = None
    from services.ai_service import detect_anomalies
    preview = {
        "body_rows": [["Mean age", "75.0", "74.2", "75.1"]],
        "column_headers": ["Label", "A", "B", "C"],
        "footnotes": [],
    }
    res = detect_anomalies(preview)
    # No zero-percent, no clinical abbreviations, no MedDRA cells → clean
    assert res.anomalies == []
