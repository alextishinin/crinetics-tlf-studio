"""Tests for the study-level, hash-chained audit trail."""

from __future__ import annotations

import json

from services import audit_service, study_service


def _make_study(client) -> str:
    return client.post(
        "/api/studies",
        json={"title": "Audit Study", "protocol_number": "AUD"},
    ).json()["meta"]["study_id"]


def test_actions_are_recorded_and_chain_verifies(client):
    sid = _make_study(client)

    # Config change -> field-level old/new diff.
    client.put(f"/api/studies/{sid}", json={"meddra_version": "27.0"})

    # Review workflow events.
    out_dir = study_service.study_dir(sid) / "outputs"
    (out_dir / "AUD_Table_14.1.1.1_03JUN2026.rtf").write_text("{\\rtf1 x}")
    oid = "AUD_Table_14.1.1.1_03JUN2026"
    client.post(
        f"/api/studies/{sid}/outputs/{oid}/qc",
        json={
            "reviewer": "QC",
            "items": [{"id": "titles", "label": "t", "result": "pass", "comment": ""}],
            "comments": "",
            "auto_checks": {},
        },
    )
    client.post(f"/api/studies/{sid}/outputs/{oid}/signoff", json={"name": "B", "comment": ""})

    resp = client.get(f"/api/studies/{sid}/audit-trail")
    assert resp.status_code == 200
    body = resp.json()
    actions = [e["action"] for e in body["entries"]]
    assert "study.created" in actions
    assert "study.config_updated" in actions
    assert "output.qc_recorded" in actions
    assert "output.signed_off" in actions
    assert body["chain"]["valid"] is True
    assert body["chain"]["entries"] == len(body["entries"])

    # The config event carries the old -> new diff.
    cfg_event = next(e for e in body["entries"] if e["action"] == "study.config_updated")
    fields = {c["field"]: c for c in cfg_event["details"]["changes"]}
    assert fields["meddra_version"]["new"] == "27.0"

    # Every entry has an actor and a hash.
    assert all(e["actor"] and e["hash"] for e in body["entries"])


def test_tampering_breaks_the_chain(client):
    sid = _make_study(client)
    client.put(f"/api/studies/{sid}", json={"meddra_version": "27.0"})

    trail = study_service.study_dir(sid) / "audit" / "trail.jsonl"
    lines = trail.read_text().splitlines()
    first = json.loads(lines[0])
    first["actor"] = "someone-else"  # rewrite history
    lines[0] = json.dumps(first)
    trail.write_text("\n".join(lines) + "\n")

    chain = client.get(f"/api/studies/{sid}/audit-trail").json()["chain"]
    assert chain["valid"] is False
    assert chain["first_invalid_seq"] == 1


def test_csv_export(client):
    sid = _make_study(client)
    resp = client.get(f"/api/studies/{sid}/audit-trail/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    lines = resp.text.splitlines()
    assert lines[0] == "seq,timestamp_utc,actor,action,details,hash"
    assert any("study.created" in line for line in lines[1:])


def test_package_includes_audit_trail_csv(client):
    import io
    import zipfile

    sid = _make_study(client)
    resp = client.get(f"/api/studies/{sid}/outputs/package")
    assert resp.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    assert "audit_trail.csv" in z.namelist()
