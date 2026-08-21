using Test
using Statistics

if !isdefined(@__MODULE__, :Challenge148)
    include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
end
using .Challenge148
using .Challenge148: CWAState

@testset "raw bins can be rebinned without changing the mean" begin
    rebinned = rebin_series([1.0, 2.0, 3.0, 4.0], 2)
    @test rebinned == [1.5, 3.5]
    @test mean(rebinned) == 2.5
    @test_throws ArgumentError rebin_series([1.0, 2.0, 3.0], 2)
end

@testset "Binder ratio uses correlated delete-one-bin jackknife" begin
    estimate = binder_from_bins([1.0, 2.0, 3.0], [2.0, 5.0, 10.0])
    leave_one = [5 / 6, 2 / 3, 9 / 14]
    leave_mean = 5 / 7
    expected_error = sqrt(2 / 3 * sum((leave_one .- leave_mean) .^ 2))
    @test estimate.mean ≈ 12 / 17 atol = 1e-14
    @test estimate.stderr ≈ expected_error atol = 1e-14
    @test estimate.bins == 3
end

@testset "honeycomb continuous-time cluster matches ED" begin
    geometry = lattice_geometry(:honeycomb, 2)
    h = 2.1325
    beta = beta_for_aspect(h, 2; c = 1.0)
    exact = ed_thermal_observables(geometry; J = 1.0, h, beta)
    result = run_cwa(
        geometry;
        J = 1.0,
        h,
        beta,
        thermalization = 5_000,
        sweeps = 100_000,
        binsize = 200,
        seed = 148_102,
    )

    @test abs(result.energy_per_site.mean - exact.energy_per_site) <=
          6result.energy_per_site.stderr
    @test abs(result.m_equal2.mean - exact.m2) <= 6result.m_equal2.stderr
    @test abs(result.m_equal4.mean - exact.m4) <= 6result.m_equal4.stderr
end

@testset "single-spin continuous-time cluster matches analytic moments" begin
    geometry = LatticeGeometry(:single, 1, 1, Tuple{Int,Int}[], [0])
    beta = 0.7
    h = 1.3
    x = beta * h
    result = run_cwa(
        geometry;
        J = 0.0,
        h,
        beta,
        thermalization = 2_000,
        sweeps = 50_000,
        binsize = 100,
        seed = 148_101,
    )

    exact_energy = -h * tanh(x)
    exact_m2 = tanh(x) / x
    exact_m4 = 3 * (x - tanh(x)) / x^3
    @test abs(result.energy_per_site.mean - exact_energy) <=
          6result.energy_per_site.stderr
    @test abs(result.m_time2.mean - exact_m2) <= 6result.m_time2.stderr
    @test abs(result.m_time4.mean - exact_m4) <= 6result.m_time4.stderr
    @test result.mean_cuts.mean > 0
end

@testset "periodic continuous-time worldline" begin
    line = Worldline(1, [0.25, 0.75])
    @test spin_at(line, 0.10) == 1
    @test spin_at(line, 0.50) == -1
    @test spin_at(line, 0.90) == 1
    @test integrated_spin(line, 1.0) ≈ 0.0 atol = 1e-14
    @test_throws ArgumentError Worldline(1, [0.25])
    @test_throws ArgumentError Worldline(0, Float64[])
end

@testset "incremental bins reproduce an uninterrupted chain" begin
    geometry = lattice_geometry(:triangle, 3)
    a = CWAState(geometry; J=1.0, h=4.76811, beta=3 / 4.76811, seed=148201)
    b = deepcopy(a)
    thermalize!(a, 20)
    thermalize!(b, 20)
    whole = run_bins!(a, 4, 5)
    split = vcat(run_bins!(b, 2, 5), run_bins!(b, 2, 5))
    @test whole == split
    @test getfield.(a.worldlines, :spin0) == getfield.(b.worldlines, :spin0)
    @test getfield.(a.worldlines, :cuts) == getfield.(b.worldlines, :cuts)
    @test run_bins!(a, 1, 5) == run_bins!(b, 1, 5)
end
