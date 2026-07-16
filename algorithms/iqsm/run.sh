#!/usr/bin/env bash
# QSM-CI submission — iQSM (end-to-end span), CPU-only.
#
# iQSM is a single-step deep network (LoT-Unet) that goes straight from raw wrapped MRI phase to
# susceptibility chi — phase unwrapping, background-field removal, and dipole inversion all happen
# inside the network. Hence stage = end-to-end:
#   consumes  phase.nii.gz, magnitude.nii.gz, mask.nii.gz, params.json   ->   produces  chimap.nii.gz
#
# Units:
#   * Input phase is RAW WRAPPED phase in radians — exactly what iQSM ingests (it multiplies by the
#     sign convention and Laplacian-preprocesses internally). QSM-CI's phase.nii.gz is in radians,
#     so it is passed through unchanged (no ppm conversion — iQSM does NOT take a field map).
#   * Output chi is already in ppm (the network is trained to output ppm susceptibility). No
#     rescaling is applied; iQSM.nii.gz is copied verbatim to chimap.nii.gz.
#
# Multi-echo: iQSM runs the net per echo and combines them with magnitude x TE^2 weighting. We hand
# the 4D phase + 4D magnitude to run.py's own CLI (--echo_4d --mag), which reproduces exactly that
# combination — we do not re-implement it. A 3D (single-echo) phase is handled by the same code path.
#
# B0 direction: base iQSM assumes an axial acquisition (B0 ~ [0,0,1]); the network takes no B0_dir
# argument, so QSMCI_B0_DIR is informational only and is not passed through.
#
# Acquisition parameters are injected as env vars (see CONTRACT.md):
#   $QSMCI_B0 (T)   $QSMCI_TE / $QSMCI_TE0 (s)   $QSMCI_B0_DIR   $QSMCI_VOXEL_SIZE (mm)
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
IQSM_HOME="${IQSM_HOME:-/opt/iqsm}"

# Force CPU (belt-and-braces; also set in the image).
export CUDA_VISIBLE_DEVICES="-1"

mkdir -p "$OUT"

# B0 field strength (T): prefer env var, fall back to params.json, default 3 T.
if [ -n "${QSMCI_B0:-}" ]; then
  B0="$QSMCI_B0"
else
  B0="$(jq -r '.B0 // 3' "$IN/params.json")"
fi

# Echo time(s) in SECONDS, one per phase echo. Prefer env var (space-separated), else params.json.
if [ -n "${QSMCI_TE:-}" ]; then
  read -r -a TE_S <<< "$QSMCI_TE"
else
  # shellcheck disable=SC2207
  TE_S=($(jq -r '.TE | if type=="array" then .[] else . end' "$IN/params.json"))
fi
if [ "${#TE_S[@]}" -eq 0 ]; then
  echo "iQSM: no TE found in params.json / QSMCI_TE" >&2
  exit 1
fi

# Optional magnitude (used for magnitude x TE^2 multi-echo combination).
MAG_ARG=()
if [ -f "$IN/magnitude.nii.gz" ]; then
  MAG_ARG=(--mag "$IN/magnitude.nii.gz")
fi

# run.py's --echo_4d path splits a 4D phase into per-echo volumes and combines them; a 3D phase is
# treated as single-echo by the same flag. --te is in seconds. We only need chi, so skip iQFM.
python "$IQSM_HOME/run.py" \
  --echo_4d "$IN/phase.nii.gz" \
  --te "${TE_S[@]}" \
  "${MAG_ARG[@]}" \
  --mask "$IN/mask.nii.gz" \
  --b0 "$B0" \
  --no-iqfm \
  --output "$OUT/iqsm_run"

# iQSM writes the susceptibility map as iQSM.nii.gz (in ppm). Publish it under the canonical name.
cp "$OUT/iqsm_run/iQSM.nii.gz" "$OUT/chimap.nii.gz"
