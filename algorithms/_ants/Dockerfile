# ANTs N4BiasFieldCorrection, the original of QSM.rs's N4 port (qsm_core::utils::n4, which cites
# ANTs 2.4.3 / ITK 5.3.0). QSMxT/QSM-CI#302.
#
# The official ANTs 2.4.3 release binary (ants-2.4.3-ubuntu-22.04-X64-gcc.zip, checked by SHA-256),
# on the Ubuntu 22.04 it was built for, pinned by digest. Only N4BiasFieldCorrection is kept: it is
# a self-contained executable (ITK is linked in; it needs libstdc++, libm and libc only). ANTs and
# ITK are Apache-2.0; the licence is copied in from the v2.4.3 tag. The fixture scripts (n4.sh) are
# mounted at run time, never baked.
#
#   podman build -t ghcr.io/astewartau/qsm-ci/ants-n4:v1 algorithms/_ants
#   podman push  ghcr.io/astewartau/qsm-ci/ants-n4:v1
FROM docker.io/library/ubuntu:22.04@sha256:8a2321a92b438238f93b4346fff61bc4259c99fdd4d9b52ee86f153fee0c344f

ARG ANTS_VERSION=2.4.3
ARG ANTS_ZIP_SHA256=acdeb56e4eadd2b7620ad5355334bc3beb45dd7c8bec820c406beef60cf92fd6
ARG ANTS_COPYING_SHA256=9d616c0ce0884dfb38a92a6e4cdbc52dd9b68293c028e75edad7a8e5704d0592

RUN set -eu; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl unzip; \
    cd /tmp; \
    curl -fsSL -o ants.zip \
      "https://github.com/ANTsX/ANTs/releases/download/v${ANTS_VERSION}/ants-${ANTS_VERSION}-ubuntu-22.04-X64-gcc.zip"; \
    echo "${ANTS_ZIP_SHA256}  ants.zip" | sha256sum -c -; \
    unzip -q ants.zip "ants-${ANTS_VERSION}/bin/N4BiasFieldCorrection"; \
    install -D -m 0755 "ants-${ANTS_VERSION}/bin/N4BiasFieldCorrection" /opt/ants/bin/N4BiasFieldCorrection; \
    curl -fsSL -o /opt/ants/COPYING.txt \
      "https://raw.githubusercontent.com/ANTsX/ANTs/v${ANTS_VERSION}/COPYING.txt"; \
    echo "${ANTS_COPYING_SHA256}  /opt/ants/COPYING.txt" | sha256sum -c -; \
    rm -rf /tmp/ants.zip "/tmp/ants-${ANTS_VERSION}"; \
    apt-get purge -y --auto-remove curl unzip; \
    rm -rf /var/lib/apt/lists/*

# ITK's thread count is fixed by the fixture script (n4.sh); 4 here as well, so a bare
# `N4BiasFieldCorrection` in this image runs as the fidelity record says.
ENV PATH=/opt/ants/bin:$PATH \
    ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS=4
