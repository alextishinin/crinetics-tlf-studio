"""Generate vital-sign summary and blood-pressure threshold tables.

This file builds the 14.3.5.x vital-sign tables from ADVS. The main
summary table reports continuous vital-sign values by parameter and visit,
including change from baseline for post-baseline visits.

The blood-pressure threshold table finds each subject's maximum
post-baseline systolic or diastolic blood pressure and counts how many
subjects meet the configured threshold rows.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl

from tlf import shell_layouts
from tlf.aggregator import continuous_summary
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
from tlf.validator import format_n_pct, raw_decimal_places


def generate(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Table 14.3.5.1 — Summary of Vital Signs."""
    shell = registry.shell("t_14_3_5_1")
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    domains = load_domains(cfg, ["adsl", "advs"])
    adsl_raw = domains["adsl"]
    advs = domains["advs"].filter(
        (pl.col("ANL01FL") == "Y") & (pl.col("SAFFL") == "Y")
    )
    # The spec excludes Height from this longitudinal summary (it isn't
    # collected post-baseline in a meaningful way).
    advs = advs.filter(pl.col("PARAM") != "Height (cm)")

    denoms = column_denominators(cfg, columns, adsl=adsl_raw, analysis_set=shell["analysis_set"])
    arms = [int(c["trtpn"]) for c in columns if not c.get("is_total")]
    # Issue 2: single-line label header
    headers, n_labels = build_column_headers(
        cfg, columns, denoms, label_header="Parameter (Unit) / Visit / Statistic",
    )

    has_chg = "CHG" in advs.columns
    has_ablfl = "ABLFL" in advs.columns
    # Shell mode replaces the body with the static layout below — skip the
    # per-parameter aggregation entirely rather than computing and discarding.
    if cfg.shell_mode:
        params: list[str] = []
    else:
        params = sorted(advs.select("PARAM").drop_nulls().unique().to_series().to_list())
    body_rows: list[list[str]] = []
    for param in params:
        body_rows.append([param, *[""] * len(columns)])
        sub_p = advs.filter(pl.col("PARAM") == param)
        all_vals = sub_p.select("AVAL").drop_nulls().to_series().to_list()
        raw_dp = raw_decimal_places(all_vals)
        visits = (
            sub_p.select(["AVISIT", "AVISITN"]).drop_nulls().unique()
                 .sort("AVISITN").select("AVISIT").to_series().to_list()
        )
        for visit in visits:
            sub_v = sub_p.filter(pl.col("AVISIT") == visit)
            body_rows.append([f"  {visit}", *[""] * len(columns)])
            # Absolute value block
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
            # Issue 27: Change from Baseline block for post-baseline visits
            is_baseline = has_ablfl and sub_v.filter(pl.col("ABLFL") == "Y").height == sub_v.height
            if has_chg and not is_baseline:
                sub_chg = sub_v.filter(pl.col("CHG").is_not_null())
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
        from tlf.tables.labs import _last_value_blocks
        body_rows.extend(_last_value_blocks(sub_p, columns, arms, raw_dp))

    if cfg.shell_mode:
        body_rows = shell_layouts.vitals_summary(columns)
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
    path = resolve_output_path(cfg, "14.3.5.1", out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def generate_bp_levels(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Table 14.3.5.2 — Post-Baseline BP Meeting Specific Levels."""
    shell = registry.shell("t_14_3_5_2")
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    domains = load_domains(cfg, ["adsl", "advs"])
    adsl_raw = domains["adsl"]
    advs = domains["advs"].filter(
        (pl.col("ANL01FL") == "Y") & (pl.col("SAFFL") == "Y")
    )

    denoms = column_denominators(cfg, columns, adsl=adsl_raw, analysis_set=shell["analysis_set"])
    arms = [int(c["trtpn"]) for c in columns if not c.get("is_total")]
    arm_denoms = {a: denoms.get(a, 0) for a in arms}
    headers, n_labels = build_column_headers(
        cfg, columns, denoms, label_header="",
    )

    # Compute per-subject max post-baseline AVAL for each PARAMCD once.
    post_baseline = advs.filter(pl.col("ABLFL") != "Y")
    sysbp_max = _max_per_subject(post_baseline, "SYSBP")
    diabp_max = _max_per_subject(post_baseline, "DIABP")
    paramcd_to_max = {"SYSBP": sysbp_max, "DIABP": diabp_max}

    body_rows: list[list[str]] = []
    for entry in shell["row_schema"]:
        kind = entry["kind"]
        label = entry["label"]
        if kind == "header":
            body_rows.append([label, *[""] * len(columns)])
            continue
        if kind != "bp_threshold":
            continue
        paramcd = entry["paramcd"]
        op = entry["op"]
        value = float(entry["value"])
        max_df = paramcd_to_max[paramcd]
        qualifying = max_df.filter(_op_expr(op, pl.col("max_aval"), value))
        cells = []
        for col in columns:
            if col.get("is_total"):
                n = qualifying.select("USUBJID").n_unique()
                cells.append(format_n_pct(n, denoms.get("TOTAL")))
            else:
                arm = int(col["trtpn"])
                n = qualifying.filter(pl.col("TRTPN") == arm).select("USUBJID").n_unique()
                cells.append(format_n_pct(n, arm_denoms.get(arm, 0)))
        body_rows.append([f"   {label}", *cells])

    if cfg.shell_mode:
        body_rows = shell_layouts.bp_specific_levels(columns)
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
    path = resolve_output_path(cfg, "14.3.5.2", out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def _max_per_subject(advs: pl.DataFrame, paramcd: str) -> pl.DataFrame:
    sub = advs.filter(pl.col("PARAMCD") == paramcd)
    return (
        sub.group_by(["USUBJID", "TRTPN"])
           .agg(pl.col("AVAL").max().alias("max_aval"))
    )


def _op_expr(op: str, col: pl.Expr, value: float) -> pl.Expr:
    return {
        ">":  col > value,
        ">=": col >= value,
        "<":  col < value,
        "<=": col <= value,
    }[op]
