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
end
