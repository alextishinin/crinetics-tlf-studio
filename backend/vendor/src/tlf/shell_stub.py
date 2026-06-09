"""Generate synthetic placeholder ADaM data for SHELL MODE.

When the configured data folder has no ADaM datasets, the pipeline still
needs concrete rows to drive table iteration: one PARAMCD row per
parameter, one SOC row per body system, one visit per timepoint, etc.
This module writes minimal parquet files whose schemas mirror the
CDISCPILOT01 datasets but whose values are placeholder category names
that match the CRO TFL shell template ("Group #1", "System Organ Class
#1", "Preferred Term #1.1", ...).

Combined with ``validator.set_shell_mode(True)``, which makes every
numeric formatter emit ``"xx"`` / ``"xx (xx.x)"`` strings, the resulting
tables render with placeholder structure throughout — same titles,
columns, footnotes, and row layouts as a real run, but with the cell
values redacted to the shell-template format.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import polars as pl

from tlf.config import StudyConfig


# How many synthetic subjects to put behind each treatment arm.  Three is
# enough to make every analysis-set denominator non-zero so the table modules
# don't short-circuit to "No participant meeting the selection criteria".
SUBJECTS_PER_ARM = 3

# Placeholder category names — match the TFL shell template style.
SOC_NAMES = ["System Organ Class #1", "System Organ Class #2", "System Organ Class #3"]
PT_NAMES = ["Preferred Term #{soc}.1", "Preferred Term #{soc}.2"]
SEX_GROUPS = ["Group #1", "Group #2"]
RACE_GROUPS = ["Group #1", "Group #2", "Group #3"]
ETHNIC_GROUPS = ["Group #1", "Group #2"]
AGEGR_LABELS = ["Group #1", "Group #2", "Group #3"]
COUNTRY_GROUPS = ["Country #1", "Country #2"]
REGION_GROUPS = ["Region #1", "Region #2"]
LAB_PARAM_C = [("PARAM1", "Parameter #1 (unit)"), ("PARAM2", "Parameter #2 (unit)")]
LAB_PARAM_H = [("PARAM3", "Parameter #3 (unit)"), ("PARAM4", "Parameter #4 (unit)")]
VS_PARAMS = [
    ("SYSBP", "Systolic Blood Pressure (mmHg)"),
    ("DIABP", "Diastolic Blood Pressure (mmHg)"),
    ("PULSE", "Pulse Rate (beats/min)"),
    ("TEMP",  "Body Temperature (C)"),
    ("WEIGHT", "Weight (kg)"),
    ("HEIGHT", "Height (cm)"),
]
QS_PARAM = ("PARAM1", "Parameter #1 (score)")
TTE_PARAMS = [
    ("TTDISC", "Time to Discontinuation"),
    ("TTDTH",  "Time to Death"),
]
VISITS = [
    ("Baseline", 0),
    ("Visit #1", 1),
    ("Visit #2", 2),
    ("Visit #3", 3),
]


def generate(cfg: StudyConfig, target: Path) -> None:
    """Write every required stub parquet into ``target``."""
    target.mkdir(parents=True, exist_ok=True)

    subjects = _subject_list(cfg)
    _adsl(cfg, subjects).write_parquet(target / "adsl.parquet")
    _adae(subjects).write_parquet(target / "adae.parquet")
    _advs(subjects).write_parquet(target / "advs.parquet")
    _adlb(subjects, LAB_PARAM_C).write_parquet(target / "adlbc.parquet")
    _adlb(subjects, LAB_PARAM_H).write_parquet(target / "adlbh.parquet")
    _adlbhy(subjects).write_parquet(target / "adlbhy.parquet")
    _adqs(subjects).write_parquet(target / "adqsadas.parquet")
    _adqs(subjects).write_parquet(target / "adqscibc.parquet")
    _adqs(subjects).write_parquet(target / "adqsnpix.parquet")
    _adtte(subjects).write_parquet(target / "adtte.parquet")


# ---------------------------------------------------------------------------
# Subject scaffold
# ---------------------------------------------------------------------------

def _subject_list(cfg: StudyConfig) -> list[dict]:
    """Build the master per-subject scaffold reused by every domain."""
    rows: list[dict] = []
    for arm in cfg.treatment_arms:
        for i in range(SUBJECTS_PER_ARM):
            seq = len(rows) + 1
            rows.append({
                "USUBJID": f"CDISCPILOT01-001-{arm.trtpn:03d}{seq:03d}",
                "SUBJID":  f"{arm.trtpn:03d}{seq:03d}",
                "TRTPN":   arm.trtpn,
                "TRTP":    arm.label,
                "TRTAN":   arm.trtpn,
                "TRTA":    arm.label,
                "SEX":     SEX_GROUPS[i % len(SEX_GROUPS)],
                "RACE":    RACE_GROUPS[i % len(RACE_GROUPS)],
                "ETHNIC":  ETHNIC_GROUPS[i % len(ETHNIC_GROUPS)],
                "AGEGR1":  AGEGR_LABELS[i % len(AGEGR_LABELS)],
                "AGEGR1N": (i % len(AGEGR_LABELS)) + 1,
                "AGE":     50 + i,
                "COUNTRY": COUNTRY_GROUPS[i % len(COUNTRY_GROUPS)],
                "REGION":  REGION_GROUPS[i % len(REGION_GROUPS)],
            })
    return rows


# ---------------------------------------------------------------------------
# Per-domain generators.  Every domain is built from the same scaffold so the
# subject IDs / arm assignments stay consistent across joins.
# ---------------------------------------------------------------------------

def _adsl(cfg: StudyConfig, subjects: list[dict]) -> pl.DataFrame:
    base_dt = date(2025, 1, 1)
    rows = []
    for s in subjects:
        rows.append({
            "STUDYID":   cfg.study_id,
            "USUBJID":   s["USUBJID"],
            "SUBJID":    s["SUBJID"],
            "SITEID":    "001",
            "SITEGR1":   "Site #1",
            "COUNTRY":   s["COUNTRY"],
            "REGION":    s["REGION"],
            "ARM":       s["TRTP"],
            "TRT01P":    s["TRTP"],
            "TRT01PN":   s["TRTPN"],
            "TRT01A":    s["TRTA"],
            "TRT01AN":   s["TRTAN"],
            "TRTSDT":    base_dt,
            "TRTEDT":    base_dt + timedelta(days=84),
            "TRTDUR":    84,
            "TRTDURD":   84,
            "AVGDD":     54.0,
            "CUMDOSE":   4536.0,
            "AGE":       s["AGE"],
            "AGEGR1":    s["AGEGR1"],
            "AGEGR1N":   s["AGEGR1N"],
            "AGEU":      "YEARS",
            "RACE":      s["RACE"],
            "RACEN":     1,
            "SEX":       s["SEX"],
            "ETHNIC":    s["ETHNIC"],
            "SAFFL":     "Y",
            "ITTFL":     "Y",
            "EFFFL":     "Y",
            "COMP8FL":   "Y",
            "COMP16FL":  "Y",
            "COMP24FL":  "Y",
            "DISCONFL":  "N",
            "DSRAEFL":   "N",
            "DTHFL":     "N",
            "BMIBL":     27.0,
            "BMIBLGR1":  "Group #1",
            "HEIGHTBL":  170.0,
            "WEIGHTBL":  75.0,
            "EDUCLVL":   12,
            "DISONSDT":  base_dt - timedelta(days=365),
            "DURDIS":    12.0,
            "DURDSGR1":  "Group #1",
            "VISIT1DT":  base_dt,
            "RFSTDTC":   str(base_dt),
            "RFENDTC":   str(base_dt + timedelta(days=84)),
            "VISNUMEN":  4,
            "RFENDT":    base_dt + timedelta(days=84),
            "DCDECOD":   "COMPLETED",
            "DCREASCD":  "Completed",
            "MMSETOT":   25,
        })
    return pl.DataFrame(rows)


def _adae(subjects: list[dict]) -> pl.DataFrame:
    rows = []
    seq = 0
    base_dt = date(2025, 1, 15)
    for s in subjects:
        for si, soc in enumerate(SOC_NAMES, start=1):
            for pt_tmpl in PT_NAMES:
                pt = pt_tmpl.format(soc=si)
                seq += 1
                rows.append({
                    "STUDYID":   "CDISCPILOT01",
                    "SITEID":    "001",
                    "USUBJID":   s["USUBJID"],
                    "TRTA":      s["TRTA"],
                    "TRTAN":     s["TRTAN"],
                    "AGE":       s["AGE"],
                    "AGEGR1":    s["AGEGR1"],
                    "AGEGR1N":   s["AGEGR1N"],
                    "RACE":      s["RACE"],
                    "RACEN":     1,
                    "SEX":       s["SEX"],
                    "SAFFL":     "Y",
                    "TRTSDT":    base_dt,
                    "TRTEDT":    base_dt + timedelta(days=84),
                    "ASTDT":     base_dt + timedelta(days=si),
                    "ASTDTF":    "",
                    "ASTDY":     si,
                    "AENDT":     base_dt + timedelta(days=si + 1),
                    "AENDY":     si + 1,
                    "ADURN":     1.0,
                    "ADURU":     "DAYS",
                    "AETERM":    pt,
                    "AELLT":     pt,
                    "AELLTCD":   1000 + seq,
                    "AEDECOD":   pt,
                    "AEPTCD":    1000 + seq,
                    "AEHLT":     pt,
                    "AEHLTCD":   2000 + seq,
                    "AEHLGT":    soc,
                    "AEHLGTCD":  3000 + si,
                    "AEBODSYS":  soc,
                    "AESOC":     soc,
                    "AESOCCD":   3000 + si,
                    "AESEV":     ["MILD", "MODERATE", "SEVERE"][seq % 3],
                    "AESER":     "N",
                    "AESCAN":    "N",
                    "AESCONG":   "N",
                    "AESDISAB":  "N",
                    "AESDTH":    "N",
                    "AESHOSP":   "N",
                    "AESLIFE":   "N",
                    "AESOD":     "N",
                    "AEREL":     ["NOT RELATED", "RELATED"][seq % 2],
                    "AEACN":     "DOSE NOT CHANGED",
                    "AEOUT":     "RECOVERED/RESOLVED",
                    "AESEQ":     seq,
                    "TRTEMFL":   "Y",
                    "AOCCFL":    "Y",
                    "AOCCSFL":   "Y" if seq % 4 == 0 else "",
                    "AOCCPFL":   "Y",
                    "AOCC02FL":  "Y" if seq % 5 == 0 else "",
                    "AOCC03FL":  "Y" if seq % 7 == 0 else "",
                    "AOCC04FL":  "",
                    "CQ01NAM":   "AESI #1" if seq % 6 == 0 else "",
                    "AOCC01FL":  "Y" if seq % 6 == 0 else "",
                })
    return pl.DataFrame(rows)


def _advs(subjects: list[dict]) -> pl.DataFrame:
    rows = []
    seq = 0
    base_dt = date(2025, 1, 1)
    for s in subjects:
        for pcd, pname in VS_PARAMS:
            for visit, vn in VISITS:
                seq += 1
                rows.append({
                    "STUDYID":  "CDISCPILOT01",
                    "SITEID":   "001",
                    "USUBJID":  s["USUBJID"],
                    "AGE":      s["AGE"],
                    "AGEGR1":   s["AGEGR1"],
                    "AGEGR1N":  s["AGEGR1N"],
                    "RACE":     s["RACE"],
                    "RACEN":    1,
                    "SEX":      s["SEX"],
                    "SAFFL":    "Y",
                    "TRTSDT":   base_dt,
                    "TRTEDT":   base_dt + timedelta(days=84),
                    "TRTP":     s["TRTP"],
                    "TRTPN":    s["TRTPN"],
                    "TRTA":     s["TRTA"],
                    "TRTAN":    s["TRTAN"],
                    "PARAMCD":  pcd,
                    "PARAM":    pname,
                    "PARAMN":   1,
                    "ADT":      base_dt + timedelta(days=vn * 14),
                    "ADY":      vn * 14 + 1,
                    "ATPTN":    1,
                    "ATPT":     "",
                    "AVISIT":   visit,
                    "AVISITN":  vn,
                    "AVAL":     100.0 + vn,
                    "BASE":     100.0,
                    "CHG":      float(vn),
                    "PCHG":     float(vn),
                    "VISITNUM": vn,
                    "VISIT":    visit,
                    "VSSEQ":    seq,
                    "ANL01FL":  "Y",
                    "ABLFL":    "Y" if vn == 0 else "",
                })
    return pl.DataFrame(rows)


def _adlb(subjects: list[dict], params: list[tuple[str, str]]) -> pl.DataFrame:
    rows = []
    seq = 0
    base_dt = date(2025, 1, 1)
    for s in subjects:
        for pcd, pname in params:
            for visit, vn in VISITS:
                seq += 1
                rows.append({
                    "STUDYID":   "CDISCPILOT01",
                    "SUBJID":    s["SUBJID"],
                    "USUBJID":   s["USUBJID"],
                    "TRTP":      s["TRTP"],
                    "TRTPN":     s["TRTPN"],
                    "TRTA":      s["TRTA"],
                    "TRTAN":     s["TRTAN"],
                    "TRTSDT":    base_dt,
                    "TRTEDT":    base_dt + timedelta(days=84),
                    "AGE":       s["AGE"],
                    "AGEGR1":    s["AGEGR1"],
                    "AGEGR1N":   s["AGEGR1N"],
                    "RACE":      s["RACE"],
                    "RACEN":     1,
                    "SEX":       s["SEX"],
                    "COMP24FL":  "Y",
                    "DSRAEFL":   "N",
                    "SAFFL":     "Y",
                    "AVISIT":    visit,
                    "AVISITN":   vn,
                    "ADY":       vn * 14 + 1,
                    "ADT":       base_dt + timedelta(days=vn * 14),
                    "VISIT":     visit,
                    "VISITNUM":  vn,
                    "PARAM":     pname,
                    "PARAMCD":   pcd,
                    "PARAMN":    1,
                    "PARCAT1":   "CHEM" if pcd.endswith("1") or pcd.endswith("2") else "HEM",
                    "AVAL":      5.0 + vn * 0.1,
                    "BASE":      5.0,
                    "CHG":       vn * 0.1,
                    "A1LO":      4.0,
                    "A1HI":      6.0,
                    "R2A1LO":    1.0,
                    "R2A1HI":    2.0,
                    "BR2A1LO":   1.0,
                    "BR2A1HI":   2.0,
                    "ANL01FL":   "Y",
                    "ALBTRVAL":  None,
                    "ANRIND":    ["NORMAL", "HIGH", "LOW"][seq % 3],
                    "BNRIND":    "NORMAL",
                    "ABLFL":     "Y" if vn == 0 else "",
                    "AENTMTFL":  "Y" if vn == max(v for _, v in VISITS) else "",
                    "LBSEQ":     seq,
                    "LBNRIND":   "NORMAL",
                    "LBSTRESN":  5.0 + vn * 0.1,
                })
    return pl.DataFrame(rows)


def _adlbhy(subjects: list[dict]) -> pl.DataFrame:
    """Hy's-law dataset — minimal subset for the DILI figure / table."""
    rows = []
    seq = 0
    base_dt = date(2025, 1, 1)
    params = [("ALT",  "Alanine Aminotransferase (xULN)"),
              ("AST",  "Aspartate Aminotransferase (xULN)"),
              ("BILI", "Total Bilirubin (xULN)")]
    for s in subjects:
        for pcd, pname in params:
            for visit, vn in VISITS:
                seq += 1
                rows.append({
                    "STUDYID":   "CDISCPILOT01",
                    "SUBJID":    s["SUBJID"],
                    "USUBJID":   s["USUBJID"],
                    "TRTP":      s["TRTP"],
                    "TRTPN":     s["TRTPN"],
                    "TRTA":      s["TRTA"],
                    "TRTAN":     s["TRTAN"],
                    "TRTSDT":    base_dt,
                    "TRTEDT":    base_dt + timedelta(days=84),
                    "AGE":       s["AGE"],
                    "AGEGR1":    s["AGEGR1"],
                    "AGEGR1N":   s["AGEGR1N"],
                    "RACE":      s["RACE"],
                    "RACEN":     1,
                    "SEX":       s["SEX"],
                    "COMP24FL":  "Y",
                    "DSRAEFL":   "N",
                    "SAFFL":     "Y",
                    "AVISIT":    visit,
                    "AVISITN":   vn,
                    "ADY":       vn * 14 + 1,
                    "ADT":       base_dt + timedelta(days=vn * 14),
                    "VISIT":     visit,
                    "VISITNUM":  vn,
                    "PARAMTYP":  "",
                    "PARAM":     pname,
                    "PARAMCD":   pcd,
                    "PARAMN":    1,
                    "PARCAT1":   "DILI",
                    "AVAL":      1.0 + vn * 0.1,
                    "BASE":      1.0,
                    "A1LO":      0.5,
                    "A1HI":      1.0,
                    "R2A1LO":    1.0,
                    "R2A1HI":    3.0,
                    "BR2A1LO":   1.0,
                    "BR2A1HI":   3.0,
                    "ABLFL":     "Y" if vn == 0 else "",
                    "SHIFT1":    "Normal to High",
                    "SHIFT1N":   1,
                    "CRIT1":     ">3x ULN",
                    "CRIT1FL":   "N",
                    "CRIT1FN":   0,
                })
    return pl.DataFrame(rows)


def _adqs(subjects: list[dict]) -> pl.DataFrame:
    rows = []
    seq = 0
    base_dt = date(2025, 1, 1)
    pcd, pname = QS_PARAM
    for s in subjects:
        for visit, vn in VISITS:
            seq += 1
            rows.append({
                "STUDYID":   "CDISCPILOT01",
                "SITEID":    "001",
                "SITEGR1":   "Site #1",
                "USUBJID":   s["USUBJID"],
                "TRTSDT":    base_dt,
                "TRTEDT":    base_dt + timedelta(days=84),
                "TRTP":      s["TRTP"],
                "TRTPN":     s["TRTPN"],
                "AGE":       s["AGE"],
                "AGEGR1":    s["AGEGR1"],
                "AGEGR1N":   s["AGEGR1N"],
                "RACE":      s["RACE"],
                "RACEN":     1,
                "SEX":       s["SEX"],
                "ITTFL":     "Y",
                "EFFFL":     "Y",
                "COMP24FL":  "Y",
                "AVISIT":    visit,
                "AVISITN":   vn,
                "VISIT":     visit,
                "VISITNUM":  vn,
                "ADY":       vn * 14 + 1,
                "ADT":       base_dt + timedelta(days=vn * 14),
                "PARAM":     pname,
                "PARAMCD":   pcd,
                "PARAMN":    1,
                "AVAL":      20.0 + vn,
                "BASE":      20.0,
                "CHG":       float(vn),
                "PCHG":      float(vn),
                "ABLFL":     "Y" if vn == 0 else "",
                "ANL01FL":   "Y",
                "DTYPE":     "",
                "AWRANGE":   "",
                "AWTARGET":  vn * 14,
                "AWTDIFF":   0,
                "AWLO":      0,
                "AWHI":      0,
                "AWU":       "DAYS",
                "QSSEQ":     seq,
            })
    return pl.DataFrame(rows)


def _adtte(subjects: list[dict]) -> pl.DataFrame:
    rows = []
    seq = 0
    base_dt = date(2025, 1, 1)
    for s in subjects:
        for pcd, pname in TTE_PARAMS:
            seq += 1
            rows.append({
                "STUDYID":   "CDISCPILOT01",
                "SITEID":    "001",
                "USUBJID":   s["USUBJID"],
                "AGE":       s["AGE"],
                "AGEGR1":    s["AGEGR1"],
                "AGEGR1N":   s["AGEGR1N"],
                "RACE":      s["RACE"],
                "RACEN":     1,
                "SEX":       s["SEX"],
                "TRTSDT":    base_dt,
                "TRTEDT":    base_dt + timedelta(days=84),
                "TRTDUR":    84,
                "TRTP":      s["TRTP"],
                "TRTA":      s["TRTA"],
                "TRTAN":     s["TRTAN"],
                "PARAM":     pname,
                "PARAMCD":   pcd,
                "AVAL":      30.0 + seq,
                "STARTDT":   base_dt,
                "ADT":       base_dt + timedelta(days=30 + seq),
                "CNSR":      seq % 2,
                "EVNTDESC":  "Censored at end of follow-up",
                "SRCDOM":    "ADSL",
                "SRCVAR":    "RFENDT",
                "SRCSEQ":    seq,
                "SAFFL":     "Y",
            })
    return pl.DataFrame(rows)
