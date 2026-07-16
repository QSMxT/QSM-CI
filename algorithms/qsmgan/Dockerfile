# QSMGAN environment image — CPU-only, patch-based inference (no GPU).
#
# QSMGAN (Chen et al., NeuroImage 2020) is a 3D U-Net generator refined by a WGAN-GP.
# The published code targets "PyTorch >= 0.4"; the released checkpoints are the legacy
# (pre-1.6, tar/pickle) torch.save format. The state_dict is only standard
# Conv3d/BatchNorm3d/ConvTranspose3d layers, so a legacy torch loads and runs it as-is
# — we do NOT rewrite the model, only vendor its UNet3D definition in recon.py.
#
# Pinning: Python 3.7 + the legacy CPU wheel torch==1.1.0 from the PyTorch download
# index. torch 1.1.0 (May 2019) is contemporaneous with the QSMGAN release (checkpoints
# dated 2019) and satisfies the code's "PyTorch >= 0.4" requirement. We do NOT use the
# 0.4.1 wheel: its prebuilt cu92 binary was compiled WITHOUT NumPy support, so
# torch.from_numpy() raises at runtime. 1.1.0 is the lowest legacy torch that both loads
# the pre-1.6 checkpoint AND has working NumPy interop.
#
# Weights (~30 MB total) are committed in the working fork and unzipped at BUILD time
# (network is on only during build); the run phase is offline (--network none).
#
# Build & push once (see algorithms/qsmgan/README.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/qsmgan:v1 algorithms/qsmgan
#   docker push  ghcr.io/astewartau/qsm-ci/qsmgan:v1
FROM python:3.7-slim

RUN apt-get update && apt-get install -y --no-install-recommends git unzip \
    && rm -rf /var/lib/apt/lists/*

# Legacy PyTorch (CPU). torch 0.4.1 is the version the QSMGAN code was written for and
# is published as a cp37 CPU wheel on the PyTorch index. numpy/nibabel are pinned to
# versions that still support py3.7 and the old torch ABI.
RUN pip install --no-cache-dir "numpy<1.20" \
    && pip install --no-cache-dir \
        torch==1.1.0 -f https://download.pytorch.org/whl/torch_stable.html \
    && pip install --no-cache-dir "nibabel==3.2.2" "scipy<1.6"

# Fetch the WGAN-refined generator weights from the working fork and unzip. The
# official LupoLab-UCSF/QSMGAN repo ships README only; the fork below carries the
# code + committed checkpoints (UNet3D_i64o48.zip, WGAN_i64o48.zip). We use the
# WGAN generator (the checkpoint the upstream NIFTI inference script loads).
# The committed .zip preserves the checkpoints' original 0660 root:root perms; the
# scorer runs the container as a non-root user (docker run --user <uid>:<gid>), which
# then can't read config.json / net_best.pt (recon.py -> PermissionError). chmod the
# tree world-readable so inference works regardless of the run uid.
RUN git clone --depth 1 https://github.com/mmorri10/QSMGAN-LupoLab /tmp/qsmgan \
    && mkdir -p /opt/qsmgan \
    && unzip -q /tmp/qsmgan/WGAN_i64o48.zip -d /opt/qsmgan \
    && unzip -q /tmp/qsmgan/UNet3D_i64o48.zip -d /opt/qsmgan \
    && rm -rf /tmp/qsmgan \
    && chmod -R a+rX /opt/qsmgan

ENV CUDA_VISIBLE_DEVICES="-1" \
    QSMGAN_WEIGHTS="/opt/qsmgan/WGAN_i64o48"
