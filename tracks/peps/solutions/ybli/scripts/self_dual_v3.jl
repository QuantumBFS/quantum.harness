"""
Weak self-dual point v3: uses log Z_m directly for c_eff.

Key insight: the Born amplitude <m|TC> = <0|B_1...B_Ly|0> can be DECAYING
even when the transfer matrix has positive leading Lyapunov exponent,
because the vacuum |0> may be orthogonal to the dominant eigenvector.

So we compute:
  - c_eff from Phi_L = -(2/Ly) * <log|A_m|>_m  (direct amplitude)
  - Delta_m from Lyapunov spectrum of B  (ratio of eigenvalues is meaningful)
"""

using Random, LinearAlgebra, Statistics, Printf

include("SelfDualFunctions.jl")

const ALPHA = 1.0
const THETA = pi / 4
const NK = 6
const LY_FACTOR = 10

function nsamples_for(L::Int)
    L <= 4 && return 200
    L <= 6 && return 50
    L <= 8 && return 10
    return 5
end

println("=" ^ 70)
println("Weak Self-Dual Point v3: log Z_m based")
println("  theta = pi/4, alpha = 1.0")
println("=" ^ 70)

Ls = [4, 6, 8]
if length(ARGS) > 0
    Ls = parse.(Int, split(ARGS[1], ","))
end

results_dir = joinpath(@__DIR__, "results")
mkpath(results_dir)

M_mat = measurement_matrix(THETA)

mean_Phi = Float64[]
err_Phi = Float64[]
mean_Deltas = Vector{Vector{Float64}}()
raw_Phi = Dict{Int, Vector{Float64}}()
raw_spec = Dict{Int, Vector{Vector{Float64}}}()

for L in Ls
    Ly = LY_FACTOR * L
    nsamp = nsamples_for(L)
    println("\n--- L = $L, Ly = $Ly, samples = $nsamp ---")

    Phis = Float64[]
    all_gammas = Vector{Vector{Float64}}()

    csv_file = joinpath(results_dir, "self_dual_v3_L$(L).csv")
    csv_io = open(csv_file, "w")
    println(csv_io, "sample,logA,logZ,Phi_L,gamma0,g1,g2,g3,g4,g5,d1,d2,d3")

    t0 = time()
    for i in 1:nsamp
        rng = MersenneTwister(60000 + i * 37 + L * 11)
        mh, mv = sample_tc_born_two_stage(L, THETA, Ly; rng=rng)

        # Compute log|A_m| directly (sequential matvec with log normalization)
        N = 2^L
        psi = zeros(Float64, N)
        psi[1] = 1.0
        log_scale = 0.0
        for y in 1:Ly
            B = build_tc_row_transfer(L, M_mat, mh[:, y], mv[:, y])
            psi = B * psi
            s = maximum(abs.(psi))
            if s > 0
                psi ./= s
                log_scale += log(s)
            end
        end
        logA = log_scale + log(abs(psi[1]))
        logZ = 2 * logA
        Phi = -logZ / Ly  # free energy per row of Born weight

        # Lyapunov spectrum for scaling dimensions
        gammas = tc_lyapunov_spectrum(L, M_mat, mh, mv, Ly, NK)
        Deltas = [L / (2 * pi * ALPHA) * (gammas[1] - gammas[j]) for j in 2:NK]

        push!(Phis, Phi)
        push!(all_gammas, gammas)
        println(csv_io, "$i,$logA,$logZ,$Phi,$(join(gammas, ",")),$(join(Deltas, ","))")

        if i % 20 == 0 || i == nsamp
            @printf("  [%3d/%3d]  Phi = %8.4f  D1 = %8.5f  (%.1fs)\n",
                    i, nsamp, Phi, Deltas[1], time() - t0)
            flush(stdout)
            flush(csv_io)
        end
    end
    close(csv_io)

    raw_Phi[L] = Phis
    raw_spec[L] = all_gammas
    mean_D = [mean([all_gammas[s][1] - all_gammas[s][j] for s in 1:length(all_gammas)])
              for j in 2:NK]
    mean_D = mean_D .* [L / (2 * pi * ALPHA) for _ in 1:(NK-1)]

    push!(mean_Phi, mean(Phis))
    push!(err_Phi, std(Phis) / sqrt(nsamp))
    push!(mean_Deltas, mean_D)

    @printf("  L=%2d done:  Phi = %12.6f +/- %8.6f  (%.1fs)\n",
            L, mean_Phi[end], err_Phi[end], time() - t0)
    flush(stdout)
end

# ================================================================
# Finite-size scaling
# ================================================================
include(joinpath(@__DIR__, "..", "src", "OpenCriticality.jl"))
using .OpenCriticality

println("\n" * "=" ^ 70)
println("Finite-Size Scaling")
println("=" ^ 70)

println("\nc_eff from Phi_L = -logZ/Ly:")
println("  L    Phi_L           err        f = Phi/L")
for (i, L) in enumerate(Ls)
    f = mean_Phi[i] / L
    @printf("  %2d   %12.6f   %8.6f   %10.6f\n", L, mean_Phi[i], err_Phi[i], f)
end

if length(Ls) >= 2
    c_A = fit_central_charge(Ls, mean_Phi, ALPHA; model=:A)[1]
    println("  Model A:  c_eff = $(round(c_A, digits=6))")
end
if length(Ls) >= 3
    c_B = fit_central_charge(Ls, mean_Phi, ALPHA; model=:B)[1]
    println("  Model B:  c_eff = $(round(c_B, digits=6))")
end

if length(Ls) >= 2
    println("\nPair estimators:")
    fs = free_energy_densities(mean_Phi, Ls, ALPHA)
    for (L1, L2, c) in pair_estimator_table(Ls, fs, ALPHA)
        @printf("  c_eff(%2d, %2d) = %8.6f\n", L1, L2, c)
    end
end

println("\nScaling dimensions Delta_m:")
println("  L    Delta_1         Delta_2         Delta_3")
for (i, L) in enumerate(Ls)
    @printf("  %2d   %10.6f   %10.6f   %10.6f\n",
            L, mean_Deltas[i][1], mean_Deltas[i][2], mean_Deltas[i][3])
end

if length(Ls) >= 2
    for j in 1:min(NK-1, 3)
        gaps = [mean_Deltas[i][j] * 2 * pi * ALPHA / Ls[i] for i in 1:length(Ls)]
        sd = fit_scaling_dimension(gaps, Ls, ALPHA; model=:linear)
        println("  Delta_$j (extrapolated) = $(round(sd.x, digits=6))")
    end
end

println("\n" * "=" ^ 70)
println("  Target: c_eff ~ 0.447 (arXiv:2502.14034)")
println("=" ^ 70)
