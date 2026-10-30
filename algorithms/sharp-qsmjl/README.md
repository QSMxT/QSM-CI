# SHARP (QSM.jl)

SHARP background field removal (SMV high-pass + TSVD deconvolution), run as the original QSM.jl code (`QSM.sharp`, fde4b92).

- **Stage:** `bfr` (reads `totalfield`, `mask`, `params`)
- **Code:** QSM.jl at fde4b92 (v0.5.4), the authors' package, called from `recon.jl` with the package's own
  defaults. [`qsmci_io.jl`](qsmci_io.jl) only reads the inputs, applies `--set` overrides and
  writes the output.
- **Environment:** the shared Julia base image [`algorithms/_julia`](../_julia) (Julia 1.10.11,
  Manifest committed there, packages compiled into a sysimage), pinned by digest in `algorithm.yml`.
- **QSM.rs port:** [`sharp-qsmrs`](../sharp-qsmrs) (same `algorithm: sharp`).
- **Parity only:** the reference of the port's parity pair (`parity/thresholds.yml`, [docs/parity.md](../../docs/parity.md)); not scored and not on the leaderboard.
- **Reference:** Schweser et al., NeuroImage 2011 · doi:[10.1016/j.neuroimage.2010.10.070](https://doi.org/10.1016/j.neuroimage.2010.10.070)

## How QSM-CI runs it

```bash
qsm-ci run sharp-qsmjl --totalfield totalfield.nii.gz --mask mask.nii.gz --params params.json
```

`run.sh` starts Julia with 4 threads (FFTW 4, BLAS 1) and the image's `qsmjl.so` sysimage.

## Parameters

Defaults are the original's. The *QSM.rs-matched* column is what to `--set` so the pair computes
the same thing as far as the original allows.

| parameter | default | QSM.rs-matched | description |
|---|---|---|---|
| `radius` | 18*min(voxel_size) | 6 (QSM.rs: 6 × the smallest voxel size, mm) | SMV kernel radius, mm (`r`) |
| `threshold` | 0.05 |  | deconvolution (TSVD) threshold (`thr`) |

## Against the QSM.rs port

- QSM.rs's `--radius` is a factor of the smallest voxel size (6 by default); QSM.jl's `r` is in mm (18 mm on 1 mm voxels). They agree with `--set radius=6` on 1 mm isotropic voxels.
