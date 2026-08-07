using LinearAlgebra
using PEPSKit

tied_peps(A) = InfinitePEPS([copy(A) for _ in 1:2, _ in 1:2])

function is_tied(psi; atol = 0.0, rtol = sqrt(eps(Float64)))
    ref = psi.A[1, 1]
    return all(isapprox(psi.A[r, c], ref; atol, rtol) for r in 1:2, c in 1:2)
end

peps_frobnorm(g) = sqrt(sum(norm(g.A[r, c])^2 for r in 1:2, c in 1:2))

function project_tied_gradient(g)
    avg = copy(g.A[1, 1])
    for r in 1:2, c in 1:2
        (r == 1 && c == 1) && continue
        avg = avg + g.A[r, c]
    end
    avg = avg / 4
    return tied_peps(avg)
end

function tied_descent_direction(g; grad_tol)
    projected = project_tied_gradient(g)
    gradnorm = peps_frobnorm(projected)
    (!isfinite(gradnorm) || gradnorm <= grad_tol) && return nothing, gradnorm
    direction = InfinitePEPS([
        -projected.A[r, c] / gradnorm for r in 1:2, c in 1:2
    ])
    return direction, gradnorm
end
