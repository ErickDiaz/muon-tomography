#!/usr/bin/env python3
"""One-shot patcher: rewires notebook 05 to read the detector position from
data/detector_sites.csv and re-center the phi grid on the crater direction.

Replaces:
  - the cell containing `det_x, det_y = 3000.0, 0.0` (hardcoded detector)
  - the cell starting with `theta_deg = np.arange(40.0, 85.5, 0.5)` (fixed phi grid)

Idempotent: re-running detects the new code and skips. Keep the script for
future iterations (e.g., when target_volcan needs to vary).
"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parent.parent / "notebooks" / "05_muograma_dem_fuego.ipynb"

DETECTOR_NEW_SRC = '''# Detector position from the curated INSIVUMEH station roster.
# Edit STATION_NAME / TARGET_VOLCAN to point the muogram at a different site.
STATION_NAME = "Fg16"
TARGET_VOLCAN = "fuego"

import pandas as pd
from pyproj import Transformer

_sites = pd.read_csv(REPO_ROOT / "data" / "detector_sites.csv")
_mask = (_sites["name"] == STATION_NAME) & (_sites["target_volcan"] == TARGET_VOLCAN)
if not _mask.any():
    raise ValueError(f"({STATION_NAME!r}, {TARGET_VOLCAN!r}) not in data/detector_sites.csv")
_site = _sites[_mask].iloc[0]

# Convert station (lat, lon) to detector (det_x, det_y) relative to the
# DEM origin (= crater of the target volcano).
_tx = Transformer.from_crs("EPSG:4326", f"EPSG:{terrain.utm_epsg}", always_xy=True)
_e_utm, _n_utm = _tx.transform(_site["lon"], _site["lat"])
det_x = float(_e_utm - terrain.origin_utm[0])
det_y = float(_n_utm - terrain.origin_utm[1])
det_z_ground = float(terrain.elevation_at(np.array(det_x), np.array(det_y)))
det_z = det_z_ground + 2.0
detector_xyz = (det_x, det_y, det_z)

# Vista de la cima desde el detector
summit_z = terrain.summit_elevation
dx, dy, dz = -det_x, -det_y, summit_z - det_z
dist_horiz = np.hypot(dx, dy)
elev_summit_deg = np.degrees(np.arctan2(dz, dist_horiz))
theta_summit_deg = 90.0 - elev_summit_deg
phi_summit_deg = np.degrees(np.arctan2(dy, dx)) % 360.0

print(f"Station: {_site['name']!r} ({_site['fuente']}) targeting {TARGET_VOLCAN}")
print(f"  Coords (lat, lon): ({_site['lat']:.4f}, {_site['lon']:.4f})")
print(f"  Distance to crater (per roster): {_site['dist_km']:.2f} km")
print(f"Detector en (este, norte, z) = ({det_x:.0f}, {det_y:.0f}, {det_z:.0f}) m")
print(f"  Terreno bajo el detector: {det_z_ground:.0f} m  (detector 2 m arriba)")
print(f"  Distancia horizontal al eje del volcán: {dist_horiz:.0f} m")
print(f"Cima vista desde el detector:")
print(f"  θ = {theta_summit_deg:.1f}°  (elevación = {elev_summit_deg:.1f}°)")
print(f"  φ = {phi_summit_deg:.0f}°  (math convention: 0°=E, 90°=N, 180°=W, 270°=S)")
'''

# The new phi-grid cell: same theta range, but phi centered on the crater
# direction computed from the detector position cell above.
PHI_GRID_NEW_SRC = '''theta_deg = np.arange(40.0, 85.5, 0.5)
# Re-center the azimuth grid on the crater direction (phi_summit_deg, computed
# above from the detector coords). ±60° gives a 120° wedge covering the
# volcanic edifice plus generous open-sky margin on both sides.
_phi_half = 60.0
phi_deg = np.arange(phi_summit_deg - _phi_half, phi_summit_deg + _phi_half + 0.5, 0.5)
theta_rad = np.radians(theta_deg)
phi_rad   = np.radians(phi_deg)
'''


def patch_cell(cell: dict, needle: str, new_src: str) -> bool:
    """Return True if cell matched the needle and was replaced (or already patched)."""
    src = cell.get("source", "")
    if isinstance(src, list):
        joined = "".join(src)
    else:
        joined = src
    if needle not in joined:
        return False
    # Idempotency: if our new source's signature is already there, skip
    if "data/detector_sites.csv" in joined and "_phi_half" not in needle:
        # Detector cell already patched
        return True
    if "_phi_half" in joined and "_phi_half" in needle:
        # Phi cell already patched
        return True
    cell["source"] = new_src.splitlines(keepends=True)
    return True


def main() -> None:
    nb = json.loads(NB.read_text())
    patched = {"detector": False, "phi": False}

    for cell in nb["cells"]:
        if cell.get("cell_type") != "code":
            continue
        # Detector cell signature
        if patch_cell(cell, "det_x, det_y = 3000.0, 0.0", DETECTOR_NEW_SRC):
            patched["detector"] = True
            continue
        # Phi grid cell signature
        joined = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
        if "theta_deg = np.arange(40.0, 85.5, 0.5)" in joined and "phi_deg" in joined:
            if "_phi_half" in joined:
                patched["phi"] = True  # already patched
            else:
                cell["source"] = PHI_GRID_NEW_SRC.splitlines(keepends=True)
                patched["phi"] = True

    NB.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    for k, v in patched.items():
        print(f"  {k}: {'OK' if v else 'NOT FOUND'}")


if __name__ == "__main__":
    main()
