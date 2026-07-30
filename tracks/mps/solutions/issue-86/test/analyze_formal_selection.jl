using Test
using JSON

include(joinpath(@__DIR__, "..", "analyze_formal.jl"))

function analysis_row(
        cell_id;
        normalized_variance,
        residual,
        stage = "stage2",
        resource_class = "A",
    )
    return Dict{String, Any}(
        "cell_id" => cell_id,
        "stage" => stage,
        "resource_class" => resource_class,
        "model" => "long_range",
        "sigma" => 1.75,
        "L" => 32,
        "Gamma" => 1.56,
        "chi" => 64,
        "poles" => 16,
        "gap" => nothing,
        "E0" => -1.0,
        "ground_variance" => normalized_variance,
        "normalized_ground_variance" => normalized_variance,
        "convergence_residual" => residual,
    )
end

function write_raw_rows(path, rows)
    open(path, "w") do io
        JSON.print(io, Dict("rows" => rows), 2)
        println(io)
    end
end

@testset "Convergence failures retain cell provenance" begin
    audit = convergence_audit([
        analysis_row(
            "failed-cell";
            normalized_variance = 2.0e-10,
            residual = 1.0e-9,
            stage = "stage1",
            resource_class = "A",
        ),
    ])

    @test !audit["passes"]
    @test length(audit["failures"]) == 1
    failure = only(audit["failures"])
    @test failure["cell_id"] == "failed-cell"
    @test failure["stage"] == "stage1"
    @test failure["resource_class"] == "A"
    @test failure["excited"] == false
end

@testset "Passing retry supersedes a lower-residual variance failure" begin
    mktempdir() do directory
        old_path = joinpath(directory, "old.json")
        retry_path = joinpath(directory, "retry.json")
        write_raw_rows(old_path, [
            analysis_row(
                "old-failure";
                normalized_variance = 2.0e-10,
                residual = 1.0e-12,
            ),
        ])
        write_raw_rows(retry_path, [
            analysis_row(
                "strict-retry";
                normalized_variance = 5.0e-11,
                residual = 2.0e-12,
                stage = "stage2-followup-r1",
            ),
        ])

        selected = load_rows([old_path, retry_path])

        @test length(selected) == 1
        @test only(selected)["cell_id"] == "strict-retry"
    end
end
