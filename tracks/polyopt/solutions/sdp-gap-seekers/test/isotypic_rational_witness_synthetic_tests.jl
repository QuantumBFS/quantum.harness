using Test

include(joinpath(
    @__DIR__,
    "..",
    "scripts",
    "replay_shastry_sutherland_isotypic_rational_witness.jl",
))

@testset "isotypic rational witness helpers" begin
    value = -1.23456789012345
    @test bits_to_float(bitstring(value)) == value

    denominator_value, numerators, values =
        rounded_values([1.0, value], 6)
    @test denominator_value == 1_000_000
    @test numerators == BigInt[1_000_000, -1_234_568]
    @test values[1] == 1
    @test values[2] == -154_321 // 125_000

    positive = ExactRational[2 1; 1 2]
    positive_pivots = exact_ldl_positive_pivots(positive)
    @test !isnothing(positive_pivots)
    @test all(>(0), something(positive_pivots))

    indefinite = ExactRational[1 2; 2 1]
    @test isnothing(exact_ldl_positive_pivots(indefinite))
end
