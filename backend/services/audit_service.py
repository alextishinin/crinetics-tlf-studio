"""Study-level audit trail: who did what, when — append-only and tamper-evident.

Every meaningful action on a study (creation, config changes with old→new
values, data uploads, TFL selection changes, generation runs, QC, sign-off,
downloads) is appended to ``<study>/audit/trail.jsonl`` — one JSON object per
line, never rewritten.

Tamper evidence: each entry carries a SHA-256 hash over its own content plus
the previous entry's hash (a hash chain). Editing or deleting any line breaks
every hash after it, which ``verify_chain`` detects. This is the standard
lightweight construction for audit trails in regulated (GxP-adjacent) tools.

The actor is the OS username — appropriate for a per-user desktop install,
where the app runs under the operator's own Windows account.
"""

from __future__ import annotations

import csv
import getpass
import hashlib
import io
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from config import get_settings

TRAIL_NAME = "trail.jsonl"
_GENESIS = "0" * 64


def _trail_path(study_id: str) -> Path:
    # Resolved from settings (not study_service) to avoid an import cycle.
    return get_settings().studies_root.resolve() / study_id / "audit" / TRAIL_NAME


@contextmanager
def _trail_lock(path: Path, timeout_s: float = 5.0) -> Iterator[None]:
    """O_EXCL lock-file so concurrent appends (API + worker thread) serialize."""
    lock_path = path.with_suffix(".jsonl.lock")
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                try:
                    lock_path.unlink()
                except OSError:
                    pass
                deadline = time.monotonic() + timeout_s
            time.sleep(0.02)
    try:
        yield
    finally:
        os.close(fd)
        try:
            lock_path.unlink()
        except OSError:
            pass


def _entry_hash(prev_hash: str, entry: dict[str, Any]) -> str:
    core = {k: entry[k] for k in ("seq", "at", "actor", "action", "details")}
    payload = prev_hash + json.dumps(core, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            # A corrupt line still counts as an entry slot so verify_chain
            # reports the break instead of silently skipping it.
            entries.append({"_corrupt": line})
    return entries


def log_event(study_id: str, action: str, details: dict[str, Any] | None = None) -> None:
    """Append one event to the study's audit trail.

    Best-effort: an audit-write failure is printed, not raised, so it can
    never abort the user's actual operation.
    """
    try:
        path = _trail_path(study_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _trail_lock(path):
            existing = _read_entries(path)
            prev_hash = existing[-1].get("hash", _GENESIS) if existing else _GENESIS
            entry: dict[str, Any] = {
                "seq": len(existing) + 1,
                "at": datetime.now(tz=timezone.utc).isoformat(),
                "actor": getpass.getuser(),
                "action": action,
                "details": details or {},
                "prev_hash": prev_hash,
            }
            entry["hash"] = _entry_hash(prev_hash, entry)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
    except Exception as exc:  # noqa: BLE001 — never break the audited operation
        print(f"[audit] failed to record {action} for {study_id}: {exc}")


def list_events(study_id: str) -> list[dict[str, Any]]:
    return _read_entries(_trail_path(study_id))


def verify_chain(study_id: str) -> dict[str, Any]:
    """Walk the hash chain; report the first entry where it breaks."""
    entries = _read_entries(_trail_path(study_id))
    prev_hash = _GENESIS
    for i, entry in enumerate(entries, start=1):
        if "_corrupt" in entry:
            return {"valid": False, "entries": len(entries), "first_invalid_seq": i}
        try:
            ok = (
                entry.get("seq") == i
                and entry.get("prev_hash") == prev_hash
                and entry.get("hash") == _entry_hash(prev_hash, entry)
            )
        except KeyError:
            ok = False
        if not ok:
            return {"valid": False, "entries": len(entries), "first_invalid_seq": i}
        prev_hash = entry["hash"]
    return {"valid": True, "entries": len(entries), "first_invalid_seq": None}


def to_csv(study_id: str) -> str:
    """Flatten the trail to CSV for inspection / delivery packages."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["seq", "timestamp_utc", "actor", "action", "details", "hash"])
    for e in list_events(study_id):
        if "_corrupt" in e:
            writer.writerow(["", "", "", "CORRUPT ENTRY", e["_corrupt"], ""])
            continue
        writer.writerow([
            e.get("seq"),
            e.get("at"),
            e.get("actor"),
            e.get("action"),
            json.dumps(e.get("details", {}), default=str),
            e.get("hash"),
        ])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Helpers for callers
# ---------------------------------------------------------------------------

def short(value: Any, limit: int = 160) -> str:
    """Compact one value for an old→new diff entry."""
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def config_diff(old: dict[str, Any], patch: dict[str, Any]) -> list[dict[str, str]]:
    """Field-level old→new changes for a config update (changed keys only)."""
    changes = []
    for key, new in patch.items():
        if old.get(key) != new:
            changes.append({"field": key, "old": short(old.get(key)), "new": short(new)})
    return changes
