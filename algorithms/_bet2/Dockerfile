# FSL BET2 (`bet2`), the original of QSM.rs's BET port (qsm_core::bet, which cites
# Bostrix/FSL-BET2 d5acd7f). QSMxT/QSM-CI#302.
#
# LOCAL ONLY: do not push this image. bet2 is FSL code under the FSL (Release 5.0) licence, which
# allows passing it on only without financial return, with the licence imposed on the receiver
# and with all source included; a public registry image cannot impose terms on whoever pulls it.
# See README.md. Build it yourself for the parity measurement:
#
#   podman build -t localhost/qsm-ci/bet2:d5acd7f algorithms/_bet2
#
# Built from source at the pinned commit with the repository's own CMake files, on Ubuntu 22.04
# (pinned by digest). The source tree is kept in the image (/opt/FSL-BET2), as the licence asks.
FROM docker.io/library/ubuntu:22.04@sha256:8a2321a92b438238f93b4346fff61bc4259c99fdd4d9b52ee86f153fee0c344f

ARG BET2_COMMIT=d5acd7fe09a34679aaac63f67f20409abf2ed3b9
RUN set -eu; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates git build-essential cmake zlib1g-dev; \
    git clone https://github.com/Bostrix/FSL-BET2.git /opt/FSL-BET2; \
    cd /opt/FSL-BET2; git checkout -q "$BET2_COMMIT"; \
    mkdir build; cd build; cmake .. -DCMAKE_BUILD_TYPE=Release; make -j4 bet2; \
    install -m 0755 /opt/FSL-BET2/bin/bet2 /usr/local/bin/bet2; \
    rm -rf /opt/FSL-BET2/build /opt/FSL-BET2/.git; \
    apt-get purge -y --auto-remove git cmake; \
    rm -rf /var/lib/apt/lists/*
ENV FSLOUTPUTTYPE=NIFTI_GZ
