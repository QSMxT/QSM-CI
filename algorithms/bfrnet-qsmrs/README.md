# BFRnet (QSM.rs)

BFRnet as QSM.rs runs it: the authors' trained weights exported to ONNX (QSM.rs's
`scripts/onnx-export/`) and run by `qsmxt bgremove bfrnet` on QSM.rs's ONNX engine (tract, CPU).

- **Stage:** `bfr`: reads `totalfield` (ppm) and `mask`; writes `localfield.nii.gz` (ppm).
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs).
- **Original:** [`bfrnet`](../bfrnet) runs the authors' own code and weights; the two entries share `algorithm: bfrnet`, so they form a port parity pair. First look: [`fidelity/dl/`](../../fidelity/dl).
- **Image:** `qsmxt:v10.0.0-models-2`, the QSMxT v10.0.0 release image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)), since the run has no network.
- **Reference:** Zhu et al., Z Med Phys 2022 · doi:[10.1016/j.zemedi.2022.08.001](https://doi.org/10.1016/j.zemedi.2022.08.001)

## How QSM-CI runs it

```bash
# B0 direction and field strength from params.json (QSMCI_* env, CONTRACT.md).
B0DIR="${QSMCI_B0_DIR:-0 0 1}"
qsmxt bgremove bfrnet "$IN/totalfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/localfield.nii.gz" \
  --b0-direction $B0DIR
```
