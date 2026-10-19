# iSMV

Iterative Spherical Mean Value background field removal.

- **Stage:** `bfr` (totalfield → localfield, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Wen et al., 2014 _(DOI: TODO — verify)_

## How QSM-CI runs it

```bash
qsmxt bgremove ismv /input/totalfield.nii.gz -m /input/mask.nii.gz -o /output/localfield.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `tol` | 1e-6 | tolerance |
| `max_iter` | 50 | iterations |
| `radius` | 5.0 | SMV kernel radius (mm) |

_Citations/DOIs are auto-generated best-effort references and should be verified._
