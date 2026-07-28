using Test
using JSON3

include(joinpath(@__DIR__, "..", "finite_bath_mps_runner.jl"))

function minimal_runner_request()
    gamma = 0.1
    bandwidth = 1.0
    n_bath = 2
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
        "schema_version" => 2,
        "bath_artifact_json" => bath_json,
        "bath_artifact_file_sha256" => bytes2hex(sha256(codeunits(bath_json))),
        "checkpoint" => Dict(
            "checkpoint_schema" => 1,
            "writer_version" => "1.0.0",
            "source_hashes" => Dict(
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
