#!/usr/bin/env bash
# QSM-CI submission — IR2QSM (dipole stage), CPU-only, PyTorch.
#
# IR2QSM is a pretrained deep-learning dipole-inversion network (an "IR2U-net": a tailored 3D U-net
# iterated 4 times with reverse concatenations and a recurrent SRU middle module). It takes the LOCAL
# (tissue) field and produces susceptibility. Hence stage = dipole:
#   consumes  localfield.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# Units: the QSM-CI localfield is the local/tissue field already in ppm (normalized by B0), which is
# exactly what IR2QSM was trained on (their `lfs`). Unlike QSMnet there is NO dataset mean/std
# normalization — the field is fed to the net directly and the output is already in ppm. ir2qsm_infer.py
# only zero-pads each dim to a multiple of 8 (the U-net's 3 pool/deconv levels) and crops back.
#
# Orientation/voxel size are carried by the input NIfTI affine (read + written unchanged), so
# $QSMCI_B0_DIR / $QSMCI_VOXEL_SIZE (see CONTRACT.md) are not consumed by this path. Trained at 1 mm
# isotropic.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

export CUDA_VISIBLE_DEVICES="-1"                         # force CPU

# The IR2QSM repo (with the baked checkpoint) lives in the image; run.sh + the wrapper are at /algo.
export IR2QSM_CODE="${IR2QSM_CODE:-/opt/IR2QSM/Evaluate}"
export IR2QSM_CKPT="${IR2QSM_CKPT:-/opt/IR2QSM/Evaluate/model_IR2Unet.pth}"

mkdir -p "$OUT"

python "$SCRIPT_DIR/ir2qsm_infer.py" \
  "$IN/localfield.nii.gz" \
  "$IN/mask.nii.gz" \
  "$OUT/chimap.nii.gz"
