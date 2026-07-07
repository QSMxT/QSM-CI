# QSMxT engine image

Shared environment for the QSMxT-backed submissions (the QSM.rs algorithms). Pinned to an official
QSMxT release (`v9.1.0`, which includes the MEDI ppm↔radians fix) plus `jq` (used by each `run.sh`
to read `B0_dir` from `params.json`). Submissions mount their `run.sh` at `/algo` and call
`qsmxt bgremove <algo>` / `qsmxt invert <algo>`.

    docker build -t ghcr.io/astewartau/qsm-ci/qsmxt:v9.2.0 .   # downloads the pinned release
