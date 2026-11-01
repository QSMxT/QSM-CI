# QSM-CI glue shared by the Julia submissions (*-qsmjl, romeo-romeojl, tgv-tgvjl). Each folder is
# mounted on its own at /algo, so every one carries an identical copy of this file
# (tests/test_julia_submissions.py checks they stay identical). It reads the contract inputs, applies
# `--set` overrides, fixes the thread counts, and writes Float32 NIfTI on the mask's grid. No
# algorithm code lives here: recon.jl calls the authors' package functions directly.
using NIfTI, JSON, FFTW, LinearAlgebra

const IN = length(ARGS) >= 1 ? ARGS[1] : "/input"
const OUT = length(ARGS) >= 2 ? ARGS[2] : "/output"
const PARAMS = JSON.parsefile(joinpath(IN, "params.json"))
const CONFIG = let f = joinpath(IN, "config.json")
    isfile(f) ? JSON.parsefile(f) : Dict{String,Any}()
end

# γ/2π in MHz/T, QSM-CI's contract value: ppm = Hz · 1e6 / (γ · B0).
const GAMMA_MHZ = 42.576

# Thread counts are fixed for reproducibility: Julia's (run.sh starts Julia with
# JULIA_NUM_THREADS), FFTW's (QSM.jl reads QSM.FFTW_NTHREADS, which it otherwise sets from the
# core count of the machine the package was compiled on), and BLAS (single-threaded).
const NTHREADS = Threads.nthreads()
FFTW.set_num_threads(NTHREADS)
BLAS.set_num_threads(1)

"""`--set NAME=VALUE` override for `name`, converted to the type of `default` (`nothing`: as given)."""
function setting(name, default)
    haskey(CONFIG, name) || return default
    v = CONFIG[name]
    default === nothing && return v
    if default isa Bool
        return v isa Bool ? v : parse(Bool, lowercase(string(v)))
    elseif default isa Integer
        return v isa Integer ? Int(v) : round(Int, parse(Float64, string(v)))
    elseif default isa Real
        return v isa Real ? Float64(v) : parse(Float64, string(v))
    elseif default isa AbstractString
        return string(v)
    end
    return v
end

"""Read `/input/<name>` as Float64, with the header's scaling applied. Returns (data, volume)."""
function readvol(name)
    nii = niread(joinpath(IN, name))
    x = Float64.(nii.raw)
    s, b = Float64(nii.header.scl_slope), Float64(nii.header.scl_inter)
    if s != 0 && !(s == 1 && b == 0)
        x .= x .* s .+ b
    end
    return x, nii
end

readmask() = (m = readvol("mask.nii.gz"); (m[1] .> 0.5, m[2]))
"""Voxel size (mm) from the mask's NIfTI header (`pixdim`), the source qsmxt (and NIfTI.jl's
`voxel_size`) uses, not params.json: the two can differ in the last float32 bit (the KKI travelling
head's z is 0.99999994 in the header, 1.0 in params.json), and QSM.jl's SMV box padding,
`cld(r, minimum(vsz))`, turns that into a different FFT box (vsharp-qsmjl: 1.19 % NRMSE)."""
voxel_size() = Tuple(Float64.(niread(joinpath(IN, "mask.nii.gz")).header.pixdim[2:4]))
b0_dir() = (d = Float64.(PARAMS["B0_dir"]); Tuple(d ./ norm(d)))
echo_times() = Float64.(PARAMS["TE"] isa AbstractVector ? PARAMS["TE"] : [PARAMS["TE"]])
field_strength() = Float64(PARAMS["B0"])

"""Write `x` (3D) as Float32 `/output/<name>`, on the grid and affine of `ref` (the mask)."""
function writevol(name, x, ref)
    h = deepcopy(ref.header)
    h.scl_slope = 1
    h.scl_inter = 0
    y = Float32.(x)
    y[.!isfinite.(y)] .= 0
    niwrite(joinpath(OUT, name), NIVolume(h, NIfTI.NIfTIExtension[], y))
end

"""One line on stderr recording the run's environment (thread counts, CPU) in the run log."""
log_env(what) = println(stderr, "[qsm-ci] $(what): julia $(VERSION), $(NTHREADS) threads (FFTW $(NTHREADS), BLAS ",
                        "$(BLAS.get_num_threads())), CPU $(Sys.CPU_NAME), $(Sys.CPU_THREADS) logical CPUs")
