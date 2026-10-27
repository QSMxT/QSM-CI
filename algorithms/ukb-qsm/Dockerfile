# MCR image for the compiled ukb-qsm submission. Build the `recon` binary first (BUILD.md: licensed
# MATLAB R2023b + MATLAB Compiler, against the real Image Processing Toolbox), then:
#   podman build -t ghcr.io/astewartau/qsm-ci/matlab-ukb-qsm:v2 .
# STI Suite, the UKB code and the toolbox functions they call are baked into `recon` at compile
# time; the image only needs the MATLAB Runtime of the compiling release, which includes the
# toolboxes' runtime components. CI never builds this file; it pulls `image:` from algorithm.yml.
FROM containers.mathworks.com/matlab-runtime:r2023b@sha256:3441eaf9691d81d96322169ffb7a26d7fda2f4b4a9ae3a49d0ac408b05472f25
ENV AGREE_TO_MATLAB_RUNTIME_LICENSE=yes
# The r2023b base doesn't put the Runtime's libraries on the loader path (r2026a does), so the
# compiled binary can't find libmwlaunchermain.so without this.
ENV MCRROOT=/opt/matlabruntime/R2023b
ENV LD_LIBRARY_PATH=${MCRROOT}/runtime/glnxa64:${MCRROOT}/bin/glnxa64:${MCRROOT}/sys/os/glnxa64:${MCRROOT}/extern/bin/glnxa64
# 755 rather than +x: CI runs as a non-root user that must READ the binary to extract its
# embedded CTF archive.
COPY --chmod=755 recon /opt/qsm-ci/recon
