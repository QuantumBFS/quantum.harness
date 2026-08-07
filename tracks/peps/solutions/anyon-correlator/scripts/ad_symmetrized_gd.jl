# Symmetrized GradientDescent test: does per-step RotateReflect symmetrization
# prevent the one-defect local minimum from random init?
# Rationale: the exact TC state is translation-uniform (4 identical tensors);
# the defect state found by plain GD is not. Projecting state and gradient onto
# the C4-symmetric submanifold each step should remove defect basins.
# Same seed (20260728), same Armijo stepper as ad_staged_gd.jl.
include(joinpath(@__DIR__, "ad_staged_gd.jl"))
using Printf, Random, JLD2

const ST = Stage("symm", 12, 1.0e-8, 150, 1.0e-7, 35)
const SYMM = PEPSKit.RotateReflect()
fmt4(v) = "[" * join([@sprintf("%+.5f", x) for x in v], " ") * "]"

function symm_gd_step(ψ, E0, g, st::Stage)
    PEPSKit.symmetrize!(g, SYMM)   # project gradient onto the symmetric submanifold
    ng = frobnorm(g)
    δ = [-(g.A[i, j] / ng) for i in 1:2, j in 1:2]
    α = 0.3
    for _ in 1:12
        ψt = InfinitePEPS([ψ.A[i, j] + α * δ[i, j] for i in 1:2, j in 1:2])
        ψt = PEPSKit.peps_normalize(ψt)
        PEPSKit.symmetrize!(ψt, SYMM)   # project state back to the symmetric submanifold
        envt, infot = stage_env(ψt, st)
        ϕ = cost_function(ψt, envt, H0)
        ϕ ≤ E0 + 1e-4 * α * (-ng) && return ψt, ϕ, ng, α, infot
        α /= 2
    end
    return nothing
end

function main()
    seed = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : 20260728
    logline("symmetrized GD test (seed $seed, χ=12, tol 1e-8, ≤35 steps)")
    Random.seed!(seed)
    ψ = InfinitePEPS([random_dense_tensor(2, UP, UV) for _ in 1:2, _ in 1:2])
    env, _ = stage_env(ψ, ST)
    rundir = joinpath(@__DIR__, "..", "..", "..", "results",
                      Dates.format(now(), "yyyymmdd-HHMMSS") * "-ad-symm-gd")
    mkpath(rundir)
    for k in 1:(ST.nsteps)
        t_step = time()
        E, g, info_fg = fg(ψ, env, ST)
        res = symm_gd_step(ψ, E, g, ST)
        if res === nothing
            logline("  step $k: ARMIJO FAILED — stop")
            break
        end
        ψ, Enew, ng, α, infot = res
        env, _ = stage_env(ψ, ST)
        a, b = stabilizers(ψ, env)
        logline(@sprintf("  step %2d: E = %+.10f, min⟨B⟩ = %+.5f, ‖g‖ = %.2e, α = %.3f (%.0f s)",
                         k, Enew, minimum(b), ng, α, time() - t_step))
        (k % 5 == 0) && logline("    ⟨B_p⟩ = " * fmt4(b))
        jldsave(joinpath(rundir, "symm_step$(k).jld2"); tensors = ψ.A, E = Enew)
        flush(stdout)
    end

    # acceptance check at χ=20, tol 1e-10
    envf, infof = leading_boundary(CTMRGEnv(randn, ComplexF64, ψ, uenv(20)), ψ;
                                   tol = 1.0e-10, maxiter = 500, verbosity = 0)
    E_cell = real(expectation_value(ψ, H0, envf))
    a, b = stabilizers(ψ, envf)
    pass = abs(E_cell + 8) ≤ 1e-6 &&
           maximum(abs(x - 1) for x in a) ≤ 1e-6 &&
           maximum(abs(x - 1) for x in b) ≤ 1e-6
    logline(@sprintf("final: E_cell = %+.10f", E_cell))
    logline("  ⟨Aₛ⟩ = " * fmt4(a))
    logline("  ⟨B_p⟩ = " * fmt4(b))
    logline(pass ? "VERDICT: symmetrized GD reaches the ground state" :
                   "VERDICT: symmetrized GD did NOT reach the ground state")
    return pass
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main() ? 0 : 1)
end
