#!/usr/bin/env julia
# combine_to_4d.jl
# Combine 3D multi-echo phase images and magnitude images into a 4D time-series

import Pkg
Pkg.activate("/workdir/tgv_old_env")

using JSON3, NIfTI

if length(ARGS) < 1
    println("Usage: julia combine_to_4d.jl <output_dir>")
    exit(1)
end

outdir = ARGS[1]
isdir(outdir) || mkpath(outdir)

println("[INFO] Loading inputs.json...")
d = JSON3.read(open("inputs.json"))

#  JSON3.Array to Vector{String}
function resolve_path(f)
    isabspath(f) ? f : joinpath(pwd(), f)
end

phase_files = collect(String.(d["phase_nii"]))
mag_files   = collect(String.(d["mag_nii"]))

# Resolve all file paths to absolute paths
phase_files = [resolve_path(f) for f in phase_files]
mag_files   = [resolve_path(f) for f in mag_files]

println("[INFO] Phase files: ", join(phase_files, ", "))
println("[INFO] Magnitude files: ", join(mag_files, ", "))

function combine_to_4d(in_files::Vector{String}, out_file::String)
    imgs  = [NIfTI.niread(f) for f in in_files]
    datas = [Array(img) for img in imgs]

    shapes = unique(size.(datas))
    if length(shapes) != 1
        error("[ERROR] Inconsistent input shapes: $shapes")
    end

    stacked = cat(datas...; dims=ndims(datas[1])+1)

# Header from first Echo
hdr = imgs[1].header
desc = hdr.descrip
if desc isa NTuple{80,UInt8}
    desc = String(collect(desc))
end

# --- Create Volume with voxel + qform ---
out_img = NIfTI.NIVolume(
    stacked;
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

# --- Set affine (srow) ---
out_img.header.srow_x     = hdr.srow_x
out_img.header.srow_y     = hdr.srow_y
out_img.header.srow_z     = hdr.srow_z
out_img.header.sform_code = hdr.sform_code

# --- Set qform code as well ---
out_img.header.qform_code = hdr.qform_code

# --- Save ---
NIfTI.niwrite(out_file, out_img)

println("[INFO] Created 4D NIfTI: $out_file with size ", size(stacked))

end


combine_to_4d(phase_files, joinpath(outdir, "sub-1_phase_4D.nii"))
combine_to_4d(mag_files,   joinpath(outdir, "sub-1_mag_4D.nii"))

println("[INFO] Saved:")
println("  → $(joinpath(outdir, "sub-1_phase_4D.nii"))")
println("  → $(joinpath(outdir, "sub-1_mag_4D.nii"))")
println("[INFO] Converting to 4D done.")
