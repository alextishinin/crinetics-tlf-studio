"""Tests for the /api/studies endpoints."""

from __future__ import annotations

import io
from pathlib import Path

import polars as pl


def _create(client, title: str = "Study A", protocol: str = "PROT-001"):
    resp = client.post(
        "/api/studies",
        json={"title": title, "protocol_number": protocol, "drug": "X", "indication": "Y"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def test_list_empty(client):
    resp = client.get("/api/studies")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_returns_detail(client):
    body = _create(client)
    assert body["meta"]["title"] == "Study A"
    assert body["meta"]["status"] == "draft"
    assert body["config"]["protocol_number"] == "PROT-001"
    assert "study_id" in body["meta"]


def test_get_after_create(client):
    created = _create(client)
    sid = created["meta"]["study_id"]
    resp = client.get(f"/api/studies/{sid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["study_id"] == sid


def test_get_missing_returns_404(client):
    resp = client.get("/api/studies/does-not-exist")
    assert resp.status_code == 404


def test_list_includes_created_study(client):
    _create(client, "Study 1")
    _create(client, "Study 2")
    resp = client.get("/api/studies")
    assert resp.status_code == 200
    items = resp.json()
    titles = {s["title"] for s in items}
    assert titles == {"Study 1", "Study 2"}


def test_update_config(client):
    created = _create(client)
    sid = created["meta"]["study_id"]
    resp = client.put(
        f"/api/studies/{sid}",
        json={"meddra_version": "26.0", "include_total_column": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["config"]["meddra_version"] == "26.0"
    assert body["config"]["include_total_column"] is False


def test_update_treatment_arms(client):
    sid = _create(client)["meta"]["study_id"]
    resp = client.put(
        f"/api/studies/{sid}",
        json={
            "treatment_arms": [
                {"label": "Drug A", "trtpn": 1, "column_header": "Drug\nA", "target_daily_dose_mg": 10},
                {"label": "Placebo", "trtpn": 0, "column_header": "Placebo", "target_daily_dose_mg": None},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    arms = resp.json()["config"]["treatment_arms"]
    assert [a["label"] for a in arms] == ["Drug A", "Placebo"]


def test_delete_study(client):
    sid = _create(client)["meta"]["study_id"]
    resp = client.delete(f"/api/studies/{sid}")
    assert resp.status_code == 204
    assert client.get(f"/api/studies/{sid}").status_code == 404


# ---------------------------------------------------------------------------
# Upload + metadata extraction
# ---------------------------------------------------------------------------

def test_upload_extracts_metadata(client, synthetic_data_dir: Path):
    sid = _create(client)["meta"]["study_id"]
    adsl = synthetic_data_dir / "adsl.parquet"
    files = {"files": ("adsl.parquet", adsl.read_bytes(), "application/octet-stream")}
    resp = client.post(f"/api/studies/{sid}/upload", files=files)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["study_id_value"] == "MOCK01"
    domain_codes = {d["domain"] for d in body["domains"]}
    assert "adsl" in domain_codes
    # Three arms detected (54, 81, 0) sorted by TRTPN
    assert [a["trtpn"] for a in body["detected_arms"]] == [0, 54, 81]
    # Analysis sets include SAF / ITT / EFF / ALL
    assert {"SAF", "ITT", "EFF", "ALL"}.issubset(body["detected_analysis_sets"].keys())


def test_upload_unknown_filename(client, tmp_path):
    sid = _create(client)["meta"]["study_id"]
    bogus = tmp_path / "random.parquet"
    pl.DataFrame({"a": [1, 2]}).write_parquet(bogus)
    files = {"files": ("random.parquet", bogus.read_bytes(), "application/octet-stream")}
    resp = client.post(f"/api/studies/{sid}/upload", files=files)
    assert resp.status_code == 200
    domains = resp.json()["domains"]
    assert domains[0]["domain"] == ""
    assert "Unrecognised filename" in domains[0]["notes"][0]
