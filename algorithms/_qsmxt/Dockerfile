# QSMxT engine image — pinned to an official release (reproducible).
FROM debian:bookworm-slim
ARG QSMXT_VERSION=v9.2.0
RUN apt-get update && apt-get install -y --no-install-recommends jq ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL "https://github.com/QSMxT/QSMxT/releases/download/${QSMXT_VERSION}/qsmxt-${QSMXT_VERSION}-x86_64-unknown-linux-gnu.tar.gz" \
    | tar -xz -C /usr/local/bin qsmxt \
    && chmod +x /usr/local/bin/qsmxt
