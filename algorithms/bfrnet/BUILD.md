# Building the BFRnet (ONNX) image

BFRnet ships only as a MATLAB Deep Learning Toolbox network (`BFRnet.mat`, a `DAGNetwork`). We run it
**without MATLAB** by exporting that network to ONNX once and running it with ONNX Runtime. The output
matches MATLAB `predict` to max |Δ| ≈ 1e-8; it peaks at ~1.5 GB RAM (the former MCR build was
OOM-killed above the 16 GB hosted-runner limit → DNF) and the image is ~0.4 GB (vs several GB for MCR).

## 1. Obtain the trained network

Download `BFRnet_L2_64PS_24BS_45Epo_NewHCmix.mat` from the authors' Dropbox
("data & checkpoints" link in <https://github.com/sunhongfu/BFRnet>) and rename it to `BFRnet.mat`.
(It is the same network that was bundled into the former `matlab-bfrnet` MCR image.)

## 2. Export to ONNX (needs MATLAB + Deep Learning Toolbox + the ONNX Converter support package)

```matlab
S = load('BFRnet.mat'); net = S.net;         % trained DAGNetwork (186 std layers, no custom classes)
exportONNXNetwork(net, 'BFRnet.onnx', 'OpsetVersion', 13);
```

Then mark the input/output spatial dims dynamic so the fully-convolutional net accepts any
divisible-by-8 volume (it computes its own padding from the runtime shape):

```python
import onnx
m = onnx.load('BFRnet.onnx')
for vi in list(m.graph.input) + list(m.graph.output):
    for i in (2, 3, 4):                       # N, C, D, H, W -> make D,H,W symbolic
        d = vi.type.tensor_type.shape.dim[i]; d.ClearField('dim_value'); d.dim_param = f'ax{i}'
onnx.save(m, 'BFRnet.onnx')
```

Place the resulting `BFRnet.onnx` in this folder (it is gitignored — a build-time weight).

## 3. Build & push

```bash
docker build -t ghcr.io/astewartau/qsm-ci/bfrnet:v1 algorithms/bfrnet
docker push  ghcr.io/astewartau/qsm-ci/bfrnet:v1
```

New GHCR packages default to **private** — make `qsm-ci/bfrnet` **public** once in the package settings
so the scoring runner (anonymous `docker manifest inspect`) can pull it.
