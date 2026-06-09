"""Shared statistical calculations for clinical tables and figures.

This file is responsible for the raw math behind the TLF outputs. It uses
Polars data frames to calculate continuous summaries, categorical counts,
percentages, adverse-event incidence, event occurrence counts, worst AE
severity, strongest AE relationship, lab abnormality shifts, and exposure
bins.

The functions here intentionally return plain counts and numeric values.
They do not decide how values should look in the final table; display
formatting and precision rules are handled later by validator.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import polars as pl


# ---------------------------------------------------------------------------
# Continuous summaries
# ---------------------------------------------------------------------------

CONTINUOUS_STATS = ("n", "mean", "sd", "se", "median", "min", "max")


@dataclass(frozen=True)
class ContinuousSummary:
    """Result of a continuous summary by treatment arm.

    .stats is a {trtpn -> {stat -> value}} mapping. n is int; the rest are
    floats (None when n=0 or undefined).
    """
    stats: dict[int, dict[str, float | int | None]]

    def get(self, trtpn: int, stat: str) -> float | int | None:
        return self.stats.get(trtpn, {}).get(stat)


def continuous_summary(
    df: pl.DataFrame,
    *,
    value_col: str,
    arm_col: str = "TRT01PN",
    arms: Iterable[int],
) -> ContinuousSummary:
    """n / mean / SD / SE / median / min / max per arm for one variable.

    Subjects with null `value_col` are excluded from n and all summaries.
    """
    out: dict[int, dict[str, float | int | None]] = {}
    for trtpn in arms:
        vals = (
            df.filter(pl.col(arm_col) == trtpn)
            .select(value_col)
            .drop_nulls()
            .to_series()
        )
        n = int(vals.len())
        if n == 0:
            out[trtpn] = {s: None for s in CONTINUOUS_STATS}
            out[trtpn]["n"] = 0
            continue
        mean = float(vals.mean())
        sd = float(vals.std(ddof=1)) if n > 1 else None
        se = (sd / (n ** 0.5)) if sd is not None else None
        out[trtpn] = {
            "n": n,
            "mean": mean,
            "sd": sd,
            "se": se,
            "median": float(vals.median()),
            "min": float(vals.min()),
            "max": float(vals.max()),
        }
    return ContinuousSummary(stats=out)


# ---------------------------------------------------------------------------
# Categorical summaries — counts and percentages
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CategoricalSummary:
    """Counts and percentages per (category, arm).

    .counts: {category -> {trtpn -> int}}
    .pcts:   {category -> {trtpn -> float | None}}  (None when denom is 0)
    .denominators: {trtpn -> int}
    """
    counts: dict[str, dict[int, int]]
    pcts: dict[str, dict[int, float | None]]
    denominators: dict[int, int]


def categorical_summary(
    df: pl.DataFrame,
    *,
    var: str,
    arm_col: str = "TRT01PN",
    arms: Iterable[int],
    denominators: dict[int, int],
    keep_categories: list[str] | None = None,
    subject_col: str = "USUBJID",
) -> CategoricalSummary:
    """Count distinct subjects in each (category × arm) cell.

    keep_categories — if provided, output rows are exactly these (zero-count
    categories preserved per the General Instructions). Otherwise, the set
    is taken from the data.
    """
    if df.is_empty():
        seen: list[str] = []
    else:
        seen_series = df.select(pl.col(var).cast(pl.Utf8)).drop_nulls().to_series().unique()
        seen = sorted(seen_series.to_list())
    categories = list(keep_categories) if keep_categories is not None else seen

    counts: dict[str, dict[int, int]] = {c: {a: 0 for a in arms} for c in categories}
    if not df.is_empty():
        agg = (
            df.select([subject_col, arm_col, var])
            .drop_nulls(var)
            .unique(subset=[subject_col, arm_col, var])
            .group_by([var, arm_col])
            .agg(pl.len().alias("n"))
        )
        for row in agg.iter_rows(named=True):
            cat = str(row[var])
            trtpn = int(row[arm_col])
            if cat in counts and trtpn in counts[cat]:
                counts[cat][trtpn] = int(row["n"])

    pcts: dict[str, dict[int, float | None]] = {}
    for cat in categories:
        pcts[cat] = {}
        for arm in arms:
            denom = denominators.get(arm, 0) or 0
            if denom == 0:
                pcts[cat][arm] = None
            else:
                pcts[cat][arm] = 100.0 * counts[cat][arm] / denom
    return CategoricalSummary(counts=counts, pcts=pcts, denominators=dict(denominators))


# ---------------------------------------------------------------------------
# Change from baseline
# ---------------------------------------------------------------------------

def cfb_visit_summary(
    df: pl.DataFrame,
    *,
    value_col: str = "AVAL",
    chg_col: str = "CHG",
    base_col: str = "BASE",
    arm_col: str = "TRT01PN",
    visit_col: str = "AVISIT",
    arms: Iterable[int],
) -> dict[str, dict[int, ContinuousSummary]]:
    """Return {visit -> {arm -> ContinuousSummary on CHG}} for a parameter.

    Only subjects with both non-null BASE and non-null AVAL at that visit are
    included in n.
    """
    eligible = df.filter(pl.col(base_col).is_not_null() & pl.col(value_col).is_not_null())
    visits = sorted(eligible.select(visit_col).drop_nulls().unique().to_series().to_list())
    out: dict[str, dict[int, ContinuousSummary]] = {}
    for v in visits:
        out[v] = {}
        sub = eligible.filter(pl.col(visit_col) == v)
        out[v] = continuous_summary(
            sub, value_col=chg_col, arm_col=arm_col, arms=arms
        ).stats  # type: ignore[assignment]
        # repack the dict-of-dicts as a fresh ContinuousSummary per arm for symmetry
    # The signature says "{arm -> ContinuousSummary}" but the body produced
    # raw {arm -> {stat -> val}}.  Fix it cleanly below.
    fixed: dict[str, dict[int, ContinuousSummary]] = {}
    for v, arm_stats in out.items():
        fixed[v] = {}
        for arm in arms:
            fixed[v][arm] = ContinuousSummary(stats={arm: arm_stats.get(arm, {})})  # type: ignore[arg-type]
    return fixed


def visit_summary(
    df: pl.DataFrame,
    *,
    value_col: str,
    arm_col: str = "TRT01PN",
    visit_col: str = "AVISIT",
    arms: Iterable[int],
    require_baseline: bool = False,
    base_col: str = "BASE",
) -> dict[str, ContinuousSummary]:
    """{visit -> ContinuousSummary of value_col} per arm.

    If require_baseline=True, only subjects with non-null BASE are counted
    (matches the SAP definition for post-baseline visit n).
    """
    eligible = df
    if require_baseline:
        eligible = eligible.filter(pl.col(base_col).is_not_null())
    visits = sorted(eligible.select(visit_col).drop_nulls().unique().to_series().to_list())
    return {
        v: continuous_summary(
            eligible.filter(pl.col(visit_col) == v),
            value_col=value_col,
            arm_col=arm_col,
            arms=arms,
        )
        for v in visits
    }


# ---------------------------------------------------------------------------
# Adverse-event aggregation
# ---------------------------------------------------------------------------

_DOSE_MOD_AEACN_VALUES = frozenset({
    "DOSE INTERRUPTED", "DOSE REDUCED", "DOSE DELAYED",
    "DOSE INCREASED", "DOSE NOT CHANGED",
})


def _apply_ae_filter(df: pl.DataFrame, filt: dict[str, Any]) -> pl.DataFrame:
    """Apply AE-specific filters.

    Special keys handled beyond plain column == value matching:

    * ``related: true``         — AEREL ∈ (POSSIBLE, PROBABLE), missing→POSSIBLE
    * ``CQ01NAM_not_null: true``— CQ01NAM not null/empty
    * ``AETOXGR_gte: N``        — AETOXGR >= N (graceful no-op when column absent)
    * ``AEACN_dose_mod: true``  — AEACN in the dose-modification value set
    * ``AEACN_dose_mod_other``  — AEACN is a dose-mod value NOT captured elsewhere
    """
    out = df
    for key, val in filt.items():
        if key == "related" and val is True:
            out = out.with_columns(
                pl.col("AEREL").fill_null("POSSIBLE")
            ).filter(pl.col("AEREL").is_in(["POSSIBLE", "PROBABLE"]))
        elif key == "CQ01NAM_not_null":
            if val:
                out = out.filter(pl.col("CQ01NAM").is_not_null() & (pl.col("CQ01NAM") != ""))
        elif key == "AETOXGR_gte":
            # Issues 18: grade >= N filter; graceful no-op when column absent.
            if "AETOXGR" in out.columns:
                out = out.filter(pl.col("AETOXGR").cast(pl.Float64, strict=False) >= float(val))
            else:
                out = out.head(0)  # column absent → 0 subjects
        elif key == "AEACN_dose_mod":
            # Issue 19: any dose modification (interruption, reduction, delay, …)
            if "AEACN" in out.columns:
                out = out.filter(pl.col("AEACN").is_in(_DOSE_MOD_AEACN_VALUES))
            else:
                out = out.head(0)
        elif key == "AEACN_dose_mod_other":
            # Issue 19: dose-mod "Other" = a dose-mod AEACN not covered by the
            # three explicit sub-rows (interrupted / reduced / delayed).
            known = frozenset({"DOSE INTERRUPTED", "DOSE REDUCED", "DOSE DELAYED"})
            other_vals = _DOSE_MOD_AEACN_VALUES - known
            if "AEACN" in out.columns:
                out = out.filter(pl.col("AEACN").is_in(other_vals))
            else:
                out = out.head(0)
        elif key in out.columns:
            out = out.filter(pl.col(key) == val)
        else:
            # Unknown filter key — surface as an error rather than silently dropping.
            raise KeyError(f"AE filter references unknown column or special key: {key!r}")
    return out


def ae_incidence(
    df: pl.DataFrame,
    *,
    arm_col: str = "TRTAN",
    arms: Iterable[int],
    denominators: dict[int, int],
    filt: dict[str, Any] | None = None,
    group_by: str | None = None,
    subject_col: str = "USUBJID",
) -> CategoricalSummary:
    """AE incidence (unique subjects with >= 1 qualifying event).

    If `group_by` is None, returns a single 'Any' category. If set (e.g.
    AEBODSYS, AEDECOD, CQ01NAM), returns one row per group level.
    """
    sub = _apply_ae_filter(df, filt or {})
    if group_by is None:
        # Single combined row
        counts: dict[str, dict[int, int]] = {"Any": {a: 0 for a in arms}}
        if not sub.is_empty():
            agg = (
                sub.select([subject_col, arm_col])
                .unique()
                .group_by(arm_col)
                .agg(pl.len().alias("n"))
            )
            for row in agg.iter_rows(named=True):
                arm = int(row[arm_col])
                if arm in counts["Any"]:
                    counts["Any"][arm] = int(row["n"])
        pcts = {
            "Any": {
                a: (None if (denominators.get(a) or 0) == 0
                    else 100.0 * counts["Any"][a] / denominators[a])
                for a in arms
            }
        }
        return CategoricalSummary(counts=counts, pcts=pcts, denominators=dict(denominators))
    else:
        # Group-level: unique subjects per (group, arm)
        groups: list[str] = []
        counts = {}
        if not sub.is_empty():
            sub_filled = sub.with_columns(
                pl.col(group_by).cast(pl.Utf8).fill_null("UNCODED").alias(group_by)
            )
            groups = sorted(
                sub_filled.select(group_by)
                .to_series()
                .unique()
                .to_list()
            )
            counts = {g: {a: 0 for a in arms} for g in groups}
            agg = (
                sub_filled.select([subject_col, arm_col, group_by])
                .unique(subset=[subject_col, arm_col, group_by])
                .group_by([group_by, arm_col])
                .agg(pl.len().alias("n"))
            )
            for row in agg.iter_rows(named=True):
                g = str(row[group_by])
                arm = int(row[arm_col])
                counts[g][arm] = int(row["n"])
        pcts = {}
        for g in groups:
            pcts[g] = {}
            for a in arms:
                d = denominators.get(a, 0) or 0
                pcts[g][a] = None if d == 0 else 100.0 * counts[g][a] / d
        return CategoricalSummary(counts=counts, pcts=pcts, denominators=dict(denominators))


def ae_occurrence_count(
    df: pl.DataFrame,
    *,
    arm_col: str = "TRTAN",
    arms: Iterable[int],
    filt: dict[str, Any] | None = None,
    group_by: str | None = None,
) -> dict[str, dict[int, int]]:
    """Total event count (every qualifying row), per group × arm. Used for
    the 'm' column in safety overview tables."""
    sub = _apply_ae_filter(df, filt or {})
    if group_by is None:
        counts: dict[str, dict[int, int]] = {"Any": {a: 0 for a in arms}}
        if not sub.is_empty():
            agg = sub.group_by(arm_col).agg(pl.len().alias("m"))
            for row in agg.iter_rows(named=True):
                arm = int(row[arm_col])
                if arm in counts["Any"]:
                    counts["Any"][arm] = int(row["m"])
        return counts
    else:
        if not sub.is_empty():
            sub_filled = sub.with_columns(
                pl.col(group_by).cast(pl.Utf8).fill_null("UNCODED").alias(group_by)
            )
            groups = sorted(
                sub_filled.select(group_by).to_series().unique().to_list()
            )
        else:
            sub_filled = sub
            groups = []
        out = {g: {a: 0 for a in arms} for g in groups}
        if not sub.is_empty():
            agg = (
                sub_filled
                .group_by([group_by, arm_col])
                .agg(pl.len().alias("m"))
            )
            for row in agg.iter_rows(named=True):
                g = str(row[group_by])
                arm = int(row[arm_col])
                out[g][arm] = int(row["m"])
        return out


def ae_severity_max(
    df: pl.DataFrame,
    *,
    severity_col: str = "AESEV",
    severity_order: tuple[str, ...] = ("MILD", "MODERATE", "SEVERE"),
    group_cols: tuple[str, ...] = ("AEBODSYS", "AEDECOD"),
    subject_col: str = "USUBJID",
    arm_col: str = "TRTAN",
) -> pl.DataFrame:
    """Return one row per (subject, group_cols) with worst severity captured.

    Subjects with multiple AEs in the same (SOC, PT) keep only their max
    severity per the SAP rule for the severity table.
    """
    rank = {s: i for i, s in enumerate(severity_order)}
    sub = df.with_columns(
        pl.col(severity_col).map_elements(
            lambda x: rank.get(x, -1), return_dtype=pl.Int32
        ).alias("_sev_rank")
    )
    # Take row with highest _sev_rank per (subject, *group_cols)
    out = (
        sub.sort("_sev_rank", descending=True)
        .unique(subset=[subject_col, arm_col, *group_cols], keep="first")
        .drop("_sev_rank")
    )
    return out


def ae_relationship_max(
    df: pl.DataFrame,
    *,
    rel_col: str = "AEREL",
    order: tuple[str, ...] = ("NONE", "REMOTE", "POSSIBLE", "PROBABLE"),
    group_cols: tuple[str, ...] = ("AEBODSYS", "AEDECOD"),
    subject_col: str = "USUBJID",
    arm_col: str = "TRTAN",
    impute_missing: str = "POSSIBLE",
) -> pl.DataFrame:
    """One row per (subject, group_cols) with strongest relationship kept.

    Missing values are imputed before ranking, per SAP.
    """
    rank = {s: i for i, s in enumerate(order)}
    sub = df.with_columns(pl.col(rel_col).fill_null(impute_missing))
    sub = sub.with_columns(
        pl.col(rel_col).map_elements(
            lambda x: rank.get(x, -1), return_dtype=pl.Int32
        ).alias("_rel_rank")
    )
    out = (
        sub.sort("_rel_rank", descending=True)
        .unique(subset=[subject_col, arm_col, *group_cols], keep="first")
        .drop("_rel_rank")
    )
    return out


# ---------------------------------------------------------------------------
# Lab / vital abnormality shift counts
# ---------------------------------------------------------------------------

def anrind_shift(
    df: pl.DataFrame,
    *,
    param: str,
    visit: str,
    arms: Iterable[int],
    denominators: dict[int, int],
    arm_col: str = "TRT01PN",
    visit_col: str = "AVISIT",
    param_col: str = "PARAM",
    indicator_col: str = "ANRIND",
    subject_col: str = "USUBJID",
) -> CategoricalSummary:
    """N/L/H/Missing counts for one param at one visit. ANL01FL filter is
    the caller's responsibility."""
    sub = df.filter((pl.col(param_col) == param) & (pl.col(visit_col) == visit))
    # Normalise indicator
    sub = sub.with_columns(
        pl.when(pl.col(indicator_col).is_null() | (pl.col(indicator_col) == ""))
          .then(pl.lit("Missing"))
          .otherwise(pl.col(indicator_col))
          .alias(indicator_col)
    )
    return categorical_summary(
        sub,
        var=indicator_col,
        arm_col=arm_col,
        arms=arms,
        denominators=denominators,
        keep_categories=["N", "L", "H", "Missing"],
        subject_col=subject_col,
    )


# ---------------------------------------------------------------------------
# Exposure / compliance helpers
# ---------------------------------------------------------------------------

def categorical_bins(
    df: pl.DataFrame,
    *,
    value_col: str,
    bins: list[dict[str, Any]],
    arm_col: str = "TRT01PN",
    arms: Iterable[int],
    denominators: dict[int, int],
    subject_col: str = "USUBJID",
) -> CategoricalSummary:
    """Bin a continuous variable into labelled categories.

    Each bin: {label, lo, hi, inclusive_lo (default false), inclusive_hi
    (default false)}. lo=None means -inf; hi=None means +inf.
    """
    expr_list = []
    labels = []
    for b in bins:
        label = b["label"]
        labels.append(label)
        cond = pl.lit(True)
        if b.get("lo") is not None:
            inc = b.get("inclusive_lo", False)
            cond = cond & (pl.col(value_col) >= b["lo"] if inc else pl.col(value_col) > b["lo"])
        if b.get("hi") is not None:
            inc = b.get("inclusive_hi", False)
            cond = cond & (pl.col(value_col) <= b["hi"] if inc else pl.col(value_col) < b["hi"])
        expr_list.append((label, cond))

    counts: dict[str, dict[int, int]] = {lbl: {a: 0 for a in arms} for lbl in labels}
    for lbl, cond in expr_list:
        sub = df.filter(cond & pl.col(value_col).is_not_null())
        if sub.is_empty():
            continue
        agg = (
            sub.select([subject_col, arm_col])
            .unique()
            .group_by(arm_col)
            .agg(pl.len().alias("n"))
        )
        for row in agg.iter_rows(named=True):
            arm = int(row[arm_col])
            if arm in counts[lbl]:
                counts[lbl][arm] = int(row["n"])

    pcts: dict[str, dict[int, float | None]] = {}
    for lbl in labels:
        pcts[lbl] = {}
        for a in arms:
            d = denominators.get(a, 0) or 0
            pcts[lbl][a] = None if d == 0 else 100.0 * counts[lbl][a] / d
    return CategoricalSummary(counts=counts, pcts=pcts, denominators=dict(denominators))
