mutable struct BinAccumulator
    m2_sum::Float64
    m4_sum::Float64
    measurement_count::Int
end

function tau_segments(LTrot::Int, count::Int)::Vector{UnitRange{Int}}
    LTrot > 0 || throw(ArgumentError("LTrot must be positive"))
    count > 0 || throw(ArgumentError("segment count must be positive"))
    count <= LTrot ||
        throw(ArgumentError("segment count must not exceed LTrot"))

    base, remainder = divrem(LTrot, count)
    segments = Vector{UnitRange{Int}}(undef, count)
    first_tau = 1

    for index in 1:count
        segment_length = base + (index <= remainder)
        last_tau = first_tau + segment_length - 1
        segments[index] = first_tau:last_tau
        first_tau = last_tau + 1
    end

    return segments
end

function sample_measurement_slices(
    segments::AbstractVector{<:UnitRange{Int}},
    rng,
)::Vector{Int}
    return [rand(rng, segment) for segment in segments]
end

function measure_at_slices(
    spins::Matrix{Int8},
    slices::Vector{Int},
)
    isempty(slices) &&
        throw(ArgumentError("at least one measurement slice is required"))

    NumNS = size(spins, 1)
    NumNS > 0 || throw(ArgumentError("spins must contain at least one site"))
    m2_sum = 0.0
    m4_sum = 0.0

    for tau in slices
        1 <= tau <= size(spins, 2) ||
            throw(BoundsError(spins, (:, tau)))
        magnetization = sum(@view spins[:, tau]) / NumNS
        m2 = magnetization^2
        m2_sum += m2
        m4_sum += m2^2
    end

    count = length(slices)
    return m2_sum / count, m4_sum / count
end

function measure!(
    accumulator::BinAccumulator,
    state::SimulationState,
    segments::AbstractVector{<:UnitRange{Int}},
    rng,
)::Nothing
    slices = sample_measurement_slices(segments, rng)
    m2, m4 = measure_at_slices(state.spins, slices)
    accumulator.m2_sum += m2
    accumulator.m4_sum += m4
    accumulator.measurement_count += 1
    return nothing
end
