using LinearAlgebra
using DelimitedFiles

@testset "frequency-resolved zero-temperature heat current" begin
    model = SpinBosonModel(alpha=0.05, omega_c=2.5)

    @testset "direct quadrature matches analytic decaying exponential" begin
        decay_rate = 0.7
        dt = 0.0025
        times = collect(0:dt:25.0)
        correlation = ComplexF64.(exp.(-decay_rate .* times))
        frequencies = Float64[0.0, 0.4, 1.3, 3.0]
        current = similar(frequencies)
        continuous_current_direct!(
            current, frequencies, correlation, dt, model; block_size=2)
        expected = [
            2spectral_density(model, omega) * omega *
            decay_rate / (decay_rate^2 + omega^2)
            for omega in frequencies
        ]
        @test current ≈ expected rtol=3e-6 atol=2e-9
        @test current[1] == 0.0
    end

    @testset "FFT backend agrees with direct quadrature on its grid" begin
        dt = 0.04
        times = dt .* (0:256)
        correlation = ComplexF64.(
            exp.(-0.8 .* times) .* (1 .+ 0.2im .* sin.(0.6 .* times)))
        transformed = continuous_current_fft(correlation, dt, model)
        selected = 1:40
        direct = zeros(Float64, length(selected))
        continuous_current_direct!(
            direct, transformed.omega[selected], correlation, dt, model;
            block_size=7)
        @test transformed.current[selected] ≈ direct rtol=3e-13 atol=3e-13
        @test transformed.window == :none
        @test transformed.endpoint_rule == :trapezoid
    end

    @testset "delta peaks preserve positions and integrated weights" begin
        omega_d = 1.5
        coefficients = Float64[0.2, 0.12, 0.03, 0.005]
        peaks = delta_peak_weights(
            model, omega_d, coefficients;
            nmax=3, omega_max=10.0, weight_tolerance=0.0)
        @test getfield.(peaks, :n) == [1, 2, 3]
        @test getfield.(peaks, :omega) == omega_d .* (1:3)
        @test getfield.(peaks, :c_n) == coefficients[2:4]
        @test getfield.(peaks, :integrated_weight) ≈ [
            π * spectral_density(model, n * omega_d) *
            (n * omega_d) * coefficients[n + 1]
            for n in 1:3
        ]
        @test all(peak -> peak.integrated_weight >= 0, peaks)

        clipped = delta_peak_weights(
            model, omega_d, coefficients;
            nmax=20, omega_max=3.1, weight_tolerance=0.0)
        @test getfield.(clipped, :n) == [1, 2]
    end

    @testset "delta coefficients agree with an independent harmonic fit" begin
        M = 48
        phases = 2π .* (0:(M - 1)) ./ M
        signal = @. 0.3 + 0.4cos(phases) - 0.2sin(phases) +
                     0.1cos(2phases) + 0.05sin(2phases)
        asymptotic = ComplexF64.(periodic_autocorrelation_direct(
            signal; lag_count=2M))
        decomposition = decompose_correlation(
            asymptotic, signal;
            tail_count=M,
            tail_norm_tolerance=1e-12,
            tail_mean_tolerance=1e-12,
            tail_slope_tolerance=1e-12)

        # Independent real least-squares Fourier fit, without using FFT.
        design = hcat(
            ones(M), cos.(phases), sin.(phases),
            cos.(2phases), sin.(2phases))
        fitted = design \ signal
        expected = [
            fitted[1]^2,
            (fitted[2]^2 + fitted[3]^2) / 2,
            (fitted[4]^2 + fitted[5]^2) / 2,
        ]
        @test decomposition.delta_coefficients[1:3] ≈ expected atol=2e-14
        @test maximum(abs, decomposition.delta_coefficients[4:end]) < 2e-28
    end

    @testset "undriven zero-temperature ground state carries no heat" begin
        Ω = 1.0
        periods = 16
        samples_per_period = 128
        dt = 2π / (Ω * samples_per_period)
        times = dt .* (0:(periods * samples_per_period))
        # For H=Ωσx/2 in its ground state and S=σz, the ordered
        # equilibrium correlator has support only at negative frequency.
        correlation = ComplexF64.(exp.(-im .* Ω .* times))
        frequencies = Ω .* collect(0:6)
        continuous = zeros(Float64, length(frequencies))
        continuous_current_direct!(
            continuous, frequencies, correlation, dt, model; block_size=3)
        peaks = delta_peak_weights(
            model, Ω, zeros(4);
            nmax=3, omega_max=6Ω, weight_tolerance=1e-15)
        total = integrated_current(frequencies, continuous, peaks)

        @test maximum(abs, continuous) < 2e-13
        @test isempty(peaks)
        @test abs(total.total) < 2e-13
    end

    @testset "invalid grids and hidden windowing fail closed" begin
        correlation = ones(ComplexF64, 8)
        @test_throws ArgumentError continuous_current_fft(
            correlation, 0.1, model; window=:hann)
        @test_throws ArgumentError continuous_current_direct!(
            zeros(2), [0.0, -1.0], correlation, 0.1, model)
        @test_throws DimensionMismatch continuous_current_direct!(
            zeros(1), [0.0, 1.0], correlation, 0.1, model)
        @test_throws ArgumentError delta_peak_weights(
            model, 0.0, [1.0, 0.2];
            nmax=1, omega_max=1.0, weight_tolerance=0.0)
    end

    @testset "Zenodo Fig. 3 grid and shape are strict" begin
        expected_omega = collect(0.005:0.005:15.0)
        @test fig3_reference_grid() == expected_omega
        mktempdir() do directory
            path = joinpath(directory, "reference.csv")
            values = @. 0.01 * expected_omega * exp(-expected_omega)
            writedlm(path, values)
            reference = load_fig3_reference(path)
            @test reference.omega == expected_omega
            @test reference.current == values

            writedlm(path, values[1:(end - 1)])
            @test_throws ArgumentError load_fig3_reference(path)
            writedlm(path, [values[1:(end - 1)]; NaN])
            @test_throws ArgumentError load_fig3_reference(path)
        end
    end

    @testset "quick Fig. 3 pipeline writes every required point artifact" begin
        config = Fig3Config(
            mode=:quick,
            dt_target=π,
            longitudinal_frequencies=[10.0, 5.0, 2.5],
            transversal_frequencies=[2.0, 1.5, 1.0],
            correlation_lag_steps=8,
            tail_count=4,
            tail_norm_tolerance=1e-10,
            tail_mean_tolerance=1e-10,
            tail_slope_tolerance=1e-10,
            c0_tolerance=1e-10,
            omega_max=8.0,
            nmax=4,
            weight_tolerance=0.0,
            eigensolver_tolerance=1e-10,
            eigensolver_max_iterations=200)
        adapter_provider = function (point_model, exact_dt)
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
        reference_provider = function (drive, omega_d)
            return (;
                omega=fig3_reference_grid(),
                current=zeros(Float64, length(fig3_reference_grid())))
        end

        mktempdir() do output_dir
            results = run_fig3(
                config, output_dir; adapter_provider, reference_provider)
            @test length(results) == 6
            required = (
                "config.json",
                "steady_state.jld2",
                "floquet_spectrum.csv",
                "micromotion.csv",
                "correlation.csv",
                "correlation_decomposition.csv",
                "continuous_heat_current.csv",
                "delta_peaks.csv",
                "diagnostics.json",
                "timing.json",
            )
            for (drive, frequencies) in (
                (:longitudinal, config.longitudinal_frequencies),
                (:transversal, config.transversal_frequencies))
                for omega_d in frequencies
                    point_dir = joinpath(
                        output_dir, String(drive), string(omega_d))
                    @test isdir(point_dir)
                    @test all(name -> isfile(joinpath(point_dir, name)), required)
                    @test first(readlines(joinpath(
                        point_dir, "delta_peaks.csv"))) ==
                        "n,omega,c_n,spectral_density,integrated_weight"
                    @test first(readlines(joinpath(
                        point_dir, "continuous_heat_current.csv"))) ==
                        "omega,current"
                    @test length(readlines(joinpath(
                        point_dir, "continuous_heat_current.csv"))) == 3001
                    for json_name in ("config.json", "diagnostics.json", "timing.json")
                        contents = read(joinpath(point_dir, json_name), String)
                        @test !occursin(r"NaN|Inf", contents)
                    end
                    @test occursin(
                        "\"reference_rmse\"",
                        read(joinpath(point_dir, "diagnostics.json"), String))
                    @test occursin(
                        "\"c0_error\"",
                        read(joinpath(point_dir, "diagnostics.json"), String))
                end
            end
        end
    end
end
