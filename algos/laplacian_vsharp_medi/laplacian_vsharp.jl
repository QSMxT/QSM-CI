#!/usr/bin/env julia
# pipeline_laplacian.jl
#
# Führt Laplacian Unwrapping + V-SHARP aus
# und speichert die Zwischenergebnisse für den MEDI-Step.

using Pkg
Pkg.activate(@__DIR__)

using QSM
using NIfTI
using Statistics
using JSON

println("[INFO] Starting Laplacian V-SHARP pipeline...")

# --- Load input JSON ---
input_file = "inputs.json"
json_data = JSON.parsefile(input_file)
mask_file = json_data["mask"]
mag_files = json_data["mag_nii"]
phas_files = json_data["phase_nii"]
TEs = json_data["EchoTime"]
B0 = json_data["MagneticFieldStrength"]

# constants
γ = 267.52 # gyromagnetic ratio (MHz/T)
bdir = (0.,0.,1.)   # direction of B-field
vsz  = (1.0, 1.0, 1.0)   # voxel size (assuming isotropic)

# --- Load magnitude and phase ---
println("[INFO] Loading magnitude image for echo-1 to get shape...")
nii_mag = niread(mag_files[1])
shape3d = size(Float32.(nii_mag))
n_echo = length(mag_files)

mag  = Array{Float32}(undef, shape3d..., n_echo)
phas = Array{Float32}(undef, shape3d..., n_echo)

for i in 1:n_echo
    println("[INFO] Loading echo $i...")
    mag[:,:,:,i]  = Float32.(niread(mag_files[i]))
    phas[:,:,:,i] = Float32.(niread(phas_files[i]))
end

# --- Load mask ---
println("[INFO] Loading mask: $mask_file")
mask = Bool.(niread(mask_file))

# --- Step 1: Phase Unwrapping ---
println("[INFO] Performing Laplacian phase unwrapping...")
uphas = unwrap_laplacian(phas, mask, vsz)

# --- Step 2: Convert to fieldmap (Hz) ---
println("[INFO] Converting to frequency shift (Hz)...")
@views for t in axes(uphas, 4)
    uphas[:,:,:,t] .*= inv(B0 * γ * TEs[t])
end
fieldmap = mean(uphas, dims=4)[:,:,:,1]

# --- Step 3: Background field removal (V-SHARP) ---
println("[INFO] Running V-SHARP...")
fl, mask2 = vsharp(fieldmap, mask, vsz)

# --- Save Laplacian outputs for MEDI ---
println("[INFO] Saving Laplacian outputs for MEDI...")

mkpath("output_laplacian")

niwrite(joinpath("output_laplacian", "fieldmap_local.nii"), Float32.(fl))
niwrite(joinpath("output_laplacian", "mask.nii"), Int16.(mask2))  # save as binary mask
niwrite(joinpath("output_laplacian", "magnitude.nii"), Float32.(mag[:,:,:,1]))

println("[INFO] Laplacian pipeline finished successfully.")
println("[INFO] Results written to: output_laplacian/")
