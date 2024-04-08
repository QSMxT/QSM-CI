using QSM
using NIfTI
using Statistics

println("[INFO] Starting script...")

# constants
γ = 267.52      # gyromagnetic ratio
B0 = 3          # main magnetic field strength
println("[INFO] Constants set: gyromagnetic ratio = $γ, main magnetic field strength = $B0 T")

# Assuming prior steps for data loading are handled as needed...

## concatenate nifti files
num_images = 4
println("[INFO] Loading magnitude image for echo-1 to get shape...")
nii_mag = niread("bids/sub-1/anat/sub-1_echo-1_part-mag_T2starw.nii")
phs_shape = size(Float32.(nii_mag))
mag_shape = tuple(phs_shape..., num_images)
phas_shape = tuple(phs_shape..., num_images)

mag = Array{Float32}(undef, mag_shape...)
phas = Array{Float32}(undef, phas_shape...)

println("[INFO] Concatenating magnitude and phase images...")
for i in 1:num_images
    println("[INFO] Loading images for echo $i...")
    mag_tmp = niread("bids/sub-1/anat/sub-1_echo-" * string(i) * "_part-mag_T2starw.nii")
    phas_tmp = niread("bids/sub-1/anat/sub-1_echo-" * string(i) * "_part-phase_T2starw.nii")

    mag_tmp = Float32.(mag_tmp)
    phas_tmp = Float32.(phas_tmp)

    mag[:,:,:,i] = mag_tmp
    phas[:,:,:,i] = phas_tmp
end

bdir = (0.,0.,1.)   # direction of B-field
vsz  = (1.0,1.0,1.0)   # voxel size
TEs  = [0.004,0.012,0.02,0.028]    # echo times
println("[INFO] Acquisition parameters set.")

mask = niread("bids/derivatives/qsm-forward/sub-1/anat/sub-1_mask.nii")
mask = Bool.(mask)
println("[INFO] Mask loaded.")

# unwrap phase + harmonic background field correction
println("[INFO] Unwrapping phase and correcting for harmonic background fields...")
uphas = unwrap_laplacian(phas, mask, vsz)

# convert units
println("[INFO] Converting phase units...")
@views for t in axes(uphas, 4)
    uphas[:,:,:,t] .*= inv(B0 * γ * TEs[t])
end

# remove non-harmonic background fields
println("[INFO] Removing non-harmonic background fields...")
fl, mask2 = vsharp(uphas, mask, vsz)

# dipole inversion
println("[INFO] Performing dipole inversion...")
x = rts(fl, mask2, vsz, bdir=bdir)
x = mean(x, dims = 4)
println("[INFO] Dipole inversion completed.")

ni = NIVolume(x[:,:,:]; voxel_size=vsz,
            orientation=nothing, dim_info=Integer.(vsz),
            time_step=nii_mag.header.slice_duration != false && !isempty(time_step.data) ? time_step.data[1] : 0f0)

println("[INFO] Writing output to NIfTI...")
niwrite("output/laplacian_vsharp_rts.nii.gz", ni)
println("[INFO] Process completed successfully.")
