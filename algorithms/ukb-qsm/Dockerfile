# MCR image for a compiled MATLAB submission. Build the `recon` binary first (mcc, see BUILD.md),
# then: docker build -t ghcr.io/astewartau/qsm-ci/matlab-ukb-qsm:v1 .
#
# --chmod on the COPY rather than a RUN layer: the executable bit is all that is needed, and it
# avoids a build step that requires container networking.
FROM containers.mathworks.com/matlab-runtime:r2026a
ENV AGREE_TO_MATLAB_RUNTIME_LICENSE=yes
COPY --chmod=755 recon /opt/qsm-ci/recon
