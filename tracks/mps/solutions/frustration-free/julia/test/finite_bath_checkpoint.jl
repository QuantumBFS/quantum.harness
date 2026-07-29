using Test
using JSON3
using SHA
using HDF5
using ITensors
using ITensorMPS

include(joinpath(@__DIR__, "..", "finite_bath_checkpoint.jl"))
using .FiniteBathCheckpoint:
    CheckpointCursor,
    CheckpointIdentity,
    EvolutionResumeState,
    ObservableCursor,
    ObservableResumeState,
    load_current_checkpoint,
    write_checkpoint_generation

function checkpoint_identity(; overrides...)
    values = (;
        request_sha256 = repeat("1", 64),
        input_payload_sha256 = repeat("2", 64),
        bath_sha256 = repeat("3", 64),
        solver_settings = Dict(
            "beta" => 0.2,
            "time_step" => 0.05,
            "cutoff" => 1.0e-12,
            "maxdim" => 64,
        ),
        source_hashes = Dict(
            "runner" => repeat("4", 64),
            "purification" => repeat("5", 64),
        ),
        project_toml_sha256 = repeat("6", 64),
        manifest_toml_sha256 = repeat("7", 64),
        bath_representation = "direct_star",
        chain_mapping_sha256 = nothing,
        julia_version = string(VERSION),
        itensors_version = string(Base.pkgversion(ITensors)),
        itensormps_version = string(Base.pkgversion(ITensorMPS)),
        hdf5_version = "0.17.3",
        checkpoint_schema = 1,
        writer_version = "1.0.0",
    )
    return CheckpointIdentity(; merge(values, overrides)...)
end

@testset "checkpoint identity binds bath geometry" begin
    direct = checkpoint_identity()
    chain = checkpoint_identity(
        bath_representation = "chain",
        chain_mapping_sha256 = repeat("a", 64),
    )

    @test direct.bath_representation == "direct_star"
    @test direct.chain_mapping_sha256 === nothing
    @test chain.bath_representation == "chain"
    @test chain.chain_mapping_sha256 == repeat("a", 64)
    @test_throws ArgumentError checkpoint_identity(
        bath_representation = "tree",
        chain_mapping_sha256 = nothing,
    )
    @test_throws ArgumentError checkpoint_identity(
        bath_representation = "direct_star",
        chain_mapping_sha256 = repeat("a", 64),
    )
    @test_throws ArgumentError checkpoint_identity(
        bath_representation = "chain",
        chain_mapping_sha256 = nothing,
    )
    @test_throws ArgumentError checkpoint_identity(
        bath_representation = "chain",
        chain_mapping_sha256 = "not-a-sha256",
    )
end

function checkpoint_fixture()
    sites = siteinds("S=1/2", 3)
    psi = random_mps(sites; linkdims = 2)
    normalize!(psi)
    history = [
        (;
            beta_endpoint = 0.05,
            cumulative_log_norm = -0.01,
            maximum_link_dimension = 2,
        ),
        (;
            beta_endpoint = 0.10,
            cumulative_log_norm = -0.02,
            maximum_link_dimension = 2,
        ),
    ]
    state = EvolutionResumeState(
        completed_steps = 2,
        beta_endpoint = 0.1,
        log_unnormalized_norm = -0.02,
        maximum_link_dimensions_by_bond = [2, 2],
        step_history = history,
        expansion_applied = true,
    )
    return psi, state
end

function parse_json(path)
    return JSON3.read(read(path, String), Dict{String,Any})
end

function write_json(path, value)
    open(path, "w") do io
        JSON3.write(io, value)
        write(io, '\n')
    end
end

function same_resume_state(left, right)
    return all(
        getfield(left, field) == getfield(right, field) for
        field in fieldnames(EvolutionResumeState)
    )
end

function same_observable_cursor(left, right)
    return all(
        getfield(left, field) == getfield(right, field) for
        field in fieldnames(typeof(left))
    )
end

@testset "observable cursor validation" begin
    legal = [
        ObservableCursor(:thermal, 0, :none, :none, :none),
        ObservableCursor(:green, 1, :up, :creation, :before),
        ObservableCursor(:green, 1, :up, :creation, :after),
        ObservableCursor(:green, 1, :dn, :annihilation, :before),
        ObservableCursor(:green, 1, :dn, :annihilation, :after),
        ObservableCursor(:complete, 0, :none, :none, :none),
    ]
    @test length(unique(legal)) == length(legal)
    @test legal[2] ==
          ObservableCursor(:green, 1, :up, :creation, :before)
    @test_throws MethodError ObservableCursor(:green, 1, :up, :before)
    @test_throws ArgumentError ObservableCursor(
        :thermal, 1, :none, :none, :none
    )
    @test_throws ArgumentError ObservableCursor(
        :green, 0, :up, :creation, :before
    )
    @test_throws ArgumentError ObservableCursor(
        :green, 1, :sideways, :creation, :before
    )
    @test_throws ArgumentError ObservableCursor(
        :green, 1, :up, :none, :before
    )
    @test_throws ArgumentError ObservableCursor(
        :green, 1, :up, :creation, :middle
    )
    @test_throws ArgumentError ObservableCursor(
        :complete, 1, :none, :none, :none
    )
end

@testset "zero Green terminal checkpoints omit active MPS" begin
    mktempdir() do root
        identity = checkpoint_identity()
        thermal, _ = checkpoint_fixture()
        cursor =
            ObservableCursor(:green, 2, :up, :creation, :terminal)
        state = ObservableResumeState(
            cursor,
            nothing,
            thermal,
            (;
                branch_status = :zero,
                expected_sector =
                    (; insertion = :creation, spin = :up, nf = 3, sz = 1),
            ),
        )
        written = write_checkpoint_generation(
            root, identity, CheckpointCursor(0), nothing, state
        )
        loaded = load_current_checkpoint(root, identity)
        @test loaded.cursor == written
        @test loaded.psi === nothing
        @test loaded.resume_state.cursor == cursor
        @test loaded.resume_state.data.branch_status === :zero
        state_path = joinpath(
            root, "generations", written.generation, "state.h5"
        )
        h5open(state_path, "r") do file
            @test !haskey(file, "psi")
            @test haskey(file, "thermal_psi")
        end
    end
end

@testset "atomic version-bound MPS checkpoints" begin
    @testset "observable workflow state round trip" begin
        mktempdir() do root
            identity = checkpoint_identity()
            psi, evolution = checkpoint_fixture()
            workflow = ObservableResumeState(
                ObservableCursor(:green, 2, :dn, :creation, :after),
                evolution,
                deepcopy(psi),
                (;
                    tau = [0.2, 0.1, 0.1],
                    G_up = [-0.4, nothing, nothing],
                    G_dn = [-0.6, nothing, nothing],
                    diagnostics_up = [(; spin = :up, insertion = :creation)],
                    diagnostics_dn = NamedTuple[],
                    operator_log_norm = -0.25,
                ),
            )

            write_checkpoint_generation(
                root, identity, CheckpointCursor(2), psi, workflow
            )
            loaded = load_current_checkpoint(root, identity)

            @test same_observable_cursor(
                loaded.resume_state.cursor, workflow.cursor
            )
            @test same_resume_state(
                loaded.resume_state.evolution_state, evolution
            )
            @test loaded.resume_state.data == workflow.data
            @test abs(inner(loaded.resume_state.thermal_psi, psi)) ≈ 1.0 atol = 1.0e-12
        end
    end

    @testset "exact metadata and MPS round trip" begin
        mktempdir() do root
            identity = checkpoint_identity()
            psi, state = checkpoint_fixture()

            cursor = write_checkpoint_generation(
                root, identity, CheckpointCursor(2), psi, state
            )
            loaded = load_current_checkpoint(root, identity)

            @test cursor isa CheckpointCursor
            @test loaded.identity == identity
            @test loaded.cursor == cursor
            @test same_resume_state(loaded.resume_state, state)
            @test loaded.cursor.completed_steps == 2
            @test norm(loaded.psi) ≈ norm(psi) atol = 1.0e-12
            @test abs(inner(psi, loaded.psi)) ≈ 1.0 atol = 1.0e-12
            @test basename(loaded.cursor.generation) ==
                  "checkpoint-$(loaded.cursor.metadata_sha256)"
            metadata = parse_json(
                joinpath(
                    root,
                    "generations",
                    loaded.cursor.generation,
                    "metadata.json",
                )
            )
            @test Set(keys(metadata["identity"])) == Set([
                "request_sha256",
                "input_payload_sha256",
                "bath_sha256",
                "bath_representation",
                "chain_mapping_sha256",
                "solver_settings",
                "source_hashes",
                "project_toml_sha256",
                "manifest_toml_sha256",
                "julia_version",
                "itensors_version",
                "itensormps_version",
                "hdf5_version",
                "checkpoint_schema",
                "writer_version",
            ])
            @test metadata["identity"]["bath_representation"] == "direct_star"
            @test metadata["identity"]["chain_mapping_sha256"] === nothing
        end
    end

    @testset "same identity resumes while geometry and mapping replay fail" begin
        for (written, matching, mismatch) in (
            (
                checkpoint_identity(),
                checkpoint_identity(),
                checkpoint_identity(
                    bath_representation = "chain",
                    chain_mapping_sha256 = repeat("a", 64),
                ),
            ),
            (
                checkpoint_identity(
                    bath_representation = "chain",
                    chain_mapping_sha256 = repeat("a", 64),
                ),
                checkpoint_identity(
                    bath_representation = "chain",
                    chain_mapping_sha256 = repeat("a", 64),
                ),
                checkpoint_identity(),
            ),
            (
                checkpoint_identity(
                    bath_representation = "chain",
                    chain_mapping_sha256 = repeat("a", 64),
                ),
                checkpoint_identity(
                    bath_representation = "chain",
                    chain_mapping_sha256 = repeat("a", 64),
                ),
                checkpoint_identity(
                    bath_representation = "chain",
                    chain_mapping_sha256 = repeat("b", 64),
                ),
            ),
            (
                checkpoint_identity(
                    bath_representation = "chain",
                    chain_mapping_sha256 = repeat("b", 64),
                ),
                checkpoint_identity(
                    bath_representation = "chain",
                    chain_mapping_sha256 = repeat("b", 64),
                ),
                checkpoint_identity(
                    bath_representation = "chain",
                    chain_mapping_sha256 = repeat("a", 64),
                ),
            ),
        )
            mktempdir() do root
                psi, state = checkpoint_fixture()
                write_checkpoint_generation(root, written, 2, psi, state)
                @test load_current_checkpoint(root, matching).identity == matching
                error = try
                    load_current_checkpoint(root, mismatch)
                    nothing
                catch caught
                    caught
                end
                @test error isa ArgumentError
                @test sprint(showerror, error) == "ArgumentError: checkpoint identity mismatch"
            end
        end
    end

    @testset "legacy identity metadata fails closed" begin
        mktempdir() do root
            identity = checkpoint_identity()
            psi, state = checkpoint_fixture()
            cursor = write_checkpoint_generation(root, identity, 2, psi, state)
            generation = joinpath(root, "generations", cursor.generation)
            metadata = parse_json(joinpath(generation, "metadata.json"))
            delete!(metadata["identity"], "bath_representation")
            delete!(metadata["identity"], "chain_mapping_sha256")
            metadata_bytes = FiniteBathCheckpoint._canonical_bytes(metadata)
            metadata_sha256 = bytes2hex(sha256(metadata_bytes))
            state_sha256 = bytes2hex(
                sha256(read(joinpath(generation, "state.h5")))
            )
            new_name = "checkpoint-$metadata_sha256"
            write(joinpath(generation, "metadata.json"), metadata_bytes)
            completion = Dict{String,Any}(
                "checkpoint_schema" => identity.checkpoint_schema,
                "writer_version" => identity.writer_version,
                "generation" => new_name,
                "metadata_sha256" => metadata_sha256,
                "state_sha256" => state_sha256,
            )
            completion_bytes = FiniteBathCheckpoint._canonical_bytes(completion)
            completion_sha256 = bytes2hex(sha256(completion_bytes))
            write(joinpath(generation, "completion.json"), completion_bytes)
            destination = joinpath(root, "generations", new_name)
            mv(generation, destination)
            pointer = Dict{String,Any}(
                "checkpoint_schema" => identity.checkpoint_schema,
                "writer_version" => identity.writer_version,
                "generation" => new_name,
                "completed_steps" => 2,
                "metadata_sha256" => metadata_sha256,
                "state_sha256" => state_sha256,
                "completion_sha256" => completion_sha256,
            )
            write(
                joinpath(root, "current.json"),
                FiniteBathCheckpoint._canonical_bytes(pointer),
            )

            @test_throws ArgumentError load_current_checkpoint(root, identity)
        end
    end

    @testset "publication preserves valid generations and ignores stages" begin
        mktempdir() do root
            identity = checkpoint_identity()
            psi, state = checkpoint_fixture()
            first =
                write_checkpoint_generation(root, identity, 2, psi, state)
            first_pointer = read(joinpath(root, "current.json"))

            interrupted_stage = joinpath(root, "generations", ".stage-abandoned")
            mkpath(interrupted_stage)
            write(joinpath(interrupted_stage, "metadata.json"), "{")
            @test load_current_checkpoint(root, identity).cursor == first
            @test read(joinpath(root, "current.json")) == first_pointer

            second_state = EvolutionResumeState(
                completed_steps = 3,
                beta_endpoint = 0.15,
                log_unnormalized_norm = -0.03,
                maximum_link_dimensions_by_bond = [2, 2],
                step_history = [
                    state.step_history...,
                    (;
                        beta_endpoint = 0.15,
                        cumulative_log_norm = -0.03,
                        maximum_link_dimension = 2,
                    ),
                ],
                expansion_applied = true,
            )
            second = write_checkpoint_generation(
                root, identity, 3, psi, second_state
            )
            @test second != first
            @test isdir(joinpath(root, "generations", first.generation))

            write(joinpath(root, "current.json"), first_pointer)
            restored = load_current_checkpoint(root, identity)
            @test restored.cursor == first
            @test same_resume_state(restored.resume_state, state)
        end
    end

    @testset "failed generation never advances current" begin
        mktempdir() do root
            identity = checkpoint_identity()
            psi, state = checkpoint_fixture()
            write_checkpoint_generation(root, identity, 2, psi, state)
            pointer_before = read(joinpath(root, "current.json"))
            invalid_state = EvolutionResumeState(
                -1, 0.1, -0.02, [2, 2], state.step_history, true
            )

            @test_throws ArgumentError write_checkpoint_generation(
                root, identity, 2, psi, invalid_state
            )
            @test read(joinpath(root, "current.json")) == pointer_before
            @test same_resume_state(
                load_current_checkpoint(root, identity).resume_state, state
            )
        end
    end

    @testset "malformed, nonregular, symlinked, and corrupted artifacts fail closed" begin
        function prepared_root()
            root = mktempdir()
            identity = checkpoint_identity()
            psi, state = checkpoint_fixture()
            cursor =
                write_checkpoint_generation(root, identity, 2, psi, state)
            generation =
                joinpath(root, "generations", cursor.generation)
            return root, identity, cursor, generation
        end

        root, identity, _, _ = prepared_root()
        write(joinpath(root, "current.json"), "{")
        @test_throws ArgumentError load_current_checkpoint(root, identity)

        root, identity, _, _ = prepared_root()
        pointer = joinpath(root, "current.json")
        bytes = read(pointer)
        rm(pointer)
        write(joinpath(root, "pointer-target.json"), bytes)
        symlink("pointer-target.json", pointer)
        @test_throws ArgumentError load_current_checkpoint(root, identity)

        root, identity, _, generation = prepared_root()
        metadata = joinpath(generation, "metadata.json")
        rm(metadata)
        mkdir(metadata)
        @test_throws ArgumentError load_current_checkpoint(root, identity)

        root, identity, _, generation = prepared_root()
        state_path = joinpath(generation, "state.h5")
        state_bytes = read(state_path)
        rm(state_path)
        write(joinpath(generation, "state-target.h5"), state_bytes)
        symlink("state-target.h5", state_path)
        @test_throws ArgumentError load_current_checkpoint(root, identity)

        root, identity, _, generation = prepared_root()
        write(joinpath(generation, "state.h5"), "not an HDF5 file")
        @test_throws ArgumentError load_current_checkpoint(root, identity)

        root, identity, _, generation = prepared_root()
        completion_path = joinpath(generation, "completion.json")
        completion = parse_json(completion_path)
        completion["state_sha256"] = repeat("f", 64)
        write_json(completion_path, completion)
        @test_throws ArgumentError load_current_checkpoint(root, identity)
    end

    @testset "identity mismatches fail closed" begin
        mktempdir() do root
            identity = checkpoint_identity()
            psi, state = checkpoint_fixture()
            write_checkpoint_generation(root, identity, 2, psi, state)

            mismatches = [
                checkpoint_identity(request_sha256 = repeat("a", 64)),
                checkpoint_identity(
                    source_hashes = Dict(
                        "runner" => repeat("b", 64),
                        "purification" => repeat("5", 64),
                    )
                ),
                checkpoint_identity(itensors_version = "0.0.0"),
                checkpoint_identity(itensormps_version = "0.0.0"),
                checkpoint_identity(hdf5_version = "0.0.0"),
                checkpoint_identity(julia_version = "0.0.0"),
                checkpoint_identity(checkpoint_schema = 2),
            ]
            for mismatch in mismatches
                @test_throws ArgumentError load_current_checkpoint(
                    root, mismatch
                )
            end
        end
    end
end
