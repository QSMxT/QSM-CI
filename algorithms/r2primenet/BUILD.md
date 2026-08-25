# Building the R2PRIMEnet image

R2PRIMEnet runs a trained ONNX model via `onnxruntime` (CPU) — no MATLAB. The model
(`240531_R2PRIMEnet.onnx`) and its normalisation stats (`xsepnet_train_patch_norm_factor_*.mat`)
come from the SNU-LIST chi-separation toolbox (academic use, via their Google form) and are **not**
public, so they're gitignored and baked into the image at build time (same delivery as the χ-sepnet
submission — the two share the toolbox's models/ dir and the `$XSEPNET_MODELS` convention). The
`Dockerfile` is gitignored too, so CI pulls the prebuilt image rather than building it.

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir numpy scipy nibabel onnxruntime
COPY run.sh recon.py 240531_R2PRIMEnet.onnx xsepnet_train_patch_norm_factor_inplane_largedegree_romeo_arlo.mat /opt/qsm-ci/
ENV XSEPNET_MODELS=/opt/qsm-ci
```

```bash
# from the repo root, with the two model files copied into algorithms/r2primenet/
docker build -t ghcr.io/astewartau/qsm-ci/r2primenet:v1 algorithms/r2primenet
docker push  ghcr.io/astewartau/qsm-ci/r2primenet:v1   # make the GHCR package public
```

Smoke test (docker runner):
```bash
python -m qsm_ci.cli run r2primenet \
  --magnitude data/sim/chisep/inputs/magnitude.nii.gz \
  --mask      data/sim/chisep/inputs/mask.nii.gz \
  --params    data/sim/chisep/inputs/params.json \
  -o out/ --runner docker
```

Local run (no container): `XSEP_PYTHON=<python-with-onnxruntime> bash run.sh <in> <out>` with
`CHISEP_TOOLBOX` pointing at the toolbox checkout (recon.py reads its models/ dir).
