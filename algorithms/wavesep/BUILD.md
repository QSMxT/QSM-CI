# Building the WaveSep image

WaveSep runs a purely iterative wavelet-domain optimiser on CPU — no MATLAB, no GPU, and **no
pretrained weights** (despite the upstream README saying "PyTorch", the QSM separation path is pure
NumPy + PyWavelets). The only third-party payload is the WaveSep **source code**
(https://github.com/ZhenghanFang/WaveSep), which has no license file and is used here with the
author's permission for academic benchmarking. To avoid redistributing it in this public repo, the
vendored package (`algorithms/wavesep/wavesep/`) is gitignored (`algorithms/wavesep/wavesep/`) and
baked into the image at build time. The `Dockerfile` is gitignored too, so CI pulls the prebuilt image
rather than building it.

## Get the source

Clone the WaveSep repo and vendor its `wavesep` package into this submission folder (pinned commit for
reproducibility):

```bash
git clone https://github.com/ZhenghanFang/WaveSep /tmp/WaveSep
git -C /tmp/WaveSep checkout f3a192efc2ceabcec87ae2b782db6dc80e100043
rm -rf algorithms/wavesep/wavesep
cp -r /tmp/WaveSep/wavesep algorithms/wavesep/wavesep
```

`recon.py` is our own thin wrapper (it imports `wavesep.utils.solver_wavesep_qsm.Solver` and drives it);
the vendored WaveSep source is used unmodified.

## Build + push

```bash
# from the repo root, with algorithms/wavesep/wavesep/ present (see "Get the source")
docker build -t ghcr.io/astewartau/qsm-ci/wavesep:v1 algorithms/wavesep
docker push  ghcr.io/astewartau/qsm-ci/wavesep:v1   # make the GHCR package public
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

Local run (no docker): clone the source as above, then point `XSEP_PYTHON` at a python with
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
