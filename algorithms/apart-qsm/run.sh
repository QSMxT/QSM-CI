#!/usr/bin/env bash
# APART-QSM — runs the MATLAB-compiled `recon` on the free MATLAB Runtime (no license at run time).
# The binary bundles the APART-QSM core solver, its published helpers (dipole_kernel, gradient_mask_all,
# @TVOP), the NIfTI I/O toolbox and the Optimization Toolbox. Baked into the image at /opt/qsm-ci/recon,
# or mounted at /algo/recon. See BUILD.md.
#   consumes magnitude.nii.gz, localfield.nii.gz, r2prime.nii.gz, chimap.nii.gz, mask.nii.gz, params.json
#   produces chi-para.nii.gz (χ+), chi-dia.nii.gz (χ−, positive magnitude)
# For a local (full-MATLAB, Optimization-Toolbox) run instead:
#   matlab -batch "addpath('.'); recon('IN','OUT')"  with APART_CORE (author-obtained solver) +
#   optional APART_UTILS/CHISEP_NIFTI set (see BUILD.md).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="${MATLAB_RECON:-/opt/qsm-ci/recon}"
[ -x "$BIN" ] || BIN="$DIR/recon"
export MCR_CACHE_ROOT="${MCR_CACHE_ROOT:-$(mktemp -d)}"
# CI runs the container as a homeless non-root user (--user 1000:1001). The MATLAB Runtime extracts the
# embedded CTF and starts a parpool under HOME, so point HOME at a writable dir or it fails with
# "Cannot find nonembedded CTF archive".
export HOME="${HOME:-}"; { [ -n "$HOME" ] && [ -w "$HOME" ]; } || export HOME="$MCR_CACHE_ROOT"
exec "$BIN" "$IN" "$OUT"
