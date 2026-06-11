"""Format values and check table structure before rendering.

This file contains the rules that keep generated tables consistent with
the TFL instructions. It decides how many decimals to show for each kind
of statistic, how to display percentages, how to suppress zero percentages,
and how to format p-values.

It also checks structural rules that should fail loudly if they are wrong:
continuous summary rows must appear in the required order, titles must have
three non-empty lines, footnotes must be ordered correctly, and footnotes
must end with periods.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence


# Required order for the continuous-summary block. The spec compresses
# "SD, SE" and "Min, Max" onto single lines, but for validation we keep them
# as discrete row labels and just enforce the sequence.
CONTINUOUS_BLOCK_ORDER: tuple[str, ...] = (
    "n",
    "Mean",
    "SD",
    "SE",
    "Median",
    "Min",
    "Max",
)

# Footnote ordering (1-indexed labels for diagnostics)
FOOTNOTE_ORDER: tuple[str, ...] = (
    "coding_dictionary",
    "abbreviations",
    "definitions",
    "statistical",
)


class ValidationError(ValueError):
    """Raised when a TFL output violates a General Instructions rule."""


# ---------------------------------------------------------------------------
# Shell mode: when enabled, every numeric formatter returns the placeholder
# strings used by the CRO TFL shell template ("xx", "xx (xx.x)", etc.) instead
# of computed values.  The pipeline sets this once at startup based on
# cfg.shell_mode; nothing else in the table modules needs to change.
# ---------------------------------------------------------------------------

_SHELL_MODE: bool = False


def set_shell_mode(enabled: bool) -> None:
    """Toggle shell-mode placeholder output for all formatters in this module."""
    global _SHELL_MODE
    _SHELL_MODE = bool(enabled)


def is_shell_mode() -> bool:
    return _SHELL_MODE


# ---------------------------------------------------------------------------
# Precision helpers
# ---------------------------------------------------------------------------

def raw_decimal_places(values: Iterable[float | int | None]) -> int:
    """Return the maximum number of decimal places observed in raw values.

    >=3 raw decimals are clipped to 2 per the spec. Nulls / NaNs / ints
    contribute 0. The result feeds the precision rules in `format_stat`.
    """
    max_dp = 0
    for v in values:
        if v is None:
            continue
        if isinstance(v, float) and math.isnan(v):
            continue
        # Use repr to recover decimal text reliably
        s = repr(float(v))
        if "e" in s or "E" in s:
            # Scientific notation — best-effort: count digits after the dot
            mantissa = s.split("e")[0] if "e" in s else s.split("E")[0]
            dp = len(mantissa.split(".")[1]) if "." in mantissa else 0
        elif "." in s:
            dec = s.split(".")[1].rstrip("0")
            dp = len(dec)
        else:
            dp = 0
        max_dp = max(max_dp, dp)
    return min(max_dp, 2)


def format_stat(value: float | int | None, *, stat: str, raw_dp: int) -> str:
    """Format a single statistic per the precision rules.

    stat in {n, mean, median, ci_lower, ci_upper, sd, se, min, max}.
    raw_dp is the parameter's max raw decimal places (capped at 2).
    """
    stat = stat.lower()
    if _SHELL_MODE:
        # Shell template placeholder: "xx" for integers, "xx.x"/"xx.xx" for
        # decimals.  Decimal count tracks the same rules as the real formatter.
        if stat == "n":
            return "xx"
        if stat in ("min", "max"):
            dp = raw_dp
        elif stat in ("mean", "median", "ci_lower", "ci_upper"):
            dp = raw_dp + 1
        elif stat in ("sd", "se"):
            dp = raw_dp + 2
        else:
            raise ValidationError(f"Unknown stat label: {stat!r}")
        return "xx" if dp == 0 else "xx." + "x" * dp

    if value is None:
        return "-"
    if isinstance(value, float) and math.isnan(value):
        return "-"

    if stat == "n":
        return f"{int(value)}"
    if stat in ("min", "max"):
        return f"{float(value):.{raw_dp}f}"
    if stat in ("mean", "median", "ci_lower", "ci_upper"):
        return f"{float(value):.{raw_dp + 1}f}"
    if stat in ("sd", "se"):
        return f"{float(value):.{raw_dp + 2}f}"
    raise ValidationError(f"Unknown stat label: {stat!r}")


def format_percent(n: int | None, denom: int | None) -> str:
    """Percentage to 1 decimal place; suppressed if n is 0 or null.

    Exactly 100% deliberately renders as "100" (not "100.0") per the shell
    template convention — full-population rows show a bare 100.
    """
    if _SHELL_MODE:
        return "xx.x"
    if n is None or denom in (None, 0):
        return ""
    if int(n) == 0:
        return ""
    pct = 100.0 * int(n) / int(denom)
    if pct == 100.0:
        return "100"
    return f"{pct:.1f}"


def format_n_pct(n: int | None, denom: int | None, *, paren: bool = True) -> str:
    """'xx (yy.y)' formatter. Returns '0' (no percent) when n=0."""
    if _SHELL_MODE:
        return "xx (xx.x)" if paren else "xx xx.x"
    if n is None:
        return ""
    n = int(n)
    if n == 0:
        return "0"
    pct = format_percent(n, denom)
    if not pct:
        return f"{n}"
    return f"{n} ({pct})" if paren else f"{n} {pct}"


def format_n_pct_m(n: int | None, denom: int | None, m: int | None) -> str:
    """'xx (yy.y) zz' — incidence n, percentage, occurrence m (safety overview).

    When n=0 the row is rendered as just '0' (no percent, no occurrence count)
    consistent with the zero-percent suppression rule.
    """
    if _SHELL_MODE:
        return "xx (xx.x) xx"
    base = format_n_pct(n, denom)
    if base == "" or base == "0":
        return base
    if m is None:
        return base
    return f"{base} {int(m)}"


def format_pvalue(p: float | None) -> str:
    """4-decimal p-values; <0.0001 / >0.9999 boundaries."""
    if _SHELL_MODE:
        return "0.xxxx"
    if p is None:
        return ""
    if isinstance(p, float) and math.isnan(p):
        return ""
    p = float(p)
    if p < 0.0001:
        return "<0.0001"
    if p > 0.9999:
        return ">0.9999"
    return f"{p:.4f}"


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------

def validate_continuous_block_order(row_labels: Sequence[str]) -> None:
    """Raise if a continuous-summary block is out of the canonical order.

    Combined labels like 'SD, SE' or 'Min, Max' are tolerated; what matters
    is that the underlying statistics appear in the order n → Mean → SD →
    SE → Median → Min → Max.
    """
    # Flatten combined labels
    flat: list[str] = []
    for lbl in row_labels:
        for part in lbl.split(","):
            part = part.strip()
            if part:
                flat.append(part)
    # Match labels case-insensitively, ignoring punctuation
    canonical = [s.lower() for s in CONTINUOUS_BLOCK_ORDER]
    got = [s.lower() for s in flat]
    if got != canonical:
        raise ValidationError(
            f"Continuous summary block out of order: got {flat}, "
            f"expected {list(CONTINUOUS_BLOCK_ORDER)}"
        )


def validate_footnote_order(footnotes: Sequence[dict]) -> None:
    """Each footnote dict must carry a 'kind' in FOOTNOTE_ORDER. Order must
    be non-decreasing along the canonical sequence."""
    seen_idx = -1
    for fn in footnotes:
        kind = fn.get("kind")
        if kind not in FOOTNOTE_ORDER:
            raise ValidationError(f"Footnote kind {kind!r} not recognised")
        idx = FOOTNOTE_ORDER.index(kind)
        if idx < seen_idx:
            raise ValidationError(
                f"Footnote of kind {kind!r} appears after a later kind"
            )
        seen_idx = max(seen_idx, idx)


def validate_footnote_ends_with_period(footnote_text: str) -> None:
    """Each rendered footnote line must end with a period per the spec."""
    if not footnote_text.rstrip().endswith("."):
        raise ValidationError(
            f"Footnote must end with a period: {footnote_text!r}"
        )


def validate_title_lines(title: Sequence[str]) -> None:
    """Title must have exactly three non-empty lines."""
    if len(title) != 3:
        raise ValidationError(
            f"Title must have 3 lines (got {len(title)}): {title!r}"
        )
    for i, line in enumerate(title, 1):
        if not str(line).strip():
            raise ValidationError(f"Title line {i} is empty")


def validate_column_count(columns: Sequence[dict], expected: int) -> None:
    if len(columns) != expected:
        raise ValidationError(
            f"Expected {expected} columns but layout has {len(columns)}"
        )


def validate_isodate(value: str) -> None:
    """Listings must use ISO8601 dates (YYYY-MM-DD)."""
    import re
    if value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValidationError(f"Date {value!r} is not ISO8601 (YYYY-MM-DD)")
