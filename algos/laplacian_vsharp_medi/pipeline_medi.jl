#!/usr/bin/env julia

# pipeline_medi.jl

using Pkg
Pkg.activate("/workdir/medi_env")
println("Activated environment: ", Base.active_project())

using ArgParse
using NIfTI

include("medi.jl")   # contains run_medi_from_laplacian

function main()
    # --- Argument parsing ---
    s = ArgParseSettings()
    @add_arg_table! s begin
        "--input"
            help = "Input folder (must contain Laplacian outputs: fieldmap_local.nii, mask.nii, magnitude.nii)"
            arg_type = String
            required = true
        "--output"
            help = "Output folder"
            arg_type = String
            required = true
    end
    args = parse_args(s)

    input_dir  = args["input"]
    output_dir = args["output"]

    if isempty(input_dir) || isempty(output_dir)
        error("[ERROR] Input or output directory is empty. Please provide valid paths.")
    end

    println("[INFO] Starting MEDI pipeline with Laplacian input: $input_dir")

    # --- Expected Laplacian outputs ---
    rdf_path  = joinpath(input_dir, "fieldmap_local.nii")
    mask_path = joinpath(input_dir, "mask.nii")
    mag_path  = joinpath(input_dir, "magnitude.nii")

    for path in (rdf_path, mask_path, mag_path)
        if !isfile(path)
            error("[ERROR] Required file not found: $path")
        end
    end

    # --- Load NIfTI files ---
    rdf_nii  = niread(rdf_path)
    mask_nii = niread(mask_path)
    mag_nii  = niread(mag_path)

    rdf  = rdf_nii.raw
    mask = Bool.(mask_nii.raw)
    imag = mag_nii.raw

    # --- Extract voxel size ---
    voxel_size = Tuple(Float64.(mag_nii.header.pixdim[2:4]))
    println("[INFO] Voxel size: $voxel_size (converted to Float64)")

    # --- Run MEDI reconstruction ---
    run_medi_from_laplacian(rdf, imag, mask, voxel_size, output_dir; header=mag_nii.header)

    # --- Final check ---
    final_out = joinpath(output_dir, "chimap.nii.gz")
    if isfile(final_out)
        println("[INFO] MEDI pipeline completed successfully. Result saved: $final_out")
    else
        println("[ERROR] MEDI pipeline finished but no chimap.nii.gz found!")
    end
end

main()
