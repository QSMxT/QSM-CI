# MoDL-QSM environment image — CPU-only inference on legacy TensorFlow 1.15.
#
# MoDL-QSM ships as source (github.com/Ruimin-Feng/MoDL-QSM) with the ~1.8 MB trained weights
# (logs/last.h5) and the input-normalisation factors (NormFactor.mat) committed in-repo. We clone
# the repo at BUILD time (network is ON) so everything — code + weights + NormFactor.mat — is baked
# in and the run phase works fully offline (--network none).
#
# The method targets Python 3.6 + TensorFlow 1.15.0 + Keras 2.2.5 (README "Environmental
# Requirements"). This legacy stack is pinned exactly; the code is NOT ported to TF2.
#
# Build & push once (see algorithms/modl-qsm/README.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/modl-qsm:v1 algorithms/modl-qsm
#   docker push ghcr.io/astewartau/qsm-ci/modl-qsm:v1
FROM python:3.6-slim

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Legacy stack, pinned. TF 1.15 CPU wheel + Keras 2.2.5; numpy/h5py/protobuf pinned to versions that
# still resolve against TF 1.15 on py36. nibabel for NIfTI I/O in run.sh's converter.
RUN pip install --no-cache-dir \
      "tensorflow==1.15.0" \
      "keras==2.2.5" \
      "numpy==1.18.5" \
      "h5py==2.10.0" \
      "protobuf==3.20.1" \
      "scipy==1.4.1" \
      "nibabel==3.0.2"

# Bake the algorithm source (code + logs/last.h5 weights + NormFactor.mat) into the image at
# /opt/MoDL-QSM. The run phase has no network, so this cannot be fetched at run time.
RUN git clone --depth 1 https://github.com/Ruimin-Feng/MoDL-QSM /opt/MoDL-QSM
ENV MODL_QSM_HOME="/opt/MoDL-QSM"

# Force CPU + quiet TensorFlow logging at run time (the repo hardcodes CUDA device 0; override it).
ENV CUDA_VISIBLE_DEVICES="-1" \
    TF_CPP_MIN_LOG_LEVEL="2"
