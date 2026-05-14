"""List/inspect generated output files and assemble download packages."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services import study_service


@dataclass
class OutputRecord:
    output_id: str       # filename stem
    filename: str
    table_number: str
    table_id: str        # shell id derived from filename
    population: str
    generated_at: datetime
    size_bytes: int
    status: str          # 'pending' | 'approved'
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


def _table_number_from_name(name: str) -> str:
    """Recover '14.1.1.1' or '14.3.5.2' from 'CDISCPILOT01_Table_14.1.1.1_12MAY2026.rtf'."""
    stem = Path(name).stem
    parts = stem.split("_")
    # Skip leading study tokens and trailing date token
    if len(parts) >= 4 and parts[1] in {"Table", "Figure"}:
        return "_".join(parts[2:-1])
    return stem


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
        # Try to look up the population from study config + registry
        population = ""
        out.append(
            OutputRecord(
                output_id=p.stem,
                filename=p.name,
                table_number=number,
                table_id=f"t_{number.replace('.', '_')}",
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


def set_status(study_id: str, output_id: str, status: str) -> str:
    statuses = _read_status_map(study_id)
    statuses[output_id] = status
    _write_status_map(study_id, statuses)
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
    buf.seek(0)
    filename = f"{study_id}_package_{datetime.now(tz=timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    return buf.getvalue(), filename
