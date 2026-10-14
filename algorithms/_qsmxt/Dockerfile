# QSMxT engine image — pinned to an official release (reproducible).
FROM debian:bookworm-slim
ARG QSMXT_VERSION=v10.0.0
RUN apt-get update && apt-get install -y --no-install-recommends jq ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
# Statically-linked musl build — no glibc dependency, so it runs on any slim base. The archive is
# checked against the release's SHA256SUMS (published from v10.0.0) before it is unpacked.
RUN set -eu; A="qsmxt-${QSMXT_VERSION}-x86_64-unknown-linux-musl.tar.gz"; \
    U="https://github.com/QSMxT/QSMxT/releases/download/${QSMXT_VERSION}"; \
    cd /tmp && curl -fsSLO "$U/$A" \
    && curl -fsSL "$U/SHA256SUMS" | grep " $A\$" | sha256sum -c - \
    && tar -xzf "$A" -C /usr/local/bin qsmxt && chmod +x /usr/local/bin/qsmxt && rm -f "$A"
