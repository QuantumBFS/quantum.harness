# AD gradient diagnosis for the failed M2 primary run (seed 20260728).
# Replicates fixedpoint's exact fg evaluation at the fresh random init, then checks:
#   (a) inner CTMRG convergence quality (tol, truncation error, condition number);
#   (b) gradient-solve convergence: FixedPointGradient maxiter 10 vs 100;
#   (c) AD vs finite-difference directional derivative along the descent direction;
#   (d) smoothness of the energy along the linesearch line.
include(joinpath(@__DIR__, "..", "scripts", "tc_peps.jl"))
using Printf, Random, Zygote

UP = UPSPACE
UV = uspace(2)
H0, _ = toric_code_hamiltonian(0.0, 0.0; P = UP)

function random_dense_tensor(D, P, Vsp)
    T = randn(ComplexF64, 2, 2, D, D, D, D)
    data = reshape(reshape(T, 4, D, D, D, D), 4, D^4)
    return normalize!(TensorMap(data, P, Vsp ⊗ Vsp ⊗ Vsp' ⊗ Vsp'), Inf
    )
end

function converge_fresh(ψ, χ; seed = 424242, tol = 1.0e-10, maxiter = 1000)
    Random.seed!(seed)
    env0 = CTMRGEnv(randn, ComplexF64, ψ, uenv(χ))
    return leading_boundary(env0, ψ; tol = tol, maxiter = maxiter, verbosity = 0)
end

boundary_struct = SimultaneousCTMRG(; tol = 1.0e-10, maxiter = 1000, verbosity = 0)

"One fg evaluation exactly as fixedpoint does it (given a GradientAlgorithm struct)."
function fg_eval(ψ, env, gradient_struct)
    E, gs = withgradient(ψ) do ψv
        env′, info = PEPSKit.hook_pullback(leading_boundary, env, ψv, boundary_struct;
                                           alg_rrule = gradient_struct)
        return cost_function(ψv, env′, H0)
    end
    return E, only(gs)
end

# rebuild the failed run's init (same seed)
Random.seed!(20260728)
ψ0 = InfinitePEPS([random_dense_tensor(2, UP, UV) for _ in 1:2, _ in 1:2])

println("=== (a) inner environment quality ==="); flush(stdout)
env0, info0 = converge_fresh(ψ0, 20)
println("  converged = $(info0.converged), convergence_error = $(info0.convergence_error)")
println("  contraction_metrics (last) = $(info0.contraction_metrics[end])")
flush(stdout)

println("\n=== (b) gradient-solve convergence: maxiter 10 vs 100 ==="); flush(stdout)
g_alg10 = PEPSKit.GradientAlgorithm(; alg = :FixedPointGradient, tol = 1.0e-6, maxiter = 10)
g_alg100 = PEPSKit.GradientAlgorithm(; alg = :FixedPointGradient, tol = 1.0e-8, maxiter = 100)
E10, g10 = fg_eval(ψ0, env0, g_alg10)
println(@sprintf("  maxiter=10:  E = %+.10f, ‖g‖ = %.6e", E10, sqrt(sum(norm.(g10.A) .^ 2))))
flush(stdout)
E100, g100 = fg_eval(ψ0, env0, g_alg100)
println(@sprintf("  maxiter=100: E = %+.10f, ‖g‖ = %.6e", E100, sqrt(sum(norm.(g100.A) .^ 2))))
dg = sqrt(sum(norm.(g10.A .- g100.A) .^ 2))
ng = sqrt(sum(norm.(g100.A) .^ 2))
println(@sprintf("  relative gradient difference ‖g10−g100‖/‖g100‖ = %.3e", dg / ng))
flush(stdout)

println("\n=== (c)+(d) finite-difference check along d = −g100/‖g100‖ ==="); flush(stdout)
# descent direction: negative unit-Frobenius-norm gradient, applied in flat tensor space
# descent direction: negative unit-Frobenius-norm gradient, applied in flat tensor space
δarr = [-(g100.A[i, j] / ng) for i in 1:2, j in 1:2]
function cost_at(ψ)
    env, = converge_fresh(ψ, 20)
    return cost_function(ψ, env, H0)
end
φ0 = cost_at(ψ0)
println(@sprintf("  φ(0) = %+.10f, predicted slope ⟨g,−g/‖g‖⟩ = %.6e", φ0, -ng))
for α in [1e-4, 1e-3, 1e-2, 3e-2, 1e-1, 3e-1]
    ψp = InfinitePEPS([ψ0.A[i, j] + α * δarr[i, j] for i in 1:2, j in 1:2])
    ψm = InfinitePEPS([ψ0.A[i, j] - α * δarr[i, j] for i in 1:2, j in 1:2])
    φp, φm = cost_at(ψp), cost_at(ψm)
    slope = (φp - φm) / (2α)
    println(@sprintf("  α = %7.4f: φ(+) = %+.8f, φ(−) = %+.8f, FD slope = %+.4e, |FD−pred| = %.2e",
                     α, φp, φm, slope, abs(slope - (-ng))))
    flush(stdout)
end
println("\ninterpretation: FD slope ≈ predicted (−‖g‖) => gradient OK;")
println("FD slope ≈ 0 or sign-reversed => gradient solve/environment inconsistent;")
println("jagged φ at tiny α => environment noise dominates the energy landscape.")
