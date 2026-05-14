#!/usr/bin/env bash
# =============================================================================
# deploy.sh
#
# Transfiere el proyecto al servidor dedicado y prepara la imagen Docker.
#
# Lee credenciales y rutas desde .env (ver .env.example).
#
# Estrategias:
#   build  -> rsync repo + tarball, construir imagen en el servidor
#   load   -> construir local, exportar tar, scp, docker load
#   pull   -> push local a registry, pull en servidor (requiere DOCKER_REGISTRY)
#
# Uso:
#   bash scripts/deploy.sh                  # usa DEPLOY_STRATEGY del .env
#   bash scripts/deploy.sh build            # forzar estrategia
#   bash scripts/deploy.sh --no-tarball     # solo codigo, sin tarball CORSIKA
# =============================================================================

set -euo pipefail

# ----------------------------------------------------------------------------
# Localizar repo y cargar .env
# ----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ ! -f "${REPO_ROOT}/.env" ]]; then
    cat >&2 <<EOF
ERROR: falta ${REPO_ROOT}/.env

Crear con:
  cp .env.example .env
  \$EDITOR .env       # llenar SERVER_HOST, SERVER_USER, SERVER_PROJECT_DIR
EOF
    exit 1
fi

# shellcheck disable=SC1091
set -a; source "${REPO_ROOT}/.env"; set +a

# ----------------------------------------------------------------------------
# Parseo de argumentos
# ----------------------------------------------------------------------------
STRATEGY="${DEPLOY_STRATEGY:-build}"
SKIP_TARBALL=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        build|load|pull)
            STRATEGY="$1"; shift ;;
        --no-tarball)
            SKIP_TARBALL=true; shift ;;
        -h|--help)
            sed -n '2,/^# ===/p' "$0" | grep -E '^#'
            exit 0 ;;
        *)
            echo "argumento no reconocido: $1" >&2
            exit 1 ;;
    esac
done

log() { printf '\033[1;34m[deploy]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# ----------------------------------------------------------------------------
# Validaciones
# ----------------------------------------------------------------------------
[[ -n "${SERVER_HOST:-}" ]]        || die "SERVER_HOST vacio en .env"
[[ -n "${SERVER_USER:-}" ]]        || die "SERVER_USER vacio en .env"
[[ -n "${SERVER_PROJECT_DIR:-}" ]] || die "SERVER_PROJECT_DIR vacio en .env"

SSH_PORT="${SERVER_PORT:-22}"
SSH_KEY="${SERVER_SSH_KEY:-}"
SSH_OPTS="-p ${SSH_PORT}"
RSYNC_SSH="ssh -p ${SSH_PORT}"
if [[ -n "${SSH_KEY}" ]]; then
    # Expandir tilde
    SSH_KEY="${SSH_KEY/#\~/$HOME}"
    [[ -f "${SSH_KEY}" ]] || die "SERVER_SSH_KEY apunta a archivo inexistente: ${SSH_KEY}"
    SSH_OPTS="${SSH_OPTS} -i ${SSH_KEY}"
    RSYNC_SSH="${RSYNC_SSH} -i ${SSH_KEY}"
fi

SERVER="${SERVER_USER}@${SERVER_HOST}"
TARBALL="corsika-${CORSIKA_VERSION:-78050}.tar.gz"

log "destino: ${SERVER}:${SERVER_PROJECT_DIR}"
log "estrategia: ${STRATEGY}"

# ----------------------------------------------------------------------------
# Probar conexion SSH
# ----------------------------------------------------------------------------
log "probando SSH"
if ! ssh ${SSH_OPTS} -o ConnectTimeout=10 -o BatchMode=yes "${SERVER}" "true" 2>/dev/null; then
    die "no se pudo conectar a ${SERVER}. Verificar SERVER_HOST, SERVER_USER, SERVER_SSH_KEY"
fi
log "SSH OK"

# ----------------------------------------------------------------------------
# Asegurar directorio remoto
# ----------------------------------------------------------------------------
ssh ${SSH_OPTS} "${SERVER}" "mkdir -p '${SERVER_PROJECT_DIR}'"

# ----------------------------------------------------------------------------
# Sincronizar repositorio (todas las estrategias necesitan el codigo)
# ----------------------------------------------------------------------------
log "sincronizando repo (rsync, sin .git ni outputs)"

# rsync con exclusiones equivalentes a .dockerignore + .git
rsync -avz --delete \
    -e "${RSYNC_SSH}" \
    --exclude='.git/' \
    --exclude='.env' \
    --exclude='*.pdf' \
    --exclude='sim/output/' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='corsika-*/' \
    --exclude='thesis-*.tar.gz' \
    --exclude='corsika-*.tar.gz' \
    "${REPO_ROOT}/" \
    "${SERVER}:${SERVER_PROJECT_DIR}/"

# ----------------------------------------------------------------------------
# Tarball CORSIKA (necesario para build, no para load/pull)
# ----------------------------------------------------------------------------
if [[ "${STRATEGY}" == "build" && "${SKIP_TARBALL}" == "false" ]]; then
    if [[ ! -f "${REPO_ROOT}/${TARBALL}" ]]; then
        die "falta ${TARBALL} en la raiz del repo (necesario para build remoto)"
    fi

    # rsync con resume — tarball pesa ~500 MB
    log "transfiriendo ${TARBALL} ($(du -h "${REPO_ROOT}/${TARBALL}" | cut -f1))"
    rsync -avz --progress --partial \
        -e "${RSYNC_SSH}" \
        "${REPO_ROOT}/${TARBALL}" \
        "${SERVER}:${SERVER_PROJECT_DIR}/"
fi

# ----------------------------------------------------------------------------
# Estrategia: build remoto
# ----------------------------------------------------------------------------
build_remote() {
    local he="${HE_MODEL:-1}"
    log "construyendo imagen en el servidor (15-25 min, HE_MODEL=${he})"
    ssh ${SSH_OPTS} -t "${SERVER}" "cd '${SERVER_PROJECT_DIR}' && make build-corsika HE_MODEL=${he}"
}

# ----------------------------------------------------------------------------
# Estrategia: load (tar+scp+docker load)
# ----------------------------------------------------------------------------
deploy_via_load() {
    local IMAGE_TAR="thesis-corsika-${IMAGE_TAG:-latest}.tar.gz"

    log "construyendo imagen localmente"
    (cd "${REPO_ROOT}" && make build-corsika)

    log "exportando imagen a ${IMAGE_TAR}"
    (cd "${REPO_ROOT}" && make save TAG="${IMAGE_TAG:-latest}")

    log "transfiriendo ${IMAGE_TAR} al servidor"
    rsync -avz --progress --partial \
        -e "${RSYNC_SSH}" \
        "${REPO_ROOT}/${IMAGE_TAR}" \
        "${SERVER}:${SERVER_PROJECT_DIR}/"

    log "cargando imagen en el servidor"
    ssh ${SSH_OPTS} "${SERVER}" \
        "cd '${SERVER_PROJECT_DIR}' && gunzip -c ${IMAGE_TAR} | docker load && rm ${IMAGE_TAR}"
}

# ----------------------------------------------------------------------------
# Estrategia: pull (registry)
# ----------------------------------------------------------------------------
deploy_via_pull() {
    [[ -n "${DOCKER_REGISTRY:-}" ]] || die "DEPLOY_STRATEGY=pull requiere DOCKER_REGISTRY en .env"

    log "push a registry: ${DOCKER_REGISTRY}"
    (cd "${REPO_ROOT}" && make push REGISTRY="${DOCKER_REGISTRY}" TAG="${IMAGE_TAG:-latest}")

    log "pull en el servidor"
    ssh ${SSH_OPTS} "${SERVER}" \
        "docker pull ${DOCKER_REGISTRY}/thesis-corsika:${IMAGE_TAG:-latest} \
         && docker tag ${DOCKER_REGISTRY}/thesis-corsika:${IMAGE_TAG:-latest} thesis-corsika:${IMAGE_TAG:-latest}"
}

# ----------------------------------------------------------------------------
# Ejecutar estrategia
# ----------------------------------------------------------------------------
case "${STRATEGY}" in
    build) build_remote ;;
    load)  deploy_via_load ;;
    pull)  deploy_via_pull ;;
    *) die "estrategia desconocida: ${STRATEGY} (build|load|pull)" ;;
esac

log "deploy completo"
log "validar con: make ssh   y luego en el servidor: cd ${SERVER_PROJECT_DIR} && make verify-corsika"
