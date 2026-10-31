# NLTV (QSM.jl)

Nonlinear-data-term total-variation dipole inversion by ADMM (Milovic et al. 2018), run as the original QSM.jl code (`QSM.nltv`, fde4b92) on the local field as phase in rad at the first echo time, with a magnitude data weight `W`.

- **Stage:** `dipole` (reads `localfield`, `mask`, `params`, `magnitude`)
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
qsm-ci run nltv-qsmjl --localfield localfield.nii.gz --mask mask.nii.gz --params params.json \
  --magnitude magnitude.nii.gz
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
| `pad` | 0 |  | QSM.jl `pad` (all three axes): >= 0 zero-pads to a fast FFT size (QSM.jl default 0: padding only up to that size); -1 does not pad. QSM.rs pads the same way by default (astewartau/QSM.rs#323) |
| `te` | first echo time |  | echo time (s) the field is converted to phase at (QSM.rs: `--te`, first by default) |

## Inputs given to QSM.jl

QSM.jl's `nltv` takes the phase in rad (its nonlinear data term is `exp(i·f)`) and leaves the data
weight `W` to the caller, with no rule for making it. `recon.jl` gives it the same inputs as the
QSM.rs port (astewartau/QSM.rs#323):

- the local field in ppm times `2π · γ̄ · B0 · TE₁` (γ̄ = 42.576 MHz/T, QSM-CI's and QSM.rs's), and
  the result divided by the same factor;
- `W = min(2 · mask · mag / max(mag), 1)`, where `mag` is the magnitude (root-sum-of-squares over
  the echoes): the normalisation of FANSI's in-vivo example by the paper's authors. QSM.jl squares it.

Unweighted (`W = nothing`, QSM.jl's default), QSM.jl's `nltv` never refreshes the FFT of `x`
before the Newton step and diverges on fields of more than a few radians, so the port requires the
magnitude.

## Against the QSM.rs port

- **Upstream bug:** QSM.jl's `nltv` allocates its data-term multiplier `ue` with `similar` and never
  initialises it. On small arrays (which reuse freed memory) the output is NaN and changes from run
  to run; the full-size volumes here get fresh, zeroed memory, so it starts at zero, as the port does.
  The pair's checks would show it if that ever stopped holding.
- The pair is in `parity/thresholds.yml` (`nltv`).
- `nltv-qsmrs` as pinned (QSM.rs v0.39.0, QSMxT v10.0.0) is an iteratively reweighted TV, a different algorithm.
