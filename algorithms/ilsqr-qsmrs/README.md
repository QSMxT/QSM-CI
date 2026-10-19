# iLSQR

Iterative LSQR inversion with streaking-artifact reduction.

Since qsmxt v10.0.0 (QSM.rs v0.39.0) this is a new implementation of the reference iLSQR algorithm,
and the field is zero-padded by 16 mm per side before the k-space solve (`pad_mm`).

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Li et al., NMR Biomed 2015 _(DOI: TODO — verify)_

## How QSM-CI runs it

```bash
qsmxt invert ilsqr /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `tol` | 1e-3 | tolerance |
| `max_iter` | 100 | iterations |
| `pad_mm` | 16 | zero-padding per side (mm) |

_Citations/DOIs are auto-generated best-effort references and should be verified._
