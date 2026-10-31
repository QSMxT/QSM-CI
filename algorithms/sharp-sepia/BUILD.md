# Building sharp-sepia (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler, with the Image Processing
Toolbox**, and bake it onto the R2023b MATLAB Runtime. R2023b because it is the licensed MATLAB the
fidelity check runs on ([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the
container and the reference runs share one release. Same patterns as `../vsharp-sti/BUILD.md`
(bundled NIfTI toolbox, OS gzip, no JVM, no toolbox shims).

Stage: `bfr`. It consumes `totalfield` (ppm) + `mask` + `params`, runs SEPIA's SHARP path (odd
dimensions zero-padded, `SHARP.m`, cropped) and writes `localfield` (ppm).

## 1. Fetch build-time deps (not committed)
```bash
git clone https://github.com/kschan0214/sepia.git /tmp/sepia && git -C /tmp/sepia checkout db939ccc1e9aa2d02c2dc0e6adb5ad2b1f0cc839
mkdir -p algorithms/sharp-sepia/sepia algorithms/sharp-sepia/medi
cp /tmp/sepia/misc/background_removal/SHARP/SHARP.m /tmp/sepia/utils/zeropad_odd_dimension.m algorithms/sharp-sepia/sepia/
cp /path/to/MEDI_toolbox-2024.11.26/functions/{SMV,SMV_kernel,sphere_kernel}.m algorithms/sharp-sepia/medi/
cp -r /path/to/NIfTI_20140122 algorithms/sharp-sepia/nifti
```
Only these five files of SEPIA and MEDI are reached (`SHARP.m` → `SMV`, `SMV_kernel` →
`sphere_kernel`; `zeropad_odd_dimension` → `padarray`). MEDI 2024.11.26's three files have been
unchanged since 2013, so they are also what SEPIA's README's MEDI (Jan 2020) has. MD5:
`SHARP.m` 78a424c68a7bf209c3b8b752fb33b3b3, `SMV.m` 0e1425ce8e58aac06e5b609d5ce94bc0,
`SMV_kernel.m` 4717e88ef8b4d643807b570cff3196b5, `sphere_kernel.m` 2b1ef1c9beb375dc4fa978c4aea062c7.
[`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
cd algorithms/sharp-sepia
matlab -batch "addpath('nifti'); addpath('sepia'); addpath('medi'); \
  mcc('-m','recon.m','-o','recon','-d','.')"
```
Everything is plain `.m`, so mcc traces it all. Check that `unresolvedSymbols.txt` is empty and
`requiredMCRProducts.txt` lists the Image Processing Toolbox (35010). The harness does this compile
as a Slurm job (`submit.sh sharp-sepia build`) and keeps the log in `reports/build.txt`.

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/matlab-sharp-sepia:v1 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/matlab-sharp-sepia:v1
```
Make the package public, pin `image:` in `algorithm.yml` by the pushed digest, and rerun the
fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)).

## Defaults and units
SEPIA's GUI defaults, radius 4 and threshold 0.03, which its config export passes to `SHARP.m`
unchanged (`Wrapper_BFR_SHARP.m`'s own fallbacks, 0.1 and 30, apply only to a config without the
fields). The GUI calls the radius "voxel", but `sphere_kernel.m` takes it in mm. SHARP is linear
and scale-agnostic, so `recon.m` filters the ppm total field directly; `localfield` is ppm.
