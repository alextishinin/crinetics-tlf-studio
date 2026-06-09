"""Generate the adverse-event table family.

This file creates the 14.3.1.x safety tables from ADSL and ADAE. It covers
the AE overview, system-organ-class by preferred-term tables, preferred
term only tables, common AE tables, adverse events of special interest,
maximum severity summaries, and relationship-to-treatment summaries.

The module applies shell-driven AE filters, counts unique subjects with
events, optionally counts total event occurrences, formats treatment cells,
and sorts AE rows by the table rules so the most frequent events appear
first.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from tlf.aggregator import (
    ae_incidence,
    ae_occurrence_count,
    ae_relationship_max,
    ae_severity_max,
    _apply_ae_filter,
)
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
from tlf.validator import format_n_pct, format_n_pct_m


# Map shell id -> output table number.
_NUMBER_BY_ID = {
    "t_14_3_1_1": "14.3.1.1",
    "t_14_3_1_2": "14.3.1.2",
    "t_14_3_1_5": "14.3.1.5",
    "t_14_3_1_6": "14.3.1.6",
    "t_14_3_1_7": "14.3.1.7",
    "t_14_3_1_8": "14.3.1.8",
    "t_14_3_1_9": "14.3.1.9",
    "t_14_3_1_10": "14.3.1.10",
    "t_14_3_1_11_common": "14.3.1.11_common",
    "t_14_3_1_11_aesi": "14.3.1.11_aesi",
    "t_14_3_1_12": "14.3.1.12",
    "t_14_3_1_13": "14.3.1.13",
    "t_14_3_1_14": "14.3.1.14",
}


def generate_overview(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Table 14.3.1.1 — Overview of TEAEs."""
    shell = registry.shell("t_14_3_1_1")
    return _render_overview(shell, cfg, registry, out_dir, run_dt)


def generate_soc_pt(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    shell_id: str = "t_14_3_1_2",
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """SOC × PT incidence table. Used by 14.3.1.2 / .5 / .6 / .7 / .8."""
    shell = registry.shell(shell_id)
    return _render_soc_pt(shell, cfg, registry, out_dir, run_dt)


def generate_pt_only(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    shell_id: str = "t_14_3_1_9",
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """PT-only incidence (14.3.1.9 / .10 / .11_common)."""
    shell = registry.shell(shell_id)
    return _render_pt_only(shell, cfg, registry, out_dir, run_dt)


def generate_aesi(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    shell_id: str = "t_14_3_1_11_aesi",
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """AESI category × PT table (14.3.1.11_aesi / 14.3.1.12)."""
    shell = registry.shell(shell_id)
    return _render_aesi(shell, cfg, registry, out_dir, run_dt)


def generate_severity(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Table 14.3.1.13 — TEAEs by SOC × PT × Maximum Severity."""
    shell = registry.shell("t_14_3_1_13")
    return _render_severity_or_causality(shell, cfg, registry, out_dir, run_dt, mode="severity")


def generate_causality(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Table 14.3.1.14 — TEAEs by SOC × PT × Strongest Relationship."""
    shell = registry.shell("t_14_3_1_14")
    return _render_severity_or_causality(shell, cfg, registry, out_dir, run_dt, mode="causality")


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _load(cfg: StudyConfig, shell: dict) -> tuple[pl.DataFrame, pl.DataFrame]:
    domains = load_domains(cfg, ["adsl", "adae"])
    return domains["adsl"], domains["adae"]


def _ae_arms(cfg: StudyConfig, columns: list[dict]) -> list[int]:
    return [int(c["trtpn"]) for c in columns if not c.get("is_total")]


def _ae_denoms(
    cfg: StudyConfig,
    columns: list[dict],
    adsl_raw: pl.DataFrame,
    analysis_set: str,
) -> dict[int | str, int]:
    return column_denominators(cfg, columns, adsl=adsl_raw, analysis_set=analysis_set)


def _format_cells(
    counts_by_arm: dict[int, int],
    columns: list[dict],
    denominators: dict[int | str, int],
    *,
    show_occurrences: bool,
    occ_by_arm: dict[int, int] | None = None,
) -> list[str]:
    cells = []
    arms_trtpn = [c for c in columns if not c.get("is_total")]
    for col in columns:
        if col.get("is_total"):
            n = sum(counts_by_arm.get(int(c["trtpn"]), 0) for c in arms_trtpn)
            if show_occurrences and occ_by_arm is not None:
                m = sum(occ_by_arm.get(int(c["trtpn"]), 0) for c in arms_trtpn)
                cells.append(format_n_pct_m(n, denominators.get("TOTAL"), m))
            else:
                cells.append(format_n_pct(n, denominators.get("TOTAL")))
        else:
            arm = int(col["trtpn"])
            n = counts_by_arm.get(arm, 0)
            if show_occurrences and occ_by_arm is not None:
                cells.append(format_n_pct_m(n, denominators.get(arm), occ_by_arm.get(arm, 0)))
            else:
                cells.append(format_n_pct(n, denominators.get(arm)))
    return cells


def _render_overview(
    shell: dict,
    cfg: StudyConfig,
    registry: ShellRegistry,
    out_dir: Path | None,
    run_dt: datetime | None,
) -> Path:
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl_raw, adae = _load(cfg, shell)
    arms = _ae_arms(cfg, columns)
    denoms = _ae_denoms(cfg, columns, adsl_raw, shell["analysis_set"])
    arm_denoms = {a: denoms.get(a, 0) for a in arms}
    headers, n_labels = build_column_headers(cfg, columns, denoms, label_header="")

    show_occ = bool(shell.get("show_occurrences"))
    body_rows: list[list[str]] = []
    for entry in shell["row_schema"]:
        label = entry["label"]
        filt = entry.get("filter", {}) or {}
        inc = ae_incidence(adae, arm_col="TRTAN", arms=arms, denominators=arm_denoms, filt=filt)
        counts_by_arm = inc.counts["Any"]
        if show_occ:
            occ = ae_occurrence_count(adae, arm_col="TRTAN", arms=arms, filt=filt)
            cells = _format_cells(
                counts_by_arm, columns, denoms,
                show_occurrences=True, occ_by_arm=occ["Any"],
            )
        else:
            cells = _format_cells(counts_by_arm, columns, denoms, show_occurrences=False)
        body_rows.append([label, *cells])

    if cfg.shell_mode:
        body_rows = shell_layouts.ae_overview(columns)
    footnotes = render_footnotes(shell.get("footnotes", []), context=cfg.footnote_context())
    spec = TableSpec(
        shell_id=shell["id"],
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
    )
    path = resolve_output_path(cfg, _NUMBER_BY_ID[shell["id"]], out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def _render_soc_pt(
    shell: dict,
    cfg: StudyConfig,
    registry: ShellRegistry,
    out_dir: Path | None,
    run_dt: datetime | None,
) -> Path:
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl_raw, adae = _load(cfg, shell)
    arms = _ae_arms(cfg, columns)
    denoms = _ae_denoms(cfg, columns, adsl_raw, shell["analysis_set"])
    arm_denoms = {a: denoms.get(a, 0) for a in arms}
    # Issue 2: single-cell label header (no embedded newline)
    headers, n_labels = build_column_headers(
        cfg, columns, denoms, label_header="System Organ Class / Preferred Term",
    )

    base_filter = shell.get("base_filter", {"TRTEMFL": "Y"})
    show_occ = bool(shell.get("show_occurrences"))
    sub = _apply_ae_filter(adae, base_filter)

    body_rows: list[list[str]] = []

    # "Subjects with at Least One ..." row from the schema header
    header_label = next(
        (r["label"] for r in shell["row_schema"] if "Subjects with" in r.get("label", "")),
        "Subjects with at Least One Treatment-Emergent Adverse Event",
    )
    any_inc = ae_incidence(adae, arm_col="TRTAN", arms=arms, denominators=arm_denoms, filt=base_filter)
    any_counts = any_inc.counts["Any"]
    if show_occ:
        any_occ = ae_occurrence_count(adae, arm_col="TRTAN", arms=arms, filt=base_filter)["Any"]
        body_rows.append([header_label, *_format_cells(any_counts, columns, denoms, show_occurrences=True, occ_by_arm=any_occ)])
    else:
        body_rows.append([header_label, *_format_cells(any_counts, columns, denoms, show_occurrences=False)])

    if sub.is_empty():
        return _finalize(
            body_rows, shell, columns, headers, n_labels, cfg, out_dir, run_dt,
            shell_layout=shell_layouts.ae_soc_pt,
        )

    # SOC-level rows
    soc_inc = ae_incidence(adae, arm_col="TRTAN", arms=arms, denominators=arm_denoms, filt=base_filter, group_by="AEBODSYS")
    soc_occ = ae_occurrence_count(adae, arm_col="TRTAN", arms=arms, filt=base_filter, group_by="AEBODSYS") if show_occ else None

    soc_total_for_sort = {
        soc: sum(soc_inc.counts[soc].get(a, 0) for a in arms)
        for soc in soc_inc.counts
    }
    socs_sorted = _sorted_groups(soc_inc.counts, arms, soc_total_for_sort)

    # For each SOC, also compute PT-level
    pt_inc = ae_incidence(adae, arm_col="TRTAN", arms=arms, denominators=arm_denoms, filt=base_filter, group_by="AEDECOD")
    pt_occ = ae_occurrence_count(adae, arm_col="TRTAN", arms=arms, filt=base_filter, group_by="AEDECOD") if show_occ else None

    # Map PT -> SOC for grouping (a PT can belong to only one SOC in MedDRA)
    pt_to_soc = (
        sub.with_columns([
            pl.col("AEDECOD").fill_null("UNCODED"),
            pl.col("AEBODSYS").fill_null("UNCODED"),
        ])
        .select(["AEDECOD", "AEBODSYS"])
        .unique()
        .to_dict(as_series=False)
    )
    pt_soc_map: dict[str, str] = dict(zip(pt_to_soc["AEDECOD"], pt_to_soc["AEBODSYS"]))

    for soc in socs_sorted:
        soc_counts = soc_inc.counts[soc]
        soc_cells = _format_cells(
            soc_counts, columns, denoms,
            show_occurrences=show_occ,
            occ_by_arm=(soc_occ[soc] if soc_occ else None),
        )
        body_rows.append([soc, *soc_cells])

        # PTs in this SOC, sorted by total descending
        pts_in_soc = [pt for pt, s in pt_soc_map.items() if s == soc]
        pt_total = {pt: sum(pt_inc.counts.get(pt, {}).get(a, 0) for a in arms) for pt in pts_in_soc}
        for pt in _sorted_groups(pt_inc.counts, arms, pt_total, restrict=pts_in_soc):
            if pt_total[pt] == 0:
                continue
            pt_counts = pt_inc.counts[pt]
            pt_cells = _format_cells(
                pt_counts, columns, denoms,
                show_occurrences=show_occ,
                occ_by_arm=(pt_occ[pt] if pt_occ else None),
            )
            body_rows.append([f"   {pt}", *pt_cells])

    return _finalize(
        body_rows, shell, columns, headers, n_labels, cfg, out_dir, run_dt,
        shell_layout=shell_layouts.ae_soc_pt,
    )


def _render_pt_only(
    shell: dict,
    cfg: StudyConfig,
    registry: ShellRegistry,
    out_dir: Path | None,
    run_dt: datetime | None,
) -> Path:
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl_raw, adae = _load(cfg, shell)
    arms = _ae_arms(cfg, columns)
    denoms = _ae_denoms(cfg, columns, adsl_raw, shell["analysis_set"])
    arm_denoms = {a: denoms.get(a, 0) for a in arms}
    headers, n_labels = build_column_headers(cfg, columns, denoms, label_header="Preferred Term")

    base_filter = shell.get("base_filter", {"TRTEMFL": "Y"})
    show_occ = bool(shell.get("show_occurrences"))

    body_rows: list[list[str]] = []
    any_inc = ae_incidence(adae, arm_col="TRTAN", arms=arms, denominators=arm_denoms, filt=base_filter)
    any_counts = any_inc.counts["Any"]
    any_occ = ae_occurrence_count(adae, arm_col="TRTAN", arms=arms, filt=base_filter)["Any"] if show_occ else None
    header_label = next(
        (r["label"] for r in shell["row_schema"] if "Subjects with" in r.get("label", "")),
        "Subjects with at Least One Treatment-Emergent Adverse Event",
    )
    body_rows.append([header_label, *_format_cells(any_counts, columns, denoms, show_occurrences=show_occ, occ_by_arm=any_occ)])

    pt_inc = ae_incidence(adae, arm_col="TRTAN", arms=arms, denominators=arm_denoms, filt=base_filter, group_by="AEDECOD")
    pt_occ = ae_occurrence_count(adae, arm_col="TRTAN", arms=arms, filt=base_filter, group_by="AEDECOD") if show_occ else None

    pt_total = {pt: sum(pt_inc.counts[pt].get(a, 0) for a in arms) for pt in pt_inc.counts}

    # Frequency-cutoff filter for the "common AEs" table
    cutoff_pct = _frequency_cutoff(shell, cfg)
    keep_pts: set[str] | None = None
    if cutoff_pct is not None:
        keep_pts = set()
        for pt, by_arm in pt_inc.counts.items():
            for arm in arms:
                d = arm_denoms.get(arm, 0) or 0
                if d == 0:
                    continue
                if 100.0 * by_arm.get(arm, 0) / d >= cutoff_pct:
                    keep_pts.add(pt)
                    break

    for pt in _sorted_groups(pt_inc.counts, arms, pt_total):
        if pt_total[pt] == 0:
            continue
        if keep_pts is not None and pt not in keep_pts:
            continue
        cells = _format_cells(
            pt_inc.counts[pt], columns, denoms,
            show_occurrences=show_occ,
            occ_by_arm=(pt_occ[pt] if pt_occ else None),
        )
        body_rows.append([pt, *cells])

    return _finalize(
        body_rows, shell, columns, headers, n_labels, cfg, out_dir, run_dt,
        shell_layout=shell_layouts.ae_pt_only,
    )


def _render_aesi(
    shell: dict,
    cfg: StudyConfig,
    registry: ShellRegistry,
    out_dir: Path | None,
    run_dt: datetime | None,
) -> Path:
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl_raw, adae = _load(cfg, shell)
    arms = _ae_arms(cfg, columns)
    denoms = _ae_denoms(cfg, columns, adsl_raw, shell["analysis_set"])
    arm_denoms = {a: denoms.get(a, 0) for a in arms}
    # Issue 2: single-cell label header
    headers, n_labels = build_column_headers(
        cfg, columns, denoms, label_header="AE of Special Interest Category / Preferred Term",
    )

    base_filter = shell.get("base_filter", {"TRTEMFL": "Y", "CQ01NAM_not_null": True})
    show_occ = bool(shell.get("show_occurrences"))

    cat_inc = ae_incidence(adae, arm_col="TRTAN", arms=arms, denominators=arm_denoms, filt=base_filter, group_by="CQ01NAM")
    cat_occ = ae_occurrence_count(adae, arm_col="TRTAN", arms=arms, filt=base_filter, group_by="CQ01NAM") if show_occ else None

    pt_inc = ae_incidence(adae, arm_col="TRTAN", arms=arms, denominators=arm_denoms, filt=base_filter, group_by="AEDECOD")
    pt_occ = ae_occurrence_count(adae, arm_col="TRTAN", arms=arms, filt=base_filter, group_by="AEDECOD") if show_occ else None

    pt_to_cat_raw = (
        _apply_ae_filter(adae, base_filter)
        .select(["AEDECOD", "CQ01NAM"])
        .drop_nulls()
        .unique()
        .to_dict(as_series=False)
    )
    pt_cat_map: dict[str, str] = dict(zip(pt_to_cat_raw["AEDECOD"], pt_to_cat_raw["CQ01NAM"]))

    body_rows: list[list[str]] = []
    cat_total = {c: sum(cat_inc.counts[c].get(a, 0) for a in arms) for c in cat_inc.counts}
    for cat in _sorted_groups(cat_inc.counts, arms, cat_total):
        if cat_total[cat] == 0:
            continue
        cat_cells = _format_cells(
            cat_inc.counts[cat], columns, denoms,
            show_occurrences=show_occ,
            occ_by_arm=(cat_occ[cat] if cat_occ else None),
        )
        body_rows.append([cat, *cat_cells])

        pts_in_cat = [pt for pt, c in pt_cat_map.items() if c == cat]
        pt_total = {pt: sum(pt_inc.counts.get(pt, {}).get(a, 0) for a in arms) for pt in pts_in_cat}
        for pt in _sorted_groups(pt_inc.counts, arms, pt_total, restrict=pts_in_cat):
            if pt_total[pt] == 0:
                continue
            cells = _format_cells(
                pt_inc.counts[pt], columns, denoms,
                show_occurrences=show_occ,
                occ_by_arm=(pt_occ[pt] if pt_occ else None),
            )
            body_rows.append([f"   {pt}", *cells])

    return _finalize(
        body_rows, shell, columns, headers, n_labels, cfg, out_dir, run_dt,
        shell_layout=shell_layouts.ae_aesi,
    )


def _render_severity_or_causality(
    shell: dict,
    cfg: StudyConfig,
    registry: ShellRegistry,
    out_dir: Path | None,
    run_dt: datetime | None,
    *,
    mode: str,
) -> Path:
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl_raw, adae = _load(cfg, shell)
    arms = _ae_arms(cfg, columns)
    denoms = _ae_denoms(cfg, columns, adsl_raw, shell["analysis_set"])
    arm_denoms = {a: denoms.get(a, 0) for a in arms}
    # Issue 2: single-cell label header
    headers, n_labels = build_column_headers(
        cfg, columns, denoms, label_header="System Organ Class / Preferred Term",
    )

    base_filter = shell.get("base_filter", {"TRTEMFL": "Y"})
    sub = _apply_ae_filter(adae, base_filter)

    if mode == "severity":
        worst = ae_severity_max(sub)
        bucket_col = "AESEV"
        # Issue 5 (audit): render Grades in ascending order Grade 1..5 with
        # Grade 4/Grade 5 always present (zero rows when no data).
        labels = shell.get(
            "severity_labels",
            {"MILD": "Grade 1", "MODERATE": "Grade 2", "SEVERE": "Grade 3"},
        )
        grade_order = shell.get(
            "severity_grade_order",
            ["Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"],
        )
        # Map each display grade label back to the AESEV value that feeds it
        # (or None when the grade has no source values in this study).
        label_to_aesev = {v: k for k, v in labels.items()}
        levels = tuple((g, label_to_aesev.get(g)) for g in grade_order)
    else:
        worst = ae_relationship_max(sub)
        # Group the four collected levels into Related / Unrelated bands per shell
        rel_labels = shell.get("relationship_labels", {})
        worst = worst.with_columns(
            pl.col("AEREL").replace_strict(
                rel_labels, default="Unrelated"
            ).alias("AEREL_GROUPED")
        )
        bucket_col = "AEREL_GROUPED"
        # Tuple form matches the severity branch: (display_label, source_value)
        levels = (("Related", "Related"), ("Unrelated", "Unrelated"))
        labels = {"Related": "Related", "Unrelated": "Unrelated"}

    body_rows: list[list[str]] = []

    # Subjects with at least one TEAE (any bucket)
    any_inc = ae_incidence(adae, arm_col="TRTAN", arms=arms, denominators=arm_denoms, filt=base_filter)
    body_rows.append([
        "Subjects with at Least One Treatment-Emergent Adverse Event",
        *_format_cells(any_inc.counts["Any"], columns, denoms, show_occurrences=False),
    ])
    for display_label, src in levels:
        if src is None:
            counts = {a: 0 for a in arms}
        else:
            bucket_sub = worst.filter(pl.col(bucket_col) == src)
            counts = _counts_per_arm(bucket_sub, arms)
        body_rows.append([f"      {display_label}", *_format_cells(counts, columns, denoms, show_occurrences=False)])

    # Per SOC, per PT
    socs = sorted(worst.select("AEBODSYS").drop_nulls().unique().to_series().to_list())
    soc_total = {soc: worst.filter(pl.col("AEBODSYS") == soc).select("USUBJID").n_unique() for soc in socs}
    for soc in sorted(socs, key=lambda s: (-soc_total[s], s)):
        if soc_total[soc] == 0:
            continue
        soc_worst = worst.filter(pl.col("AEBODSYS") == soc).unique(subset=["USUBJID", "TRTAN"])
        body_rows.append([soc, *_format_cells(_counts_per_arm(soc_worst, arms), columns, denoms, show_occurrences=False)])
        for display_label, src in levels:
            if src is None:
                counts = {a: 0 for a in arms}
            else:
                counts = _counts_per_arm(
                    worst.filter((pl.col("AEBODSYS") == soc) & (pl.col(bucket_col) == src))
                         .unique(subset=["USUBJID", "TRTAN"]),
                    arms,
                )
            body_rows.append([f"      {display_label}", *_format_cells(counts, columns, denoms, show_occurrences=False)])

        pts = sorted(
            worst.filter(pl.col("AEBODSYS") == soc)
                 .select("AEDECOD").drop_nulls().unique().to_series().to_list()
        )
        pt_total = {
            pt: worst.filter((pl.col("AEBODSYS") == soc) & (pl.col("AEDECOD") == pt))
                     .select("USUBJID").n_unique()
            for pt in pts
        }
        first_pt = True
        for pt in sorted(pts, key=lambda p: (-pt_total[p], p)):
            if pt_total[pt] == 0:
                continue
            if not first_pt:
                body_rows.append(["", *[""] * len(columns)])
            first_pt = False
            body_rows.append([
                f"   {pt}",
                *_format_cells(
                    _counts_per_arm(
                        worst.filter(pl.col("AEDECOD") == pt).unique(subset=["USUBJID", "TRTAN"]),
                        arms,
                    ),
                    columns, denoms, show_occurrences=False,
                ),
            ])
            for display_label, src in levels:
                if src is None:
                    counts = {a: 0 for a in arms}
                else:
                    counts = _counts_per_arm(
                        worst.filter((pl.col("AEDECOD") == pt) & (pl.col(bucket_col) == src))
                             .unique(subset=["USUBJID", "TRTAN"]),
                        arms,
                    )
                body_rows.append([
                    f"      {display_label}",
                    *_format_cells(counts, columns, denoms, show_occurrences=False),
                ])

    shell_layout_fn = shell_layouts.ae_severity if mode == "severity" else shell_layouts.ae_causality
    return _finalize(
        body_rows, shell, columns, headers, n_labels, cfg, out_dir, run_dt,
        shell_layout=shell_layout_fn,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _counts_per_arm(df: pl.DataFrame, arms: list[int]) -> dict[int, int]:
    if df.is_empty():
        return {a: 0 for a in arms}
    agg = (
        df.select(["USUBJID", "TRTAN"])
        .unique()
        .group_by("TRTAN")
        .agg(pl.len().alias("n"))
    )
    out = {a: 0 for a in arms}
    for row in agg.iter_rows(named=True):
        arm = int(row["TRTAN"])
        if arm in out:
            out[arm] = int(row["n"])
    return out


def _sorted_groups(
    counts: dict[str, dict[int, int]],
    arms: list[int],
    total_map: dict[str, int],
    *,
    restrict: list[str] | None = None,
) -> list[str]:
    """Sort group keys by descending Total then Low → High → Placebo within
    ties (using the SAP order: 54, 81, 0)."""
    keys = list(counts.keys()) if restrict is None else [k for k in counts if k in restrict]
    arm_order = [54, 81, 0]
    def key(g: str):
        return (
            g == "UNCODED",  # UNCODED always last
            -total_map.get(g, 0),
            *(-counts.get(g, {}).get(a, 0) for a in arm_order if a in arms),
            g,
        )
    return sorted(keys, key=key)


def _frequency_cutoff(shell: dict, cfg: StudyConfig) -> float | None:
    for row in shell.get("row_schema", []):
        if "frequency_cutoff_pct" in row:
            raw = row["frequency_cutoff_pct"]
            if isinstance(raw, str):
                # Resolve any {{ template }} via the config context
                from tlf.footnotes import render
                raw = render(raw, cfg.footnote_context())
            try:
                return float(raw)
            except (TypeError, ValueError):
                return None
    return None


def _finalize(
    body_rows: list[list[str]],
    shell: dict,
    columns: list[dict[str, Any]],
    headers: list[str],
    n_labels: list[str],
    cfg: StudyConfig,
    out_dir: Path | None,
    run_dt: datetime | None,
    *,
    shell_layout=None,
) -> Path:
    if cfg.shell_mode and shell_layout is not None:
        body_rows = shell_layout(columns)
    if not body_rows:
        # Renderer requires at least one body row.
        body_rows = [["No participant meeting the selection criteria", *[""] * (len(columns))]]
    footnotes = render_footnotes(shell.get("footnotes", []), context=cfg.footnote_context())
    spec = TableSpec(
        shell_id=shell["id"],
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
    )
    path = resolve_output_path(cfg, _NUMBER_BY_ID[shell["id"]], out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)
