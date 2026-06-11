"""List/inspect generated output files, review workflow, download packages.

Review workflow (mirrors the clinical programming process):

    pending ──QC review──> qc_passed ──biostat sign-off──> approved
                └────────> qc_failed (back to the primary programmer)

The QC checklist + sign-off records live in the per-output audit JSON
(``audit/{output_id}.json``). Redoing a review archives the previous record
into ``review_history`` rather than deleting it, and regenerating an output
voids its review (the file changed, so prior QC no longer applies).
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services import study_service

# pending -> qc_passed | qc_failed -> approved (signed off)
VALID_STATUSES = {"pending", "qc_passed", "qc_failed", "approved"}


@dataclass
class OutputRecord:
    output_id: str       # filename stem
    filename: str
    table_number: str
    table_id: str        # shell id derived from filename
    population: str
    generated_at: datetime
    size_bytes: int
    status: str          # one of VALID_STATUSES
    audit_path: str | None


def _output_dir(study_id: str) -> Path:
    return study_service.study_dir(study_id) / "outputs"


def _audit_dir(study_id: str) -> Path:
    return study_service.study_dir(study_id) / "audit"


def _read_status_map(study_id: str) -> dict[str, str]:
    path = _audit_dir(study_id) / "_status.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _write_status_map(study_id: str, statuses: dict[str, str]) -> None:
    aud = _audit_dir(study_id)
    aud.mkdir(parents=True, exist_ok=True)
    (aud / "_status.json").write_text(json.dumps(statuses, indent=2))


def _kind_and_number_from_name(name: str) -> tuple[str, str]:
    """Recover ('Table', '14.1.1.1') from a generated output filename.

    Study IDs may contain underscores, so split-based parsing is fragile for
    names like ``NEW_STUDY_Table_14.1.1.1_03JUN2026.rtf``.
    """
    stem = Path(name).stem
    match = re.search(r"_(Table|Figure)_([^_]+)_\d{2}[A-Z]{3}\d{4}$", stem)
    if not match:
        return "Table", stem
    return match.group(1), match.group(2)


def _table_number_from_name(name: str) -> str:
    return _kind_and_number_from_name(name)[1]


def _table_id_from_name(name: str) -> str:
    kind, number = _kind_and_number_from_name(name)
    prefix = "f" if kind == "Figure" else "t"
    return f"{prefix}_{number.replace('.', '_')}"


def list_outputs(study_id: str) -> list[OutputRecord]:
    out: list[OutputRecord] = []
    statuses = _read_status_map(study_id)
    odir = _output_dir(study_id)
    if not odir.exists():
        return out
    for p in sorted(odir.iterdir()):
        if p.suffix.lower() not in (".rtf", ".png"):
            continue
        stat = p.stat()
        number = _table_number_from_name(p.name)
        table_id = _table_id_from_name(p.name)
        # Try to look up the population from study config + registry
        population = ""
        out.append(
            OutputRecord(
                output_id=p.stem,
                filename=p.name,
                table_number=number,
                table_id=table_id,
                population=population,
                generated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                size_bytes=stat.st_size,
                status=statuses.get(p.stem, "pending"),
                audit_path=str((_audit_dir(study_id) / f"{p.stem}.json")) if (_audit_dir(study_id) / f"{p.stem}.json").exists() else None,
            )
        )
    return out


def get_path(study_id: str, output_id: str) -> Path:
    for p in _output_dir(study_id).iterdir():
        if p.stem == output_id:
            return p
    raise FileNotFoundError(f"Output {output_id} not found")


def get_audit(study_id: str, output_id: str) -> dict[str, Any]:
    aud = _audit_dir(study_id) / f"{output_id}.json"
    if not aud.exists():
        return {}
    return json.loads(aud.read_text())


def _write_audit(study_id: str, output_id: str, audit: dict[str, Any]) -> None:
    aud_dir = _audit_dir(study_id)
    aud_dir.mkdir(parents=True, exist_ok=True)
    (aud_dir / f"{output_id}.json").write_text(json.dumps(audit, indent=2, default=str))


def _set_status(study_id: str, output_id: str, status: str) -> str:
    statuses = _read_status_map(study_id)
    statuses[output_id] = status
    _write_status_map(study_id, statuses)
    return status


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _archive_review(audit: dict[str, Any], reason: str) -> None:
    """Move any existing qc/signoff blocks into review_history (never delete)."""
    archived = {k: audit.pop(k) for k in ("qc", "signoff") if k in audit}
    if archived:
        archived["archived_at"] = _now_iso()
        archived["archived_reason"] = reason
        audit.setdefault("review_history", []).append(archived)


def record_generated(study_id: str, output_path: Path, *, table_id: str,
                     data_extract_date: str | None) -> None:
    """Stamp generation metadata into the audit record and void any prior
    review — the file changed, so existing QC / sign-off no longer applies."""
    output_id = output_path.stem
    audit = get_audit(study_id, output_id)
    _archive_review(audit, "output regenerated")
    audit["generated"] = {
        "at": _now_iso(),
        "table_id": table_id,
        "filename": output_path.name,
        "data_extract_date": data_extract_date or "",
    }
    _write_audit(study_id, output_id, audit)
    _set_status(study_id, output_id, "pending")


def record_qc(study_id: str, output_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Record a QC review. Overall result: fail if any checklist item failed."""
    get_path(study_id, output_id)  # raises FileNotFoundError for unknown ids
    items = payload.get("items") or []
    result = "fail" if any(i.get("result") == "fail" for i in items) else "pass"
    audit = get_audit(study_id, output_id)
    _archive_review(audit, "QC redone")
    audit["qc"] = {
        "reviewer": payload["reviewer"],
        "performed_at": _now_iso(),
        "result": result,
        "items": items,
        "comments": payload.get("comments", ""),
        "auto_checks": payload.get("auto_checks") or {},
    }
    _write_audit(study_id, output_id, audit)
    _set_status(study_id, output_id, "qc_passed" if result == "pass" else "qc_failed")

    from services import audit_service

    audit_service.log_event(
        study_id, "output.qc_recorded",
        {"output_id": output_id, "reviewer": payload["reviewer"], "result": result},
    )
    return audit


def record_signoff(study_id: str, output_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Record the biostatistician sign-off. Requires a passed QC."""
    get_path(study_id, output_id)
    statuses = _read_status_map(study_id)
    if statuses.get(output_id, "pending") != "qc_passed":
        raise ValueError("Sign-off requires a passed QC review first.")
    audit = get_audit(study_id, output_id)
    audit["signoff"] = {
        "name": payload["name"],
        "role": "Biostatistician",
        "signed_at": _now_iso(),
        "comment": payload.get("comment", ""),
        "qc_reviewer": (audit.get("qc") or {}).get("reviewer", ""),
        "qc_performed_at": (audit.get("qc") or {}).get("performed_at", ""),
    }
    _write_audit(study_id, output_id, audit)
    _set_status(study_id, output_id, "approved")

    from services import audit_service

    audit_service.log_event(
        study_id, "output.signed_off",
        {"output_id": output_id, "name": payload["name"], "role": "Biostatistician"},
    )
    return audit


def reset_review(study_id: str, output_id: str, *, reason: str = "review reset") -> str:
    """Archive any review records and return the output to Pending QC."""
    audit = get_audit(study_id, output_id)
    _archive_review(audit, reason)
    _write_audit(study_id, output_id, audit)
    status = _set_status(study_id, output_id, "pending")

    from services import audit_service

    audit_service.log_event(
        study_id, "output.review_reset", {"output_id": output_id, "reason": reason},
    )
    return status


def package(study_id: str, *, approved_only: bool = True) -> tuple[bytes, str]:
    """Return (zip_bytes, filename). Includes a manifest.csv."""
    records = list_outputs(study_id)
    if approved_only:
        records = [r for r in records if r.status == "approved"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        manifest_lines = ["filename,table_number,status,generated_at,size_bytes"]
        for rec in records:
            path = get_path(study_id, rec.output_id)
            z.write(path, arcname=rec.filename)
            manifest_lines.append(
                f"{rec.filename},{rec.table_number},{rec.status},{rec.generated_at.isoformat()},{rec.size_bytes}"
            )
        z.writestr("manifest.csv", "\n".join(manifest_lines))
        # The full study audit trail ships with every delivery package.
        from services import audit_service

        z.writestr("audit_trail.csv", audit_service.to_csv(study_id))
    buf.seek(0)
    filename = f"{study_id}_package_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    return buf.getvalue(), filename
