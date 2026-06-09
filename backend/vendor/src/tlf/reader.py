"""Read ADaM clinical datasets from the study data folder.

This file hides the details of the input file format from the rest of the
project. A table module can ask for a dataset by short name, such as adsl
or adae, and this reader will find a matching parquet, SAS7BDAT, or XPT
file under the configured ADaM path.

It also trims common text columns at load time so values such as visits,
parameters, body systems, and preferred terms group correctly during later
summary calculations.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl


# Columns where leading/trailing whitespace must be stripped at read time.
# AVISIT in particular is known to carry leading spaces in the sample data.
_STRIP_COLS = ("AVISIT", "VISIT", "PARAM", "PARAMCD", "AEBODSYS", "AEDECOD", "AESOC")


def read_adam(name: str, adam_path: Path) -> pl.LazyFrame:
    """Read an ADaM dataset by short name (e.g. 'adsl').

    Resolves to <adam_path>/<name>.parquet or <adam_path>/<name>.sas7bdat,
    whichever exists. Returns a LazyFrame with string columns trimmed.
    """
    name = name.lower()
    parquet = adam_path / f"{name}.parquet"
    sas = adam_path / f"{name}.sas7bdat"
    xpt = adam_path / f"{name}.xpt"

    if parquet.exists():
        lf = pl.scan_parquet(parquet)
    elif sas.exists():
        df = _read_sas(sas)
        lf = df.lazy()
    elif xpt.exists():
        df = _read_sas(xpt)
        lf = df.lazy()
    else:
        raise FileNotFoundError(
            f"No {name}.parquet / {name}.sas7bdat / {name}.xpt under {adam_path}"
        )

    return _normalise_strings(lf)


def _read_sas(path: Path) -> pl.DataFrame:
    """Read SAS7BDAT or XPT into a polars DataFrame via pyreadstat."""
    import pyreadstat

    if path.suffix.lower() == ".xpt":
        df, _ = pyreadstat.read_xport(str(path))
    else:
        df, _ = pyreadstat.read_sas7bdat(str(path))
    # pyreadstat returns a pandas DataFrame; convert columns manually to avoid
    # pulling pandas into the public dependency surface.
    return pl.from_pandas(df)


def _normalise_strings(lf: pl.LazyFrame) -> pl.LazyFrame:
    """Strip whitespace from known string columns if present in the schema."""
    schema = lf.collect_schema()
    cols = [c for c in _STRIP_COLS if c in schema and schema[c] == pl.Utf8]
    if not cols:
        return lf
    return lf.with_columns([pl.col(c).str.strip_chars() for c in cols])


def read_all(adam_path: Path, names: list[str] | None = None) -> dict[str, pl.LazyFrame]:
    """Read every ADaM dataset under `adam_path` into a dict {name: LazyFrame}."""
    if names is None:
        names = sorted(
            p.stem.lower()
            for p in adam_path.iterdir()
            if p.suffix.lower() in (".parquet", ".sas7bdat", ".xpt")
        )
    return {name: read_adam(name, adam_path) for name in names}
