# =============================================================================
# thesis-ml — PyTorch + CUDA para Fase 3 (surrogate model / super-resolucion)
# =============================================================================
# Imagen separada de thesis-corsika porque:
#   - Solo se usa en Fase 3 (semanas 12-17 del plan)
#   - Pesa ~10 GB por CUDA — no contamina la imagen CORSIKA (~2.5 GB)
#   - Necesita GPU passthrough (--gpus all)
#
# Build:
#   docker build -f docker/Dockerfile.ml -t thesis-ml .
#
# Run con GPU:
#   docker run --rm -it --gpus all \
#     -v $(pwd)/sim:/work/sim \
#     -v $(pwd)/ml:/work/ml \
#     thesis-ml
#
# Verificar GPU dentro del contenedor:
#   python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
# =============================================================================

# Imagen base oficial PyTorch + CUDA 12 + cuDNN 9 (devel para tener compilers C++)
FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-devel

ARG DEBIAN_FRONTEND=noninteractive

LABEL description="PyTorch 2.4 + CUDA 12.1 para ML sobre datos CORSIKA"
LABEL phase="3"

# Dependencias del sistema (geoespacial + lectura DAT)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        proj-bin \
        libproj-dev \
        libgeos-dev \
        libhdf5-dev \
        libnetcdf-dev \
        git \
        curl \
        less \
        vim-tiny \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Dependencias Python para ML
# Reutilizamos requirements.txt de CORSIKA (numpy, scipy, etc.) y agregamos ML.
COPY docker/requirements.txt /tmp/requirements-base.txt
COPY docker/requirements-ml.txt /tmp/requirements-ml.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements-base.txt \
    && pip install --no-cache-dir -r /tmp/requirements-ml.txt \
    && rm /tmp/requirements-base.txt /tmp/requirements-ml.txt

WORKDIR /work

# Verificar instalacion al construir
RUN python3 -c "import torch; print(f'PyTorch {torch.__version__}, CUDA built: {torch.version.cuda}')"

CMD ["/bin/bash"]
