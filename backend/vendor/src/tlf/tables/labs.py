"""Generate chemistry and hematology laboratory tables.

This file builds the 14.3.4.x lab table family from the ADLB-style lab
domains. It creates continuous summaries by parameter and visit, adds
change-from-baseline summaries where available, counts normal/low/high
abnormality categories, and counts subjects who meet specific lab
thresholds defined in the shell registry.

The same code supports both chemistry and hematology shells by choosing
the correct lab domain and threshold set from the shell ID.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from tlf.aggregator import (
    anrind_shift,
    categorical_summary,
    continuous_summary,
)
from tlf import shell_layouts
from tlf.config import ShellRegistry, StudyConfig
from tlf.footnotes import render_footnotes
from tlf.renderer import TableSpec, render_table, resolve_output_path
from tlf.tables._common import (
    build_column_headers,
    column_denominators,
    continuous_summary_rows,
    filter_to_set,
    load_domains,
    prepend_blank_column,
    resolve_columns,
)
from tlf.tables.baseline import _stats_from_series
from tlf.validator import format_n_pct, raw_decimal_places


# Map (shell_id, fallback domain) so a single function generates all six
# lab tables.
_DOMAIN_BY_SHELL = {
    "t_14_3_4_1": "adlbc",
    "t_14_3_4_2": "adlbh",
    "t_14_3_4_3": "adlbc",
    "t_14_3_4_4": "adlbh",
    "t_14_3_4_5": "adlbc",
    "t_14_3_4_6": "adlbh",
}
_NUMBER_BY_SHELL = {
    "t_14_3_4_1": "14.3.4.1",
    "t_14_3_4_2": "14.3.4.2",
    "t_14_3_4_3": "14.3.4.3",
    "t_14_3_4_4": "14.3.4.4",
    "t_14_3_4_5": "14.3.4.5",
    "t_14_3_4_6": "14.3.4.6",
}


def generate_summary(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    shell_id: str = "t_14_3_4_1",
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Continuous summary by parameter × visit. 14.3.4.1 / 14.3.4.2."""
    shell = registry.shell(shell_id)
    return _render_continuous(shell, cfg, registry, out_dir, run_dt)


def generate_abnormality(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    shell_id: str = "t_14_3_4_3",
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """ANRIND shift table by parameter × visit. 14.3.4.3 / 14.3.4.4."""
    shell = registry.shell(shell_id)
    return _render_abnormality(shell, cfg, registry, out_dir, run_dt)


def generate_specific_levels(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    shell_id: str = "t_14_3_4_5",
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Specific-level thresholds. 14.3.4.5 / 14.3.4.6."""
    shell = registry.shell(shell_id)
    return _render_thresholds(shell, cfg, registry, out_dir, run_dt)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _load_lab(cfg: StudyConfig, shell: dict) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return (adsl, lab) DataFrames. The lab domain is whichever ADLBx the
    shell references."""
    domain = _DOMAIN_BY_SHELL[shell["id"]]
    domains = load_domains(cfg, ["adsl", domain])
    return domains["adsl"], domains[domain]


def _arms(cfg: StudyConfig, columns: list[dict]) -> list[int]:
    return [int(c["trtpn"]) for c in columns if not c.get("is_total")]


def _render_continuous(
    shell: dict,
    cfg: StudyConfig,
    registry: ShellRegistry,
    out_dir: Path | None,
    run_dt: datetime | None,
) -> Path:
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl_raw, lab = _load_lab(cfg, shell)
    lab = lab.filter(pl.col("ANL01FL") == "Y")
    # Issue 7 (audit): exclude derived PARAMs that describe a change relative
    # to normal range — they are SDTM-derived and don't belong in this shell.
    lab = lab.filter(~pl.col("PARAM").str.contains("change from previous visit"))
    denoms = column_denominators(cfg, columns, adsl=adsl_raw, analysis_set=shell["analysis_set"])
    # Issue 2: single-line label header
    headers, n_labels = build_column_headers(
        cfg, columns, denoms, label_header="Parameter (Unit) / Visit / Statistic",
    )

    arms = _arms(cfg, columns)
    has_chg = "CHG" in lab.columns
    has_ablfl = "ABLFL" in lab.columns
    # Shell mode replaces the body with the static layout below — skip the
    # per-parameter aggregation entirely rather than computing and discarding.
    if cfg.shell_mode:
        params: list[str] = []
    else:
        params = sorted(lab.select("PARAM").drop_nulls().unique().to_series().to_list())
    body_rows: list[list[str]] = []
    for param in params:
        body_rows.append([param, *[""] * len(columns)])
        sub_param = lab.filter(pl.col("PARAM") == param)
        visits_ordered = (
            sub_param.select(["AVISIT", "AVISITN"]).drop_nulls().unique()
            .sort("AVISITN")
            .select("AVISIT").to_series().to_list()
        )
        all_vals = sub_param.select("AVAL").drop_nulls().to_series().to_list()
        raw_dp = raw_decimal_places(all_vals)
        for visit in visits_ordered:
            sub = sub_param.filter(pl.col("AVISIT") == visit)
            body_rows.append([f"  {visit}", *[""] * len(columns)])
            # Absolute value block
            summary = continuous_summary(sub, value_col="AVAL", arm_col="TRTPN", arms=arms)
            total_stats = _stats_from_series(sub.select("AVAL").drop_nulls().to_series()) if any(c.get("is_total") for c in columns) else None
            body_rows.extend(
                continuous_summary_rows(
                    columns=columns,
                    stats_per_arm=summary.stats,
                    raw_dp=raw_dp,
                    total_stats=total_stats,
                    label_indent="    ",
                )
            )
            # Issue 23: Change from Baseline block for post-baseline visits
            is_baseline = has_ablfl and sub.filter(pl.col("ABLFL") == "Y").height == sub.height
            if has_chg and not is_baseline:
                sub_chg = sub.filter(pl.col("CHG").is_not_null()) if has_chg else sub.head(0)
                if not sub_chg.is_empty():
                    body_rows.append([f"  Change from Baseline to {visit}", *[""] * len(columns)])
                    chg_dp = raw_decimal_places(sub_chg.select("CHG").drop_nulls().to_series().to_list())
                    chg_sum = continuous_summary(sub_chg, value_col="CHG", arm_col="TRTPN", arms=arms)
                    chg_total = _stats_from_series(sub_chg.select("CHG").drop_nulls().to_series()) if any(c.get("is_total") for c in columns) else None
                    body_rows.extend(
                        continuous_summary_rows(
                            columns=columns,
                            stats_per_arm=chg_sum.stats,
                            raw_dp=chg_dp,
                            total_stats=chg_total,
                            label_indent="    ",
                        )
                    )
        # Issue 6 (audit): Last Value + Change from Baseline to Last Value
        body_rows.extend(_last_value_blocks(sub_param, columns, arms, raw_dp))

    if cfg.shell_mode:
        body_rows = shell_layouts.labs_summary(columns)
    footnotes = render_footnotes(shell.get("footnotes", []), context=cfg.footnote_context())
    # Issue 3: prepend blank leading column
    headers, n_labels, body_rows, col_widths = prepend_blank_column(
        headers, n_labels,
        body_rows or [["No participant meeting the selection criteria", *[""] * len(columns)]],
    )
    spec = TableSpec(
        shell_id=shell["id"],
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
        col_rel_widths=col_widths,
    )
    path = resolve_output_path(cfg, _NUMBER_BY_SHELL[shell["id"]], out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def _render_abnormality(
    shell: dict,
    cfg: StudyConfig,
    registry: ShellRegistry,
    out_dir: Path | None,
    run_dt: datetime | None,
) -> Path:
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl_raw, lab = _load_lab(cfg, shell)
    lab = lab.filter(pl.col("ANL01FL") == "Y")
    # Issue 7 (audit): drop the "change from previous visit, relative to normal
    # range" derived PARAMs that the shell template does not include.
    lab = lab.filter(~pl.col("PARAM").str.contains("change from previous visit"))
    denoms = column_denominators(cfg, columns, adsl=adsl_raw, analysis_set=shell["analysis_set"])
    # Issue 2: single-line label header
    headers, n_labels = build_column_headers(
        cfg, columns, denoms, label_header="Parameter (Unit) / Visit",
    )

    arms = _arms(cfg, columns)
    arm_denoms = {a: denoms.get(a, 0) for a in arms}
    # Shell mode: skip the aggregation; the body is replaced below.
    if cfg.shell_mode:
        params: list[str] = []
    else:
        params = sorted(lab.select("PARAM").drop_nulls().unique().to_series().to_list())

    body_rows: list[list[str]] = []
    _anrind_display = {"N": "Normal", "L": "Low", "H": "High", "Missing": "Missing"}
    for param in params:
        body_rows.append([param, *[""] * len(columns)])
        sub_param = lab.filter(pl.col("PARAM") == param)
        visits_ordered = (
            sub_param.select(["AVISIT", "AVISITN"]).drop_nulls().unique()
               .sort("AVISITN").select("AVISIT").to_series().to_list()
        )
        for visit in visits_ordered:
            body_rows.append([f"  {visit}", *[""] * len(columns)])
            summary = anrind_shift(
                lab, param=param, visit=visit, arms=arms,
                denominators=arm_denoms, arm_col="TRTPN",
            )
            for cat in ("N", "L", "H", "Missing"):
                cells = []
                for col in columns:
                    if col.get("is_total"):
                        n = sum(summary.counts[cat].get(a, 0) for a in arms)
                        cells.append(format_n_pct(n, denoms.get("TOTAL")))
                    else:
                        arm = int(col["trtpn"])
                        cells.append(format_n_pct(summary.counts[cat].get(arm, 0), arm_denoms.get(arm, 0)))
                body_rows.append([f"    {_anrind_display[cat]}", *cells])
            # Issue 25: Total row removed — template shows only Normal/Low/High/Missing
        # Issue 6 (audit): Last Value + Change from Baseline to Last Value blocks
        all_vals = sub_param.select("AVAL").drop_nulls().to_series().to_list()
        raw_dp = raw_decimal_places(all_vals)
        body_rows.extend(_last_value_blocks(sub_param, columns, arms, raw_dp))

    if cfg.shell_mode:
        body_rows = shell_layouts.labs_abnormality(columns)
    footnotes = render_footnotes(shell.get("footnotes", []), context=cfg.footnote_context())
    # Issue 3: prepend blank leading column
    headers, n_labels, body_rows, col_widths = prepend_blank_column(
        headers, n_labels,
        body_rows or [["No participant meeting the selection criteria", *[""] * len(columns)]],
    )
    spec = TableSpec(
        shell_id=shell["id"],
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
        col_rel_widths=col_widths,
    )
    path = resolve_output_path(cfg, _NUMBER_BY_SHELL[shell["id"]], out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def _render_thresholds(
    shell: dict,
    cfg: StudyConfig,
    registry: ShellRegistry,
    out_dir: Path | None,
    run_dt: datetime | None,
) -> Path:
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl_raw, lab = _load_lab(cfg, shell)
    lab = lab.filter(pl.col("ANL01FL") == "Y")
    denoms = column_denominators(cfg, columns, adsl=adsl_raw, analysis_set=shell["analysis_set"])
    headers, n_labels = build_column_headers(
        cfg, columns, denoms, label_header="Parameter (Unit)",
    )

    # Pull thresholds dict referenced by the shell
    thresholds_key = next(
        (e.get("thresholds_key") for e in shell.get("row_schema", []) if "thresholds_key" in e),
        None,
    )
    if thresholds_key == "chemistry_thresholds":
        thresholds = registry.chemistry_thresholds
    elif thresholds_key == "hematology_thresholds":
        thresholds = registry.hematology_thresholds
    else:
        thresholds = {}

    arms = _arms(cfg, columns)
    arm_denoms = {a: denoms.get(a, 0) for a in arms}

    body_rows: list[list[str]] = []
    # Shell mode: skip the aggregation; the body is replaced below.
    for paramcd in ([] if cfg.shell_mode else sorted(thresholds.keys())):
        sub = lab.filter(pl.col("PARAMCD") == paramcd)
        if sub.is_empty():
            continue
        param_name = sub.select("PARAM").drop_nulls().unique().to_series()[0]
        body_rows.append([param_name, *[""] * len(columns)])
        for spec_row in thresholds[paramcd]:
            cond = _threshold_condition(spec_row)
            qualifying = sub.filter(cond) if cond is not None else sub.head(0)
            cells = []
            for col in columns:
                if col.get("is_total"):
                    n = qualifying.select("USUBJID").n_unique()
                    cells.append(format_n_pct(n, denoms.get("TOTAL")))
                else:
                    arm = int(col["trtpn"])
                    n = qualifying.filter(pl.col("TRTPN") == arm).select("USUBJID").n_unique()
                    cells.append(format_n_pct(n, arm_denoms.get(arm, 0)))
            body_rows.append([f"   {spec_row['label']}", *cells])

    if cfg.shell_mode:
        body_rows = shell_layouts.labs_specific_levels(columns)
    footnotes = render_footnotes(shell.get("footnotes", []), context=cfg.footnote_context())
    # Issue 3: prepend blank leading column
    headers, n_labels, body_rows, col_widths = prepend_blank_column(
        headers, n_labels,
        body_rows or [["No participant meeting the selection criteria", *[""] * len(columns)]],
    )
    spec = TableSpec(
        shell_id=shell["id"],
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
        col_rel_widths=col_widths,
    )
    path = resolve_output_path(cfg, _NUMBER_BY_SHELL[shell["id"]], out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def _last_value_blocks(
    sub_param: pl.DataFrame,
    columns: list[dict],
    arms: list[int],
    raw_dp: int,
) -> list[list[str]]:
    """Issue 6 (audit): emit "Last Value" and "Change from Baseline to Last
    Value" continuous-summary blocks for one parameter.

    Last value is the maximum-AVISITN post-baseline non-missing AVAL per
    subject. If no post-baseline data is present, both blocks render with
    dashes so the shell structure is preserved.
    """
    rows: list[list[str]] = []
    has_chg = "CHG" in sub_param.columns
    has_ablfl = "ABLFL" in sub_param.columns
    post = (
        sub_param.filter(pl.col("ABLFL") != "Y")
        if has_ablfl else sub_param
    )
    post = post.filter(pl.col("AVAL").is_not_null())
    if post.is_empty():
        for header in ("  Last Value", "  Change from Baseline to Last Value"):
            rows.append([header, *[""] * len(columns)])
            for stat in ("n", "Mean", "SD, SE", "Median", "Min, Max"):
                rows.append([f"    {stat}", *["-" for _ in columns]])
        return rows

    # Pick each subject's latest post-baseline visit
    last = (
        post.sort(["USUBJID", "AVISITN"], descending=[False, True])
            .group_by("USUBJID").agg(pl.all().first())
    )
    rows.append(["  Last Value", *[""] * len(columns)])
    summary = continuous_summary(last, value_col="AVAL", arm_col="TRTPN", arms=arms)
    total_stats = _stats_from_series(last.select("AVAL").drop_nulls().to_series()) if any(c.get("is_total") for c in columns) else None
    rows.extend(continuous_summary_rows(
        columns=columns, stats_per_arm=summary.stats,
        raw_dp=raw_dp, total_stats=total_stats, label_indent="    ",
    ))

    rows.append(["  Change from Baseline to Last Value", *[""] * len(columns)])
    if has_chg:
        chg = last.filter(pl.col("CHG").is_not_null())
        if not chg.is_empty():
            chg_dp = raw_decimal_places(chg.select("CHG").drop_nulls().to_series().to_list())
            chg_sum = continuous_summary(chg, value_col="CHG", arm_col="TRTPN", arms=arms)
            chg_total = _stats_from_series(chg.select("CHG").drop_nulls().to_series()) if any(c.get("is_total") for c in columns) else None
            rows.extend(continuous_summary_rows(
                columns=columns, stats_per_arm=chg_sum.stats,
                raw_dp=chg_dp, total_stats=chg_total, label_indent="    ",
            ))
            return rows
    # No CHG available — placeholder dashes
    for stat in ("n", "Mean", "SD, SE", "Median", "Min, Max"):
        rows.append([f"    {stat}", *["-" for _ in columns]])
    return rows


def _threshold_condition(spec_row: dict[str, Any]) -> pl.Expr | None:
    op = spec_row.get("op", ">")
    if "x_uln" in spec_row:
        x = float(spec_row["x_uln"])
        col = pl.col("AVAL") / pl.col("A1HI")
    elif "abs_value" in spec_row:
        x = float(spec_row["abs_value"])
        col = pl.col("AVAL")
    else:
        return None
    return {
        ">":  col > x,
        ">=": col >= x,
        "<":  col < x,
        "<=": col <= x,
    }.get(op)
