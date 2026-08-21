using Test
import StochasticSeriesExpansion as SSE

include(joinpath(@__DIR__, "..", "..", "src", "Challenge148.jl"))
using .Challenge148
include("LegacySSEModel.jl")
using .LegacySSEModel

@testset "legacy SSE model preserves Pauli normalization and is sign-free" begin
    params = Dict{Symbol,Any}(
        :lattice => :triangle,
        :L => 3,
        :J => 1.0,
        :h => 4.76811,
        :measure => [:magnetization],
    )
    model = TFIMModel(params)
    data = SSE.generate_sse_data(model)

    @test SSE.normalization_site_count(model) == 9
    @test length(data.bonds) == 27
    @test [(bond.sites[1], bond.sites[2]) for bond in data.bonds] == model.geometry.bonds
    @test SSE.magnetization_state(model, Val(nothing), 1, 1) == 1.0
    @test SSE.magnetization_state(model, Val(nothing), 1, 2) == -1.0
    @test all(sign == 1 for vertex in data.vertex_data for sign in vertex.signs)
    @test length(SSE.get_opstring_estimators(model)) == 1

    negative = TFIMModel(merge(params, Dict(:h => -4.76811)))
    negative_data = SSE.generate_sse_data(negative)
    @test negative.h_input == -4.76811
    @test negative.h_simulated == 4.76811
    @test all(sign == 1 for vertex in negative_data.vertex_data for sign in vertex.signs)
end

@testset "legacy SSE bond Hamiltonian retains Pauli convention" begin
    Hbond = tfim_bond_hamiltonian(1.0, 2.0, 4)
    @test Hbond == [
        -1.0 -0.5 -0.5 0.0
        -0.5 1.0 0.0 -0.5
        -0.5 0.0 1.0 -0.5
        0.0 -0.5 -0.5 -1.0
    ]
end
