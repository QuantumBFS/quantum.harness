using Test
using JSON
using SHA

module CalibrationBuilderHarness
include(joinpath(@__DIR__, "..", "scripts", "build_route_a_calibration.jl"))
end

const C = CalibrationBuilderHarness

@testset "calibration builder CLI grammar is exact" begin
    @test C.parse_calibration_args([
        "--campaign", "campaign.json",
        "--task-paths", "task_paths.txt",
        "--results", "results",
        "--accounting", "evidence",
        "--bundle-script", "route_a_bundle.sbatch",
        "--output", "calibration",
    ]) == (
        campaign_path="campaign.json",
        task_paths_path="task_paths.txt",
        results_path="results",
        evidence_path="evidence",
        bundle_script_path="route_a_bundle.sbatch",
        output_path="calibration",
    )
    @test_throws ArgumentError C.parse_calibration_args(String[])
    @test_throws ArgumentError C.parse_calibration_args([
        "--results", "results", "--campaign", "campaign.json",
        "--task-paths", "task_paths.txt", "--accounting", "evidence",
        "--bundle-script", "bundle", "--output", "out",
    ])
end

@testset "SCNet memory units normalize to exact bytes" begin
    @test C.parse_slurm_memory("4063576K") == 4_161_101_824
    @test C.parse_slurm_memory("64G") == 68_719_476_736
    @test C.parse_slurm_memory("8Gc") == 8_589_934_592
    @test C.parse_slurm_memory("1024Mn") == 1_073_741_824
    @test_throws ArgumentError C.parse_slurm_memory("")
    @test_throws ArgumentError C.parse_slurm_memory("64")
    @test_throws ArgumentError C.parse_slurm_memory("-1G")
    @test_throws ArgumentError C.parse_slurm_memory("1GB")
    @test_throws ArgumentError C.parse_slurm_memory("18446744073709551615G")
end

@testset "SCNet durations normalize to exact seconds" begin
    @test C.parse_slurm_seconds("210") == 210
    @test C.parse_slurm_seconds("01:12:41") == 4361
    @test C.parse_slurm_seconds("1-00:00:00") == 86400
    @test C.parse_slurm_seconds("2-03:04:05") == 183_845
    @test_throws ArgumentError C.parse_slurm_seconds("")
    @test_throws ArgumentError C.parse_slurm_seconds("-1")
    @test_throws ArgumentError C.parse_slurm_seconds("01:60:00")
    @test_throws ArgumentError C.parse_slurm_seconds("1-24:00:00")
    @test_throws ArgumentError C.parse_slurm_seconds("Unknown")
end

function write_accounting_fixture(root; mutation::Symbol=:complete)
    mkpath(joinpath(root, "wrappers"))
    first_wrapper = "route_a_bundle: completed task indices 0-7\n"
    second_range = mutation == :overlap ? "7-15" :
        mutation in (:short, :probe) ? "8-11" :
        mutation == :forged_mapping ? "9-16" : "8-15"
    second_task = mutation == :probe ? 2 : 1
    second_bundle = mutation == :probe ? 4 : 8
    second_wrapper = "route_a_bundle: completed task indices $second_range\n"
    write(joinpath(root, "wrappers", "probe-8000_0.out"), first_wrapper)
    write(joinpath(root, "wrappers", "probe-8000_$second_task.out"), second_wrapper)
    first_sha = bytes2hex(sha256(codeunits(first_wrapper)))
    second_sha = bytes2hex(sha256(codeunits(second_wrapper)))
    inventory = join([
        "allocation_key|raw_job_id|array_task_id|wrapper_file|wrapper_sha256|start_index|end_index",
        "8000_0|9001|0|probe-8000_0.out|$first_sha|0|7",
        "8000_$second_task|9002|$second_task|probe-8000_$second_task.out|$second_sha|" *
            replace(second_range, "-" => "|"),
    ], "\n") * "\n"
    mutation == :wrong_inventory_header &&
        (inventory = replace(inventory, "allocation_key" => "allocation"; count=1))
    write(joinpath(root, "wrapper_inventory.psv"), inventory)

    state = mutation == :failed ? "FAILED" : "COMPLETED"
    reqmem = mutation == :bad_memory ? "64GB" : "64G"
    rows = [
        "JobIDRaw|JobID|JobName|State|ElapsedRaw|TimelimitRaw|ReqMem|AllocCPUS|MaxRSS|ExitCode|SubmitLine",
        "9001|8000_0|route_a_bundle.sbatch|COMPLETED|210|1800|64G|8||0:0|sbatch --array=0 --export=ALL,BUNDLE_SIZE=8",
        "9001.batch|8000_0.batch|batch|COMPLETED|210|||8|4063576K|0:0|",
        "9002|8000_$second_task|route_a_bundle.sbatch|$state|221|1800|$reqmem|8||0:0|sbatch --array=$second_task --export=ALL,BUNDLE_SIZE=$second_bundle",
        "9002.batch|8000_$second_task.batch|batch|COMPLETED|221|||8|4100000K|0:0|",
    ]
    mutation == :missing_batch && deleteat!(rows, 5)
    mutation == :wrong_sacct_header && (rows[1] = replace(rows[1], "JobIDRaw" => "RawJobID"))
    write(joinpath(root, "sacct.psv"), join(rows, "\n") * "\n")

    result_count = mutation in (:short, :probe) ? 12 : mutation == :overlap ? 17 : 16
    result_rows = ["result_file|result_sha256|slurm_job_id"]
    for index in 0:(result_count - 1)
        job = index < 8 ? "9001" : "9002"
        push!(result_rows, "result-$index.json|" * repeat(string(index % 10), 64) * "|$job")
    end
    write(joinpath(root, "result_provenance.psv"), join(result_rows, "\n") * "\n")
    capture = Dict{String,Any}(
        "schema_version" => 1,
        "kind" => "route_a_accounting_capture",
        "campaign_sha256" => repeat("a", 64),
        "bundle_script_sha256" => repeat("b", 64),
        "sacct_sha256" => bytes2hex(sha256(read(joinpath(root, "sacct.psv")))),
        "wrapper_inventory_sha256" => bytes2hex(sha256(read(joinpath(root, "wrapper_inventory.psv")))),
        "result_provenance_sha256" => bytes2hex(sha256(read(joinpath(root, "result_provenance.psv")))),
        "allocation_count" => 2,
        "result_count" => result_count,
    )
    mutation == :forged_hash && (capture["sacct_sha256"] = repeat("f", 64))
    open(joinpath(root, "capture.json"), "w") do io
        JSON.print(io, capture)
        write(io, '\n')
    end
    return root
end

@testset "accounting evidence preserves allocation grain" begin
    mktempdir() do dir
        evidence = C.read_accounting_evidence(write_accounting_fixture(dir))
        @test isimmutable(evidence)
        @test length(evidence.allocations) == 2
        first = evidence.allocations[1]
        @test isimmutable(first)
        @test first.allocation_key == "8000_0"
        @test first.raw_job_id == "9001"
        @test first.array_task_id == 0
        @test first.requested_memory_bytes == 68_719_476_736
        @test first.requested_walltime_seconds == 1800
        @test first.elapsed_seconds == 210
        @test first.max_rss_upper_bytes == 4_161_101_824
        @test first.alloc_cpus == 8
        @test first.task_indices == Tuple(0:7)
        @test first.bundle_size == 8
        @test first.nominal_bundle_size == 8
        @test first.canonical_accounting_rows == (
            "9001|8000_0|route_a_bundle.sbatch|COMPLETED|210|1800|64G|8||0:0|sbatch --array=0 --export=ALL,BUNDLE_SIZE=8",
            "9001.batch|8000_0.batch|batch|COMPLETED|210|||8|4063576K|0:0|",
        )
        table = C.build_allocation_table(evidence; expected_task_count=16)
        @test length(table) == 16
        @test table[0].allocation_key == "8000_0"
        @test table[15].allocation_key == "8000_1"
    end

    mktempdir() do dir
        evidence = C.read_accounting_evidence(write_accounting_fixture(dir; mutation=:short))
        @test evidence.allocations[2].task_indices == Tuple(8:11)
        @test evidence.allocations[2].bundle_size == 4
        @test evidence.allocations[2].nominal_bundle_size == 8
        @test length(C.build_allocation_table(evidence; expected_task_count=12)) == 12
    end

    mktempdir() do dir
        evidence = C.read_accounting_evidence(write_accounting_fixture(dir; mutation=:probe))
        @test evidence.allocations[2].array_task_id == 2
        @test evidence.allocations[2].task_indices == Tuple(8:11)
        @test evidence.allocations[2].nominal_bundle_size == 4
        @test length(C.build_allocation_table(evidence; expected_task_count=12)) == 12
    end
end

@testset "accounting evidence fails closed" begin
    for mutation in (
        :wrong_inventory_header,
        :wrong_sacct_header,
        :forged_hash,
        :failed,
        :missing_batch,
        :bad_memory,
        :forged_mapping,
    )
        mktempdir() do dir
            @test_throws ArgumentError C.read_accounting_evidence(
                write_accounting_fixture(dir; mutation))
        end
    end
    mktempdir() do dir
        @test_throws ArgumentError C.read_accounting_evidence(
            write_accounting_fixture(dir; mutation=:overlap))
    end
end

function write_audited_benchmark_fixture(root)
    task_dir = joinpath(root, "benchmark-tasks")
    results = joinpath(root, "results")
    evidence = joinpath(root, "evidence")
    bundle_script = joinpath(root, "route_a_bundle.sbatch")
    mkpath(task_dir)
    mkpath(results)
    mkpath(joinpath(evidence, "wrappers"))
    write(bundle_script, "#!/usr/bin/env bash\n# fixture bundle\n")
    release_commit = String(readchomp(`git -C $(joinpath(@__DIR__, "..")) rev-parse HEAD`))
    manifest_hash = bytes2hex(sha256(read(joinpath(@__DIR__, "..", "Manifest.toml"))))
    old_h = 4.76811
    tasks = C.ClusterTask[]
    task_number = 0
    for replica in 1:2, offset in (-0.01, 0.0, 0.01)
        task_number += 1
        push!(tasks, C.ClusterTask(
            1, :triangle, 3, 1.0, old_h + offset, 1.0, replica,
            UInt64(100 + task_number), 10, 20, 5, 1,
            "fixture-result-$task_number.json",
        ))
    end
    for replica in 3:4
        task_number += 1
        push!(tasks, C.ClusterTask(
            1, :triangle, 3, 1.0, old_h, 1.0, replica,
            UInt64(100 + task_number), 20, 20, 5, 1,
            "fixture-result-$task_number.json",
        ))
    end
    sort!(tasks; by=C.task_id)
    campaign_path = joinpath(root, "benchmark.json")
    C.write_campaign_manifest(
        campaign_path, "fixture-benchmark", release_commit, manifest_hash, tasks)
    task_entries = String[]
    result_rows = ["result_file|result_sha256|slurm_job_id"]
    for (manifest_index, task) in enumerate(tasks)
        task_entry = C.task_id(task) * ".json"
        C.write_task(joinpath(task_dir, task_entry), task)
        push!(task_entries, task_entry)
        bins = C.BinRecord[]
        for bin_index in 1:4
            shift = 0.003 * manifest_index + 0.007 * bin_index
            m2 = 0.35 + shift
            m4 = m2^2 + 0.08 + 0.001 * bin_index
            histogram = C.CutHistogramBin([bin_index], [5], [5m2], [5m4])
            push!(bins, C.BinRecord(
                -1.2 - shift, m2, m4,
                m2 + 0.02, (m2 + 0.02)^2 + 0.09, 2.0 + shift, histogram,
            ))
        end
        record = withenv(
            "SLURM_JOB_ID" => "9001",
            "SLURM_ARRAY_TASK_ID" => string(manifest_index - 1),
        ) do
            C._result_record(
                task, release_commit, manifest_hash, bins,
                "2026-07-29T00:00:00Z", time() - 1.0,
            )
        end
        mutable_record = JSON.parse(JSON.json(record); dicttype=Dict)
        mutable_record["provenance"]["wall_seconds"] = 10.0 + manifest_index
        result_path = joinpath(results, task.output_path)
        C.atomic_write_json(result_path, mutable_record)
        push!(result_rows,
            task.output_path * "|" * bytes2hex(sha256(read(result_path))) * "|9001")
    end
    write(joinpath(task_dir, "task_paths.txt"), join(task_entries, "\n") * "\n")

    wrapper_name = "fixture-8000_0.out"
    wrapper_content = "route_a_bundle: completed task indices 0-7\n"
    write(joinpath(evidence, "wrappers", wrapper_name), wrapper_content)
    wrapper_sha = bytes2hex(sha256(codeunits(wrapper_content)))
    inventory = join([
        "allocation_key|raw_job_id|array_task_id|wrapper_file|wrapper_sha256|start_index|end_index",
        "8000_0|9001|0|$wrapper_name|$wrapper_sha|0|7",
    ], "\n") * "\n"
    write(joinpath(evidence, "wrapper_inventory.psv"), inventory)
    accounting = join([
        "JobIDRaw|JobID|JobName|State|ElapsedRaw|TimelimitRaw|ReqMem|AllocCPUS|MaxRSS|ExitCode|SubmitLine",
        "9001|8000_0|route_a_bundle.sbatch|COMPLETED|210|1800|64G|8||0:0|sbatch --array=0 --export=ALL,BUNDLE_SIZE=8",
        "9001.batch|8000_0.batch|batch|COMPLETED|210|||8|4063576K|0:0|",
    ], "\n") * "\n"
    write(joinpath(evidence, "sacct.psv"), accounting)
    result_provenance = join(result_rows, "\n") * "\n"
    write(joinpath(evidence, "result_provenance.psv"), result_provenance)
    capture = Dict{String,Any}(
        "schema_version" => 1,
        "kind" => "route_a_accounting_capture",
        "campaign_sha256" => bytes2hex(sha256(read(campaign_path))),
        "bundle_script_sha256" => bytes2hex(sha256(read(bundle_script))),
        "sacct_sha256" => bytes2hex(sha256(codeunits(accounting))),
        "wrapper_inventory_sha256" => bytes2hex(sha256(codeunits(inventory))),
        "result_provenance_sha256" => bytes2hex(sha256(codeunits(result_provenance))),
        "allocation_count" => 1,
        "result_count" => 8,
    )
    C.atomic_write_json(joinpath(evidence, "capture.json"), capture)
    return (
        campaign_path=campaign_path,
        task_paths_path=joinpath(task_dir, "task_paths.txt"),
        results_path=results,
        evidence_path=evidence,
        bundle_script_path=bundle_script,
        release_commit=release_commit,
        tasks=tasks,
    )
end


@testset "schema-4 build is byte-stable and keeps memory at allocation grain" begin
    mktempdir() do dir
        fixture = write_audited_benchmark_fixture(joinpath(dir, "inputs"))
        resolve_anchor = task -> begin
            delta = task.h - 4.76811
            abs(delta) < 1e-12 ? 0.0 : delta < 0 ? -0.6 : 0.6
        end
        reference = task -> task.h == 4.76811 && task.thermalization_sweeps == 20
        slope = record -> record.anchor_x == 0.0 &&
            record.thermalization_sweeps == 10 && record.replica <= 2
        first_output = joinpath(dir, "build-one")
        second_output = joinpath(dir, "build-two")
        for output in (first_output, second_output)
            C.build_calibration(
                fixture.campaign_path, fixture.task_paths_path, fixture.results_path,
                fixture.evidence_path, fixture.bundle_script_path, output;
                expected_campaign_id="fixture-benchmark", expected_task_count=8,
                expected_release_commit=fixture.release_commit,
                anchor_resolver=resolve_anchor,
                reference_selector=reference,
                slope_required=slope,
            )
        end
        @test read(joinpath(first_output, "calibration.json")) ==
            read(joinpath(second_output, "calibration.json"))
        @test read(joinpath(first_output, "CALIBRATION.md")) ==
            read(joinpath(second_output, "CALIBRATION.md"))
        calibration = JSON.parsefile(joinpath(first_output, "calibration.json"); dicttype=Dict)
        @test calibration["schema_version"] == 4
        @test calibration["kind"] == "route_a_calibration"
        @test calibration["campaign_id"] == "fixture-benchmark"
        @test length(calibration["allocations"]) == 1
        @test length(calibration["records"]) == 8
        @test calibration["resource_summary"]["memory_fit_sample_count"] == 1
        allocation = only(calibration["allocations"])
        @test allocation["requested_memory_bytes"] == 68_719_476_736
        @test allocation["max_rss_upper_bytes"] == 4_161_101_824
        @test allocation["bundle_size"] == 8
        @test all(record -> record["max_rss_upper_bytes"] == 4_161_101_824,
            calibration["records"])
        @test all(record ->
            record["nominal_requested_memory_per_chain_bytes"] == 8_589_934_592,
            calibration["records"])
        @test count(record -> record["binder_slope"] !== nothing,
            calibration["records"]) == 2
        @test count(record -> record["tau_int_base_bins"] !== nothing,
            calibration["records"]) == 2
        @test occursin("Allocation-grain memory samples: 1",
            read(joinpath(first_output, "CALIBRATION.md"), String))

        original = read(joinpath(first_output, "calibration.json"))
        @test_throws ArgumentError C.build_calibration(
            fixture.campaign_path, fixture.task_paths_path, fixture.results_path,
            fixture.evidence_path, fixture.bundle_script_path, first_output;
            expected_campaign_id="fixture-benchmark", expected_task_count=8,
            expected_release_commit=fixture.release_commit,
            anchor_resolver=resolve_anchor, reference_selector=reference,
            slope_required=slope)
        @test read(joinpath(first_output, "calibration.json")) == original

        write(fixture.bundle_script_path, "changed\n")
        refused = joinpath(dir, "refused")
        @test_throws ArgumentError C.build_calibration(
            fixture.campaign_path, fixture.task_paths_path, fixture.results_path,
            fixture.evidence_path, fixture.bundle_script_path, refused;
            expected_campaign_id="fixture-benchmark", expected_task_count=8,
            expected_release_commit=fixture.release_commit,
            anchor_resolver=resolve_anchor, reference_selector=reference,
            slope_required=slope)
        @test !ispath(refused)
    end
end

@testset "benchmark audit maps task inputs to immutable result outputs" begin
    mktempdir() do dir
        fixture = write_audited_benchmark_fixture(dir)
        audited = C.audit_benchmark_inputs(
            fixture.campaign_path,
            fixture.task_paths_path,
            fixture.results_path,
            fixture.evidence_path;
            expected_campaign_id="fixture-benchmark",
            expected_task_count=8,
            expected_release_commit=fixture.release_commit,
        )
        @test length(audited.tasks) == 8
        @test length(audited.results) == 8
        @test length(audited.allocations) == 1
        @test audited.task_paths_sha256 == bytes2hex(sha256(read(fixture.task_paths_path)))
        @test audited.campaign_sha256 == bytes2hex(sha256(read(fixture.campaign_path)))
        @test all(index ->
            audited.results[index]["task"]["output_path"] == audited.tasks[index].output_path,
            eachindex(audited.tasks))
        @test all(index ->
            audited.results[index]["provenance"]["slurm_array_task_id"] == string(index - 1),
            eachindex(audited.tasks))
        @test all(==("9001"),
            getindex.(getindex.(audited.results, "provenance"), "slurm_job_id"))

        first_result = joinpath(fixture.results_path, audited.tasks[1].output_path)
        original_result = read(first_result)
        tampered = JSON.parse(String(copy(original_result)); dicttype=Dict)
        tampered["raw_bins"]["energy_per_site"][1] += 1.0
        C.atomic_write_json(first_result, tampered)
        @test_throws ArgumentError C.audit_benchmark_inputs(
            fixture.campaign_path, fixture.task_paths_path, fixture.results_path,
            fixture.evidence_path;
            expected_campaign_id="fixture-benchmark", expected_task_count=8,
            expected_release_commit=fixture.release_commit)
        write(first_result, original_result)

        original_paths = read(fixture.task_paths_path)
        entries = readlines(fixture.task_paths_path)
        entries[1] = audited.tasks[1].output_path
        write(fixture.task_paths_path, join(entries, "\n") * "\n")
        @test_throws ArgumentError C.audit_benchmark_inputs(
            fixture.campaign_path, fixture.task_paths_path, fixture.results_path,
            fixture.evidence_path;
            expected_campaign_id="fixture-benchmark", expected_task_count=8,
            expected_release_commit=fixture.release_commit)
        write(fixture.task_paths_path, original_paths)
    end
end

@testset "chain records derive direct raw-bin statistics and allocation links" begin
    mktempdir() do dir
        fixture = write_audited_benchmark_fixture(dir)
        audited = C.audit_benchmark_inputs(
            fixture.campaign_path, fixture.task_paths_path, fixture.results_path,
            fixture.evidence_path;
            expected_campaign_id="fixture-benchmark", expected_task_count=8,
            expected_release_commit=fixture.release_commit)
        record = C.derive_chain_record(audited, 1; anchor_x=-0.6)
        task = audited.tasks[1]
        @test isimmutable(record)
        @test record.manifest_index == 0
        @test record.task_id == C.task_id(task)
        @test record.task_hash == C.task_hash(task)
        @test record.seed == "u64:" * string(task.seed; base=16, pad=16)
        @test record.allocation_key == "8000_0"
        @test record.raw_slurm_job_id == "9001"
        @test record.slurm_task_index == 0
        @test record.energy_mean ≈ -1.2205 atol=1e-15
        @test record.energy_stderr ≈ 0.004518480570575338 atol=1e-15
        @test record.energy_first_half_mean ≈ -1.2135 atol=1e-15
        @test record.energy_first_half_stderr ≈ 0.0035 atol=1e-15
        @test record.energy_second_half_mean ≈ -1.2275 atol=1e-15
        @test record.energy_second_half_stderr ≈ 0.0035 atol=1e-15
        @test record.binder_mean ≈ 0.624433941450611 atol=1e-15
        @test record.binder_stderr ≈ 0.003886995199327732 atol=1e-15
        @test record.cut_count_mean ≈ 2.0205 atol=1e-15
        @test record.elapsed_seconds == 11.0
        @test record.elapsed_per_sweep_seconds ==
            11.0 / (task.thermalization_sweeps + task.measurement_sweeps)
        @test record.result_bytes == length(audited.result_bytes[1])
        @test record.max_rss_upper_bytes == 4_161_101_824
        @test record.nominal_requested_memory_per_chain_bytes == 8_589_934_592
        @test record.binder_slope === nothing
        @test record.tau_int_base_bins === nothing

        reference = C.derive_chain_record(
            audited, 1; anchor_x=-0.6, reference_diagnostics=true)
        @test reference.tau_int_base_bins >= 0.5
        @test reference.tau_int_stderr_base_bins >= 0.0
        @test reference.binder_variance_per_base_bin > 0.0
        @test reference.binder_variance_stderr_per_base_bin >= 0.0
    end
end

@testset "three-anchor slopes update only the central chain" begin
    rows = [
        (manifest_index=0, lattice=:triangle, L=16, c=1.0, replica=1,
            thermalization_sweeps=500, anchor_x=-0.6, h=4.0,
            binder_mean=0.8, binder_stderr=0.01,
            binder_slope=nothing, binder_slope_stderr=nothing),
        (manifest_index=1, lattice=:triangle, L=16, c=1.0, replica=1,
            thermalization_sweeps=500, anchor_x=0.0, h=5.0,
            binder_mean=0.6, binder_stderr=0.01,
            binder_slope=nothing, binder_slope_stderr=nothing),
        (manifest_index=2, lattice=:triangle, L=16, c=1.0, replica=1,
            thermalization_sweeps=500, anchor_x=0.6, h=6.0,
            binder_mean=0.4, binder_stderr=0.01,
            binder_slope=nothing, binder_slope_stderr=nothing),
    ]
    updated = C.derive_three_anchor_slopes(rows; slope_required=_ -> true)
    @test updated[1].binder_slope === nothing
    @test updated[2].binder_slope ≈ -0.2 atol=1e-15
    @test updated[2].binder_slope_stderr ≈ 0.007071067811865475 atol=1e-15
    @test updated[3].binder_slope === nothing
    @test getfield.(updated, :manifest_index) == [0, 1, 2]
    @test_throws ArgumentError C.derive_three_anchor_slopes(rows[1:2]; slope_required=_ -> true)
    @test_throws ArgumentError C.derive_three_anchor_slopes(
        [rows[1], rows[2], merge(rows[3], (anchor_x=0.0,))]; slope_required=_ -> true)
end
