# MEDI

Morphology Enabled Dipole Inversion: magnitude-guided edge regularization.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Liu et al., 2012 _(DOI: TODO — verify)_

## How QSM-CI runs it

```bash
qsmxt invert medi /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `lambda` | 1e-4 | regularization |
| `percentage` | 0.95 | edge percentage |

_Citations/DOIs are auto-generated best-effort references and should be verified._
