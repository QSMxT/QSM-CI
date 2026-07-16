# Submitting a MATLAB algorithm

MATLAB QSM code is welcome. The scoring run is offline (`--network none`), so the real question is
*what executes your code without a license at run time*. Two routes, **recommended first**:

- **Compile → MATLAB Runtime (Option A, recommended).** Compile your `.m` (+ toolboxes) with the
  MATLAB Compiler once — the **only** place a license is needed, at *build* time on your own machine.
  The standalone binary runs on the **free MATLAB Runtime**, so scoring stays
  fully offline and license-free, and any toolbox (SEPIA, MEDI, STI Suite, chi-separation) works
  because `mcc` bundles it. This is the [`matlab-tkd`](../algorithms/matlab-tkd) template, and what
  `qsm-ci new --lang matlab` scaffolds.
- **Full MATLAB at run time (Option B).** A licensed MATLAB container runs raw `.m` + toolboxes with
  no compilation, but needs a **license at run time**, which the offline run phase can't reach over a
  network license server — so it requires an offline/node-locked license or a controlled
  license-server exception on the runner. Use only if compiling is impractical.

> Neurodesk ships no ready MATLAB *QSM* container (its QSM tools — QSMxT, TGV-QSM, CLEARSWI, ROMEO —
> are Python/Julia; its full `matlab` image is BYO-license, and its `matlabmcr`/`matlab-runtime`
> images are the free Runtime). You supply the environment via `image:` or a small `Dockerfile`.

## Option A — compile → MATLAB Runtime (recommended)

Compile once (license at build time only), run license-free on the free Runtime (offline at scoring).

```matlab
% recon.m:  function recon(inputDir, outputDir)  — reads /input, writes /output/chimap.nii.gz (ppm)
mcc -m recon.m -o recon        % standalone binary; mcc bundles the toolbox code it uses
```

Bake into an MCR image and push:

```dockerfile
FROM containers.mathworks.com/matlab-runtime:r2023b   # free Runtime; match the compiler release
COPY recon /opt/qsm-ci/recon
RUN chmod +x /opt/qsm-ci/recon
```

Point `algorithm.yml`'s `image:` at that tag. QSM-CI mounts your `run.sh` at `/algo` and runs
`/opt/qsm-ci/recon /input /output` with `--network none`. Full recipe + version-pinning:
[`algorithms/matlab-tkd/BUILD.md`](../algorithms/matlab-tkd/BUILD.md).

**What lands where:** your PR holds only text — `algorithm.yml`, `run.sh`, `recon.m` (source), `BUILD.md`.
The compiled binary is **not** committed; it ships inside the image you push, and QSM-CI pulls that image.
(Unlike Python/Julia/Rust, where the source itself runs in a ready base image — nothing to compile or push.)

No MATLAB Compiler license? Use Option B below, or reuse an existing licensed container.

## Option B — full MATLAB at run time (needs a run-time license)

A licensed MATLAB base runs raw `.m` + a downloaded toolbox with no compilation:

```dockerfile
FROM containers.mathworks.com/matlab:r2023b                                 # BYO-license MATLAB base
RUN git clone --depth 1 https://github.com/kschan0214/sepia /opt/sepia      # download at build
```

```bash
matlab -batch "addpath(genpath('/opt/sepia')); addpath('/algo'); recon('$IN','$OUT')"
```

**Licensing caveat:** the scoring run is offline, so a full MATLAB base needs a license usable
**without** a network license server (an offline/node-locked license, or a controlled license-server
exception on a self-hosted runner). If you can't provide that, prefer Option A.

## Reusing an existing container

If your method already ships in a container (a Neurodesk tool, your own image), just point `image:`
at it and write a thin `run.sh` mapping `/input`/`/output` onto its CLI — often the fastest path.

## Notes

- No network at scoring time — everything the algorithm needs must be in the environment.
- Keep to the [contract](../CONTRACT.md): produce your stage's artifact(s) in **ppm** on the
  `mask.nii.gz` grid.
- MCR versions and env vars: Neurodesk `matlabmcr` template
  (`~/repos/neurodesk/neurocontainers/builder/templates/matlabmcr.yaml`).
