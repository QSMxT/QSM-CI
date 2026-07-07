# TKD

Thresholded K-space Division: direct inversion with the dipole kernel thresholded.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Shmueli et al., Magn Reson Med 2009 _(DOI: TODO — verify)_

## How QSM-CI runs it

```bash
qsmxt invert tkd /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `threshold` | 0.1 | k-space threshold |

_Citations/DOIs are auto-generated best-effort references and should be verified._
