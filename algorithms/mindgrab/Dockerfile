# MindGrab, the original: brainchop-cli (the authors' Python/tinygrad pipeline) with its MindGrab
# MeshNet checkpoint, CPU. QSMxT/QSM-CI#301.
#
# brainchop-cli is pinned to 31150c3 (2026-10-19, neuroneural/brainchop-cli#60), the first commit
# that applies the trained head bias [+1.525, -1.526] (model.25.bias); every release up to 0.2.5
# drops it (neuroneural/brainchop-cli#59), so the CLI and the web app gave different masks. The
# Python dependencies are its uv.lock's; the weights are brainchop-models 528f2d8's, checked by
# SHA-256, and baked in because the run has no network.
#
#   podman build -t ghcr.io/astewartau/qsm-ci/mindgrab:v1 algorithms/mindgrab
FROM docker.io/library/python:3.12-slim@sha256:1148dbb014615300fa7e713b2f94f550c0d1c69780c0805f84f093ceee34dd0b

# clang: tinygrad's CPU backend compiles its kernels with it. pigz: niimath's gzip.
RUN apt-get update && apt-get install -y --no-install-recommends git clang pigz ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG BRAINCHOP_COMMIT=31150c3
ARG MODELS_COMMIT=528f2d8d2ca937968b2d4b2b9ef9fa9170f4b9cf
RUN git clone https://github.com/neuroneural/brainchop-cli /opt/brainchop-cli \
    && git -C /opt/brainchop-cli checkout "$BRAINCHOP_COMMIT" \
    && pip install --no-cache-dir uv==0.9.5 nibabel==5.3.2 \
    && cd /opt/brainchop-cli \
    && uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt \
    && pip install --no-cache-dir --no-deps . \
    && pip freeze > /opt/brainchop-cli/pip-freeze.txt

# brainchop reads models.json and the checkpoint from ~/.cache/brainchop (downloading them when
# absent): bake them under a fixed HOME. run.sh copies it to a writable HOME at run time, because
# brainchop and tinygrad write their caches there.
ENV BRAINCHOP_HOME=/opt/brainchop-home
RUN d="$BRAINCHOP_HOME/.cache/brainchop" && mkdir -p "$d/models/mindgrab" \
    && cp /opt/brainchop-cli/models.json "$d/models.json" \
    && base="https://github.com/neuroneural/brainchop-models/raw/$MODELS_COMMIT/meshnet/mindgrab" \
    && python3 -c "import sys,urllib.request; [urllib.request.urlretrieve(f'$base/{f}', f'$d/models/mindgrab/{f}') for f in ('model.json','model.pth')]" \
    && printf '%s  %s\n' \
         31f1bda17b8d3eee17a54cf3f199899763a6615a049f05ab2a05f18eb98ec23a "$d/models/mindgrab/model.pth" \
         e321f27014eb05f187667873d5301be57f9aac4c5be427e68e9f484748d643fd "$d/models/mindgrab/model.json" \
         d2081bfc952f22938186c38e8c8c971c940714d9b2a7fd67c14756a0eb41415c "$d/models.json" \
       | sha256sum -c - \
    && chmod -R a+rX "$BRAINCHOP_HOME"
