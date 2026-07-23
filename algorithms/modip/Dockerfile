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
# CPU by default: we install the CPU PyTorch wheel and force CUDA off at run time. The reference is
# GPU-oriented and per-subject optimization is expensive; see algorithms/modip/README.md
# "RUNTIME/GPU CAVEAT". A GPU build would swap the torch index-url below.
#
# Build & push once (see algorithms/modip/README.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/modip:v1 algorithms/modip
#   docker push ghcr.io/astewartau/qsm-ci/modip:v1
FROM python:3.10-slim

LABEL description="MoDIP — CPU-capable per-subject deep-image-prior QSM dipole inversion for QSM-CI"

# git to clone the repo; libgomp1 for the PyTorch CPU (OpenMP) runtime; ca-certificates for TLS.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# CPU PyTorch wheel + NIfTI/array deps. Pin torch to the CPU index so no CUDA runtime is pulled in.
RUN pip install --no-cache-dir \
        "torch>=2.1.0" --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir \
        "numpy>=1.23" \
        "scipy>=1.10" \
        "nibabel>=5.0"

# Clone MoDIP (no weights — the network is optimized per subject at run time) into /opt/MoDIP.
# Pin a ref for reproducibility (override with --build-arg MODIP_REF=<sha>).
ARG MODIP_REF=master
RUN git clone https://github.com/sunhongfu/MoDIP /opt/MoDIP \
 && git -C /opt/MoDIP checkout "$MODIP_REF"
ENV MODIP_HOME="/opt/MoDIP"

# Force CPU + quiet threads at run time (override MODIP_HOME / device if building a GPU variant).
ENV CUDA_VISIBLE_DEVICES="-1"
