#!/usr/bin/env bash
# =============================================================================
# sync_figures_from_alcyon.sh
#
# Descarga (rsync) las figuras generadas en alcyon hacia el repo local,
# reemplazando cualquier PNG local que ya exista con la versión del server.
# Alcyon es la fuente de verdad para figuras: ahí corren los notebooks.
#
# Uso:
#   bash scripts/sync_figures_from_alcyon.sh
# =============================================================================
set -euo pipefail

REMOTE_HOST="alcyon"
REMOTE_DIR="/home/jarjarbinks/muon-tomography/docs/paper/figures/"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/docs/paper/figures/"

mkdir -p "${LOCAL_DIR}"

rsync -avz --progress \
    --include='*.png' \
    --exclude='*' \
    "${REMOTE_HOST}:${REMOTE_DIR}" "${LOCAL_DIR}"
