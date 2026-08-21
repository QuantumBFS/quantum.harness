using Test

module AvailableAnalysisHarness
include(joinpath(@__DIR__, "..", "scripts", "analyze_available_results.jl"))
end

@testset "available-result analysis labels gate failures without a verdict" begin
    @test AvailableAnalysisHarness.analysis_status(true, true) ==
          (status="pass", verdict_eligible=true)
    @test AvailableAnalysisHarness.analysis_status(false, true) ==
          (status="gate-pending", verdict_eligible=false)
    @test AvailableAnalysisHarness.analysis_status(true, false) ==
          (status="gate-pending", verdict_eligible=false)
end

@testset "available-result analysis CLI is exact" begin
    @test AvailableAnalysisHarness.parse_available_args([
        "--manifest", "campaign.json",
        "--results", "raw",
        "--output", "analysis",
    ]) == (manifest="campaign.json", results="raw", output="analysis")
    @test_throws ArgumentError AvailableAnalysisHarness.parse_available_args(String[])
    @test_throws ArgumentError AvailableAnalysisHarness.parse_available_args([
        "--results", "raw", "--manifest", "campaign.json", "--output", "analysis",
    ])
end
