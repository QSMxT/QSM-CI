#!/usr/bin/env bash
set -euo pipefail
# HD-BET reads its baked weights from $HOME/hd-bet_params (image ENV HOME=/opt/hdbet). Docker honours
# that ENV, but apptainer overrides HOME to the host home, so HD-BET can't find the weights and tries
# to re-download them (fails offline). Force it back so both runners find the in-image weights.
export HOME=/opt/hdbet
IN="${1:-/input}"; OUT="${2:-/output}"
python3 "$(dirname "$0")/extract.py" "$IN" "$OUT"
