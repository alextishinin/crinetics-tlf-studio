"""Load the YAML files that describe the study and the table shells.

This file turns config/study_config.yaml and shells/registry.yaml into
Python objects that the rest of the pipeline can use. The study config
contains study metadata, treatment arms, analysis sets, input/output paths,
SAP wording, optional-output switches, and footnote values. The shell
registry contains the table and figure templates that say what each output
should contain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class TreatmentArm:
    label: str
    trtpn: int
    column_header: str
    target_daily_dose_mg: float | None


@dataclass(frozen=True)
class AnalysisSet:
    name: str
    label: str
    flag_var: str | None
    flag_val: str | None
    n: dict[int, int | None]


@dataclass
class StudyConfig:
    study_id: str
    protocol_number: str
    protocol_title: str
    indication: str
    data_extract_date: str
    data_cut_date: str
    run_datetime: str
    sas_version: str
    meddra_version: str
    who_drug_version: str
    treatment_arms: list[TreatmentArm]
    pooled_active: bool
    include_total_column: bool
    analysis_sets: dict[str, AnalysisSet]
    adam_path: Path
    output_path: Path
    shell_registry_path: Path
    sap_definitions: dict[str, str]
    exposure_duration_bins: list[dict[str, Any]]
    common_ae_cutoff_pct: float
    optional_outputs: dict[str, bool]
    source_code_location: str
    shell_mode: bool = False
    # CRF-derived category lists/order keyed by ADaM variable (uppercase),
    # e.g. {"RACE": [...], "ETHNIC": [...], "DCDECOD": [...], "AESEV": [...]}.
    # Sourced from document_extracts.crf.category_lists (human-reviewed).
    crf_categories: dict[str, list[str]] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def crf_category_order(self, var: str) -> list[str] | None:
        """Return the human-reviewed CRF category order for an ADaM variable,
        or None if the CRF didn't define one. Lookup is case-insensitive."""
        if not var:
            return None
        vals = self.crf_categories.get(var.upper())
        return list(vals) if vals else None

    @property
    def arm_trtpns(self) -> list[int]:
        return [a.trtpn for a in self.treatment_arms]

    def arm_by_trtpn(self, trtpn: int) -> TreatmentArm:
        for arm in self.treatment_arms:
            if arm.trtpn == trtpn:
                return arm
        raise KeyError(f"No arm with TRT01PN={trtpn} in study config")

    def is_optional_enabled(self, flag: str | None) -> bool:
        """Return True if an optional output should be generated.

        None (no flag) means the output is required.
        """
        if flag is None:
            return True
        return bool(self.optional_outputs.get(flag, False))

    def footnote_context(self) -> dict[str, Any]:
        """Variables exposed to Jinja2 footnote templates."""
        # Multiplication sign declared by Unicode escape so the source file
        # contains no raw extended-ASCII character (avoids the Latin-1/UTF-8
        # double-encoding bug seen in Table 14.1.3.2's compliance footnote).
        MULTIPLY_SIGN = "\u00d7"
        ctx: dict[str, Any] = {
            "study_id": self.study_id,
            "protocol_number": self.protocol_number,
            "protocol_title": self.protocol_title,
            "data_extract_date": self.data_extract_date,
            "data_cut_date": self.data_cut_date,
            "run_datetime": self.run_datetime,
            "sas_version": self.sas_version,
            "meddra_version": self.meddra_version,
            "who_drug_version": self.who_drug_version,
            "source": self.source_code_location,
            "common_ae_cutoff_pct": f"{self.common_ae_cutoff_pct:g}",
            "multiply_sign": MULTIPLY_SIGN,
        }
        ctx.update(self.sap_definitions)
        return ctx


def load_study_config(path: str | Path | None = None) -> StudyConfig:
    """Load study_config.yaml, resolving paths relative to repo root."""
    cfg_path = Path(path) if path else REPO_ROOT / "config" / "study_config.yaml"
    with open(cfg_path) as f:
        raw = yaml.safe_load(f)

    _require_keys(raw, ["study_id", "treatment_arms", "analysis_sets"])

    arms = [
        TreatmentArm(
            label=a["label"],
            trtpn=int(a["trtpn"]),
            column_header=a["column_header"],
            target_daily_dose_mg=a.get("target_daily_dose_mg"),
        )
        for a in raw["treatment_arms"]
    ]
    if not arms:
        raise ValueError("study_config.treatment_arms must list at least one arm")

    sets: dict[str, AnalysisSet] = {}
    for name, s in raw["analysis_sets"].items():
        # Coerce keys (which load as ints) and values (None preserved)
        n_map = {int(k): v for k, v in (s.get("n") or {}).items()}
        sets[name] = AnalysisSet(
            name=name,
            label=s["label"],
            flag_var=s.get("flag_var"),
            flag_val=s.get("flag_val"),
            n=n_map,
        )

    # Shell mode: auto-detect when the configured ADaM directory has no input
    # datasets (.parquet / .sas7bdat / .xpt).  In shell mode the pipeline still
    # generates every TFL but with synthetic placeholder rows and "xx" / "xx
    # (xx.x)" cell values, matching the CRO shell-template format.
    adam_dir = (REPO_ROOT / raw.get("adam_path", "data/")).resolve()
    shell_mode = True
    if adam_dir.exists():
        for p in adam_dir.iterdir():
            if p.is_file() and p.suffix.lower() in (".parquet", ".sas7bdat", ".xpt"):
                shell_mode = False
                break
    # Explicit override in study_config.yaml wins over auto-detection.
    if "shell_mode" in raw:
        shell_mode = bool(raw["shell_mode"])

    return StudyConfig(
        study_id=raw["study_id"],
        protocol_number=raw.get("protocol_number", raw["study_id"]),
        protocol_title=raw.get("protocol_title", ""),
        indication=raw.get("indication", ""),
        data_extract_date=raw.get("data_extract_date", "") or "",
        data_cut_date=raw.get("data_cut_date", "") or "",
        run_datetime=raw.get("run_datetime", "") or "",
        sas_version=str(raw.get("sas_version", "9.4")),
        meddra_version=str(raw.get("meddra_version", "")),
        who_drug_version=str(raw.get("who_drug_version", "")),
        treatment_arms=arms,
        pooled_active=bool(raw.get("pooled_active", False)),
        include_total_column=bool(raw.get("include_total_column", True)),
        analysis_sets=sets,
        adam_path=(REPO_ROOT / raw.get("adam_path", "data/")).resolve(),
        output_path=(REPO_ROOT / raw.get("output_path", "outputs/")).resolve(),
        shell_registry_path=(REPO_ROOT / raw.get("shell_registry", "shells/registry.yaml")).resolve(),
        sap_definitions=dict(raw.get("sap_definitions", {})),
        exposure_duration_bins=list(raw.get("exposure_duration_bins", [])),
        common_ae_cutoff_pct=float(raw.get("common_ae_cutoff_pct", 5.0)),
        optional_outputs=dict(raw.get("optional_outputs", {})),
        source_code_location=raw.get("source_code_location", "src/tlf/"),
        shell_mode=shell_mode,
        crf_categories=_load_crf_categories(raw),
        raw=raw,
    )


def _load_crf_categories(raw: dict[str, Any]) -> dict[str, list[str]]:
    """Read CRF category lists from document_extracts.crf.category_lists.

    Each entry may be either a bare list of values or a dict with a
    ``values`` key (the shape produced by the studio's CRF extractor, which
    also stores a source excerpt). Keys are normalised to uppercase ADaM
    variable names. Returns {} when nothing is configured.
    """
    crf = (raw.get("document_extracts", {}) or {}).get("crf", {}) or {}
    lists = crf.get("category_lists", {}) or {}
    out: dict[str, list[str]] = {}
    for var, spec in lists.items():
        values = spec.get("values") if isinstance(spec, dict) else spec
        if values:
            out[str(var).upper()] = [str(v) for v in values]
    return out


@dataclass
class ShellRegistry:
    version: int
    study_id: str
    header_template: str
    footer_template: str
    column_layouts: dict[str, list[dict[str, Any]]]
    shells: dict[str, dict[str, Any]]
    chemistry_thresholds: dict[str, list[dict[str, Any]]]
    hematology_thresholds: dict[str, list[dict[str, Any]]]
    raw: dict[str, Any] = field(default_factory=dict)

    def shell(self, shell_id: str) -> dict[str, Any]:
        try:
            return self.shells[shell_id]
        except KeyError as exc:
            raise KeyError(f"Shell '{shell_id}' not in registry") from exc

    def column_layout(self, layout_id: str) -> list[dict[str, Any]]:
        try:
            return self.column_layouts[layout_id]
        except KeyError as exc:
            raise KeyError(f"Column layout '{layout_id}' not defined") from exc


def load_shell_registry(path: str | Path) -> ShellRegistry:
    """Load shells/registry.yaml and index shells by id.

    The registry can either contain a legacy inline ``shells:`` list or a
    ``shell_files:`` list whose entries are YAML files relative to the registry
    directory. In both cases callers receive the same merged shape.
    """
    raw = _load_registry_raw(path)
    shells_list = raw.get("shells", [])
    shells = {s["id"]: s for s in shells_list}
    if len(shells) != len(shells_list):
        seen: set[str] = set()
        dupes = [s["id"] for s in shells_list if s["id"] in seen or seen.add(s["id"])]
        raise ValueError(f"Duplicate shell ids: {sorted(set(dupes))}")

    return ShellRegistry(
        version=int(raw.get("version", 1)),
        study_id=raw.get("study_id", ""),
        header_template=raw.get("header_template", ""),
        footer_template=raw.get("footer_template", ""),
        column_layouts=dict(raw.get("column_layouts", {})),
        shells=shells,
        chemistry_thresholds=dict(raw.get("chemistry_thresholds", {})),
        hematology_thresholds=dict(raw.get("hematology_thresholds", {})),
        raw=raw,
    )


def _load_registry_raw(path: str | Path) -> dict[str, Any]:
    registry_path = Path(path)
    with open(registry_path) as f:
        raw = yaml.safe_load(f) or {}

    if raw.get("shell_files"):
        shells: list[dict[str, Any]] = []
        for rel in raw["shell_files"]:
            shell_path = registry_path.parent / rel
            with open(shell_path) as f:
                shell = yaml.safe_load(f) or {}
            if "id" not in shell:
                raise ValueError(f"Shell file {shell_path} is missing required key 'id'")
            shells.append(shell)
        raw["shells"] = shells
    else:
        raw["shells"] = raw.get("shells", [])
    return raw


def _require_keys(d: dict[str, Any], keys: list[str]) -> None:
    missing = [k for k in keys if k not in d]
    if missing:
        raise ValueError(f"study_config missing required keys: {missing}")
