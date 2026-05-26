#!/usr/bin/env python3
"""Fetch and parse the INSIVUMEH automated weather stations map.

INSIVUMEH publishes its automated meteorological station network as a Folium
(Python + Leaflet) HTML page embedded in an iframe at:

    https://www.insivumeh.gob.gt/img/estaciones_automaticas_met/

Each station is a Leaflet marker whose popup contains a base64-encoded
HTML iframe with the station name, source/operator, and the latest
reading. There is no public REST/JSON API; this script scrapes the
generated HTML and yields a structured CSV.

Output: data/insivumeh_stations.csv with columns name, fuente, lat, lon.

Also prints, for each of the four target volcanoes of this project,
the subset of stations within 15 km — these are candidate detector
sites for muography deployment in collaboration with INSIVUMEH.

Run periodically (e.g., monthly) to refresh the snapshot; the station
roster changes slowly but new stations do get added.
"""
import argparse
import base64
import csv
import math
import re
import ssl
import sys
import urllib.request
from pathlib import Path

URL = "https://www.insivumeh.gob.gt/img/estaciones_automaticas_met/"

# Project target volcanoes (latitude, longitude)
VOLCANOS = {
    "fuego":      (14.473, -90.880),
    "acatenango": (14.501, -90.876),
    "pacaya":     (14.380, -90.601),
    "agua":       (14.466, -90.743),
}
NEARBY_KM = 15.0

# Folium emits these patterns deterministically per marker
RE_MARKER  = re.compile(r"var marker_(\w+) = L\.marker\(\s*\[([-\d.]+),\s*([-\d.]+)\]")
RE_BIND    = re.compile(r"marker_(\w+)\.bindPopup\(popup_(\w+)\)")
RE_IFRAME  = re.compile(r"popup_(\w+)\.setContent\(i_frame_(\w+)\)")
RE_B64     = re.compile(r"var i_frame_(\w+) = \$\(`<iframe src=\"data:text/html;charset=utf-8;base64,([^\"]+)\"")
RE_NAME    = re.compile(r'<div class="header">([^<]+)</div>')
RE_FUENTE  = re.compile(r'<div class="fuente">Fuente:\s*([^<]+)</div>')


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def fetch_html(url: str) -> str:
    # INSIVUMEH's certificate chain is sometimes incomplete; allow unverified
    # TLS here since we are only reading public coordinates.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(url, context=ctx, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_stations(html: str) -> list[dict]:
    markers: dict[str, dict] = {}
    for m in RE_MARKER.finditer(html):
        markers[m.group(1)] = {"lat": float(m.group(2)), "lon": float(m.group(3))}
    for m in RE_BIND.finditer(html):
        if m.group(1) in markers:
            markers[m.group(1)]["popup_id"] = m.group(2)
    popup_to_iframe = {m.group(1): m.group(2) for m in RE_IFRAME.finditer(html)}
    iframe_b64      = {m.group(1): m.group(2) for m in RE_B64.finditer(html)}

    rows: list[dict] = []
    for info in markers.values():
        name, fuente = "?", "?"
        pid = info.get("popup_id")
        if pid and (iid := popup_to_iframe.get(pid)) and (b64 := iframe_b64.get(iid)):
            try:
                content = base64.b64decode(b64).decode("utf-8", errors="replace")
                if nm := RE_NAME.search(content):    name   = nm.group(1).strip()
                if fm := RE_FUENTE.search(content):  fuente = fm.group(1).strip()
            except Exception:
                pass
        rows.append({"name": name, "fuente": fuente, "lat": info["lat"], "lon": info["lon"]})
    return rows


def write_csv(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "fuente", "lat", "lon"])
        w.writeheader()
        for r in rows:
            w.writerow(r)


def report_nearby(rows: list[dict], radius_km: float) -> None:
    print(f"\nStations within {radius_km:.0f} km of each target volcano:")
    for v, (vlat, vlon) in VOLCANOS.items():
        near = sorted(
            ((r, haversine_km(r["lat"], r["lon"], vlat, vlon)) for r in rows),
            key=lambda x: x[1],
        )
        near = [(r, d) for r, d in near if d <= radius_km]
        print(f"\n- {v.upper()} ({vlat}, {vlon}) -> {len(near)} station(s)")
        print(f"  {'dist[km]':>8}  {'name':30s}  {'source':10s}  coords")
        for r, d in near:
            print(f"  {d:>8.2f}  {r['name']:30s}  {r['fuente']:10s}  ({r['lat']:.4f}, {r['lon']:.4f})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--out", type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "insivumeh_stations.csv",
        help="Output CSV path",
    )
    ap.add_argument(
        "--radius-km", type=float, default=NEARBY_KM,
        help=f"Radius for the nearby-volcano report (default {NEARBY_KM})",
    )
    args = ap.parse_args()

    print(f"Fetching {URL} ...", file=sys.stderr)
    html = fetch_html(URL)
    rows = parse_stations(html)
    print(f"Parsed {len(rows)} stations "
          f"({sum(1 for r in rows if r['name'] != '?')} with identified names)", file=sys.stderr)

    write_csv(rows, args.out)
    print(f"Wrote {args.out}", file=sys.stderr)

    report_nearby(rows, args.radius_km)
    return 0


if __name__ == "__main__":
    sys.exit(main())
