# NLTV (QSM.jl)

Nonlinear-data-term total-variation dipole inversion by ADMM (Milovic et al. 2018), run as the original QSM.jl code (`QSM.nltv`, fde4b92), unweighted (`W` = nothing, QSM.jl's default) on the local field in ppm, as QSM.jl's README pipeline passes it.

- **Stage:** `dipole` (reads `localfield`, `mask`, `params`)
- **Code:** QSM.jl at fde4b92 (v0.5.4), the authors' package, called from `recon.jl` with the package's own
  defaults. [`qsmci_io.jl`](qsmci_io.jl) only reads the inputs, applies `--set` overrides and
  writes the output.
- **Environment:** the shared Julia base image [`algorithms/_julia`](../_julia) (Julia 1.10.11,
  Manifest committed there, packages compiled into a sysimage), pinned by digest in `algorithm.yml`.
- **QSM.rs port:** [`nltv-qsmrs`](../nltv-qsmrs) (same `algorithm: nltv`).
- **Parity only:** the reference of the port's parity pair (`parity/thresholds.yml`, [docs/parity.md](../../docs/parity.md)); not scored and not on the leaderboard.
- **Reference:** Milovic et al., Magn Reson Med 2018 · doi:[10.1002/mrm.27073](https://doi.org/10.1002/mrm.27073)

## How QSM-CI runs it

```bash
qsm-ci run nltv-qsmjl --localfield localfield.nii.gz --mask mask.nii.gz --params params.json
```

`run.sh` starts Julia with 4 threads (FFTW 4, BLAS 1) and the image's `qsmjl.so` sysimage.

## Parameters

Defaults are the original's. The *QSM.rs-matched* column is what to `--set` so the pair computes
the same thing as far as the original allows.

| parameter | default | QSM.rs-matched | description |
|---|---|---|---|
| `lambda` | 0.001 |  | TV regularization |
| `rho` | 100*lambda |  | ADMM penalty (TV split) |
| `mu` | 1 |  | ADMM penalty (data-term split) |
| `tol` | 0.001 |  | stopping tolerance |
| `max_iter` | 250 |  | maximum ADMM iterations (`maxit`) |
| `newton_tol` | 1e-06 |  | Newton stopping tolerance (`toln`) |
| `newton_iter` | 10 |  | maximum Newton iterations (`maxitn`) |
| `pad` | 0 | -1 | QSM.jl `pad` (all three axes): >= 0 zero-pads to a fast FFT size (QSM.jl default 0: padding only up to that size); -1 does not pad, as QSM.rs |

## Against the QSM.rs port

- **Not a parity reference yet.** This entry calls QSM.jl's `nltv` on the local field in ppm and without the data weight `W`. QSM.jl's `nltv` works on the phase in rad (its nonlinear data term is `exp(i·f)`), and QSM.rs's port (astewartau/QSM.rs#323) takes the magnitude as `W` and requires it. QSM.jl's `nltv` also never initialises its `ue` buffer, so on small arrays the result can contain NaN that changes from run to run. The pair stays blocked (parity/thresholds.yml) until this entry passes the phase in rad and the same `W`, and the uninitialised buffer is shown not to matter on the full volume.
- `nltv-qsmrs` as pinned (QSM.rs v0.39.0, QSMxT v10.0.0) is an iteratively reweighted TV, a different algorithm.
