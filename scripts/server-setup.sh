#!/usr/bin/env bash
# =============================================================================
# server-setup.sh
#
# Configura un servidor Debian para correr la imagen thesis-corsika.
#
# Subcomandos:
#   libs    -> solo paquetes base del sistema (rsync, curl, git, tmux, etc.)
#   docker  -> solo Docker Engine + Compose plugin + (opcional) NVIDIA toolkit
#   all     -> ambos (default)
#
# Uso:
#   Local -> remoto en una sola pasada:
#     ssh usuario@servidor 'bash -s libs'    < scripts/server-setup.sh
#     ssh usuario@servidor 'bash -s docker'  < scripts/server-setup.sh
#     ssh usuario@servidor 'bash -s'         < scripts/server-setup.sh   # = all
#
#   Via Makefile (mas comodo):
#     make server-libs
#     make server-docker
#     make server-setup             # ambos
#
# Variables (opcionales):
#   INSTALL_GPU=true   instala nvidia-container-toolkit (solo en subcomando docker)
# =============================================================================

set -euo pipefail

readonly INSTALL_GPU="${INSTALL_GPU:-false}"
readonly ACTION="${1:-all}"

log() { printf '\033[1;34m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# ----------------------------------------------------------------------------
# Verificaciones previas comunes
# ----------------------------------------------------------------------------
preflight() {
    [[ $EUID -ne 0 ]] || die "no correr como root — el script usa sudo donde lo necesita"

    if ! grep -qi "debian" /etc/os-release; then
        warn "esto fue probado en Debian. Detectado: $(grep PRETTY_NAME /etc/os-release | cut -d= -f2)"
    fi

    log "Debian: $(lsb_release -ds 2>/dev/null || cat /etc/debian_version)"
    log "Kernel: $(uname -r)"
    log "Arquitectura: $(dpkg --print-architecture)"
}

# ----------------------------------------------------------------------------
# Subcomando: libs — paquetes base del sistema
# ----------------------------------------------------------------------------
install_libs() {
    log "instalando paquetes base"
    sudo apt-get update -qq
    sudo apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        rsync \
        git \
        htop \
        tmux

    log "libs instaladas"
}

# ----------------------------------------------------------------------------
# Subcomando: docker — Docker Engine + Compose + (opcional) NVIDIA
# ----------------------------------------------------------------------------
install_docker_engine() {
    if command -v docker &>/dev/null; then
        log "Docker ya instalado: $(docker --version)"
        return 0
    fi

    log "instalando Docker Engine desde el repo oficial"

    # curl y gnupg son requisitos — instalarlos por las dudas si saltaron libs
    sudo apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release

    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg \
        | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    DEBIAN_CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME:-bookworm}")"
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
         https://download.docker.com/linux/debian ${DEBIAN_CODENAME} stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

    sudo apt-get update -qq
    sudo apt-get install -y \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin
}

configure_docker_user() {
    if ! groups "$USER" | grep -qw docker; then
        log "agregando $USER al grupo docker (requiere logout/login despues)"
        sudo usermod -aG docker "$USER"
        warn "cerrar sesion y volver a entrar para que el cambio tome efecto"
    fi

    sudo systemctl enable --now docker

    log "verificando Docker: $(docker --version 2>/dev/null || echo 'no disponible')"
    log "verificando Compose: $(docker compose version 2>/dev/null || echo 'no disponible')"
}

install_nvidia_toolkit() {
    if [[ "$INSTALL_GPU" != "true" ]]; then
        log "skip GPU setup (INSTALL_GPU=false)"
        return 0
    fi

    if ! lspci | grep -qi nvidia; then
        warn "INSTALL_GPU=true pero no se detecto hardware NVIDIA — saltando"
        return 0
    fi

    if command -v nvidia-container-runtime &>/dev/null; then
        log "nvidia-container-toolkit ya instalado"
        return 0
    fi

    log "instalando nvidia-container-toolkit"

    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
        | sudo gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
        | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
        | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null

    sudo apt-get update -qq
    sudo apt-get install -y nvidia-container-toolkit
    sudo nvidia-ctk runtime configure --runtime=docker
    sudo systemctl restart docker

    log "probando GPU passthrough"
    docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi \
        || warn "GPU passthrough fallo — revisar driver NVIDIA en el host"
}

install_docker_full() {
    install_docker_engine
    configure_docker_user
    install_nvidia_toolkit
}

# ----------------------------------------------------------------------------
# Dispatcher
# ----------------------------------------------------------------------------
preflight

case "$ACTION" in
    libs)
        install_libs
        ;;
    docker)
        install_docker_full
        ;;
    all)
        install_libs
        install_docker_full
        ;;
    -h|--help|help)
        sed -n '2,/^# ===/p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    *)
        die "subcomando desconocido: '$ACTION' (libs|docker|all)"
        ;;
esac

# ----------------------------------------------------------------------------
# Resumen
# ----------------------------------------------------------------------------
log "setup '$ACTION' completo"

if [[ "$ACTION" != "libs" ]] && ! groups "$USER" | grep -qw docker; then
    warn "RECORDAR: cerrar sesion y volver a entrar para usar docker sin sudo"
fi
