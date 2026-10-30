# Laplacian field mapping (QSM.jl)

Multi-echo B0 field mapping with the original QSM.jl code (fde4b92): `unwrap_laplacian` on every echo (DCT solver, Neumann boundary on the array), each echo scaled to ppm by its own TE, then QSM.jl's magnitude-weighted echo average `multi_echo_average(...; TEs, W = magnitude)` (or `multi_echo_linear_fit`).

- **Stage:** `field-mapping` (reads `phase`, `magnitude`, `mask`, `params`)
- **Code:** QSM.jl at fde4b92 (v0.5.4), the authors' package, called from `recon.jl` with the package's own
  defaults. [`qsmci_io.jl`](qsmci_io.jl) only reads the inputs, applies `--set` overrides and
  writes the output.
- **Environment:** the shared Julia base image [`algorithms/_julia`](../_julia) (Julia 1.10.11,
  Manifest committed there, packages compiled into a sysimage), pinned by digest in `algorithm.yml`.
- **QSM.rs port:** [`laplacian-qsmrs`](../laplacian-qsmrs) (same `algorithm: laplacian`).
- **Parity only:** the reference of the port's parity pair (`parity/thresholds.yml`, [docs/parity.md](../../docs/parity.md)); not scored and not on the leaderboard.
- **Reference:** Schofield & Zhu, Optics Letters 2003 · doi:[10.1364/OL.28.001194](https://doi.org/10.1364/OL.28.001194)

## How QSM-CI runs it

```bash
qsm-ci run laplacian-qsmjl --phase phase.nii.gz --magnitude magnitude.nii.gz --mask mask.nii.gz --params params.json
```

`run.sh` starts Julia with 4 threads (FFTW 4, BLAS 1) and the image's `qsmjl.so` sysimage.

## Parameters

Defaults are the original's. The *QSM.rs-matched* column is what to `--set` so the pair computes
the same thing as far as the original allows.

| parameter | default | QSM.rs-matched | description |
|---|---|---|---|
| `solver` | dct |  | Poisson solver: dct / fft / mgpcg. QSM.jl's own default, mgpcg, puts a Dirichlet boundary on the mask and so also removes the harmonic background, which belongs to the bfr stage; dct unwraps only |
| `combine` | average |  | echo combination: average (multi_echo_average with TEs and W = magnitude: sum(mag*phase)/sum(mag*TE), the phase-SNR weighting) / linear-fit (multi_echo_linear_fit, W = magnitude, with a phase-offset term) |
| `mask_phase` | false | true | zero the wrapped phase outside the mask before unwrapping (QSM.jl's README passes the raw phase) |
| `demean` | false | true | subtract each unwrapped echo's mean inside the mask before combining (QSM-CI glue, not QSM.jl: the DCT solution of each echo is defined only up to a constant) |

## Against the QSM.rs port

- `laplacian-qsmrs` (QSM.rs v0.39.0) zeroes the phase outside the mask, unwraps each echo with the same DCT solver, subtracts each echo's masked mean, and takes the phase-SNR weighted average `Σ mag·φ / Σ mag·TE`. `--set mask_phase=true demean=true` makes QSM.jl compute the same steps; QSM.jl itself has neither step.
