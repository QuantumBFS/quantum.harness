using LinearAlgebra

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
                                         InsertionConvention(operator))
    convention.side === :left ||
        throw(ArgumentError("ordered correlation requires left insertion Sρ"))
    convention.operator == ComplexF64.(operator) ||
        throw(ArgumentError("insertion convention does not match operator"))
    M = _validate_correlation_inputs(C, floquet, phase_states, v_left, convention)
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
