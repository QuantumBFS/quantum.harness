using Test
using LinearAlgebra
using JSON3
using ITensors
using ITensorMPS

include(joinpath(@__DIR__, "validated_chain_fixture.jl"))
using .FiniteBathPurification:
    FiniteBathParameters,
    identity_purification,
    non_qn_purification,
    qn_dual_purification

isdefined(Main, :FiniteBathObservables) ||
    include(joinpath(@__DIR__, "..", "finite_bath_observables.jl"))
using .FiniteBathObservables:
    AppliedOperatorBranch,
    ObservableCursor,
    ObservableInterrupted,
    OperatorSector,
    _thermal_setup_maxima,
    build_finite_bath_context,
    copy_identity_purification,
    finite_bath_observables,
    impurity_green_function,
    operator_sector
using .FiniteBathCheckpoint:
    CheckpointCursor,
    CheckpointIdentity,
    EvolutionResumeState,
    ObservableResumeState,
    load_current_checkpoint,
    write_checkpoint_generation

const QN_TASK4_MAX_BATH =
    parse(Int, get(ENV, "QN_TASK4_MAX_BATH", "2"))
QN_TASK4_MAX_BATH in 1:6 ||
    error("QN_TASK4_MAX_BATH must be between 1 and 6")

@testset "Green operators carry explicit QN sectors" begin
    validated = validated_chain_fixture(; n_bath = 2)
    parameters = FiniteBathParameters(validated)
    purification = qn_dual_purification(parameters, validated)
    context =
        build_finite_bath_context(parameters; purification)

    expected = (
        (:creation, :up, 7, 1),
        (:creation, :dn, 7, -1),
        (:annihilation, :up, 5, -1),
        (:annihilation, :dn, 5, 1),
    )
    @test_throws ArgumentError OperatorSector(
        :creation, :up, 7, -1
    )
    for (insertion, spin, nf, sz) in expected
        sector = operator_sector(purification, insertion, spin)
        @test sector == OperatorSector(insertion, spin, nf, sz)
        branch = FiniteBathObservables._apply_impurity_operator(
            context.identity,
            context.sites[1],
            spin,
            insertion,
            sector,
        )
        @test branch isa AppliedOperatorBranch
        @test branch.status === :finite
        @test branch.expected_sector == sector
        @test flux(branch.psi) == QN(("Nf", nf, -1), ("Sz", sz))
    end
    @test_throws ArgumentError FiniteBathObservables._apply_impurity_operator(
        context.identity,
        context.sites[1],
        :up,
        :creation,
        nothing,
    )

    qn_blocked = MPS(
        context.sites,
        ["Up", "Dn", "Emp", "UpDn", "Emp", "UpDn"],
    )
    blocked_sector = operator_sector(purification, :creation, :up)
    qn_zero = FiniteBathObservables._apply_impurity_operator(
        qn_blocked,
        context.sites[1],
        :up,
        :creation,
        blocked_sector,
    )
    @test qn_zero.status === :zero
    @test qn_zero.psi === nothing
    @test qn_zero.log_norm == -Inf
    @test qn_zero.expected_sector == blocked_sector
    terminal_state = ObservableResumeState(
        ObservableCursor(
            :green, 1, :up, :creation, :terminal
        ),
        nothing,
        qn_blocked,
        (;
            branch_status = :zero,
            expected_sector = blocked_sector,
        ),
    )
    resumed_active, resumed_state =
        FiniteBathObservables._resume_parts(
            ObservableInterrupted(nothing, terminal_state)
        )
    @test resumed_active === nothing
    @test resumed_state === terminal_state
    @test FiniteBathObservables._validate_resume_sectors(
        context, terminal_state, nothing
    ) === nothing
    forged_terminal = ObservableResumeState(
        terminal_state.cursor,
        nothing,
        qn_blocked,
        merge(
            terminal_state.data,
            (;
                expected_sector =
                    operator_sector(purification, :creation, :dn),
            ),
        ),
    )
    @test_throws ArgumentError FiniteBathObservables._validate_resume_sectors(
        context, forged_terminal, nothing
    )

    direct = FiniteBathParameters(parameters.epsilon, parameters.V)
    direct_context = build_finite_bath_context(direct)
    direct_sites = direct_context.sites
    non_qn_blocked = MPS(
        direct_sites,
        ["Up", "Emp", "Emp", "Emp", "Emp", "Emp"],
    )
    non_qn_zero = FiniteBathObservables._apply_impurity_operator(
        non_qn_blocked,
        direct_sites[1],
        :up,
        :creation,
        nothing,
    )
    @test non_qn_zero.status === :zero
    @test non_qn_zero.psi === nothing
    @test non_qn_zero.expected_sector === nothing
    direct_terminal = ObservableResumeState(
        ObservableCursor(
            :green, 1, :up, :creation, :terminal
        ),
        nothing,
        direct_context.identity,
        (; branch_status = :zero, expected_sector = nothing),
    )
    @test FiniteBathObservables._validate_resume_sectors(
        direct_context, direct_terminal, nothing
    ) === nothing
    forged_direct_terminal = ObservableResumeState(
        direct_terminal.cursor,
        nothing,
        direct_terminal.thermal_psi,
        merge(
            direct_terminal.data,
            (; expected_sector = blocked_sector),
        ),
    )
    @test_throws ArgumentError FiniteBathObservables._validate_resume_sectors(
        direct_context, forged_direct_terminal, nothing
    )
    @test_throws ArgumentError FiniteBathObservables._apply_impurity_operator(
        non_qn_blocked,
        direct_sites[1],
        :up,
        :creation,
        blocked_sector,
    )
end

@testset "creation and annihilation Green forms are explicit" begin
    validated = validated_chain_fixture(; n_bath = 1)
    parameters = FiniteBathParameters(validated)
    purification = qn_dual_purification(parameters, validated)
    common = (;
        beta = 0.04,
        tau = [0.01, 0.03],
        purification,
        time_step = 0.02,
        cutoff = 1.0e-12,
        maxdim = 32,
    )
    creation = finite_bath_observables(
        parameters; common..., green_insertion = :creation
    )
    annihilation = finite_bath_observables(
        parameters; common..., green_insertion = :annihilation
    )
    @test creation.G_up ≈ annihilation.G_up atol = 1.0e-10
    @test creation.G_dn ≈ annihilation.G_dn atol = 1.0e-10
    @test all(
        diagnostic.insertion === :creation &&
        diagnostic.operator_sector.insertion === :creation
        for diagnostic in creation.diagnostics.green_up
    )
    @test all(
        diagnostic.insertion === :annihilation &&
        diagnostic.operator_sector.insertion === :annihilation
        for diagnostic in annihilation.diagnostics.green_up
    )
    @test_throws ArgumentError finite_bath_observables(
        parameters; common..., green_insertion = :sideways
    )

    context =
        build_finite_bath_context(parameters; purification)
    identity = CheckpointIdentity(;
        request_sha256 = repeat("1", 64),
        input_payload_sha256 = repeat("2", 64),
        bath_sha256 = validated.source_bath_sha256,
        bath_representation = "chain",
        chain_mapping_sha256 = validated.mapping_sha256,
        solver_settings = Dict("beta" => common.beta),
        source_hashes = Dict("observables" => repeat("3", 64)),
        project_toml_sha256 = repeat("4", 64),
        manifest_toml_sha256 = repeat("5", 64),
        julia_version = string(VERSION),
        itensors_version = string(Base.pkgversion(ITensors)),
        itensormps_version = string(Base.pkgversion(ITensorMPS)),
        hdf5_version = "0.17.3",
        checkpoint_schema = 1,
        writer_version = "1.0.0",
    )
    for insertion in (:creation, :annihilation)
        expected = operator_sector(purification, insertion, :up)
        branch = FiniteBathObservables._apply_impurity_operator(
            context.identity,
            context.sites[1],
            :up,
            insertion,
            expected,
        )
        state = ObservableResumeState(
            ObservableCursor(
                :green, 1, :up, insertion, :after
            ),
            nothing,
            context.identity,
            (;
                branch_status = :finite,
                expected_sector = expected,
            ),
        )
        mktempdir() do root
            write_checkpoint_generation(
                root,
                identity,
                CheckpointCursor(0),
                branch.psi,
                state;
                purification,
            )
            loaded = load_current_checkpoint(
                root, identity; purification
            )
            @test loaded.resume_state.cursor.insertion === insertion
            @test loaded.resume_state.data.expected_sector == expected
            @test flux(loaded.psi) ==
                  QN(("Nf", expected.nf, -1), ("Sz", expected.sz))
            @test siteinds(loaded.psi) == siteinds(branch.psi)
        end
    end
end

@testset "non-QN zero terminal resumes through public HDF5 path" begin
    parameters = FiniteBathParameters(
        [0.0], [0.2]; U = 0.8, epsilon_d = -0.4, mu = 0.0
    )
    common = (;
        beta = 0.04,
        tau = [0.02],
        green_insertion = :creation,
        time_step = 0.02,
        cutoff = 1.0e-12,
        maxdim = 32,
    )
    identity = CheckpointIdentity(;
        request_sha256 = repeat("1", 64),
        input_payload_sha256 = repeat("2", 64),
        bath_sha256 = repeat("3", 64),
        solver_settings = Dict("beta" => common.beta),
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
    mktempdir() do before_root
        before_written = Ref(false)
        interruption = try
            finite_bath_observables(
                parameters;
                common...,
                checkpoint_manager = (psi, state) -> begin
                    completed_steps =
                        state.evolution_state === nothing ?
                        0 :
                        state.evolution_state.completed_steps
                    write_checkpoint_generation(
                        before_root,
                        identity,
                        CheckpointCursor(completed_steps),
                        psi,
                        state,
                    )
                    cursor = state.cursor
                    before_written[] =
                        cursor.phase === :green &&
                        cursor.tau_index == 1 &&
                        cursor.spin === :up &&
                        cursor.segment === :before &&
                        state.evolution_state !== nothing &&
                        state.evolution_state.completed_steps == 1
                end,
                stop_requested = () -> before_written[],
            )
            nothing
        catch error
            error
        end
        @test interruption isa ObservableInterrupted
        before_loaded =
            load_current_checkpoint(before_root, identity)
        blocked = MPS(
            siteinds(before_loaded.psi),
            ["Up", "Emp", "Emp", "Emp"],
        )

        mktempdir() do terminal_root
            terminal_written = Ref(false)
            terminal_interruption = try
                finite_bath_observables(
                    parameters;
                    common...,
                    resume = (;
                        psi = blocked,
                        resume_state = before_loaded.resume_state,
                    ),
                    checkpoint_manager = (psi, state) -> begin
                        completed_steps =
                            state.evolution_state === nothing ?
                            0 :
                            state.evolution_state.completed_steps
                        write_checkpoint_generation(
                            terminal_root,
                            identity,
                            CheckpointCursor(completed_steps),
                            psi,
                            state,
                        )
                        terminal_written[] =
                            state.cursor.segment === :terminal
                    end,
                    stop_requested = () -> terminal_written[],
                )
                nothing
            catch error
                error
            end
            @test terminal_interruption isa ObservableInterrupted
            @test terminal_interruption.psi === nothing
            terminal_loaded =
                load_current_checkpoint(terminal_root, identity)
            @test terminal_loaded.psi === nothing
            @test terminal_loaded.resume_state.cursor.segment === :terminal
            @test terminal_loaded.resume_state.data.branch_status === :zero
            @test terminal_loaded.resume_state.data.expected_sector === nothing

            result = finite_bath_observables(
                parameters; common..., resume = terminal_loaded
            )
            @test result.G_up[1] == -0.0
            @test result.diagnostics.green_up[1].settings.after_steps == 0
        end
    end
end

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
    logZ = -beta * minimum(eig.values) + log(scaled_Z)
    return (;
        logZ,
        n_up,
        n_dn,
        n_d = n_up + n_dn,
        double_occupancy,
        green,
    )
end

function independent_noninteracting_trace(parameters, beta, tau)
    n_orbitals = length(parameters.epsilon) + 1
    one_particle = diagm(
        [parameters.epsilon_d - parameters.mu; parameters.epsilon .- parameters.mu]
    )
    one_particle[1, 2:end] = parameters.V
    one_particle[2:end, 1] = parameters.V
    eig = eigen(Hermitian(one_particle))
    occupations = 1.0 ./ (1.0 .+ exp.(beta .* eig.values))
    density = eig.vectors * Diagonal(occupations) * eig.vectors'
    n_spin = real(density[1, 1])
    green = [
        -real(
            (
                eig.vectors *
                Diagonal(exp.(-point .* eig.values) .* (1 .- occupations)) *
                eig.vectors'
            )[1, 1],
        ) for point in tau
    ]
    return (;
        logZ = 2 * sum(
            max(0.0, -beta * value) +
            log1p(exp(-abs(beta * value))) for value in eig.values
        ),
        n_up = n_spin,
        n_dn = n_spin,
        n_d = 2 * n_spin,
        double_occupancy = n_spin^2,
        green = Dict(:up => green, :dn => green),
    )
end

function assert_task4_scientific_equivalence(actual, expected; atol)
    @test actual.diagnostics.log_partition ≈ expected.logZ atol = atol
    @test actual.n_d ≈ expected.n_d atol = atol
    @test actual.double_occupancy ≈ expected.double_occupancy atol = atol
    @test maximum(abs.(actual.G_up .- expected.green[:up]); init = 0.0) <=
          atol
    @test maximum(abs.(actual.G_dn .- expected.green[:dn]); init = 0.0) <=
          atol
    @test actual.G_up[1] ≈ -(1 - expected.n_up) atol = atol
    @test actual.G_up[end] ≈ -expected.n_up atol = atol
    @test actual.G_dn[1] ≈ -(1 - expected.n_dn) atol = atol
    @test actual.G_dn[end] ≈ -expected.n_dn atol = atol
end

function resume_task4_qn_branch(parameters, purification, settings)
    published = Ref{Any}(nothing)
    target_written = Ref(false)
    target_tau_index =
        settings.green_insertion === :creation ? 4 : 2
    target_cursor = ObservableCursor(
        :green,
        target_tau_index,
        :up,
        settings.green_insertion,
        :after,
    )
    interruption = try
        finite_bath_observables(
            parameters;
            settings...,
            purification,
            checkpoint_manager = (psi, state) -> begin
                if state.cursor == target_cursor &&
                   state.evolution_state !== nothing &&
                   state.evolution_state.completed_steps == 1
                    published[] = (;
                        psi = copy(psi),
                        resume_state = state,
                    )
                    target_written[] = true
                end
            end,
            stop_requested = () -> target_written[],
        )
        nothing
    catch error
        error
    end
    @test interruption isa ObservableInterrupted
    @test target_written[]
    @test published[] !== nothing
    @test published[].resume_state.cursor == target_cursor
    @test published[].resume_state.evolution_state.completed_steps == 1
    base_nf = 2 * (length(parameters.epsilon) + 1)
    expected_nf =
        base_nf + (settings.green_insertion === :creation ? 1 : -1)
    expected_sz = settings.green_insertion === :creation ? 1 : -1
    @test flux(published[].psi) ==
          QN(("Nf", expected_nf, -1), ("Sz", expected_sz))

    resumed_publications = NamedTuple[]
    resumed = finite_bath_observables(
        parameters;
        settings...,
        purification,
        resume = published[],
        checkpoint_manager = (_, state) -> begin
            completed_steps =
                state.evolution_state === nothing ?
                0 :
                state.evolution_state.completed_steps
            push!(
                resumed_publications,
                (; cursor = state.cursor, completed_steps),
            )
        end,
    )
    target_tau = settings.tau[target_tau_index]
    after_duration =
        settings.green_insertion === :creation ?
        target_tau :
        settings.beta - target_tau
    expected_after_steps =
        ceil(Int, after_duration / settings.time_step)
    @test resumed.diagnostics.green_up[
        target_tau_index
    ].settings.after_steps == expected_after_steps
    resumed_target_steps = [
        publication.completed_steps
        for publication in resumed_publications
        if publication.cursor == target_cursor
    ]
    @test resumed_target_steps == collect(2:expected_after_steps)
    @test !any(
        publication ->
            publication.cursor.phase === :green &&
            publication.cursor.tau_index == target_tau_index &&
            publication.cursor.spin === :up &&
            publication.cursor.insertion === settings.green_insertion &&
            publication.cursor.segment === :before,
        resumed_publications,
    )
    return resumed
end

function run_qn_observable_equivalence_matrix(max_bath::Int)
    beta = 0.04
    tau = [0.0, beta / 4, beta / 2, 3 * beta / 4, beta]
    base_settings = (;
        beta,
        tau,
        time_step = 0.01,
        cutoff = 1.0e-14,
        maxdim = 256,
        krylov_expansion_dim = 32,
    )
    for n_bath in 1:max_bath
        artifacts = validated_chain_fixture_artifacts(n_bath)
        validated = validate_chain_mapping_artifact(
            artifacts.mapping_artifact,
            artifacts.mapping_json,
            artifacts.bath_artifact,
        )
        bath_payload = artifacts.bath_artifact["payload"]
        epsilon = Float64.(bath_payload["epsilon"])
        coupling = Float64.(bath_payload["V"])
        for interaction in (0.0, 0.8)
            interaction != 0.0 && n_bath > 3 && continue
            common = (;
                U = interaction,
                epsilon_d = -0.31,
                mu = 0.07,
            )
            direct = FiniteBathParameters(
                epsilon, coupling; common...
            )
            chain = FiniteBathParameters(validated; common...)
            purification = qn_dual_purification(chain, validated)
            exact =
                interaction == 0.0 ?
                independent_noninteracting_trace(direct, beta, tau) :
                independent_observables_trace(direct, beta, tau)

            direct_result =
                finite_bath_observables(direct; base_settings...)
            chain_result =
                finite_bath_observables(chain; base_settings...)
            qn_results = Dict(
                insertion => finite_bath_observables(
                    chain;
                    base_settings...,
                    purification,
                    green_insertion = insertion,
                ) for insertion in (:creation, :annihilation)
            )

            for result in
                (direct_result, chain_result, qn_results[:creation], qn_results[:annihilation])
                assert_task4_scientific_equivalence(result, exact; atol = 1.0e-6)
            end
            assert_star_chain_observables(
                chain_result, direct_result; atol = 1.0e-6
            )
            for insertion in (:creation, :annihilation)
                owned_site =
                    qn_results[insertion].thermal_state.sites[1]
                mismatched_site =
                    build_finite_bath_context(
                        chain; purification
                    ).sites[1]
                @test mismatched_site !== owned_site
                @test !hasind(
                    qn_results[insertion].thermal_state.psi[1],
                    mismatched_site,
                )
                @test hasind(
                    qn_results[insertion].thermal_state.psi[1],
                    owned_site,
                )
                assert_star_chain_observables(
                    qn_results[insertion], direct_result; atol = 1.0e-6
                )
                @test qn_results[insertion].provenance.purification_mode ===
                      :qn_dual
                @test qn_results[insertion].provenance.bath_representation ===
                      :chain
                @test qn_results[insertion].provenance.chain_mapping_sha256 ==
                      validated.mapping_sha256
                for spin_diagnostics in (
                    qn_results[insertion].diagnostics.green_up,
                    qn_results[insertion].diagnostics.green_dn,
                )
                    @test spin_diagnostics[1].operator_sector === nothing
                    @test spin_diagnostics[end].operator_sector === nothing
                    @test all(
                        point.operator_sector !== nothing &&
                        point.operator_sector.insertion === insertion
                        for point in spin_diagnostics[2:(end - 1)]
                    )
                end
                base_nf = 2 * (n_bath + 1)
                for (spin, expected_nf, expected_sz) in (
                    (
                        :up,
                        base_nf + (insertion === :creation ? 1 : -1),
                        insertion === :creation ? 1 : -1,
                    ),
                    (
                        :dn,
                        base_nf + (insertion === :creation ? 1 : -1),
                        insertion === :creation ? -1 : 1,
                    ),
                )
                    diagnostics =
                        spin === :up ?
                        qn_results[insertion].diagnostics.green_up :
                        qn_results[insertion].diagnostics.green_dn
                    @test all(
                        point.operator_sector.insertion === insertion &&
                        point.operator_sector.spin === spin &&
                        point.operator_sector.nf == expected_nf &&
                        point.operator_sector.sz == expected_sz
                        for point in diagnostics[2:(end - 1)]
                    )
                    explicit_sector = OperatorSector(
                        insertion,
                        spin,
                        expected_nf,
                        expected_sz,
                    )
                    applied =
                        FiniteBathObservables._apply_impurity_operator(
                            qn_results[insertion].thermal_state.psi,
                            owned_site,
                            spin,
                            insertion,
                            explicit_sector,
                        )
                    @test applied.status === :finite
                    @test flux(applied.psi) ==
                          QN(
                        ("Nf", expected_nf, -1),
                        ("Sz", expected_sz),
                    )
                end
            end
            @test qn_results[:creation].G_up ≈
                  qn_results[:annihilation].G_up atol = 1.0e-6
            @test qn_results[:creation].G_dn ≈
                  qn_results[:annihilation].G_dn atol = 1.0e-6
            @test flux(qn_results[:creation].thermal_state.psi) ==
                  QN(
                ("Nf", purification.base_sector_nf, -1),
                ("Sz", purification.base_sector_sz),
            )
            @test qn_results[:creation].diagnostics.log_partition ≈
                  (n_bath + 1) * log(4.0) +
                  2 *
                  qn_results[:creation].thermal_state.diagnostics.log_unnormalized_norm atol =
                5.0e-13
            @test direct_result.provenance.purification_mode === :non_qn
            @test chain_result.provenance.purification_mode === :non_qn
            @test direct_result.provenance.chain_mapping_sha256 === nothing
            @test chain_result.provenance.chain_mapping_sha256 ==
                  validated.mapping_sha256

            if interaction == (n_bath <= 3 ? 0.8 : 0.0)
                for insertion in (:creation, :annihilation)
                    settings = merge(
                        base_settings, (; green_insertion = insertion)
                    )
                    resumed = resume_task4_qn_branch(
                        chain, purification, settings
                    )
                    assert_task4_scientific_equivalence(
                        resumed, exact; atol = 1.0e-6
                    )
                    @test resumed.G_up ≈
                          qn_results[insertion].G_up atol = 1.0e-10
                    @test resumed.G_dn ≈
                          qn_results[insertion].G_dn atol = 1.0e-10
                end
            end
        end
    end
end

function validated_observable_chain_fixtures()
    gamma = 0.1
    bandwidth = 1.0
    return [
        (;
            n_bath,
            epsilon = [
                bandwidth * cos(k * pi / (n_bath + 1))
                for k in 1:n_bath
            ],
            coupling = [
                sqrt(
                    gamma * bandwidth / (n_bath + 1) *
                    sin(k * pi / (n_bath + 1))^2
                ) for k in 1:n_bath
            ],
            validated = validated_chain_fixture(; n_bath),
        ) for n_bath in 1:QN_TASK4_MAX_BATH
    ]
end

function mapped_observable_parameters(fixture)
    common = (; U = 0.8, epsilon_d = -0.4, mu = 0.0)
    direct =
        FiniteBathParameters(fixture.epsilon, fixture.coupling; common...)
    chain = FiniteBathParameters(fixture.validated; common...)
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

@testset "one-physical-orbital dense normalization" begin
    n_bath = 0
    physical_orbitals = n_bath + 1
    beta = 0.73
    interaction = 0.8
    epsilon_d = -0.31
    chemical_potential = 0.07
    energies = [
        0.0,
        epsilon_d - chemical_potential,
        epsilon_d - chemical_potential,
        2 * (epsilon_d - chemical_potential) + interaction,
    ]
    dense_hamiltonian = Diagonal(energies)
    dense_log_partition = log(real(tr(exp(-beta * dense_hamiltonian))))
    normalized_identity = fill(0.5, 4)
    evolved = exp(-beta * dense_hamiltonian / 2) * normalized_identity
    purification_log_partition =
        physical_orbitals * log(4.0) + 2 * log(norm(evolved))

    @test physical_orbitals == 1
    @test norm(normalized_identity) == 1.0
    @test purification_log_partition ≈ dense_log_partition atol = 5.0e-14
end

@testset "QN chain thermal and observable equivalence matrix" begin
    run_qn_observable_equivalence_matrix(QN_TASK4_MAX_BATH)
end

const CHAIN_FIXTURES = validated_observable_chain_fixtures()

@testset "geometry diagnostics preserve mapped spin convention without QNs" begin
    fixture = CHAIN_FIXTURES[2]
    direct, chain = mapped_observable_parameters(fixture)
    direct_context = build_finite_bath_context(direct)
    chain_context = build_finite_bath_context(chain)

    @test direct_context.bath_representation === :direct_star
    @test chain_context.bath_representation === :chain
    @test direct_context.chain_mapping_sha256 === nothing
    @test chain_context.chain_mapping_sha256 ==
          fixture.validated.mapping_sha256
    @test direct_context.spin_qn_enabled == false
    @test chain_context.spin_qn_enabled == false
    @test direct_context.spin_transform == chain_context.spin_transform
end

@testset "direct star and mapped finite chain MPS observables agree through selected N_b" begin
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
            fixture.validated.mapping_sha256,
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
            ObservableCursor(:green, 2, :up, :creation, :before) &&
            snapshot.resume_state.evolution_state !== nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :up, :creation, :after) &&
            snapshot.resume_state.evolution_state === nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :up, :creation, :after) &&
            snapshot.resume_state.evolution_state !== nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :dn, :creation, :before) &&
            snapshot.resume_state.evolution_state === nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :dn, :creation, :before) &&
            snapshot.resume_state.evolution_state !== nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :dn, :creation, :after) &&
            snapshot.resume_state.evolution_state === nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 2, :dn, :creation, :after) &&
            snapshot.resume_state.evolution_state !== nothing,
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 3, :up, :creation, :before),
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 1, :up, :creation, :before),
        snapshot ->
            snapshot.resume_state.cursor ==
            ObservableCursor(:green, 1, :dn, :creation, :before),
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
        ObservableCursor(:green, 2, :dn, :creation, :after),
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
            ObservableCursor(:green, 1, :up, :creation, :before),
        snapshots,
    ))
    false_endpoint_after = ObservableResumeState(
        ObservableCursor(:green, 1, :up, :creation, :after),
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
            ObservableCursor(:green, 2, :up, :creation, :before) &&
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

function phase_aligned_mps_error(reference, candidate)
    overlap = inner(reference, candidate)
    abs(overlap) > eps(Float64) || return Inf
    aligned = copy(candidate)
    aligned[1] *= conj(overlap / abs(overlap))
    return norm(aligned - reference)
end

@testset "QN shifted branches resume from genuine HDF5 interruptions" begin
    validated = validated_chain_fixture(; n_bath = 1)
    parameters = FiniteBathParameters(
        validated; U = 0.8, epsilon_d = -0.4, mu = 0.0
    )
    purification = qn_dual_purification(parameters, validated)
    for insertion in (:creation, :annihilation)
        common = (;
            beta = 0.04,
            tau = [0.02],
            purification,
            green_insertion = insertion,
            time_step = 0.02,
            cutoff = 1.0e-12,
            maxdim = 32,
        )
        uninterrupted = finite_bath_observables(parameters; common...)
        identity = CheckpointIdentity(;
            request_sha256 = repeat("1", 64),
            input_payload_sha256 = repeat("2", 64),
            bath_sha256 = validated.source_bath_sha256,
            bath_representation = "chain",
            chain_mapping_sha256 = validated.mapping_sha256,
            solver_settings = Dict(
                "beta" => common.beta,
                "green_insertion" => String(insertion),
            ),
            source_hashes = Dict(
                "observables" => repeat("3", 64)
            ),
            project_toml_sha256 = repeat("4", 64),
            manifest_toml_sha256 = repeat("5", 64),
            julia_version = string(VERSION),
            itensors_version = string(Base.pkgversion(ITensors)),
            itensormps_version = string(Base.pkgversion(ITensorMPS)),
            hdf5_version = "0.17.3",
            checkpoint_schema = 1,
            writer_version = "1.0.0",
        )
        mktempdir() do root
            target_written = Ref(false)
            target_psi = Ref{Any}(nothing)
            interruption = try
                finite_bath_observables(
                    parameters;
                    common...,
                    checkpoint_manager = (psi, state) -> begin
                        completed_steps =
                            state.evolution_state === nothing ?
                            0 :
                            state.evolution_state.completed_steps
                        write_checkpoint_generation(
                            root,
                            identity,
                            CheckpointCursor(completed_steps),
                            psi,
                            state;
                            purification,
                        )
                        cursor = state.cursor
                        if cursor.phase === :green &&
                           cursor.tau_index == 1 &&
                           cursor.spin === :up &&
                           cursor.insertion === insertion &&
                           cursor.segment === :after &&
                           state.evolution_state === nothing
                            target_psi[] = copy(psi)
                            target_written[] = true
                        end
                    end,
                    stop_requested = () -> target_written[],
                )
                nothing
            catch error
                error
            end
            @test interruption isa ObservableInterrupted
            @test target_written[]

            loaded = load_current_checkpoint(
                root, identity; purification
            )
            expected =
                operator_sector(purification, insertion, :up)
            @test loaded.resume_state.cursor ==
                  ObservableCursor(
                :green, 1, :up, insertion, :after
            )
            @test loaded.resume_state.data.expected_sector == expected
            @test flux(loaded.psi) ==
                  QN(("Nf", expected.nf, -1), ("Sz", expected.sz))
            @test siteinds(loaded.psi) == siteinds(target_psi[])
            @test all(
                inds(loaded.psi[index]) == inds(target_psi[][index])
                for index in eachindex(loaded.psi)
            )
            @test phase_aligned_mps_error(
                target_psi[], loaded.psi
            ) <= 1.0e-11

            resumed_cursors = ObservableCursor[]
            resumed = finite_bath_observables(
                parameters;
                common...,
                resume = loaded,
                checkpoint_manager = (_, state) ->
                    push!(resumed_cursors, state.cursor),
            )
            assert_observable_equivalence(resumed, uninterrupted)
            @test !any(
                cursor ->
                    cursor.phase === :green &&
                    cursor.tau_index == 1 &&
                    cursor.spin === :up &&
                    cursor.segment === :before,
                resumed_cursors,
            )
            @test resumed.diagnostics.green_up[1].settings.before_steps ==
                  uninterrupted.diagnostics.green_up[1].settings.before_steps
            @test resumed.diagnostics.green_up[1].settings.after_steps ==
                  uninterrupted.diagnostics.green_up[1].settings.after_steps

            forged_sector = operator_sector(
                purification,
                insertion,
                :dn,
            )
            forged_data = merge(
                loaded.resume_state.data,
                (; expected_sector = forged_sector),
            )
            forged_state = ObservableResumeState(
                loaded.resume_state.cursor,
                loaded.resume_state.evolution_state,
                loaded.resume_state.thermal_psi,
                forged_data,
            )
            mktempdir() do forged_root
                @test_throws ArgumentError write_checkpoint_generation(
                    forged_root,
                    identity,
                    CheckpointCursor(0),
                    loaded.psi,
                    forged_state;
                    purification,
                )
            end
            @test_throws ArgumentError finite_bath_observables(
                parameters;
                common...,
                resume = (; psi = loaded.psi, resume_state = forged_state),
            )
            @test_throws ArgumentError finite_bath_observables(
                parameters;
                common...,
                resume = (;
                    psi = loaded.resume_state.thermal_psi,
                    resume_state = loaded.resume_state,
                ),
            )

            terminal_data = merge(
                loaded.resume_state.data,
                (;
                    operator_log_norm = -Inf,
                    expected_sector = expected,
                    branch_status = :zero,
                ),
            )
            terminal_state = ObservableResumeState(
                ObservableCursor(
                    :green, 1, :up, insertion, :terminal
                ),
                nothing,
                loaded.resume_state.thermal_psi,
                terminal_data,
            )
            mktempdir() do terminal_root
                write_checkpoint_generation(
                    terminal_root,
                    identity,
                    CheckpointCursor(0),
                    nothing,
                    terminal_state;
                    purification,
                )
                terminal_loaded =
                    load_current_checkpoint(
                        terminal_root, identity; purification
                    )
                @test terminal_loaded.psi === nothing
                terminal_result = finite_bath_observables(
                    parameters;
                    common...,
                    resume = terminal_loaded,
                )
                @test terminal_result.G_up[1] == -0.0
                @test terminal_result.diagnostics.green_up[1].settings.after_steps ==
                      0

                forged_terminal_state = ObservableResumeState(
                    terminal_loaded.resume_state.cursor,
                    nothing,
                    terminal_loaded.resume_state.thermal_psi,
                    merge(
                        terminal_loaded.resume_state.data,
                        (; expected_sector = forged_sector),
                    ),
                )
                mktempdir() do forged_terminal_root
                    @test_throws ArgumentError write_checkpoint_generation(
                        forged_terminal_root,
                        identity,
                        CheckpointCursor(0),
                        nothing,
                        forged_terminal_state;
                        purification,
                    )
                end
                @test_throws ArgumentError finite_bath_observables(
                    parameters;
                    common...,
                    resume = (;
                        psi = nothing,
                        resume_state = forged_terminal_state,
                    ),
                )
            end
        end
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
