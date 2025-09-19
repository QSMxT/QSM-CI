import Pkg

#install_packages_medi

#local env for MEDI
println("[INFO] Activating local project environment...")
Pkg.activate("/workdir/medi_env")

println("[INFO] Updating registries...")
try
    Pkg.Registry.add(Pkg.RegistrySpec(url="https://github.com/JuliaRegistries/General"))
catch
    println("[INFO] Registry already exists")
end
Pkg.Registry.update()

# --- Fix broken packages --- delete then
for broken in ["NIfTI", "PtrArrays"]
    try
        Pkg.rm(broken; force=true)
        println("[INFO] Removed possible broken $broken")
    catch
        println("[INFO] No broken $broken to remove")
    end
end

# --- Add packages cleanly ---
Pkg.add("ArgParse") 
Pkg.add("FFTW")
Pkg.add("Statistics")
Pkg.add("LinearAlgebra")
Pkg.add("MriResearchTools")
Pkg.add("Images")

println("[INFO] Instantiating environment...")
Pkg.instantiate()
Pkg.precompile()
Pkg.status()
println("[INFO] Install finished...")
