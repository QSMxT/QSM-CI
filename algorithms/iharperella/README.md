# iHARPERELLA

Improved HARPERELLA with low-frequency suppression.

- **Stage:** `bfr` (totalfield → localfield, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Li et al., 2015 _(DOI: TODO — verify)_

## How QSM-CI runs it

```bash
qsmxt bgremove iharperella /input/totalfield.nii.gz -m /input/mask.nii.gz -o /output/localfield.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `radius` | 15.0 | SMV kernel radius (mm) |
| `max_iter` | 1000 | iterations |

_Citations/DOIs are auto-generated best-effort references and should be verified._
