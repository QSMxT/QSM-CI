#!/usr/bin/env bash
# N4 bias field correction, run as the original: ANTs 2.4.3's N4BiasFieldCorrection with only an
# input and outputs, as QSMART's brainmask.m calls it and as QSM.rs's N4Params::default mirrors
# (no mask, shrink 4, 50x50x50x50 iterations, threshold 0, mesh 1x1x1, cubic spline, FWHM 0.15,
# Wiener noise 0.01, 200 bins). Extra arguments are passed through (e.g. `-x mask.nii.gz`).
#
#   bash n4.sh IN.nii[.gz] OUT.nii.gz [BIAS.nii.gz] [N4 options...]
#
# ITK's thread count is fixed (4), part of the fidelity record: N4's B-spline fit sums its points
# in per-thread blocks, so the output depends on it.
set -euo pipefail
IN="$1"; OUT="$2"; shift 2
BIAS=""
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then BIAS="$1"; shift; fi
export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS="${ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS:-4}"
N4="${N4_BIN:-N4BiasFieldCorrection}"
if [ -n "$BIAS" ]; then
  exec "$N4" -i "$IN" -o "[$OUT,$BIAS]" "$@"
else
  exec "$N4" -i "$IN" -o "$OUT" "$@"
fi
