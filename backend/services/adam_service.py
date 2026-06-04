"""Inspect uploaded ADaM files and surface study-config metadata.

Given the contents of a study's data/ directory, this service:
  - Identifies each file's ADaM domain by filename pattern
  - Counts rows and unique subjects
  - Extracts treatment arms / analysis-set Ns from ADSL
  - Lists visit schedule and per-domain PARAMCDs
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from models.study import AnalysisSet, DomainSummary, TreatmentArm, UploadResult


# Map filename stem (lowercase, no extension) → canonical domain code.
_DOMAIN_ALIASES = {
    "adsl": "adsl",
    "adae": "adae",
    "adlbc": "adlbc",
    "adlbh": "adlbh",
    "adlbhy": "adlbhy",
    "advs": "advs",
    "adtte": "adtte",
    "adqsadas": "adqsadas",
    "adqscibc": "adqscibc",
    "adqsnpix": "adqsnpix",
    "adeg": "adeg",
    "adcm": "adcm",
}

# Analysis-set flags we look for in ADSL.
_ANALYSIS_FLAGS = {
    "SAF": ("SAFFL", "Y", "Safety Analysis Set"),
    "ITT": ("ITTFL", "Y", "Intent-To-Treat Set"),
    "EFF": ("EFFFL", "Y", "Efficacy Population"),
}


def identify_domain(filename: str) -> str:
    """Return canonical domain code or '' if unrecognised."""
    stem = Path(filename).stem.lower()
    # accept dots-or-dashes embedded in the name (e.g. "adsl-final")
    stem_token = stem.split("_")[0].split("-")[0].split(".")[0]
    return _DOMAIN_ALIASES.get(stem_token, "")


def read_dataset(path: Path) -> pl.DataFrame:
    """Read parquet / sas7bdat / xpt into polars. Whitespace is stripped on
    AVISIT etc. by the tlf library's reader — replicate here so we don't
    depend on the library being importable in unit tests."""
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        df = pl.read_parquet(path)
    elif suffix in (".sas7bdat", ".xpt"):
        import pyreadstat

        if suffix == ".xpt":
            pdf, _ = pyreadstat.read_xport(str(path))
        else:
            pdf, _ = pyreadstat.read_sas7bdat(str(path))
        df = pl.from_pandas(pdf)
    else:
        raise ValueError(f"Unsupported file type: {path}")
    # Light-touch whitespace strip on visit / param columns.
    schema = df.schema
    cols = [c for c in ("AVISIT", "VISIT", "PARAM", "PARAMCD") if c in schema and schema[c] == pl.Utf8]
    if cols:
        df = df.with_columns([pl.col(c).str.strip_chars() for c in cols])
    return df


# ---------------------------------------------------------------------------
# Per-file summary
# ---------------------------------------------------------------------------

def summarise_file(path: Path) -> DomainSummary:
    """Build a DomainSummary for one uploaded file."""
    domain = identify_domain(path.name)
    if not domain:
        return DomainSummary(
            filename=path.name, domain="", n_rows=0, n_subjects=0, columns=[],
            notes=["Unrecognised filename — please rename to e.g. adsl.parquet"],
        )
    try:
        df = read_dataset(path)
    except Exception as exc:
        return DomainSummary(
            filename=path.name, domain=domain, n_rows=0, n_subjects=0, columns=[],
            notes=[f"Failed to read: {exc}"],
        )
    n_subjects = df.select("USUBJID").n_unique() if "USUBJID" in df.columns else 0
    return DomainSummary(
        filename=path.name,
        domain=domain,
        n_rows=df.height,
        n_subjects=int(n_subjects),
        columns=df.columns,
    )


# ---------------------------------------------------------------------------
# Cross-file extraction
# ---------------------------------------------------------------------------

def extract_metadata(study_id: str, data_dir: Path) -> UploadResult:
    """Inspect every file under `data_dir` and assemble UploadResult."""
    files = sorted(p for p in data_dir.iterdir() if p.is_file())
    domain_summaries = [summarise_file(p) for p in files]

    adsl_file = _pick(data_dir, ["adsl.parquet", "adsl.sas7bdat", "adsl.xpt"])
    arms: list[TreatmentArm] = []
    sets: dict[str, AnalysisSet] = {}
    study_id_value: str | None = None
    if adsl_file:
        adsl = read_dataset(adsl_file)
        if "STUDYID" in adsl.columns:
            values = adsl.select("STUDYID").drop_nulls().unique().to_series().to_list()
            study_id_value = values[0] if values else None
        arms = _extract_arms(adsl)
        sets = _extract_analysis_sets(adsl, arms)

    visit_schedule = _extract_visit_schedule(data_dir)
    available_paramcds = _extract_paramcds(data_dir)

    return UploadResult(
        study_id=study_id,
        domains=domain_summaries,
        detected_arms=arms,
        detected_analysis_sets=sets,
        visit_schedule=visit_schedule,
        available_paramcds=available_paramcds,
        study_id_value=study_id_value,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pick(directory: Path, names: list[str]) -> Path | None:
    for name in names:
        path = directory / name
        if path.exists():
            return path
    return None


def _extract_arms(adsl: pl.DataFrame) -> list[TreatmentArm]:
    if "TRT01P" not in adsl.columns or "TRT01PN" not in adsl.columns:
        return []
    rows = (
        adsl.select(["TRT01P", "TRT01PN"])
        .drop_nulls()
        .unique()
        .to_dicts()
    )
    out: list[TreatmentArm] = []

    def _sort_key(row: dict) -> tuple[int, int]:
        label = str(row["TRT01P"]).lower()
        trtpn = int(row["TRT01PN"])
        is_control = trtpn == 0 or "placebo" in label or "control" in label
        return (1 if is_control else 0, trtpn)

    for row in sorted(rows, key=_sort_key):
        label = str(row["TRT01P"])
        trtpn = int(row["TRT01PN"])
        out.append(
            TreatmentArm(
                label=label,
                trtpn=trtpn,
                column_header=label.replace(" ", "\n", 1),
                target_daily_dose_mg=_guess_target_dose(label),
            )
        )
    return out


def _guess_target_dose(label: str) -> float | None:
    """Crude regex over the arm label for a 'NN mg' chunk."""
    import re

    m = re.search(r"(\d+(?:\.\d+)?)\s*mg", label, re.IGNORECASE)
    if m:
        return float(m.group(1))
    # Common dose tags from CDISCPILOT
    text = label.lower()
    if "high dose" in text:
        return 81.0
    if "low dose" in text:
        return 54.0
    if "placebo" in text:
        return None
    return None


def _extract_analysis_sets(adsl: pl.DataFrame, arms: list[TreatmentArm]) -> dict[str, AnalysisSet]:
    out: dict[str, AnalysisSet] = {}
    for name, (var, val, label) in _ANALYSIS_FLAGS.items():
        if var not in adsl.columns:
            continue
        sub = adsl.filter(pl.col(var) == val)
        n_map: dict[str, int | None] = {}
        for arm in arms:
            n_map[str(arm.trtpn)] = int(sub.filter(pl.col("TRT01PN") == arm.trtpn).height)
        out[name] = AnalysisSet(label=label, flag_var=var, flag_val=val, n=n_map)
    out["ALL"] = AnalysisSet(
        label="All Subjects",
        flag_var=None,
        flag_val=None,
        n={str(arm.trtpn): int(adsl.filter(pl.col("TRT01PN") == arm.trtpn).height) for arm in arms},
    )
    return out


def _extract_visit_schedule(data_dir: Path) -> list[str]:
    """Union of AVISIT values across longitudinal domains."""
    visits: set[str] = set()
    for stem in ("advs", "adlbc", "adlbh", "adqscibc", "adqsadas"):
        f = _pick(data_dir, [f"{stem}.parquet", f"{stem}.sas7bdat", f"{stem}.xpt"])
        if not f:
            continue
        try:
            df = read_dataset(f)
        except Exception:
            continue
        if "AVISIT" not in df.columns:
            continue
        for v in df.select("AVISIT").drop_nulls().unique().to_series().to_list():
            if v:
                visits.add(str(v))
    return sorted(visits)


def _extract_paramcds(data_dir: Path) -> dict[str, list[str]]:
    """Per-domain PARAMCD inventories (helps the shells page show whether
    e.g. ALT exists for chemistry threshold tables)."""
    out: dict[str, list[str]] = {}
    for stem in ("adlbc", "adlbh", "adlbhy", "advs", "adqsadas", "adqscibc", "adqsnpix", "adeg"):
        f = _pick(data_dir, [f"{stem}.parquet", f"{stem}.sas7bdat", f"{stem}.xpt"])
        if not f:
            continue
        try:
            df = read_dataset(f)
        except Exception:
            continue
        if "PARAMCD" not in df.columns:
            continue
        out[stem] = sorted(df.select("PARAMCD").drop_nulls().unique().to_series().to_list())
    return out
