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
| `chi-separation` | `localfield`, `r2prime`, `chimap`, `magnitude`, `mask`, `params` | `chi-para`, `chi-dia` |
| `r2prime-generation` | `magnitude`, `mask`, `params` | `r2prime` |
| `brain-extraction` | `magnitude`, `params` | `mask` |

`chi-separation` (susceptibility source separation) splits χ into a paramagnetic (χ+, iron) and a
diamagnetic (χ−, myelin·calcium) source map from the local field, R2′, χ_total and the multi-echo
magnitude. It is scored **isolated only**: its outputs are neither `localfield` nor `chimap`, so it
never enters the field-mapping × bfr × dipole composed matrix. Most methods read a subset of the six
inputs — declare what your code actually reads under `inputs:` in `algorithm.yml` (e.g.
`inputs: [localfield, chimap, r2prime, mask]`) and only those are mounted and offered as `qsm-ci run`
flags.

`r2prime-generation` estimates R2′ from the multi-echo GRE magnitude alone, for the GRE-only
condition where no spin-echo acquisition provides a measured R2. It is scored isolated against the
phantom's true R2′ and composed with each R2′-consuming `chi-separation` method (the generated map
replaces the true `r2prime`), to measure what a GRE-only protocol sacrifices.

`brain-extraction` is a standalone stage that *produces* the `mask` every other stage consumes — for
datasets that ship without a mask. Its output is not a scored ground-truth artifact, so it doesn't
enter the composed matrix.

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
| `r2prime` | `r2prime.nii.gz` | **Hz** (R2′ = R2* − R2, ≥ 0) | 3D |
| `chi-para` | `chi-para.nii.gz` | **ppm** (χ+, ≥ 0) | 3D |
| `chi-dia` | `chi-dia.nii.gz` | **ppm** (\|χ−\|, stored as a positive magnitude) | 3D |

All field maps and susceptibility maps (`chimap`, `chi-para`, `chi-dia`) are in **ppm** (normalized
by B0). Convert from Hz with `ppm = Hz · 1e6 / (γ · B0)`, `γ = 42.576e6` Hz/T. `r2prime` is the one
exception — a relaxation rate in **Hz** (s⁻¹), not normalized. All 3D artifacts share the grid,
voxel size, and affine of `mask.nii.gz`.

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

### Environment variables (no JSON parsing needed)

The same values are also injected into your container as environment variables, so a `run.sh` can use
them directly without `jq`:

| Variable | From | Example |
|----------|------|---------|
| `QSMCI_B0` | `params.json` `B0` | `7` |
| `QSMCI_TE` | `params.json` `TE` (space-separated) | `0.004 0.012 0.020` |
| `QSMCI_TE0` | first echo | `0.004` |
| `QSMCI_B0_DIR` | `params.json` `B0_dir` | `0 0 1` |
| `QSMCI_VOXEL_SIZE` | `params.json` `voxel_size` (mm) | `1 1 1` |
| `QSMCI_SET_<NAME>` | each `--set NAME=VALUE` override | `QSMCI_SET_THRESHOLD=0.2` |

```bash
qsmxt invert tkd "$IN/localfield.nii.gz" -m "$IN/mask.nii.gz" -o "$OUT/chimap.nii.gz" \
  --b0-direction $QSMCI_B0_DIR
```

The JSON files above are still written, so parsing them stays valid — the env vars are purely a
convenience.

## Execution model — environment vs. code

Your submission is **code plus an environment**; you do not have to bake your code into a custom
image. Evaluation is two phases:

**1. Environment phase (network ON — on your machine, not in CI).** `image:` names a prebuilt
container image. QSM-CI **pulls** that image and never builds one (`qsm_ci/containers.py`):
- Point `image:` at a base that already has what you need (the shared `py-ref` image, a MATLAB
  Runtime container, a Neurodesk image, …) — nothing to build.
- Or write a `Dockerfile` that starts `FROM` any base and installs or **downloads dependencies**
  (this is where a MATLAB toolbox like SEPIA gets `git clone`d), build and push it yourself, and set
  `image:` to the pushed tag. Keep the Dockerfile in your folder as the recipe for that image, but do
  **not** copy your algorithm code in; it is mounted.

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

So a Python submission is: your scripts + `run.sh` in the folder, and an `image:` that has the
dependencies (a shared base, or one you built from a `Dockerfile` and pushed). A compiled-MATLAB
submission bakes only the *compiled binary* into a MATLAB Runtime image (see
[docs/matlab.md](docs/matlab.md)); its `run.sh` and `.m` source still live in the folder and are
mounted.

## How your stage is evaluated

Two modes (see [`stages.yml`](stages.yml)):

- **Isolated** — your stage is fed the **ground-truth** artifacts it consumes (e.g. a `dipole`
  submission gets the true `localfield`), and its output is scored against ground truth. This is a
  fair, error-free measurement of your stage alone.
- **Composed** — your stage is chained with others' (e.g. someone's `bfr` output feeds your
  `dipole`), producing the full BFR × inversion interaction matrix scored on the final `chimap`.

### Integrity — what your container does and doesn't see

- Your container receives the artifacts your stage **consumes**. In isolated mode these are
  ground-truth boundaries, mounted **at run time** from the dataset's `groundtruth/`.
- Your container **never** receives the artifact it is supposed to **produce** (its scoring target),
  and has **no network**, so a run cannot read its own answer.
- Scoring against ground truth happens in a separate step your container never touches.
- The ground truth itself is **public**: the results viewer shows it next to every reconstruction,
  and each phantom's truth is published once to the Hugging Face volumes repo. QSM-CI is a
  benchmark, not a blind challenge — submissions are reviewed as pull requests, and a method has to
  generalise across every dataset it is scored on.

This is what keeps scores honest while still letting stages be tested in isolation.
