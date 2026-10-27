# QSM-CI Julia base image: the authors' Julia packages, pinned, for the *-qsmjl / *-romeojl /
# *-tgvjl submissions (the originals of QSM.rs's ports; QSMxT/QSM-CI#299).
#
# Exact Julia (1.10.11, official image pinned by digest) and an exact Manifest (env/): QSM.jl
# fde4b92, ROMEO.jl 08776d4, MriResearchTools.jl 771eadf, QuantitativeSusceptibilityMappingTGV.jl
# 6c0886a, CLEARSWI.jl 0949bc5 (git revisions), every other package at the version the Manifest
# records. The packages are compiled into two sysimages (see below), so a run does not start with
# a minute of JIT compilation. JULIA_CPU_TARGET is the official Julia 1.10 binaries' target list
# (generic x86-64 with sandybridge and haswell clones), for the sysimages and the package images
# alike, so the image runs on any x86-64 host. Submission code is mounted at /algo, never baked.
#
#   podman build -t ghcr.io/astewartau/qsm-ci/julia-qsm:v1 algorithms/_julia
#   podman push  ghcr.io/astewartau/qsm-ci/julia-qsm:v1
FROM docker.io/library/julia:1.10.11-bookworm@sha256:be36b80433fe0090aef2ff604e22fc13e51876f0765ac09aba4ee3ad01b4b17e

# Build-time depot. At run time a writable scratch depot goes in front of it (Julia writes logs
# and caches to the first depot; the container may run as an unknown UID with no home).
ENV JULIA_DEPOT_PATH=/opt/julia-depot \
    JULIA_PROJECT=/opt/qsmci-julia \
    JULIA_PKG_PRECOMPILE_AUTO=0 \
    JULIA_CPU_TARGET="generic;sandybridge,-xsaveopt,clone_all;haswell,-rdrnd,base(1)" \
    QSMCI_JULIA_SYSIMAGE_DIR=/opt/qsmci-julia

COPY env/Project.toml env/Manifest.toml /opt/qsmci-julia/
RUN julia -e 'using Pkg; Pkg.instantiate(); Pkg.precompile(strict=true)'

# Two sysimages, one per package family, each built with precompile_<name>.jl as the workload.
# They have to be separate: MriResearchTools has one extension for QSM.jl and one for the TGV
# package that define the same functions ("load exactly one per session", its ext/QSMExt.jl), so
# QSM.jl and MriResearchTools + TGV cannot be loaded, or compiled, into one image.
#   qsmjl.so     QSM.jl (the *-qsmjl submissions)
#   mritools.so  ROMEO.jl, MriResearchTools.jl, the TGV package, CLEARSWI.jl (romeo-romeojl, tgv-tgvjl)
# PackageCompiler is installed into a throwaway project with its own pinned version, not into the
# runtime project; gcc (which links the sysimages) is installed and removed in the same layer.
# Only the packages that actually load go into a sysimage (include_transitive_dependencies=false):
# the Manifest also lists FFTW's optional MKL backend, whose library is a lazy artifact that would
# otherwise be initialised at start-up and fetched from the network.
COPY precompile_qsmjl.jl precompile_mritools.jl /opt/qsmci-julia/
ARG PACKAGECOMPILER_VERSION=2.4.4
RUN set -eu; \
    apt-get update; apt-get install -y --no-install-recommends gcc libc6-dev; \
    julia --project=/tmp/pc -e "using Pkg; Pkg.add(name=\"PackageCompiler\", version=\"$PACKAGECOMPILER_VERSION\")"; \
    JULIA_LOAD_PATH="/opt/qsmci-julia:/tmp/pc:@stdlib" julia -e ' \
      using PackageCompiler; \
      for (name, pkgs) in (("qsmjl", [:NIfTI, :JSON, :FFTW, :QSM]), \
                           ("mritools", [:NIfTI, :JSON, :FFTW, :ArgParse, :ROMEO, :MriResearchTools, \
                                         :QuantitativeSusceptibilityMappingTGV, :CLEARSWI])); \
        create_sysimage(pkgs; project="/opt/qsmci-julia", \
          sysimage_path="/opt/qsmci-julia/$(name).so", \
          precompile_execution_file="/opt/qsmci-julia/precompile_$(name).jl", \
          cpu_target=ENV["JULIA_CPU_TARGET"], include_transitive_dependencies=false); \
      end'; \
    rm -rf /tmp/pc; \
    apt-get purge -y --auto-remove gcc libc6-dev; rm -rf /var/lib/apt/lists/*; \
    chmod -R a+rX /opt/julia-depot /opt/qsmci-julia

ENV JULIA_DEPOT_PATH=/tmp/julia-depot:/opt/julia-depot \
    JULIA_PKG_OFFLINE=true
