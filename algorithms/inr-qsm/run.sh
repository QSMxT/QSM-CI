#!/usr/bin/env bash
# QSM-CI submission — INR-QSM (dipole stage), CPU by default.
#
# INR-QSM is an UNSUPERVISED, subject-specific dipole inversion: it loads NO pretrained recon
# weights. A sine-activated coordinate MLP (SIREN) is OPTIMIZED per-subject at run time so that the
# susceptibility it represents, pushed through the QSM dipole forward model, reproduces the input
# local field (with edge-weighted TV + gradient-domain regularizers). Stage = dipole:
#   consumes  localfield.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# Units. The QSM-CI localfield is the tissue field already in ppm (normalized by B0), which is the
# repo's `phi` input (also ppm). Fed unchanged; the output susceptibility (ppm) is written unchanged,
# on the input affine.
#
# The B0 direction (for the dipole kernel) and voxel size are passed through from params.json / env:
#   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm).
#
# RUNTIME/GPU CAVEAT: per-subject optimization (default 50 epochs) is expensive and the reference is
# GPU-oriented (~10 GB VRAM, NVIDIA A6000). On CPU this may be slow or exceed the CI time limit — see
# README. Force CPU here for parity with the other subs; a GPU runner or fewer epochs may be needed.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

export CUDA_VISIBLE_DEVICES="-1"                         # force CPU
export INR_QSM_HOME="${INR_QSM_HOME:-/opt/INR-QSM/inr-qsm}"

mkdir -p "$OUT"

# inr_qsm_infer.py reuses the repo's SIREN model + dipole kernel + TV/GD losses, runs the per-subject
# optimization, and writes χ to chimap.nii.gz (ppm).
python "$(dirname "$0")/inr_qsm_infer.py" "$IN" "$OUT"
