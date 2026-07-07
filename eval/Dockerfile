# qsm-eval scorer image (pushed to GHCR by .github/workflows/eval-image.yml).
#
# NOTE: the build must be able to fetch qsm-core. For a reproducible image, pin the git rev in
# eval/Cargo.toml (see the comment there) before building this — a local `path` dependency won't
# resolve inside this isolated build context.
FROM rust:1-slim AS build
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends git pkg-config && rm -rf /var/lib/apt/lists/*
COPY Cargo.toml ./
COPY src ./src
RUN cargo build --release --bin qsm-eval

FROM debian:bookworm-slim
COPY --from=build /build/target/release/qsm-eval /usr/local/bin/qsm-eval
ENTRYPOINT ["qsm-eval"]
