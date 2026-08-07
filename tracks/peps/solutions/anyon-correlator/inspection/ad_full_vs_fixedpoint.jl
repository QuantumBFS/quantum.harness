# Pinning test: full-AD gradient (differentiate through every CTMRG iteration,
# alg_rrule = nothing) vs fixed-point-differentiation gradient, same init point.
# If full-AD matches the finite-difference slope but fixed-point-AD does not,
# the fixed-point differentiation machinery is the culprit.
include(joinpath(@__DIR__, "..", "scripts", "tc_peps.jl"))
using Printf, Random, Zygote

UP = UPSPACE
UV = uspace(2)
H0, _ = toric_code_hamiltonian(0.0, 0.0; P = UP)

function random_dense_tensor(D, P, Vsp)
    T = randn(ComplexF64, 2, 2, D, D, D, D)
    data = reshape(reshape(T, 4, D, D, D, D), 4, D^4)
    return normalize!(TensorMap(data, P, Vsp ⊗ Vsp ⊗ Vsp' ⊗ Vsp'), Inf)
end

function converge_fresh(ψ, χ; seed = 424242, tol = 1.0e-10, maxiter = 1000)
    Random.seed!(seed)
    env0 = CTMRGEnv(randn, ComplexF64, ψ, uenv(χ))
    return leading_boundary(env0, ψ; tol = tol, maxiter = maxiter, verbosity = 0)
end

boundary_struct = SimultaneousCTMRG(; tol = 1.0e-10, maxiter = 1000, verbosity = 0)
g_fixedpoint = PEPSKit.GradientAlgorithm(; alg = :FixedPointGradient, tol = 1.0e-6, maxiter = 10)

function fg_eval(ψ, env, alg_rrule)
    E, gs = withgradient(ψ) do ψv
        env′, info = PEPSKit.hook_pullback(leading_boundary, env, ψv, boundary_struct;
                                           alg_rrule = alg_rrule)
        return cost_function(ψv, env′, H0)
    end
    return E, only(gs)
end

frobnorm(g) = sqrt(sum(norm.(g.A) .^ 2))

function fd_check(ψ0, g, tag)
    ng = frobnorm(g)
    δarr = [-(g.A[i, j] / ng) for i in 1:2, j in 1:2]
    for α in [1e-3, 1e-2]
        ψp = InfinitePEPS([ψ0.A[i, j] + α * δarr[i, j] for i in 1:2, j in 1:2])
        ψm = InfinitePEPS([ψ0.A[i, j] - α * δarr[i, j] for i in 1:2, j in 1:2])
        envp, = converge_fresh(ψp, 20)
        envm, = converge_fresh(ψm, 20)
        φp, φm = cost_function(ψp, envp, H0), cost_function(ψm, envm, H0)
        slope = (φp - φm) / (2α)
        println(@sprintf("  %s α = %.3f: FD slope = %+.6e, AD predicted = %+.6e, ratio = %.3f",
                         tag, α, slope, -ng, slope / (-ng)))
        flush(stdout)
    end
end

Random.seed!(20260728)
ψ0 = InfinitePEPS([random_dense_tensor(2, UP, UV) for _ in 1:2, _ in 1:2])
env0, _ = converge_fresh(ψ0, 20)

println("=== fixed-point-differentiation gradient ==="); flush(stdout)
E1, g1 = fg_eval(ψ0, env0, g_fixedpoint)
println(@sprintf("  E = %+.10f, ‖g‖ = %.6e", E1, frobnorm(g1))); flush(stdout)
fd_check(ψ0, g1, "fixedpoint-AD")

println("\n=== full-AD gradient (alg_rrule = nothing) ==="); flush(stdout)
E2, g2 = fg_eval(ψ0, env0, nothing)
println(@sprintf("  E = %+.10f, ‖g‖ = %.6e", E2, frobnorm(g2))); flush(stdout)
fd_check(ψ0, g2, "full-AD")

dg = sqrt(sum(norm.(g1.A .- g2.A) .^ 2))
println(@sprintf("\n‖g_fixedpoint − g_fullAD‖ / ‖g_fullAD‖ = %.3e", dg / frobnorm(g2)))
flush(stdout)
