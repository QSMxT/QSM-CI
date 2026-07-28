#!/usr/bin/env bash
# QSM-CI chi-separation submission (MATLAB, --runner local for the PoC). The SNU-LIST toolbox needs
# a run-time MATLAB license; env vars point at the toolbox + IPT/SPT shims + NIfTI I/O.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"; DIR="$(cd "$(dirname "$0")" && pwd)"
export CHISEP_TOOLBOX="${CHISEP_TOOLBOX:-/home/ashley/repos/qsm/chi-separation/Chisep_Toolbox_v1.1.3}"
export CHISEP_SHIMS="${CHISEP_SHIMS:-/tmp/mshims}"
export CHISEP_NIFTI="${CHISEP_NIFTI:-/home/ashley/repos/qsm/qsmci/qsmci/algorithms/matlab-tkd/nifti}"
mkdir -p "$OUT"
matlab -batch "addpath('$DIR'); recon('$IN','$OUT')"
