# TSVD

Truncated Singular Value Decomposition inversion.

- **Stage:** `dipole` (localfield → chimap, ppm)
- **Engine:** [QSMxT](https://github.com/QSMxT/QSMxT) — the [QSM.rs](https://github.com/astewartau/QSM.rs) Rust implementation
- **Reference:** Wharton et al., Magn Reson Med 2010 · doi:[10.1002/mrm.22334](https://doi.org/10.1002/mrm.22334)

## How QSM-CI runs it

```bash
qsmxt invert tsvd /input/localfield.nii.gz -m /input/mask.nii.gz -o /output/chimap.nii.gz --b0-direction <B0>
```

## Parameters

| parameter | default | description |
|---|---|---|
| `threshold` | 0.1 | singular-value threshold |

_Citations/DOIs are auto-generated best-effort references and should be verified._
