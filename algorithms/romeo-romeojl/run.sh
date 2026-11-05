#!/usr/bin/env bash
# QSM-CI submission: ROMEO field mapping (ROMEO.jl). Runs recon.jl (the authors' Julia code, called directly) in the
# pinned Julia base image (algorithms/_julia: Julia 1.10.11 + committed Manifest, sysimage).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
HERE="$(cd "$(dirname "$0")" && pwd)"
# Fixed thread counts, part of the fidelity record (algorithm.yml `fidelity:`): one Julia thread,
# FFTW at the same count (qsmci_io.jl), BLAS single-threaded. One, not the 4 of the other Julia
# submissions: ROMEO.jl's individual mode (`unwrap_individual!`, src/unwrapping.jl) unwraps the
# echoes in a `Threads.@threads` loop, each reading a neighbouring echo as `phase2` while another
# thread may be unwrapping it in place, so its result depends on the thread count. Echo by echo
# in order is the one reading that does not, and is what QSM.rs ports.
export JULIA_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
# The image's mritools.so sysimage holds the compiled packages; without it (`--runner local`
# against a Julia with the same Manifest) the same code is compiled on first use.
exec julia ${QSMCI_JULIA_SYSIMAGE_DIR:+--sysimage "$QSMCI_JULIA_SYSIMAGE_DIR/mritools.so"} \
  --startup-file=no --history-file=no \
  "$HERE/recon.jl" "$IN" "$OUT"
