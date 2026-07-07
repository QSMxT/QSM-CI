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

## 2. Package your algorithm as a container

Put your reconstruction in any container image, any language. It must read the consumed artifacts
from `/input` and write the produced artifact(s) to `/output`. No network at run time — bake in all
dependencies and weights. Push the image somewhere public (GHCR, Docker Hub, quay.io).

A minimal Python `dipole` example image:

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir nibabel numpy scipy
COPY recon.py run.sh /opt/algo/
WORKDIR /opt/algo
```

where `run.sh` runs `python recon.py /input /output` and `recon.py` reads
`/input/localfield.nii.gz` (+ `mask.nii.gz`, `params.json`) and writes `/output/chimap.nii.gz`.
The in-repo reference submissions [`algorithms/tkd`](../algorithms/tkd),
[`algorithms/sharp`](../algorithms/sharp), and [`algorithms/matlab-tkd`](../algorithms/matlab-tkd)
(MATLAB via MATLAB Runtime — see [matlab.md](matlab.md)) are working templates to copy.

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
