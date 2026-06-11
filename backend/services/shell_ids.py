"""Map registry shell ids to display table numbers.

Shell ids look like ``t_14_1_1_1`` / ``f_14_3_5_1`` with an optional variant
suffix (``t_14_3_1_11_common``). The dotted number is only the numeric part;
the suffix is a variant label, not another number segment — naive
``replace("_", ".")`` produced display strings like ``14.3.1.11.common``.
"""

from __future__ import annotations

import re


def table_number(shell_id: str) -> str:
    """'t_14_3_1_11_common' -> '14.3.1.11 (common)'; 't_14_1_1_1' -> '14.1.1.1'."""
    body = re.sub(r"^[tf]_", "", shell_id)
    parts = body.split("_")
    numeric: list[str] = []
    suffix: list[str] = []
    for p in parts:
        if not suffix and p.isdigit():
            numeric.append(p)
        else:
            suffix.append(p)
    if not numeric:
        return shell_id
    number = ".".join(numeric)
    return f"{number} ({' '.join(suffix)})" if suffix else number
