# iQFM environment image — CPU-only, single-step tissue (local) field from raw phase.
#
# iQFM is the tissue/local-field output of the SAME iQSM network/repo: a LoT-Unet maps raw wrapped
# MRI phase -> local field, doing phase unwrapping + background-field removal in one pass. This image
# is byte-identical to algorithms/iqsm/Dockerfile — same repo, same pinned commit, same weights — the
# only difference between the two submissions is the run.sh flag (iqsm passes --no-iqfm; iqfm keeps
# the iQFM output). We clone the upstream repo into /opt/iqsm, install the CPU-only torch wheel + the
# repo's Python deps, then BAKE the pretrained weights into the image via
# `run.py --download-checkpoints` so the scoring run works fully offline (--network none).
#
# The four checkpoints downloaded by --download-checkpoints include BOTH the iQSM (chi) weights
# (iQSM_50_v2.pth, LPLayer_chi_50_v2.pth) AND the iQFM (tissue-field) weights (iQFM_40_v2.pth,
# LoTLayer_lfs_40_v2.pth), so the same download step covers iQFM as-is — no extra fetch needed.
#
# The algorithm folder is mounted read-only at /algo at run time; run.sh invokes the baked
# /opt/iqsm/run.py (iQFM resolves its checkpoints/ relative to its own source dir, so the source
# and weights must live together inside the image, not in the mounted /algo).
#
# NOTE: because this image is identical to iqsm's, iqfm could instead reuse the iqsm image tag; we
# default to its own tag (ghcr.io/astewartau/qsm-ci/iqfm:v1) for clarity/independence.
#
# Build & push once (see algorithms/iqfm/README.md):
#   docker build -t ghcr.io/astewartau/qsm-ci/iqfm:v1 algorithms/iqfm
#   docker push ghcr.io/astewartau/qsm-ci/iqfm:v1
FROM python:3.11-slim

# jq is used by run.sh to read params.json; git to clone the iQSM source.
RUN apt-get update && apt-get install -y --no-install-recommends git jq \
    && rm -rf /var/lib/apt/lists/*

# iQSM/iQFM source (CLI is run.py; pure-Python inference in inference.py — no MATLAB).
# Pin to a specific commit for reproducibility.
ARG IQSM_COMMIT=bb163ef
RUN git clone https://github.com/sunhongfu/iQSM /opt/iqsm \
    && git -C /opt/iqsm checkout "$IQSM_COMMIT"

# CPU-only PyTorch wheel (no CUDA libs), then the repo's runtime deps (CLI only, no web stack).
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r /opt/iqsm/requirements.txt

# Bake the four pretrained checkpoints (~16 MB each) into the image so the run phase needs no
# network. `run.py --download-checkpoints` pulls them from HuggingFace sunhongfu/iQSM into
# /opt/iqsm/checkpoints/, then exits. This includes the iQFM weights (iQFM_40_v2.pth,
# LoTLayer_lfs_40_v2.pth) used by this submission.
RUN cd /opt/iqsm && python run.py --download-checkpoints

# Force CPU inference at run time (the code falls back to CPU when CUDA is unavailable; this makes
# it explicit and belt-and-braces).
ENV CUDA_VISIBLE_DEVICES="-1" \
    IQSM_HOME="/opt/iqsm"
