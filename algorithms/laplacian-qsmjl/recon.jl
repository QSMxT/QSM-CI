# QSM-CI `field-mapping` stage: Laplacian field mapping (QSM.jl). The authors' Julia code (QSM.jl at fde4b92 (v0.5.4)), called directly; the
# pinned environment is the base image algorithms/_julia (Manifest committed there).
# Glue (inputs, `--set` overrides, thread counts, output) is in qsmci_io.jl, identical in every
# Julia submission. Parameters and their QSM.rs-matched values: README.md.
include(joinpath(@__DIR__, "qsmci_io.jl"))
using QSM
QSM.FFTW_NTHREADS[] = NTHREADS

phas, _ = readvol("phase.nii.gz")
mag, _ = readvol("magnitude.nii.gz")
mask, ref = readmask()
vsz, TEs, B0 = voxel_size(), echo_times(), field_strength()
ndims(phas) == 3 && (phas = reshape(phas, size(phas)..., 1); mag = reshape(mag, size(mag)..., 1))
solver = Symbol(setting("solver", "dct"))
combine = setting("combine", "average")
log_env("laplacian-qsmjl")

setting("mask_phase", false) && (phas .*= mask)
uphas = unwrap_laplacian(phas, mask, vsz; solver=solver)
if setting("demean", false)
    for t in axes(uphas, 4)
        u = @view uphas[:, :, :, t]
        u .-= sum(u[mask]) / count(mask)
    end
end

rad_per_ppm(te) = 2pi * GAMMA_MHZ * B0 * te     # phase (rad) per ppm of field at echo time te
if size(uphas, 4) == 1
    fieldmap = uphas[:, :, :, 1] ./ rad_per_ppm(TEs[1])
elseif combine == "average"
    # QSM.jl's README: scale each echo to ppm by its own TE, then QSM.jl's weighted average,
    # sum(TE*W*f)/sum(TE*W) with W = magnitude, i.e. sum(mag*phase)/sum(mag*TE).
    for t in axes(uphas, 4)
        uphas[:, :, :, t] ./= rad_per_ppm(TEs[t])
    end
    fieldmap = multi_echo_average(uphas; TEs=TEs, W=mag, mask=mask)
elseif combine == "linear-fit"
    slope, _ = multi_echo_linear_fit(uphas, TEs; W=mag, mask=mask, phase_offset=true)   # rad/s
    fieldmap = slope ./ (2pi * GAMMA_MHZ * B0)
else
    error("combine must be average or linear-fit, got $(combine)")
end
writevol("totalfield.nii.gz", fieldmap .* mask, ref)
