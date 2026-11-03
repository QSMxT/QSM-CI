#!/usr/bin/env bash
# PRELUDE, run as the original: FSL's `prelude` (fsl-fugue 2603.0), the reference of
# qsm_core::unwrap::unwrap_prelude. Unwraps every volume of PHASE (rad) on its own, inside MASK;
# MAG is required by `prelude -p` (with a mask given it only sets the region outside it).
# Further arguments go to prelude: `-f` (full 3-D, the report's algorithm and QSM.rs's),
# `-n N` (phase partitions; FSL's default is 8, QSM.rs's 6), `-s` (slice by slice).
# FSL's default without `-f` labels its regions slice by slice (`--labelslices`) and merges in 3-D.
#
#   bash prelude.sh PHASE MAG MASK OUT [prelude options...]
set -euo pipefail
PH="$1"; MAG="$2"; MASK="$3"; OUT="$4"; shift 4
export FSLOUTPUTTYPE=NIFTI_GZ
exec "${PRELUDE_BIN:-prelude}" -p "$PH" -a "$MAG" -m "$MASK" -o "$OUT" "$@"
