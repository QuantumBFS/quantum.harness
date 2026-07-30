using Test
using JSON

if !isdefined(@__MODULE__, :Challenge148)
    include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
end
using .Challenge148

module AggregationHarness
include(joinpath(@__DIR__, "..", "scripts", "aggregate_route_a.jl"))
end

const _AGGREGATE_SCRIPT = joinpath(@__DIR__, "..", "scripts", "aggregate_route_a.jl")
const _AGGREGATE_PROJECT_ROOT = normpath(joinpath(@__DIR__, ".."))
const _AGGREGATION_CHALLENGE = AggregationHarness.Challenge148

function _aggregation_task(output_path::String, replica::Int)
    fixture = _AGGREGATION_CHALLENGE.read_task(joinpath(@__DIR__, "fixtures", "tiny_triangle_task.json"))
    return _AGGREGATION_CHALLENGE.ClusterTask(
        fixture.schema_version,
        fixture.lattice,
        fixture.L,
        fixture.J,
        fixture.h,
        fixture.c,
        replica,
        _AGGREGATION_CHALLENGE.task_seed(:route_a, fixture.lattice, fixture.L, fixture.h, fixture.c, replica),
        fixture.thermalization_sweeps,
        fixture.measurement_sweeps,
        fixture.base_bin_size,
        fixture.checkpoint_interval_bins,
        output_path,
    )
end

function _write_aggregation_fixture(dir::String; mutation::Symbol=:complete)
    results = joinpath(dir, "results")
    output = joinpath(dir, "output")
    mkpath(results)
    mkpath(output)
    tasks = [_aggregation_task("chain-$(replica).json", replica) for replica in 1:2]
    if mutation === :duplicate_seed
        original = tasks[2]
        first = tasks[1]
        tasks[2] = _AGGREGATION_CHALLENGE.ClusterTask(
            original.schema_version, original.lattice, original.L, original.J, original.h,
            original.c, original.replica, first.seed, original.thermalization_sweeps,
            original.measurement_sweeps, original.base_bin_size,
            original.checkpoint_interval_bins, original.output_path,
        )
    end
    manifest_path = joinpath(dir, "campaign.json")
    AggregationHarness.write_campaign_manifest(
        manifest_path,
        "tiny-campaign",
        AggregationHarness._git_commit(),
        AggregationHarness._manifest_hash(),
        tasks,
    )
    for task in tasks
        task_path = joinpath(dir, "task-$(task.replica).json")
        result_path = joinpath(results, task.output_path)
        run_task = _AGGREGATION_CHALLENGE.ClusterTask(
            task.schema_version, task.lattice, task.L, task.J, task.h, task.c,
            task.replica, task.seed, task.thermalization_sweeps, task.measurement_sweeps,
            task.base_bin_size, task.checkpoint_interval_bins, result_path,
        )
        _AGGREGATION_CHALLENGE.write_task(task_path, run_task)
        AggregationHarness.run_cluster_task(task_path)
        result = JSON.parsefile(result_path; dicttype=Dict)
        result["task"]["output_path"] = task.output_path
        # The campaign task identity deliberately uses the staged basename, so regenerate a
        # matching trusted result using the runner's exact record implementation.
        staged_task = task
        bins = AggregationHarness._result_bins(
            result, result["completed_bins"], staged_task.base_bin_size)
        staged = AggregationHarness._result_record(
            staged_task,
            AggregationHarness._git_commit(),
            AggregationHarness._manifest_hash(),
            bins,
            result["provenance"]["started_at"],
            0.0,
        )
        _AGGREGATION_CHALLENGE.atomic_write_json(result_path, staged)
    end
    if mutation === :missing
        rm(joinpath(results, tasks[end].output_path))
    elseif mutation === :mixed_commit
        path = joinpath(results, tasks[end].output_path)
        damaged = JSON.parsefile(path; dicttype=Dict)
        damaged["provenance"]["git_commit"] = repeat("a", 40)
        _AGGREGATION_CHALLENGE.atomic_write_json(path, damaged)
    elseif mutation === :corrupt
        open(joinpath(results, tasks[end].output_path), "w") do io
            write(io, "not-json")
        end
    elseif mutation === :checksum
        path = joinpath(results, tasks[end].output_path)
        damaged = JSON.parsefile(path; dicttype=Dict)
        damaged["completion_checksum"] = repeat("0", 64)
        _AGGREGATION_CHALLENGE.atomic_write_json(path, damaged)
    elseif mutation === :partial
        open(joinpath(results, "stale.partial"), "w") do io
            write(io, "stale")
        end
    end
    return (manifest=manifest_path, results=results, output=output, tasks=tasks)
end

function audit_fixture(case::Symbol)
    mktempdir() do dir
        fixture = _write_aggregation_fixture(dir; mutation=case)
        audit = AggregationHarness.aggregate_campaign(
            fixture.manifest, fixture.results, fixture.output)
        @test isfile(joinpath(fixture.output, "audit.json"))
        @test audit.passed == isfile(joinpath(fixture.output, "combined_bins.json"))
        if audit.passed
            combined = JSON.parsefile(joinpath(fixture.output, "combined_bins.json"))
            @test [chain["task_id"] for chain in combined["chains"]] ==
                  [_AGGREGATION_CHALLENGE.task_id(task) for task in fixture.tasks]
            @test [chain["raw_bins"] for chain in combined["chains"]] ==
                  [JSON.parsefile(joinpath(fixture.results, task.output_path))["raw_bins"] for task in fixture.tasks]
        end
        return audit
    end
end

@testset "aggregator accepts only its declared command-line grammar" begin
    @test AggregationHarness.parse_aggregate_args(["--manifest", "campaign.json", "--results", "results", "--output", "output"]) ==
          (manifest_path="campaign.json", results_dir="results", output_dir="output")
    @test_throws ArgumentError AggregationHarness.parse_aggregate_args(String[])
    @test_throws ArgumentError AggregationHarness.parse_aggregate_args(["--results", "r", "--manifest", "m", "--output", "o"])
    @test_throws ArgumentError AggregationHarness.parse_aggregate_args(["--manifest", "m", "--results", "r", "--output", "o", "--extra", "x"])
    @test AggregationHarness.parse_aggregate_args(["--audit-manifest", "frozen.json"]) ==
          (audit_manifest_path="frozen.json",)
end

function _write_frozen_manifest_audit_fixture(dir::String)
    tasks = _AGGREGATION_CHALLENGE.ClusterTask[]
    counter = 0
    h_old = Dict(:triangle => 4.76811, :honeycomb => 2.13250)
    for lattice in (:triangle, :honeycomb), L in (8, 12, 16, 24, 32, 48, 64),
        x in (-0.6, 0.0, 0.6), replica in 1:8
        counter += 1
        h = h_old[lattice] + x * L^-1.5868
        push!(tasks, _AGGREGATION_CHALLENGE.ClusterTask(1, lattice, L, 1.0, h, 1.0,
            replica, _AGGREGATION_CHALLENGE.task_seed(:route_a, lattice, L, h, 1.0, replica),
            5000, 12500, 100, 10, "result-$(lpad(counter, 4, '0')).json"))
    end
    for lattice in (:triangle, :honeycomb), L in (24, 48), c in (1.5, 2.0),
        x in (-0.6, 0.0, 0.6), replica in 1:8
        counter += 1
        h = h_old[lattice] + x * L^-1.5868
        push!(tasks, _AGGREGATION_CHALLENGE.ClusterTask(1, lattice, L, 1.0, h, c,
            replica, _AGGREGATION_CHALLENGE.task_seed(:route_a, lattice, L, h, c, replica),
            5000, 12500, 100, 10, "result-$(lpad(counter, 4, '0')).json"))
    end
    sort!(tasks; by=_AGGREGATION_CHALLENGE.task_id)
    manifest_path = joinpath(dir, "route_a_recon_manifest.json")
    commit = AggregationHarness._git_commit()
    manifest_hash = AggregationHarness._manifest_hash()
    AggregationHarness.write_campaign_manifest(
        manifest_path, "route-a-frozen-v1", commit, manifest_hash, tasks)
    campaign = AggregationHarness._read_campaign_manifest(manifest_path)
    task_resources = [(
        task_id=_AGGREGATION_CHALLENGE.task_id(task),
        task_hash=_AGGREGATION_CHALLENGE.task_hash(task),
        predicted_wall_seconds=1.0,
        predicted_memory_bytes=1.0e8,
        predicted_disk_bytes=1.0,
    ) for task in campaign.tasks]
    payload = (
        schema_version=2, kind="route_a_frozen_resource_estimate", approved=true,
        calibration_path="route_a_calibration.json",
        calibration_content_sha256=repeat("c", 64),
        config_path="route_a_recon_config.toml",
        config_content_sha256=repeat("d", 64),
        campaign_id=campaign.campaign_id, campaign_checksum=campaign.campaign_checksum,
        release_git_commit=campaign.git_commit,
        release_julia_manifest_sha256=campaign.julia_manifest_sha256,
        release_julia_version=campaign.julia_version, task_count=528,
        predicted_cpu_seconds=528.0, max_task_wall_seconds=1.0,
        max_task_memory_bytes=1.0e8, predicted_disk_bytes=528.0,
        requested_walltime_seconds=86400.0, requested_memory_bytes=17179869184.0,
        requested_disk_bytes=25000000000.0, walltime_fraction_limit=0.70,
        memory_fraction_limit=0.70, disk_fraction_limit=0.70, task_resources=task_resources,
        deployment_instruction="stage release_git_commit; copy frozen inputs separately without changing campaign provenance",
    )
    estimate = merge(payload,
        (estimate_checksum=AggregationHarness._resource_estimate_checksum(payload),))
    estimate_path = joinpath(dir, "route_a_resource_estimate.json")
    _AGGREGATION_CHALLENGE.atomic_write_json(estimate_path, estimate)
    return (manifest=manifest_path, estimate=estimate_path)
end

@testset "frozen audit rejects estimates without recomputable evidence snapshots" begin
    mktempdir() do dir
        fixture = _write_frozen_manifest_audit_fixture(dir)
        audit = AggregationHarness.audit_frozen_manifest(fixture.manifest)
        @test !audit.passed
        @test "resource_estimate" in audit.errors
    end
end

@testset "aggregator refuses incompatible campaign data" begin
    complete = audit_fixture(:complete)
    @test isempty(complete.audit.errors)
    @test complete.passed
    for case in (:missing, :duplicate_seed, :mixed_commit, :corrupt, :checksum, :partial)
        @test !audit_fixture(case).passed
    end
end

@testset "a failed rerun invalidates an earlier combined aggregate" begin
    mktempdir() do dir
        fixture = _write_aggregation_fixture(dir)
        @test AggregationHarness.aggregate_campaign(
            fixture.manifest, fixture.results, fixture.output).passed
        combined = joinpath(fixture.output, "combined_bins.json")
        @test isfile(combined)

        rm(joinpath(fixture.results, fixture.tasks[end].output_path))
        failed = AggregationHarness.aggregate_campaign(
            fixture.manifest, fixture.results, fixture.output)
        @test !failed.passed
        @test JSON.parsefile(joinpath(fixture.output, "audit.json"))["passed"] == false
        @test !ispath(combined)
    end
end

@testset "aggregator rejects aliases to immutable campaign inputs" begin
    mktempdir() do dir
        fixture = _write_aggregation_fixture(dir)
        manifest_bytes = read(fixture.manifest)
        result_names = readdir(fixture.results)
        result_bytes = Dict(name => read(joinpath(fixture.results, name)) for name in result_names)

        @test_throws ArgumentError AggregationHarness.aggregate_campaign(
            fixture.manifest, fixture.results, fixture.results)
        nested_output = joinpath(fixture.results, "nested-output")
        mkpath(nested_output)
        @test_throws ArgumentError AggregationHarness.aggregate_campaign(
            fixture.manifest, fixture.results, nested_output)
        canonical_results_alias = joinpath(fixture.results, "..", basename(fixture.results))
        @test_throws ArgumentError AggregationHarness.aggregate_campaign(
            fixture.manifest, fixture.results, canonical_results_alias)
        output_symlink = joinpath(dir, "output-symlink")
        symlink(fixture.output, output_symlink)
        @test_throws ArgumentError AggregationHarness.aggregate_campaign(
            fixture.manifest, fixture.results, output_symlink)
        @test read(fixture.manifest) == manifest_bytes
        @test readdir(fixture.results) == sort(vcat(result_names, ["nested-output"]))
        @test all(read(joinpath(fixture.results, name)) == result_bytes[name] for name in result_names)

        for destination in ("audit.json", "combined_bins.json")
            alias_path = joinpath(fixture.output, destination)
            cp(fixture.manifest, alias_path; force=false)
            @test_throws ArgumentError AggregationHarness.aggregate_campaign(
                alias_path, fixture.results, fixture.output)
            @test read(alias_path) == manifest_bytes
            @test read(fixture.manifest) == manifest_bytes
            rm(alias_path)
        end
    end
end
