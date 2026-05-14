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
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
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

.PHONY: clean
clean:  ## Borrar imagenes locales
	-docker rmi $(CORSIKA_IMAGE) $(ML_IMAGE) 2>/dev/null
	-rm -f thesis-corsika-*.tar.gz thesis-ml-*.tar.gz

.PHONY: clean-output
clean-output:  ## Borrar outputs de simulaciones (CUIDADO, irreversible)
	@read -p "Borrar sim/output/* ? [y/N] " ans; \
	if [ "$$ans" = "y" ]; then rm -rf sim/output/*; echo "borrado"; else echo "cancelado"; fi
