# QSMxT engine image

Shared environment for the QSMxT-backed submissions (all the QSM.rs algorithms). It contains the
self-contained `qsmxt` binary plus `jq` (used by each `run.sh` to read `B0_dir` from `params.json`).
Submissions mount their `run.sh` at `/algo` and call `qsmxt bgremove <algo>` / `qsmxt invert <algo>`.

Build (with a `qsmxt` binary in this dir):

    docker build -t ghcr.io/astewartau/qsm-ci/qsmxt:v1 .
