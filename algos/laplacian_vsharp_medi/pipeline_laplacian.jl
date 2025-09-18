#!/usr/bin/env julia

using Pkg
Pkg.activate("/workdir/laplacian_env")  # nur lokales Laplacian-Env wird genutzt
println("Activated environment: ", Base.active_project())

using ArgParse
using JSON
using NIfTI
using QSM
using Statistics

println("[INFO] Starting Laplacian V-SHARP pipeline...")

# --- Argument parsing ---
s = ArgParseSettings()
@add_arg_table! s begin
    "--input"
        help = "Folder containing inputs.json"
        arg_type = String
        required = true
    "--output"
        help = "Output folder for Laplacian results"
        arg_type = String
        required = true
end
args = parse_args(s)

input_dir  = args["input"]
output_dir = args["output"]
mkpath(output_dir)

# --- Load inputs.json ---
println("[INFO] Loading input JSON...")
input_file = joinpath(input_dir, "inputs.json")
if !isfile(input_file)
    error("[ERROR] inputs.json not found in $input_dir")
end

json_data = JSON.parsefile(input_file)
mask_file = json_data["mask"]
mag_files = json_data["mag_nii"]
phas_files = json_data["phase_nii"]
TEs       = json_data["EchoTime"]
B0        = json_data["MagneticFieldStrength"]

# --- Constants ---
γ = 267.52 # gyromagnetic ratio (MHz/T)
vsz  = (1.0, 1.0, 1.0)

# --- Load magnitude & phase ---
println("[INFO] Loading magnitude and phase images...")
nii_mag = niread(mag_files[1])
shape3d = size(Float32.(nii_mag))
n_echo  = length(mag_files)

mag  = Array{Float32}(undef, shape3d..., n_echo)
phas = Array{Float32}(undef, shape3d..., n_echo)

for i in 1:n_echo
    println("[DEBUG] Loading echo $i...")
    mag[:,:,:,i]  = Float32.(niread(mag_files[i]))
    phas[:,:,:,i] = Float32.(niread(phas_files[i]))
end

# --- Load mask ---
println("[INFO] Loading mask: $mask_file")
mask = Bool.(niread(mask_file))
println("[INFO] Mask loaded.")

# --- Step 1: Laplacian phase unwrapping ---
println("[INFO] Performing Laplacian phase unwrapping...")
uphas = unwrap_laplacian(phas, mask, vsz)

# --- Step 2: Convert to frequency shift (Hz) ---
println("[INFO] Converting to frequency shift (Hz)...")
@views for t in axes(uphas, 4)
    uphas[:,:,:,t] .*= inv(B0 * γ * TEs[t])
end
fieldmap = mean(uphas, dims=4)[:,:,:,1]

# --- Step 3: Background field removal (V-SHARP) ---
println("[INFO] Running V-SHARP...")
fl, mask2 = vsharp(fieldmap, mask, vsz)

# --- Step 4: Save outputs for MEDI ---
println("[INFO] Saving Laplacian outputs for MEDI...")

# fieldmap_local.nii
fieldmap_vol = NIVolume(Float32.(fl); voxel_size=(1.0,1.0,1.0))
niwrite(joinpath(output_dir, "fieldmap_local.nii"), fieldmap_vol)

# mask.nii
mask_vol = NIVolume(Int16.(mask2); voxel_size=(1.0,1.0,1.0))
niwrite(joinpath(output_dir, "mask.nii"), mask_vol)

# magnitude.nii (first echo)
mag_vol = NIVolume(Float32.(mag[:,:,:,1]); voxel_size=(1.0,1.0,1.0))
niwrite(joinpath(output_dir, "magnitude.nii"), mag_vol)

println("[INFO] Laplacian outputs saved successfully:")
println("       fieldmap_local.nii")
println("       mask.nii")
println("       magnitude.nii")
println("[INFO] Laplacian pipeline finished.")