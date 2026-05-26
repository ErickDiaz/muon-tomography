# =============================================================================
# Comandos de conveniencia para el proyecto.
# Ver `make help` para la lista completa.
# =============================================================================

# Cargar .env si existe (variables del servidor). No falla si no existe.
# IMPORTANTE: el .env NO debe tener comentarios en linea (VAR=valor # comentario)
# porque Make los interpreta como parte del valor. Ver .env.example.
-include .env
export

CORSIKA_VERSION ?= 78050
CORSIKA_TARBALL := corsika-$(CORSIKA_VERSION).tar.gz

# Modelo hadronico de alta energia (ver docker/coconut.expect):
#   1=DPMJET-III, 2=EPOS.LHC-R, 3=QGSJETIII-01, 4=SIBYLL 2.3e
HE_MODEL ?= 1

REGISTRY ?= $(DOCKER_REGISTRY)
TAG      ?= $(IMAGE_TAG)
TAG      := $(if $(TAG),$(TAG),latest)

# SSH al servidor (usa variables del .env)
SSH_PORT := $(if $(SERVER_PORT),$(SERVER_PORT),22)
SSH_KEY_FLAG := $(if $(SERVER_SSH_KEY),-i $(SERVER_SSH_KEY),)
SSH_CMD := ssh -p $(SSH_PORT) $(SSH_KEY_FLAG) $(SERVER_USER)@$(SERVER_HOST)

CORSIKA_IMAGE := thesis-corsika:$(TAG)
ML_IMAGE      := thesis-ml:$(TAG)

# Argumentos comunes a docker run. -it solo se agrega en los shell-* targets
# (los batch como test-corsika y verify-corsika no leen stdin del host).
RUN_FLAGS := --rm \
	-v $(PWD)/sim:/work/sim \
	-v $(PWD)/data:/work/data \
	-v $(PWD)/scripts:/work/scripts

.PHONY: help
help:  ## Mostrar esta ayuda
	@echo "Targets disponibles:"
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# -- Verificaciones ----------------------------------------------------------

.PHONY: check-tarball
check-tarball:  ## Verificar que corsika-78050.tar.gz exista en la raiz
	@test -f $(CORSIKA_TARBALL) || \
		(echo "ERROR: falta $(CORSIKA_TARBALL) en la raiz del repo" && exit 1)
	@echo "OK: $(CORSIKA_TARBALL) presente ($$(du -h $(CORSIKA_TARBALL) | cut -f1))"

# -- Build -------------------------------------------------------------------

.PHONY: build
build: build-corsika  ## Alias: construir imagen CORSIKA

.PHONY: build-corsika
build-corsika: check-tarball  ## Construir imagen thesis-corsika
	docker build \
		-f docker/Dockerfile.corsika \
		-t $(CORSIKA_IMAGE) \
		--build-arg CORSIKA_VERSION=$(CORSIKA_VERSION) \
		--build-arg HE_MODEL=$(HE_MODEL) \
		.

.PHONY: build-ml
build-ml:  ## Construir imagen thesis-ml (Fase 3, requiere ~10 GB)
	docker build \
		-f docker/Dockerfile.ml \
		-t $(ML_IMAGE) \
		.

.PHONY: build-all
build-all: build-corsika build-ml  ## Construir ambas imagenes

# -- Run ---------------------------------------------------------------------

.PHONY: shell
shell: shell-corsika  ## Alias: shell en thesis-corsika

.PHONY: shell-corsika
shell-corsika:  ## Abrir shell interactiva en thesis-corsika
	docker run -it $(RUN_FLAGS) $(CORSIKA_IMAGE)

.PHONY: shell-ml
shell-ml:  ## Abrir shell interactiva en thesis-ml (con GPU)
	docker run -it $(RUN_FLAGS) --gpus all --shm-size=8g $(ML_IMAGE)

# -- Simulaciones ------------------------------------------------------------

.PHONY: test-corsika
test-corsika:  ## Correr fuego_test.inp (500 showers, ~8 min)
	@mkdir -p sim/output
	@rm -f sim/output/DAT001001 sim/output/DAT001001.long sim/output/fuego_test.lst
	docker run $(RUN_FLAGS) $(CORSIKA_IMAGE) bash -c \
		"cd /opt/corsika/run && \
		 corsika < /work/sim/steering/fuego_test.inp > /work/sim/output/fuego_test.lst && \
		 grep 'END OF RUN' /work/sim/output/fuego_test.lst && \
		 echo 'OK: simulacion completa'"

# Parametros para corsika-run / server-run
# RUNNR se asigna leyendo sim/runs.csv (max+1). Sequence-based, no derivado de
# NSHOW: evita colisiones entre volcanes que corran con el mismo NSHOW.
# VOLCAN y DETECTOR_POS son requeridos (default: fuego / 1).
NSHOW        ?= 5000
VOLCAN       ?= fuego
DETECTOR_POS ?= 1

# Helper: usa anaconda env si python3 no es la system shell
PY_NEXT_RUNNR := python3 scripts/_next_runnr.py 2>/dev/null || $(HOME)/anaconda3/envs/muon-tomography/bin/python3 scripts/_next_runnr.py

.PHONY: corsika-run
corsika-run:  ## Corrida parametrica. Vars: VOLCAN={fuego,acatenango,pacaya,agua} DETECTOR_POS=1 NSHOW=10000. Registra en sim/runs.csv.
	@test -f sim/steering/$(VOLCAN)_template.inp || \
		(echo "ERROR: no existe sim/steering/$(VOLCAN)_template.inp (volcanes: fuego, acatenango, pacaya, agua)" && exit 1)
	@mkdir -p sim/output logs/steering logs/lst
	@RUNNR_INT=$$($(PY_NEXT_RUNNR)); \
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

.PHONY: runs
runs:  ## Mostrar el manifest sim/runs.csv con columnas alineadas
	@test -f sim/runs.csv || (echo "sin sim/runs.csv aun (correr alguna corsika-run primero)"; exit 0)
	@column -t -s, sim/runs.csv

.PHONY: backfill-runs
backfill-runs:  ## Re-escanear sim/output/ y agregar runs faltantes al manifest
	@python3 scripts/backfill_runs_manifest.py 2>/dev/null || $(HOME)/anaconda3/envs/muon-tomography/bin/python3 scripts/backfill_runs_manifest.py

.PHONY: sync-runs
sync-runs: check-env  ## Bajar sim/runs.csv del server y mergear con local (dedup por runnr)
	@TMP=$$(mktemp); \
	 rsync -az -e "ssh -p $(SSH_PORT) $(SSH_KEY_FLAG)" \
		$(SERVER_USER)@$(SERVER_HOST):$(SERVER_PROJECT_DIR)/sim/runs.csv \
		$$TMP 2>/dev/null || { echo "server no tiene sim/runs.csv aun"; rm -f $$TMP; exit 0; }; \
	 if [ ! -f sim/runs.csv ]; then \
		mv $$TMP sim/runs.csv; \
		echo "sin local previo, copiado del server"; \
	 else \
		(head -1 sim/runs.csv; \
		 (tail -n +2 sim/runs.csv; tail -n +2 $$TMP) | sort -t, -u -k1,1n) > sim/runs.merged.csv && \
		mv sim/runs.merged.csv sim/runs.csv && \
		rm -f $$TMP && \
		echo "merged. ahora: make runs"; \
	 fi

.PHONY: prod-corsika
prod-corsika:  ## Correr fuego_prod.inp (50k showers, ~13h). RUNNR=1101 → DAT001101
	@mkdir -p sim/output
	@rm -f sim/output/DAT001101 sim/output/fuego_prod.lst
	docker run $(RUN_FLAGS) $(CORSIKA_IMAGE) bash -c \
		"cd /opt/corsika/run && \
		 corsika < /work/sim/steering/fuego_prod.inp > /work/sim/output/fuego_prod.lst && \
		 grep 'END OF RUN' /work/sim/output/fuego_prod.lst && \
		 echo 'OK: prod completa'"

# -- Datos georeferenciados --------------------------------------------------

DEM_TILE := Copernicus_DSM_COG_10_N14_00_W091_00_DEM.tif
DEM_URL  := https://copernicus-dem-30m.s3.amazonaws.com/$(basename $(DEM_TILE))/$(DEM_TILE)

.PHONY: download-dem
download-dem:  ## Bajar el tile Copernicus DEM 30m que cubre el Fuego (~44 MB, sin auth)
	@mkdir -p data/dem
	@test -f data/dem/$(DEM_TILE) && echo "Ya existe: data/dem/$(DEM_TILE)" || \
		curl -fsSL -o data/dem/$(DEM_TILE) $(DEM_URL)
	@ls -lh data/dem/$(DEM_TILE)

.PHONY: verify-corsika
verify-corsika:  ## Validar la imagen ejecutando el ejemplo all-inputs de CORSIKA
	docker run $(RUN_FLAGS) $(CORSIKA_IMAGE) bash -c \
		"cd /opt/corsika/run && corsika < all-inputs > /tmp/verify.lst 2>&1 && \
		 grep 'END OF RUN' /tmp/verify.lst && echo 'OK: CORSIKA funciona'"

# -- Distribucion --------------------------------------------------------------

.PHONY: save
save: build-corsika  ## Exportar imagen a archivo .tar (para transferir al servidor sin registry)
	docker save $(CORSIKA_IMAGE) | gzip > thesis-corsika-$(TAG).tar.gz
	@echo "Imagen exportada: thesis-corsika-$(TAG).tar.gz ($$(du -h thesis-corsika-$(TAG).tar.gz | cut -f1))"
	@echo "Transferir al servidor con:  scp thesis-corsika-$(TAG).tar.gz usuario@servidor:"
	@echo "Cargar en el servidor con:   gunzip -c thesis-corsika-$(TAG).tar.gz | docker load"

.PHONY: push
push: build-corsika  ## Push al registry (definir REGISTRY=...)
	@test -n "$(REGISTRY)" || (echo "ERROR: definir REGISTRY=ghcr.io/usuario" && exit 1)
	docker tag $(CORSIKA_IMAGE) $(REGISTRY)/$(CORSIKA_IMAGE)
	docker push $(REGISTRY)/$(CORSIKA_IMAGE)

# -- Limpieza ----------------------------------------------------------------

# -- Servidor remoto ----------------------------------------------------------

.PHONY: check-env
check-env:  ## Verificar que .env este configurado
	@test -f .env || (echo "ERROR: falta .env (cp .env.example .env y editar)" && exit 1)
	@test -n "$(SERVER_HOST)" || (echo "ERROR: SERVER_HOST vacio en .env" && exit 1)
	@test -n "$(SERVER_USER)" || (echo "ERROR: SERVER_USER vacio en .env" && exit 1)
	@echo "OK: .env apunta a $(SERVER_USER)@$(SERVER_HOST):$(SSH_PORT)"

# Helper: transferir server-setup.sh al servidor y ejecutarlo con TTY.
# scp + ssh -t separa la entrega del script de su ejecucion, lo que permite
# que sudo pueda pedir password interactivamente.
SCP_CMD := scp -P $(SSH_PORT) $(SSH_KEY_FLAG)
SSH_TTY := ssh -t -p $(SSH_PORT) $(SSH_KEY_FLAG) $(SERVER_USER)@$(SERVER_HOST)
REMOTE_SCRIPT := /tmp/thesis-server-setup.sh
GPU_ENV := INSTALL_GPU=$(if $(filter true,$(SERVER_HAS_GPU)),true,false)

# Funcion: subir script + ejecutar con accion $(1), borrar despues.
define run_server_setup
	$(SCP_CMD) scripts/server-setup.sh $(SERVER_USER)@$(SERVER_HOST):$(REMOTE_SCRIPT)
	$(SSH_TTY) '$(GPU_ENV) bash $(REMOTE_SCRIPT) $(1); ec=$$?; rm -f $(REMOTE_SCRIPT); exit $$ec'
endef

.PHONY: server-libs
server-libs: check-env  ## Instalar paquetes base (rsync, curl, git, tmux) en servidor
	$(call run_server_setup,libs)

.PHONY: server-docker
server-docker: check-env  ## Instalar Docker Engine + Compose en servidor Debian
	$(call run_server_setup,docker)

.PHONY: server-setup
server-setup: check-env  ## Setup completo: libs + Docker (idempotente, alias de libs+docker)
	$(call run_server_setup,all)

.PHONY: ssh
ssh: check-env  ## Abrir shell SSH en el servidor
	$(SSH_CMD)

.PHONY: sync-code
sync-code: check-env  ## Rsync solo de codigo al servidor (sin tarball, sin rebuild Docker)
	rsync -avz --delete \
		-e "ssh -p $(SSH_PORT) $(SSH_KEY_FLAG)" \
		--exclude='.git/' \
		--exclude='.env' \
		--exclude='*.pdf' \
		--exclude='sim/output/' \
		--exclude='sim/steering/fuego_run.inp' \
		--exclude='sim/timings.csv' \
		--exclude='data/' \
		--exclude='logs/' \
		--exclude='__pycache__/' \
		--exclude='*.pyc' \
		--exclude='corsika-*/' \
		--exclude='*.tar.gz' \
		./ $(SERVER_USER)@$(SERVER_HOST):$(SERVER_PROJECT_DIR)/

.PHONY: deploy
deploy: check-env check-tarball  ## Transferir codigo + tarball + construir imagen en servidor
	bash scripts/deploy.sh

.PHONY: deploy-load
deploy-load: check-env  ## Construir local, exportar a tar y cargar en servidor
	bash scripts/deploy.sh load

.PHONY: server-verify
server-verify: check-env  ## Validar CORSIKA en el servidor
	$(SSH_CMD) "cd $(SERVER_PROJECT_DIR) && make verify-corsika"

.PHONY: server-test
server-test: check-env  ## Correr fuego_test.inp en el servidor
	$(SSH_CMD) "cd $(SERVER_PROJECT_DIR) && make test-corsika"

# Nombre de la sesion tmux: incluye volcan y nshow para permitir multi-volcan paralelo.
SERVER_SESSION := corsika-$(VOLCAN)-$(NSHOW)

.PHONY: server-run
server-run: check-env  ## Corrida parametrica en server con tmux. Vars: VOLCAN=fuego DETECTOR_POS=1 NSHOW=10000
	@$(SSH_CMD) "command -v tmux >/dev/null || (echo 'tmux no instalado; ejecutar make server-libs'; exit 1)"
	@$(SSH_CMD) "tmux has-session -t $(SERVER_SESSION) 2>/dev/null && \
		(echo 'sesion $(SERVER_SESSION) ya existe; usar make server-run-status VOLCAN=$(VOLCAN) NSHOW=$(NSHOW)'; exit 1) || true"
	$(SSH_CMD) "mkdir -p $(SERVER_PROJECT_DIR)/logs && \
		cd $(SERVER_PROJECT_DIR) && \
		tmux new-session -d -s $(SERVER_SESSION) \
		  'make corsika-run VOLCAN=$(VOLCAN) DETECTOR_POS=$(DETECTOR_POS) NSHOW=$(NSHOW) 2>&1 | tee logs/run-$(VOLCAN)-$(NSHOW)-$$(date +%Y%m%d-%H%M%S).log'"
	@echo "OK: $(VOLCAN) pos=$(DETECTOR_POS) NSHOW=$(NSHOW) arrancada en tmux $(SERVER_SESSION). Monitor: make server-run-status VOLCAN=$(VOLCAN) NSHOW=$(NSHOW)"

.PHONY: server-run-status
server-run-status: check-env  ## Estado de la corrida parametrica. Vars: VOLCAN=fuego NSHOW=10000
	@$(SSH_CMD) "tmux has-session -t $(SERVER_SESSION) 2>/dev/null && echo 'sesion ACTIVA' || echo 'sesion TERMINADA o nunca arranco'"
	@$(SSH_CMD) "cd $(SERVER_PROJECT_DIR) && ls -1t logs/run-$(VOLCAN)-$(NSHOW)-*.log 2>/dev/null | head -1 | xargs -r tail -25"

.PHONY: server-run-attach
server-run-attach: check-env  ## Adjuntar a la sesion tmux parametrica. Vars: VOLCAN=fuego NSHOW=10000 (Ctrl+B D detach)
	$(SSH_TTY) "tmux attach-session -t $(SERVER_SESSION)"

.PHONY: server-prod
server-prod: check-env  ## Correr prod-corsika en server en tmux detached (~13h)
	@$(SSH_CMD) "command -v tmux >/dev/null || (echo 'tmux no instalado; ejecutar make server-libs'; exit 1)"
	@$(SSH_CMD) "tmux has-session -t corsika-prod 2>/dev/null && \
		(echo 'sesion corsika-prod ya existe; usar make server-prod-status'; exit 1) || true"
	$(SSH_CMD) "mkdir -p $(SERVER_PROJECT_DIR)/logs && \
		cd $(SERVER_PROJECT_DIR) && \
		tmux new-session -d -s corsika-prod \
		  'make prod-corsika 2>&1 | tee logs/prod-$$(date +%Y%m%d-%H%M%S).log'"
	@echo "OK: prod arrancada en tmux. Monitor: make server-prod-status"

.PHONY: server-prod-status
server-prod-status: check-env  ## Ver tail del log y estado de tmux de la prod en server
	@$(SSH_CMD) "tmux has-session -t corsika-prod 2>/dev/null && echo 'sesion ACTIVA' || echo 'sesion TERMINADA o nunca arranco'"
	@$(SSH_CMD) "cd $(SERVER_PROJECT_DIR) && ls -1t logs/prod-*.log 2>/dev/null | head -1 | xargs -r tail -25"

.PHONY: server-prod-attach
server-prod-attach: check-env  ## Adjuntar a la sesion tmux (Ctrl+B D para detach)
	$(SSH_TTY) "tmux attach-session -t corsika-prod"

.PHONY: server-logs
server-logs: check-env  ## Tail del ultimo .lst en sim/output/ del servidor
	$(SSH_CMD) "cd $(SERVER_PROJECT_DIR) && tail -f \$$(ls -t sim/output/*.lst | head -1)"

.PHONY: sync-output
sync-output: check-env  ## Descargar sim/output/ del servidor a local
	rsync -avz --progress \
		-e "ssh -p $(SSH_PORT) $(SSH_KEY_FLAG)" \
		$(SERVER_USER)@$(SERVER_HOST):$(SERVER_PROJECT_DIR)/sim/output/ \
		./sim/output/

# -- Limpieza ----------------------------------------------------------------

.PHONY: test
test:  ## Correr tests de analysis/ con pytest (usa env conda local)
	python3 -m pytest tests/ -v

.PHONY: export-notebooks-pdf
export-notebooks-pdf:  ## Exportar markdown de todos los notebooks a notebooks_resumen.pdf (sin codigo, sin to-dos)
	python3 scripts/export_notebooks_pdf.py

.PHONY: clean
clean:  ## Borrar imagenes locales
	-docker rmi $(CORSIKA_IMAGE) $(ML_IMAGE) 2>/dev/null
	-rm -f thesis-corsika-*.tar.gz thesis-ml-*.tar.gz

.PHONY: clean-output
clean-output:  ## Borrar outputs de simulaciones (CUIDADO, irreversible)
	@read -p "Borrar sim/output/* ? [y/N] " ans; \
	if [ "$$ans" = "y" ]; then rm -rf sim/output/*; echo "borrado"; else echo "cancelado"; fi

# -- Batch multi-volcano ----------------------------------------------------
# Lee sim/runs_plan.yaml y ejecuta cada corrida secuencialmente reusando
# `make corsika-run`. Diseñado para correr EN EL SERVIDOR bajo tmux.

.PHONY: batch-start
batch-start:  ## Lanzar el batch de sim/runs_plan.yaml en tmux session 'batch' (server-side)
	@command -v tmux >/dev/null || (echo "ERROR: tmux no esta instalado" && exit 1)
	@command -v python3 >/dev/null || (echo "ERROR: python3 no esta instalado" && exit 1)
	@if tmux has-session -t batch 2>/dev/null; then \
		echo "tmux session 'batch' ya esta corriendo."; \
		echo "  ver progreso:   make sim-status"; \
		echo "  attach:         tmux attach -t batch (Ctrl+B D para detach)"; \
		echo "  detener:        make batch-stop"; \
		exit 1; \
	fi
	@mkdir -p logs
	tmux new-session -d -s batch \
		"python3 scripts/run_batch.py 2>&1 | tee -a logs/batch_$$(date +%Y%m%d_%H%M%S).log"
	@echo "Batch lanzado en tmux session 'batch'."
	@echo "  ver progreso:   make sim-status   (o make sim-status WATCH=1 para auto-refresh)"
	@echo "  attach:         tmux attach -t batch"

.PHONY: batch-stop
batch-stop:  ## Detener el batch (mata tmux session 'batch'; la corrida CORSIKA en curso continua hasta terminar)
	@tmux kill-session -t batch 2>/dev/null && echo "Session 'batch' detenida." || echo "No hay session 'batch' corriendo."

.PHONY: sim-status
sim-status:  ## Mostrar tabla rich con el status del batch. Var: WATCH=1 para auto-refresh
	@if [ "$(WATCH)" = "1" ]; then python3 scripts/sim_status.py --watch; \
	else python3 scripts/sim_status.py; fi
