# Submitting an algorithm to QSM-CI

A submission is one folder and a pull request. You bring a container image; QSM-CI runs and scores it.

## Quickstart — the `qsm-ci` CLI

The CLI scaffolds a submission, runs one stage on **files you provide**, and (if you hand it a
ground truth) scores it with the *exact* code the leaderboard uses, so your numbers match. It does
**not** parse BIDS — bring the specific NIfTIs a stage consumes. (BIDS parsing is qsmxt's job, and
QSM-CI only does it server-side to build the challenge dataset.)

```bash
pipx install git+https://github.com/astewartau/qsm-ci   # or: pip install qsm-ci

qsm-ci new                 # interactive scaffold -> algorithms/<slug>/ (or use the web wizard)
# ... edit your recon.py / recon.m / recon.rs / recon.jl ...

# run one stage on explicit inputs; the --<artifact> flags depend on the stage:
qsm-ci run my-method --localfield lf.nii.gz --mask mask.nii.gz --params params.json
#   add --truth chi.nii.gz [--seg dseg.nii.gz] to score the output
qsm-ci run my-method --help    # show exactly which files this submission's stage needs

qsm-ci submit my-method    # commit on a branch and open a pull request
qsm-ci doctor              # check docker / gh / deps
```

Need a dataset to test against? Generate one with **qsm-forward** (it forward-simulates a phantom,
so it comes *with* ground truth) and pass the files to `qsm-ci run`:

```bash
qsm-forward simple bids/            # permission-free cylinder phantom (or: qsm-forward head <maps> bids/)
# the fields/χ/mask/dseg land under bids/derivatives/qsm-forward/… — feed them to qsm-ci run
```

`qsm-ci run` uses **Docker** by default; pick a container engine with `--runner`
(`docker` · `podman` · `apptainer`), or `--runner local` to run `run.sh` on the host. Everything below is the
detail behind these commands — read on if you want to hand-build a submission.

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
| `bfr+dipole` | `totalfield`, `mask`, `params`, `magnitude` | `chimap` |
| `end-to-end` | `phase`, `magnitude`, `mask`, `params` | `chimap` |

All fields and χ are **ppm**. Your stage is scored two ways: **isolated** (fed the ground-truth
input boundary) and **composed** (chained with other people's stages — e.g. every BFR × your
dipole).

## 2. Provide your code + an environment (you don't bake an image)

A submission is **your code plus an environment**. Your `run.sh` and scripts stay in the folder and
are **mounted** into the environment at `/algo` at run time — you don't build or push a per-submission
image with your code inside. Two ways to specify the environment (see [../CONTRACT.md](../CONTRACT.md)):

- **Point at a base image** — set `image:` to a container that already has what you need (the shared
  `py-ref` deps image, a Neurodesk MATLAB Runtime container, etc.). No build at all.
- **Add a `Dockerfile`** — start `FROM` any base and install/download dependencies (including
  toolboxes; the build phase has network). Do **not** `COPY` your code — it's mounted.

Your `run.sh` reads the consumed artifacts from `/input` and writes the produced artifact(s) to
`/output`. At run time there is **no network**, so anything your code needs must already be in the
environment.

Working templates to copy:
- Python `dipole`: [`algorithms/tkd`](../algorithms/tkd) — just `recon.py` + `run.sh`, `image:`
  pointing at the shared deps base. No Dockerfile.
- MATLAB compiled to the free MATLAB Runtime: [`algorithms/matlab-tkd`](../algorithms/matlab-tkd) —
  `recon.m` + a `matlab:` block; compiled once (license at build time only). See [matlab.md](matlab.md).
- BFR: [`algorithms/sharp`](../algorithms/sharp).

## 3. Add your submission folder

Copy a reference folder to `algorithms/<your-slug>/` and edit:

- **`algorithm.yml`** — one manifest: name, authors, DOI, license, your `stage:`, your `image:`,
  the `run:` command, and any `parameters:`.
- Bake your code into the image (or, like the reference algos, keep `recon.*` + `run.sh` in the
  folder and a small `Dockerfile` that copies them onto a base image).

## 4. Run it locally

```bash
# flags depend on the stage — see: qsm-ci run <your-slug> --help
qsm-ci run <your-slug> --localfield lf.nii.gz --mask mask.nii.gz --params params.json \
  --truth chi.nii.gz --seg dseg.nii.gz         # --truth/--seg optional; omit to just run
qsm-ci run <your-slug> ... --runner podman     # or apptainer (docker:// images); local = run on host
```

Your stage runs with **no network**, writes its produced artifact, and — if you passed `--truth` —
is scored by `qsm_ci.qsm_eval`, the same scorer the CI uses. Generate a phantom with `qsm-forward`
(see the Quickstart) if you need inputs with ground truth. To drive the whole isolated + composed
matrix across all submissions at once (from a repo checkout):

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
authoritative score always comes from CI — it holds the real, hidden scoring phantom — but running
locally against your own phantom confirms your plumbing and shows roughly where you'd land.
