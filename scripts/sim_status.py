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
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("ERROR: install pyyaml first (`pip install pyyaml`)")

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


def load_plan() -> list[dict]:
    cfg = yaml.safe_load(PLAN_FILE.read_text())
    defaults = cfg.get("defaults", {}) or {}
    plan = cfg["plan"]
    for entry in plan:
        for k, v in defaults.items():
            entry.setdefault(k, v)
    return plan


def load_runs() -> list[dict]:
    if not RUNS_CSV.exists():
        return []
    with RUNS_CSV.open() as f:
        return list(csv.DictReader(f))


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
