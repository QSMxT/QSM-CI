# iQFM (QSM.rs)

iQFM as QSM.rs runs it: the authors' trained weights exported to ONNX (QSM.rs's
`scripts/onnx-export/`) and run by `qsmxt bgremove iqfm` on QSM.rs's ONNX engine (tract, CPU).

- **Stage:** `unwrap+bfr`: reads every echo's wrapped `phase` (radians, 4-D), `magnitude`, `mask` and `params`; writes `localfield.nii.gz` (ppm).
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs).
- **Original:** [`iqfm`](../iqfm) runs the authors' own code and weights; the two entries share `algorithm: iqfm`, so they form a port parity pair (`parity/thresholds.yml`).
- **Echo combination:** each echo goes through the network, and the echoes are combined with (magnitude × TE)² weights, as the authors' Python code that the original entry runs; `--set echo_weighting=mag-te2` gives their MATLAB code's magnitude × TE².
- **Image:** `qsmxt:v10.0.0-models-2`, the QSMxT v10.0.0 release image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)). v10.0.0 has no `qsmxt bgremove iqfm` (QSMxT/QSMxT#460 came after it), so the entry is `ci_skip` until it is repinned to a release that has it; the parity workflow builds qsmxt from source.
- **Reference:** Gao et al., NeuroImage 2022 · doi:[10.1016/j.neuroimage.2022.119410](https://doi.org/10.1016/j.neuroimage.2022.119410)

## How QSM-CI runs it

```bash
qsmxt bgremove iqfm "$IN/phase.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" \
  --field-strength "$FIELD" --echo-times $TES --b0-direction $B0DIR $MAG $SET
```
