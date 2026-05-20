"""Primitivas para muografia volcanica: geometria, ray tracing, perdida de
energia, integracion del flujo.

Pensado como primer pase con un cono sintetico (sin DEM). Cuando se ingiera
un DEM real, solo cambia `rock_opacity_grid` para usar un mapa de elevacion
en vez de la formula del cono — el resto del pipeline (CSDA, transmision)
queda igual.

Convenciones:
- Sistema cartesiano local con origen en la base del volcan (z=base, x_este, y_norte).
- z hacia arriba, theta cenital medido desde +z, phi azimutal con 0 = +x (este).
- Densidades en g/cm^3, longitudes en metros, opacidades en g/cm^2,
  energias y momentos en GeV (asumimos pc = E para muones a estos momentos).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .reyna import reyna_flux


@dataclass(frozen=True)
class ConicalVolcano:
    """Modelo sintetico de volcan: cono recto vertical.

    Args:
        summit_xyz: posicion de la cima (x, y, z) en metros.
        base_z: altura de la base (m). El cono solo existe entre base_z y z_cima.
        base_radius_m: radio horizontal del cono al nivel de la base.
        density_gcc: densidad de la roca (g/cm^3). Roca estandar ~ 2.65.
    """

    summit_xyz: tuple[float, float, float]
    base_z: float
    base_radius_m: float
    density_gcc: float = 2.65

    @property
    def height_m(self) -> float:
        return self.summit_xyz[2] - self.base_z

    @property
    def tan_half_angle(self) -> float:
        """tan(α) donde α es el angulo entre el eje y el flanco."""
        return self.base_radius_m / self.height_m

    def is_inside(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
        """Mascara booleana: ¿estan los puntos (x,y,z) dentro del cono?"""
        x_s, y_s, z_s = self.summit_xyz
        r_horiz = np.sqrt((x - x_s) ** 2 + (y - y_s) ** 2)
        # Radio del cono a la altura z (0 en la cima, base_radius_m en la base)
        r_cone = np.maximum(0.0, (z_s - z) * self.tan_half_angle)
        return (r_horiz <= r_cone) & (z >= self.base_z) & (z <= z_s)


class DEMTerrain:
    """Terreno real desde un DEM (Digital Elevation Model) GeoTIFF.

    Sustituye a `ConicalVolcano` cuando queremos usar topografia real en lugar
    del cono sintetico. Expone la misma interfaz (`is_inside`, `density_gcc`)
    para que `rock_opacity_grid` lo trate igual.

    Coordenadas internas: sistema cartesiano local en metros con origen en
    `origin_lonlat`, ejes (este, norte, arriba). La proyeccion plana es la
    zona UTM apropiada para esa longitud (deformacion < 0.1% en una caja de
    ~50 km, suficiente para muografia).

    Args:
        dem_path: ruta al GeoTIFF (descargado con `make download-dem`).
        origin_lonlat: (lon, lat) en grados del origen del sistema local.
            Tipicamente la cima del volcan. Default: cima del Volcan de Fuego.
        density_gcc: densidad de roca asumida (g/cm^3). 2.65 = basalto/andesita.
    """

    def __init__(
        self,
        dem_path: str | Path,
        origin_lonlat: tuple[float, float] = (-90.8806, 14.4747),
        density_gcc: float = 2.65,
    ) -> None:
        import rasterio
        from pyproj import Transformer

        self.dem_path = Path(dem_path)
        self.origin_lonlat = origin_lonlat
        self.density_gcc = density_gcc

        # Cargar el raster completo en memoria (un tile de Copernicus 30m son ~45 MB)
        with rasterio.open(self.dem_path) as src:
            self.array = src.read(1).astype(np.float32)
            self.transform = src.transform
            self.dem_crs = src.crs

        # Zona UTM derivada de la longitud del origen.
        # zone = floor((lon + 180) / 6) + 1, hemisferio norte para lat > 0.
        zone = int((origin_lonlat[0] + 180) / 6) + 1
        self.utm_epsg = (32600 if origin_lonlat[1] >= 0 else 32700) + zone

        # Transformadores entre coordenadas locales (UTM) y el CRS del DEM (WGS84 lonlat).
        self._to_lonlat = Transformer.from_crs(
            self.utm_epsg, self.dem_crs, always_xy=True
        )
        from_lonlat = Transformer.from_crs(
            self.dem_crs, self.utm_epsg, always_xy=True
        )
        self.origin_utm = from_lonlat.transform(*origin_lonlat)

    @property
    def summit_elevation(self) -> float:
        """Elevacion (m) en el origen local — tipicamente la cima del volcan."""
        return float(self.elevation_at(np.array(0.0), np.array(0.0)))

    def elevation_at(self, x_local: np.ndarray, y_local: np.ndarray) -> np.ndarray:
        """Elevacion del terreno (m) en coordenadas locales (este, norte).

        Interpolacion bilineal sobre el raster. Puntos fuera del tile devuelven
        la elevacion del pixel del borde (no NaN, para que el ray tracing
        no se rompa).
        """
        # Local UTM -> UTM absoluto -> (lon, lat) -> indice de pixel float.
        e_abs = x_local + self.origin_utm[0]
        n_abs = y_local + self.origin_utm[1]
        lon, lat = self._to_lonlat.transform(e_abs, n_abs)
        col_f = (lon - self.transform.c) / self.transform.a
        row_f = (lat - self.transform.f) / self.transform.e

        h, w = self.array.shape
        # Limites: clamp para que (row_i, col_i) y +1 siempre sean validos.
        row_f = np.clip(row_f, 0.0, h - 1.001)
        col_f = np.clip(col_f, 0.0, w - 1.001)
        row_i = np.floor(row_f).astype(np.int32)
        col_i = np.floor(col_f).astype(np.int32)
        dr = (row_f - row_i).astype(np.float32)
        dc = (col_f - col_i).astype(np.float32)

        a00 = self.array[row_i, col_i]
        a01 = self.array[row_i, col_i + 1]
        a10 = self.array[row_i + 1, col_i]
        a11 = self.array[row_i + 1, col_i + 1]
        return (a00 * (1 - dr) * (1 - dc) + a01 * (1 - dr) * dc
                + a10 * dr * (1 - dc) + a11 * dr * dc)

    def is_inside(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> np.ndarray:
        """True donde el punto (x, y, z) cae bajo la superficie del terreno."""
        return z < self.elevation_at(x, y)


def rock_opacity_grid(
    volcano: ConicalVolcano,
    detector_xyz: tuple[float, float, float],
    theta_rad: np.ndarray,
    phi_rad: np.ndarray,
    max_length_m: float = 20_000.0,
    n_steps: int = 400,
) -> np.ndarray:
    """Opacidad de roca L(θ,φ) en g/cm² para una malla angular.

    Para cada (theta, phi) lanza un rayo desde el detector hacia el cielo,
    lo muestrea en `n_steps` pasos uniformes, y suma la masa por unidad de
    area de los pasos que caen DENTRO del cono.

    Args:
        volcano: cono.
        detector_xyz: (x, y, z) del detector en m.
        theta_rad: array 1D de angulos cenitales (rad). 0 = vertical hacia arriba.
        phi_rad: array 1D de azimutes (rad). 0 = +x (este).
        max_length_m: longitud maxima del rayo (m). Debe ser > altura del volcan
            + distancia detector-volcan, para no perder roca por truncamiento.
        n_steps: numero de pasos por rayo. 400 da ~50 m de resolucion para
            max_length=20 km, suficiente para volcanes de escala km.

    Returns:
        Array 2D (len(theta), len(phi)) con la opacidad en g/cm².
    """
    theta_grid, phi_grid = np.meshgrid(theta_rad, phi_rad, indexing="ij")
    # Vector unitario de direccion del rayo:
    # theta = 0 → +z (vertical arriba); theta = pi/2 → horizontal.
    dx = np.sin(theta_grid) * np.cos(phi_grid)
    dy = np.sin(theta_grid) * np.sin(phi_grid)
    dz = np.cos(theta_grid)

    t = np.linspace(0.0, max_length_m, n_steps + 1)
    # Broadcast a forma (Nθ, Nφ, Nsteps+1)
    x = detector_xyz[0] + t[None, None, :] * dx[:, :, None]
    y = detector_xyz[1] + t[None, None, :] * dy[:, :, None]
    z = detector_xyz[2] + t[None, None, :] * dz[:, :, None]

    inside = volcano.is_inside(x, y, z)  # bool (Nθ, Nφ, Nsteps+1)

    # Longitud de paso en cm (para que opacidad = densidad * longitud salga en g/cm²)
    step_cm = (max_length_m / n_steps) * 100.0
    # Suma de pasos dentro del cono * masa por unidad de area por paso
    return inside.sum(axis=-1) * step_cm * volcano.density_gcc


def csda_min_momentum(
    opacity_gcm2: np.ndarray,
    a: float = 2.0e-3,
    b: float = 4.0e-6,
) -> np.ndarray:
    """Momento minimo (GeV/c) que un muon necesita para atravesar `opacity_gcm2`.

    Aproximacion Continuous Slowing Down (CSDA) con la parametrizacion
    estandar -dE/dx = a + b·E (ionizacion + perdidas radiativas):

        R(E) = (1/b) · ln(1 + b·E/a)
        ⇒ E_min(X) = (a/b) · (exp(b·X) - 1)

    Para muones en roca estandar (Z ≈ 11, A ≈ 22, ρ = 2.65 g/cm³):
      a ≈ 2 MeV/(g/cm²) = 2e-3 GeV/(g/cm²)
      b ≈ 4e-6 (g/cm²)⁻¹ (dominante a E ≳ 100 GeV)

    A baja energia (b·X « 1) recupera la formula lineal E_min ≈ a·X.

    Args:
        opacity_gcm2: opacidad en g/cm². Escalar o array.
        a, b: coeficientes de la perdida. Default = roca estandar.

    Returns:
        Energia minima en GeV. Asumimos E ≈ pc para muones (m_μ ≈ 0.1 GeV, despreciable).
    """
    X = np.asarray(opacity_gcm2, dtype=float)
    return (a / b) * (np.expm1(b * X))


def integrated_flux_above(
    p_min_gevc: np.ndarray,
    theta_rad: np.ndarray | float,
    p_upper_gevc: float = 5_000.0,
    n_log_bins: int = 400,
) -> np.ndarray:
    """Flujo integrado por encima de p_min, a un dado theta.

    ∫_{p_min}^{p_upper} I_Reyna(p, theta) dp

    Args:
        p_min_gevc: cota inferior (GeV/c). Escalar o array.
        theta_rad: angulo cenital. Si array, debe broadcastear con p_min.
        p_upper_gevc: cota superior (5 TeV cubre el ~99% del flujo).
        n_log_bins: bines en escala logaritmica para integrar.

    Returns:
        Flujo integrado en (cm² s sr)^-1. Misma shape que p_min broadcastea con theta.
    """
    p_min = np.asarray(p_min_gevc, dtype=float)
    # Evitar log(0): suelo en 0.1 GeV/c (debajo de eso Reyna no esta calibrada)
    p_min = np.maximum(p_min, 0.1)

    # Para cada p_min hacemos una integral logaritmica de p_min a p_upper.
    # Vectorizamos: shape de salida = shape de p_min.
    # Usamos un grid comun en log para todos los puntos, integramos por trapezoidal,
    # pero recortando bajo p_min (el integrando es 0 ahi).
    log_grid = np.linspace(np.log10(0.1), np.log10(p_upper_gevc), n_log_bins)
    p_grid = 10**log_grid  # (n_log_bins,)
    theta_b = np.broadcast_to(theta_rad, p_min.shape) if not np.isscalar(theta_rad) else theta_rad
    # Flux at each (p_grid, theta) — shape (..., n_log_bins)
    p_expanded = np.broadcast_to(p_grid, p_min.shape + p_grid.shape)
    theta_expanded = np.broadcast_to(
        np.asarray(theta_b)[..., None] if not np.isscalar(theta_rad) else theta_rad,
        p_min.shape + p_grid.shape,
    )
    flux_grid = reyna_flux(p_expanded, theta_expanded)
    # Mascara: solo p > p_min (extendido)
    mask = p_expanded >= p_min[..., None]
    integrand = np.where(mask, flux_grid, 0.0)
    return np.trapezoid(integrand, x=p_grid, axis=-1)


def transmission_map(
    opacity_gcm2: np.ndarray,
    theta_rad: np.ndarray,
    p_threshold_gevc: float = 0.1,
) -> np.ndarray:
    """Transmision T(θ,φ) = N(p>p_min(X), θ) / N(p>p_threshold, θ).

    Es la fraccion del flujo de muones que sobrevive al pasar por una
    columna de roca de opacidad `opacity_gcm2`. T=1 significa cielo abierto;
    T=0 significa que ningun muon puede atravesar.

    Args:
        opacity_gcm2: opacidad por pixel angular (Nθ, Nφ).
        theta_rad: angulo cenital de cada fila (Nθ,). Se broadcastea a (Nθ, Nφ).
        p_threshold_gevc: corte inferior del detector / aceptancia. 0.1 GeV/c
            es razonable para un detector tipico.

    Returns:
        Transmision por pixel, shape (Nθ, Nφ).
    """
    theta_grid = np.broadcast_to(theta_rad[:, None], opacity_gcm2.shape)
    p_min = csda_min_momentum(opacity_gcm2)
    N_with = integrated_flux_above(p_min, theta_grid)
    N_open = integrated_flux_above(np.full_like(opacity_gcm2, p_threshold_gevc), theta_grid)
    # Donde el flujo abierto es 0 (theta cerca de 90°, no fisico aqui), evitar /0.
    return np.where(N_open > 0, N_with / N_open, 0.0)
