using Test
using LinearAlgebra
using ITensors
using ITensorMPS

include(joinpath(@__DIR__, "..", "finite_bath_purification.jl"))
using .FiniteBathPurification:
    FiniteBathParameters,
    MAX_EVOLUTION_STEPS,
    MAX_IMAGINARY_TIME_STEPS,
    MAX_LOCAL_EXPONENT_MAGNITUDE,
    evolve_purification,
    identity_purification,
    interleaved_sites,
    physical_hamiltonian_mpo

function dense_annihilation(n_modes::Int, mode::Int)
    dimension = 1 << n_modes
    operator = zeros(Float64, dimension, dimension)
    mask = 1 << (mode - 1)
    lower_mask = mask - 1
    for source in 0:(dimension - 1)
        iszero(source & mask) && continue
        target = source ⊻ mask
        sign = isodd(count_ones(source & lower_mask)) ? -1.0 : 1.0
        operator[target + 1, source + 1] = sign
    end
    return operator
end

@testset "shared TDVP loop emits bounded step progress" begin
    parameters =
        FiniteBathParameters([0.0], [0.1]; U = 0.8, epsilon_d = -0.4)
    text = mktemp() do path, output
        redirect_stdout(output) do
            evolve_purification(
                parameters;
                beta = 0.2,
                time_step = 0.01,
                cutoff = 1.0e-12,
                maxdim = 64,
                progress = true,
                progress_label = "thermal-test",
            )
        end
        flush(output)
        read(path, String)
    end
    lines = filter(
        line -> contains(line, "progress phase=tdvp"),
        split(text, '\n'),
    )
    @test 10 <= length(lines) <= 50
    @test all(contains("evolution=thermal-test"), lines)
    @test all(contains("step="), lines)
    @test all(contains("beta_endpoint="), lines)
    @test all(contains("max_link_dimension="), lines)
    @test all(contains("truncation_max_error="), lines)
    @test all(contains("krylov_all_converged="), lines)
    @test all(contains("krylov_max_error_estimate="), lines)
end

function independent_dense_thermal(parameters, beta)
    n_orbitals = length(parameters.epsilon) + 1
    annihilators = [
        dense_annihilation(2 * n_orbitals, mode)
        for mode in 1:(2 * n_orbitals)
    ]
    numbers = [operator' * operator for operator in annihilators]
    hamiltonian =
        (parameters.epsilon_d - parameters.mu) * (numbers[1] + numbers[2]) +
        parameters.U * numbers[1] * numbers[2]
    for bath in eachindex(parameters.epsilon)
        for spin in 1:2
            bath_mode = 2 * bath + spin
            impurity_mode = spin
            hamiltonian +=
                (parameters.epsilon[bath] - parameters.mu) *
                numbers[bath_mode]
            hamiltonian +=
                parameters.V[bath] *
                (
                    annihilators[impurity_mode]' *
                    annihilators[bath_mode] +
                    annihilators[bath_mode]' *
                    annihilators[impurity_mode]
                )
        end
    end
    eig = eigen(Hermitian(hamiltonian))
    weights = exp.(-beta .* (eig.values .- minimum(eig.values)))
    probabilities = weights ./ sum(weights)
    density = eig.vectors * Diagonal(probabilities) * eig.vectors'
    occupancy = real(tr(density * (numbers[1] + numbers[2])))
    double_occupancy = real(tr(density * numbers[1] * numbers[2]))
    normalized_purification_norm = norm(sqrt.(probabilities))
    raw_purification_norm =
        sqrt(sum(exp.(-beta .* eig.values)) / length(eig.values))
    return (;
        occupancy,
        double_occupancy,
        normalized_purification_norm,
        raw_purification_norm,
    )
end

@testset "finite-bath parameter validation" begin
    @test_throws ArgumentError FiniteBathParameters([0.0, 0.1], [0.2])
    @test_throws ArgumentError FiniteBathParameters([Inf], [0.2])
    @test_throws ArgumentError FiniteBathParameters([0.0], [-0.2])
    @test_throws ArgumentError FiniteBathParameters([0.0], [0.2]; U = -0.1)
    @test_throws ArgumentError FiniteBathParameters([0.0], [0.2]; mu = NaN)

    parameters = FiniteBathParameters([0.0], [0.2])
    @test_throws ArgumentError evolve_purification(parameters; beta = -1.0)
    @test_throws ArgumentError evolve_purification(parameters; beta = Inf)
    @test_throws ArgumentError evolve_purification(parameters; beta = 1.0, time_step = 0.0)
    @test_throws ArgumentError evolve_purification(parameters; beta = 1.0, cutoff = -1.0)
    @test_throws ArgumentError evolve_purification(parameters; beta = 1.0, maxdim = 0)
    @test_throws ArgumentError evolve_purification(
        parameters; beta = 1.0, time_step = nextfloat(0.0)
    )
    @test_throws ArgumentError evolve_purification(
        parameters;
        beta = 1.0,
        time_step = 1 / (MAX_IMAGINARY_TIME_STEPS + 1),
    )
end

@testset "safe increment subdivision and rejection" begin
    parameters =
        FiniteBathParameters([0.2], [0.0]; U = 0.0, epsilon_d = 0.2)

    @test MAX_EVOLUTION_STEPS == MAX_IMAGINARY_TIME_STEPS
    huge_error = try
        evolve_purification(parameters; beta = 1.0e308, time_step = 1.0e308)
        nothing
    catch error
        error
    end
    @test huge_error isa ArgumentError
    @test occursin("safe", lowercase(sprint(showerror, huge_error)))
    @test occursin("MAX_EVOLUTION_STEPS", sprint(showerror, huge_error))

    beta = 100.0
    result = evolve_purification(
        parameters; beta, time_step = beta, cutoff = 1.0e-13, maxdim = 64
    )
    bound = result.diagnostics.hamiltonian_norm_bound
    exact_occupancy = 2 / (1 + exp(beta * parameters.epsilon_d))

    @test bound ≈ 0.8 atol = 0.0
    @test result.diagnostics.requested_time_step == beta
    @test result.diagnostics.effective_time_step < beta
    @test result.diagnostics.requested_steps == 1
    @test 1 < result.diagnostics.steps <= MAX_EVOLUTION_STEPS
    @test result.diagnostics.maximum_safe_beta_increment ≈
          2 * MAX_LOCAL_EXPONENT_MAGNITUDE / bound
    @test all(
        entry ->
            entry.beta_increment * bound / 2 <=
            MAX_LOCAL_EXPONENT_MAGNITUDE * (1 + 2 * eps()),
        result.diagnostics.step_history,
    )
    @test last(result.diagnostics.step_history).beta_endpoint == beta
    @test FiniteBathPurification.impurity_observables(result.psi).occupancy ≈
          exact_occupancy atol = 2.0e-10
    @test isfinite(result.diagnostics.log_unnormalized_norm)
end

@testset "Krylov aggregation includes every updater call" begin
    metrics = FiniteBathPurification.KrylovStepMetrics()
    FiniteBathPurification._accumulate_krylov!(
        metrics,
        (; converged = 1, normres = 1.0e-12, numops = 4, numiter = 1),
    )
    FiniteBathPurification._accumulate_krylov!(
        metrics,
        (; converged = 0, normres = 3.0e-8, numops = 7, numiter = 2),
    )

    @test metrics.local_updates == 2
    @test !metrics.all_converged
    @test metrics.max_error_estimate == 3.0e-8
    @test metrics.num_operations == 11
    @test metrics.num_iterations == 3
end

@testset "beta-zero identity purification with one bath orbital" begin
    parameters = FiniteBathParameters([0.17], [0.23])
    sites, psi = identity_purification(parameters)

    @test length(sites) == 4
    @test norm(psi) ≈ 1.0 atol = 1.0e-13
    @test maximum(linkdims(psi); init = 1) == 4
    @test expect(psi, "Ntot")[[1, 3]] ≈ [1.0, 1.0] atol = 1.0e-13
    @test expect(psi, "Nupdn")[[1, 3]] ≈ [0.25, 0.25] atol = 1.0e-13
end

@testset "public beta-zero evolution returns identity diagnostics" begin
    parameters = FiniteBathParameters([0.17], [0.23])
    result = evolve_purification(parameters; beta = 0.0)
    impurity = FiniteBathPurification.impurity_observables(result.psi)

    @test result.diagnostics.steps == 0
    @test result.diagnostics.log_unnormalized_norm == 0.0
    @test isempty(result.diagnostics.step_history)
    @test norm(result.psi) ≈ 1.0 atol = 1.0e-13
    @test impurity.occupancy ≈ 1.0 atol = 1.0e-13
    @test impurity.double_occupancy ≈ 0.25 atol = 1.0e-13
end

@testset "site validation rejects aliases and non-Electron tags" begin
    parameters = FiniteBathParameters([0.2], [0.1])
    sites = interleaved_sites(parameters)

    repeated_index = copy(sites)
    repeated_index[2] = repeated_index[1]
    @test_throws ArgumentError physical_hamiltonian_mpo(repeated_index, parameters)

    repeated_tags = [
        Index(4, "Electron,Site,n=1") for _ in eachindex(sites)
    ]
    @test_throws ArgumentError physical_hamiltonian_mpo(repeated_tags, parameters)

    wrong_tag = copy(sites)
    wrong_tag[2] = Index(4, "Site,n=2")
    @test_throws ArgumentError physical_hamiltonian_mpo(wrong_tag, parameters)
end

@testset "physical MPO is Hermitian and carries strings through ancillas" begin
    coupling = 0.37
    parameters = FiniteBathParameters([0.2], [coupling]; U = 0.0, epsilon_d = 0.0)
    sites = interleaved_sites(parameters)
    hamiltonian = physical_hamiltonian_mpo(sites, parameters)

    source_even = MPS(sites, ["Emp", "Emp", "Up", "Emp"])
    target_even = MPS(sites, ["Up", "Emp", "Emp", "Emp"])
    source_odd = MPS(sites, ["Emp", "Up", "Up", "Emp"])
    target_odd = MPS(sites, ["Up", "Up", "Emp", "Emp"])
    @test real(inner(target_even', hamiltonian, source_even)) ≈ coupling atol = 1.0e-14
    @test real(inner(target_odd', hamiltonian, source_odd)) ≈ -coupling atol = 1.0e-14

    left = random_mps(sites; linkdims = 3)
    right = random_mps(sites; linkdims = 3)
    @test inner(left', hamiltonian, right) ≈
          conj(inner(right', hamiltonian, left)) atol = 1.0e-12
end

@testset "decoupled bath has factorized thermal limits" begin
    beta = 2.3
    parameters =
        FiniteBathParameters([0.31], [0.0]; U = 0.8, epsilon_d = -0.4)
    result = evolve_purification(
        parameters; beta, time_step = 0.1, cutoff = 1.0e-13, maxdim = 64
    )
    impurity = FiniteBathPurification.impurity_observables(result.psi)
    impurity_weights = [1.0, exp(-beta * parameters.epsilon_d),
                        exp(-beta * parameters.epsilon_d),
                        exp(-beta * (2 * parameters.epsilon_d + parameters.U))]
    exact_double = impurity_weights[4] / sum(impurity_weights)
    exact_bath_occupancy = 2 / (1 + exp(beta * parameters.epsilon[1]))

    @test impurity.occupancy ≈ 1.0 atol = 2.0e-10
    @test impurity.double_occupancy ≈ exact_double atol = 2.0e-10
    @test real(expect(result.psi, "Ntot")[3]) ≈ exact_bath_occupancy atol = 2.0e-10
end

@testset "nonzero chemical potential shifts all decoupled levels" begin
    beta = 1.9
    mu = 0.13
    parameters = FiniteBathParameters(
        [0.31], [0.0]; U = 0.8, epsilon_d = -0.27, mu
    )
    result = evolve_purification(
        parameters; beta, time_step = 0.1, cutoff = 1.0e-13, maxdim = 64
    )
    impurity = FiniteBathPurification.impurity_observables(result.psi)
    shifted_impurity = parameters.epsilon_d - mu
    shifted_bath = parameters.epsilon[1] - mu
    impurity_weights = [
        1.0,
        exp(-beta * shifted_impurity),
        exp(-beta * shifted_impurity),
        exp(-beta * (2 * shifted_impurity + parameters.U)),
    ]

    @test impurity.occupancy ≈
          (impurity_weights[2] + impurity_weights[3] + 2 * impurity_weights[4]) /
          sum(impurity_weights) atol = 2.0e-10
    @test impurity.double_occupancy ≈
          impurity_weights[4] / sum(impurity_weights) atol = 2.0e-10
    @test real(expect(result.psi, "Ntot")[3]) ≈
          2 / (1 + exp(beta * shifted_bath)) atol = 2.0e-10
end

@testset "one-bath purification matches independent dense thermal trace" begin
    beta = 1.2
    parameters =
        FiniteBathParameters([0.17], [0.23]; U = 0.8, epsilon_d = -0.4)
    exact = independent_dense_thermal(parameters, beta)
    result = evolve_purification(
        parameters; beta, time_step = 0.02, cutoff = 1.0e-14, maxdim = 256
    )
    impurity = FiniteBathPurification.impurity_observables(result.psi)

    @test norm(result.psi) ≈ exact.normalized_purification_norm atol = 2.0e-12
    @test impurity.occupancy ≈ exact.occupancy atol = 2.0e-8
    @test impurity.double_occupancy ≈ exact.double_occupancy atol = 2.0e-8
    @test exp(result.diagnostics.log_unnormalized_norm) ≈
          exact.raw_purification_norm atol = 2.0e-8
    @test result.diagnostics.beta == beta
    @test result.diagnostics.steps == 60
    @test result.diagnostics.norm ≈ 1.0 atol = 2.0e-12
    @test result.diagnostics.max_link_dimension <= 256
    @test length(result.diagnostics.maximum_link_dimensions_by_bond) ==
          length(result.sites) - 1
    @test maximum(result.diagnostics.maximum_link_dimensions_by_bond) ==
          result.diagnostics.max_link_dimension
    @test all(>(0), result.diagnostics.maximum_link_dimensions_by_bond)
    @test result.diagnostics.parameters == parameters

    history = result.diagnostics.step_history
    @test length(history) == result.diagnostics.steps
    @test last(history).beta_endpoint ≈ beta atol = 2.0e-15
    @test all(entry -> isfinite(entry.log_norm_increment), history)
    @test all(entry -> isfinite(entry.cumulative_log_norm), history)
    @test all(entry -> entry.max_link_dimension <= 256, history)
    @test all(entry -> entry.max_truncation_error >= 0, history)
    @test all(entry -> entry.krylov_all_converged, history)
    @test all(entry -> entry.krylov_max_error_estimate >= 0, history)
    @test all(entry -> entry.krylov_num_operations > 0, history)
    @test all(entry -> entry.krylov_num_iterations >= 0, history)
    @test all(entry -> entry.krylov_local_updates > 0, history)
    @test all(
        entry ->
            entry.krylov_local_updates >
            entry.observer_visible_krylov_updates,
        history,
    )
    @test result.diagnostics.metric_availability == (
        truncation_error = "ITensor two-site SVD spec.truncerr",
        krylov_error = "KrylovKit exponentiate info.normres estimate",
    )
end

@testset "Krylov expansion is explicit and defaults to scalable TDVP" begin
    parameters = FiniteBathParameters(
        [-0.5, 0.5], [0.1, 0.1]; U = 0.8, epsilon_d = -0.4
    )
    scalable = evolve_purification(
        parameters;
        beta = 0.02,
        time_step = 0.02,
        cutoff = 1.0e-14,
        maxdim = 64,
    )
    expanded = evolve_purification(
        parameters;
        beta = 0.02,
        time_step = 0.02,
        cutoff = 1.0e-14,
        maxdim = 64,
        krylov_expansion_dim = 2,
    )

    @test scalable.diagnostics.expansion_krylov_dimension == 0
    @test expanded.diagnostics.expansion_krylov_dimension == 2
    @test expanded.diagnostics.expanded_max_link_dimension >=
          expanded.diagnostics.initial_max_link_dimension
end
