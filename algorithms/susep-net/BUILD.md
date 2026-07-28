# Building the SUSEP-Net image

SUSEP-Net runs a trained PyTorch model (`SUSEPNet.pth`) on CPU — no MATLAB, no GPU. The weights and
their normalisation stats (`all_mean_std.mat`) come from the authors' public Google-Drive release
(linked from https://github.com/YangGaoUQ/SUSEP-Net). They are large / weight files, so they're
gitignored (`algorithms/*/*.pth`, `*.mat`) and baked into the image at build time. The `Dockerfile`
is gitignored too, so CI pulls the prebuilt image rather than building it.

## Get the weights

Download `SUSEPNet.pth` and `all_mean_std.mat` from the SUSEP-Net Google-Drive folder
(https://drive.google.com/drive/folders/1oxgbs4BJ7m3tl2Z_GPj4BwdKxZLyywVP) and place them in
`algorithms/susep-net/`:

```bash
python -m venv /tmp/gdenv && /tmp/gdenv/bin/pip install gdown
/tmp/gdenv/bin/gdown --folder \
  "https://drive.google.com/drive/folders/1oxgbs4BJ7m3tl2Z_GPj4BwdKxZLyywVP" -O /tmp/susep-dl
cp /tmp/susep-dl/*/SUSEPNet.pth        algorithms/susep-net/
cp /tmp/susep-dl/*/norm/all_mean_std.mat algorithms/susep-net/
```

`recon.py` vendors the model architecture (`susepnet_model.py`, verbatim from the release's
`SUSEPNet.py`); the pretrained `SUSEPNet.pth` loads into it `strict=True`.

## Build + push

```bash
# from the repo root, with SUSEPNet.pth + all_mean_std.mat present in algorithms/susep-net/
docker build -t ghcr.io/astewartau/qsm-ci/susep-net:v1 algorithms/susep-net
docker push  ghcr.io/astewartau/qsm-ci/susep-net:v1   # make the GHCR package public
```

## Smoke test (docker runner)

```bash
python -m qsm_ci.cli run susep-net \
  --localfield data/sim/chisep/inputs/localfield.nii.gz \
  --chimap     data/sim/chisep/inputs/chimap.nii.gz \
  --r2prime    data/sim/chisep/inputs/r2prime.nii.gz \
  --magnitude  data/sim/chisep/inputs/magnitude.nii.gz \
  --mask       data/sim/chisep/inputs/mask.nii.gz \
  --params     data/sim/chisep/inputs/params.json \
  -o out/ --truth data/sim/chisep/groundtruth/ --runner docker
```

## Preprocessing (what the network expects)

- Inputs, 3 channels into `model(QSM, R2', LFS)`, each z-scored by `all_mean_std.mat`:
  - **QSM** (χ_total) in **ppm**
  - **R2'** in **Hz** (no Dr scaling)
  - **local field** in **ppm**
- Whole-volume (fully convolutional; padded up to a multiple of 8, cropped back).
- Outputs: channel 1 = χ+ (paramagnetic), channel 2 = χ− (diamagnetic). Decoder ends in ReLU, so
  both are non-negative magnitudes — χ− is stored as a positive magnitude, as the stage contract
  requires. De-normalise with the chi_pos / chi_neg stats.
- Inference forced onto CPU (`CUDA_VISIBLE_DEVICES=""`).
