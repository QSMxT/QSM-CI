#!/usr/bin/env bash
# QSM-CI submission — QSMART (bfr+dipole stage) via QSMxT / QSM.rs.
# Total field -> susceptibility; QSMART does its own background field removal.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
# Acquisition parameters are injected as env vars — no need to parse params.json/config.json:
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
#   $QSMCI_SET_<NAME>  for each  qsm-ci run --set NAME=VALUE  override
B0=$(jq -r '.B0_dir | join(" ")' "$IN/params.json")
MAG=""; [ -f "$IN/magnitude.nii.gz" ] && MAG="--magnitude $IN/magnitude.nii.gz"
# QSMART's reliability map R_0 (optional input): only port parity supplies one, the original's own.
REL=""; [ -f "$IN/reliability.nii.gz" ] && REL="--reliability $IN/reliability.nii.gz"
# QSMART's stage maps (CONTRACT.md, "Intermediates"), when asked for and the qsmxt has
# `qsmxt qsmart --intermediates` (after v10.0.0, QSMxT/QSMxT#461). It writes vessel_mask,
# localfield_stage1, chimap_stage1, localfield_stage2, chimap_stage2 (and vessel_magnitude) as .nii.
INTER=""
if [ -n "${QSMCI_INTERMEDIATES:-}" ] && qsmxt qsmart --help 2>/dev/null | grep -q -- '--intermediates'; then
  INTER="$(mktemp -d)"
fi
qsmxt qsmart "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0 \
  --field-strength "$(jq -r .B0 "$IN/params.json")" \
  --echo-time "$(jq -r .TE[0] "$IN/params.json")" $MAG $REL ${INTER:+--intermediates "$INTER"}
if [ -n "$INTER" ]; then
  mkdir -p "$QSMCI_INTERMEDIATES"
  for f in "$INTER"/*.nii; do gzip -c "$f" > "$QSMCI_INTERMEDIATES/$(basename "$f").gz"; done
fi
