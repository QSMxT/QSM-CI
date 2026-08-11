# Self-contained image for the r2star-qsm submission (recon baked; also runs with the repo dir mounted).
# Build & push: docker build -t ghcr.io/astewartau/qsm-ci/r2star-qsm:v1 algorithms/r2star-qsm
FROM python:3.12-slim
LABEL org.opencontainers.image.authors="Ashley Stewart" \
      org.opencontainers.image.source="https://github.com/QSMxT/QSM-CI" \
      org.opencontainers.image.description="QSM-CI chi-separation submission: r2star-qsm (Dimov et al. 2022)" \
      org.opencontainers.image.licenses="MIT"
RUN pip install --no-cache-dir numpy scipy nibabel
COPY run.sh recon.py /opt/qsm-ci/
