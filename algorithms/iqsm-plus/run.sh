#!/usr/bin/env bash
# QSM-CI submission — iQSM+ (end-to-end stage), CPU-only.
#
# iQSM+ is a single-step, orientation-adaptive deep network: it takes the RAW WRAPPED phase and
# produces susceptibility directly (unwrap + background-field removal + dipole inversion in one
# forward pass). Hence stage = end-to-end:
#   consumes  phase.nii.gz, magnitude.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# Units: QSM-CI `phase` is the RAW WRAPPED phase in radians — exactly iQSM+'s expected input (the
# network unwraps internally). No conversion to ppm is applied on input. The output χ is in ppm,
# which is the QSM-CI chimap unit.
#
# Orientation: iQSM+ is orientation-adaptive — its OA-LFE blocks consume the B0 direction vector, so
# oblique/sagittal/coronal acquisitions reconstruct correctly. We pass it via --b0-dir.
#
# Multi-echo: QSM-CI `phase` is 4D (x,y,z,echo). We hand iQSM+ the 4D phase via --echo_4d and let its
# own CLI do the per-echo inference + magnitude×TE² weighted combination (rather than re-implementing
# it here). Single-echo (3D) phase is handled by the same flag.
#
# Acquisition parameters are injected as env vars (see CONTRACT.md):
#   $QSMCI_B0 (T)   $QSMCI_TE (s, space-separated)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"

# Force CPU-only torch (belt-and-braces; also set in the image).
export CUDA_VISIBLE_DEVICES="-1"

# The iQSM+ engine (cloned + weights baked at build time) lives here.
IQSM_PLUS_HOME="${IQSM_PLUS_HOME:-/opt/iQSM_Plus}"

# ── B0 direction (orientation-adaptive input) ───────────────────────────────
# Prefer the env var; fall back to params.json; default axial [0 0 1].
if [ -n "${QSMCI_B0_DIR:-}" ]; then
  B0_DIR="$QSMCI_B0_DIR"
elif command -v jq >/dev/null 2>&1 && [ -f "$IN/params.json" ]; then
  B0_DIR="$(jq -r '.B0_dir | join(" ")' "$IN/params.json")"
else
  B0_DIR="0 0 1"
fi
# shellcheck disable=SC2086
set -- $B0_DIR
BDX="${1:-0}"; BDY="${2:-0}"; BDZ="${3:-1}"

# ── Echo times (seconds) ────────────────────────────────────────────────────
# QSM-CI provides TE(s) in seconds; iQSM+ --te takes seconds. Length must match the phase echo dim.
if [ -n "${QSMCI_TE:-}" ]; then
  TE_S="$QSMCI_TE"
elif command -v jq >/dev/null 2>&1 && [ -f "$IN/params.json" ]; then
  TE_S="$(jq -r '.TE | map(tostring) | join(" ")' "$IN/params.json")"
else
  echo "ERROR: no echo time(s) available (QSMCI_TE / params.json TE)" >&2
  exit 1
fi

# ── B0 field strength (Tesla) ───────────────────────────────────────────────
B0_T="${QSMCI_B0:-3.0}"

# ── Voxel size (mm) — optional; iQSM+ reads the NIfTI header otherwise ───────
VOXEL_ARG=()
if [ -n "${QSMCI_VOXEL_SIZE:-}" ]; then
  # shellcheck disable=SC2206
  VOX=($QSMCI_VOXEL_SIZE)
  if [ "${#VOX[@]}" -eq 3 ]; then
    VOXEL_ARG=(--voxel-size "${VOX[0]}" "${VOX[1]}" "${VOX[2]}")
  fi
fi

mkdir -p "$OUT"

# ── Run iQSM+ ───────────────────────────────────────────────────────────────
# --echo_4d takes the 4D (or 3D single-echo) wrapped phase; --te lists per-echo TEs in seconds.
# The engine writes iQSM_plus.nii.gz (combined χ, ppm) into --output; we rename it to chimap.nii.gz.
# shellcheck disable=SC2086
python "$IQSM_PLUS_HOME/run.py" \
  --echo_4d "$IN/phase.nii.gz" \
  --te $TE_S \
  --mag "$IN/magnitude.nii.gz" \
  --mask "$IN/mask.nii.gz" \
  --b0 "$B0_T" \
  --b0-dir "$BDX" "$BDY" "$BDZ" \
  "${VOXEL_ARG[@]}" \
  --output "$OUT"

# The engine's canonical output filename is iQSM_plus.nii.gz; QSM-CI scores chimap.nii.gz.
mv -f "$OUT/iQSM_plus.nii.gz" "$OUT/chimap.nii.gz"

# Per-echo iQSM_plus_e<i>.nii.gz and echo<i>_output/ folders may be left behind by the multi-echo
# combiner — harmless; QSM-CI only reads the canonical chimap.nii.gz.
