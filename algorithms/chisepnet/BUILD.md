# Building the χ-sepnet image

χ-sepnet runs a trained ONNX model via `onnxruntime` (CPU) — no MATLAB. The model
(`240904_xsepnet.onnx`) and its normalisation stats (`xsepnet_train_patch_norm_factor_*.mat`) come
from the SNU-LIST chi-separation toolbox (academic use, via their Google form) and are **not** public,
so they're gitignored and baked into the image at build time. The `Dockerfile` is gitignored too, so
CI pulls the prebuilt image rather than building it.

```bash
# from the repo root, with the two model files present in algorithms/chi-sepnet/
docker build -t ghcr.io/astewartau/qsm-ci/chi-sepnet:v1 algorithms/chi-sepnet
docker push  ghcr.io/astewartau/qsm-ci/chi-sepnet:v1   # make the GHCR package public
```

Smoke test (docker runner):
```bash
python -m qsm_ci.cli run chi-sepnet \
  --localfield data/sim/chisep/inputs/localfield.nii.gz \
  --chimap     data/sim/chisep/inputs/chimap.nii.gz \
  --r2prime    data/sim/chisep/inputs/r2prime.nii.gz \
  --magnitude  data/sim/chisep/inputs/magnitude.nii.gz \
  --mask       data/sim/chisep/inputs/mask.nii.gz \
  --params     data/sim/chisep/inputs/params.json \
  -o out/ --truth data/sim/chisep/groundtruth/ --runner docker
```
