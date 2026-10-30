#!/usr/bin/env bash
# QSM-CI submission — TGV (bfr+dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Units: since qsmxt v10.0.0, `qsmxt invert tgv` takes the field in ppm (QSM-CI's totalfield
# contract) and writes χ in ppm, with no --echo-time / --field-strength. Its α are in ppm too, so a
# value means the same at every TE and field strength. (Before v10 the command expected a phase in
# radians and this script passed a dummy TE·B0 with 2π·γ·TE·B0 = 1 so a ppm field passed straight
# through; α given here were therefore already ppm-valued, and an override from that era means the
# same thing now.)
#
# REGULARIZATION DEFAULT: QSMxT's own (QSM.rs TgvParams::default — α1 = 0.0005 / 7.49 = 6.675e-5 ppm,
# α0 = 0.0015 / 7.49 = 2.002e-4 ppm: the Langkammer/nipype rad-domain α at the 7 T / 4 ms reference).
# Earlier QSM-CI releases passed α1 = 0.0005, α0 = 0.0015 here, because the bare default of the time
# (α = 0.001 in these units) over-smoothed; the v10 default is weaker than both, so that reason no
# longer applies and no α is passed unless overridden.

# Parameter overrides (qsm-ci run --set NAME=VALUE) arrive as /input/config.json.
SET=""
CFG="$IN/config.json"
if [ -f "$CFG" ]; then
  V=$(jq -r '.iterations // empty' "$CFG"); [ -n "$V" ] && SET="$SET --iterations $V"
  V=$(jq -r '.alpha1 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --alpha1 $V"
  V=$(jq -r '.alpha0 // empty' "$CFG"); [ -n "$V" ] && SET="$SET --alpha0 $V"
  # TGV.jl's divergence and mask erosion, for the tgv-tgvjl parity pair (qsmxt after v10.0.0,
  # QSMxT/QSMxT#460; an older qsmxt refuses the flag rather than ignoring it).
  V=$(jq -r 'if has("reference_divergence") then .reference_divergence | tostring else empty end' "$CFG")
  if [ "$V" = true ]; then SET="$SET --reference-divergence"; fi
  V=$(jq -r 'if has("reference_edge_erosion") then .reference_edge_erosion | tostring else empty end' "$CFG")
  if [ "$V" = true ]; then SET="$SET --reference-edge-erosion"; fi
fi

# QSMxT after v10.0.0 (QSM.rs main, run by the parity workflow's qsmxt builds) ports TGV.jl's
# qsm_tgv as it is: the field is scaled to phase at an echo time (--te, default the first), α are
# in the package's rad units at that TE and B0, and the iteration count comes from the voxel size.
# That CLI needs the field strength and echo times. Until the pin moves to such a release this
# branch runs only there; the α overrides above then mean rad-unit α (algorithm.yml documents the
# pinned v10's ppm α), so `--set alpha*` values from v10 do not carry over.
if qsmxt invert tgv --help 2>/dev/null | grep -q -- '--field-strength'; then
  FS=$(jq -r '.B0' "$IN/params.json"); TES=$(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")
  SET="$SET --field-strength $FS --echo-times $TES"
fi
qsmxt invert tgv "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" --b0-direction $B0 $SET
