#!/usr/bin/env python3
"""Re-render the metrics-test overview sheets in the page's colours.

sh/plot_fdb_v1_task_overview.py is the canonical plotter and metrics-test checks
two of its outputs byte-for-byte, so it is imported and patched here rather than
edited: the model palette is swapped for the poster's (Moshi green, PersonaPlex
orange, Freeze-Omni blue) and the column heading is reduced to the DEMAND code
on its own, which is how the rest of the page names the noise types.

    python make_overview_figs.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent / "projects" / "fdb-exp"
PYTHON = REPO / "Full-Duplex-Bench" / "v1_v1.5" / ".venv" / "bin" / "python3"
CACHE = REPO / "metrics-test" / "data" / "raw_samples"

# The page's palette, keyed the way plot_fdb_v1_violins.MODEL_COLORS is.
COLOURS = {"Moshi": "#2CA02C", "PersonaPlex": "#FF7F0E", "Freeze-Omni": "#1F77B4"}
DEMAND = ["dkitchen", "dliving", "dwashing", "nfield", "npark", "nriver",
          "ohallway", "omeeting", "ooffice", "pcafeter", "presto", "pstation",
          "scafe", "spsquare", "straffic", "tbus", "tcar", "tmetro"]
TASKS = {"pause_handling": "pause", "backchannel": "backchannel",
         "smooth_turn_taking": "smooth", "user_interruption": "interruption"}

# The column heading is built as an f-string inside the plotter, so the parens
# cannot be patched away at run time; the source is copied with that one line
# rewritten instead, leaving the repo's script untouched.
TITLE_FROM = 'f"{noise_title(noise)} ({noise})", fontsize=12.5,'
TITLE_TO = 'noise.upper(), fontsize=12.5,'

PATCH = '''
import sys
sys.path.insert(0, {sh!r})
sys.path.insert(0, {tmp!r})
import plot_fdb_v1_violins as violins

violins.MODEL_COLORS.update({colours!r})
import patched_overview as overview

overview.MODEL_COLORS.update({colours!r})
sys.exit(overview.main())
'''


def main() -> int:
    sh = REPO / "sh"
    if not PYTHON.exists():
        print(f"venv が見つかりません: {PYTHON}", file=sys.stderr)
        return 1

    source = (sh / "plot_fdb_v1_task_overview.py").read_text(encoding="utf-8")
    assert TITLE_FROM in source, "列見出しの書式が変わっています"

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "plots"
        (Path(tmp) / "patched_overview.py").write_text(
            source.replace(TITLE_FROM, TITLE_TO), encoding="utf-8")
        runner = Path(tmp) / "runner.py"
        runner.write_text(PATCH.format(sh=str(sh), tmp=tmp, colours=COLOURS))
        # Explicit list, not "auto": auto also picks up the legacy MUSAN usgov
        # condition, which is excluded from every other figure on the page.
        argv = [str(PYTHON), str(runner),
                "--raw-samples-dir", str(CACHE),
                "--output-dir", str(out),
                "--conditions", ",".join(DEMAND)]
        result = subprocess.run(argv, cwd=str(sh))
        if result.returncode != 0:
            return result.returncode

        for task, key in TASKS.items():
            source = out / f"{task}_overview.png"
            if not source.exists():
                print(f"  生成されず: {source.name}", file=sys.stderr)
                continue
            for width, suffix in ((2600, ""), (5400, "_large")):
                target = HERE / "figures" / f"scope_{key}_detail{suffix}.png"
                subprocess.run(["convert", str(source), "-resize", f"{width}x",
                                "-strip", "-colors", "255", f"PNG8:{target}"], check=True)
                print(f"  {target.name}  {target.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
