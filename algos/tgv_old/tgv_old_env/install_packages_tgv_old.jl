import Pkg

println("[INFO] Activating local project environment for TGV_QSM (old)...")
Pkg.activate("/workdir/tgv_old_env")

println("[INFO] Updating registries...")
try
    Pkg.Registry.add(Pkg.RegistrySpec(url="https://github.com/JuliaRegistries/General"))
catch
    println("[INFO] Registry already exists")
end
Pkg.Registry.update()

#  Packages
Pkg.add("JSON3")
Pkg.add("NIfTI")
Pkg.add("MriResearchTools")
Pkg.add(Pkg.PackageSpec(name="ROMEO", version=v"1.1.1"))
# Add ArgParse for CLI parsing in romeo_step.jl
Pkg.add("ArgParse")

println("[INFO] Instantiating environment...")
Pkg.instantiate()
Pkg.precompile()
Pkg.status()

println("[INFO] Install finished for TGV_QSM (old)...")
