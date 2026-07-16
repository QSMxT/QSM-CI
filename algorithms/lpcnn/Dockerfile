# LPCNN environment image — CPU-only dipole inversion (modern PyTorch code path).
#
# The LPCNN repo was modernized in 2025 (README/pyproject: tested Python 3.13, PyTorch 2.9)
# with the deprecated torch FFT / scikit-image APIs replaced. We use that updated code path,
# NOT the old conda environment.yml. The ~5 MB pretrained checkpoints and the small
# normalization stat .npy files (train_gt_mean/std, ...) are committed in the repo, so the
# run phase works fully offline (--network none) — nothing is downloaded at run time.
#
# The QSM-CI scorer builds this folder Dockerfile at score time (build phase, network ON),
# then runs `bash /algo/run.sh` with the network OFF. run.sh imports LPCNN from /opt/LPCNN.
#
# Build & push once (see algorithms/lpcnn/README.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/lpcnn:v1 algorithms/lpcnn
#   docker push  ghcr.io/astewartau/qsm-ci/lpcnn:v1
FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends git jq \
    && rm -rf /var/lib/apt/lists/*

# CPU-only PyTorch to keep the image small (no CUDA libraries needed for --no_cuda).
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision \
    && pip install --no-cache-dir \
        "nibabel>=5.3.3" "numpy>=2.3.5" "scikit-image>=0.25.2" "tqdm>=4.67.1" "scipy"

# Bake the LPCNN repo (modernized code + committed checkpoints + normalization stat .npy
# files under data/numpy_data/whole/list/) into the image so inference runs offline.
RUN git clone --depth 1 https://github.com/Sulam-Group/LPCNN.git /opt/LPCNN

ENV LPCNN_HOME=/opt/LPCNN
