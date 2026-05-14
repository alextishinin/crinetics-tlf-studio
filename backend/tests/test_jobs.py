"""Tests for the generation job pipeline.

These tests run with the inline executor (TLF_JOB_EXECUTOR != 'celery'),
which is the default. They exercise the real tlf library against the
CDISCPILOT01 reference data sitting in the sibling automation project.
"""

from __future__ import annotations

import shutil
from pathlib import Path


REFERENCE_DATA = Path(__file__).resolve().parents[2].parent / "crinetics-tlf-automation" / "data"


def _create_study_with_data(client) -> str:
    """Create a study and copy the real CDISCPILOT01 ADaM parquet files into
    its data/ directory."""
    resp = client.post("/api/studies", json={"title": "ref", "protocol_number": "CDISCPILOT01"})
    sid = resp.json()["meta"]["study_id"]
    # Locate this study's data directory and copy parquet files
    from services.study_service import study_dir
    target = study_dir(sid) / "data"
    target.mkdir(parents=True, exist_ok=True)
    for p in REFERENCE_DATA.glob("*.parquet"):
        shutil.copy(p, target / p.name)
    return sid


def test_submit_creates_job_record(client):
    sid = client.post("/api/studies", json={"title": "x", "protocol_number": "Y"}).json()["meta"]["study_id"]
    resp = client.post(
        f"/api/studies/{sid}/jobs",
        json={"table_ids": ["t_14_1_1_1"]},
    )
    # Job will fail (no data uploaded) but record must still be present
    assert resp.status_code == 200, resp.text
    jobs = resp.json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["status"] in {"complete", "failed"}


def test_full_disposition_job_runs(client):
    """End-to-end: real ADaM data → disposition table generated."""
    if not REFERENCE_DATA.exists():
        import pytest
        pytest.skip("reference automation data not available")
    sid = _create_study_with_data(client)
    resp = client.post(f"/api/studies/{sid}/jobs", json={"table_ids": ["t_14_1_1_1"]})
    assert resp.status_code == 200, resp.text
    job = resp.json()["jobs"][0]
    assert job["status"] == "complete", job.get("error")
    assert job["output_path"] is not None
    assert Path(job["output_path"]).exists()


def test_batch_submission_creates_batch_id(client):
    sid = client.post("/api/studies", json={"title": "x", "protocol_number": "Y"}).json()["meta"]["study_id"]
    resp = client.post(
        f"/api/studies/{sid}/jobs",
        json={"table_ids": ["t_14_1_1_1", "t_14_1_2_1"]},
    )
    body = resp.json()
    assert body["batch_id"] is not None
    assert all(j["batch_id"] == body["batch_id"] for j in body["jobs"])


def test_failed_job_records_error(client):
    """No data uploaded → disposition generation fails and the error is captured."""
    sid = client.post("/api/studies", json={"title": "x", "protocol_number": "Y"}).json()["meta"]["study_id"]
    resp = client.post(f"/api/studies/{sid}/jobs", json={"table_ids": ["t_14_1_1_1"]})
    job = resp.json()["jobs"][0]
    if job["status"] == "failed":
        assert job["error"], "Failure must capture an error message"


def test_list_jobs_returns_persisted_records(client):
    sid = client.post("/api/studies", json={"title": "x", "protocol_number": "Y"}).json()["meta"]["study_id"]
    client.post(f"/api/studies/{sid}/jobs", json={"table_ids": ["t_14_1_1_1"]})
    resp = client.get(f"/api/studies/{sid}/jobs")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_cancel_job(client):
    sid = client.post("/api/studies", json={"title": "x", "protocol_number": "Y"}).json()["meta"]["study_id"]
    job = client.post(f"/api/studies/{sid}/jobs", json={"table_ids": ["t_14_1_1_1"]}).json()["jobs"][0]
    resp = client.delete(f"/api/studies/{sid}/jobs/{job['job_id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_get_unknown_job_returns_404(client):
    sid = client.post("/api/studies", json={"title": "x", "protocol_number": "Y"}).json()["meta"]["study_id"]
    resp = client.get(f"/api/studies/{sid}/jobs/missing-id")
    assert resp.status_code == 404
