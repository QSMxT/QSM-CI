# Building chisep-ilsqr (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler, with the Image Processing and
Signal Processing toolboxes**, and bake it onto the R2023b MATLAB Runtime. R2023b because it is the
licensed MATLAB the fidelity check runs on ([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)),
so the container and the reference runs share one release. Same pattern as `../ilsqr-sti/BUILD.md`
(bundled NIfTI + STI Suite `.p`, no toolbox shims), plus the **SNU-LIST χ-separation toolbox**
(`chi_sep_iLSQR`, pcode).

Stage: `chi-separation` — consumes `localfield` (ppm) + `r2prime` (Hz) + `magnitude` + `mask` + `params`;
reconstructs the QSM in-house with STI-Suite `QSM_iLSQR` (NOT the phantom's GT χ_total — that fails,
see recon.m note), runs `chi_sep_iLSQR` → `chi-para` (χ+) + `chi-dia` (χ−).

## 1. Fetch build-time deps (not committed)
```bash
cp -r /path/to/NIfTI_20140122                                 algorithms/chisep-ilsqr/nifti
cp -r /path/to/STISuite_V3.0/Core_Functions_P                 algorithms/chisep-ilsqr/sti
# χ-separation toolbox (obtained via the SNU-LIST Google Form) — only functions/ + utils/ are needed:
mkdir -p algorithms/chisep-ilsqr/chisep
cp -r /path/to/Chisep_Toolbox_v1.1.3/functions               algorithms/chisep-ilsqr/chisep/functions
cp -r /path/to/Chisep_Toolbox_v1.1.3/utils                   algorithms/chisep-ilsqr/chisep/utils
```
[`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
cd algorithms/chisep-ilsqr
matlab -batch "addpath('nifti'); addpath('sti'); addpath(genpath('chisep')); \
  mcc('-m','recon.m','-a','sti','-a','chisep','-o','recon','-d','.')"
```
- `-a sti -a chisep` force-bundle every `.p` (mcc can't trace dependencies inside pcode).
- For the same reason `recon.m` names the toolbox functions the pcode calls in a `%#function` pragma:
  `imclose`, `imdilate`, `imerode`, `padarray`, `strel` (Image Processing; `QSM_iLSQR`) and
  `tukeywin` (Signal Processing; `chi_sep_iLSQR`), found by profiling a licensed run
  (`fidelity/matlab/submit.sh chisep-ilsqr trace`), plus `hann`, `hanning` and `imopen`, which the
  old shim set covered.
- **Path order matters.** The toolbox comes first, as its own scripts put it: its `utils/` carries
  pcode copies of the NIfTI loaders (`load_untouch_nii` and friends) and a `medfilt3`, which shadow
  Jimmy Shen's and the Image Processing Toolbox's. `recon.m` reads its inputs through them.
- Check that `unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing, and that
  `requiredMCRProducts.txt` lists the Image Processing (35010) and Signal Processing toolboxes. The
  harness does this compile as a Slurm job (`submit.sh chisep-ilsqr build`; log in `reports/build.txt`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/chi-sep-ilsqr:v2 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/chi-sep-ilsqr:v2
```
Keep the package public, pin `image:` in `algorithm.yml` by the pushed digest, and rerun the
fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)). The [`Dockerfile`](Dockerfile) is the
R2023b Runtime base (pinned by digest) plus `recon`.

Images: `v1` (R2026a Runtime, IPT/SPT shims whose greyscale `imdilate`/`imerode` wrapped round at the
volume border; its Dockerfile was `FROM matlab-runtime:r2026a` + `COPY recon` + `chmod +x`); `v2`
(R2023b, the real toolboxes, no shims; see `fidelity:` in `algorithm.yml`).

## Notes
- Requires STI Suite because `recon.m` reconstructs the QSM with `QSM_iLSQR` from the local field — the
  χ-separation toolbox expects a QSM in its own scaling/orientation conventions, not an external χ map.
- CSF referencing is disabled (isolated eval provides no CSF mask); the Bunya diagnostic showed CSF
  mask + N_std have no measurable effect vs the QSM-input fix.
