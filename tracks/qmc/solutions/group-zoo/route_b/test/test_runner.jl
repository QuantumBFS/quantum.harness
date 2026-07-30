@testset "controlled runner resume is deterministic" begin
    task = tiny_task()
    root = mktempdir()
    full_path = joinpath(root, "full.checkpoint")
    partial_path = joinpath(root, "partial.checkpoint")
    full = run_task(task; checkpoint_path=full_path)
    partial = run_task(task; checkpoint_path=partial_path, stop_after_bins=3)
    @test partial.status == :partial
    resumed = run_task(task; checkpoint_path=partial_path, resume=true)
    @test full.status == :complete
    @test resumed.status == :complete
    @test resumed.raw_bins == full.raw_bins
    @test resumed.completion_checksum == full.completion_checksum
end

@testset "JSON raw bins combine across independent replicas" begin
    first = RawBin(0.25, 0.0, 0.5, 0.5, 0.0, 0.0, 2.0, 3.0, 1.0, 2.0,
                   0.8, 0.8, 0.6, -2.3, 0.7, 0.6, 20, 80)
    second = RawBin(0.75, 1.0, 0.5, 1.0, 0.0, 0.0, 3.0, 4.0, 2.0, 2.0,
                    0.9, 0.9, 0.7, -2.5, 0.8, 0.7, 20, 120)
    payloads = [
        Dict("status" => "complete", "raw_bins" => [RouteBWorm._raw_bin_record(first)]),
        Dict("status" => "complete", "raw_bins" => [RouteBWorm._raw_bin_record(second)]),
    ]
    combined = summarize_result_payloads(payloads)
    @test combined["energy"] ≈ -2.4 atol=1e-15
    @test combined["mx"] ≈ 0.85 atol=1e-15
    @test combined["bond"] ≈ 0.65 atol=1e-15
    @test combined["worm_return"] ≈ 5.0 atol=1e-15
    @test_throws ArgumentError summarize_result_payloads([
        Dict("status" => "partial", "raw_bins" => [RouteBWorm._raw_bin_record(first)]),
    ])
end

@testset "runner bins retain closed observables and worm normalization" begin
    task = tiny_task(bins=4)
    root = mktempdir()
    result = run_task(task; checkpoint_path=joinpath(root, "observable.checkpoint"))
    @test result.raw_bins isa Vector{RawBin}
    @test length(result.raw_bins) == 4
    @test all(bin.z_visits == task.visits_per_bin for bin in result.raw_bins)
    @test all(bin.g_visits >= 0 for bin in result.raw_bins)
    @test result.elapsed_seconds > 0
    @test sum(values(result.proposed)) > 0
    @test all(result.accepted[family] <= result.proposed[family] for family in instances(ProposalFamily))
    @test all(result.illegal[family] <= result.proposed[family] for family in instances(ProposalFamily))

    summary = summarize_observable_bins(result.raw_bins)
    for name in ("R_down", "energy", "mx", "bond", "worm_return")
        @test isfinite(summary[name])
        @test isfinite(summary[name * "_stderr"])
        @test 0 < summary[name * "_ess"] <= length(result.raw_bins)
    end
    @test summary["worm_return"] ==
          sum(bin.g_visits for bin in result.raw_bins) /
          sum(bin.z_visits for bin in result.raw_bins)
end

@testset "complete result payloads are cryptographically rechecked" begin
    task = tiny_task(bins=4)
    result = run_task(task; checkpoint_path=joinpath(mktempdir(), "audit.checkpoint"))
    payload = Dict{String,Any}(
        "status" => "complete",
        "task_hash" => task_hash(task),
        "raw_bins" => [
            Dict(string(key) => value for (key, value) in pairs(RouteBWorm._raw_bin_record(bin)))
            for bin in result.raw_bins
        ],
        "summary" => summarize_observable_bins(result.raw_bins),
        "completion_checksum" => result.completion_checksum,
    )
    @test verify_result_payload(task, payload)

    tampered = deepcopy(payload)
    tampered["raw_bins"][1]["R_down"] += 0.125
    @test_throws ArgumentError verify_result_payload(task, tampered)

    wrong_hash = deepcopy(payload)
    wrong_hash["task_hash"] = repeat("0", 64)
    @test_throws ArgumentError verify_result_payload(task, wrong_hash)

    wrong_summary = deepcopy(payload)
    wrong_summary["summary"]["energy"] += 1e-8
    @test_throws ArgumentError verify_result_payload(task, wrong_summary)

    bad_provenance = deepcopy(payload)
    bad_provenance["git_commit"] = "not-a-commit"
    bad_provenance["manifest_sha256"] = repeat("b", 64)
    @test_throws ArgumentError verify_result_payload(task, bad_provenance)
end

@testset "result payload provenance is mandatory and frozen" begin
    task = tiny_task(bins=4)
    result = run_task(task; checkpoint_path=joinpath(mktempdir(), "provenance.checkpoint"))
    commit = repeat("a", 40)
    manifest = repeat("b", 64)
    payload = make_result_payload(
        task, result; git_commit=commit, manifest_sha256=manifest,
    )
    @test payload.git_commit == commit
    @test payload.manifest_sha256 == manifest
    @test payload.task_hash == task_hash(task)
    @test payload.status == "complete"
    @test_throws ArgumentError make_result_payload(
        task, result; git_commit="uncommitted", manifest_sha256=manifest,
    )
    @test_throws ArgumentError make_result_payload(
        task, result; git_commit=commit, manifest_sha256="bad",
    )
end
