using Test

if !isdefined(Main, :Issue86TrackB)
    include(joinpath(@__DIR__, "..", "src", "Issue86TrackB.jl"))
end
using .Issue86TrackB

@testset "Long-range DMRG uses the precision-gated periodic fit" begin
    result = dmrg_point(
        model = "long_range", sigma = 1.75, L = 6, gamma = 1.5609,
        chi = 16, poles = 16, tolerance = 1.0e-9, maxiter = 20,
        excited = false,
    )
    @test result["MPO_error"]["max_relative"] < 1.0e-8
    @test result["ed_energy_relative_error"] < 1.0e-8
    @test result["correlation_ratio_absolute_error"] < 1.0e-6
end
