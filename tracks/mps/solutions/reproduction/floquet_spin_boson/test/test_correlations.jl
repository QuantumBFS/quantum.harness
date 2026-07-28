using LinearAlgebra
using Random

function correlation_random_channels(rng, phase_count)
    left = [randn(rng, ComplexF64, 4, 4) for _ in 1:phase_count]
    right = [randn(rng, ComplexF64, 4, 4) for _ in 1:phase_count]
    return left, right
end

function explicit_system_action(x, channel, χ)
    y = zeros(ComplexF64, 4χ)
    for sout in 1:4, a in 1:χ, sin in 1:4
        y[a + χ * (sout - 1)] +=
            channel[sout, sin] * x[a + χ * (sin - 1)]
    end
    return y
end

function explicit_augmented_phase(x, q, left, right)
    χ = size(q, 1)
    after_left = explicit_system_action(x, left, χ)
    after_q = zeros(ComplexF64, 4χ)
    for sout in 1:4, aout in 1:χ, sin in 1:4, ain in 1:χ
        after_q[aout + χ * (sout - 1)] +=
            q[aout, sout, ain, sin] * after_left[ain + χ * (sin - 1)]
    end
    return explicit_system_action(after_q, right, χ)
end

function explicit_late_contraction(state, v_left, late_vector)
    χ = length(v_left)
    value = 0.0 + 0.0im
    for s in 1:4, a in 1:χ
        value += v_left[a] * state[a + χ * (s - 1)] * late_vector[s]
    end
    return value
end

function explicit_correlation(floquet, phase_states, operator, v_left, max_lag)
    M = length(floquet.left_channels)
    early = kron(Matrix{ComplexF64}(I, 2, 2), ComplexF64.(operator))
    late = transpose(early) * vec(Matrix{ComplexF64}(I, 2, 2))
    result = zeros(ComplexF64, max_lag + 1)
    for start in 1:M
        state = explicit_system_action(phase_states[start], early,
                                       floquet.layout.bond_dimension)
        result[1] += explicit_late_contraction(state, v_left, late)
        for lag in 1:max_lag
            phase = mod1(start + lag - 1, M)
            state = explicit_augmented_phase(
                state, floquet.q_storage, floquet.left_channels[phase],
                floquet.right_channels[phase])
            result[lag + 1] += explicit_late_contraction(state, v_left, late)
        end
    end
    return result / M
end

@testset "serial Floquet two-time correlation" begin
    rng = MersenneTwister(0xC022)

    @testset "column-major left insertion represents S rho" begin
        operator = ComplexF64[1 2im; 3 -1]
        density = ComplexF64[0.7 0.2im; -0.1im 0.3]
        convention = InsertionConvention(operator)
        @test convention.side == :left
        @test convention.early_superoperator * vec(density) ≈
              vec(operator * density)
        @test convention.late_trace_vector ==
              transpose(convention.early_superoperator) *
              vec(Matrix{ComplexF64}(I, 2, 2))
    end

    @testset "real v_left contraction, C(0), and explicit χ≤2 oracle" begin
        χ = 2
        M = 3
        q = randn(rng, ComplexF64, χ, 4, χ, 4)
        left, right = correlation_random_channels(rng, M)
        floquet = FloquetOperator(q, left, right)
        phase_states = [randn(rng, ComplexF64, 4χ) for _ in 1:M]
        v_left = ComplexF64[1 + 0.2im, -0.4 + 0.3im]
        C = zeros(ComplexF64, 6)
        floquet_correlation_serial!(C, floquet, phase_states, SIGMA_Z, v_left)
        expected = explicit_correlation(floquet, phase_states, SIGMA_Z,
                                        v_left, length(C) - 1)
        @test C ≈ expected rtol=2e-12 atol=2e-12
        @test eltype(C) == ComplexF64
        @test C[1] ≈ sum(explicit_late_contraction(
            phase_states[m], v_left, vec(Matrix{ComplexF64}(I, 2, 2)))
            for m in 1:M) / M
        @test !isapprox(C[2], real(C[2]); atol=1e-12)
        with_closure = similar(C)
        floquet_correlation_serial!(
            with_closure, floquet, [phase_states; phase_states[1:1]],
            SIGMA_Z, v_left)
        @test with_closure == C

        short = zeros(ComplexF64, 4)
        long = zeros(ComplexF64, 100)
        floquet_correlation_serial!(short, floquet, phase_states, SIGMA_Z, v_left)
        floquet_correlation_serial!(long, floquet, phase_states, SIGMA_Z, v_left)
        short_alloc = @allocated floquet_correlation_serial!(
            short, floquet, phase_states, SIGMA_Z, v_left)
        long_alloc = @allocated floquet_correlation_serial!(
            long, floquet, phase_states, SIGMA_Z, v_left)
        @test long_alloc <= short_alloc + 256
    end

    @testset "alpha=0 closed identity limit" begin
        identity4 = Matrix{ComplexF64}(I, 4, 4)
        floquet = FloquetOperator(reshape(identity4, 1, 4, 1, 4),
                                  fill(identity4, 4), fill(identity4, 4))
        rho = ComplexF64[1, 0, 0, 0]
        C = zeros(ComplexF64, 9)
        floquet_correlation_serial!(C, floquet, fill(rho, 4),
                                    SIGMA_Z, ComplexF64[1])
        @test C ≈ ones(ComplexF64, 9)
    end

    @testset "epsilon_d=0 exact closed-system correlation" begin
        M = 16
        omega_d = 1.0
        dt = 2π / M
        model = SpinBosonModel(epsilon_d=0.0, alpha=0.0)
        identity4 = Matrix{ComplexF64}(I, 4, 4)
        floquet = FloquetOperator(
            UniformIFAdapter(reshape(identity4, 1, 4, 1, 4),
                             ComplexF64[1], ComplexF64[1],
                             uniform_if_metadata(model, dt, 1e-7)),
            model, omega_d, M, dt)
        rho = ComplexF64[0.5, 0, 0, 0.5]
        C = zeros(ComplexF64, 9)
        floquet_correlation_serial!(C, floquet, fill(rho, M),
                                    SIGMA_Z, ComplexF64[1])
        @test real.(C) ≈ cos.(model.omega .* (0:8) .* dt) atol=2e-12
        @test maximum(abs.(imag.(C))) < 2e-12
    end

    @testset "invalid insertion and layout fail closed" begin
        @test_throws DimensionMismatch InsertionConvention(zeros(ComplexF64, 3, 3))
        identity4 = Matrix{ComplexF64}(I, 4, 4)
        floquet = FloquetOperator(reshape(identity4, 1, 4, 1, 4),
                                  [identity4], [identity4])
        @test_throws DimensionMismatch floquet_correlation_serial!(
            zeros(ComplexF64, 2), floquet, [zeros(ComplexF64, 8)],
            SIGMA_Z, ComplexF64[1])
        @test_throws DimensionMismatch floquet_correlation_serial!(
            zeros(ComplexF64, 2), floquet, [zeros(ComplexF64, 4)],
            SIGMA_Z, ComplexF64[1, 1])
        @test_throws ArgumentError floquet_correlation_serial!(
            zeros(Float64, 2), floquet, [zeros(ComplexF64, 4)],
            SIGMA_Z, ComplexF64[1])
    end

    @testset "tail diagnostics retain complex mean" begin
        C = ComplexF64[1, 0.6 + 0.2im, 0.3 + 0.1im, 0.1 - 0.2im, 0.05 - 0.1im]
        diagnostics = correlation_diagnostics(C; tail_count=3)
        @test diagnostics.c0 == C[1]
        @test diagnostics.tail_norm ≈ norm(C[end-2:end])
        @test diagnostics.tail_mean ≈ sum(C[end-2:end]) / 3
        @test diagnostics.tail_slope isa Float64
        @test_throws ArgumentError correlation_diagnostics(C; tail_count=1)
        @test_throws ArgumentError correlation_diagnostics(C; tail_count=6)
    end
end
