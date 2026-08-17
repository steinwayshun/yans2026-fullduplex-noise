#!/usr/bin/env python3
"""The four Full-Duplex-Bench tasks, averaged over all 18 DEMAND noise types.

These are the measurements that did not make the poster: TOR, latency, frequency
and JSD, which the poster argues are not trustworthy enough to compare
conditions with.  They are published here in full so the claim can be checked.

One figure per task, no figure title — the metric name is the y-axis label, and
the section heading on the page says which task it is.

Metric definition is the same one the poster used (local criteria with the 2.0 s
latency cap), so these line up with the GPT-4o figure next to them.

Backchannel Frequency is the one metric with no per-sample values in the caches
— the extractor only recovers a per-condition scalar — so it is averaged over the
18 noise types unweighted, while everything else pools at the sample level.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "projects" / "fdb-exp" / "poster"))
import poster_data as pd  # noqa: E402

CACHE = HERE.parent / "projects" / "fdb-exp" / "metrics-test" / "data" / "raw_samples"
COLOURS = {"moshi": "#2CA02C", "personaplex": "#FF7F0E", "freezeomni": "#1F77B4"}

TASKS = [
    ("pause", [("pause_synthetic_tor", "Synthetic TOR ↓"),
               ("pause_candor_tor", "CANDOR TOR ↓")]),
    ("backchannel", [("backchannel_tor", "TOR ↓"),
                     ("backchannel_freq", "Frequency ↑"),
                     ("backchannel_jsd", "JSD ↓")]),
    ("smooth", [("smooth_candor_tor", "TOR ↑"),
                ("smooth_latency", "Latency [s] ↓")]),
    ("interruption", [("user_interruption_tor", "TOR ↑"),
                      ("user_interruption_latency", "Latency [s] ↓"),
                      ("user_interruption_gpt4o", "GPT-4o Score ↑")]),
]


def aggregate_scalar(model: str, condition: str, metric: str) -> float | None:
    """Backchannel Frequency lives in aggregate_only_metrics, not in metrics."""
    path = CACHE / model / f"{condition}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text()).get("aggregate_only_metrics", {}).get(metric)


def series(model: str, metric: str, noises: list[str]):
    """(values per SNR, clean value); pooled per sample unless scalar-only."""
    if metric == "backchannel_freq":
        values = []
        for snr in pd.SNRS:
            per = [aggregate_scalar(model, pd.cond_name(n, snr), metric) for n in noises]
            per = [v for v in per if v is not None]
            values.append(float(np.mean(per)) if per else None)
        return values, aggregate_scalar(model, "clean", metric)
    return ([pd.pooled(model, metric, snr, noises)[0] for snr in pd.SNRS],
            pd.clean_value(model, metric))


def draw(task: str, metrics, noises: list[str]) -> None:
    width = 2.55 * len(metrics) + 0.5
    fig, axes = plt.subplots(1, len(metrics), figsize=(width, 2.35))
    axes = np.atleast_1d(axes)
    clean_x = len(pd.SNRS) + 0.9
    xs = np.arange(len(pd.SNRS))

    for ax, (metric, label) in zip(axes, metrics):
        for model in pd.MODELS:
            colour = COLOURS[model]
            values, clean = series(model, metric, noises)
            ax.plot(xs, values, color=colour, marker="o", ms=3.4, lw=1.6,
                    label=pd.MODEL_LABEL[model], zorder=3)
            if clean is not None:
                ax.axhline(clean, color=colour, ls=(0, (4, 3)), lw=0.9, alpha=0.7, zorder=1)
                ax.plot([clean_x], [clean], marker="D", ms=4.2, color=colour,
                        mec="white", mew=0.7, zorder=4)
        ax.axvline(len(pd.SNRS) - 0.5 + 0.7, color="0.6", lw=0.8, ls=":")
        ax.set_xticks(list(xs) + [clean_x])
        ax.set_xticklabels([str(v) for v in pd.SNRS] + ["clean"])
        ax.set_xlim(-0.4, clean_x + 0.5)
        ax.set_xlabel("SNR [dB]")
        # Arrow above the panel, not on the y axis: rotated 90 degrees its
        # direction is hard to read at a glance.
        ax.set_ylabel(label.rstrip(" ↑↓"))
        ax.set_title(label, fontsize=10, pad=5)
        ax.yaxis.set_major_locator(plt.MaxNLocator(5))
        ax.grid(alpha=0.25, lw=0.5)
        ax.set_axisbelow(True)
    axes[0].legend(loc="best", framealpha=0.9, handlelength=1.2,
                   borderpad=0.3, labelspacing=0.2)
    fig.tight_layout(pad=0.3, w_pad=1.0)
    out = HERE / "figures" / f"scope_{task}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  {out.name}  ({len(metrics)} 指標)")


def draw_detail(task: str, metrics, noises: list[str]) -> None:
    """Every noise type kept separate: one heat map per metric.

    Rows are the 18 DEMAND recordings in D/N/O/P/S/T order, columns the six SNRs,
    and the cell is the condition's value minus its clean baseline, signed so
    warmer always means worse.  Each metric gets its own colour scale — they are
    rates, seconds and a JSD, and one shared scale would flatten most of them.
    """
    rows = [c for _, codes in pd.CATEGORIES for c in codes]
    width = 2.35 * len(metrics) + 1.25
    fig, axes = plt.subplots(len(pd.MODELS), len(metrics),
                             figsize=(width, 1.55 * len(pd.MODELS) + 1.5),
                             squeeze=False)
    for col, (metric, label) in enumerate(metrics):
        grids = {}
        for model in pd.MODELS:
            clean = (aggregate_scalar(model, "clean", metric)
                     if metric == "backchannel_freq" else pd.clean_value(model, metric))
            grid = np.full((len(rows), len(pd.SNRS)), np.nan)
            for r, code in enumerate(rows):
                for c, snr in enumerate(pd.SNRS):
                    name = pd.cond_name(code, snr)
                    value = (aggregate_scalar(model, name, metric)
                             if metric == "backchannel_freq"
                             else pd.condition_value(model, name, metric))
                    if value is not None and clean is not None:
                        grid[r, c] = pd.degradation(clean, value,
                                                    pd.is_higher_better(metric)
                                                    if metric in pd.METRICS else True)
            grids[model] = grid
        limit = np.nanmax(np.abs(np.stack(list(grids.values())))) or 1.0
        for row, model in enumerate(pd.MODELS):
            ax = axes[row][col]
            ax.set_facecolor("0.88")
            image = ax.imshow(grids[model], cmap="RdYlBu_r", vmin=-limit, vmax=limit,
                              aspect="auto", interpolation="nearest")
            ax.set_xticks(range(len(pd.SNRS)))
            ax.set_xticklabels(pd.SNRS if row == len(pd.MODELS) - 1 else [])
            ax.set_yticks(range(len(rows)))
            ax.set_yticklabels([pd.NOISE_LABEL[c] for c in rows] if col == 0 else [],
                               fontsize=5.6)
            boundary = -0.5
            for _, codes in pd.CATEGORIES[:-1]:
                boundary += len(codes)
                ax.axhline(boundary, color="white", lw=0.8)
            if row == 0:
                ax.set_title(label, fontsize=9)
            if col == len(metrics) - 1:
                bar = fig.colorbar(image, ax=ax, fraction=0.05, pad=0.03)
                bar.ax.tick_params(labelsize=6)
            if col == 0:
                ax.text(-0.32, 0.5, pd.MODEL_LABEL[model], transform=ax.transAxes,
                        rotation=90, ha="center", va="center", fontsize=8.5,
                        fontweight="bold", color=COLOURS[model])
            if row == len(pd.MODELS) - 1:
                ax.set_xlabel("SNR [dB]", fontsize=8.5)
            ax.grid(False)
    fig.suptitle("clean からの悪化量（暖色ほど悪化）", fontsize=8.5, color="0.35", y=0.995)
    fig.tight_layout(rect=(0.02, 0, 1, 0.975))
    out = HERE / "figures" / f"scope_{task}_detail.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  {out.name}")


def main() -> None:
    plt.rcParams.update({
        "font.family": ["IPAPGothic", "IPAGothic", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "font.size": 9, "axes.labelsize": 9.5, "legend.fontsize": 8,
        "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
        "figure.facecolor": "white", "savefig.facecolor": "white",
    })
    noises = pd.common_noises()
    print(f"雑音 {len(noises)} 種を平均")
    for task, metrics in TASKS:
        draw(task, metrics, noises)
        draw_detail(task, metrics, noises)


if __name__ == "__main__":
    main()
