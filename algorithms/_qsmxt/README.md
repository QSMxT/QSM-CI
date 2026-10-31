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

## With the deep-learning weights (`models.Dockerfile`)

The QSM.rs ports of the deep-learning models (`xqsm-qsmrs`, `hd-bet-qsmrs`, ...) need qsmxt's ONNX
weights, which qsmxt would download on first use; the run has no network. `models.Dockerfile` adds
them to a qsmxt image at `/opt/qsm-models` (`$QSM_MODEL_DIR`), fetched from `qsmxt/qsm-onnx-weights`
at a pinned commit and checked against `models.sha256` (QSM.rs's registry hashes):

    docker build -f models.Dockerfile -t ghcr.io/astewartau/qsm-ci/qsmxt:v10.0.0-models .
    docker build -f models.Dockerfile --build-arg BASE=<any qsmxt image> -t <tag> .   # e.g. a source build

`v10.0.0-models` is `sha256:4327e61dec101830cd9620049ea216939ea9bbb235e26688d198d90481c6f7df`.
