# M2 continuation — 10 additional GradientDescent + Armijo steps from the
# stage-C step-20 checkpoint (same process, same optimizer/retraction).
# Protocol (ratified 2026-07-29): D=2, χ=20, CTMRG (tol 1e-10, maxiter 500),
# checkpoint per accepted step, full per-step telemetry incl. all 8 stabilizers
# and the slow plaquette identified explicitly. Stop after 10 accepted steps and
# report the slow-plaquette trajectory separately.
#
# Usage: julia --project=julia-env scripts/ad_staged_gd_continue.jl [ckpt_dir]

using LinearAlgebra, Printf, Dates, Random, Statistics, JLD2
using TensorKit, PEPSKit, MPSKit
using Zygote

include(joinpath(@__DIR__, "ad_staged_gd.jl"))   # reuse helpers (no auto-run)

const CKPT = length(ARGS) >= 1 ? ARGS[1] :
    joinpath(@__DIR__, "..", "..", "..", "results", "20260729-090528-ad-staged-gd")
const NSTEPS = 10
const ST = Stage("C+", 20, 1.0e-10, 500, 1.0e-6, NSTEPS)

fmt4(v) = "[" * join([@sprintf("%+.6f", x) for x in v], " ") * "]"

function main()
    logline("continuation: loading checkpoint from $CKPT")
    d = load(joinpath(CKPT, "stageC_step20.jld2"))
    ψ = InfinitePEPS(d["tensors"])
    E_prev = d["E"]
    logline(@sprintf("resumed: stage %s, E = %+.10f, ‖g‖ = %.3e", d["stage"], E_prev, d["gradnorm"]))

    rundir = CKPT
    env, _ = stage_env(ψ, ST)
    _, initial_plaquettes = stabilizers(ψ, env)
    slow_start = minimum(initial_plaquettes)
    slow_traj = Float64[]
    E_hist = Float64[]
    for k in 1:NSTEPS
        t_step = time()
        E, g, info_fg = fg(ψ, env, ST)
        res = gd_step(ψ, E, g, info_fg, ST)
        if res === nothing
            logline("  step $k: ARMIJO FAILED — stop")
            break
        end
        ψ, Enew, ng, α, infot = res
        env, _ = stage_env(ψ, ST)
        a, b = stabilizers(ψ, env)
        islow = argmin(b)
        push!(slow_traj, b[islow])
        push!(E_hist, Enew)
        logline(@sprintf("  step %d: E_cell = %+.10f", k, Enew))
        logline("    ⟨Aₛ⟩ = " * fmt4(a))
        logline("    ⟨B_p⟩ = " * fmt4(b) * @sprintf("  (slow plaquette #%d = %+.6f)", islow, b[islow]))
        niter_ctm = length(infot.contraction_metrics)
        logline(@sprintf("    ‖g‖ = %.3e, α = %.4f, CTMRG iters ≈ %d, residual = %.2e, step time = %.1f s",
                         ng, α, niter_ctm, infot.convergence_error, time() - t_step))
        jldsave(joinpath(rundir, "contC_step$(k).jld2");
                tensors = ψ.A, E = Enew, gradnorm = ng, alpha = α,
                stabilizers = (a, b), stage = "C+")
        flush(stdout)
        E_prev = Enew
    end

    logline("\n--- slow-plaquette trajectory (10 accepted steps) ---")
    logline("  " * join([@sprintf("%+.6f", x) for x in slow_traj], " -> "))
    logline("E trajectory: " * join([@sprintf("%+.8f", x) for x in E_hist], " -> "))
    if !isempty(E_hist)
        imp = diff(vcat([d["E"]], E_hist))
        logline(@sprintf("slow ⟨B_p⟩: start %+0.6f → end %+0.6f; mean ΔE/step = %.2e",
                         slow_start, slow_traj[end], -mean(imp)))
    end
    return nothing
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
