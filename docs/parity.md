# Port parity

Some algorithms have two implementations here: the authors' original and the QSM.rs port, with the
same `algorithm:` in `algorithm.yml` (e.g. `qsmart-matlab` and `qsmart-qsmrs`). The `parity`
workflow runs both on the same dataset and checks that they still agree as well as they did when the
limits were set. It is the QSM.rs release gate (see the last section).

Where each pair stands (last check, QSM.rs, result, stale or not): [parity/STATUS.md](../parity/STATUS.md),
and the **Parity** page on the site.

## Running it

From the Actions tab: **parity** → *Run workflow* → fill in the fields below. From a shell:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=qsmart                 # one pair, every dataset it has
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=qsmart,ilsqr,tkd       # several pairs
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=enabled                # every enabled pair (the release gate)
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=all-configured -f baseline=true   # every pair, enabled or not
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=tkd,tsvd -f dataset=sim -f qsmrs_ref=main
```

| Input | Meaning |
|---|---|
| `algorithm` | pairs in `parity/thresholds.yml`, comma-separated (`qsmart,ilsqr,tkd`), and/or `enabled` (every enabled pair) or `all-configured` (every pair with a dataset, enabled or not). Default `enabled`. |
| `dataset` | `scripts/datasets.json` keys, comma-separated, or `configured` for every dataset each pair has an entry for |
| `baseline` | `true` measures and prints suggested limits, never fails, and records nothing |
| `qsmrs_ref` | a QSM.rs branch, tag or SHA: QSMxT (`qsmxt_ref`, default `main`) is built with its `qsm-core` pin moved to that commit |
| `qsmxt_ref` | a QSMxT ref, built with the QSM.rs it pins |
| `qsmxt_image` | a prebuilt qsmxt image (overrides both refs) |
| `record` | `true` records the results (see "Recorded results"); a run from `main` always does |

Every name is checked before any job starts: an unknown pair or dataset, or a pair that no longer
matches `algorithm.yml`, fails the `plan` job with the reason. A disabled pair runs when named; it
is only left out of `enabled`. Watch a run with `gh run watch -R QSMxT/QSM-CI --exit-status <id>`
(`gh run list -R QSMxT/QSM-CI -w parity -L 1` gives the id).

With none of the last three, every QSM.rs step runs the qsmxt image its `algorithm.yml` pins (today
v10.0.0). With a ref, a `qsmxt` job builds the binary the way QSMxT's release does (`cargo build
--release`, `x86_64-unknown-linux-musl`, default features; the Rust build is cached), and each
parity job puts it in a debian-slim image like `algorithms/_qsmxt` (`parity/qsmxt.Dockerfile`). Every
step with `source: qsmrs` then runs that image instead of the pinned one, through `qsm-ci run
--image`; `algorithm.yml` is not edited. The report names the build (QSMxT and qsm-core commits) and,
for each step, the image, its ID and `qsmxt --version`.

Each job runs the reference and then the candidate through `qsm-ci run`, compares them inside the
dataset mask, and writes a report to the job summary and the `parity-<key>-<pair>-<dataset>` artifact (`<key>` names the run's selection and QSM.rs build; with
both outputs and their intermediates). The job fails when a limit is exceeded. Locally, with
Docker or Podman and the dataset fetched:

```bash
python scripts/parity.py pairs                       # configured pairs, and pairs not configured
python scripts/parity.py pairs --matrix --algorithm qsmart,tkd   # the jobs a selection plans
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
it has limits. Only enabled pairs run in the release gate. A pair whose port does not match its
original yet stays disabled with `blocked_by: <issue>`: the status shows it as a **gap**, never as a
pass, and it gets no limits that would bless the gap.

Either side may be a method scoring skips:
- An original with `ci_skip` (e.g. `amp-pe`, `decompose-qsm`, retired from scoring) or
  `parity_only` (the Julia originals: references of a pair, never scored or shown on the site) runs
  when its pair does.
- A QSM.rs port with `ci_skip` because the qsmxt release its `algorithm.yml` pins lacks it (e.g.
  `star-qsmrs` before a release with `qsmxt invert star`) runs against a qsmxt build (`qsmrs_ref`,
  `qsmxt_ref` or `qsmxt_image`; locally `--qsmrs-image`), and is refused without one.

A method with `runner: self-hosted` (e.g. `decompose-qsm`) takes its pair's job to the self-hosted
runners, with that method's `timeout_minutes`.

### Matched settings

When the two implementations' defaults differ, `reference_set` / `candidate_set` (per pair, or per
dataset) are the `--set NAME=VALUE` overrides that make them compute the same thing: e.g. QSM.jl's
padding off (`pad: -1`) as in QSM.rs, or TGV.jl's α in rad units for the dataset's field strength
and first echo time. For a Julia original they are its README's "QSM.rs-matched" column. Only the
pair's own method gets them; prefix steps run with their defaults.

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
−0.01, |Δ| +25 % and at least 1e-6 ppm, Dice −0.01), and the file records the runs and images they came from. A limit is
never loosened to hide a gap. To set or reset them, dispatch with `baseline=true`: the report prints
limits derived from what it measured, ready to paste. Re-baseline when either side changes on
purpose (a new original image, or a QSM.rs change that is meant to move the result), or when
`feed:` or a `*_prefix:` changes what is measured, and say why in the PR.

With no ref, the QSM.rs steps run the pinned qsmxt v10.0.0 (QSM.rs v0.39.0), which predates the
QSMART fixes the limits were measured with, so the QSMART pair fails there (sim NRMSE 65.9 %, KKI
133.8 %). It passes once a QSMxT release with those fixes is pinned.

## Recorded results

Every run from `main`, and every run dispatched with `record=true`, commits one record per pair ×
dataset to [`parity/results.json`](../parity/results.json) (the `record` job, as `qsm-ci-bot`, the
way score.yml commits `results/index.json`). Baselines and runs from other branches record nothing.
A record holds:

- the date and the run's URL;
- the result (`pass`, `fail`, or `error` when the job ended before the comparison) and the metrics
  of every compared map, with the limits that failed;
- the QSM.rs commit and version the candidate ran (from its own `qsmxt --version`), the QSMxT
  commit (for a build), and the candidate image and its digest;
- the reference slug, image and digest;
- the thresholds version: a hash of what the pair measures and the limits it is held to on that
  dataset (`parity.py thresholds_version`).

Each pair × dataset keeps its 50 newest records. The same job regenerates
[`parity/STATUS.md`](../parity/STATUS.md) and `parity/status.json` (the site's Parity page).

## Staleness

`python scripts/parity.py status` says, for each enabled pair and dataset, whether its last
recorded check still stands. It is **stale** when any of these holds:

- **(a)** the reference image pinned in `algorithm.yml` is not the one last checked;
- **(b)** QSM.rs `main` has commits touching the pair's `qsmrs_paths` (in `thresholds.yml`) since the
  QSM.rs commit last checked (GitHub's compare API, at the time `status` runs);
- **(c)** the pair's settings or limits for that dataset changed since (the thresholds version);
- **(d)** it was never checked, or last checked more than `stale_after_days` ago (`thresholds.yml`,
  default 90);
- **(e)** the last check failed, or ended without a result.

```bash
python scripts/parity.py status                              # the table, to stdout
python scripts/parity.py status --offline                    # without rule (b): no GitHub calls
python scripts/parity.py status --json parity/status.json --markdown parity/STATUS.md --issue issue.md
```

The **parity-status** workflow runs it every Monday (and on demand), commits the regenerated
status, and keeps one tracking issue, *Port parity: stale checks*: created the first time a pair is
stale, edited on every run after, closed when nothing is stale, and reopened (never duplicated)
next time. It lists each stale pair, why, and the command that refreshes it, e.g.

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=ilsqr,tkd -f dataset=configured -f qsmrs_ref=main
```

Dispatched on `main` (the default), the refresh records its results, which clears the staleness
once it passes. With the repository variable `PARITY_AUTO_REFRESH=true` (unset by default) the
workflow dispatches that refresh itself.

## Before a QSM.rs release

Dispatch the workflow against the release candidate and wait for it:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI \
  -f algorithm=enabled -f dataset=configured -f qsmrs_ref=<release candidate SHA>
gh run watch -R QSMxT/QSM-CI --exit-status "$(gh run list -R QSMxT/QSM-CI -w parity -L 1 \
  --json databaseId -q '.[0].databaseId')"
```

The run's summary (the `report` job) has one row per pair × dataset, then the answer the release
needs: which pairs passed against exactly the QSM.rs commit under test, which failed, and any
enabled pair the run did not check. "Release gate: passed" means every enabled pair passed on
every configured dataset against that one commit. A dispatch from `main` also records the results,
so the status shows each pair checked against the release candidate.

`qsmxt_ref` defaults to QSMxT `main`. If the release changes an API that QSMxT main does not build
against yet, pass the QSMxT branch that moves to it (`-f qsmxt_ref=<branch>`). A failing pair blocks
the release until the port is fixed, or until the change is shown to be intended and the pair is
re-baselined in a QSM-CI PR.
