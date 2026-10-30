# qsmxt built from source, for the parity workflow's QSM.rs under test (.github/workflows/parity.yml).
# The same environment as algorithms/_qsmxt (debian-slim, jq, a static musl qsmxt), with the binary
# taken from the build context instead of a release download. Context: a directory holding `qsmxt`.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends jq ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY qsmxt /usr/local/bin/qsmxt
