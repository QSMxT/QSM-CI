# QSMxT engine image (the QSM.rs Rust binary) — shared by all QSMxT-backed submissions.
# The build context must contain the `qsmxt` binary (from a GitHub release,
# https://github.com/QSMxT/QSMxT/releases, or `cargo build --release`).
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends jq ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY qsmxt /usr/local/bin/qsmxt
RUN chmod +x /usr/local/bin/qsmxt
