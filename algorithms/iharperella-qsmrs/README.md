# iHARPERELLA

Improved HARPERELLA: background field removal by directly minimising the weighted resulting field, on the multi-echo total field.

- **Stage:** `bfr` (totalfield → localfield, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Li, Wu & Liu, Proc. ISMRM 23 (2015), p. 3313 ([abstract](https://archive.ismrm.org/2015/3313.html)); HARPERELLA: Li et al., NMR Biomed 2014 · doi:[10.1002/nbm.3056](https://doi.org/10.1002/nbm.3056)

## How QSM-CI runs it

```bash
qsmxt bgremove iharperella /input/totalfield.nii.gz -m /input/mask.nii.gz -o /output/localfield.nii.gz
```

Without `--te`/`--field-strength`, qsmxt reads the input as an unwrapped total field in ppm, so
iHARPERELLA removes the background from the multi-echo field map, as `qsmxt run` does. The published
method starts from one wrapped echo and unwraps it at the same time; given `--te` and
`--field-strength`, qsmxt does that instead.

## Parameters

| parameter | default | description |
|---|---|---|
| `max_iter` | 40 | iterations |
| `tol` | 1e-6 | tolerance |

_Citations/DOIs are auto-generated best-effort references and should be verified._
