# BFRnet environment image — CPU-only ONNX Runtime inference (no MATLAB / MCR).
#
# BFRnet (Zhu et al., Z Med Phys 2022) is a 3D octave-convolution U-net for background field removal.
# The authors distribute only a MATLAB Deep Learning Toolbox network (BFRnet.mat). We exported it to
# ONNX once (MATLAB `exportONNXNetwork`); this image runs that ONNX graph with onnxruntime — the
# output matches MATLAB `predict` to ~1e-8. recon.py does memory-bounded sliding-window inference
# (the whole 205^3 volume peaks ~18.7 GB and OOM-kills; tiled 128^3 patches peak ~5.3 GB) — a
# fraction of the MCR build's memory and image size.
#
# The ONNX weights (BFRnet.onnx, ~80 MB) are baked in at build time so scoring runs fully offline
# (--network none). The submission's run.sh + recon.py are mounted at /algo at run time (not baked).
#
# Build & push once (see README.md / BUILD.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/bfrnet:v2 algorithms/bfrnet
#   docker push  ghcr.io/astewartau/qsm-ci/bfrnet:v2
FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir onnxruntime numpy nibabel

# Bake the exported network (gitignored; see BUILD.md for how it's produced from BFRnet.mat).
COPY BFRnet.onnx /opt/bfrnet/BFRnet.onnx
