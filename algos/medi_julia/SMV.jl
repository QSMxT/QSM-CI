using FFTW: fft, ifft, fftshift, ifftshift
using Test
include("sphere_kernel.jl")

# SMV: Spherical Mean Value operator
#   y, K = SMV(iFreq, matrix_size, voxel_size, radius)
# or
#   y, K = SMV(iFreq, K)
# where if only one extra argument is provided it is assumed to be the kernel.
function SMV(iFreq::AbstractArray, args...)
    if length(args) == 1
        K = args[1]
    else
        matrix_size = args[1]
        voxel_size = args[2]
        if length(args) < 3
            # Default radius: round(6/max(voxel_size)) * max(voxel_size)
            radius = round(6 / maximum(voxel_size)) * maximum(voxel_size)
        else
            radius = args[3]
        end
        K = sphere_kernel(matrix_size, voxel_size, radius)
    end
    # Use ifftshift(K) to realign the kernel with fft(iFreq)
    y = ifft( fft(iFreq) .* ifftshift(K) )
    return y, K
end

# Test function for SMV in Julia
function test_SMV()
    # Create a simple 3x3x3 test input (a ramp)
    iFreq = reshape(collect(1:27), (3,3,3))
    matrix_size = (3,3,3)
    voxel_size = (1.0, 1.0, 1.0)
    radius = 6.0

    # Option 1: Provide the kernel directly.
    K = sphere_kernel(matrix_size, voxel_size, radius)
    y1, K1 = SMV(iFreq, K)
    println("Test with provided kernel:")
    println("y1 = ")
    display(y1)
    println("K1 = ")
    display(K1)

    # Option 2: Provide parameters and let SMV compute the kernel.
    y2, K2 = SMV(iFreq, matrix_size, voxel_size, radius)
    println("Test with computed kernel:")
    println("y2 = ")
    display(y2)
    println("K2 = ")
    display(K2)
end

