"""Generate safety figures as PNG image files.

This file creates the configured safety figures from ADaM datasets using
matplotlib. It includes time-to-event curves, adverse-event risk-difference
plots, lab change-from-baseline panels, Hy's Law liver-safety scatterplots,
blood-pressure over-time plots, and baseline-versus-maximum blood-pressure
scatterplots.

The functions save figures into the output directory using the same
study/date naming convention as the table renderer.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl

from tlf.config import ShellRegistry, StudyConfig
from tlf.reader import read_adam
from tlf.renderer import output_filename, purge_prior_outputs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_time_to_disc(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Figure 14.1.1.1 — KM curve for Time to First Dermatologic Event."""
    shell = registry.shell("f_14_1_1_1")
    adtte = read_adam("adtte", cfg.adam_path).collect()
    df = adtte.filter(pl.col("PARAM") == "Time to First Dermatologic Event")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    for arm in cfg.treatment_arms:
        sub = df.filter(pl.col("TRTAN") == arm.trtpn)
        if sub.is_empty():
            continue
        times, surv = _km_estimator(
            sub.select("AVAL").to_series().to_list(),
            sub.select("CNSR").to_series().to_list(),
        )
        ax.step(times, surv, where="post", label=arm.label)
    ax.set_xlabel("Days from First Dose")
    ax.set_ylabel("Probability of Remaining Event-Free")
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.set_title("\n".join([shell["title_line1"], shell["title_line2"], shell["title_line3"]]))

    return _save_figure(fig, cfg, shell["title_line1"], out_dir, run_dt)


def generate_ae_forest(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Figure 14.3.1.1 — TEAE risk-difference forest (pooled active vs placebo).

    Arms and denominators come from the study config + ADSL rather than
    hard-coded CDISCPILOT01 codes: placebo = arms with TRTPN 0 or no target
    daily dose; active = every other arm; Ns = SAFFL='Y' counts per arm.
    """
    shell = registry.shell("f_14_3_1_1")
    adae = read_adam("adae", cfg.adam_path).collect()
    adsl = read_adam("adsl", cfg.adam_path).collect()
    df = adae.filter(pl.col("TRTEMFL") == "Y")

    placebo_trtpns = [
        a.trtpn for a in cfg.treatment_arms
        if a.trtpn == 0 or a.target_daily_dose_mg is None
    ]
    active_trtpns = [a.trtpn for a in cfg.treatment_arms if a.trtpn not in placebo_trtpns]

    saf = adsl.filter(pl.col("SAFFL") == "Y") if "SAFFL" in adsl.columns else adsl
    placebo_n = saf.filter(pl.col("TRT01PN").is_in(placebo_trtpns)).height
    active_n = saf.filter(pl.col("TRT01PN").is_in(active_trtpns)).height

    placebo_subj = (
        df.filter(pl.col("TRTAN").is_in(placebo_trtpns))
          .select(["USUBJID", "AEBODSYS"]).drop_nulls().unique()
    )
    placebo_pct = (
        placebo_subj.group_by("AEBODSYS").agg(pl.len().alias("n"))
        .with_columns((pl.col("n") / max(placebo_n, 1)).alias("p_pbo"))
    )

    active_subj = (
        df.filter(pl.col("TRTAN").is_in(active_trtpns))
          .select(["USUBJID", "AEBODSYS"]).drop_nulls().unique()
    )
    active_pct = (
        active_subj.group_by("AEBODSYS").agg(pl.len().alias("n"))
        .with_columns((pl.col("n") / max(active_n, 1)).alias("p_active"))
    )

    rd = (
        active_pct.join(placebo_pct, on="AEBODSYS", how="full", coalesce=True)
        .with_columns(
            (pl.col("p_active").fill_null(0) - pl.col("p_pbo").fill_null(0)).alias("rd")
        )
        .sort("rd", descending=True)
    )

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    socs = rd.select("AEBODSYS").to_series().to_list()
    rds = rd.select("rd").to_series().to_list()
    fig, ax = plt.subplots(figsize=(9, max(4, 0.3 * len(socs))))
    y = list(range(len(socs)))
    ax.barh(y, rds, color=["#1f77b4" if v > 0 else "#888" for v in rds])
    ax.axvline(0, color="black", lw=0.5)
    ax.set_yticks(y)
    ax.set_yticklabels(socs)
    ax.invert_yaxis()
    ax.set_xlabel("Risk difference (active − placebo)")
    ax.set_title("\n".join([shell["title_line1"], shell["title_line2"], shell["title_line3"]]))
    fig.tight_layout()

    return _save_figure(fig, cfg, shell["title_line1"], out_dir, run_dt)


def generate_lab_cfb(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    domain: str = "adlbc",
    shell_id: str = "f_14_3_4_1",
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Figure 14.3.4.1 / 14.3.4.2 — Mean lab CFB over time, one panel per param."""
    shell = registry.shell(shell_id)
    lab = read_adam(domain, cfg.adam_path).collect().filter(pl.col("ANL01FL") == "Y")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    params = sorted(lab.select("PARAM").drop_nulls().unique().to_series().to_list())
    n = len(params)
    cols = 3
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 2.8 * rows), squeeze=False)
    for i, param in enumerate(params):
        ax = axes[i // cols][i % cols]
        sub = lab.filter(pl.col("PARAM") == param)
        for arm in cfg.treatment_arms:
            asub = sub.filter(pl.col("TRTPN") == arm.trtpn)
            agg = (
                asub.filter(pl.col("CHG").is_not_null())
                    .group_by(["AVISITN", "AVISIT"])
                    .agg(pl.col("CHG").mean().alias("mean_chg"), pl.col("CHG").std(ddof=1).alias("sd_chg"), pl.len().alias("n"))
                    .sort("AVISITN")
            )
            if agg.is_empty():
                continue
            x = agg.select("AVISITN").to_series().to_list()
            y = agg.select("mean_chg").to_series().to_list()
            err = [
                (sd / (nn ** 0.5)) if (sd is not None and nn) else 0
                for sd, nn in zip(agg.select("sd_chg").to_series().to_list(),
                                   agg.select("n").to_series().to_list())
            ]
            ax.errorbar(x, y, yerr=err, marker="o", label=arm.label, capsize=3)
        ax.set_title(param, fontsize=9)
        ax.axhline(0, color="grey", lw=0.5)
    # Hide unused subplots
    for j in range(n, rows * cols):
        axes[j // cols][j % cols].axis("off")
    axes[0][0].legend(loc="best", fontsize=8)
    fig.suptitle("\n".join([shell["title_line1"], shell["title_line2"], shell["title_line3"]]))
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return _save_figure(fig, cfg, shell["title_line1"], out_dir, run_dt)


def generate_hys_law(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Figure 14.3.4.3 — Hy's Law scatter."""
    shell = registry.shell("f_14_3_4_3")
    adlbhy = read_adam("adlbhy", cfg.adam_path).collect()

    # Max ALT / AST per subject as ratio to A1HI; max BILI per subject as
    # ratio to A1HI.
    altast = (
        adlbhy.filter(pl.col("PARAMCD").is_in(["ALT", "AST"]))
              .with_columns((pl.col("AVAL") / pl.col("A1HI")).alias("ratio"))
              .group_by(["USUBJID", "TRTPN"])
              .agg(pl.col("ratio").max().alias("x"))
    )
    bili = (
        adlbhy.filter(pl.col("PARAMCD") == "BILI")
              .with_columns((pl.col("AVAL") / pl.col("A1HI")).alias("ratio"))
              .group_by(["USUBJID", "TRTPN"])
              .agg(pl.col("ratio").max().alias("y"))
    )
    hys_flag = (
        adlbhy.filter((pl.col("PARAMCD") == "HYLAW") & (pl.col("CRIT1FL") == "Y"))
              .select("USUBJID").unique()
              .with_columns(pl.lit(True).alias("is_hys"))
    )
    df = altast.join(bili, on=["USUBJID", "TRTPN"], how="inner").join(hys_flag, on="USUBJID", how="left")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 6))
    normal = df.filter(pl.col("is_hys").is_null())
    flagged = df.filter(pl.col("is_hys") == True)
    if not normal.is_empty():
        ax.scatter(normal["x"], normal["y"], s=20, c="grey", alpha=0.6, label="Other")
    if not flagged.is_empty():
        ax.scatter(flagged["x"], flagged["y"], s=80, facecolors="none", edgecolors="red", linewidths=1.5, label="Potential Hy's Law case")
    ax.axvline(3.0, color="red", linestyle="--", lw=0.8)
    ax.axhline(2.0, color="red", linestyle="--", lw=0.8)
    ax.set_xlabel("Maximum (ALT or AST) / ULN")
    ax.set_ylabel("Maximum Total Bilirubin / ULN")
    ax.legend()
    ax.set_title("\n".join([shell["title_line1"], shell["title_line2"], shell["title_line3"]]))
    fig.tight_layout()
    return _save_figure(fig, cfg, shell["title_line1"], out_dir, run_dt)


def generate_bp_over_time(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Figure 14.3.5.1 — Mean BP over time (SBP and DBP)."""
    shell = registry.shell("f_14_3_5_1")
    advs = read_adam("advs", cfg.adam_path).collect().filter(
        (pl.col("ANL01FL") == "Y") & (pl.col("SAFFL") == "Y")
    )
    advs = advs.filter(pl.col("PARAM").is_in([
        "Systolic Blood Pressure (mmHg)", "Diastolic Blood Pressure (mmHg)",
    ]))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, param in zip(axes, ["Systolic Blood Pressure (mmHg)", "Diastolic Blood Pressure (mmHg)"]):
        sub = advs.filter(pl.col("PARAM") == param)
        for arm in cfg.treatment_arms:
            asub = sub.filter(pl.col("TRTPN") == arm.trtpn)
            agg = (
                asub.group_by(["AVISITN", "AVISIT"])
                    .agg(pl.col("AVAL").mean().alias("mean"), pl.col("AVAL").std(ddof=1).alias("sd"), pl.len().alias("n"))
                    .sort("AVISITN")
            )
            if agg.is_empty():
                continue
            x = agg.select("AVISITN").to_series().to_list()
            y = agg.select("mean").to_series().to_list()
            err = [
                (sd / (nn ** 0.5)) if (sd is not None and nn) else 0
                for sd, nn in zip(agg.select("sd").to_series().to_list(), agg.select("n").to_series().to_list())
            ]
            ax.errorbar(x, y, yerr=err, marker="o", label=arm.label, capsize=3)
        ax.set_title(param)
        ax.set_xlabel("Visit")
        ax.set_ylabel("Mean (± SE)")
        ax.legend(fontsize=8)
    fig.suptitle("\n".join([shell["title_line1"], shell["title_line2"], shell["title_line3"]]))
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    return _save_figure(fig, cfg, shell["title_line1"], out_dir, run_dt)


def generate_bp_baseline_vs_max(
    cfg: StudyConfig,
    registry: ShellRegistry,
    *,
    out_dir: Path | None = None,
    run_dt: datetime | None = None,
) -> Path:
    """Figure 14.3.5.2 — Baseline vs max post-baseline BP scatter."""
    shell = registry.shell("f_14_3_5_2")
    advs = read_adam("advs", cfg.adam_path).collect().filter(
        (pl.col("ANL01FL") == "Y") & (pl.col("SAFFL") == "Y")
    )
    advs = advs.filter(pl.col("PARAM").is_in([
        "Systolic Blood Pressure (mmHg)", "Diastolic Blood Pressure (mmHg)",
    ]))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, param in zip(axes, ["Systolic Blood Pressure (mmHg)", "Diastolic Blood Pressure (mmHg)"]):
        sub = advs.filter(pl.col("PARAM") == param)
        base = sub.filter(pl.col("ABLFL") == "Y").select(["USUBJID", "TRTPN", "AVAL"]).rename({"AVAL": "base"})
        post = (
            sub.filter(pl.col("ABLFL") != "Y")
               .group_by(["USUBJID", "TRTPN"])
               .agg(pl.col("AVAL").max().alias("max_post"))
        )
        merged = base.join(post, on=["USUBJID", "TRTPN"], how="inner")
        if merged.is_empty():
            continue
        for arm in cfg.treatment_arms:
            asub = merged.filter(pl.col("TRTPN") == arm.trtpn)
            if asub.is_empty():
                continue
            x = asub.select("base").to_series().to_list()
            y = asub.select("max_post").to_series().to_list()
            ax.scatter(x, y, label=arm.label, alpha=0.6, s=20)
            if len(x) > 1:
                m, b = np.polyfit(x, y, 1)
                xs = np.linspace(min(x), max(x), 50)
                style = "--" if arm.trtpn == 0 else "-"
                ax.plot(xs, m * xs + b, linestyle=style, alpha=0.7)
        # No-change reference
        lo, hi = ax.get_xlim()
        ax.plot([lo, hi], [lo, hi], color="grey", linestyle=":", lw=0.8)
        ax.set_xlabel(f"Baseline {param}")
        ax.set_ylabel(f"Max Post-baseline {param}")
        ax.set_title(param)
        ax.legend(fontsize=8)
    fig.suptitle("\n".join([shell["title_line1"], shell["title_line2"], shell["title_line3"]]))
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    return _save_figure(fig, cfg, shell["title_line1"], out_dir, run_dt)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _km_estimator(times: list[float], censor: list[int]) -> tuple[list[float], list[float]]:
    """Tiny KM estimator with CNSR=0 meaning event, CNSR=1 meaning censored."""
    events = sorted(set(t for t, c in zip(times, censor) if c == 0))
    n_at_risk = len(times)
    survival = 1.0
    xs = [0.0]
    ys = [1.0]
    for t in events:
        d = sum(1 for tt, c in zip(times, censor) if tt == t and c == 0)
        # number at risk just before t
        nr = sum(1 for tt in times if tt >= t)
        if nr == 0:
            continue
        survival *= (1 - d / nr)
        xs.append(t)
        ys.append(survival)
    return xs, ys


def _save_figure(fig, cfg: StudyConfig, figure_label: str, out_dir: Path | None, run_dt: datetime | None) -> Path:
    """Save a matplotlib figure as PNG to outputs/."""
    base = (out_dir or cfg.output_path).resolve()
    base.mkdir(parents=True, exist_ok=True)
    # Use the figure number from the label (e.g. "Figure 14.1.1.1" -> "14.1.1.1")
    number = figure_label.replace("Figure ", "").strip()
    name = output_filename(cfg.study_id, number, run_dt).replace(".rtf", ".png").replace("_Table_", "_Figure_")
    path = base / name
    purge_prior_outputs(base, path)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return path
