"""Reusable generator for standard endpoint summary tables.

This file is for tables that follow a common pattern but do not need a
fully custom module. A GenericTableRequest tells the generator which ADaM
domain to read, which table number to use, which analysis set to apply,
which endpoint label to show, and whether the table should be continuous,
categorical, or subgroup-based.

It is useful for efficacy-style domains where rows are usually organized
by parameter, visit, and statistic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

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
from tlf.tables.baseline import _stats_from_series
from tlf.validator import format_n_pct, raw_decimal_places


@dataclass
class GenericTableRequest:
    """Parameters needed to render one generic efficacy table.

    domain: short ADaM name (e.g. 'adqscibc')
    table_number: file-name token, e.g. '14.2.4.1'
    endpoint_label: e.g. 'CIBIC+ Score Over Time'
    analysis_set: ITT / EFF / SAF
    paramcd: optional filter to a single PARAMCD
    layout: 'continuous' | 'categorical' | 'subgroup'
    subgroup_var: variable for layout='subgroup'
    """
    domain: str
    table_number: str
    endpoint_label: str
    analysis_set: str = "EFF"
    paramcd: str | None = None
    layout: str = "continuous"
    shell_id: str = "generic_continuous"
    subgroup_var: str | None = None
    show_chg: bool = True
    extra_footnotes: list[str] = field(default_factory=list)


def generate_generic(
    req: GenericTableRequest,
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    shell = registry.shell(req.shell_id)
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    domains = load_domains(cfg, ["adsl", req.domain])
    adsl_raw = domains["adsl"]
    df = domains[req.domain]
    if "ANL01FL" in df.columns:
        df = df.filter(pl.col("ANL01FL") == "Y")
    df = filter_to_set(df, cfg, req.analysis_set)
    if req.paramcd:
        df = df.filter(pl.col("PARAMCD") == req.paramcd)

    denoms = column_denominators(cfg, columns, adsl=adsl_raw, analysis_set=req.analysis_set)
    headers, n_labels = build_column_headers(
        cfg, columns, denoms,
        label_header="Parameter (Unit)\n  Visit\n    Statistic",
    )

    arms = [int(c["trtpn"]) for c in columns if not c.get("is_total")]
    body_rows: list[list[str]] = []

    if req.layout == "subgroup" and req.subgroup_var:
        # One block per subgroup level; each block is its own AVAL summary.
        levels = sorted(df.select(req.subgroup_var).drop_nulls().unique().to_series().to_list())
        for lvl in levels:
            body_rows.append([f"Subgroup: {lvl}", *[""] * len(columns)])
            body_rows.extend(
                _continuous_block(df.filter(pl.col(req.subgroup_var) == lvl), columns, arms)
            )
    elif req.layout == "categorical":
        body_rows.extend(_categorical_block(df, columns, denoms, arms))
    else:
        body_rows.extend(_continuous_block(df, columns, arms))

    title2 = shell["title_line2"].replace("{{ endpoint }}", req.endpoint_label)
    title3 = shell["title_line3"].replace(
        "{{ analysis_set_label }}",
        cfg.analysis_sets[req.analysis_set].label,
    )
    footnotes = render_footnotes(
        list(shell.get("footnotes", [])) + list(req.extra_footnotes),
        context=cfg.footnote_context(),
    )

    spec = TableSpec(
        shell_id=req.shell_id,
        title=(shell["title_line1"], title2, title3),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows or [["No participant meeting the selection criteria", *[""] * len(columns)]],
        footnotes=footnotes,
    )
    path = resolve_output_path(cfg, req.table_number, out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


# ---------------------------------------------------------------------------
# Block builders
# ---------------------------------------------------------------------------

def _continuous_block(
    df: pl.DataFrame,
    columns: list[dict],
    arms: list[int],
) -> list[list[str]]:
    rows: list[list[str]] = []
    params = sorted(df.select("PARAM").drop_nulls().unique().to_series().to_list())
    for param in params:
        rows.append([param, *[""] * len(columns)])
        sub_p = df.filter(pl.col("PARAM") == param)
        all_vals = sub_p.select("AVAL").drop_nulls().to_series().to_list()
        raw_dp = raw_decimal_places(all_vals)
        visits = (
            sub_p.select(["AVISIT", "AVISITN"]).drop_nulls().unique()
                 .sort("AVISITN").select("AVISIT").to_series().to_list()
        )
        for visit in visits:
            rows.append([f"  {visit}", *[""] * len(columns)])
            sub_v = sub_p.filter(pl.col("AVISIT") == visit)
            summary = continuous_summary(sub_v, value_col="AVAL", arm_col="TRTPN", arms=arms)
            total_stats = _stats_from_series(sub_v.select("AVAL").drop_nulls().to_series()) if any(c.get("is_total") for c in columns) else None
            rows.extend(
                continuous_summary_rows(
                    columns=columns,
                    stats_per_arm=summary.stats,
                    raw_dp=raw_dp,
                    total_stats=total_stats,
                    label_indent="    ",
                )
            )
    return rows


def _categorical_block(
    df: pl.DataFrame,
    columns: list[dict],
    denoms: dict[int | str, int],
    arms: list[int],
) -> list[list[str]]:
    rows: list[list[str]] = []
    arm_denoms = {a: denoms.get(a, 0) for a in arms}
    params = sorted(df.select("PARAM").drop_nulls().unique().to_series().to_list())
    for param in params:
        rows.append([param, *[""] * len(columns)])
        sub_p = df.filter(pl.col("PARAM") == param)
        visits = (
            sub_p.select(["AVISIT", "AVISITN"]).drop_nulls().unique()
                 .sort("AVISITN").select("AVISIT").to_series().to_list()
        )
        for visit in visits:
            rows.append([f"   {visit}", *[""] * len(columns)])
            sub_v = sub_p.filter(pl.col("AVISIT") == visit)
            # Bucket AVAL into discrete categories using AVAL itself (numeric
            # CRF categories) — the caller can preprocess to a string category
            # if integer codes need labels.
            summary = categorical_summary(
                sub_v, var="AVAL", arm_col="TRTPN", arms=arms,
                denominators=arm_denoms,
            )
            for cat, by_arm in summary.counts.items():
                cells = []
                for col in columns:
                    if col.get("is_total"):
                        n = sum(by_arm.get(a, 0) for a in arms)
                        cells.append(format_n_pct(n, denoms.get("TOTAL")))
                    else:
                        arm = int(col["trtpn"])
                        cells.append(format_n_pct(by_arm.get(arm, 0), arm_denoms.get(arm, 0)))
                rows.append([f"      {cat}", *cells])
    return rows
