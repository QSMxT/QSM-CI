# Building chi-sep-ilsqr (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` on a machine with **MATLAB + MATLAB Compiler** (R2026a). The result runs license-free
on the MATLAB Runtime. Same pattern as `../matlab-sti-ilsqr/BUILD.md` (bundled NIfTI + STI Suite `.p` +
IPT/SPT shims), plus the **SNU-LIST chi-separation toolbox** (`chi_sep_iLSQR`, obfuscated `.p`).

Stage: `chi-separation` — consumes `localfield` (ppm) + `r2prime` (Hz) + `magnitude` + `mask` + `params`;
reconstructs the QSM in-house with STI-Suite `QSM_iLSQR` (NOT the phantom's GT χ_total — that fails,
see recon.m note), runs `chi_sep_iLSQR` → `chi-para` (χ+) + `chi-dia` (χ−). Scored χ+ xsim ~0.49 / χ− 0.32.

## 1. Fetch build-time deps (not committed; `shims/` IS committed — it's ours)
```bash
cp -r /path/to/NIfTI_20140122                                 algorithms/chi-sep-ilsqr/nifti
cp -r /path/to/STISuite_V3.0/Core_Functions_P                 algorithms/chi-sep-ilsqr/sti
# chi-separation toolbox (obtained via SNU-LIST Google Form) — only functions/ + utils/ are needed:
mkdir -p algorithms/chi-sep-ilsqr/chisep
cp -r /path/to/Chisep_Toolbox_v1.1.3/functions               algorithms/chi-sep-ilsqr/chisep/functions
cp -r /path/to/Chisep_Toolbox_v1.1.3/utils                   algorithms/chi-sep-ilsqr/chisep/utils
```
`sti/` and `chisep/` hold obfuscated `.p` (real code) that mcc can't trace into, so they're force-bundled
with `-a` below. `shims/` replaces the Image Processing + Signal Processing Toolbox functions the `.p`
call (`padarray`, `strel`/`imdilate`/`imerode`/`imclose`/`imopen`, `tukeywin`/`hann`/`hanning`) — the
MATLAB Runtime ships neither toolbox.

## 2. Compile
```bash
cd algorithms/chi-sep-ilsqr
matlab -batch "addpath('shims'); addpath('nifti'); addpath('sti'); addpath(genpath('chisep')); \
  mcc('-m','recon.m','-a','sti','-a','chisep','-a','shims','-o','recon','-d','.')"
```
`-a sti -a chisep` force-bundle every `.p` (mcc can't see dependencies inside obfuscated pcode);
`-a shims` bundles the IPT/SPT replacements onto the deployed path.

## 3. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/chi-sep-ilsqr:v1 .   # FROM matlab-runtime:r2026a + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/chi-sep-ilsqr:v1
```
Then **make the GHCR package public** (Package settings → Danger Zone → Change visibility → Public),
so the scoring environment's unauthenticated `docker manifest inspect` can pull it.

## Notes
- Requires STI Suite because `recon.m` reconstructs the QSM with `QSM_iLSQR` from the local field — the
  chi-separation toolbox expects a QSM in its own scaling/orientation conventions, not an external χ map.
- CSF referencing is disabled (isolated eval provides no CSF mask); the Bunya diagnostic showed CSF
  mask + N_std have no measurable effect vs the QSM-input fix.
