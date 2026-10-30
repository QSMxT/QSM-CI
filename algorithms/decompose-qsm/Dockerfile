# MCR image for the compiled decompose-qsm submission, recovered from the v2 image's history
# (ghcr.io/astewartau/qsm-ci/decompose-qsm v2). `recon` was compiled with licensed MATLAB R2023b and
# the Optimization and Parallel Computing toolboxes (lsqcurvefit, parfor), then:
#   podman build -t ghcr.io/astewartau/qsm-ci/decompose-qsm:v2 .
# CI never builds this file; it pulls `image:` from algorithm.yml.
FROM containers.mathworks.com/matlab-runtime:r2023b
ENV AGREE_TO_MATLAB_RUNTIME_LICENSE=yes
# The r2023b base doesn't put the Runtime's libraries on the loader path.
ENV MCRROOT=/opt/matlabruntime/R2023b
ENV LD_LIBRARY_PATH=/opt/matlabruntime/R2023b/runtime/glnxa64:/opt/matlabruntime/R2023b/bin/glnxa64:/opt/matlabruntime/R2023b/sys/os/glnxa64:/opt/matlabruntime/R2023b/extern/bin/glnxa64
COPY recon /opt/qsm-ci/recon
# 755: CI runs as a non-root user that must read the binary to extract its CTF archive.
RUN chmod 755 /opt/qsm-ci/recon
