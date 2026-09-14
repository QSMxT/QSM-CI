# ROMEO field mapping (QSM.rs)

Combined multi-echo B0 field mapping with ROMEO (Dymerska, Eckstein et al., *MRM* 2021) through the
QSMxT / QSM.rs engine's `qsmxt fieldmap romeo`: MCPC-3D-S phase-offset removal, template/temporal
multi-echo unwrapping, and a magnitude/TE-weighted B0 estimate (`--b0-estimation weighted-avg`).
The alternative to `laplacian-qsmci`; it replaced an earlier per-echo unwrap + unweighted linear
fit.

- **Stage:** `field-mapping` — reads `phase` (multi-echo), `magnitude`, `mask`, `params`; writes
  `totalfield.nii.gz` (ppm)
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs) (Rust), CPU
- **Reference:** Dymerska et al., *Magn Reson Med* 2021 ·
  doi:[10.1002/mrm.28563](https://doi.org/10.1002/mrm.28563)
- **Image:** `ghcr.io/astewartau/qsm-ci/romeo-fieldmap:v2`, built from this folder's `Dockerfile`:
  the shared `py-ref` base plus the statically linked `qsmxt` release binary (`QSMXT_VERSION`,
  ≥ v9.15.0, where `qsmxt fieldmap romeo` landed). Unlike the BFR/dipole QSM.rs ports it does not
  use the shared `_qsmxt` engine image.

## How QSM-CI runs it

`run.sh` is a single `qsmxt fieldmap romeo` call over the input phase, magnitude, mask and
`params.json`, writing the total field in ppm.

```bash
qsm-ci run romeo-qsmrs --phase phase.nii.gz --magnitude magnitude.nii.gz --mask mask.nii.gz --params params.json -o totalfield.nii.gz
```
