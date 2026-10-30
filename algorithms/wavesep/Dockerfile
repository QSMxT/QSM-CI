# WaveSep (Fang et al., MLCN 2023): the authors' solver, unmodified, for the `wavesep` submission.
#
# The recipe of the published image (algorithm.yml `image:`, v1). The WaveSep source has no licence
# and is used with the author's permission for academic benchmarking, so it is not in this
# repository: the build clones it at the pinned commit (f3a192e, 2025-04-23, the latest) into
# /opt/wavesep. Python and every package are pinned to what the v1 image holds (`pip freeze` in
# it, 2026-10-28); a rebuild from this file gives the same output as v1 (see
# fidelity/cpp-py/README.md). recon.py and run.sh are mounted at run time, never baked.
#
#   podman build -t ghcr.io/astewartau/qsm-ci/wavesep:<tag> algorithms/wavesep
FROM docker.io/library/python:3.10.20-slim-trixie@sha256:bc2021edaa0ed48c55ccf295efeed3922147736c6a9f179e0c3b741e96d45fbc

ARG WAVESEP_COMMIT=f3a192efc2ceabcec87ae2b782db6dc80e100043
RUN set -eu; \
    apt-get update; \
    apt-get install -y --no-install-recommends libgomp1 git ca-certificates; \
    git clone https://github.com/ZhenghanFang/WaveSep.git /tmp/WaveSep; \
    git -C /tmp/WaveSep checkout -q "$WAVESEP_COMMIT"; \
    mkdir -p /opt/wavesep; cp -r /tmp/WaveSep/wavesep /opt/wavesep/wavesep; \
    chmod -R a+rX /opt/wavesep; rm -rf /tmp/WaveSep; \
    apt-get purge -y --auto-remove git; rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir \
      numpy==2.2.6 scipy==1.15.3 nibabel==5.4.2 PyWavelets==1.8.0 scikit-image==0.25.2 \
      matplotlib==3.10.9 tqdm==4.70.0 \
      contourpy==1.3.2 cycler==0.12.1 fonttools==4.63.0 ImageIO==2.37.4 \
      importlib_resources==7.1.0 kiwisolver==1.5.0 lazy-loader==0.5 networkx==3.4.2 \
      packaging==26.2 pillow==12.3.0 pyparsing==3.3.2 python-dateutil==2.9.0.post0 six==1.17.0 \
      tifffile==2025.5.10 typing_extensions==4.16.0
ENV WAVESEP_SRC=/opt/wavesep PYTHONUNBUFFERED=1
