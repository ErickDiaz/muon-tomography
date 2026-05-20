"""Appendea una fila a sim/runs.csv después de una corrida CORSIKA.

Lee parámetros físicos del .lst recién generado (OBSLEV, MAGNET, ATMOD, HE
model) y los junta con los argumentos pasados por run_and_time.sh.

Uso (lo invoca run_and_time.sh):
    python scripts/_append_run.py \
        --runnr 2901 \
        --volcan fuego \
        --detector-pos 1 \
        --started-at 2026-05-18T12:34:56-06:00 \
        --nshow 10000 \
        --duration-sec 305 \
        --host alcyon \
        --status ok \
        --lst sim/output/fuego_run.lst \
        --dat sim/output/DAT002901 \
        --steering-snapshot logs/lst/002901.lst \
        --notes ""

Si el .lst no existe (caso 'fail' raro), las columnas físicas quedan vacías.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "sim" / "runs.csv"

FIELDS = [
    "runnr", "volcan", "detector_pos", "started_at", "nshow",
    "duration_sec", "host", "he_model", "obslev_cm", "magnet_h",
    "magnet_v", "atmod", "status", "steering_snapshot", "dat_path", "notes",
]


def parse_lst(path: Path) -> dict:
    """Saca OBSLEV, MAGNET, ATMOD, HE model del .lst."""
    out: dict[str, object] = {}
    if not path.exists():
        return out
    txt = path.read_text(errors="ignore")

    m = re.search(r"OBSERVATION LEVEL.*?\n\s*1\s+([\d.+\-Ee]+)\s+([\d.+\-Ee]+)",
                  txt, re.DOTALL)
    if m:
        out["obslev_cm"] = float(m.group(1))

    m = re.search(r"^\s*MAGNET\s+([\d.+\-Ee]+)\s+([\d.+\-Ee]+)",
                  txt, re.MULTILINE)
    if m:
        out["magnet_h"] = float(m.group(1))
        out["magnet_v"] = float(m.group(2))

    m = re.search(r"^\s*ATMOD\s+(\d+)", txt, re.MULTILINE)
    if m:
        out["atmod"] = int(m.group(1))

    m = re.search(r"^\s*(\S+)\s+TREATS HIGH ENERGY HADRONIC INTERACTIONS",
                  txt, re.MULTILINE)
    if m:
        mapping = {"DPMJET": 1, "EPOS": 2, "QGSJET": 3,
                   "QGSJETIII": 3, "SIBYLL": 4}
        out["he_model"] = mapping.get(m.group(1).upper())
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--runnr", type=int, required=True)
    p.add_argument("--volcan", required=True)
    p.add_argument("--detector-pos", type=int, required=True)
    p.add_argument("--started-at", required=True)
    p.add_argument("--nshow", type=int, required=True)
    p.add_argument("--duration-sec", type=int, required=True)
    p.add_argument("--host", required=True)
    p.add_argument("--status", required=True, choices=["ok", "fail"])
    p.add_argument("--lst", required=True, help="Path al .lst (para parsear)")
    p.add_argument("--dat", required=True)
    p.add_argument("--steering-snapshot", default="")
    p.add_argument("--notes", default="")
    args = p.parse_args()

    lst_path = Path(args.lst)
    physical = parse_lst(lst_path)

    row = {
        "runnr": args.runnr,
        "volcan": args.volcan,
        "detector_pos": args.detector_pos,
        "started_at": args.started_at,
        "nshow": args.nshow,
        "duration_sec": args.duration_sec,
        "host": args.host,
        "he_model": physical.get("he_model", ""),
        "obslev_cm": physical.get("obslev_cm", ""),
        "magnet_h": physical.get("magnet_h", ""),
        "magnet_v": physical.get("magnet_v", ""),
        "atmod": physical.get("atmod", ""),
        "status": args.status,
        "steering_snapshot": args.steering_snapshot,
        "dat_path": args.dat,
        "notes": args.notes,
    }

    new_file = not MANIFEST.exists()
    with MANIFEST.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerow(row)

    print(f"manifest: RUNNR={args.runnr} {args.volcan} pos={args.detector_pos} "
          f"NSHOW={args.nshow} status={args.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
