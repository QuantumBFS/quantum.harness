# Stage-wise SU inspection (ungraded): random V/P init -> contract -> SU ->
# ground-state checks. No Z2 symmetry, no AD. Verdict: E_cell -> -8 and
# site-resolved <A_s> = <B_p> = 1 mean SU + conventions are sound.
#
# Result: FAILED to reach the ground state (E_cell = -6.026) — the SU stall
# documented in ../M2_SU_FINDINGS.md. Usage: julia --project=julia-env inspection/su_ungraded_test.jl [seed] [nstep]

using LinearAlgebra, Printf, Dates, Random
using TensorKit, PEPSKit, MPSKit

include(joinpath(@__DIR__, "..", "scripts", "tc_peps.jl"))

const D_SU = 2
const CHI_SU = 20

logline(msg) = (println(msg); flush(stdout))

"Site-resolved stabilizers for an ungraded state (term op = -stabilizer)."
function stab_check(ψ, env)
    lat = fill(UPSPACE, 2, 2)
    s_op, p_op = star_op(1.0, UPSPACE), plaq_op(1.0, UPSPACE)
    vals = Float64[]
    for r in 1:2, c in 1:2
        Hs = empty_localoperator(lat)
        PEPSKit.add_term!(Hs, [CartesianIndex(r, c - 1), CartesianIndex(r, c), CartesianIndex(r + 1, c)], s_op)
        push!(vals, -real(expectation_value(ψ, Hs, env)))
        Hp = empty_localoperator(lat)
        PEPSKit.add_term!(Hp, [CartesianIndex(r - 1, c), CartesianIndex(r, c), CartesianIndex(r, c + 1)], p_op)
        push!(vals, -real(expectation_value(ψ, Hp, env)))
    end
    return vals
end

function main()
    seed = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : 1
    nstep = length(ARGS) >= 2 ? parse(Int, ARGS[2]) : 600
    logline("ungraded SU inspection · seed=$seed · nstep=$nstep")

    UP, UV = UPSPACE, uspace(D_SU)
    H0, _ = toric_code_hamiltonian(0.0, 0.0; P = UP)

    # -- stage 0: ungraded machinery check with the exact tensor --
    ψex = exact_peps(UP, UV)
    envex, _ = leading_boundary(CTMRGEnv(randn, ComplexF64, ψex, uenv(CHI_SU)), ψex;
                                tol = 1e-8, maxiter = 500, verbosity = 0)
    Eex = real(expectation_value(ψex, H0, envex))
    mex = maximum(abs(v - 1) for v in stab_check(ψex, envex))
    logline(@sprintf("[stage 0] exact tensor: E_cell = %+.12f, max stab dev = %.2e", Eex, mex))

    # -- stage 1: random V/P init (user's split construction, contracted) --
    Random.seed!(seed)
    V_arr = randn(2, 2, 2, 2)
    PE_arr = randn(2, 2, 2)
    PN_arr = randn(2, 2, 2)
    T0 = random_merged_tensor_VP(V_arr, PE_arr, PN_arr, UP, UV)
    ψ = InfinitePEPS(fill(T0, 2, 2))

    # -- stage 2: simple update (identity bond weights) --
    circuit = build_su_circuit(0.05; P = UP)
    alg = SimpleUpdate(; trunc = PEPSKit._get_fixedspacetrunc(ψ), imaginary_time = true)
    env = init_suweight(ψ, UV)
    env_prev = deepcopy(env)
    for i in 1:nstep
        ψ, env, ϵ = PEPSKit.su_iter(ψ, circuit, alg, env)
        if i % 25 == 0 || i == 1 || i == nstep
            diff = PEPSKit.compare_weights(env_prev, env)
            E = real(expectation_value(ψ, H0, CTMRGEnv(env)))
            logline(@sprintf("  SU iter %-4d E_cell ≈ %+.8f  |Δλ| = %.3e  ϵ = %.3e", i, E, diff, ϵ))
            env_prev = deepcopy(env)
            if diff < 1e-10
                logline("  SU bond weights converged at iter $i")
                break
            end
        end
    end

    # -- stage 3: ground-state checks --
    envf, infof = leading_boundary(CTMRGEnv(randn, ComplexF64, ψ, uenv(CHI_SU)), ψ;
                                   tol = 1e-8, maxiter = 500, verbosity = 0)
    E_cell = real(expectation_value(ψ, H0, envf))
    logline(@sprintf("[stage 3] post-SU: E_cell = %+.10f (per edge spin %+.10f), CTMRG converged = %s",
                     E_cell, E_cell / 8, infof.converged))
    vals = stab_check(ψ, envf)
    kinds = [isodd(i) ? "A_star" : "B_plaq" for i in 1:8]
    poss = [(r, c) for r in 1:2 for c in 1:2 for _ in 1:2]
    for (k, pos, v) in zip(kinds, poss, vals)
        logline(@sprintf("  %s %s: ⟨·⟩ = %+.8f", k, pos, v))
    end
    ok = abs(E_cell + 8) ≤ 1e-6 && all(v -> abs(v - 1) ≤ 1e-6, vals)
    logline(ok ? "SU INSPECTION PASSED: ground state reached (E_cell = −8, all stabilizers = 1)" :
                 "SU INSPECTION FAILED: not the toric-code ground state")
    return ok
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main() ? 0 : 1)
end
