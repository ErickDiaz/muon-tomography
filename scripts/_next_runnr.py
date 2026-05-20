"""Imprime el próximo runnr libre leyendo sim/runs.csv.

Estrategia simple: max(runnr existente) + 1. Si el manifest está vacío, empieza
en 1. Lo invoca el Makefile para asignar el ID de cada nueva corrida.

No es seguro frente a races: si dos `make corsika-run` arrancan en paralelo en
el mismo host pueden recibir el mismo runnr. Para nuestro flujo (secuencial,
un host a la vez) basta. Si más adelante hace falta, agregar lockfile sobre
sim/runs.csv con flock.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "sim" / "runs.csv"


def main() -> int:
    if not MANIFEST.exists():
        print(1)
        return 0
    max_runnr = 0
    with MANIFEST.open() as f:
        for row in csv.DictReader(f):
            try:
                r = int(row["runnr"])
            except (KeyError, ValueError, TypeError):
                continue
            if r > max_runnr:
                max_runnr = r
    print(max_runnr + 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
