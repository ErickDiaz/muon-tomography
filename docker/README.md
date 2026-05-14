# Docker — Imagenes para el Proyecto

Dos imagenes Docker independientes:

| Imagen | Tamaño aprox. | Uso | Cuando |
|--------|---------------|-----|--------|
| **thesis-corsika** | ~2.5 GB | CORSIKA + Python para simulacion y post-procesamiento | Fases 0–2 |
| **thesis-ml** | ~10 GB | PyTorch + CUDA para entrenamiento de modelos | Fase 3 |

Las dos comparten datos por volumenes (`sim/`, `data/`), no por capas de imagen.

---

## Prerequisitos

### Estacion local (donde construyes la imagen)
- Docker Engine ≥ 24.0 (`docker --version`)
- ~15 GB libres en disco
- `corsika-78050.tar.gz` en la raiz del repo

### Servidor dedicado (donde corres las simulaciones)
- Linux con Docker instalado (`curl -fsSL https://get.docker.com | sh`)
- Para `thesis-ml`: GPU NVIDIA + [`nvidia-container-toolkit`](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- ~50–500 GB libres para outputs CORSIKA (dependiendo del NSHOW)

---

## Quick start

### 1. Construir la imagen CORSIKA

```bash
# Desde la raiz del repo
make build-corsika

# O directamente con docker:
docker build -f docker/Dockerfile.corsika -t thesis-corsika .
```

El build tarda **15–25 min** (la mayor parte es la compilacion de CORSIKA).

### 2. Validar que CORSIKA funciona

```bash
make verify-corsika
```

Debe imprimir `END OF RUN` y `OK: CORSIKA funciona`.

### 3. Correr la primera simulacion de prueba

```bash
make test-corsika
```

Esto monta `sim/steering/fuego_test.inp`, corre CORSIKA dentro del contenedor, y deja la salida en `sim/output/`.

### 4. Shell interactiva (exploracion)

```bash
make shell-corsika
```

Dentro del contenedor:
```bash
# Correr una simulacion
corsika < /work/sim/steering/fuego_test.inp > /work/sim/output/fuego_test.lst

# Leer la salida con Python
python3
>>> import corsika_panama as cp
>>> with cp.reader("/work/sim/output/DAT001001") as f:
...     for event in f:
...         print(event.header.event_number, len(event.particles))
```

---

## Desplegar al servidor dedicado (Debian)

El flujo completo está scriptado y se configura con un archivo `.env` en la raíz.

### Setup inicial (una sola vez)

1. **Copiar la plantilla y editarla:**
   ```bash
   cp .env.example .env
   $EDITOR .env
   ```
   Llenar al menos: `SERVER_HOST`, `SERVER_USER`, `SERVER_PROJECT_DIR`, `SERVER_SSH_KEY`.

2. **Validar conectividad:**
   ```bash
   make check-env       # valida .env
   make ssh             # prueba abrir shell SSH
   ```

3. **Instalar Docker en el servidor Debian** (idempotente, seguro re-correr):
   ```bash
   make server-setup
   ```
   Esto corre `scripts/server-setup.sh` por SSH e instala Docker Engine, Compose plugin y, si `SERVER_HAS_GPU=true`, el nvidia-container-toolkit.

   > Si es la primera vez, cerrar sesión y volver a entrar al servidor para que el usuario quede en el grupo `docker` sin necesitar `sudo`.

### Desplegar el proyecto

```bash
make deploy
```

Lee `DEPLOY_STRATEGY` del `.env`:
- `build` (default): rsync repo + tarball CORSIKA al servidor, construye la imagen allí.
- `load`: construye la imagen localmente, exporta a `.tar.gz`, transfiere y carga.
- `pull`: push al registry, pull en el servidor (requiere `DOCKER_REGISTRY`).

### Operar las simulaciones

```bash
make server-verify     # validar CORSIKA en el servidor
make server-test       # correr fuego_test.inp en el servidor
make server-logs       # tail -f del último .lst remoto
make sync-output       # descargar sim/output/ del servidor a local
```

---

## Transferir al servidor (manual, sin scripts)

### Opcion A — registry (recomendado si vas a iterar)

```bash
# En la estacion local
make build-corsika
docker tag thesis-corsika:latest ghcr.io/TU_USUARIO/thesis-corsika:latest
docker push ghcr.io/TU_USUARIO/thesis-corsika:latest

# En el servidor
docker pull ghcr.io/TU_USUARIO/thesis-corsika:latest
docker tag ghcr.io/TU_USUARIO/thesis-corsika:latest thesis-corsika:latest
```

### Opcion B — archivo tar (sin registry)

```bash
# En la estacion local: exporta la imagen a un tarball
make save
# Genera: thesis-corsika-latest.tar.gz (~1.5 GB comprimido)

# Transferir
scp thesis-corsika-latest.tar.gz usuario@servidor:~/

# En el servidor: cargar la imagen
gunzip -c thesis-corsika-latest.tar.gz | docker load
```

### Opcion C — build directo en el servidor

```bash
# Clonar repo + tarball en el servidor
git clone <repo> && cd physics-master-thesis
# Transferir el tarball CORSIKA aparte (no esta en git)
scp corsika-78050.tar.gz usuario@servidor:~/physics-master-thesis/

# Construir en el servidor
make build-corsika
```

Esta opcion es la mas simple si el servidor tiene buen ancho de banda y CPU para compilar.

---

## Workflow tipico de simulacion

```bash
# 1. Asegurarse de que existe el steering file
ls sim/steering/fuego_prod.inp

# 2. Correr la simulacion (background, redirigiendo log)
docker run -d \
    --name fuego_prod_001 \
    -v $(pwd)/sim:/work/sim \
    -v $(pwd)/data:/work/data \
    thesis-corsika \
    bash -c "corsika < /work/sim/steering/fuego_prod.inp > /work/sim/output/fuego_prod_001.lst 2>&1"

# 3. Monitorear progreso
docker logs -f fuego_prod_001
tail -f sim/output/fuego_prod_001.lst

# 4. Cuando termine, limpiar el contenedor
docker rm fuego_prod_001

# 5. Post-procesar
make shell-corsika
# >>> python3 scripts/analyze_run.py sim/output/DAT001101
```

Para corridas paralelas (varios shower runs simultaneos), abrir multiples contenedores con `RUNNR` y `SEED` distintos en sus steering files.

---

## Estructura de volumenes

```
host                              container
----                              ---------
sim/steering/   <----volumen---->  /work/sim/steering/    (RO en la practica)
sim/output/     <----volumen---->  /work/sim/output/      (writable)
sim/atmosphere/ <----volumen---->  /work/sim/atmosphere/  (perfiles ERA5)
data/dem/       <----volumen---->  /work/data/dem/        (DEMs SRTM/ALOS)
data/ml/        <----volumen---->  /work/data/ml/         (datasets entrenamiento)
scripts/        <----volumen---->  /work/scripts/         (analisis Python)
```

Los volumenes implican que **editar archivos en el host se refleja inmediatamente en el contenedor** y viceversa. No hay que reconstruir la imagen al cambiar un steering file.

---

## Troubleshooting

### El build falla en el paso de coconut

El script `coconut.expect` automatiza preguntas que pueden variar entre versiones. Si falla:

1. Construir hasta la etapa builder solamente para entrar a inspeccionar:
   ```bash
   docker build --target builder -f docker/Dockerfile.corsika -t corsika-builder .
   docker run --rm -it corsika-builder bash
   # Dentro del contenedor:
   cd /build/corsika-78050
   ./coconut    # ejecutar manualmente y anotar el orden de prompts
   ```
2. Ajustar `docker/coconut.expect` con el orden real.
3. Reconstruir.

### `make test-corsika` reporta "permission denied" en sim/output

```bash
# Los archivos creados por CORSIKA dentro del contenedor pertenecen a root.
# Cambiar permisos en el host:
sudo chown -R $USER:$USER sim/output/

# O correr el contenedor como tu usuario:
docker run --user $(id -u):$(id -g) ... thesis-corsika
```

### GPU no detectada en thesis-ml

```bash
# Verificar que nvidia-container-toolkit esta instalado
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# Si falla, reinstalar:
sudo apt-get install nvidia-container-toolkit
sudo systemctl restart docker
```

### La imagen es muy grande

```bash
# Ver tamaño:
docker images thesis-corsika

# Ver capas:
docker history thesis-corsika
```

Si pesa mas de 3 GB hay algo mal — probablemente quedo el toolchain de compilacion en la imagen final. Verificar que el `FROM ubuntu:22.04 AS runtime` esta despues del builder.

---

## Comandos Make disponibles

```
make help              # listar todos los targets
make build-corsika     # construir thesis-corsika
make build-ml          # construir thesis-ml
make build-all         # construir ambas
make shell-corsika     # shell interactiva
make shell-ml          # shell con GPU
make test-corsika      # correr fuego_test.inp
make verify-corsika    # validar con all-inputs de ejemplo
make save              # exportar imagen a .tar.gz
make push              # push a registry (definir REGISTRY=)
make clean             # borrar imagenes locales
```
