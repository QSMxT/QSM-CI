# xQSM environment image — CPU-only dipole inversion (no GPU).
#
# xQSM is an octave-convolutional, noise-regularized U-Net for QSM dipole inversion. It is not a pip
# package, so we clone the repo into the image and bake its two pretrained checkpoints so the run
# phase works fully offline (--network none). run.sh (mounted at /algo) drives the repo's pure-Python
# inference entrypoint (run.py -> inference.run_xqsm).
#
# Build & push once (see algorithms/xqsm/README.md); scoring also builds this folder at score-time:
#   docker build -t ghcr.io/astewartau/qsm-ci/xqsm:v1 algorithms/xqsm
#   docker push ghcr.io/astewartau/qsm-ci/xqsm:v1
FROM python:3.10-slim

LABEL description="xQSM — CPU-only QSM dipole inversion for QSM-CI"

# curl to fetch checkpoints; git to clone the xQSM repo; libgomp1 for the PyTorch CPU (OpenMP) runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch (no CUDA libs) + xQSM's runtime deps (numpy/scipy/nibabel/pyyaml). We deliberately
# skip gradio/pydicom/matplotlib from the repo's requirements — we only use the inference path, not the
# Gradio app.
RUN pip install --no-cache-dir "torch>=2.1.0" \
        --index-url "https://download.pytorch.org/whl/cpu" \
 && pip install --no-cache-dir \
        "numpy>=1.23" "scipy>=1.10" "nibabel>=5.0" "pyyaml>=6.0"

# Clone xQSM (pinned for reproducibility) into /opt/xQSM.
ARG XQSM_REF=5d13b36
RUN git clone https://github.com/sunhongfu/xQSM.git /opt/xQSM \
 && git -C /opt/xQSM checkout "$XQSM_REF"

# Bake the pretrained checkpoints at build time (network is ON here, OFF at scoring). inference.py
# looks for them in the repo's python/ dir (CHECKPOINTS_DIR = <repo>/python), from the v1.0-demo
# GitHub Release. Pre-placing them means inference._ensure_checkpoints() finds them and never hits the
# network at run time.
RUN curl -fSL -o /opt/xQSM/python/xQSM_invivo.pth \
        https://github.com/sunhongfu/xQSM/releases/download/v1.0-demo/xQSM_invivo.pth \
 && curl -fSL -o /opt/xQSM/python/Unet_invivo.pth \
        https://github.com/sunhongfu/xQSM/releases/download/v1.0-demo/Unet_invivo.pth

ENV XQSM_DIR="/opt/xQSM" \
    CUDA_VISIBLE_DEVICES="-1"
