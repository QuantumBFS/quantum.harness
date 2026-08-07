# Pinpoint the linesearch failure: replicate the optimizer's trial evaluations
# along the norm-preserving retract path at the (pseudo-)stuck point, and compare
# with the flat-space probe that showed smooth descent.
#   ψ_stuck ≈ init + 0.9·(−g/‖g‖)  (flat step reproducing f = −0.033 → −0.270)
# Then at ψ_stuck, along d = −g_stuck:
#   ϕ_retract(α) = cost(peps_retract((ψ, env), −g, α)[1])   vs   ϕ_flat(α)
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

function converge_fresh(ψ, χ; seed = 424242, tol = 1.0e-10, maxiter = 300)
    Random.seed!(seed)
    env0 = CTMRGEnv(randn, ComplexF64, ψ, uenv(χ))
    return leading_boundary(env0, ψ; tol = tol, maxiter = maxiter, verbosity = 0)
end

boundary_struct = SimultaneousCTMRG(; tol = 1.0e-10, maxiter = 300, verbosity = 0)
g_fp = PEPSKit.GradientAlgorithm(; alg = :FixedPointGradient, tol = 1.0e-6, maxiter = 10)

function fg_eval(ψ, env)
    E, gs = withgradient(ψ) do ψv
        env′, info = PEPSKit.hook_pullback(leading_boundary, env, ψv, boundary_struct;
                                           alg_rrule = g_fp)
        return cost_function(ψv, env′, H0)
    end
    return E, only(gs)
end

frobnorm(g) = sqrt(sum(norm.(g.A) .^ 2))

# ---- init + exact gradient ----
Random.seed!(20260728)
ψ0 = InfinitePEPS([random_dense_tensor(2, UP, UV) for _ in 1:2, _ in 1:2])
env0, _ = converge_fresh(ψ0, 20)
E0, g0 = fg_eval(ψ0, env0)
ng0 = frobnorm(g0)
println(@sprintf("init: E = %+.8f, ‖g‖ = %.4e", E0, ng0)); flush(stdout)

# ---- pseudo-stuck point: flat step 0.9 along −g/‖g‖ ----
ψs = InfinitePEPS([ψ0.A[i, j] - 0.9 * g0.A[i, j] / ng0 for i in 1:2, j in 1:2])
envs, _ = converge_fresh(ψs, 20)
Es, gs = fg_eval(ψs, envs)
ngs = frobnorm(gs)
println(@sprintf("pseudo-stuck: E = %+.8f (optimizer reached −0.270183), ‖g‖ = %.4e", Es, ngs))
flush(stdout)

# ---- exactness of the gradient at the stuck point (FD, flat) ----
δ = [-(gs.A[i, j] / ngs) for i in 1:2, j in 1:2]
for α in [1e-3, 1e-2]
    ψp = InfinitePEPS([ψs.A[i, j] + α * δ[i, j] for i in 1:2, j in 1:2])
    ψm = InfinitePEPS([ψs.A[i, j] - α * δ[i, j] for i in 1:2, j in 1:2])
    envp, = converge_fresh(ψp, 20)
    envm, = converge_fresh(ψm, 20)
    slope = (cost_function(ψp, envp, H0) - cost_function(ψm, envm, H0)) / (2α)
    println(@sprintf("  flat FD α = %.3f: slope = %+.6e (pred %+.6e)", α, slope, -ngs))
    flush(stdout)
end

# ---- the linesearch's actual path: norm-preserving retract along d = −g ----
println("\nretract-path evaluation (what the linesearch sees):"); flush(stdout)
x = (PEPSKit.peps_normalize(ψs), envs)
η = InfinitePEPS([-gs.A[i, j] for i in 1:2, j in 1:2])
for α in [0.0, 1e-4, 1e-3, 1e-2, 3e-2, 1e-1, 3e-1, 1.0]
    if α == 0.0
        ϕ = cost_function(ψs, envs, H0)
        println(@sprintf("  α = %6.4f: ϕ = %+.8f", α, ϕ))
    else
        (peps′, env′), ξ = PEPSKit.peps_retract(x, η, α)
        envr, = converge_fresh(peps′, 20)
        ϕ = cost_function(peps′, envr, H0)
        println(@sprintf("  α = %6.4f: ϕ(retract) = %+.8f", α, ϕ))
    end
    flush(stdout)
end
println("\nif ϕ(retract) is jagged/increasing while flat FD descends,")
println("the norm-preserving retract path is where the linesearch dies.")
