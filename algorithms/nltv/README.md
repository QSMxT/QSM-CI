# NLTV

Nonlocal Total Variation regularized inversion.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** — _(DOI: TODO — verify)_

## How QSM-CI runs it

```bash
qsmxt invert nltv /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `lambda` | 1e-4 | regularization |
| `max_iter` | 1000 | iterations |

_Citations/DOIs are auto-generated best-effort references and should be verified._
