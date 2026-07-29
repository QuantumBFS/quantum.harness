# M2 staged GradientDescent driver — one Julia process, compilation paid once.
# Protocol (ratified 2026-07-28):
#   Stage A: minimal descent test — seed 20260728, D=2, χ=8, CTMRG (tol 1e-6,
#     maxiter 50), exactly 5 ACCEPTED steps, raw −g direction, Armijo backtracking
#     (no Wolfe/L-BFGS). Per accepted step: iteration, energy, grad norm, accepted
#     step size, CTMRG iterations+residual, wall time; checkpoint saved per step.
#   Stage B: only if all 5 Stage-A energies decrease — χ=12, tol 1e-8,
#     maxiter 150, ≤20 more steps.
#   Stage C: final acceptance — continue from checkpoint, χ=20, tol 1e-10,
#     maxiter 300, only necessary refinement steps; report E_cell + 4⟨Aₛ⟩ + 4⟨B_p⟩.
# Compilation time is distinguished from numerical runtime (flushed markers).
#
# Usage: julia --project=julia-env scripts/ad_staged_gd.jl

using LinearAlgebra, Printf, Dates, Random, JLD2
using TensorKit, PEPSKit, MPSKit
using Zygote

include(joinpath(@__DIR__, "tc_peps.jl"))

const UP = UPSPACE
const UV = uspace(2)
const H0, _ = toric_code_hamiltonian(0.0, 0.0; P = UP)
const T0 = time()
logline(msg) = (println(@sprintf("[%8.1f s] %s", time() - T0, msg)); flush(stdout))

"Generic random dense merged PEPSTensor (physical 2×2 fused, virtual D), Inf-normalized."
function random_dense_tensor(D, P, Vsp)
    T = randn(ComplexF64, 2, 2, D, D, D, D)
    data = reshape(reshape(T, 4, D, D, D, D), 4, D^4)
    return normalize!(TensorMap(data, P, Vsp ⊗ Vsp ⊗ Vsp' ⊗ Vsp'), Inf)
end

struct Stage
    name::String
    χ::Int
    ctm_tol::Float64
    ctm_maxiter::Int
    grad_tol::Float64
    nsteps::Int
end

stage_env(ψ, st::Stage) = leading_boundary(
    CTMRGEnv(randn, ComplexF64, ψ, uenv(st.χ)), ψ;
    tol = st.ctm_tol, maxiter = st.ctm_maxiter, verbosity = 0)

"fg evaluation (energy + fixed-point-AD gradient + CTMRG diagnostics)."
function fg(ψ, env, st::Stage)
    bnd = SimultaneousCTMRG(; tol = st.ctm_tol, maxiter = st.ctm_maxiter, verbosity = 0)
    galg = PEPSKit.GradientAlgorithm(; alg = :FixedPointGradient,
                                     tol = st.grad_tol, maxiter = 10)
    E, gs = withgradient(ψ) do ψv
        env′, info = PEPSKit.hook_pullback(leading_boundary, env, ψv, bnd;
                                           alg_rrule = galg)
        return cost_function(ψv, env′, H0)
    end
    env′, info = leading_boundary(env, ψ, bnd)
    return E, only(gs), info
end

frobnorm(g) = sqrt(sum(norm.(g.A) .^ 2))

"One Armijo-backtracking GradientDescent step; returns (ψ_new, E_new, gnorm, α, info) or nothing on failure."
function gd_step(ψ, E0, g, info_fg, st::Stage)
    ng = frobnorm(g)
    δ = [-(g.A[i, j] / ng) for i in 1:2, j in 1:2]
    slope = -ng
    α = 0.3
    for _ in 1:12
        ψt = InfinitePEPS([ψ.A[i, j] + α * δ[i, j] for i in 1:2, j in 1:2])
        ψt = PEPSKit.peps_normalize(ψt)
        envt, infot = stage_env(ψt, st)
        ϕ = cost_function(ψt, envt, H0)
        if ϕ ≤ E0 + 1e-4 * α * slope
            return ψt, ϕ, ng, α, infot
        end
        α /= 2
    end
    return nothing
end

"Run one stage; returns (ψ, E_history, all_decreased)."
function run_stage(ψ, st::Stage, rundir, ckpt_prefix)
    logline("--- stage $(st.name): χ=$(st.χ), CTMRG (tol $(st.ctm_tol), maxiter $(st.ctm_maxiter)), ≤$(st.nsteps) steps ---")
    env, info0 = stage_env(ψ, st)
    Es = Float64[]
    decreased = true
    for k in 1:(st.nsteps)
        E, g, info_fg = fg(ψ, env, st)
        res = gd_step(ψ, E, g, info_fg, st)
        if res === nothing
            logline("  step $k: ARMIJO FAILED (no decrease in 12 halvings) — stop stage")
            return ψ, Es, false
        end
        ψ, Enew, ng, α, infot = res
        decreased &= Enew < E
        env, _ = stage_env(ψ, st)
        push!(Es, Enew)
        niter_ctm = length(infot.contraction_metrics)
        logline(@sprintf("  step %d: E = %+.10f, ‖g‖ = %.3e, α = %.4f, CTMRG iters ≈ %d, residual = %.2e",
                         k, Enew, ng, α, niter_ctm, infot.convergence_error))
        jldsave(joinpath(rundir, "$(ckpt_prefix)_step$(k).jld2");
                tensors = ψ.A, E = Enew, gradnorm = ng, alpha = α, stage = st.name)
    end
    return ψ, Es, decreased && length(Es) == st.nsteps
end

"Site-resolved stabilizers (ungraded)."
function stabilizers(ψ, env)
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
    return a, b
end
fmt(v) = "[" * join([@sprintf("%+.6f", x) for x in v], " ") * "]"

function main()
    logline("warmup: packages loaded, compiling stage functions now (compilation time, not numerical)")
    rundir = joinpath(@__DIR__, "..", "..", "..", "results",
                      Dates.format(now(), "yyyymmdd-HHMMSS") * "-ad-staged-gd")
    mkpath(rundir)
    logline("run dir: $rundir")

    logline("first CTMRG evaluation next (triggers main numerical compilation)")
    Random.seed!(20260728)
    ψ = InfinitePEPS([random_dense_tensor(2, UP, UV) for _ in 1:2, _ in 1:2])

    stA = Stage("A", 8, 1.0e-6, 50, 1.0e-5, 5)
    ψ, EsA, okA = run_stage(ψ, stA, rundir, "stageA")
    logline("stage A verdict: " * (okA ? "all 5 energies decreased — proceed to B" : "STOP (energies not all decreasing)"))
    okA || return false

    logline("first optimizer iteration of stage B next")
    stB = Stage("B", 12, 1.0e-8, 150, 1.0e-7, 20)
    ψ, EsB, okB = run_stage(ψ, stB, rundir, "stageB")
    logline("stage B done: E trace ends at $(isempty(EsB) ? "n/a" : @sprintf("%.8f", EsB[end]))")

    logline("stage C: final acceptance (χ=20, tol 1e-10, maxiter 300)")
    stC = Stage("C", 20, 1.0e-10, 300, 1.0e-6, 20)
    ψ, EsC, _ = run_stage(ψ, stC, rundir, "stageC")

    # final acceptance evaluation
    envf, infof = leading_boundary(CTMRGEnv(randn, ComplexF64, ψ, uenv(20)), ψ;
                                   tol = 1.0e-10, maxiter = 300, verbosity = 0)
    E_cell = real(expectation_value(ψ, H0, envf))
    a, b = stabilizers(ψ, envf)
    env30, _ = leading_boundary(CTMRGEnv(randn, ComplexF64, ψ, uenv(30)), ψ;
                                tol = 1.0e-10, maxiter = 300, verbosity = 0)
    E30 = real(expectation_value(ψ, H0, env30))
    stable = abs(E30 - E_cell) ≤ 1e-6
    pass = abs(E_cell + 8) ≤ 1e-6 &&
           maximum(abs(x - 1) for x in a) ≤ 1e-6 &&
           maximum(abs(x - 1) for x in b) ≤ 1e-6 &&
           E_cell ≥ -8 - 1e-6 && stable

    logline("\n--- M2 staged-GD acceptance report ---")
    logline("seed: 20260728")
    logline(@sprintf("final E_cell (χ=20) = %+.10f", E_cell))
    logline("  final ⟨Aₛ⟩ = " * fmt(a))
    logline("  final ⟨B_p⟩ = " * fmt(b))
    logline("CTMRG converged: $(infof.converged)")
    logline(@sprintf("χ 20→30 stability: |ΔE| = %.2e → %s", abs(E30 - E_cell), stable ? "stable" : "UNSTABLE"))
    logline(pass ? "VERDICT: M2 PASSED" : "VERDICT: M2 FAILED")
    return pass
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main() ? 0 : 1)
end
