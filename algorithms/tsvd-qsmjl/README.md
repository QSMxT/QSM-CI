# TSVD (QSM.jl)

Truncated singular-value (k-space) division, run as the original QSM.jl code (`QSM.tsvd`, fde4b92).

- **Stage:** `dipole` (reads `localfield`, `mask`, `params`)
- **Code:** QSM.jl at fde4b92 (v0.5.4), the authors' package, called from `recon.jl` with the package's own
  defaults. [`qsmci_io.jl`](qsmci_io.jl) only reads the inputs, applies `--set` overrides and
  writes the output.
- **Environment:** the shared Julia base image [`algorithms/_julia`](../_julia) (Julia 1.10.11,
  Manifest committed there, packages compiled into a sysimage), pinned by digest in `algorithm.yml`.
- **QSM.rs port:** [`tsvd-qsmrs`](../tsvd-qsmrs) (same `algorithm: tsvd`).
- **Parity only:** the reference of the port's parity pair (`parity/thresholds.yml`, [docs/parity.md](../../docs/parity.md)); not scored and not on the leaderboard.
- **Reference:** Wharton et al., Magn Reson Med 2010 · doi:[10.1002/mrm.22334](https://doi.org/10.1002/mrm.22334)

## How QSM-CI runs it

```bash
qsm-ci run tsvd-qsmjl --localfield localfield.nii.gz --mask mask.nii.gz --params params.json
```

`run.sh` starts Julia with 4 threads (FFTW 4, BLAS 1) and the image's `qsmjl.so` sysimage.

## Parameters

Defaults are the original's. The *QSM.rs-matched* column is what to `--set` so the pair computes
the same thing as far as the original allows.

| parameter | default | QSM.rs-matched | description |
|---|---|---|---|
| `threshold` | 0.15 |  | singular-value threshold (`thr`) |
| `pad` | 0 | -1 | QSM.jl `pad` (all three axes): >= 0 zero-pads to a fast FFT size (QSM.jl default 0: padding only up to that size); -1 does not pad, as QSM.rs |

## Against the QSM.rs port

- The defaults are the same in both; nothing to set.
