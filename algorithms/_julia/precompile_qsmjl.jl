# Precompile workload for the QSM.jl sysimage (qsmjl.so) of the QSM-CI Julia base image.
#
# Runs every call the Julia submissions' recon.jl files make, with the argument types they use
# (Float64 fields for QSM.jl, Float32 for TGV, the ROMEO command line on NIfTI files), on a small
# synthetic volume, so PackageCompiler bakes the compiled code into the sysimage and a run does not
# spend its first minute in the JIT. It only exercises code paths; its numbers mean nothing.
using NIfTI, JSON, FFTW, LinearAlgebra
using QSM

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

# QSM.jl: dipole inversions, background removal, Laplacian unwrapping, echo combination.
QSM.FFTW_NTHREADS[] = Threads.nthreads()
for f in (tkd, tsvd)
    f(field, mask, vsz; bdir=bdir, thr=0.15)
end
for reg in (:identity, :gradient, :laplacian)
    tikh(field, mask, vsz; bdir=bdir, lambda=1e-2, reg=reg)
end
tv(field, mask, vsz; bdir=bdir, maxit=3)
rts(field, mask, vsz; bdir=bdir, maxit=3)
nltv(field, mask, vsz; bdir=bdir, maxit=3)
nltv(field, mask, vsz; W=mask .* 1.0, bdir=bdir, maxit=3)
sharp(field, mask, vsz; r=3.0, thr=0.05)
vsharp(field, mask, vsz; r=[4.0, 3.0, 2.0], thr=0.05)
vsharp(field, mask, vsz)
ismv(field, mask, vsz; r=2.0, maxit=3)
for s in (:dct, :fft, :mgpcg)
    uph = unwrap_laplacian(phase4, mask, vsz; solver=s)
    unwrap_laplacian(phase4[:, :, :, 1], mask, vsz; solver=s)
    multi_echo_average(uph; TEs=TEs, W=mag4, mask=mask)
    multi_echo_linear_fit(uph, TEs; W=mag4, mask=mask, phase_offset=true)
    multi_echo_linear_fit(uph, TEs; W=mag4, mask=mask, phase_offset=false)
end

rm(tmp; recursive=true)
