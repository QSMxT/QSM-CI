#!/usr/bin/env bash
# QSM-CI submission — AFTER-QSM (dipole stage), GPU-capable / CPU-optional.
#
# AFTER-QSM is a PRETRAINED, affine-equivariant deep dipole-inversion network: it takes the LOCAL
# (tissue) field and produces susceptibility, robust to arbitrary head orientation and anisotropic
# resolution. Stage = dipole:
#   consumes  localfield.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# Units. The QSM-CI localfield is the tissue field already in ppm (normalized by B0). AFTER-QSM is
# trained (see utils/dataset.py) on χ maps in ppm forward-projected through the UNNORMALIZED dipole
# kernel (D = 1/3 - kz²/k²), i.e. the field it expects is in the SAME units as χ = ppm. So the ppm
# local field is fed straight through with NO rescaling, and the output susceptibility (ppm) is
# written unchanged, on the input affine (inference.run_after_qsm reads and re-writes the NIfTI
# affine from the input local field).
#
# Voxel size + B0 direction. AFTER-QSM's affine-transformation stage NEEDS the true voxel size (mm)
# and B0 direction (z-projections) — the network reconstructs in a canonical axial / 0.6 mm frame and
# transforms back. We wire them from params.json via the QSM-CI env vars:
#   --voxel-size  <- $QSMCI_VOXEL_SIZE (mm, x y z)
#   --b0-dir      <- $QSMCI_B0_DIR     (unit vector, x y z)
# (see CONTRACT.md). Defaults fall back to 1 1 1 / 0 0 1 (axial) if unset.
#
# The AFTER-QSM repo (with its committed checkpoints/AFTER-QSM.pkl) lives in the image at
# $AFTERQSM_HOME; run.sh is mounted at /algo. We drive the repo's own pure-Python CLI (run.py ->
# inference.run_after_qsm), which writes AFTER-QSM_blur.nii.gz (coarse) + AFTER-QSM_deblur.nii.gz
# (refined). We publish the REFINED (deblur) map as the canonical chimap.
#
# RUNTIME / GPU CAVEAT: AFTER-QSM is GPU-oriented (8 GB+ VRAM). It is packaged but ci_skip'd (see
# algorithm.yml) until QSM-CI has a GPU runner; on CPU the two nets + full-volume 3-D affine grids do
# not fit the CI budget. See README.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Device is chosen at run time inside inference.run_after_qsm: GPU when the runner exposes one
# (torch.cuda.is_available()), otherwise CPU. Set QSMCI_FORCE_CPU=1 to force CPU even on a GPU host
# (parity / reproducibility).
[ "${QSMCI_FORCE_CPU:-0}" = "1" ] && export CUDA_VISIBLE_DEVICES="-1"

AFTERQSM_HOME="${AFTERQSM_HOME:-/opt/AFTER-QSM}"

# Voxel size (mm) and B0 direction from the QSM-CI env (populated from params.json); axial defaults.
VOX="${QSMCI_VOXEL_SIZE:-1 1 1}"
B0DIR="${QSMCI_B0_DIR:-0 0 1}"

# segment_num — step-2 refinement memory/quality knob (repo default 3; larger = less VRAM, finer
# slabs). Overridable via the declared parameter (QSMCI_SET_SEGMENT_NUM).
SEGMENT_NUM="${QSMCI_SET_SEGMENT_NUM:-3}"

mkdir -p "$OUT"
WORK="$(mktemp -d)"

# run.py -> inference.run_after_qsm reads the local field, preserves its affine, runs both stages, and
# writes AFTER-QSM_blur.nii.gz + AFTER-QSM_deblur.nii.gz into --output.
python "$AFTERQSM_HOME/run.py" \
  --lfs        "$IN/localfield.nii.gz" \
  --voxel-size $VOX \
  --b0-dir     $B0DIR \
  --segment-num "$SEGMENT_NUM" \
  --output     "$WORK"

# Publish the REFINED (deblur) susceptibility map under the canonical name (ppm, input affine).
mv "$WORK/AFTER-QSM_deblur.nii.gz" "$OUT/chimap.nii.gz"
rm -rf "$WORK"
