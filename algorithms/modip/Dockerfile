# MoDIP environment image — CPU-capable PyTorch, per-subject deep-image-prior QSM dipole inversion.
#
# MoDIP (github.com/sunhongfu/MoDIP; also mirrored in sunhongfu/deepMRI/MoDIP) is UNSUPERVISED:
# there are NO pretrained weights to download. A small 3D U-Net (deep image prior) is optimized
# directly on the input local field at inference time, driven by the QSM dipole forward model. So
# this image only needs the method source + a PyTorch runtime — no weights step.
#
# We clone the repo at BUILD time (network is ON) into /opt/MoDIP so the run phase works fully
# offline (--network none). We do NOT COPY the submission code — run.sh + modip_infer.py are mounted
# at /algo at run time (QSM-CI execution model).
#
# GPU-capable, CPU-optional: we install the default (CUDA) PyTorch wheel, which also runs on CPU-only
# hosts (torch falls back to CPU when no GPU is visible). Device is chosen AT RUN TIME —
# run.sh uses the GPU when the runner exposes one (QSM-CI's --runner passes --nv / --gpus all under
# QSMCI_GPU=1) and CPU otherwise, or on demand via QSMCI_FORCE_CPU=1. See README "RUNTIME/GPU CAVEAT".
#
# Build & push once (see algorithms/modip/README.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/modip:v2 algorithms/modip
#   docker push ghcr.io/astewartau/qsm-ci/modip:v2
FROM python:3.10-slim

LABEL description="MoDIP — GPU-capable (CPU-optional) per-subject deep-image-prior QSM dipole inversion for QSM-CI"

# git to clone the repo; libgomp1 for the PyTorch (OpenMP) CPU runtime; ca-certificates for TLS.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Default (CUDA) PyTorch wheel + NIfTI/array deps. The CUDA wheel bundles its own CUDA runtime, so it
# needs only an NVIDIA driver at run time (via --nv/--gpus) and otherwise falls back to CPU cleanly.
RUN pip install --no-cache-dir \
        "torch==2.13.0" \
 && pip install --no-cache-dir \
        "numpy==2.2.6" \
        "scipy==1.15.3" \
        "nibabel==5.4.2"

# Clone MoDIP (no weights — the network is optimized per subject at run time) into /opt/MoDIP.
# Pin a ref for reproducibility (override with --build-arg MODIP_REF=<sha>).
# Pinned (QSMxT/QSM-CI#301) to what the published image holds, so its scores stand: the head of the
# default branch then and now.
ARG MODIP_REF=59959f8349af43e7aa57bcf02ea74a3c918af4d3
RUN git clone https://github.com/sunhongfu/MoDIP /opt/MoDIP \
 && git -C /opt/MoDIP checkout "$MODIP_REF"
ENV MODIP_HOME="/opt/MoDIP"

# Device is selected at run time by run.sh (GPU when exposed, else CPU; force CPU with
# QSMCI_FORCE_CPU=1) — no build-time CUDA lock.
