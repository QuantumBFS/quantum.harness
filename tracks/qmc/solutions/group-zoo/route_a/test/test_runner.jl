using Test
using JSON

if !isdefined(@__MODULE__, :Challenge148)
    include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
end
using .Challenge148

module RunnerArgumentHarness
include(joinpath(@__DIR__, "..", "scripts", "run_cluster.jl"))
end

const _RUNNER_SCRIPT = joinpath(@__DIR__, "..", "scripts", "run_cluster.jl")
const _PROJECT_ROOT = normpath(joinpath(@__DIR__, ".."))

function _fixture_task(output_path::String)
    fixture = read_task(joinpath(@__DIR__, "fixtures", "tiny_triangle_task.json"))
    return ClusterTask(
        fixture.schema_version,
        fixture.lattice,
        fixture.L,
        fixture.J,
        fixture.h,
        fixture.c,
        fixture.replica,
        fixture.seed,
        fixture.thermalization_sweeps,
        fixture.measurement_sweeps,
        fixture.base_bin_size,
        fixture.checkpoint_interval_bins,
        output_path,
    )
end

function _with_field(task::ClusterTask, h::Float64)
    return ClusterTask(
        task.schema_version,
        task.lattice,
        task.L,
        task.J,
        h,
        task.c,
        task.replica,
        task.seed,
        task.thermalization_sweeps,
        task.measurement_sweeps,
        task.base_bin_size,
        task.checkpoint_interval_bins,
        task.output_path,
    )
end

function _run_cli(task_path::String, args::String...)
    cmd = `$(Base.julia_cmd()) --project=$_PROJECT_ROOT $_RUNNER_SCRIPT --task $task_path $args`
    return success(pipeline(cmd; stdout=devnull, stderr=devnull))
end

function _raw_bin_bytes(result)
    io = IOBuffer()
    JSON.print(io, result["raw_bins"])
    return take!(io)
end

function _write_json(path::String, value)
    open(path, "w") do io
        JSON.print(io, value)
    end
    return path
end

function _save_matching_runner_checkpoint(task_path::String)
    runner = RunnerArgumentHarness
    task = runner.Challenge148.read_task(task_path)
    state = runner.Challenge148.CWAState(
        runner.Challenge148.lattice_geometry(task.lattice, task.L);
        J=task.J,
        h=task.h,
        beta=runner.Challenge148.beta_for_aspect(task.h, task.L; c=task.c),
        seed=task.seed,
    )
    runner.Challenge148.thermalize!(state, task.thermalization_sweeps)
    runner.Challenge148.save_checkpoint(
        task.output_path * ".checkpoint",
        task,
        state,
        runner.Challenge148.BinRecord[];
        git_commit=runner._git_commit(),
        manifest_hash=runner._manifest_hash(),
    )
    return task.output_path * ".checkpoint"
end

@testset "runner accepts only its declared command-line grammar" begin
    @test RunnerArgumentHarness.parse_runner_args(["--task", "task.json"]) ==
          (task_path = "task.json", stop_after_bins = nothing)
    @test RunnerArgumentHarness.parse_runner_args(
        ["--task", "task.json", "--stop-after-bins", "4"],
    ) == (task_path = "task.json", stop_after_bins = 4)
    @test_throws ArgumentError RunnerArgumentHarness.parse_runner_args(String[])
    @test_throws ArgumentError RunnerArgumentHarness.parse_runner_args(["--task", "task.json", "--task", "again.json"])
    @test_throws ArgumentError RunnerArgumentHarness.parse_runner_args(["--stop-after-bins", "4", "--task", "task.json"])
    @test_throws ArgumentError RunnerArgumentHarness.parse_runner_args(["--task", "task.json", "--stop-after-bins", "-1"])
    @test_throws ArgumentError RunnerArgumentHarness.parse_runner_args(["--task", "task.json", "--unknown", "x"])
end

@testset "runner accepts a validated archived-release commit" begin
    release_commit = "1234567890abcdef1234567890abcdef12345678"
    @test withenv("CHALLENGE148_RELEASE_COMMIT" => release_commit) do
        RunnerArgumentHarness._git_commit()
    end == release_commit
    @test_throws ArgumentError withenv(
        "CHALLENGE148_RELEASE_COMMIT" => "not-a-commit",
    ) do
        RunnerArgumentHarness._git_commit()
    end
end

@testset "completed-result verification rejects incomplete or tampered schemas" begin
    mktempdir() do dir
        task = _fixture_task(joinpath(dir, "result.json"))
        task_path = joinpath(dir, "task.json")
        write_task(task_path, task)
        @test RunnerArgumentHarness.run_cluster_task(task_path) == task.output_path
        original = JSON.parsefile(task.output_path; dicttype=Dict)
        checkpoint_path = _save_matching_runner_checkpoint(task_path)
        checkpoint_bytes = read(checkpoint_path)

        mutations = [
            result -> pop!(result, "algorithm"),
            result -> pop!(result, "physics"),
            result -> pop!(result, "estimates"),
            result -> (result["estimates"]["energy_per_site"]["mean"] += 1.0),
            result -> (result["task"]["L"] = 4),
            result -> (result["provenance"]["julia_version"] = "tampered"),
            result -> (result["raw_bins"]["cut_histogram"][1]["counts"][1] += 1),
        ]
        for mutate in mutations
            damaged = deepcopy(original)
            mutate(damaged)
            _write_json(task.output_path, damaged)
            @test_throws ArgumentError RunnerArgumentHarness.run_cluster_task(task_path)
            @test read(checkpoint_path) == checkpoint_bytes
        end
    end
end

@testset "completed-result verification tolerates JSON roundoff in derived estimates" begin
    mktempdir() do dir
        task = _fixture_task(joinpath(dir, "result.json"))
        task_path = joinpath(dir, "task.json")
        write_task(task_path, task)
        @test RunnerArgumentHarness.run_cluster_task(task_path) == task.output_path

        rounded = JSON.parsefile(task.output_path; dicttype=Dict)
        stderr = Float64(rounded["estimates"]["m_equal4"]["stderr"])
        rounded["estimates"]["m_equal4"]["stderr"] = nextfloat(nextfloat(stderr))
        _write_json(task.output_path, rounded)

        @test RunnerArgumentHarness.run_cluster_task(task_path) == task.output_path
    end
end

@testset "runner preserves dangling result and checkpoint symlink sentinels" begin
    mktempdir() do dir
        result_path = joinpath(dir, "result.json")
        result_target = joinpath(dir, "missing-result-target")
        symlink(result_target, result_path)
        result_task = _fixture_task(result_path)
        result_task_path = joinpath(dir, "result-task.json")
        write_task(result_task_path, result_task)
        @test islink(result_path)
        @test !ispath(result_path)
        @test_throws ArgumentError RunnerArgumentHarness.run_cluster_task(result_task_path)
        @test islink(result_path)
        @test readlink(result_path) == result_target

        checkpoint_task = _fixture_task(joinpath(dir, "checkpoint-result.json"))
        checkpoint_task_path = joinpath(dir, "checkpoint-task.json")
        write_task(checkpoint_task_path, checkpoint_task)
        checkpoint_path = checkpoint_task.output_path * ".checkpoint"
        checkpoint_target = joinpath(dir, "missing-checkpoint-target")
        symlink(checkpoint_target, checkpoint_path)
        @test islink(checkpoint_path)
        @test !ispath(checkpoint_path)
        @test_throws ArgumentError RunnerArgumentHarness.run_cluster_task(
            checkpoint_task_path; stop_after_bins=0)
        @test islink(checkpoint_path)
        @test readlink(checkpoint_path) == checkpoint_target
        @test !ispath(checkpoint_task.output_path)
    end
end

@testset "cluster CLI completes one immutable task" begin
    mktempdir() do dir
        task = _fixture_task(joinpath(dir, "result.json"))
        task_path = joinpath(dir, "task.json")
        write_task(task_path, task)

        @test _run_cli(task_path)
        result = JSON.parsefile(task.output_path)
        @test result["status"] == "complete"
        @test result["completed_bins"] == 8
        @test result["task_hash"] == task_hash(read_task(task_path))
        @test haskey(result, "completion_checksum")
        @test haskey(result, "provenance")
        @test result["physics"]["h_input"] == task.h
        @test result["physics"]["h_simulated"] == abs(task.h)
        @test sort(collect(keys(result["raw_bins"]))) == sort([
            "energy_per_site", "m_time2", "m_time4", "m_equal2", "m_equal4", "cuts_mean",
            "cut_histogram",
        ])
        @test length(result["raw_bins"]["cut_histogram"]) == result["completed_bins"]
        @test all(histogram -> sum(histogram["counts"]) == task.base_bin_size,
            result["raw_bins"]["cut_histogram"])
        @test !ispath(task.output_path * ".checkpoint")
    end
end

@testset "controlled exit resumes byte-identical raw bins" begin
    mktempdir() do dir
        reference_task = _fixture_task(joinpath(dir, "reference.json"))
        reference_path = joinpath(dir, "reference-task.json")
        write_task(reference_path, reference_task)
        @test RunnerArgumentHarness.run_cluster_task(reference_path) == reference_task.output_path
        reference = JSON.parsefile(reference_task.output_path)

        resumed_task = _fixture_task(joinpath(dir, "resumed.json"))
        resumed_path = joinpath(dir, "resumed-task.json")
        write_task(resumed_path, resumed_task)
        @test RunnerArgumentHarness.run_cluster_task(resumed_path; stop_after_bins=4) === nothing
        @test isfile(resumed_task.output_path * ".checkpoint")
        @test !ispath(resumed_task.output_path)

        foreign_checkpoint_task = _with_field(resumed_task, 4.5)
        foreign_checkpoint_path = joinpath(dir, "foreign-checkpoint-task.json")
        write_task(foreign_checkpoint_path, foreign_checkpoint_task)
        checkpoint_bytes = read(resumed_task.output_path * ".checkpoint")
        @test_throws ArgumentError RunnerArgumentHarness.run_cluster_task(foreign_checkpoint_path)
        @test read(resumed_task.output_path * ".checkpoint") == checkpoint_bytes

        unrotated_task = _fixture_task(joinpath(dir, "unrotated.json"))
        unrotated_path = joinpath(dir, "unrotated-task.json")
        write_task(unrotated_path, unrotated_task)
        @test RunnerArgumentHarness.run_cluster_task(unrotated_path; stop_after_bins=2) === nothing
        foreign_unrotated_task = _with_field(unrotated_task, 4.5)
        foreign_unrotated_path = joinpath(dir, "foreign-unrotated-task.json")
        write_task(foreign_unrotated_path, foreign_unrotated_task)
        unrotated_checkpoint_bytes = read(unrotated_task.output_path * ".checkpoint")
        @test_throws ArgumentError RunnerArgumentHarness.run_cluster_task(foreign_unrotated_path)
        @test read(unrotated_task.output_path * ".checkpoint") == unrotated_checkpoint_bytes

        zero_task = _fixture_task(joinpath(dir, "zero-stop.json"))
        zero_path = joinpath(dir, "zero-stop-task.json")
        write_task(zero_path, zero_task)
        @test RunnerArgumentHarness.run_cluster_task(zero_path; stop_after_bins=0) === nothing
        @test isfile(zero_task.output_path * ".checkpoint")
        @test !ispath(zero_task.output_path)

        @test RunnerArgumentHarness.run_cluster_task(resumed_path) == resumed_task.output_path
        resumed = JSON.parsefile(resumed_task.output_path)
        @test resumed["completed_bins"] == 8
        @test _raw_bin_bytes(resumed) == _raw_bin_bytes(reference)
        @test !ispath(resumed_task.output_path * ".checkpoint")
        @test !ispath(resumed_task.output_path * ".checkpoint.previous")

        foreign_result_task = _with_field(resumed_task, 4.5)
        foreign_result_path = joinpath(dir, "foreign-result-task.json")
        write_task(foreign_result_path, foreign_result_task)
        result_bytes = read(resumed_task.output_path)
        @test_throws ArgumentError RunnerArgumentHarness.run_cluster_task(foreign_result_path)
        @test read(resumed_task.output_path) == result_bytes
    end
end
