# Shared base image for the reference Python submissions (deps only).
# Build & push once: docker build -t ghcr.io/astewartau/qsm-ci/py-ref:v1 algorithms/_base
FROM python:3.12-slim
RUN pip install --no-cache-dir numpy scipy nibabel
