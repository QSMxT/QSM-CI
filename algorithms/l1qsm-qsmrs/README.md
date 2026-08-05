# L1-QSM

L1-norm data-fidelity QSM (PI-QSM): an L1 fidelity term with TV regularization, robust to phase inconsistencies.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Milovic et al., Magn Reson Med 2022 · doi:[10.1002/mrm.28957](https://doi.org/10.1002/mrm.28957)

## How QSM-CI runs it

```bash
qsmxt invert l1qsm /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `alpha1` | 2e-4 | gradient L1 (TV) penalty |
| `mu1` | 2e-2 | gradient-consistency ADMM weight |
| `lambda` | 1.0 | L1 fidelity strength (<1 rejects more inconsistent voxels) |
| `max_iter` | 50 | iterations |
| `tol_update` | 1.0 | convergence threshold on the solution update (percent) |

_Citations/DOIs are auto-generated best-effort references and should be verified._
