# HD-BET (QSM.rs)

HD-BET as QSM.rs runs it: the authors' trained weights exported to ONNX (QSM.rs's
`scripts/onnx-export/`) and run by `qsmxt mask hd-bet` on QSM.rs's ONNX engine (tract, CPU).

- **Stage:** `brain-extraction`: reads `magnitude`; writes `mask.nii.gz`.
- **Engine:** QSMxT / [QSM.rs](https://github.com/astewartau/QSM.rs).
- **Original:** [`hd-bet-qsmci`](../hd-bet-qsmci) runs the authors' own code and weights; the two entries share `algorithm: hd-bet`, so they form a port parity pair. First look: [`fidelity/dl/`](../../fidelity/dl).
- **Image:** `qsmxt:v10.0.0-models-2`, the QSMxT v10.0.0 release image with the ONNX weights baked in ([`_qsmxt/models.Dockerfile`](../_qsmxt/models.Dockerfile)), since the run has no network.
- **Reference:** Isensee et al., Hum Brain Mapp 2019 · doi:[10.1002/hbm.24750](https://doi.org/10.1002/hbm.24750)

## How QSM-CI runs it

```bash
# HD-BET without test-time augmentation, as the `hd-bet-qsmci` entry runs it. On a multi-echo
# magnitude `qsmxt mask` reads the first echo, where `hd-bet-qsmci` combines the echoes by
# root-sum-of-squares first (fidelity/dl/README.md).
qsmxt mask hd-bet "$IN/magnitude.nii.gz" -o "$OUT/mask.nii.gz"
```
