# iHARPERELLA

Improved HARPERELLA: iterative integrated unwrapping + background removal on wrapped phase.

- **Stage:** `unwrap+bfr` (phase → localfield, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Li et al., NeuroImage 2014 · doi:[10.1016/j.neuroimage.2014.08.029](https://doi.org/10.1016/j.neuroimage.2014.08.029)

## How QSM-CI runs it

```bash
qsmxt bgremove iharperella /input/phase.nii.gz -m /input/mask.nii.gz -o /output/localfield.nii.gz --te <TE1> --field-strength <B0>
```

iHARPERELLA works on one wrapped echo: qsmxt reads the first volume of the 4D phase, and `--te` (echo 1's
TE) with `--field-strength` tell it that the input is wrapped phase in rad. The local field is
written in ppm (qsmxt ≥ v10.0.0).

## Parameters

| parameter | default | description |
|---|---|---|
| `max_iter` | 40 | iterations |
| `tol` | 1e-6 | tolerance |

_Citations/DOIs are auto-generated best-effort references and should be verified._
