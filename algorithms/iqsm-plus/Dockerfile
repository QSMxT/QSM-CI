# iQSM+ environment image — CPU-only single-step QSM inference (no GPU).
#
# iQSM+ (Gao et al., Medical Image Analysis 2024) is an orientation-adaptive deep network that maps
# raw wrapped phase straight to susceptibility (unwrap + background removal + dipole inversion in one
# pass). It is not published as a pip package, so we `git clone` the repo into the image, install its
# CPU dependencies, and bake the pretrained weights in — the scoring run has no network
# (`--network none`), so nothing can be fetched at run time.
#
# The submission's own code (run.sh) is mounted at /algo at run time; the cloned iQSM+ engine lives
# at $IQSM_PLUS_HOME and run.sh drives it from there.
#
# Build & push once (see algorithms/iqsm-plus/README.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/iqsm-plus:v1 algorithms/iqsm-plus
#   docker push ghcr.io/astewartau/qsm-ci/iqsm-plus:v1
FROM python:3.11-slim

# git to clone the engine; the Python deps below are pure wheels (no build toolchain needed).
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV IQSM_PLUS_HOME=/opt/iQSM_Plus

# Clone the iQSM+ engine at a pinned commit for reproducibility.
RUN git clone https://github.com/sunhongfu/iQSM_Plus.git "$IQSM_PLUS_HOME" \
    && git -C "$IQSM_PLUS_HOME" checkout a534d94ab6a24b70d3041b3d0164c7a13fb0d2d0

# CPU-only PyTorch wheel (the CUDA build would pull hundreds of MB of unused GPU libs). Inference is
# forced onto CPU at run time via CUDA_VISIBLE_DEVICES=-1 below.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# iQSM+ core (CLI) dependencies — numpy / scipy / nibabel / h5py / pydicom / huggingface_hub / pyyaml.
RUN pip install --no-cache-dir -r "$IQSM_PLUS_HOME/requirements.txt"

# Bake the pretrained weights into the image (scoring runs offline; weights cannot download at
# runtime). This fetches iQSM_plus.pth + LoTLayer_chi.pth from HuggingFace (sunhongfu/iQSM_Plus) into
# $IQSM_PLUS_HOME/checkpoints/, then exits.
RUN cd "$IQSM_PLUS_HOME" && python run.py --download-checkpoints

# Force CPU at run time (belt-and-braces; also set by run.sh).
ENV CUDA_VISIBLE_DEVICES="-1"
