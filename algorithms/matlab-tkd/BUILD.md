# Building the MATLAB submission

The container runs a **compiled** MATLAB binary on the license-free MATLAB Runtime, so no MATLAB
license is needed to *run* the submission — only to *build* it.

## 1. Compile `recon.m` (needs MATLAB + MATLAB Compiler)

```matlab
mcc -m recon.m -o recon
```

This produces the standalone `recon` executable (and an MCR wrapper). Use a MATLAB version whose
Runtime matches the base image in `Dockerfile` (here R2023b).

## 2. Build the image

Place the compiled `recon` next to the `Dockerfile`, then:

```bash
docker build -t ghcr.io/astewartau/qsm-ci/matlab-tkd:v1 .
docker push  ghcr.io/astewartau/qsm-ci/matlab-tkd:v1
```

## Notes

- The compiled `recon` is a binary artifact, not committed here — build it in your environment (or a
  CI job with a MATLAB license) and push the resulting image.
- Alternatively, wrap an existing Neurodesk MATLAB QSM container (e.g. TGV-QSM) by pointing
  `algorithm.yml`'s `image:` at it and adapting `run.sh` to its CLI — often the fastest MATLAB path.
- See [`../../docs/matlab.md`](../../docs/matlab.md) and the Neurodesk `matlabmcr` template for
  Runtime versions and environment variables.
