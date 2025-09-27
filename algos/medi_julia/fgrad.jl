# Discrete Gradient Using Forward Differences
# with the Neumann Boundary Condition

# References:
# [1] Chambolle, An Algorithm for Total Variation Minimization and
# Applications, JMIV 2004
# [2] Pock et al., Global Solutions of Variational Models with Convex
# Regularization, SIIMS 2010

function fgrad(chi::AbstractArray{T,3}, voxel_size::Tuple{S,S,S}=(1.0,1.0,1.0)) where {T,S<:Real}
    chi = convert(Array{Float64}, chi)  # Ensure floating point consistency

    # Forward differences with Neumann boundary conditions
    Dx = vcat(chi[2:end, :, :] .- chi[1:end-1, :, :], chi[end:end, :, :] .- chi[end-1:end-1, :, :]) ./ voxel_size[1]
    Dy = hcat(chi[:, 2:end, :] .- chi[:, 1:end-1, :], chi[:, end:end, :] .- chi[:, end-1:end-1, :]) ./ voxel_size[2]
    Dz = cat(chi[:, :, 2:end] .- chi[:, :, 1:end-1], chi[:, :, end:end] .- chi[:, :, end-1:end-1], dims=3) ./ voxel_size[3]

    return cat(Dx, Dy, Dz, dims=4)
end

# Unit tests
using Test

function test_fgrad()
    chi = Array(reshape(1:27, (3,3,3)))  # Ensure explicit conversion
    voxel_size = (1.0, 1.0, 1.0)
    Gx = fgrad(chi, voxel_size)

    @test size(Gx) == (3,3,3,3)
    @test eltype(Gx) == Float64  # Ensure output is Float64
    @test Gx[1,1,1,1] == 1.0  # Check forward difference in x direction
    @test Gx[1,1,1,2] == 3.0  # Check forward difference in y direction
    @test Gx[1,1,1,3] == 9.0  # Check forward difference in z direction
end

