# QSM-CI `dipole` stage: NLTV (QSM.jl). The authors' Julia code (QSM.jl at fde4b92 (v0.5.4)), called directly; the
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
lambda = setting("lambda", 1e-3)

# QSM.jl's nltv works on the phase in rad (its data term is exp(i*f)) and takes the data weight W
# from the caller. The inputs follow the QSM.rs port (astewartau/QSM.rs#323): the local field in
# ppm becomes phase at the first echo time (QSM-CI's gamma, which QSM.rs also uses), and
# W = min(2*mask*mag/max(mag), 1) from the magnitude (root-sum-of-squares over the echoes), the
# normalisation of FANSI's in-vivo example by the paper's authors. The result is converted back
# to ppm. Unweighted (W = nothing), QSM.jl's nltv diverges on fields of more than a few radians.
te = setting("te", echo_times()[1])
ppm_to_rad = 2pi * GAMMA_MHZ * field_strength() * te
mag, _ = readvol("magnitude.nii.gz")
mag = ndims(mag) == 4 ? dropdims(sqrt.(sum(abs2, mag; dims=4)); dims=4) : mag
magmax = maximum(mag)
W = magmax > 0 ? mask .* min.(2 .* mag ./ magmax, 1.0) : zeros(size(mask))

log_env("nltv-qsmjl")
chi = nltv(f .* ppm_to_rad, mask, vsz; W=W, bdir=bdir, pad=pad3(setting("pad", 0)), lambda=lambda, rho=setting("rho", 100 * lambda), mu=setting("mu", 1.0), tol=setting("tol", 1e-3), maxit=setting("max_iter", 250), toln=setting("newton_tol", 1e-6), maxitn=setting("newton_iter", 10))
writevol("chimap.nii.gz", chi ./ ppm_to_rad, ref)
