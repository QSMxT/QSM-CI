# ROMEO combined field-mapping image: py-ref + the qsmxt engine (QSM.rs).
#
# The `qsmxt fieldmap romeo` subcommand (combined multi-echo B0 mapping) lands in QSMxT v9.15.0.
# Pin QSMXT_VERSION to the first release that ships it. Statically-linked musl build — no glibc
# dependency — matching the shared _qsmxt engine image.
FROM ghcr.io/astewartau/qsm-ci/py-ref:v1
ARG QSMXT_VERSION=v9.15.0
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL "https://github.com/QSMxT/QSMxT/releases/download/${QSMXT_VERSION}/qsmxt-${QSMXT_VERSION}-x86_64-unknown-linux-musl.tar.gz" \
       | tar -xz -C /usr/local/bin qsmxt \
    && chmod +x /usr/local/bin/qsmxt \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
