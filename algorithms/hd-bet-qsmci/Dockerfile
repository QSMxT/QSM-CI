# HD-BET brain-extraction image: py-ref (python + nibabel) + a CPU torch + the HD-BET CNN.
# Model weights are fetched at build time (network is OFF at run time) and baked into the image.
FROM ghcr.io/astewartau/qsm-ci/py-ref:v1

# CPU-only torch + torchvision (installed together from the same index so their builds match —
# installing torch alone lets HD-BET pull an incompatible torchvision from PyPI, which breaks with
# "operator torchvision::nms does not exist"); then HD-BET from PyPI.
# Pinned (QSMxT/QSM-CI#301) to what the published image holds, so its scores stand.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
        torch==2.13.0+cpu torchvision==0.28.0+cpu \
    && pip install --no-cache-dir HD-BET==2.0.1 \
    && pip install --no-cache-dir scipy==1.18.0   # extract.py's signal-gated erosion (ndimage); already
                                          # pulled in transitively by nnU-Net, declared here so a
                                          # future HD-BET dependency change can't silently drop it

# HD-BET reads its weights from `os.path.expanduser('~')/hd-bet_params` — i.e. $HOME, with no env
# override. The qsm-ci runner runs containers as an arbitrary non-root user (docker --user), which
# doesn't set HOME, so it would resolve to `/` and fail with `PermissionError: /hd-bet_params`. Pin
# HOME to a fixed in-image directory and bake the weights there, world-READABLE (not writable — the
# weights are only read at run time; nothing is written, and nothing touches the host home dir).
ENV HOME=/opt/hdbet

# Pre-fetch the HD-BET model weights at build time (network is OFF at run time). Call the downloader
# directly (robust — no inference on a dummy volume, whose size the nnU-Net patching could reject).
RUN mkdir -p "$HOME" \
    && python3 -c "from HD_BET.entry_point import maybe_download_parameters; maybe_download_parameters()" \
    && echo 'd31dc59b4c5fe0028070901870c44c0b526f48c507ce50804941344356df7b52  /opt/hdbet/hd-bet_params/release_2.0.0/fold_all/checkpoint_final.pth' \
       | sha256sum -c - \
    && chmod -R a+rX "$HOME"

# HD-BET pulls in matplotlib, which wants to write a config cache under $HOME (read-only here). Point
# it at a writable tmp path so the non-root runtime user doesn't hit a (benign but noisy) warning.
ENV MPLCONFIGDIR=/tmp/mplconfig
