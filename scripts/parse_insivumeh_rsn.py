#!/usr/bin/env python3
"""Parse data/Vulca_RSN2026.ods (or equivalent INSIVUMEH RSN spreadsheet)
into a clean CSV, deriving the target volcano from the station code
prefix and adding distances to the four target volcanoes of this project.

This is the canonical seismic-network list shared by INSIVUMEH for the
muography collaboration. It complements data/insivumeh_stations.csv
(the scraped meteorological-station map) — RSN coords are the
authoritative ones for the stations we plan to colocate muon detectors
with.

The .ods file is parsed via stdlib zipfile + ElementTree, so no pandas
or odfpy is required (handy when running on an environment that does
not have those installed).

Run:
    python3 scripts/parse_insivumeh_rsn.py
Output:
    data/insivumeh_rsn_stations.csv
"""
import csv
import math
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ODS = REPO_ROOT / "data" / "Vulca_RSN2026.ods"
OUT = REPO_ROOT / "data" / "insivumeh_rsn_stations.csv"

# Target volcanoes of the project (catalogued summit coordinates).
VOLCANOS = {
    "fuego":      (14.473, -90.880),
    "acatenango": (14.501, -90.876),
    "pacaya":     (14.380, -90.601),
    "agua":       (14.466, -90.743),
}

NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text":  "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def volcan_from_code(code: str) -> str:
    """Map RSN station code prefix to the volcano it monitors."""
    c = code.upper()
    if c.startswith("AT"):  return "atitlan"
    if c.startswith("FG"):  return "fuego"
    if c.startswith("PCG"): return "pacaya"
    if c == "SAOB":         return "agua"
    if c.startswith("STG"): return "santiaguito"
    if c.startswith("TC"):  return "tacana"
    return "unknown"


def parse_ods(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as z:
        xml = z.read("content.xml").decode("utf-8")
    root = ET.fromstring(xml)

    rows = []
    for tbl in root.iter(f"{{{NS['table']}}}table"):
        for r in tbl.iter(f"{{{NS['table']}}}table-row"):
            cells = []
            for c in r.iter(f"{{{NS['table']}}}table-cell"):
                txts = [t.text or "" for t in c.iter(f"{{{NS['text']}}}p")]
                cells.append(" ".join(txts).strip())
            if any(cells):
                rows.append(cells)

    # First row is header
    out = []
    for r in rows[1:]:
        if len(r) < 5 or not r[3] or not r[4]:
            continue
        try:
            lat = float(r[3])
            lon = float(r[4])
        except ValueError:
            continue
        out.append({
            "code": r[0],
            "ubicacion": r[1],
            "departamento": r[2],
            "lat": lat,
            "lon": lon,
            "volcano": volcan_from_code(r[0]),
        })
    return out


def main() -> int:
    if not ODS.exists():
        sys.exit(f"ERROR: missing {ODS}")
    stations = parse_ods(ODS)

    # Add distances to each of the 4 project volcanoes
    for s in stations:
        for vname, (vlat, vlon) in VOLCANOS.items():
            s[f"d_{vname}"] = round(haversine_km(s["lat"], s["lon"], vlat, vlon), 3)

    fields = ["code", "volcano", "ubicacion", "departamento", "lat", "lon",
              "d_fuego", "d_acatenango", "d_pacaya", "d_agua"]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in stations:
            w.writerow({k: s[k] for k in fields})
    print(f"Parsed {len(stations)} stations -> {OUT.relative_to(REPO_ROOT)}")

    # Quick report: closest stations per target volcano
    for vname in VOLCANOS:
        nearest = sorted(stations, key=lambda s: s[f"d_{vname}"])[:5]
        print(f"\nClosest 5 to {vname.upper()} ({VOLCANOS[vname][0]}, {VOLCANOS[vname][1]}):")
        for s in nearest:
            print(f"  {s['code']:6s}  {s[f'd_{vname}']:6.2f} km  {s['ubicacion']}  ({s['volcano']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
