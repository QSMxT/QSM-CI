using FFTW: fft, fftshift
using Statistics, Images

"""
    dipole_kernel(matrix_size, voxel_size, B0_dir; domain="kspace")

Generate the dipole kernel.

# Arguments
- `matrix_size::NTuple{3,Int}`: size of the 3D field, e.g. (nx, ny, nz).
- `voxel_size::NTuple{3,Float64}`: voxel dimensions (in mm).
- `B0_dir`: either an integer (1 for [1,0,0], 2 for [0,1,0], 3 for [0,0,1]) or a 3-element vector.
- `domain`: either `"kspace"` (default) or `"imagespace"`.  
    - In k‑space, the kernel is defined according to Salomir et al. (2003).  
    - In image space, it is defined as in Li et al. (2004).

# Returns
- `D`: the dipole kernel (in Fourier space if `domain=="imagespace"`, or in k‑space otherwise).
"""
function dipole_kernel(matrix_size::NTuple{3,Int}, voxel_size::NTuple{3,Float64}, B0_dir, domain::String="kspace")
    # Process B0_dir: if an integer, convert it to a unit vector.
    if B0_dir isa Integer
        if B0_dir == 1
            B0_dir = [1.0, 0.0, 0.0]
        elseif B0_dir == 2
            B0_dir = [0.0, 1.0, 0.0]
        elseif B0_dir == 3
            B0_dir = [0.0, 0.0, 1.0]
        else
            error("B0_dir integer must be 1, 2, or 3")
        end
    end
    nx, ny, nz = matrix_size
    # Create coordinate ranges (we use a floating‐point range so that even for odd sizes the number of points is correct)
    x_range = collect(-nx/2 : nx/2 - 1)
    y_range = collect(-ny/2 : ny/2 - 1)
    z_range = collect(-nz/2 : nz/2 - 1)
    
    # Build 3D coordinate arrays in the natural (x,y,z) order:
    X = reshape(x_range, (nx, 1, 1)) .+ zeros(1, ny, nz)
    Y = reshape(y_range, (1, ny, 1)) .+ zeros(nx, 1, nz)
    Z = reshape(z_range, (1, 1, nz)) .+ zeros(nx, ny, 1)
    
    if domain == "kspace"
        # Scale coordinates for k-space as in the MATLAB code:
        X = X ./ (nx * voxel_size[1])
        Y = Y ./ (ny * voxel_size[2])
        Z = Z ./ (nz * voxel_size[3])
        # Compute the dipole kernel in k-space
        # Note: elementwise operations with broadcasting (use .^, .+, etc.)
        numer = (X .* B0_dir[1] .+ Y .* B0_dir[2] .+ Z .* B0_dir[3]).^2
        denom = X.^2 .+ Y.^2 .+ Z.^2
        D = 1/3 .- numer ./ denom
        D[isnan.(D)] .= 0.0  # set any NaNs (from 0/0) to zero
        D = fftshift(D)
    elseif domain == "imagespace"
        # In image space, scale the coordinates by the voxel size
        X = X .* voxel_size[1]
        Y = Y .* voxel_size[2]
        Z = Z .* voxel_size[3]
        d = ( 3 .* (X .* B0_dir[1] .+ Y .* B0_dir[2] .+ Z .* B0_dir[3]).^2 .- (X.^2 .+ Y.^2 .+ Z.^2) ) ./
            (4 * π * (X.^2 .+ Y.^2 .+ Z.^2).^(2.5))
        d[isnan.(d)] .= 0.0
        # In MATLAB, D = fftn(fftshift(d)); Julia’s fft performs a multidimensional FFT.
        D = fft(fftshift(d))
    else
        error("domain must be either \"kspace\" or \"imagespace\"")
    end
    return D
end

function test_dipole_kernel()
    # Define parameters.
    matrix_size = (32, 32, 32)
    voxel_size = (1.0, 1.0, 1.0)
    B0_dir = 3            # will be converted to [0, 0, 1]
    domain = "kspace"     # choose "kspace" or "imagespace"

    # Generate the dipole kernel.
    D = dipole_kernel(matrix_size, voxel_size, B0_dir, domain)
    
    # For visualization, take the center slice in the third dimension.
    center = cld(matrix_size[3], 2)  # center index
    slice_img = real(D[:, :, center])
    
    # Normalize the slice to the range [0,1].
    slice_norm = (slice_img .- minimum(slice_img)) ./ (maximum(slice_img) - minimum(slice_img) + eps())
    
    # Save the image.
    save("dipole_kernel.png", colorview(Gray, slice_norm))
    println("Saved dipole_kernel.png (center slice)")
end

