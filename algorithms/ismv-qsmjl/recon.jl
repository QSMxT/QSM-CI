# QSM-CI `bfr` stage: iSMV (QSM.jl). The authors' Julia code (QSM.jl at fde4b92 (v0.5.4)), called directly; the
# pinned environment is the base image algorithms/_julia (Manifest committed there).
# Glue (inputs, `--set` overrides, thread counts, output) is in qsmci_io.jl, identical in every
# Julia submission. Parameters and their QSM.rs-matched values: README.md.
include(joinpath(@__DIR__, "qsmci_io.jl"))
using QSM
QSM.FFTW_NTHREADS[] = NTHREADS

f, _ = readvol("totalfield.nii.gz")
mask, ref = readmask()
vsz = voxel_size()
log_env("ismv-qsmjl")
fl, _ = ismv(f, mask, vsz; r=setting("radius", 2 * maximum(vsz)), tol=setting("tol", 1e-3), maxit=setting("max_iter", 500))
writevol("localfield.nii.gz", fl, ref)
