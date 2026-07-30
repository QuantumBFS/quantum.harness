using Test
include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
using .Challenge148

@testset "production module is SSE-independent" begin
    @test !isdefined(Challenge148, :TFIMModel)
    @test !isdefined(Challenge148, :SSE)
end

include("test_geometry_ed.jl")
include("test_cluster.jl")
include("test_task_schema.jl")
include("test_checkpoint_io.jl")
include("test_reweighting.jl")
include("test_runner.jl")
include("test_available_analysis.jl")
include("test_diagnostics.jl")
include("test_aggregation.jl")
include("test_fss_analysis.jl")
include("test_manifest_generation.jl")
include("test_calibration_builder.jl")
