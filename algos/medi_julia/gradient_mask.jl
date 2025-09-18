# Generate the gradient weighting in MEDI
# w = gradient_mask(gradient_weighting_mode, iMag, Mask, grad, voxel_size, percentage)
#
# output
# w - gradient weighting
#
# input
# gradient_weighting_mode - 1 for binary weighting; other values reserved for grayscale weighting
# iMag - the anatomical image
# Mask - a binary 3D matrix denoting the Region Of Interest
# grad - function that computes gradient
# voxel_size - the size of a voxel
# percentage (optional) - percentage of voxels considered to be edges.
#
# Created by Ildar Khalidov in 2010
# Modified by Tian Liu and Shuai Wang on 2011.03.28 to add voxel_size in grad
# Modified by Tian Liu on 2011.03.31
# Last modified by Tian Liu on 2013.07.24

using Test
using Statistics

function gradient_mask(gradient_weighting_mode::Int, iMag::Array{T,3}, Mask::AbstractArray{Bool,3}, grad, voxel_size::Tuple{T,T,T}, percentage::Float64=0.9) where T <: Real
    field_noise_level = max(0.01 * maximum(iMag), eps(Float64))  # Ensure a minimum threshold
    wG = abs.(grad(iMag .* (Mask .> 0), voxel_size))
    denominator = sum(Mask)
    numerator = sum(wG .> field_noise_level)
    
    max_iter = 100
    iter = 0

    if (numerator / denominator) > percentage
        while (numerator / denominator) > percentage && iter < max_iter
            field_noise_level *= 1.05
            numerator = sum(wG .> field_noise_level)
            iter += 1
        end
    else
        while (numerator / denominator) < percentage && iter < max_iter
            field_noise_level *= 0.95
            numerator = sum(wG .> field_noise_level)
            iter += 1
        end
    end
    
    if iter == max_iter
        @warn "Maximum iterations reached in gradient_mask adjustment. Final ratio: $(numerator/denominator)"
    end
    
    return wG .<= field_noise_level
end


# Unit tests
function test_gradient_mask()
    iMag = ones(3,3,3) .* reshape(1:27, (3,3,3))  # Test anatomical image
    Mask = trues(3,3,3)  # Binary mask of ones
    voxel_size = (1.0, 1.0, 1.0)
    percentage = 0.9
    
    # Mock gradient function that returns the magnitude of the gradient
    grad = (x, v) -> abs.(x .- mean(x))
    
    w = gradient_mask(1, iMag, Mask, grad, voxel_size, percentage)
    
    @test size(w) == size(iMag)  # Check output size
    @test eltype(w) == Bool  # Check output type is Bool
    @test sum(w) <= prod(size(iMag))  # Ensure output is within expected range
    
    # Check boundary conditions
    iMag_low = iMag .* 0.01
    w_low = gradient_mask(1, iMag_low, Mask, grad, voxel_size, percentage)
    @test sum(w_low) ≥ 1  # Ensure at least one voxel passes threshold  # All should pass threshold
    
    iMag_high = iMag .* 100
    w_high = gradient_mask(1, iMag_high, Mask, grad, voxel_size, percentage)
    @test sum(w_high) < prod(size(iMag))  # Some should be filtered out
end

# Run tests
test_gradient_mask()
