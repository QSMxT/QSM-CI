# TGV (QuantitativeSusceptibilityMappingTGV.jl)

Single-step TGV-QSM (total field to susceptibility, with its own background removal), run as the Julia package `qsm_tgv` (6c0886a) on CPU threads. The total field (ppm) is turned into phase at one echo time, as the package expects; its α are in the package's own (rad) units.

- **Stage:** `bfr+dipole` (reads `totalfield`, `mask`, `params`)
- **Code:** QuantitativeSusceptibilityMappingTGV.jl at 6c0886a (0.5.2), the authors' package, called from `recon.jl` with the package's own
  defaults. [`qsmci_io.jl`](qsmci_io.jl) only reads the inputs, applies `--set` overrides and
  writes the output.
- **Environment:** the shared Julia base image [`algorithms/_julia`](../_julia) (Julia 1.10.11,
  Manifest committed there, packages compiled into a sysimage), pinned by digest in `algorithm.yml`.
- **QSM.rs port:** [`tgv-qsmrs`](../tgv-qsmrs) (same `algorithm: tgv`).
- **Reference:** Langkammer et al., NeuroImage 2015 · doi:[10.1016/j.neuroimage.2015.02.041](https://doi.org/10.1016/j.neuroimage.2015.02.041)

## How QSM-CI runs it

```bash
qsm-ci run tgv-tgvjl --totalfield totalfield.nii.gz --mask mask.nii.gz --params params.json
```

`run.sh` starts Julia with 4 threads (FFTW 4, BLAS 1) and the image's `mritools.so` sysimage.

## Parameters

Defaults are the original's. The *QSM.rs-matched* column is what to `--set` so the pair computes
the same thing as far as the original allows.

| parameter | default | QSM.rs-matched | description |
|---|---|---|---|
| `regularization` | 2 |  | the package's regularization level; sets alpha0/alpha1 when they are not given (2: 0.002 / 0.003) |
| `alpha0` | from regularization (0.002) | 2.002e-4 × 2π·42.5781·B0·TE (0.0015 there) | second-order weight, rad units at the chosen TE and B0 |
| `alpha1` | from regularization (0.003) | 6.675e-5 × 2π·42.5781·B0·TE (0.0005 on the 7 T / 4 ms sim) | first-order (gradient) weight, rad units at the chosen TE and B0 |
| `iterations` | max(1000, 3200/prod(voxel_size)^0.42)/step_size^0.6 | 1000 | iterations (the package's voxel-size formula by default) |
| `erosions` | 3 |  | mask erosions |
| `step_size` | 3 |  | primal-dual step-size multiplier |
| `laplacian` | del | romeo | phase Laplacian: del (the package default, sin/cos) / romeo (ROMEO unwrap then the discrete Laplacian) / phase3 (the original Python's) |
| `correct_laplacian` | true |  | subtract the Laplacian's mean inside the mask |
| `te` | first echo |  | echo time (s) the field is scaled to phase at |

## Against the QSM.rs port

- `tgv-qsmrs` (QSM.rs v0.39.0) solves in ppm with α in ppm (α1 6.675e-5, α0 2.002e-4 by default); the package solves on the phase at one TE with α in rad units, which is the same problem when α_rad = α_ppm · 2π·42.5781·B0·TE. QSM.rs v0.39.0 runs 1000 iterations with an early stop (tol 1e-5, checked every 100 iterations) and forms ∇² of the field with the ordinary discrete Laplacian; the package has no early stop.
