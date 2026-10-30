# Precompile workload for the ROMEO / MriResearchTools / TGV sysimage (mritools.so) of the QSM-CI
# Julia base image.
#
# Runs every call the Julia submissions' recon.jl files make, with the argument types they use
# (Float64 fields for QSM.jl, Float32 for TGV, the ROMEO command line on NIfTI files), on a small
# synthetic volume, so PackageCompiler bakes the compiled code into the sysimage and a run does not
# spend its first minute in the JIT. It only exercises code paths; its numbers mean nothing.
using NIfTI, JSON, FFTW, LinearAlgebra
using ROMEO, MriResearchTools, QuantitativeSusceptibilityMappingTGV, CLEARSWI
using ArgParse   # loads ROMEO's RomeoApp extension (the `romeo` command line)

const tmp = mktempdir()
n = (24, 22, 20)
vsz = (1.0, 1.0, 1.2)
bdir = (0.0, 0.1, 0.995)
mask = falses(n); mask[5:end-4, 5:end-4, 4:end-3] .= true
field = [0.05 * sin(i / 3) * cos(j / 4) + 0.01 * k for i in 1:n[1], j in 1:n[2], k in 1:n[3]]
TEs = [0.004, 0.008, 0.012]
phase4 = cat((angle.(cis.(2pi * 42.576 * 3 * te .* field .+ 0.3)) for te in TEs)...; dims=4)
mag4 = cat((exp(-te / 0.03) .* (1 .+ 0.1 .* rand(n...)) for te in TEs)...; dims=4)

# NIfTI I/O, as the recon.jl files do it (gzip, Float32 out, header copied from the mask).
ref = NIVolume(Float32.(mask)); ref.header.pixdim = (1f0, Float32.(vsz)..., 1f0, 1f0, 1f0, 1f0)
niwrite(joinpath(tmp, "mask.nii.gz"), NIVolume(ref.header, ref.extensions, UInt8.(mask)))
niwrite(joinpath(tmp, "phase.nii.gz"), NIVolume(ref.header, ref.extensions, Float32.(phase4)))
niwrite(joinpath(tmp, "magnitude.nii.gz"), NIVolume(ref.header, ref.extensions, Float32.(mag4)))
m = niread(joinpath(tmp, "mask.nii.gz")); _ = Float64.(m.raw) .> 0.5
p = niread(joinpath(tmp, "phase.nii.gz")); _ = Float64.(p.raw)
JSON.parse(JSON.json(Dict("TE" => TEs, "B0" => 3.0, "B0_dir" => collect(bdir), "voxel_size" => collect(vsz))))

# ROMEO command line (MCPC-3D-S + unwrapping + B0), as romeo-romeojl calls it.
TEms = string.(1000 .* TEs)
base = ["-p", joinpath(tmp, "phase.nii.gz"), "-m", joinpath(tmp, "magnitude.nii.gz"), "-t", TEms...,
        "-k", joinpath(tmp, "mask.nii.gz"), "-B", "B0", "--no-phase-rescale"]
ROMEO.unwrapping_main([base..., "-o", joinpath(tmp, "r1")])
ROMEO.unwrapping_main([base..., "-o", joinpath(tmp, "r2"), "-i", "-g", "-w", "romeo4",
                       "--phase-offset-smoothing-sigma-mm", "4", "4", "4", "--temporal-uncertain-unwrapping", "0.5"])
niread(joinpath(tmp, "r1", "B0.nii"))

# TGV-QSM (Float32, the package default), with each Laplacian the submission offers.
ph1 = Float32.(field .* (2pi * 42.5781 * 3 * 0.004))
for lap in (get_laplace_phase_del, get_laplace_phase_romeo, get_laplace_phase3)
    qsm_tgv(ph1, mask, collect(vsz); TE=0.004, fieldstrength=3, B0_dir=collect(bdir),
            iterations=3, laplacian=lap)
end
qsm_tgv(ph1, mask, collect(vsz); TE=0.004, fieldstrength=3, B0_dir=collect(bdir), iterations=3,
        alpha=[0.002, 0.003], erosions=3, step_size=3)

rm(tmp; recursive=true)
