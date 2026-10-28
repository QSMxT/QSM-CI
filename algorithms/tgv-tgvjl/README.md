# TGV (QuantitativeSusceptibilityMappingTGV.jl)

Single-step TGV-QSM (total field to susceptibility, with its own background removal), run as the Julia package `qsm_tgv` (6c0886a) on CPU threads. The total field (ppm) is turned into phase at one echo time, as the package expects; its α are in the package's own (rad) units.

- **Stage:** `bfr+dipole` (reads `totalfield`, `mask`, `params`)
- **Code:** QuantitativeSusceptibilityMappingTGV.jl at 6c0886a (0.5.2), the authors' package, called from `recon.jl` with the package's own
  defaults. [`qsmci_io.jl`](qsmci_io.jl) only reads the inputs, applies `--set` overrides and
  writes the output.
- **Environment:** the shared Julia base image [`algorithms/_julia`](../_julia) (Julia 1.10.11,
  Manifest committed there, packages compiled into a sysimage), pinned by digest in `algorithm.yml`.
- **QSM.rs port:** [`tgv-qsmrs`](../tgv-qsmrs) (same `algorithm: tgv`).
- **Parity only:** the reference of the port's parity pair (`parity/thresholds.yml`, [docs/parity.md](../../docs/parity.md)); not scored and not on the leaderboard.
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
| `alpha0` | from regularization (0.002) |  | second-order weight, rad units at the chosen TE and B0 |
| `alpha1` | from regularization (0.003) |  | first-order (gradient) weight, rad units at the chosen TE and B0 |
| `iterations` | max(1000, 3200/prod(voxel_size)^0.42)/step_size^0.6 |  | iterations (the package's voxel-size formula by default) |
| `erosions` | 3 |  | mask erosions |
| `step_size` | 3 |  | primal-dual step-size multiplier |
| `laplacian` | del | unwrapped | phase Laplacian: del (the package default, sin/cos) / romeo (ROMEO unwrap then the discrete Laplacian) / unwrapped (the package's discrete Laplacian of the phase as given: `romeo` without the unwrap, for a field that is already unwrapped) / phase3 (the original Python's) |
| `correct_laplacian` | true |  | subtract the Laplacian's mean inside the mask |
| `te` | first echo |  | echo time (s) the field is scaled to phase at |

## Against the QSM.rs port

- QSM.rs after v0.39.0 (main, and astewartau/QSM.rs#324) ports `qsm_tgv` with the package's defaults: α in the same rad units at the scan's TE and B0, the voxel-size iteration count, 3 erosions, step size 3. For a field in ppm it forms ∇² with the ordinary discrete Laplacian, so the only setting to match is `laplacian=unwrapped`.
- `romeo` is not a match for an unwrapped field: ROMEO re-unwraps the scaled phase and leaves ±2π jumps where it exceeds π (seen 2 voxels from the mask edge).
- `tgv-qsmrs` as pinned (QSM.rs v0.39.0, QSMxT v10.0.0) solves in ppm with α in ppm and 1000 iterations with an early stop; no setting of the package reproduces that.
