using Test

if !isdefined(@__MODULE__, :Challenge148)
    include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
end
using .Challenge148

@testset "cluster task is immutable and deterministic" begin
    task = ClusterTask(
        1, :triangle, 8, 1.0, 4.76811, 1.0, 1,
        UInt64(148001), 100, 200, 20, 5, "runs/test.json",
    )

    @test isimmutable(task)
    @test validate_task(task) === task
    @test task_hash(task) == task_hash(task)
    @test task_id(task) == "ra-triangle-L0008-r001-" * task_hash(task)[1:8]
    @test canonical_task_string(task) ==
          "schema_version=1|lattice=triangle|L=8|J=f64:3ff0000000000000|" *
          "h=f64:4013128b6d86ec18|c=f64:3ff0000000000000|replica=1|" *
          "seed=u64:0000000000024221|thermalization_sweeps=100|" *
          "measurement_sweeps=200|base_bin_size=20|checkpoint_interval_bins=5|" *
          "output_path=utf8:72756e732f746573742e6a736f6e"

    bad = ClusterTask(
        1, :triangle, 8, 1.0, 0.0, 1.0, 1,
        UInt64(148001), 100, 200, 20, 5, "runs/test.json",
    )
    @test_throws ArgumentError validate_task(bad)
end

@testset "task schema validation rejects invalid inputs" begin
    base = ClusterTask(
        1, :triangle, 8, 1.0, 4.76811, 1.0, 1,
        UInt64(148001), 100, 200, 20, 5, "runs/test.json",
    )
    invalid = (
        ClusterTask(2, :triangle, 8, 1.0, 4.76811, 1.0, 1, UInt64(1), 0, 20, 5, 1, "x"),
        ClusterTask(1, :square, 8, 1.0, 4.76811, 1.0, 1, UInt64(1), 0, 20, 5, 1, "x"),
        ClusterTask(1, :triangle, 2, 1.0, 4.76811, 1.0, 1, UInt64(1), 0, 20, 5, 1, "x"),
        ClusterTask(1, :triangle, 8, -1.0, 4.76811, 1.0, 1, UInt64(1), 0, 20, 5, 1, "x"),
        ClusterTask(1, :triangle, 8, 1.0, Inf, 1.0, 1, UInt64(1), 0, 20, 5, 1, "x"),
        ClusterTask(1, :triangle, 8, 1.0, 4.76811, 0.0, 1, UInt64(1), 0, 20, 5, 1, "x"),
        ClusterTask(1, :triangle, 8, 1.0, 4.76811, 1.0, 0, UInt64(1), 0, 20, 5, 1, "x"),
        ClusterTask(1, :triangle, 8, 1.0, 4.76811, 1.0, 1, UInt64(0), 0, 20, 5, 1, "x"),
        ClusterTask(1, :triangle, 8, 1.0, 4.76811, 1.0, 1, UInt64(1), -1, 20, 5, 1, "x"),
        ClusterTask(1, :triangle, 8, 1.0, 4.76811, 1.0, 1, UInt64(1), 0, 21, 5, 1, "x"),
        ClusterTask(1, :triangle, 8, 1.0, 4.76811, 1.0, 1, UInt64(1), 0, 20, 0, 1, "x"),
        ClusterTask(1, :triangle, 8, 1.0, 4.76811, 1.0, 1, UInt64(1), 0, 20, 5, 0, "x"),
        ClusterTask(1, :triangle, 8, 1.0, 4.76811, 1.0, 1, UInt64(1), 0, 20, 5, 1, ""),
    )
    @test all(task -> try
        validate_task(task)
        false
    catch error
        error isa ArgumentError
    end, invalid)
    @test validate_task(base) === base
end

@testset "task serialization and seed derivation are reproducible" begin
    task = ClusterTask(
        1, :honeycomb, 8, 1.0, -2.1325, 1.5, 2,
        UInt64(148002), 0, 200, 20, 5, "runs/negative-field.json",
    )
    @test beta_for_aspect(task.h, task.L; c=task.c) == beta_for_aspect(2.1325, 8; c=1.5)
    @test canonical_task_string(task) != canonical_task_string(ClusterTask(
        1, :honeycomb, 8, 1.0, 2.1325, 1.5, 2,
        UInt64(148002), 0, 200, 20, 5, "runs/negative-field.json",
    ))
    @test task_seed(:route_a, :honeycomb, 8, -2.1325, 1.5, 2) !=
          task_seed(:route_a, :honeycomb, 8, 2.1325, 1.5, 2)
    @test task_seed(:route_a, :honeycomb, 8, -2.1325, 1.5, 2) ==
          task_seed(:route_a, :honeycomb, 8, -2.1325, 1.5, 2)
    @test task_seed(:route_a, :honeycomb, 8, -2.1325, 1.5, 2) ==
          UInt64(0x631d10620da2ed0b)
    @test task_seed(:honeycomb, 8, -2.1325, 1.5, 2) ==
          task_seed(:route_a, :honeycomb, 8, -2.1325, 1.5, 2)

    mktempdir() do dir
        path = joinpath(dir, "task.json")
        @test write_task(path, task) == path
        @test read_task(path) == task
    end

    seeds = Set{UInt64}()
    for replica in 1:10_000
        push!(seeds, task_seed(:route_a, :triangle, 8, 4.76811, 1.0, replica))
    end
    @test length(seeds) == 10_000
    @test all(!iszero, seeds)
end
