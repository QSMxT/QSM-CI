#!/usr/bin/env bash
# QSM-CI hc-chisep submission (hollow-cylinder signal-derived-orientation chi-separation,
# pure Python on CPU — no MATLAB, no GPU, no weights, no network).
#   consumes chimap.nii.gz (χ_total), r2prime.nii.gz, magnitude.nii.gz (multi-echo GRE),
#            mask.nii.gz, params.json  [optional: se_magnitude.nii.gz; fiber_angle.nii.gz
#            is read ONLY in the HCCHISEP_MODE=dti comparison arm]
#   produces chi-para.nii.gz (χ+), chi-dia.nii.gz (χ−, positive magnitude)
# recon.py is fully self-contained (numpy/scipy/nibabel). In the image `python` has the
# deps; for a local (--runner local) run set HCCHISEP_PYTHON to a python that has
# numpy/scipy/nibabel (see BUILD.md).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"; DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${HCCHISEP_PYTHON:-python}"
mkdir -p "$OUT"
"$PY" "$DIR/recon.py" "$IN" "$OUT"
