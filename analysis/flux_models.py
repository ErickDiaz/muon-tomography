"""Parametrizaciones del flujo de muones a nivel del mar alternativas a Reyna.

Todas devuelven el flujo diferencial I(p, theta) en (cm^2 s sr GeV/c)^-1,
con la misma firma que `analysis.reyna.reyna_flux`, para poder pasarlas como
`flux=` a `analysis.muograma.integrated_flux_above` / `transmission_map`.

- `gaisser_flux`: formula de Gaisser con el angulo cenital efectivo cos(θ*)
  de Chirkin (2004), que corrige la curvatura de la Tierra a θ grande. Es la
  rama de alta energia del "modified Gaisser" de Tang et al. (2006),
  PRD 74, 053007. Valida para E ≳ 100/cos(θ*) GeV.
- `guan_flux`: Guan et al. (2015), arXiv:1509.06176. Modified Gaisser con un
  termino que extiende la validez a bajas energias (~1 GeV) y cos(θ*) de
  Chirkin. Es la parametrizacion recomendada para espesores de roca de escala
  volcanica (umbrales de 0.1-10 TeV).

Asumimos E ≈ p (GeV) para muones por encima de ~1 GeV.
"""

from __future__ import annotations

import numpy as np

# Coeficientes de cos(θ*) de Chirkin (2004), usados por Guan et al. (2015), eq. 2.
_P1, _P2, _P3, _P4, _P5 = 0.102573, -0.068287, 0.958633, 0.0407253, 0.817285


def cos_theta_star(theta_rad: np.ndarray | float) -> np.ndarray:
    """Coseno del angulo cenital efectivo en la altura de produccion."""
    c = np.cos(np.asarray(theta_rad, dtype=float))
    num = c**2 + _P1**2 + _P2 * c**_P3 + _P4 * c**_P5
    return np.sqrt(num / (1.0 + _P1**2 + _P2 + _P4))


def gaisser_flux(p_gevc: np.ndarray | float, theta_rad: np.ndarray | float) -> np.ndarray:
    """Gaisser con cos(θ*): 0.14 E^-2.7 [1/(1+1.1E cosθ*/115) + 0.054/(1+1.1E cosθ*/850)]."""
    E = np.asarray(p_gevc, dtype=float)
    cs = cos_theta_star(theta_rad)
    return 0.14 * E**-2.7 * (1.0 / (1.0 + 1.1 * E * cs / 115.0)
                             + 0.054 / (1.0 + 1.1 * E * cs / 850.0))


def guan_flux(p_gevc: np.ndarray | float, theta_rad: np.ndarray | float) -> np.ndarray:
    """Guan et al. (2015), eq. 3: Gaisser modificado valido desde ~1 GeV."""
    E = np.asarray(p_gevc, dtype=float)
    cs = cos_theta_star(theta_rad)
    low_e = (1.0 + 3.64 / (E * cs**1.29)) ** -2.7
    return 0.14 * E**-2.7 * low_e * (1.0 / (1.0 + 1.1 * E * cs / 115.0)
                                     + 0.054 / (1.0 + 1.1 * E * cs / 850.0))
