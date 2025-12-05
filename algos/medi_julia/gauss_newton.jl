
# Define a basic Gauss-Newton solver.
function gaussnewton()
    iter = 0
    x = zeros(Float64, matrix_size)  # initial guess
    res_norm_ratio = Inf
    cost_data_history = zeros(Float64, max_iter)
    cost_reg_history = zeros(Float64, max_iter)
    e = 1e-6
    badpoint = zeros(Float64, matrix_size)
    
    println("Starting Gauss-Newton iterations...")
    while (res_norm_ratio > tol_norm_ratio) && (iter < max_iter)
        iter += 1

        println("Computing weighting factor for regularization term...")
        Vr = 1 ./ sqrt.(abs.(wG .* fgrad(real(x), voxel_size)).^2 .+ e)
        w = m .* exp.(im .* real(ifft(D .* fft(x))))
        
        println("Computing regularization term...")
        reg0 = (dx) -> div(wG .* (Vr .* (wG .* fgrad(real(dx), voxel_size))), voxel_size)

        println("Computing data fidelity term...")
        fidelity(dx) = Dconv(conj(w) .* w .* Dconv(dx))

        println("Solving linear system...")
        A(dx) = reg0(dx) + 2 * lambda * fidelity(dx)
        b = reg0(x) + 2 * lambda * Dconv(real(conj(w) .* (-im) .* (w - b0)))
        @time dx = cgsolve(A, -b, cg_tol, cg_max_iter)

        println("Updating solution...")
        res_norm_ratio = norm(dx[:]) / (norm(x[:]) + eps())
        x .+= dx
        
        println("Computing cost...")
        wres = m .* exp.(im .* real(ifft(D .* fft(x)))) - b0
        cost_data_history[iter] = norm(wres[:], 2)
        cost = abs.(wG .* fgrad(x, voxel_size))
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
    
    return x, cost_reg_history[1:iter], cost_data_history[1:iter]
end