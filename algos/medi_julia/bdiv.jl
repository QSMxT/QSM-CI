# Discrete Divergence Using Backward Difference
# with the Dirichlet Boundary Condition

# Created by Youngwook Kee (Oct 21 2015)
# Last modified date: Oct 24 2015
# Converted to Julia Feb 27 2025

# References:
# [1] Chambolle, An Algorithm for Total Variation Minimization and
# Applications, JMIV 2004

using Test, Images

function bdiv(Gx::Array{T,4}, voxel_size::NTuple{3,T} = (one(T), one(T), one(T))) where T<:Real
    # Gx is a 4D array with the last dimension containing the gradient components.
    Gx_x = Gx[:,:,:,1]
    Gx_y = Gx[:,:,:,2]
    Gx_z = Gx[:,:,:,3]
    
    Mx, My, Mz = size(Gx_x)
    
    # Backward difference in x (dimension 1) with Dirichlet boundary condition:
    # Take Gx_x[1:end-1,:,:] then append a zero slice at the bottom.
    # Subtract from that the same slice shifted down (with zeros at the top).
    Dx = vcat(Gx_x[1:end-1, :, :], zeros(T, 1, My, Mz)) .-
         vcat(zeros(T, 1, My, Mz), Gx_x[1:end-1, :, :])
    
    # Backward difference in y (dimension 2)
    Dy = cat(Gx_y[:, 1:end-1, :], zeros(T, Mx, 1, Mz); dims=2) .-
         cat(zeros(T, Mx, 1, Mz), Gx_y[:, 1:end-1, :]; dims=2)
    
    # Backward difference in z (dimension 3)
    Dz = cat(Gx_z[:, :, 1:end-1], zeros(T, Mx, My, 1); dims=3) .-
         cat(zeros(T, Mx, My, 1), Gx_z[:, :, 1:end-1]; dims=3)
    
    # Divide each difference by its corresponding voxel size.
    Dx ./= voxel_size[1]
    Dy ./= voxel_size[2]
    Dz ./= voxel_size[3]
    
    # The divergence is the negative sum of the backward differences.
    div = -(Dx .+ Dy .+ Dz)
    return div
end

# Test function for bdiv in Julia.

# Test function for bdiv in Julia.
function test_bdiv()
    # Define a 3x3x3 grid.
    M, N, P = 3, 3, 3
    # Create a gradient field corresponding to f(x)=x^2 in the x-direction.
    # That is, let Gx_x(i,j,k) = 2*i for i=1:M.
    Gx_x = zeros(Float64, M, N, P)
    for i in 1:M
        Gx_x[i, :, :] .= 2 * i
    end
    Gx_y = zeros(Float64, M, N, P)
    Gx_z = zeros(Float64, M, N, P)
    # Assemble the 4D gradient field: size (M, N, P, 3)
    G = cat(Gx_x, Gx_y, Gx_z; dims=4)
    
    # Compute divergence.
    div_field = bdiv(G, (1.0, 1.0, 1.0))
    
    # Expected divergence:
    # For i = 1: expected = - (2 - 0) = -2.
    # For i = 2: expected = - (4 - 2) = -2.
    # For i = 3: expected = - (0 - 4) = 4.
    expected = zeros(Float64, M, N, P)
    for i in 1:M, j in 1:N, k in 1:P
        if i < M
            expected[i, j, k] = -2.0
        else
            expected[i, j, k] = 4.0
        end
    end

    tol = 1e-12
    @test all(abs.(div_field .- expected) .< tol)
    
    println("Divergence field:")
    display(div_field)
    
    # Extract the center slice (along the third dimension) and normalize it for visualization.
    center = cld(P, 2)
    slice_img = div_field[:, :, center]
    slice_norm = (slice_img .- minimum(slice_img)) ./ (maximum(slice_img) - minimum(slice_img) + eps())
    save("bdiv_test.png", colorview(Gray, slice_norm))
    println("Saved bdiv_test.png")
end

