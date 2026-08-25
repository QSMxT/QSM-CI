# Self-contained image for the r2prime-scaled submission (recon baked; also runs with the repo dir mounted).
# Build & push: docker build -t ghcr.io/astewartau/qsm-ci/r2prime-scaled-qsmci:v1 algorithms/r2prime-scaled-qsmci
FROM python:3.12-slim
LABEL org.opencontainers.image.authors="Ashley Stewart" \
      org.opencontainers.image.source="https://github.com/QSMxT/QSM-CI" \
      org.opencontainers.image.description="QSM-CI r2prime-generation submission: fixed-fraction R2' = 0.52*R2*" \
      org.opencontainers.image.licenses="MIT"
RUN pip install --no-cache-dir numpy nibabel
COPY run.sh recon.py /opt/qsm-ci/
