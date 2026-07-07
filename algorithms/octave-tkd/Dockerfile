# Environment image for MATLAB-language submissions: GNU Octave (deps only).
# The submission's .m code is mounted at /algo at run time, not baked in.
# A submission needing a toolbox would download it here (build phase has network), e.g.:
#   RUN git clone --depth 1 https://github.com/<org>/<octave-qsm-toolbox> /opt/toolbox
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends octave gzip \
    && rm -rf /var/lib/apt/lists/*
