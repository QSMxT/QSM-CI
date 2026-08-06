#!/usr/bin/env bash
# QSM-CI submission — DIP-UP phase unwrapping (field-mapping stage), GPU-capable / CPU-optional.
#
# DIP-UP is a PRETRAINED-net + test-time Deep-Image-Prior PHASE UNWRAPPING method. It unwraps a
# single echo of wrapped phase; it does NOT itself produce a total field. This wrapper runs DIP-UP on
# EACH echo, then does the standard per-voxel echo-fit + B0 normalization to a total field in ppm
# (the same echo-fit math as laplacian-fieldmap / romeo-fieldmap). Stage = field-mapping:
#   consumes  phase.nii.gz (multi-echo, rad), mask.nii.gz, params.json   ->   produces  totalfield.nii.gz (ppm)
#
# The base-net checkpoints (PHU-NET3D.pth / PhaseNet3D.pth) and the DIP-UP repo network defs are baked
# into the image (see Dockerfile); the reconstructed Unet_blocks.py is mounted with this wrapper.
#
# RUNTIME/GPU CAVEAT: the reference recommends a 16–24 GB GPU. The test-time DIP loop runs once PER
# ECHO, so cost scales with (iterations x echoes). On CPU this can be slow — see README.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Device is chosen at run time: use the GPU when the runner exposes one (torch.cuda.is_available()),
# otherwise CPU. Set QSMCI_FORCE_CPU=1 to force CPU even on a GPU host (parity / reproducibility).
[ "${QSMCI_FORCE_CPU:-0}" = "1" ] && export CUDA_VISIBLE_DEVICES="-1"
export DIPUP_HOME="${DIPUP_HOME:-/opt/DIP-UP}"
export DIPUP_WEIGHTS="${DIPUP_WEIGHTS:-/opt/dip-up-weights}"

mkdir -p "$OUT"

# dip_up_infer.py loads the chosen base net + weights, runs the DIP refinement per echo, does the
# echo-fit -> ppm, and writes totalfield.nii.gz on the input affine.
python "$(dirname "$0")/dip_up_infer.py" "$IN" "$OUT"
