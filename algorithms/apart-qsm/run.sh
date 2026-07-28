#!/usr/bin/env bash
# QSM-CI chi-separation submission (MATLAB, --runner local for the PoC). APART-QSM needs a run-time
# MATLAB license. Env vars point at the APART-QSM repo (which must ALSO contain the core solver
# apart_qsm_single_ori.m — not shipped in the public repo; see BUILD.md) and the NIfTI I/O toolbox.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"; DIR="$(cd "$(dirname "$0")" && pwd)"
export APART_HOME="${APART_HOME:-/home/ashley/repos/qsm/APART-QSM/single_orientation}"
export CHISEP_NIFTI="${CHISEP_NIFTI:-/home/ashley/repos/qsm/qsmci/qsmci/algorithms/matlab-tkd/nifti}"
mkdir -p "$OUT"
matlab -batch "addpath('$DIR'); recon('$IN','$OUT')"
