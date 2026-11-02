# iQSM+ (QSM.rs)

iQSM+ as QSM.rs runs it: the authors' trained weights exported to ONNX (QSM.rs's
`scripts/onnx-export/`) and run by `qsmxt invert iqsm-plus` on QSM.rs's ONNX engine (tract, CPU).

- **Stage:** `end-to-end`: reads every echo's wrapped `phase` (radians, 4-D), `magnitude`, `mask` and `params` (with the B0 direction); writes `chimap.nii.gz` (ppm).
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs).
- **Original:** [`iqsm-plus`](../iqsm-plus) runs the authors' own code and weights; the two entries share `algorithm: iqsm-plus`, so they form a port parity pair (`parity/thresholds.yml`).
- **Echo combination:** each echo goes through the network, and the echoes are combined with (magnitude × TE)² weights, as both of the authors' versions (Python and MATLAB) do.
- **Image:** `qsmxt:v10.0.0-models-2`, the QSMxT v10.0.0 release image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)). v10.0.0 has no `qsmxt invert iqsm-plus` (QSMxT/QSMxT#460 came after it), so the entry is `ci_skip` until it is repinned to a release that has it; the parity workflow builds qsmxt from source.
- **Reference:** Gao et al., Med Image Anal 2024 · doi:[10.1016/j.media.2024.103160](https://doi.org/10.1016/j.media.2024.103160)

## How QSM-CI runs it

```bash
qsmxt invert iqsm-plus "$IN/phase.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --field-strength "$FIELD" --echo-times $TES --b0-direction $B0DIR --magnitude "$IN/magnitude.nii.gz"
```
