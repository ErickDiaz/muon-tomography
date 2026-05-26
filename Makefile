# =============================================================================
# Makefile — muon-tomography
#
# All operations are local: clone the repo (laptop or server), `make install`,
# `make build-corsika`, `make corsika-run` (or `make batch-start`), done.
# No SSH, no rsync, no server-side targets. To move data between machines,
# use plain rsync ad-hoc.
#
# Run `make help` for the full target list.
# =============================================================================

# Optional .env override (CORSIKA_VERSION, HE_MODEL, IMAGE_TAG). Defaults below.
-include .env
export

CORSIKA_VERSION ?= 78050
HE_MODEL        ?= 1
IMAGE_TAG       ?= latest

CORSIKA_TARBALL := corsika-$(CORSIKA_VERSION).tar.gz
CORSIKA_IMAGE   := thesis-corsika:$(IMAGE_TAG)
ML_IMAGE        := thesis-ml:$(IMAGE_TAG)

# Bind-mounts shared by all `docker run` invocations.
RUN_FLAGS := --rm \
	-v $(PWD)/sim:/work/sim \
	-v $(PWD)/data:/work/data \
	-v $(PWD)/scripts:/work/scripts

# Default parameters for `make corsika-run`.
VOLCAN       ?= fuego
DETECTOR_POS ?= 1
NSHOW        ?= 5000

# Python interpreter for repo scripts. Prefer the poetry .venv if it exists.
PY := $(if $(wildcard .venv/bin/python3),.venv/bin/python3,python3)

.PHONY: help \
	install install-no-dev poetry-shell export-requirements \
	check-tarball build build-corsika build-ml build-all \
	shell shell-corsika shell-ml \
	verify-corsika test-corsika corsika-run \
	batch-start batch-stop sim-status \
	runs backfill-runs \
	download-dem \
	test export-notebooks-pdf \
	clean clean-output

help:  ## Mostrar esta ayuda
	@echo "Targets disponibles:"
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# -- Python environment (poetry) ---------------------------------------------
# Single source of truth: pyproject.toml + poetry.lock. The .venv lives
# in-project (poetry.toml says so). The Docker image installs via pip from
# docker/requirements.txt, which is regenerated from pyproject.toml by
# `make export-requirements`.

install:  ## Crear .venv local con poetry (incluye grupos notebook + dev)
	poetry install

install-no-dev:  ## Solo deps de produccion (sin pytest ni jupyter)
	poetry install --without dev,notebook

poetry-shell:  ## Mostrar comando para activar el .venv en la shell actual
	@echo "Para activar:    source .venv/bin/activate"
	@echo "Para desactivar: deactivate"

export-requirements:  ## Regenerar docker/requirements.txt desde pyproject.toml (correr cuando cambien deps)
	poetry export -f requirements.txt --output docker/requirements.txt --without-hashes --only main
	@echo "docker/requirements.txt regenerado. Re-build de la imagen: make build-corsika"

# -- Docker build -------------------------------------------------------------

check-tarball:  ## Verificar que corsika-78050.tar.gz exista en la raiz
	@test -f $(CORSIKA_TARBALL) || \
		(echo "ERROR: falta $(CORSIKA_TARBALL) en la raiz del repo" && exit 1)
	@echo "OK: $(CORSIKA_TARBALL) presente ($$(du -h $(CORSIKA_TARBALL) | cut -f1))"

build: build-corsika  ## Alias: construir imagen CORSIKA

build-corsika: check-tarball  ## Construir imagen thesis-corsika
	docker build \
		-f docker/Dockerfile.corsika \
		-t $(CORSIKA_IMAGE) \
		--build-arg CORSIKA_VERSION=$(CORSIKA_VERSION) \
		--build-arg HE_MODEL=$(HE_MODEL) \
		.

build-ml:  ## Construir imagen thesis-ml (Fase 3, requiere ~10 GB)
	docker build \
		-f docker/Dockerfile.ml \
		-t $(ML_IMAGE) \
		.

build-all: build-corsika build-ml  ## Construir ambas imagenes

# -- Interactive use ----------------------------------------------------------

shell: shell-corsika  ## Alias: shell en thesis-corsika

shell-corsika:  ## Abrir shell interactiva en thesis-corsika
	docker run -it $(RUN_FLAGS) $(CORSIKA_IMAGE)

shell-ml:  ## Abrir shell interactiva en thesis-ml (con GPU)
	docker run -it $(RUN_FLAGS) --gpus all --shm-size=8g $(ML_IMAGE)

verify-corsika:  ## Validar la imagen ejecutando el ejemplo all-inputs de CORSIKA
	docker run $(RUN_FLAGS) $(CORSIKA_IMAGE) bash -c \
		"cd /opt/corsika/run && corsika < all-inputs > /tmp/verify.lst 2>&1 && \
		 grep 'END OF RUN' /tmp/verify.lst && echo 'OK: CORSIKA funciona'"

test-corsika:  ## Correr fuego_test.inp (500 showers, ~8 min)
	@mkdir -p sim/output
	@rm -f sim/output/DAT001001 sim/output/DAT001001.long sim/output/fuego_test.lst
	docker run $(RUN_FLAGS) $(CORSIKA_IMAGE) bash -c \
		"cd /opt/corsika/run && \
		 corsika < /work/sim/steering/fuego_test.inp > /work/sim/output/fuego_test.lst && \
		 grep 'END OF RUN' /work/sim/output/fuego_test.lst && \
		 echo 'OK: simulacion completa'"

# -- Parametric simulation ----------------------------------------------------
# `make corsika-run VOLCAN=fuego DETECTOR_POS=1 NSHOW=10000`
# RUNNR is assigned sequentially by scripts/_next_runnr.py reading sim/runs.csv,
# avoiding collisions when multiple volcanoes share an NSHOW.

corsika-run:  ## Corrida parametrica. Vars: VOLCAN={fuego,acatenango,pacaya,agua} DETECTOR_POS=1 NSHOW=10000
	@test -f sim/steering/$(VOLCAN)_template.inp || \
		(echo "ERROR: no existe sim/steering/$(VOLCAN)_template.inp (volcanes: fuego, acatenango, pacaya, agua)" && exit 1)
	@mkdir -p sim/output logs/steering logs/lst
	@RUNNR_INT=$$($(PY) scripts/_next_runnr.py); \
	 RUNNR=$$(printf '%06d' $$RUNNR_INT); \
	 SEED1=$$((RUNNR_INT * 10 + 1)); \
	 SEED2=$$((RUNNR_INT * 10 + 10001)); \
	 SEED3=$$((RUNNR_INT * 10 + 20001)); \
	 sed -e "s/@NSHOW@/$(NSHOW)/g" \
	     -e "s/@RUNNR@/$$RUNNR_INT/g" \
	     -e "s/@SEED1@/$$SEED1/g" \
	     -e "s/@SEED2@/$$SEED2/g" \
	     -e "s/@SEED3@/$$SEED3/g" \
	     sim/steering/$(VOLCAN)_template.inp > sim/steering/$(VOLCAN)_run.inp; \
	 echo "VOLCAN=$(VOLCAN) pos=$(DETECTOR_POS) NSHOW=$(NSHOW) RUNNR=$$RUNNR → sim/output/DAT$$RUNNR"; \
	 rm -f sim/output/DAT$$RUNNR sim/output/$(VOLCAN)_run.lst; \
	 bash scripts/run_and_time.sh $(VOLCAN) $(DETECTOR_POS) $(NSHOW) $$RUNNR_INT $(HE_MODEL) $(CORSIKA_IMAGE) $(PWD)

# -- Batch multi-volcano ------------------------------------------------------
# Reads sim/runs_plan.yaml and runs each entry through `make corsika-run`
# sequentially under a tmux session.

batch-start:  ## Lanzar el batch de sim/runs_plan.yaml en tmux session 'batch'
	@command -v tmux >/dev/null || (echo "ERROR: tmux no esta instalado" && exit 1)
	@if tmux has-session -t batch 2>/dev/null; then \
		echo "tmux session 'batch' ya esta corriendo."; \
		echo "  ver progreso:   make sim-status"; \
		echo "  attach:         tmux attach -t batch (Ctrl+B D para detach)"; \
		echo "  detener:        make batch-stop"; \
		exit 1; \
	fi
	@mkdir -p logs
	tmux new-session -d -s batch \
		"$(PY) scripts/run_batch.py 2>&1 | tee -a logs/batch_$$(date +%Y%m%d_%H%M%S).log"
	@echo "Batch lanzado en tmux session 'batch'."
	@echo "  ver progreso:   make sim-status   (o make sim-status WATCH=1 para auto-refresh)"
	@echo "  attach:         tmux attach -t batch"

batch-stop:  ## Detener el batch. La corrida CORSIKA en curso continua hasta terminar
	@tmux kill-session -t batch 2>/dev/null && echo "Session 'batch' detenida." || echo "No hay session 'batch' corriendo."

sim-status:  ## Mostrar tabla rich con el status del batch. Var: WATCH=1 para auto-refresh
	@if [ "$(WATCH)" = "1" ]; then $(PY) scripts/sim_status.py --watch; \
	else $(PY) scripts/sim_status.py; fi

# -- Manifest -----------------------------------------------------------------

runs:  ## Mostrar el manifest sim/runs.csv con columnas alineadas
	@test -f sim/runs.csv || (echo "sin sim/runs.csv aun (correr alguna corsika-run primero)"; exit 0)
	@column -t -s, sim/runs.csv

backfill-runs:  ## Re-escanear sim/output/ y agregar runs faltantes al manifest
	@$(PY) scripts/backfill_runs_manifest.py

# -- Data ---------------------------------------------------------------------

DEM_TILE := Copernicus_DSM_COG_10_N14_00_W091_00_DEM.tif
DEM_URL  := https://copernicus-dem-30m.s3.amazonaws.com/$(basename $(DEM_TILE))/$(DEM_TILE)

download-dem:  ## Bajar el tile Copernicus DEM 30m que cubre el Fuego (~44 MB, sin auth)
	@mkdir -p data/dem
	@test -f data/dem/$(DEM_TILE) && echo "Ya existe: data/dem/$(DEM_TILE)" || \
		curl -fsSL -o data/dem/$(DEM_TILE) $(DEM_URL)
	@ls -lh data/dem/$(DEM_TILE)

# -- Tests / docs -------------------------------------------------------------

test:  ## Correr tests de analysis/ con pytest
	$(PY) -m pytest tests/ -v

export-notebooks-pdf:  ## Exportar markdown de todos los notebooks a notebooks_resumen.pdf
	$(PY) scripts/export_notebooks_pdf.py

# -- Cleanup ------------------------------------------------------------------

clean:  ## Borrar imagenes Docker locales
	-docker rmi $(CORSIKA_IMAGE) $(ML_IMAGE) 2>/dev/null

clean-output:  ## Borrar outputs de simulaciones (CUIDADO, irreversible)
	@read -p "Borrar sim/output/* ? [y/N] " ans; \
	if [ "$$ans" = "y" ]; then rm -rf sim/output/*; echo "borrado"; else echo "cancelado"; fi
