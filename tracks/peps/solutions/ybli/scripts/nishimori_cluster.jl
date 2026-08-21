"""
Nishimori RBIM cluster job: Lyapunov spectrum + boundary MPS.

Runs on scnet via Slurm.  Computes:
  - Lyapunov spectrum (6 exponents) for L = 4..12 (dense, on-the-fly)
  - Free energy via boundary MPS for L = 14, 16 (chi = 128, 256)
  - Scaling dimensions from Lyapunov gaps
  - c_eff from finite-size scaling

Output: results/nishimori_L{L}.csv and results/nishimori_summary.txt
"""

using Random, Printf, LinearAlgebra, Statistics, Dates

include(joinpath(@__DIR__, "..", "src", "OpenCriticality.jl"))
using .OpenCriticality

# -------------------------------------------------------------------
# On-the-fly Lyapunov spectrum (memory-efficient for large L)
# -------------------------------------------------------------------

"""
Compute Lyapunov spectrum without storing all transfer matrices.
Builds T_y one at a time and discards after use.
"""
function lyapunov_spectrum_otf(model::BornModel, config::Configuration, k::Int;
                                 burn_in::Int = max(1, config.Ly ÷ 10))
    Ly = config.Ly
    N = 2^model.L

    # Initialize orthonormal frame
    Q = Matrix(qr(randn(N, k)).Q)

    s = zeros(k)
    N_prod = 0

    for y in 1:Ly
        T = build_row_transfer_dense(model, config, y)
        Y = T * Q

        F = qr(Y)
        Qnew = Matrix(F.Q)
        R = F.R

        # Fix signs
        for i in 1:k
            if R[i, i] < 0
                Qnew[:, i] .= -Qnew[:, i]
                R[i, :] .= -R[i, :]
            end
        end

        # Reorthogonalize
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

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

const p_nish = 0.8899
const alpha = 1.0
const nk = 6  # number of Lyapunov exponents
const Ly_factor = 40

# L values and sample counts
const DENSE_Ls = [4, 6, 8, 10, 12]
const MPS_Ls = [14, 16]
const CHI_VALUES = [128, 256]

function nsamples_dense(L)
    L <= 6 && return 500
    L <= 8 && return 300
    L <= 10 && return 200
    return 100  # L=12
end

function nsamples_mps(L)
    L <= 14 && return 100
    return 50
end

# -------------------------------------------------------------------
# Output setup
# -------------------------------------------------------------------

results_dir = joinpath(@__DIR__, "results")
mkpath(results_dir)

summary_file = joinpath(results_dir, "nishimori_summary.txt")
summary_io = open(summary_file, "w")

function logprintln(args...)
    println(args...)
    println(summary_io, args...)
    flush(stdout)
    flush(summary_io)
end

logprintln("=" ^ 70)
logprintln("Nishimori RBIM Cluster Job")
logprintln("  Started: ", Dates.now())
logprintln("  p = $p_nish, beta_N = $(0.5*log(p_nish/(1-p_nish)))")
logprintln("  Lyapunov exponents: $nk")
logprintln("  Dense Ls: $DENSE_Ls")
logprintln("  MPS Ls: $MPS_Ls, chi values: $CHI_VALUES")
logprintln("=" ^ 70)

# -------------------------------------------------------------------
# Part 1: Dense Lyapunov spectrum for L = 4..12
# -------------------------------------------------------------------

dense_mean_neg_g0 = Float64[]
dense_err_neg_g0 = Float64[]
dense_mean_x1 = Float64[]  # x from gap g0-g1
dense_mean_x2 = Float64[]  # x from gap g0-g2
dense_Ls_used = Int[]

for L in DENSE_Ls
    Ly = Ly_factor * L
    nsamp = nsamples_dense(L)
    model = NishimoriRBIM(L=L, p=p_nish)
    conv = convention(model)
    burn = max(1, Ly ÷ 10)

    logprintln("\n--- L = $L, Ly = $Ly, samples = $nsamp (dense Lyapunov) ---")

    neg_g0s = Float64[]
    x1s = Float64[]  # L/(2pi) * (g0 - g1)
    x2s = Float64[]  # L/(2pi) * (g0 - g2)
    all_gammas = Vector{Vector{Float64}}()

    # CSV output
    csv_file = joinpath(results_dir, "nishimori_dense_L$(L).csv")
    csv_io = open(csv_file, "w")
    println(csv_io, "sample,g0,g1,g2,g3,g4,g5,neg_g0,x1,x2")

    t0 = time()
    for i in 1:nsamp
        rng = MersenneTwister(1000 + i * 31 + L * 7)
        config = sample_config(model, rng, Ly)

        gammas = lyapunov_spectrum_otf(model, config, nk; burn_in=burn)
        push!(all_gammas, gammas)

        neg_g0 = -gammas[1]
        x1 = L / (2 * pi * alpha) * (gammas[1] - gammas[2])
        x2 = L / (2 * pi * alpha) * (gammas[1] - gammas[3])

        push!(neg_g0s, neg_g0)
        push!(x1s, x1)
        push!(x2s, x2)

        println(csv_io, "$i,$(join(gammas, ",")),$neg_g0,$x1,$x2")

        if i % 50 == 0 || i == nsamp
            @printf("  [%4d/%4d]  -g0 = %10.5f  x1 = %8.5f  x2 = %8.5f  (%.1fs)\n",
                    i, nsamp, neg_g0, x1, x2, time() - t0)
            flush(stdout)
        end
    end
    close(csv_io)

    push!(dense_mean_neg_g0, mean(neg_g0s))
    push!(dense_err_neg_g0, std(neg_g0s) / sqrt(nsamp))
    push!(dense_mean_x1, mean(x1s))
    push!(dense_mean_x2, mean(x2s))
    push!(dense_Ls_used, L)

    elapsed = time() - t0
    @printf("  L=%2d done:  -g0 = %12.6f +/- %8.6f  x1 = %8.6f  x2 = %8.6f  (%.1fs)\n",
            L, mean(neg_g0s), std(neg_g0s)/sqrt(nsamp),
            mean(x1s), mean(x2s), elapsed)
    logprintln("  L=$L complete in $(round(elapsed, digits=1))s")
end

# -------------------------------------------------------------------
# Part 2: Boundary MPS for L = 14, 16
# -------------------------------------------------------------------

mps_results = Dict{Tuple{Int,Int}, Tuple{Float64, Float64}}()  # (L, chi) -> (mean_Phi, err_Phi)

for L in MPS_Ls
    Ly = Ly_factor * L
    nsamp = nsamples_mps(L)
    model = NishimoriRBIM(L=L, p=p_nish)
    conv = convention(model)

    for chi in CHI_VALUES
        logprintln("\n--- L = $L, Ly = $Ly, samples = $nsamp, chi = $chi (boundary MPS) ---")

        Phis = Float64[]

        csv_file = joinpath(results_dir, "nishimori_mps_L$(L)_chi$(chi).csv")
        csv_io = open(csv_file, "w")
        println(csv_io, "sample,logZ,Phi_L")

        t0 = time()
        for i in 1:nsamp
            rng = MersenneTwister(2000 + i * 41 + L * 13)
            config = sample_config(model, rng, Ly)
            logZ = boundary_mps_logZ(model, config; chi=chi, tol=1e-12)
            Phi = free_energy_per_row(conv, logZ, Ly)
            push!(Phis, Phi)

            println(csv_io, "$i,$logZ,$Phi")

            if i % 20 == 0 || i == nsamp
                @printf("  [%4d/%4d]  Phi_L = %12.6f  (%.1fs)\n",
                        i, nsamp, Phi, time() - t0)
                flush(stdout)
            end
        end
        close(csv_io)

        mps_results[(L, chi)] = (mean(Phis), std(Phis) / sqrt(nsamp))
        elapsed = time() - t0
        @printf("  L=%2d chi=%3d done:  Phi_L = %12.6f +/- %8.6f  (%.1fs)\n",
                L, chi, mean(Phis), std(Phis)/sqrt(nsamp), elapsed)
        logprintln("  L=$L chi=$chi complete in $(round(elapsed, digits=1))s")
    end
end

# -------------------------------------------------------------------
# Part 3: Finite-size scaling analysis
# -------------------------------------------------------------------

logprintln("\n" * "=" ^ 70)
logprintln("Finite-Size Scaling Analysis")
logprintln("=" ^ 70)

# c_eff from dense Lyapunov (-gamma0)
logprintln("\nc_eff from -gamma0 (dense, L = $dense_Ls_used):")
logprintln("  L    -gamma0          err")
for (i, L) in enumerate(dense_Ls_used)
    @printf("  %2d   %12.6f   %8.6f\n", L, dense_mean_neg_g0[i], dense_err_neg_g0[i])
    logprintln("  $L   $(dense_mean_neg_g0[i])   $(dense_err_neg_g0[i])")
end

c_A, _, _, _ = fit_central_charge(dense_Ls_used, dense_mean_neg_g0, alpha; model=:A)
c_B, _, _, _ = fit_central_charge(dense_Ls_used, dense_mean_neg_g0, alpha; model=:B)
logprintln("  Model A:  c_eff = $(round(c_A, digits=6))")
logprintln("  Model B:  c_eff = $(round(c_B, digits=6))")

# Scaling dimensions
logprintln("\nScaling dimensions from Lyapunov gaps:")
logprintln("  L    x1 (g0-g1)      x2 (g0-g2)")
for (i, L) in enumerate(dense_Ls_used)
    @printf("  %2d   %10.6f      %10.6f\n", L, dense_mean_x1[i], dense_mean_x2[i])
    logprintln("  $L   $(dense_mean_x1[i])   $(dense_mean_x2[i])")
end

# Extrapolate scaling dimensions
gaps1 = [all_gammas_l[1] - all_gammas_l[2] for all_gammas_l in
         [[dense_mean_neg_g0[i] + dense_mean_x1[i] * 2*pi*alpha/L for _ in 1:1] for (i, L) in enumerate(dense_Ls_used)]]
# Actually just use the means directly
sd1 = fit_scaling_dimension(
    [dense_mean_x1[i] * 2*pi*alpha / dense_Ls_used[i] for i in 1:length(dense_Ls_used)],
    dense_Ls_used, alpha; model=:linear)
sd2 = fit_scaling_dimension(
    [dense_mean_x2[i] * 2*pi*alpha / dense_Ls_used[i] for i in 1:length(dense_Ls_used)],
    dense_Ls_used, alpha; model=:linear)

logprintln("  x1 (extrapolated) = $(round(sd1.x, digits=6))")
logprintln("  x2 (extrapolated) = $(round(sd2.x, digits=6))")

# c_eff from boundary MPS
logprintln("\nc_eff from boundary MPS:")
for chi in CHI_VALUES
    mps_Ls_avail = sort([L for (L, c) in keys(mps_results) if c == chi])
    if length(mps_Ls_avail) >= 2
        Phis_mps = [mps_results[(L, chi)][1] for L in mps_Ls_avail]
        c_mps, _, _, _ = fit_central_charge(mps_Ls_avail, Phis_mps, alpha; model=:A)
        logprintln("  chi=$chi, L=$mps_Ls_avail:  c_eff = $(round(c_mps, digits=6))")
    end
end

# Combined fit: dense + MPS
logprintln("\nCombined fit (dense -gamma0 for L<=12 + MPS Phi_L for L>=14):")
for chi in CHI_VALUES
    all_Ls = copy(dense_Ls_used)
    all_Phis = copy(dense_mean_neg_g0)
    for L in MPS_Ls
        if haskey(mps_results, (L, chi))
            push!(all_Ls, L)
            push!(all_Phis, mps_results[(L, chi)][1])
        end
    end
    perm = sortperm(all_Ls)
    all_Ls = all_Ls[perm]
    all_Phis = all_Phis[perm]

    c_comb_A, _, _, _ = fit_central_charge(all_Ls, all_Phis, alpha; model=:A)
    c_comb_B, _, _, _ = fit_central_charge(all_Ls, all_Phis, alpha; model=:B)
    logprintln("  chi=$chi:  c_eff(A) = $(round(c_comb_A, digits=6)),  c_eff(B) = $(round(c_comb_B, digits=6))")
end

logprintln("\n" * "=" ^ 70)
logprintln("  Literature: c_eff ~ 0.464 (Gruzberg et al.)")
logprintln("  Completed: ", Dates.now())
logprintln("=" ^ 70)

close(summary_io)
println("\nResults saved to $results_dir")