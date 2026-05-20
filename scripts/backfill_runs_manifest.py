"""Reconstruye sim/runs.csv a partir de los DATs presentes en sim/output/.

Se ejecuta una sola vez para registrar los runs históricos en el manifest.
Para runs nuevos, run_and_time.sh appendea filas directamente.

Fuentes que combina:
  - run_header del binario (runnr, nshow, energy range)
  - .lst asociado si sobrevivió (OBSLEV, MAGNET, ATMOD, HE_MODEL)
  - sim/timings.csv si tiene la corrida (started_at, duration_sec, host)
  - Fallback al template del Fuego para los runs paramétricos que perdieron .lst

Uso:
    python scripts/backfill_runs_manifest.py
    python scripts/backfill_runs_manifest.py --dry-run   # solo imprime, no escribe
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sys
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "sim" / "output"
MANIFEST = REPO_ROOT / "sim" / "runs.csv"
TIMINGS = REPO_ROOT / "sim" / "timings.csv"
TEMPLATE = REPO_ROOT / "sim" / "steering" / "fuego_template.inp"

# Fallbacks para runs paramétricos que perdieron su .lst (el .lst único
# se sobreescribe entre corridas paramétricas).
TEMPLATE_FALLBACK = {
    "volcan": "fuego",
    "obslev_cm": 250000.0,
    "magnet_h": 28.6,
    "magnet_v": 30.5,
    "atmod": 1,
    "he_model": 1,
    "notes": "backfill — .lst perdido, valores del template del Fuego",
}

# RUNNR explícitos cuyo origen se conoce
KNOWN_RUNS = {
    1001: {"steering": "fuego_test.inp",  "volcan": "fuego", "notes": "fuego_test (500 showers)"},
    1050: {"steering": None,              "volcan": "fuego", "notes": "fuego intermedio (5k)"},
    1101: {"steering": "fuego_prod.inp",  "volcan": "fuego", "notes": "fuego_prod (50k showers)"},
}


def parse_lst(path: Path) -> dict:
    """Extrae parámetros físicos del .lst de un run."""
    txt = path.read_text(errors="ignore")
    out: dict[str, float | int | str | None] = {}

    m = re.search(r"^\s*RUNNR\s+(\d+)", txt, re.MULTILINE)
    out["runnr"] = int(m.group(1)) if m else None

    m = re.search(r"^\s*NSHOW\s+(\d+)", txt, re.MULTILINE)
    out["nshow"] = int(m.group(1)) if m else None

    m = re.search(r"OBSERVATION LEVEL.*?\n\s*1\s+([\d.+\-Ee]+)\s+([\d.+\-Ee]+)",
                  txt, re.DOTALL)
    if m:
        out["obslev_cm"] = float(m.group(1))

    m = re.search(r"^\s*MAGNET\s+([\d.+\-Ee]+)\s+([\d.+\-Ee]+)", txt, re.MULTILINE)
    if m:
        out["magnet_h"] = float(m.group(1))
        out["magnet_v"] = float(m.group(2))

    m = re.search(r"^\s*ATMOD\s+(\d+)", txt, re.MULTILINE)
    if m:
        out["atmod"] = int(m.group(1))

    # HE model: línea "XXX TREATS HIGH ENERGY HADRONIC INTERACTIONS"
    m = re.search(r"^\s*(\S+)\s+TREATS HIGH ENERGY HADRONIC INTERACTIONS",
                  txt, re.MULTILINE)
    if m:
        name = m.group(1).upper()
        mapping = {"DPMJET": 1, "EPOS": 2, "QGSJET": 3, "QGSJETIII": 3,
                   "SIBYLL": 4}
        out["he_model"] = mapping.get(name)

    return out


def load_run_header(dat_path: Path) -> dict:
    """Lee runnr y nshow del run_header del binario."""
    try:
        from corsikaio import CorsikaParticleFile
    except ImportError:
        return {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with CorsikaParticleFile(str(dat_path)) as f:
            rh = f.run_header
            return {
                "runnr": int(rh["run_number"]),
                "nshow": int(rh["n_showers"]),
            }


def load_timings() -> dict[int, dict]:
    """Indexa timings.csv por RUNNR para hacer match."""
    if not TIMINGS.exists():
        return {}
    out = {}
    with TIMINGS.open() as f:
        for row in csv.DictReader(f):
            try:
                runnr = int(row["runnr"])
            except (KeyError, ValueError):
                continue
            out[runnr] = {
                "started_at": row.get("started_at"),
                "duration_sec": int(row["duration_sec"]) if row.get("duration_sec") else None,
                "host": row.get("host"),
                "status": row.get("status", "ok"),
            }
    return out


def find_matching_lst(runnr: int) -> Path | None:
    """Encuentra el .lst que contenga RUNNR <runnr>. None si no hay."""
    needle = re.compile(rf"^\s*RUNNR\s+{runnr}\b", re.MULTILINE)
    for lst in OUTPUT_DIR.glob("*.lst"):
        if needle.search(lst.read_text(errors="ignore")):
            return lst
    return None


def build_row(dat_path: Path, timings: dict[int, dict]) -> dict:
    hdr = load_run_header(dat_path)
    runnr = hdr.get("runnr")
    if runnr is None:
        # último recurso: parsear del nombre del archivo
        m = re.match(r"DAT0*(\d+)$", dat_path.name)
        if m:
            runnr = int(m.group(1))

    row: dict[str, object] = {
        "runnr": runnr,
        "volcan": "fuego",
        "detector_pos": 1,
        "started_at": None,
        "nshow": hdr.get("nshow"),
        "duration_sec": None,
        "host": None,
        "he_model": None,
        "obslev_cm": None,
        "magnet_h": None,
        "magnet_v": None,
        "atmod": None,
        "status": "ok",
        "steering_snapshot": "",
        "dat_path": str(dat_path.relative_to(REPO_ROOT)),
        "notes": "",
    }

    # 1) Conocidos explícitos
    if runnr in KNOWN_RUNS:
        info = KNOWN_RUNS[runnr]
        row["volcan"] = info["volcan"]
        row["notes"] = info["notes"]

    # 2) .lst si sobrevive
    lst = find_matching_lst(runnr) if runnr is not None else None
    if lst is not None:
        params = parse_lst(lst)
        for k in ("obslev_cm", "magnet_h", "magnet_v", "atmod", "he_model", "nshow"):
            if params.get(k) is not None:
                row[k] = params[k]
        row["steering_snapshot"] = str(lst.relative_to(REPO_ROOT))
    else:
        # 3) Fallback del template (todos los paramétricos perdidos son Fuego)
        for k, v in TEMPLATE_FALLBACK.items():
            if row.get(k) in (None, "") or k == "notes":
                row[k] = v

    # 4) timings.csv
    t = timings.get(runnr, {})
    if t:
        row["started_at"] = t.get("started_at") or row["started_at"]
        row["duration_sec"] = t.get("duration_sec")
        row["host"] = t.get("host")
        row["status"] = t.get("status", "ok")

    # 5) Default started_at desde mtime si nada más lo tiene
    if not row["started_at"]:
        ts = dt.datetime.fromtimestamp(dat_path.stat().st_mtime).astimezone()
        row["started_at"] = ts.isoformat(timespec="seconds")

    return row


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="No escribir runs.csv; solo imprimir filas resultantes")
    args = p.parse_args()

    timings = load_timings()
    dats = sorted(d for d in OUTPUT_DIR.glob("DAT[0-9]*") if d.suffix == "")
    if not dats:
        print("No hay DATs en sim/output/, nada que backfillear.", file=sys.stderr)
        return 1

    rows = [build_row(d, timings) for d in dats]
    rows.sort(key=lambda r: (r["runnr"] or 0))

    fields = [
        "runnr", "volcan", "detector_pos", "started_at", "nshow",
        "duration_sec", "host", "he_model", "obslev_cm", "magnet_h",
        "magnet_v", "atmod", "status", "steering_snapshot", "dat_path",
        "notes",
    ]

    if args.dry_run:
        w = csv.DictWriter(sys.stdout, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
        print(f"\n(dry-run) {len(rows)} filas. No se escribió {MANIFEST}.",
              file=sys.stderr)
        return 0

    # Si el manifest ya tiene runs (que no sean backfill), no pisamos:
    # leemos existentes y mezclamos por runnr.
    existing: list[dict] = []
    if MANIFEST.exists():
        with MANIFEST.open() as f:
            existing = list(csv.DictReader(f))

    existing_runnrs = {int(r["runnr"]) for r in existing if r.get("runnr")}
    new_rows = [r for r in rows if r["runnr"] not in existing_runnrs]

    with MANIFEST.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(existing + new_rows)

    print(f"OK: {len(new_rows)} runs backfilled, {len(existing)} ya estaban. "
          f"Total filas: {len(existing) + len(new_rows)} en {MANIFEST.relative_to(REPO_ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
