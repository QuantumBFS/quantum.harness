"""
    autocorrelation_fft_free(series; maxlag=nothing)

Return normalized scalar autocorrelations from lag zero through `maxlag`.
Each lag uses its overlapping observations, so a nonconstant alternating series
has autocorrelations exactly `(-1)^lag`.  This implementation deliberately uses
direct, numerically explicit sums and has no FFT or package dependency.

When `maxlag` is omitted, the result is capped at `floor(sqrt(length(series)))`
(or the final available lag).  The cap keeps the direct method subquadratic for
large raw-bin chains; callers requiring a particular horizon must pass it
explicitly.  `series` must contain at least two finite real values with positive
finite variance.  Constant, non-finite, too-short, or numerically degenerate
series raise `ArgumentError`; no values are discarded.
"""
function autocorrelation_fft_free(series::AbstractVector{<:Real}; maxlag::Union{Nothing,Integer}=nothing)
    values, _, sumsq = _checked_scalar_series(series; minimum_length=2)
    n = length(values)
    limit = isnothing(maxlag) ? min(n - 1, max(1, isqrt(n))) : Int(maxlag)
    0 <= limit < n || throw(ArgumentError("maxlag must lie between 0 and $(n - 1)"))

    centered = values .- mean(values)
    autocorrelation = Vector{Float64}(undef, limit + 1)
    autocorrelation[1] = 1.0
    for lag in 1:limit
        autocorrelation[lag + 1] = _lag_autocorrelation(centered, sumsq, lag)
    end
    return autocorrelation
end

"""
    tau_int_initial_positive(series; maxlag=nothing)

Estimate the integrated autocorrelation time with the initial-positive adjacent
pair estimator.  Starting with `(rho[0], rho[1])`, it stops before the first
pair whose sum is non-positive; every accepted pair contributes its positive-lag
members to `0.5 + sum(rho[lag])`.  The returned value is clamped below by `0.5`.

With no explicit `maxlag`, every complete adjacent pair available in the chain
is examined, so a returned estimate has not silently stopped at a lag horizon.
Passing `maxlag` requests a finite horizon; if no non-positive pair occurs
before that horizon, the function raises `ArgumentError` instead of returning a
truncated estimate.  An odd final lag is ignored because adjacent pairs are
indivisible.  Inputs must be finite, nonconstant scalar series of length at
least two.  Invalid or numerically degenerate inputs raise `ArgumentError`
rather than being repaired or filtered.
"""
function tau_int_initial_positive(
    series::AbstractVector{<:Real};
    maxlag::Union{Nothing,Integer}=nothing,
)
    values, _, sumsq = _checked_scalar_series(series; minimum_length=2)
    n = length(values)
    limit = _tau_lag_limit(n, maxlag)
    centered = values .- mean(values)
    return _tau_from_centered(centered, sumsq, limit; truncated_if_exhausted=limit < n - 1)
end

"""
    effective_sample_size(series; maxlag=nothing)

Return `n / (2 * tau_int_initial_positive(series))`.  Its value lies in
`(0, n]` because the autocorrelation-time estimator is bounded below by `0.5`.
The same finite, nonconstant, at-least-two-observation requirements and
autocorrelation horizon semantics as `tau_int_initial_positive` apply.
"""
function effective_sample_size(
    series::AbstractVector{<:Real};
    maxlag::Union{Nothing,Integer}=nothing,
)
    values, _, sumsq = _checked_scalar_series(series; minimum_length=2)
    limit = _tau_lag_limit(length(values), maxlag)
    tau = _tau_from_centered(
        values .- mean(values), sumsq, limit;
        truncated_if_exhausted=limit < length(values) - 1,
    )
    ess = length(values) / (2 * tau)
    isfinite(ess) && 0 < ess <= length(values) ||
        throw(ArgumentError("effective sample size is not finite and positive"))
    return ess
end

"""
    split_chain_z(series; maxlag=nothing)

Return the signed difference between the first- and second-half means divided
by their independent raw-bin standard errors.  A half-chain mean standard
error is `sqrt(s^2 / n)`, where `s^2` is its sample variance.  The denominator
is the quadrature sum of the two half standard errors.  Autocorrelation and
ESS are reported separately and do not rescale this fixed split-chain gate.

The input must have an even length of at least four, so both halves contain at
least two samples.  Either constant, non-finite, or otherwise degenerate half
raises `ArgumentError`; the diagnostic never silently omits a half.
"""
function split_chain_z(
    series::AbstractVector{<:Real};
    maxlag::Union{Nothing,Integer}=nothing,
)
    values, _, _ = _checked_scalar_series(series; minimum_length=4)
    iseven(length(values)) || throw(ArgumentError("split-chain diagnostic requires an even-length series"))
    midpoint = length(values) ÷ 2
    first = _chain_mean_summary(@view(values[1:midpoint]); maxlag=maxlag)
    second = _chain_mean_summary(@view(values[(midpoint + 1):end]); maxlag=maxlag)
    denominator = sqrt(first.stderr^2 + second.stderr^2)
    isfinite(denominator) && denominator > 0 ||
        throw(ArgumentError("split-chain standard-error denominator is degenerate"))
    z = (first.mean - second.mean) / denominator
    isfinite(z) || throw(ArgumentError("split-chain z diagnostic is not finite"))
    return z
end

"""
    chain_compatibility(chains; maxlag=nothing)

Evaluate every supplied chain without filtering.  For each finite,
nonconstant chain of length at least two, its compatibility mean standard error
is the raw-bin standard error `sqrt(s^2 / n)`, with `s^2` the sample variance.
Autocorrelation time and `ESS = n / (2 * tau_int)` are returned as separate
diagnostics but deliberately do not alter this prescribed between-chain gate.
The pooled mean is the inverse-variance weighted mean
`sum(w_i * mean_i) / sum(w_i)`, where `w_i = 1 / stderr_i^2`; its fitted mean
uses one degree of freedom, so `dof = number_of_chains - 1`.

The returned named tuple contains all chain means, standard errors, scaled
inverse-variance weights, standardized residuals, and raw gate statistics.
`weights` are `(minimum(stderr) / stderr_i)^2`, which is algebraically
equivalent to inverse-variance weighting while remaining finite under a common
rescaling of all chains.  `passed` is true exactly
when `max_standardized_residual <= 3.5` and `reduced_chisquare <= 2.0`.
At least two valid chains are required.  Constant, non-finite, too-short, or
numerically degenerate chains raise `ArgumentError` rather than being dropped;
a statistically incompatible but valid chain remains in every returned field
and makes `passed` false.
"""
function chain_compatibility(chains::AbstractVector; maxlag::Union{Nothing,Integer}=nothing)
    count = length(chains)
    count >= 2 || throw(ArgumentError("chain compatibility requires at least two chains"))

    summaries = [_chain_mean_summary(chain; maxlag=maxlag) for chain in chains]
    chain_means = getfield.(summaries, :mean)
    chain_stderrs = getfield.(summaries, :stderr)
    chain_taus = getfield.(summaries, :tau_int)
    chain_ess = getfield.(summaries, :ess)
    reference_stderr = minimum(chain_stderrs)
    isfinite(reference_stderr) && reference_stderr > 0 ||
        throw(ArgumentError("chain mean standard-error reference is degenerate"))
    weights = (reference_stderr ./ chain_stderrs) .^ 2
    all(isfinite, weights) && all(>(0.0), weights) ||
        throw(ArgumentError("scaled chain mean weights must be finite and positive"))
    total_weight = sum(weights)
    isfinite(total_weight) && total_weight > 0 ||
        throw(ArgumentError("total chain mean weight is degenerate"))
    pooled_mean = sum(weights .* chain_means) / total_weight
    isfinite(pooled_mean) || throw(ArgumentError("pooled chain mean is not finite"))
    standardized_residuals = (chain_means .- pooled_mean) ./ chain_stderrs
    all(isfinite, standardized_residuals) ||
        throw(ArgumentError("standardized chain residual is not finite"))
    chisquare = sum(abs2, standardized_residuals)
    dof = count - 1
    reduced_chisquare = chisquare / dof
    max_standardized_residual = maximum(abs, standardized_residuals)
    isfinite(chisquare) && isfinite(reduced_chisquare) && isfinite(max_standardized_residual) ||
        throw(ArgumentError("chain compatibility statistic is not finite"))
    passed = max_standardized_residual <= 3.5 && reduced_chisquare <= 2.0
    return (
        passed=passed,
        chain_means=chain_means,
        chain_stderrs=chain_stderrs,
        chain_taus=chain_taus,
        chain_ess=chain_ess,
        weights=weights,
        pooled_mean=pooled_mean,
        standardized_residuals=standardized_residuals,
        max_standardized_residual=max_standardized_residual,
        chisquare=chisquare,
        dof=dof,
        reduced_chisquare=reduced_chisquare,
    )
end

function _checked_scalar_series(series::AbstractVector{<:Real}; minimum_length::Integer)
    n = length(series)
    n >= minimum_length || throw(ArgumentError("series must contain at least $minimum_length observations"))
    values = Vector{Float64}(undef, n)
    for index in eachindex(series)
        value = Float64(series[index])
        isfinite(value) || throw(ArgumentError("series contains a non-finite value at index $index"))
        values[index] = value
    end
    series_mean = mean(values)
    isfinite(series_mean) || throw(ArgumentError("series mean is not finite"))
    centered = values .- series_mean
    sumsq = sum(abs2, centered)
    isfinite(sumsq) && sumsq > 0 ||
        throw(ArgumentError("series must have positive finite variance"))
    return values, series_mean, sumsq
end

function _tau_lag_limit(n::Integer, requested::Union{Nothing,Integer})
    limit = isnothing(requested) ? n - 1 : Int(requested)
    1 <= limit < n || throw(ArgumentError("maxlag must lie between 1 and $(n - 1) for tau estimation"))
    return limit
end

@inline function _lag_autocorrelation(centered::AbstractVector{Float64}, sumsq::Float64, lag::Integer)
    overlap = length(centered) - lag
    overlap > 0 || throw(ArgumentError("autocorrelation lag exceeds the series length"))
    covariance_sum = 0.0
    @inbounds for index in 1:overlap
        covariance_sum += centered[index] * centered[index + lag]
    end
    autocorrelation = (covariance_sum / overlap) / (sumsq / length(centered))
    isfinite(autocorrelation) || throw(ArgumentError("autocorrelation is not finite"))
    return autocorrelation
end

@inline _adjacent_pair_positive(first::Float64, second::Float64) = first + second > 0

function _lag_autocovariance_sum(centered::AbstractVector{Float64}, lag::Integer)
    overlap = length(centered) - lag
    overlap > 0 || throw(ArgumentError("autocovariance lag exceeds the series length"))
    covariance_sum = 0.0
    @inbounds for index in 1:overlap
        covariance_sum += centered[index] * centered[index + lag]
    end
    isfinite(covariance_sum) || throw(ArgumentError("autocovariance is not finite"))
    return covariance_sum
end

function _tau_from_centered(
    centered::AbstractVector{Float64},
    sumsq::Float64,
    limit::Integer;
    truncated_if_exhausted::Bool,
)
    tau = 0.5
    pair_start = 0
    while pair_start + 1 <= limit
        first = pair_start == 0 ? sumsq : _lag_autocovariance_sum(centered, pair_start)
        second = _lag_autocovariance_sum(centered, pair_start + 1)
        _adjacent_pair_positive(first, second) || return max(0.5, tau)
        tau += pair_start == 0 ? second / sumsq : (first + second) / sumsq
        pair_start += 2
    end
    truncated_if_exhausted &&
        throw(ArgumentError("no non-positive adjacent autocovariance pair occurred before maxlag=$limit"))
    isfinite(tau) || throw(ArgumentError("integrated autocorrelation time is not finite"))
    return max(0.5, tau)
end

function _chain_mean_summary(series::AbstractVector{<:Real}; maxlag::Union{Nothing,Integer}=nothing)
    values, chain_mean, sumsq = _checked_scalar_series(series; minimum_length=2)
    limit = _tau_lag_limit(length(values), maxlag)
    tau = _tau_from_centered(
        values .- chain_mean, sumsq, limit;
        truncated_if_exhausted=limit < length(values) - 1,
    )
    ess = length(values) / (2 * tau)
    variance = sumsq / (length(values) - 1)
    stderr = sqrt(variance) / sqrt(length(values))
    isfinite(ess) && ess > 0 || throw(ArgumentError("chain effective sample size is invalid"))
    isfinite(stderr) && stderr > 0 || throw(ArgumentError("chain mean standard error is invalid"))
    return (mean=chain_mean, stderr, tau_int=tau, ess)
end
