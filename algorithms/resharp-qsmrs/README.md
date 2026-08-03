# RESHARP

Regularized SHARP with Tikhonov regularization of the deconvolution.

- **Stage:** `bfr` (totalfield → localfield, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Sun & Wilman, Magn Reson Med 2014 · doi:[10.1002/mrm.24765](https://doi.org/10.1002/mrm.24765)

## How QSM-CI runs it

```bash
qsmxt bgremove resharp /input/totalfield.nii.gz -m /input/mask.nii.gz -o /output/localfield.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `radius` | 15.0 | SMV kernel radius (mm) |
| `tik_reg` | 1e-3 | Tikhonov regularization |

_Citations/DOIs are auto-generated best-effort references and should be verified._
