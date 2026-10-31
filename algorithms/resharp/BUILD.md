# Building resharp (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` with **licensed MATLAB R2023b + MATLAB Compiler, with the Image Processing
Toolbox**, and bake it onto the R2023b MATLAB Runtime. R2023b because it is the licensed MATLAB the
fidelity check runs on ([`../../fidelity/matlab/`](../../fidelity/matlab/README.md)), so the
container and the reference runs share one release. Bundled NIfTI toolbox and OS gzip (no JVM), no
toolbox shims, plus the first author's `resharp.m` from **github.com/sunhongfu/QSM at commit
c75b138**, the commit QSM.rs's port (`resharp-qsmrs`) cites.

Stage: `bfr`. It consumes `totalfield` (ppm), `mask` and `params`, runs `resharp.m` and writes
`localfield` (ppm), 0 outside RESHARP's eroded mask.

## 1. Fetch build-time deps (not committed)
```bash
git clone https://github.com/sunhongfu/QSM.git /tmp/sunhongfu-qsm && git -C /tmp/sunhongfu-qsm checkout c75b138
cd algorithms/resharp
cp -r /path/to/NIfTI_20140122 nifti
mkdir -p sun && cp /tmp/sunhongfu-qsm/background_field_removal/resharp.m sun/   # MD5 6b4b48c08f4346e6e5568ddab68eb9a7
```
[`fidelity/config.sh`](fidelity/config.sh) (`fid_assemble`) is the same recipe as a script.

## 2. Compile
```bash
matlab -batch "addpath('nifti'); addpath('sun'); mcc('-m','recon.m','-o','recon','-d','.')"
```
Everything is plain `.m`, so mcc traces it all; `resharp.m` calls the Image Processing Toolbox's
`padarray`. Check that `unresolvedSymbols.txt` and `mccExcludedFiles.log` list nothing
(`submit.sh resharp build`).

## 3. Bake the image and push
```bash
podman build -t ghcr.io/astewartau/qsm-ci/resharp:v1 .   # needs ./recon from §2
podman push  ghcr.io/astewartau/qsm-ci/resharp:v1
```
Make the package public (a new package starts private), pin `image:` in `algorithm.yml` by the
pushed digest, and rerun the fidelity check ([`fidelity/REPORT.md`](fidelity/REPORT.md)).

## Defaults and units
`resharp.m`'s own defaults: `ker_rad` 3 mm, `tik_reg` 1e-4, `iter_num` 200, and `cgs` at tolerance
1e-6 (l. 24-34, 92). Hongfu Sun's scanner drivers in the same repository override them
inconsistently (3T Siemens 3 mm / 1e-3 / 500; Philips 3 mm / 1e-4 / 200; 1.5 T and 4.7 T 4-5 mm /
5e-4), so the function's defaults are the reference, as in QSM.rs's `ResharpParams`.

RESHARP solves `(H'H + λ)x = H'Hy`, linear in the field, with a relative CGS tolerance, so the result
does not depend on the field's unit; `recon.m` passes the ppm total field (the drivers pass ppm too).
