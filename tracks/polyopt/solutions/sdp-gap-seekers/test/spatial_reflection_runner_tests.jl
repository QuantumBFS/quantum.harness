using Test
using JuMP

const TRACK_ROOT = normpath(joinpath(@__DIR__, ".."))
include(joinpath(
    TRACK_ROOT,
    "scripts",
    "solve_shastry_sutherland_spatial_reflection_reduced_mof.jl",
))

function rational_metadata_for_test(
    numerator::String,
    denominator::String,
)
    value = parse(BigInt, numerator) // parse(BigInt, denominator)
    return Dict(
        "numerator" => numerator,
        "denominator" => denominator,
        "canonical" => string(value),
        "float64" => Float64(value),
    )
end

function top_level_runmeta_for_test(
    input_files;
    gamma_numerator="0",
    gamma_denominator="1",
)
    return Dict(
        "schema_version" => RUNMETA_SCHEMA,
        "claim_level" =>
            "solver_free_exact_equivalent_spatial_reflection_real_reduction",
        "solver_invoked" => false,
        "optimizer_attached" => false,
        "output_relative" => input_files.output_relative,
        "mof" => Dict(
            "filename" => "model.mof.json",
            "sha256" => input_files.model_sha256,
        ),
        "setup" => Dict(
            "model" => "shastry-sutherland",
            "patch_level" => 1,
            "degree_d" => 2,
            "state_class" => "unrestricted",
            "physical_boundary_condition" =>
                "none-local-consistency-window",
            "g_square_over_dimer" =>
                rational_metadata_for_test("4", "5"),
            "gamma" => rational_metadata_for_test(
                gamma_numerator,
                gamma_denominator,
            ),
        ),
    )
end

function structural_model_for_test(; omit_name=nothing)
    model = JuMP.Model()
    moments = JuMP.@variable(model, [1:1_711], base_name="test_moment")
    JuMP.@constraint(
        model,
        moments[1] == 1.0,
        base_name="normalization",
    )
    for (name, dimension) in EXPECTED_PSD_DIMENSIONS
        name == omit_name && continue
        matrix = [
            row == column ? 1.0 * moments[1] : 0.0 * moments[1]
            for row in 1:dimension, column in 1:dimension
        ]
        JuMP.@constraint(
            model,
            Symmetric(matrix) in JuMP.PSDCone(),
            base_name=name,
        )
    end
    return model
end

@testset "spatial solve runner metadata boundaries" begin
    input_files = (
        model_sha256=repeat("a", 64),
        runmeta_sha256=repeat("b", 64),
        checksums_sha256=repeat("c", 64),
        output_relative="results/test-input",
    )
    valid = top_level_runmeta_for_test(input_files)
    @test isnothing(validate_top_level_metadata(
        valid,
        input_files,
        "0//1",
    ))

    wrong_schema = deepcopy(valid)
    wrong_schema["schema_version"] =
        "shastry-sutherland-full-spin-isotypic-real-mof-runmeta-v1"
    @test_throws ErrorException validate_top_level_metadata(
        wrong_schema,
        input_files,
        "0//1",
    )

    wrong_gamma = deepcopy(valid)
    wrong_gamma["setup"]["gamma"] =
        rational_metadata_for_test("1", "2")
    @test_throws ErrorException validate_top_level_metadata(
        wrong_gamma,
        input_files,
        "0//1",
    )

    passed_diagnostics = Dict("passed" => true)
    @test classify_spatial_result(
        JuMP.MOI.OPTIMAL,
        JuMP.MOI.FEASIBLE_POINT,
        JuMP.MOI.FEASIBLE_POINT,
        passed_diagnostics,
    ) == "feasible_residual_checked_float"
    @test classify_spatial_result(
        JuMP.MOI.ALMOST_OPTIMAL,
        JuMP.MOI.NEARLY_FEASIBLE_POINT,
        JuMP.MOI.NEARLY_FEASIBLE_POINT,
        passed_diagnostics,
    ) == "unknown"
end

@testset "spatial solve runner immutable hashes" begin
    mktempdir() do repository_root
        input_directory = joinpath(repository_root, "results", "test-input")
        mkpath(input_directory)
        model_path = joinpath(input_directory, "model.mof.json")
        runmeta_path = joinpath(input_directory, "runmeta.toml")
        checksums_path = joinpath(input_directory, "SHA256SUMS")
        write(model_path, "model-v1")
        write(runmeta_path, "runmeta-v1")
        model_sha256 = B.file_sha256(model_path)
        runmeta_sha256 = B.file_sha256(runmeta_path)
        write(
            checksums_path,
            "$model_sha256  model.mof.json\n" *
            "$runmeta_sha256  runmeta.toml\n",
        )
        expected_inputs = Dict(
            "0//1" => (
                model_sha256=model_sha256,
                runmeta_sha256=runmeta_sha256,
                output_relative="results/test-input",
            ),
        )
        verified = validate_input_files(
            model_path,
            runmeta_path,
            checksums_path,
            "0//1",
            repository_root;
            expected_inputs=expected_inputs,
        )
        @test verified.model_sha256 == model_sha256
        @test verified.runmeta_sha256 == runmeta_sha256

        write(model_path, "tampered-model")
        @test_throws ErrorException validate_input_files(
            model_path,
            runmeta_path,
            checksums_path,
            "0//1",
            repository_root;
            expected_inputs=expected_inputs,
        )
        @test_throws ErrorException validate_input_files(
            model_path,
            runmeta_path,
            checksums_path,
            "1//2",
            repository_root;
            expected_inputs=expected_inputs,
        )
    end
end

@testset "spatial solve runner named-cone inventory" begin
    valid_model = structural_model_for_test()
    report = validate_reloaded_model(valid_model)
    @test report["passed"]
    @test report["variable_count"] == 1_711
    @test report["psd_constraint_count"] == 17
    @test report["real_psd_triangle_entries"] == 3_191
    @test report["max_psd_side_dimension"] == 24

    missing_name = first(sort!(collect(keys(EXPECTED_PSD_DIMENSIONS))))
    missing_model = structural_model_for_test(; omit_name=missing_name)
    @test_throws ErrorException validate_reloaded_model(missing_model)
end
