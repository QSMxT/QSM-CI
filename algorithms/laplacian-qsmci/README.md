# Laplacian field mapping (QSM-CI reference)

The in-repo reference `field-mapping` submission: Laplacian phase unwrapping of each echo, then a
per-voxel linear fit of unwrapped phase against echo time for the off-resonance frequency, converted
Hz → ppm. Plain numpy/nibabel, no parameters. The other field-mapping submission is `romeo-qsmrs`.

- **Stage:** `field-mapping` — reads `phase` (multi-echo), `mask`, `params` (TE, B0); writes
  `totalfield.nii.gz` (ppm)
- **Engine:** Python (`recon.py`), CPU
- **Reference:** none — an in-repo reference implementation (MIT)
- **Image:** `ghcr.io/astewartau/qsm-ci/py-ref:v1`, the shared deps-only base (numpy, scipy,
  nibabel) built from [`algorithms/_base/Dockerfile`](../_base/Dockerfile). This folder has no
  Dockerfile: `recon.py` and `run.sh` are mounted into that image at run time.

## How QSM-CI runs it

`run.sh` calls `python3 recon.py <input-dir> <output-dir>`. The same thing, locally:

```bash
qsm-ci run laplacian-qsmci --phase phase.nii.gz --mask mask.nii.gz --params params.json -o totalfield.nii.gz
```

(`--te … --field-strength …` build the `params.json` if you don't have one; `qsm-ci run
laplacian-qsmci --help` lists the flags.)
