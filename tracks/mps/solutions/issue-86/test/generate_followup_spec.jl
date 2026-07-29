using Test
using JSON

const GENERATOR = joinpath(@__DIR__, "..", "generate_followup_spec.jl")

function write_json_fixture(path, payload)
    mkpath(dirname(path))
    open(path, "w") do io
        JSON.print(io, payload, 2)
        println(io)
    end
end

@testset "Follow-up generator entrypoint exists" begin
    @test isfile(GENERATOR)
end

if isfile(GENERATOR)
    include(GENERATOR)

    @testset "Adaptive and convergence retry cells form one run spec" begin
        mktempdir() do directory
            formal_directory = joinpath(directory, "formal")
            source_directory = joinpath(directory, "stage1")
            output_spec = joinpath(directory, "followup", "run_spec.json")
            reason_csv = joinpath(directory, "followup", "followup_reason.csv")

            source_job = Dict{String, Any}(
                "model" => "long_range",
                "sigma" => 1.75,
                "L" => 32,
                "gamma" => 1.56,
                "chi" => 64,
                "poles" => 16,
                "tolerance" => 1.0e-9,
                "maxiter" => 40,
                "excited" => false,
                "seed" => 86,
            )
            variance_only_job = merge(
                copy(source_job),
                Dict{String, Any}("gamma" => 1.565),
            )
            adaptive_job = Dict{String, Any}(
                "model" => "long_range",
                "sigma" => 2.0,
                "L" => 64,
                "gamma" => 1.425,
                "chi" => 128,
                "poles" => 16,
                "tolerance" => 1.0e-9,
                "maxiter" => 50,
                "excited" => false,
                "seed" => 86,
            )
            completed_adaptive_job = Dict{String, Any}(
                "model" => "long_range",
                "sigma" => 2.0,
                "L" => 32,
                "gamma" => 1.43,
                "chi" => 64,
                "poles" => 16,
                "tolerance" => 1.0e-9,
                "maxiter" => 40,
                "excited" => false,
                "seed" => 86,
            )

            write_json_fixture(
                joinpath(source_directory, "run_spec.json"),
                Dict(
                    "metadata" => Dict("run_id" => "stage1", "stage" => "stage1"),
                    "cells" => [
                        Dict(
                            "cell_id" => "source-failure",
                            "stage" => "stage1",
                            "resource_class" => "A",
                            "params" => source_job,
                        ),
                        Dict(
                            "cell_id" => "completed-adaptive",
                            "stage" => "stage1",
                            "resource_class" => "A",
                            "params" => completed_adaptive_job,
                        ),
                        Dict(
                            "cell_id" => "variance-only-failure",
                            "stage" => "stage1",
                            "resource_class" => "A",
                            "params" => variance_only_job,
                        ),
                    ],
                ),
            )
            write_json_fixture(
                joinpath(
                    source_directory,
                    "cells",
                    "completed-adaptive",
                    "manifest.json",
                ),
                Dict(
                    "cell_id" => "completed-adaptive",
                    "stage" => "stage1",
                    "resource_class" => "A",
                    "status" => "success",
                    "params" => completed_adaptive_job,
                    "result" => Dict{String, Any}(),
                ),
            )
            write_json_fixture(
                joinpath(formal_directory, "formal_summary.json"),
                Dict(
                    "convergence_audit" => Dict(
                        "failures" => [Dict(
                            "cell_id" => "source-failure",
                            "stage" => "stage1",
                            "resource_class" => "A",
                            "model" => "long_range",
                            "sigma" => 1.75,
                            "L" => 32,
                            "Gamma" => 1.56,
                            "chi" => 64,
                            "poles" => 16,
                            "excited" => false,
                            "normalized_ground_variance" => 2.0e-10,
                            "convergence_residual" => 2.0e-8,
                        ), Dict(
                            "cell_id" => "variance-only-failure",
                            "stage" => "stage1",
                            "resource_class" => "A",
                            "model" => "long_range",
                            "sigma" => 1.75,
                            "L" => 32,
                            "Gamma" => 1.565,
                            "chi" => 64,
                            "poles" => 16,
                            "excited" => false,
                            "normalized_ground_variance" => 2.0e-10,
                            "convergence_residual" => 2.0e-9,
                        )],
                    ),
                ),
            )
            write_json_fixture(
                joinpath(formal_directory, "adaptive_run_spec.json"),
                Dict(
                    "metadata" => Dict(
                        "run_id" => "issue-86-adaptive",
                        "stage" => "adaptive",
                    ),
                    "cells" => [
                        Dict(
                            "cell_id" => "adaptive-source",
                            "stage" => "adaptive",
                            "resource_class" => "B",
                            "params" => adaptive_job,
                        ),
                        Dict(
                            "cell_id" => "completed-adaptive-source",
                            "stage" => "adaptive",
                            "resource_class" => "A",
                            "params" => completed_adaptive_job,
                        ),
                        Dict(
                            "cell_id" => "overlap-adaptive-source",
                            "stage" => "adaptive",
                            "resource_class" => "A",
                            "params" => source_job,
                        ),
                    ],
                ),
            )

            main([
                formal_directory,
                output_spec,
                reason_csv,
                "issue-86-stage2-followup-r1",
                "stage2-followup-r1",
                source_directory,
            ])

            spec = JSON.parsefile(output_spec)
            @test spec["metadata"]["run_id"] == "issue-86-stage2-followup-r1"
            @test spec["metadata"]["stage"] == "stage2-followup-r1"
            @test spec["metadata"]["jobs_total"] == 2
            @test !isempty(spec["metadata"]["created_utc"])
            @test !isempty(spec["metadata"]["code_commit"])
            @test occursin("Gamma", spec["metadata"]["hamiltonian"])
            @test occursin("periodic", spec["metadata"]["boundary"])
            @test spec["metadata"]["completed_adaptive_cells_skipped"] == 1
            @test spec["metadata"]["convergence_failure_source_cells"] == 2
            @test spec["metadata"]["convergence_retry_source_cells"] == 1
            @test spec["metadata"]["deferred_quality_source_cells"] == 1
            @test length(spec["cells"]) == 2
            @test count(cell -> cell["resource_class"] == "A", spec["cells"]) == 1
            @test count(cell -> cell["resource_class"] == "B", spec["cells"]) == 1
            @test all(
                cell -> cell["params"] != completed_adaptive_job,
                spec["cells"],
            )
            @test all(
                cell -> cell["stage"] == "stage2-followup-r1",
                spec["cells"],
            )

            retry = only(filter(
                cell -> cell["params"]["chi"] == 64,
                spec["cells"],
            ))
            @test retry["params"]["tolerance"] == 1.0e-11
            @test retry["params"]["maxiter"] == 80
            @test retry["params"]["seed"] == 86
            @test retry["params"]["excited"] == false

            adaptive = only(filter(
                cell -> cell["params"]["chi"] == 128,
                spec["cells"],
            ))
            @test adaptive["params"] == adaptive_job

            reason_lines = readlines(reason_csv)
            @test length(reason_lines) == 3
            @test startswith(reason_lines[1], "cell_id,resource_class,reason")
            @test count(line -> occursin("convergence_retry", line), reason_lines) == 1
            @test count(line -> occursin("adaptive", line), reason_lines) == 2
            @test count(
                line -> occursin("adaptive+convergence_retry", line),
                reason_lines,
            ) == 1

            deferred_csv = joinpath(
                dirname(reason_csv), "deferred_quality.csv"
            )
            deferred_lines = readlines(deferred_csv)
            @test length(deferred_lines) == 2
            @test startswith(
                deferred_lines[1],
                "source_cell_id,model,sigma,L,Gamma,chi,poles,excited",
            )
            @test occursin("variance-only-failure", deferred_lines[2])
            @test occursin("finite_chi_limit", deferred_lines[2])
            @test occursin("chi128_manual_review", deferred_lines[2])
            @test !any(
                cell -> cell["params"]["gamma"] == 1.565,
                spec["cells"],
            )
        end
    end
end
