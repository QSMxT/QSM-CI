# QSM-CI `field-mapping` stage: ROMEO field mapping (ROMEO.jl). The authors' Julia code (ROMEO.jl at 08776d4 and MriResearchTools.jl at 771eadf), called directly; the
# pinned environment is the base image algorithms/_julia (Manifest committed there).
# Glue (inputs, `--set` overrides, thread counts, output) is in qsmci_io.jl, identical in every
# Julia submission. Parameters and their QSM.rs-matched values: README.md.
include(joinpath(@__DIR__, "qsmci_io.jl"))
using ROMEO, MriResearchTools, ArgParse   # ArgParse loads ROMEO's command line (RomeoApp)

mask, ref = readmask()
TEs, B0 = echo_times(), field_strength()
log_env("romeo-romeojl")

sigma = setting("phase_offset_sigma_mm", 7.0)
sigma = string.(sigma isa AbstractVector ? Float64.(sigma) : fill(Float64(sigma), 3))
work = mktempdir()
args = ["-p", joinpath(IN, "phase.nii.gz"), "-m", joinpath(IN, "magnitude.nii.gz"),
        "-t", string.(1000 .* TEs)...,                  # the CLI takes echo times in ms
        "-k", joinpath(IN, "mask.nii.gz"),              # the contract's brain mask
        "-B", "B0",                                     # combined B0 map, Hz
        "--no-phase-rescale",                           # the contract phase is already in rad
        "-w", setting("weights", "romeo"),
        "--template", string(setting("template", 1)),
        "--temporal-uncertain-unwrapping", string(setting("temporal_uncertain_unwrapping", 0.0)),
        "--phase-offset-correction", setting("phase_offset_correction", "on"),
        "--phase-offset-smoothing-sigma-mm", sigma...,
        "--B0-phase-weighting", setting("b0_weighting", "phase_snr"),
        "-s", string(setting("max_seeds", 1)),
        "-o", work]
setting("individual_unwrapping", false) && push!(args, "-i")
setting("correct_global", false) && push!(args, "-g")
println(stderr, "[qsm-ci] romeo ", join(args, " "))
ROMEO.unwrapping_main(args)

b0_hz = Float64.(niread(joinpath(work, "B0.nii")).raw)
writevol("totalfield.nii.gz", b0_hz ./ (GAMMA_MHZ * B0) .* mask, ref)   # Hz -> ppm
