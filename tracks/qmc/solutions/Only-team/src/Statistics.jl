struct BinRecord
    bin::Int
    m2::Float64
    m4::Float64
    Q::Float64
end

function bin_record(bin::Int, m2::Float64, m4::Float64)::BinRecord
    bin > 0 || throw(ArgumentError("bin must be positive"))
    isfinite(m2) && m2 >= 0 ||
        throw(ArgumentError("m2 must be finite and nonnegative"))
    isfinite(m4) && m4 > 0 ||
        throw(ArgumentError("m4 must be finite and positive"))

    Q = m2^2 / m4
    isfinite(Q) || throw(ArgumentError("Binder Q must be finite"))
    return BinRecord(bin, m2, m4, Q)
end

function bin_sem(values::Vector{Float64})::NamedTuple
    length(values) >= 2 ||
        throw(ArgumentError("bin_sem requires at least two values"))
    all(isfinite, values) ||
        throw(ArgumentError("bin_sem values must be finite"))

    count = length(values)
    mean_value = sum(values) / count
    squared_deviation =
        sum((value - mean_value)^2 for value in values)
    error = sqrt(squared_deviation / (count * (count - 1)))
    return (; mean = mean_value, error, n = count)
end

function filter_series(
    records::Vector{BinRecord},
    field::Symbol,
    discard::Int,
    trim::Bool,
)::NamedTuple
    field in (:m2, :Q) ||
        throw(ArgumentError("field must be :m2 or :Q"))
    0 <= discard < length(records) ||
        throw(ArgumentError("discard must satisfy 0 <= discard < record count"))

    discarded_bins = [records[index].bin for index in 1:discard]
    candidates = records[(discard + 1):end]
    candidate_values = [getfield(record, field) for record in candidates]

    retained_indices, trimmed_bins = if trim
        length(candidates) >= 4 ||
            throw(
                ArgumentError(
                    "extrema trimming requires at least four values after initial-bin removal",
                ),
            )
        order = sortperm(
            eachindex(candidates);
            by = index -> (candidate_values[index], candidates[index].bin),
        )
        trimmed = [
            candidates[first(order)].bin,
            candidates[last(order)].bin,
        ]
        order[2:(end - 1)], trimmed
    else
        length(candidates) >= 2 ||
            throw(
                ArgumentError(
                    "at least two values must remain after initial-bin removal",
                ),
            )
        collect(eachindex(candidates)), Int[]
    end

    values = candidate_values[retained_indices]
    retained_bins = [candidates[index].bin for index in retained_indices]
    removed_bins = sort!(vcat(copy(discarded_bins), copy(trimmed_bins)))
    statistics = bin_sem(values)

    return (;
        values,
        retained_bins,
        discarded_bins,
        trimmed_bins,
        removed_bins,
        number_before_filtering = length(records),
        number_after_discard = length(candidates),
        number_after_filtering = length(values),
        mean = statistics.mean,
        error = statistics.error,
    )
end

function summarize_bins(
    records::Vector{BinRecord},
    config::SimulationConfig,
)::NamedTuple
    length(records) == config.NmBin ||
        throw(ArgumentError("record count must equal NmBin"))

    m2_filter = filter_series(
        records,
        :m2,
        config.discard_initial_bins,
        config.trim_extrema,
    )
    binder_Q_filter = filter_series(
        records,
        :Q,
        config.discard_initial_bins,
        config.trim_extrema,
    )

    return (;
        m2 = m2_filter.mean,
        m2_error = m2_filter.error,
        binder_Q = binder_Q_filter.mean,
        binder_Q_error = binder_Q_filter.error,
        m2_filter,
        binder_Q_filter,
        statistics_mode = config.statistics_mode,
        discard_initial_bins = config.discard_initial_bins,
        trim_extrema = config.trim_extrema,
        number_of_bins_before_filtering = length(records),
        number_of_bins_after_filtering = m2_filter.number_after_filtering,
    )
end
