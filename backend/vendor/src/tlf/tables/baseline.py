"""Generate the demographics and baseline characteristics table.

This file builds Table 14.1.2.1 from ADSL. It reads the row definitions
from the shell registry, summarizes continuous baseline variables such as
age, summarizes categorical variables such as sex or race, calculates the
Total column when requested, and sends the finished rows to the RTF
renderer.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

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
    filter_to_set,
    load_domains,
    resolve_columns,
)
from tlf.validator import (
    format_n_pct,
    format_stat,
    raw_decimal_places,
)


SHELL_ID = "t_14_1_2_1"
TABLE_NUMBER = "14.1.2.1"


# Continuous-summary row order is handled by
# tlf.tables._common.continuous_summary_rows — the five-row Crinetics shell
# layout (n / Mean / SD,SE / Median / Min,Max).


def generate(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    shell = registry.shell(SHELL_ID)
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    domains = load_domains(cfg, shell["adam_domains"])
    adsl_raw = domains["adsl"]
    adsl = filter_to_set(adsl_raw, cfg, shell["analysis_set"])

    denominators = column_denominators(cfg, columns, adsl=adsl_raw, analysis_set=shell["analysis_set"])
    headers, n_labels = build_column_headers(cfg, columns, denominators, label_header="Characteristic")

    if cfg.shell_mode:
        body_rows = shell_layouts.baseline(columns)
    else:
        body_rows = []
        for entry in shell["row_schema"]:
            body_rows.extend(_block(entry, adsl, columns, denominators, cfg))

    footnotes = render_footnotes(
        shell.get("footnotes", []),
        context=cfg.footnote_context(),
    )

    spec = TableSpec(
        shell_id=SHELL_ID,
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
    )
    path = resolve_output_path(cfg, TABLE_NUMBER, out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------

def _block(
    entry: dict,
    adsl: pl.DataFrame,
    columns: list[dict],
    denominators: dict[int | str, int],
    cfg: StudyConfig,
) -> list[list[str]]:
    kind = entry["kind"]
    if kind == "continuous":
        return _continuous_block(entry, adsl, columns)
    if kind == "categorical":
        return _categorical_block(entry, adsl, columns, denominators, cfg)
    return [[entry["label"], *[""] * len(columns)]]


def _continuous_block(
    entry: dict,
    adsl: pl.DataFrame,
    columns: list[dict],
) -> list[list[str]]:
    var = entry["var"]
    arms_trtpn = [c["trtpn"] for c in columns if not c.get("is_total")]
    summary = continuous_summary(adsl, value_col=var, arm_col="TRT01PN", arms=arms_trtpn)

    # For Total we treat all subjects as one group (computed from raw series).
    if any(c.get("is_total") for c in columns):
        total_vals = adsl.select(var).drop_nulls().to_series()
        total_stats = _stats_from_series(total_vals)
    else:
        total_stats = None

    raw_dp = raw_decimal_places(adsl.select(var).drop_nulls().to_series().to_list())

    rows: list[list[str]] = [[entry["label"], *[""] * len(columns)]]
    rows.extend(
        continuous_summary_rows(
            columns=columns,
            stats_per_arm=summary.stats,
            raw_dp=raw_dp,
            total_stats=total_stats,
        )
    )
    return rows


def _stats_from_series(s: pl.Series) -> dict:
    n = int(s.len())
    if n == 0:
        return {k: None for k in ("n", "mean", "sd", "se", "median", "min", "max")} | {"n": 0}
    mean = float(s.mean())
    sd = float(s.std(ddof=1)) if n > 1 else None
    se = (sd / (n ** 0.5)) if sd is not None else None
    return {
        "n": n,
        "mean": mean,
        "sd": sd,
        "se": se,
        "median": float(s.median()),
        "min": float(s.min()),
        "max": float(s.max()),
    }


def _categorical_block(
    entry: dict,
    adsl: pl.DataFrame,
    columns: list[dict],
    denominators: dict[int | str, int],
    cfg: StudyConfig | None = None,
) -> list[list[str]]:
    var = entry["var"]
    keep = entry.get("categories")
    # A human-reviewed CRF category list (from document_extracts.crf) takes
    # precedence over the shell-spec default so the table matches the CRF.
    if cfg is not None:
        crf_order = cfg.crf_category_order(var)
        if crf_order:
            keep = crf_order
    cat_labels: dict[str, str] = entry.get("category_labels", {}) or {}
    arms_trtpn = [c["trtpn"] for c in columns if not c.get("is_total")]
    arm_denoms = {a: denominators.get(a, 0) for a in arms_trtpn}

    # Issue 2 (audit): if the variable is not collected, emit the section
    # header with placeholder empty rows so the shell structure is preserved.
    if entry.get("optional") and var not in adsl.columns:
        rows: list[list[str]] = [[entry["label"], *[""] * len(columns)]]
        if keep:
            for cat in keep:
                rows.append([f"   {cat_labels.get(cat, cat)}", *["-" for _ in columns]])
        else:
            rows.append(["   Not collected in this study", *["-" for _ in columns]])
        return rows

    summary = categorical_summary(
        adsl, var=var, arm_col="TRT01PN", arms=arms_trtpn,
        denominators=arm_denoms, keep_categories=keep,
    )

    # Skip categories whose total count across arms is zero AND where the
    # category was not explicitly requested via category_labels (spec: keep
    # CRF categories, drop unobserved + unrequested ones).
    rows: list[list[str]] = []
    rows.append([entry["label"], *[""] * len(columns)])
    # Determine display order: use the provided category order if any, else alpha
    display = list(keep) if keep else sorted(summary.counts.keys())
    for cat in display:
        n_total = 0
        cells = []
        for col in columns:
            if col.get("is_total"):
                n = sum(summary.counts.get(cat, {}).get(a, 0) for a in arms_trtpn)
                cells.append(format_n_pct(n, denominators.get("TOTAL", 0)))
                n_total += n
            else:
                arm = int(col["trtpn"])
                n = summary.counts.get(cat, {}).get(arm, 0)
                n_total += n
                cells.append(format_n_pct(n, arm_denoms.get(arm, 0)))
        # When an explicit category list is provided (e.g. Race), always show
        # all listed categories even with n=0, so the table structure matches
        # the CRF (Issue 7).  When no list is given, suppress zero-count rows.
        if n_total == 0 and keep is None:
            continue
        rows.append([f"   {cat_labels.get(cat, cat)}", *cells])
    return rows
