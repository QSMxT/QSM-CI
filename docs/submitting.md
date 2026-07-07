# Submitting an algorithm to QSM-CI

A submission is one folder and a pull request. You bring a container image; QSM-CI runs and scores it.

## Quickstart — the `qsm-ci` CLI

The CLI scaffolds, tests, and submits — it builds and runs your container on a small public **dev
phantom** and scores it with the *exact* code the leaderboard uses, so your local numbers match.

```bash
pipx install git+https://github.com/astewartau/qsm-ci   # or: pip install qsm-ci

qsm-ci new                 # interactive scaffold -> algorithms/<slug>/ (or use the web wizard)
# ... edit your recon.py / recon.m / recon.rs / recon.jl ...
qsm-ci test <slug>         # build + run your container on the dev phantom, print your scores
qsm-ci submit <slug>       # commit on a branch and open a pull request

qsm-ci doctor              # check docker / gh / deps / dataset
```

`qsm-ci test` needs Docker (or `--runner local` to run `run.sh` on the host). Everything below is
the detail behind those commands — read on if you want to hand-build a submission.

## 1. Pick your stage

QSM is a pipeline: **field-mapping → background field removal (BFR) → dipole inversion**. You
implement one stage, or a span for methods that cross boundaries. See
[`../CONTRACT.md`](../CONTRACT.md) and [`../stages.yml`](../stages.yml).

| `stage:` | Consumes (in `/input`) | Produces (in `/output`) |
|---|---|---|
| `field-mapping` | `phase`, `magnitude`, `mask`, `params` | `totalfield` |
| `bfr` | `totalfield`, `mask`, `params` | `localfield` |
| `dipole` | `localfield`, `mask`, `params` | `chimap` |
| `unwrap+bfr` | `phase`, `magnitude`, `mask`, `params` | `localfield` |
| `bfr+dipole` | `totalfield`, `mask`, `params` | `chimap` |
| `end-to-end` | `phase`, `magnitude`, `mask`, `params` | `chimap` |

All fields and χ are **ppm**. Your stage is scored two ways: **isolated** (fed the ground-truth
input boundary) and **composed** (chained with other people's stages — e.g. every BFR × your
dipole).

## 2. Provide your code + an environment (you don't bake an image)

A submission is **your code plus an environment**. Your `run.sh` and scripts stay in the folder and
are **mounted** into the environment at `/algo` at run time — you don't build or push a per-submission
image with your code inside. Two ways to specify the environment (see [../CONTRACT.md](../CONTRACT.md)):

- **Point at a base image** — set `image:` to a container that already has what you need (the shared
  `py-ref` deps image, a Neurodesk MATLAB/Octave container, etc.). No build at all.
- **Add a `Dockerfile`** — start `FROM` any base and install/download dependencies (including
  toolboxes; the build phase has network). Do **not** `COPY` your code — it's mounted.

Your `run.sh` reads the consumed artifacts from `/input` and writes the produced artifact(s) to
`/output`. At run time there is **no network**, so anything your code needs must already be in the
environment.

Working templates to copy:
- Python `dipole`: [`algorithms/tkd`](../algorithms/tkd) — just `recon.py` + `run.sh`, `image:`
  pointing at the shared deps base. No Dockerfile.
- MATLAB-language via Octave: [`algorithms/octave-tkd`](../algorithms/octave-tkd) — `.m` files + a
  tiny `Dockerfile` that installs Octave (deps only). See [matlab.md](matlab.md).
- BFR: [`algorithms/sharp`](../algorithms/sharp).

## 3. Add your submission folder

Copy a reference folder to `algorithms/<your-slug>/` and edit:

- **`algorithm.yml`** — one manifest: name, authors, DOI, license, your `stage:`, your `image:`,
  the `run:` command, and any `parameters:`.
- Bake your code into the image (or, like the reference algos, keep `recon.*` + `run.sh` in the
  folder and a small `Dockerfile` that copies them onto a base image).

## 4. Test locally

```bash
qsm-ci test <your-slug>          # fetches the dev phantom, builds+runs your container, scores it
qsm-ci test <your-slug> --runner local   # run run.sh on the host instead of in Docker
```

Under the hood this is one iteration of the isolated evaluation: your stage is fed the dev phantom's
ground-truth boundary, run with **no network**, and its output scored by `qsm_ci.qsm_eval` — the same
scorer the CI uses. To drive the whole isolated + composed matrix at once (from a repo checkout):

```bash
python scripts/pipeline.py --dataset data/sim/dev --mode both --runner docker
```

## 5. Open a pull request

```bash
qsm-ci submit <your-slug>        # commit on a branch + open the PR (uses gh if present)
```

QSM-CI runs your stage **isolated** on the held-out ground-truth boundary (no network, time-limited),
scores it, and comments the metrics on your PR. The full **composition matrix** (your stage against
everyone else's) refreshes on the [leaderboard](https://astewartau.github.io/qsm-ci/). The
authoritative score always comes from CI — it holds the real, hidden scoring phantom — but
`qsm-ci test` on the open dev phantom confirms your plumbing and shows roughly where you'd land.
