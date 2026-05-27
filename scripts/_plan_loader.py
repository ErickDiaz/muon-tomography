"""Shared loader for sim/runs_plan.yaml.

Supports two ways of declaring runs:

1. Explicit list (`plan`) — one entry per (volcan, nshow, detector_pos):

       plan:
         - { volcan: fuego, nshow: 100000 }
         - { volcan: acatenango }

2. Sweeps (`sweeps`) — syntactic sugar that expands to multiple plan
   entries when you want to study the same volcano at several NSHOW
   values (e.g., convergence studies):

       sweeps:
         - volcan: fuego
           nshow_list: [500, 1000, 10000, 100000, 1000000]

   Each sweep produces len(nshow_list) plan entries; other keys on the
   sweep (e.g., detector_pos) are copied to every expanded entry.

The two blocks can coexist. After expansion, defaults are applied
field-by-field via setdefault, so entry-level values override the
top-level defaults section.

Used by scripts/run_batch.py and scripts/sim_status.py to keep the
expansion logic identical between orchestrator and dashboard.
"""
from pathlib import Path

import yaml


def load_plan(plan_file: Path) -> list[dict]:
    if not plan_file.exists():
        example = plan_file.with_suffix(".example.yaml")
        msg = f"ERROR: missing {plan_file}"
        if example.exists():
            msg += (
                f"\n  Copia el template para empezar:"
                f"\n    cp {example} {plan_file}"
                f"\n  Despues editalo a gusto (es personal, ya esta en .gitignore)."
            )
        raise FileNotFoundError(msg)

    cfg = yaml.safe_load(plan_file.read_text())
    defaults = cfg.get("defaults") or {}

    plan: list[dict] = list(cfg.get("plan") or [])

    for sweep in (cfg.get("sweeps") or []):
        base = {k: v for k, v in sweep.items() if k != "nshow_list"}
        for n in sweep.get("nshow_list") or []:
            plan.append({**base, "nshow": n})

    for entry in plan:
        for k, v in defaults.items():
            entry.setdefault(k, v)
    return plan
