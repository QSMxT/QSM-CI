#!/usr/bin/env bash
# BET, run as the original: FSL bet2 (Bostrix/FSL-BET2 d5acd7f), the reference of qsm_core::bet.
# Writes OUT_PREFIX.nii.gz (the brain) and OUT_PREFIX_mask.nii.gz (the binary mask); any further
# arguments go to bet2 (e.g. `-f 0.2`, as QSMART's brainmask.m runs it). This fork always writes
# the mask; its `-m` takes a file name (FSL's is a flag), so it is not passed. bet2 is
# single-threaded.
#
#   bash bet.sh IN.nii[.gz] OUT_PREFIX [bet2 options...]
set -euo pipefail
IN="$1"; OUT="$2"; shift 2
export FSLOUTPUTTYPE=NIFTI_GZ
exec "${BET2_BIN:-bet2}" "$IN" "$OUT" "$@"
