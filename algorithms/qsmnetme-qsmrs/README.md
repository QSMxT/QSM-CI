# QSMnetME (QSM.rs)

QSMnetME as QSM.rs runs it: the χ-separation toolbox's network (its ONNX graph with the spatial axes
re-declared dynamic) and the toolbox's route (rotation into the training frame, 1 mm spline
resampling, the whole frame in one pass, mapped back), run by `qsmxt invert qsmnetme` on QSM.rs's
ONNX engine (tract, CPU).

- **Stage:** `dipole`: reads `localfield` (ppm), `mask` and `params`; writes `chimap.nii.gz` (ppm).
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs) (`inversion::qsmnetme`).
- **Original:** [`qsmnetme`](../qsmnetme) runs the toolbox's own network by its route; the two
  entries share `algorithm: qsmnetme`, so they form a port parity pair.
- **Image:** `qsmxt:v12.0.0-models-1`, the QSMxT image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)).
- **Reference:** Kim et al., Hum Brain Mapp 2025 · doi:[10.1002/hbm.70136](https://doi.org/10.1002/hbm.70136)

## How QSM-CI runs it

```bash
B0DIR="${QSMCI_B0_DIR:-0 0 1}"
qsmxt invert qsmnetme "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $B0DIR --field-strength "${QSMCI_B0:-3}"
```
