# HARPERELLA

Laplacian-based background field removal (HARPERELLA's harmonic phase removal) on the multi-echo total field.

- **Stage:** `bfr` (totalfield → localfield, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Li et al., NMR Biomed 2014 · doi:[10.1002/nbm.3056](https://doi.org/10.1002/nbm.3056)

## How QSM-CI runs it

```bash
qsmxt bgremove harperella /input/totalfield.nii.gz -m /input/mask.nii.gz -o /output/localfield.nii.gz
```

Without `--te`/`--field-strength`, qsmxt reads the input as an unwrapped total field in ppm, so
HARPERELLA removes the background from the multi-echo field map, as `qsmxt run` does. The published
method starts from one wrapped echo and unwraps it at the same time; given `--te` and
`--field-strength`, qsmxt does that instead.

## Parameters

| parameter | default | description |
|---|---|---|
| `radius` | 10.0 | SMV kernel radius (mm) |
| `max_iter` | 40 | iterations |
| `tol` | 1e-6 | tolerance |

_Citations/DOIs are auto-generated best-effort references and should be verified._
