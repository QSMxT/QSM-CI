# IR2QSM environment image: CPU-only dipole inversion (PyTorch), for QSM-CI.
#
# The recipe of the published image (ir2qsm v1), pinned (QSMxT/QSM-CI#301) to what it holds: IR2QSM
# 1ddb147 (the head of main then and now), CPU torch 2.5.1, and the authors' checkpoint
# model_IR2Unet.pth, checked by SHA-256. run.sh and ir2qsm_infer.py are mounted at /algo at run
# time, not baked. The checkpoint is the authors' Google Drive file (BUILD.md); when Drive refuses
# the download, fetch it by hand into this folder and build with --build-arg IR2QSM_CKPT_LOCAL=1
# (v1 was built that way).
#
#   docker build -t ghcr.io/astewartau/qsm-ci/ir2qsm:v1 algorithms/ir2qsm
FROM python:3.10-slim

LABEL description="IR2QSM — CPU-only QSM dipole inversion (PyTorch) for QSM-CI"

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "torch==2.5.1+cpu" --index-url "https://download.pytorch.org/whl/cpu" \
 && pip install --no-cache-dir "numpy==2.2.6" "scipy==1.15.3" "nibabel==5.4.2" "gdown==6.1.0"

ARG IR2QSM_REF=1ddb147090c7b98917013a372df1a74dbed80850
RUN git clone https://github.com/YangGaoUQ/IR2QSM.git /opt/IR2QSM \
 && git -C /opt/IR2QSM checkout "$IR2QSM_REF"

ARG IR2QSM_GDRIVE_ID=1EGZGxdgVWI8r0RlyfjP-xQyOL88vLeDf
ARG IR2QSM_CKPT_LOCAL=0
COPY Dockerfile model_IR2Unet.pth* /tmp/ckpt/
RUN set -eu; C=/opt/IR2QSM/Evaluate/model_IR2Unet.pth; \
    if [ "$IR2QSM_CKPT_LOCAL" = 1 ]; then cp /tmp/ckpt/model_IR2Unet.pth "$C"; \
    else gdown "$IR2QSM_GDRIVE_ID" -O "$C"; fi; rm -rf /tmp/ckpt; \
    echo "26e55e56c52307a63ecf4f9f40aa2dc808ef8c3ce96edbd1ca2a8ff459ffe366  $C" | sha256sum -c -

ENV IR2QSM_HOME=/opt/IR2QSM \
    IR2QSM_CODE=/opt/IR2QSM/Evaluate \
    IR2QSM_CKPT=/opt/IR2QSM/Evaluate/model_IR2Unet.pth \
    CUDA_VISIBLE_DEVICES=-1
