# QSM-CI `bfr+dipole` stage: TGV (QuantitativeSusceptibilityMappingTGV.jl). The authors' Julia code (QuantitativeSusceptibilityMappingTGV.jl at 6c0886a (0.5.2)), called directly; the
# pinned environment is the base image algorithms/_julia (Manifest committed there).
# Glue (inputs, `--set` overrides, thread counts, output) is in qsmci_io.jl, identical in every
# Julia submission. Parameters and their QSM.rs-matched values: README.md.
include(joinpath(@__DIR__, "qsmci_io.jl"))
using QuantitativeSusceptibilityMappingTGV

field, _ = readvol("totalfield.nii.gz")
mask, ref = readmask()
vsz, B0 = collect(voxel_size()), field_strength()
log_env("tgv-tgvjl")

# The package takes one echo's phase (rad) at TE and divides chi by 2pi*TE*B0*42.5781 at the
# end; scaling the ppm field to phase with the package's own constant makes the two cancel.
te = setting("te", nothing)
te = te === nothing || te == "first echo" ? echo_times()[1] : Float64(te isa AbstractString ? parse(Float64, te) : te)
phase = field .* (2pi * 42.5781 * B0 * te)

reg = setting("regularization", 2)
alpha = QuantitativeSusceptibilityMappingTGV.get_default_alpha(reg)          # [alpha0, alpha1]
haskey(CONFIG, "alpha0") && (alpha[1] = setting("alpha0", 0.0))
haskey(CONFIG, "alpha1") && (alpha[2] = setting("alpha1", 0.0))
step_size = setting("step_size", 3.0)
iterations = haskey(CONFIG, "iterations") ? setting("iterations", 0) :
             QuantitativeSusceptibilityMappingTGV.get_default_iterations(vsz, step_size)
# `unwrapped`: the package's own discrete Laplacian (laplacian_kernel, as get_laplace_phase_romeo
# applies it) of the phase as given. The input here is an unwrapped field, so ROMEO's unwrap step
# (`romeo`) only re-wraps it at the scaled phase's large values and adds +-2pi jumps; `unwrapped`
# is get_laplace_phase_romeo without that step, which is what the package computes on a phase
# ROMEO has already unwrapped.
TGV = QuantitativeSusceptibilityMappingTGV
lap_unwrapped(phase, res) = TGV.imfilter(phase, TGV.laplacian_kernel(res))
lap = Dict("del" => get_laplace_phase_del, "romeo" => get_laplace_phase_romeo,
           "phase3" => get_laplace_phase3, "unwrapped" => lap_unwrapped)[setting("laplacian", "del")]
println(stderr, "[qsm-ci] qsm_tgv TE=$(te) alpha=$(alpha) iterations=$(iterations) step_size=$(step_size)")

chi = qsm_tgv(phase, mask, vsz; TE=te, fieldstrength=B0, B0_dir=collect(b0_dir()), alpha=alpha,
              step_size=step_size, iterations=iterations, erosions=setting("erosions", 3),
              correct_laplacian=setting("correct_laplacian", true), laplacian=lap)
writevol("chimap.nii.gz", chi, ref)
