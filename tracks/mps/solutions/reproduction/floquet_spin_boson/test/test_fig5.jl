using DelimitedFiles

@testset "resumable Fig. 5 total-current scans" begin
    @test isdefined(FloquetSpinBoson, :group_frequencies_by_dt)
    @test isdefined(FloquetSpinBoson, :integrated_current)
    @test isdefined(FloquetSpinBoson, :period_averaged_power)
    @test isdefined(FloquetSpinBoson, :pending_fig5_points)
    @test isdefined(FloquetSpinBoson, :fig5_config_hash)

    if all(name -> isdefined(FloquetSpinBoson, name), (
            :group_frequencies_by_dt,
            :integrated_current,
            :period_averaged_power,
            :pending_fig5_points,
            :fig5_config_hash))
        common_dt = 0.1
        frequencies = [
            2π / (10common_dt),
            2π / (20common_dt),
            2π / (13common_dt),
        ]
        groups = group_frequencies_by_dt(frequencies, common_dt)
        @test length(groups) == 1
        @test groups[1].dt == common_dt
        @test groups[1].frequencies == frequencies

        omega = Float64[0, 1, 2]
        continuous = Float64[0, 2, 0]
        peaks = [
            DeltaPeak(1, 1.0, 0.1, 1.0, 0.3),
            DeltaPeak(2, 2.0, 0.1, 1.0, 0.2),
        ]
        total = integrated_current(omega, continuous, peaks)
        @test total.continuous == 2.0
        @test total.delta == 0.5
        @test total.total == 2.5
        truncated = integrated_current(
            omega, continuous, DeltaPeak[]; omega_max=1.5)
        @test truncated.continuous == 1.75
        @test truncated.total == 1.75

        @test period_averaged_power([1.0, 3.0, 1.0]) == 2.0
        @test period_averaged_power(zeros(5)) == 0.0
        closed_undriven = SpinBosonModel(epsilon_d=0.0, alpha=0.0)
        closed_transform = continuous_current_fft(
            ComplexF64[1.0, 0.5, 0.25], 0.1, closed_undriven)
        closed_total = integrated_current(
            closed_transform.omega, closed_transform.current, DeltaPeak[])
        @test closed_total.total == 0.0
        default_config = Fig5Config(frequencies=[1.0])
        @test fig5_config_hash(default_config, "adapter-a") !=
              fig5_config_hash(default_config, "adapter-b")
        invalid_bandwidth = Fig5Config(
            mode=:quick,
            dt_target=0.5,
            frequencies=[1.0],
            correlation_lag_steps=8,
            tail_count=2,
            omega_max=100.0)
        mktempdir() do output_dir
            @test_throws ArgumentError run_fig5(
                invalid_bandwidth, output_dir;
                adapter_provider=(_...) ->
                    error("adapter must not be constructed"),
                run_identity="invalid-bandwidth")
        end

        mktempdir() do output_dir
            config_hash = "fig5-config"
            successful = joinpath(output_dir, "longitudinal", "0.5")
            failed = joinpath(output_dir, "longitudinal", "0.55")
            mkpath(successful)
            mkpath(failed)
            write(joinpath(successful, "manifest.json"),
                  "{\"status\":\"ok\",\"config_hash\":\"fig5-config\"}")
            write(joinpath(failed, "manifest.json"),
                  "{\"status\":\"failed\",\"config_hash\":\"fig5-config\"}")
            pending = pending_fig5_points(
                output_dir, :longitudinal, [0.5, 0.55, 0.6], config_hash)
            @test pending == [0.55, 0.6]
            @test pending_fig5_points(
                output_dir, :longitudinal, [0.5], "changed-config") == [0.5]
        end
    end
end

@testset "Fig. 5 CLI and declared configurations exist" begin
    project_dir = normpath(joinpath(@__DIR__, ".."))
    @test isfile(joinpath(project_dir, "scripts", "reproduce_fig5.jl"))
    @test isfile(joinpath(project_dir, "configs", "fig5.toml"))
    @test isfile(joinpath(project_dir, "configs", "fig5_quick.toml"))
end

@testset "Fig. 5 scan orchestration reuses q and resumes points" begin
    @test isdefined(FloquetSpinBoson, :Fig5Config)
    @test isdefined(FloquetSpinBoson, :run_fig5)
    @test isdefined(FloquetSpinBoson, :fig5_reference_grid)
    @test isdefined(FloquetSpinBoson, :load_fig5_reference)

    if all(name -> isdefined(FloquetSpinBoson, name), (
            :Fig5Config, :run_fig5, :fig5_reference_grid,
            :load_fig5_reference))
        expected_frequencies = collect(0.5:0.05:10.0)
        @test fig5_reference_grid() == expected_frequencies
        mktempdir() do directory
            path = joinpath(directory, "fig5.csv")
            values = @. 0.1 * exp(-expected_frequencies)
            writedlm(path, values)
            reference = load_fig5_reference(path)
            @test reference.frequencies == expected_frequencies
            @test reference.current == values
            writedlm(path, values[1:(end - 1)])
            @test_throws ArgumentError load_fig5_reference(path)
        end

        common_dt = 0.1
        scan_frequencies = sort([
            2π / (10common_dt),
            2π / (20common_dt),
        ])
        config = Fig5Config(
            mode=:quick,
            dt_target=common_dt,
            frequencies=scan_frequencies,
            correlation_lag_steps=20,
            tail_count=4,
            tail_norm_tolerance=1e-10,
            tail_mean_tolerance=1e-10,
            tail_slope_tolerance=1e-10,
            c0_tolerance=1e-10,
            omega_max=8.0,
            nmax=4,
            weight_tolerance=0.0,
            eigensolver_tolerance=1e-10,
            eigensolver_max_iterations=200,
            # The synthetic reset channel is not an energy-conserving bath;
            # the test exercises scan plumbing rather than physical balance.
            energy_balance_tolerance=1.0)
        adapter_calls = Ref(0)
        adapter_provider = function (point_model, exact_dt)
            adapter_calls[] += 1
            reset = ComplexF64[
                0.5 0 0 0.5
                0   0 0 0
                0   0 0 0
                0.5 0 0 0.5
            ]
            return UniformIFAdapter(
                reshape(reset, 1, 4, 1, 4),
                ComplexF64[1], ComplexF64[1],
                uniform_if_metadata(point_model, exact_dt, 1e-3);
                convergence_metadata=Dict("fixture" => "reset channel"))
        end

        mktempdir() do output_dir
            results = run_fig5(
                config, output_dir; adapter_provider,
                run_identity="reset-fixture-v1", parallel_mode=:none)
            @test length(results) == 4
            @test adapter_calls[] == 1
            for drive in (:longitudinal, :transversal)
                first_manifest = read(joinpath(
                    output_dir, String(drive),
                    string(scan_frequencies[1]), "manifest.json"), String)
                second_manifest = read(joinpath(
                    output_dir, String(drive),
                    string(scan_frequencies[2]), "manifest.json"), String)
                @test occursin("\"warm_start_used\":false", first_manifest)
                @test occursin("\"warm_start_used\":true", second_manifest)
                @test occursin("\"status\":\"ok\"", second_manifest)
            end

            adapter_calls[] = 0
            resumed = run_fig5(
                config, output_dir; adapter_provider, resume=true,
                run_identity="reset-fixture-v1", parallel_mode=:none)
            @test isempty(resumed)
            @test adapter_calls[] == 0

            failed_manifest = joinpath(
                output_dir, "transversal", string(scan_frequencies[2]),
                "manifest.json")
            write(failed_manifest,
                  replace(read(failed_manifest, String),
                          "\"status\":\"ok\"" => "\"status\":\"failed\""))
            rerun = run_fig5(
                config, output_dir; adapter_provider, resume=true,
                run_identity="reset-fixture-v1", parallel_mode=:none)
            @test collect(keys(rerun)) ==
                  [(:transversal, scan_frequencies[2])]
            @test adapter_calls[] == 1

            adapter_calls[] = 0
            parallel_result = try
                run_fig5(
                    config, joinpath(output_dir, "frequency-parallel");
                    adapter_provider, run_identity="reset-fixture-v1",
                    parallel_mode=:frequencies)
            catch
                nothing
            end
            @test !isnothing(parallel_result)
            if !isnothing(parallel_result)
                @test length(parallel_result) == 4
                @test adapter_calls[] == 1
            end

            failure_config = Fig5Config(
                mode=:quick,
                dt_target=common_dt,
                frequencies=scan_frequencies[1:1],
                correlation_lag_steps=20,
                tail_count=4,
                tail_norm_tolerance=1e-10,
                tail_mean_tolerance=1e-10,
                tail_slope_tolerance=1e-10,
                c0_tolerance=1e-10,
                omega_max=8.0,
                nmax=4,
                weight_tolerance=0.0,
                eigensolver_tolerance=1e-10,
                eigensolver_max_iterations=200,
                energy_balance_tolerance=0.0)
            failure_dir = joinpath(output_dir, "failure-isolation")
            @test_throws ErrorException run_fig5(
                failure_config, failure_dir;
                adapter_provider, run_identity="reset-fixture-v1",
                parallel_mode=:none)
            for drive in (:longitudinal, :transversal)
                manifest = joinpath(
                    failure_dir, String(drive),
                    string(scan_frequencies[1]), "manifest.json")
                @test isfile(manifest)
                if isfile(manifest)
                    contents = read(manifest, String)
                    @test occursin("\"status\":\"failed\"", contents)
                    @test occursin("\"params\"", contents)
                    @test occursin("\"settings\"", contents)
                    @test occursin("\"provenance\"", contents)
                end
            end
        end
    end
end
