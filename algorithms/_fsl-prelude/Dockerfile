# FSL PRELUDE (`prelude`, fsl-fugue 2603.0), the original of QSM.rs's PRELUDE port
# (qsm_core::unwrap::unwrap_prelude, written clean-room from Jenkinson's report; QSMxT/QSM-CI#302).
#
# LOCAL ONLY for now, as algorithms/_bet2: FSL's licence lets the software be passed on only without
# financial return, with the licence imposed on the receiver and all source included (README.md).
# Build it yourself for the parity measurement:
#
#   podman build -t localhost/qsm-ci/fsl-prelude:2603.0 algorithms/_fsl-prelude
#
# FSL's own compiled binaries, installed from FSL's official conda channel (the route FSL's
# installer takes), pinned to an exact package set: fsl-explicit.lock is `micromamba env export
# --explicit --md5` of `fsl-fugue=2603.0=he1a3b45_0` with its dependencies (FSL channel +
# conda-forge), and the install checks every package's MD5. Nothing is compiled here.
FROM docker.io/mambaorg/micromamba:2.0.5@sha256:c6c6daf6d2dbeb3be78b0bce740f19dbdbd51422e1dd9e56439efec0dbcdb9bb
USER root
COPY fsl-explicit.lock /opt/fsl-explicit.lock
RUN micromamba create -y -p /opt/fsl --file /opt/fsl-explicit.lock \
    && micromamba clean -afy \
    && /opt/fsl/bin/prelude 2>&1 | grep -q "Part of FSL"
ENV FSLDIR=/opt/fsl FSLOUTPUTTYPE=NIFTI_GZ PATH=/opt/fsl/bin:$PATH
