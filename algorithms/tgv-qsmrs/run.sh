#!/usr/bin/env bash
# QSM-CI submission — TGV (bfr+dipole stage) via QSMxT / QSM.rs.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")

# Units: `qsmxt invert tgv` takes the field in ppm (QSM-CI's totalfield contract) and writes χ in
# ppm. Since qsmxt v11 its α are in TGV.jl's rad units at the echo time (--te, default the first)
# and the field strength, which is why the field strength and echo times are passed below.
#
# REGULARIZATION DEFAULT: QSMxT's own (QSM.rs TgvParams::default), and no α is passed unless
# overridden. From QSMxT v12.1 (astewartau/QSM.rs#478) that is α0 0.00636, α1 0.00212 (ratio 3 at
# 1.5x the strength of TGV.jl's regularization 2, from our challenge-data evaluation); qsmxt v11 and
# v12.0 have TGV.jl's regularization 2 (α0 0.002, α1 0.003). The tgv parity pair passes α0/α1 to
# both sides explicitly (parity/thresholds.yml).

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
  # TGV.jl's whole output box (the rim just outside the eroded mask), astewartau/QSM.rs#369
  # (QSMxT/QSMxT#465).
  V=$(jq -r 'if has("reference_output_box") then .reference_output_box | tostring else empty end' "$CFG")
  if [ "$V" = true ]; then SET="$SET --reference-output-box"; fi
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
