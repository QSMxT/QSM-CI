#!/usr/bin/env bash
# DECOMPOSE-QSM — runs the MATLAB-compiled `recon` on the free MATLAB Runtime (no license at run time).
# The binary bundles the chi-separation toolbox, STI Suite, DECOMPOSE utils and the Optimization Toolbox
# (lsqcurvefit). Baked into the image at /opt/qsm-ci/recon, or mounted at /algo/recon. See bunya_test.md.
#   consumes magnitude.nii.gz, phase.nii.gz, mask.nii.gz, params.json
#   produces chi-para.nii.gz (χ+), chi-dia.nii.gz (χ−)
# For a local (full-MATLAB, Optimization-Toolbox) run instead:
#   matlab -batch "addpath('.'); recon('IN','OUT')"  with CHISEP_TOOLBOX/CHISEP_STISUITE/DECOMPOSE_UTILS/
#   CHISEP_NIFTI set (see bunya_test.md).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="${MATLAB_RECON:-/opt/qsm-ci/recon}"
[ -x "$BIN" ] || BIN="$DIR/recon"
export MCR_CACHE_ROOT="${MCR_CACHE_ROOT:-$(mktemp -d)}"
exec "$BIN" "$IN" "$OUT"
