# MindGrab (QSM.rs)

MindGrab as QSM.rs runs it: the authors' trained weights exported to ONNX (QSM.rs's
`scripts/onnx-export/`) and run by `qsmxt mask mindgrab` on QSM.rs's ONNX engine (tract, CPU).

- **Stage:** `brain-extraction`: reads `magnitude`; writes `mask.nii.gz`.
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs).
- **Original:** none in QSM-CI yet (see [`fidelity/dl/`](../../fidelity/dl)).
- **Image:** `qsmxt:v10.0.0-models-2`, the QSMxT v10.0.0 release image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)), since the run has no network.
- **Reference:** Fani et al., arXiv:2506.11860 (2025) · doi:[10.48550/arXiv.2506.11860](https://doi.org/10.48550/arXiv.2506.11860)
- **Not scored yet:** `qsmxt mask mindgrab` is in QSMxT main but not in v10.0.0 (`ci_skip`); the parity workflow runs it with qsmxt built from source.

## How QSM-CI runs it

```bash
# On a multi-echo magnitude `qsmxt mask` reads the first echo.
qsmxt mask mindgrab "$IN/magnitude.nii.gz" -o "$OUT/mask.nii.gz"
```
