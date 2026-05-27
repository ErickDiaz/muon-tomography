#!/usr/bin/env python3
"""Process sim/runs_plan.yaml sequentially.

Designed to run on the simulation server inside a tmux session named
'batch' (launched by `make batch-start`). For each entry in the plan:

  1. Skip if an equivalent run (same volcan + nshow + detector_pos) is
     already in sim/runs.csv with status=ok.
  2. Otherwise dispatch `make corsika-run VOLCAN=<v> DETECTOR_POS=<dp>
     NSHOW=<n>` which assigns RUNNR sequentially and updates the manifest.
  3. Append the result to logs/batch_status.json.

Idempotent: re-running picks up where it left off.

Requires: pyyaml.
"""
import csv
import json
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

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN_FILE = REPO_ROOT / "sim" / "runs_plan.yaml"
RUNS_CSV = REPO_ROOT / "sim" / "runs.csv"
STATUS_FILE = REPO_ROOT / "logs" / "batch_status.json"


def load_plan() -> list[dict]:
    return _load_plan_from_file(PLAN_FILE)


def already_done(entry: dict) -> str | None:
    """Return RUNNR of an existing ok run matching this plan entry, or None."""
    if not RUNS_CSV.exists():
        return None
    with RUNS_CSV.open() as f:
        for row in csv.DictReader(f):
            if (
                row["volcan"] == entry["volcan"]
                and int(row["nshow"]) == int(entry["nshow"])
                and int(row["detector_pos"]) == int(entry["detector_pos"])
                and row["status"] == "ok"
            ):
                return row["runnr"]
    return None


def append_status(record: dict) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(STATUS_FILE.read_text()) if STATUS_FILE.exists() else []
    data.append(record)
    STATUS_FILE.write_text(json.dumps(data, indent=2) + "\n")


def main() -> int:
    plan = load_plan()
    total = len(plan)
    print(f"Batch plan: {total} run(s) from {PLAN_FILE.relative_to(REPO_ROOT)}")

    for i, entry in enumerate(plan, 1):
        v, n, dp = entry["volcan"], entry["nshow"], entry["detector_pos"]
        prefix = f"[{i}/{total}] {v} nshow={n} dp={dp}"

        existing = already_done(entry)
        if existing:
            print(f"{prefix}: skip (already done as RUNNR={existing})")
            continue

        print(f"{prefix}: STARTING at {datetime.now().isoformat(timespec='seconds')}")
        t0 = time.time()
        rc = subprocess.call(
            ["make", "corsika-run",
             f"VOLCAN={v}", f"DETECTOR_POS={dp}", f"NSHOW={n}"],
            cwd=REPO_ROOT,
        )
        dt = int(time.time() - t0)
        status = "ok" if rc == 0 else "failed"

        append_status({
            "volcan": v,
            "nshow": n,
            "detector_pos": dp,
            "status": status,
            "duration_sec": dt,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        print(f"{prefix}: {status} in {dt}s")

    print("Batch complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
