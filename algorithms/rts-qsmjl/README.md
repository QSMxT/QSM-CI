# RTS (QSM.jl)

Rapid two-step dipole inversion, run as the original QSM.jl code (`QSM.rts`, fde4b92) by the method's first author.

- **Stage:** `dipole` (reads `localfield`, `mask`, `params`)
- **Code:** QSM.jl at fde4b92 (v0.5.4), the authors' package, called from `recon.jl` with the package's own
  defaults. [`qsmci_io.jl`](qsmci_io.jl) only reads the inputs, applies `--set` overrides and
  writes the output.
- **Environment:** the shared Julia base image [`algorithms/_julia`](../_julia) (Julia 1.10.11,
  Manifest committed there, packages compiled into a sysimage), pinned by digest in `algorithm.yml`.
- **QSM.rs port:** [`rts-qsmrs`](../rts-qsmrs) (same `algorithm: rts`).
- **Parity only:** the reference of the port's parity pair (`parity/thresholds.yml`, [docs/parity.md](../../docs/parity.md)); not scored and not on the leaderboard.
- **Reference:** Kames et al., NeuroImage 2018 · doi:[10.1016/j.neuroimage.2017.11.018](https://doi.org/10.1016/j.neuroimage.2017.11.018)

## How QSM-CI runs it

```bash
qsm-ci run rts-qsmjl --localfield localfield.nii.gz --mask mask.nii.gz --params params.json
```

`run.sh` starts Julia with 4 threads (FFTW 4, BLAS 1) and the image's `qsmjl.so` sysimage.

## Parameters

Defaults are the original's. The *QSM.rs-matched* column is what to `--set` so the pair computes
the same thing as far as the original allows.

| parameter | default | QSM.rs-matched | description |
|---|---|---|---|
| `delta` | 0.15 |  | threshold of the ill-conditioned k-space region |
| `mu` | 100000.0 |  | weight holding the well-conditioned coefficients |
| `rho` | 10 |  | ADMM penalty |
| `tol` | 0.01 |  | stopping tolerance |
| `max_iter` | 20 |  | maximum ADMM iterations (`maxit`) |
| `lsmr_iter` | 4 |  | LSMR stopping tolerance in iterations (`lstol`) |
| `pad` | 0 | -1 | QSM.jl `pad` (all three axes): >= 0 zero-pads to a fast FFT size (QSM.jl default 0: padding only up to that size); -1 does not pad, as QSM.rs |

## Against the QSM.rs port

- QSM.rs uses complex FFTs where QSM.jl uses real-to-complex ones, and does not pad; `--set pad=-1` turns QSM.jl's fast-FFT-size padding off. The FFT type cannot be changed in QSM.jl.
