# Submitting an algorithm to QSM-CI

A submission is one folder and a pull request. You bring a container image; QSM-CI runs and scores it.

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

- **`metadata.yml`** — name, authors, paper DOI, license, and `stage:`.
- **`algorithm.yml`** — `contract: v2`, your `stage:`, your `image:`, and the `run:` command.
- Bake your code into the image (or, like the reference algos, keep `recon.*` + `run.sh` in the
  folder and a small `Dockerfile` that copies them onto a base image).

## 4. Open a pull request

Open a PR adding only your `algorithms/<your-slug>/` folder. QSM-CI will pull your image, run your
stage **isolated** on the ground-truth boundary (no network, time-limited), score the output, and
comment the metrics on your PR. The full **composition matrix** (your stage against everyone else's)
refreshes on the [leaderboard](https://astewartau.github.io/qsm-ci/).

## 5. Test locally before submitting

Dry-run the contract with the dev phantom (see [`../data/sim/README.md`](../data/sim/README.md) to
generate it), then run the local pipeline:

```bash
# your container, no network, isolated boundary as input
docker run --rm --network none \
  -v "$PWD/data/sim/dev/groundtruth:/input:ro" -v "$PWD/out:/output" \
  <your-image> bash run.sh
ls out/chimap.nii.gz

# or drive the whole isolated+composed evaluation locally (no Docker)
python scripts/pipeline.py --dataset data/sim/dev --mode both
```

The authoritative score always comes from CI (it holds the real, hidden ground truth), but the local
run confirms your plumbing and lets you see where you'd land.
