"""Common helper functions used by the table-generation modules.

Most tables need the same setup work: load ADaM domains, decide which
treatment columns to show, compute denominators for each analysis set,
build column headers with N values, filter data to an analysis set, and
format the standard continuous-summary row block.

Keeping those operations here prevents each table module from rebuilding
the same column and denominator logic in slightly different ways.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from tlf.config import ShellRegistry, StudyConfig
from tlf.reader import read_adam


def load_domains(cfg: StudyConfig, names: list[str]) -> dict[str, pl.DataFrame]:
    """Eagerly collect a set of ADaM domains for the table module to use."""
    return {n: read_adam(n, cfg.adam_path).collect() for n in names}


def resolve_columns(
    cfg: StudyConfig,
    registry: ShellRegistry,
    layout_id: str,
) -> list[dict[str, Any]]:
    """Return the column-layout list derived from cfg.treatment_arms.

    Columns are always built from the study config so the automation works
    for any arm codes, not just the 54/81/0 codes used in the reference
    CDISCPILOT01 study.  The registry's column_layouts section is kept for
    documentation purposes but is no longer the source of truth.
    """
    cols: list[dict[str, Any]] = [
        {"id": f"arm_{arm.trtpn}", "trtpn": arm.trtpn, "n_source": "SAF", "show_n": True}
        for arm in cfg.treatment_arms
    ]
    if cfg.include_total_column:
        cols.append({"id": "total", "trtpn": None, "n_source": "SAF", "show_n": True, "is_total": True})
    return cols


def column_denominators(
    cfg: StudyConfig,
    columns: list[dict[str, Any]],
    *,
    adsl: pl.DataFrame,
    analysis_set: str,
) -> dict[int | str, int]:
    """Compute denominators per column. Keyed by trtpn for arms, and the
    sentinel 'TOTAL' for the Total column."""
    aset = cfg.analysis_sets[analysis_set]
    filtered = adsl if aset.flag_var is None else adsl.filter(
        pl.col(aset.flag_var) == aset.flag_val
    )
    denominators: dict[int | str, int] = {}
    for col in columns:
        if col.get("is_total"):
            denominators["TOTAL"] = filtered.height
            continue
        trtpn = int(col["trtpn"])
        denominators[trtpn] = filtered.filter(pl.col("TRT01PN") == trtpn).height
    return denominators


def build_column_headers(
    cfg: StudyConfig,
    columns: list[dict[str, Any]],
    denominators: dict[int | str, int],
    *,
    label_header: str = "",
    split_n_row: bool = True,
) -> tuple[list[str], list[str]]:
    """Return (column_headers, arm_n_labels) for the renderer.

    When *split_n_row* is True (default) the arm name and the N count are
    placed on separate rows: column_headers contains the arm names; arm_n_labels
    contains "(N=xx)".  The renderer then emits a two-row header band with the
    top rule on the name row and the bottom rule on the N row.  This keeps long
    arm labels (e.g. "Xanomeline Low Dose") on a single line and consistent
    across every column regardless of width.

    When *split_n_row* is False each treatment column header is a single
    combined cell "Treatment Name (N=xx)" and arm_n_labels is all-empty,
    producing a one-row header band.
    """
    # The renderer disables rtflite's text_convert in header cells (to keep
    # ">=" literal), which also disables rtflite's \n → \line mapping.  Emit
    # the RTF \line control word directly so an arm's configured line break
    # (e.g. "Xanomeline\nLow Dose") renders as a soft break inside the cell
    # instead of being collapsed to a space and word-wrapped by Word.
    def _wrap(name: str) -> str:
        return name.replace("\n", "\\line ")

    # Shell mode replaces every N count with the CRO shell placeholder "xx".
    def _n(value: int | None) -> str:
        if cfg.shell_mode:
            return "xx"
        return str(value if value is not None else 0)

    headers: list[str] = [label_header]
    n_labels: list[str] = [""]
    for col in columns:
        if col.get("is_total"):
            n = _n(denominators.get("TOTAL", 0))
            if split_n_row:
                headers.append("Total")
                n_labels.append(f"(N={n})")
            else:
                headers.append(f"Total (N={n})")
                n_labels.append("")
        else:
            trtpn = int(col["trtpn"])
            arm = cfg.arm_by_trtpn(trtpn)
            n = _n(denominators.get(trtpn, 0))
            name = _wrap(arm.column_header)
            if split_n_row:
                headers.append(name)
                n_labels.append(f"(N={n})")
            else:
                headers.append(f"{name} (N={n})")
                n_labels.append("")
    return headers, n_labels


def prepend_blank_column(
    headers: list[str],
    n_labels: list[str],
    body_rows: list[list[str]],
) -> tuple[list[str], list[str], list[list[str]], list[float]]:
    """Prepend a narrow blank column to match the 5-column lab / vitals / ECG
    shell template layout (blank | label | Arm1 | Arm2 | ... | Total).

    Returns ``(headers, n_labels, body_rows, col_rel_widths)``.  The caller
    should pass the returned ``col_rel_widths`` to ``TableSpec`` so the blank
    column is rendered as a narrow indent rather than taking a proportional
    share of the page width.
    """
    new_headers = [""] + headers
    new_n_labels = [""] + n_labels
    new_rows = [[""] + row for row in body_rows]

    # Blank col ≈ 4%, label col ≈ 34%, data cols split the rest.
    n_data = len(headers) - 1          # data cols (arms + total)
    blank_w = 0.04
    label_w = 0.34
    if n_data > 0:
        data_w = (1.0 - blank_w - label_w) / n_data
        widths = [blank_w, label_w] + [data_w] * n_data
    else:
        widths = [blank_w, 1.0 - blank_w]

    return new_headers, new_n_labels, new_rows, widths


def filter_to_set(
    df: pl.DataFrame,
    cfg: StudyConfig,
    analysis_set: str,
) -> pl.DataFrame:
    """Filter a DataFrame to the named analysis set's flag (no-op for ALL)."""
    aset = cfg.analysis_sets[analysis_set]
    if aset.flag_var is None:
        return df
    return df.filter(pl.col(aset.flag_var) == aset.flag_val)


# ---------------------------------------------------------------------------
# Continuous summary block (the n / Mean / SD,SE / Median / Min,Max
# five-row layout used by every continuous-stats table)
# ---------------------------------------------------------------------------

from tlf.validator import format_stat  # noqa: E402 — circular-safe at module load


def continuous_summary_rows(
    *,
    columns: list[dict[str, Any]],
    stats_per_arm: dict[int, dict[str, float | int | None]],
    raw_dp: int,
    total_stats: dict[str, float | int | None] | None = None,
    label_indent: str = "  ",
) -> list[list[str]]:
    """Build the canonical 5-row continuous-summary block per Crinetics shell.

    The shell collapses ``SD`` + ``SE`` onto one line ("SD, SE") and
    ``Min`` + ``Max`` onto one line ("Min, Max"). This helper does the
    flattening once so every table that summarises a continuous variable
    emits identical formatting.

    Args:
        columns: column layout from registry (arm dicts and optional Total).
        stats_per_arm: ``{trtpn: {"n":.., "mean":.., "sd":.., "se":..,
            "median":.., "min":.., "max":..}}`` — as produced by
            ``aggregator.continuous_summary``.
        raw_dp: raw decimal-places count for the parameter (drives format).
        total_stats: same shape but for the Total column (single combined
            group), or None if the layout has no Total.
        label_indent: prefix applied to each row label; defaults to three
            spaces so the renderer's ``\\li`` derivation indents the row.

    Returns one list-of-strings per row, in the order:
        n, Mean, "SD, SE", Median, "Min, Max"
    """
    arms = [c for c in columns if not c.get("is_total")]

    def _val(col: dict[str, Any], stat: str) -> float | int | None:
        if col.get("is_total"):
            return total_stats.get(stat) if total_stats else None
        return stats_per_arm.get(int(col["trtpn"]), {}).get(stat)

    def _single(stat: str) -> list[str]:
        return [format_stat(_val(c, stat), stat=stat, raw_dp=raw_dp) for c in columns]

    def _combined(stat_a: str, stat_b: str) -> list[str]:
        out: list[str] = []
        for c in columns:
            a = format_stat(_val(c, stat_a), stat=stat_a, raw_dp=raw_dp)
            b = format_stat(_val(c, stat_b), stat=stat_b, raw_dp=raw_dp)
            if not a and not b:
                out.append("")
            elif a == "-" and b == "-":
                out.append("-")
            elif not b:
                out.append(a)
            elif not a:
                out.append(b)
            else:
                out.append(f"{a}, {b}")
        return out

    return [
        [f"{label_indent}n",       *_single("n")],
        [f"{label_indent}Mean",    *_single("mean")],
        [f"{label_indent}SD, SE",  *_combined("sd", "se")],
        [f"{label_indent}Median",  *_single("median")],
        [f"{label_indent}Min, Max", *_combined("min", "max")],
    ]
