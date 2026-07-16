# NeXtQSM environment image — CPU-only inference (no GPU, no ONNX).
#
# NeXtQSM requires Python 3.8 (higher versions may be incompatible). We install the published
# `nextqsm` package, then bake the ~150 MB pretrained weights into the image via
# `nextqsm --download_weights` so the run phase works fully offline (--network none).
#
# Build & push once (see algorithms/nextqsm/README.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/nextqsm:v1 algorithms/nextqsm
#   docker push ghcr.io/astewartau/qsm-ci/nextqsm:v1
FROM python:3.8-slim

# nextqsm depends on `tensorflow` (not the separate `tensorflow-cpu` distribution — installing that
# alongside would pull BOTH). Let nextqsm pull its own `tensorflow`; inference is forced onto CPU at
# run time via CUDA_VISIBLE_DEVICES=-1 below (the GPU build runs fine CPU-only, no GPU libs needed).
RUN pip install --no-cache-dir nextqsm

# Bake the pretrained weights into the image (scoring runs offline; weights cannot download at
# runtime). --download_weights fetches the ~150 MB checkpoint tarball from OSF and extracts it into
# the installed package's checkpoints/ dir, then exits.
RUN nextqsm --download_weights

# Force CPU + quiet TensorFlow logging at run time.
ENV CUDA_VISIBLE_DEVICES="-1" \
    TF_CPP_MIN_LOG_LEVEL="2"
