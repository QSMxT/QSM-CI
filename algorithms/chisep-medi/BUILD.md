# Building chisep-medi (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler, with the Image Processing and
Signal Processing toolboxes**, and bake it onto the R2023b MATLAB Runtime. R2023b because it is the
licensed MATLAB the fidelity check runs on ([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)),
so the container and the reference runs share one release. Same pattern as `../chisep-ilsqr/BUILD.md`,
but the core solver is `chi_sep_MEDI` and the extra toolbox is the **Cornell MEDI toolbox
2024.11.26** (not STI Suite).

Stage: `chi-separation` — consumes `localfield` (ppm) + `r2prime` (Hz) + `chimap` (χ_total, ppm) +
`magnitude` + `mask` + `params`; runs `chi_sep_MEDI` → `chi-para` (χ+) + `chi-dia` (χ−).

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122                                 algorithms/chisep-medi/nifti
# Cornell MEDI toolbox 2024.11.26: its top-level functions only (bet2/ calls `mex`), without the
# MEDI_L1ss* solver variant (it calls Symbolic Math's heaviside); neither can be deployed, and
# chi_sep_MEDI reaches neither. store_CG_results is named by an unused MEDI_L1 debug branch; a
# no-op stub lets mcc resolve it.
mkdir -p algorithms/chisep-medi/medi
find /path/to/MEDI_toolbox-2024.11.26/functions -maxdepth 1 -type f -name '*.m' ! -name 'MEDI_L1ss*' \
    -exec cp {} algorithms/chisep-medi/medi/ \;
printf 'function store_CG_results(varargin)\nend\n' > algorithms/chisep-medi/medi/store_CG_results.m
# χ-separation toolbox (obtained via the SNU-LIST Google Form) — only functions/ + utils/ are needed:
mkdir -p algorithms/chisep-medi/chisep
cp -r /path/to/Chisep_Toolbox_v1.1.3/functions               algorithms/chisep-medi/chisep/functions
cp -r /path/to/Chisep_Toolbox_v1.1.3/utils                   algorithms/chisep-medi/chisep/utils
```
[`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
cd algorithms/chisep-medi
matlab -batch "addpath('nifti'); addpath('medi'); addpath(genpath('chisep')); \
  mcc('-m','recon.m','-a','medi','-a','chisep','-o','recon','-d','.')"
```
- `-a medi -a chisep` force-bundle the MEDI toolbox and every `.p` (mcc can't trace dependencies
  inside pcode). In the profiled licensed run `chi_sep_MEDI` reached no MEDI function at all; MEDI
  stays bundled as the toolbox requires it.
- For the same reason `recon.m` names the toolbox functions the pcode calls in a `%#function` pragma:
  `imerode`, `padarray`, `strel` (Image Processing), found by profiling a licensed run
  (`fidelity/matlab/submit.sh chisep-medi trace`), plus `hann`, `hanning`, `imclose`, `imdilate`,
  `imopen` and `tukeywin`, which the old shim set covered.
- **Path order matters.** The toolbox comes first, as its own scripts put it: its `utils/` carries
  pcode copies of the NIfTI loaders (`load_untouch_nii` and friends) and a `medfilt3`, which shadow
  Jimmy Shen's and the Image Processing Toolbox's. `recon.m` reads its inputs through them.
- Check that `unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and that
  `requiredMCRProducts.txt` lists the Image Processing (35010) and Signal Processing toolboxes. The
  harness does this compile as a Slurm job (`submit.sh chisep-medi build`; log in `reports/build.txt`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/chi-sep-medi:v4 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/chi-sep-medi:v4
```
Keep the package public, pin `image:` in `algorithm.yml` by the pushed digest, and rerun the
fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)). The [`Dockerfile`](Dockerfile) is the
R2023b Runtime base (pinned by digest) plus `recon`.

Images: `v1` (R2026a Runtime, IPT/SPT shims whose greyscale `imdilate`/`imerode` wrapped round at the
volume border; its Dockerfile was `FROM matlab-runtime:r2026a` + `COPY recon` + `chmod +x`); `v2`
(R2023b, the real toolboxes, no shims; see `fidelity:` in `algorithm.yml`); `v3` (`mask_CSF = []`
instead of an all-false mask, so MEDI iterates, #315); `v4` (`N_std` from MEDI's `Fit_ppm_complex` on
the multi-echo magnitude instead of ones, and `params.time_limit = Inf`; build job 31198842).

## Notes
- No CSF term: isolated eval provides no CSF mask, so `option_data.mask_CSF = []`, as the toolbox GUI
  passes without one. An all-false mask is not the same: the toolbox's CSF mean over it is NaN, every
  step is lost and the solver returns its initial guess (QSMxT/QSM-CI#315; `v2` did this).
- `N_std` is MEDI `Fit_ppm_complex`'s error estimate `dp1` from the multi-echo magnitude (zero
  outside the mask). It depends on the magnitude alone, so the stage needs no phase. The toolbox
  computes the same map in `Chisep_script.m` (`Preprocessing4Phase`) and in its GUI
  (`WrapperChisepMEDI`); see `fidelity/REPORT.md`. `v1`–`v3` passed ones.
- No wall-clock limit: `params.time_limit = Inf`. The toolbox's default stops the Gauss-Newton loop
  after 1800 s, which would make results depend on the runner's speed. Below the limit, `Inf` gives
  the same output as the default, bit for bit.
