module ErrorBudget

using Statistics

export acceptance_tolerance, baseline_acceptance, summarize_samples

function summarize_samples(samples)
    length(samples) >= 2 ||
        throw(ArgumentError("at least two independent seeds are required for an SE"))
    values = Float64.(samples)
    all(isfinite, values) || throw(ArgumentError("samples must all be finite"))
    standard_deviation = std(values; corrected = true)
    return (
        n = length(values),
        mean = mean(values),
        standard_deviation,
        standard_error = standard_deviation / sqrt(length(values)),
    )
end

acceptance_tolerance(summary) = max(0.002, 3 * summary.standard_error)

function baseline_acceptance(samples, reference::Real)
    summary = summarize_samples(samples)
    difference = abs(summary.mean - reference)
    tolerance = acceptance_tolerance(summary)
    return (; summary..., reference = Float64(reference), difference, tolerance, accepted = difference <= tolerance)
end

end
