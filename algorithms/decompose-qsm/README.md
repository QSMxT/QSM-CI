# DECOMPOSE-QSM (MATLAB)

Signal-domain susceptibility source separation (Chen et al., *NeuroImage* 2021): a three-stage
alternating non-linear least-squares fit (`lsqcurvefit`) of the multi-echo complex GRE signal, per
voxel, that splits χ into paramagnetic (χ+, iron) and diamagnetic (χ−, myelin/calcium) components.
This is Tim Ho's open MATLAB re-implementation (GPL-3.0) with one adaptation for QSM-CI: the
reference re-derives a per-echo QSM from the raw phase (STI-Suite unwrap → V-SHARP → STAR-QSM)
purely to build the signal's phase term; since χ is echo-independent and QSM-CI already provides
χ_total (`chimap`) as a stage input, `recon.m` uses that directly — no phase input, no STI
dependency, and DECOMPOSE's separation step is isolated from any upstream QSM error. The per-voxel
fit itself is the reference code (`decompose_utils/`, vendored).

- **Stage:** `chi-separation` — reads `magnitude` (multi-echo), `chimap` (χ_total), `mask`,
  `params` (TE, B0); writes `chi-para.nii.gz` (χ+) and `chi-dia.nii.gz` (χ−, positive magnitude), ppm
- **Engine:** compiled MATLAB — `recon.m` built with `mcc` (Optimization Toolbox needed at compile
  time only) and run on the licence-free MATLAB Runtime R2023b
- **Reference:** Chen et al., *NeuroImage* 2021 ·
  doi:[10.1016/j.neuroimage.2021.118735](https://doi.org/10.1016/j.neuroimage.2021.118735) ·
  code: https://github.com/timwahoo/DECOMPOSE-QSM
- **Image:** `ghcr.io/astewartau/qsm-ci/decompose-qsm:v2` — the compiled binary and its
  dependencies baked at `/opt/qsm-ci/recon` on a MATLAB Runtime base. There is no Dockerfile in
  this folder: the `mcc` compile and the image build were done on Bunya (see
  [`docs/matlab.md`](../../docs/matlab.md) for the general compiled-MATLAB recipe).
- **Runner:** `self-hosted` with a 720-min cap — the per-voxel fit took ~31 min on 48 cores and
  2–6 h on the shared self-hosted box. The per-PR smoke gate fits only a 24³ central box
  (`smoke_box`); the full scoring run is unaffected.

## How QSM-CI runs it

`run.sh` execs the compiled `recon` (`$MATLAB_RECON`, default `/opt/qsm-ci/recon`, falling back to
`./recon`) on the MATLAB Runtime, pointing `MCR_CACHE_ROOT` and — because CI runs the container as a
non-root user with no home — `HOME` at a writable directory. `DECOMPOSE_CROPBOX` (central-box side,
voxels) and `DECOMPOSE_NINNER` (inner iterations, default 10) bound the fit for feasibility runs.

```bash
qsm-ci run decompose-qsm --magnitude magnitude.nii.gz --chimap chimap.nii.gz --mask mask.nii.gz --params params.json -o out/
```

With a full MATLAB instead of the Runtime: `matlab -batch "addpath('.'); recon('IN','OUT')"` with
`DECOMPOSE_UTILS` (and optionally `CHISEP_NIFTI`) pointing at the toolboxes `recon.m` adds via
`addpath_env`.
