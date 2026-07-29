include(joinpath(@__DIR__, "..", "src", "ErrorBudget.jl"))
using .ErrorBudget

@testset "G2 baseline summary and acceptance" begin
    samples = [0.80, 0.82, 0.84]
    summary = summarize_samples(samples)

    @test summary.n == 3
    @test summary.mean ≈ 0.82
    @test summary.standard_deviation ≈ 0.02
    @test summary.standard_error ≈ 0.02 / sqrt(3)
    @test acceptance_tolerance(summary) ≈ 3 * summary.standard_error
    @test baseline_acceptance([0.8210, 0.8220, 0.8215], 0.821658489).accepted
    @test !baseline_acceptance(fill(0.81, 3), 0.821658489).accepted
    @test_throws ArgumentError summarize_samples([0.82])
end
