using Test
using LinearAlgebra

@testset "approved periodic lattice geometry" begin
    triangle = lattice_geometry(:triangle, 3)
    @test triangle.nsites == 9
    @test length(triangle.bonds) == 27
    @test all(==(6), triangle.coordination)
    @test all(i != j for (i, j) in triangle.bonds)

    honeycomb = lattice_geometry(:honeycomb, 2)
    @test honeycomb.nsites == 8
    @test length(honeycomb.bonds) == 12
    @test all(==(3), honeycomb.coordination)
    @test all(i != j for (i, j) in honeycomb.bonds)
end

@testset "ED thermal moments use sigma-z = plus or minus one" begin
    geometry = lattice_geometry(:honeycomb, 2)
    result = ed_thermal_observables(geometry; J = 1.0, h = 2.1325, beta = 0.0)
    N = geometry.nsites

    @test result.energy_per_site ≈ 0.0 atol = 1e-12
    @test result.m2 ≈ 1 / N atol = 1e-12
    @test result.m4 ≈ (3N - 2) / N^3 atol = 1e-12
    @test result.binder_ratio ≈ N / (3N - 2) atol = 1e-12
end

@testset "exact Pauli Hamiltonian limits and h symmetry" begin
    triangle = lattice_geometry(:triangle, 3)
    @test eigmin(dense_hamiltonian(triangle; J = 1.0, h = 0.0)) ≈ -27.0 atol = 1e-12

    honeycomb = lattice_geometry(:honeycomb, 2)
    @test eigmin(dense_hamiltonian(honeycomb; J = 0.0, h = 2.0)) ≈ -16.0 atol = 1e-12

    positive = eigvals(dense_hamiltonian(honeycomb; J = 1.0, h = 2.1325))
    negative = eigvals(dense_hamiltonian(honeycomb; J = 1.0, h = -2.1325))
    @test positive ≈ negative atol = 1e-11
end

@testset "c=1 aspect ratio preserves signed-field symmetry" begin
    @test beta_for_aspect(4.76811, 8; c = 1.0) ≈ 8 / 4.76811
    @test beta_for_aspect(-2.13250, 8; c = 1.0) ≈ 8 / 2.13250
end
