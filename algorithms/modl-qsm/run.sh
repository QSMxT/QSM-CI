#!/usr/bin/env bash
# QSM-CI submission — MoDL-QSM (dipole stage), CPU-only.
#
# MoDL-QSM is a model-based unrolled dipole-inversion network. Stage = dipole:
#   consumes  localfield.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# Units. The QSM-CI localfield is the tissue field already in ppm (normalized by B0), which is
# exactly MoDL-QSM's `phi` input (the repo's example test data `phi` spans ~±0.1-0.2 ppm, not
# radians). It is fed to the network unchanged, and the output susceptibility (χ33, ppm) is written
# unchanged.
#
# NormFactor.mat. The train-set input normalization (CosTrnMean/CosTrnStd) is baked into the Keras
# graph by define_generator() — it normalizes each intermediate susceptibility estimate and
# de-normalizes after the CNN prior. recon.py runs from $MODL_QSM_HOME/test so model_test can load
# '../NormFactor.mat'; skipping it would leave the output scale wrong.
#
# The B0 direction (for the internally-generated dipole kernel) and voxel size are passed through
# from params.json / env vars:
#   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Force CPU-only TensorFlow (the repo hardcodes CUDA device 0; also set in the image).
export CUDA_VISIBLE_DEVICES="-1"
export TF_CPP_MIN_LOG_LEVEL="${TF_CPP_MIN_LOG_LEVEL:-2}"
export MODL_QSM_HOME="${MODL_QSM_HOME:-/opt/MoDL-QSM}"

# recon.py loads localfield + mask, feeds the field (ppm) to model_test — which builds the dipole
# kernel from the B0 direction and applies NormFactor.mat — then writes χ33 to chimap.nii.gz (ppm).
python "$(dirname "$0")/recon.py" "$IN" "$OUT"
