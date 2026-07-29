using Test
using LinearAlgebra
using ITensors
using ITensorMPS

include(joinpath(@__DIR__, "validated_chain_fixture.jl"))
using .FiniteBathPurification:
    EvolutionInterrupted,
    EvolutionResumeState,
    FiniteBathParameters,
    MAX_EVOLUTION_STEPS,
    MAX_IMAGINARY_TIME_STEPS,
    MAX_LOCAL_EXPONENT_MAGNITUDE,
    evolve_purification,
    identity_purification,
    interleaved_sites,
    physical_hamiltonian_mpo

@testset "evolution resume state validation" begin
    history = [
        (; beta_endpoint = 0.05, cumulative_log_norm = -0.01),
        (; beta_endpoint = 0.10, cumulative_log_norm = -0.02),
    ]
    state = EvolutionResumeState(
        completed_steps = 2,
        beta_endpoint = 0.1,
        log_unnormalized_norm = -0.02,
        maximum_link_dimensions_by_bond = [4, 8, 4],
        step_history = history,
        expansion_applied = true,
    )

    @test state.completed_steps == 2
    @test state.beta_endpoint == 0.1
    @test state.log_unnormalized_norm == -0.02
    @test state.maximum_link_dimensions_by_bond == [4, 8, 4]
    @test state.step_history == history
    @test state.expansion_applied
    @test_throws ArgumentError EvolutionResumeState(
        completed_steps = -1,
        beta_endpoint = 0.0,
        log_unnormalized_norm = 0.0,
        maximum_link_dimensions_by_bond = Int[],
        step_history = NamedTuple[],
    )
    @test_throws ArgumentError EvolutionResumeState(
        completed_steps = 0,
        beta_endpoint = 0.0,
        log_unnormalized_norm = Inf,
        maximum_link_dimensions_by_bond = Int[],
        step_history = NamedTuple[],
    )
    @test_throws ArgumentError EvolutionResumeState(
        completed_steps = 2,
        beta_endpoint = 0.1,
        log_unnormalized_norm = -0.02,
        maximum_link_dimensions_by_bond = [4, 8, 4],
        step_history = history[1:1],
    )
end

@testset "resume cursor matches the evolution plan" begin
    parameters =
        FiniteBathParameters([0.0], [0.1]; U = 0.8, epsilon_d = -0.4)
    sites, psi = identity_purification(parameters)
    hamiltonian = physical_hamiltonian_mpo(sites, parameters)
    common = (;
        beta = 0.2,
        time_step = 0.05,
        cutoff = 1.0e-12,
        maxdim = 64,
        krylov_expansion_dim = 0,
        hamiltonian_norm_bound =
            FiniteBathPurification._hamiltonian_norm_bound(parameters),
    )
    five_steps = [
        (; beta_endpoint = 0.05 * step, cumulative_log_norm = -0.01 * step)
        for step in 1:5
    ]
    beyond_plan = EvolutionResumeState(
        completed_steps = 5,
        beta_endpoint = 0.25,
        log_unnormalized_norm = -0.05,
        maximum_link_dimensions_by_bond = linkdims(psi),
        step_history = five_steps,
    )
    inconsistent_endpoint = EvolutionResumeState(
        completed_steps = 2,
        beta_endpoint = 0.11,
        log_unnormalized_norm = -0.02,
        maximum_link_dimensions_by_bond = linkdims(psi),
        step_history = five_steps[1:2],
    )

    @test_throws ArgumentError FiniteBathPurification._evolve_normalized_state(
        psi, hamiltonian; common..., resume_state = beyond_plan
    )
    @test_throws ArgumentError FiniteBathPurification._evolve_normalized_state(
        psi, hamiltonian; common..., resume_state = inconsistent_endpoint
    )
end

@testset "interrupted TDVP resumes at a completed step boundary" begin
    parameters =
        FiniteBathParameters([0.0], [0.1]; U = 0.8, epsilon_d = -0.4)
    sites, initial = identity_purification(parameters)
    hamiltonian = physical_hamiltonian_mpo(sites, parameters)
    common = (;
        beta = 0.2,
        time_step = 0.05,
        cutoff = 1.0e-12,
        maxdim = 64,
        krylov_expansion_dim = 2,
        hamiltonian_norm_bound =
            FiniteBathPurification._hamiltonian_norm_bound(parameters),
    )

    full_psi, full_diagnostics =
        FiniteBathPurification._evolve_normalized_state(
            copy(initial), hamiltonian; common...
        )
    callback_states = EvolutionResumeState[]
    interruption = try
        FiniteBathPurification._evolve_normalized_state(
            copy(initial),
            hamiltonian;
            common...,
            step_callback = (psi, state) -> begin
                @test norm(psi) ≈ 1.0 atol = 1.0e-12
                @test length(state.step_history) == state.completed_steps
                @test last(state.step_history).cumulative_log_norm ==
                      state.log_unnormalized_norm
                push!(callback_states, state)
            end,
            stop_requested = () -> length(callback_states) == 2,
        )
        nothing
    catch error
        error
    end

    @test interruption isa EvolutionInterrupted
    @test length(callback_states) == 2
    @test interruption.state == callback_states[end]
    @test interruption.state.completed_steps == 2
    @test interruption.state.beta_endpoint == 0.1
    @test interruption.state.expansion_applied
    resumed_psi, resumed_diagnostics =
        FiniteBathPurification._evolve_normalized_state(
            interruption.psi,
            hamiltonian;
            common...,
            resume_state = interruption.state,
        )

    @test norm(full_psi) ≈ norm(resumed_psi) atol = 1.0e-12
    @test full_diagnostics.log_unnormalized_norm ≈
          resumed_diagnostics.log_unnormalized_norm atol = 1.0e-12
    @test full_diagnostics.maximum_link_dimensions_by_bond ==
          resumed_diagnostics.maximum_link_dimensions_by_bond
    @test linkdims(full_psi) == linkdims(resumed_psi)
    @test full_diagnostics.step_history == resumed_diagnostics.step_history
    @test abs(inner(full_psi, resumed_psi)) ≈ 1.0 atol = 1.0e-11
end

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

function chain_equivalence_fixture(n_bath::Int)
    gamma = 0.13
    bandwidth = 1.2
    epsilon = [
        bandwidth * cos(k * pi / (n_bath + 1)) for k in 1:n_bath
    ]
    coupling = [
        sqrt(
            gamma *
            bandwidth / (n_bath + 1) *
            sin(k * pi / (n_bath + 1))^2,
        ) for k in 1:n_bath
    ]
    return (;
        epsilon,
        coupling,
        chain_onsite = zeros(n_bath),
        chain_hopping = fill(bandwidth / 2, max(0, n_bath - 1)),
        lambda = sqrt(gamma * bandwidth / 2),
    )
end

function geometry_one_particle(parameters)
    n_bath = length(parameters.epsilon)
    matrix = zeros(Float64, n_bath + 1, n_bath + 1)
    matrix[1, 1] = parameters.epsilon_d - parameters.mu
    if parameters.bath_representation === :direct_star
        matrix[2:end, 2:end] =
            Diagonal(parameters.epsilon .- parameters.mu)
        matrix[1, 2:end] = parameters.V
        matrix[2:end, 1] = parameters.V
    elseif parameters.bath_representation === :chain
        matrix[2:end, 2:end] =
            Diagonal(parameters.chain_onsite .- parameters.mu)
        matrix[1, 2] = matrix[2, 1] = parameters.lambda
        for link in eachindex(parameters.chain_hopping)
            matrix[link + 1, link + 2] =
                matrix[link + 2, link + 1] =
                    parameters.chain_hopping[link]
        end
    else
        error("unsupported test geometry")
    end
    return matrix
end

function spinless_sector_matrix(one_particle, particle_count::Int)
    n_orbitals = size(one_particle, 1)
    basis = [
        state for state in 0:((1 << n_orbitals) - 1) if
        count_ones(state) == particle_count
    ]
    positions = Dict(state => index for (index, state) in enumerate(basis))
    matrix = zeros(Float64, length(basis), length(basis))
    for (source_index, source) in enumerate(basis)
        for annihilate in 1:n_orbitals
            annihilate_mask = 1 << (annihilate - 1)
            iszero(source & annihilate_mask) && continue
            intermediate = source ⊻ annihilate_mask
            annihilate_sign =
                isodd(count_ones(source & (annihilate_mask - 1))) ? -1.0 : 1.0
            for create in 1:n_orbitals
                create_mask = 1 << (create - 1)
                iszero(intermediate & create_mask) || continue
                target = intermediate | create_mask
                create_sign =
                    isodd(count_ones(intermediate & (create_mask - 1))) ?
                    -1.0 : 1.0
                matrix[positions[target], source_index] +=
                    one_particle[create, annihilate] *
                    annihilate_sign *
                    create_sign
            end
        end
    end
    return matrix, basis
end

function independent_sector_spectrum(
    parameters, n_up::Int, n_down::Int
)
    one_particle = geometry_one_particle(parameters)
    up_matrix, up_basis = spinless_sector_matrix(one_particle, n_up)
    down_matrix, down_basis = spinless_sector_matrix(one_particle, n_down)
    matrix =
        kron(up_matrix, I(length(down_basis))) +
        kron(I(length(up_basis)), down_matrix)
    for (up_index, up_state) in enumerate(up_basis)
        iszero(up_state & 1) && continue
        for (down_index, down_state) in enumerate(down_basis)
            iszero(down_state & 1) && continue
            index = (up_index - 1) * length(down_basis) + down_index
            matrix[index, index] += parameters.U
        end
    end
    return eigvals(Hermitian(matrix))
end

function occupation_product_mps_basis(sites, n_up::Int, n_down::Int)
    n_orbitals = length(sites) ÷ 2
    up_basis = [
        state for state in 0:((1 << n_orbitals) - 1) if
        count_ones(state) == n_up
    ]
    down_basis = [
        state for state in 0:((1 << n_orbitals) - 1) if
        count_ones(state) == n_down
    ]
    basis = MPS[]
    sizehint!(basis, length(up_basis) * length(down_basis))
    for up_state in up_basis, down_state in down_basis
        labels = fill("Emp", length(sites))
        for orbital in 1:n_orbitals
            mask = 1 << (orbital - 1)
            occupied_up = !iszero(up_state & mask)
            occupied_down = !iszero(down_state & mask)
            labels[2 * orbital - 1] =
                occupied_up ?
                (occupied_down ? "UpDn" : "Up") :
                (occupied_down ? "Dn" : "Emp")
        end
        push!(basis, MPS(sites, labels))
    end
    return basis
end

function production_mpo_sector_matrix(parameters, n_up::Int, n_down::Int)
    sites = interleaved_sites(parameters)
    hamiltonian = physical_hamiltonian_mpo(sites, parameters)
    basis = occupation_product_mps_basis(sites, n_up, n_down)
    matrix = Matrix{ComplexF64}(undef, length(basis), length(basis))
    for source in eachindex(basis), target in eachindex(basis)
        matrix[target, source] =
            inner(basis[target]', hamiltonian, basis[source])
    end
    return matrix
end

function chain_parameters(n_bath::Int; U = 0.8, mu = 0.07)
    validated = validated_chain_fixture(
        ; n_bath, gamma = 0.13, bandwidth = 1.2
    )
    return FiniteBathParameters(
        validated;
        U,
        epsilon_d = -0.31,
        mu,
    )
end

function direct_parameters(n_bath::Int; U = 0.8, mu = 0.07)
    fixture = chain_equivalence_fixture(n_bath)
    return FiniteBathParameters(
        fixture.epsilon,
        fixture.coupling;
        U,
        epsilon_d = -0.31,
        mu,
    )
end

@testset "validated finite chain parameters preserve non-QN defaults" begin
    validated = validated_chain_fixture(; n_bath = 3)
    parameters = FiniteBathParameters(
        validated; U = 0.8, epsilon_d = -0.4, mu = 0.07
    )
    sites = interleaved_sites(parameters)

    @test parameters.bath_representation === :chain
    @test all(!hasqns(site) for site in sites)
    @test length(sites) == 8
    identity_sites, identity = identity_purification(parameters)
    @test length(identity_sites) == 8
    @test all(!hasqns(site) for site in identity_sites)
    @test norm(identity) ≈ 1.0 atol = 1.0e-13
    @test_throws MethodError FiniteBathParameters(
        :chain;
        epsilon = [0.0],
        V = [0.1],
        chain_onsite = [0.0],
        chain_hopping = Float64[],
        lambda = 0.1,
        mapping_sha256 = repeat("a", 64),
    )
end

@testset "purification specification and validated chain capability" begin
    validated = validated_chain_fixture(; n_bath = 1)
    chain = FiniteBathParameters(
        validated; U = 0.8, epsilon_d = -0.4, mu = 0.0
    )
    non_qn = FiniteBathPurification.non_qn_purification()
    qn = FiniteBathPurification.qn_dual_purification(chain, validated)

    @test non_qn.mode === :non_qn
    @test non_qn.qn_gauge === nothing
    @test non_qn.qn_gauge_version === nothing
    @test non_qn.base_sector_nf === nothing
    @test non_qn.base_sector_sz === nothing
    @test qn.mode === :qn_dual
    @test qn.qn_gauge == "electron_nf_sz_ancilla_particle_hole"
    @test qn.qn_gauge_version == 1
    @test (qn.base_sector_nf, qn.base_sector_sz) == (4, 0)
    @test_throws ArgumentError FiniteBathPurification.qn_dual_purification(
        FiniteBathParameters([0.0], [0.1]), validated
    )
    @test !(:ValidatedChainMappingCapability in
            names(FiniteBathPurification))
    @test !(:ChainMappingValidationSeal in names(FiniteBathPurification))
    @test_throws MethodError FiniteBathPurification.ValidatedChainMappingCapability(
        ;
        source_bath_sha256 = repeat("a", 64),
        mapping_sha256 = repeat("b", 64),
        epsilon = [0.0],
        chain_onsite = [0.0],
        chain_hopping = Float64[],
        lambda = 0.1,
    )
end

@testset "validated capability coefficients are immutable snapshots" begin
    validated = validated_chain_fixture(; n_bath = 2)
    epsilon = collect(validated.epsilon)
    onsite = collect(validated.chain_onsite)
    hopping = collect(validated.chain_hopping)

    @test_throws MethodError setindex!(
        validated.epsilon, validated.epsilon[1] + 1, 1
    )
    @test_throws MethodError setindex!(
        validated.chain_onsite, validated.chain_onsite[1] + 1, 1
    )
    @test_throws MethodError setindex!(
        validated.chain_hopping, validated.chain_hopping[1] + 1, 1
    )

    parameters = FiniteBathParameters(validated)
    @test parameters.epsilon == epsilon
    @test parameters.chain_onsite == onsite
    @test parameters.chain_hopping == hopping
    @test FiniteBathPurification.qn_dual_purification(
        parameters, validated
    ).mode === :qn_dual
end

@testset "validated constructors have no positional fabrication bypass" begin
    @test_throws MethodError FiniteBathPurification.ValidatedChainMappingCapability(
        repeat("a", 64),
        repeat("b", 64),
        [0.0],
        [0.0],
        Float64[],
        0.1,
    )
    @test_throws MethodError FiniteBathParameters(
        [0.0],
        [0.1],
        0.8,
        -0.4,
        0.0,
        :chain,
        [0.0],
        Float64[],
        0.1,
        repeat("a", 64),
        repeat("b", 64),
    )
    @test_throws MethodError FiniteBathPurification.PurificationSpec(
        :qn_dual,
        "electron_nf_sz_ancilla_particle_hole",
        1,
        4,
        0,
    )
end

@testset "QN specifications bind every validated parameter" begin
    validated = validated_chain_fixture(; n_bath = 2)
    parameters = FiniteBathParameters(
        validated; U = 0.8, epsilon_d = -0.4, mu = 0.0
    )
    spec =
        FiniteBathPurification.qn_dual_purification(parameters, validated)
    sites = interleaved_sites(parameters; purification = spec)

    changed_before_spec = deepcopy(parameters)
    changed_before_spec.V[1] += 0.125
    @test_throws ArgumentError FiniteBathPurification.qn_dual_purification(
        changed_before_spec, validated
    )

    for field in (:epsilon, :V, :chain_onsite, :chain_hopping)
        changed = deepcopy(parameters)
        values = getfield(changed, field)
        values[1] += 0.125
        @test_throws ArgumentError identity_purification(
            changed; purification = spec
        )
        @test_throws ArgumentError physical_hamiltonian_mpo(
            sites, changed; purification = spec
        )
    end

    for changed_model in (
        FiniteBathParameters(
            validated; U = 0.9, epsilon_d = -0.4, mu = 0.0
        ),
        FiniteBathParameters(
            validated; U = 0.8, epsilon_d = -0.3, mu = 0.0
        ),
        FiniteBathParameters(
            validated; U = 0.8, epsilon_d = -0.4, mu = 0.1
        ),
    )
        @test_throws ArgumentError identity_purification(
            changed_model; purification = spec
        )
        @test_throws ArgumentError physical_hamiltonian_mpo(
            sites, changed_model; purification = spec
        )
    end

    direct = FiniteBathParameters(parameters.epsilon, parameters.V)
    @test_throws ArgumentError identity_purification(
        direct; purification = spec
    )
    @test_throws ArgumentError physical_hamiltonian_mpo(
        sites, direct; purification = spec
    )

    other_validated = validated_chain_fixture(
        ; n_bath = 2, gamma = 0.17, bandwidth = 1.3
    )
    other_parameters = FiniteBathParameters(other_validated)
    other_spec = FiniteBathPurification.qn_dual_purification(
        other_parameters, other_validated
    )
    @test other_parameters.lambda != parameters.lambda
    @test other_parameters.mapping_sha256 != parameters.mapping_sha256
    other_sites =
        interleaved_sites(other_parameters; purification = other_spec)
    @test_throws ArgumentError identity_purification(
        parameters; purification = other_spec
    )
    @test_throws ArgumentError identity_purification(
        other_parameters; purification = spec
    )
    @test_throws ArgumentError physical_hamiltonian_mpo(
        other_sites, other_parameters; purification = spec
    )

    qn_hamiltonian = physical_hamiltonian_mpo(
        sites, parameters; purification = spec
    )
    @test length(qn_hamiltonian) == length(sites)
end

@testset "QN Electron labels and complementary dual identity" begin
    validated = validated_chain_fixture(; n_bath = 1)
    chain = FiniteBathParameters(validated)
    spec = FiniteBathPurification.qn_dual_purification(chain, validated)
    sites = interleaved_sites(chain; purification = spec)
    identity_sites, psi =
        identity_purification(chain; purification = spec)

    @test length(sites) == length(identity_sites)
    @test space.(sites) == space.(identity_sites)
    @test all(hasqns, sites)
    @test all(
        site -> !occursin("NfParity", sprint(show, space(site))),
        sites,
    )
    expected_qns = Dict(
        "Emp" => QN(("Nf", 0, -1), ("Sz", 0)),
        "Up" => QN(("Nf", 1, -1), ("Sz", 1)),
        "Dn" => QN(("Nf", 1, -1), ("Sz", -1)),
        "UpDn" => QN(("Nf", 2, -1), ("Sz", 0)),
    )
    for site in sites, (label, expected) in expected_qns
        @test flux(state(site, label)) == expected
    end

    pair = psi[1] * psi[2]
    pair *= onehot(dag(linkind(psi, 2)) => 1)
    @test flux(pair) == QN(("Nf", 2, -1), ("Sz", 0))
    A = [
        pair[identity_sites[1] => physical, identity_sites[2] => ancilla]
        for physical in 1:4, ancilla in 1:4
    ]
    expected = [
        0.0 0.0 0.0 0.5
        0.0 0.0 0.5 0.0
        0.0 0.5 0.0 0.0
        0.5 0.0 0.0 0.0
    ]
    @test A == expected
    for physical in 1:4, ancilla in 1:4
        target = physical + ancilla == 5 ? 0.5 : 0.0
        @test A[physical, ancilla] == target
    end
    @test A * A' ≈ Matrix{Float64}(I, 4, 4) / 4 atol = 1.0e-15
    @test norm(psi) ≈ 1.0 atol = 1.0e-15
    @test flux(psi) == QN(("Nf", 4, -1), ("Sz", 0))
    terms = [
        ("Emp", "UpDn", 0 + 2, 0 + 0),
        ("Up", "Dn", 1 + 1, 1 - 1),
        ("Dn", "Up", 1 + 1, -1 + 1),
        ("UpDn", "Emp", 2 + 0, 0 + 0),
    ]
    @test all(term -> term[3] == 2 && term[4] == 0, terms)

    larger_validated = validated_chain_fixture(; n_bath = 2)
    larger = FiniteBathParameters(larger_validated)
    larger_spec =
        FiniteBathPurification.qn_dual_purification(larger, larger_validated)
    _, larger_psi =
        identity_purification(larger; purification = larger_spec)
    @test flux(larger_psi) == QN(("Nf", 6, -1), ("Sz", 0))
end

@testset "direct star constructor remains backward compatible" begin
    parameters =
        FiniteBathParameters([-0.4, 0.2], [0.31, 0.17]; mu = 0.07)
    @test parameters.bath_representation === :direct_star
    @test parameters.chain_onsite == parameters.epsilon
    @test parameters.chain_hopping == [0.0]
    @test parameters.lambda ≈ norm(parameters.V)
    @test parameters.mapping_sha256 === nothing
end

@testset "chain MPO has physical fermion signs on every link and spin" begin
    parameters = chain_parameters(3)
    sites = interleaved_sites(parameters)
    hamiltonian = physical_hamiltonian_mpo(sites, parameters)
    links = [
        (1, 3, parameters.lambda),
        (3, 5, parameters.chain_hopping[1]),
        (5, 7, parameters.chain_hopping[2]),
    ]
    for (left, right, coefficient) in links
        for (spin, state) in (("up", "Up"), ("dn", "Dn"))
            for (parity_state, expected) in
                (("Emp", coefficient), ("Up", -coefficient))
                elements = ComplexF64[]
                for (source_site, target_site) in
                    ((right, left), (left, right))
                    source = fill("Emp", length(sites))
                    target = fill("Emp", length(sites))
                    source[source_site] = state
                    target[target_site] = state
                    source[left + 1] = parity_state
                    target[left + 1] = parity_state
                    element = inner(
                        MPS(sites, target)',
                        hamiltonian,
                        MPS(sites, source),
                    )
                    push!(elements, element)
                    @test element ≈ expected atol = 1.0e-14
                end
                @test elements[1] ≈ conj(elements[2]) atol = 1.0e-14
            end
        end
    end
end

@testset "chain norm bound uses only selected unshifted geometry" begin
    parameters = chain_parameters(3; U = 0.8, mu = 0.07)
    expected =
        2 * abs(parameters.epsilon_d - parameters.mu) +
        parameters.U +
        2 * sum(abs.(parameters.chain_onsite .- parameters.mu)) +
        4 * (parameters.lambda + sum(parameters.chain_hopping))
    @test FiniteBathPurification._hamiltonian_norm_bound(parameters) ≈
          expected atol = 0.0
end

@testset "production chain MPO one-up one-down spectra match direct star" begin
    for n_bath in 1:6, interaction in (0.0, 0.8)
        direct = direct_parameters(n_bath; U = interaction)
        chain = chain_parameters(n_bath; U = interaction)
        matrix = production_mpo_sector_matrix(chain, 1, 1)
        @test ishermitian(matrix)
        @test eigvals(Hermitian(matrix)) ≈
              independent_sector_spectrum(direct, 1, 1) atol = 8.0e-12
    end
end

@testset "production chain MPO spectra and Hermiticity in every small sector" begin
    for n_bath in 1:3, interaction in (0.0, 0.8)
        direct = direct_parameters(n_bath; U = interaction)
        chain = chain_parameters(n_bath; U = interaction)
        for n_up in 0:(n_bath + 1), n_down in 0:(n_bath + 1)
            (n_up, n_down) == (1, 1) && continue
            matrix = production_mpo_sector_matrix(chain, n_up, n_down)
            @test ishermitian(matrix)
            @test eigvals(Hermitian(matrix)) ≈
                  independent_sector_spectrum(direct, n_up, n_down) atol =
                8.0e-12
        end
    end
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
