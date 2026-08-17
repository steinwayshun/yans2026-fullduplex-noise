#!/usr/bin/env python3
"""Build sample set 2: audio and per-model waveforms for every extra condition.

Sample set 2 has the same shape as set 1 — per model a waveform, the user track,
the model track and a stereo mix — over two groups:

    A. one noise type (PCAFETER) across all six SNRs
    B. the noise types set 1 had no room for, all at 0 dB

The noisy sample directories ship input_full.wav and output_full.wav but no
stereo_full.wav, so the stereo track is merged here, left = input and
right = model output, matching the files the clean condition already had.

    python make_samples2.py           # writes audio/<key>_*.mp3 and figures/wave_<key>_<model>.png
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_waves as mw  # noqa: E402

ROOT = mw.ROOT
TASK = mw.TASK
SAMPLE = mw.SAMPLE

# key -> (noise code, snr tag on disk)
GROUP_A = [(f"pcafeter_{tag}", "pcafeter", tag) for tag in ("m5", "0", "5", "10", "15", "20")]
GROUP_B = [(code, code, "0") for code in
           ("dkitchen", "npark", "scafe", "pstation", "presto")]
CONDITIONS = GROUP_A + GROUP_B


def directory(model: str, noise: str, tag: str) -> Path:
    return (ROOT / f"dataset_{model}" / f"v1_0_noisy_{noise}" /
            TASK / f"snr_{tag}" / SAMPLE)


def encode(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def export_audio(key: str, noise: str, tag: str) -> None:
    base = directory("moshi", noise, tag)
    encode(["-i", str(base / "input_full.wav"), "-ac", "1", "-ar", "24000",
            "-b:a", "48k", f"audio/{key}_input.mp3"])
    for model in mw.MODELS:
        out = directory(model, noise, tag) / "output_full.wav"
        encode(["-i", str(out), "-ac", "1", "-ar", "24000", "-b:a", "48k",
                f"audio/{key}_{model}.mp3"])
        # Left = what the model heard, right = what it said.
        encode(["-i", str(base / "input_full.wav"), "-i", str(out),
                "-filter_complex", "[0:a][1:a]join=inputs=2:channel_layout=stereo[a]",
                "-map", "[a]", "-ar", "24000", "-b:a", "64k",
                f"audio/{key}_{model}_stereo.mp3"])


def main() -> None:
    span = mw.interrupt_span(SAMPLE)
    print(f"  割り込み発話 {span[0]:.2f}–{span[1]:.2f} 秒 / 採点開始 {span[2]:.2f} 秒")
    for key, noise, tag in CONDITIONS:
        label = f"{noise.upper()} {'−5' if tag == 'm5' else '+' + tag if tag != '0' else '0'} dB"
        ratio = mw.RATIOS[noise]
        export_audio(key, noise, tag)
        for model in mw.MODELS:
            mw.draw(key, label, ratio, model, span,
                    directory_override=directory(model, noise, tag))
        print(f"  {key:14s} {label}")


if __name__ == "__main__":
    main()
