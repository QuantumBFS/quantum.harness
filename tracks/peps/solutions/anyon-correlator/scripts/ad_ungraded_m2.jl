# M2 primary test — direct CTMRG-based variational (AD) optimization at h = 0,
# ungraded, from a genuinely fresh generic random merged PEPS. No SU before AD.
# FAST PROFILE (test phase, approved 2026-07-28): CTMRG maxiter 300 (measured
# convergence needs fewer), L-BFGS ≤ 60 iters, χ = 20/30, all checks batched in
# one process to amortize AD compilation. Tolerances stay tight (1e-10) because
# a loose environment makes the energy landscape jagged and breaks linesearches.
#
# Protocol (ratified 2026-07-28):
#   fresh generic random merged InfinitePEPS (dense ℂ^4 physical, ℂ^2 virtual,
#   4 independent tensors on the (2,2) cell, Inf-normalized, seed recorded)
#   → converged CTMRG environment (χ = 20) → initial E_cell + 8 stabilizers
#   → AD fixedpoint variational energy optimization (exact tensor only as the
#     stage-0 benchmark, never as initialization)
#   → final E_cell + 8 stabilizers at χ = 20, stability spot at χ = 30
#   → FD smoothness probe at the final point (linesearch-failure diagnostic).
#
# Pass criteria: |E_cell + 8| ≤ 1e-6, max|⟨Aₛ⟩−1| ≤ 1e-6, max|⟨B_p⟩−1| ≤ 1e-6,
# stable under χ increase, and E_cell ≥ −8 − 1e-6.
#
# Usage: julia --project=julia-env scripts/ad_ungraded_m2.jl [seed] [ad_maxiter]

using LinearAlgebra, Printf, Dates, Random
using TensorKit, PEPSKit, MPSKit

include(joinpath(@__DIR__, "tc_peps.jl"))

const UP = UPSPACE
const UV = uspace(2)
const CHI = 20
const CHI_SPOT = 30
const CTM_MAXITER = 300

logline(msg) = (println(msg); flush(stdout))

"Generic random dense merged PEPSTensor (physical 2×2 fused, virtual D), Inf-normalized."
function random_dense_tensor(D, P, Vsp)
    T = randn(ComplexF64, 2, 2, D, D, D, D)
    data = reshape(reshape(T, 4, D, D, D, D), 4, D^4)
    return normalize!(TensorMap(data, P, Vsp ⊗ Vsp ⊗ Vsp' ⊗ Vsp'), Inf)
end

"Converge a fresh ungraded CTMRG environment (fixed init seed for determinism)."
function converge_fresh(ψ, χ; seed = 424242, tol = 1.0e-8, maxiter = CTM_MAXITER)
    Random.seed!(seed)
    env0 = CTMRGEnv(randn, ComplexF64, ψ, uenv(χ))
    return leading_boundary(env0, ψ; tol = tol, maxiter = maxiter, verbosity = 0)
end

"(E_cell, [4×⟨Aₛ⟩, 4×⟨B_p⟩]) for an ungraded state. Term op = −stabilizer."
function evaluate(ψ, H0, env)
    E_cell = real(expectation_value(ψ, H0, env))
    lat = fill(UP, 2, 2)
    s_op, p_op = star_op(1.0, UP), plaq_op(1.0, UP)
    a = Float64[]; b = Float64[]
    for r in 1:2, c in 1:2
        Hs = empty_localoperator(lat)
        PEPSKit.add_term!(Hs, [CartesianIndex(r, c - 1), CartesianIndex(r, c), CartesianIndex(r + 1, c)], s_op)
        push!(a, -real(expectation_value(ψ, Hs, env)))
        Hp = empty_localoperator(lat)
        PEPSKit.add_term!(Hp, [CartesianIndex(r - 1, c), CartesianIndex(r, c), CartesianIndex(r, c + 1)], p_op)
        push!(b, -real(expectation_value(ψ, Hp, env)))
    end
    return E_cell, a, b
end

fmt(v) = "[" * join([@sprintf("%+.6f", x) for x in v], " ") * "]"

"FD smoothness probe along direction g (unit-normalized) at point ψ — same process."
function fd_probe(ψ, H0, g, tag)
    ng = sqrt(sum(norm.(g.A) .^ 2))
    ng == 0 && return nothing
    δarr = [-(g.A[i, j] / ng) for i in 1:2, j in 1:2]
    logline("  FD probe along −g/‖g‖ ($tag, ‖g‖ = $(@sprintf("%.3e", ng))):")
    for α in [1e-3, 1e-2, 5e-2]
        ψp = InfinitePEPS([ψ.A[i, j] + α * δarr[i, j] for i in 1:2, j in 1:2])
        ψm = InfinitePEPS([ψ.A[i, j] - α * δarr[i, j] for i in 1:2, j in 1:2])
        envp, = converge_fresh(ψp, CHI)
        envm, = converge_fresh(ψm, CHI)
        φp, φm = cost_function(ψp, envp, H0), cost_function(ψm, envm, H0)
        slope = (φp - φm) / (2α)
        logline(@sprintf("    α = %6.3f: φ(+) = %+.8f, φ(−) = %+.8f, FD slope = %+.5e (pred %+.5e)",
                         α, φp, φm, slope, -ng))
    end
    return nothing
end

function main()
    seed = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : 20260728
    ad_maxiter = length(ARGS) >= 2 ? parse(Int, ARGS[2]) : 60
    logline("M2 primary AD test (ungraded, fresh random init, no SU, fast profile) · seed=$seed")

    H0, _ = toric_code_hamiltonian(0.0, 0.0; P = UP)

    # ---- benchmark: exact tensor machinery check (benchmark only, not init) ----
    ψex = exact_peps(UP, UV)
    envex, _ = converge_fresh(ψex, CHI)
    Eex, aex, bex = evaluate(ψex, H0, envex)
    logline(@sprintf("[benchmark] exact tensor: E_cell = %+.12f, max stab dev = %.2e",
                     Eex, max(maximum(abs(x - 1) for x in aex), maximum(abs(x - 1) for x in bex))))

    # ---- fresh generic random merged PEPS ----
    Random.seed!(seed)
    ψ0 = InfinitePEPS([random_dense_tensor(2, UP, UV) for _ in 1:2, _ in 1:2])
    env0, _ = converge_fresh(ψ0, CHI)
    E0, a0, b0 = evaluate(ψ0, H0, env0)
    logline(@sprintf("[init] E_cell = %+.6f", E0))
    logline("  init ⟨Aₛ⟩ = " * fmt(a0))
    logline("  init ⟨B_p⟩ = " * fmt(b0))

    # ---- AD fixedpoint variational optimization ----
    boundary_alg = (; tol = 1.0e-10, alg = :SimultaneousCTMRG,
                    trunc = (; alg = :FixedSpaceTruncation), maxiter = CTM_MAXITER)
    gradient_alg = (; tol = 1.0e-6, alg = :FixedPointGradient, maxiter = 10)
    optimizer_alg = (; alg = :GradientDescent, tol = 1.0e-6, maxiter = ad_maxiter,
                     ls_maxiter = 3, ls_maxfg = 3)
    logline("[AD] fixedpoint: GradientDescent ≤ $ad_maxiter iters, grad tol 1e-6, boundary (tol 1e-10, maxiter $CTM_MAXITER), reuse_env = false")
    ψ, env, E, info = fixedpoint(H0, ψ0, env0; boundary_alg, gradient_alg,
                                 optimizer_alg, reuse_env = false, verbosity = 3)
    logline(@sprintf("[AD] done: fg evals = %d, final grad norm = %.3e",
                     info.fg_evaluations, info.gradnorms[end]))
    logline("  E trace: " * join([@sprintf("%.4f", c) for c in info.costs], " -> "))
    logline("  ‖∇‖ trace: " * join([@sprintf("%.2e", g) for g in info.gradnorms], " -> "))

    # ---- final evaluation at χ=20 and stability spot at χ=30 ----
    envf, infof = converge_fresh(ψ, CHI)
    Ef, af, bf = evaluate(ψ, H0, envf)
    env30, _ = converge_fresh(ψ, CHI_SPOT)
    E30, a30, b30 = evaluate(ψ, H0, env30)

    chi_stable = abs(E30 - Ef) ≤ 1e-6 &&
                 maximum(abs.(a30 .- af)) ≤ 1e-6 && maximum(abs.(b30 .- bf)) ≤ 1e-6
    pass = abs(Ef + 8) ≤ 1e-6 &&
           maximum(abs(x - 1) for x in af) ≤ 1e-6 &&
           maximum(abs(x - 1) for x in bf) ≤ 1e-6 &&
           Ef ≥ -8 - 1e-6 && chi_stable

    logline("\n--- M2 primary AD test — final report ---")
    logline("seed: $seed")
    logline(@sprintf("initial E_cell = %+.6f (genuinely random init)", E0))
    logline("  init ⟨Aₛ⟩ = " * fmt(a0) * "   init ⟨B_p⟩ = " * fmt(b0))
    logline(@sprintf("final E_cell (χ=%d) = %+.10f", CHI, Ef))
    logline("  final ⟨Aₛ⟩ = " * fmt(af))
    logline("  final ⟨B_p⟩ = " * fmt(bf))
    logline("CTMRG converged: $(infof.converged)")
    logline(@sprintf("χ %d→%d stability: |ΔE| = %.2e, max |Δstab| = %.2e → %s",
                     CHI, CHI_SPOT, abs(E30 - Ef),
                     max(maximum(abs.(a30 .- af)), maximum(abs.(b30 .- bf))),
                     chi_stable ? "stable" : "UNSTABLE"))
    logline(pass ? "VERDICT: M2 PASSED" : "VERDICT: M2 FAILED")

    # ---- linesearch-failure diagnostic (same process, cheap) ----
    logline("\n--- FD smoothness probe at the final point ---")
    fd_probe(ψ, H0, info.last_gradient, "final point")
    return pass
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main() ? 0 : 1)
end
