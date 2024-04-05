using QSM
using NIfTI
using Statistics

# constants
γ = 267.52      # gyromagnetic ratio
B0 = 3          # main magnetic field strength

# load 3D single-, or multi-echo data using your favourite
# package, e.g. MAT.jl, NIfTI.jl, ParXRec.jl, ...

## concatenate nifti files
num_images = 4
nii_mag = niread("./../../bids/sub-simulated-sources/anat/sub-simulated-sources_echo-1_part-mag_T2starw.nii")
phs_shape = size(Float32.(nii_mag))
mag_shape = tuple(phs_shape..., num_images)
phas_shape = tuple(phs_shape..., num_images)

mag = Array{Float32}(undef, mag_shape...)
phas = Array{Float32}(undef, phas_shape...)

for i in 1:num_images
    mag_tmp = niread("./../../bids/sub-simulated-sources/anat/sub-simulated-sources_echo-" * string(i) * "_part-mag_T2starw.nii")
    phas_tmp = niread("./../../bids/sub-simulated-sources/anat/sub-simulated-sources_echo-" * string(i) * "_part-phase_T2starw.nii")

    mag_tmp = Float32.(mag_tmp)
    phas_tmp = Float32.(phas_tmp)

    mag[:,:,:,i] = mag_tmp
    phas[:,:,:,i] = phas_tmp
end

bdir = (0.,0.,1.)   # direction of B-field
vsz  = (1.0,1.0,1.0)   # voxel size
TEs  = [0.004,0.012,0.02,0.028]    # echo times


mask = niread("./../../bids/derivatives/qsm-forward/sub-simulated-sources/anat/sub-simulated-sources_mask.nii")
mask = Bool.(mask)

# unwrap phase + harmonic background field correction
uphas = unwrap_laplacian(phas, mask, vsz)

# convert units
@views for t in axes(uphas, 4)
    uphas[:,:,:,t] .*= inv(B0 * γ * TEs[t])
end

# remove non-harmonic background fields
fl, mask2 = vsharp(uphas, mask, vsz)

# dipole inversion
x = rts(fl, mask2, vsz, bdir=bdir)
x = mean(x, dims = 4)


ni = NIVolume(x[:,:,:]; voxel_size=vsz,
            orientation=nothing, dim_info=Integer.(vsz),
            time_step=nii_mag.header.slice_duration != false && !isempty(time_step.data) ? time_step.data[1] : 0f0)

niwrite("./../../recons/qsmjl_unwrapLaplacian_vsharp_rts/qsmjl_unwrapLaplacian_vsharp_rts.nii.gz", ni)
