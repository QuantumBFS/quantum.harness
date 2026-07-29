using Test
using JSON3

include(joinpath(@__DIR__, "..", "finite_bath_mps_runner.jl"))

function minimal_runner_request(; n_bath = 2)
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
    grid = [-1.0, 0.0, 1.0]
    width = bandwidth / (n_bath + 1)
    broadened = [
        pi * sum(
            coupling[index]^2 *
            exp(-0.5 * ((omega - epsilon[index]) / width)^2) /
            (sqrt(2pi) * width) for index in eachindex(epsilon)
        ) for omega in grid
    ]
    bath_payload = Dict(
        "V" => coupling,
        "broadening" => Dict(
            "kernel" => "normalized_gaussian",
            "width" => width,
            "width_rule" => "bandwidth / (n_bath + 1)",
            "interpretation" =>
                "broadened finite-bath realization; not the fitted continuum",
        ),
        "broadened_finite_bath_hybridization" => broadened,
        "conventions" => Dict(
            "hybridization" =>
                "Gamma(omega) = pi * sum_k V_k^2 * delta(omega - epsilon_k)",
            "quadrature" =>
                "Gauss-Chebyshev quadrature of the second kind",
            "target_continuum" =>
                "Gamma_target(omega) = gamma * sqrt(1 - (omega / bandwidth)^2) for |omega| <= bandwidth; 0 otherwise",
            "ordering" => "k = 1..n_bath; epsilon in descending order",
            "epsilon" => "bandwidth * cos(k * pi / (n_bath + 1))",
            "V_squared" =>
                "gamma * bandwidth / (n_bath + 1) * sin(k * pi / (n_bath + 1))^2",
        ),
        "epsilon" => epsilon,
        "frequency_grid" => grid,
        "parameters" => Dict(
            "bandwidth" => bandwidth, "gamma" => gamma, "n_bath" => n_bath
        ),
        "provenance" => Dict(
            "module" => "bath",
            "module_version" => "1.0.0",
            "python_version" => "3.12.13",
            "numpy_version" => "2.5.1",
            "schema_version" => 2,
        ),
        "schema_version" => 2,
        "target_continuum_hybridization" => [0.0, gamma, 0.0],
    )
    bath_artifact = Dict(
        "payload" => bath_payload,
        "sha256" =>
            bytes2hex(sha256(codeunits(canonical_artifact_json(bath_payload)))),
    )
    bath_json = canonical_artifact_json(bath_artifact) * "\n"
    payload = Dict(
        "schema_version" => 3,
        "bath_artifact_json" => bath_json,
        "bath_artifact_file_sha256" => bytes2hex(sha256(codeunits(bath_json))),
        "bath_geometry" => Dict(
            "representation" => "direct_star",
            "chain_mapping_artifact_json" => nothing,
            "chain_mapping_artifact_file_sha256" => nothing,
        ),
        "checkpoint" => Dict(
            "checkpoint_schema" => 1,
            "writer_version" => "1.0.0",
            "source_hashes" => Dict(
                "chain_mapping" => source_sha256(
                    joinpath(@__DIR__, "..", "..", "chain_mapping.py")
                ),
                "checkpoint" => source_sha256(
                    joinpath(@__DIR__, "..", "finite_bath_checkpoint.jl")
                ),
                "model_definition" => source_sha256(
                    joinpath(@__DIR__, "..", "..", "model.json")
                ),
                "observables" => source_sha256(
                    joinpath(@__DIR__, "..", "finite_bath_observables.jl")
                ),
                "purification" => source_sha256(
                    joinpath(@__DIR__, "..", "finite_bath_purification.jl")
                ),
                "runner" => source_sha256(
                    joinpath(@__DIR__, "..", "finite_bath_mps_runner.jl")
                ),
            ),
            "project_toml_sha256" => source_sha256(
                joinpath(@__DIR__, "..", "Project.toml")
            ),
            "manifest_toml_sha256" => source_sha256(
                joinpath(@__DIR__, "..", "Manifest.toml")
            ),
        ),
        "model" => Dict(
            "U" => 0.8, "beta" => 0.5, "epsilon_d" => -0.4, "mu" => 0.0
        ),
        "tau" => [0.0, 0.25, 0.5],
        "solver_settings" => Dict(
            "cutoff" => 1.0e-14,
            "krylov_expansion_dim" => 32,
            "maxdim" => 256,
            "time_step" => 0.01,
        ),
    )
    return Dict(
        "payload_json" => canonical_request_json(payload),
        "sha256" => repeat("0", 64),
    )
end

function resign_runner_request!(request)
    request["payload_json"] = canonical_request_json(
        strict_json_read(request["payload_json"], "test request")
    )
    request["sha256"] =
        bytes2hex(sha256(codeunits(request["payload_json"])))
    return request
end

function python_chain_mapping(bath_json)
    solution_dir = normpath(joinpath(@__DIR__, "..", ".."))
    return mktempdir() do directory
        bath_path = joinpath(directory, "bath.json")
        mapping_path = joinpath(directory, "chain-mapping.json")
        write(bath_path, bath_json)
        script = """
import json
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
import chain_mapping
with pathlib.Path(sys.argv[2]).open(encoding="utf-8") as stream:
    bath = json.load(stream)
chain_mapping.write_chain_mapping_json(
    sys.argv[3], bath_artifact=bath
)
"""
        command = `uv run --project=$solution_dir --frozen python -c $script $solution_dir $bath_path $mapping_path`
        run(command)
        read(mapping_path, String)
    end
end

function chain_runner_request(; n_bath = 2)
    request = minimal_runner_request(; n_bath)
    payload = strict_json_read(request["payload_json"], "test request")
    mapping_json = python_chain_mapping(payload["bath_artifact_json"])
    payload["bath_geometry"] = Dict(
        "representation" => "chain",
        "chain_mapping_artifact_json" => mapping_json,
        "chain_mapping_artifact_file_sha256" =>
            bytes2hex(sha256(codeunits(mapping_json))),
    )
    request["payload_json"] = canonical_request_json(payload)
    return resign_runner_request!(request)
end

function write_and_read_request(request)
    return mktempdir() do directory
        path = joinpath(directory, "request.json")
        write(path, JSON3.write(request))
        read_request(path)
    end
end

function mutate_mapping!(request, mutation; rehash_payload = true)
    payload = strict_json_read(request["payload_json"], "test request")
    geometry = payload["bath_geometry"]
    mapping = strict_json_read(
        geometry["chain_mapping_artifact_json"], "mapping artifact"
    )
    mutation(mapping)
    if rehash_payload
        mapping["sha256"] = bytes2hex(
            sha256(codeunits(canonical_artifact_json(mapping["payload"])))
        )
    end
    mapping_json = canonical_artifact_json(mapping) * "\n"
    geometry["chain_mapping_artifact_json"] = mapping_json
    geometry["chain_mapping_artifact_file_sha256"] =
        bytes2hex(sha256(codeunits(mapping_json)))
    request["payload_json"] = canonical_request_json(payload)
    return resign_runner_request!(request)
end

function mutate_mapping_python!(request, path, replacement)
    payload = strict_json_read(request["payload_json"], "test request")
    geometry = payload["bath_geometry"]
    solution_dir = normpath(joinpath(@__DIR__, "..", ".."))
    mapping_json = mktempdir() do directory
        input_path = joinpath(directory, "mapping.json")
        output_path = joinpath(directory, "mutated.json")
        write(input_path, geometry["chain_mapping_artifact_json"])
        script = """
import hashlib
import json
import pathlib
import sys
sys.path.insert(0, sys.argv[1])
import chain_mapping
mapping = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))
path = json.loads(sys.argv[4])
replacement = json.loads(sys.argv[5])
target = mapping
for key in path[:-1]:
    target = target[key]
target[path[-1]] = replacement
mapping["sha256"] = hashlib.sha256(
    chain_mapping._canonical_json(mapping["payload"])
).hexdigest()
pathlib.Path(sys.argv[3]).write_bytes(
    chain_mapping._canonical_json(mapping) + b"\\n"
)
"""
        command = `uv run --project=$solution_dir --frozen python -c $script $solution_dir $input_path $output_path $(canonical_request_json(path)) $(canonical_artifact_json(replacement))`
        run(command)
        read(output_path, String)
    end
    geometry["chain_mapping_artifact_json"] = mapping_json
    geometry["chain_mapping_artifact_file_sha256"] =
        bytes2hex(sha256(codeunits(mapping_json)))
    request["payload_json"] = canonical_request_json(payload)
    return resign_runner_request!(request)
end

function semantic_rejection_message(request)
    try
        write_and_read_request(request)
    catch error
        @test error isa ArgumentError
        return sprint(showerror, error)
    end
    @test false
    return ""
end

function mapping_output_fixture(request)
    thermal_diagnostics = (;
        step_history = NamedTuple[],
        maximum_link_dimensions_by_bond = Int[],
    )
    result = (;
        tau = [0.0],
        n_d = 1.0,
        double_occupancy = 0.25,
        G_up = [-0.5],
        G_dn = [-0.5],
        diagnostics = (;
            log_partition = 0.0,
            thermal_log_norm = 0.0,
            thermal_max_link_dimension = 1,
            maximum_link_dimensions_by_bond = Int[],
            green_up = NamedTuple[],
            green_dn = NamedTuple[],
            disclaimer = "test fixture",
        ),
        thermal_state = (; diagnostics = thermal_diagnostics),
    )
    return make_output(request, result, (; fixture = true))
end

function signed_runner_request(; beta = 0.5, time_step = 0.01)
    request = minimal_runner_request()
    payload = strict_json_read(request["payload_json"], "test request")
    payload["model"]["beta"] = beta
    payload["tau"] = [0.0, beta]
    payload["solver_settings"]["time_step"] = time_step
    payload["solver_settings"]["maxdim"] = 64
    payload["solver_settings"]["krylov_expansion_dim"] = 0
    request["payload_json"] = canonical_request_json(payload)
    request["sha256"] =
        bytes2hex(sha256(codeunits(request["payload_json"])))
    return request
end

@testset "runner schema 3 consumes direct and Python chain geometry" begin
    direct = write_and_read_request(resign_runner_request!(minimal_runner_request()))
    chain_request = chain_runner_request()
    chain = write_and_read_request(chain_request)
    mapping = strict_json_read(
        chain.payload["bath_geometry"]["chain_mapping_artifact_json"],
        "mapping artifact",
    )

    @test direct.parameters.bath_representation === :direct_star
    @test direct.bath_representation == "direct_star"
    @test direct.mapping_sha256 === nothing
    @test chain.parameters.bath_representation === :chain
    @test chain.bath_representation == "chain"
    @test chain.mapping_sha256 == mapping["sha256"]
    @test chain.parameters.mapping_sha256 == chain.mapping_sha256
    @test chain.parameters.chain_onsite == mapping["payload"]["chain_onsite"]
    @test chain.parameters.chain_hopping == mapping["payload"]["chain_hopping"]
    @test chain.parameters.mu == 0.0
end

@testset "runner checkpoint identity uses validated geometry" begin
    direct_request =
        write_and_read_request(resign_runner_request!(minimal_runner_request()))
    chain_request = write_and_read_request(chain_runner_request())
    direct = checkpoint_identity(direct_request)
    chain = checkpoint_identity(chain_request)

    @test direct.bath_representation == "direct_star"
    @test direct.chain_mapping_sha256 === nothing
    @test chain.bath_representation == "chain"
    @test chain.chain_mapping_sha256 == chain_request.mapping_sha256
    @test direct.request_sha256 == bytes2hex(sha256(direct_request.raw))
    @test chain.request_sha256 == bytes2hex(sha256(chain_request.raw))
end

@testset "runner geometry requires exact representation and mapping pairing" begin
    direct_with_mapping = chain_runner_request()
    payload = strict_json_read(
        direct_with_mapping["payload_json"], "test request"
    )
    payload["bath_geometry"]["representation"] = "direct_star"
    direct_with_mapping["payload_json"] = canonical_request_json(payload)
    resign_runner_request!(direct_with_mapping)
    @test_throws ArgumentError write_and_read_request(direct_with_mapping)

    absent_geometry = chain_runner_request()
    payload = strict_json_read(absent_geometry["payload_json"], "test request")
    delete!(payload, "bath_geometry")
    absent_geometry["payload_json"] = canonical_request_json(payload)
    resign_runner_request!(absent_geometry)
    @test_throws ArgumentError write_and_read_request(absent_geometry)

    for mutation in (
        geometry -> delete!(geometry, "chain_mapping_artifact_json"),
        geometry -> (
            geometry["chain_mapping_artifact_json"] = nothing;
            geometry["chain_mapping_artifact_file_sha256"] = nothing
        ),
        geometry -> geometry["representation"] = "tree",
        geometry -> geometry["unexpected"] = nothing,
    )
        request = chain_runner_request()
        payload = strict_json_read(request["payload_json"], "test request")
        mutation(payload["bath_geometry"])
        request["payload_json"] = canonical_request_json(payload)
        resign_runner_request!(request)
        @test_throws ArgumentError write_and_read_request(request)
    end
end

@testset "runner rejects mapping byte and hash corruption" begin
    wrong_file_hash = chain_runner_request()
    payload = strict_json_read(wrong_file_hash["payload_json"], "test request")
    payload["bath_geometry"]["chain_mapping_artifact_file_sha256"] =
        repeat("0", 64)
    wrong_file_hash["payload_json"] = canonical_request_json(payload)
    resign_runner_request!(wrong_file_hash)
    @test_throws ArgumentError write_and_read_request(wrong_file_hash)

    wrong_payload_hash = mutate_mapping!(
        chain_runner_request(),
        mapping -> mapping["payload"]["lambda"] += 0.01;
        rehash_payload = false,
    )
    @test_throws ArgumentError write_and_read_request(wrong_payload_hash)

    noncanonical = chain_runner_request()
    payload = strict_json_read(noncanonical["payload_json"], "test request")
    mapping_json =
        payload["bath_geometry"]["chain_mapping_artifact_json"] * "\n"
    payload["bath_geometry"]["chain_mapping_artifact_json"] = mapping_json
    payload["bath_geometry"]["chain_mapping_artifact_file_sha256"] =
        bytes2hex(sha256(codeunits(mapping_json)))
    noncanonical["payload_json"] = canonical_request_json(payload)
    resign_runner_request!(noncanonical)
    @test_throws ArgumentError write_and_read_request(noncanonical)

    noncanonical_number = mutate_mapping!(
        chain_runner_request(),
        mapping -> mapping["payload"]["chain_onsite"][1] = 0,
    )
    @test_throws ArgumentError write_and_read_request(noncanonical_number)
end

@testset "runner requires exact chain mapping keys" begin
    for mutation in (
        mapping -> mapping["unexpected"] = nothing,
        mapping -> delete!(mapping["payload"], "representation"),
        mapping -> mapping["payload"]["unexpected"] = nothing,
        mapping -> mapping["payload"]["numerics"]["unexpected"] = nothing,
        mapping -> delete!(
            mapping["payload"]["numerics"], "off_tridiagonal_max_abs"
        ),
    )
        request = mutate_mapping!(chain_runner_request(), mutation)
        @test_throws ArgumentError write_and_read_request(request)
    end
end

@testset "runner independently rejects invalid mapping science" begin
    mutations = [
        mapping -> mapping["payload"]["source_bath_sha256"] = repeat("0", 64),
        mapping -> mapping["payload"]["conventions"]["chemical_potential"] =
            "subtract mu before transforming E",
        mapping -> mapping["payload"]["chain_hopping"][1] = -0.1,
        mapping -> mapping["payload"]["Q"] = [[1.0]],
        mapping -> mapping["payload"]["Q"][1][1] += 0.1,
        mapping -> mapping["payload"]["chain_onsite"][1] += 0.1,
        mapping -> mapping["payload"]["chain_hopping"] = Float64[],
        mapping -> mapping["payload"]["lambda"] += 0.1,
    ]
    for mutation in mutations
        request = mutate_mapping!(chain_runner_request(), mutation)
        @test_throws ArgumentError write_and_read_request(request)
    end
end

@testset "valid outer digests cannot bless scientific corruption" begin
    request = mutate_mapping_python!(
        chain_runner_request(),
        ["payload", "chain_onsite", 0],
        0.123,
    )
    payload = strict_json_read(request["payload_json"], "corrupted request")
    geometry = payload["bath_geometry"]
    mapping_json = geometry["chain_mapping_artifact_json"]
    mapping = strict_json_read(mapping_json, "corrupted mapping")

    prefix = "{\"payload\":"
    suffix = ",\"sha256\":\"$(mapping["sha256"])\"}\n"
    payload_bytes = codeunits(mapping_json)[
        (ncodeunits(prefix) + 1):(ncodeunits(mapping_json) - ncodeunits(suffix))
    ]
    @test mapping["sha256"] == bytes2hex(sha256(payload_bytes))
    @test geometry["chain_mapping_artifact_file_sha256"] ==
        bytes2hex(sha256(codeunits(mapping_json)))
    @test request["sha256"] == bytes2hex(sha256(codeunits(request["payload_json"])))
    message = semantic_rejection_message(request)
    @test occursin("chain onsite", message)
end

@testset "runner replays every diagnostic and locks producer provenance" begin
    for n_bath in 1:6
        request = write_and_read_request(chain_runner_request(; n_bath))
        @test length(request.parameters.epsilon) == n_bath
        @test request.parameters.bath_representation === :chain
    end

    runner_source = read(
        joinpath(@__DIR__, "..", "finite_bath_mps_runner.jl"), String
    )
    @test !occursin("CHAIN_MAPPING_DIAGNOSTIC_REPLAY_SCRIPT", runner_source)
    @test !occursin("uv run", runner_source)
    portable_request = chain_runner_request()
    mktempdir() do spool
        withenv("PATH" => spool) do
            cd(spool) do
                validated = write_and_read_request(portable_request)
                @test validated.parameters.bath_representation === :chain
            end
        end
    end

    numeric_corruptions = [
        (
            ["payload", "numerics", "algorithm"],
            "tampered algorithm",
            "algorithm",
        ),
        (
            ["payload", "numerics", "breakdown_tolerance"],
            0.0,
            "breakdown_tolerance",
        ),
        (
            ["payload", "numerics", "breakdown_tolerance_rule"],
            "tampered rule",
            "breakdown_tolerance_rule",
        ),
        (
            ["payload", "numerics", "orthogonality_max_error"],
            0.0,
            "orthogonality_max_error",
        ),
        (
            ["payload", "numerics", "off_tridiagonal_max_abs"],
            1.5e-30,
            "off_tridiagonal_max_abs",
        ),
        (
            ["payload", "numerics", "coupling_max_error"],
            0.0,
            "coupling_max_error",
        ),
    ]
    for (path, replacement, field) in numeric_corruptions
        request = mutate_mapping_python!(
            chain_runner_request(), path, replacement
        )
        mapping_json = strict_json_read(
            request["payload_json"], "test request"
        )["bath_geometry"]["chain_mapping_artifact_json"]
        mapping = strict_json_read(mapping_json, "mutated mapping")
        @test canonical_chain_mapping_json(mapping) == mapping_json
        message = semantic_rejection_message(request)
        @test occursin(field, message)
    end

    provenance_corruptions = [
        ("module", "not_chain_mapping"),
        ("module_version", "9.9.9"),
        ("python_version", "3.12.12"),
        ("numpy_version", "2.5.0"),
        ("schema_version", 2),
    ]
    for (field, replacement) in provenance_corruptions
        request = mutate_mapping_python!(
            chain_runner_request(),
            ["payload", "provenance", field],
            replacement,
        )
        mapping_json = strict_json_read(
            request["payload_json"], "test request"
        )["bath_geometry"]["chain_mapping_artifact_json"]
        mapping = strict_json_read(mapping_json, "mutated mapping")
        @test canonical_chain_mapping_json(mapping) == mapping_json
        message = semantic_rejection_message(request)
        @test occursin(field, message)
    end
end

@testset "runner publishes geometry hashes in every output section" begin
    for request in (
        write_and_read_request(resign_runner_request!(minimal_runner_request())),
        write_and_read_request(chain_runner_request()),
    )
        output = mapping_output_fixture(request)
        expected_mapping = request.mapping_sha256
        @test output.solver.settings.bath_representation ==
            request.bath_representation
        @test output.solver.settings.chain_mapping_sha256 == expected_mapping
        @test output.diagnostics.bath_representation ==
            request.bath_representation
        @test output.diagnostics.chain_mapping_sha256 == expected_mapping
        @test output.provenance.bath_representation ==
            request.bath_representation
        @test output.provenance.chain_mapping_sha256 == expected_mapping
        @test output.provenance.chain_mapping_source_sha256 == source_sha256(
            joinpath(@__DIR__, "..", "..", "chain_mapping.py")
        )
    end
end

@testset "runner thermal diagnostics are complete and bounded" begin
    history = [
        (;
            max_link_dimension = 8,
            max_truncation_error = 1.0e-12,
            krylov_all_converged = true,
            krylov_max_error_estimate = 2.0e-13,
            krylov_num_operations = 12,
            krylov_num_iterations = 3,
            krylov_local_updates = 4,
        ),
        (;
            max_link_dimension = 12,
            max_truncation_error = 3.0e-12,
            krylov_all_converged = true,
            krylov_max_error_estimate = 4.0e-13,
            krylov_num_operations = 14,
            krylov_num_iterations = 5,
            krylov_local_updates = 6,
        ),
    ]
    summary = thermal_diagnostics_summary(history, [4, 12, 8])
    @test summary.steps == 2
    @test summary.maximum_link_dimensions_by_bond == [4, 12, 8]
    @test summary.max_link_dimension == 12
    @test summary.truncation_max_error == 3.0e-12
    @test summary.krylov_all_converged
    @test summary.krylov_max_error_estimate == 4.0e-13
    @test summary.krylov_num_operations == 26
    @test summary.krylov_num_iterations == 8
    @test summary.krylov_local_updates == 10
end

@testset "SIGUSR1 and SIGTERM set only cooperative flags" begin
    install_cooperative_shutdown_handlers()
    for signal_number in (10, Base.SIGTERM)
        Threads.atomic_xchg!(SHUTDOWN_REQUESTED, false)
        @test ccall(:kill, Cint, (Cint, Cint), getpid(), signal_number) == 0
        deadline = time() + 5
        while !SHUTDOWN_REQUESTED[] && time() < deadline
            sleep(0.01)
        end
        @test SHUTDOWN_REQUESTED[]
    end
end

@testset "SIGUSR1 checkpoints and resumes without final output" begin
    mktempdir() do directory
        input_path = joinpath(directory, "input.json")
        output_path = joinpath(directory, "output.json")
        checkpoint_root = joinpath(directory, "checkpoint")
        log_path = joinpath(directory, "runner.log")
        write(input_path, JSON3.write(signed_runner_request(; beta = 0.2, time_step = 0.05)))
        project = dirname(Base.active_project())
        command = `$(Base.julia_cmd()) --project=$project $(joinpath(@__DIR__, "..", "finite_bath_mps_runner.jl")) $input_path $output_path $checkpoint_root`

        process = open(log_path, "w") do log
            child = run(pipeline(command; stdout = log, stderr = log); wait = false)
            deadline = time() + 90
            while time() < deadline
                flush(log)
                occursin("Running finite-bath MPS", read(log_path, String)) && break
                process_exited(child) && break
                sleep(0.05)
            end
            @test process_running(child)
            process_running(child) && kill(child, 10)
            wait(child)
            child
        end

        @test process.exitcode == 75
        @test !ispath(output_path)
        @test isfile(joinpath(checkpoint_root, "current.json"))
        first_log = read(log_path, String)
        @test occursin("continuation required", first_log)
        @test !occursin("Published validated MPS result", first_log)

        resumed = run(command; wait = false)
        wait(resumed)
        @test resumed.exitcode == 0
        @test isfile(output_path)
        output = strict_json_read(read(output_path), "resumed output")
        @test output["schema_version"] == RUNNER_SCHEMA_VERSION
        @test output["provenance"]["checkpoint_source_sha256"] ==
            source_sha256(joinpath(@__DIR__, "..", "finite_bath_checkpoint.jl"))
    end
end

@testset "runner rejects unverified payload hashes and duplicate keys" begin
    request = minimal_runner_request()
    mktempdir() do directory
        valid = deepcopy(request)
        valid["sha256"] =
            bytes2hex(sha256(codeunits(valid["payload_json"])))
        valid_path = joinpath(directory, "valid.json")
        write(valid_path, JSON3.write(valid))
        checked = read_request(valid_path)
        @test checked.payload_digest == valid["sha256"]
        @test checked.settings.krylov_expansion_dim == 32
        @test checked.checkpoint["checkpoint_schema"] == 1

        wrong_source = deepcopy(valid)
        wrong_source_payload = strict_json_read(
            wrong_source["payload_json"], "wrong source payload"
        )
        wrong_source_payload["checkpoint"]["source_hashes"]["runner"] =
            repeat("f", 64)
        wrong_source["payload_json"] =
            canonical_request_json(wrong_source_payload)
        wrong_source["sha256"] = bytes2hex(
            sha256(codeunits(wrong_source["payload_json"]))
        )
        wrong_source_path = joinpath(directory, "wrong-source.json")
        write(wrong_source_path, JSON3.write(wrong_source))
        @test_throws ArgumentError read_request(wrong_source_path)

        corrupted = deepcopy(valid)
        corrupted_payload = strict_json_read(
            corrupted["payload_json"], "corrupted payload"
        )
        corrupted_bath = strict_json_read(
            corrupted_payload["bath_artifact_json"], "corrupted bath"
        )
        corrupted_bath["payload"]["epsilon"][1] += 0.01
        corrupted_bath["sha256"] = bytes2hex(
            sha256(codeunits(canonical_artifact_json(corrupted_bath["payload"])))
        )
        corrupted_payload["bath_artifact_json"] =
            canonical_artifact_json(corrupted_bath)
        corrupted_payload["bath_artifact_file_sha256"] = bytes2hex(
            sha256(codeunits(corrupted_payload["bath_artifact_json"]))
        )
        corrupted["payload_json"] = canonical_request_json(corrupted_payload)
        corrupted["sha256"] =
            bytes2hex(sha256(codeunits(corrupted["payload_json"])))
        corrupted_path = joinpath(directory, "corrupted-bath.json")
        write(corrupted_path, JSON3.write(corrupted))
        @test_throws ArgumentError read_request(corrupted_path)

        invalid_expansion = deepcopy(valid)
        invalid_payload = strict_json_read(
            invalid_expansion["payload_json"], "invalid payload"
        )
        invalid_payload["solver_settings"]["krylov_expansion_dim"] = -1
        invalid_expansion["payload_json"] =
            canonical_request_json(invalid_payload)
        invalid_expansion["sha256"] = bytes2hex(
            sha256(codeunits(invalid_expansion["payload_json"]))
        )
        invalid_expansion_path =
            joinpath(directory, "invalid-expansion.json")
        write(invalid_expansion_path, JSON3.write(invalid_expansion))
        @test_throws ArgumentError read_request(invalid_expansion_path)

        wrong_hash_path = joinpath(directory, "wrong-hash.json")
        write(wrong_hash_path, JSON3.write(request))
        @test_throws ArgumentError read_request(wrong_hash_path)

        encoded = JSON3.write(request)
        duplicate = replace(
            encoded,
            "\"sha256\":\"$(repeat("0", 64))\"" =>
                "\"sha256\":\"$(repeat("0", 64))\"," *
                "\"sha256\":\"$(repeat("0", 64))\"",
            count = 1,
        )
        duplicate_path = joinpath(directory, "duplicate.json")
        write(duplicate_path, duplicate)
        @test_throws ArgumentError read_request(duplicate_path)
    end
end
