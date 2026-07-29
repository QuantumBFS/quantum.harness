using Test
using JSON

const FINALIZER = joinpath(@__DIR__, "..", "finalize_track_b.jl")

function write_finalizer_fixture(path, payload)
    mkpath(dirname(path))
    open(path, "w") do io
        JSON.print(io, payload, 2)
        println(io)
    end
end

function sigma_fixture(sigma; bracket_width = 8.0e-4)
    reference = sigma == 1.75 ? 1.5609 : 1.4208
    reference_error = sigma == 1.75 ? 3.0e-4 : 2.0e-4
    return Dict{String, Any}(
        "sigma" => sigma,
        "estimate" => reference,
        "interval" => [reference - reference_error, reference + reference_error],
        "reference" => reference,
        "reference_error" => reference_error,
        "reference_interval" =>
            [reference - reference_error, reference + reference_error],
        "covers_reference_interval" => true,
        "crossing_bracket_refined" => bracket_width <= 1.0e-3,
        "components" => Dict(
            "chi" => 1.0e-4,
            "finite_size" => 2.0e-4,
            "interpolation" => bracket_width / 2,
            "mpo" => 1.0e-4,
        ),
        "total_error" => 8.0e-4,
        "largest_crossing" => Dict(
            "model" => "long_range",
            "sigma" => sigma,
            "chi" => 64,
            "poles" => 16,
            "L" => 32,
            "L_pair" => [32, 64],
            "Gamma_low" => reference - bracket_width / 2,
            "Gamma_high" => reference + bracket_width / 2,
            "Gamma_crossing" => reference,
            "interpolation_half_width" => bracket_width / 2,
        ),
        "size_fit" => Dict(
            "Gamma_c" => reference,
            "without_smallest" => Dict("Gamma_c" => reference),
        ),
    )
end

function crossing_fixtures(; bracket_width = 8.0e-4, movement = 5.0e-5)
    current = Dict{String, Any}[]
    previous = Dict{String, Any}[]
    for sigma in (1.75, 2.0)
        reference = sigma == 1.75 ? 1.5609 : 1.4208
        for L in (8, 16, 24, 32)
            row = Dict{String, Any}(
                "model" => "long_range",
                "sigma" => sigma,
                "chi" => 64,
                "poles" => 16,
                "L" => L,
                "L_pair" => [L, 2L],
                "Gamma_low" => reference - bracket_width / 2,
                "Gamma_high" => reference + bracket_width / 2,
                "Gamma_crossing" => reference,
                "interpolation_half_width" => bracket_width / 2,
            )
            push!(current, row)
            old = copy(row)
            old["Gamma_crossing"] = reference - movement
            push!(previous, old)
        end
    end
    return current, previous
end

function build_finalizer_fixture(
        directory;
        bracket_width = 8.0e-4,
        movement = 5.0e-5,
        convergence_failures = Dict{String, Any}[],
    )
    formal_directory = joinpath(directory, "formal-v2")
    previous_directory = joinpath(directory, "formal-v1")
    current_crossings, previous_crossings = crossing_fixtures(
        ; bracket_width, movement
    )
    summary = Dict{String, Any}(
        "status" => "formal reproduction",
        "adaptive_cells" => 0,
        "sigma_audits" => Dict(
            "1.75" => sigma_fixture(1.75; bracket_width),
            "2.0" => sigma_fixture(2.0; bracket_width),
        ),
        "nn_audit" => Dict("status" => "pass"),
        "convergence_audit" => Dict(
            "normalized_variance_tolerance" => 1.0e-10,
            "residual_tolerance" => 1.0e-8,
            "passes" => isempty(convergence_failures),
            "failures" => convergence_failures,
        ),
    )
    write_finalizer_fixture(
        joinpath(formal_directory, "formal_summary.json"), summary
    )
    write_finalizer_fixture(
        joinpath(formal_directory, "crossings.json"), current_crossings
    )
    write_finalizer_fixture(
        joinpath(previous_directory, "crossings.json"), previous_crossings
    )
    write_finalizer_fixture(
        joinpath(formal_directory, "adaptive_run_spec.json"),
        Dict(
            "metadata" => Dict(
                "schema_version" => 1,
                "run_id" => "issue-86-adaptive",
                "stage" => "adaptive",
                "jobs_total" => 0,
            ),
            "cells" => Any[],
        ),
    )
    return formal_directory, previous_directory
end

@testset "Issue 86 finalizer entrypoint exists" begin
    @test isfile(FINALIZER)
end

if isfile(FINALIZER)
    include(FINALIZER)

    @testset "All validation-floor gates yield a scoped formal status" begin
        mktempdir() do directory
            formal_directory, previous_directory =
                build_finalizer_fixture(directory)
            main([
                formal_directory,
                previous_directory,
                "486b2673baa11d44a1048fbf9fd36751189889d7",
                repeat("a", 64),
            ])

            validation = JSON.parsefile(
                joinpath(formal_directory, "validation_summary.json")
            )
            @test validation["status"] ==
                "formal reproduction of the Track B validation floor"
            @test all(values(validation["gates"]))
            @test validation["scope"]["full_track_b_complete"] == false
            @test Set(validation["scope"]["not_measured"]) == Set([
                "dynamic exponent z for the long-range model",
                "gamma/nu",
                "sigma=1.6",
                "sigma=1.8",
            ])
            @test validation["provenance"]["compute_commit"] ==
                "486b2673baa11d44a1048fbf9fd36751189889d7"
            @test validation["provenance"]["analyzer_sha256"] == repeat("a", 64)

            report = JSON.parsefile(joinpath(formal_directory, "report.json"))
            @test [section["title"] for section in report["sections"]] ==
                ["Challenge", "Approach", "Results", "Highlight"]
            @test occursin("validation floor", lowercase(report["lede"]))
            report_text = JSON.json(report)
            @test occursin("gamma/nu", report_text)
            @test occursin("z", report_text)

            run = JSON.parsefile(joinpath(formal_directory, "run.json"))
            @test run["scope"]["full_track_b_complete"] == false
            @test run["result"]["status"] == validation["status"]
        end
    end

    @testset "A wide bracket or excessive adjacent drift stays preliminary" begin
        for (width, movement, failed_gate) in (
                (2.0e-3, 5.0e-5, "largest_crossing_bracket"),
                (8.0e-4, 2.0e-4, "adjacent_round_drift"),
            )
            mktempdir() do directory
                formal_directory, previous_directory =
                    build_finalizer_fixture(
                        directory;
                        bracket_width = width,
                        movement = movement,
                    )
                main([
                    formal_directory,
                    previous_directory,
                    "486b2673baa11d44a1048fbf9fd36751189889d7",
                    repeat("b", 64),
                ])
                validation = JSON.parsefile(
                    joinpath(formal_directory, "validation_summary.json")
                )
                @test validation["status"] ==
                    "pipeline validation / finite-size preliminary result"
                @test validation["gates"][failed_gate] == false
            end
        end
    end

    @testset "A remaining convergence failure creates a chi=128 retry" begin
        mktempdir() do directory
            failure = Dict{String, Any}(
                "cell_id" => "failed-cell",
                "model" => "long_range",
                "sigma" => 1.75,
                "L" => 32,
                "Gamma" => 1.56,
                "chi" => 64,
                "poles" => 16,
                "excited" => false,
                "normalized_ground_variance" => 2.0e-10,
                "convergence_residual" => 2.0e-9,
            )
            formal_directory, previous_directory =
                build_finalizer_fixture(
                    directory; convergence_failures = [failure]
                )
            main([
                formal_directory,
                previous_directory,
                "486b2673baa11d44a1048fbf9fd36751189889d7",
                repeat("c", 64),
            ])

            retry = JSON.parsefile(
                joinpath(
                    formal_directory,
                    "next-recommendations",
                    "chi128_retry_run_spec.json",
                )
            )
            @test retry["metadata"]["jobs_total"] == 1
            params = only(retry["cells"])["params"]
            @test params["chi"] == 128
            @test params["tolerance"] == 1.0e-11
            @test params["maxiter"] == 100
            @test params["seed"] == 86

            recommendations = JSON.parsefile(
                joinpath(formal_directory, "next-recommendations.json")
            )
            @test recommendations["automatic_submission"] == false
            @test recommendations["tiers"]["chi128_retry"]["cells"] == 1
            @test recommendations["tiers"]["l128_contingency"]["cells"] > 0
            @test recommendations["tiers"]["chi256_last_resort"]["cells"] > 0

            reasons = readlines(
                joinpath(
                    formal_directory,
                    "next-recommendations",
                    "reason_map.csv",
                )
            )
            @test startswith(reasons[1], "cell_id,tier,reason")
            @test any(line -> occursin("chi128_retry", line), reasons[2:end])
            @test any(line -> occursin("l128_contingency", line), reasons[2:end])
            @test any(line -> occursin("chi256_last_resort", line), reasons[2:end])
        end
    end
end
