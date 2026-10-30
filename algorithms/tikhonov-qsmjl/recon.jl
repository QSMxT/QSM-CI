# QSM-CI `dipole` stage: Tikhonov (QSM.jl). The authors' Julia code (QSM.jl at fde4b92 (v0.5.4)), called directly; the
# pinned environment is the base image algorithms/_julia (Manifest committed there).
# Glue (inputs, `--set` overrides, thread counts, output) is in qsmci_io.jl, identical in every
# Julia submission. Parameters and their QSM.rs-matched values: README.md.
include(joinpath(@__DIR__, "qsmci_io.jl"))
using QSM
QSM.FFTW_NTHREADS[] = NTHREADS

pad3(p) = (Int(p), Int(p), Int(p))

f, _ = readvol("localfield.nii.gz")
mask, ref = readmask()
vsz, bdir = voxel_size(), b0_dir()
log_env("tikhonov-qsmjl")
chi = tikh(f, mask, vsz; bdir=bdir, pad=pad3(setting("pad", 0)), lambda=setting("lambda", 1e-2), reg=Symbol(setting("reg", "identity")))
writevol("chimap.nii.gz", chi, ref)
