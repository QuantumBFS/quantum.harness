using Test
using LinearAlgebra
using JSON3
using ITensors
using ITensorMPS

isdefined(Main, :FiniteBathPurification) ||
    include(joinpath(@__DIR__, "..", "finite_bath_purification.jl"))
using .FiniteBathPurification: FiniteBathParameters

include(joinpath(@__DIR__, "..", "finite_bath_observables.jl"))
using .FiniteBathObservables:
    ObservableCursor,
    ObservableInterrupted,
    _thermal_setup_maxima,
    build_finite_bath_context,
    copy_identity_purification,
    finite_bath_observables,
    impurity_green_function
using .FiniteBathCheckpoint:
    CheckpointCursor,
    CheckpointIdentity,
    EvolutionResumeState,
    ObservableResumeState,
    load_current_checkpoint,
    write_checkpoint_generation

function observables_dense_annihilation(n_modes::Int, mode::Int)
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

function assert_observable_equivalence(actual, expected)
    @test actual.n_d ≈ expected.n_d atol = 1.0e-10
    @test actual.double_occupancy ≈ expected.double_occupancy atol = 1.0e-10
    @test actual.G_up ≈ expected.G_up atol = 1.0e-10
    @test actual.G_dn ≈ expected.G_dn atol = 1.0e-10
    @test actual.tau == expected.tau
    @test actual.diagnostics == expected.diagnostics
    @test keys(actual.thermal_state.diagnostics) ==
          keys(expected.thermal_state.diagnostics)
    for key in keys(actual.thermal_state.diagnostics)
        actual_value = getproperty(actual.thermal_state.diagnostics, key)
        expected_value = getproperty(expected.thermal_state.diagnostics, key)
        if key === :parameters
            @test fieldnames(typeof(actual_value)) ==
                  fieldnames(typeof(expected_value))
            for field in fieldnames(typeof(actual_value))
                @test getfield(actual_value, field) ==
                      getfield(expected_value, field)
            end
        else
            @test actual_value == expected_value
        end
    end
end

"""
Independent full-Fock-space thermal trace. This test oracle intentionally
constructs K directly and never calls a production Hamiltonian helper.
"""
function independent_observables_trace(parameters, beta, tau)
    n_orbitals = length(parameters.epsilon) + 1
    annihilators = [
        observables_dense_annihilation(2 * n_orbitals, mode)
        for mode in 1:(2 * n_orbitals)
    ]
    numbers = [operator' * operator for operator in annihilators]
    K =
        (parameters.epsilon_d - parameters.mu) * (numbers[1] + numbers[2]) +
        parameters.U * numbers[1] * numbers[2]
    for bath in eachindex(parameters.epsilon)
        for spin in 1:2
            bath_mode = 2 * bath + spin
            K +=
                (parameters.epsilon[bath] - parameters.mu) *
                numbers[bath_mode]
            K +=
                parameters.V[bath] *
                (
                    annihilators[spin]' * annihilators[bath_mode] +
                    annihilators[bath_mode]' * annihilators[spin]
                )
        end
    end

    eig = eigen(Hermitian(K))
    shifted = eig.values .- minimum(eig.values)
    weights = exp.(-beta .* shifted)
    scaled_Z = sum(weights)
    density = eig.vectors * Diagonal(weights ./ scaled_Z) * eig.vectors'
    n_up = real(tr(density * numbers[1]))
    n_dn = real(tr(density * numbers[2]))
    double_occupancy = real(tr(density * numbers[1] * numbers[2]))
    green = Dict{Symbol,Vector{Float64}}()
    for (spin, mode) in ((:up, 1), (:dn, 2))
        d_eigen = eig.vectors' * annihilators[mode] * eig.vectors
        spectral_weight = abs2.(d_eigen)
        green[spin] = [
            -sum(
                exp.(
                    -(beta - tau_value) .* shifted .-
                    tau_value .* shifted'
                ) .* spectral_weight,
            ) / scaled_Z for tau_value in tau
        ]
    end
    return (; n_up, n_dn, n_d = n_up + n_dn, double_occupancy, green)
end

function python_chain_fixtures()
    solution_dir = normpath(joinpath(@__DIR__, "..", ".."))
    script = """
import json
import sys
sys.path.insert(0, sys.argv[1])
import bath
import chain_mapping

fixtures = []
for n_bath in range(1, 7):
    star = bath.make_bath_artifact(
        gamma=0.1,
        bandwidth=1.0,
        n_bath=n_bath,
        frequency_grid=[-1.0, 0.0, 1.0],
    )
    mapping = chain_mapping.derive_chain_mapping(star)
    fixtures.append({
        "n_bath": n_bath,
        "epsilon": star["payload"]["epsilon"],
        "coupling": star["payload"]["V"],
        "lambda": mapping["payload"]["lambda"],
        "chain_onsite": mapping["payload"]["chain_onsite"],
        "chain_hopping": mapping["payload"]["chain_hopping"],
        "mapping_sha256": mapping["sha256"],
        "spin_transform": mapping["payload"]["conventions"]["spin_transform"],
    })
print(json.dumps(fixtures, sort_keys=True, separators=(",", ":")))
"""
    command =
        `uv run --project=$solution_dir --frozen python -c $script $solution_dir`
    return JSON3.read(read(command, String))
end

function mapped_observable_parameters(fixture)
    epsilon = Float64.(fixture["epsilon"])
    coupling = Float64.(fixture["coupling"])
    n_bath = Int(fixture["n_bath"])
    common = (; U = 0.8, epsilon_d = -0.4, mu = 0.0)
    direct = FiniteBathParameters(epsilon, coupling; common...)
    chain = FiniteBathParameters(
        :chain;
        epsilon,
        V = [Float64(fixture["lambda"]); zeros(n_bath - 1)],
        chain_onsite = Float64.(fixture["chain_onsite"]),
        chain_hopping = Float64.(fixture["chain_hopping"]),
        lambda = Float64(fixture["lambda"]),
        mapping_sha256 = String(fixture["mapping_sha256"]),
        common...,
    )
    return direct, chain
end

function assert_geometry_diagnostics(result, context, representation, mapping_sha256)
    @test context.spin_qn_enabled == false
    @test context.bath_representation === representation
    @test context.chain_mapping_sha256 == mapping_sha256
    @test context.spin_transform == "the same real Q is used for up and down"
    @test all(!hasqns(site) for site in context.sites)
    @test result.diagnostics.bath_representation === representation
    @test result.diagnostics.chain_mapping_sha256 == mapping_sha256
    @test result.diagnostics.spin_qn_enabled == false
    @test result.diagnostics.spin_transform == context.spin_transform
    @test result.provenance.bath_representation === representation
    @test result.provenance.chain_mapping_sha256 == mapping_sha256
    @test result.provenance.spin_transform == context.spin_transform
end

function assert_star_chain_observables(chain, direct; atol)
    @test chain.n_d ≈ direct.n_d atol = atol
    @test chain.double_occupancy ≈ direct.double_occupancy atol = atol
    average_chain = (chain.G_up .+ chain.G_dn) ./ 2
    average_direct = (direct.G_up .+ direct.G_dn) ./ 2
    @test maximum(abs.(chain.G_up .- direct.G_up); init = 0.0) <= atol
    @test maximum(abs.(chain.G_dn .- direct.G_dn); init = 0.0) <= atol
    @test maximum(abs.(average_chain .- average_direct); init = 0.0) <= atol
    @test maximum(
        abs.(chain.G_up[[1, end]] .- direct.G_up[[1, end]]);
        init = 0.0,
    ) <= atol
    @test maximum(
        abs.(chain.G_dn[[1, end]] .- direct.G_dn[[1, end]]);
        init = 0.0,
    ) <= atol
    @test maximum(
        abs.(chain.G_up[2:(end - 1)] .- direct.G_up[2:(end - 1)]);
        init = 0.0,
    ) <= atol
    @test maximum(
        abs.(chain.G_dn[2:(end - 1)] .- direct.G_dn[2:(end - 1)]);
        init = 0.0,
    ) <= atol
end

const CHAIN_FIXTURES = python_chain_fixtures()

@testset "geometry diagnostics preserve mapped spin convention without QNs" begin
    fixture = CHAIN_FIXTURES[2]
    direct, chain = mapped_observable_parameters(fixture)
    direct_context = build_finite_bath_context(direct)
    chain_context = build_finite_bath_context(chain)

    @test fixture["spin_transform"] ==
          "the same real Q is used for up and down"
    @test direct_context.bath_representation === :direct_star
    @test chain_context.bath_representation === :chain
    @test direct_context.chain_mapping_sha256 === nothing
    @test chain_context.chain_mapping_sha256 == fixture["mapping_sha256"]
    @test direct_context.spin_qn_enabled == false
    @test chain_context.spin_qn_enabled == false
    @test direct_context.spin_transform == chain_context.spin_transform
end

@testset "direct star and mapped finite chain MPS observables agree for N_b=1:6" begin
    beta = 0.04
    tau = [0.0, beta / 4, beta / 2, 3 * beta / 4, beta]
    settings = (;
        beta,
        tau,
        time_step = 0.04,
        cutoff = 1.0e-14,
        maxdim = 128,
        krylov_expansion_dim = 0,
    )
    for fixture in CHAIN_FIXTURES
        direct, chain = mapped_observable_parameters(fixture)
        direct_context = build_finite_bath_context(direct)
        chain_context = build_finite_bath_context(chain)
        star_result = finite_bath_observables(direct; settings...)
        chain_result = finite_bath_observables(chain; settings...)

        # A single unexpanded two-site TDVP step is intentionally bounded but
        # not basis invariant. The stricter expanded fixture below retains the
        # established 1e-6 acceptance threshold.
        assert_star_chain_observables(chain_result, star_result; atol = 5.0e-6)
        assert_geometry_diagnostics(
            star_result, direct_context, :direct_star, nothing
        )
        assert_geometry_diagnostics(
            chain_result,
            chain_context,
            :chain,
            String(fixture["mapping_sha256"]),
        )
    end
end

@testset "mapped two-site chain retains stricter acceptance settings" begin
    fixture = CHAIN_FIXTURES[2]
    direct, chain = mapped_observable_parameters(fixture)
    beta = 0.5
    settings = (;
        beta,
        tau = [0.0, 0.125, 0.25, 0.375, beta],
        time_step = 0.02,
        cutoff = 1.0e-14,
        maxdim = 128,
        krylov_expansion_dim = 32,
    )
    star_result = finite_bath_observables(direct; settings...)
    chain_result = finite_bath_observables(chain; settings...)
    assert_star_chain_observables(chain_result, star_result; atol = 1.0e-6)
end

@testset "direct and chain interruption resume preserve geometry equivalence" begin
    fixture = CHAIN_FIXTURES[1]
    direct, chain = mapped_observable_parameters(fixture)
    beta = 0.04
    common = (;
        beta,
        tau = [0.0, beta / 2, beta],
        time_step = 0.02,
        cutoff = 1.0e-14,
        maxdim = 128,
        krylov_expansion_dim = 0,
    )
    resumed = Dict{Symbol,Any}()
    uninterrupted = Dict{Symbol,Any}()
    for (representation, parameters) in
        ((:direct_star, direct), (:chain, chain))
        uninterrupted[representation] =
            finite_bath_observables(parameters; common...)
        published = Ref{Any}(nothing)
        publications = Ref(0)
        interruption = try
            finite_bath_observables(
                parameters;
                common...,
                checkpoint_manager = (psi, state) -> begin
                    publications[] += 1
                    published[] = (; psi = copy(psi), resume_state = state)
                end,
                stop_requested = () -> publications[] == 2,
            )
            nothing
        catch error
            error
        end
        @test interruption isa ObservableInterrupted
        @test published[] !== nothing
        resumed[representation] = finite_bath_observables(
            parameters; common..., resume = published[]
        )
        assert_observable_equivalence(
            resumed[representation], uninterrupted[representation]
        )
    end
    assert_star_chain_observables(
        resumed[:chain], resumed[:direct_star]; atol = 1.0e-6
    )
end

@testset "finite-bath observable input validation" begin
    parameters = FiniteBathParameters(
        [0.21], [0.19]; U = 0.73, epsilon_d = -0.29, mu = 0.08
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters; beta = -0.1, tau = [0.0]
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters; beta = 1.0, tau = Float64[]
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters; beta = 1.0, tau = [NaN]
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters; beta = 1.0, tau = [-eps()]
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters; beta = 1.0, tau = [nextfloat(1.0)]
    )
    @test_throws ArgumentError impurity_green_function(
        parameters; beta = 1.0, tau = [0.5], spin = :sideways
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters;
        beta = 1.0,
        tau = [0.5],
        krylov_expansion_dim = -1,
    )
end

@testset "one-bath MPS observables match independent dense trace" begin
    beta = 1.3
    tau = [beta, 0.17, 0.0, 0.89, 0.51, 0.17]
    parameters = FiniteBathParameters(
        [0.23], [0.27]; U = 0.71, epsilon_d = -0.31, mu = 0.09
    )
    exact = independent_observables_trace(parameters, beta, tau)
    result = finite_bath_observables(
        parameters;
        beta,
        tau,
        time_step = 0.02,
        cutoff = 1.0e-14,
        maxdim = 256,
        krylov_expansion_dim = 0,
    )

    errors = vcat(
        abs(result.n_d - exact.n_d),
        abs(result.double_occupancy - exact.double_occupancy),
        abs.(result.G_up .- exact.green[:up]),
        abs.(result.G_dn .- exact.green[:dn]),
    )
    println("dense-reference max error: ", maximum(errors))
    @test maximum(errors) <= 1.0e-6
    @test result.tau == tau
    @test result.G_up[6] == result.G_up[2]
    @test result.G_dn[6] == result.G_dn[2]
    @test result.diagnostics.green_up[6].tau == tau[6]
    @test result.diagnostics.green_dn[6].tau == tau[6]
    @test result.G_up[3] ≈ -(1 - exact.n_up) atol = 1.0e-6
    @test result.G_up[1] ≈ -exact.n_up atol = 1.0e-6
    @test result.G_dn[3] ≈ -(1 - exact.n_dn) atol = 1.0e-6
    @test result.G_dn[1] ≈ -exact.n_dn atol = 1.0e-6

    @test length(result.diagnostics.green_up) == length(tau)
    @test length(result.diagnostics.green_dn) == length(tau)
    for entry in vcat(
        result.diagnostics.green_up, result.diagnostics.green_dn
    )
        @test all(isfinite, values(entry.branch_log_norms))
        @test entry.overlap_magnitude >= 0
        @test !haskey(entry, :overlap_phase)
        @test !haskey(entry, :imaginary_residual)
        @test entry.max_link_dimension <= 256
        @test length(entry.maximum_link_dimensions_by_bond) ==
              length(result.thermal_state.sites) - 1
        @test maximum(entry.maximum_link_dimensions_by_bond) ==
              entry.max_link_dimension
        @test entry.truncation.max_error >= 0
        @test entry.krylov.max_error_estimate >= 0
        @test entry.settings.time_step == 0.02
        @test entry.settings.cutoff == 1.0e-14
        @test entry.settings.maxdim == 256
        @test entry.settings.krylov_expansion_dim == 0
        @test !haskey(entry, :step_history)
    end
    @test occursin("full grand-canonical", result.provenance.thermal_space)
    @test occursin("beta-tau", result.provenance.green_function)
    @test result.provenance.impurity_physical_site == 1
    @test result.thermal_state.diagnostics.expansion_krylov_dimension == 0
    @test length(result.diagnostics.maximum_link_dimensions_by_bond) ==
          length(result.thermal_state.sites) - 1
    @test maximum(result.diagnostics.maximum_link_dimensions_by_bond) ==
          maximum(
              vcat(
                  result.thermal_state.diagnostics.maximum_link_dimensions_by_bond,
                  (
                      entry.maximum_link_dimensions_by_bond
                      for entry in vcat(
                          result.diagnostics.green_up,
                          result.diagnostics.green_dn,
                      )
                  )...,
              ),
          )
end

@testset "particle-hole symmetry and endpoint identities" begin
    beta = 1.1
    tau = [0.0, beta]
    parameters =
        FiniteBathParameters([0.0], [0.22]; U = 0.8, epsilon_d = -0.4)
    result = finite_bath_observables(
        parameters;
        beta,
        tau,
        time_step = 0.02,
        cutoff = 1.0e-14,
        maxdim = 256,
    )
    n_up = real(expect(result.thermal_state.psi, "Nup")[1])
    n_dn = real(expect(result.thermal_state.psi, "Ndn")[1])

    @test result.n_d ≈ 1.0 atol = 1.0e-6
    @test result.G_up[1] ≈ -(1 - n_up) atol = 1.0e-6
    @test result.G_up[2] ≈ -n_up atol = 1.0e-6
    @test result.G_dn[1] ≈ -(1 - n_dn) atol = 1.0e-6
    @test result.G_dn[2] ≈ -n_dn atol = 1.0e-6
    @test all(
        entry -> entry.branch_status == :endpoint_identity,
        vcat(result.diagnostics.green_up, result.diagnostics.green_dn),
    )
    @test all(
        entry -> entry.settings.before_steps == 0 &&
                 entry.settings.after_steps == 0,
        vcat(result.diagnostics.green_up, result.diagnostics.green_dn),
    )
end

@testset "resumable thermal and Green-function workflow" begin
    beta = 0.06
    tau = [beta, 0.02, 0.0, 0.04, 0.02]
    parameters = FiniteBathParameters(
        [0.13], [0.17]; U = 0.61, epsilon_d = -0.27, mu = 0.03
    )
    common = (;
        beta,
        tau,
        time_step = 0.02,
        cutoff = 1.0e-14,
        maxdim = 128,
        krylov_expansion_dim = 0,
    )
    uninterrupted = finite_bath_observables(parameters; common...)
    snapshots = NamedTuple[]
    managed = finite_bath_observables(
        parameters;
        common...,
        checkpoint_manager = (psi, state) ->
            push!(snapshots, (; psi = copy(psi), resume_state = state)),
    )
    assert_observable_equivalence(managed, uninterrupted)
    @test !any(
        snapshot ->
            snapshot.resume_state.cursor.phase === :green &&
            snapshot.resume_state.cursor.segment === :after &&
            snapshot.resume_state.data.tau[
                snapshot.resume_state.cursor.tau_index
            ] in (0.0, beta),
        snapshots,
    )

    selectors = [
        snapshot ->
            snapshot.resume_state.cursor.phase === :thermal &&
            snapshot.resume_state.evolution_state.completed_steps == 1,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :up, :before) &&
            snapshot.resume_state.evolution_state !== nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :up, :after) &&
            snapshot.resume_state.evolution_state === nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :up, :after) &&
            snapshot.resume_state.evolution_state !== nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :dn, :before) &&
            snapshot.resume_state.evolution_state === nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :dn, :before) &&
            snapshot.resume_state.evolution_state !== nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :dn, :after) &&
            snapshot.resume_state.evolution_state === nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :dn, :after) &&
            snapshot.resume_state.evolution_state !== nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 3, :up, :before),
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 1, :up, :before),
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 1, :dn, :before),
    ]
    for selector in selectors
        target = findfirst(selector, snapshots)
        @test target !== nothing
        published = Ref{Any}(nothing)
        seen = Ref(0)
        interruption = try
            finite_bath_observables(
                parameters;
                common...,
                checkpoint_manager = (psi, state) -> begin
                    seen[] += 1
                    published[] = (; psi = copy(psi), resume_state = state)
                end,
                stop_requested = () -> seen[] == target,
            )
            nothing
        catch error
            error
        end
        @test interruption isa ObservableInterrupted
        @test published[] !== nothing
        resumed = finite_bath_observables(
            parameters; common..., resume = published[]
        )
        assert_observable_equivalence(resumed, uninterrupted)
    end
    @test tau[2] == tau[5]
    @test uninterrupted.G_up[2] == uninterrupted.G_up[5]
    @test uninterrupted.G_dn[2] == uninterrupted.G_dn[5]

    inconsistent = snapshots[findfirst(selectors[3], snapshots)]
    bad_state = FiniteBathCheckpoint.ObservableResumeState(
        ObservableCursor(:green, 2, :dn, :after),
        inconsistent.resume_state.evolution_state,
        inconsistent.resume_state.thermal_psi,
        inconsistent.resume_state.data,
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters;
        common...,
        resume = (; psi = inconsistent.psi, resume_state = bad_state),
    )

    thermal_snapshot = only(filter(
        snapshot ->
            snapshot.resume_state.cursor.phase === :thermal &&
            snapshot.resume_state.evolution_state.completed_steps == 1,
        snapshots,
    ))
    missing_thermal_evolution = ObservableResumeState(
        thermal_snapshot.resume_state.cursor,
        nothing,
        nothing,
        thermal_snapshot.resume_state.data,
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters;
        common...,
        resume = (;
            psi = thermal_snapshot.psi,
            resume_state = missing_thermal_evolution,
        ),
    )

    endpoint_before = only(filter(
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 1, :up, :before),
        snapshots,
    ))
    false_endpoint_after = ObservableResumeState(
        ObservableCursor(:green, 1, :up, :after),
        nothing,
        endpoint_before.resume_state.thermal_psi,
        endpoint_before.resume_state.data,
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters;
        common...,
        resume = (; psi = endpoint_before.psi, resume_state = false_endpoint_after),
    )
    endpoint_with_evolution = ObservableResumeState(
        endpoint_before.resume_state.cursor,
        thermal_snapshot.resume_state.evolution_state,
        endpoint_before.resume_state.thermal_psi,
        endpoint_before.resume_state.data,
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters;
        common...,
        resume = (;
            psi = endpoint_before.psi,
            resume_state = endpoint_with_evolution,
        ),
    )
    endpoint_with_operator_claim = ObservableResumeState(
        endpoint_before.resume_state.cursor,
        nothing,
        endpoint_before.resume_state.thermal_psi,
        merge(
            endpoint_before.resume_state.data,
            (; operator_log_norm = 0.0),
        ),
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters;
        common...,
        resume = (;
            psi = endpoint_before.psi,
            resume_state = endpoint_with_operator_claim,
        ),
    )

    interior_before = only(filter(
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :up, :before) &&
            snapshot.resume_state.evolution_state === nothing,
        snapshots,
    ))
    zero_step_evolution = EvolutionResumeState(;
        completed_steps = 0,
        beta_endpoint = 0.0,
        log_unnormalized_norm = 0.0,
        maximum_link_dimensions_by_bond = linkdims(interior_before.psi),
        step_history = NamedTuple[],
        expansion_applied = true,
    )
    before_with_zero_step = ObservableResumeState(
        interior_before.resume_state.cursor,
        zero_step_evolution,
        interior_before.resume_state.thermal_psi,
        interior_before.resume_state.data,
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters;
        common...,
        resume = (;
            psi = interior_before.psi,
            resume_state = before_with_zero_step,
        ),
    )

    complete_snapshot = only(filter(
        snapshot -> snapshot.resume_state.cursor.phase === :complete,
        snapshots,
    ))
    complete_with_evolution = ObservableResumeState(
        complete_snapshot.resume_state.cursor,
        thermal_snapshot.resume_state.evolution_state,
        complete_snapshot.resume_state.thermal_psi,
        complete_snapshot.resume_state.data,
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters;
        common...,
        resume = (;
            psi = complete_snapshot.psi,
            resume_state = complete_with_evolution,
        ),
    )
end

@testset "nonzero Krylov thermal resume preserves complete diagnostics" begin
    beta = 0.04
    tau = [0.01]
    parameters = FiniteBathParameters(
        [0.13], [0.17]; U = 0.61, epsilon_d = -0.27, mu = 0.03
    )
    common = (;
        beta,
        tau,
        time_step = 0.02,
        cutoff = 1.0e-14,
        maxdim = 128,
        krylov_expansion_dim = 2,
    )
    context = build_finite_bath_context(parameters)
    setup_maxima = _thermal_setup_maxima(
        copy_identity_purification(context),
        context.hamiltonian;
        krylov_expansion_dim = common.krylov_expansion_dim,
        cutoff = common.cutoff,
        maxdim = common.maxdim,
    )
    uninterrupted = finite_bath_observables(parameters; common...)
    @test setup_maxima == (
        uninterrupted.thermal_state.diagnostics.initial_max_link_dimension,
        uninterrupted.thermal_state.diagnostics.expanded_max_link_dimension,
    )

    snapshots = NamedTuple[]
    managed = finite_bath_observables(
        parameters;
        common...,
        checkpoint_manager = (psi, state) ->
            push!(snapshots, (; psi = copy(psi), resume_state = state)),
    )
    assert_observable_equivalence(managed, uninterrupted)

    thermal_step = only(filter(
        snapshot ->
            snapshot.resume_state.cursor.phase === :thermal &&
            snapshot.resume_state.evolution_state.completed_steps == 1,
        snapshots,
    ))
    resumed = finite_bath_observables(
        parameters; common..., resume = thermal_step
    )
    assert_observable_equivalence(resumed, uninterrupted)
    @test resumed.diagnostics.maximum_link_dimensions_by_bond ==
          uninterrupted.diagnostics.maximum_link_dimensions_by_bond
    @test resumed.diagnostics.settings == uninterrupted.diagnostics.settings
end

@testset "durable observable checkpoint resumes through Task 3 manager" begin
    beta = 0.02
    tau = [0.01, 0.01]
    parameters =
        FiniteBathParameters([0.1], [0.12]; U = 0.5, epsilon_d = -0.2)
    common = (;
        beta,
        tau,
        time_step = 0.02,
        cutoff = 1.0e-14,
        maxdim = 64,
    )
    uninterrupted = finite_bath_observables(parameters; common...)
    identity = CheckpointIdentity(;
        request_sha256 = repeat("1", 64),
        input_payload_sha256 = repeat("2", 64),
        bath_sha256 = repeat("3", 64),
        solver_settings = Dict("beta" => beta),
        source_hashes = Dict("observables" => repeat("4", 64)),
        project_toml_sha256 = repeat("5", 64),
        manifest_toml_sha256 = repeat("6", 64),
        julia_version = string(VERSION),
        itensors_version = string(Base.pkgversion(ITensors)),
        itensormps_version = string(Base.pkgversion(ITensorMPS)),
        hdf5_version = "0.17.3",
        checkpoint_schema = 1,
        writer_version = "1.0.0",
    )
    mktempdir() do root
        publications = Ref(0)
        interruption = try
            finite_bath_observables(
                parameters;
                common...,
                checkpoint_manager = (psi, state) -> begin
                    publications[] += 1
                    completed_steps =
                        state.evolution_state === nothing ?
                        0 : state.evolution_state.completed_steps
                    write_checkpoint_generation(
                        root,
                        identity,
                        CheckpointCursor(completed_steps),
                        psi,
                        state,
                    )
                end,
                stop_requested = () -> publications[] == 4,
            )
            nothing
        catch error
            error
        end
        @test interruption isa ObservableInterrupted
        loaded = load_current_checkpoint(root, identity)
        resumed = finite_bath_observables(
            parameters; common..., resume = loaded
        )
        assert_observable_equivalence(resumed, uninterrupted)
    end
end

@testset "observable progress remains quiet by default" begin
    parameters =
        FiniteBathParameters([0.0], [0.1]; U = 0.8, epsilon_d = -0.4)
    text = mktemp() do path, output
        redirect_stdout(output) do
            finite_bath_observables(
                parameters;
                beta = 0.02,
                tau = [0.0, 0.005, 0.01, 0.015, 0.02],
                time_step = 0.02,
                cutoff = 1.0e-12,
                maxdim = 64,
            )
        end
        flush(output)
        read(path, String)
    end
    @test isempty(strip(text))
end

@testset "bounded N_b12 reusable context construction" begin
    n_bath = 12
    gamma = 0.1
    bandwidth = 1.0
    epsilon = [
        bandwidth * cos(k * pi / (n_bath + 1)) for k in 1:n_bath
    ]
    coupling = [
        sqrt(
            gamma * bandwidth / (n_bath + 1) *
            sin(k * pi / (n_bath + 1))^2
        ) for k in 1:n_bath
    ]
    parameters = FiniteBathParameters(
        epsilon, coupling; U = 0.8, epsilon_d = -0.4, mu = 0.0
    )

    context = build_finite_bath_context(parameters)

    @test length(context.sites) == 2 * (n_bath + 1)
    @test length(context.identity) == length(context.sites)
    @test length(context.hamiltonian) == length(context.sites)
    @test context.hamiltonian_norm_bound > 0
    @test context.spin_qn_enabled == false
    @test context.reuse_policy ==
          "identity template and immutable MPO may be deep-copied across branches"
end
