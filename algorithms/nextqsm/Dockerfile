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
# Pinned (QSMxT/QSM-CI#301) to what the published image holds, so its scores stand.
RUN pip install --no-cache-dir nextqsm==1.0.6 tensorflow==2.13.1 keras==2.13.1 numpy==1.24.3 \
        nibabel==5.2.1 h5py==3.11.0

# Bake the pretrained weights into the image (scoring runs offline; weights cannot download at
# runtime). --download_weights fetches the ~150 MB checkpoint tarball from OSF and extracts it into
# the installed package's checkpoints/ dir, then exits.
RUN nextqsm --download_weights \
    && cd /usr/local/lib/python3.8/site-packages/nextqsm/checkpoints \
    && printf '%s\n' 'e7c6ba36073cfa5a59d163a50ec3ad16cc9dd67214311430f5ae105a76323635  zdir_calc-HR-vn-nets.weights.h5' \
         '7963d53bf19644bd9e4d32ebad5204613c472b338f29550688c4de88612c667c  zdir_calc-HRbf-rmse-weights.weights.h5' \
       | sha256sum -c -

# Force CPU + quiet TensorFlow logging at run time.
ENV CUDA_VISIBLE_DEVICES="-1" \
    TF_CPP_MIN_LOG_LEVEL="2"
