# QSMxT engine image with the deep-learning weights baked in, for the QSM.rs ports of the
# deep-learning models (`*-qsmrs` entries of xQSM, QSMnet, HD-BET, ...).
#
# qsmxt downloads ONNX weights on first use, but a submission runs with no network, so the weights
# are fetched here at build time from the Hugging Face repo QSM.rs's registry points at
# (qsmxt/qsm-onnx-weights), pinned to a commit, and checked against the SHA-256s in
# models.sha256 (copied from QSM.rs's src/models/registry.rs). qsmxt reads them from
# $QSM_MODEL_DIR.
#
#   docker build -f models.Dockerfile -t ghcr.io/astewartau/qsm-ci/qsmxt:v12.0.0-models-1 .
#
# BASE is the qsmxt image to add them to: by default the release image (algorithms/_qsmxt/Dockerfile),
# by digest. Any qsmxt image works, e.g. the parity workflow's build from source
# (--build-arg BASE=qsmxt-under-test:<run>), which needs the weights for these entries too.
ARG BASE=ghcr.io/astewartau/qsm-ci/qsmxt@sha256:c78a9ffb14b54c319cb5fb3409ccf06ac83bb79bf250a0baa2663710255b709e

FROM debian:bookworm-slim AS weights
ARG HF_REVISION=e7116c8b8be0ad0aa4155d68cb2f9c23363be362
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
COPY models.sha256 /opt/qsm-models/SHA256SUMS
RUN set -eu; cd /opt/qsm-models; \
    for f in $(awk '{print $2}' SHA256SUMS); do \
      curl -fsSL -o "$f" "https://huggingface.co/qsmxt/qsm-onnx-weights/resolve/${HF_REVISION}/$f"; \
    done; \
    sha256sum -c SHA256SUMS; chmod -R a+rX /opt/qsm-models

FROM ${BASE}
COPY --from=weights /opt/qsm-models /opt/qsm-models
ENV QSM_MODEL_DIR=/opt/qsm-models
