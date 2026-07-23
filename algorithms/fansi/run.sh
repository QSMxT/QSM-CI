#!/usr/bin/env bash
# Runs the MATLAB-compiled `recon` on the free MATLAB Runtime (no license at run time).
# The binary is either baked into the image at /opt/qsm-ci/recon (recommended) or committed
# alongside this script and mounted at /algo. No network needed.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
DIR="$(cd "$(dirname "$0")" && pwd)"
BIN="${MATLAB_RECON:-/opt/qsm-ci/recon}"
[ -x "$BIN" ] || BIN="$DIR/recon"
# MATLAB Runtime extracts its CTF archive to MCR_CACHE_ROOT; the default ($HOME/.mcrCache*) is
# not writable when the container runs as a mounted host UID with no home (e.g. GitHub-hosted
# runners: "Could not access the MATLAB Runtime component cache"). Point it at a writable temp.
export MCR_CACHE_ROOT="${MCR_CACHE_ROOT:-$(mktemp -d)}"
exec "$BIN" "$IN" "$OUT"    # the MCR wrapper sets LD_LIBRARY_PATH
