"""Canonical sparse sufficient statistics for cut-count field reweighting."""
struct CutHistogramBin
    cut_counts::Tuple{Vararg{Int}}
    counts::Tuple{Vararg{Int}}
    sum_m2::Tuple{Vararg{Float64}}
    sum_m4::Tuple{Vararg{Float64}}

    function CutHistogramBin(
        cut_counts::AbstractVector{<:Integer},
        counts::AbstractVector{<:Integer},
        sum_m2::AbstractVector{<:Real},
        sum_m4::AbstractVector{<:Real},
    )
        length(cut_counts) == length(counts) == length(sum_m2) == length(sum_m4) ||
            throw(ArgumentError("cut histogram fields must have equal lengths"))
        normalized_cuts = Int.(cut_counts)
        normalized_counts = Int.(counts)
        normalized_m2 = Float64.(sum_m2)
        normalized_m4 = Float64.(sum_m4)
        all(>=(0), normalized_cuts) ||
            throw(ArgumentError("cut histogram cut counts must be nonnegative"))
        all(>(0), normalized_counts) ||
            throw(ArgumentError("cut histogram sample counts must be positive"))
        issorted(normalized_cuts) && all(diff(normalized_cuts) .> 0) ||
            throw(ArgumentError("cut histogram cut counts must be strictly sorted"))
        all(isfinite, normalized_m2) && all(isfinite, normalized_m4) ||
            throw(ArgumentError("cut histogram moments must be finite"))
        return new(
            Tuple(normalized_cuts),
            Tuple(normalized_counts),
            Tuple(normalized_m2),
            Tuple(normalized_m4),
        )
    end
end

"""Aggregate one cut count and its time-magnetization moments per sweep."""
function CutHistogramBin(
    cut_counts::AbstractVector{<:Integer},
    m2::AbstractVector{<:Real},
    m4::AbstractVector{<:Real},
)
    length(cut_counts) == length(m2) == length(m4) ||
        throw(ArgumentError("cut histogram samples must have equal lengths"))
    normalized_cuts = Int.(cut_counts)
    normalized_m2 = Float64.(m2)
    normalized_m4 = Float64.(m4)
    all(>=(0), normalized_cuts) ||
        throw(ArgumentError("cut histogram cut counts must be nonnegative"))
    all(isfinite, normalized_m2) && all(isfinite, normalized_m4) ||
        throw(ArgumentError("cut histogram moments must be finite"))
    order = sortperm(normalized_cuts)
    canonical_cuts = Int[]
    counts = Int[]
    sum_m2 = Float64[]
    sum_m4 = Float64[]
    for index in order
        if isempty(canonical_cuts) || normalized_cuts[index] != canonical_cuts[end]
            push!(canonical_cuts, normalized_cuts[index])
            push!(counts, 1)
            push!(sum_m2, normalized_m2[index])
            push!(sum_m4, normalized_m4[index])
        else
            counts[end] += 1
            sum_m2[end] += normalized_m2[index]
            sum_m4[end] += normalized_m4[index]
        end
    end
    return CutHistogramBin(canonical_cuts, counts, sum_m2, sum_m4)
end

"""Merge canonical sparse histograms without retaining individual sweeps."""
function merge_histograms(left::CutHistogramBin, right::CutHistogramBin)
    cut_counts = Int[]
    counts = Int[]
    sum_m2 = Float64[]
    sum_m4 = Float64[]
    left_index = 1
    right_index = 1
    while left_index <= length(left.cut_counts) || right_index <= length(right.cut_counts)
        if right_index > length(right.cut_counts) ||
           (left_index <= length(left.cut_counts) && left.cut_counts[left_index] < right.cut_counts[right_index])
            source, index = left, left_index
            left_index += 1
        elseif left_index > length(left.cut_counts) || right.cut_counts[right_index] < left.cut_counts[left_index]
            source, index = right, right_index
            right_index += 1
        else
            push!(cut_counts, left.cut_counts[left_index])
            push!(counts, left.counts[left_index] + right.counts[right_index])
            push!(sum_m2, left.sum_m2[left_index] + right.sum_m2[right_index])
            push!(sum_m4, left.sum_m4[left_index] + right.sum_m4[right_index])
            left_index += 1
            right_index += 1
            continue
        end
        push!(cut_counts, source.cut_counts[index])
        push!(counts, source.counts[index])
        push!(sum_m2, source.sum_m2[index])
        push!(sum_m4, source.sum_m4[index])
    end
    return CutHistogramBin(cut_counts, counts, sum_m2, sum_m4)
end

function merge_histograms(histograms::AbstractVector{<:CutHistogramBin})
    return foldl(merge_histograms, histograms; init=CutHistogramBin(Int[], Int[], Float64[], Float64[]))
end

_reweight_ratio(ratio::Real) = begin
    normalized = Float64(ratio)
    isfinite(normalized) && normalized > 0 ||
        throw(ArgumentError("reweight ratio must be positive and finite"))
    normalized
end

function _scaled_weights(histogram::CutHistogramBin, ratio::Float64)
    isempty(histogram.cut_counts) &&
        throw(ArgumentError("cannot reweight an empty cut histogram"))
    isone(ratio) && return ones(Float64, length(histogram.cut_counts))
    log_ratio = log(ratio)
    reference_cut_count = log_ratio > 0 ? maximum(histogram.cut_counts) : minimum(histogram.cut_counts)
    log_weights = Float64[
        (Float64(cut_count) - Float64(reference_cut_count)) * log_ratio for
        cut_count in histogram.cut_counts
    ]
    max_log_weight = maximum(log_weights)
    return exp.(log_weights .- max_log_weight)
end

"""Return stable reweighted time moments and the 30%-ESS usability gate."""
function reweight_moments(histogram::CutHistogramBin, ratio::Real)
    normalized_ratio = _reweight_ratio(ratio)
    weights = _scaled_weights(histogram, normalized_ratio)
    denominator = sum(weights .* histogram.counts)
    denominator > 0 && isfinite(denominator) ||
        throw(ArgumentError("reweighting normalization is not finite and positive"))
    m2 = sum(weights .* histogram.sum_m2) / denominator
    m4 = sum(weights .* histogram.sum_m4) / denominator
    isfinite(m2) && isfinite(m4) ||
        throw(ArgumentError("reweighted moments are not finite"))
    ess_fraction = reweight_ess_fraction(histogram, normalized_ratio)
    return (m2=m2, m4=m4, ess_fraction=ess_fraction, usable=ess_fraction >= 0.30)
end

function reweight_binder(histogram::CutHistogramBin, ratio::Real)
    moments = reweight_moments(histogram, ratio)
    moments.m4 != 0 || throw(ArgumentError("reweighted fourth moment is zero"))
    binder = moments.m2^2 / moments.m4
    isfinite(binder) || throw(ArgumentError("reweighted Binder ratio is not finite"))
    return binder
end

"""Return reweighted ESS divided by the total number of retained sweeps."""
function reweight_ess_fraction(histogram::CutHistogramBin, ratio::Real)
    normalized_ratio = _reweight_ratio(ratio)
    weights = _scaled_weights(histogram, normalized_ratio)
    weighted_sum = sum(weights .* histogram.counts)
    weighted_square_sum = sum((weights .^ 2) .* histogram.counts)
    samples = sum(histogram.counts)
    fraction = weighted_sum^2 / weighted_square_sum / samples
    isfinite(fraction) && 0 < fraction <= 1 ||
        throw(ArgumentError("reweighted ESS fraction is invalid"))
    return fraction
end
