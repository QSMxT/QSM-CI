# MindGrab (brainchop)

MindGrab, brainchop's any-contrast skull-stripping MeshNet, run by the authors' own pipeline,
`brainchop --skull-strip` (brainchop-cli, tinygrad, CPU).

- **Stage:** `brain-extraction`: reads the multi-echo `magnitude`; writes `mask.nii.gz` (uint8).
- **Pipeline:** the echoes combined by root-sum-of-squares (as `hd-bet-qsmci` and `qsmxt mask`); then brainchop's niimath `-conform` (256³, 1 mm), quantile normalisation, the network, the largest 26-connected component and a nearest-neighbour reslice back to the input grid. No beam search (`--no-optimize`).
- **Pinned:** brainchop-cli `31150c3` (neuroneural/brainchop-cli#60, the first commit that applies the trained head bias; releases up to 0.2.5 drop it, #59), its `uv.lock` dependencies, the weights of brainchop-models `528f2d8` (SHA-256 checked at build), base image by digest.
- **Port:** [`mindgrab-qsmrs`](../mindgrab-qsmrs) (`qsmxt mask mindgrab`); the pair is `mindgrab` in `parity/thresholds.yml`.

```bash
podman build -t ghcr.io/astewartau/qsm-ci/mindgrab:v1 algorithms/mindgrab
```
