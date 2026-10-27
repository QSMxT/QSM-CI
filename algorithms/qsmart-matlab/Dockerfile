# MCR + ANTs image for the compiled QSMART submission. Build the `recon` binary first (BUILD.md
# §1–3, licensed MATLAB R2023b + MATLAB Compiler), then:
#   podman build -t ghcr.io/astewartau/qsm-ci/matlab-qsmart:v3 .
# The QSMART toolbox, Frangi/curvatures, STI Suite and the Image Processing Toolbox functions they
# call are baked into `recon` at compile time. The image only needs the MATLAB Runtime of the
# compiling release (which includes the toolboxes' runtime components), plus ANTs'
# N4BiasFieldCorrection, which vasculature_mask_qsmci.m runs on the mean-echo magnitude.
# CI never builds this file; it pulls `image:` from algorithm.yml.
FROM containers.mathworks.com/matlab-runtime:r2023b
ENV AGREE_TO_MATLAB_RUNTIME_LICENSE=yes

# ANTs N4 from the pinned release zip. The binary must not see the MATLAB Runtime's libraries
# (its bundled libcurl/libstdc++ shadow the system ones), so N4BiasFieldCorrection is a wrapper
# that drops LD_LIBRARY_PATH: MATLAB's system() passes the Runtime's LD_LIBRARY_PATH to children.
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip ca-certificates && \
    env -u LD_LIBRARY_PATH curl -fsSL -o /tmp/ants.zip \
        https://github.com/ANTsX/ANTs/releases/download/v2.5.4/ants-2.5.4-ubuntu-22.04-X64-gcc.zip && \
    unzip /tmp/ants.zip -d /opt/ants && rm /tmp/ants.zip && \
    printf '#!/bin/sh\nexec env -u LD_LIBRARY_PATH /opt/ants/ants-2.5.4/bin/N4BiasFieldCorrection "$@"\n' \
        > /usr/local/bin/N4BiasFieldCorrection && \
    chmod +x /usr/local/bin/N4BiasFieldCorrection && \
    apt-get purge -y curl unzip && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# The r2023b base doesn't put the Runtime's libraries on the loader path (r2026a does), so the
# compiled binary can't find libmwlaunchermain.so without this. Set after the apt/curl step.
ENV MCRROOT=/opt/matlabruntime/R2023b
ENV LD_LIBRARY_PATH=${MCRROOT}/runtime/glnxa64:${MCRROOT}/bin/glnxa64:${MCRROOT}/sys/os/glnxa64:${MCRROOT}/extern/bin/glnxa64

# 755 rather than +x: CI runs as a non-root user that must READ the binary to extract its
# embedded CTF archive.
COPY --chmod=755 recon /opt/qsm-ci/recon
