"""Parsers de salida CORSIKA (texto .lst, .long, binario DAT).

Pensado para CORSIKA 7.8050 con CURVED + MUPROD. El formato puede variar
entre versiones / opciones de compilacion; los regex apuntan a fragmentos
estables, pero si CORSIKA cambia el wording habra que ajustar.

Para el archivo binario DAT (output de particulas) se delega a la libreria
`corsikaio` (la trae `corsika-panama` en thesis-corsika; instalar suelta
con `pip install corsikaio` en envs locales).

Uso tipico:
    from analysis.corsika import CorsikaRun

    run = CorsikaRun("sim/output", run_number=1001)
    md = run.lst.metadata()
    avgs = run.lst.particle_averages()           # promedios al obslev
    long = run.long.particles()                  # perfil longitudinal
    muons = run.particles.muons()                # binario DAT, solo muones
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

# CORSIKA particle codes (parcial; ver tabla 4 del manual de CORSIKA).
PARTICLE_NAMES: dict[int, str] = {
    1: "gamma",
    2: "e+",
    3: "e-",
    5: "mu+",
    6: "mu-",
    7: "pi0",
    8: "pi+",
    9: "pi-",
    13: "n",
    14: "p",
    15: "anti-p",
    25: "anti-n",
}

# Masas en reposo en GeV/c^2 (PDG, para las particulas mas comunes).
# Solo necesario para calcular energia desde momento.
PARTICLE_MASSES_GEV: dict[int, float] = {
    1: 0.0,
    2: 5.110e-4,
    3: 5.110e-4,
    5: 0.10566,
    6: 0.10566,
    7: 0.13498,
    8: 0.13957,
    9: 0.13957,
    13: 0.93957,
    14: 0.93827,
    15: 0.93827,
    25: 0.93957,
}

MUON_IDS: tuple[int, int] = (5, 6)


@dataclass
class RunMetadata:
    """Metadatos extraidos del .lst. Campos None si no se encontraron."""

    run_number: int | None = None
    n_showers: int | None = None
    primary_id: int | None = None
    primary_name: str | None = None
    energy_min_gev: float | None = None
    energy_max_gev: float | None = None
    spectral_slope: float | None = None
    theta_min_deg: float | None = None
    theta_max_deg: float | None = None
    phi_min_deg: float | None = None
    phi_max_deg: float | None = None
    obslev_cm: float | None = None
    obslev_gcm2: float | None = None
    corsika_version: str | None = None


class LstFile:
    """Parser del archivo .lst (log ASCII de CORSIKA).

    El log mezcla banner, echo de steering cards, registros por evento y
    tablas resumen. Este parser apunta solo a las secciones mas utiles:
      - metadatos del run (RunMetadata)
      - promedios de particulas al nivel de observacion
    """

    # Patrones simples (clave -> regex). El primer grupo capturado es el valor.
    _SIMPLE_PATTERNS: dict[str, str] = {
        "corsika_version": r"NUMBER OF VERSION\s*:\s*(\S+)",
        "n_showers": r"^\s*NSHOW\s+(\d+)",
        "run_number": r"^\s*RUNNR\s+(\d+)",
        "primary_id": r"PRIMARY PARTICLE IDENTIFICATION IS\s+(\d+)",
        "spectral_slope": r"SLOPE OF PRIMARY SPECTRUM\s*=\s*(\S+)",
        "energy_min_gev": r"LOWER LIMIT CUT-OFF FOR PRIMARY SPECTRUM\s*=\s*(\S+)",
        "energy_max_gev": r"UPPER LIMIT CUT-OFF FOR PRIMARY SPECTRUM\s*=\s*(\S+)",
    }

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._text: str | None = None

    @property
    def text(self) -> str:
        if self._text is None:
            self._text = self.path.read_text()
        return self._text

    def metadata(self) -> RunMetadata:
        md = RunMetadata()
        for attr, pat in self._SIMPLE_PATTERNS.items():
            m = re.search(pat, self.text, re.MULTILINE)
            if not m:
                continue
            raw = m.group(1)
            if attr in ("n_showers", "run_number", "primary_id"):
                setattr(md, attr, int(raw))
            elif attr == "corsika_version":
                md.corsika_version = raw
            else:
                setattr(md, attr, float(raw))

        # Rango angular (formato distinto: "FROM X ... Y DEGREES")
        m = re.search(
            r"THETA OF INCIDENCE CHOSEN FROM\s+([\d.+-Ee]+)\.\.\.\s+([\d.+-Ee]+)\s+DEGREES",
            self.text,
        )
        if m:
            md.theta_min_deg = float(m.group(1))
            md.theta_max_deg = float(m.group(2))
        m = re.search(
            r"PHI\s+OF INCIDENCE CHOSEN FROM\s+([\d.+-Ee]+)\.\.\.\s+([\d.+-Ee]+)\s+DEGREES",
            self.text,
        )
        if m:
            md.phi_min_deg = float(m.group(1))
            md.phi_max_deg = float(m.group(2))

        # Nivel de observacion (tabla con una sola fila para 1 nivel)
        m = re.search(
            r"OBSERVATION LEVEL.*?\n\s*1\s+([\d.+-Ee]+)\s+([\d.+-Ee]+)",
            self.text,
            re.DOTALL,
        )
        if m:
            md.obslev_cm = float(m.group(1))
            md.obslev_gcm2 = float(m.group(2))

        if md.primary_id is not None:
            md.primary_name = PARTICLE_NAMES.get(md.primary_id, f"id={md.primary_id}")
        return md

    def particle_averages(self) -> pd.DataFrame:
        """Promedios por evento al nivel de observacion.

        Returns DataFrame con columnas: particle, mean, std.
        """
        # Cortar el bloque "AVERAGE NUMBER OF PARTICLES PER EVENT" hasta el
        # siguiente bloque 'AVERAGE' o el final.
        m = re.search(
            r"AVERAGE NUMBER OF PARTICLES PER EVENT.*?"
            r"(?=AVERAGE LONGITUDINAL|\Z)",
            self.text,
            re.DOTALL,
        )
        if not m:
            return pd.DataFrame(columns=["particle", "mean", "std"])

        rows = []
        for line in m.group(0).splitlines():
            match = re.match(
                r"\s*NO OF\s+(\S.+?)\s*=\s*([\d.+-Ee]+)\s*\+-\s*([\d.+-Ee]+)",
                line,
            )
            if match:
                rows.append(
                    {
                        "particle": match.group(1).strip(),
                        "mean": float(match.group(2)),
                        "std": float(match.group(3)),
                    }
                )
        return pd.DataFrame(rows)


class LongFile:
    """Parser del archivo .long (perfil longitudinal por shower).

    Formato (CORSIKA 7.8050):
      Por cada shower hay dos bloques consecutivos:
        1. "LONGITUDINAL DISTRIBUTION IN N VERTICAL STEPS OF X G/CM**2 FOR SHOWER M"
           columnas: DEPTH GAMMAS POSITRONS ELECTRONS MU+ MU- HADRONS CHARGED NUCLEI CHERENKOV
        2. "LONGITUDINAL ENERGY DEPOSIT ..."
           columnas: DEPTH GAMMA EM_IONIZ EM_CUT MU_IONIZ MU_CUT HADR_IONIZ HADR_CUT NEUTRINO SUM

    Al final del archivo puede haber un bloque "FIT OF THE HILLAS CURVE"
    que ignoramos aqui.
    """

    _PARTICLE_COLS = [
        "depth",
        "gammas",
        "positrons",
        "electrons",
        "mu+",
        "mu-",
        "hadrons",
        "charged",
        "nuclei",
        "cherenkov",
    ]
    _ENERGY_COLS = [
        "depth",
        "gamma",
        "em_ioniz",
        "em_cut",
        "mu_ioniz",
        "mu_cut",
        "hadr_ioniz",
        "hadr_cut",
        "neutrino",
        "sum",
    ]

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def particles(self) -> pd.DataFrame:
        """Cuentas de particulas por (shower, depth)."""
        return self._parse(
            header_keyword="LONGITUDINAL DISTRIBUTION",
            columns=self._PARTICLE_COLS,
        )

    def energy_deposit(self) -> pd.DataFrame:
        """Energia depositada (GeV) por (shower, depth)."""
        return self._parse(
            header_keyword="LONGITUDINAL ENERGY DEPOSIT",
            columns=self._ENERGY_COLS,
        )

    def _parse(self, header_keyword: str, columns: list[str]) -> pd.DataFrame:
        text = self.path.read_text()
        # Cada bloque empieza con "<header_keyword> ... FOR SHOWER <n>", luego
        # encabezado de columnas (DEPTH ...) y luego N filas numericas hasta
        # el proximo header o EOF.
        block_re = re.compile(
            re.escape(header_keyword)
            + r".*?FOR SHOWER\s+(\d+)\s*\n"
            + r"\s*DEPTH.*?\n"
            + r"(.*?)"
            + r"(?=\n\s*LONGITUDINAL|\n\s*FIT OF THE|\Z)",
            re.DOTALL,
        )

        frames: list[pd.DataFrame] = []
        for match in block_re.finditer(text):
            shower_id = int(match.group(1))
            rows = []
            for line in match.group(2).splitlines():
                parts = line.split()
                if len(parts) != len(columns):
                    continue
                try:
                    rows.append([float(p) for p in parts])
                except ValueError:
                    continue
            if not rows:
                continue
            df = pd.DataFrame(rows, columns=columns)
            df.insert(0, "shower", shower_id)
            frames.append(df)

        if not frames:
            return pd.DataFrame(columns=["shower", *columns])
        return pd.concat(frames, ignore_index=True)


class ParticleFile:
    """Lectura del binario DAT de CORSIKA (output de particulas).

    Delega la I/O del binario a `corsikaio` (la trae `corsika-panama`).
    Sobre eso construimos DataFrames de pandas con derivadas listas:
    energia, angulos cenital y azimutal.

    Convenciones (CORSIKA 7.x, ver manual FZKA 6019 sec 4.3):
      - Componentes de momento (px, py, pz) en GeV/c.
      - pz se almacena como MAGNITUD POSITIVA (la particula siempre va
        hacia abajo en el shower estandar).
      - Posicion (x, y) en cm respecto al eje del primer primario.
      - Tiempo (t) en ns desde el inicio del shower.
      - Angulo cenital theta: 0 = vertical descendente, pi/2 = horizontal.
        Formula: theta = arccos(pz / |p|).
      - Azimut phi: arctan2(py, px), en [-pi, pi].
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _open(self):
        try:
            from corsikaio import CorsikaParticleFile
        except ImportError as exc:
            raise ImportError(
                "ParticleFile requiere `corsikaio`. Instalar con:\n"
                "  pip install corsikaio"
            ) from exc
        return CorsikaParticleFile(str(self.path))

    def run_header(self) -> dict:
        """Header de la corrida (RUNNR, modelo HE, energias, etc.)."""
        with self._open() as f:
            return self._record_to_dict(f.run_header)

    def event_headers(self) -> pd.DataFrame:
        """Header por evento como DataFrame (sin particulas)."""
        rows: list[dict] = []
        with self._open() as f:
            for event in f:
                rows.append(self._record_to_dict(event.header))
        return pd.DataFrame(rows)

    def particles(
        self,
        particle_ids: Iterable[int] | None = None,
        energy_min_gev: float | None = None,
        energy_max_gev: float | None = None,
    ) -> pd.DataFrame:
        """Devuelve DataFrame con todas las particulas filtradas.

        Columnas:
          event, particle_id, px, py, pz, x_cm, y_cm, t_ns,
          energy_gev, theta_rad, phi_rad, weight (si esta en el binario).

        Args:
            particle_ids: si se da, filtra solo estos IDs (ej. (5, 6) para muones).
            energy_min_gev / energy_max_gev: cortes de energia.
        """
        chunks: list[pd.DataFrame] = []
        pid_filter = set(particle_ids) if particle_ids is not None else None

        with self._open() as f:
            for event_idx, event in enumerate(f, start=1):
                arr = getattr(event, "particles", None)
                if arr is None or len(arr) == 0:
                    continue
                df = self._particles_to_df(arr)
                df.insert(0, "event", event_idx)

                if pid_filter is not None:
                    df = df[df["particle_id"].isin(pid_filter)]
                if energy_min_gev is not None:
                    df = df[df["energy_gev"] >= energy_min_gev]
                if energy_max_gev is not None:
                    df = df[df["energy_gev"] <= energy_max_gev]
                if not df.empty:
                    chunks.append(df)

        if not chunks:
            return pd.DataFrame()
        return pd.concat(chunks, ignore_index=True)

    def muons(self, **filters) -> pd.DataFrame:
        """Atajo: solo muones (IDs 5 y 6)."""
        return self.particles(particle_ids=MUON_IDS, **filters)

    @staticmethod
    def _record_to_dict(rec) -> dict:
        """Convierte un numpy record en dict plano."""
        out = {}
        for name in rec.dtype.names:
            value = rec[name]
            try:
                out[name] = value.item()
            except (AttributeError, ValueError):
                out[name] = value.tolist() if hasattr(value, "tolist") else value
        return out

    @staticmethod
    def _particles_to_df(arr) -> pd.DataFrame:
        """Convierte numpy structured array de particulas a DataFrame."""
        # CORSIKA codifica particle_description = id*1000 + hadr_gen*10 + obs_lev.
        desc = arr["particle_description"].astype(np.int64)
        pid = (desc // 1000).astype(np.int32)

        px = arr["px"].astype(np.float64)
        py = arr["py"].astype(np.float64)
        pz = arr["pz"].astype(np.float64)
        p_total = np.sqrt(px**2 + py**2 + pz**2)

        # Energia relativista: E = sqrt(|p|^2 + m^2). Para gammas y leptones
        # ligeros m^2 es despreciable a estas energias; igual lo incluimos.
        masses = np.array(
            [PARTICLE_MASSES_GEV.get(int(p), 0.0) for p in pid], dtype=np.float64
        )
        energy = np.sqrt(p_total**2 + masses**2)

        # Direccion: CORSIKA almacena pz>0 para particulas descendentes
        # (manual FZKA 6019 sec 4.3). theta = arccos(pz/|p|) → 0 vertical,
        # pi/2 horizontal.
        with np.errstate(invalid="ignore", divide="ignore"):
            cos_theta = np.where(p_total > 0, pz / p_total, 1.0)
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
        theta = np.arccos(cos_theta)
        phi = np.arctan2(py, px)

        df = pd.DataFrame(
            {
                "particle_id": pid,
                "px": px,
                "py": py,
                "pz": pz,
                "x_cm": arr["x"].astype(np.float64),
                "y_cm": arr["y"].astype(np.float64),
                "t_ns": arr["t"].astype(np.float64),
                "energy_gev": energy,
                "theta_rad": theta,
                "phi_rad": phi,
            }
        )
        if "weight" in arr.dtype.names:
            df["weight"] = arr["weight"].astype(np.float64)
        return df


@dataclass
class CorsikaRun:
    """Orquestador: dada una carpeta de output, expone .lst, .long y DAT.

    Args:
        output_dir: carpeta con los archivos generados por CORSIKA.
        run_number: si hay varios runs en la misma carpeta, especificar cual.
                    Si es None, toma el primero alfabeticamente.
    """

    output_dir: Path
    run_number: int | None = None
    lst_path: Path | None = field(init=False, default=None)
    dat_path: Path | None = field(init=False, default=None)
    long_path: Path | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        self._resolve_paths()

    def _resolve_paths(self) -> None:
        if self.run_number is not None:
            dat_candidate = self.output_dir / f"DAT{self.run_number:06d}"
            self.dat_path = dat_candidate if dat_candidate.exists() else None
        else:
            dats = sorted(self.output_dir.glob("DAT[0-9]*"))
            # Filtrar .long: queremos solo el binario
            dats = [d for d in dats if d.suffix == ""]
            self.dat_path = dats[0] if dats else None

        if self.dat_path is not None:
            long_candidate = self.dat_path.with_suffix(".long")
            self.long_path = long_candidate if long_candidate.exists() else None

        lsts = sorted(self.output_dir.glob("*.lst"))
        self.lst_path = lsts[0] if lsts else None

    @property
    def has_lst(self) -> bool:
        return self.lst_path is not None and self.lst_path.exists()

    @property
    def has_long(self) -> bool:
        """False si la corrida uso `LONGI F` (no genera .long)."""
        return self.long_path is not None and self.long_path.exists()

    @property
    def has_dat(self) -> bool:
        return self.dat_path is not None and self.dat_path.exists()

    @property
    def lst(self) -> LstFile:
        if not self.has_lst:
            raise FileNotFoundError(f"no se encontro .lst en {self.output_dir}")
        return LstFile(self.lst_path)

    @property
    def long(self) -> LongFile:
        if not self.has_long:
            raise FileNotFoundError(f"no se encontro .long en {self.output_dir}")
        return LongFile(self.long_path)

    @property
    def particles(self) -> ParticleFile:
        if not self.has_dat:
            raise FileNotFoundError(f"no se encontro DAT en {self.output_dir}")
        return ParticleFile(self.dat_path)
