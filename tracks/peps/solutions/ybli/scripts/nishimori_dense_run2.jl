"""
Nishimori RBIM dense Lyapunov run #2: independent seeds, L=4..12.
Seeds offset by 50000 from run #1 to produce independent samples.
"""

using Random, Printf, LinearAlgebra, Statistics, Dates

include(joinpath(@__DIR__, "..", "src", "OpenCriticality.jl"))
using .OpenCriticality

function lyapunov_spectrum_otf(model::BornModel, config::Configuration, k::Int;
                                 burn_in::Int = max(1, config.Ly ÷ 10))
    Ly = config.Ly
    N = 2^model.L
    Q = Matrix(qr(randn(N, k)).Q)
    s = zeros(k)
    N_prod = 0
    for y in 1:Ly
        T = build_row_transfer_dense(model, config, y)
        Y = T * Q
        F = qr(Y)
        Qnew = Matrix(F.Q)
        R = F.R
        for i in 1:k
            if R[i, i] < 0
                Qnew[:, i] .= -Qnew[:, i]
                R[i, :] .= -R[i, :]
            end
        end
        if norm(Qnew' * Qnew - I) > 1e-10
            F2 = qr(Qnew)
            Qnew = Matrix(F2.Q)
        end
        Q = Qnew
        if y > burn_in
            for i in 1:k
                s[i] += log(abs(R[i, i]))
            end
            N_prod += 1
        end
    end
    gammas = N_prod > 0 ? s ./ N_prod : fill(NaN, k)
    return gammas
end

const p_nish = 0.8899
const alpha = 1.0
const nk = 6
const Ly_factor = 40

const DENSE_Ls = [4, 6, 8, 10, 12]

function nsamples_dense(L)
    L <= 6 && return 500
    L <= 8 && return 300
    L <= 10 && return 200
    return 100
end

results_dir = joinpath(@__DIR__, "results")
mkpath(results_dir)

summary_file = joinpath(results_dir, "dense_run2_summary.txt")
summary_io = open(summary_file, "w")

function logprintln(args...)
    println(args...)
    println(summary_io, args...)
    flush(stdout)
    flush(summary_io)
end

logprintln("=" ^ 70)
logprintln("Nishimori RBIM Dense Lyapunov Run #2")
logprintln("  Started: ", Dates.now())
logprintln("  Seeds offset by 50000 from run #1")
logprintln("=" ^ 70)

for L in DENSE_Ls
    Ly = Ly_factor * L
    nsamp = nsamples_dense(L)
    model = NishimoriRBIM(L=L, p=p_nish)
    burn = max(1, Ly ÷ 10)

    logprintln("\n--- L = $L, Ly = $Ly, samples = $nsamp ---")

    csv_file = joinpath(results_dir, "nishimori_dense_L$(L)_run2.csv")
    csv_io = open(csv_file, "w")
    println(csv_io, "sample,g0,g1,g2,g3,g4,g5,neg_g0,x1,x2")

    t0 = time()
    for i in 1:nsamp
        # Offset seeds by 50000 to get independent samples
        rng = MersenneTwister(51000 + i * 31 + L * 7)
        config = sample_config(model, rng, Ly)
        gammas = lyapunov_spectrum_otf(model, config, nk; burn_in=burn)
        neg_g0 = -gammas[1]
        x1 = L / (2 * pi * alpha) * (gammas[1] - gammas[2])
        x2 = L / (2 * pi * alpha) * (gammas[1] - gammas[3])
        println(csv_io, "$i,$(join(gammas, ",")),$neg_g0,$x1,$x2")

        if i % 50 == 0 || i == nsamp
            @printf("  [%4d/%4d]  -g0 = %10.5f  x1 = %8.5f  x2 = %8.5f  (%.1fs)\n",
                    i, nsamp, neg_g0, x1, x2, time() - t0)
            flush(stdout)
            flush(csv_io)
        end

        if i % 20 == 0
            GC.gc()
        end
    end
    close(csv_io)

    elapsed = time() - t0
    logprintln("  L=$L complete in $(round(elapsed, digits=1))s")
    GC.gc()
end

logprintln("\n" * "=" ^ 70)
logprintln("  Completed: ", Dates.now())
logprintln("=" ^ 70)
close(summary_io)
println("\nResults saved to $results_dir")