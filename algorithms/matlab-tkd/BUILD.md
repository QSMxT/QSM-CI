# Building matlab-tkd (compiled MATLAB → MATLAB Runtime)

Compile `recon.m` once on a machine with **MATLAB + MATLAB Compiler** (no license needed to *run*
the result on the free MATLAB Runtime). Proven with R2026a.

## Key patterns (reused by every MATLAB submission)
- **No Image Processing Toolbox.** Read/write NIfTI with the bundled **Jimmy Shen NIfTI toolbox**
  (`load_untouch_nii`/`save_untouch_nii`), not `niftiread`/`niftiwrite`.
- **No JVM in compiled binaries** → decompress/compress `.nii.gz` with the OS (`gunzip`/`gzip` via
  `system()`), since the toolbox's own gzip path needs Java. See `read_niigz`/`write_niigz` in `recon.m`.

## 1. Fetch the NIfTI toolbox (build-time only; not committed)
```bash
# any copy of the Jimmy Shen "Tools for NIfTI and ANALYZE image" toolbox, e.g.:
cp -r /path/to/NIfTI_20140122 algorithms/matlab-tkd/nifti
```

## 2. Compile
```bash
cd algorithms/matlab-tkd
matlab -batch "addpath('nifti'); mcc('-m','recon.m','-o','recon','-d','.')"   # -> ./recon (ELF binary)
```

## 3. Bake the MCR image and push
```bash
docker build -t ghcr.io/astewartau/qsm-ci/matlab-tkd:v1 .   # FROM matlab-runtime:r2026a + COPY recon
docker push  ghcr.io/astewartau/qsm-ci/matlab-tkd:v1
```
Point `algorithm.yml`'s `image:` at that tag and make the package public. QSM-CI runs
`/opt/qsm-ci/recon /input /output` on the free Runtime, offline.

> CI compile (`.github/workflows/matlab-compile.yml`) needs a MATLAB **batch licensing token** for
> Compiler (pilot program) — until you have one, compile locally as above.
