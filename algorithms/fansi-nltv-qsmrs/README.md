# FANSI (nlTV)

Fast Nonlinear Susceptibility Inversion with nonlinear total-variation regularization, solved with ADMM.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Milovic et al., Magn Reson Med 2018 · doi:[10.1002/mrm.27073](https://doi.org/10.1002/mrm.27073)

## How QSM-CI runs it

```bash
qsmxt invert fansi /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `alpha1` | 2e-4 | gradient L1 (TV) penalty |
| `mu1` | 2e-2 | gradient-consistency ADMM weight |
| `max_iter` | 150 | iterations |
| `tol_update` | 0.1 | convergence threshold on the solution update (percent) |

_Citations/DOIs are auto-generated best-effort references and should be verified._
