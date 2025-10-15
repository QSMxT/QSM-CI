#!/usr/bin/env julia
# Convert B0 fieldmap (Hz) to radians at arbitrary TE

import Pkg
Pkg.activate("/workdir/tgv_old_env")

using NIfTI, JSON3

if length(ARGS) < 2
    println("Usage: julia fieldmap_to_radians.jl <B0_fieldmap.nii> <output_dir>")
    exit(1)
end

b0_file = abspath(ARGS[1])           
outdir  = abspath(ARGS[2])
isdir(outdir) || mkpath(outdir)

# --- EchoTime + B0 from inputs.json ---
json_file = joinpath(dirname(outdir), "inputs.json")
if !isfile(json_file)
    println("[ERROR] inputs.json not found: $json_file")
    exit(1)
end
data = JSON3.read(open(json_file, "r"), Dict)

TE = Float64(data["EchoTime"][1])   
B0 = Float64(data["MagneticFieldStrength"])  
println("[INFO] Using EchoTime: $TE s")
println("[INFO] Using B0: $B0 T")



println("[INFO] Converting fieldmap to radians...")
println("  Input:  $b0_file")
println("  Output: $outdir")

# --- Load B0 Fieldmap (Hz) ---
b0_img  = NIfTI.niread(b0_file)
b0_data = Array(b0_img)  # in Hz
hdr     = b0_img.header

# --- Convert Hz to Radians ---
radian_data = 2π .* b0_data .* TE

# --- Clean NaNs/Infs ---
n_nan = count(isnan, radian_data)
n_inf = count(isinf, radian_data)
if n_nan > 0 || n_inf > 0
    println("[WARN] Found $n_nan NaN and $n_inf Inf voxels → setting to 0.0")
    radian_data[.!isfinite.(radian_data)] .= 0.0
end

# --- Copy description safely ---
desc = hdr.descrip
if desc isa NTuple{80,UInt8}
    desc = String(collect(desc))
elseif desc isa SubString{String}
    desc = String(desc)
else
    desc = String(desc)
end

# --- New NIfTI-Volume ---
radian_volume = NIfTI.NIVolume(
    radian_data;
    voxel_size = Tuple(hdr.pixdim[2:4]),
    descrip    = desc,
    qfac       = hdr.pixdim[1],
    quatern_b  = hdr.quatern_b,
    quatern_c  = hdr.quatern_c,
    quatern_d  = hdr.quatern_d,
    qoffset_x  = hdr.qoffset_x,
    qoffset_y  = hdr.qoffset_y,
    qoffset_z  = hdr.qoffset_z
)

# --- Copy geometry from mask ---
acq = get(data, "Acquisition", nothing)
mask_filename = if !isnothing(acq) && acq != "null"
    "sub-1_acq-$(acq)_mask.nii"
else
    "sub-1_mask.nii"
end

mask_file = abspath("bids/derivatives/qsm-forward/sub-1/anat/$(mask_filename)")
println("[INFO] Looking for mask file: $mask_file")

if isfile(mask_file)
    mask_img = NIfTI.niread(mask_file)
    hdr_mask = mask_img.header

    radian_volume.header.srow_x     = hdr_mask.srow_x
    radian_volume.header.srow_y     = hdr_mask.srow_y
    radian_volume.header.srow_z     = hdr_mask.srow_z
    radian_volume.header.sform_code = hdr_mask.sform_code
    radian_volume.header.qform_code = hdr_mask.qform_code
    radian_volume.header.pixdim     = hdr_mask.pixdim
    radian_volume.header.xyzt_units = hdr_mask.xyzt_units

    println("[INFO] Copied qform/sform geometry from mask: $mask_file")
else
    println("[WARN] Mask file not found: $mask_file (skipping geometry copy)")
end

# --- Save ---
out_file = joinpath(outdir, "sub-1_radians.nii")
NIfTI.niwrite(out_file, radian_volume)

println("[INFO] Saved radians fieldmap → $out_file")
