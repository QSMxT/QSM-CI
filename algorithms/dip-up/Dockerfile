# DIP-UP environment image — GPU-capable (CPU-optional) PyTorch, pretrained phase-unwrapping net +
# test-time Deep-Image-Prior refinement, packaged as a QSM-CI field-mapping submission.
#
# DIP-UP (github.com/sunhongfu/DIP-UP; Zhu et al., Information 2025) UNWRAPS a single echo of wrapped
# phase: a PRETRAINED 3-D CNN predicts the per-voxel integer wrap-count, and a test-time DIP loop
# fine-tunes that net on the specific input under a Laplacian-consistency + masked-TV loss. So unlike
# INR-QSM this method IS weight-dependent — it needs the base-net checkpoints:
#   * PHU-NET3D.pth   — 2-channel [wrapped phase, Laplacian], width 64  (paper default)
#   * PhaseNet3D.pth  — 1-channel [wrapped phase],            width 48
# both published on the authors' Dropbox (see BUILD.md). We BAKE the checkpoints into the image at
# build time so the run phase is fully offline (--network none). We also clone the DIP-UP repo (its
# Unet_*Chan_9Class network classes are reused by the wrapper). The DIP-UP repo does NOT ship the
# Unet_blocks.py the network classes import — it is reconstructed in this folder (Unet_blocks.py,
# byte-compatible with the released state_dicts) and mounted with the wrapper at run time.
#
# We do NOT COPY the submission code — run.sh + dip_up_infer.py + Unet_blocks.py are mounted at /algo
# at run time (QSM-CI execution model). Only the repo (network defs) and the weights are baked in.
#
# GPU-capable, CPU-optional: the default (CUDA) PyTorch wheel also runs on CPU-only hosts (torch falls
# back when no GPU is visible). Device is chosen AT RUN TIME by run.sh — GPU when the runner exposes
# one (QSM-CI's --runner passes --nv / --gpus all under QSMCI_GPU=1), else CPU, or on demand via
# QSMCI_FORCE_CPU=1. The reference recommends a 16–24 GB GPU; see README "RUNTIME/GPU CAVEAT".
#
# Build & push once (see algorithms/dip-up/BUILD.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/dip-up:v1 algorithms/dip-up
#   docker push  ghcr.io/astewartau/qsm-ci/dip-up:v1
FROM python:3.10-slim

LABEL description="DIP-UP — pretrained CNN + Deep-Image-Prior phase unwrapping (field-mapping) for QSM-CI"

# git to clone the repo; libgomp1 for the PyTorch CPU (OpenMP) runtime; ca-certificates for TLS;
# curl + unzip to fetch and unpack the Dropbox checkpoints.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git libgomp1 curl unzip \
    && rm -rf /var/lib/apt/lists/*

# Default (CUDA) PyTorch wheel + NIfTI/array deps. The CUDA wheel bundles its own CUDA runtime, so it
# needs only an NVIDIA driver at run time (via --nv/--gpus) and falls back to CPU when none is visible.
RUN pip install --no-cache-dir \
        "torch>=2.1.0" \
 && pip install --no-cache-dir \
        "numpy>=1.23" \
        "scipy>=1.10" \
        "nibabel>=5.0"

# Clone DIP-UP (the Unet_2Chan_9Class / Unet_1Chan_9Class network classes are reused by the wrapper).
# Pin a ref for reproducibility (override with --build-arg DIPUP_REF=<sha>).
ARG DIPUP_REF=bae8a90469140841fb44f5b02555c1c45016932a
RUN git clone https://github.com/sunhongfu/DIP-UP /opt/DIP-UP \
 && git -C /opt/DIP-UP checkout "$DIPUP_REF"
ENV DIPUP_HOME="/opt/DIP-UP"

# Bake the pretrained checkpoints into the image so the run phase is offline. The Dropbox FOLDER URL
# with dl=1 returns a zip of {PHU-NET3D.pth, PhaseNet3D.pth}. Override the URL with --build-arg if the
# share link rotates. (~410 MB download; ~410 MB in the image.)
ARG DIPUP_WEIGHTS_URL="https://www.dropbox.com/scl/fo/r4qv54fsdznxxmqgdcwn0/AMCMT9M-hvgmZ276-hcgaV8?rlkey=di0g1drz4whpz308rn84cxnx9&dl=1"
ENV DIPUP_WEIGHTS="/opt/dip-up-weights"
RUN mkdir -p "$DIPUP_WEIGHTS" \
 && curl -fSL "$DIPUP_WEIGHTS_URL" -o /tmp/dipup_weights.zip \
 # The Dropbox folder zip carries a root "/" dir entry, so `unzip -j` prints "mapname: conversion
 # failed" and returns exit 2 (a warning) even though both .pth files extract fine. Tolerate the
 # warning; the test -f assertions below are the real correctness gate.
 && { unzip -o -j /tmp/dipup_weights.zip -d "$DIPUP_WEIGHTS" || true; } \
 && rm -f /tmp/dipup_weights.zip \
 && test -f "$DIPUP_WEIGHTS/PHU-NET3D.pth" \
 && test -f "$DIPUP_WEIGHTS/PhaseNet3D.pth"

# Device is selected at run time by run.sh (GPU when exposed, else CPU; force CPU with
# QSMCI_FORCE_CPU=1) — no build-time CUDA lock.
