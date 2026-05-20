"""Parametrizacion empirica del flujo de muones a nivel del suelo.

Reyna 2006 (arXiv:hep-ph/0604145):
    "A Simple Parameterization of the Cosmic-Ray Muon Momentum Spectra
     at the Surface as a Function of Zenith Angle"

Idea central: el flujo diferencial de muones a un angulo cenital theta es

    I(p, theta) = cos^3(theta) * I_v(p * cos(theta))

donde I_v(p_v) es el flujo VERTICAL como funcion del momento vertical
equivalente p_v = p * cos(theta), parametrizado como:

    I_v(p_v) = c1 * p_v^( -(c2 + c3*log10(p_v) + c4*log10(p_v)^2 + c5*log10(p_v)^3) )

Unidades: I_v en (cm^2 s sr GeV/c)^-1, p_v en GeV/c.

El rango de validez de la parametrizacion es ~1 GeV/c a ~2000 GeV/c.
Fuera de ese rango la extrapolacion no esta calibrada.

Uso tipico (validacion del MC):
    from analysis.reyna import reyna_flux, reyna_vertical_flux

    # Curva vertical analitica:
    p = np.logspace(0, 3, 100)
    flux_v = reyna_vertical_flux(p)

    # Comparar a un theta dado:
    flux = reyna_flux(p, theta_rad=np.radians(30))
"""

from __future__ import annotations

import numpy as np

# Coeficientes de la Tabla 1 de Reyna 2006 (fit a datos de muones a nivel del mar).
_C1 = 0.00253
_C2 = 0.2455
_C3 = 1.288
_C4 = -0.2555
_C5 = 0.0209


def reyna_vertical_flux(p_gevc: np.ndarray | float) -> np.ndarray:
    """Flujo vertical I_v(p_v) en (cm^2 s sr GeV/c)^-1.

    Args:
        p_gevc: momento (vertical) en GeV/c. Escalar o array.

    Returns:
        Flujo diferencial vertical. Misma shape que `p_gevc`.
    """
    p = np.asarray(p_gevc, dtype=float)
    lg = np.log10(p)
    alpha = _C2 + _C3 * lg + _C4 * lg**2 + _C5 * lg**3
    return _C1 * p ** (-alpha)


def reyna_flux(p_gevc: np.ndarray | float, theta_rad: np.ndarray | float) -> np.ndarray:
    """Flujo diferencial I(p, theta) en (cm^2 s sr GeV/c)^-1.

    Aplica el escalamiento cos^3(theta) * I_v(p * cos(theta)).

    Args:
        p_gevc: momento del muon en GeV/c.
        theta_rad: angulo cenital en radianes (0 = vertical).

    Returns:
        Flujo diferencial. Broadcasting numpy estandar entre `p_gevc` y `theta_rad`.
    """
    cos_t = np.cos(np.asarray(theta_rad, dtype=float))
    p_v = np.asarray(p_gevc, dtype=float) * cos_t
    return cos_t**3 * reyna_vertical_flux(p_v)
