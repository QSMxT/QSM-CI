#!/usr/bin/env bash
# QSM-CI submission — TGV (bfr+dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# REGULARIZATION DEFAULT. The bare `qsmxt invert tgv` defaults (qsm_core TgvParams::default:
# alpha1=alpha0=0.001) OVER-SMOOTH this data: alpha1 is the first-order (gradient) TGV weight, and
# 0.001 flattens genuine susceptibility contrast (measured mean|grad| ~40% of ground truth, xsim
# 0.32). The TGV-QSM reference (Langkammer et al., NeuroImage 2015 — the citation in algorithm.yml,
# and the classic tgv_qsm default) uses alpha = [alpha1=0.0005, alpha0=0.0015], i.e. a weaker
# gradient penalty. Passing those explicitly recovers the contrast (mean|grad| ~0.0094 vs 0.0074,
# xsim 0.32 -> 0.47, nrmse 64.8% -> 56.1% on data/sim/scoring). These stay overridable via config.json.
ALPHA1=0.0005; ALPHA0=0.0015; ITERS=""

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.iterations // empty' "$CFG"); [ -n "$V" ] && ITERS="$V"
  V=$(jq -r '.alpha1 // empty' "$CFG"); [ -n "$V" ] && ALPHA1="$V"
  V=$(jq -r '.alpha0 // empty' "$CFG"); [ -n "$V" ] && ALPHA0="$V"
fi
SET="--alpha1 $ALPHA1 --alpha0 $ALPHA0"
[ -n "$ITERS" ] && SET="$SET --iterations $ITERS"
# UNIT FIX (QSM-CI contract: totalfield is in ppm; QSMxT/QSM.rs `invert tgv` expects the field in
# RADIANS). Internally tgv_qsm scales its result to ppm with  chi_ppm = chi_raw / (2*pi*gamma*TE*B0),
# gamma = 42.5781 Hz/T (see QSM.rs src/inversion/tgv.rs). QSM.rs's own pipeline (run_tgv in
# src/pipeline/inversion.rs) therefore feeds it phase in radians. Passing our ppm field with the real
# TE/B0 makes TGV divide by 2*pi*gamma*TE*B0 (~7.5 here) a SECOND time -> output ~10x too small.
#
# Fix without touching the NIfTI (no python/fslmaths in the image): choose --echo-time/--field-strength
# so the internal rad->ppm scale is exactly 1, i.e. 2*pi*gamma*TE*B0 = 1. Then a ppm field passes
# straight through to a ppm chimap. This is algebraically identical to converting ppm->rad on input
# with the real TE/B0 and letting TGV convert it back (the TE/B0 cancel).
TGV_TE=$(awk 'BEGIN{ pi=atan2(0,-1); gamma=42.5781; printf "%.15g\n", 1.0/(2*pi*gamma) }')
qsmxt invert tgv "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 --field-strength 1 --echo-time "$TGV_TE" $SET
