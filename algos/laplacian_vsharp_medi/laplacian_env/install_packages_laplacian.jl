#!/usr/bin/env julia
using Pkg

# local env for Laplacian
Pkg.activate(@__DIR__)
ENV["JULIA_PKG_PRECOMPILE_AUTO"] = 0

println("[INFO] Installing Laplacian packages...")


Pkg.add("ArgParse")   # for --input / --output 
Pkg.add("JSON")
Pkg.add(Pkg.PackageSpec(name="FFTW", version=v"1.8"))
Pkg.add(Pkg.PackageSpec(name="QSM", version=v"0.5.4"))
Pkg.add(Pkg.PackageSpec(name="NIfTI", version=v"0.6.0"))
Pkg.add("Statistics")

println("[INFO] Instantiating...")
Pkg.instantiate()
Pkg.precompile()
Pkg.status()

println("[INFO] Laplacian environment ready.")
