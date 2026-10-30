# V-SHARP (QSM.jl)

Variable-radius SHARP with TSVD deconvolution by the largest kernel, run as the original QSM.jl code (`QSM.vsharp`, fde4b92).

- **Stage:** `bfr` (reads `totalfield`, `mask`, `params`)
- **Code:** QSM.jl at fde4b92 (v0.5.4), the authors' package, called from `recon.jl` with the package's own
  defaults. [`qsmci_io.jl`](qsmci_io.jl) only reads the inputs, applies `--set` overrides and
  writes the output.
- **Environment:** the shared Julia base image [`algorithms/_julia`](../_julia) (Julia 1.10.11,
  Manifest committed there, packages compiled into a sysimage), pinned by digest in `algorithm.yml`.
- **QSM.rs port:** [`vsharp-qsmrs`](../vsharp-qsmrs) (same `algorithm: vsharp`).
- **Parity only:** the reference of the port's parity pair (`parity/thresholds.yml`, [docs/parity.md](../../docs/parity.md)); not scored and not on the leaderboard.
- **Reference:** Wu et al., Magn Reson Med 2012 · doi:[10.1002/mrm.23000](https://doi.org/10.1002/mrm.23000)

## How QSM-CI runs it

```bash
qsm-ci run vsharp-qsmjl --totalfield totalfield.nii.gz --mask mask.nii.gz --params params.json
```

`run.sh` starts Julia with 4 threads (FFTW 4, BLAS 1) and the image's `qsmjl.so` sysimage.

## Parameters

Defaults are the original's. The *QSM.rs-matched* column is what to `--set` so the pair computes
the same thing as far as the original allows.

| parameter | default | QSM.rs-matched | description |
|---|---|---|---|
| `max_radius` | 18*min(voxel_size) | 12 | largest SMV radius, mm |
| `min_radius` | 2*max(voxel_size) | 1 | smallest SMV radius, mm |
| `radius_step` | 2*max(voxel_size) | 1 | step between radii, mm |
| `threshold` | 0.05 |  | deconvolution (TSVD) threshold (`thr`) |

## Against the QSM.rs port

- QSM.jl always deconvolves; `vsharp-qsmrs` runs with `deconvolve: true` and threshold 0.05 too, so only the radii differ (QSM.jl 18 → 2 mm in 2 mm steps on 1 mm voxels, QSM.rs 12 → 1 mm in 1 mm steps). QSM.rs's `deconvolve: false` (STI Suite's behaviour) has no QSM.jl equivalent.
