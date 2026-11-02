# Port parity

Some algorithms have two implementations here: the authors' original and the QSM.rs port, with the
same `algorithm:` in `algorithm.yml` (e.g. `qsmart-matlab` and `qsmart-qsmrs`). The `parity`
workflow runs both on the same dataset and checks that they still agree as well as they did when the
limits were set. It is the QSM.rs release gate (see the last section).

Where each pair stands (last check, QSMxT and QSM.rs, result, stale or not), per track:
[parity/STATUS.md](../parity/STATUS.md), and the **Parity** page on the site.

## Tracks

Every recorded check belongs to one of two tracks.

| | **Released** (shown first) | **Development** |
|---|---|---|
| QSM.rs side | the latest QSMxT release: the `x86_64-unknown-linux-musl` binary that release ships (checked against its `SHA256SUMS`), with the QSM.rs it pins | QSMxT `main` built with its `qsm-core` pin moved to QSM.rs `main` (or a QSM.rs release candidate: the release gate) |
| Dispatch | `-f qsmxt_release=<tag>` (or `latest`) | `-f qsmrs_ref=main` (or `qsmxt_ref`, `qsmxt_image`) |
| A record names | the release tag, its QSMxT commit, and the QSM.rs version and commit its binary reports | the QSMxT and QSM.rs commits |
| Runs when | QSMxT publishes a release, or a pair's reference image or settings change (`parity-release.yml`, daily) | on demand, when a check is stale (QSM.rs or QSMxT changed the pair's paths; "Staleness") |
| History | one record per pair × dataset × release, for every release | the 50 newest records per pair × dataset |
| Badges | `parity/badges/<pair>.json` (the QSM.rs README) and `parity/badges/release/<tag>/<pair>.json` | `parity/badges/dev/<pair>.json` |

A release never changes, so on the released track a failure is that release's result, not
something to rerun. A pair whose port the release does not have is recorded as **not in
`<tag>`** (result `unavailable`, a grey badge), not as a failure: before the original runs, the job
asks the release's qsmxt for each subcommand the port's `run.sh` calls (`qsmxt invert star
--help`); and if the run then fails because qsmxt refuses the command line (clap's `unrecognized
subcommand`, `unexpected argument` or `invalid value`: an option or value added after the release,
such as `--variant qsmjl`), that is recorded the same way. So is clap's `the following required
arguments were not provided`: the release's command is an earlier port that needs an input the
current one does not take (qsmxt v10.0.0's paper-based `separate chi-sep-ilsqr --magnitude`, not the
toolbox port the pair checks). Any other failure is a failure.

One exception keeps a number where the port exists but a pair's extra input does not: when qsmxt
refuses the command line and the pair feeds the candidate an **optional** input (a `feed:` artifact
the candidate's `algorithm.yml` lists under `optional_inputs:`, e.g. QSMART's `reliability`, which
qsmxt v10.0.0 has no `--reliability` for), the job reruns only the candidate without those feeds
(`parity.py run --candidate-only --drop-optional-feeds`) and compares that. The record says
`dropped_feeds: [reliability]`, and the badge says so too: `65.9 % · v10.0.0 · no reliability`.
Required feeds (e.g. a fed total field) are never dropped.

If qsmxt still refuses the command line, the same applies to the pair's `candidate_set` settings
(the matched settings, e.g. QSMART's `offset_grid: qsmart-reference`, which v10.0.0 has no
`--qsmart-offset-grid` for): `parity.py rejected-setting` names the setting behind each refusal (the
key whose hyphenated name the refused option contains), and the candidate is rerun without it, one
more setting per refusal (`--drop-setting KEY`). The record says `dropped_settings: [offset_grid]`
and the badge `… · v10.0.0 · no reliability, no offset_grid`. The reference is never rerun, and
keeps its own settings. A refusal no feed or setting explains (a missing subcommand) is "not in".

Records from before the tracks (the runs of 30 and 31 October 2026) were all QSMxT `main` builds
with qsm-core at QSM.rs `main`, and are labelled `dev`.

## Running it

From the Actions tab: **parity** → *Run workflow* → fill in the fields below. From a shell:

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=qsmart                 # one pair, every dataset it has
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=qsmart,ilsqr,tkd       # several pairs
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=enabled                # every enabled pair (the release gate)
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=all-configured -f baseline=true   # every pair, enabled or not
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=tkd,tsvd -f dataset=sim -f qsmrs_ref=main
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=enabled -f qsmxt_release=latest   # the released track
```

| Input | Meaning |
|---|---|
| `algorithm` | pairs in `parity/thresholds.yml`, comma-separated (`qsmart,ilsqr,tkd`), and/or `enabled` (every enabled pair) or `all-configured` (every pair with a dataset, enabled or not). Default `enabled`. |
| `dataset` | `scripts/datasets.json` keys, comma-separated, or `configured` for every dataset each pair has an entry for |
| `baseline` | `true` measures and prints suggested limits, never fails, and records nothing |
| `qsmxt_release` | released track: a QSMxT release tag, or `latest`. Not combined with the three below |
| `qsmrs_ref` | a QSM.rs branch, tag or SHA: QSMxT (`qsmxt_ref`, default `main`) is built with its `qsm-core` pin moved to that commit |
| `qsmxt_ref` | a QSMxT ref, built with the QSM.rs it pins |
| `qsmxt_image` | a prebuilt qsmxt image (overrides both refs) |
| `record` | `true` records the results (see "Recorded results"); a run from `main` always does, except a run of the pinned images (no track) |

Every name is checked before any job starts: an unknown pair or dataset, or a pair that no longer
matches `algorithm.yml`, fails the `plan` job with the reason. A disabled pair runs when named; it
is only left out of `enabled`. Watch a run with `gh run watch -R QSMxT/QSM-CI --exit-status <id>`
(`gh run list -R QSMxT/QSM-CI -w parity -L 1` gives the id).

With none of `qsmxt_release`, `qsmrs_ref`, `qsmxt_ref` and `qsmxt_image`, every QSM.rs step runs the
qsmxt image its `algorithm.yml` pins (today v10.0.0), and nothing is recorded: use `qsmxt_release`
for a release. With `qsmxt_release`, the `qsmxt` job downloads that release's musl binary instead
of building one. With a ref, a `qsmxt` job builds the binary the way QSMxT's release does (`cargo build
--release`, `x86_64-unknown-linux-musl`, default features; the Rust build is cached), and each
parity job puts it in a debian-slim image like `algorithms/_qsmxt` (`parity/qsmxt.Dockerfile`). Every
step with `source: qsmrs` then runs that image instead of the pinned one, through `qsm-ci run
--image`; `algorithm.yml` is not edited. The report names the build (QSMxT and qsm-core commits) and,
for each step, the image, its ID and `qsmxt --version`.

Each job runs the reference and then the candidate through `qsm-ci run`, compares them inside the
dataset mask, and writes a report to the job summary and the `parity-<key>-<pair>-<dataset>`
artifact, with both outputs and their intermediates (`<key>` stands for the run's selection and
QSM.rs build, so several calls in one run stay apart). The job fails when a limit is exceeded. Locally, with
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

A deep-learning pair (`qsmrs_models: true`) needs the ONNX weights on the QSM.rs side. The pinned
`qsmxt:v10.0.0-models-2` image has them; a qsmxt built from source does not, and a run has no
network, so the workflow layers them onto the build with `algorithms/_qsmxt/models.Dockerfile`.

### Matched settings

When the two implementations' defaults differ, `reference_set` / `candidate_set` (per pair, or per
dataset) are the `--set NAME=VALUE` overrides that make them compute the same thing: e.g. STI
Suite's V-SHARP radii for QSM.jl's `vsharp` (`reference_set`), or QSM.jl's iSMV, which QSM.rs keeps
as an option next to its default (`candidate_set: {variant: qsmjl}`, passed on by the port's
`run.sh`). For a Julia original they are its README's "QSM.rs-matched" column. Only the pair's own
method gets them; prefix steps run with their defaults.

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

A feed may also name an optional input that no dataset ships, one the candidate's `algorithm.yml`
opts into with `optional_inputs:` (CONTRACT.md, "Artifacts"). The QSMART pair feeds
`reliability: reliability` as well: the original's own reliability map R₀ from its echo fit, which
`qsmart-qsmrs` passes on as `qsmxt qsmart --reliability`, so both sides reconstruct over the same
voxels. Scoring never mounts it, so the scored `qsmart-qsmrs` runs without one, as before.

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

Limits are measured on the development track. A release older than the fixes they were measured
with fails them, which is what the released track should show: QSMxT v10.0.0 (QSM.rs v0.39.0)
predates the QSMART fixes (sim NRMSE 65.9 %, KKI 133.8 %) and most ports' parity fixes.

## Recorded results

Every run from `main`, and every run dispatched with `record=true`, unless it was cancelled, commits one record per pair ×
dataset to [`parity/results.json`](../parity/results.json) (the `record` job, as `qsm-ci-bot`, the
way score.yml commits `results/index.json`). Baselines, runs from other branches and runs of the
pinned images record nothing. A record holds:

- its `track` (`released` or `dev`) and, on the released track, the `release` tag;
- the date and the run's URL;
- the result (`pass`, `fail`, `unavailable` when the release has no such command or option, or
  `error` when the job ended before the comparison) and the metrics of every compared map, with
  the limits that failed;
- the QSM.rs commit and version the candidate ran (from its own `qsmxt --version`), the QSMxT
  commit (for a build), and the candidate image and its digest;
- the reference slug, image and digest;
- the thresholds version: a hash of what the pair measures and the limits it is held to on that
  dataset (`parity.py thresholds_version`).

On the development track each pair × dataset keeps its 50 newest records; on the released track
each pair × dataset keeps one record per release (a rerun for a changed reference replaces that
release's earlier one), for every release. The same job regenerates
[`parity/STATUS.md`](../parity/STATUS.md) and `parity/status.json` (the site's Parity page).

## Staleness

`python scripts/parity.py status` says, for each enabled pair and dataset and each track, whether
its last recorded check still stands.

On the **released** track only the latest QSMxT release counts (GitHub's latest release; offline,
`--latest-release` or the newest release recorded). A pair × dataset is flagged when it has no run
against that release, when the reference image or the pair's settings or limits changed since that
run (both rerun automatically, below), or when that run ended without a result (flagged for a person:
an error that repeats is not rerun on its own). A failure or a "not in" is the release's result.

On the **development** track a check is **stale** when any of these holds:

- **(a)** the reference image pinned in `algorithm.yml` is not the one last checked;
- **(b)** QSM.rs `main` has commits touching the pair's `qsmrs_paths`, or QSM.rs's `Cargo.lock`
  (`qsmrs_shared_paths`, every pair), since the QSM.rs commit last checked (GitHub's compare API, at
  the time `status` runs);
- **(c)** the pair's settings or limits for that dataset changed since (the thresholds version);
- **(d)** it was never checked;
- **(e)** the last check failed, or ended without a result;
- **(f)** QSMxT `main` has commits touching the pair's `qsmxt_paths` (the CLI and engine files that
  wire the step its `run.sh` calls), or QSMxT's `Cargo.lock` (`qsmxt_shared_paths`, every pair),
  since the QSMxT commit last checked: the build's commit, or for a pinned image the release tag
  its `qsmxt --version` names. `Cargo.lock` counts on both sides because the qsmxt binary takes its
  dependency versions (rustfft and the rest) from QSMxT's lockfile, not QSM.rs's.

A check does not expire with age: it stands until one of these changes, and a QSM.rs release runs
every enabled pair anyway (below).

`qsmrs_paths` lists the port's own modules, the `src/pipeline/` files QSMxT calls it through, and
every module those import, followed through shared code (`fft.rs`, `grid.rs`, `kernels/`,
`solvers/`, `utils/`, …) but not into another algorithm's module that shared code also serves.
`thresholds.yml` has the exact rule; recheck a pair's list when its port's imports change.

```bash
python scripts/parity.py status                              # the tables, to stdout
python scripts/parity.py status --offline                    # without rules (b) and (f): no GitHub calls
python scripts/parity.py status --offline --latest-release v10.0.0
python scripts/parity.py released-plan                       # what parity-release.yml would dispatch
python scripts/parity.py status --json parity/status.json --markdown parity/STATUS.md --issue issue.md \
    [--badges parity-badges/]
```

The **parity-status** workflow runs it every Monday (and on demand), commits the regenerated
status, and keeps one tracking issue, *Port parity: stale checks*, with a section per track:
created the first time a pair is flagged, edited on every run after, closed when nothing is, and
reopened (never duplicated) next time. It lists each flagged pair, why, and the command that
refreshes it, e.g.

```bash
gh workflow run parity.yml -R QSMxT/QSM-CI -f algorithm=ilsqr,tkd -f dataset=configured -f qsmrs_ref=main
```

Dispatched on `main` (the default), the refresh records its results, which clears the staleness
once it passes. With the repository variable `PARITY_AUTO_REFRESH=true` (unset by default) the
workflow dispatches the development refresh itself.

The **parity-release** workflow runs when QSMxT's release workflow sends a `repository_dispatch` of
type `qsmxt-release` (QSMxT/QSMxT#470, once QSMxT has its `QSM_CI_DISPATCH_TOKEN` secret), daily as
a fallback, and on demand. `parity.py released-plan`
compares GitHub's latest QSMxT release with `parity/results.json`: for a release with no records it
dispatches every enabled pair (`-f qsmxt_release=<tag> -f algorithm=enabled`); for the recorded
latest release, only the pairs whose reference image or settings changed since, or that never ran
on one of their datasets. It skips the dispatch while a released run for that tag is queued or
running (parity.yml's run name says `released <tag>`; `parity.py released-busy`), but not for one
that is cancelled or being cancelled. Every enabled pair with no released record for the release,
on any of its datasets, is due, whatever was dispatched before. A cancelled parity run records
nothing (its unfinished jobs would otherwise be recorded as errors and count as the release's run).

## Badges

Each pair, and each `no_original` entry, has [shields.io endpoint](https://shields.io/badges/endpoint-badge)
files, `{"schemaVersion": 1, "label": "parity", "message": …, "color": …}`, published with the site:

- `https://qsmxt.github.io/QSM-CI/parity/badges/<pair>.json`: the released track, the latest QSMxT
  release (what the QSM.rs README shows);
- `…/parity/badges/dev/<pair>.json`: the development track;
- `…/parity/badges/release/<tag>/<pair>.json`: each release's own result, for every recorded release.

The QSM.rs README's algorithm tables show one per port, linked to the pair's row on the Parity page
(`parity.html#pair-<pair>`; `parity.html?track=dev#pair-<pair>` for the development track):

```markdown
[![parity](https://img.shields.io/endpoint?url=https%3A%2F%2Fqsmxt.github.io%2FQSM-CI%2Fparity%2Fbadges%2Ftkd.json)](https://qsmxt.github.io/QSM-CI/parity.html#pair-tkd)
```

| Badge | Colour | When |
|---|---|---|
| `0.33 % · v10.0.0` / `identical · v10.0.0` | green | released: enabled, passed on every dataset against the release: the worst final-map NRMSE over the datasets |
| `failing · v10.0.0` | red | released: a dataset failed against the release, or its run ended without a result |
| `not in v10.0.0` | grey | released: the release has no such command or option |
| `stale · v10.0.0` | orange | released: the reference image or the pair's settings changed since the run |
| `not checked · v10.0.0` | grey | released: no run against the release yet |
| `0.33 % · 30 Oct` / `identical · 30 Oct` | green | dev: enabled, every dataset's last check stands: the worst final-map NRMSE over the datasets (`identical` when bit-identical), dated by the oldest check |
| `stale · 29 Oct` | orange | dev: enabled, and a check is stale (above); the date of the oldest last check |
| `failing · 28 Oct` | red | dev: enabled, and a last check failed or ended without a result |
| `gap · QSM.rs#323` | yellow | not enabled: `blocked_by` a known gap |
| `not yet checked` | grey | dev: enabled, never checked on any dataset |
| `not enabled` | grey | not enabled, no known gap |
| `no original` | grey | a `no_original` entry: no original code exists (QSMxT/QSM-CI#302) |

A per-release badge (`release/<tag>/`) is that release's recorded result alone (green, red or "not
in"), never stale. `not-checked.json` (and `dev/not-checked.json`) is a generic `not yet checked`
badge for a QSM.rs method with no pair here yet.
The pages workflow writes the files from the `parity/status.json` it deploys (`parity.py badges`),
so they always match the Parity page; `parity.py status --badges DIR` writes the same files locally.

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
