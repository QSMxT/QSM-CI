# R2PRIMEnet (QSM.rs)

R2PRIMEnet as QSM.rs runs it: R2* by ARLO (`qsmxt r2star`), then the authors' trained network
exported to ONNX (QSM.rs's `scripts/onnx-export/`) and run by `qsmxt r2prime --r2primenet` on
QSM.rs's ONNX engine (tract, CPU).

- **Stage:** `r2prime-generation`: reads the multi-echo `magnitude`, `mask` and `params`; writes `r2prime.nii.gz` (Hz).
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs).
- **Original:** [`r2primenet`](../r2primenet) runs the toolbox's model, with the toolbox's ARLO fit; the two entries share `algorithm: r2primenet`, so they form a port parity pair (`parity/thresholds.yml`).
- **R2\*:** MEDI's `arlo.m` on both sides (the toolbox's `r2star_arlo` is `arlo.m`, checked in licensed MATLAB). QSM.rs sets negative rates to 0; the toolbox keeps them.
- **Field strength:** the weights are trained at 3 T, and qsmxt refuses any other unless `--set ignore_field_mismatch=true`.
- **Image:** `qsmxt:v10.0.0-models-2`, the QSMxT v10.0.0 release image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)). v10.0.0 has no `qsmxt r2prime --r2primenet` (QSMxT/QSMxT#460 came after it), so the entry is `ci_skip` until it is repinned to a release that has it; the parity workflow builds qsmxt from source.
- **Reference:** Kim et al., Human Brain Mapping 2025 · doi:[10.1002/hbm.70136](https://doi.org/10.1002/hbm.70136)

## How QSM-CI runs it

```bash
qsmxt r2star "$IN/magnitude.nii.gz" -m "$IN/mask.nii.gz" -o "$WORK/r2star.nii.gz" --echo-times $TES
qsmxt r2prime --r2star "$WORK/r2star.nii.gz" --r2primenet -m "$IN/mask.nii.gz" \
  -o "$OUT/r2prime.nii.gz" --field-strength "$FIELD" $SET
```
