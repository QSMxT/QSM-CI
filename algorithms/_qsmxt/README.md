# QSMxT engine image

Shared environment for the QSMxT-backed submissions (the QSM.rs algorithms). Pinned to an official
QSMxT release plus `jq` (used by each `run.sh` to read `B0_dir` from `params.json`). Submissions
mount their `run.sh` at `/algo` and call `qsmxt bgremove <algo>` / `qsmxt invert <algo>`.

    docker build -t ghcr.io/astewartau/qsm-ci/qsmxt:v10.0.0 .   # downloads the pinned release

Each submission pins its own tag in `image:`, so older methods keep running against the release they
were scored on. Build a new tag when a submission needs a QSMxT version that is not published yet —
`--build-arg QSMXT_VERSION=vX.Y.Z` overrides the default above — and push it before the submission
merges, since the run phase has no network.
