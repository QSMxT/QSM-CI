# DECOMPOSE-QSM (MATLAB)

Signal-domain susceptibility source separation (Chen et al., *NeuroImage* 2021): a three-stage
alternating non-linear least-squares fit (`lsqcurvefit`) of the multi-echo complex GRE signal, per
voxel, that splits χ into paramagnetic (χ+, iron) and diamagnetic (χ−, myelin/calcium) components.
This is Tim Ho's open MATLAB re-implementation (GPL-3.0). The reference computes a QSM per echo,
χ(TE), from the raw phase (STI-Suite unwrap → V-SHARP → STAR-QSM), only to build each echo's phase
term (Chen 2021, Eq. 4). QSM-CI provides that per-echo χ(TE) as the optional `chimap-echoes` input
(x,y,z,echo, ppm), and `recon.m` uses it when the dataset ships it. Otherwise it uses χ_total
(`chimap`) at every echo. That phase is linear in TE and leaves DECOMPOSE little to separate. No phase
input and no STI dependency: DECOMPOSE's separation step is isolated from any upstream QSM error. The
per-voxel fit itself is the reference code (`decompose_utils/`, vendored).

**Output mapping.** χ+ = |DSC| and |χ−| = |PSC|, as the reference script writes them (`DSC` →
`XPSC`, `PSC` → `XDSC`). This is not a filename swap. The script fits
`ydata = squeeze(y_data(i,j,k,:))'`, and MATLAB's `'` is the conjugate transpose, so it fits conj(y).
Conjugation mirrors the model: `conj(S(C+, C−, χ+, χ−)) = S(C−, C+, −χ−, −χ+)`. A paramagnetic
source therefore lands in the fitted χ− pool, and `dscModel` reconstructs it. That is the paper's PCS
(Eq. 6) of the unconjugated signal. QSM.rs's port documents the same identity
(`src/separation/decompose.rs`, "Output mapping").

- **Stage:** `chi-separation` — reads `magnitude` (multi-echo), `chimap` (χ_total), `mask`,
  `params` (TE, B0), and `chimap-echoes` (χ(TE)) when the dataset ships it; writes `chi-para.nii.gz` (χ+) and `chi-dia.nii.gz` (χ−, positive magnitude), ppm
- **Engine:** compiled MATLAB — `recon.m` built with `mcc` (Optimization Toolbox needed at compile
  time only) and run on the licence-free MATLAB Runtime R2023b
- **Reference:** Chen et al., *NeuroImage* 2021 ·
  doi:[10.1016/j.neuroimage.2021.118735](https://doi.org/10.1016/j.neuroimage.2021.118735) ·
  code: https://github.com/timwahoo/DECOMPOSE-QSM
- **Image:** `ghcr.io/astewartau/qsm-ci/decompose-qsm:v3` (v3: reads `chimap-echoes`; v2 did not) — the compiled binary and its
  dependencies baked at `/opt/qsm-ci/recon` on a MATLAB Runtime base. The [`Dockerfile`](Dockerfile) is
  recovered from the image's history; the `mcc` compile and the image build were done on Bunya (see
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
qsm-ci run decompose-qsm --magnitude magnitude.nii.gz --chimap chimap.nii.gz --mask mask.nii.gz --params params.json \
  [--chimap-echoes chimap-echoes.nii.gz] -o out/
```

With a full MATLAB instead of the Runtime: `matlab -batch "addpath('.'); recon('IN','OUT')"` with
`DECOMPOSE_UTILS` (and optionally `CHISEP_NIFTI`) pointing at the toolboxes `recon.m` adds via
`addpath_env`.
