# Self-contained image for the ridani-null-qsmci submission (recon baked; also runs with the repo dir mounted).
# Build & push: docker build -t ghcr.io/astewartau/qsm-ci/ridani-null-qsmci:v1 algorithms/ridani-null-qsmci
FROM python:3.12-slim
LABEL org.opencontainers.image.authors="Ashley Stewart" \
      org.opencontainers.image.source="https://github.com/QSMxT/QSM-CI" \
      org.opencontainers.image.description="QSM-CI chi-separation submission: ridani-null-qsmci" \
      org.opencontainers.image.licenses="MIT"
RUN pip install --no-cache-dir numpy scipy nibabel
COPY run.sh recon.py /opt/qsm-ci/
