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

- QSM.jl always deconvolves; `vsharp-qsmrs` runs with `deconvolve: true` and threshold 0.05 too. QSM.rs's radii are STI Suite's (12 → 1 mm in 1 mm steps), so the matched settings give QSM.jl those.
- QSM.rs's default ball and edge test are STI Suite's (`VsharpBall::StiSuite`, astewartau/QSM.rs#332); QSM.jl's are `VsharpBall::QsmJl`, which matches this submission to rounding in QSM.rs's own test, and `qsmxt bgremove vsharp --ball qsmjl` selects it (QSMxT/QSMxT#460). The pair also gives the candidate the native grid.
- The voxel size comes from the mask's NIfTI header (`qsmci_io.jl`, every Julia submission), which is what `qsmxt` reads, not from `params.json`: QSM.jl's working box is padded by `⌈max(r) / min(voxel size)⌉` voxels, so a header spacing stored one float32 ulp below 1 mm (0.99999994, the KKI travelling head's z) pads 13 voxels at 12 mm where `params.json`'s 1.0 pads 12. With `params.json`'s value the pair measured 1.19 % NRMSE on KKI; with the header's, the outputs are identical.
- QSM.rs's `deconvolve: false` (STI Suite's behaviour) has no QSM.jl equivalent.
