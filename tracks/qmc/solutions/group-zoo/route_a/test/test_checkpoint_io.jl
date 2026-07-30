using Test
using JSON

if !isdefined(@__MODULE__, :Challenge148)
    include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
end
using .Challenge148

function checkpoint_fixture(dir; L=3, seed=UInt64(148401))
    task = ClusterTask(
        1, :triangle, L, 1.0, 4.76811, 1.0, 1,
        seed, 10, 40, 5, 2, joinpath(dir, "result.json"),
    )
    state = CWAState(lattice_geometry(:triangle, L);
        J=task.J, h=task.h, beta=task.c * task.L / abs(task.h), seed=task.seed)
    thermalize!(state, 10)
    return task, state
end

function sentinel_directory(path)
    mkdir(path)
    sentinel = joinpath(path, "keep")
    write(sentinel, "sentinel")
    return sentinel
end

@testset "checkpoint resume is exact and version guarded" begin
    mktempdir() do dir
        task = ClusterTask(
            1, :triangle, 3, 1.0, 4.76811, 1.0, 1,
            UInt64(148401), 10, 40, 5, 2, joinpath(dir, "result.json"),
        )
        state = CWAState(lattice_geometry(:triangle, 3);
            J=1.0, h=task.h, beta=task.c * task.L / abs(task.h), seed=task.seed)
        thermalize!(state, 10)
        bins = run_bins!(state, 2, 5)
        uninterrupted = deepcopy(state)
        expected_next = run_bins!(uninterrupted, 4, 5)
        path = joinpath(dir, "state.checkpoint")

        save_checkpoint(path, task, state, bins; git_commit="abc123", manifest_hash="m1")
        restored = load_checkpoint(path, task; git_commit="abc123", manifest_hash="m1")

        @test restored.bins == bins
        @test getfield.(restored.state.worldlines, :spin0) ==
              getfield.(state.worldlines, :spin0)
        @test getfield.(restored.state.worldlines, :cuts) ==
              getfield.(state.worldlines, :cuts)
        @test restored.state.rng == state.rng
        @test run_bins!(restored.state, 4, 5) == expected_next
        @test getfield.(restored.state.worldlines, :spin0) ==
              getfield.(uninterrupted.worldlines, :spin0)
        @test getfield.(restored.state.worldlines, :cuts) ==
              getfield.(uninterrupted.worldlines, :cuts)
        @test restored.state.rng == uninterrupted.rng
        mismatched_task = ClusterTask(
            1, :triangle, 3, 1.0, 4.76811, 1.0, 2,
            UInt64(148402), 10, 40, 5, 2, joinpath(dir, "other-result.json"),
        )
        @test_throws ArgumentError load_checkpoint(
            path, mismatched_task; git_commit="abc123", manifest_hash="m1")
        @test_throws ArgumentError load_checkpoint(
            path, task; git_commit="different", manifest_hash="m1")
        @test_throws ArgumentError load_checkpoint(
            path, task; git_commit="abc123", manifest_hash="different")

        saved_bins = vcat(bins, run_bins!(state, 1, 5))
        save_checkpoint(path, task, state, saved_bins; git_commit="abc123", manifest_hash="m1")
        @test load_checkpoint(path, task;
            git_commit="abc123", manifest_hash="m1").bins == saved_bins
        @test load_checkpoint(path * ".previous", task;
            git_commit="abc123", manifest_hash="m1").bins == bins
        @test !any(endswith(".partial"), readdir(dir))
    end
end

@testset "checkpoint paths reject non-files without destroying sentinels" begin
    mktempdir() do dir
        task, state = checkpoint_fixture(dir)
        bins = run_bins!(state, 1, 5)
        checkpoint_dir = joinpath(dir, "checkpoint-directory")
        checkpoint_sentinel = sentinel_directory(checkpoint_dir)
        @test_throws ArgumentError save_checkpoint(
            checkpoint_dir, task, state, bins; git_commit="abc123", manifest_hash="m1")
        @test isdir(checkpoint_dir)
        isdir(checkpoint_dir) && @test read(checkpoint_sentinel, String) == "sentinel"

        result_dir = joinpath(dir, "result-directory")
        result_sentinel = sentinel_directory(result_dir)
        @test_throws ArgumentError atomic_write_json(result_dir, (status="complete",))
        @test isdir(result_dir)
        isdir(result_dir) && @test read(result_sentinel, String) == "sentinel"

        path = joinpath(dir, "state.checkpoint")
        save_checkpoint(path, task, state, bins; git_commit="abc123", manifest_hash="m1")
        previous_dir = path * ".previous"
        previous_sentinel = sentinel_directory(previous_dir)
        original = read(path)
        @test_throws ArgumentError save_checkpoint(
            path, task, state, bins; git_commit="abc123", manifest_hash="m1")
        @test read(path) == original
        @test isdir(previous_dir)
        isdir(previous_dir) && @test read(previous_sentinel, String) == "sentinel"

        dangling_checkpoint = joinpath(dir, "dangling.checkpoint")
        dangling_checkpoint_target = joinpath(dir, "missing-checkpoint-target")
        symlink(dangling_checkpoint_target, dangling_checkpoint)
        @test !ispath(dangling_checkpoint)
        @test islink(dangling_checkpoint)
        @test_throws ArgumentError save_checkpoint(
            dangling_checkpoint, task, state, bins; git_commit="abc123", manifest_hash="m1")
        @test islink(dangling_checkpoint)
        @test readlink(dangling_checkpoint) == dangling_checkpoint_target

        dangling_result = joinpath(dir, "dangling-result.json")
        dangling_result_target = joinpath(dir, "missing-result-target")
        symlink(dangling_result_target, dangling_result)
        @test !ispath(dangling_result)
        @test islink(dangling_result)
        @test_throws ArgumentError atomic_write_json(dangling_result, (status="complete",))
        @test islink(dangling_result)
        @test readlink(dangling_result) == dangling_result_target
    end
end

@testset "checkpoint rejects state and bin progress inconsistent with its task" begin
    mktempdir() do dir
        task, state = checkpoint_fixture(dir)
        wrong_task, wrong_state = checkpoint_fixture(dir; L=4, seed=UInt64(148402))
        path = joinpath(dir, "state.checkpoint")
        @test_throws ArgumentError save_checkpoint(
            path, task, wrong_state, BinRecord[]; git_commit="abc123", manifest_hash="m1")

        wrong_state_envelope = CheckpointEnvelope(
            3, task_hash(task), "abc123", "m1", string(VERSION), 0, wrong_state, BinRecord[])
        Challenge148._write_serialized_checkpoint(path, wrong_state_envelope)
        @test_throws ArgumentError load_checkpoint(
            path, task; git_commit="abc123", manifest_hash="m1")

        impossible_bins = fill(BinRecord(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), 9)
        @test_throws ArgumentError save_checkpoint(
            path, task, state, impossible_bins; git_commit="abc123", manifest_hash="m1")
        impossible_envelope = CheckpointEnvelope(
            3, task_hash(task), "abc123", "m1", string(VERSION), 9, state, impossible_bins)
        Challenge148._write_serialized_checkpoint(path, impossible_envelope)
        @test_throws ArgumentError load_checkpoint(
            path, task; git_commit="abc123", manifest_hash="m1")
    end
end

@testset "checkpoint runtime, rotation, and corrupt-current recovery are guarded" begin
    mktempdir() do dir
        task, state = checkpoint_fixture(dir)
        path = joinpath(dir, "state.checkpoint")
        old_bins = run_bins!(state, 1, 5)
        save_checkpoint(path, task, state, old_bins; git_commit="abc123", manifest_hash="m1")

        @test_throws ArgumentError load_checkpoint(
            path, task; git_commit="abc123", manifest_hash="m1", runtime_version="0.0.0")
        bytes = read(path)
        runtime_length = ncodeunits(string(VERSION))
        bytes[11:10+runtime_length] .= codeunits(repeat("x", runtime_length))
        write(path, bytes)
        @test_throws ArgumentError load_checkpoint(
            path, task; git_commit="abc123", manifest_hash="m1")
        save_checkpoint(path, task, state, old_bins; git_commit="abc123", manifest_hash="m1")

        new_bins = vcat(old_bins, run_bins!(state, 1, 5))
        observed = Symbol[]
        save_checkpoint(path, task, state, new_bins;
            git_commit="abc123", manifest_hash="m1",
            checkpoint_observer=stage -> begin
                push!(observed, stage)
                @test load_checkpoint(path, task;
                    git_commit="abc123", manifest_hash="m1").bins ==
                    (stage === :old_retained ? old_bins : new_bins)
            end)
        @test observed == [:old_retained, :candidate_promoted, :previous_installed]
        @test load_checkpoint(path * ".previous", task;
            git_commit="abc123", manifest_hash="m1").bins == old_bins

        fault_bins = vcat(new_bins, run_bins!(state, 1, 5))
        @test_throws ErrorException save_checkpoint(path, task, state, fault_bins;
            git_commit="abc123", manifest_hash="m1",
            checkpoint_observer=stage -> stage === :candidate_promoted && error("fault"))
        @test load_checkpoint(path, task;
            git_commit="abc123", manifest_hash="m1").bins == fault_bins
        @test load_checkpoint(path * ".previous", task;
            git_commit="abc123", manifest_hash="m1").bins == new_bins

        write(path, "corrupt current sentinel")
        recovery_bins = vcat(fault_bins, run_bins!(state, 1, 5))
        save_checkpoint(path, task, state, recovery_bins;
            git_commit="abc123", manifest_hash="m1")
        @test load_checkpoint(path, task;
            git_commit="abc123", manifest_hash="m1").bins == recovery_bins
        @test load_checkpoint(path * ".previous", task;
            git_commit="abc123", manifest_hash="m1").bins == new_bins
    end
end

@testset "failed previous installation retains a recoverable old checkpoint" begin
    mktempdir() do dir
        task, state = checkpoint_fixture(dir)
        path = joinpath(dir, "state.checkpoint")
        old_bins = run_bins!(state, 1, 5)
        save_checkpoint(path, task, state, old_bins; git_commit="abc123", manifest_hash="m1")
        new_bins = vcat(old_bins, run_bins!(state, 1, 5))

        try
            @test_throws Base.IOError save_checkpoint(path, task, state, new_bins;
                git_commit="abc123", manifest_hash="m1",
                checkpoint_observer=stage ->
                    stage === :candidate_promoted && chmod(dir, 0o500))
        finally
            chmod(dir, 0o700)
        end

        recovery = path * ".previous.recovery"
        @test load_checkpoint(path, task;
            git_commit="abc123", manifest_hash="m1").bins == new_bins
        @test !ispath(path * ".previous")
        @test isfile(recovery)
        @test load_checkpoint(recovery, task;
            git_commit="abc123", manifest_hash="m1").bins == old_bins
        @test !any(contains(".partial"), readdir(dir))

        retry_bins = vcat(new_bins, run_bins!(state, 1, 5))
        save_checkpoint(path, task, state, retry_bins;
            git_commit="abc123", manifest_hash="m1")
        @test load_checkpoint(path, task;
            git_commit="abc123", manifest_hash="m1").bins == retry_bins
        @test load_checkpoint(path * ".previous", task;
            git_commit="abc123", manifest_hash="m1").bins == new_bins
        @test !ispath(recovery)
        @test !any(contains(".partial"), readdir(dir))
    end
end

@testset "completed results are validated before atomic replacement" begin
    mktempdir() do dir
        path = joinpath(dir, "result.json")
        write_completed_result(path, (status="complete", completed_bins=2))
        expected = read(path, String)

        @test JSON.parsefile(path)["status"] == "complete"
        @test_throws ArgumentError write_completed_result(path, Dict("value" => NaN))
        @test read(path, String) == expected
        @test !any(endswith(".partial"), readdir(dir))
    end
end
