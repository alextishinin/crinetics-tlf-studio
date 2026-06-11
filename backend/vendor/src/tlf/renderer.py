"""Turn prepared table rows into formatted RTF output files.

Table modules calculate the rows for a table, then pass them here in a
TableSpec. This renderer validates the table shape, builds the title,
column headers, body, footnotes, source area, page header, and page footer,
and writes the final RTF file through rtflite.

This file owns the document-level presentation rules: landscape page
layout, Courier New font, borders, row indentation, right-aligned data
columns, Crinetics header text, footer text, generated output filenames,
and page-number field codes.

It also performs a small RTF post-processing step so continuous summary
blocks such as n, Mean, SD/SE, Median, and Min/Max are less likely to split
awkwardly across pages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import polars as pl
from jinja2 import Environment, StrictUndefined
from rtflite import (
    RTFBody,
    RTFColumnHeader,
    RTFDocument,
    RTFFootnote,
    RTFPage,
    RTFPageFooter,
    RTFPageHeader,
    RTFSource,
    RTFTitle,
)

from tlf.config import StudyConfig
from tlf.footnotes import Footnote, assert_no_unresolved
from tlf.validator import (
    ValidationError,
    validate_title_lines,
)


_jinja_env = Environment(undefined=StrictUndefined, autoescape=False)


# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------

COURIER_NEW = 9         # rtflite font number for Courier New
BODY_FONT_SIZE = 8      # 8pt body / 8pt everywhere

# Twips per inch
TWIPS = 1440

# Landscape letter dimensions in twips
PAGE_WIDTH = 15840      # 11 inches
PAGE_HEIGHT = 12240     # 8.5 inches
# 1-inch margins on all four sides (Crinetics shell template).
MARGIN_TOP = 1440
MARGIN_BOTTOM = 1440
MARGIN_LEFT = 1440
MARGIN_RIGHT = 1440

# Spaces-per-indent-level convention used by the table modules: row
# labels with 3*N leading spaces sit at level N (0=top-level header,
# 1=first sub-level, 2=second). Conversion to twips below.
INDENT_SPACES_PER_LEVEL = 3
INDENT_TWIPS_PER_LEVEL = 240   # ~0.17" per level (matches the shell)


# ---------------------------------------------------------------------------
# Renderable table representation
# ---------------------------------------------------------------------------

@dataclass
class TableSpec:
    """Fully-formatted, ready-to-render table specification.

    `body_rows` is a list of rows; each row is a sequence with one entry
    per column (label column first, then one cell per arm). A row whose
    label is the empty string after stripping is treated as a section
    break (rendered as a blank row).
    """
    shell_id: str
    title: tuple[str, str, str]
    column_headers: list[str]
    arm_n_labels: list[str]
    body_rows: list[list[str]]
    footnotes: list[Footnote] = field(default_factory=list)
    source_lines: list[str] = field(default_factory=list)
    col_rel_widths: list[float] | None = None
    # Row labels that should render bold (after lstrip()). For Table
    # 14.1.1.1 this is just "Safety Analysis Set"; other tables typically
    # leave it empty.
    bold_row_labels: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Filename + path helpers
# ---------------------------------------------------------------------------

def output_filename(study_id: str, table_number: str, run_dt: datetime | None = None) -> str:
    dt = run_dt or datetime.now()
    stamp = dt.strftime("%d%b%Y").upper()
    return f"{study_id}_Table_{table_number}_{stamp}.rtf"


def purge_prior_outputs(out_dir: Path, new_path: Path) -> None:
    """Delete any earlier-dated versions of the same output.

    Matches files whose name shares the same study/type/number prefix up to
    the date stamp, e.g. ``CDISCPILOT01_Table_14.3.1.1_*.rtf``.  Both the
    .rtf and its companion .pdf (or .png for figures) are removed so the
    output folder always contains exactly one copy of each output.
    """
    # The date stamp is always the last ``_``-delimited token before the
    # extension, so stripping it gives the stable per-output prefix.
    prefix = new_path.stem.rsplit("_", 1)[0] + "_"
    for ext in (".rtf", ".pdf", ".png"):
        for old in out_dir.glob(f"{prefix}*{ext}"):
            if old.resolve() != new_path.with_suffix(ext).resolve():
                old.unlink(missing_ok=True)


def resolve_output_path(
    cfg: StudyConfig,
    table_number: str,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    base = (out_dir or cfg.output_path).resolve()
    base.mkdir(parents=True, exist_ok=True)
    new_path = base / output_filename(cfg.study_id, table_number, run_dt)
    purge_prior_outputs(base, new_path)
    return new_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_table(
    spec: TableSpec,
    *,
    cfg: StudyConfig,
    output_path: Path,
    run_dt: datetime | None = None,
) -> Path:
    _validate(spec, cfg)

    now = run_dt or datetime.now()
    ncol = len(spec.column_headers)

    # ---------------- body assembly --------------------------------------

    # Strip leading whitespace from the first column and remember the
    # indent level per row, so we can pass it to rtflite as text_indent_left
    # rather than embedding spaces in the cell text.
    cleaned_rows: list[list[str]] = []
    indent_levels: list[int] = []
    is_bold_row: list[bool] = []
    bold_set = {b.strip() for b in spec.bold_row_labels}
    for row in spec.body_rows:
        first = str(row[0]) if row else ""
        stripped = first.lstrip(" ")
        leading = len(first) - len(stripped)
        level = leading // INDENT_SPACES_PER_LEVEL
        cleaned_rows.append([stripped] + [str(c) for c in row[1:]])
        indent_levels.append(level)
        is_bold_row.append(stripped in bold_set)

    nrow = len(cleaned_rows)

    df = _rows_to_polars(spec.column_headers, cleaned_rows)

    # ---- per (row,col) formatting matrices for rtf_body ----
    fonts = [[COURIER_NEW] * ncol for _ in range(nrow)]
    sizes = [[BODY_FONT_SIZE] * ncol for _ in range(nrow)]
    fmt = [
        ["b" if is_bold_row[r] else "" for _ in range(ncol)]
        for r in range(nrow)
    ]
    # Row-label column left-aligned; every data column centered.
    just = [["l"] + ["c"] * (ncol - 1) for _ in range(nrow)]
    # Indent: applies only to the label column
    indents = [
        [indent_levels[r] * INDENT_TWIPS_PER_LEVEL] + [0] * (ncol - 1)
        for r in range(nrow)
    ]

    # ---- borders: empty everywhere except bottom rule on last body row ----
    empty_border_matrix = [[""] * ncol for _ in range(nrow)]
    bottom_border_matrix = [[""] * ncol for _ in range(nrow)]
    if nrow > 0:
        bottom_border_matrix[-1] = ["single"] * ncol

    body_kwargs: dict = dict(
        text_font=fonts,
        text_font_size=sizes,
        text_format=fmt,
        text_justification=just,
        text_indent_left=indents,
        border_left=empty_border_matrix,
        border_right=empty_border_matrix,
        border_top=empty_border_matrix,
        border_bottom=bottom_border_matrix,
        border_first=empty_border_matrix,
        border_last=empty_border_matrix,
        cell_justification=just,
        # Issue 8b (audit): rtflite's default LaTeX→Unicode conversion turns
        # ">=" into "≥" and "<=" into "≤". The shell template requires the
        # ASCII form, so disable conversion for all body cells.
        text_convert=[[False] * ncol for _ in range(nrow)],
    )
    if spec.col_rel_widths and len(spec.col_rel_widths) == ncol:
        body_kwargs["col_rel_width"] = list(spec.col_rel_widths)
    else:
        body_kwargs["col_rel_width"] = _default_col_widths(ncol)
    rtf_body = RTFBody(**body_kwargs)

    # ---------------- column header band --------------------------------

    rtf_headers = _build_column_headers(spec, ncol)

    # ---------------- title + page header + footer ----------------------

    # Render Jinja2 placeholders in title lines (e.g. {{ common_ae_cutoff_pct }})
    from tlf.footnotes import render as _render_template
    _ctx = cfg.footnote_context()
    rendered_title = [_render_template(t, _ctx) for t in spec.title]

    title = RTFTitle(
        text=rendered_title,
        text_font=[COURIER_NEW] * 3,
        text_font_size=[BODY_FONT_SIZE] * 3,
        text_format=[""] * 3,   # not bold
        text_justification=["c"] * 3,
        # Issue 8b (audit): preserve literal ">=" in titles (e.g. "Grade >=3")
        # rather than letting rtflite remap to U+2265.
        text_convert=[False] * 3,
    )

    header_lines = _page_header_lines(cfg)
    page_header = RTFPageHeader(
        text=header_lines,
        text_font=[COURIER_NEW] * len(header_lines),
        text_font_size=[BODY_FONT_SIZE] * len(header_lines),
        text_justification=["r"] * len(header_lines),
        text_convert=[True] * len(header_lines),
    )

    footer_lines, footer_just, footer_convert = _page_footer(cfg, now)
    page_footer = RTFPageFooter(
        text=footer_lines,
        text_font=[COURIER_NEW] * len(footer_lines),
        text_font_size=[BODY_FONT_SIZE] * len(footer_lines),
        text_justification=footer_just,
        text_convert=footer_convert,
    )

    # ---------------- footnotes (above page footer, below table) --------

    # Pre-convert Latin-1 range chars (128–255) to RTF Unicode escapes.
    # rtflite writes chars with ord ≤ 255 as raw bytes; Word then reads them
    # as Latin-1, so UTF-8 bytes for × (U+00D7 → 0xC3 0x97) appear as "Ã—".
    # Converting before passing to rtflite keeps the footnotes as pure ASCII.
    footnote_text = [_rtf_escape_latin1(f.text) for f in spec.footnotes]
    for line in footnote_text:
        assert_no_unresolved(line)

    rtf_footnote = None
    if footnote_text:
        n = len(footnote_text)
        rtf_footnote = RTFFootnote(
            text=footnote_text,
            text_font=[[COURIER_NEW]] * n,
            text_font_size=[[BODY_FONT_SIZE]] * n,
            text_justification=[["l"]] * n,
            border_left=[[""]] * n,
            border_right=[[""]] * n,
            border_top=[[""]] * n,
            border_bottom=[[""]] * n,
            border_first=[[""]] * n,
            border_last=[[""]] * n,
            as_table=False,
        )

    rtf_source = None
    if spec.source_lines:
        rtf_source = RTFSource(
            text=spec.source_lines,
            text_font=[[COURIER_NEW]] * len(spec.source_lines),
            text_font_size=[[BODY_FONT_SIZE]] * len(spec.source_lines),
            text_justification=[["l"]] * len(spec.source_lines),
            border_left=[[""]] * len(spec.source_lines),
            border_right=[[""]] * len(spec.source_lines),
            border_top=[[""]] * len(spec.source_lines),
            border_bottom=[[""]] * len(spec.source_lines),
            border_first=[[""]] * len(spec.source_lines),
            border_last=[[""]] * len(spec.source_lines),
            as_table=False,
        )

    # ---------------- page geometry -------------------------------------

    page = RTFPage(
        orientation="landscape",
        width=11.0,        # rtflite expects inches as floats
        height=8.5,
        # margin sequence: [left, right, top, bottom, header, footer] in inches
        margin=[1.0, 1.0, 1.0, 1.0, 0.5, 0.5],
        # Force the table to fill the full usable width (page - left/right
        # margins = 11 - 1 - 1 = 9"). rtflite's landscape default is 8.5",
        # which leaves a 0.5" gap on the right.
        col_width=9.0,
        border_first="",
        border_last="",
    )

    doc_kwargs: dict = {
        "df": df,
        "rtf_page": page,
        "rtf_page_header": page_header,
        "rtf_title": title,
        "rtf_column_header": rtf_headers,
        "rtf_body": rtf_body,
        "rtf_page_footer": page_footer,
    }
    if rtf_footnote is not None:
        doc_kwargs["rtf_footnote"] = rtf_footnote
    if rtf_source is not None:
        doc_kwargs["rtf_source"] = rtf_source

    doc = RTFDocument(**doc_kwargs)
    doc.write_rtf(output_path)
    _apply_keep_with_next(output_path)
    return output_path


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _validate(spec: TableSpec, cfg: StudyConfig) -> None:
    validate_title_lines(spec.title)
    if not spec.body_rows:
        raise ValidationError(f"TableSpec {spec.shell_id} has no body rows")
    ncol = len(spec.column_headers)
    if len(spec.arm_n_labels) != ncol:
        raise ValidationError(
            f"arm_n_labels length {len(spec.arm_n_labels)} != column count {ncol}"
        )
    for i, row in enumerate(spec.body_rows):
        if len(row) != ncol:
            raise ValidationError(
                f"Row {i} has {len(row)} cells, expected {ncol}"
            )


def _rows_to_polars(headers: list[str], rows: list[list[str]]) -> pl.DataFrame:
    # Polars raises ShapeError when two column names are identical because the
    # dict accumulates entries for the same key at double the normal rate (e.g.
    # prepend_blank_column adds a "" column while label_header="" already put
    # one in).  Deduplicate by appending a counter suffix to collisions so the
    # DataFrame constructor always receives unique column names.  The names are
    # internal only — RTFColumnHeader controls what is displayed.
    seen: dict[str, int] = {}
    unique: list[str] = []
    for h in headers:
        count = seen.get(h, 0)
        seen[h] = count + 1
        unique.append(h if count == 0 else f"{h}_{count}")

    data: dict[str, list[str]] = {c: [] for c in unique}
    for row in rows:
        for col, val in zip(unique, row):
            data[col].append(str(val))
    return pl.DataFrame(data)


def _default_col_widths(ncol: int) -> list[float]:
    """Label column ~40% of width; data columns share the remaining 60%."""
    if ncol <= 1:
        return [1.0]
    data_share = 0.6 / (ncol - 1)
    return [0.4] + [data_share] * (ncol - 1)


def _build_column_headers(spec: TableSpec, ncol: int) -> list[RTFColumnHeader]:
    """Two-row column header band: arm labels (top), N labels (bottom).

    Borders:
      Top band:    top=single, bottom='' (no rule between header lines)
      Bottom band: top='',      bottom=single

    If arm_n_labels is empty, we collapse to a single header row with
    both top + bottom rules.
    """
    has_n_row = any(s for s in spec.arm_n_labels)
    headers: list[RTFColumnHeader] = []

    if has_n_row:
        headers.append(_one_header_row(
            spec.column_headers, ncol,
            top="single", bottom="",
            col_rel_widths=spec.col_rel_widths,
        ))
        headers.append(_one_header_row(
            spec.arm_n_labels, ncol,
            top="", bottom="single",
            col_rel_widths=spec.col_rel_widths,
        ))
    else:
        headers.append(_one_header_row(
            spec.column_headers, ncol,
            top="single", bottom="single",
            col_rel_widths=spec.col_rel_widths,
        ))
    return headers


def _one_header_row(
    text: list[str],
    ncol: int,
    *,
    top: str,
    bottom: str,
    col_rel_widths: list[float] | None,
) -> RTFColumnHeader:
    # Centre column-header text in data columns; the label slot stays
    # left-aligned for consistency with the body.
    just = [["l"] + ["c"] * (ncol - 1)]
    return RTFColumnHeader(
        text=text,
        text_font=[[COURIER_NEW] * ncol],
        text_font_size=[[BODY_FONT_SIZE] * ncol],
        text_justification=just,
        cell_justification=just,
        border_top=[[top] * ncol],
        border_bottom=[[bottom] * ncol],
        border_left=[[""] * ncol],
        border_right=[[""] * ncol],
        border_first=[[top] * ncol],
        border_last=[[bottom] * ncol],
        col_rel_width=list(col_rel_widths) if col_rel_widths and len(col_rel_widths) == ncol
                     else _default_col_widths(ncol),
        # Issue 8b (audit): preserve ASCII ">=" / "<=" in header cells.
        text_convert=[[False] * ncol],
    )


def _page_header_lines(cfg: StudyConfig) -> list[str]:
    """Right-aligned, two lines: company on top, protocol number below."""
    return ["Crinetics Pharmaceuticals", cfg.protocol_number]


def _page_footer(
    cfg: StudyConfig,
    run_dt: datetime,
) -> tuple[list[str], list[str], list[bool]]:
    """Build the page footer matching the Crinetics shell template.

    Layout (2 lines):
      Line 1: "Source: <source>"                                          (left)
      Line 2: "Data Extracted: ..."                                       (left)
              "v<sas> DDMMMYYYY:HH:MM:SS Page <chpgn> of <NUMPAGES>"      (right)

    rtflite's RTFPageFooter joins all text entries into a single paragraph
    with one alignment (\\line separators), so we cannot mix left/right
    alignment per line. Because Courier 8pt is monospaced, we instead pad
    the second line with spaces to push the right portion to the right
    margin. text_convert=False so the page-field RTF escapes survive.
    """
    extract = cfg.data_extract_date or run_dt.strftime("%Y-%m-%d")
    cut_clause = f", Data Cut: {cfg.data_cut_date}" if cfg.data_cut_date else ""
    ts = run_dt.strftime("%d%b%Y:%H:%M:%S").upper()

    line_source = f"Source: {cfg.source_code_location}"
    left2 = f"Data Extracted: {extract}{cut_clause}"
    # Right portion: timestamp + page numbering using RTF field codes.
    right_visible = f"v{cfg.sas_version} {ts} Page 1 of 1"  # widths only
    right_actual = (
        f"v{cfg.sas_version} {ts} "
        r"Page \chpgn of {\field{\*\fldinst NUMPAGES }}"
    )
    # Courier New 8pt advance width in Word: 600/1000 of em = 96 twips/char
    # at 8pt × 20 twips/pt = 160 twips em → 96 twips/char → 15 chars/inch.
    # Usable width with 1" margins on a landscape letter page is 9", so
    # ~135 characters fit per line. Pad the text to that count so the
    # right-hand portion lands at the right margin.
    USABLE_CHARS = 135
    pad = max(2, USABLE_CHARS - len(left2) - len(right_visible))
    line_combined = left2 + " " * pad + right_actual

    return (
        [line_source, line_combined],
        ["l", "l"],
        [False, False],   # keep field-code backslashes verbatim
    )


# ---------------------------------------------------------------------------
# Post-write: enforce continuous-summary-block atomicity
# ---------------------------------------------------------------------------

# Label strings (after leading-whitespace strip) whose row should never be
# separated from the next row by a page break. Chaining keep-with-next on
# rows 1–4 of the 5-row Crinetics summary block keeps n / Mean / SD, SE /
# Median / Min, Max together as one unit. The Min, Max row itself doesn't
# need the marker — it's last, so any page break after it is acceptable.
_KEEP_WITH_NEXT_LABELS: frozenset[str] = frozenset({
    "n",
    "Mean",
    "SD, SE",
    "Median",
})


def _rtf_escape_latin1(text: str) -> str:
    """Convert Latin-1 range chars (128–255) to RTF Unicode escape sequences.

    rtflite's row.py writes chars with ``ord(ch) <= 255`` as raw bytes.  When
    Word reads the resulting RTF file it interprets those bytes as Latin-1, so
    a UTF-8-encoded char like × (U+00D7 = 215) appears as "Ã—".  Pre-converting
    to ``\\uc1\\uN*`` escapes ensures those characters are encoded as all-ASCII
    RTF markup that round-trips correctly.
    """
    result: list[str] = []
    for ch in text:
        cp = ord(ch)
        if 128 <= cp <= 255:
            result.append(f"\\uc1\\u{cp}*")
        else:
            result.append(ch)
    return "".join(result)


def _apply_keep_with_next(rtf_path: Path) -> None:
    """Inject RTF ``\\trkeepfollow`` into rows whose first-column label is in
    _KEEP_WITH_NEXT_LABELS.

    Why this exists: rtflite has no per-row "keep with next" attribute, so
    Word's default pagination can split a 5-row continuous summary across
    two pages. This pass scans the emitted file, finds every ``\\trowd`` …
    ``\\row`` block, looks at the first cell's visible text, and prepends
    ``\\trkeepfollow`` to the row properties when the label matches.

    Content-based matching is deliberate — it survives rtflite changes to
    row ordering or multi-page header repetition, both of which would
    break position-based indexing.
    """
    import re

    text = rtf_path.read_text(encoding="utf-8")

    # rtflite emits cell text as ``{\f<n> <label>}\cell``. Extract just the
    # label by stripping leading whitespace inside the braces.
    label_pat = re.compile(r"\{\\f\d+\s+([^{}]*?)\}\\cell")

    out_chunks: list[str] = []
    cursor = 0
    for m in re.finditer(r"\\trowd", text):
        # Emit everything before this \trowd
        out_chunks.append(text[cursor:m.start()])

        # Locate the matching \row that ends this row
        row_end = text.find(r"\row", m.end())
        if row_end == -1:
            # Truncated / malformed — bail and emit the rest as-is
            out_chunks.append(text[m.start():])
            cursor = len(text)
            break
        row_block = text[m.start():row_end]

        # Find the first cell label inside this row block
        label_match = label_pat.search(row_block)
        label = label_match.group(1).strip() if label_match else ""

        if label in _KEEP_WITH_NEXT_LABELS:
            # Insert \trkeepfollow immediately after \trowd
            out_chunks.append(r"\trowd\trkeepfollow")
            out_chunks.append(text[m.end():row_end])
        else:
            out_chunks.append(text[m.start():row_end])

        cursor = row_end

    out_chunks.append(text[cursor:])
    rtf_path.write_text("".join(out_chunks), encoding="utf-8")
