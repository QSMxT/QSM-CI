using FFTW: fft, fftshift
using Test, Images, Statistics

function generate_sphere(matrix_size::NTuple{3,Int}, voxel_size::NTuple{3,Float64}, radius::Float64)
    nx, ny, nz = matrix_size
    xs = collect(-nx/2 : 1 : nx/2 - 1) .* voxel_size[1]
    ys = collect(-ny/2 : 1 : ny/2 - 1) .* voxel_size[2]
    zs = collect(-nz/2 : 1 : nz/2 - 1) .* voxel_size[3]
    
    # Build 3D coordinate arrays via reshaping (no meshgrid)
    X = reshape(xs, :, 1, 1) .+ zeros(1, ny, nz)
    Y = reshape(ys, 1, :, 1) .+ zeros(nx, 1, nz)
    Z = reshape(zs, 1, 1, :) .+ zeros(nx, ny, 1)
    
    # Define outer and inner regions
    Sphere_out = ((max.(abs.(X) .- 0.5 * voxel_size[1], 0).^2 .+
                max.(abs.(Y) .- 0.5 * voxel_size[2], 0).^2 .+
                max.(abs.(Z) .- 0.5 * voxel_size[3], 0).^2) .> radius^2)
    Sphere_in = (((abs.(X) .+ 0.5 * voxel_size[1]).^2 .+
                (abs.(Y) .+ 0.5 * voxel_size[2]).^2 .+
                (abs.(Z) .+ 0.5 * voxel_size[3]).^2) .<= radius^2)
    
    # Prepare a finer grid for computing partial contributions on the boundary (shell)
    Sphere_mid = zeros(Float64, matrix_size)
    split = 10
    dv = (-split+0.5 : split-0.5) ./ (2*split)
    xv = reshape(dv, :, 1, 1)
    yv = reshape(dv, 1, :, 1)
    zv = reshape(dv, 1, 1, :)
    
    # Points that are neither clearly inside nor outside
    shell = .!Sphere_in .& .!Sphere_out
    X_shell = X[shell]
    Y_shell = Y[shell]
    Z_shell = Z[shell]
    
    shell_val = map((xx, yy, zz) ->
        mean((((xx .+ xv .* voxel_size[1]).^2 .+
            (yy .+ yv .* voxel_size[2]).^2 .+
            (zz .+ zv .* voxel_size[3]).^2) .<= radius^2)),
        X_shell, Y_shell, Z_shell)
    
    Sphere_mid[shell] .= shell_val
    Sphere = Sphere_in .+ Sphere_mid
    Sphere ./= sum(Sphere)
    return Sphere
end

function sphere_kernel(matrix_size::Tuple{Int,Int,Int}, voxel_size::Tuple{Float64,Float64,Float64}, radius::Float64)
    Sphere = generate_sphere(matrix_size, voxel_size, radius)
    Sphere ./= sum(Sphere)
    kernel = real(fftshift(fft(fftshift(Sphere))))
    return kernel
end

function SMV_kernel(matrix_size::NTuple{3,Int}, voxel_size::NTuple{3,Float64}, radius::Float64)
    return 1 .- sphere_kernel(matrix_size, voxel_size, radius)
end

function test_sphere_kernel()
    matrix_size = (32, 32, 32)
    voxel_size = (1.0, 1.0, 1.0)
    radius = 12.0

    kernel = sphere_kernel(matrix_size, voxel_size, radius)
    @test size(kernel) == matrix_size

    slice_idx = 15
    slice_img = real.(fftshift(kernel[:, :, slice_idx]))
    
    # Normalize the slice to [0, 1] range
    slice_img = (slice_img .- minimum(slice_img)) ./ (maximum(slice_img) - minimum(slice_img) + eps(Float64))
end

