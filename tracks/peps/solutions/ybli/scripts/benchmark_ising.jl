"""
Benchmark: clean 2D Ising model at criticality.

Runs L = 4, 6, 8, 10, 12 at beta_c = log(1+sqrt(2))/2, extracts the
effective central charge c_eff via finite-size scaling, and compares
to the exact result c = 1/2.

Usage (from repo root):
  julia --project=julia-env tracks/peps/solutions/ybli/scripts/benchmark_ising.jl

Usage (with PEPSKit cross-check):
  julia --project=julia-env tracks/peps/solutions/ybli/scripts/benchmark_ising.jl --pepskit
"""

using Random
using Printf
using LinearAlgebra
using Statistics

# Include the module
include("../src/OpenCriticality.jl")
using .OpenCriticality

const RNG = MersenneTwister(2024)

# Parse command-line args
use_pepskit = "--pepskit" in ARGS
Ls = use_pepskit ? [4, 6, 8] : [4, 6, 8, 10]
Ly_factor = 10  # Ly = Ly_factor * L

beta_c = log(1 + sqrt(2)) / 2
alpha = 1.0  # cylinder/torus with Ly>>L: same Casimir term
c_exact = 0.5

println("=" ^ 70)
println("Clean Ising Benchmark")
println("=" ^ 70)
println("  beta_c = $(round(beta_c, digits=6))")
println("  Ls     = $Ls")
println("  Ly     = $(Ly_factor)*L")
println("  alpha  = $alpha")
println("  c_exact = $c_exact")
println("-" ^ 70)

# ----------------------------------------------------------------------
# Dense backend: compute Phi_L for each L
# ----------------------------------------------------------------------

Phis = Float64[]
Phi_errors = Float64[]
Phis_replicas = Vector{Vector{Float64}}()

n_replicas = 3

for L in Ls
    Ly = Ly_factor * L
    model = ClassicalIsing(L=L, beta=beta_c)
    conv = convention(model)

    Phi_reps = Float64[]
    for rep in 1:n_replicas
        rng = MersenneTwister(2024 + rep * 1000 + L)
        config = sample_config(model, rng, Ly)
        logZ = dense_logZ(model, config)
        Phi = free_energy_per_row(conv, logZ, Ly)
        push!(Phi_reps, Phi)
    end

    Phi_mean = mean(Phi_reps)
    Phi_std = std(Phi_reps)

    push!(Phis, Phi_mean)
    push!(Phi_errors, Phi_std)
    push!(Phis_replicas, Phi_reps)

    f_density = Phi_mean / (alpha * L)
    @printf("  L=%2d  Ly=%4d  Phi_L=%12.6f  +/- %8.6f  f_L=%10.6f\n",
            L, Ly, Phi_mean, Phi_std, f_density)
end

# ----------------------------------------------------------------------
# Finite-size scaling
# ----------------------------------------------------------------------

println("-" ^ 70)
println("Finite-size scaling:")
println("-" ^ 70)

# Model A (no correction)
c_A, a_A, _, fq_A = fit_central_charge(Ls, Phis, alpha; model=:A)
@printf("  Model A (no correction):     c_eff = %8.6f  (R^2 = %.6f)\n", c_A, fq_A.r2)

# Model B (1/L^3 correction)
c_B, a_B, _, fq_B = fit_central_charge(Ls, Phis, alpha; model=:B)
@printf("  Model B (1/L^3 correction):  c_eff = %8.6f  (R^2 = %.6f)\n", c_B, fq_B.r2)

# Model C (1/L^3 + 1/L^5)
if length(Ls) >= 4
    c_C, a_C, _, fq_C = fit_central_charge(Ls, Phis, alpha; model=:C)
    @printf("  Model C (1/L^3+1/L^5):       c_eff = %8.6f  (R^2 = %.6f)\n", c_C, fq_C.r2)
end

# Bootstrap
boot = bootstrap_c_eff(Ls, Phis_replicas, alpha; n_bootstrap=500, model=:B, rng=RNG)
@printf("  Bootstrap (model B):         c_eff = %8.6f +/- %8.6f\n", boot.mean, boot.std)
@printf("  95%% CI:                      [%8.6f, %8.6f]\n", boot.ci_lo, boot.ci_hi)

# Pair estimators
println("-" ^ 70)
println("Pair estimators (bulk-free):")
fs = free_energy_densities(Phis, Ls, alpha)
for (L1, L2, c) in pair_estimator_table(Ls, fs, alpha)
    @printf("  c_eff(%2d, %2d) = %8.6f\n", L1, L2, c)
end

# Stability envelope
println("-" ^ 70)
println("Stability envelope:")
for (Lm, mdl, c, rmse) in stability_envelope(Ls, Phis, alpha)
    @printf("  L_min=%2d  model=%s  c_eff=%8.6f  rmse=%10.2e\n", Lm, mdl, c, rmse)
end

# Summary
println("=" ^ 70)
c_best = c_B
c_err = max(boot.std, abs(c_B - c_A))
@printf("  Result:  c_eff = %8.6f +/- %8.6f\n", c_best, c_err)
@printf("  Exact:   c     = %8.6f\n", c_exact)
@printf("  Error:   %8.6f (%.2f%%)\n", c_best - c_exact, 100 * (c_best - c_exact) / c_exact)
println("=" ^ 70)

# ----------------------------------------------------------------------
# PEPSKit cross-check (optional)
# ----------------------------------------------------------------------

if use_pepskit
    println("\nPEPSKit CTMRG cross-check (thermodynamic limit):")
    try
        using PEPSKit
        using TensorKit

        for chi_env in [10, 20]
            O, _ = PEPSKit.classical_ising(; beta=beta_c)
            Z = PEPSKit.InfinitePartitionFunction(O)
            env = PEPSKit.CTMRGEnv(Z, TensorKit.VectSpace[PEPSKit.trivial_space], chi_env)
            env, = PEPSKit.leading_boundary(env, Z; tol=1e-10)
            lambda = PEPSKit.network_value(Z, env)
            f_inf = -log(lambda) / beta_c
            @printf("  chi_env=%2d  f_inf = %10.6f\n", chi_env, f_inf)
        end
    catch e
        println("  PEPSKit cross-check failed: $e")
        println("  (This is expected if PEPSKit APIs have changed.)")
    end
end
