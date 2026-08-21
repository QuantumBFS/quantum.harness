@testset "calibration grid is complete and tie breaking is frozen" begin
    grid = calibration_grid((0.25, 0.5, 1.0, 2.0))
    @test length(grid) == 64
    @test length(unique(grid)) == 64
    @test ((0.25, 0.25, 0.25) in grid)
    @test ((2.0, 2.0, 2.0) in grid)

    candidates = [
        (multipliers=(1.0, 1.0, 1.0), ess_per_second=100.0, ergodic=true),
        (multipliers=(0.5, 0.5, 0.5), ess_per_second=99.0, ergodic=true),
        (multipliers=(0.25, 0.25, 0.25), ess_per_second=101.0, ergodic=false),
    ]
    selected = select_calibration(candidates)
    @test selected.multipliers == (0.5, 0.5, 0.5)
    @test selected.ess_per_second == 99.0
end

@testset "universal regression grid uses only the frozen calibration" begin
    config = Dict{String,Any}(
        "J" => 1.0,
        "selected_tau_multipliers" => [0.5, 0.5, 1.0],
        "replicas" => 4,
        "warmup_bins" => 32,
        "retained_bins" => 64,
        "visits_per_bin" => 1024,
        "checkpoint_every" => 8,
        "field_anchors" => [-1.0, -0.5, 0.0, 0.5, 1.0],
        "systems" => Dict(
            "chain" => Dict(
                "sizes" => [8, 12, 16, 24, 32], "hc_anchor" => 1.0,
                "yt" => 1.0, "yi" => -1.0,
            ),
            "square" => Dict(
                "sizes" => [6, 8, 10, 12, 16], "hc_anchor" => 3.044330,
                "yt" => 1.5873, "yi" => -0.83,
            ),
        ),
    )
    tasks = make_universal_regression_tasks(config)
    @test length(tasks) == 200
    @test length(unique(task_hash.(tasks))) == 200
    @test count(task -> task.lattice == :chain, tasks) == 100
    @test count(task -> task.lattice == :square, tasks) == 100
    @test all(task.tau_multipliers == (0.5, 0.5, 1.0) for task in tasks)
    @test all(task.purpose == :universal_regression for task in tasks)
    chain_fields = sort!(unique(task.h for task in tasks if task.lattice == :chain && task.L == 8))
    @test chain_fields == [0.875, 0.9375, 1.0, 1.0625, 1.125]
end

@testset "regression calibration tasks cover both universal checks" begin
    config = Dict{String,Any}(
        "J" => 1.0,
        "multiplier_values" => [0.25, 0.5, 1.0, 2.0],
        "replicas" => 2,
        "warmup_bins" => 8,
        "retained_bins" => 16,
        "visits_per_bin" => 256,
        "checkpoint_every" => 4,
        "systems" => Dict(
            "chain" => Dict("L" => 16, "h" => 1.0, "c" => 1.0),
            "square" => Dict("L" => 8, "h" => 3.044330, "c" => 1.0),
        ),
    )
    tasks = make_regression_calibration_tasks(config)
    @test length(tasks) == 256
    @test length(unique(task_hash.(tasks))) == 256
    @test count(task -> task.lattice == :chain, tasks) == 128
    @test count(task -> task.lattice == :square, tasks) == 128
    @test Set(task.tau_multipliers for task in tasks) == Set(calibration_grid((0.25, 0.5, 1.0, 2.0)))
    @test all(task.purpose == :regression_calibration for task in tasks)
end

@testset "calibration multipliers use the frozen beta field and coordination scale" begin
    task = TaskSpec(
        lattice=:square, L=8, J=1.0, h=3.04433, beta_over_L=1.0, seed=1,
        kernel=:huang, tau_multipliers=(0.25, 0.5, 1.0), warmup_bins=1,
        retained_bins=2, visits_per_bin=20, checkpoint_every=1,
        purpose=:regression_calibration,
    )
    parameters = task_worm_parameters(task)
    @test parameters.tau_a ≈ 0.25 * 0.25
    @test parameters.tau_b ≈ 0.5 * 0.25
    @test parameters.tau_c ≈ 1.0 * 0.25
end

@testset "calibration rejects unusable candidate tables" begin
    @test_throws ArgumentError select_calibration(NamedTuple[])
    @test_throws ArgumentError select_calibration([
        (multipliers=(1.0, 1.0, 1.0), ess_per_second=10.0, ergodic=false),
    ])
    @test_throws ArgumentError select_calibration([
        (multipliers=(1.0, 1.0, 1.0), ess_per_second=NaN, ergodic=true),
    ])
end
