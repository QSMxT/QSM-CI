# Submitting an algorithm to QSM-CI

A submission is one folder and a pull request. You bring a container image; QSM-CI does the rest.

## 1. Package your algorithm as a container

Put your reconstruction in any container image, in any language. The only requirement is that it
honors [the contract](../CONTRACT.md): read `/input`, write `/output/chimap.nii.gz` (ppm).

- Bake in all dependencies, weights, and models — **there is no network at run time**.
- Push the image somewhere public: GHCR, Docker Hub, or quay.io.
- MATLAB users: see [matlab.md](matlab.md) for a no-license template using the Neurodesk MATLAB
  Runtime image.

A minimal Python example image:

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir nibabel numpy scipy
COPY recon.py /opt/recon.py
COPY run.sh /opt/run.sh
WORKDIR /opt
```

where `run.sh` calls `python recon.py /input /output` and `recon.py` writes
`/output/chimap.nii.gz`.

## 2. Add your submission folder

Copy [`algorithms/example-tkd/`](../algorithms/example-tkd/) to `algorithms/<your-slug>/` and edit:

- **`metadata.yml`** — name, authors, paper DOI, license, tracks.
- **`algorithm.yml`** — your `image:` reference and the `run:` command. Keep `contract: v1`.
- **`run.sh`** — the command(s) inside your container that produce the output. (You can also embed
  this in your image and just point `run:` at it.)

## 3. Open a pull request

Push a branch and open a PR that adds only your `algorithms/<your-slug>/` folder. When it's merged
(or on demand), QSM-CI will:

1. Pull your image.
2. Run it on the challenge inputs, with no network, under a time limit.
3. Score `chimap.nii.gz` against the held-out ground truth with `qsm-eval`.
4. Post the metrics (and slice figures) back on the PR, and add your run to the
   [leaderboard](https://astewartau.github.io/qsm-ci/).

## 4. Check your result

Your reconstruction shows up on the leaderboard with an interactive 3D viewer (reconstruction,
ground truth, and error). Sort by any metric to see where you land.

## Testing locally before you submit

You can dry-run the contract yourself:

```bash
docker run --rm --network none \
  -v "$PWD/data/sim/public:/input:ro" \
  -v "$PWD/out:/output" \
  <your-image> bash run.sh
ls out/chimap.nii.gz   # should exist
```

Scoring needs the held-out ground truth, so the authoritative score always comes from CI — but the
dry-run confirms your plumbing works.
