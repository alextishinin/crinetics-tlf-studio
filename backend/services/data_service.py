"""Read-only access to a study's ADaM datasets for the AI assistant.

The chat tool-use loop calls these to answer patient-level / data questions
that the aggregated table can't. Queries use a structured (non-eval) filter
spec so the model can't run arbitrary code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services import study_service

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000

# Filter operators the model is allowed to use.
_OPS = {
    "==", "!=", ">", "<", ">=", "<=",
    "in", "not_in", "contains", "is_null", "not_null",
}


def _data_dir(study_id: str) -> Path:
    return study_service.study_dir(study_id) / "data"


_DATA_SUFFIXES = (".parquet", ".sas7bdat", ".xpt")


def _datasets(study_id: str) -> list[Path]:
    """Every queryable ADaM file — all upload formats, not just parquet."""
    d = _data_dir(study_id)
    if not d.exists():
        return []
    return sorted(p for p in d.iterdir() if p.suffix.lower() in _DATA_SUFFIXES)


def _scan(path: Path):
    """LazyFrame over any supported format (parquet stays lazy; SAS formats
    are read eagerly via the shared reader and wrapped)."""
    import polars as pl

    if path.suffix.lower() == ".parquet":
        return pl.scan_parquet(path)
    from services.adam_service import read_dataset

    return read_dataset(path).lazy()


def dataset_schemas(study_id: str) -> list[dict[str, Any]]:
    """Return [{name, n_rows, columns}] for every ADaM dataset in the study."""
    import polars as pl

    out: list[dict[str, Any]] = []
    for p in _datasets(study_id):
        try:
            lf = _scan(p)
            names = lf.collect_schema().names()
            n_rows = lf.select(pl.len()).collect().item()
            out.append({"name": p.stem.lower(), "n_rows": int(n_rows), "columns": names})
        except Exception as exc:  # pragma: no cover - corrupt file
            out.append({"name": p.stem.lower(), "n_rows": 0, "columns": [], "error": str(exc)})
    return out


def query_dataset(
    study_id: str,
    dataset: str,
    columns: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    distinct: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """Filter/select one ADaM dataset and return matching rows (capped).

    Returns a JSON-serialisable dict. On any user-correctable problem
    (unknown dataset/column/op) it returns ``{"error": ...}`` so the model
    can read the message and retry, rather than raising.
    """
    import polars as pl

    # Resolve the dataset file case-insensitively (adsl == ADSL).
    target: Path | None = None
    for p in _datasets(study_id):
        if p.stem.lower() == str(dataset).lower():
            target = p
            break
    if target is None:
        available = [p.stem.lower() for p in _datasets(study_id)]
        return {"error": f"Dataset '{dataset}' not found. Available: {available}"}

    lf = _scan(target)
    schema_names = lf.collect_schema().names()
    name_map = {c.lower(): c for c in schema_names}

    # --- filters (combined with AND) ---------------------------------------
    exprs = []
    for f in filters or []:
        col = f.get("column")
        op = f.get("op")
        val = f.get("value")
        if op not in _OPS:
            return {"error": f"Unsupported op '{op}'. Allowed: {sorted(_OPS)}"}
        real = name_map.get(str(col).lower())
        if real is None:
            return {"error": f"Unknown column '{col}' in {target.stem}. Columns: {schema_names}"}
        c = pl.col(real)
        try:
            if op == "==":
                e = c == val
            elif op == "!=":
                e = c != val
            elif op == ">":
                e = c > val
            elif op == "<":
                e = c < val
            elif op == ">=":
                e = c >= val
            elif op == "<=":
                e = c <= val
            elif op == "in":
                e = c.is_in(val if isinstance(val, list) else [val])
            elif op == "not_in":
                e = ~c.is_in(val if isinstance(val, list) else [val])
            elif op == "contains":
                e = c.cast(pl.Utf8).str.contains(str(val), literal=True)
            elif op == "is_null":
                e = c.is_null()
            else:  # not_null
                e = c.is_not_null()
        except Exception as exc:
            return {"error": f"Filter error on {real} {op}: {exc}"}
        exprs.append(e)

    if exprs:
        cond = exprs[0]
        for e in exprs[1:]:
            cond = cond & e
        lf = lf.filter(cond)

    # --- column selection --------------------------------------------------
    if columns:
        real_cols = []
        for c in columns:
            rc = name_map.get(str(c).lower())
            if rc is None:
                return {"error": f"Unknown column '{c}' in {target.stem}. Columns: {schema_names}"}
            real_cols.append(rc)
        lf = lf.select(real_cols)

    if distinct:
        lf = lf.unique()

    lim = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    try:
        df = lf.collect()
    except Exception as exc:
        return {"error": f"Query failed: {exc}"}

    n_matched = df.height
    return {
        "dataset": target.stem.lower(),
        "columns": df.columns,
        "n_matched": n_matched,
        "returned": min(n_matched, lim),
        "truncated": n_matched > lim,
        "rows": df.head(lim).to_dicts(),
    }
