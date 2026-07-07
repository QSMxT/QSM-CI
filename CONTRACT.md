# QSM-CI submission contract — `v1`

Every submission is a container that satisfies this contract. It is **frozen**: changes bump the
version string, and each submission declares which contract it targets (`contract: v1` in
`algorithm.yml`).

## Execution model

QSM-CI runs your container roughly like this:

```bash
docker run --rm --network none \
  -v <challenge-inputs>:/input:ro \
  -v <fresh-output-dir>:/output \
  <your-image> bash run.sh
```

- **No network.** Your container cannot reach the internet during the run. Bake all weights,
  models, and dependencies into the image.
- **Read-only input.** `/input` is mounted read-only.
- **Time limit.** Runs are capped at a wall-clock limit (default **2 hours**). Exceeding it is a DNF.
- **Exit code.** Exit `0` on success. Any non-zero exit is recorded as a failed run (DNF).
- **Resources.** CPU and (where available) one GPU on the self-hosted runner. Do not assume a
  specific GPU model.

## `/input` (read-only)

| File | Description |
|------|-------------|
| `phase.nii.gz` | Wrapped phase, **radians**. 4D if multi-echo (`x,y,z,echo`), else 3D. |
| `magnitude.nii.gz` | Magnitude, arbitrary units. Same shape as `phase.nii.gz`. |
| `mask.nii.gz` | Brain mask, `uint8` (1 = brain, 0 = background). 3D. |
| `params.json` | Acquisition parameters (below). |

### `params.json` schema

```json
{
  "contract": "v1",
  "TE": [0.004, 0.008, 0.012, 0.016],
  "B0": 3.0,
  "B0_dir": [0.0, 0.0, 1.0],
  "voxel_size": [1.0, 1.0, 1.0]
}
```

| Field | Type | Units | Meaning |
|-------|------|-------|---------|
| `contract` | string | — | Contract version this data targets (`"v1"`). |
| `TE` | number[] | seconds | Echo time(s). Length matches the echo dimension of the phase. |
| `B0` | number | tesla | Main field strength. |
| `B0_dir` | number[3] | unit vector | B0 direction in image coordinates. |
| `voxel_size` | number[3] | mm | Voxel dimensions (x, y, z). Also present in the NIfTI header. |

Parameters are provided in one flat `params.json` so you never have to parse BIDS sidecars. The
field names mirror QSM.rs' `EchoTime` / `MagneticFieldStrength` conventions.

## `/output`

Write exactly one file:

| File | Requirement |
|------|-------------|
| `chimap.nii.gz` | Your susceptibility map. **ppm**. `float32` or `float64`. Same 3D grid, voxel size, and affine as `mask.nii.gz`. Values outside the mask are ignored by scoring. |

If `chimap.nii.gz` is missing, has the wrong shape, or is unreadable, the run is a DNF.

## Notes on units

- Output must be in **ppm** (not Hz, not radians). The simulated ground truth is in ppm; the scorer
  compares directly.
- If your method works internally in Hz, convert with the field strength from `params.json`:
  `ppm = Hz · 1e6 / (γ · B0)`, where `γ = 42.576e6` Hz/T.
