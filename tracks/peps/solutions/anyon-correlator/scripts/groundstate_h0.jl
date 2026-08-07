# Legacy M2 simple-update route retained for inspection and comparison.
# This is not the completed random-start tied-AD driver; see ad_tied_gd.jl.
# Historical workflow: exact-tensor machinery check → random Z₂ init → SU warm
# start → CTMRG → AD fixedpoint polish → optional spectrum diagnostics.
#
# STATUS (2026-07-28, see M2_SU_FINDINGS.md): stage 0 passes (exact tensor gives
# E_cell = −8, stabilizers = 1 to 2e-16). Random-init full-circuit SU stalls at
# non-ground fixed points (product states / one-sector-pinned states), and AD from
# such a point shows a spurious near-zero gradient. The SU stage will be amended
# (stage-wise SU or product-state init — see M2_SU_FINDINGS.md §6); AD is currently
# suspended in this historical route. Optional spectrum/VUMPS diagnostics can be
# enabled with the 4th CLI argument `true`; they are not M2 acceptance gates.
#
# Usage: julia --project=julia-env scripts/groundstate_h0.jl [seed] [su_nstep] [ad_maxiter] [do_spectrum]

using LinearAlgebra, Printf, Dates, Random, JLD2
using TensorKit, PEPSKit, MPSKit

include(joinpath(@__DIR__, "tc_peps.jl"))

"Write a vector of NamedTuples to CSV (manual, no CSV.jl dependency)."
function write_csv(path, rows, header)
    open(path, "w") do io
        println(io, header)
        for r in rows
            println(io, join(string.(values(r)), ","))
        end
    end
    return path
end

const NSPIN_CELL = 8          # original edge spins per (2,2) composite cell (4 sites × 2)
const NSITE_CELL = 4          # composite PEPS sites per cell
const CHI = 20                # CTMRG environment dimension (Z2Space 10+10)
const CHI_SPOT = 40           # environment-convergence spot check
const D_PEPS = 2              # PEPS bond dimension

# ---------- small helpers ----------
logline(msg) = (println(msg); flush(stdout))

# NOTE (verified 2026-07-28): `expectation_value(peps, H, env)` returns the
# UNIT-CELL TOTAL — the sum of all terms of H, each evaluated once per cell
# (on the exact state: raw = −8.000000000000 = 4 stars + 4 plaquettes × (−1)).
energy_cell(peps, H, env) = real(expectation_value(peps, H, env))
energy_per_edge_spin(peps, H, env) = energy_cell(peps, H, env) / NSPIN_CELL
energy_per_composite_site(peps, H, env) = energy_cell(peps, H, env) / NSITE_CELL

"Converge a CTMRG environment with seeded retries (random graded envs can hit
degenerate LAPACK blocks on first draw)."
function converge_env(psi, χ, runseed; tol = 1.0e-8, maxiter = 500, attempts = 8)
    for k in 1:attempts
        Random.seed!(runseed + 1000k)
        env0 = CTMRGEnv(randn, ComplexF64, psi, envspace(χ))
        try
            return leading_boundary(env0, psi; tol = tol, maxiter = maxiter, verbosity = 0)
        catch err
            k == attempts && rethrow(err)
            logline(@sprintf("  env attempt %d failed (%s), retrying", k, typeof(err)))
        end
    end
end

"Site-resolved stabilizer expectations ⟨Aₛ⟩, ⟨B_p⟩ from the term table."
function stabilizers(peps, env)
    lattice = fill(PSPACE, 2, 2)
    rows = NamedTuple[]
    s_op, p_op = star_op(), plaq_op()
    for r in 1:2, c in 1:2
        star_sites = [CartesianIndex(r, c - 1), CartesianIndex(r, c), CartesianIndex(r + 1, c)]
        Hs = empty_localoperator(lattice)
        PEPSKit.add_term!(Hs, star_sites, s_op)   # term = −Aₛ
        val = real(expectation_value(peps, Hs, env))
        push!(rows, (kind = "A_star", center = "($r,$c)", value = -val))
        plaq_sites = [CartesianIndex(r - 1, c), CartesianIndex(r, c), CartesianIndex(r, c + 1)]
        Hp = empty_localoperator(lattice)
        PEPSKit.add_term!(Hp, plaq_sites, p_op)   # term = −B_p
        val = real(expectation_value(peps, Hp, env))
        push!(rows, (kind = "B_plaq", center = "($r,$c)", value = -val))
    end
    return rows
end

"SU warm start with progress logging; returns (peps, su_env, log_rows)."
function run_su(psi, dt, nstep, H; tol = 1e-10, check_every = 25)
    circuit = build_su_circuit(dt)
    alg = SimpleUpdate(; trunc = PEPSKit._get_fixedspacetrunc(psi), imaginary_time = true)
    env = init_suweight(psi, vspace(D_PEPS))
    env_prev = deepcopy(env)
    rows = NamedTuple[]
    for i in 1:nstep
        psi, env, ϵ = PEPSKit.su_iter(psi, circuit, alg, env)
        if i % check_every == 0 || i == 1 || i == nstep
            diff = PEPSKit.compare_weights(env_prev, env)
            E = energy_per_edge_spin(psi, H, CTMRGEnv(env))
            logline(@sprintf("  SU iter %-5d E/edge spin ≈ %+.8f  |Δλ| = %.3e  ϵ = %.3e", i, E, diff, ϵ))
            push!(rows, (iter = i, E = E, dlambda = diff, trunc_err = ϵ))
            env_prev = deepcopy(env)
            if diff < tol
                logline(@sprintf("  SU bond weights converged (|Δλ| < %.0e) at iter %d", tol, i))
                break
            end
        end
    end
    return psi, env, rows
end

function main()
    seed = length(ARGS) >= 1 ? parse(Int, ARGS[1]) : 20260728
    su_nstep = length(ARGS) >= 2 ? parse(Int, ARGS[2]) : 1000
    ad_maxiter = length(ARGS) >= 3 ? parse(Int, ARGS[3]) : 100
    do_spectrum = length(ARGS) >= 4 ? parse(Bool, ARGS[4]) : false

    rundir = joinpath(@__DIR__, "..", "..", "..", "results",
                      Dates.format(now(), "yyyymmdd-HHMMSS") * "-groundstate-h0")
    mkpath(rundir)
    logline("M2 ground state at h=0 · seed=$seed · run dir: $rundir")

    H0, term_table = toric_code_hamiltonian(0.0, 0.0)
    logline("Hamiltonian: $(length(H0.terms)) terms on the (2,2) composite cell " *
            "($(count(t -> t.kind == :star, term_table)) stars, " *
            "$(count(t -> t.kind == :plaquette, term_table)) plaquettes)")

    energy_rows = NamedTuple[]

    # ---- stage 0: machinery validation on the exact V/P tensor ----
    logline("\n[stage 0] exact V/P tensor machinery check (CTMRG χ=$CHI)")
    ψex = exact_peps()
    envex, info_ex = converge_env(ψex, CHI, seed)
    Eex_cell = energy_cell(ψex, H0, envex)
    logline(@sprintf("  exact state: E_cell = %+.12f (expect −8; per edge spin %+.12f), CTMRG converged = %s",
                     Eex_cell, Eex_cell / NSPIN_CELL, info_ex.converged))
    push!(energy_rows, (stage = "exact_vp", E = Eex_cell / NSPIN_CELL, note = "machinery check"))
    stab_ex = stabilizers(ψex, envex)
    maxdev_ex = maximum(r -> abs(r.value - 1), stab_ex)
    logline(@sprintf("  exact state: max |⟨stabilizer⟩ − 1| = %.3e", maxdev_ex))

    # ---- stage 1: random Z₂-symmetric init ----
    logline("\n[stage 1] random Z₂-graded init (seed $seed)")
    Random.seed!(seed)
    Vd2 = vspace(D_PEPS)
    ψ0 = InfinitePEPS(randn, ComplexF64, fill(PSPACE, 2, 2), fill(Vd2, 2, 2))

    # ---- stage 2: SU warm start ----
    logline("\n[stage 2] simple-update warm start (dt = 0.05, ≤ $su_nstep steps, tol 1e-10)")
    ψsu, suenv, su_rows = run_su(ψ0, 0.05, su_nstep, H0)
    write_csv(joinpath(rundir, "su_log.csv"), su_rows, "iter,E_per_edge_spin,dlambda,trunc_err")

    # ---- stage 3: CTMRG environment at χ=20 ----
    logline("\n[stage 3] CTMRG (χ=$CHI, tol 1e-8)")
    envsu, info_su = converge_env(ψsu, CHI, seed + 1)
    Esu_cell = energy_cell(ψsu, H0, envsu)
    logline(@sprintf("  post-SU: E_cell = %+.10f (per edge spin %+.10f), CTMRG converged = %s",
                     Esu_cell, Esu_cell / NSPIN_CELL, info_su.converged))
    push!(energy_rows, (stage = "su", E = Esu_cell / NSPIN_CELL, note = "dt=0.05"))
    stab_su = stabilizers(ψsu, envsu)
    for r in stab_su
        logline(@sprintf("  post-SU %s %s: ⟨·⟩ = %+.6f", r.kind, r.center, r.value))
    end

    # ---- stage 4: AD fixedpoint polish ----
    logline("\n[stage 4] AD fixedpoint (L-BFGS ≤ $ad_maxiter iters, grad tol 1e-6, boundary tol 1e-10)")
    boundary_alg = (; tol = 1.0e-10, alg = :SimultaneousCTMRG,
                    trunc = (; alg = :FixedSpaceTruncation), maxiter = 500)
    gradient_alg = (; tol = 1.0e-6, alg = :FixedPointGradient, maxiter = 10)
    optimizer_alg = (; alg = :LBFGS, tol = 1.0e-6, maxiter = ad_maxiter,
                     lbfgs_memory = 16, ls_maxiter = 3, ls_maxfg = 3)
    ψ, env, E, info_opt = fixedpoint(H0, ψsu, envsu; boundary_alg, gradient_alg,
                                     optimizer_alg, reuse_env = true, verbosity = 3)
    Eopt_cell = E                      # fixedpoint cost = unit-cell total
    Eopt = Eopt_cell / NSPIN_CELL      # per edge spin
    gradnorm_final = info_opt.gradnorms[end]
    logline(@sprintf("  post-AD: E_cell = %+.12f (per edge spin %+.12f), grad norm = %.3e, fg evals = %d",
                     Eopt_cell, Eopt, gradnorm_final, info_opt.fg_evaluations))
    push!(energy_rows, (stage = "ad_fixedpoint", E = Eopt, note = "gradnorm=$gradnorm_final"))

    # ---- stage 5: environment-convergence spot check χ=40 ----
    logline("\n[stage 5] χ=$CHI_SPOT spot check")
    env40, _ = converge_env(ψ, CHI_SPOT, seed + 2)
    E40 = energy_per_edge_spin(ψ, H0, env40)
    logline(@sprintf("  E/edge spin(χ=%d) = %+.12f, |ΔE| = %.3e", CHI_SPOT, E40, abs(E40 - Eopt)))
    push!(energy_rows, (stage = "chi$(CHI_SPOT)_spot", E = E40, note = "env convergence"))

    # ---- stage 6: site-resolved stabilizers ----
    logline("\n[stage 6] site-resolved stabilizers")
    stab = stabilizers(ψ, env)
    maxdev = maximum(r -> abs(r.value - 1), stab)
    for r in stab
        logline(@sprintf("  %s %s: ⟨·⟩ = %+.10f", r.kind, r.center, r.value))
    end
    write_csv(joinpath(rundir, "stabilizers_h0.csv"), stab, "kind,center,value")

    # ---- stages 7+8: optional legacy transfer-spectrum and VUMPS diagnostics ----
    if do_spectrum
        logline("\n[stage 7] transfer spectrum (correlation_length, num_vals=8)")
        ξ_h, ξ_v, λ_h, λ_v = correlation_length(ψ, env; num_vals = 8)
        spec_rows = NamedTuple[]
        for (dir, λs, ξ) in (("h", λ_h, ξ_h), ("v", λ_v, ξ_v))
            mags = sort(abs.(λs); rev = true)
            λ0 = first(mags)
            for (i, m) in enumerate(mags)
                push!(spec_rows, (direction = dir, index = i - 1, abs_lambda = m,
                                  ratio = m / λ0, xi = ξ))
            end
            logline("  dir $dir: |λ|/|λ₀| = " * join([@sprintf("%.3e", m / λ0) for m in mags], " ") *
                    @sprintf("  ξ = %.3e", ξ))
        end
        write_csv(joinpath(rundir, "spectrum_h0.csv"), spec_rows, "direction,index,abs_lambda,ratio,xi")

        logline("\n[stage 8] VUMPS boundary cross-check (χ=$CHI)")
        T = MultilineTransferPEPS(ψ, 1)
        mps0 = initialize_mps(T, fill(envspace(CHI), 2, 2))
        mps, env_v, ϵ_v = leading_boundary(mps0, T, VUMPS(; tol = 1.0e-8, verbosity = 1))
        λ_vumps = MPSKit.transfer_spectrum(mps; num_vals = 8)
        mags_v = sort(abs.(λ_vumps); rev = true)
        logline("  VUMPS: |λ|/|λ₀| = " * join([@sprintf("%.3e", m / mags_v[1]) for m in mags_v], " "))
        norm_ctm = network_value(ψ, env)
        norm_vumps = abs(prod(expectation_value(mps, T)))
        logline(@sprintf("  norm per cell: CTMRG %.6e, VUMPS %.6e", norm_ctm, norm_vumps))
    end

    # ---- acceptance gates ----
    logline("\n--- M2 acceptance gates ---")
    gates = NamedTuple[]
    push!(gates, (gate = "S0 exact-tensor machinery: E_cell = −8, stabilizers = 1 (≤ 1e-10)",
                  passed = abs(Eex_cell + 8) ≤ 1e-10 && maxdev_ex ≤ 1e-10,
                  detail = @sprintf("E_cell = %+.12f, max stab dev = %.2e", Eex_cell, maxdev_ex)))
    push!(gates, (gate = "A1 |E₀/N + 1| ≤ 1e-6 (target 1e-8)",
                  passed = abs(Eopt + 1) ≤ 1e-6,
                  detail = @sprintf("E/edge spin = %+.12f (E_cell = %+.12f)", Eopt, Eopt_cell)))
    push!(gates, (gate = "A2 stabilizers = 1 site-resolved ≤ 1e-6",
                  passed = maxdev ≤ 1e-6,
                  detail = @sprintf("max dev = %.2e", maxdev)))
    push!(gates, (gate = "A3 χ $CHI→$CHI_SPOT changes E/edge spin ≤ 1e-8",
                  passed = abs(E40 - Eopt) ≤ 1e-8,
                  detail = @sprintf("|ΔE| = %.2e", abs(E40 - Eopt))))
    if do_spectrum
        mags = sort(abs.(λ_h); rev = true)
        floor_i = findfirst(m -> m / mags[1] ≤ 1e-3, mags)
        ndominant = isnothing(floor_i) ? length(mags) : floor_i - 1
        push!(gates, (gate = "A4 spectrum: dominant multiplicity ≤ 2 above 1e-3 floor",
                      passed = ndominant ≤ 2,
                      detail = @sprintf("dominant count = %d", ndominant)))
    end
    allpass = true
    for g in gates
        allpass &= g.passed
        logline(@sprintf("[%s] %s\n       %s", g.passed ? "PASS" : "FAIL", g.gate, g.detail))
    end
    logline(allpass ? "ALL M2 GATES PASSED" : "SOME M2 GATES FAILED")

    write_csv(joinpath(rundir, "energy_convergence.csv"), energy_rows, "stage,E,note")
    jldsave(joinpath(rundir, "groundstate_h0.jld2");
            seed, D = D_PEPS, chi = CHI, peps_tensors = ψ.A,
            E_per_spin = Eopt, gradnorm = gradnorm_final,
            gates = [(g.gate, g.passed, g.detail) for g in gates])
    artifacts = ["energy_convergence.csv", "stabilizers_h0.csv", "su_log.csv", "groundstate_h0.jld2"]
    do_spectrum && push!(artifacts, "spectrum_h0.csv")
    logline("artifacts: $rundir (" * join(artifacts, ", ") * ")")
    return allpass
end

if abspath(PROGRAM_FILE) == @__FILE__
    exit(main() ? 0 : 1)
end
