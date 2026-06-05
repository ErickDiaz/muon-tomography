# Muon Tomography of Guatemalan Volcanoes

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20560417-blue)](https://doi.org/10.5281/zenodo.20560417)

CORSIKA-based simulation pipeline + deep-learning analysis to image the internal density of four
Guatemalan stratovolcanoes. The simulation feasibility study targets Volcán de Fuego as the
primary science case; Acatenango, Pacaya and Volcán de Agua provide calibration and comparison.

The methodological precedent is the Colombian work of Vesga-Ramírez et al. (2019). The main
contribution of this project on top of that baseline is the integration of deep learning for
super-resolution and surrogate forward modelling of the muon flux.

## Volcanoes

| Volcán | Role | Altitude | Composition | Activity |
|---|---|---|---|---|
| **Fuego** | Primary target | 3,763 m | Basalt | Highly active |
| **Acatenango** | Calibration (known mass) | 3,976 m | Andesite | Dormant |
| **Pacaya** | Secondary candidate | 2,552 m | Olivine basalt | Persistent |
| **Volcán de Agua** | Secondary / calibration | 3,760 m | Andesite | Dormant |

---

## Setup

The workflow is fully **local**: clone the repo (laptop or server), install Python deps with
Poetry, build the Docker image, run simulations. No SSH wrappers, no cross-server orchestration.
Use plain `rsync` ad-hoc if you need to move data between machines.

### Prerequisites

- Docker Engine ≥ 24.0
- Python ≥ 3.10
- [Poetry](https://python-poetry.org/docs/#installation) (`pipx install poetry` or `python3 -m pip install --user poetry`)
- `make`, `tmux`, `git`
- `corsika-78050.tar.gz` in the repo root (download from [KIT](https://www.iap.kit.edu/corsika/);
  not in git, ~80 MB)

### One-time install

```bash
git clone https://github.com/ErickDiaz/muon-tomography.git
cd muon-tomography
make install               # poetry creates .venv/ with all dependencies
make build-corsika         # Docker image with DPMJET-III (~10–15 min)
make verify-corsika        # AAA test inside the container (~30 s)
```

For a server install without notebook tooling:

```bash
make install-no-dev        # omits jupyterlab and pytest
```

Optional: `cp .env.example .env` if you want to override `CORSIKA_VERSION`, `HE_MODEL`, or
`IMAGE_TAG` — otherwise the defaults in the Makefile are used.

---

## Running simulations

### Quick test (~8 min)

```bash
make test-corsika          # runs fuego_test.inp (500 cascades)
```

### Single parametric run

```bash
make corsika-run VOLCAN=fuego DETECTOR_POS=1 NSHOW=10000
```

Available volcanoes: `fuego`, `acatenango`, `pacaya`, `agua`.
`RUNNR` is auto-assigned sequentially from `sim/runs.csv` (no manual collision management).

### Batch (multi-volcano)

The plan is personal (gitignored). Copy the template once, edit, then run:

```bash
cp sim/runs_plan.example.yaml sim/runs_plan.yaml
$EDITOR sim/runs_plan.yaml
```

Then:

```bash
make batch-start           # runs the plan sequentially in a detached tmux session
make sim-status            # snapshot of the dashboard
make sim-status WATCH=1    # auto-refresh every 5 s
tmux attach -t batch       # see raw output (Ctrl+B D to detach)
make batch-stop            # kill the orchestrator (current CORSIKA run finishes its cycle)
```

The orchestrator (`scripts/run_batch.py`) skips entries already present in `sim/runs.csv` with
`status=ok`, so re-running picks up where it left off.

### Inspecting outputs

```bash
make runs                  # pretty-print sim/runs.csv
make backfill-runs         # rescan sim/output/ and add missing runs to the manifest
```

### Moving data between machines

Plain rsync, not a Make target:

```bash
rsync -avz alcyon:muon-tomography/sim/output/  ./sim/output/
rsync -avz alcyon:muon-tomography/sim/runs.csv ./sim/runs.csv
```

---

## Analysis

Notebooks live under `notebooks/` and run on the local kernel. After `make install` you can
register the poetry `.venv` as a Jupyter kernel or activate it before launching JupyterLab:

```bash
source .venv/bin/activate
jupyter lab notebooks/
```

| Notebook | Purpose |
|---|---|
| `01_inspect_run.ipynb` | Quick sanity inspection of a run |
| `02_inspect_muons.ipynb` | Muon kinematics + NSHOW convergence study |
| `03_validation_reyna.ipynb` | Validation against the Reyna 2006 atmospheric muon flux |
| `04_muograma_fuego.ipynb` | Synthetic muogram (conical model) of Fuego |
| `05_muograma_dem_fuego.ipynb` | DEM-based muogram + opacity residual |
| `06_timing_model.ipynb` | Linear model of CORSIKA run duration vs NSHOW |

---

## Repo layout

```
muon-tomography/
├── analysis/           Python modules (CORSIKA parsers, ray tracing, Reyna parametrization)
├── docker/             Dockerfile and coconut.expect for the thesis-corsika image
├── docs/               Project documentation (corsika_*.md, paper/, …)
├── notebooks/          Jupyter analysis notebooks
├── scripts/            Helper scripts (run_batch, sim_status, manifest tools, …)
├── sim/
│   ├── steering/       Parametric CORSIKA steering templates (one per volcano)
│   ├── runs.csv        Manifest of completed runs (host, duration, paths, status)
│   ├── runs_plan.example.yaml  Template for the batch plan (versioned)
│   ├── runs_plan.yaml  Personal batch plan (gitignored, copy from example)
│   └── output/         CORSIKA DAT + .lst files (gitignored, can reach tens of GB)
├── tests/              Pytest suite for analysis/
├── Makefile            Single source of commands; run `make help`
├── pyproject.toml      Python dependencies (Poetry) — single source of truth
└── poetry.lock         Pinned versions for reproducible installs
```

---

## Make target reference

Run `make help` for the full list with descriptions. The targets cluster as:

- **Env**: `install`, `install-no-dev`, `poetry-shell`, `export-requirements`
- **Build**: `check-tarball`, `build`, `build-corsika`, `build-ml`, `build-all`
- **Interactive**: `shell`, `shell-corsika`, `shell-ml`, `verify-corsika`, `test-corsika`
- **Simulation**: `corsika-run`
- **Batch**: `batch-start`, `batch-stop`, `sim-status`
- **Manifest**: `runs`, `backfill-runs`
- **Data**: `download-dem`
- **Tests / docs**: `test`, `export-notebooks-pdf`
- **Cleanup**: `clean`, `clean-output`

---

## Documentation

| Document | What it covers |
|---|---|
| [`docs/corsika_instalacion.md`](docs/corsika_instalacion.md) | Manual CORSIKA install (without Docker) and coconut walkthrough |
| [`docs/corsika_parametros.md`](docs/corsika_parametros.md) | Steering parameters with physical justification |
| [`sim/README.md`](sim/README.md) | DAT / .lst output format and how to parse them |

---

## References

- Vesga-Ramírez et al. 2019, *Muon Tomography sites for Colombian volcanoes*, arXiv:1705.09884
- Heck et al. 1998, *CORSIKA: A Monte Carlo Code to Simulate Extensive Air Showers*, FZKA 6019
- Reyna 2006, *A Simple Parameterization of the Cosmic-Ray Muon Momentum Spectra at the Surface as a Function of Zenith Angle*, arXiv:hep-ph/0604145
