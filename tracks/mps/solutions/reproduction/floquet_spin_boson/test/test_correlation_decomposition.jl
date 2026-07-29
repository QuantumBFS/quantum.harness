using LinearAlgebra

@testset "periodic and decaying correlation decomposition" begin
    @testset "FFT autocorrelation matches direct circular average" begin
        M = 24
        phases = 2π .* (0:(M - 1)) ./ M
        signal = @. 0.3 + 0.8 * cos(phases) - 0.4 * sin(2phases)
        direct = periodic_autocorrelation_direct(signal; lag_count=3M + 5)
        transformed = periodic_autocorrelation_fft(signal; lag_count=3M + 5)
        expected_period =
            0.3^2 .+ (0.8^2 / 2) .* cos.(phases) .+
            (0.4^2 / 2) .* cos.(2 .* phases)
        @test transformed ≈ direct rtol=2e-13 atol=2e-13
        @test transformed[1:M] ≈ expected_period rtol=2e-13 atol=2e-13
        @test transformed[(M + 1):(2M)] ≈ transformed[1:M]
    end

    @testset "Fourier coefficients retain integrated delta weights" begin
        M = 32
        phases = 2π .* (0:(M - 1)) ./ M
        signal = @. 0.25 + 0.6 * cos(phases) + 0.2 * sin(3phases)
        full = ComplexF64.(periodic_autocorrelation_fft(
            signal; lag_count=4M))
        decomposition = decompose_correlation(
            full, signal;
            tail_count=M,
            tail_norm_tolerance=1e-12,
            tail_mean_tolerance=1e-12,
            tail_slope_tolerance=1e-12)
        @test decomposition.c_asym ≈ full rtol=2e-13 atol=2e-13
        @test norm(decomposition.c_decay) < 2e-13
        @test decomposition.delta_coefficients[1] ≈ 0.25^2 atol=2e-14
        @test decomposition.delta_coefficients[2] ≈ 0.6^2 / 2 atol=2e-14
        @test decomposition.delta_coefficients[4] ≈ 0.2^2 / 2 atol=2e-14
        inactive = setdiff(eachindex(decomposition.delta_coefficients), (1, 2, 4))
        @test maximum(abs, decomposition.delta_coefficients[inactive]) < 2e-28
        @test sum(decomposition.delta_coefficients) ≈ decomposition.c_asym[1]

        nyquist_signal = (-1.0) .^ (0:(M - 1))
        nyquist_full = ComplexF64.(periodic_autocorrelation_fft(
            nyquist_signal; lag_count=M))
        nyquist = decompose_correlation(
            nyquist_full, nyquist_signal;
            tail_count=M,
            tail_norm_tolerance=1e-12,
            tail_mean_tolerance=1e-12,
            tail_slope_tolerance=1e-12)
        @test length(nyquist.delta_coefficients) == M ÷ 2 + 1
        @test nyquist.delta_coefficients[end] ≈ 1.0
        @test sum(nyquist.delta_coefficients) ≈ nyquist.c_asym[1]
    end

    @testset "persistent connected tail is rejected" begin
        M = 16
        signal = zeros(Float64, M)
        persistent = fill(0.1 + 0.05im, 4M)
        error = try
            decompose_correlation(
                persistent, signal;
                tail_count=M,
                tail_norm_tolerance=1e-3,
                tail_mean_tolerance=1e-3,
                tail_slope_tolerance=1e-3)
            nothing
        catch caught
            caught
        end
        @test error isa ArgumentError
        @test occursin("decaying correlation tail", sprint(showerror, error))
        @test occursin("tail_norm=", sprint(showerror, error))
        @test occursin("tail_mean=", sprint(showerror, error))
        @test occursin("tail_slope=", sprint(showerror, error))
    end

    @testset "invalid signal and tolerance inputs fail closed" begin
        @test_throws ArgumentError periodic_autocorrelation_fft(
            ComplexF64[1, im])
        @test_throws ArgumentError periodic_autocorrelation_direct(Float64[])
        @test_throws DimensionMismatch decompose_correlation(
            ones(ComplexF64, 3), ones(Float64, 4);
            tail_count=2,
            tail_norm_tolerance=1.0,
            tail_mean_tolerance=1.0,
            tail_slope_tolerance=1.0)
        @test_throws ArgumentError decompose_correlation(
            ones(ComplexF64, 4), ones(Float64, 4);
            tail_count=2,
            tail_norm_tolerance=-1.0,
            tail_mean_tolerance=1.0,
            tail_slope_tolerance=1.0)
    end
end
