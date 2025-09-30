#!/usr/bin/env julia
import Pkg
Pkg.activate("/workdir/tgv_old_env")

using ROMEO, MriResearchTools, ArgParse, JSON3

println("[INFO] Unwrapping with ROMEO...")

# -------------------------
# CLI Argument Parsing
# -------------------------
s = ArgParseSettings()
@add_arg_table s begin
    "--phase"
        help = "4D phase NIfTI"
        arg_type = String
    "--mag"
        help = "4D magnitude NIfTI"
        arg_type = String
    "--mask"
        help = "Brain mask NIfTI"
        arg_type = String
    "--compute-B0"
        help = "Output path for B0 fieldmap"
        arg_type = String
        required = true
    "--correct-global"
        help = "Enable global phase correction"
        action = :store_true
    "--phase-offset-correction"
        help = "Method for phase offset correction (e.g. bipolar)"
        arg_type = String
        default = ""
end

parsed_args = parse_args(ARGS, s)

# -------------------------
# Load EchoTimes from inputs.json
# -------------------------
inputs_file = "inputs.json"   
if !isfile(inputs_file)
    error("[ERROR] inputs.json not found in current dir")
end

d = JSON3.read(open(inputs_file))
TEs_sec = Float64.(d["EchoTime"])   # in seconds
TEs_ms  = TEs_sec .* 1000.0         # convert to ms

println("[INFO] Found EchoTimes in inputs.json: ", TEs_ms)

# -------------------------
# Run ROMEO
# -------------------------
@time msg = ROMEO.unwrapping_main([
    "--phase", parsed_args["phase"],
    "--mag",   parsed_args["mag"],
    "--mask",  parsed_args["mask"],
    "-t",      "[" * join(string.(TEs_ms), " ") * "]",
    "--compute-B0", parsed_args["compute-B0"],
    "--correct-global",
    "--phase-offset-correction", parsed_args["phase-offset-correction"]
])

println(msg)
println("[INFO] ROMEO step finished successfully.")
