# R2023b MATLAB Runtime (pinned by digest) + recon (BUILD.md §2) + mritools 4.7.1's romeo binary,
# which the χ-separation toolbox's script calls through mritools' ROMEO.m.
FROM containers.mathworks.com/matlab-runtime:r2023b@sha256:3441eaf9691d81d96322169ffb7a26d7fda2f4b4a9ae3a49d0ac408b05472f25
ENV AGREE_TO_MATLAB_RUNTIME_LICENSE=yes
ENV MCRROOT=/opt/matlabruntime/R2023b
ENV LD_LIBRARY_PATH=${MCRROOT}/runtime/glnxa64:${MCRROOT}/bin/glnxa64:${MCRROOT}/sys/os/glnxa64:${MCRROOT}/extern/bin/glnxa64
ADD https://github.com/korbinian90/CompileMRI.jl/releases/download/v4.7.1/mritools_ubuntu-22.04_4.7.1.tar.gz /tmp/mritools.tar.gz
RUN mkdir -p /opt/mritools && tar -xzf /tmp/mritools.tar.gz -C /opt/mritools --strip-components=1 && rm /tmp/mritools.tar.gz \
    && test -x /opt/mritools/bin/romeo
ENV MRITOOLS_ROMEO=/opt/mritools/bin/romeo
# FSL's licence: the bet2 sources the mex was built from, and licence.html (README.md, BUILD.md).
COPY fsl-bet2/ /opt/fsl-bet2/
LABEL org.opencontainers.image.licenses="LicenseRef-FSL-Release-4.0 AND LicenseRef-MATLAB-Runtime"
COPY --chmod=755 recon /opt/qsm-ci/recon
