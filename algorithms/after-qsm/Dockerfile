# AFTER-QSM environment image — GPU-capable (CPU-optional) PyTorch, pretrained affine-equivariant
# dipole-inversion network, packaged as a QSM-CI dipole-stage submission.
#
# AFTER-QSM (github.com/sunhongfu/AFTER-QSM; Xiong et al., NeuroImage 2022) is a two-stage deep network
# for QSM dipole inversion that is robust to ARBITRARY head orientation and ANISOTROPIC resolution
# (down to 0.6 mm iso). It (1) affine-transforms the input local field to the network's canonical
# axial / 0.6 mm frame, (2) runs a U-net for coarse dipole inversion, (3) inverse-affine-transforms
# back, then (4) runs a Residual-Dense refinement net to deblur. So it IS weight-dependent — it needs
# the pretrained checkpoint:
#   * checkpoints/AFTER-QSM.pkl — a torch state_dict {recon_model_state, refine_model_state}, ~34 MB,
#     COMMITTED directly in the repo (a real zip/pickle, not an LFS pointer). Baked in with the clone.
#
# We clone the repo at BUILD time (network ON) into /opt/AFTER-QSM so the run phase works fully offline
# (--network none) — the committed checkpoint comes along with the clone, so there is no separate
# download step (unlike dip-up's Dropbox fetch). We do NOT COPY the submission code — run.sh is mounted
# at /algo at run time (QSM-CI execution model); it drives the repo's own pure-Python entrypoint
# (run.py -> inference.run_after_qsm), which reads the field, preserves the input affine, auto-selects
# the device, and writes the refined (deblur) χ map.
#
# GPU-capable, CPU-optional: the default (CUDA) PyTorch wheel also runs on CPU-only hosts (torch falls
# back when no GPU is visible). Device is chosen AT RUN TIME by inference.run_after_qsm
# (cuda:0 if torch.cuda.is_available() else cpu) — GPU when the runner exposes one (QSM-CI's --runner
# passes --nv / --gpus all under QSMCI_GPU=1), else CPU, or forced CPU via QSMCI_FORCE_CPU=1. The
# reference recommends an 8 GB+ VRAM NVIDIA GPU; see README "RUNTIME / GPU CAVEAT". This submission is
# ci_skip'd until a GPU runner exists — it will not be scored on CPU (it does not fit the CI budget).
#
# Build & push once (see algorithms/after-qsm/BUILD.md) — build is deferred to a GPU/host, NOT run here:
#   docker build -t ghcr.io/astewartau/qsm-ci/after-qsm:v1 algorithms/after-qsm
#   docker push  ghcr.io/astewartau/qsm-ci/after-qsm:v1
FROM python:3.10-slim

LABEL description="AFTER-QSM — pretrained affine-equivariant dipole inversion (dipole) for QSM-CI"

# git to clone the repo (checkpoint is committed, so it comes along); libgomp1 for the PyTorch CPU
# (OpenMP) runtime; ca-certificates for TLS.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Default (CUDA) PyTorch wheel + NIfTI/array deps. The CUDA wheel bundles its own CUDA runtime, so it
# needs only an NVIDIA driver at run time (via --nv/--gpus) and falls back to CPU when none is visible.
# pyyaml is required by the repo's run.py config loader.
RUN pip install --no-cache-dir \
        "torch>=2.1.0" \
 && pip install --no-cache-dir \
        "numpy>=1.23" \
        "scipy>=1.10" \
        "nibabel>=5.0" \
        "pyyaml>=6.0"

# Clone AFTER-QSM (run.py / inference.py / networks / utils are driven by the wrapper; the committed
# checkpoints/AFTER-QSM.pkl comes with the clone). Pin a ref for reproducibility (override with
# --build-arg AFTERQSM_REF=<sha>).
ARG AFTERQSM_REF=d29afefc6d556242e498aa7a3ef6a102832ec851
RUN git clone https://github.com/sunhongfu/AFTER-QSM /opt/AFTER-QSM \
 && git -C /opt/AFTER-QSM checkout "$AFTERQSM_REF" \
 && test -f /opt/AFTER-QSM/checkpoints/AFTER-QSM.pkl
ENV AFTERQSM_HOME="/opt/AFTER-QSM"

# Device is selected at run time by inference.run_after_qsm (GPU when exposed, else CPU; force CPU with
# QSMCI_FORCE_CPU=1 via run.sh) — no build-time CUDA lock.
