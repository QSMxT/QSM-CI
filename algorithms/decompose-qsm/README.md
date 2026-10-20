# DECOMPOSE-QSM (MATLAB)

Signal-domain susceptibility source separation (Chen et al., *NeuroImage* 2021): a three-stage
alternating non-linear least-squares fit (`lsqcurvefit`) of the multi-echo complex GRE signal, per
voxel, that splits χ into paramagnetic (χ+, iron) and diamagnetic (χ−, myelin/calcium) components.
This is Tim Ho's open MATLAB re-implementation (GPL-3.0). DECOMPOSE is defined on a QSM of
each echo, χ(t): the paper's Eq. 4 builds the fitted data as
`y(t) = M(t)·exp(−i·(2/3)·χ(t)·γ·B0·t)` and states that TE-dependent QSM is required. The reference
computes χ(t) per echo with STI Suite (Laplacian unwrapping → V-SHARP → STAR-QSM); here it is the
phantom's `chimap-echoes.nii.gz` (4D, one χ per echo, echo order of the magnitude), and `recon.m`
builds `y_data` from it as `DECOMPOSE_analysis.m` does. A phantom without it falls back to
`chimap.nii.gz` (χ_total) for every echo, with a note in the log. The per-voxel fit itself is the
reference code (`decompose_utils/`, vendored).

Output mapping follows the paper: χ+ is the PCS, from the paramagnetic sub-model (Eq. 6), and χ−
the DCS (Eq. 7). The reference demo writes DSC to the file `XPSC` and PSC to `XDSC`; that filename
swap is not followed.

> **The pinned image predates both changes.** It was compiled from the earlier `recon.m` (χ_total
> only, χ+ = |DSC|) and could not be rebuilt here (no MATLAB on Bunya). Rebuild the `mcc` binary
> and image before scoring this entry again.

- **Stage:** `chi-separation` — reads `magnitude` (multi-echo), `chimap-echoes` (per-echo QSM,
  optional) or `chimap` (χ_total), `mask`, `params` (TE, B0); writes `chi-para.nii.gz` (χ+) and `chi-dia.nii.gz` (χ−, positive magnitude), ppm
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
qsm-ci run decompose-qsm --magnitude magnitude.nii.gz --chimap chimap.nii.gz \
  --chimap-echoes chimap-echoes.nii.gz --mask mask.nii.gz --params params.json -o out/
```

With a full MATLAB instead of the Runtime: `matlab -batch "addpath('.'); recon('IN','OUT')"` with
`DECOMPOSE_UTILS` (and optionally `CHISEP_NIFTI`) pointing at the toolboxes `recon.m` adds via
`addpath_env`.
