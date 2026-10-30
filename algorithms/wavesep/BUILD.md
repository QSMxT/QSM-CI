# Building the WaveSep image

WaveSep runs a purely iterative wavelet-domain optimiser on CPU — no MATLAB, no GPU, and **no
pretrained weights** (despite the upstream README saying "PyTorch", the QSM separation path is pure
NumPy + PyWavelets). The only third-party payload is the WaveSep **source code**
(https://github.com/ZhenghanFang/WaveSep), which has no license file and is used here with the
author's permission for academic benchmarking. To avoid redistributing it in this public repo, it
is not committed: the committed `Dockerfile` clones it at the pinned commit (f3a192e) into
`/opt/wavesep` at build time, with Python and every package pinned to what the published v1 image
holds. A rebuild gives the same output as v1 (fidelity/cpp-py/README.md).

`recon.py` is our own thin wrapper (it imports `wavesep.utils.solver_wavesep_qsm.Solver` and drives it);
the WaveSep source is used unmodified.

## Build + push

```bash
podman build -t ghcr.io/astewartau/qsm-ci/wavesep:<tag> algorithms/wavesep
podman push  ghcr.io/astewartau/qsm-ci/wavesep:<tag>   # then pin the digest in algorithm.yml
```

## Smoke test (docker runner)

```bash
python -m qsm_ci.cli run wavesep \
  --chimap   data/sim/chisep/inputs/chimap.nii.gz \
  --r2prime  data/sim/chisep/inputs/r2prime.nii.gz \
  --mask     data/sim/chisep/inputs/mask.nii.gz \
  --params   data/sim/chisep/inputs/params.json \
  -o out/ --truth data/sim/chisep/groundtruth/ --runner docker
```

Local run (no docker): clone the source (`git clone https://github.com/ZhenghanFang/WaveSep` at
f3a192e, copy its `wavesep/` next to `recon.py`; gitignored), then point `XSEP_PYTHON` at a python with
`numpy scipy nibabel PyWavelets scikit-image matplotlib tqdm` and use `--runner local`.

## Algorithm notes (what WaveSep expects)

- Inputs (QSM path only — the B0 direction is **not** used, so single-orientation data needs no
  reorientation):
  - **χ_total** (QSM) in **ppm** (`chimap.nii.gz`)
  - **R2'** in **Hz** (`r2prime.nii.gz`)
  - brain **mask**
- Model: χ+ + χ− ≈ χ_total and χ+ − χ− ≈ R2'/Dr, with a single relaxivity kernel **Dr = 137 Hz/ppm**
  (the qsm-forward phantom's kernel; WaveSep assumes Dr_pos == Dr_neg). Override with `$WAVESEP_DR` or a
  `"Dr"` key in `params.json`.
- Solver: proximal-gradient with wavelet-domain L1 (soft-thresholding), `db4`, max level, α=0.2,
  λ=0.02, ≤100 iterations with early stop (relative change < 1e-3). Repo defaults from
  `wavesep/qsm_sep.py`.
- Volumes are padded to a multiple of 2^L (L = max periodization level) so the wavelet round-trips,
  then cropped back — odd dims otherwise grow on reconstruction.
- Outputs: `chi-para.nii.gz` = χ+ (paramagnetic), `chi-dia.nii.gz` = χ− stored as a **positive
  magnitude** (−xn), as the stage contract requires.
- CPU-only; no CUDA, no network, no weight downloads.
