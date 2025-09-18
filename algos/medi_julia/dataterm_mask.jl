using Statistics
using Test, Images

"""
    dataterm_mask(dataterm_weighting_mode, N_std, Mask)

Generate the data weighting.

# Arguments
- `dataterm_weighting_mode::Int`: 0 for uniform weighting, 1 for SNR weighting.
- `N_std`: noise standard deviation (can be a scalar or an array) on the field map.
- `Mask::AbstractArray{Bool,3}`: a binary 3D matrix denoting the ROI.

# Returns
- `w`: if mode==0, returns the scalar 1;
       if mode==1, returns an array weighting computed as
           w = (float.(Mask) ./ N_std) with any NaNs/Inf set to 0,
           multiplied elementwise by Mask and normalized so that the mean over ROI equals 1.
"""
function dataterm_mask(dataterm_weighting_mode::Int, N_std, Mask::AbstractArray{Bool,3})
    if dataterm_weighting_mode == 0
        return 1
    elseif dataterm_weighting_mode == 1
        # Convert Mask (Bool) to float so that true becomes 1.0, false remains 0.0.
        w = float.(Mask) ./ N_std
        w[isnan.(w)] .= 0
        w[isinf.(w)] .= 0
        # Multiply by Mask to ensure zero outside the ROI.
        w .= w .* (Mask .> 0)
        # Normalize: divide by the mean over the ROI.
        m = mean(w[Mask])
        w .= w ./ m
        return w
    else
        error("Unsupported dataterm_weighting_mode: $dataterm_weighting_mode")
    end
end

# Test function for dataterm_mask in Julia.
function test_dataterm_mask()
    # Create a simple 3x3x3 binary mask.
    Mask = trues(3,3,3)
    # Optionally, set a few voxels outside the ROI.
    Mask[1,1,1] = false

    N_std = 2.0

    # Test mode 0: uniform weighting.
    w0 = dataterm_mask(0, N_std, Mask)
    @test w0 == 1
    println("Test mode 0 passed: w0 = ", w0)

    # Test mode 1: SNR weighting.
    w1 = dataterm_mask(1, N_std, Mask)
    # Check that only voxels inside Mask are nonzero.
    @test all(w1[.!Mask] .== 0)
    # Check that the mean over ROI is 1.
    m = mean(w1[Mask])
    @test abs(m - 1) < 1e-12
    println("Test mode 1 passed: mean(w1 over ROI) = ", m)

    # For visualization: extract center slice along the third dimension.
    center = cld(size(Mask,3), 2)
    slice_img = w1[:,:,center]
    # Normalize the slice to [0,1] (it should already be near that range).
    slice_norm = (slice_img .- minimum(slice_img)) ./ (maximum(slice_img) - minimum(slice_img) + eps())
    save("dataterm_mask_test.png", colorview(Gray, slice_norm))
    println("Saved dataterm_mask_test.png")
end
