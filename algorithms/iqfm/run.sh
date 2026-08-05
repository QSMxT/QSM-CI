#!/usr/bin/env bash
# QSM-CI submission — iQFM (unwrap+bfr span), CPU-only.
#
# iQFM (Instant Quantitative Field Mapping) is the tissue/local-field output of the SAME iQSM
# network/repo. A LoT-Unet maps raw wrapped MRI phase straight to the LOCAL (tissue) field —
# phase unwrapping AND background-field removal both happen inside the network. Hence stage =
# unwrap+bfr span:
#   consumes  phase.nii.gz, magnitude.nii.gz, mask.nii.gz, params.json   ->   produces  localfield.nii.gz
#
# It is the SAME repo, run.py and weights as algorithms/iqsm/ — the iqsm submission passes
# --no-iqfm to skip exactly this output; here we run WITHOUT --no-iqfm to keep it. run.py always
# also writes iQSM.nii.gz (chi); we only publish the iQFM tissue field.
#
# Units:
#   * Input phase is RAW WRAPPED phase in radians — exactly what the network ingests (it applies the
#     sign convention and Laplacian preprocessing internally). QSM-CI's phase.nii.gz is in radians,
#     so it is passed through unchanged.
#   * Output iQFM.nii.gz is the tissue field ALREADY in ppm (B0-normalized). The LoT layer divides
#     the Laplacian-derived field by (B0 * TE) — removing the field-strength and echo-time
#     dependence — so the network is trained to output a ppm-scale field. Upstream confirms this: the
#     repo README's LFS display window is "± 0.05 ppm". QSM-CI's localfield artifact is also ppm, so
#     NO unit conversion is applied — run.sh copies iQFM.nii.gz verbatim to localfield.nii.gz.
#
# Multi-echo: the net is run per echo and per-echo field maps are combined with magnitude x TE^2
# weighting inside run.py (--echo_4d --mag), identical to iqsm — we do not re-implement it. A 3D
# (single-echo) phase is handled by the same code path.
#
# Mask: iQFM REQUIRES a brain mask (run.py auto-skips iQFM when no --mask is given). QSM-CI always
# provides mask.nii.gz, so iQFM always runs.
#
# B0 direction: base iQSM/iQFM assumes an axial acquisition (B0 ~ [0,0,1]); the network takes no
# B0_dir argument, so QSMCI_B0_DIR is informational only and is not passed through.
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
  echo "iQFM: no TE found in params.json / QSMCI_TE" >&2
  exit 1
fi

# Optional magnitude (used for magnitude x TE^2 multi-echo combination).
MAG_ARG=()
if [ -f "$IN/magnitude.nii.gz" ]; then
  MAG_ARG=(--mag "$IN/magnitude.nii.gz")
fi

# run.py's --echo_4d path splits a 4D phase into per-echo volumes and combines them; a 3D phase is
# treated as single-echo by the same flag. --te is in seconds. We run WITHOUT --no-iqfm so the iQFM
# tissue-field output is produced (run.py also writes iQSM.nii.gz, which we ignore).
python "$IQSM_HOME/run.py" \
  --echo_4d "$IN/phase.nii.gz" \
  --te "${TE_S[@]}" \
  "${MAG_ARG[@]}" \
  --mask "$IN/mask.nii.gz" \
  --b0 "$B0" \
  --output "$OUT/iqfm_run"

# iQFM writes the tissue (local) field as iQFM.nii.gz (in ppm). Publish it under the canonical name.
cp "$OUT/iqfm_run/iQFM.nii.gz" "$OUT/localfield.nii.gz"
