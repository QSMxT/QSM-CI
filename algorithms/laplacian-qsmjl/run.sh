#!/usr/bin/env bash
# QSM-CI submission: Laplacian field mapping (QSM.jl). Runs recon.jl (the authors' Julia code, called directly) in the
# pinned Julia base image (algorithms/_julia: Julia 1.10.11 + committed Manifest, sysimage).
set -euo pipefail
IN="${1:-/input}"; OUT="${2:-/output}"
HERE="$(cd "$(dirname "$0")" && pwd)"
# Fixed thread counts, part of the fidelity record (algorithm.yml `fidelity:`): 4 Julia threads
# (QSM.jl's Polyester loops, TGV's KernelAbstractions kernels), FFTW at the same count
# (qsmci_io.jl), BLAS single-threaded.
export JULIA_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1
# The image's qsmjl.so sysimage holds the compiled packages; without it (`--runner local`
# against a Julia with the same Manifest) the same code is compiled on first use.
exec julia ${QSMCI_JULIA_SYSIMAGE_DIR:+--sysimage "$QSMCI_JULIA_SYSIMAGE_DIR/qsmjl.so"} \
  --startup-file=no --history-file=no \
  "$HERE/recon.jl" "$IN" "$OUT"
