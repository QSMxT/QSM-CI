# MCR + ANTs image for the compiled QSMART submission. Build the `recon` binary first (BUILD.md
# §1–3, licensed MATLAB R2023b + MATLAB Compiler), then:
#   podman build -t ghcr.io/astewartau/qsm-ci/matlab-qsmart:v4 .
# The QSMART toolbox, Frangi/curvatures, STI Suite and the Image Processing Toolbox functions they
# call are baked into `recon` at compile time. The image only needs the MATLAB Runtime of the
# compiling release (which includes the toolboxes' runtime components), plus ANTs'
# N4BiasFieldCorrection, which vasculature_mask_qsmci.m runs on the mean-echo magnitude.
# CI never builds this file; it pulls `image:` from algorithm.yml.
# FSL bet2 for brainmask.m, built from Bostrix/FSL-BET2 d5acd7f as ../_bet2 does. Its source and
# FSL's licence text go into the image (README.md, *Licence*).
FROM docker.io/library/ubuntu:22.04@sha256:8a2321a92b438238f93b4346fff61bc4259c99fdd4d9b52ee86f153fee0c344f AS bet2
ARG BET2_COMMIT=d5acd7fe09a34679aaac63f67f20409abf2ed3b9
RUN set -eu; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates git build-essential cmake zlib1g-dev; \
    git clone https://github.com/Bostrix/FSL-BET2.git /opt/FSL-BET2; \
    cd /opt/FSL-BET2; git checkout -q "$BET2_COMMIT"; \
    mkdir build; cd build; cmake .. -DCMAKE_BUILD_TYPE=Release; make -j4 bet2; \
    install -m 0755 /opt/FSL-BET2/bin/bet2 /usr/local/bin/bet2; \
    rm -rf /opt/FSL-BET2/build /opt/FSL-BET2/.git /opt/FSL-BET2/bin; \
    awk '/LICENCE/,/\*\//' $(find /opt/FSL-BET2 -name bet2.cpp | head -1) > /opt/FSL-BET2/LICENCE-FSL.txt; \
    test -s /opt/FSL-BET2/LICENCE-FSL.txt

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
COPY --from=bet2 /usr/local/bin/bet2 /usr/local/bin/bet2
COPY --from=bet2 /opt/FSL-BET2 /opt/FSL-BET2
LABEL org.opencontainers.image.licenses="LicenseRef-FSL-Release-5.0 AND Apache-2.0 AND LicenseRef-MATLAB-Runtime"
COPY --chmod=755 recon /opt/qsm-ci/recon
