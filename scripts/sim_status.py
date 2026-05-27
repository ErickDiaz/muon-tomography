#!/usr/bin/env python3
"""Terminal dashboard for the multi-volcano batch.

Reads sim/runs_plan.yaml (the declared plan) and sim/runs.csv (the
manifest of completed runs), then renders a rich-formatted table with
status per plan entry. Intended to be run on the server (where the data
lives) — invoked via `make sim-status` or directly.

Flags:
    --watch / -w        auto-refresh every <interval> seconds
    --interval N        refresh interval (default 5)

Requires: pyyaml, rich.
"""
import argparse
import csv
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from _plan_loader import load_plan as _load_plan_from_file
except ImportError:
    sys.exit("ERROR: missing scripts/_plan_loader.py (pyyaml required)")

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
except ImportError:
    sys.exit("ERROR: install rich first (`pip install rich`)")

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN_FILE = REPO_ROOT / "sim" / "runs_plan.yaml"
RUNS_CSV = REPO_ROOT / "sim" / "runs.csv"
OUTPUT_DIR = REPO_ROOT / "sim" / "output"

CORSIKA_IMAGE_PREFIX = "thesis-corsika"
RUNNING_VOLCAN_RE = re.compile(r"/work/sim/steering/(\w+)_run\.inp")


def load_plan() -> list[dict]:
    return _load_plan_from_file(PLAN_FILE)


def load_runs() -> list[dict]:
    if not RUNS_CSV.exists():
        return []
    with RUNS_CSV.open() as f:
        return list(csv.DictReader(f))


def detect_running_run() -> dict | None:
    """Return {'volcan': str, 'container_id': str, 'duration_sec': int|None} if
    a thesis-corsika container is actively running a *_run.inp simulation;
    None otherwise. Identifies the volcano by parsing the container's command
    for the rendered steering file path."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--no-trunc",
             "--format", "{{.Image}}\t{{.Command}}\t{{.ID}}"],
            capture_output=True, text=True, timeout=3, check=False,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None

    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        image, command, container_id = parts[0], parts[1], parts[2]
        if not image.startswith(CORSIKA_IMAGE_PREFIX):
            continue
        m = RUNNING_VOLCAN_RE.search(command)
        if not m:
            continue

        duration_sec: int | None = None
        try:
            inspect = subprocess.run(
                ["docker", "inspect", container_id,
                 "--format", "{{.State.StartedAt}}"],
                capture_output=True, text=True, timeout=2, check=False,
            )
            started_at = inspect.stdout.strip()
            if started_at:
                t0 = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                duration_sec = int((datetime.now(timezone.utc) - t0).total_seconds())
        except (subprocess.SubprocessError, ValueError, FileNotFoundError):
            pass

        return {
            "volcan": m.group(1),
            "container_id": container_id[:12],
            "duration_sec": duration_sec,
        }
    return None


def match_run(entry: dict, runs: list[dict]) -> dict | None:
    matches = [
        r for r in runs
        if r["volcan"] == entry["volcan"]
        and int(r["nshow"]) == int(entry["nshow"])
        and int(r["detector_pos"]) == int(entry["detector_pos"])
    ]
    if not matches:
        return None
    return max(matches, key=lambda r: r.get("started_at", ""))


def dat_size(runnr: str) -> int | None:
    if not runnr:
        return None
    p = OUTPUT_DIR / f"DAT{int(runnr):06d}"
    return p.stat().st_size if p.exists() else None


def fmt_size(b: int | None) -> str:
    if b is None:
        return "—"
    f = float(b)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024:
            return f"{f:.0f} {unit}"
        f /= 1024
    return f"{f:.1f} TB"


def fmt_duration(s) -> str:
    if not s or s in ("", None):
        return "—"
    try:
        s = int(s)
    except (TypeError, ValueError):
        return "—"
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}h{m:02d}m{sec:02d}s" if h else f"{m:02d}'{sec:02d}\""


def status_icon(status: str) -> str:
    return {
        "ok":      "[green]✓ done[/]",
        "failed":  "[red]✗ failed[/]",
        "running": "[yellow]⏳ running[/]",
    }.get(status, f"[dim]{status}[/]")


def build_table() -> Table:
    plan = load_plan()
    runs = load_runs()
    running = detect_running_run()
    table = Table(
        title="CORSIKA multi-volcano batch  —  sim/runs_plan.yaml",
        show_lines=False,
        title_style="bold",
    )
    table.add_column("Volcán", style="bold")
    table.add_column("RUNNR")
    table.add_column("NSHOW", justify="right")
    table.add_column("DET", justify="right")
    table.add_column("Status")
    table.add_column("Duración", justify="right")
    table.add_column("DAT", justify="right")
    table.add_column("Host")

    for entry in plan:
        run = match_run(entry, runs)
        is_running = (
            running is not None
            and running["volcan"] == entry["volcan"]
            and run is None
        )
        if run:
            runnr = run["runnr"]
            row = (
                entry["volcan"],
                runnr,
                str(entry["nshow"]),
                str(entry["detector_pos"]),
                status_icon(run["status"]),
                fmt_duration(run.get("duration_sec")),
                fmt_size(dat_size(runnr)),
                run.get("host") or "—",
            )
        elif is_running:
            row = (
                entry["volcan"],
                f"#{running['container_id']}",
                str(entry["nshow"]),
                str(entry["detector_pos"]),
                "[yellow]⏳ running[/]",
                fmt_duration(running.get("duration_sec")),
                "—",
                "local",
            )
        else:
            row = (
                entry["volcan"],
                "—",
                str(entry["nshow"]),
                str(entry["detector_pos"]),
                "[dim]⏸ queued[/]",
                "—", "—", "—",
            )
        table.add_row(*row)
    return table


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-w", "--watch", action="store_true", help="auto-refresh")
    ap.add_argument("--interval", type=int, default=5, help="refresh interval (s)")
    args = ap.parse_args()

    console = Console()
    if not args.watch:
        console.print(build_table())
        return 0

    with Live(build_table(), console=console, refresh_per_second=1) as live:
        try:
            while True:
                time.sleep(args.interval)
                live.update(build_table())
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
