using Test
using JSON
using TOML

module ManifestGenerationHarness
include(joinpath(@__DIR__, "..", "scripts", "make_route_a_manifest.jl"))
end

const MGH = ManifestGenerationHarness

@testset "approved route A candidate manifest is deterministic" begin
    manifest = ManifestGenerationHarness.make_candidate_manifest(
        ManifestGenerationHarness.load_recon_config())
    @test length(manifest.tasks) == 528
    @test length(unique(ManifestGenerationHarness.task_hash.(manifest.tasks))) == 528
    @test length(unique(getfield.(manifest.tasks, :seed))) == 528
    @test manifest == ManifestGenerationHarness.make_candidate_manifest(
        ManifestGenerationHarness.load_recon_config())
end

@testset "smoke and benchmark schedules implement the approved Task 12 contract" begin
    config = MGH.load_recon_config()
    smoke = MGH.make_smoke_manifest(config)
    benchmark = MGH.make_benchmark_manifest(config)
    @test length(smoke.tasks) == 4
    @test Set((task.lattice, task.L, task.replica) for task in smoke.tasks) ==
          Set((lattice, L, replica) for (lattice, L) in ((:triangle, 3), (:honeycomb, 2)) for replica in 1:2)
    c1 = filter(task -> task.c == 1.0, benchmark.tasks)
    c1_resource_slope = filter(task -> task.thermalization_sweeps == 500 && task.replica <= 2 &&
        (task.L in (16, 24, 32) || (task.L == 48 && task.h == config.h_old[task.lattice])), c1)
    @test length(c1_resource_slope) == 40
    @test Set(task.L for task in c1_resource_slope) == Set((16, 24, 32, 48))
    @test count(task -> task.L == 48, c1_resource_slope) == 4
    @test all(task -> task.h == config.h_old[task.lattice], filter(task -> task.L == 48, c1_resource_slope))
    # Cost and autocorrelation at c=1 cannot justify c=1.5 or c=2.0.  The
    # benchmark therefore includes the extra groups needed to freeze thermal checks.
    @test length(benchmark.tasks) == 328
    @test length(unique(getfield.(benchmark.tasks, :seed))) == 328
    @test length(unique(MGH.task_id.(benchmark.tasks))) == 328
    @test Set(task.c for task in benchmark.tasks) == Set((1.0, 1.5, 2.0))
    @test all(c -> Set(task.L for task in benchmark.tasks if task.c == c) == Set((16, 24, 32, 48)), (1.5, 2.0))
    for lattice in (:triangle, :honeycomb), c in (1.0, 1.5, 2.0),
        L in (c == 1.0 ? config.sizes : (16, 24, 32, 48))
        central = filter(task -> task.lattice == lattice && task.c == c && task.L == L &&
            task.h == config.h_old[lattice], benchmark.tasks)
        @test Set(getfield.(central, :thermalization_sweeps)) == Set((500, 2000, 5000, 10000))
        @test all(level -> count(task -> task.thermalization_sweeps == level, central) == 2,
            (500, 2000, 5000, 10000))
    end
end

@testset "candidate is exactly compatible with the Task 9 frozen science grid" begin
    config = MGH.load_recon_config()
    manifest = MGH.make_candidate_manifest(config)
    expected = Set{Tuple{Symbol,Int,Float64,Float64,Int}}()
    for lattice in (:triangle, :honeycomb), L in (8, 12, 16, 24, 32, 48, 64),
        x in (-0.6, 0.0, 0.6), replica in 1:8
        h = config.h_old[lattice] + x * L^-1.5868
        push!(expected, (lattice, L, h, 1.0, replica))
    end
    for lattice in (:triangle, :honeycomb), L in (24, 48), c in (1.5, 2.0),
        x in (-0.6, 0.0, 0.6), replica in 1:8
        h = config.h_old[lattice] + x * L^-1.5868
        push!(expected, (lattice, L, h, c, replica))
    end
    observed = Set((task.lattice, task.L, task.h, task.c, task.replica) for task in manifest.tasks)
    @test observed == expected
    @test all(task -> basename(task.output_path) == task.output_path && endswith(task.output_path, ".json"), manifest.tasks)
    @test length(unique(getfield.(manifest.tasks, :output_path))) == 528
end

@testset "all reviewed execution and confidence controls are exact" begin
    source = read(joinpath(MGH._RECON_ROOT, "config", "route_a_recon.toml"), String)
    raw = TOML.parse(source)
    @test raw["confidence_policy"] == "student_t_two_sided_95"
    @test raw["confidence_level"] == 0.95
    @test !haskey(raw, "confidence_z")
    for (before, after) in (
        ("thermalization_sweeps = 5000", "thermalization_sweeps = 1"),
        ("candidate_measurement_sweeps = 10000", "candidate_measurement_sweeps = 100"),
        ("base_bin_size = 100", "base_bin_size = 10"),
        ("checkpoint_interval_bins = 10", "checkpoint_interval_bins = 1"),
        ("requested_walltime_seconds = 86400.0", "requested_walltime_seconds = 1.0e300"),
        ("requested_memory_bytes = 17179869184.0", "requested_memory_bytes = 1.0e300"),
        ("requested_disk_bytes = 25000000000.0", "requested_disk_bytes = 1.0e300"),
        ("disk_fraction_limit = 0.70", "disk_fraction_limit = 1.0"),
        ("benchmark_replicas = 2", "benchmark_replicas = 1"),
        ("burnin_prefix_sweeps = [500, 2000, 5000, 10000]", "burnin_prefix_sweeps = [500, 1000, 5000, 10000]"),
        ("burnin_compatibility_z = 3.5", "burnin_compatibility_z = 4.0"),
        ("smoke_thermalization_sweeps = 10", "smoke_thermalization_sweeps = 1"),
        ("smoke_measurement_sweeps = 20", "smoke_measurement_sweeps = 10"),
        ("smoke_base_bin_size = 5", "smoke_base_bin_size = 10"),
        ("smoke_checkpoint_interval_bins = 1", "smoke_checkpoint_interval_bins = 2"),
        ("benchmark_thermalization_sweeps = 500", "benchmark_thermalization_sweeps = 50"),
        ("benchmark_measurement_sweeps = 2000", "benchmark_measurement_sweeps = 1000"),
        ("benchmark_base_bin_size = 100", "benchmark_base_bin_size = 10"),
        ("benchmark_checkpoint_interval_bins = 5", "benchmark_checkpoint_interval_bins = 1"),
        ("benchmark_requested_walltime_seconds = 14400.0", "benchmark_requested_walltime_seconds = 1.0e300"),
        ("benchmark_requested_memory_bytes = 17179869184.0", "benchmark_requested_memory_bytes = 1.0e300"),
        ("benchmark_requested_disk_bytes = 25000000000.0", "benchmark_requested_disk_bytes = 1.0e300"),
        ("elapsed_relative_tolerance = 1.0e-6", "elapsed_relative_tolerance = 1.0"),
        ("confidence_policy = \"student_t_two_sided_95\"", "confidence_policy = \"normal\""),
        ("confidence_level = 0.95", "confidence_level = 0.50"),
    )
        mktempdir() do dir
            path = joinpath(dir, "mutated.toml")
            write(path, replace(source, before => after; count=1))
            @test_throws ArgumentError MGH.load_recon_config(path)
        end
    end
end

@testset "campaign bundles use the Task 8 schema and stable Slurm indexing" begin
    config = MGH.load_recon_config()
    manifest = MGH.make_smoke_manifest(config)
    mktempdir() do dir
        output = joinpath(dir, "smoke.json")
        MGH.write_manifest_bundle(output, manifest)
        parsed = MGH._read_campaign_manifest(output)
        @test parsed.tasks == collect(manifest.tasks)
        @test parsed.git_commit == readchomp(`git -C $(MGH._RECON_ROOT) rev-parse HEAD`)
        @test parsed.julia_manifest_sha256 == bytes2hex(MGH.sha256(read(joinpath(MGH._RECON_ROOT, "Manifest.toml"))))
        task_dir = joinpath(dir, "smoke-tasks")
        ids = sort(MGH.task_id.(collect(manifest.tasks)))
        @test filter(name -> endswith(name, ".json"), readdir(task_dir)) == ids .* ".json"
        paths = readlines(joinpath(task_dir, "task_paths.txt"))
        @test paths == ids .* ".json"
        @test all(!isabspath, paths)
        @test MGH.read_task(joinpath(task_dir, paths[1])) == sort(collect(manifest.tasks); by=MGH.task_id)[1]
        @test read(output) == read(MGH.write_manifest_bundle(output, manifest))

        write(joinpath(task_dir, "stale.json"), "stale")
        MGH.write_manifest_bundle(output, manifest)
        @test !ispath(joinpath(task_dir, "stale.json"))
    end
end


@testset "task index remains valid after bundle relocation" begin
    manifest = MGH.make_smoke_manifest(MGH.load_recon_config())
    mktempdir() do dir
        original = joinpath(dir, "original")
        relocated = joinpath(dir, "relocated")
        mkpath(original)
        MGH.write_manifest_bundle(joinpath(original, "smoke.json"), manifest)
        mv(original, relocated)
        task_dir = joinpath(relocated, "smoke-tasks")
        paths = readlines(joinpath(task_dir, "task_paths.txt"))
        @test all(path -> isfile(joinpath(task_dir, path)), paths)
        @test MGH.read_task(joinpath(task_dir, first(paths))) == first(manifest.tasks)
    end
end

@testset "bundle destinations reject path aliases and symlinks" begin
    manifest = MGH.make_smoke_manifest(MGH.load_recon_config())
    mktempdir() do dir
        target = joinpath(dir, "target.json")
        write(target, "sentinel")
        link = joinpath(dir, "smoke.json")
        symlink(target, link)
        @test_throws ArgumentError MGH.write_manifest_bundle(link, manifest)
        @test read(target, String) == "sentinel"

        rm(link)
        task_dir = joinpath(dir, "smoke-tasks")
        mkpath(joinpath(dir, "elsewhere"))
        symlink(joinpath(dir, "elsewhere"), task_dir)
        @test_throws ArgumentError MGH.write_manifest_bundle(link, manifest)
        @test isempty(readdir(joinpath(dir, "elsewhere")))

        rm(task_dir)
        hardlink_source = joinpath(dir, "hardlink-source")
        write(hardlink_source, "immutable")
        hardlink(hardlink_source, link)
        @test_throws ArgumentError MGH.write_manifest_bundle(link, manifest)
        @test read(hardlink_source, String) == "immutable"
    end
end

function calibration_fixture(config; mutation::Symbol=:complete)
    benchmark = MGH.make_benchmark_manifest(config)
    release_commit = String(readchomp(`git -C $(MGH._RECON_ROOT) rev-parse HEAD^`))
    bundle_size = 8
    allocation_for(index) = div(index - 1, bundle_size) + 1
    allocation_key(index) = "$(9000 + allocation_for(index))_$(allocation_for(index) - 1)"
    records = Dict{String,Any}[]
    for (index, task) in enumerate(benchmark.tasks)
        anchor_x = only(x for x in config.anchors if task.h == config.h_old[task.lattice] + x * task.L^-config.yt_anchor)
        central = anchor_x == 0.0
        slope_available = central && task.thermalization_sweeps == 500 && task.replica <= 2 &&
            !(task.c == 1.0 && task.L == 48)
        reference = central && task.thermalization_sweeps == 10000
        slope = task.lattice == :triangle ? -3.0 : -2.0
        binder = 0.62 + slope * (task.h - config.h_old[task.lattice]) + task.replica * 1e-7
        energy = -1.25 - task.L * 1e-5 + task.replica * 1e-8
        push!(records, Dict{String,Any}(
            "calibration_key" => "cal-$(lpad(index, 4, '0'))",
            "manifest_index" => index - 1,
            "allocation_key" => allocation_key(index),
            "raw_slurm_job_id" => string(9000 + allocation_for(index)),
            "slurm_task_index" => index - 1,
            "task_id" => MGH.task_id(task),
            "task_hash" => MGH.task_hash(task),
            "seed" => "u64:" * string(task.seed; base=16, pad=16),
            "result_sha256" => MGH.bytes2hex(MGH.sha256(codeunits("result-$index"))),
            "completion_checksum" => MGH.bytes2hex(MGH.sha256(codeunits("completion-$index"))),
            "release_git_commit" => release_commit,
            "release_julia_manifest_sha256" => benchmark.julia_manifest_sha256,
            "release_julia_version" => benchmark.julia_version,
            "algorithm" => benchmark.algorithm,
            "observable_schema_version" => benchmark.observable_schema_version,
            "lattice" => String(task.lattice),
            "L" => task.L,
            "J" => task.J,
            "h" => task.h,
            "c" => task.c,
            "anchor_x" => anchor_x,
            "replica" => task.replica,
            "thermalization_sweeps" => task.thermalization_sweeps,
            "measurement_sweeps" => task.measurement_sweeps,
            "base_bin_size" => task.base_bin_size,
            "energy_mean" => energy,
            "energy_stderr" => 1e-6,
            "energy_first_half_mean" => energy - 1e-8,
            "energy_first_half_stderr" => 2e-6,
            "energy_second_half_mean" => energy + 1e-8,
            "energy_second_half_stderr" => 2e-6,
            "binder_mean" => binder,
            "binder_stderr" => 1e-6,
            "binder_first_half_mean" => binder - 1e-8,
            "binder_first_half_stderr" => 2e-6,
            "binder_second_half_mean" => binder + 1e-8,
            "binder_second_half_stderr" => 2e-6,
            "binder_slope" => slope_available ? slope : nothing,
            "binder_slope_stderr" => slope_available ? 1e-10 : nothing,
            "tau_int_base_bins" => reference ? 0.5 : nothing,
            "tau_int_stderr_base_bins" => reference ? 0.0 : nothing,
            "binder_variance_per_base_bin" => reference ? 1e-10 : nothing,
            "binder_variance_stderr_per_base_bin" => reference ? 0.0 : nothing,
            "cut_count_mean" => task.L^2 * task.c,
            "elapsed_seconds" => 0.0001 * task.L * task.c *
                (task.thermalization_sweeps + task.measurement_sweeps),
            "elapsed_per_sweep_seconds" => 0.0001 * task.L * task.c,
            "max_rss_upper_bytes" => 1.0e5 * task.L * task.c,
            "nominal_requested_memory_per_chain_bytes" => 8 * 1024^3,
            "result_bytes" => 100.0 * task.measurement_sweeps * task.L / 16,
        ))
    end
    allocations = Dict{String,Any}[]
    for first_index in 1:bundle_size:length(records)
        last_index = min(first_index + bundle_size - 1, length(records))
        indices = collect(first_index:last_index)
        allocation_number = allocation_for(first_index)
        upper = maximum(record["max_rss_upper_bytes"] for record in records[indices])
        foreach(index -> records[index]["max_rss_upper_bytes"] = upper, indices)
        push!(allocations, Dict{String,Any}(
            "allocation_key" => allocation_key(first_index),
            "raw_job_id" => string(9000 + allocation_number),
            "array_task_id" => allocation_number - 1,
            "state" => "COMPLETED",
            "exit_code" => "0:0",
            "alloc_cpus" => length(indices),
            "requested_memory_bytes" => 64 * 1024^3,
            "requested_walltime_seconds" => 4 * 3600,
            "elapsed_seconds" => ceil(Int, maximum(records[index]["elapsed_seconds"] for index in indices)),
            "max_rss_upper_bytes" => round(Int, upper),
            "nominal_bundle_size" => bundle_size,
            "bundle_size" => length(indices),
            "task_indices" => [index - 1 for index in indices],
            "task_ids" => [records[index]["task_id"] for index in indices],
            "task_hashes" => [records[index]["task_hash"] for index in indices],
            "wrapper_file" => "wrapper-$(allocation_number).out",
            "wrapper_sha256" => MGH.bytes2hex(MGH.sha256(codeunits("wrapper-$allocation_number"))),
            "completed_start_index" => first_index - 1,
            "completed_end_index" => last_index - 1,
            "canonical_accounting_rows" => [
                "$(9000 + allocation_number)_$(allocation_number - 1)|COMPLETED",
                "$(9000 + allocation_number)_$(allocation_number - 1).batch|COMPLETED",
            ],
        ))
    end
    if mutation == :duplicate_key
        push!(records, copy(records[1]))
    elseif mutation == :duplicate_task
        duplicate = copy(records[1])
        duplicate["calibration_key"] = "cal-extra"
        push!(records, duplicate)
    elseif mutation == :missing_tau
        records[findfirst(record -> record["tau_int_base_bins"] !== nothing, records)]["tau_int_base_bins"] = nothing
    elseif mutation == :missing_stored_slope
        records[findfirst(record -> record["binder_slope"] !== nothing, records)]["binder_slope"] = nothing
    elseif mutation == :missing_slope
        filter!(record -> !(record["lattice"] == "triangle" && record["L"] == 16 && record["c"] == 1.0 && record["anchor_x"] == 0.6), records)
    elseif mutation == :walltime
        foreach(record -> begin
            record["elapsed_per_sweep_seconds"] *= 1e8
            record["elapsed_seconds"] *= 1e8
        end, records)
    elseif mutation == :memory
        foreach(allocation -> allocation["max_rss_upper_bytes"] *= 1e8, allocations)
        foreach(record -> record["max_rss_upper_bytes"] *= 1e8, records)
    elseif mutation == :disk
        foreach(record -> record["result_bytes"] *= 1e8, records)
    elseif mutation == :sigma
        foreach(record -> record["binder_variance_per_base_bin"] === nothing ||
            (record["binder_variance_per_base_bin"] = 1e8), records)
    elseif mutation == :provenance
        records[1]["release_git_commit"] = repeat("a", 40)
    elseif mutation == :missing_resource
        allocations[1]["max_rss_upper_bytes"] = 0
        for index in eachindex(records)
            allocation_for(index) == 1 || continue
            records[index]["max_rss_upper_bytes"] = 0.0
        end
    elseif mutation == :tau_uncertainty
        foreach(record -> record["tau_int_stderr_base_bins"] === nothing ||
            (record["tau_int_stderr_base_bins"] = 1e12), records)
    elseif mutation == :single_slow_replica
        candidates = filter(record -> record["lattice"] == "triangle" && record["c"] == 1.0 &&
            record["L"] == 48 && record["tau_int_base_bins"] !== nothing, records)
        candidates[1]["tau_int_base_bins"] = 50.0
    elseif mutation == :variance_uncertainty
        foreach(record -> record["binder_variance_stderr_per_base_bin"] === nothing ||
            (record["binder_variance_stderr_per_base_bin"] = 1e12), records)
    elseif mutation == :timing
        records[1]["elapsed_seconds"] *= 100.0
    elseif mutation == :array_index
        records[1]["slurm_task_index"] = 999
    elseif mutation == :slurm_format
        records[1]["raw_slurm_job_id"] = "job-9001"
    elseif mutation == :slurm_duplicate
        records[2]["slurm_task_index"] = records[1]["slurm_task_index"]
    elseif mutation == :requested_resource
        allocations[1]["alloc_cpus"] = 1
    elseif mutation == :split_half
        record = records[findfirst(record -> record["anchor_x"] == 0.0 &&
            record["thermalization_sweeps"] == 10000, records)]
        record["energy_second_half_mean"] += 1.0
    elseif mutation == :burnin_missing
        index = findfirst(record -> record["lattice"] == "triangle" && record["c"] == 1.0 &&
            record["L"] == 16 && record["thermalization_sweeps"] == 2000, records)
        deleteat!(records, index)
    elseif mutation == :burnin_scaling
        foreach(record -> begin
            record["anchor_x"] == 0.0 && record["thermalization_sweeps"] < 5000 || return
            record["energy_mean"] += 1.0
            record["energy_first_half_mean"] += 1.0
            record["energy_second_half_mean"] += 1.0
            record["binder_mean"] += 1.0
            record["binder_first_half_mean"] += 1.0
            record["binder_second_half_mean"] += 1.0
        end, records)
    elseif mutation == :inadequate_longest_prefix
        foreach(record -> begin
            record["lattice"] == "triangle" && record["c"] == 1.0 && record["L"] == 16 &&
                record["anchor_x"] == 0.0 && record["thermalization_sweeps"] < 10000 || return
            for field in ("energy_mean", "energy_first_half_mean", "energy_second_half_mean",
                "binder_mean", "binder_first_half_mean", "binder_second_half_mean")
                record[field] += 1.0
            end
        end, records)
    elseif mutation == :inconsistent_later_prefix
        foreach(record -> begin
            record["lattice"] == "triangle" && record["c"] == 1.0 && record["L"] == 16 &&
                record["anchor_x"] == 0.0 && record["thermalization_sweeps"] == 5000 || return
            for field in ("energy_mean", "energy_first_half_mean", "energy_second_half_mean",
                "binder_mean", "binder_first_half_mean", "binder_second_half_mean")
                record[field] += 1.0
            end
        end, records)
    elseif mutation == :ill_conditioned_fit
        foreach(record -> begin
            record["binder_mean"] = 0.62 + record["replica"] * 1e-7
            record["binder_slope"] === nothing || (record["binder_slope"] = 0.0)
        end, records)
    elseif mutation == :nonfinite_fit
        records[1]["elapsed_per_sweep_seconds"] = big"1e999"
    elseif mutation == :missing_thermal_group
        filter!(record -> record["c"] != 2.0, records)
    elseif mutation != :complete
        error("unknown fixture mutation")
    end
    return Dict{String,Any}(
        "schema_version" => 4,
        "kind" => "route_a_calibration",
        "builder_version" => "route-a-calibration-builder-v1",
        "sampling_unit" => "base_bin",
        "campaign_id" => "benchmark-5c3e1a4868c36f8e",
        "campaign_checksum" => MGH._campaign_checksum(
            "benchmark-5c3e1a4868c36f8e", release_commit, benchmark.julia_manifest_sha256,
            benchmark.julia_version, benchmark.algorithm, benchmark.observable_schema_version,
            collect(benchmark.tasks)),
        "campaign_manifest_sha256" => repeat("1", 64),
        "task_paths_sha256" => repeat("2", 64),
        "release_git_commit" => release_commit,
        "release_julia_manifest_sha256" => benchmark.julia_manifest_sha256,
        "release_julia_version" => benchmark.julia_version,
        "algorithm" => benchmark.algorithm,
        "observable_schema_version" => benchmark.observable_schema_version,
        "bundle_script_sha256" => repeat("3", 64),
        "accounting_snapshot_filename" => "sacct.psv",
        "accounting_snapshot_sha256" => repeat("4", 64),
        "wrapper_inventory_filename" => "wrapper_inventory.psv",
        "wrapper_inventory_sha256" => repeat("5", 64),
        "result_provenance_filename" => "result_provenance.psv",
        "result_provenance_sha256" => repeat("6", 64),
        "resource_summary" => Dict(
            "memory_fit_sample_count" => length(allocations),
            "chain_count" => length(records),
            "max_rss_semantics" => "allocation_batch_upper_bound_per_chain",
        ),
        "allocations" => allocations,
        "records" => records,
    )
end

function write_calibration_fixture(path, config; mutation::Symbol=:complete)
    MGH.atomic_write_json(path, calibration_fixture(config; mutation))
    if mutation == :nonfinite_fit
        encoded = read(path, String)
        encoded = replace(encoded, "\"elapsed_per_sweep_seconds\":null" =>
            "\"elapsed_per_sweep_seconds\":1e999"; count=1)
        encoded = replace(encoded, "\"elapsed_per_sweep_seconds\":\"Inf\"" =>
            "\"elapsed_per_sweep_seconds\":1e999"; count=1)
        write(path, encoded)
    end
    return path
end

@testset "versioned calibration schema retains allocation and chain provenance" begin
    config = MGH.load_recon_config()
    mktempdir() do dir
        path = write_calibration_fixture(joinpath(dir, "calibration.json"), config)
        calibration = MGH.read_calibration(path, config)
        @test isimmutable(calibration)
        @test length(calibration.records) == 328
        @test calibration.release_git_commit != MGH._git_commit()
        @test length(calibration.allocations) == 41
        @test calibration.memory_fit_sample_count == 41
        @test all(allocation -> allocation.requested_memory_bytes == 64 * 1024^3,
            calibration.allocations)
        @test first(calibration.allocations).requested_memory_bytes !=
            config.benchmark_requested_memory_bytes
        @test all(record -> !isempty(record.raw_slurm_job_id) &&
            !isempty(record.task_hash) && !isempty(record.allocation_key), calibration.records)
        references = filter(record -> record.anchor_x == 0.0 &&
            record.thermalization_sweeps == 10000, calibration.records)
        @test all(record -> record.tau_int_base_bins !== nothing &&
            record.binder_variance_per_base_bin !== nothing, references)
        @test all(record -> isfinite(record.energy_mean) && isfinite(record.energy_first_half_mean) &&
            isfinite(record.binder_second_half_mean), calibration.records)
        @test calibration.sampling_unit == "base_bin"
        for sample in MGH._allocation_memory_samples(calibration, :triangle, 1.0)
            linked = Set(record.allocation_key for record in calibration.records
                if record.lattice == :triangle && record.c == 1.0 && record.L == sample.L)
            @test Set(sample.allocation_keys) == linked
            @test length(sample.values) == length(linked)
        end
        @test Set((record.lattice, record.L, record.c) for record in calibration.records) >=
              Set((lattice, L, 1.0) for lattice in (:triangle, :honeycomb) for L in (16, 24, 32, 48))
    end
end

@testset "historical release verification fails closed and requires runnable files" begin
    current_release = readchomp(`git -C $(MGH._RECON_ROOT) rev-parse HEAD^`)
    current_hash = MGH.bytes2hex(MGH.sha256(
        read(`git -C $(MGH._RECON_ROOT) show $(current_release * ":Manifest.toml")`)))
    @test MGH._verify_release_snapshot(current_release, current_hash)

    manifestless = "36160c3dc65e2a9b03ecc4d45f42918b7628a95c"
    @test success(`git -C $(MGH._RECON_ROOT) cat-file -e $(manifestless * "^{commit}")`)
    @test !MGH._verify_release_snapshot(manifestless, repeat("0", 64))

    missing_runner = "501847fc69961de5541ae2a3a1ee3b16cc5d6f21"
    missing_runner_hash = MGH.bytes2hex(MGH.sha256(
        read(`git -C $(MGH._RECON_ROOT) show $(missing_runner * ":Manifest.toml")`)))
    @test !MGH._verify_release_snapshot(missing_runner, missing_runner_hash)

    mktempdir() do exported
        for relative in MGH._RELEASE_REQUIRED_FILES
            destination = joinpath(exported, relative)
            mkpath(dirname(destination))
            write(destination, "exported")
        end
        @test !MGH._verify_release_snapshot(current_release, current_hash; root=exported)
    end

    mktempdir() do dir
        repository = joinpath(dir, "repository")
        linked = joinpath(dir, "linked")
        run(`git clone --quiet --no-hardlinks $(MGH._RECON_ROOT) $repository`)
        run(`git -C $repository worktree add --quiet --detach $linked HEAD`)
        linked_commit = readchomp(`git -C $linked rev-parse HEAD`)
        linked_hash = MGH.bytes2hex(MGH.sha256(
            read(`git -C $linked show $(linked_commit * ":Manifest.toml")`)))
        @test isfile(joinpath(linked, ".git"))
        @test MGH._verify_release_snapshot(linked_commit, linked_hash; root=linked)
    end

    mktempdir() do repository
        packaged = joinpath(repository, "tracks", "qmc", "solutions", "group-zoo", "route_a")
        for relative in MGH._RELEASE_REQUIRED_FILES
            destination = joinpath(packaged, relative)
            mkpath(dirname(destination))
            write(destination, relative == "Manifest.toml" ? "packaged manifest\n" : "fixture\n")
        end
        run(`git -C $repository init --quiet`)
        run(`git -C $repository config user.name fixture`)
        run(`git -C $repository config user.email fixture@example.invalid`)
        run(`git -C $repository add tracks`)
        run(`git -C $repository commit --quiet -m fixture`)
        packaged_commit = readchomp(`git -C $repository rev-parse HEAD`)
        packaged_hash = MGH.bytes2hex(MGH.sha256(read(joinpath(packaged, "Manifest.toml"))))
        @test MGH._verify_release_snapshot(packaged_commit, packaged_hash; root=packaged)
    end
end

@testset "frozen sweeps are the smallest base-bin multiple meeting both ESS gates" begin
    config = MGH.load_recon_config()
    mktempdir() do dir
        calibration = MGH.read_calibration(
            write_calibration_fixture(joinpath(dir, "calibration.json"), config), config)
        frozen = MGH.make_frozen_manifest(config, calibration)
        @test length(frozen.tasks) == 528
        @test frozen.git_commit == calibration.release_git_commit
        @test frozen.julia_manifest_sha256 == calibration.release_julia_manifest_sha256
        @test Set(getfield.(frozen.tasks, :measurement_sweeps)) == Set((12500,))
        @test all(task -> begin
            tau_upper = MGH.predict_tau_upper(calibration, task.lattice, task.L, task.c, config)
            bins = task.measurement_sweeps / task.base_bin_size
            bins / (2tau_upper) >= config.min_ess_per_replica
            config.replicas * bins / (2tau_upper) >= config.min_ess_per_point
        end, frozen.tasks)
        @test all(task -> task.measurement_sweeps - task.base_bin_size <= 0 ||
            ((task.measurement_sweeps - task.base_bin_size) / task.base_bin_size) /
                (2MGH.predict_tau_upper(
                calibration, task.lattice, task.L, task.c, config)) < config.min_ess_per_point / config.replicas,
            frozen.tasks)
        @test MGH.predict_burnin_upper(calibration, :triangle, 64, 1.0, config) <=
            maximum(config.burnin_prefix_sweeps)
        unsupported = try
            MGH.predict_burnin_upper(calibration, :triangle, 64, 2.0, config)
            nothing
        catch error
            error
        end
        @test unsupported isa MGH.FreezeRefusal
        @test "thermalization" in unsupported.report.gates
        @test MGH._student_t_critical(2) ≈ 4.30265272975
        exact_values = Float64[16, 24, 32, 48]
        ten_percent = 0.1 .* exact_values
        leverage_fit = MGH._log_scaling_fit([16, 24, 32, 48], exact_values,
            ten_percent, "reviewer leverage")
        leverage = MGH.dot([1.0, log(64.0)],
            inv(transpose(hcat(ones(4), log.([16.0, 24.0, 32.0, 48.0]))) *
                hcat(ones(4), log.([16.0, 24.0, 32.0, 48.0]))) * [1.0, log(64.0)])
        @test MGH._prediction_log_variance(leverage_fit, 64, :mean) ≈ 0.01 * leverage rtol=1e-8
        @test MGH._prediction_log_variance(leverage_fit, 64, :individual) ≈
            0.01 * (leverage + 1) rtol=1e-8
        slow = MGH.read_calibration(write_calibration_fixture(
            joinpath(dir, "slow-replica.json"), config; mutation=:single_slow_replica), config)
        @test MGH.predict_tau_upper(slow, :triangle, 64, 1.0, config) >
            MGH.predict_tau_upper(calibration, :triangle, 64, 1.0, config)
        output = joinpath(dir, "approved-fixture.json")
        MGH.write_manifest_bundle(output, frozen)
        @test MGH._read_campaign_manifest(output).tasks == collect(frozen.tasks)
        @test length(readlines(joinpath(dir, "approved-fixture-tasks", "task_paths.txt"))) == 528

        scaled = MGH.read_calibration(write_calibration_fixture(
            joinpath(dir, "burnin-scaling.json"), config; mutation=:burnin_scaling), config)
        @test MGH.predict_burnin_upper(scaled, :triangle, 48, 2.0, config) == 5000
        scaled_frozen = MGH.make_frozen_manifest(config, scaled)
        @test Set(task.thermalization_sweeps for task in scaled_frozen.tasks) == Set((5000,))
    end
end

@testset "frozen generation refuses every scientific and resource gate" begin
    config = MGH.load_recon_config()
    for (mutation, gate) in (
        (:duplicate_key, "duplicate_calibration_key"),
        (:duplicate_task, "duplicate_calibration_task"),
        (:missing_tau, "missing_tau"),
        (:missing_stored_slope, "missing_slope"),
        (:missing_slope, "insufficient_three_anchors"),
        (:missing_resource, "missing_resource"),
        (:tau_uncertainty, "uncertainty"),
        (:variance_uncertainty, "uncertainty"),
        (:timing, "timing"),
        (:array_index, "array_index"),
        (:slurm_format, "slurm_id"),
        (:slurm_duplicate, "array_index"),
        (:requested_resource, "requested_resource"),
        (:split_half, "thermalization"),
        (:burnin_missing, "thermalization"),
        (:inadequate_longest_prefix, "thermalization"),
        (:inconsistent_later_prefix, "thermalization"),
        (:ill_conditioned_fit, "ill_conditioned_fit"),
        (:nonfinite_fit, "nonfinite_fit"),
        (:walltime, "walltime"),
        (:memory, "memory"),
        (:disk, "disk"),
        (:sigma, "sigma_stat_R"),
        (:provenance, "provenance"),
        (:missing_thermal_group, "missing_calibration_group"),
    )
        mktempdir() do dir
            path = write_calibration_fixture(joinpath(dir, "calibration.json"), config; mutation)
            error = try
                calibration = MGH.read_calibration(path, config)
                MGH.make_frozen_manifest(config, calibration)
                nothing
            catch caught
                caught
            end
            @test error isa MGH.FreezeRefusal
            @test gate in getfield(error, :report).gates
        end
    end
end

@testset "failed frozen CLI writes only an atomic machine-readable refusal" begin
    config = MGH.load_recon_config()
    mktempdir() do dir
        config_path = joinpath(dir, "config.toml")
        cp(joinpath(MGH._RECON_ROOT, "config", "route_a_recon.toml"), config_path)
        calibration_path = write_calibration_fixture(joinpath(dir, "calibration.json"), config; mutation=:missing_tau)
        output = joinpath(dir, "frozen.json")
        write(output, "stale approval")
        mkpath(joinpath(dir, "frozen-tasks"))
        write(joinpath(dir, "frozen-tasks", "stale.json"), "stale")
        @test !MGH.generate_manifest(config_path, calibration_path, "frozen", output)
        @test !ispath(output)
        @test !ispath(joinpath(dir, "frozen-tasks"))
        refusal = JSON.parsefile(joinpath(dir, "frozen-refusal.json"))
        @test refusal["approved"] == false
        @test "missing_tau" in refusal["gates"]
        @test refusal["recovery_path"] === nothing
        @test !any(contains("quarantine"), readdir(dir))

        write(output, "second stale approval")
        mkpath(joinpath(dir, "frozen-tasks"))
        @test !MGH.generate_manifest(joinpath(dir, "absent.toml"), calibration_path, "frozen", output)
        @test !ispath(output)
        @test !ispath(joinpath(dir, "frozen-tasks"))
        @test "config" in JSON.parsefile(joinpath(dir, "frozen-refusal.json"))["gates"]

        # Inputs are immutable even when an adversarial caller aliases output to one.
        calibration_bytes = read(calibration_path)
        @test !MGH.generate_manifest(joinpath(dir, "absent-again.toml"), calibration_path,
            "frozen", calibration_path)
        @test read(calibration_path) == calibration_bytes
        @test isfile(joinpath(dir, "calibration-refusal.json"))

        # A clean checkout need not pre-create config/frozen/.
        missing_parent_output = joinpath(dir, "new", "frozen", "route_a_recon_manifest.json")
        @test !MGH.generate_manifest(joinpath(dir, "absent-third.toml"), calibration_path,
            "frozen", missing_parent_output)
        @test isfile(joinpath(dirname(missing_parent_output), "route_a_recon_manifest-refusal.json"))

        # Refusal invalidates the manifest before quarantining an unsafe task tree.
        write(output, "third stale approval")
        task_dir = joinpath(dir, "frozen-tasks")
        mkpath(task_dir)
        sentinel = joinpath(dir, "sentinel")
        write(sentinel, "immutable")
        symlink(sentinel, joinpath(task_dir, "unsafe-link"))
        @test !MGH.generate_manifest(joinpath(dir, "absent-fourth.toml"), calibration_path,
            "frozen", output)
        @test !ispath(output)
        @test !ispath(task_dir)
        @test read(sentinel, String) == "immutable"
        refusal_path = joinpath(dir, "frozen-refusal.json")
        @test isfile(refusal_path)
        recovery = joinpath(dir, ".frozen-recovery")
        @test JSON.parsefile(refusal_path)["recovery_path"] == recovery
        @test isdir(recovery)
        @test islink(joinpath(recovery, "unsafe-link"))

        # Repeating the same refusal is idempotent: no uniquely named hidden
        # bundles accumulate and the one recovery location remains recorded.
        @test !MGH.generate_manifest(joinpath(dir, "absent-fourth.toml"), calibration_path,
            "frozen", output)
        @test JSON.parsefile(refusal_path)["recovery_path"] == recovery
        @test count(name -> occursin("recovery", name), readdir(dir)) == 1
    end
end

@testset "approved frozen generation writes a campaign-bound resource estimate" begin
    config = MGH.load_recon_config()
    mktempdir() do dir
        config_path = joinpath(dir, "route_a_recon.toml")
        cp(joinpath(MGH._RECON_ROOT, "config", "route_a_recon.toml"), config_path)
        calibration_path = write_calibration_fixture(joinpath(dir, "calibration.json"), config)
        output = joinpath(dir, "route_a_recon_manifest.json")
        @test MGH.generate_manifest(config_path, calibration_path, "frozen", output)
        campaign = MGH._read_campaign_manifest(output)
        estimate_path = joinpath(dir, "route_a_resource_estimate.json")
        @test isfile(estimate_path)
        estimate = JSON.parsefile(estimate_path)
        @test estimate["schema_version"] == 3
        @test estimate["estimate_checksum"] == MGH._resource_estimate_checksum(estimate)
        @test estimate["calibration_path"] == "route_a_calibration.json"
        @test estimate["config_path"] == "route_a_recon_config.toml"
        @test read(joinpath(dir, estimate["calibration_path"])) == read(calibration_path)
        @test read(joinpath(dir, estimate["config_path"])) == read(config_path)
        @test estimate["calibration_content_sha256"] ==
            MGH.bytes2hex(MGH.sha256(read(calibration_path)))
        @test estimate["config_content_sha256"] ==
            MGH.bytes2hex(MGH.sha256(read(config_path)))
        @test estimate["campaign_checksum"] == campaign.campaign_checksum
        @test estimate["release_git_commit"] == campaign.git_commit
        @test estimate["task_count"] == 528
        @test length(estimate["task_resources"]) == 528
        @test estimate["predicted_cpu_seconds"] ==
            sum(detail["predicted_wall_seconds"] for detail in estimate["task_resources"])
        @test estimate["max_task_memory_bytes"] ==
            maximum(detail["predicted_memory_bytes"] for detail in estimate["task_resources"])
        @test estimate["predicted_disk_bytes"] <= estimate["disk_fraction_limit"] * estimate["requested_disk_bytes"]
        recomputed = MGH._recompute_resource_estimate(output, campaign, estimate)
        @test MGH._same_resource_estimate(estimate, recomputed)
        @test MGH.audit_frozen_manifest(output) == (passed=true, errors=String[])
        calibration_snapshot = joinpath(dir, estimate["calibration_path"])
        config_snapshot = joinpath(dir, estimate["config_path"])
        calibration_snapshot_bytes = read(calibration_snapshot)
        config_snapshot_bytes = read(config_snapshot)

        forged = JSON.parsefile(estimate_path; dicttype=Dict)
        for detail in forged["task_resources"]
            detail["predicted_wall_seconds"] = 1.0
            detail["predicted_memory_bytes"] = 1.0
            detail["predicted_disk_bytes"] = 1.0
        end
        forged["predicted_cpu_seconds"] =
            sum(detail["predicted_wall_seconds"] for detail in forged["task_resources"])
        forged["max_task_wall_seconds"] =
            maximum(detail["predicted_wall_seconds"] for detail in forged["task_resources"])
        forged["max_task_memory_bytes"] =
            maximum(detail["predicted_memory_bytes"] for detail in forged["task_resources"])
        forged["predicted_disk_bytes"] =
            sum(detail["predicted_disk_bytes"] for detail in forged["task_resources"])
        forged["estimate_checksum"] = MGH._resource_estimate_checksum(forged)
        MGH.atomic_write_json(estimate_path, forged)
        forged_audit = MGH.audit_frozen_manifest(output)
        @test !forged_audit.passed
        @test "resource_estimate" in forged_audit.errors

        MGH.atomic_write_json(estimate_path, estimate)
        MGH._atomic_write_bytes(config_snapshot, vcat(config_snapshot_bytes, codeunits("\n# tampered\n")))
        @test "resource_estimate" in MGH.audit_frozen_manifest(output).errors
        MGH._atomic_write_bytes(config_snapshot, config_snapshot_bytes)

        for field in ("accounting_snapshot_sha256", "result_provenance_sha256")
            tampered = JSON.parse(String(copy(calibration_snapshot_bytes)); dicttype=Dict)
            tampered[field] = repeat(field == "accounting_snapshot_sha256" ? "7" : "8", 64)
            MGH.atomic_write_json(calibration_snapshot, tampered)
            @test "resource_estimate" in MGH.audit_frozen_manifest(output).errors
            MGH._atomic_write_bytes(calibration_snapshot, calibration_snapshot_bytes)
        end
    end
end

@testset "manifest CLI grammar is strict and nonfrozen modes ignore production data" begin
    @test MGH.parse_manifest_args(["--config", "c", "--calibration", "none", "--mode", "candidate", "--output", "o.json"]) ==
          (config_path="c", calibration_path="none", mode=:candidate, output_path="o.json")
    @test_throws ArgumentError MGH.parse_manifest_args(String[])
    @test_throws ArgumentError MGH.parse_manifest_args(["--mode", "candidate", "--config", "c", "--calibration", "none", "--output", "o"])
    @test_throws ArgumentError MGH.parse_manifest_args(["--config", "c", "--calibration", "none", "--mode", "other", "--output", "o"])
    mktempdir() do dir
        config_path = joinpath(dir, "config.toml")
        cp(joinpath(MGH._RECON_ROOT, "config", "route_a_recon.toml"), config_path)
        output = joinpath(dir, "candidate.json")
        @test MGH.generate_manifest(config_path, joinpath(dir, "absent.json"), "candidate", output)
        @test length(MGH._read_campaign_manifest(output).tasks) == 528
    end
end
