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
# Pinned (QSMxT/QSM-CI#301) to what the published image holds, so its scores stand.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        torch==2.13.0+cpu torchvision==0.28.0+cpu \
    && pip install --no-cache-dir \
        nibabel==5.4.2 numpy==2.4.4 scikit-image==0.26.0 tqdm==4.68.4 scipy==1.18.0

# Bake the LPCNN repo (modernized code + committed checkpoints + normalization stat .npy
# files under data/numpy_data/whole/list/) into the image so inference runs offline.
# dd1ef2b (2025-12-16) is the commit the image holds; master has since added only a uv environment
# (39b7820, README/pyproject/uv.lock). The trained checkpoints ship in the repo.
ARG LPCNN_REF=dd1ef2b1642766f0708f0d8534957b4052ff9747
RUN git clone https://github.com/Sulam-Group/LPCNN.git /opt/LPCNN \
    && git -C /opt/LPCNN checkout "$LPCNN_REF" \
    && cd /opt/LPCNN/checkpoints \
    && printf '%s\n' 'e302ea3ed64f4824fd44956d16a49963f4c253ebba5a5a97a82f5c112df9f6c9  lpcnn_test_Bmodel.pkl' \
         'eafd4277df6d7b1074a302d57ace8b6e110104db11626b58d610043c9c69c72f  lpcnn_test_Emodel.pkl' | sha256sum -c -

ENV LPCNN_HOME=/opt/LPCNN
