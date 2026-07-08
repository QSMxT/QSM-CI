# QSM-CI submission contract

Every submission is a container that implements one **stage** (or a **span** of stages) of the QSM
pipeline. It reads the artifacts that stage *consumes* from `/input` and writes the artifacts it
*produces* to `/output`. The registry of artifacts and stages is [`stages.yml`](stages.yml); this
document is the human contract.

## Why stages

QSM is a pipeline: **field-mapping → background field removal (BFR) → dipole inversion**. QSM-CI
lets you submit any single stage, or a span for methods that cross boundaries (e.g. single-step
methods that go straight from phase to susceptibility). This makes it possible to test one stage in
isolation *and* to test how different stages combine.

## Stages

| Stage | Consumes | Produces |
|-------|----------|----------|
| `field-mapping` | `phase`, `magnitude`, `mask`, `params` | `totalfield` |
| `bfr` | `totalfield`, `mask`, `params` | `localfield` |
| `dipole` | `localfield`, `mask`, `params` | `chimap` |

Spans (declare one of these if your method crosses stages):

| Span | Consumes | Produces | Example |
|------|----------|----------|---------|
| `unwrap+bfr` | `phase`, `magnitude`, `mask`, `params` | `localfield` | HARPERELLA |
| `bfr+dipole` | `totalfield`, `mask`, `params`, `magnitude` | `chimap` | QSMART, TGV |
| `end-to-end` | `phase`, `magnitude`, `mask`, `params` | `chimap` | TGV |

Your `algorithm.yml` sets `stage:` to one of these names. The platform mounts exactly the consumed
artifacts into `/input`, and expects exactly the produced artifacts in `/output`.

## Artifacts

| Artifact | File (`/input` or `/output`) | Units | Shape |
|----------|------------------------------|-------|-------|
| `phase` | `phase.nii.gz` | radians | 4D `x,y,z,echo` (or 3D if single-echo) |
| `magnitude` | `magnitude.nii.gz` | arbitrary | same shape as `phase` |
| `mask` | `mask.nii.gz` | binary uint8 | 3D |
| `params` | `params.json` | — | see below |
| `totalfield` | `totalfield.nii.gz` | **ppm** | 3D |
| `localfield` | `localfield.nii.gz` | **ppm** | 3D |
| `chimap` | `chimap.nii.gz` | **ppm** | 3D |

All field maps and the susceptibility map are in **ppm** (normalized by B0). Convert from Hz with
`ppm = Hz · 1e6 / (γ · B0)`, `γ = 42.576e6` Hz/T. All 3D artifacts share the grid, voxel size, and
affine of `mask.nii.gz`.

### `params.json`

```json
{
  "TE": [0.004, 0.012, 0.020, 0.028],
  "B0": 3.0,
  "B0_dir": [0.0, 0.0, 1.0],
  "voxel_size": [1.0, 1.0, 1.0]
}
```

| Field | Units | Meaning |
|-------|-------|---------|
| `TE` | seconds | echo time(s); length matches the phase echo dimension |
| `B0` | tesla | main field strength |
| `B0_dir` | unit vector | B0 direction in image coordinates |
| `voxel_size` | mm | voxel dimensions (x, y, z) |

### `config.json` (optional — parameter overrides)

A method may declare tunable `parameters:` in its `algorithm.yml` (name, default, description). When a
caller overrides one — `qsm-ci run <slug> --set threshold=0.2` — QSM-CI writes those values as a flat
JSON object to `/input/config.json`:

```json
{ "threshold": 0.2 }
```

Your `run.sh` (or recon code) reads it and applies the values, falling back to your own defaults for
anything absent. **`config.json` is optional**: when no overrides are given the file is absent and your
method runs at its defaults, so nothing breaks if you ignore it. Only keys you declared in
`parameters:` are ever written.

## Execution model — environment vs. code

Your submission is **code plus an environment**; you do not have to bake your code into a custom
image. Evaluation is two phases:

**1. Build/setup phase (network ON).** QSM-CI produces your environment image:
- If your folder has a `Dockerfile`, it is built — start `FROM` any base (a MATLAB Runtime/Python
  container, a Neurodesk image, …) and install or **download dependencies here** (this is where a
  MATLAB toolbox like SEPIA gets `git clone`d). Do **not** copy your algorithm code in; it is mounted.
- Otherwise your `image:` is used directly as the environment (a base that already has what you need).

**2. Run phase (network OFF).** QSM-CI runs your code in that environment:

```bash
docker run --rm --network none \
  -v <your-folder>:/algo:ro \
  -v <consumed-artifacts>:/input:ro \
  -v <fresh-output-dir>:/output \
  <environment-image> bash /algo/run.sh
```

- **Code is mounted**, not baked — your `run.sh`/scripts live in `/algo`.
- **No network** at run time; everything your algorithm needs must already be in the environment.
- **Read-only input.** `/input` contains only the artifacts your stage consumes.
- **Time limit.** Default 2 h wall-clock; exceeding it is a DNF.
- **Exit code.** `0` on success; non-zero is a failed run (DNF).
- **Output.** Write each produced artifact under its canonical filename to `/output`. A missing,
  misshapen, or unreadable output is a DNF.

So a MATLAB submission is: your `.m` files + either a base MATLAB Runtime `image:`, or a `Dockerfile`
that starts from one and downloads your toolbox. Nothing is baked by you.

## How your stage is evaluated

Two modes (see [`stages.yml`](stages.yml)):

- **Isolated** — your stage is fed the **ground-truth** artifacts it consumes (e.g. a `dipole`
  submission gets the true `localfield`), and its output is scored against ground truth. This is a
  fair, error-free measurement of your stage alone.
- **Composed** — your stage is chained with others' (e.g. someone's `bfr` output feeds your
  `dipole`), producing the full BFR × inversion interaction matrix scored on the final `chimap`.

### Integrity — what your container does and doesn't see

- Your container receives the artifacts your stage **consumes**. In isolated mode these are
  ground-truth boundaries, mounted **at run time** from held-out data.
- Your container **never** receives the artifact it is supposed to **produce** (its scoring target),
  and has **no network**, so it cannot see or exfiltrate the answer.
- Scoring against ground truth happens in a separate step your container never touches.

This is what keeps scores honest while still letting stages be tested in isolation.
