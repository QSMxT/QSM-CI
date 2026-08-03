# WH-QSM

Weak-Harmonic QSM: jointly estimates susceptibility and a residual harmonic background field, correcting imperfect background-field removal.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Milovic et al., Magn Reson Med 2019 · doi:[10.1002/mrm.27483](https://doi.org/10.1002/mrm.27483)

## How QSM-CI runs it

```bash
qsmxt invert whqsm /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `alpha1` | 2e-4 | gradient L1 (TV) penalty |
| `mu1` | 2e-2 | gradient-consistency ADMM weight |
| `beta` | 150 | harmonic-constraint weight |
| `max_iter` | 300 | iterations |
| `tol_update` | 0.1 | convergence threshold on the solution update (percent) |

_Citations/DOIs are auto-generated best-effort references and should be verified._
