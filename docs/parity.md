# Port parity

Some algorithms have two implementations here: the authors' original and the QSM.rs port, with the
same `algorithm:` in `algorithm.yml` (e.g. `qsmart-matlab` and `qsmart-qsmrs`). The `parity`
workflow runs both on the same dataset and checks that they still agree as well as they did when the
limits were set. It is the QSM.rs release gate (see the last section).

## Running it

Actions → **parity** → *Run workflow*, or:

```bash
gh workflow run parity.yml -f algorithm=qsmart                         # every dataset the pair has limits for
gh workflow run parity.yml -f algorithm=enabled -f dataset=configured  # every enabled pair and dataset
gh workflow run parity.yml -f algorithm=qsmart -f qsmrs_ref=<sha>      # against a QSM.rs commit
```

| Input | Meaning |
|---|---|
| `algorithm` | a pair in `parity/thresholds.yml`, or `enabled` for every enabled pair |
| `dataset` | a `scripts/datasets.json` key, or `configured` for every dataset the pair has limits for |
| `baseline` | `true` measures and prints suggested limits, and never fails |
| `qsmrs_ref` | a QSM.rs branch, tag or SHA: QSMxT (`qsmxt_ref`, default `main`) is built with its `qsm-core` pin moved to that commit |
| `qsmxt_ref` | a QSMxT ref, built with the QSM.rs it pins |
| `qsmxt_image` | a prebuilt qsmxt image (overrides both refs) |

With none of the last three, every QSM.rs step runs the qsmxt image its `algorithm.yml` pins (today
v10.0.0). With a ref, a `qsmxt` job builds the binary the way QSMxT's release does (`cargo build
--release`, `x86_64-unknown-linux-musl`, default features; the Rust build is cached), and each
parity job puts it in a debian-slim image like `algorithms/_qsmxt` (`parity/qsmxt.Dockerfile`). Every
step with `source: qsmrs` then runs that image instead of the pinned one, through `qsm-ci run
--image`; `algorithm.yml` is not edited. The report names the build (QSMxT and qsm-core commits) and,
for each step, the image, its ID and `qsmxt --version`.

Each job runs the reference and then the candidate through `qsm-ci run`, compares them inside the
dataset mask, and writes a report to the job summary and the `parity-<pair>-<dataset>` artifact (with
both outputs and their intermediates). The job fails when a limit is exceeded. Locally, with
Docker or Podman and the dataset fetched:

```bash
python scripts/parity.py pairs                       # configured pairs, and pairs not configured
python scripts/parity.py run     --algorithm qsmart --phantom sim --dataset data/sim/scoring --work .parity \
    [--runner podman] [--qsmrs-image qsmxt-under-test:local]
python scripts/parity.py compare --algorithm qsmart --phantom sim --dataset data/sim/scoring --work .parity
```

## Pairs

A pair is an original (`reference`) and a QSM.rs port (`candidate`, `source: qsmrs`) of the same
`algorithm:`. `parity/thresholds.yml` always names the reference. That is the whole rule: when an
algorithm has more than one original (an STI Suite one and a Julia `-qsmjl` one, say), each original
that is checked gets its own entry, keyed by the algorithm for the first and by the original's slug
for the others. A pair whose two slugs are not an original and a port of one algorithm is refused
before anything runs. `parity.py pairs` also lists the algorithms that have an original and a port
but no pair yet.

A pair is `enabled` once its original is verified (for MATLAB, the container's fidelity check) and
it has limits. Only enabled pairs run in the release gate.

## What is compared

- **The final artifact** (χ): NRMSE (‖candidate − reference‖ / ‖reference‖, %), correlation, and the
  maximum and 99th-percentile |Δ| (ppm), inside the mask.
- **Intermediates**, for every name both sides write (CONTRACT.md, "Intermediates"). Binary maps
  are compared by Dice. An intermediate with no limits is reported but does not fail the job; one
  that only one side writes is listed. A prefix step's output (e.g. a field-mapping `totalfield`)
  counts as an intermediate of that side.
- `reference_names` / `candidate_names` map a side's own intermediate names onto the compared ones,
  for an implementation that predates the convention (the compiled QSMART writes `tfs`, `R_0`,
  `vasc_only`, `lfs1`, …).

## Isolating a step: `feed`

`feed: {totalfield: totalfield}` gives the candidate the reference's own `totalfield` intermediate
in place of the dataset's, so the port starts from exactly what the original computed and only the
steps after it are compared. The QSMART pair uses this: `qsmart-qsmrs` is a `bfr+dipole` method, so
it is fed the total field from `qsmart-matlab`'s Laplacian unwrapping and echo fit, and the
comparison covers vasculature detection, both SDF stages, both iLSQR inversions and the offset
adjustment. A feed whose intermediate the reference did not write is an error, not a fallback.

`candidate_prefix: [laplacian-qsmrs]` instead runs a field-mapping step first, for a pair whose
port needs a boundary the dataset does not have and the original does not write.

## Limits

`parity/thresholds.yml` holds the limits per pair and dataset. They are the agreement measured with
the current QSMxT main build, plus a margin (`derive_limits`: NRMSE +10 % +0.5 pp, correlation
−0.01, |Δ| +25 %, Dice −0.01), and the file records the runs and images they came from. A limit is
never loosened to hide a gap. To set or reset them, dispatch with `baseline=true`: the report prints
limits derived from what it measured, ready to paste. Re-baseline when either side changes on
purpose (a new original image, or a QSM.rs change that is meant to move the result), or when
`feed:` or a `*_prefix:` changes what is measured, and say why in the PR.

With no ref, the QSM.rs steps run the pinned qsmxt v10.0.0 (QSM.rs v0.39.0), which predates the
QSMART fixes the limits were measured with, so the QSMART pair fails there (sim NRMSE 65.9 %, KKI
133.8 %). It passes once a QSMxT release with those fixes is pinned.

## Before a QSM.rs release

Dispatch the workflow against the release candidate and wait for it:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI \
  -f algorithm=enabled -f dataset=configured -f qsmrs_ref=<release candidate SHA>
gh run watch -R QSMxT/QSM-CI --exit-status "$(gh run list -R QSMxT/QSM-CI -w parity -L 1 \
  --json databaseId -q '.[0].databaseId')"
```

`qsmxt_ref` defaults to QSMxT `main`. If the release changes an API that QSMxT main does not build
against yet, pass the QSMxT branch that moves to it (`-f qsmxt_ref=<branch>`). A failing pair blocks
the release until the port is fixed, or until the change is shown to be intended and the pair is
re-baselined in a QSM-CI PR.
