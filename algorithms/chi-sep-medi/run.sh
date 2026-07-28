#!/usr/bin/env bash
# Runs the MATLAB-compiled `recon` on the free MATLAB Runtime (no license at run time). The binary is
# baked into the image at /opt/qsm-ci/recon (recommended) or committed alongside this script and mounted
# at /algo. It bundles the chi-separation toolbox, STI Suite (QSM_iLSQR), NIfTI I/O and IPT/SPT shims.
#   consumes localfield.nii.gz, r2prime.nii.gz, mask.nii.gz, magnitude.nii.gz, params.json
#   produces chi-para.nii.gz (χ+), chi-dia.nii.gz (χ−)
# For a local (full-MATLAB) run instead: matlab -batch "addpath('.'); recon('IN','OUT')" with
# CHISEP_SHIMS/CHISEP_TOOLBOX/CHISEP_STISUITE/CHISEP_NIFTI set (see BUILD.md).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="${MATLAB_RECON:-/opt/qsm-ci/recon}"
[ -x "$BIN" ] || BIN="$DIR/recon"
# MATLAB Runtime extracts its CTF archive to MCR_CACHE_ROOT; the default ($HOME/.mcrCache*) is not
# writable when the container runs as a mounted host UID with no home. Point it at a writable temp.
export MCR_CACHE_ROOT="${MCR_CACHE_ROOT:-$(mktemp -d)}"
exec "$BIN" "$IN" "$OUT"    # the MCR wrapper sets LD_LIBRARY_PATH
