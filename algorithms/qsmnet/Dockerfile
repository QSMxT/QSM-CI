# QSMnet environment image — CPU-only QSM dipole inversion, TensorFlow 1.14 / Python 3.7.
#
# QSMnet is a pretrained 3D U-Net for dipole inversion (local field in ppm -> susceptibility in ppm).
# It targets the legacy TF1 stack (TensorFlow 1.14, Python 3.7) and is NOT ported to TF2 — that
# legacy pin is intentional and fine for offline inference. The repo isn't a pip package, so we clone
# it and drive its network_model.py from qsmnet_infer.py (mounted at /algo).
#
# The pretrained checkpoints live on the authors' Google Drive (see Checkpoints/download_network.sh):
#   QSMnet_64.tar.gz   id 1kyRKSPN78i1npIaFvJJJgmB84v-N106m
#   QSMnet+_64.tar.gz  id 1ee5nI-MMySImX2tM4m71szcjFow4DD5g
# We fetch them with gdown at BUILD time (network is ON here, OFF at scoring) so inference runs fully
# offline. gdown handles Google Drive's large-file confirm-token that a plain wget would trip on.
# Each image bakes only its own checkpoint, selected by the QSMNET_GDRIVE_ID / QSMNET_NAME build args.
#
# Build & push once (see algorithms/qsmnet/README.md); scoring also builds this folder at score-time:
#   docker build -t ghcr.io/astewartau/qsm-ci/qsmnet:v1 algorithms/qsmnet
#   docker push ghcr.io/astewartau/qsm-ci/qsmnet:v1
FROM python:3.7-slim

LABEL description="QSMnet — CPU-only QSM dipole inversion (TF 1.14) for QSM-CI"

# git to clone the repo; libgomp1 for the TF CPU (OpenMP) runtime; ca-certificates for gdown TLS.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Legacy TF1 stack. tensorflow==1.14.0 is CPU+GPU in one wheel and runs CPU-only fine (we pin
# CUDA_VISIBLE_DEVICES=-1). Its deps (numpy/scipy) are constrained to versions that import cleanly
# on this old TF; nibabel provides NIfTI I/O; gdown fetches the Google-Drive checkpoints.
RUN pip install --no-cache-dir \
        "tensorflow==1.14.0" \
        "protobuf<3.20" \
        "numpy==1.16.4" \
        "scipy==1.2.1" \
        "nibabel==3.2.2" \
        "gdown==4.7.1" \
        "matplotlib==3.0.3"

# Clone QSMnet (pinned for reproducibility) into /opt/QSMnet.
# Pinned (QSMxT/QSM-CI#301): the commit the published image was built from (master's head then
# and now).
ARG QSMNET_REF=f8782ed26a60680559037d3d11d4b5953eb77f4b
RUN git clone https://github.com/SNU-LIST/QSMnet.git /opt/QSMnet \
 && git -C /opt/QSMnet checkout "$QSMNET_REF"

# Bake this image's checkpoint. Downloads <name>.tar.gz from Google Drive and extracts the
# Checkpoints/<name>/ dir (weights + norm_factor_<name>.mat + network_info_<name>.npy).
ARG QSMNET_NAME=QSMnet_64
ARG QSMNET_GDRIVE_ID=1kyRKSPN78i1npIaFvJJJgmB84v-N106m
RUN cd /opt/QSMnet/Checkpoints \
 && gdown "$QSMNET_GDRIVE_ID" -O "${QSMNET_NAME}.tar.gz" \
 && tar -xvzf "${QSMNET_NAME}.tar.gz" \
 && rm "${QSMNET_NAME}.tar.gz" \
 && test -d "/opt/QSMnet/Checkpoints/${QSMNET_NAME}" \
 && cd "/opt/QSMnet/Checkpoints/${QSMNET_NAME}" \
 && printf '%s\n' 'd5151f37fa77821eedcf94e4e40978ba3fb7b94f45e84f7e247a49c4ce0b1de7  QSMnet_64-25.data-00000-of-00001' '0cfd066ceb169f2acef28005964d305811d8b510cf356755b0b9d195f1e7dc6d  QSMnet_64-25.index' 'ecaf52ab7ae2b27caa17b031c393ec1791bae302ca13431ef0861b1e34b63cc7  QSMnet_64-25.meta' | sha256sum -c -

ENV QSMNET_NAME="QSMnet_64" \
    QSMNET_CKPT_DIR="/opt/QSMnet/Checkpoints/QSMnet_64" \
    QSMNET_CODE="/opt/QSMnet/Code" \
    QSMNET_EPOCH="25" \
    CUDA_VISIBLE_DEVICES="-1" \
    TF_CPP_MIN_LOG_LEVEL="2"
