#!/usr/bin/env bash
# =============================================================================
# run_and_time.sh
#
# Corre una corrida paramétrica de CORSIKA y appendea fila al manifest
# sim/runs.csv. El steering generado ({volcan}_run.inp) y su .lst se snapshot
# ean a logs/steering/RUNNR.inp y logs/lst/RUNNR.lst para preservación.
#
# Uso (lo invoca make corsika-run):
#   bash scripts/run_and_time.sh \
#     VOLCAN DETECTOR_POS NSHOW RUNNR HE_MODEL CORSIKA_IMAGE PROJECT_ROOT
# =============================================================================
set -uo pipefail

VOLCAN="$1"
DETECTOR_POS="$2"
NSHOW="$3"
RUNNR="$4"
HE_MODEL="$5"
IMG="$6"
ROOT="$7"

RUNNR_PADDED=$(printf '%06d' "$RUNNR")

STEERING_RUN="${ROOT}/sim/steering/${VOLCAN}_run.inp"
LST_RAW="${ROOT}/sim/output/${VOLCAN}_run.lst"
DAT_RAW="${ROOT}/sim/output/DAT${RUNNR_PADDED}"

STEERING_SNAPSHOT_DIR="${ROOT}/logs/steering"
LST_SNAPSHOT_DIR="${ROOT}/logs/lst"
mkdir -p "${STEERING_SNAPSHOT_DIR}" "${LST_SNAPSHOT_DIR}"

STEERING_SNAPSHOT="${STEERING_SNAPSHOT_DIR}/${RUNNR_PADDED}.inp"
LST_SNAPSHOT="${LST_SNAPSHOT_DIR}/${RUNNR_PADDED}.lst"

# Snapshot del steering ANTES de correr (por si CORSIKA falla, queda el .inp).
cp "${STEERING_RUN}" "${STEERING_SNAPSHOT}"

START_ISO=$(date -Iseconds)
START_TS=$(date +%s)
HOST=$(hostname)

docker run --rm \
    -v "${ROOT}/sim:/work/sim" \
    -v "${ROOT}/data:/work/data" \
    -v "${ROOT}/scripts:/work/scripts" \
    "${IMG}" bash -c \
    "cd /opt/corsika/run && \
     corsika < /work/sim/steering/${VOLCAN}_run.inp > /work/sim/output/${VOLCAN}_run.lst && \
     grep 'END OF RUN' /work/sim/output/${VOLCAN}_run.lst"
RC=$?

END_TS=$(date +%s)
DUR=$((END_TS - START_TS))

if [ "${RC}" -eq 0 ]; then
    STATUS=ok
else
    STATUS=fail
fi

# Snapshot inmutable del .lst (incluye steering eco-eado + log completo).
# Hacemos copy, no move: el .lst temporario puede seguir siendo útil para
# el próximo target make que aún lo lea por nombre genérico.
if [ -f "${LST_RAW}" ]; then
    cp "${LST_RAW}" "${LST_SNAPSHOT}"
fi

# Detectar python del env (anaconda preferido, fallback a sistema).
if [ -x "${HOME}/anaconda3/envs/muon-tomography/bin/python3" ]; then
    PY="${HOME}/anaconda3/envs/muon-tomography/bin/python3"
elif command -v python3 >/dev/null; then
    PY="python3"
else
    PY="python"
fi

"${PY}" "${ROOT}/scripts/_append_run.py" \
    --runnr "${RUNNR}" \
    --volcan "${VOLCAN}" \
    --detector-pos "${DETECTOR_POS}" \
    --started-at "${START_ISO}" \
    --nshow "${NSHOW}" \
    --duration-sec "${DUR}" \
    --host "${HOST}" \
    --status "${STATUS}" \
    --lst "${LST_SNAPSHOT}" \
    --dat "sim/output/DAT${RUNNR_PADDED}" \
    --steering-snapshot "logs/lst/${RUNNR_PADDED}.lst"

# Render legible
H=$((DUR / 3600)); M=$(((DUR % 3600) / 60)); S=$((DUR % 60))
printf 'Run: RUNNR=%s volcan=%s pos=%s NSHOW=%s host=%s dur=%02d:%02d:%02d status=%s\n' \
    "${RUNNR}" "${VOLCAN}" "${DETECTOR_POS}" "${NSHOW}" "${HOST}" \
    "${H}" "${M}" "${S}" "${STATUS}"

exit "${RC}"
