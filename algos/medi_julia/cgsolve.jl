using LinearAlgebra
using LinearAlgebra.BLAS: axpy!

function cgsolve(A, b, tol, max_iter)
    x = zeros(eltype(b), size(b))
    r = b - A(x)
    p = copy(r)
    rsold = dot(r, r)
    for i in 1:max_iter
        Ap = A(p)
        α = rsold / dot(p, Ap)
        # x ← x + α * p  (using BLAS.axpy! for in-place update)
        axpy!(α, p, x)
        # r ← r - α * Ap
        axpy!(-α, Ap, r)
        rsnew = dot(r, r)
        if sqrt(rsnew) < tol
            break
        end
        p .= r .+ (rsnew / rsold) .* p
        rsold = rsnew
    end
    return x
end
