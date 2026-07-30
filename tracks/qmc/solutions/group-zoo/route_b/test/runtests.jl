using Test
using RouteBWorm

@testset "Route B independence" begin
    include("test_independence.jl")
end

include("test_geometry.jl")
include("test_weight.jl")
include("test_rng.jl")
include("test_state.jl")
include("test_proposals.jl")
include("test_updates.jl")
include("test_kernel_balance.jl")
include("test_winding.jl")
include("test_estimators.jl")
include("test_statistics.jl")
include("test_task_schema.jl")
include("test_checkpoint.jl")
include("test_runner.jl")
include("test_ed_reference.jl")
include("test_ed_manifest.jl")
include("test_ed_validation.jl")
include("test_crossing_analysis.jl")
include("test_regression_calibration.jl")
include("test_regression_gate.jl")
