# Building the χ-separation toolbox image (χ-sepnet and QSMnetME)

The `chisepnet` and `qsmnetme` entries run the χ-separation toolbox v1.1.3's own networks via
`onnxruntime` (CPU) — no MATLAB: `models/240904_QSMnet.onnx` (QSMnetME), `240904_xsepnet.onnx`
(χ-sepnet), `240531_R2PRIMEnet.onnx` and the normalisation file
`xsepnet_train_patch_norm_factor_inplane_largedegree_romeo_arlo.mat`. They come from the SNU-LIST
toolbox (academic use, via their Google form) and are **not** public, so they are baked into the
image, which is built outside the repo:

```dockerfile
FROM python:3.12.7-slim
RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 nibabel==5.3.2 onnx==1.17.0 onnxruntime==1.19.2
COPY 240904_QSMnet.onnx 240904_xsepnet.onnx 240531_R2PRIMEnet.onnx xsepnet_train_patch_norm_factor_inplane_largedegree_romeo_arlo.mat /opt/xsepnet/
RUN cd /opt/xsepnet && sha256sum * > SHA256SUMS && chmod -R a+rX /opt/xsepnet
ENV XSEPNET_MODELS=/opt/xsepnet
```

```bash
# in a directory holding that Dockerfile and the toolbox's models/ files
podman build -t ghcr.io/astewartau/qsm-ci/chisep-toolbox:v1 .
podman push  ghcr.io/astewartau/qsm-ci/chisep-toolbox:v1   # then make the GHCR package public
```

SHA-256 of the files: `240904_QSMnet.onnx` de2f2c23d0374e92500ac9916b16de9e519ddc3971450a214af38cde7079b9ec,
`240904_xsepnet.onnx` 4f2343649cf36b4c9b371fc732da600720060bf2e76ed845578f16fe3411b3f2,
`240531_R2PRIMEnet.onnx` 0c5b48254adbbe77e00f8862dbb32373e5b951c19d1392f01f451b66ffa143de, the `.mat`
0a4ea04bbc55008ff89e2b5c9f9bab4f087d6e413bc2dd89d45bfc7616818ad9.

The run.sh / recon.py / chisep_route.py of each entry are mounted from the repo; the image only
holds the environment and the networks. The networks declare a fixed 192×192×128 input; the toolbox
replaces the input layer to fit its frame, and `chisep_route.load_net` re-declares the spatial axes
dynamic in memory for ONNX Runtime (weights and nodes untouched).

Smoke test (docker runner):
```bash
python -m qsm_ci.cli run chisepnet \
  --localfield data/sim/chisep/inputs/localfield.nii.gz \
  --r2prime    data/sim/chisep/inputs/r2prime.nii.gz \
  --mask       data/sim/chisep/inputs/mask.nii.gz \
  --params     data/sim/chisep/inputs/params.json \
  -o out/ --truth data/sim/chisep/groundtruth/ --runner docker
```

Local run (no container): `XSEP_PYTHON=<python with numpy, scipy, nibabel, onnx, onnxruntime> bash
run.sh <in> <out>`, with `CHISEP_TOOLBOX` pointing at the toolbox checkout.
