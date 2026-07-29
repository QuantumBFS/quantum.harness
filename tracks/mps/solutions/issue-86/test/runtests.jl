using Test

include(joinpath(@__DIR__, "..", "src", "Issue86TrackB.jl"))
using .Issue86TrackB
using LinearAlgebra
using MPSKit
using TensorKit

include("periodic_fit.jl")
include("run_spec.jl")
include("formal_analysis.jl")

@testset "Issue #86 Hamiltonian conventions" begin
    @test pauli_x() * pauli_x() ≈ id(ComplexF64, ℂ^2)
    @test pauli_z() * pauli_z() ≈ id(ComplexF64, ℂ^2)

    two_site_couplings = [0.0 0.37; 0.37 0.0]
    gamma_two_site = 0.21
    identity_two_site = Matrix{ComplexF64}(I, 2, 2)
    x_matrix = Matrix(pauli_x()[])
    z_matrix = Matrix(pauli_z()[])
    analytic_two_site = -0.37 * kron(z_matrix, z_matrix) -
        gamma_two_site * (
            kron(x_matrix, identity_two_site) + kron(identity_two_site, x_matrix)
        )
    @test Matrix(ed_hamiltonian(two_site_couplings, gamma_two_site)) ≈ analytic_two_site

    for sigma in (1.75, 2.0), L in (6, 8, 12)
        for r in 1:(L - 1)
            @test periodic_coupling(L, sigma, r) ≈
                periodic_coupling(L, sigma, L - r) rtol = 1.0e-13
        end
    end

    L = 4
    gamma = 0.7
    for couplings in (nn_coupling_matrix(L), periodic_coupling_matrix(L, 1.75))
        H_ed = Matrix(ed_hamiltonian(couplings, gamma))
        H_mpo = convert(TensorMap, exact_mpo(couplings, gamma))
        values_ed = eigvals(Hermitian(H_ed))
        values_mpo = eigvals(Hermitian(reshape(Array(H_mpo[]), 1 << L, 1 << L)))
        @test values_mpo ≈ values_ed atol = 1.0e-11
    end
end

@testset "Sum-of-exponentials periodic MPO" begin
    L = 6
    sigma = 1.75
    errors = Float64[]
    for poles in (8, 12, 16)
        approximation = fit_power_law_soe(1 + sigma, poles; dmax = 128)
        push!(errors, coupling_error(L, sigma, approximation)["max_relative"])
    end
    @test issorted(errors; rev = true)
    @test errors[end] < 5.0e-4

    approximation = fit_periodic_soe(L, sigma, 16)
    exact = convert(TensorMap, exact_mpo(periodic_coupling_matrix(L, sigma), 1.2))
    fitted = convert(TensorMap, soe_mpo(L, sigma, 1.2, approximation))
    @test norm(exact - fitted) / norm(exact) < 1.0e-8
end

@testset "DMRG agrees with ED on a small NN chain" begin
    result = dmrg_point(
        model = "nn", L = 6, gamma = 1.0, chi = 16,
        tolerance = 1.0e-9, maxiter = 20, excited = true,
    )
    @test result["ed_energy_relative_error"] < 1.0e-8
    @test result["correlation_ratio_absolute_error"] < 1.0e-6
    @test abs(result["gap"] - result["ed_gap"]) < 1.0e-6
    @test result["ground_variance"] < 1.0e-8
    @test result["excited_variance"] < 1.0e-6
end

include("dmrg_periodic_gate.jl")
