# AutoQSM environment image — CPU-only inference (TensorFlow 1.15 / Python 3.6).
#
# AutoQSM (Wei et al., NeuroImage 2019) is a single-step V-Net that maps a total field map straight
# to susceptibility — no brain extraction, no separate background-field removal. Its published code
# targets a *legacy* stack: Python 3.6, TensorFlow 1.15.0, Keras 2.2.5. We pin exactly that here and
# run it CPU-only; we do NOT port it to a newer TF.
#
# The AutoQSM repo (code + the ~17 MB pretrained weights model_final_1.hdf5, committed in-repo, not
# LFS) is baked into the image at build time so the scoring run works fully offline (--network none).
# The submission's own run.sh + predict.py are mounted at /algo at run time (not baked).
#
# Build & push once (see algorithms/autoqsm/README.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/autoqsm:v1 algorithms/autoqsm
#   docker push  ghcr.io/astewartau/qsm-ci/autoqsm:v1
FROM python:3.6-slim

# git: to clone the AutoQSM repo at build time.
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Legacy stack, pinned exactly to what AutoQSM was published against. TF 1.15.0 ships CPU + GPU in one
# wheel; with no GPU libs / CUDA_VISIBLE_DEVICES=-1 it runs CPU-only. numpy is capped because TF 1.15
# breaks against numpy>=1.19 (np.object / np.bool removals). h5py<3 for Keras 2.2.5 weight loading.
RUN pip install --no-cache-dir \
      tensorflow==1.15.0 \
      keras==2.2.5 \
      "numpy<1.19" \
      "h5py<3.0" \
      "scipy<1.6" \
      nibabel

# Bake the AutoQSM code + pretrained weights into the image (the run phase has no network, so nothing
# can be fetched at run time). Pinned to the commit reviewed for this submission.
RUN git clone https://github.com/AMRI-Lab/AutoQSM /opt/AutoQSM && \
    cd /opt/AutoQSM && git checkout b59f5e74954d2c2c12626068fdca3160d7826348
ENV AUTOQSM_HOME=/opt/AutoQSM

# Force CPU + quiet TensorFlow logging at run time.
ENV CUDA_VISIBLE_DEVICES="-1" \
    TF_CPP_MIN_LOG_LEVEL="2"
