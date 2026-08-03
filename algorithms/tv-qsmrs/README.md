# TV (ADMM)

Total Variation regularized dipole inversion solved with ADMM.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Bilgic et al., 2014 _(DOI: TODO — verify)_

## How QSM-CI runs it

```bash
qsmxt invert tv /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `lambda` | 1e-4 | TV regularization |
| `rho` | 1.0 | ADMM penalty |
| `max_iter` | 1000 | iterations |

_Citations/DOIs are auto-generated best-effort references and should be verified._
