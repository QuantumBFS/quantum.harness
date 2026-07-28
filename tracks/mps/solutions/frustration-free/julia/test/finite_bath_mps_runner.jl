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
        "schema_version" => 1,
        "bath_artifact_json" => bath_json,
        "bath_artifact_file_sha256" => bytes2hex(sha256(codeunits(bath_json))),
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
