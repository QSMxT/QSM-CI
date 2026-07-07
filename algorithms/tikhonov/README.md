# Tikhonov

Closed-form L2 (Tikhonov) regularized inversion.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Kames et al., 2018 _(DOI: TODO — verify)_

## How QSM-CI runs it

```bash
qsmxt invert tikhonov /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `lambda` | 1e-4 | L2 regularization |
| `reg` | laplacian | identity|gradient|laplacian |

_Citations/DOIs are auto-generated best-effort references and should be verified._
