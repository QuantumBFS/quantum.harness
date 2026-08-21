using Test

if !isdefined(@__MODULE__, :Challenge148)
    include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
end
using .Challenge148

@testset "cut histogram reweighting matches explicit sums" begin
    n = [0, 2, 2, 4]
    m2 = [1.0, 2.0, 4.0, 8.0]
    m4 = [2.0, 5.0, 17.0, 65.0]
    hist = CutHistogramBin(n, m2, m4)
    ratio = 1.1
    weights = ratio .^ n
    expected_m2 = sum(weights .* m2) / sum(weights)
    expected_m4 = sum(weights .* m4) / sum(weights)
    result = reweight_moments(hist, ratio)
    @test result.m2 ≈ expected_m2 atol=1e-14
    @test result.m4 ≈ expected_m4 atol=1e-14
    @test reweight_binder(hist, ratio) ≈ expected_m2^2 / expected_m4 atol=1e-14
end

@testset "cut histograms are canonical and merge sufficient statistics" begin
    hist = CutHistogramBin([4, 0, 4, 2], [8.0, 1.0, 16.0, 4.0], [65.0, 2.0, 257.0, 17.0])
    @test hist.cut_counts == (0, 2, 4)
    @test hist.counts == (1, 1, 2)
    @test hist.sum_m2 == (1.0, 4.0, 24.0)
    @test hist.sum_m4 == (2.0, 17.0, 322.0)
    @test merge_histograms(hist, CutHistogramBin([2, 6], [32.0, 64.0], [1025.0, 4097.0])) ==
          CutHistogramBin([0, 2, 4, 6], [1, 2, 2, 1], [1.0, 36.0, 24.0, 64.0], [2.0, 1042.0, 322.0, 4097.0])
    @test_throws ArgumentError CutHistogramBin([2, 0], [1, 1], [1.0, 2.0], [1.0, 2.0])
    @test_throws ArgumentError CutHistogramBin([0], [0], [1.0], [2.0])
    @test_throws ArgumentError CutHistogramBin([0], [1], [NaN], [2.0])
end

@testset "log-space reweighting reports stable ESS gate" begin
    hist = CutHistogramBin(
        [249_000, 250_000, 251_000],
        [1, 2, 1],
        [1.0, 4.0, 4.0],
        [1.0, 8.0, 16.0],
    )
    for ratio in (0.999, 1.001)
        moments = reweight_moments(hist, ratio)
        @test isfinite(moments.m2)
        @test isfinite(moments.m4)
        @test isfinite(reweight_binder(hist, ratio))
    end

    ess_hist = CutHistogramBin([0, 4], [3, 1], [3.0, 8.0], [3.0, 64.0])
    ratio = 4.0
    weights = ratio .^ [0, 0, 0, 4]
    expected_fraction = (sum(weights)^2 / sum(weights .^ 2)) / length(weights)
    @test reweight_ess_fraction(ess_hist, ratio) ≈ expected_fraction atol=1e-14
    @test !reweight_moments(ess_hist, ratio).usable
    @test reweight_moments(ess_hist, 1.0).usable
end

@testset "measurement bins retain per-sweep cut statistics" begin
    state = CWAState(lattice_geometry(:triangle, 3); J=1.0, h=4.76811, beta=3 / 4.76811, seed=148407)
    record = measure_bin!(state, 4)
    @test sum(record.cut_histogram.counts) == 4
    @test sum(record.cut_histogram.sum_m2) ≈ 4 * record.m_time2 atol=1e-14
    @test sum(record.cut_histogram.sum_m4) ≈ 4 * record.m_time4 atol=1e-14
end
