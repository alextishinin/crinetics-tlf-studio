"""Shell-template body row layouts for every TFL.

When ``cfg.shell_mode`` is enabled each table generator calls the matching
function in this module to get its body rows.  The layouts mirror the CRO TFL
shell template (file: ``TFL shell template DDMMM2025 (v1.1).docx``) exactly:
the same sections, the same row labels, and the same placeholder category
names (``System Organ Class #1``, ``Preferred Term #1.1``, ``parameter name
(unit)``, ``Visit #x``, ``Group #1`` ...).

The functions receive the resolved ``columns`` list — same shape every table
already uses — so they know how many arm columns vs Total columns to fill.
Pre-randomisation sections (e.g. Screened, Entered Run-in on the disposition
shell) populate only the Total column; everything else populates all columns.

Every callable here returns ``list[list[str]]`` matching the
``column_headers`` length the renderer expects (label + one per column).
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Cell helpers
# ---------------------------------------------------------------------------

def _ndata(columns: list[dict[str, Any]]) -> int:
    return len(columns)


def _total_idx(columns: list[dict[str, Any]]) -> int:
    for i, c in enumerate(columns):
        if c.get("is_total"):
            return i
    return -1


def _all(value: str, columns: list[dict[str, Any]]) -> list[str]:
    return [value] * _ndata(columns)


def _total_only(value: str, columns: list[dict[str, Any]]) -> list[str]:
    cells = [""] * _ndata(columns)
    idx = _total_idx(columns)
    if idx >= 0:
        cells[idx] = value
    return cells


def _blank(columns: list[dict[str, Any]]) -> list[str]:
    """A full-width section break — all cells empty."""
    return [""] * (1 + _ndata(columns))


def _row(label: str, cells: list[str]) -> list[str]:
    return [label, *cells]


# ---------------------------------------------------------------------------
# The 5-row continuous-summary block (n / Mean / SD,SE / Median / Min,Max) is
# what the shell template prints as "continuous descriptive summary" + "xx".
# Every continuous block in the engine emits these five rows already; we
# stamp "xx" in each so they match the template.
# ---------------------------------------------------------------------------

def _continuous_block(columns: list[dict[str, Any]], indent: str = "    ") -> list[list[str]]:
    cells = _all("xx", columns)
    return [
        _row(f"{indent}n",         cells),
        _row(f"{indent}Mean",      cells),
        _row(f"{indent}SD, SE",    cells),
        _row(f"{indent}Median",    cells),
        _row(f"{indent}Min, Max",  cells),
    ]


# ===========================================================================
# 14.1.1.1 — Subject Disposition  (docx table 5)
# ===========================================================================

def disposition(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    rows: list[list[str]] = []

    # Screened (Total column only — pre-randomisation)
    rows.append(_row("Screened [1]",                                _total_only("xx", columns)))
    rows.append(_row("   Completed Screening",                      _total_only("xx (xx.x)", columns)))
    rows.append(_row("   Screen Failures",                          _total_only("xx (xx.x)", columns)))
    rows.append(_row("      < screen failure reason 1 >",           _total_only("xx (xx.x)", columns)))
    rows.append(_row("      < screen failure reason 2 >",           _total_only("xx (xx.x)", columns)))
    rows.append(blank)

    # Entered Run-in (Total column only)
    rows.append(_row("Entered Run-in [1]",                          _total_only("xx", columns)))
    rows.append(_row("   Completed Run-in",                         _total_only("xx (xx.x)", columns)))
    rows.append(_row("   Run-in Failure",                           _total_only("xx (xx.x)", columns)))
    rows.append(_row("      < run-in failure reason 1 >",           _total_only("xx (xx.x)", columns)))
    rows.append(_row("      < run-in failure reason 2 >",           _total_only("xx (xx.x)", columns)))
    rows.append(blank)

    # Randomized Population — all analysis sets
    rows.append(_row("Randomized Population [1]",                   _all("xx", columns)))
    rows.append(_row("   Intent-To-Treat Set",                      _all("xx (xx.x)", columns)))
    rows.append(_row("   Modified Intent-To-Treat Set",             _all("xx (xx.x)", columns)))
    rows.append(_row("   Full Analysis Set",                        _all("xx (xx.x)", columns)))
    rows.append(_row("   Safety Analysis Set",                      _all("xx (xx.x)", columns)))
    rows.append(_row("   Per-Protocol Analysis Set",                _all("xx (xx.x)", columns)))
    rows.append(blank)

    # Treatment completion / discontinuation
    rows.append(_row("Completed Study Treatment",                   _all("xx (xx.x)", columns)))
    rows.append(_row("   Ongoing Treatment",                        _all("xx (xx.x)", columns)))
    rows.append(_row("   Early Discontinuation from Study Treatment", _all("xx (xx.x)", columns)))
    rows.append(_row("      <reason 1>",                            _all("xx (xx.x)", columns)))
    rows.append(_row("      <reason 2>",                            _all("xx (xx.x)", columns)))
    rows.append(_row("      Other",                                 _all("xx (xx.x)", columns)))
    rows.append(blank)

    # OLE
    rows.append(_row("Participated in OLE",                         _all("xx (xx.x)", columns)))
    rows.append(_row("   Refused Participation in OLE",             _all("xx (xx.x)", columns)))
    rows.append(_row("      <reason 1>",                            _all("xx (xx.x)", columns)))
    rows.append(_row("      <reason 2>",                            _all("xx (xx.x)", columns)))
    return rows


# ===========================================================================
# 14.1.2.1 — Demographics and Baseline Characteristics  (docx table 9)
# ===========================================================================

def randomization_by_country(columns: list[dict[str, Any]]) -> list[list[str]]:
    cells = _all("xx (xx.x)", columns)
    return [
        _row("< country 1 >", _all("", columns)),
        _row("   Investigator 1 (<siteid>)", cells),
        _row("   Investigator 2 (<siteid>)", cells),
        _blank(columns),
        _row("< country 2 >", _all("", columns)),
        _row("   Investigator 1 (<siteid>)", cells),
        _row("   Investigator 2 (<siteid>)", cells),
    ]


def analysis_sets(columns: list[dict[str, Any]]) -> list[list[str]]:
    cells = _all("xx (xx.x)", columns)
    return [
        _row("Safety Analysis Set (SAF)", cells),
        _row("Not Included in the SAF", cells),
        _row("   < reason 1 >", cells),
        _row("   < reason 2 >", cells),
        _blank(columns),
        _row("Intent-To-Treat Set (ITT)", cells),
        _row("Not Included in the ITT", cells),
        _row("   < reason 1 >", cells),
        _row("   < reason 2 >", cells),
    ]


def protocol_deviations(columns: list[dict[str, Any]]) -> list[list[str]]:
    cells = _all("xx (xx.x)", columns)
    rows = [
        _row("Subjects with at Least One Important Protocol Deviation", cells),
        _blank(columns),
    ]
    for cat in (1, 2):
        rows.append(_row(f"Deviation Category #{cat}", cells))
        rows.append(_row(f"   Deviation Subcategory #{cat}.1", cells))
        rows.append(_row(f"   Deviation Subcategory #{cat}.2", cells))
        rows.append(_blank(columns))
    rows.append(_row("...", _all("", columns)))
    return rows


def medical_history(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    cells = _all("xx (xx.x)", columns)
    rows: list[list[str]] = [
        _row("Subjects with Any Medical History", cells),
        blank,
    ]
    for soc in (1, 2):
        rows.append(_row(f"System Organ Class #{soc}", cells))
        for pt in (1, 2, 3):
            rows.append(_row(f"   Preferred Term #{soc}.{pt}", cells))
        rows.append(blank)
    rows.append(_row("...", _all("", columns)))
    return rows


def medications(columns: list[dict[str, Any]], *, prior: bool) -> list[list[str]]:
    label = "Prior" if prior else "Concomitant"
    cells = _all("xx (xx.x)", columns)
    rows = [
        _row(f"Subjects with at Least One {label} Medication", cells),
        _blank(columns),
    ]
    for atc2 in (1, 2):
        rows.append(_row(f"ATC Level 2 Category #{atc2}", cells))
        rows.append(_row(f"   ATC Level 4 Category #{atc2}.1", cells))
        rows.append(_row(f"   ATC Level 4 Category #{atc2}.2", cells))
        rows.append(_blank(columns))
    rows.append(_row("...", _all("", columns)))
    return rows


def baseline(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    rows: list[list[str]] = []

    def cont_block(title: str) -> list[list[str]]:
        return [_row(title, _all("", columns))] + _continuous_block(columns)

    def cat_block(title: str, categories: list[str]) -> list[list[str]]:
        out = [_row(title, _all("", columns))]
        for cat in categories:
            out.append(_row(f"   {cat}", _all("xx (xx.x)", columns)))
        return out

    rows.extend(cont_block("Age (years)"))
    rows.append(blank)
    rows.extend(cat_block("Age Group 1 (years), n (%)",
                          ["Group #1", "Group #2", "..."]))
    rows.append(blank)
    rows.extend(cat_block("Age Group 2 (years), n (%)",
                          ["Group #1", "Group #2", "..."]))
    rows.append(blank)
    rows.extend(cat_block("Sex, n (%)", ["Female", "Male"]))
    rows.append(blank)
    rows.extend(cat_block("Race, n (%)", [
        "American Indian or Alaska Native",
        "Asian",
        "Black or African American",
        "Native Hawaiian or Other Pacific Islander",
        "White",
        "Unknown",
        "Other",
    ]))
    rows.append(blank)
    rows.extend(cat_block("Race Group, n (%)",
                          ["Group #1", "Group #2", "..."]))
    rows.append(blank)
    rows.extend(cat_block("Ethnicity, n (%)",
                          ["Hispanic or Latino", "Not Hispanic or Latino", "Unknown"]))
    rows.append(blank)
    rows.extend(cat_block("Region, n (%)",
                          ["< region 1 >", "< region 2 >", "..."]))
    rows.append(blank)
    rows.extend(cat_block("Country, n (%)",
                          ["< country 1 >", "< country 2 >", "..."]))
    rows.append(blank)
    rows.extend(cont_block("Height (cm)"))
    rows.append(blank)
    rows.extend(cont_block("Weight (kg)"))
    rows.append(blank)
    rows.extend(cont_block("Body Mass Index (kg/m2)"))
    return rows


# ===========================================================================
# 14.1.3.1 — Extent of Exposure  (docx table 13)
# ===========================================================================

def exposure(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    rows: list[list[str]] = []

    rows.append(_row("Duration of Exposure During the Randomized Treatment Period (unit)",
                     _all("", columns)))
    rows.extend(_continuous_block(columns))
    rows.append(blank)

    rows.append(_row("Duration of Exposure During the Randomized Treatment Period, n (%)",
                     _all("", columns)))
    for label in [
        "< xx (unit) (or xx to xx (unit))",
        ">= xx (unit) (or xx to xx (unit))",
        ">= xx (unit) (or xx to xx (unit))",
        ">= xx (unit) (or xx to xx (unit))",
    ]:
        rows.append(_row(f"   {label}", _all("xx (xx.x)", columns)))
    rows.append(blank)

    rows.append(_row("Total Amount of Dose Received (unit)", _all("", columns)))
    rows.extend(_continuous_block(columns))
    rows.append(blank)

    rows.append(_row("Total Number of Dose/Injection Received, n (%)", _all("", columns)))
    for label in [
        "xx (or xx to xx)",
        "xx (or xx to xx)",
        "xx (or xx to xx)",
        "...",
    ]:
        rows.append(_row(f"   {label}", _all("xx (xx.x)", columns)))
    rows.append(blank)

    rows.append(_row("Exposure Gap Due to Interruption", _all("", columns)))
    rows.extend(_continuous_block(columns))
    return rows


# ===========================================================================
# 14.1.3.2 — Treatment Compliance  (docx table 14)
# ===========================================================================

def compliance(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    rows: list[list[str]] = []

    rows.append(_row("Dose Intensity (unit)", _all("", columns)))
    rows.extend(_continuous_block(columns))
    rows.append(blank)

    rows.append(_row("Relative Dose Intensity (%)", _all("", columns)))
    rows.extend(_continuous_block(columns))
    rows.append(blank)

    rows.append(_row("Treatment Compliance (%)", _all("", columns)))
    rows.extend(_continuous_block(columns))
    rows.append(blank)

    rows.append(_row("Treatment Compliance (%)", _all("", columns)))
    for label in ["< 80%", "80 to 120%", "> 120%"]:
        rows.append(_row(f"   {label}", _all("xx (xx.x)", columns)))
    return rows


# ===========================================================================
# 14.3.1.1 — AE Overview  (docx table 15)
# ===========================================================================

def ae_overview(columns: list[dict[str, Any]]) -> list[list[str]]:
    cells = _all("xx (xx.x) xx", columns)
    rows = [
        _row("Any Treatment-Emergent Adverse Events (TEAE)", cells),
        _row("Any Related TEAE",                              cells),
        _row("Any Grade >=3 TEAE",                            cells),
        _row("Any Grade >=3 Related TEAE",                    cells),
        _row("Any Severe TEAE",                               cells),
        _row("Any Serious TEAE",                              cells),
        _row("   Result in Death",                            cells),
        _row("   Life-threatening",                           cells),
        _row("   Hospitalization",                            cells),
        _row("   Congenital Anomaly or Birth Defect",         cells),
        _row("   Significant Disability",                     cells),
        _row("   Other Medically Important Event",            cells),
        _row("Any Serious Related TEAE",                      cells),
        _row("Any TEAE Leading to Discontinuation of Study Drug", cells),
        _row("Any TEAE Leading to Dose Modification of Study Drug", cells),
        _row("   Interruption",                               cells),
        _row("   Dose Reduction",                             cells),
        _row("   Dose Delay",                                 cells),
        _row("   Other",                                      cells),
        _row("Any TEAE Leading to Study Discontinuation",     cells),
        _row("Any TEAE of Special Interest",                  cells),
        _row("Any Related TEAE of Special Interest",          cells),
        _row("Any Fatal TEAE",                                cells),
    ]
    return rows


# ===========================================================================
# AE by SOC and PT  (docx table 16)
# Used by shells 14.3.1.2, 14.3.1.5, 14.3.1.6, 14.3.1.7, 14.3.1.8
# ===========================================================================

def ae_soc_pt(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    cells = _all("xx (xx.x) xx", columns)
    rows: list[list[str]] = []

    rows.append(_row("Subjects with at Least One Treatment-Emergent Adverse Event", cells))
    rows.append(blank)
    for soc in (1, 2):
        rows.append(_row(f"System Organ Class #{soc}", cells))
        for pt in (1, 2, 3):
            rows.append(_row(f"   Preferred Term #{soc}.{pt}", cells))
        rows.append(_row("   ...", cells))
        rows.append(blank)
    rows.append(_row("...", _all("", columns)))
    return rows


# ===========================================================================
# AE by PT only  (docx table 17)
# Used by shells 14.3.1.9, 14.3.1.10, 14.3.1.11_common
# ===========================================================================

def ae_pt_only(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    cells = _all("xx (xx.x) xx", columns)
    rows = [
        _row("Subjects with at Least One Treatment-Emergent Adverse Event", cells),
        blank,
        _row("Preferred Term #1", cells),
        _row("Preferred Term #2", cells),
        _row("Preferred Term #3", cells),
        _row("...",               cells),
    ]
    return rows


# ===========================================================================
# AE of Special Interest by Category and PT  (docx table 18)
# Used by shells 14.3.1.11_aesi, 14.3.1.12
# ===========================================================================

def ae_aesi(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    cells = _all("xx (xx.x) xx", columns)
    rows: list[list[str]] = []
    for cat in (1, 2):
        rows.append(_row(f"AE of Special Interest Category #{cat}", cells))
        rows.append(_row(f"   Preferred Term #{cat}.1", cells))
        rows.append(_row(f"   Preferred Term #{cat}.2", cells))
        rows.append(_row("   ...", cells))
        rows.append(blank)
    rows.append(_row("...", _all("", columns)))
    return rows


# ===========================================================================
# 14.3.1.13 — TEAEs by SOC, PT, and Maximum Severity  (docx table 19)
# ===========================================================================

def ae_severity(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    cells = _all("xx (xx.x)", columns)
    rows: list[list[str]] = []

    def grade_block(parent_indent: str = "") -> list[list[str]]:
        return [_row(f"{parent_indent}   Grade {g}", cells) for g in range(1, 6)]

    rows.append(_row("Subjects with at Least One Treatment-Emergent Adverse Event", cells))
    rows.extend(grade_block())
    rows.append(blank)

    for soc in (1, 2):
        rows.append(_row(f"System Organ Class #{soc}", cells))
        rows.extend(grade_block())
        rows.append(blank)
        for pt in (1, 2):
            rows.append(_row(f"   Preferred Term #{soc}.{pt}", cells))
            rows.extend(grade_block(parent_indent="   "))
            rows.append(blank)
        rows.append(_row("   ...", cells))
        rows.append(blank)
    return rows


# ===========================================================================
# 14.3.1.14 — TEAEs by SOC, PT, and Strongest Relationship  (docx table 20)
# ===========================================================================

def ae_causality(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    cells = _all("xx (xx.x)", columns)
    rows: list[list[str]] = []

    def rel_block(parent_indent: str = "") -> list[list[str]]:
        return [
            _row(f"{parent_indent}   Related",   cells),
            _row(f"{parent_indent}   Unrelated", cells),
        ]

    rows.append(_row("Subjects with at Least One Treatment-Emergent Adverse Event", cells))
    rows.extend(rel_block())
    rows.append(blank)

    for soc in (1, 2):
        rows.append(_row(f"System Organ Class #{soc}", cells))
        rows.extend(rel_block())
        rows.append(blank)
        for pt in (1, 2):
            rows.append(_row(f"   Preferred Term #{soc}.{pt}", cells))
            rows.extend(rel_block(parent_indent="   "))
            rows.append(blank)
        rows.append(_row("   ...", cells))
        rows.append(blank)
    return rows


# ===========================================================================
# 14.3.4.1 / 14.3.4.2 — Clinical Chemistry / Hematology Summary
# (docx table 21)
# 14.3.5.1 — Vital Signs Summary (docx table 24)
# 14.3.6.1 — ECG Summary (docx table 26 — interpretation rows variant)
# ===========================================================================

def labs_summary(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    rows: list[list[str]] = []

    def parameter_block(label: str) -> list[list[str]]:
        out: list[list[str]] = [_row(label, _all("", columns))]
        for visit_label in ["Baseline", "Visit x", "Change from Baseline to Visit x"]:
            out.append(_row(f"   {visit_label}", _all("", columns)))
            out.extend(_continuous_block(columns, indent="      "))
            out.append(blank)
        out.append(_row("   < Repeat for all scheduled visits >", _all("", columns)))
        out.append(blank)
        out.append(_row("   Last Value", _all("", columns)))
        out.extend(_continuous_block(columns, indent="      "))
        out.append(blank)
        out.append(_row("   Change from Baseline to Last Value", _all("", columns)))
        out.extend(_continuous_block(columns, indent="      "))
        out.append(blank)
        return out

    rows.extend(parameter_block("parameter name (unit)"))
    rows.append(_row("< Repeat for all lab parameters >", _all("", columns)))
    return rows


def vitals_summary(columns: list[dict[str, Any]]) -> list[list[str]]:
    # Identical layout to labs_summary in the template (docx 24 vs 21 differ
    # only in titling, which is shell-driven and not part of body rows).
    return labs_summary(columns)


def ecg_summary(columns: list[dict[str, Any]]) -> list[list[str]]:
    """ECG summary (docx table 26): an Interpretation, n (%) categorical block
    at the top followed by the standard continuous-summary parameter block."""
    blank = _blank(columns)
    cells = _all("xx (xx.x)", columns)
    rows: list[list[str]] = []

    rows.append(_row("Interpretation, n (%)", _all("", columns)))
    for visit_label in ["Baseline", "Visit x"]:
        rows.append(_row(f"   {visit_label}", _all("", columns)))
        for cat in ["Normal", "Abnormal Not CS", "Abnormal CS"]:
            rows.append(_row(f"      {cat}", cells))
        rows.append(blank)
    rows.append(_row("   < Repeat for all visits >", _all("", columns)))
    rows.append(blank)

    rows.extend(labs_summary(columns))
    return rows


# ===========================================================================
# 14.3.4.3 / 14.3.4.4 — Abnormality of Chemistry / Hematology (docx table 22)
# ===========================================================================

def labs_abnormality(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    cells = _all("xx (xx.x)", columns)
    rows: list[list[str]] = []

    rows.append(_row("parameter name (unit)", _all("", columns)))
    for visit_label in ["Baseline", "Visit x"]:
        rows.append(_row(f"   {visit_label}", _all("", columns)))
        for cat in ["Normal", "Low", "High", "Missing"]:
            rows.append(_row(f"      {cat}", cells))
        rows.append(blank)
    rows.append(_row("   < Repeat for all scheduled visits >", _all("", columns)))
    rows.append(blank)

    rows.append(_row("   Last Value", _all("", columns)))
    for cat in ["Normal", "Low", "High", "Missing"]:
        rows.append(_row(f"      {cat}", cells))
    rows.append(blank)
    rows.append(_row("< Repeat for all lab parameters >", _all("", columns)))
    return rows


# ===========================================================================
# 14.3.4.5 / 14.3.4.6 — Chemistry / Hematology Specific Levels
# (docx table 23)
# ===========================================================================

def labs_specific_levels(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    cells = _all("xx (xx.x)", columns)
    rows = [
        _row("parameter name (unit)", _all("", columns)),
        _row("   Level 1 (< XXX)", cells),
        _row("   Level 2 (< XXX)", cells),
        _row("   Level 3 (< XXX)", cells),
        blank,
        _row("Repeat for all lab parameters", _all("", columns)),
    ]
    return rows


# ===========================================================================
# 14.3.5.2 — BP Specific Levels  (docx table 25)
# ===========================================================================

def bp_specific_levels(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    cells = _all("xx (xx.x)", columns)
    rows: list[list[str]] = []

    rows.append(_row("Maximum Systolic Blood Pressure (SBP)(mmHg)", _all("", columns)))
    for lvl in ["<90", ">=90", ">=120", ">=140", ">=160", ">=180"]:
        rows.append(_row(f"   {lvl}", cells))
    rows.append(blank)

    rows.append(_row("Maximum Diastolic Blood Pressure (DBP)(mmHg)", _all("", columns)))
    for lvl in ["<60", ">=60", ">=90", ">=110", ">=120"]:
        rows.append(_row(f"   {lvl}", cells))
    rows.append(blank)

    rows.append(_row("Hypotension Levels", _all("", columns)))
    rows.append(_row("   Any SBP <90", cells))
    rows.append(_row("   Any DBP <60", cells))
    return rows


# ===========================================================================
# 14.3.6.2 — QTcF Criteria  (docx table 27)
# ===========================================================================

def qtcf_criteria(columns: list[dict[str, Any]]) -> list[list[str]]:
    blank = _blank(columns)
    cells = _all("xx (xx.x)", columns)
    rows = [
        _row("Maximum QTcF (msec)", _all("", columns)),
        _row("   >= 450", cells),
        _row("   >= 480", cells),
        _row("   >= 500", cells),
        blank,
        _row("Maximum QTcF Change from Baseline", _all("", columns)),
        _row("   >= 30", cells),
        _row("   >= 60", cells),
    ]
    return rows
