"""
Test suite for OpenCriticality.

Run with:
  julia --project=julia-env -e 'include("tracks/peps/solutions/ybli/test/runtests.jl")'

Or from within the solution directory:
  julia --project=../../../julia-env -e 'include("test/runtests.jl")'
"""

using Random
using LinearAlgebra
using Test

# Include the module
include("../src/OpenCriticality.jl")
using .OpenCriticality

const RNG = MersenneTwister(42)

# ====================================================================
# 1. Conventions
# ====================================================================

@testset "Conventions" begin
    conv = ClassicalIsingConvention()
    @test conv.ztype == :partition
    @test conv.kappa == 1.0
    @test conv.bc_x == :periodic
    @test conv.anisotropy == 1.0
    @test conv.sign_convention == :standard

    # Free energy per row
    fe = free_energy_per_row(conv, log(2.0), 10)
    @test fe ≈ -log(2.0) / 10

    conv_n = NishimoriConvention()
    @test conv_n.ztype == :partition
    @test conv_n.disorder == :nishimori

    conv_m = MeasuredToricCodeConvention()
    @test conv_m.ztype == :squared_norm
    @test conv_m.flux_sector == 1
    @test conv_m.parity_sector == 1
end

# ====================================================================
# 2. Classical Ising model
# ====================================================================

@testset "ClassicalIsing" begin
    model = ClassicalIsing(L=4)
    @test width(model) == 4
    @test physical_dim(model) == 2
    @test convention(model).ztype == :partition

    # Sample a configuration
    config = sample_config(model, RNG, 6)
    @test config.L == 4
    @test config.Ly == 6

    # Build row transfer matrix
    T = build_row_transfer_dense(model, config, 1)
    @test size(T) == (16, 16)
    @test all(diag(T) .> 0)

  # MPO site tensor
  W = build_local_mpo_tensor(model, config, 1, 1)
  @test size(W) == (4, 4, 2, 2)
end

# ====================================================================
# 3. Dense contraction vs exact enumeration

# ====================================================================

@testset "Dense contraction" begin
    model = ClassicalIsing(L=4, beta=0.5)
    config = sample_config(model, RNG, 4)

    logZ_dense = dense_logZ(model, config)
    Z_exact = exact_partition_function(model, config)

    @test exp(logZ_dense) ≈ Z_exact rtol=1e-8
end

# ====================================================================
# 4. Boundary MPS vs dense
# ====================================================================

@testset "Boundary MPS" begin
    model = ClassicalIsing(L=4, beta=0.5, bc_y=:open)
    config = sample_config(model, RNG, 6)

   logZ_dense = dense_logZ(model, config)
    logZ_bmps = boundary_mps_logZ(model, config; chi=256, tol=1e-14)

    # For clean Ising with large chi, should agree closely
    @test logZ_bmps ≈ logZ_dense rtol=1e-6
end

# ====================================================================
# 5. Lyapunov exponents
# ====================================================================

@testset "Lyapunov" begin
    model = ClassicalIsing(L=4, beta=0.5)
    config = sample_config(model, RNG, 50)

   # Leading exponent
    gamma0 = leading_lyapunov(model, config; burn_in=2)
   @test !isnan(gamma0)
    @test gamma0 > 0  # transfer matrix has positive leading eigenvalue

    # Spectrum
    gammas = lyapunov_spectrum(model, config, 3; burn_in=10)
    @test length(gammas) == 3
    @test gammas[1] >= gammas[2] >= gammas[3]

    # SVD cross-check on short product
    Ts = [build_row_transfer_dense(model, config, y) for y in 1:20]
    svd_exponents = svd_lyapunov_check(Ts; n_product=20)
    qr_exponents, _ = lyapunov_spectrum(Ts, 3; burn_in=0)

    # Should agree for the first few exponents
    for i in 1:3
        @test svd_exponents[i] ≈ qr_exponents[i] rtol=0.1
    end
end

# ====================================================================
# 6. Free energy consistency
# ====================================================================

@testset "Free energy" begin
    model = ClassicalIsing(L=4, beta=0.5)
    config = sample_config(model, RNG, 10)

    logZ = dense_logZ(model, config)
    fe = dense_free_energy(model, config)
    conv = convention(model)

    expected_fe = free_energy_per_row(conv, logZ, config.Ly)
    @test fe ≈ expected_fe
end

# ====================================================================
# 7. Ising critical point benchmark
# ====================================================================

@testset "Ising benchmark" begin
    beta_c = log(1 + sqrt(2)) / 2
    Ls = [4, 6]
    Ly = 30

    Phis = Float64[]
    for L in Ls
        model = ClassicalIsing(L=L, beta=beta_c)
        config = sample_config(model, RNG, Ly)
        logZ = dense_logZ(model, config)
        push!(Phis, free_energy_per_row(convention(model), logZ, Ly))
    end

    # For clean Ising, Phi_L = f_inf * L - pi * c / (6L) + ...
    # c = 1/2, so the Casimir term is -pi / (12L)
    # Just check that Phi_L / L converges (bulk free energy)
    f1 = Phis[1] / Ls[1]
    f2 = Phis[2] / Ls[2]

    # Free energy density should be similar for both sizes
    @test abs(f1 - f2) < 0.5
end

# ====================================================================
# 8. Nishimori RBIM
# ====================================================================

@testset "NishimoriRBIM" begin
    model = NishimoriRBIM(L=4, p=0.8899)
    config = sample_config(model, RNG, 6)
    @test config.L == 4

    logZ = dense_logZ(model, config)
    @test !isnan(logZ)
    @test isfinite(logZ)

    # Direct sampler
    logZs, configs = run_direct(model, 6, 5; rng=RNG)
    @test length(logZs) == 5
    @test all(isfinite.(logZs))
end

# ====================================================================
# 9. Measured Toric Code
# ====================================================================

@testset "MeasuredToricCode" begin
    model = MeasuredToricCode(L=4)
    config = sample_config(model, RNG, 6)
    @test config.L == 4

    logZ = dense_logZ(model, config)
    @test !isnan(logZ)
    @test isfinite(logZ)
end

# ====================================================================
# 10. Metropolis sampler
# ====================================================================

@testset "Metropolis sampler" begin
    model = NishimoriRBIM(L=4, p=0.8899)
    sampler = MetropolisSampler(model, 10; rng=RNG)

    result, acc = run_metropolis!(sampler, RNG; nsweeps=5, burn_in=2)
    @test result.sweep == 5
    @test length(result.logZ_history) > 0
    @test all(isfinite.(result.logZ_history))
end

# ====================================================================
# 11. Finite-size scaling
# ====================================================================

@testset "FiniteSizeScaling" begin
    # Synthetic data: c = 1/2, alpha = 1
    Ls = [4, 6, 8, 10, 12]
    alpha = 1.0
    c_true = 0.5
    f_inf = 0.5  # arbitrary bulk

    Phis = [f_inf * L - pi * alpha * c_true / (6 * L) for L in Ls]

    c_fit, a_fit, params, fq = fit_central_charge(Ls, Phis, alpha; model=:A)
    @test c_fit ≈ c_true rtol=1e-6

    # With 1/L^3 correction
    Phis2 = [f_inf * L - pi * alpha * c_true / (6 * L) + 0.01 / L^3 for L in Ls]
    c_fit2, _, _, _ = fit_central_charge(Ls, Phis2, alpha; model=:B)
    @test c_fit2 ≈ c_true rtol=1e-4

    # Pair estimator
    fs = free_energy_densities(Phis, Ls, alpha)
    c_pair = effective_c_eff(Ls[1], Ls[2], fs[1], fs[2], alpha)
    @test c_pair ≈ c_true rtol=1e-4

    # Bootstrap (synthetic replicas)
    replicas = [[Phi + 0.001 * randn(RNG) for _ in 1:10] for Phi in Phis]
    boot = bootstrap_c_eff(Ls, replicas, alpha; n_bootstrap=100, model=:A, rng=RNG)
    @test !isnan(boot.mean)
    @test boot.std > 0
end

# ====================================================================
# 12. Autocorrelation
# ====================================================================

@testset "Autocorrelation" begin
    # iid series: tau ~ 1
    series = randn(RNG, 1000)
    tau = integrated_autocorrelation_time(series)
    @test tau < 3.0

    # Block mean
    m, se = block_mean(series; block_size=10)
    @test !isnan(m)
    @test !isnan(se)
end

println("\nAll tests completed.")
