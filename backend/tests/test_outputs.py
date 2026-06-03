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
