"""Compare the high-energy CORSIKA muon sample (fuego_he_*) with Reyna and Guan.

Reads sim/output/he_muons.npz (p [GeV/c], theta [rad], nsim) and prints the
integral muon intensity Φ(>p) per zenith bin, absolutely normalised with the
PDG all-nucleon primary flux, together with the analytical predictions. Also
writes docs/paper/figures/fig_he_validation.png.

Normalisation: the sample has protons with dN/dE ∝ E^-2.7 on [1e3, 1e6] GeV and
zenith angles distributed ∝ cosθ dΩ (flat-detector default) up to 89°. Each
shower represents w = ∫J dE · ∫cosθ dΩ / N_sim primaries per cm² per s, with
J(E) = 1.8 E^-2.7 cm⁻² s⁻¹ sr⁻¹ GeV⁻¹ (PDG, nucleons; protons stand in for
nuclei by superposition). A muon crossing the horizontal observation level
contributes w / (cosθ_μ ΔΩ) to the intensity of its zenith bin.

Valid only for p ≳ 300 GeV/c: primaries below 1 TeV and muons below the 50 GeV
cut are absent.
"""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from analysis.flux_models import guan_flux  # noqa: E402
from analysis.muograma import integrated_flux_above  # noqa: E402
from analysis.reyna import reyna_flux  # noqa: E402

E1, E2, GAMMA, K_NUCLEON = 1e3, 1e6, 2.7, 1.8
THETA_MAX = np.radians(89.0)

d = np.load(REPO / "sim/output/he_muons.npz")
p, th, nsim = d["p"], d["theta"], int(d["nsim"])
prim_int = K_NUCLEON / (GAMMA - 1) * (E1 ** (1 - GAMMA) - E2 ** (1 - GAMMA))
w = prim_int * np.pi * np.sin(THETA_MAX) ** 2 / nsim

def bin_average(flux, pc, lo, hi, n=60):
    """Model Φ(>pc) averaged over the solid angle of the zenith bin [lo, hi)°."""
    tg = np.radians(np.linspace(lo, hi, n))
    vals = np.array([float(integrated_flux_above(pc, t, flux=flux)) for t in tg])
    return float(np.trapezoid(vals * np.sin(tg), tg) / np.trapezoid(np.sin(tg), tg))


bins = [(0, 40), (40, 60), (60, 75)]
thresholds = np.array([300.0, 500.0, 1000.0, 2000.0, 3000.0, 5000.0])
rows = {}
for lo, hi in bins:
    sel = (th >= np.radians(lo)) & (th < np.radians(hi))
    dOmega = 2 * np.pi * (np.cos(np.radians(lo)) - np.cos(np.radians(hi)))
    mc, err, n, rey, gua = [], [], [], [], []
    for pc in thresholds:
        s = sel & (p > pc)
        wt = w / (np.cos(th[s]) * dOmega)
        mc.append(wt.sum()); err.append(np.sqrt((wt ** 2).sum())); n.append(int(s.sum()))
        rey.append(bin_average(reyna_flux, pc, lo, hi))
        gua.append(bin_average(guan_flux, pc, lo, hi))
    rows[(lo, hi)] = dict(mc=np.array(mc), err=np.array(err),
                          n=np.array(n), reyna=np.array(rey), guan=np.array(gua))

print(f"showers {nsim:,}  muons {len(p):,}  (>1 TeV: {(p > 1e3).sum():,}, >3 TeV: {(p > 3e3).sum():,})")
for (lo, hi), r in rows.items():
    print(f"\nθ ∈ [{lo},{hi})°")
    print("  p>      N      MC/Reyna        MC/Guan")
    for k, pc in enumerate(thresholds):
        rel = r["err"][k] / r["mc"][k] if r["mc"][k] > 0 else np.nan
        print(f"  {pc:5.0f} {r['n'][k]:6d}   {r['mc'][k]/r['reyna'][k]:5.2f} ± {rel*r['mc'][k]/r['reyna'][k]:4.2f}"
              f"   {r['mc'][k]/r['guan'][k]:5.2f} ± {rel*r['mc'][k]/r['guan'][k]:4.2f}")

# Normalisation-free test: zenith ratio at fixed threshold
ref, inc = rows[(0, 40)], rows[(60, 75)]
print("\nZenith ratio Φ(>p, 60–75°) / Φ(>p, 0–40°)  (independent of the primary normalisation)")
print("  p>     MC            Reyna   Guan")
for k, pc in enumerate(thresholds):
    if ref["mc"][k] > 0 and inc["mc"][k] > 0:
        rmc = inc["mc"][k] / ref["mc"][k]
        rerr = rmc * np.hypot(inc["err"][k] / inc["mc"][k], ref["err"][k] / ref["mc"][k])
        print(f"  {pc:5.0f}  {rmc:5.2f} ± {rerr:4.2f}   {inc['reyna'][k]/ref['reyna'][k]:5.2f}   {inc['guan'][k]/ref['guan'][k]:5.2f}")

if "--plot" in sys.argv:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    cols = {(0, 40): "tab:blue", (40, 60): "tab:orange", (60, 75): "tab:green"}
    for (lo, hi), r in rows.items():
        c = cols[(lo, hi)]
        ok = r["n"] > 0
        rel = r["err"][ok] / r["mc"][ok]
        for model, mk, ls in (("guan", "o", "--"), ("reyna", "s", ":")):
            ratio = r["mc"][ok] / r[model][ok]
            ratio = ratio / ratio[0]
            axes[0].errorbar(thresholds[ok] * (1.03 if model == "reyna" else 1.0), ratio, yerr=ratio * rel,
                             fmt=mk + ls, color=c, ms=6, capsize=3,
                             mfc=c if model == "guan" else "white", lw=1.2,
                             label=f"[{lo}°, {hi}°) / {'Guan' if model == 'guan' else 'Reyna'}")
    axes[0].axhline(1.0, color="k", lw=1)
    axes[0].set_xscale("log")
    axes[0].set_xlim(250, 7000)
    axes[0].set_ylim(0.4, 1.4)
    axes[0].set_xlabel("p [GeV/c]", fontsize=15)
    axes[0].set_ylabel("(CORSIKA / model), normalised at p > 300 GeV/c", fontsize=13)
    axes[0].set_title("(a) Spectral shape of Φ(>p) at 1.74 km a.s.l.", fontsize=13)
    axes[0].legend(fontsize=10, ncol=2, loc="lower left")
    axes[0].tick_params(labelsize=13)
    ks = [k for k in range(len(thresholds)) if ref["mc"][k] > 0 and inc["mc"][k] > 0]
    rmc = np.array([inc["mc"][k] / ref["mc"][k] for k in ks])
    rer = rmc * np.array([np.hypot(inc["err"][k] / inc["mc"][k], ref["err"][k] / ref["mc"][k]) for k in ks])
    axes[1].errorbar(thresholds[ks], rmc, yerr=rer, fmt="ko", ms=7, capsize=3, label="CORSIKA")
    axes[1].semilogx(thresholds, inc["reyna"] / ref["reyna"], "-", color="tab:red", lw=2, label="Reyna")
    axes[1].semilogx(thresholds, inc["guan"] / ref["guan"], "--", color="black", lw=2, label="Guan et al. 2015")
    axes[1].set_xlim(250, 7000)
    axes[1].set_xlabel("p [GeV/c]", fontsize=15)
    axes[1].set_ylabel("Φ(>p, 60–75°) / Φ(>p, 0–40°)", fontsize=15)
    axes[1].set_title("(b) Zenith ratio (normalisation-free)", fontsize=13)
    axes[1].legend(fontsize=12)
    axes[1].tick_params(labelsize=13)
    plt.tight_layout()
    out = REPO / "docs/paper/figures/fig_he_validation.png"
    fig.savefig(out, bbox_inches="tight", dpi=300)
    print(f"saved {out}")
