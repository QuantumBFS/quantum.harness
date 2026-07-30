"""
MPS-only job: boundary MPS free energy for L = 14, 16.
Runs independently to avoid OOM from dense phase.
"""

using Random, Printf, Statistics, Dates

include(joinpath(@__DIR__, "..", "src", "OpenCriticality.jl"))
using .OpenCriticality

const p_nish = 0.8899
const alpha = 1.0
const Ly_factor = 40
const MPS_Ls = [14, 16]
const CHI_VALUES = [64, 128, 256]

function nsamples_mps(L)
    L <= 14 && return 50
    return 30
end

results_dir = joinpath(@__DIR__, "results")
mkpath(results_dir)

summary_file = joinpath(results_dir, "mps_summary.txt")
summary_io = open(summary_file, "w")

function logprintln(args...)
    println(args...)
    println(summary_io, args...)
    flush(stdout)
    flush(summary_io)
end

logprintln("=" ^ 70)
logprintln("Nishimori RBIM Boundary MPS Job")
logprintln("  Started: ", Dates.now())
logprintln("  p = $p_nish, beta_N = $(0.5*log(p_nish/(1-p_nish)))")
logprintln("  MPS Ls: $MPS_Ls, chi values: $CHI_VALUES")
logprintln("=" ^ 70)

for L in MPS_Ls
    Ly = Ly_factor * L
    nsamp = nsamples_mps(L)
    model = NishimoriRBIM(L=L, p=p_nish)
    conv = convention(model)

    for chi in CHI_VALUES
        logprintln("\n--- L = $L, Ly = $Ly, samples = $nsamp, chi = $chi ---")

        Phis = Float64[]
        csv_file = joinpath(results_dir, "nishimori_mps_L$(L)_chi$(chi).csv")
        csv_io = open(csv_file, "w")
        println(csv_io, "sample,logZ,Phi_L")

        t0 = time()
        for i in 1:nsamp
            rng = MersenneTwister(2000 + i * 41 + L * 13 + chi)
            config = sample_config(model, rng, Ly)
            logZ = boundary_mps_logZ(model, config; chi=chi, tol=1e-12)
            Phi = free_energy_per_row(conv, logZ, Ly)
            push!(Phis, Phi)
            println(csv_io, "$i,$logZ,$Phi")

            if i % 10 == 0 || i == nsamp
                @printf("  [%3d/%3d]  Phi_L = %12.6f  (%.1fs)\n",
                        i, nsamp, Phi, time() - t0)
                flush(stdout)
                flush(csv_io)
            end

            # Periodic GC to prevent memory accumulation
            if i % 10 == 0
                GC.gc()
            end
        end
        close(csv_io)

        elapsed = time() - t0
        @printf("  L=%2d chi=%3d done:  Phi_L = %12.6f +/- %8.6f  (%.1fs)\n",
                L, chi, mean(Phis), std(Phis)/sqrt(nsamp), elapsed)
        logprintln("  L=$L chi=$chi complete in $(round(elapsed, digits=1))s")

        # GC between chi values
        GC.gc()
    end
    # GC between L values
    GC.gc()
end

logprintln("\n" * "=" ^ 70)
logprintln("  Completed: ", Dates.now())
logprintln("=" ^ 70)

close(summary_io)
println("\nResults saved to $results_dir")