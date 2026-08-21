using Test
using TensorKit

if !isdefined(Main, :Issue86TrackB)
    include(joinpath(@__DIR__, "..", "src", "Issue86TrackB.jl"))
end
using .Issue86TrackB

@testset "Finite-periodic SOE fit reaches the ED gate" begin
    @test isdefined(Issue86TrackB, :fit_periodic_soe)

    if isdefined(Issue86TrackB, :fit_periodic_soe)
        for sigma in (1.75, 2.0), L in (6, 16)
            approximation = Issue86TrackB.fit_periodic_soe(L, sigma, 16)
            @test coupling_error(L, sigma, approximation)["max_relative"] < 1.0e-8
        end

        for sigma in (1.75, 2.0)
            errors = [
                coupling_error(
                    64, sigma, Issue86TrackB.fit_periodic_soe(64, sigma, poles)
                )["max_relative"]
                for poles in (8, 12, 16)
            ]
            @test all(diff(errors) .<= 100eps(Float64))
            @test errors[end] < 1.0e-8
        end
    end
end

@testset "Periodic image MPO remains finite for small exponential rates" begin
    approximation = SOEApproximation(
        2.75, 1, 5, -737.0, -737.0, [1.0], [1.0e-320], 0.0, 0.0
    )
    dense = convert(TensorMap, soe_mpo(6, 1.75, 1.0, approximation))
    @test all(isfinite, dense[])
end
