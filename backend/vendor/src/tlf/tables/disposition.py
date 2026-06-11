"""Generate the subject disposition table.

This file builds Table 14.1.1.1 from ADSL. It counts randomized subjects,
analysis-set membership, treatment completion, ongoing treatment, early
treatment discontinuation, discontinuation reasons, study completion,
ongoing study participation, and early study discontinuation.

Some rows are direct flag counts, while others are derived from a
combination of completion flags, discontinuation flags, and disposition
reason values.
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


SHELL_ID = "t_14_1_1_1"
TABLE_NUMBER = "14.1.1.1"
RANDOMIZATION_SHELL_ID = "t_14_1_1_2"
RANDOMIZATION_TABLE_NUMBER = "14.1.1.2"
ANALYSIS_SETS_SHELL_ID = "t_14_1_1_3"
ANALYSIS_SETS_TABLE_NUMBER = "14.1.1.3"


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
    adsl = domains["adsl"]

    # Denominators: randomised population = all of ADSL (no SAF filter
    # because everyone in the sample data is randomised).
    denominators = column_denominators(cfg, columns, adsl=adsl, analysis_set="ALL")
    headers, n_labels = build_column_headers(cfg, columns, denominators, label_header="")

    if cfg.shell_mode:
        body_rows = shell_layouts.disposition(columns)
    else:
        body_rows = _real_data_rows(adsl, columns, denominators, cfg)

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
        source_lines=[],
        bold_row_labels=[],
    )

    path = resolve_output_path(cfg, TABLE_NUMBER, out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def generate_randomization_by_country(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    shell = registry.shell(RANDOMIZATION_SHELL_ID)
    columns = resolve_columns(cfg, registry, shell["column_layout"])

    domains = load_domains(cfg, shell["adam_domains"])
    adsl = domains["adsl"]

    denominators = column_denominators(cfg, columns, adsl=adsl, analysis_set="ALL")
    headers, n_labels = build_column_headers(cfg, columns, denominators, label_header="")

    if cfg.shell_mode:
        body_rows = shell_layouts.randomization_by_country(columns)
    else:
        body_rows = _randomization_by_country_rows(adsl, columns, denominators)

    footnotes = render_footnotes(
        shell.get("footnotes", []),
        context=cfg.footnote_context(),
    )

    spec = TableSpec(
        shell_id=RANDOMIZATION_SHELL_ID,
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
        source_lines=[],
        bold_row_labels=[],
    )

    path = resolve_output_path(cfg, RANDOMIZATION_TABLE_NUMBER, out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def generate_analysis_sets(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Table 14.1.1.3 — Analysis Set membership / exclusion counts from ADSL."""
    shell = registry.shell(ANALYSIS_SETS_SHELL_ID)
    columns = resolve_columns(cfg, registry, shell["column_layout"])
    adsl = load_domains(cfg, shell["adam_domains"])["adsl"]
    denominators = column_denominators(cfg, columns, adsl=adsl, analysis_set="ALL")
    headers, n_labels = build_column_headers(cfg, columns, denominators, label_header="")

    if cfg.shell_mode:
        body_rows = shell_layouts.analysis_sets(columns)
    else:
        body_rows = [
            _row("Safety Analysis Set (SAF)",
                 _n_pct_by_flag(adsl, "SAFFL", "Y", columns, denominators)),
            _row("Not Included in the SAF",
                 _n_pct_by_derived(adsl, lambda df: _not_flag(df, "SAFFL"), columns, denominators)),
            _row("Intent-To-Treat Set (ITT)",
                 _n_pct_by_flag(adsl, "ITTFL", "Y", columns, denominators)),
            _row("Not Included in the ITT",
                 _n_pct_by_derived(adsl, lambda df: _not_flag(df, "ITTFL"), columns, denominators)),
        ]

    footnotes = render_footnotes(shell.get("footnotes", []), context=cfg.footnote_context())
    spec = TableSpec(
        shell_id=ANALYSIS_SETS_SHELL_ID,
        title=(shell["title_line1"], shell["title_line2"], shell["title_line3"]),
        column_headers=headers,
        arm_n_labels=n_labels,
        body_rows=body_rows,
        footnotes=footnotes,
    )
    path = resolve_output_path(cfg, ANALYSIS_SETS_TABLE_NUMBER, out_dir=out_dir, run_dt=run_dt)
    return render_table(spec, cfg=cfg, output_path=path, run_dt=run_dt)


def _not_flag(df: pl.DataFrame, var: str) -> pl.DataFrame:
    """Subjects NOT in a flagged set: flag missing or anything other than 'Y'."""
    return df.filter(pl.col(var).fill_null("") != "Y")


# ---------------------------------------------------------------------------
# Body assembly: shell-template layout vs real-data layout
# ---------------------------------------------------------------------------

def _real_data_rows(
    adsl: pl.DataFrame,
    columns: list[dict],
    denominators: dict[int | str, int],
    cfg: StudyConfig | None = None,
) -> list[list[str]]:
    """Original real-data layout (analysis sets, treatment completion, study
    completion).  Unchanged from before shell-mode landed."""
    crf_order = cfg.crf_category_order("DCDECOD") if cfg is not None else None
    rows: list[list[str]] = []
    n_total_cols = len(columns) + 1
    blank_row = [""] * n_total_cols

    rows.append(_row(
        label="Randomized Population [1]",
        cells=_count_only(adsl, columns, denominators),
    ))
    rows.append(_row(
        label="Intent-To-Treat Set",
        cells=_n_pct_by_flag(adsl, "ITTFL", "Y", columns, denominators),
    ))
    rows.append(_row(
        label="Safety Analysis Set",
        cells=_n_pct_by_flag(adsl, "SAFFL", "Y", columns, denominators),
    ))
    rows.append(list(blank_row))

    rows.append(_row(
        label="Completed Study Treatment",
        cells=_n_pct_by_derived(adsl, _completed_treatment_mask, columns, denominators),
    ))
    rows.append(_row(
        label="Ongoing Treatment",
        cells=_n_pct_by_derived(adsl, _ongoing_treatment_mask, columns, denominators),
    ))
    rows.append(_row(
        label="Early Discontinuation from Study Treatment",
        cells=_n_pct_by_flag(adsl, "DSRAEFL", "Y", columns, denominators),
    ))
    for reason, raw_reason in _disc_reasons(adsl, order=crf_order):
        rows.append(_row(
            label=f"   {reason}",
            cells=_n_pct_by_value(adsl, "DCDECOD", raw_reason, columns, denominators),
        ))

    rows.append(list(blank_row))
    rows.append(_row(
        label="Completed Study",
        cells=_n_pct_by_derived(adsl, _completed_study_mask, columns, denominators),
    ))
    rows.append(_row(
        label="Ongoing in the Study",
        cells=_n_pct_by_derived(adsl, _ongoing_study_mask, columns, denominators),
    ))
    rows.append(_row(
        label="Early Discontinuation from Study",
        cells=_n_pct_by_flag(adsl, "DISCONFL", "Y", columns, denominators),
    ))
    return rows


def _randomization_by_country_rows(
    adsl: pl.DataFrame,
    columns: list[dict],
    denominators: dict[int | str, int],
) -> list[list[str]]:
    df = _randomization_source(adsl)
    rows: list[list[str]] = []

    countries = (
        df.group_by("_COUNTRY")
        .agg(pl.len().alias("_n"))
        .to_dicts()
    )
    countries = sorted(countries, key=lambda row: (-int(row["_n"]), str(row["_COUNTRY"])))

    for country_idx, country_row in enumerate(countries):
        if country_idx:
            rows.append([""] * (len(columns) + 1))

        country = str(country_row["_COUNTRY"])
        rows.append(_row(country, [""] * len(columns)))

        country_df = df.filter(pl.col("_COUNTRY") == country)
        sites = (
            country_df.group_by("_SITEID")
            .agg(pl.len().alias("_n"))
            .to_dicts()
        )
        sites = sorted(sites, key=lambda row: (-int(row["_n"]), str(row["_SITEID"])))

        for site_idx, site_row in enumerate(sites, start=1):
            siteid = str(site_row["_SITEID"])
            site_df = country_df.filter(pl.col("_SITEID") == siteid)
            rows.append(_row(
                label=f"   Investigator {site_idx} ({siteid})",
                cells=_n_pct_for_subset(site_df, columns, denominators),
            ))

    if not rows:
        rows.append(_row("No randomized subjects", [""] * len(columns)))
    return rows


def _randomization_source(adsl: pl.DataFrame) -> pl.DataFrame:
    available = set(adsl.columns)
    country = _normalised_label_expr("COUNTRY", available, default="Country Not Collected")
    siteid = _normalised_label_expr("SITEID", available, default="Unknown")
    return adsl.with_columns([
        country.alias("_COUNTRY"),
        siteid.alias("_SITEID"),
    ])


def _normalised_label_expr(column: str, available: set[str], *, default: str) -> pl.Expr:
    if column not in available:
        return pl.lit(default)
    value = pl.col(column).cast(pl.Utf8).str.strip_chars()
    return pl.when(value.is_null() | (value == "")).then(pl.lit(default)).otherwise(value)


def _n_pct_for_subset(
    df: pl.DataFrame,
    columns: list[dict],
    denoms: dict[int | str, int],
) -> list[str]:
    cells = []
    for col in columns:
        if col.get("is_total"):
            cells.append(format_n_pct(df.height, denoms.get("TOTAL", 0)))
        else:
            trtpn = int(col["trtpn"])
            n = df.filter(pl.col("TRT01PN") == trtpn).height
            cells.append(format_n_pct(n, denoms.get(trtpn, 0)))
    return cells


# ---------------------------------------------------------------------------
# Cell builders
# ---------------------------------------------------------------------------

def _row(label: str, cells: list[str]) -> list[str]:
    return [label, *cells]


def _count_only(
    df: pl.DataFrame,
    columns: list[dict],
    denoms: dict[int | str, int],
) -> list[str]:
    cells = []
    for col in columns:
        if col.get("is_total"):
            cells.append(str(denoms.get("TOTAL", 0)))
        else:
            trtpn = int(col["trtpn"])
            cells.append(str(denoms.get(trtpn, 0)))
    return cells


def _n_pct_by_flag(
    df: pl.DataFrame,
    var: str,
    val: str,
    columns: list[dict],
    denoms: dict[int | str, int],
) -> list[str]:
    cells = []
    sub = df.filter(pl.col(var) == val)
    for col in columns:
        if col.get("is_total"):
            cells.append(format_n_pct(sub.height, denoms.get("TOTAL", 0)))
        else:
            trtpn = int(col["trtpn"])
            n = sub.filter(pl.col("TRT01PN") == trtpn).height
            cells.append(format_n_pct(n, denoms.get(trtpn, 0)))
    return cells


def _n_pct_by_value(
    df: pl.DataFrame,
    var: str,
    val: str,
    columns: list[dict],
    denoms: dict[int | str, int],
) -> list[str]:
    return _n_pct_by_flag(df, var, val, columns, denoms)


def _disc_reasons(
    adsl: pl.DataFrame, order: list[str] | None = None
) -> list[tuple[str, str]]:
    """Return (display_label, raw_value) pairs for discontinuation reasons.

    Issue 4 fix: raw DCDECOD values are CDISC uppercase (e.g. 'ADVERSE
    EVENT'); convert to title case for display while preserving the original
    value for data matching.  'COMPLETED' is excluded because it is not a
    discontinuation.

    When *order* is given (a human-reviewed CRF reason list, any case), the
    reasons are sorted to match that order; reasons present in the data but
    absent from the CRF list are appended alphabetically.
    """
    raw_reasons = (
        adsl.filter(pl.col("DCDECOD").is_not_null())
        .select("DCDECOD")
        .unique()
        .to_series()
        .to_list()
    )
    raw_reasons = [r for r in raw_reasons if r and r.upper() != "COMPLETED"]

    if order:
        rank = {str(v).upper(): i for i, v in enumerate(order)}
        raw_reasons.sort(
            key=lambda r: (rank.get(r.upper(), len(rank)), r.title())
        )
        return [(r.title(), r) for r in raw_reasons]

    return sorted((r.title(), r) for r in raw_reasons)


# ---------------------------------------------------------------------------
# Ongoing Treatment / Study masks (Issues 5 & 6)
# ---------------------------------------------------------------------------

def _completed_treatment_mask(adsl: pl.DataFrame) -> pl.DataFrame:
    """Subjects who completed study treatment.

    Uses the end-of-treatment status (EOTSTT='COMPLETED') when the study's
    ADSL carries it. CDISCPILOT01 has no EOTSTT/EOSSTT, so we fall back to
    COMP24FL (week-24 completion == treatment completion in that study).
    """
    if "EOTSTT" in adsl.columns:
        return adsl.filter(pl.col("EOTSTT").fill_null("").str.to_uppercase() == "COMPLETED")
    return adsl.filter(pl.col("COMP24FL").fill_null("") == "Y")


def _completed_study_mask(adsl: pl.DataFrame) -> pl.DataFrame:
    """Subjects who completed the study (distinct from treatment completion).

    Uses end-of-study status (EOSSTT='COMPLETED') when present; falls back to
    COMP24FL for studies like CDISCPILOT01 where the final visit (week 24)
    defines study completion.
    """
    if "EOSSTT" in adsl.columns:
        return adsl.filter(pl.col("EOSSTT").fill_null("").str.to_uppercase() == "COMPLETED")
    return adsl.filter(pl.col("COMP24FL").fill_null("") == "Y")


def _ongoing_treatment_mask(adsl: pl.DataFrame) -> pl.DataFrame:
    """Subjects still on treatment: neither completed nor early-discontinued."""
    comp = pl.col("COMP24FL").fill_null("") == "Y"
    disc = pl.col("DSRAEFL").fill_null("") == "Y"
    # Subjects with a non-completed DCDECOD have an explicit disc reason
    dcdecod_disc = (
        pl.col("DCDECOD").is_not_null()
        & (pl.col("DCDECOD").fill_null("") != "")
        & (pl.col("DCDECOD").str.to_uppercase() != "COMPLETED")
    )
    return adsl.filter(~comp & ~disc & ~dcdecod_disc)


def _ongoing_study_mask(adsl: pl.DataFrame) -> pl.DataFrame:
    """Subjects still participating in the study (not completed, not withdrawn)."""
    comp = pl.col("COMP24FL").fill_null("") == "Y"
    disc_study = pl.col("DISCONFL").fill_null("") == "Y"
    return adsl.filter(~comp & ~disc_study)


def _n_pct_by_derived(
    df: pl.DataFrame,
    mask_fn,
    columns: list[dict],
    denoms: dict[int | str, int],
) -> list[str]:
    sub = mask_fn(df)
    cells = []
    for col in columns:
        if col.get("is_total"):
            cells.append(format_n_pct(sub.height, denoms.get("TOTAL", 0)))
        else:
            trtpn = int(col["trtpn"])
            n = sub.filter(pl.col("TRT01PN") == trtpn).height
            cells.append(format_n_pct(n, denoms.get(trtpn, 0)))
    return cells
