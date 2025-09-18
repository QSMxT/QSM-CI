using FFTW
using Statistics
using LinearAlgebra
using MriResearchTools
using NIfTI

include("fgrad.jl")
include("bdiv.jl")
include("sphere_kernel.jl")
include("dipole_kernel.jl")
include("dataterm_mask.jl")
include("gradient_mask.jl")
include("cgsolve.jl")

"""
Simplified implementation of Morphology Enabled Dipole Inversion (MEDI).
"""
function MEDI_L1(
    RDF, N_std, iMag, Mask, voxel_size::NTuple{3,<:Real};
    lambda=1000, B0_dir=(0, 0, 1), merit=false, smv=false, radius=5.0,
    data_weighting=1, gradient_weighting=1, percentage=0.9,
    cg_max_iter=1, cg_tol=0.01, max_iter=1, tol_norm_ratio=0.1
)
    #Cast voxel_size to Float64
    voxel_size = Tuple(Float64.(voxel_size))

    # Ensure N_std is masked
    N_std = N_std .* float.(Mask)
    tempn = copy(N_std)

    println("[INFO] Generating dipole kernel...")
    D = dipole_kernel(size(RDF), voxel_size, B0_dir, "kspace")

    # Optional SMV
    if smv
        println("[INFO] Applying SMV...")
        SphereK = sphere_kernel(size(RDF), voxel_size, radius)
        Mask = SMV(Mask, SphereK)[1] .> 0.999
        D .= (1 .- SphereK) .* D
        RDF .= RDF .- SMV(RDF, SphereK)[1]
        RDF .= RDF .* Mask
        tempn .= sqrt.(SMV(tempn.^2, SphereK)[1] .+ tempn.^2)
    end

    println("[INFO] Generating data weighting...")
    m = dataterm_mask(data_weighting, tempn, Mask)
    b0 = m .* exp.(im .* RDF)

    println("[INFO] Generating gradient weighting...")
        # Ensure voxel_size matches iMag type
        vtype = eltype(iMag)
        voxel_size_cast = (vtype(voxel_size[1]), vtype(voxel_size[2]), vtype(voxel_size[3]))
        wG = gradient_mask(gradient_weighting, iMag, Mask, fgrad, voxel_size_cast, percentage)

    # Helper convolution
    Dconv(dx) = real(ifft(D .* fft(dx)))

    # Gauss–Newton solver
    function gaussnewton()
        iter = 0
        χ = zeros(Float64, size(RDF))
        res_norm_ratio = Inf
        cost_data_history = zeros(Float64, max_iter)
        cost_reg_history = zeros(Float64, max_iter)

        while (res_norm_ratio > tol_norm_ratio) && (iter < max_iter)
            iter += 1

            Vr = 1 ./ sqrt.(abs.(wG .* fgrad(real(χ), voxel_size)).^2 .+ 1e-6)
            w = m .* exp.(im .* real(ifft(D .* fft(χ))))

            reg0 = (dx) -> bdiv(wG .* (Vr .* (wG .* fgrad(real(dx), voxel_size))), voxel_size)
            fidelity(dx) = Dconv(conj(w) .* w .* Dconv(dx))

            A(dx) = reg0(dx) + 2 * lambda * fidelity(dx)
            b = reg0(χ) + 2 * lambda * Dconv(real(conj(w) .* (-im) .* (w - b0)))

            println("    Iteration $iter: solving linear system...")
            dx = cgsolve(A, -b, cg_tol, cg_max_iter)

            res_norm_ratio = norm(dx[:]) / (norm(χ[:]) + 1e-6)
            χ .+= dx

            # Costs
            wres = m .* exp.(im .* real(ifft(D .* fft(χ)))) - b0
            cost_data_history[iter] = norm(wres[:], 2)
            cost = abs.(wG .* fgrad(χ, voxel_size))
            cost_reg_history[iter] = sum(cost)

            println("    iter=$iter; res_norm_ratio=$res_norm_ratio; cost_L2=$(cost_data_history[iter]); cost_reg=$(cost_reg_history[iter])")
        end

        return χ, cost_reg_history[1:iter], cost_data_history[1:iter]
    end

    println("[INFO] Starting Gauss-Newton solver...")
    χ, cost_reg_history, cost_data_history = gaussnewton()

    χ = χ .* Mask
    return χ, cost_reg_history, cost_data_history
end

"""
Wrapper: runs MEDI when data is already loaded (rdf, iMag, Mask arrays).
"""
function run_medi_from_laplacian(
    RDF::Array{<:Real,3}, iMag::Array{<:Real,3}, Mask::BitArray{3},
    voxel_size::NTuple{3,<:Real}, output_dir::String; B0_dir=(0,0,1), header=nothing
)
    println("[INFO] Running MEDI with preloaded Laplacian outputs...")
    println("[INFO] Input size = $(size(RDF)), voxel_size = $voxel_size, datatype = $(eltype(RDF))")
    
    # Noise standard deviation map
    N_std = ones(Float64, size(RDF))

    # Run the MEDI reconstruction 
    χ, _, _ = MEDI_L1(RDF, N_std, iMag, Mask, voxel_size; B0_dir=B0_dir)

    # Save result 
    mkpath(output_dir)
    out_path = joinpath(output_dir, "chimap.nii.gz")
    println("[INFO] Saving MEDI output to $out_path")

    # handle description safely if header is provided
    desc = nothing
    if header !== nothing
        if typeof(header.descrip) <: NTuple{80,UInt8}
            desc = String(collect(header.descrip))
        else
            desc = String(header.descrip)
        end
    end

    if desc === nothing
        # fresh header
        vol = NIVolume(Float32.(χ);
            voxel_size=Tuple(Float32.(voxel_size)),
            orientation=nothing
        )
    else
        # reuse voxel size + description
        vol = NIVolume(Float32.(χ);
            voxel_size=Tuple(Float32.(voxel_size)),
            descrip=desc
        )
    end

    niwrite(out_path, vol)

    # Debug
    # if isfile(out_path)
    #     println("[DEBUG] MEDI output written: $out_path")
    #     println("[DEBUG] File size = $(stat(out_path).size / 1e6) MB")
    # else
    #     println("[ERROR] File not found after writing: $out_path")
    # end

    println("[INFO] MEDI finished successfully. Output written to $out_path")
end

