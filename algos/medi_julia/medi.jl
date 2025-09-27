
using FFTW
using Statistics
using LinearAlgebra
using MriResearchTools
using NIfTI

include("fgrad.jl")            # defines fgrad(chi, voxel_size)
include("bdiv.jl")             # defines bdiv(Gx, voxel_size)
include("sphere_kernel.jl")    # defines sphere_kernel(matrix_size, voxel_size, radius) and SMV(...)
include("dipole_kernel.jl")    # defines dipole_kernel(matrix_size, voxel_size, B0_dir; domain="kspace")
include("dataterm_mask.jl")    # defines dataterm_mask(mode, N_std, Mask)
include("gradient_mask.jl")    # defines gradient_mask(mode, iMag, Mask, fgrad, voxel_size, percentage)
include("cgsolve.jl")          # defines cgsolve(A, b, tol, max_iter)

"""
A simplified implementation of the Morphology Enabled Dipole Inversion (MEDI) method.

# Arguments (all required unless given as keywords):
- `RDF`: the measured field map (in radians) as a 3D array.
- `N_std`: noise standard deviation map (same size as RDF).
- `iMag`: the anatomical magnitude image.
- `Mask`: binary 3D mask (Bool array) of the region of interest.
- `voxel_size`: tuple of voxel dimensions (in mm).

# Keyword Arguments:
- `lambda`: regularization parameter.
- `B0_dir`: either an integer (1,2,3 corresponding to [1,0,0],[0,1,0],[0,0,1]) or a 3-element vector.
- `merit`: (Bool) if true, iterative merit–based adjustment is applied (default false).
- `smv`: (Bool) if true, apply spherical mean value (SMV) preprocessing (default false).
- `radius`: radius (in mm) used for SMV (default 5.0).
- `data_weighting`: data weighting mode (0 or 1; default 1).
- `gradient_weighting`: gradient weighting mode (default 1).
- `percentage`: parameter for gradient_mask (default 0.9).
- `cg_max_iter`: maximum iterations for conjugate gradient (default 100).
- `cg_tol`: tolerance for conjugate gradient (default 0.01).
- `max_iter`: maximum outer iterations (default 10).
- `tol_norm_ratio`: convergence tolerance (default 0.1).

# Returns
A tuple `(χ, cost_reg_history, cost_data_history)`, where:
- `χ`: the computed QSM map (in ppm, masked),
- `cost_reg_history`: regularization cost history (vector),
- `cost_data_history`: data fidelity cost history (vector).
"""
function MEDI_L1(RDF, N_std, iMag, Mask, voxel_size::NTuple{3,Float64}; 
                 lambda=1000, B0_dir=(0, 0, 1), merit=false, smv=false, radius=5.0, 
                 data_weighting=1, gradient_weighting=1, percentage=0.9, 
                 cg_max_iter=100, cg_tol=0.01, max_iter=10, tol_norm_ratio=0.1)
    
    # Ensure N_std is masked.
    N_std = N_std .* float.(Mask)
    tempn = copy(N_std)
    
    # Generate dipole kernel in k-space.
    println("Generating dipole kernel...")
    D = dipole_kernel(size(RDF), voxel_size, B0_dir, "kspace")
    
    # If SMV is enabled, modify Mask, D, RDF, and noise accordingly.
    if smv
        println("Applying SMV...")
        SphereK = sphere_kernel(size(RDF), voxel_size, radius)
        # SMV returns a tuple; use the first element.
        Mask = SMV(Mask, SphereK)[1] .> 0.999
        D .= (1 .- SphereK) .* D
        RDF .= RDF .- SMV(RDF, SphereK)[1]
        RDF .= RDF .* Mask
        tempn .= sqrt.(SMV(tempn.^2, SphereK)[1] .+ tempn.^2)
    end
    
    println("Generating data weighting...")
    m = dataterm_mask(data_weighting, tempn, Mask)
    b0 = m .* exp.(im .* RDF)
    # Use fgrad and bdiv for gradient and divergence.
    grad = fgrad
    div = bdiv

    println("Generating gradient weighting...")
    wG = gradient_mask(gradient_weighting, iMag, Mask, fgrad, voxel_size, percentage)
    
    # Define a helper function to perform the dipole convolution.
    Dconv(dx) = real(ifft(D .* fft(dx)))
    
    # Define a basic Gauss-Newton solver.
    function gaussnewton()
        iter = 0
        χ = zeros(Float64, size(RDF))  # initial guess
        res_norm_ratio = Inf
        cost_data_history = zeros(Float64, max_iter)
        cost_reg_history = zeros(Float64, max_iter)
        badpoint = zeros(Float64, size(RDF))
        
        while (res_norm_ratio > tol_norm_ratio) && (iter < max_iter)
            iter += 1

            println("Computing weighting factor for regularization term...")
            Vr = 1 ./ sqrt.(abs.(wG .* fgrad(real(χ), voxel_size)).^2 .+ 1e-6)
            w = m .* exp.(im .* real(ifft(D .* fft(χ))))
            
            println("Computing regularization term...")
            reg0 = (dx) -> div(wG .* (Vr .* (wG .* fgrad(real(dx), voxel_size))), voxel_size)

            println("Computing data fidelity term...")
            fidelity(dx) = Dconv(conj(w) .* w .* Dconv(dx))

            println("Solving linear system...")
            A(dx) = reg0(dx) + 2 * lambda * fidelity(dx)
            b = reg0(χ) + 2 * lambda * Dconv(real(conj(w) .* (-im) .* (w - b0)))
            @time dx = cgsolve(A, -b, cg_tol, cg_max_iter)

            println("Updating solution...")
            res_norm_ratio = norm(dx[:]) / (norm(χ[:]) + 1e-6)
            χ .+= dx
            
            println("Computing cost...")
            wres = m .* exp.(im .* real(ifft(D .* fft(χ)))) - b0
            cost_data_history[iter] = norm(wres[:], 2)
            cost = abs.(wG .* fgrad(χ, voxel_size))
            cost_reg_history[iter] = sum(cost)
            
            if merit
                println("Computing merit function...")
                wres .= wres .- mean(wres[Mask])
                a = wres[Mask]
                factor = std(abs.(a)) * 6
                wres .= abs.(wres) ./ factor
                wres[wres .< 1] .= 1
                badpoint[wres .> 1] .= 1
                N_std[Mask] .= N_std[Mask] .* (wres[Mask].^2)
                tempn .= N_std
                if smv
                    tempn .= sqrt.(SMV(tempn.^2, SphereK)[1] .+ tempn.^2)
                end
                m = dataterm_mask(data_weighting, tempn, Mask)
                b0 .= m .* exp.(im .* RDF)
            end
            
            println("iter: ", iter, "; res_norm_ratio: ", res_norm_ratio,
                    "; cost_L2: ", cost_data_history[iter],
                    "; cost_reg: ", cost_reg_history[iter])
        end
        
        return χ, cost_reg_history[1:iter], cost_data_history[1:iter]
    end
    
    # Use Gauss–Newton (we only support that solver here).
    println("Starting Gauss-Newton solver...")
    χ, cost_reg_history, cost_data_history = gaussnewton()
    
    # multiply χ by mask
    χ = χ .* Mask
    
    return χ, cost_reg_history, cost_data_history
end

#just for testing
# function test_MEDI_L1_nifti()
#     println("Loading test data...")

    
#     #Files must be generated at first
#     rdf_path  = joinpath(input, "fieldmap-local.nii")
#     imag_path = joinpath(input, "magnitude.nii")
#     mask_path = joinpath(input, "mask.nii")

    
#     # Load NIfTI images
#     rdf_nii = niread(rdf_path)
#     imag_nii = niread(imag_path)
#     mask_nii = niread(mask_path)
    
#     # Extract raw data.
#     RDF = rdf_nii.raw                # field map (3D array, in radians)
#     iMag = imag_nii.raw              # anatomical magnitude image (3D array)
#     Mask = mask_nii.raw .!= 0        # convert mask to Bool array
#     N_std = ones(Float64, size(RDF)) # noise std map (same size as RDF)
    
#     # Set voxel size and B0 direction.
#     voxel_size = (1.0, 1.0, 1.0)
#     B0_dir = (0, 0, 1)
    
#     # Set MEDI parameters.
#     lambda = 1000.0
#     merit = false
#     smv = false
#     radius = 5.0
#     data_weighting = 1
#     gradient_weighting = 1
#     percentage = 0.9
#     cg_max_iter = 100
#     cg_tol = 0.01
#     max_iter = 10
#     tol_norm_ratio = 0.1

#     println("Starting MEDI_L1.")
#     χ, cost_reg_history, cost_data_history = MEDI_L1(
#         RDF, N_std, iMag, Mask, voxel_size; 
#         lambda=lambda, B0_dir=B0_dir, merit=merit, smv=smv, radius=radius,
#         data_weighting=data_weighting, gradient_weighting=gradient_weighting,
#         percentage=percentage, cg_max_iter=cg_max_iter, cg_tol=cg_tol, 
#         max_iter=max_iter, tol_norm_ratio=tol_norm_ratio
#     )

#     # Save the QSM map.
#     println("Saving QSM map...")
#     mkpath(output)
#     savenii(χ, joinpath(output, "chimap.nii.gz"), header=imag_nii.header)

    
#     println("Done.")
# end


"""
Pipeline wrapper: loads NIfTI inputs, runs MEDI, saves output.
"""
function run_medi_pipeline(input::String, output::String)
    println("[INFO] Loading input files...")

    # paths
    magnitude_base = joinpath(input, "sub-1", "anat")
    fieldmap_base = joinpath(input, "derivatives", "qsm-forward", "sub-1", "anat")

    # magnitude candidates
    magnitude_candidates = [
        joinpath(magnitude_base, "sub-1_echo-1_part-mag_MEGRE.nii"),
        joinpath(magnitude_base, "sub-1_echo-1_part-mag_MEGRE.nii.gz")
    ]
    imag_path = nothing
    for candidate in magnitude_candidates
        if isfile(candidate)
            imag_path = candidate
            break
        end
    end
    if imag_path === nothing
        error("Could not find magnitude file in: $magnitude_candidates")
    end

    # field and mask
    rdf_path  = joinpath(fieldmap_base, "sub-1_fieldmap-local.nii")
    mask_path = joinpath(fieldmap_base, "sub-1_mask.nii")

    # checks for files
    for path in (rdf_path, imag_path, mask_path)
        if !isfile(path)
            error("File not found: $path")
        end
    end

    # load
    rdf_nii = niread(rdf_path)
    imag_nii = niread(imag_path)
    mask_nii = niread(mask_path)

    # data array
    RDF  = rdf_nii.raw
    iMag = imag_nii.raw
    Mask = mask_nii.raw .!= 0
    N_std = ones(Float64, size(RDF))

    # parameters
    voxel_size = (1.0, 1.0, 1.0)
    B0_dir = (0, 0, 1)

    println("[INFO] Running MEDI...")
    χ, _, _ = MEDI_L1(
        RDF, N_std, iMag, Mask, voxel_size;
        B0_dir=B0_dir
    )

    # Output saving
    println("[INFO] Saving results to $output ...")
    mkpath(output)

    # convert header.descrip safely
    desc = try
        String(collect(imag_nii.header.descrip))
    catch
        ""
    end

    out_path = joinpath(output, "chimap.nii.gz")
    vol = NIVolume(Float32.(χ);
        voxel_size=Tuple(Float32.(imag_nii.header.pixdim[2:4])),
        descrip=desc
    )

    niwrite(out_path, vol)

    # # Debug check
    # if isfile(out_path)
    #     println("[DEBUG] Output file successfully written: $out_path")
    #     println("[DEBUG] File size = $(stat(out_path).size / 1e6) MB")
    # else
    #     println("[ERROR] File not found after writing: $out_path")
    # end

    println("[INFO] MEDI pipeline finished successfully.")
end
