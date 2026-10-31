# iSMV (QSM.jl)

Iterative spherical mean value background field removal, run as the original QSM.jl code (`QSM.ismv`, fde4b92).

- **Stage:** `bfr` (reads `totalfield`, `mask`, `params`)
- **Code:** QSM.jl at fde4b92 (v0.5.4), the authors' package, called from `recon.jl` with the package's own
  defaults. [`qsmci_io.jl`](qsmci_io.jl) only reads the inputs, applies `--set` overrides and
  writes the output.
- **Environment:** the shared Julia base image [`algorithms/_julia`](../_julia) (Julia 1.10.11,
  Manifest committed there, packages compiled into a sysimage), pinned by digest in `algorithm.yml`.
- **QSM.rs port:** [`ismv-qsmrs`](../ismv-qsmrs) (same `algorithm: ismv`).
- **Parity only:** the reference of the port's parity pair (`parity/thresholds.yml`, [docs/parity.md](../../docs/parity.md)); not scored and not on the leaderboard.
- **Reference:** Wen et al., Magn Reson Med 2014 · doi:[10.1002/mrm.24998](https://doi.org/10.1002/mrm.24998)

## How QSM-CI runs it

```bash
qsm-ci run ismv-qsmjl --totalfield totalfield.nii.gz --mask mask.nii.gz --params params.json
```

`run.sh` starts Julia with 4 threads (FFTW 4, BLAS 1) and the image's `qsmjl.so` sysimage.

## Parameters

Defaults are the original's. The *QSM.rs-matched* column is what to `--set` so the pair computes
the same thing as far as the original allows.

| parameter | default | QSM.rs-matched | description |
|---|---|---|---|
| `radius` | 2*max(voxel_size) |  | SMV kernel radius, mm (`r`) |
| `tol` | 0.001 |  | stopping tolerance |
| `max_iter` | 500 |  | maximum iterations (`maxit`) |

## Against the QSM.rs port

- QSM.rs's iSMV follows the authors' paper and code by default (the lab's `iSMV.m`, Wen et al. 2014: 6 voxels, tol 5e-5; astewartau/QSM.rs#322). QSM.jl's `ismv` is kept as `IsmvVariant::QsmJl`, with QSM.jl's defaults; the pair selects it on the QSM.rs side (`candidate_set: {variant: qsmjl}`, `qsmxt bgremove ismv --variant qsmjl`), so nothing is set here.
