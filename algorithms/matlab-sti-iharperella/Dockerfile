# MCR image for a compiled MATLAB submission. Build the `recon` binary first (mcc, see BUILD.md),
# then: docker build -t ghcr.io/astewartau/qsm-ci/matlab-sti-iharperella:v1 .
FROM containers.mathworks.com/matlab-runtime:r2026a
ENV AGREE_TO_MATLAB_RUNTIME_LICENSE=yes
COPY recon /opt/qsm-ci/recon
RUN chmod +x /opt/qsm-ci/recon
