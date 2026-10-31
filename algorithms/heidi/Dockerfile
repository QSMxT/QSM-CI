# MCR image for the compiled heidi submission. Build the `recon` binary first (BUILD.md: licensed
# MATLAB R2023b + MATLAB Compiler, with qsm_heidi 4592631), then:
#   podman build -t ghcr.io/astewartau/qsm-ci/heidi:heidi-v2 .
# qsm_heidi's heidi/ and lsqr/ code is baked into `recon` at compile time; the image
# only needs the MATLAB Runtime of the compiling release, which includes the toolboxes' runtime
# components. CI never builds this file; it pulls `image:` from algorithm.yml.
FROM containers.mathworks.com/matlab-runtime:r2023b@sha256:3441eaf9691d81d96322169ffb7a26d7fda2f4b4a9ae3a49d0ac408b05472f25
ENV AGREE_TO_MATLAB_RUNTIME_LICENSE=yes
# The r2023b base doesn't put the Runtime's libraries on the loader path (r2026a does), so the
# compiled binary can't find libmwlaunchermain.so without this.
ENV MCRROOT=/opt/matlabruntime/R2023b
ENV LD_LIBRARY_PATH=${MCRROOT}/runtime/glnxa64:${MCRROOT}/bin/glnxa64:${MCRROOT}/sys/os/glnxa64:${MCRROOT}/extern/bin/glnxa64
# HEIDI denoises its gradient mask with the ITK 3.20 executable qsm_heidi ships
# (heidi/GradientAnisotropicDiffusionImageFilter and its libraries; BUILD.md §1 copies them to
# ./itk). diffusionimagefilter.m runs it from reppath; QSM-CI's reppath.m reads QSMCI_HEIDI_ITK.
COPY --chmod=755 itk/ /opt/heidi-itk/
ENV QSMCI_HEIDI_ITK=/opt/heidi-itk
# qsm_heidi's license asks that its notice ship with every copy.
COPY LICENSE.qsm_heidi /opt/qsm-ci/LICENSE.qsm_heidi
# 755 rather than +x: CI runs as a non-root user that must READ the binary to extract its
# embedded CTF archive.
COPY --chmod=755 recon /opt/qsm-ci/recon
