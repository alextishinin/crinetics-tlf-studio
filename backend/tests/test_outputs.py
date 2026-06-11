"""Tests for generated output listing metadata."""

from __future__ import annotations

from services import study_service


def test_list_outputs_recovers_table_id_when_protocol_has_underscores(client):
    sid = client.post(
        "/api/studies",
        json={"title": "x", "protocol_number": "NEW_STUDY"},
    ).json()["meta"]["study_id"]

    out_dir = study_service.study_dir(sid) / "outputs"
    output = out_dir / "NEW_STUDY_Table_14.1.1.1_03JUN2026.rtf"
    output.write_text("{\\rtf1 test}")

    resp = client.get(f"/api/studies/{sid}/outputs")

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["table_number"] == "14.1.1.1"
    assert body[0]["table_id"] == "t_14_1_1_1"


def test_list_outputs_recovers_figure_id(client):
    sid = client.post(
        "/api/studies",
        json={"title": "x", "protocol_number": "NEW_STUDY"},
    ).json()["meta"]["study_id"]

    out_dir = study_service.study_dir(sid) / "outputs"
    output = out_dir / "NEW_STUDY_Figure_14.3.5.1_03JUN2026.png"
    output.write_bytes(b"png")

    resp = client.get(f"/api/studies/{sid}/outputs")

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["table_number"] == "14.3.5.1"
    assert body[0]["table_id"] == "f_14_3_5_1"


# ---------------------------------------------------------------------------
# Review workflow: pending -> QC -> biostat sign-off
# ---------------------------------------------------------------------------

def _make_output(client) -> tuple[str, str]:
    sid = client.post(
        "/api/studies",
        json={"title": "x", "protocol_number": "REV"},
    ).json()["meta"]["study_id"]
    out_dir = study_service.study_dir(sid) / "outputs"
    (out_dir / "REV_Table_14.1.1.1_03JUN2026.rtf").write_text("{\\rtf1 test}")
    return sid, "REV_Table_14.1.1.1_03JUN2026"


def _qc_payload(result: str = "pass") -> dict:
    return {
        "reviewer": "QC Programmer",
        "items": [
            {"id": "titles", "label": "Titles match", "result": result, "comment": ""},
        ],
        "comments": "",
        "auto_checks": {},
    }


def test_signoff_requires_passed_qc(client):
    sid, oid = _make_output(client)
    resp = client.post(
        f"/api/studies/{sid}/outputs/{oid}/signoff",
        json={"name": "Biostat", "comment": ""},
    )
    assert resp.status_code == 409


def test_qc_pass_then_signoff(client):
    sid, oid = _make_output(client)

    qc = client.post(f"/api/studies/{sid}/outputs/{oid}/qc", json=_qc_payload("pass"))
    assert qc.status_code == 200
    assert qc.json()["status"] == "qc_passed"

    so = client.post(
        f"/api/studies/{sid}/outputs/{oid}/signoff",
        json={"name": "Biostat", "comment": "Looks correct"},
    )
    assert so.status_code == 200
    assert so.json()["status"] == "approved"

    listed = client.get(f"/api/studies/{sid}/outputs").json()
    assert listed[0]["status"] == "approved"

    audit = client.get(f"/api/studies/{sid}/outputs/{oid}/audit").json()
    assert audit["qc"]["reviewer"] == "QC Programmer"
    assert audit["signoff"]["name"] == "Biostat"
    assert audit["signoff"]["role"] == "Biostatistician"


def test_qc_fail_sets_qc_failed(client):
    sid, oid = _make_output(client)
    qc = client.post(f"/api/studies/{sid}/outputs/{oid}/qc", json=_qc_payload("fail"))
    assert qc.json()["status"] == "qc_failed"
    listed = client.get(f"/api/studies/{sid}/outputs").json()
    assert listed[0]["status"] == "qc_failed"


def test_reset_archives_review_records(client):
    sid, oid = _make_output(client)
    client.post(f"/api/studies/{sid}/outputs/{oid}/qc", json=_qc_payload("pass"))
    client.post(f"/api/studies/{sid}/outputs/{oid}/signoff", json={"name": "B", "comment": ""})

    reset = client.post(f"/api/studies/{sid}/outputs/{oid}/status", json={"status": "pending"})
    assert reset.json()["status"] == "pending"

    audit = client.get(f"/api/studies/{sid}/outputs/{oid}/audit").json()
    assert "qc" not in audit and "signoff" not in audit
    assert len(audit["review_history"]) == 1
    assert audit["review_history"][0]["qc"]["reviewer"] == "QC Programmer"


def test_direct_approval_is_rejected(client):
    sid, oid = _make_output(client)
    resp = client.post(f"/api/studies/{sid}/outputs/{oid}/status", json={"status": "approved"})
    assert resp.status_code == 422
