# QSM-CI submission contract — `v2`

Every submission is a container that implements one **stage** (or a **span** of stages) of the QSM
pipeline. It reads the artifacts that stage *consumes* from `/input` and writes the artifacts it
*produces* to `/output`. The registry of artifacts and stages is [`stages.yml`](stages.yml); this
document is the human contract. It is **frozen** — changes bump the version and each submission
declares `contract: v2`.

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
| `bfr+dipole` | `totalfield`, `mask`, `params` | `chimap` | QSMART |
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
  "contract": "v2",
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

## Execution model

```bash
docker run --rm --network none \
  -v <consumed-artifacts>:/input:ro \
  -v <fresh-output-dir>:/output \
  <your-image> bash run.sh
```

- **No network.** Bake all dependencies, weights, and models into the image.
- **Read-only input.** `/input` contains only the artifacts your stage consumes.
- **Time limit.** Default 2 h wall-clock; exceeding it is a DNF.
- **Exit code.** `0` on success; non-zero is a failed run (DNF).
- **Output.** Write each produced artifact under its canonical filename to `/output`. A missing,
  misshapen, or unreadable output is a DNF.

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
