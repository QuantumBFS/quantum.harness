using Test
using Random
using Statistics
using JSON
using LinearAlgebra
using SHA

if !isdefined(@__MODULE__, :Challenge148)
    include(joinpath(@__DIR__, "..", "src", "Challenge148.jl"))
end

using .Challenge148

const _FSS_SIZES = [8, 12, 16, 24, 32, 48, 64]
const _FSS_X_ANCHORS = (-0.6, 0.0, 0.6)
const _FSS_H_OLD = Dict(:triangle => 4.76811, :honeycomb => 2.13250)

_approved_anchors(lattice::Symbol, L::Int) =
    [_FSS_H_OLD[lattice] + x * L^-1.5868 for x in _FSS_X_ANCHORS]

function _synthetic_replicas(;
    include_thermal::Bool=true,
    replicas_per_group::Int=4,
    thermal_q_shifts=(triangle=1.0e-4, honeycomb=1.0e-4),
)
    replicas = ReplicaBinderData[]
    for (lattice, hc) in ((:triangle, 4.7682), (:honeycomb, 2.1325))
        for L in _FSS_SIZES, h in _approved_anchors(lattice, L), replica in 1:replicas_per_group
            Q = 0.63 - 0.08 * (h - hc) * L^1.5868 - 0.03 * L^-0.821
            Q += 5.0e-5 * (replica - (replicas_per_group + 1) / 2)
            bins = collect(Q .+ 5.0e-4 .* (-3.0, -1.0, 1.0, 3.0))
            push!(replicas, ReplicaBinderData(
                lattice, L, h, 1.0, replica, "$(lattice)-$L-$h-$replica",
                bins, bins,
            ))
        end
        if include_thermal
            for L in (24, 48), c in (1.5, 2.0), h in _approved_anchors(lattice, L), replica in 1:replicas_per_group
                Q = 0.63 - 0.08 * (h - hc) * L^1.5868 - 0.03 * L^-0.821
                Q += (c - 1.0) * getproperty(thermal_q_shifts, lattice) +
                     5.0e-5 * (replica - (replicas_per_group + 1) / 2)
                bins = collect(Q .+ 5.0e-4 .* (-3.0, -1.0, 1.0, 3.0))
                push!(replicas, ReplicaBinderData(
                    lattice, L, h, c, replica, "$(lattice)-$L-$h-$c-$replica",
                    bins, bins,
                ))
            end
        end
    end
    return replicas
end

function _combined_fixture(path::String)
    chains = Any[]
    for record in _synthetic_replicas(; replicas_per_group=8)
        task = ClusterTask(
            1, record.lattice, record.L, 1.0, record.h, record.c, record.replica,
            task_seed(:route_a, record.lattice, record.L, record.h, record.c, record.replica),
            0, 4, 1, 1, "chain-$(length(chains) + 1).json",
        )
        raw = (
            energy_per_site=zeros(4),
            m_time2=record.m2_bins,
            m_time4=record.m4_bins,
            m_equal2=record.m2_bins,
            m_equal4=record.m4_bins,
            cuts_mean=zeros(4),
            cut_histogram=[(cut_counts=[0], counts=[1], sum_m2=[record.m2_bins[i]],
                            sum_m4=[record.m4_bins[i]]) for i in 1:4],
        )
        push!(chains, (
            task_id=task_id(task),
            task_hash=task_hash(task),
            task=merge(Challenge148._task_json(task), (canonical_task=canonical_task_string(task),)),
            provenance=(
                git_commit=repeat("a", 40),
                manifest_sha256=repeat("c", 64),
                julia_version=string(VERSION),
                hostname="synthetic-host",
                slurm_job_id=nothing,
                slurm_array_task_id=nothing,
                started_at="2026-07-28T00:00:00",
                completed_at="2026-07-28T00:01:00",
                wall_seconds=60.0,
            ),
            completed_bins=4,
            raw_bins=raw,
        ))
    end
    atomic_write_json(path, (
        schema_version=1,
        kind="route_a_combined_bins",
        campaign_id="synthetic",
        campaign_checksum=repeat("b", 64),
        julia_manifest_sha256=repeat("c", 64),
        git_commit=repeat("a", 40),
        julia_version=string(VERSION),
        algorithm="continuous_time_cluster",
        observable_schema_version=2,
        chains=chains,
    ))
    return path
end

function _replace_first_task!(combined; J=nothing, L=nothing, h=nothing, c=nothing)
    chain = first(combined["chains"])
    old = chain["task"]
    lattice = Symbol(old["lattice"])
    task = ClusterTask(
        old["schema_version"], lattice, something(L, old["L"]),
        something(J, old["J"]), something(h, old["h"]), something(c, old["c"]),
        old["replica"], task_seed(
            :route_a, lattice, something(L, old["L"]), something(h, old["h"]),
            something(c, old["c"]), old["replica"]),
        old["thermalization_sweeps"], old["measurement_sweeps"], old["base_bin_size"],
        old["checkpoint_interval_bins"], old["output_path"],
    )
    chain["task"] = Dict(string(key) => value for (key, value) in pairs(
        merge(Challenge148._task_json(task), (canonical_task=canonical_task_string(task),))))
    chain["task_id"] = task_id(task)
    chain["task_hash"] = task_hash(task)
    return combined
end

function _windows_fixture(path::String; status::String="route A preliminary; not a final Challenge #148 verdict")
    open(path, "w") do io
        write(io, """
models = ["M1", "M2", "M3"]
L_min = [8, 12, 16, 24]
yt_modes = ["fixed", "free"]
yt_fixed = 1.5868
yt_free_bounds = [1.50, 1.67]
yi_fixed = -0.821
minimum_degrees_of_freedom = 2
maximum_reduced_chi_square = 2.0
bootstrap_seed = 148900
bootstrap_draws = 2000
reweight_ess_fraction = 0.30
status = "$status"
""")
    end
    return path
end

module AnalysisScriptHarness
const script_path = joinpath(@__DIR__, "..", "scripts", "analyze_route_a.jl")
isfile(script_path) && include(script_path)
end

@testset "analysis CLI is strict and writes only preliminary atomic reports" begin
    @test AnalysisScriptHarness.parse_analysis_args([
        "--data", "combined.json", "--windows", "windows.toml", "--output", "out",
    ]) == (data_path="combined.json", windows_path="windows.toml", output_dir="out")
    @test_throws ArgumentError AnalysisScriptHarness.parse_analysis_args([
        "--data", "combined.json", "--windows", "windows.toml", "--output", "out", "--final",
    ])
    mktempdir() do dir
        data = _combined_fixture(joinpath(dir, "combined_bins.json"))
        windows = _windows_fixture(joinpath(dir, "windows.toml"))
        output = joinpath(dir, "output")
        mkpath(output)
        @test_throws MethodError AnalysisScriptHarness.write_route_a_analysis(
            data, windows, output; draws_override=10)
        paths = AnalysisScriptHarness._write_route_a_test_analysis(
            data, windows, output; draws=10)
        report = JSON.parsefile(paths.preliminary)
        fit_windows = JSON.parsefile(paths.fit_windows)
        @test occursin("TEST_ONLY", basename(paths.preliminary))
        @test report["status"] == "route A preliminary; not a final Challenge #148 verdict"
        @test report["analysis_mode"] == "test_nonproduction"
        @test report["production_eligible"] == false
        @test report["bootstrap"]["seed"] == 148900
        @test report["bootstrap"]["draws"] == 10
        @test report["bootstrap"]["mode"] == "test_nonproduction"
        @test report["inputs"]["campaign_id"] == "synthetic"
        @test report["inputs"]["campaign_checksum"] == repeat("b", 64)
        @test report["inputs"]["git_commit"] == repeat("a", 40)
        @test report["inputs"]["julia_manifest_sha256"] == repeat("c", 64)
        @test report["inputs"]["data_content_sha256"] == bytes2hex(sha256(read(data)))
        @test report["inputs"]["window_config_content_sha256"] == bytes2hex(sha256(read(windows)))
        @test fit_windows["inputs"] == report["inputs"]
        @test length(fit_windows["fit_windows"]) == 48
        @test isempty(filter(name -> endswith(name, ".partial"), readdir(output)))

        invalid = _windows_fixture(joinpath(dir, "invalid.toml"); status="final verdict")
        @test_throws ArgumentError AnalysisScriptHarness._write_route_a_test_analysis(
            data, invalid, output; draws=10)
    end
end

@testset "failed attempted fits serialize as explicit JSON null diagnostics" begin
    overflow_points = [(
        lattice=:triangle, L=L, h=h, c=1.0, Q=1.0e308, sigma=1.0, source=:direct,
    ) for L in _FSS_SIZES for h in _approved_anchors(:triangle, L)]
    failed = AnalysisScriptHarness.Challenge148.fit_binder_window(
        overflow_points; model=:M1, L_min=8, yt_mode=:fixed)
    @test !failed.converged
    @test !failed.accepted
    row = AnalysisScriptHarness._fit_record(failed, :triangle)
    @test row.chi2 === nothing
    @test row.reduced_chi2 === nothing
    @test row.parameters["Qc"] === nothing
    covariance_values = [value for covariance_row in row.covariance for value in covariance_row]
    @test all(value === nothing || isfinite(value) for value in covariance_values)
    @test !isempty(row.rejection_reasons)
    mktempdir() do dir
        path = joinpath(dir, "failed-window.json")
        atomic_write_json(path, (fit_windows=[row],))
        parsed = JSON.parsefile(path)
        @test parsed["fit_windows"][1]["chi2"] === nothing
        @test parsed["fit_windows"][1]["converged"] == false
    end
end

@testset "Task 8 combined schema is validated and converted to replicas" begin
    mktempdir() do dir
        path = _combined_fixture(joinpath(dir, "combined_bins.json"))
        data = read_combined_binder_data(path)
        @test length(data.records) == length(_synthetic_replicas(; replicas_per_group=8))
        @test first(data.records).m2_bins == first(_synthetic_replicas(; replicas_per_group=8)).m2_bins
        @test data.campaign_id == "synthetic"
        @test data.campaign_checksum == repeat("b", 64)
        @test data.git_commit == repeat("a", 40)

        damaged = JSON.parsefile(path)
        delete!(damaged["chains"][1]["raw_bins"], "m_time4")
        atomic_write_json(path, damaged)
        @test_throws ArgumentError read_combined_binder_data(path)
    end
end

@testset "data and window parsing share one injected byte snapshot with hashing" begin
    mktempdir() do dir
        data_path = _combined_fixture(joinpath(dir, "combined_bins.json"))
        data_bytes = read(data_path)
        data_reads = Ref(0)
        data_reader = _ -> begin
            data_reads[] += 1
            return data_bytes
        end
        atomic_write_json(data_path, (not_the_snapshot=true,))
        data = read_combined_binder_data(data_path; reader=data_reader)
        @test data_reads[] == 1
        @test data.campaign_id == "synthetic"
        @test data.content_sha256 == bytes2hex(sha256(data_bytes))

        windows_path = _windows_fixture(joinpath(dir, "windows.toml"))
        window_bytes = read(windows_path)
        window_reads = Ref(0)
        window_reader = _ -> begin
            window_reads[] += 1
            return window_bytes
        end
        atomic_write_json(windows_path, (not_the_snapshot=true,))
        windows = AnalysisScriptHarness._frozen_windows(windows_path; reader=window_reader)
        @test window_reads[] == 1
        @test windows.value["bootstrap_draws"] == 2000
        @test windows.content_sha256 == bytes2hex(sha256(window_bytes))
    end
end

@testset "combined reader enforces the frozen Task 10 science grid" begin
    for mutation in (:J, :size, :c, :anchor)
        mktempdir() do dir
            path = _combined_fixture(joinpath(dir, "combined_bins.json"))
            combined = JSON.parsefile(path)
            if mutation === :J
                _replace_first_task!(combined; J=0.0)
            elseif mutation === :size
                _replace_first_task!(combined; L=10, h=_approved_anchors(:triangle, 10)[1])
            elseif mutation === :c
                _replace_first_task!(combined; c=1.25)
            else
                old_h = combined["chains"][1]["task"]["h"]
                _replace_first_task!(combined; h=old_h + 1.0e-6)
            end
            atomic_write_json(path, combined)
            @test_throws ArgumentError read_combined_binder_data(path)
        end
    end
end

@testset "whole-replica bootstrap propagates a deterministic joint ratio" begin
    records = _synthetic_replicas()
    first_result = bootstrap_critical_ratio(records; draws=30, seed=148900)
    second_result = bootstrap_critical_ratio(records; draws=30, seed=148900)
    @test first_result.samples == second_result.samples
    @test length(first_result.samples) == 30
    @test first_result.seed == 148900
    @test first_result.draws == 30
    @test abs(mean(first_result.samples) - 4.7682 / 2.1325) < 2.0e-4
end

@testset "point Binder errors use the pooled paired-bin jackknife" begin
    function record(replica, m2, m4)
        ReplicaBinderData(:triangle, 8, _approved_anchors(:triangle, 8)[2], 1.0,
                          replica, "paired-$replica", m2, m4)
    end

    identical = [
        record(1, [1.0, 2.0, 3.0], [2.0, 5.0, 10.0]),
        record(2, [1.0, 2.0, 3.0], [2.0, 5.0, 10.0]),
    ]
    expected_identical = binder_from_bins(
        vcat(getfield.(identical, :m2_bins)...), vcat(getfield.(identical, :m4_bins)...))
    identical_point = Challenge148._binder_point(identical)
    @test identical_point.Q == expected_identical.mean
    @test identical_point.sigma == expected_identical.stderr

    unequal = [
        record(1, [1.0, 1.5], [2.0, 3.0]),
        record(2, [2.0, 2.5, 3.0, 3.5], [5.0, 7.0, 10.0, 13.0]),
        record(3, [1.2, 1.8, 2.4], [2.5, 4.0, 6.5]),
    ]
    expected_unequal = binder_from_bins(
        vcat(getfield.(unequal, :m2_bins)...), vcat(getfield.(unequal, :m4_bins)...))
    unequal_point = Challenge148._binder_point(unequal)
    @test unequal_point.Q == expected_unequal.mean
    @test unequal_point.sigma == expected_unequal.stderr
end

@testset "ratio analysis reports frozen systematic components" begin
    report = analyze_route_a_replicas(_synthetic_replicas(); draws=30, seed=148900)
    @test report.status == "route A preliminary; not a final Challenge #148 verdict"
    @test report.Delta == report.R - sqrt(5)
    @test Set(keys(report.errors)) == Set((
        :sigma_stat, :sigma_window, :sigma_fss, :sigma_c, :sigma_total_preliminary,
    ))
    @test report.errors.sigma_total_preliminary ≈ sqrt(
        report.errors.sigma_stat^2 + report.errors.sigma_window^2 +
        report.errors.sigma_fss^2 + report.errors.sigma_c^2)
    @test length(report.fit_windows) == 48
    @test_throws ArgumentError analyze_route_a_replicas(
        _synthetic_replicas(; include_thermal=false); draws=10, seed=148900)
end

@testset "FSS systematic envelopes model-window interactions" begin
    function stub(model, L_min, yt_mode, hc; accepted=true)
        BinderFitResult(
            model, L_min, yt_mode, (:hc,), (hc=hc,), ones(1, 1), 0.0, 2, 0.0,
            true, accepted, accepted ? String[] : ["rejected"], 3, [8, 12, 16, 24],
        )
    end
    triangle = Dict{Tuple{Symbol,Int,Symbol},BinderFitResult}()
    honeycomb = Dict{Tuple{Symbol,Int,Symbol},BinderFitResult}()
    for model in (:M1, :M2, :M3), L_min in (8, 12, 16, 24), yt_mode in (:fixed, :free)
        key = (model, L_min, yt_mode)
        triangle[key] = stub(model, L_min, yt_mode, L_min == 12 ? 4.2 : 4.0)
        honeycomb[key] = stub(model, L_min, yt_mode, 2.0)
    end
    pure_window = Challenge148._systematic_envelopes(triangle, honeycomb, 2.0)
    @test pure_window.sigma_window ≈ 0.10
    @test pure_window.sigma_fss ≈ 0.0 atol=1.0e-14

    triangle[(:M3, 12, :free)] = stub(:M3, 12, :free, 4.4)
    interacting = Challenge148._systematic_envelopes(triangle, honeycomb, 2.0)
    @test interacting.sigma_window ≈ 0.10
    @test interacting.sigma_fss ≈ 0.10

    triangle[(:M1, 12, :fixed)] = stub(:M1, 12, :fixed, 4.2; accepted=false)
    @test_throws ArgumentError Challenge148._systematic_envelopes(
        triangle, honeycomb, 2.0)
end

@testset "finite-c error pairs signed lattice shifts by scenario" begin
    function thermal_envelope(shifts; drop_honeycomb_group=false)
        records = _synthetic_replicas(; thermal_q_shifts=shifts)
        if drop_honeycomb_group
            target_h = _approved_anchors(:honeycomb, 24)[1]
            records = [record for record in records if !(
                record.lattice === :honeycomb && record.L == 24 && record.c == 1.5 &&
                record.h == target_h)]
        end
        groups = Challenge148._replica_groups(records)
        triangle_fit = fit_binder_window(
            Challenge148._binder_points(groups, :triangle, 1.0);
            model=:M1, L_min=8, yt_mode=:fixed)
        honeycomb_fit = fit_binder_window(
            Challenge148._binder_points(groups, :honeycomb, 1.0);
            model=:M1, L_min=8, yt_mode=:fixed)
        R = triangle_fit.parameters.hc / honeycomb_fit.parameters.hc
        return Challenge148._thermal_ratio_envelope(
            groups, triangle_fit, honeycomb_fit, R)
    end

    R_exact = 4.7682 / 2.1325
    adding = thermal_envelope((triangle=1.0e-4, honeycomb=-1.0e-4 / R_exact))
    cancelling = thermal_envelope((triangle=1.0e-4, honeycomb=1.0e-4 / R_exact))
    @test adding > 1.0e-6
    @test cancelling < adding * 1.0e-6
    @test_throws ArgumentError thermal_envelope(
        (triangle=1.0e-4, honeycomb=-1.0e-4 / R_exact); drop_honeycomb_group=true)
end

function _exact_m1_points()
    hc = 4.7682
    Qc = 0.63
    a1 = -0.08
    b1 = -0.03
    yt = 1.5868
    yi = -0.821
    return [
        (
            lattice=:triangle,
            L=L,
            h=h,
            c=1.0,
            Q=Qc + a1 * (h - hc) * L^yt + b1 * L^yi,
            sigma=1.0e-8,
            source=:direct,
        ) for L in _FSS_SIZES for h in _approved_anchors(:triangle, L)
    ]
end

@testset "noisy M1 recovery is covered by its bootstrap uncertainty" begin
    rng = Xoshiro(148901)
    noisy = [merge(point, (Q=point.Q + 2.0e-4 * randn(rng), sigma=2.0e-4)) for point in _exact_m1_points()]
    fit = fit_binder_window(noisy; model=:M1, L_min=8, yt_mode=:fixed)
    samples = bootstrap_binder_window(
        noisy;
        model=:M1,
        L_min=8,
        yt_mode=:fixed,
        seed=148902,
        draws=120,
    )
    @test fit.accepted
    @test length(samples) == 120
    @test abs(fit.parameters.hc - 4.7682) <= 2std(samples)
end

@testset "all frozen fit families and windows are enumerated" begin
    points = _exact_m1_points()
    fits = enumerate_binder_fits(points)
    @test length(fits) == 24
    @test [(fit.model, fit.L_min, fit.yt_mode) for fit in fits] == [
        (model, L_min, yt_mode) for model in (:M1, :M2, :M3)
        for L_min in (8, 12, 16, 24) for yt_mode in (:fixed, :free)
    ]
    @test all(length(fit.sizes) >= 4 for fit in fits)
    @test fit_binder_window(points; model=:M2, L_min=8, yt_mode=:fixed).parameter_names ==
          (:hc, :Qc, :a1, :a2, :b1)
    @test fit_binder_window(points; model=:M3, L_min=8, yt_mode=:free).parameter_names ==
          (:hc, :Qc, :a1, :b1, :b2, :yt)
end

@testset "reweighted rows remain validation-only" begin
    direct = _exact_m1_points()
    validation = [merge(first(direct), (Q=100.0, sigma=1.0e-12, source=:reweighted))]
    fit = fit_binder_window(vcat(direct, validation); model=:M1, L_min=8, yt_mode=:fixed)
    @test fit.nrows == length(direct)
    @test abs(fit.parameters.hc - 4.7682) <= 1.0e-10
end

@testset "fit gates reject unapproved windows and non-identifiable data" begin
    points = _exact_m1_points()
    @test_throws ArgumentError fit_binder_window(
        points; model=:M1, L_min=10, yt_mode=:fixed)
    npoints = length(points)
    covariance = 1.0e-16 .* (0.8 .* Matrix(I, npoints, npoints) .+ 0.2 .* ones(npoints, npoints))
    @test covariance[1, 2] != 0
    correlated = fit_binder_window(
        points; model=:M1, L_min=8, yt_mode=:fixed, covariance=covariance)
    @test correlated.accepted
    @test correlated.parameters.hc ≈ 4.7682 atol=1.0e-10

    flat = [merge(point, (Q=0.63, sigma=1.0e-4)) for point in points]
    unidentified = fit_binder_window(flat; model=:M1, L_min=8, yt_mode=:fixed)
    @test !unidentified.accepted
    @test any(reason -> occursin("covariance", reason), unidentified.rejection_reasons)
end

@testset "only the frozen free-yt bounds constrain scientific fits" begin
    hc = 4.7682
    large_amplitude = [merge(point, (
        Q=0.63 - 20.0 * (point.h - hc) * point.L^1.5868 - 0.03 * point.L^-0.821,
    )) for point in _exact_m1_points()]
    amplitude_fit = fit_binder_window(
        large_amplitude; model=:M1, L_min=8, yt_mode=:fixed)
    @test amplitude_fit.accepted
    @test amplitude_fit.parameters.a1 ≈ -20.0 rtol=1.0e-10

    hc_at_observed_edge = minimum(point.h for point in _exact_m1_points())
    edge_hc_points = [merge(point, (
        Q=0.63 - 0.08 * (point.h - hc_at_observed_edge) * point.L^1.5868 -
          0.03 * point.L^-0.821,
    )) for point in _exact_m1_points()]
    @test fit_binder_window(
        edge_hc_points; model=:M1, L_min=8, yt_mode=:fixed).accepted

    for active_yt in (1.50, 1.67)
        boundary_points = [merge(point, (
            Q=0.63 - 0.08 * (point.h - hc) * point.L^active_yt -
              0.03 * point.L^-0.821,
        )) for point in _exact_m1_points()]
        boundary_fit = fit_binder_window(
            boundary_points; model=:M1, L_min=8, yt_mode=:free)
        @test !boundary_fit.accepted
        @test any(reason -> occursin("active", reason), boundary_fit.rejection_reasons)
    end
end

@testset "M1 fixed-yt fit recovers an exact critical field" begin
    fit = fit_binder_window(
        _exact_m1_points();
        model=:M1,
        L_min=8,
        yt_mode=:fixed,
    )
    @test fit.converged
    @test fit.accepted
    @test abs(fit.parameters.hc - 4.7682) <= 1.0e-10
end
