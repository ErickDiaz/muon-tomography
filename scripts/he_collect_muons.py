"""Collect (p, theta) of all muons from the fuego_he_* runs into sim/output/he_muons.npz.

Reads the DAT files in parallel (one process per run). Usage:
    .venv/bin/python scripts/he_collect_muons.py FIRST_RUNNR LAST_RUNNR
"""
import csv
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from analysis.corsika import CorsikaRun  # noqa: E402


def read(runnr):
    m = CorsikaRun(REPO / "sim/output", run_number=runnr).particles.muons()
    p = np.sqrt(m.px ** 2 + m.py ** 2 + m.pz ** 2).to_numpy()
    return p, np.arccos(np.abs(m.pz.to_numpy()) / p)


if __name__ == "__main__":
    first, last = int(sys.argv[1]), int(sys.argv[2])
    runs = list(range(first, last + 1))
    nshow = {int(r["runnr"]): int(r["nshow"]) for r in csv.DictReader(open(REPO / "sim/runs.csv"))
             if r["status"] == "ok"}
    with Pool(len(runs)) as pool:
        out = pool.map(read, runs)
    p = np.concatenate([o[0] for o in out])
    th = np.concatenate([o[1] for o in out])
    nsim = sum(nshow[r] for r in runs)
    np.savez(REPO / "sim/output/he_muons.npz", p=p, theta=th, nsim=nsim)
    print(f"showers {nsim:,} muons {len(p):,} >1TeV {(p > 1e3).sum():,} >3TeV {(p > 3e3).sum():,}")
