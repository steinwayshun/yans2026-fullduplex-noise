#!/usr/bin/env python3
"""One annotated waveform per (condition, model), for the listening page.

The page puts the figure first and keeps the prose underneath to a line or two,
so everything the caption used to say is written into the figure instead: the
4 s lead-in that is excluded from scoring, the span of the user's interruption,
the model's name, and the GPT-4o score it received.

Two panels per figure — CH1 is what the model was played, CH2 is what it said —
because the page pairs each figure with the CH1 / CH2 / stereo players for that
same model.

    python make_waves.py            # writes figures/wave_<cond>_<model>.png
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
import torch
import torchaudio

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "projects" / "fdb-exp" / "Full-Duplex-Bench" / "v1_v1.5"
TASK = "synthetic_user_interruption"
SAMPLE = "103"
PREFIX = 4.0

MODELS = {"moshi": ("Moshi", "#2CA02C"),
          "personaplex": ("PersonaPlex", "#FF7F0E"),
          "freezeomni": ("Freeze-Omni", "#1F77B4")}
RATIOS = {"tcar": 0.000, "dkitchen": 0.044, "npark": 0.084, "scafe": 0.131,
          "pstation": 0.216, "pcafeter": 0.361, "omeeting": 0.457, "presto": 0.663}

CONDITIONS = [
    ("clean", "雑音なし（clean）", None),
    ("tcar", "TCAR 0 dB", 0.000),
    ("omeeting", "OMEETING 0 dB", 0.457),
]

plt.rcParams.update({
    "font.family": ["IPAPGothic", "IPAGothic", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "figure.facecolor": "white", "savefig.facecolor": "white",
})


def sample_dir(model: str, cond: str) -> Path:
    base = ROOT / f"dataset_{model}"
    if cond == "clean":
        return base / "v1_0_clean" / TASK / SAMPLE
    return base / f"v1_0_noisy_{cond}" / TASK / "snr_0" / SAMPLE


def envelope(path: Path, points: int = 2000):
    """Peak envelope on a fixed grid — a full 33 s trace at 24 kHz is 800k points."""
    audio, rate = sf.read(str(path), always_2d=True)
    x = audio[:, 0].astype(float)
    duration = len(x) / rate
    edges = np.linspace(0, len(x), points + 1).astype(int)
    peaks = np.array([np.abs(x[a:b]).max() if b > a else 0.0
                      for a, b in zip(edges[:-1], edges[1:])])
    times = np.linspace(0, duration, points)
    return times, peaks, duration


def interrupt_span(sample_id: str) -> tuple[float, float, float]:
    """(speech start, speech end, scoring boundary) on the prefixed timeline.

    interrupt.json's span is the slot the interruption was placed in, not the
    speech itself: for sample 103 it is 3.72 s of which 0.74 s of head and 0.75 s
    of tail are silence.  Shading the whole slot makes the interruption look far
    longer than it sounds, so the band is the VAD span inside it.  The clean
    interrupt.wav is used for every condition — the speech is identical and a VAD
    run on a noisy mix would move with the noise.
    """
    directory = sample_dir("moshi", "clean")
    slot_start, slot_end = json.loads(
        (directory / "interrupt.json").read_text())[0]["timestamp"]
    audio, rate = sf.read(str(directory / "interrupt.wav"), always_2d=True)
    wave = torch.from_numpy(np.ascontiguousarray(audio[:, 0].astype("float32")))
    if rate != 16000:
        wave = torchaudio.functional.resample(wave, rate, 16000)
    from silero_vad import get_speech_timestamps, load_silero_vad
    stamps = get_speech_timestamps(wave, load_silero_vad(), sampling_rate=16000)
    lead = stamps[0]["start"] / 16000 if stamps else 0.0
    tail = stamps[-1]["end"] / 16000 if stamps else (slot_end - slot_start)
    return (slot_start + PREFIX + lead, slot_start + PREFIX + tail, slot_end + PREFIX)


def draw(cond: str, label: str, ratio: float | None, model: str,
         span: tuple[float, float, float], directory_override: Path | None = None) -> None:
    """`cond` names the output file; `directory_override` lets sample set 2 point
    at an SNR the CONDITIONS table above does not enumerate."""
    name, colour = MODELS[model]
    directory = directory_override or sample_dir(model, cond)
    # rating.json exists only where the benchmark scored the sample; a TO=0
    # sample was never sent to the judge, which is itself worth showing.
    rating_path = directory / "rating.json"
    rating = json.loads(rating_path.read_text())["rating"] if rating_path.is_file() else None
    start, end, boundary = span

    t_in, e_in, duration = envelope(directory / "input_full.wav")
    t_out, e_out, _ = envelope(directory / "output_full.wav")

    # Fixed margins rather than tight_layout: the axvspan bands and the
    # transform-based annotations above the axes confuse it, and the title ends
    # up on top of them.
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 2.7), sharex=True,
                             gridspec_kw={"hspace": 0.14})
    # Row labels sit outside the axes: inside, they land on top of the waveform.
    fig.subplots_adjust(left=0.145, right=0.988, top=0.735, bottom=0.185)
    for ax, (times, env, colour_, tag) in zip(axes, [
            (t_in, e_in, "#5c6670", "入力音声（ユーザ）"),
            (t_out, e_out, colour, "出力音声（モデル）")]):
        ax.fill_between(times, -env, env, color=colour_, lw=0)
        ax.axvspan(0, PREFIX, color="#000000", alpha=0.07, lw=0)
        ax.axvspan(start, end, color="#c0392b", alpha=0.13, lw=0)
        top = max(env.max(), 1e-3) * 1.35
        ax.set_ylim(-top, top)
        ax.set_yticks([])
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#c9d0d6")
        ax.text(-0.012, 0.5, tag, transform=ax.transAxes, ha="right", va="center",
                fontsize=9.5, fontweight="bold", color=colour_)
    axes[0].set_xlim(0, duration)

    # Everything the caption would have had to say, written on the figure.
    header = label if ratio is None else f"{label}　狭帯域パワー占有率 {ratio:.3f}"
    fig.text(0.012, 0.975, header, ha="left", va="top", fontsize=10,
             fontweight="bold", color="#1a1a1a")
    if rating is None:
        badge, ink, face = "GPT-4o 採点対象外", "#5c6670", "#eef1f3"
    else:
        good = rating >= 3
        badge = f"GPT-4o {rating} 点"
        ink = "#1f7a3d" if good else "#c0392b"
        face = "#e8f5ec" if good else "#fdecea"
    fig.text(0.988, 0.975, badge, ha="right", va="top",
             fontsize=9.5, fontweight="bold", color=ink,
             bbox=dict(boxstyle="round,pad=0.34", fc=face, ec=ink, lw=0.9))
    # Left-anchored: centred on the 4 s band the label runs off the figure.
    axes[0].text(0.1, 1.06, "4 秒の無音挿入（評価対象外）",
                 transform=axes[0].get_xaxis_transform(), ha="left", va="bottom",
                 fontsize=7.6, color="#5c6670")
    axes[0].text((start + end) / 2, 1.06, "割り込み", color="#c0392b",
                 transform=axes[0].get_xaxis_transform(), ha="center", va="bottom",
                 fontsize=8.2, fontweight="bold")
    for ax in axes:
        ax.axvline(boundary, color="#c0392b", lw=1.1, ls=(0, (4, 2.5)))
    axes[1].text(boundary + 0.25, 1.02, "ここ以降が採点対象", color="#c0392b",
                 transform=axes[1].get_xaxis_transform(), ha="left", va="top",
                 fontsize=7.6)
    axes[1].set_xlabel("時刻 [秒]", fontsize=8.5, labelpad=2)
    axes[1].tick_params(labelsize=8)

    out = HERE / "figures" / f"wave_{cond}_{model}.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  {out.name}  {badge}")


def main() -> None:
    span = interrupt_span(SAMPLE)
    print(f"  割り込み発話 {span[0]:.2f}–{span[1]:.2f} 秒 / 採点開始 {span[2]:.2f} 秒")
    for cond, label, ratio in CONDITIONS:
        for model in MODELS:
            draw(cond, label, ratio, model, span)


if __name__ == "__main__":
    main()
