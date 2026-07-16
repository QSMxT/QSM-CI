# NeXtQSM environment image — CPU-only inference (no GPU, no ONNX).
#
# NeXtQSM requires Python 3.8 (higher versions may be incompatible). We install the published
# `nextqsm` package with a CPU-only TensorFlow, then bake the ~150 MB pretrained weights into the
# image via `nextqsm --download_weights` so the run phase works fully offline (--network none).
#
# Build & push once (see algorithms/nextqsm/README.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/nextqsm:v1 algorithms/nextqsm
#   docker push ghcr.io/astewartau/qsm-ci/nextqsm:v1
FROM python:3.8-slim

# tensorflow-cpu keeps the image lean and avoids pulling CUDA. nextqsm depends on `tensorflow`, so we
# install tensorflow-cpu explicitly first to satisfy that dependency without the GPU build.
RUN pip install --no-cache-dir \
        "tensorflow-cpu>=2.11,<2.14" \
        nextqsm

# Bake the pretrained weights into the image (scoring runs offline; weights cannot download at
# runtime). --download_weights fetches the ~150 MB checkpoint tarball from OSF and extracts it into
# the installed package's checkpoints/ dir, then exits.
RUN nextqsm --download_weights

# Force CPU + quiet TensorFlow logging at run time.
ENV CUDA_VISIBLE_DEVICES="-1" \
    TF_CPP_MIN_LOG_LEVEL="2"
