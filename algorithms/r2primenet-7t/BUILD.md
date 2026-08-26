# Building the R2PRIMEnet-7T image

R2PRIMEnet-7T runs a trained ONNX model via `onnxruntime` (CPU) — no torch at runtime. The
checkpoint (`CheckPoint/r2pnet7T.pth.tar`) and normalisation stats (`r2pnet7T_norm_factor.mat`)
are public in [SNU-LIST/R2PRIMENET_7T](https://github.com/SNU-LIST/R2PRIMENET_7T) under an
academic/research-use notice, so the converted weights are gitignored here (not redistributed in
this repo) and baked into the image. The `Dockerfile` is gitignored too, so CI pulls the prebuilt
image rather than building it.

## ONNX export

`torch.onnx.export` of the repo's `R2convNet` (a plain conv+BN+ReLU U-Net; 4 pooling levels →
inputs must be multiples of 16, we pad to 64 per the official test.py) with dynamic spatial axes,
opset 17, validated against the torch forward pass to <1e-3 on random volumes. The export script
used (standalone network redefinition, no repo imports) lives in the PR that added this submission;
run it in any torch container:

```bash
python export_r2pnet7t.py R2PRIMENET_7T/CheckPoint/r2pnet7T.pth.tar r2pnet7T.onnx
```

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir numpy scipy nibabel onnxruntime
COPY run.sh recon.py r2pnet7T.onnx r2pnet7T_norm_factor.mat /opt/qsm-ci/
ENV XSEPNET_MODELS=/opt/qsm-ci
```

```bash
# from the repo root, with the two model files present in algorithms/r2primenet-7t/
docker build -t ghcr.io/astewartau/qsm-ci/r2primenet-7t:v1 algorithms/r2primenet-7t
docker push  ghcr.io/astewartau/qsm-ci/r2primenet-7t:v1   # make the GHCR package public
```

Smoke test (docker runner):
```bash
python -m qsm_ci.cli run r2primenet-7t \
  --magnitude data/sim/chisep/inputs/magnitude.nii.gz \
  --mask      data/sim/chisep/inputs/mask.nii.gz \
  --params    data/sim/chisep/inputs/params.json \
  -o out/ --runner docker
```

Local run (no container): `XSEP_PYTHON=<python-with-onnxruntime> bash run.sh <in> <out>` with the
model files next to recon.py or `R2PNET7T_DIR` pointing at the R2PRIMENET_7T checkout.
