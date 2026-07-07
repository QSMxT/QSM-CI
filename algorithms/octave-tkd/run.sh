#!/usr/bin/env bash
# Runs the Octave (MATLAB-language) reconstruction. Works locally and in the container.
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
DIR="$(cd "$(dirname "$0")" && pwd)"
octave --no-gui -q --eval "cd('$DIR'); recon('$IN','$OUT')"
