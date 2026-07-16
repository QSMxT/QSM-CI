#!/usr/bin/env bash
# QSM-CI submission — QSMnet (dipole stage), CPU-only, TensorFlow 1.14 / Python 3.7.
#
# QSMnet is a pretrained 3D U-Net dipole-inversion network: it takes the LOCAL (tissue) field and
# produces susceptibility. Hence stage = dipole:
#   consumes  localfield.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# Units: the QSM-CI localfield is already the local/tissue field in ppm (normalized by B0), which is
# exactly the quantity QSMnet was trained on (their `phs_tissue`). We do NOT re-run their MATLAB
# Laplacian-unwrap / V-SHARP preprocessing. The network additionally requires normalization by the
# DATASET mean/std baked next to the checkpoint (norm_factor_<name>.mat); qsmnet_infer.py applies
# that and de-normalizes the output back to ppm.
#
# Trained at 1 mm isotropic; qsmnet_infer.py zero-pads each dim to a multiple of 16 for the U-Net's
# 4 pool/deconv levels and crops back afterwards. Orientation/voxel size are carried by the input
# NIfTI affine (read + written unchanged), so B0 direction is not consumed by this path.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

export CUDA_VISIBLE_DEVICES="-1"                         # force CPU
export TF_CPP_MIN_LOG_LEVEL="${TF_CPP_MIN_LOG_LEVEL:-2}"

# Which baked checkpoint to use — overridden to QSMnet+_64 by the qsmnet-plus image.
export QSMNET_NAME="${QSMNET_NAME:-QSMnet_64}"
export QSMNET_CKPT_DIR="${QSMNET_CKPT_DIR:-/opt/QSMnet/Checkpoints/$QSMNET_NAME}"
export QSMNET_CODE="${QSMNET_CODE:-/opt/QSMnet/Code}"

mkdir -p "$OUT"
python "$(dirname "$0")/qsmnet_infer.py" \
  "$IN/localfield.nii.gz" \
  "$IN/mask.nii.gz" \
  "$OUT/chimap.nii.gz"
