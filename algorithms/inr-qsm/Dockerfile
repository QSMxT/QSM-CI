# INR-QSM environment image — CPU-capable PyTorch, per-subject implicit-neural-representation QSM.
#
# INR-QSM (github.com/AMRI-Lab/INR-QSM) is UNSUPERVISED and subject-specific: there are NO pretrained
# weights for the reconstruction network. A sine-activated coordinate MLP (SIREN) is OPTIMIZED
# directly on the input local field at inference time, driven by the QSM dipole forward model plus
# edge-weighted TV / gradient-domain regularizers.
#
#   * The repo ships an OPTIONAL transfer-learning init (inr-qsm/transfer_learning/
#     pre_trained_weight_for_transfer_learning.pkl) used only to SPEED UP convergence — it is not a
#     trained recon model. We clone it with the repo so it is available offline, but the wrapper does
#     not require it (INR_QSM_TL_WEIGHTS controls whether it is loaded).
#   * The repo's MATLAB data-prep (STISuite FastQSM + TVweighting.m) produces the edge-weight matrix
#     WG. STISuite is proprietary MATLAB; we do NOT ship it. The wrapper reimplements the TV edge
#     weighting in Python from an in-house initial estimate (see inr_qsm_infer.py). See README.
#
# We clone the repo at BUILD time (network ON) into /opt/INR-QSM so the run phase works fully offline
# (--network none). We do NOT COPY the submission code — run.sh + inr_qsm_infer.py are mounted at
# /algo at run time (QSM-CI execution model).
#
# GPU-capable, CPU-optional: the default (CUDA) PyTorch wheel also runs on CPU-only hosts (torch
# falls back when no GPU is visible). Device is chosen AT RUN TIME by run.sh — GPU when the runner
# exposes one (QSM-CI's --runner passes --nv / --gpus all under QSMCI_GPU=1), else CPU, or on demand
# via QSMCI_FORCE_CPU=1. The reference is GPU-oriented (~10 GB VRAM, NVIDIA A6000); see README
# "RUNTIME/GPU CAVEAT".
#
# Build & push once (see algorithms/inr-qsm/README.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/inr-qsm:v2 algorithms/inr-qsm
#   docker push ghcr.io/astewartau/qsm-ci/inr-qsm:v2
FROM python:3.10-slim

LABEL description="INR-QSM — GPU-capable (CPU-optional) per-subject implicit-neural-representation QSM for QSM-CI"

# git to clone the repo; libgomp1 for the PyTorch CPU (OpenMP) runtime; ca-certificates for TLS.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Default (CUDA) PyTorch wheel + NIfTI/array/matlab-io deps. The CUDA wheel bundles its own CUDA
# runtime, so it needs only an NVIDIA driver at run time (via --nv/--gpus) and falls back to CPU.
RUN pip install --no-cache-dir \
        "torch>=2.1.0" \
 && pip install --no-cache-dir \
        "numpy>=1.23" \
        "scipy>=1.10" \
        "nibabel>=5.0"

# Clone INR-QSM (model.py / utils.py are reused by the wrapper; transfer-learning init comes along).
# Pin a ref for reproducibility (override with --build-arg INR_QSM_REF=<sha>).
ARG INR_QSM_REF=main
RUN git clone https://github.com/AMRI-Lab/INR-QSM /opt/INR-QSM \
 && git -C /opt/INR-QSM checkout "$INR_QSM_REF"
# The python package lives in the repo's inr-qsm/ subdir (model.py, utils.py, config.py, main.py).
ENV INR_QSM_HOME="/opt/INR-QSM/inr-qsm"

# Device is selected at run time by run.sh (GPU when exposed, else CPU; force CPU with
# QSMCI_FORCE_CPU=1) — no build-time CUDA lock.
