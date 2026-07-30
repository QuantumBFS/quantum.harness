using Test
using Random
using Statistics

if !isdefined(@__MODULE__, :Challenge148)
    include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
end
using .Challenge148

@testset "diagnostics detect independent and stuck chains" begin
    alternating = repeat([-1.0, 1.0], 500)
    constant = ones(1000)

    @test autocorrelation_fft_free(alternating; maxlag=3) == [1.0, -1.0, 1.0, -1.0]
    @test tau_int_initial_positive(alternating) == 0.5
    @test effective_sample_size(alternating) == length(alternating)
    @test split_chain_z(alternating) == 0.0
    @test_throws ArgumentError autocorrelation_fft_free(constant)
    @test_throws ArgumentError tau_int_initial_positive(constant)
    @test_throws ArgumentError effective_sample_size(constant)
    @test_throws ArgumentError split_chain_z(constant)
end

@testset "chain compatibility retains the supplied trending-chain gate" begin
    base = collect(range(-1.0, 1.0; length=100))
    compatible = chain_compatibility([
        base, base .+ 0.01, base .- 0.01, base .+ 0.005,
    ])
    @test compatible.passed
    @test compatible.dof == 3
    @test compatible.pooled_mean ≈ 0.00125 atol=1e-14
    @test compatible.reduced_chisquare <= 2.0
    @test length(compatible.chain_means) == 4
    @test length(compatible.chain_stderrs) == 4

    incompatible = chain_compatibility([
        base, base .+ 0.01, base .- 0.01, base .+ 0.30,
    ])
    @test !incompatible.passed
    @test incompatible.reduced_chisquare > 2.0
    @test length(incompatible.chain_means) == 4
    @test_throws ArgumentError chain_compatibility([base])
    @test_throws ArgumentError chain_compatibility([base, ones(1000)])
end

@testset "chain compatibility is invariant to a common data scale" begin
    tiny = 1e-160 .* repeat([-1.0, 1.0], 500)
    result = chain_compatibility([tiny, tiny])
    @test result.passed
    @test all(isfinite, result.weights)
    @test all(>(0.0), result.weights)
end

@testset "chain compatibility applies both published gate thresholds inclusively" begin
    base = repeat([-1.0, 1.0], 500)
    stderr = chain_compatibility([base, base]).chain_stderrs[1]
    at_threshold = chain_compatibility([fill(base, 7)..., base .+ 4 * stderr])
    above_threshold = chain_compatibility([fill(base, 7)..., base .+ 4.000001 * stderr])

    @test at_threshold.max_standardized_residual ≈ 3.5 atol=1e-12
    @test at_threshold.reduced_chisquare ≈ 2.0 atol=1e-12
    @test at_threshold.passed
    @test above_threshold.max_standardized_residual > 3.5
    @test above_threshold.reduced_chisquare > 2.0
    @test !above_threshold.passed
end

@testset "split-chain diagnostic requires an even nondegenerate chain" begin
    @test_throws ArgumentError split_chain_z([1.0, 2.0, 3.0])
    @test_throws ArgumentError split_chain_z([1.0, Inf, 2.0, 3.0])
end

@testset "initial-positive tau estimates a fixed-seed AR(1) process" begin
    rng = MersenneTwister(148601)
    rho = 0.8
    series = Vector{Float64}(undef, 200_000)
    series[1] = randn(rng)
    noise_scale = sqrt(1 - rho^2)
    for index in 2:length(series)
        series[index] = rho * series[index - 1] + noise_scale * randn(rng)
    end
    expected = (1 + rho) / (2 * (1 - rho))
    @test tau_int_initial_positive(series) ≈ expected rtol=0.15
end

@testset "initial-positive tau scans past the legacy square-root horizon" begin
    rng = MersenneTwister(148606)
    rho = 0.95
    series = Vector{Float64}(undef, 1_000)
    series[1] = randn(rng)
    noise_scale = sqrt(1 - rho^2)
    for index in 2:length(series)
        series[index] = rho * series[index - 1] + noise_scale * randn(rng)
    end
    @test tau_int_initial_positive(series) ==
          tau_int_initial_positive(series; maxlag=length(series) - 1)
    @test_throws ArgumentError tau_int_initial_positive(series; maxlag=isqrt(length(series)))
end

@testset "initial-positive tau uses common-normalized adjacent autocovariances" begin
    series = [
        1.3686403046778453,
        0.6222523392039518,
        -0.41535589824844027,
        0.7770394061672998,
        1.0780844822768643,
        0.5462059220858744,
        2.088617848201076,
        1.128177854183542,
        0.4214483266220049,
        0.908720091713675,
        0.32919911862294615,
        -1.120762920018168,
    ]
    centered = series .- mean(series)
    c0 = sum(abs2, centered)
    c1 = sum(centered[index] * centered[index + 1] for index in 1:11)
    c2 = sum(centered[index] * centered[index + 2] for index in 1:10)
    c3 = sum(centered[index] * centered[index + 3] for index in 1:9)
    @test c0 + c1 > 0
    @test c2 + c3 < 0
    @test tau_int_initial_positive(series; maxlag=3) ≈ 0.5 + c1 / c0 atol=1e-14
end

@testset "adjacent-pair stopping uses the exact positive boundary" begin
    @test Challenge148._adjacent_pair_positive(1.0, nextfloat(-1.0))
    @test !Challenge148._adjacent_pair_positive(1.0, -1.0)
end

@testset "initial-positive tau clamps strongly anti-correlated chains" begin
    rng = MersenneTwister(148602)
    rho = -0.8
    series = Vector{Float64}(undef, 10_000)
    series[1] = randn(rng)
    noise_scale = sqrt(1 - rho^2)
    for index in 2:length(series)
        series[index] = rho * series[index - 1] + noise_scale * randn(rng)
    end
    @test tau_int_initial_positive(series) == 0.5
end
