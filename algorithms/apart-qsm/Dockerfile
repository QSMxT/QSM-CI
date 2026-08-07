# MCR image for the compiled APART-QSM submission. Build the `recon` binary first (mcc, see BUILD.md),
# then:
#   docker build -t ghcr.io/astewartau/qsm-ci/apart-qsm:v1 .
# apart_utils + the NIfTI toolbox + the (author-obtained) APART core solver are baked into `recon` at
# compile time, so the image only needs the MATLAB Runtime (incl. the Optimization + Parallel Computing
# Toolbox runtimes) + the binary. Compile on Bunya with R2023b (its MATLAB has the required toolboxes),
# so the runtime base MUST be r2023b to match.
# Dockerfile gitignored elsewhere → CI pulls the pushed image.
FROM containers.mathworks.com/matlab-runtime:r2023b
ENV AGREE_TO_MATLAB_RUNTIME_LICENSE=yes
# The r2023b base doesn't put the MCR libs on the loader path, so the compiled binary can't find
# libmwlaunchermain.so. Set it explicitly to the runtime lib dirs.
ENV MCRROOT=/opt/matlabruntime/R2023b
ENV LD_LIBRARY_PATH=${MCRROOT}/runtime/glnxa64:${MCRROOT}/bin/glnxa64:${MCRROOT}/sys/os/glnxa64:${MCRROOT}/extern/bin/glnxa64
COPY recon /opt/qsm-ci/recon
# 755 (not +x, which keeps the compiler's g/o mode): CI runs as a non-root user that must be able to
# READ the binary to extract its embedded CTF archive — o-r would fail with "Cannot find CTF".
RUN chmod 755 /opt/qsm-ci/recon
