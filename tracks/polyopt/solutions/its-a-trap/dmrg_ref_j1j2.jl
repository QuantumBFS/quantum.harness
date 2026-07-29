#!/usr/bin/env julia
# dmrg_ref_j1j2.jl — variational UPPER bounds for the J1-J2 chain, N=100 PBC
# (Phase 2a; probe order fixed by the plan: 0.5 sanity -> 0.2 -> 1.0, then
# 0.4/0.6/0.8 released on measured cost). Terminology (LAW.md): these are
# "variational upper bounds"; J2=0.5 must reproduce the exact MG value
# -0.375/site (sanity gate).
# H = Σ S_i·S_{i+1} + J2 Σ S_i·S_{i+2}, PBC (wraparound bonds included).
# Output: dmrg_refs.json in OUTDIR (arg 1), per-J2 convergence evidence.
using ITensors, ITensorMPS, Printf

const OUTDIR = length(ARGS) >= 1 ? ARGS[1] : "."
const J2LIST = length(ARGS) >= 2 ? parse.(Float64, split(ARGS[2], ",")) : [0.5, 0.2, 1.0]
const N = 100
mkpath(OUTDIR)

function run_point(J2)
    sites = siteinds("S=1/2", N; conserve_qns = true)
    ampo = OpSum()
    for j in 1:N            # NN bonds incl. wraparound
        k = mod1(j + 1, N)
        ampo += "Sz", j, "Sz", k
        ampo += 0.5, "S+", j, "S-", k
        ampo += 0.5, "S-", j, "S+", k
    end
    if J2 != 0
        for j in 1:N        # NNN bonds incl. wraparound
            k = mod1(j + 2, N)
            ampo += J2, "Sz", j, "Sz", k
            ampo += 0.5 * J2, "S+", j, "S-", k
            ampo += 0.5 * J2, "S-", j, "S+", k
        end
    end
    H = MPO(ampo, sites)
    psi0 = MPS(sites, n -> isodd(n) ? "Up" : "Dn")
    nsweeps = 18
    maxdim = [20, 50, 100, 100, 200, 200, 300, 300, 400]
    cutoff = [1e-10]
    obs = DMRGObserver(; energy_tol = 0.0)   # collect per-sweep energies
    t0 = time()
    energy, psi = dmrg(H, psi0; nsweeps, maxdim, cutoff, observer = obs, outputlevel = 1)
    wall = time() - t0
    es = obs.energies
    drift = length(es) >= 2 ? abs(es[end] - es[end-1]) / N : NaN
    chi = maxlinkdim(psi)
    @printf("J2=%.2f  E/N=%.10f  chi=%d  sweeps=%d  drift/site=%.2e  wall=%.0fs\n",
            J2, energy / N, chi, length(es), drift, wall)
    return (; J2, e_site = energy / N, chi, sweeps = length(es), drift_site = drift, wall)
end

results = []
for J2 in J2LIST
    r = run_point(J2)
    push!(results, r)
    # flush incrementally
    open(joinpath(OUTDIR, "dmrg_refs.json"), "w") do io
        entries = ["\"$(r.J2)\": {\"e_site\": $(r.e_site), \"chi\": $(r.chi), " *
                   "\"sweeps\": $(r.sweeps), \"drift_site\": $(r.drift_site), " *
                   "\"wall_s\": $(round(r.wall, digits=1))}" for r in results]
        print(io, "{\"N\": $N, \"bc\": \"PBC\", \"method\": \"DMRG (ITensorMPS)\", ",
              join(entries, ", "), "}")
    end
    if r.J2 == 0.5
        ok = abs(r.e_site - (-0.375)) < 1e-6
        println("MG SANITY: ", ok ? "PASS" : "FAIL", "  |e-(-0.375)| = ", abs(r.e_site + 0.375))
        ok || (println("STOPPING: MG sanity failed"); exit(1))
    end
end
println("DMRG REFS DONE")
