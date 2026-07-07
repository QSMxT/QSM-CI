# License-free MATLAB-language submission via GNU Octave.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends octave gzip \
    && rm -rf /var/lib/apt/lists/*
COPY recon.m readnii.m writenii.m run.sh /opt/algo/
WORKDIR /opt/algo
