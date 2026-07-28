include(joinpath(
    @__DIR__,
    "..",
    "scripts",
    "solve_square_primal_mof.jl",
))

@testset "Square primal smoke solver configuration" begin
    mock_backend = JuMP.MOI.Utilities.UniversalFallback(
        JuMP.MOI.Utilities.Model{Float64}(),
    )
    model = JuMP.Model(
        () -> JuMP.MOI.Utilities.MockOptimizer(mock_backend),
    )

    @test MOSEK_NUM_THREADS_ATTRIBUTE == "MSK_IPAR_NUM_THREADS"
    @test set_mosek_num_threads!(model, 3) === nothing
    @test JuMP.get_optimizer_attribute(
        model,
        MOSEK_NUM_THREADS_ATTRIBUTE,
    ) == 3
    @test_throws ArgumentError set_mosek_num_threads!(model, 0)

    @test MOSEK_SOLVE_FORM_ATTRIBUTE == "MSK_IPAR_INTPNT_SOLVE_FORM"
    @test set_mosek_dual_solve_form!(model) === nothing
    @test JuMP.get_optimizer_attribute(
        model,
        MOSEK_SOLVE_FORM_ATTRIBUTE,
    ) == Int(Mosek.MSK_SOLVE_DUAL.value)

    options = parse_args([
        "--model",
        "model.mof.json",
        "--runmeta",
        "runmeta.toml",
        "--output",
        "result.toml",
        "--expected-basis-family",
        "bare_weight_one",
        "--expected-positive-dimension",
        "28",
        "--expected-gap-dimension",
        "4",
        "--time-limit-seconds",
        "600",
        "--threads",
        "4",
    ])
    @test options.expected_basis_family == "bare_weight_one"
    @test options.expected_positive_dimension == 28
    @test options.expected_gap_dimension == 4
    @test options.time_limit_seconds == 600
    @test options.threads == 4
    @test_throws ArgumentError parse_args([
        "--model",
        "model.mof.json",
        "--runmeta",
        "runmeta.toml",
        "--output",
        "result.toml",
    ])
end
