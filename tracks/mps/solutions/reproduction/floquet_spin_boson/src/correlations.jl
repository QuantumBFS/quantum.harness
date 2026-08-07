using LinearAlgebra
using FFTW

"""
Ordered two-time convention in column-major Liouville space.

For a 2×2 operator `S`, early insertion is left multiplication:
`vec(Sρ) = (I₂ ⊗ S) vec(ρ)`. The late vector follows UniformTEMPO:
`transpose(I₂ ⊗ S) * vec(I₂)`.
"""
struct InsertionConvention
    side::Symbol
    operator::Matrix{ComplexF64}
    early_superoperator::Matrix{ComplexF64}
    late_trace_vector::Vector{ComplexF64}
end

function InsertionConvention(operator::AbstractMatrix)
    size(operator) == (2, 2) ||
        throw(DimensionMismatch("single-spin insertion operator must be 2×2"))
    all(isfinite, operator) ||
        throw(ArgumentError("insertion operator entries must be finite"))
    checked = ComplexF64.(operator)
    identity2 = Matrix{ComplexF64}(I, 2, 2)
    early = kron(identity2, checked)
    late = transpose(early) * vec(identity2)
    return InsertionConvention(:left, checked, early, late)
end

@inline function _late_observable_contraction(state::AbstractVector,
                                              v_left::AbstractVector,
                                              late_trace_vector::AbstractVector,
                                              layout::AugmentedLayout)
    χ = layout.bond_dimension
    value = zero(ComplexF64)
    # v_l is a transpose in UniformTEMPO, not an adjoint: do not use dot.
    @inbounds for system_index in 1:4
        offset = χ * (system_index - 1)
        for bond_index in 1:χ
            value += v_left[bond_index] * state[bond_index + offset] *
                     late_trace_vector[system_index]
        end
    end
    return value
end

function _validate_correlation_inputs(C, floquet, phase_states, v_left,
                                      convention)
    eltype(C) === ComplexF64 ||
        throw(ArgumentError("correlation output must retain ComplexF64 values"))
    isempty(C) && throw(ArgumentError("correlation output cannot be empty"))
    M = length(floquet.left_channels)
    # micromotion_states returns M+1 with the final closure copy. Direct
    # callers may provide the M distinct starting phases.
    length(phase_states) in (M, M + 1) ||
        throw(DimensionMismatch("phase states must contain M states, optionally plus closure"))
    expected = floquet.layout.augmented_dimension
    all(state -> length(state) == expected, phase_states) ||
        throw(DimensionMismatch("phase state has the wrong augmented dimension"))
    length(v_left) == floquet.layout.bond_dimension ||
        throw(DimensionMismatch("left boundary and augmented layout are incompatible"))
    length(convention.late_trace_vector) == 4 ||
        throw(DimensionMismatch("late insertion vector and layout are incompatible"))
    return M
end

function _physical_step_scale(period_eigenvalue::Number, M::Integer)
    value = ComplexF64(period_eigenvalue)
    isfinite(value) && abs(value) > sqrt(eps(Float64)) ||
        throw(ArgumentError(
            "period eigenvalue must be finite and nonzero"))
    return exp(-log(value) / M)
end

@inline function _scale_correlation_state!(state::AbstractVector, scale)
    @inbounds @simd for index in eachindex(state)
        state[index] *= scale
    end
    return state
end

"""
Compute `(1/M) Σₘ ⟨S(tₘ+k dt)S(tₘ)⟩` in the full augmented space.

The phase state at index m is immediately before step m. The algorithm streams
over lag using two augmented vectors and one reusable step workspace.
"""
function floquet_correlation_serial!(C::AbstractVector,
                                     floquet::FloquetOperator,
                                     phase_states::AbstractVector,
                                     operator::AbstractMatrix,
                                     v_left::AbstractVector;
                                     convention::InsertionConvention=
                                         InsertionConvention(operator),
                                     period_eigenvalue::Number=1 + 0im)
    convention.side === :left ||
        throw(ArgumentError("ordered correlation requires left insertion Sρ"))
    convention.operator == ComplexF64.(operator) ||
        throw(ArgumentError("insertion convention does not match operator"))
    M = _validate_correlation_inputs(C, floquet, phase_states, v_left, convention)
    step_scale = _physical_step_scale(period_eigenvalue, M)
    fill!(C, zero(ComplexF64))
    max_lag = length(C) - 1
    work = StepWorkspace(floquet)

    for start_phase in 1:M
        _apply_system_channel!(work.period1, phase_states[start_phase],
                               convention.early_superoperator, floquet.layout)
        source = work.period1
        destination = work.period2
        C[1] += _late_observable_contraction(
            source, v_left, convention.late_trace_vector, floquet.layout)
        for lag in 1:max_lag
            phase = mod1(start_phase + lag - 1, M)
            _apply_phase!(destination, source, floquet, phase, work)
            source, destination = destination, source
            _scale_correlation_state!(source, step_scale)
            C[lag + 1] += _late_observable_contraction(
                source, v_left, convention.late_trace_vector, floquet.layout)
        end
    end
    scale = inv(Float64(M))
    @inbounds for index in eachindex(C)
        C[index] *= scale
    end
    return C
end

function _accumulate_correlation_phase!(
    accumulator::AbstractVector,
    start_phase::Integer,
    floquet::FloquetOperator,
    phase_states::AbstractVector,
    v_left::AbstractVector,
    convention::InsertionConvention,
    work::StepWorkspace,
    step_scale::ComplexF64)

    M = length(floquet.left_channels)
    _apply_system_channel!(
        work.period1, phase_states[start_phase],
        convention.early_superoperator, floquet.layout)
    source = work.period1
    destination = work.period2
    accumulator[1] += _late_observable_contraction(
        source, v_left, convention.late_trace_vector, floquet.layout)
    @inbounds for lag in 1:(length(accumulator) - 1)
        phase = mod1(start_phase + lag - 1, M)
        _apply_phase!(destination, source, floquet, phase, work)
        source, destination = destination, source
        _scale_correlation_state!(source, step_scale)
        accumulator[lag + 1] += _late_observable_contraction(
            source, v_left, convention.late_trace_vector, floquet.layout)
    end
    return accumulator
end

function _validate_correlation_checkpoint(checkpoint::CorrelationCheckpoint,
                                          config_hash::AbstractString,
                                          phase_count::Integer,
                                          lag_count::Integer)
    checkpoint.config_hash == config_hash ||
        throw(ArgumentError("correlation checkpoint config hash mismatch"))
    checkpoint.phase_count == phase_count ||
        throw(ArgumentError("correlation checkpoint phase count mismatch"))
    checkpoint.lag_count == lag_count ||
        throw(ArgumentError("correlation checkpoint lag count mismatch"))
    return checkpoint
end

"""
Compute a phase-parallel correlation with resumable, atomic batch checkpoints.

Each Julia thread owns its `StepWorkspace` and complex partial accumulator.
`parallel_mode=:frequencies` is rejected to prevent nested frequency/phase
parallelism. A checkpoint stores the unnormalized sum over a contiguous prefix
of completed phases and is removed only after successful completion.
"""
function floquet_correlation_threaded!(
    C::AbstractVector,
    floquet::FloquetOperator,
    phase_states::AbstractVector,
    operator::AbstractMatrix,
    v_left::AbstractVector;
    convention::InsertionConvention=InsertionConvention(operator),
    config_hash::AbstractString,
    checkpoint_path::Union{Nothing,AbstractString}=nothing,
    batch_size::Integer=max(1, Threads.nthreads()),
    resume::Bool=false,
    parallel_mode::Symbol=:phases,
    period_eigenvalue::Number=1 + 0im,
    after_batch::Function=(_ -> nothing))

    parallel_mode in (:phases, :none) ||
        throw(ArgumentError(
            "phase correlation cannot run inside frequency parallelism"))
    batch_size > 0 || throw(ArgumentError("batch_size must be positive"))
    isempty(config_hash) &&
        throw(ArgumentError("correlation config hash cannot be empty"))
    resume && isnothing(checkpoint_path) &&
        throw(ArgumentError("resume requires a checkpoint path"))
    convention.side === :left ||
        throw(ArgumentError("ordered correlation requires left insertion Sρ"))
    convention.operator == ComplexF64.(operator) ||
        throw(ArgumentError("insertion convention does not match operator"))
    M = _validate_correlation_inputs(
        C, floquet, phase_states, v_left, convention)
    step_scale = _physical_step_scale(period_eigenvalue, M)

    LinearAlgebra.BLAS.set_num_threads(1)
    completed = 0
    total = zeros(ComplexF64, length(C))
    if resume
        checkpoint = load_correlation_checkpoint(checkpoint_path)
        _validate_correlation_checkpoint(
            checkpoint, config_hash, M, length(C))
        completed = checkpoint.completed_phases
        copyto!(total, checkpoint.partial_sum)
    elseif !isnothing(checkpoint_path) && isfile(checkpoint_path)
        throw(ArgumentError(
            "checkpoint already exists; pass resume=true or choose another path"))
    end

    # Julia may expose an interactive pool whose thread IDs are larger than
    # `Threads.nthreads()` for the default pool. Index by the full ID range so
    # every thread that can execute the loop owns a distinct workspace.
    thread_count = parallel_mode === :phases ? Threads.maxthreadid() : 1
    workspaces = [StepWorkspace(floquet) for _ in 1:thread_count]
    partials = [zeros(ComplexF64, length(C)) for _ in 1:thread_count]

    while completed < M
        batch_stop = min(M, completed + Int(batch_size))
        foreach(partial -> fill!(partial, zero(ComplexF64)), partials)
        if parallel_mode === :phases
            Threads.@threads :static for start_phase in (completed + 1):batch_stop
                thread_index = Threads.threadid()
                _accumulate_correlation_phase!(
                    partials[thread_index], start_phase, floquet, phase_states,
                    v_left, convention, workspaces[thread_index], step_scale)
            end
        else
            for start_phase in (completed + 1):batch_stop
                _accumulate_correlation_phase!(
                    partials[1], start_phase, floquet, phase_states,
                    v_left, convention, workspaces[1], step_scale)
            end
        end
        for partial in partials
            @inbounds for index in eachindex(total)
                total[index] += partial[index]
            end
        end
        completed = batch_stop
        checkpoint = CorrelationCheckpoint(
            config_hash, completed, M, total)
        isnothing(checkpoint_path) ||
            save_correlation_checkpoint(checkpoint_path, checkpoint)
        after_batch(checkpoint)
    end

    scale = inv(Float64(M))
    @inbounds for index in eachindex(C)
        C[index] = total[index] * scale
    end
    if !isnothing(checkpoint_path) && isfile(checkpoint_path)
        rm(checkpoint_path; force=true)
    end
    return C
end

"""Return C(0), complex tail mean, tail norm, and magnitude-tail slope."""
function correlation_diagnostics(C::AbstractVector; tail_count::Integer)
    eltype(C) <: Complex ||
        throw(ArgumentError("correlation diagnostics require complex input"))
    2 <= tail_count <= length(C) ||
        throw(ArgumentError("tail_count must be between 2 and length(C)"))
    tail = @view C[(length(C) - Int(tail_count) + 1):end]
    tail_mean = sum(tail) / length(tail)
    tail_norm = norm(tail)
    x_mean = (length(tail) + 1) / 2
    denominator = 0.0
    numerator = 0.0
    @inbounds for index in eachindex(tail)
        centered = index - x_mean
        numerator += centered * abs(tail[index])
        denominator += centered^2
    end
    return (; c0=ComplexF64(first(C)), tail_norm=Float64(tail_norm),
            tail_mean=ComplexF64(tail_mean),
            tail_slope=Float64(numerator / denominator))
end

function _validate_periodic_signal(signal::AbstractVector,
                                   lag_count::Integer)
    isempty(signal) &&
        throw(ArgumentError("periodic signal cannot be empty"))
    eltype(signal) <: Real ||
        throw(ArgumentError("periodic expectation signal must be real"))
    all(isfinite, signal) ||
        throw(ArgumentError("periodic signal contains non-finite values"))
    lag_count > 0 || throw(ArgumentError("lag_count must be positive"))
    return length(signal)
end

"""Direct O(M×K) circular average `(1/M)Σₘ s[m+k]s[m]`."""
function periodic_autocorrelation_direct(
    signal::AbstractVector;
    lag_count::Integer=length(signal))

    M = _validate_periodic_signal(signal, lag_count)
    result = zeros(Float64, Int(lag_count))
    @inbounds for lag in 0:(Int(lag_count) - 1)
        value = 0.0
        for phase in 1:M
            value += Float64(signal[mod1(phase + lag, M)]) *
                     Float64(signal[phase])
        end
        result[lag + 1] = value / M
    end
    return result
end

"""
FFT circular average with Julia's inverse-transform normalization made explicit.

`ifft(abs2.(fft(s)))` is the circular correlation sum, so division by M
produces the phase average used by the Floquet correlation decomposition.
"""
function periodic_autocorrelation_fft(
    signal::AbstractVector;
    lag_count::Integer=length(signal))

    M = _validate_periodic_signal(signal, lag_count)
    one_period = real.(ifft(abs2.(fft(Float64.(signal))))) ./ M
    result = Vector{Float64}(undef, Int(lag_count))
    @inbounds for index in eachindex(result)
        result[index] = one_period[mod1(index, M)]
    end
    return result
end

function _positive_frequency_coefficients(signal::AbstractVector)
    M = length(signal)
    amplitudes = fft(Float64.(signal)) ./ M
    positive_count = fld(M, 2)
    coefficients = zeros(Float64, positive_count + 1)
    coefficients[1] = abs2(amplitudes[1])
    @inbounds for harmonic in 1:positive_count
        # Positive and negative harmonics form a pair except at the
        # self-conjugate Nyquist bin of an even-length sampled period.
        multiplicity = iseven(M) && harmonic == M ÷ 2 ? 1.0 : 2.0
        coefficients[harmonic + 1] =
            multiplicity * abs2(amplitudes[harmonic + 1])
    end
    return coefficients
end

"""
Subtract the non-decaying periodic autocorrelation and validate the connected tail.

The returned `delta_coefficients` use index `n+1` for harmonic n:
`c₀=|a₀|²` and `cₙ=2|aₙ|²` for paired positive harmonics. The sampled
Nyquist bin, when present, is self-conjugate and therefore has multiplicity one.
"""
function decompose_correlation(
    correlation::AbstractVector,
    signal::AbstractVector;
    tail_count::Integer,
    tail_norm_tolerance::Real,
    tail_mean_tolerance::Real,
    tail_slope_tolerance::Real)

    eltype(correlation) <: Complex ||
        throw(ArgumentError("full correlation must retain complex values"))
    length(correlation) >= length(signal) ||
        throw(DimensionMismatch(
            "correlation must cover at least one complete drive period"))
    all(isfinite, correlation) ||
        throw(ArgumentError("full correlation contains non-finite values"))
    for (name, tolerance) in (
        ("tail_norm_tolerance", tail_norm_tolerance),
        ("tail_mean_tolerance", tail_mean_tolerance),
        ("tail_slope_tolerance", tail_slope_tolerance))
        isfinite(tolerance) && tolerance >= 0 ||
            throw(ArgumentError(name * " must be finite and nonnegative"))
    end
    _validate_periodic_signal(signal, length(correlation))

    c_asym = ComplexF64.(periodic_autocorrelation_fft(
        signal; lag_count=length(correlation)))
    c_decay = ComplexF64.(correlation) .- c_asym
    diagnostics = correlation_diagnostics(c_decay; tail_count)
    accepted =
        diagnostics.tail_norm <= tail_norm_tolerance &&
        abs(diagnostics.tail_mean) <= tail_mean_tolerance &&
        abs(diagnostics.tail_slope) <= tail_slope_tolerance
    accepted ||
        throw(ArgumentError(
            "decaying correlation tail did not satisfy configured tolerances: " *
            "tail_norm=$(diagnostics.tail_norm), " *
            "tail_mean=$(diagnostics.tail_mean), " *
            "tail_slope=$(diagnostics.tail_slope)"))
    return (;
        c_asym,
        c_decay,
        delta_coefficients=_positive_frequency_coefficients(signal),
        diagnostics)
end
