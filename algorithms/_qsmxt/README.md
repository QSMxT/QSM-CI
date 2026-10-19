# QSMxT engine image

Shared environment for every QSMxT-backed submission (the QSM.rs algorithms, `*-qsmrs`). Pinned to an
official QSMxT release (`v10.0.0`, built on QSM.rs v0.39.0) plus `jq` (used by each `run.sh` to read
`params.json` / `config.json`). Submissions mount their `run.sh` at `/algo` and call
`qsmxt fieldmap <algo>` / `qsmxt bgremove <algo>` / `qsmxt invert <algo>` / `qsmxt separate <algo>` /
`qsmxt qsmart`. The release archive is verified against its `SHA256SUMS` at build time.

    docker build --build-arg QSMXT_VERSION=v10.0.0 -t ghcr.io/astewartau/qsm-ci/qsmxt:v10.0.0 .
    docker push ghcr.io/astewartau/qsm-ci/qsmxt:v10.0.0

Each submission pins its own image in `image:` by digest (with the tag as a comment), so older
methods keep running against the release they were scored on. Build a new tag when a submission needs
a QSMxT version that is not published yet, and push it before the submission merges, since the run
phase has no network.
