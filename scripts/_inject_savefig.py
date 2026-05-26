#!/usr/bin/env python3
"""Inject fig.savefig(...) calls into notebooks 03, 04, 05.

Idempotent one-shot utility. Run from anywhere:
    python3 scripts/_inject_savefig.py

For each figure-bearing cell (detected by presence of `plt.show()`), inserts a
`fig.savefig(REPO_ROOT / 'docs/paper/figures' / 'name.<EXT>', ...)` line just
before `plt.show()`. The names follow the placeholders used in
`docs/paper/muography_fuego.tex`.

Re-running the script is safe in two senses:
  - It detects and replaces any previously-injected savefig line of the form
    `fig.savefig(REPO_ROOT / 'docs/paper/figures' / 'name.<pdf|png>', ...)`,
    so changing EXT below and re-running just swaps the extension.
  - The injection itself sits between `plt.tight_layout()` and `plt.show()`
    so bbox clipping works correctly.
"""
import json
import re
from pathlib import Path

# Output format for all injected figures. Change to 'pdf' for vector output;
# 'png' is the default for compatibility with heavy heatmaps.
EXT = "png"

ROOT = Path(__file__).resolve().parent.parent
NB_DIR = ROOT / "notebooks"

# Ordered list of output filenames per notebook (must match order of
# figure-bearing cells when reading top-to-bottom).
PLAN = {
    "03_validation_reyna.ipynb": [
        "fig_reyna_vertical",
        "fig_reyna_cos3",
        "fig_reyna_ratio",
    ],
    "04_muograma_fuego.ipynb": [
        "fig_setup_3d_synthetic",
        "fig_L_cone",
        "fig_emin_cone",
        "fig_T_cone",
        "fig_profile_cone",
    ],
    "05_muograma_dem_fuego.ipynb": [
        "fig_dem_topography",
        "fig_muograma_sintetico_dem",
        "fig_T_cone_vs_dem",
        "fig_residuo",
        "fig_perfil_phi180",
    ],
}


def savefig_line(name: str) -> str:
    return (
        f"fig.savefig(REPO_ROOT / 'docs/paper/figures' / '{name}.{EXT}', "
        f"bbox_inches='tight', dpi=300)\n"
    )


# Matches a previously-injected savefig line for ANY of our targets, regardless
# of extension. Used to strip stale lines so the script is idempotent under
# extension changes.
PRIOR_SAVEFIG_RE = re.compile(
    r"^fig\.savefig\(REPO_ROOT / 'docs/paper/figures' / 'fig_[^']+\.(pdf|png)', "
    r"bbox_inches='tight', dpi=300\)\n?$"
)


def process(nb_path: Path, names: list[str]) -> tuple[int, int]:
    with nb_path.open() as f:
        nb = json.load(f)

    name_idx = 0
    injected = 0
    replaced = 0

    for cell in nb["cells"]:
        if cell.get("cell_type") != "code":
            continue
        src = cell["source"]
        if isinstance(src, str):
            # Normalize to list-of-lines for uniform processing.
            src = src.splitlines(keepends=True)

        # Strip any previously-injected savefig line so we can re-inject cleanly.
        stripped_src = [line for line in src if not PRIOR_SAVEFIG_RE.match(line)]
        had_prior = len(stripped_src) != len(src)

        src_str = "".join(stripped_src)
        if "plt.show()" not in src_str:
            cell["source"] = stripped_src
            continue

        if name_idx >= len(names):
            print(
                f"  WARNING: {nb_path.name} has more figure cells than "
                f"planned names ({name_idx + 1} > {len(names)})"
            )
            cell["source"] = stripped_src
            break

        target = names[name_idx]
        new_line = savefig_line(target)

        new_lines = []
        inserted = False
        for line in stripped_src:
            if not inserted and "plt.show()" in line:
                new_lines.append(new_line)
                inserted = True
            new_lines.append(line)
        cell["source"] = new_lines

        name_idx += 1
        if had_prior:
            replaced += 1
        else:
            injected += 1

    with nb_path.open("w") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
        f.write("\n")

    return injected, replaced


def main() -> None:
    figs_dir = ROOT / "docs" / "paper" / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)

    for nb_name, names in PLAN.items():
        nb_path = NB_DIR / nb_name
        if not nb_path.exists():
            print(f"{nb_name}: NOT FOUND, skipping")
            continue
        injected, replaced = process(nb_path, names)
        print(
            f"{nb_name}: injected={injected}, replaced={replaced}, "
            f"planned={len(names)}"
        )

    print(
        f"\nExtension: .{EXT}\n"
        f"Figures will be written on next notebook run to:\n  {figs_dir}/"
    )


if __name__ == "__main__":
    main()
