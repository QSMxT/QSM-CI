# Building chi-sep-medi (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` on a machine with **MATLAB + MATLAB Compiler** (R2026a). The result runs license-free
on the MATLAB Runtime. Same pattern as `../chi-sep-ilsqr/BUILD.md`, but the core solver is `chi_sep_MEDI`
(morphology-enabled dipole inversion) and the extra toolbox is the **Cornell MEDI toolbox** (not STI Suite).

Stage: `chi-separation` — consumes `localfield` (ppm) + `r2prime` (Hz) + `chimap` (χ_total, ppm) +
`magnitude` + `mask` + `params`; runs `chi_sep_MEDI` → `chi-para` (χ+) + `chi-dia` (χ−). Scored χ+ xsim
~0.66 / χ− ~0.53. Unlike iLSQR, MEDI does its own dipole inversion, so it uses the provided χ_total
directly (no in-house STI-Suite QSM needed) and converges fast (~10 s).

## 1. Fetch build-time deps (not committed; `shims/` IS committed — it's ours)
```bash
cp -r /path/to/NIfTI_20140122                        algorithms/chi-sep-medi/nifti
cp -r /path/to/MEDI_toolbox/functions                algorithms/chi-sep-medi/medi
# store_CG_results is only referenced by an unused MEDI_L1 debug branch — add a no-op stub so mcc resolves it:
printf 'function store_CG_results(varargin)\nend\n' > algorithms/chi-sep-medi/medi/store_CG_results.m
# chi-separation toolbox (obtained via SNU-LIST Google Form) — only functions/ + utils/ are needed:
mkdir -p algorithms/chi-sep-medi/chisep
cp -r /path/to/Chisep_Toolbox_v1.1.3/functions       algorithms/chi-sep-medi/chisep/functions
cp -r /path/to/Chisep_Toolbox_v1.1.3/utils           algorithms/chi-sep-medi/chisep/utils
```
`chisep/` holds obfuscated `.p` (`chi_sep_MEDI`) that mcc can't trace into — and it calls the MEDI
toolbox internally — so both `chisep` and `medi` are force-bundled with `-a` below. `shims/` replaces
the IPT/SPT functions the `.p` call (`padarray`, morphology, `tukeywin`/`hann`/`hanning`).

## 2. Compile
```bash
cd algorithms/chi-sep-medi
matlab -batch "addpath('shims'); addpath('nifti'); addpath('medi'); addpath(genpath('chisep')); \
  mcc('-m','recon.m','-a','medi','-a','chisep','-a','shims','-o','recon','-d','.')"
```
`-a medi -a chisep` force-bundle the MEDI toolbox + the obfuscated chi-sep `.p` (mcc can't trace
dependencies inside pcode, and `chi_sep_MEDI.p` calls MEDI at runtime); `-a shims` bundles the IPT/SPT
replacements onto the deployed path.

## 3. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/chi-sep-medi:v1 .   # FROM matlab-runtime:r2026a + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/chi-sep-medi:v1
```
Then **make the GHCR package public** (Package settings → Danger Zone → Change visibility → Public).

## Notes
- CSF referencing is disabled (`params.lambda_CSF = 0`) — isolated eval provides no CSF mask.
- The MEDI toolbox ships DICOM/GUI `.m` files that `-a` bundles as unused resources; only the MEDI_L1
  dipole-inversion path is exercised. Linux MEX (`eig3volume`) isn't required by this path (verified —
  the local Linux run scored fine without a `.mexa64`).
