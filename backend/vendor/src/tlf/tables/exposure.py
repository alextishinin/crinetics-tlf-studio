"""Generate exposure and treatment-compliance tables.

This file builds Table 14.1.3.1 for extent of exposure and Table 14.1.3.2
for treatment compliance. Both tables use ADSL variables such as treatment
duration, average daily dose, and cumulative dose.

For compliance, the module derives each subject's compliance percentage by
comparing the observed average daily dose with the target daily dose from
the study configuration, then summarizes the result continuously and by
compliance categories.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl

from tlf import shell_layouts
from tlf.aggregator import categorical_bins, continuous_summary
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
from tlf.tables.baseline import _stats_from_series
from tlf.validator import format_n_pct, raw_decimal_places


EXPOSURE_SHELL_ID = "t_14_1_3_1"
EXPOSURE_TABLE_NUMBER = "14.1.3.1"

COMPLIANCE_SHELL_ID = "t_14_1_3_2"
COMPLIANCE_TABLE_NUMBER = "14.1.3.2"


# ---------------------------------------------------------------------------
# Extent of Exposure
# ---------------------------------------------------------------------------

def generate(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Generate Table 14.1.3.1 — Extent of Exposure."""
    shell = registry.shell(EXPOSURE_SHELL_ID)
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    domains = load_domains(cfg, shell["adam_domains"])
    adsl_raw = domains["adsl"]
    adsl = filter_to_set(adsl_raw, cfg, shell["analysis_set"])

    denominators = column_denominators(cfg, columns, adsl=adsl_raw, analysis_set=shell["analysis_set"])
    headers, n_labels = build_column_headers(cfg, columns, denominators, label_header="Parameter")

    if cfg.shell_mode:
        body_rows = shell_layouts.exposure(columns)
    else:
        body_rows = []
        # Issue 11: full label per shell template
        body_rows.extend(_continuous_block(
            "Duration of Exposure During the Randomized Treatment Period (days)",
            adsl, "TRTDUR", columns, denominators,
        ))

        # Categorical duration bins from study config
        bins = cfg.exposure_duration_bins
        if bins:
            body_rows.append([
                "Duration of Exposure During the Randomized Treatment Period (days), n (%)",
                *[""] * len(columns),
            ])
            body_rows.extend(_bins_block(adsl, "TRTDUR", bins, columns, denominators))

        # Issue 3a (audit): "Average Daily Dose (mg)" removed — not in shell template.
        body_rows.extend(_continuous_block("Total Amount of Dose Received (mg)", adsl, "CUMDOSE", columns, denominators))

        # Issue 3b (audit): Total Number of Dose / Injection Received — placeholder
        # when ADaM does not capture per-subject dose counts. Section header only.
        body_rows.append(["Total Number of Dose/Injection Received, n (%)", *[""] * len(columns)])
        body_rows.append(["   Not collected in this study", *["-" for _ in columns]])

        # Issue 3c (audit): Exposure Gap Due to Interruption — placeholder block
        # when ADaM does not capture interruption duration.
        body_rows.append(["Exposure Gap Due to Interruption (days)", *[""] * len(columns)])
        for stat in ("n", "Mean", "SD, SE", "Median", "Min, Max"):
            body_rows.append([f"    {stat}", *["-" for _ in columns]])

    footnotes = render_footnotes(
        shell.get("footnotes", []),
        context=cfg.footnote_context(),
    )

    spec = TableSpec(
        shell_id=EXPOSURE_SHELL_ID,
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
    )
    path = resolve_output_path(cfg, EXPOSURE_TABLE_NUMBER, out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


# ---------------------------------------------------------------------------
# Treatment Compliance
# ---------------------------------------------------------------------------

def generate_compliance(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Generate Table 14.1.3.2 — Treatment Compliance."""
    shell = registry.shell(COMPLIANCE_SHELL_ID)
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    domains = load_domains(cfg, shell["adam_domains"])
    adsl_raw = domains["adsl"]
    adsl = filter_to_set(adsl_raw, cfg, shell["analysis_set"])
    adsl = _add_compliance_pct(adsl, cfg)

    denominators = column_denominators(cfg, columns, adsl=adsl_raw, analysis_set=shell["analysis_set"])
    headers, n_labels = build_column_headers(cfg, columns, denominators, label_header="Parameter")

    if cfg.shell_mode:
        body_rows = shell_layouts.compliance(columns)
    else:
        body_rows = []

        # Issue 4a (audit): Dose Intensity and Relative Dose Intensity — placeholder
        # blocks when not defined in the SAP for this study.
        for header in ("Dose Intensity (unit)", "Relative Dose Intensity (%)"):
            body_rows.append([header, *[""] * len(columns)])
            for stat in ("n", "Mean", "SD, SE", "Median", "Min, Max"):
                body_rows.append([f"    {stat}", *["-" for _ in columns]])

        body_rows.extend(_continuous_block("Treatment Compliance (%)", adsl, "COMPLIANCE_PCT", columns, denominators))

        body_rows.append(["Treatment Compliance (%), n (%)", *[""] * len(columns)])
        bins = [
            {"label": "< 80%",      "lo": None, "hi": 80,   "inclusive_hi": False},
            {"label": "80 to 120%", "lo": 80,   "hi": 120,  "inclusive_lo": True, "inclusive_hi": True},
            {"label": "> 120%",     "lo": 120,  "hi": None, "inclusive_lo": False},
        ]
        # Issue 4b (audit): show "-" for arms where compliance is not applicable
        # (e.g. Placebo with no target daily dose) rather than "0".
        na_arms = {arm.trtpn for arm in cfg.treatment_arms if arm.target_daily_dose_mg is None}
        body_rows.extend(_bins_block(adsl, "COMPLIANCE_PCT", bins, columns, denominators, na_arms=na_arms))

    footnotes = render_footnotes(
        shell.get("footnotes", []),
        context=cfg.footnote_context(),
    )

    spec = TableSpec(
        shell_id=COMPLIANCE_SHELL_ID,
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
    )
    path = resolve_output_path(cfg, COMPLIANCE_TABLE_NUMBER, out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def _add_compliance_pct(adsl: pl.DataFrame, cfg: StudyConfig) -> pl.DataFrame:
    """Per-subject compliance = AVGDD / target_daily_dose * 100.
    Placebo (target=null) gets null compliance."""
    target_df = pl.DataFrame(
        {
            "TRT01PN": [arm.trtpn for arm in cfg.treatment_arms],
            "_target_dose": [arm.target_daily_dose_mg for arm in cfg.treatment_arms],
        },
        schema={"TRT01PN": pl.Int64, "_target_dose": pl.Float64},
    )
    joined = adsl.join(target_df, on="TRT01PN", how="left")
    return joined.with_columns(
        pl.when(pl.col("_target_dose").is_not_null() & (pl.col("_target_dose") > 0))
        .then(pl.col("AVGDD") / pl.col("_target_dose") * 100.0)
        .otherwise(None)
        .alias("COMPLIANCE_PCT")
    ).drop("_target_dose")


# ---------------------------------------------------------------------------
# Block helpers
# ---------------------------------------------------------------------------

def _continuous_block(
    label: str,
    df: pl.DataFrame,
    var: str,
    columns: list[dict],
    denominators: dict[int | str, int],
) -> list[list[str]]:
    arms_trtpn = [c["trtpn"] for c in columns if not c.get("is_total")]
    summary = continuous_summary(df, value_col=var, arm_col="TRT01PN", arms=arms_trtpn)
    total_stats = None
    if any(c.get("is_total") for c in columns):
        total_stats = _stats_from_series(df.select(var).drop_nulls().to_series())
    raw_dp = raw_decimal_places(df.select(var).drop_nulls().to_series().to_list())

    rows: list[list[str]] = [[label, *[""] * len(columns)]]
    rows.extend(
        continuous_summary_rows(
            columns=columns,
            stats_per_arm=summary.stats,
            raw_dp=raw_dp,
            total_stats=total_stats,
        )
    )
    return rows


def _bins_block(
    df: pl.DataFrame,
    var: str,
    bins: list[dict],
    columns: list[dict],
    denominators: dict[int | str, int],
    na_arms: set[int] | None = None,
) -> list[list[str]]:
    """Bin a continuous variable into categories and emit one row per bin.

    ``na_arms``: trtpn values for which this parameter is not applicable
    (e.g. Placebo arm in a compliance table). Those cells render as "-"
    instead of "0 (-)".
    """
    arms_trtpn = [c["trtpn"] for c in columns if not c.get("is_total")]
    arm_denoms = {a: denominators.get(a, 0) for a in arms_trtpn}
    summary = categorical_bins(
        df, value_col=var, bins=bins, arm_col="TRT01PN",
        arms=arms_trtpn, denominators=arm_denoms,
    )
    na = na_arms or set()
    rows: list[list[str]] = []
    for lbl in summary.counts:
        cells = []
        for col in columns:
            if col.get("is_total"):
                n = sum(summary.counts[lbl].get(a, 0) for a in arms_trtpn if a not in na)
                cells.append(format_n_pct(n, denominators.get("TOTAL", 0)))
            else:
                arm = int(col["trtpn"])
                if arm in na:
                    cells.append("-")
                else:
                    n = summary.counts[lbl].get(arm, 0)
                    cells.append(format_n_pct(n, arm_denoms.get(arm, 0)))
        rows.append([f"   {lbl}", *cells])
    return rows
