# QSM-CI `bfr` stage: V-SHARP (QSM.jl). The authors' Julia code (QSM.jl at fde4b92 (v0.5.4)), called directly; the
# pinned environment is the base image algorithms/_julia (Manifest committed there).
# Glue (inputs, `--set` overrides, thread counts, output) is in qsmci_io.jl, identical in every
# Julia submission. Parameters and their QSM.rs-matched values: README.md.
include(joinpath(@__DIR__, "qsmci_io.jl"))
using QSM
QSM.FFTW_NTHREADS[] = NTHREADS

f, _ = readvol("totalfield.nii.gz")
mask, ref = readmask()
# The voxel size from the NIfTI header (pixdim, as NIfTI.jl's `voxel_size` gives it), not
# params.json: QSM.jl pads its box by cld(max(r), minimum(vsz)) voxels, so a header spacing one
# float32 ulp below 1 mm (0.99999994, the KKI travelling head's z) pads 13 voxels for 12 mm where
# params.json's 1.0 pads 12, a different periodic deconvolution (1.19 % NRMSE against QSM.rs, which,
# like any QSMxT user, reads the header). The port is fed the header's value, so the original is too.
vsz = Tuple(Float64.(ref.header.pixdim[2:4]))
# QSM.jl's default radii, 18*min(vsz):-2*max(vsz):2*max(vsz) mm, unless overridden.
function radii(vsz)
    hi = setting("max_radius", 18 * minimum(vsz))
    lo = setting("min_radius", 2 * maximum(vsz))
    st = setting("radius_step", 2 * maximum(vsz))
    return collect(hi:-st:lo)
end

log_env("vsharp-qsmjl")
fl, _ = vsharp(f, mask, vsz; r=radii(vsz), thr=setting("threshold", 0.05))
writevol("localfield.nii.gz", fl, ref)
