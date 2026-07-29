using Test

if !isdefined(Main, :Issue86TrackB)
    include(joinpath(@__DIR__, "..", "src", "Issue86TrackB.jl"))
end
using .Issue86TrackB

row(gamma, ratio) = Dict{String, Any}(
    "Gamma" => gamma,
    "correlation_ratio" => ratio,
)

@testset "Crossing interpolation reports its bracket" begin
    small = [row(1.0, 0.20), row(2.0, 0.40)]
    large = [row(1.0, 0.30), row(2.0, 0.35)]
    result = crossing_bracket(small, large)

    @test result["Gamma_low"] == 1.0
    @test result["Gamma_high"] == 2.0
    @test result["Gamma_crossing"] ≈ 5 / 3
    @test result["interpolation_half_width"] == 0.5
end

@testset "Power-law crossing extrapolation recovers the limit" begin
    values = [
        Dict("L" => L, "Gamma_crossing" => 1.5609 + 0.4 / L)
        for L in (8, 16, 24, 32)
    ]
    fit = fit_crossing_sequence(values)

    @test fit["Gamma_c"] ≈ 1.5609 atol = 1.0e-8
    @test fit["omega"] ≈ 1.0 atol = 1.0e-8
    @test fit["rmse"] < 1.0e-10
    @test fit["without_smallest"]["Gamma_c"] ≈ 1.5609 atol = 1.0e-8
end

@testset "Conservative uncertainty is a linear error budget" begin
    audit = conservative_error_budget(
        1.5608;
        interpolation = 0.0001,
        finite_size = 0.0002,
        chi = 0.00005,
        mpo = 0.00003,
        reference = 1.5609,
        reference_error = 0.0003,
    )

    @test audit["total_error"] ≈ 0.00038
    @test audit["interval"] ≈ [1.56042, 1.56118]
    @test audit["covers_reference_interval"]
end

@testset "Energy variance is normalized by the squared energy" begin
    @test normalized_energy_variance(2.0, -4.0) == 0.125
    @test normalized_energy_variance(0.0, 0.0) == 0.0
end

@testset "NN gap fit selects the largest chi at Gamma one" begin
    rows = Dict{String, Any}[]
    for L in (16, 24, 32, 48, 64), chi in (64, 128)
        push!(rows, Dict(
            "model" => "nn",
            "L" => L,
            "Gamma" => 1.0,
            "chi" => chi,
            "gap" => 2.0 / L,
        ))
    end
    fit = fit_dynamic_exponent(rows)

    @test fit["z"] ≈ 1.0 atol = 1.0e-12
    @test fit["without_smallest"]["z"] ≈ 1.0 atol = 1.0e-12
    @test fit["chis"] == fill(128, 5)
end
