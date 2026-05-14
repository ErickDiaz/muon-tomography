"""Fixtures compartidas para los tests del modulo analysis/.

Las fixtures que dependen de archivos reales de CORSIKA hacen `skip` si los
archivos no existen, asi los tests corren sin sim/output/ disponible
(p. ej. en un checkout fresco antes de hacer make sync-output).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def output_dir() -> Path:
    """Carpeta sim/output/ con archivos del test run. Skip si no existe."""
    d = REPO_ROOT / "sim" / "output"
    if not (d / "fuego_test.lst").exists():
        pytest.skip(
            "sim/output/fuego_test.lst no existe. "
            "Correr `make sync-output` antes."
        )
    return d


@pytest.fixture
def lst_path(output_dir: Path) -> Path:
    return output_dir / "fuego_test.lst"


@pytest.fixture
def long_path(output_dir: Path) -> Path:
    p = output_dir / "DAT001001.long"
    if not p.exists():
        pytest.skip("DAT001001.long no existe")
    return p


@pytest.fixture
def dat_path(output_dir: Path) -> Path:
    p = output_dir / "DAT001001"
    if not p.exists():
        pytest.skip("DAT001001 binario no existe")
    return p
