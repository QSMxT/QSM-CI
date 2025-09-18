#!/usr/bin/env julia

using Pkg
Pkg.activate(@__DIR__)

using ArgParse
include("medi.jl")

function main()
    # argument setting 
    s = ArgParseSettings()

    @add_arg_table! s begin
        "--input"
            help = "Input folder"
            arg_type = String
            required = true
        "--output"
            help = "Output folder"
            arg_type = String
            required = true
    end

    # parse arguments
    args = parse_args(s)

    input_dir = args["input"]
    output_dir = args["output"]

    if isempty(input_dir) || isempty(output_dir)
        error("[ERROR] Input or output directory is empty. Please provide valid paths.")
    end

    println("[INFO] Starting MEDI pipeline with input: $input_dir, output: $output_dir...")

    # run pipeline – this already writes chimap.nii.gz
    run_medi_pipeline(input_dir, output_dir)

    println("[INFO] MEDI pipeline completed. Output: $(joinpath(output_dir, "chimap.nii.gz"))")
end

main()
