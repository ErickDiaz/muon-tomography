"""Tests del modulo analysis.corsika."""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analysis.corsika import (
    PARTICLE_NAMES,
    CorsikaRun,
    LongFile,
    LstFile,
    RunMetadata,
)


# ---------------------------------------------------------------------------
# Unit tests de regex (sin I/O, pruebas con strings inline)
# ---------------------------------------------------------------------------

class TestLstRegexes:
    """Verifica que los patrones de LstFile machean strings tipicos."""

    def test_simple_patterns_match(self, tmp_path: Path):
        sample = (
            " NUMBER OF VERSION :  7.8050\n"
            "RUNNR   1001\n"
            "NSHOW   500\n"
            " PRIMARY PARTICLE IDENTIFICATION IS           14\n"
            "      SLOPE OF PRIMARY SPECTRUM                = -2.7000E+00\n"
            "      LOWER LIMIT CUT-OFF FOR PRIMARY SPECTRUM =  1.0000E+01 GEV\n"
            "      UPPER LIMIT CUT-OFF FOR PRIMARY SPECTRUM =  1.0000E+05 GEV\n"
            " THETA OF INCIDENCE CHOSEN FROM       0.00...     89.00 DEGREES\n"
            " PHI   OF INCIDENCE CHOSEN FROM       0.00...    360.00 DEGREES\n"
            " OBSERVATION LEVEL # IN  CM    AND IN   G/CM**2 \n"
            "          1       2.00000000E+05       8.13299992E+02\n"
        )
        p = tmp_path / "stub.lst"
        p.write_text(sample)
        md = LstFile(p).metadata()

        assert md.corsika_version == "7.8050"
        assert md.run_number == 1001
        assert md.n_showers == 500
        assert md.primary_id == 14
        assert md.primary_name == "p"
        assert md.spectral_slope == pytest.approx(-2.7)
        assert md.energy_min_gev == pytest.approx(10.0)
        assert md.energy_max_gev == pytest.approx(1.0e5)
        assert md.theta_min_deg == pytest.approx(0.0)
        assert md.theta_max_deg == pytest.approx(89.0)
        assert md.phi_min_deg == pytest.approx(0.0)
        assert md.phi_max_deg == pytest.approx(360.0)
        assert md.obslev_cm == pytest.approx(2.0e5)
        assert md.obslev_gcm2 == pytest.approx(813.3, abs=1.0)

    def test_metadata_missing_fields_become_none(self, tmp_path: Path):
        """Un .lst incompleto no debe crashear: campos faltantes quedan en None."""
        sample = "RUNNR   1001\nNSHOW   500\n"
        p = tmp_path / "incomplete.lst"
        p.write_text(sample)
        md = LstFile(p).metadata()
        assert md.run_number == 1001
        assert md.n_showers == 500
        assert md.primary_id is None
        assert md.theta_min_deg is None
        assert md.obslev_cm is None

    def test_particle_averages_parses_block(self, tmp_path: Path):
        sample = (
            "X X X\n"
            " AVERAGE NUMBER OF PARTICLES PER EVENT :\n"
            " FROM LEVEL NUMBER                    1\n"
            " HEIGHT IN CM                     2.000E+05\n"
            " HEIGHT IN G/CM**2                8.133E+02\n"
            " NO OF GAMMAS       =  4.460000E-01 +- 2.088014E+00 \n"
            " NO OF MU +         =           0.1 +-          0.6 \n"
            " NO OF MU -         =           0.1 +-          0.3 \n"
            "\n"
            " AVERAGE LONGITUDINAL PARTICLE DISTRIBUTION ...\n"
        )
        p = tmp_path / "stub.lst"
        p.write_text(sample)
        df = LstFile(p).particle_averages()
        assert isinstance(df, pd.DataFrame)
        assert set(df.columns) == {"particle", "mean", "std"}
        particles = set(df["particle"])
        assert "GAMMAS" in particles
        assert "MU +" in particles
        assert "MU -" in particles
        gamma_row = df[df["particle"] == "GAMMAS"].iloc[0]
        assert gamma_row["mean"] == pytest.approx(0.446)


# ---------------------------------------------------------------------------
# Particle naming
# ---------------------------------------------------------------------------

class TestParticleNames:
    """Sanidad sobre los IDs."""

    def test_proton(self):
        assert PARTICLE_NAMES[14] == "p"

    def test_muons(self):
        assert PARTICLE_NAMES[5] == "mu+"
        assert PARTICLE_NAMES[6] == "mu-"

    def test_gamma(self):
        assert PARTICLE_NAMES[1] == "gamma"


# ---------------------------------------------------------------------------
# Integration tests sobre sim/output/ (saltean si falta el data)
# ---------------------------------------------------------------------------

class TestLstFileReal:
    def test_metadata_primary(self, lst_path: Path):
        md = LstFile(lst_path).metadata()
        # PRMPAR fix: debe ser proton, no gamma
        assert md.primary_id == 14
        assert md.primary_name == "p"
        assert md.corsika_version == "7.8050"
        assert md.n_showers == 500

    def test_metadata_geometry(self, lst_path: Path):
        md = LstFile(lst_path).metadata()
        assert md.obslev_cm == pytest.approx(2.0e5)
        assert 0 <= md.theta_min_deg <= md.theta_max_deg <= 90

    def test_particle_averages_has_muons(self, lst_path: Path):
        avgs = LstFile(lst_path).particle_averages()
        assert (avgs["particle"] == "MU +").any()
        assert (avgs["particle"] == "MU -").any()


class TestLongFileReal:
    def test_particles_grid_shape(self, long_path: Path):
        df = LongFile(long_path).particles()
        # 500 showers × 41 bins de profundidad
        assert df["shower"].nunique() == 500
        assert df["depth"].nunique() == 41
        assert len(df) == 500 * 41

    def test_particles_columns(self, long_path: Path):
        df = LongFile(long_path).particles()
        expected = {"shower", "depth", "gammas", "positrons", "electrons",
                    "mu+", "mu-", "hadrons", "charged", "nuclei", "cherenkov"}
        assert expected.issubset(set(df.columns))

    def test_particles_no_negative_counts(self, long_path: Path):
        df = LongFile(long_path).particles()
        numeric = df.drop(columns=["shower", "depth"])
        assert (numeric >= 0).all().all()

    def test_energy_deposit_shape(self, long_path: Path):
        df = LongFile(long_path).energy_deposit()
        assert df["shower"].nunique() == 500


class TestCorsikaRunReal:
    def test_finds_all_files(self, output_dir: Path):
        run = CorsikaRun(output_dir, run_number=1001)
        assert run.has_lst
        assert run.has_long
        assert run.has_dat

    def test_missing_run_number_graceful(self, output_dir: Path):
        run = CorsikaRun(output_dir, run_number=999999)
        assert not run.has_dat
        assert not run.has_long
        with pytest.raises(FileNotFoundError):
            _ = run.particles

    def test_auto_select_first_run(self, output_dir: Path):
        run = CorsikaRun(output_dir)  # sin run_number
        assert run.dat_path is not None


# ---------------------------------------------------------------------------
# Tests del binario DAT (requieren corsikaio + archivo real)
# ---------------------------------------------------------------------------

class TestParticleFileReal:
    """Tests del wrapper de corsikaio. Skipean si corsikaio no instalado."""

    @pytest.fixture(autouse=True)
    def _require_corsikaio(self):
        pytest.importorskip("corsikaio")

    def test_muons_are_muons(self, dat_path: Path):
        from analysis.corsika import ParticleFile
        muons = ParticleFile(dat_path).muons()
        if muons.empty:
            pytest.skip("0 muones en el binario — re-correr simulacion")
        assert set(muons["particle_id"].unique()) <= {5, 6}

    def test_theta_in_valid_range(self, dat_path: Path):
        """Despues del fix de signo: theta_rad debe estar en [0, pi/2] para
        particulas descendentes (la convencion de CORSIKA garantiza pz>=0)."""
        from analysis.corsika import ParticleFile
        muons = ParticleFile(dat_path).muons()
        if muons.empty:
            pytest.skip("0 muones")
        # Toleramos un poco arriba de pi/2 por errores numericos
        assert (muons["theta_rad"] >= 0).all()
        assert (muons["theta_rad"] <= math.pi / 2 + 1e-6).all()
        # Validar distribucion: NO 100% theta>70 (bug viejo)
        theta_deg = np.degrees(muons["theta_rad"])
        frac_above_70 = (theta_deg > 70).mean()
        assert frac_above_70 < 0.5, (
            f"Sospechoso: {frac_above_70:.0%} muones con theta>70°. "
            "Verificar convencion de signo de pz."
        )

    def test_energy_positive(self, dat_path: Path):
        from analysis.corsika import ParticleFile
        muons = ParticleFile(dat_path).muons()
        if muons.empty:
            pytest.skip("0 muones")
        assert (muons["energy_gev"] > 0).all()

    def test_energy_filter(self, dat_path: Path):
        from analysis.corsika import ParticleFile
        pf = ParticleFile(dat_path)
        all_muons = pf.muons()
        if len(all_muons) < 2:
            pytest.skip("muy pocos muones para testear filtro")
        median_e = all_muons["energy_gev"].median()
        high_e = pf.muons(energy_min_gev=median_e)
        assert (high_e["energy_gev"] >= median_e).all()
        assert len(high_e) <= len(all_muons)

    def test_total_count_matches_lst(self, output_dir: Path):
        """El conteo total de muones del binario debe cuadrar con el .lst
        (~ N_showers x (mean_mu+ + mean_mu-))."""
        from analysis.corsika import ParticleFile
        run = CorsikaRun(output_dir, run_number=1001)
        muons = run.particles.muons()
        avgs = run.lst.particle_averages()
        n_showers = run.lst.metadata().n_showers

        mu_avg = (
            avgs.loc[avgs["particle"] == "MU +", "mean"].sum()
            + avgs.loc[avgs["particle"] == "MU -", "mean"].sum()
        )
        expected_total = mu_avg * n_showers
        # Tolerancia generosa: el .lst usa medias redondeadas (0.1) y hay
        # cortes leves entre el reporte y el archivo
        assert abs(len(muons) - expected_total) <= max(50, 0.3 * expected_total)


# ---------------------------------------------------------------------------
# CorsikaRun: comportamiento con dirs vacios
# ---------------------------------------------------------------------------

class TestCorsikaRunEdgeCases:
    def test_empty_dir(self, tmp_path: Path):
        run = CorsikaRun(tmp_path)
        assert not run.has_lst
        assert not run.has_long
        assert not run.has_dat

    def test_only_lst_no_dat(self, tmp_path: Path):
        (tmp_path / "x.lst").write_text("dummy")
        run = CorsikaRun(tmp_path)
        assert run.has_lst
        assert not run.has_dat
        # Acceder a .long debe fallar limpio
        with pytest.raises(FileNotFoundError):
            _ = run.long
