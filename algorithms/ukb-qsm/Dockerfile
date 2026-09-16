# The compiled `recon` on the license-free MATLAB Runtime. Build it first — see BUILD.md.
FROM ghcr.io/astewartau/qsm-ci/matlab-runtime:r2026a

COPY recon /opt/qsm-ci/recon
COPY run.sh /opt/qsm-ci/run.sh

ENV MATLAB_RECON=/opt/qsm-ci/recon
ENTRYPOINT ["bash", "/opt/qsm-ci/run.sh"]
