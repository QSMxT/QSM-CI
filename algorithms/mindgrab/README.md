# MindGrab (brainchop)

MindGrab, brainchop's any-contrast skull-stripping MeshNet, run by the authors' own pipeline,
`brainchop --skull-strip` (brainchop-cli, tinygrad, CPU).

- **Stage:** `brain-extraction`: reads the multi-echo `magnitude`; writes `mask.nii.gz` (uint8).
- **Pipeline:** the echoes combined by root-sum-of-squares (as `hd-bet-qsmci` and `qsmxt mask`); then brainchop's niimath `-conform` (256³, 1 mm), quantile normalisation, the network, the largest 26-connected component and a nearest-neighbour reslice back to the input grid. No beam search (`--no-optimize`).
- **Pinned:** brainchop-cli `31150c3` (neuroneural/brainchop-cli#60, the first commit that applies the trained head bias; releases up to 0.2.5 drop it, #59), its `uv.lock` dependencies, the weights of brainchop-models `528f2d8` (SHA-256 checked at build), base image by digest.
- **Port:** [`mindgrab-qsmrs`](../mindgrab-qsmrs) (`qsmxt mask mindgrab`); the pair is `mindgrab` in `parity/thresholds.yml`.

```bash
podman build -t ghcr.io/astewartau/qsm-ci/mindgrab:v2 algorithms/mindgrab
```

## Fidelity

- **Determinism.** The image was run twice on the KKI s002001 bridge-run1 head, under apptainer from a read-only SIF on Bunya (8 CPUs). The two masks are byte-identical, and identical to v1's. Each run took 10–20 min, with 2.7 GB peak RSS.
- **v2 fix.** v2 puts niimath's own binary on PATH, because pip's `niimath` wrapper chmods it on every import, which fails on a read-only image. Nothing else changes from v1.
- **Port.** `mindgrab-qsmrs` gives Dice 0.99996 inside the dataset mask (run 41556813951).
