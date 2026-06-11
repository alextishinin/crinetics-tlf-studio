"""Generate ECG summary and QTcF criteria tables.

This file builds the 14.3.6.x ECG tables when an ADEG dataset is available.
It can summarize ECG interpretation categories, continuous ECG parameters
by visit, and post-baseline QTcF maximum or change-from-baseline criteria.

The current reference study does not include ADEG, so the same functions
also handle the no-data case by producing a valid table that clearly says
no ECG data are available.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl

from tlf import shell_layouts
from tlf.aggregator import categorical_summary, continuous_summary
from tlf.config import ShellRegistry, StudyConfig
from tlf.footnotes import render_footnotes
from tlf.renderer import TableSpec, render_table, resolve_output_path
from tlf.tables._common import (
    build_column_headers,
    column_denominators,
    continuous_summary_rows,
    load_domains,
    prepend_blank_column,
    resolve_columns,
)
from tlf.tables.baseline import _stats_from_series
from tlf.validator import format_n_pct, format_stat, raw_decimal_places


def _try_load_ecg(cfg: StudyConfig) -> pl.DataFrame | None:
    """Return ADEG if present, else None."""
    candidates = [cfg.adam_path / f"adeg.{ext}" for ext in ("parquet", "sas7bdat", "xpt")]
    if not any(p.exists() for p in candidates):
        return None
    from tlf.reader import read_adam
    return read_adam("adeg", cfg.adam_path).collect()


def generate_summary(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Table 14.3.6.1 — Summary of Electrocardiogram."""
    shell = registry.shell("t_14_3_6_1")
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl = load_domains(cfg, ["adsl"])["adsl"]
    denoms = column_denominators(cfg, columns, adsl=adsl, analysis_set=shell["analysis_set"])
    # Issue 2: single-line label header
    headers, n_labels = build_column_headers(
        cfg, columns, denoms, label_header="Parameter (Unit) / Visit / Statistic",
    )

    adeg = _try_load_ecg(cfg)
    body_rows: list[list[str]] = []
    placeholder_footnote: str | None = None

    if cfg.shell_mode:
        # Replaced with the static shell layout below — skip the aggregation.
        pass
    elif adeg is None or adeg.is_empty():
        # Issue 9 (audit): render the full shell structure with empty cells
        # so the layout matches the template, plus a footnote noting that no
        # ECG data was available for this study.
        body_rows.extend(_empty_ecg_structure(columns))
        placeholder_footnote = (
            "No ECG (ADEG) dataset was available for this study; the table is "
            "rendered with the shell structure and empty data cells."
        )
    else:
        adeg = adeg.filter(pl.col("ANL01FL") == "Y") if "ANL01FL" in adeg.columns else adeg
        arms = [int(c["trtpn"]) for c in columns if not c.get("is_total")]
        arm_denoms = {a: denoms.get(a, 0) for a in arms}

        # Interpretation block (if INTERPRT present)
        if "INTERPRT" in adeg.columns:
            body_rows.append(["Interpretation, n (%)", *[""] * len(columns)])
            for visit in _ordered_visits(adeg):
                body_rows.append([f"  {visit}", *[""] * len(columns)])
                sub = adeg.filter(pl.col("AVISIT") == visit)
                summary = categorical_summary(
                    sub, var="INTERPRT", arm_col="TRTPN", arms=arms,
                    denominators=arm_denoms,
                    keep_categories=["Normal", "Abnormal Not CS", "Abnormal CS"],
                )
                for cat in ["Normal", "Abnormal Not CS", "Abnormal CS"]:
                    cells = _arm_cells(summary.counts[cat], columns, denoms, arm_denoms, arms)
                    body_rows.append([f"      {cat}", *cells])

        # Continuous param block per param × visit
        params = sorted(adeg.select("PARAM").drop_nulls().unique().to_series().to_list())
        for param in params:
            body_rows.append([param, *[""] * len(columns)])
            sub_p = adeg.filter(pl.col("PARAM") == param)
            raw_dp = raw_decimal_places(sub_p.select("AVAL").drop_nulls().to_series().to_list())
            for visit in _ordered_visits(sub_p):
                body_rows.append([f"  {visit}", *[""] * len(columns)])
                sub_v = sub_p.filter(pl.col("AVISIT") == visit)
                summary = continuous_summary(sub_v, value_col="AVAL", arm_col="TRTPN", arms=arms)
                total_stats = _stats_from_series(sub_v.select("AVAL").drop_nulls().to_series()) if any(c.get("is_total") for c in columns) else None
                body_rows.extend(
                    continuous_summary_rows(
                        columns=columns,
                        stats_per_arm=summary.stats,
                        raw_dp=raw_dp,
                        total_stats=total_stats,
                        label_indent="    ",
                    )
                )
            # Issue 6 (audit): Last Value + CFB Last Value for each parameter
            from tlf.tables.labs import _last_value_blocks
            body_rows.extend(_last_value_blocks(sub_p, columns, arms, raw_dp))

    if cfg.shell_mode:
        body_rows = shell_layouts.ecg_summary(columns)
    footnotes_raw = list(shell.get("footnotes", []))
    if placeholder_footnote:
        footnotes_raw.append(placeholder_footnote)
    footnotes = render_footnotes(footnotes_raw, context=cfg.footnote_context())
    # Issue 3: prepend blank leading column
    headers, n_labels, body_rows, col_widths = prepend_blank_column(headers, n_labels, body_rows)
    spec = TableSpec(
        shell_id=shell["id"],
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
        col_rel_widths=col_widths,
    )
    path = resolve_output_path(cfg, "14.3.6.1", out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def generate_qtcf_criteria(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Table 14.3.6.2 — Post-Baseline QTcF Meeting Specific Criteria."""
    shell = registry.shell("t_14_3_6_2")
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl = load_domains(cfg, ["adsl"])["adsl"]
    denoms = column_denominators(cfg, columns, adsl=adsl, analysis_set=shell["analysis_set"])
    headers, n_labels = build_column_headers(cfg, columns, denoms, label_header="")

    adeg = _try_load_ecg(cfg)
    body_rows: list[list[str]] = []
    if adeg is None or adeg.is_empty():
        body_rows.append(["No ECG data available", *[""] * len(columns)])
    else:
        adeg = adeg.filter(pl.col("ANL01FL") == "Y") if "ANL01FL" in adeg.columns else adeg
        arms = [int(c["trtpn"]) for c in columns if not c.get("is_total")]
        arm_denoms = {a: denoms.get(a, 0) for a in arms}
        qtcf = adeg.filter(pl.col("PARAMCD") == "QTCF")
        post = qtcf.filter(pl.col("ABLFL") != "Y") if "ABLFL" in qtcf.columns else qtcf

        # Per-subject max post-baseline AVAL and max CHG
        max_aval = post.group_by(["USUBJID", "TRTPN"]).agg(pl.col("AVAL").max().alias("max_aval"))
        max_chg = (
            post.group_by(["USUBJID", "TRTPN"]).agg(pl.col("CHG").max().alias("max_chg"))
            if "CHG" in post.columns else None
        )

        for entry in shell["row_schema"]:
            if entry["kind"] == "header":
                body_rows.append([entry["label"], *[""] * len(columns)])
                continue
            if entry["kind"] != "qtcf_threshold":
                continue
            op = entry["op"]
            value = float(entry["value"])
            basis = entry.get("basis", "max")
            df = max_aval if basis == "max" else max_chg
            if df is None:
                cells = [""] * len(columns)
            else:
                col_name = "max_aval" if basis == "max" else "max_chg"
                qualifying = df.filter(_op_expr(op, pl.col(col_name), value))
                cells = []
                for col in columns:
                    if col.get("is_total"):
                        n = qualifying.select("USUBJID").n_unique()
                        cells.append(format_n_pct(n, denoms.get("TOTAL")))
                    else:
                        arm = int(col["trtpn"])
                        n = qualifying.filter(pl.col("TRTPN") == arm).select("USUBJID").n_unique()
                        cells.append(format_n_pct(n, arm_denoms.get(arm, 0)))
            body_rows.append([f"   {entry['label']}", *cells])

    if cfg.shell_mode:
        body_rows = shell_layouts.qtcf_criteria(columns)
    footnotes = render_footnotes(shell.get("footnotes", []), context=cfg.footnote_context())
    spec = TableSpec(
        shell_id=shell["id"],
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
    )
    path = resolve_output_path(cfg, "14.3.6.2", out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def _ordered_visits(df: pl.DataFrame) -> list[str]:
    return (
        df.select(["AVISIT", "AVISITN"]).drop_nulls().unique()
        .sort("AVISITN").select("AVISIT").to_series().to_list()
    )


def _arm_cells(
    by_arm: dict[int, int],
    columns: list[dict],
    denoms: dict[int | str, int],
    arm_denoms: dict[int, int],
    arms: list[int],
) -> list[str]:
    cells = []
    for col in columns:
        if col.get("is_total"):
            n = sum(by_arm.get(a, 0) for a in arms)
            cells.append(format_n_pct(n, denoms.get("TOTAL")))
        else:
            arm = int(col["trtpn"])
            cells.append(format_n_pct(by_arm.get(arm, 0), arm_denoms.get(arm, 0)))
    return cells


def _op_expr(op: str, col: pl.Expr, value: float) -> pl.Expr:
    return {
        ">":  col > value,
        ">=": col >= value,
        "<":  col < value,
        "<=": col <= value,
    }[op]


# ---------------------------------------------------------------------------
# Issue 9 (audit): placeholder structure for studies with no ADEG dataset.
# ---------------------------------------------------------------------------

_PLACEHOLDER_VISITS = ("Screening", "Baseline", "Week 12", "Week 24", "End of Treatment")
_PLACEHOLDER_PARAMS = (
    "Heart Rate (beats/min)",
    "PR Interval (msec)",
    "QRS Duration (msec)",
    "QT Interval (msec)",
    "QTcF Interval (msec)",
)
_PLACEHOLDER_STATS = ("n", "Mean", "SD, SE", "Median", "Min, Max")
_PLACEHOLDER_INTERPRETATIONS = ("Normal", "Abnormal Not CS", "Abnormal CS")


def _empty_ecg_structure(columns: list[dict]) -> list[list[str]]:
    """Emit the full shell layout with dashes in every data cell."""
    ncol = len(columns)
    rows: list[list[str]] = []
    # Interpretation section
    rows.append(["Interpretation, n (%)", *[""] * ncol])
    for visit in _PLACEHOLDER_VISITS:
        rows.append([f"  {visit}", *[""] * ncol])
        for cat in _PLACEHOLDER_INTERPRETATIONS:
            rows.append([f"      {cat}", *["-" for _ in range(ncol)]])
    # Continuous parameters
    for param in _PLACEHOLDER_PARAMS:
        rows.append([param, *[""] * ncol])
        for visit in _PLACEHOLDER_VISITS:
            rows.append([f"  {visit}", *[""] * ncol])
            for stat in _PLACEHOLDER_STATS:
                rows.append([f"    {stat}", *["-" for _ in range(ncol)]])
            if visit not in ("Screening", "Baseline"):
                rows.append([f"  Change from Baseline to {visit}", *[""] * ncol])
                for stat in _PLACEHOLDER_STATS:
                    rows.append([f"    {stat}", *["-" for _ in range(ncol)]])
        rows.append(["  Last Value", *[""] * ncol])
        for stat in _PLACEHOLDER_STATS:
            rows.append([f"    {stat}", *["-" for _ in range(ncol)]])
        rows.append(["  Change from Baseline to Last Value", *[""] * ncol])
        for stat in _PLACEHOLDER_STATS:
            rows.append([f"    {stat}", *["-" for _ in range(ncol)]])
    return rows
