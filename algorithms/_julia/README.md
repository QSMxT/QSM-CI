# Julia base image (the authors' Julia packages)

Shared environment for the submissions that run the **original Julia code** behind QSM.rs's
ports (QSMxT/QSM-CI#299). Each one has the same `algorithm:` as its `-qsmrs` port and a `variant:`
naming the original package, so the two can be compared method by method.

| Package | Pinned at | Submissions |
|---|---|---|
| [QSM.jl](https://github.com/kamesy/QSM.jl) | `fde4b92` (0.5.4) | `tkd-qsmjl`, `tsvd-qsmjl`, `tikhonov-qsmjl`, `tv-qsmjl`, `rts-qsmjl`, `nltv-qsmjl`, `sharp-qsmjl`, `vsharp-qsmjl`, `ismv-qsmjl`, `laplacian-qsmjl` |
| [ROMEO.jl](https://github.com/korbinian90/ROMEO.jl) + [MriResearchTools.jl](https://github.com/korbinian90/MriResearchTools.jl) | `08776d4` (1.6.0) + `771eadf` (3.8.0) | `romeo-romeojl` |
| [QuantitativeSusceptibilityMappingTGV.jl](https://github.com/korbinian90/QuantitativeSusceptibilityMappingTGV.jl) | `6c0886a` (0.5.2) | `tgv-tgvjl` |
| [CLEARSWI.jl](https://github.com/korbinian90/CLEARSWI.jl) | `0949bc5` (1.7.0) | none: QSM-CI has no SWI stage |

These are the commits QSM.rs's module docs cite. Everything else is pinned by the committed
[`env/Manifest.toml`](env/Manifest.toml), on Julia **1.10.11** (the official `julia:1.10.11-bookworm`
image, by digest). FFTW.jl stays below 1.9 because QSM.jl 0.5.4 calls `FFTW.libfftw3[]`, which
FFTW.jl 1.9 removed.

## What is in the image

- `/opt/qsmci-julia`: the project (`Project.toml`, `Manifest.toml`), `JULIA_PROJECT`.
- `/opt/qsmci-julia/qsmjl.so` and `mritools.so` (`$QSMCI_JULIA_SYSIMAGE_DIR`): PackageCompiler
  sysimages, one per package family, compiled with [`precompile_qsmjl.jl`](precompile_qsmjl.jl)
  and [`precompile_mritools.jl`](precompile_mritools.jl) as the workloads, so a run does not start
  with a minute of JIT compilation. `qsmjl.so` holds QSM.jl (the `*-qsmjl` submissions);
  `mritools.so` holds ROMEO.jl, MriResearchTools.jl, the TGV package and CLEARSWI.jl
  (`romeo-romeojl`, `tgv-tgvjl`). They cannot be one image: MriResearchTools has an extension for
  QSM.jl and one for the TGV package that define the same functions, and only one may load.
- `JULIA_CPU_TARGET` is the official Julia 1.10 binaries' list (generic x86-64 with sandybridge
  and haswell clones), for the sysimages and the package images, so the image runs on any x86-64
  host. Floating-point results can still depend on the CPU (code compiled at run time is
  native, and FFTW and the SIMD packages pick kernels by CPU features), so fidelity is checked
  per host: see [`fidelity/README.md`](fidelity/README.md).
- `/opt/julia-depot`: the packages and artifacts. At run time `JULIA_DEPOT_PATH` puts a writable
  `/tmp/julia-depot` in front of it, so the container can run as any UID with no home.

No submission code is baked in. Every submission folder has `recon.jl` (the package calls),
`run.sh` (starts Julia with 4 threads and the sysimage) and a copy of [`qsmci_io.jl`](qsmci_io.jl),
the glue that reads the inputs, applies `--set` overrides and writes the output.
`tests/test_julia_submissions.py` keeps the copies identical to this one.

## Build and push

```bash
podman build -t ghcr.io/astewartau/qsm-ci/julia-qsm:v1 algorithms/_julia
podman push ghcr.io/astewartau/qsm-ci/julia-qsm:v1
```

Pin the pushed digest in each submission's `image:` (with the tag as a comment), rerun the
fidelity check ([`fidelity/README.md`](fidelity/README.md)) and update each `fidelity:` record.
Never re-push an existing tag; a change is a new tag.

To change a package version: re-resolve `env/` (in a `julia:1.10.11` container, `Pkg.add` with
`url` and `rev` for the five packages above), rebuild under a new tag, and rerun the fidelity check.
