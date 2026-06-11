"""Generate supplemental administrative tables (14.1.1.4, 14.1.2.3, 14.1.2.4).

These tables depend on ADaM datasets that the CDISCPILOT01 reference study
does not include — ADDV (protocol deviations) and ADCM (medications). Each
generator uses the dataset when one is present under the study's data folder
and otherwise renders the shell structure with empty cells plus a footnote
explaining why, mirroring how the ECG tables handle a missing ADEG.

The data-driven paths are deliberately tolerant about column names (the exact
ADaM spec varies between sponsors); the column candidates tried for each role
are listed next to each generator.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl

from tlf import shell_layouts
from tlf.config import ShellRegistry, StudyConfig
from tlf.footnotes import render_footnotes
from tlf.renderer import TableSpec, render_table, resolve_output_path
from tlf.tables._common import (
    build_column_headers,
    column_denominators,
    load_domains,
    resolve_columns,
)
from tlf.validator import format_n_pct


DEVIATIONS_SHELL_ID = "t_14_1_1_4"
DEVIATIONS_TABLE_NUMBER = "14.1.1.4"
PRIOR_MED_SHELL_ID = "t_14_1_2_3"
PRIOR_MED_TABLE_NUMBER = "14.1.2.3"
CON_MED_SHELL_ID = "t_14_1_2_4"
CON_MED_TABLE_NUMBER = "14.1.2.4"


def _try_load(cfg: StudyConfig, name: str) -> pl.DataFrame | None:
    """Return the named ADaM dataset if a file for it exists, else None."""
    candidates = [cfg.adam_path / f"{name}.{ext}" for ext in ("parquet", "sas7bdat", "xpt")]
    if not any(p.exists() for p in candidates):
        return None
    from tlf.reader import read_adam

    return read_adam(name, cfg.adam_path).collect()


def _first_col(df: pl.DataFrame, candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _subject_count_cells(
    sub: pl.DataFrame,
    columns: list[dict],
    denominators: dict,
    arm_col: str,
) -> list[str]:
    """n (%) of distinct subjects in `sub`, per column layout."""
    cells: list[str] = []
    for col in columns:
        if col.get("is_total"):
            n = sub.select("USUBJID").n_unique() if not sub.is_empty() else 0
            cells.append(format_n_pct(n, denominators.get("TOTAL", 0)))
        else:
            trtpn = int(col["trtpn"])
            arm_sub = sub.filter(pl.col(arm_col) == trtpn) if not sub.is_empty() else sub
            n = arm_sub.select("USUBJID").n_unique() if not arm_sub.is_empty() else 0
            cells.append(format_n_pct(n, denominators.get(trtpn, 0)))
    return cells


def _grouped_rows(
    df: pl.DataFrame,
    columns: list[dict],
    denominators: dict,
    *,
    arm_col: str,
    group_col: str,
    sub_col: str | None,
) -> list[list[str]]:
    """Level-0 rows per `group_col` value with level-1 rows per `sub_col`."""
    rows: list[list[str]] = []
    groups = (
        df.select(group_col).drop_nulls().unique().to_series().to_list()
        if group_col in df.columns else []
    )
    totals = {
        g: df.filter(pl.col(group_col) == g).select("USUBJID").n_unique()
        for g in groups
    }
    for g in sorted(groups, key=lambda g: (-totals[g], str(g))):
        g_sub = df.filter(pl.col(group_col) == g)
        rows.append([str(g), *_subject_count_cells(g_sub, columns, denominators, arm_col)])
        if sub_col and sub_col in df.columns and sub_col != group_col:
            subs = g_sub.select(sub_col).drop_nulls().unique().to_series().to_list()
            sub_totals = {
                s: g_sub.filter(pl.col(sub_col) == s).select("USUBJID").n_unique()
                for s in subs
            }
            for s in sorted(subs, key=lambda s: (-sub_totals[s], str(s))):
                s_sub = g_sub.filter(pl.col(sub_col) == s)
                rows.append([
                    f"   {s}",
                    *_subject_count_cells(s_sub, columns, denominators, arm_col),
                ])
    return rows


def _render(
    cfg: StudyConfig,
    registry: ShellRegistry,
    shell_id: str,
    table_number: str,
    body_rows: list[list[str]],
    footnotes_raw: list[str],
    *,
    label_header: str,
    out_dir: Path | None,
    run_dt: datetime | None,
) -> Path:
    shell = registry.shell(shell_id)
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl = load_domains(cfg, ["adsl"])["adsl"]
    denominators = column_denominators(cfg, columns, adsl=adsl, analysis_set=shell["analysis_set"])
    headers, n_labels = build_column_headers(cfg, columns, denominators, label_header=label_header)
    footnotes = render_footnotes(footnotes_raw, context=cfg.footnote_context())
    spec = TableSpec(
        shell_id=shell_id,
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
    )
    path = resolve_output_path(cfg, table_number, out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


# ---------------------------------------------------------------------------
# 14.1.1.4 — Important Protocol Deviations
# ---------------------------------------------------------------------------

def generate_protocol_deviations(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Table 14.1.1.4 — Important Protocol Deviations from ADDV (if present).

    Column candidates: category DVCAT/DVDECOD, subcategory DVSCAT/DVTERM,
    arm TRT01PN/TRTPN/TRTAN.
    """
    shell = registry.shell(DEVIATIONS_SHELL_ID)
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    footnotes_raw = list(shell.get("footnotes", []))

    if cfg.shell_mode:
        body_rows = shell_layouts.protocol_deviations(columns)
        return _render(cfg, registry, DEVIATIONS_SHELL_ID, DEVIATIONS_TABLE_NUMBER,
                       body_rows, footnotes_raw, label_header="",
                       out_dir=out_dir, run_dt=run_dt)

    addv = _try_load(cfg, "addv")
    if addv is None or addv.is_empty():
        body_rows = [[
            "Subjects with at Least One Important Protocol Deviation",
            *[""] * len(columns),
        ]]
        footnotes_raw.append(
            "No protocol deviation (ADDV) dataset was available for this study; "
            "the table is rendered with the shell structure and empty data cells."
        )
        return _render(cfg, registry, DEVIATIONS_SHELL_ID, DEVIATIONS_TABLE_NUMBER,
                       body_rows, footnotes_raw, label_header="",
                       out_dir=out_dir, run_dt=run_dt)

    arm_col = _first_col(addv, ("TRT01PN", "TRTPN", "TRTAN")) or "TRT01PN"
    cat_col = _first_col(addv, ("DVCAT", "DVDECOD"))
    sub_col = _first_col(addv, ("DVSCAT", "DVTERM"))

    adsl = load_domains(cfg, ["adsl"])["adsl"]
    denominators = column_denominators(cfg, columns, adsl=adsl, analysis_set=shell["analysis_set"])

    body_rows = [[
        "Subjects with at Least One Important Protocol Deviation",
        *_subject_count_cells(addv, columns, denominators, arm_col),
    ]]
    if cat_col:
        body_rows.extend(_grouped_rows(
            addv, columns, denominators,
            arm_col=arm_col, group_col=cat_col, sub_col=sub_col,
        ))
    return _render(cfg, registry, DEVIATIONS_SHELL_ID, DEVIATIONS_TABLE_NUMBER,
                   body_rows, footnotes_raw, label_header="",
                   out_dir=out_dir, run_dt=run_dt)


# ---------------------------------------------------------------------------
# 14.1.2.3 / 14.1.2.4 — Prior / Concomitant Medications
# ---------------------------------------------------------------------------

def generate_prior_medications(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Table 14.1.2.3 — Prior Medication from ADCM (if present)."""
    return _render_medications(cfg, registry, prior=True, out_dir=out_dir, run_dt=run_dt)


def generate_concomitant_medications(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Table 14.1.2.4 — Concomitant Medication from ADCM (if present)."""
    return _render_medications(cfg, registry, prior=False, out_dir=out_dir, run_dt=run_dt)


def _render_medications(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    prior: bool,
    out_dir: Path | None,
    run_dt: datetime | None,
) -> Path:
    """Shared body for the two medication tables.

    Filter candidates: prior PREFL='Y' (else ASTDT < TRTSDT); concomitant
    CONFL='Y', else ONTRTFL='Y'. Grouping candidates: ATC2/CMCLAS for the
    level-0 rows, ATC4/CMDECOD for the level-1 rows. Arm TRTAN/TRT01PN/TRTPN.
    """
    shell_id = PRIOR_MED_SHELL_ID if prior else CON_MED_SHELL_ID
    number = PRIOR_MED_TABLE_NUMBER if prior else CON_MED_TABLE_NUMBER
    kind = "Prior" if prior else "Concomitant"
    shell = registry.shell(shell_id)
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    footnotes_raw = list(shell.get("footnotes", []))

    if cfg.shell_mode:
        body_rows = shell_layouts.medications(columns, prior=prior)
        return _render(cfg, registry, shell_id, number, body_rows, footnotes_raw,
                       label_header="", out_dir=out_dir, run_dt=run_dt)

    adcm = _try_load(cfg, "adcm")
    if adcm is None or adcm.is_empty():
        body_rows = [[
            f"Subjects with at Least One {kind} Medication",
            *[""] * len(columns),
        ]]
        footnotes_raw.append(
            "No medication (ADCM) dataset was available for this study; the "
            "table is rendered with the shell structure and empty data cells."
        )
        return _render(cfg, registry, shell_id, number, body_rows, footnotes_raw,
                       label_header="", out_dir=out_dir, run_dt=run_dt)

    if prior:
        if "PREFL" in adcm.columns:
            sub = adcm.filter(pl.col("PREFL") == "Y")
        elif "ASTDT" in adcm.columns and "TRTSDT" in adcm.columns:
            sub = adcm.filter(pl.col("ASTDT") < pl.col("TRTSDT"))
        else:
            sub = adcm
    else:
        if "CONFL" in adcm.columns:
            sub = adcm.filter(pl.col("CONFL") == "Y")
        elif "ONTRTFL" in adcm.columns:
            sub = adcm.filter(pl.col("ONTRTFL") == "Y")
        else:
            sub = adcm

    arm_col = _first_col(adcm, ("TRTAN", "TRT01PN", "TRTPN")) or "TRTAN"
    atc2_col = _first_col(adcm, ("ATC2", "CMCLAS"))
    atc4_col = _first_col(adcm, ("ATC4", "CMDECOD"))

    adsl = load_domains(cfg, ["adsl"])["adsl"]
    denominators = column_denominators(cfg, columns, adsl=adsl, analysis_set=shell["analysis_set"])

    body_rows = [[
        f"Subjects with at Least One {kind} Medication",
        *_subject_count_cells(sub, columns, denominators, arm_col),
    ]]
    if atc2_col:
        body_rows.extend(_grouped_rows(
            sub, columns, denominators,
            arm_col=arm_col, group_col=atc2_col, sub_col=atc4_col,
        ))
    return _render(cfg, registry, shell_id, number, body_rows, footnotes_raw,
                   label_header="", out_dir=out_dir, run_dt=run_dt)
