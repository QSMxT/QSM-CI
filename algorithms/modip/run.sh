#!/usr/bin/env bash
# QSM-CI submission — MoDIP (dipole stage), CPU by default.
#
# MoDIP is an UNSUPERVISED / untrained model-based deep-image-prior dipole inversion: it loads NO
# pretrained weights. A small 3D U-Net is OPTIMIZED per-subject at run time to fit the input local
# field through the QSM dipole forward model. Stage = dipole:
#   consumes  localfield.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# Units. The QSM-CI localfield is the tissue field already in ppm (normalized by B0), which is
# MoDIP's expected local-field input. It is fed unchanged; the output susceptibility (ppm) is written
# unchanged, on the input affine.
#
# The B0 direction (for the internally-generated dipole kernel) and voxel size are passed through
# from params.json / env vars:  $QSMCI_B0_DIR  $QSMCI_VOXEL_SIZE (mm).
#
# RUNTIME/GPU CAVEAT: per-subject optimization (default 500 iterations) is expensive and the
# reference is GPU-oriented. On CPU this may be slow or exceed the CI time limit — see README. Force
# CPU here for parity with the other subs; a GPU runner or a lower epoch_num may be needed to fit CI.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

export CUDA_VISIBLE_DEVICES="-1"                         # force CPU
export MODIP_HOME="${MODIP_HOME:-/opt/MoDIP}"

mkdir -p "$OUT"

# modip_infer.py loads localfield + mask, drives the repo's inference.run_modip optimization loop
# (dipole built from B0 direction + voxel size), then writes χ to chimap.nii.gz (ppm).
python "$(dirname "$0")/modip_infer.py" "$IN" "$OUT"
