# TV-ADMM (QSM.jl)

Total-variation dipole inversion by ADMM, run as the original QSM.jl code (`QSM.tv`, fde4b92), unweighted (`W`, `Wtv` = nothing, QSM.jl's default).

- **Stage:** `dipole` (reads `localfield`, `mask`, `params`)
- **Code:** QSM.jl at fde4b92 (v0.5.4), the authors' package, called from `recon.jl` with the package's own
  defaults. [`qsmci_io.jl`](qsmci_io.jl) only reads the inputs, applies `--set` overrides and
  writes the output.
- **Environment:** the shared Julia base image [`algorithms/_julia`](../_julia) (Julia 1.10.11,
  Manifest committed there, packages compiled into a sysimage), pinned by digest in `algorithm.yml`.
- **QSM.rs port:** [`tv-qsmrs`](../tv-qsmrs) (same `algorithm: tv`).
- **Reference:** Bilgic et al., MRM 2014 · doi:[10.1002/mrm.25029](https://doi.org/10.1002/mrm.25029)

## How QSM-CI runs it

```bash
qsm-ci run tv-qsmjl --localfield localfield.nii.gz --mask mask.nii.gz --params params.json
```

`run.sh` starts Julia with 4 threads (FFTW 4, BLAS 1) and the image's `qsmjl.so` sysimage.

## Parameters

Defaults are the original's. The *QSM.rs-matched* column is what to `--set` so the pair computes
the same thing as far as the original allows.

| parameter | default | QSM.rs-matched | description |
|---|---|---|---|
| `lambda` | 0.001 | 2e-4 | TV regularization |
| `rho` | 100*lambda |  | ADMM penalty |
| `tol` | 0.001 |  | stopping tolerance |
| `max_iter` | 250 |  | maximum iterations (`maxit`) |
| `pad` | 0 | -1 | QSM.jl `pad` (all three axes): >= 0 zero-pads to a fast FFT size (QSM.jl default 0: padding only up to that size); -1 does not pad, as QSM.rs |

## Against the QSM.rs port

- QSM.rs (v0.39.0, QSMxT v10.0.0) defaults to `lambda` 2e-4 and `rho` 2e-2 (= 100·lambda); QSM.jl to 1e-3 and 100·lambda. `--set lambda=2e-4` gives both QSM.rs values.
