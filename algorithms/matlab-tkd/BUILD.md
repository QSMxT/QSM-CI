# Building matlab-tkd for the MATLAB Runtime

Compile once on a machine with **MATLAB + MATLAB Compiler** — the only place a license is needed.
The result runs on the free **MATLAB Runtime (MCR)**, so QSM-CI scores it offline with no license.

## 1. Compile `recon.m` → standalone `recon`

```bash
matlab -batch "mcc('-m','recon.m','-o','recon','-d','.')"
```

Use the MATLAB release whose Runtime you'll target (here **R2023b**). `mcc` bundles the toolbox code
your method uses into the binary, so real toolboxes (SEPIA, MEDI, …) work. Keep the `recon`
executable (ignore the generated `run_recon.sh`, `readme.txt`, etc.).

## 2. Bake into an MCR image and push

With the compiled `recon` in this folder:

```dockerfile
# Dockerfile
FROM containers.mathworks.com/matlab-runtime:r2023b     # free Runtime; match the compiler release
COPY recon /opt/qsm-ci/recon
RUN chmod +x /opt/qsm-ci/recon
```

```bash
docker build -t ghcr.io/astewartau/qsm-ci/matlab-tkd:v1 .
docker push  ghcr.io/astewartau/qsm-ci/matlab-tkd:v1
```

That tag is what `algorithm.yml`'s `image:` points at. QSM-CI pulls it, mounts your `run.sh` at
`/algo`, and runs `/opt/qsm-ci/recon /input /output` with `--network none`.

## Alternatives

- **Let CI compile it.** If you don't want to build locally, push just `recon.m` (source) and run
  [`.github/workflows/matlab-compile.yml`](../../.github/workflows/matlab-compile.yml) — it runs on
  GitHub-hosted runners with a MATLAB batch licensing token (secret `MATLAB_BATCH_TOKEN`) and pushes the image for
  you (the license is used at *build* time, where network is allowed).
- **Mount instead of bake.** Commit the compiled `recon` in this folder and point `image:` at a plain
  `matlab-runtime` base; `run.sh` falls back to `/algo/recon`. Simpler, but puts a binary in git.

## Notes

- The MCR version **must** match the MATLAB Compiler release used.
- The binary is Linux x86_64 and opaque (source isn't recoverable) — fine, it runs sandboxed.
- A few MATLAB functions are non-deployable by `mcc`; core QSM math is fine.
