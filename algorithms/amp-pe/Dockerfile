# MCR image for the compiled amp-pe submission, recovered from the v2 image's history
# (ghcr.io/astewartau/qsm-ci/amp-pe v2). `recon` was compiled with MATLAB R2026a + MATLAB Compiler
# and the Wavelet Toolbox (BUILD.md), then:
#   docker build -t ghcr.io/astewartau/qsm-ci/amp-pe:v2 .
# CI never builds this file; it pulls `image:` from algorithm.yml.
FROM containers.mathworks.com/matlab-runtime:r2026a
ENV AGREE_TO_MATLAB_RUNTIME_LICENSE=yes
COPY recon /opt/qsm-ci/recon
RUN chmod +x /opt/qsm-ci/recon
