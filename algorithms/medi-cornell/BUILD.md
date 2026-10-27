# Building medi-cornell (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler** and bake it onto the R2023b
MATLAB Runtime. R2023b because it is the licensed MATLAB the fidelity check runs on
([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the container and the reference
runs share one release. Bundled NIfTI toolbox and OS gzip (no JVM), plus the Cornell **MEDI toolbox
2024.11.26**, the release QSM.rs's MEDI port follows.

Stage: `dipole` — consumes `localfield` (ppm), `magnitude`, `mask`, `params`; `MEDI_L1` dipole
inversion on the provided local field → `chimap` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122                        algorithms/medi-cornell/nifti   # Jimmy Shen toolbox
cp -r /path/to/MEDI_toolbox-2024.11.26/functions     algorithms/medi-cornell/medi    # Cornell MEDI toolbox
# store_CG_results is only referenced by an unused MEDI_L1 debug branch — add a no-op stub so mcc resolves it:
printf 'function store_CG_results(varargin)\nend\n' > algorithms/medi-cornell/medi/store_CG_results.m
```
[`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
cd algorithms/medi-cornell
matlab -batch "addpath('nifti'); addpath('medi'); mcc('-m','recon.m','-o','recon','-d','.')"   # -> ./recon
```
mcc traces only the MEDI functions `recon.m` actually calls (MEDI_L1 and its dependencies; there is
no pcode); the DICOM/bet2/GUI files in `medi/` are ignored. Check that `unresolvedSymbols.txt` and
`mccExcludedFiles.log` list nothing. The harness does this compile as a Slurm job
(`fidelity/matlab/submit.sh medi-cornell build`; log in `reports/build.txt`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-medi:v3 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/matlab-medi:v3
```
Keep the package public, pin `image:` in `algorithm.yml` by the pushed digest, and rerun the
fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)). The [`Dockerfile`](Dockerfile) is the
R2023b Runtime base (pinned by digest) plus `recon`.

Images: `v1`, `v2` (R2026a Runtime; see `fidelity/REPORT.md` for which MEDI release `v2` holds);
`v3` (R2023b, MEDI 2024.11.26, Cornell's default `lambda` 1000; see `fidelity:` in `algorithm.yml`).

## MEDI 2024.11.26 defaults
`parse_QSM_input` in this release turns SMV background suppression and model-error reduction
(`merit`) **on** unless told `nosmv` / `nomerit`. QSM-CI's `smv_radius` and `merit` parameters
default to off (the input is already a local field), so `recon.m` passes `nosmv` and `nomerit`
explicitly unless they are set. `lambda` defaults to Cornell's 1000.

## Units
`localfield` is ppm; MEDI works in radians. recon.m converts `iFreq = field·1e-6·2π·CF·delta_TE`
at a fixed reference scale (CF = 42.576e6·3 T, `delta_TE` = 8 ms) and MEDI_L1 converts back to ppm
via `/(2π·delta_TE·CF)·1e6`, so the factor cancels: χ is ppm, and `lambda` stays on one scale at
any field strength.
