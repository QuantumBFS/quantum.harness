using Test
using LinearAlgebra
using ITensorMPS

include(joinpath(@__DIR__, "..", "purification_smoke.jl"))
using .PurificationSmoke

@testset "local identity purification" begin
    sites, psi = identity_pair_mps()

    @test length(sites) == 2
    @test norm(psi) ≈ 1.0 atol = 1.0e-12

    observables = impurity_observables(psi)
    @test observables.occupancy ≈ 1.0 atol = 1.0e-12
    @test observables.double_occupancy ≈ 0.25 atol = 1.0e-12
end

@testset "one-site interacting thermal trace" begin
    beta = 1.7
    interaction = 0.8
    sites, psi = thermal_impurity_purification(beta, interaction)

    @test norm(psi) ≈ 1.0 atol = 1.0e-12

    observables = impurity_observables(psi)
    partition_function = 2 + 2 * exp(beta * interaction / 2)
    exact_double_occupancy = inv(partition_function)

    @test observables.occupancy ≈ 1.0 atol = 1.0e-12
    @test observables.double_occupancy ≈ exact_double_occupancy atol = 1.0e-12
    @test maximum(linkdims(psi); init = 1) == 4
end

include("finite_bath_purification.jl")
include("finite_bath_observables.jl")
include("finite_bath_mps_runner.jl")
include("qn_mpo_capability.jl")
include("finite_bath_checkpoint.jl")
