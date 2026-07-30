"""
    SSETrace

Per-sweep raw measurements retained for autocorrelation and blocking analysis.
This is SSE validation diagnostic data; it does not alter the
SSE update kernel.
"""
struct SSETrace
    n::Vector{Int}
    nJ::Vector{Int}
    n0::Vector{Int}
    nflip::Vector{Int}
    nh::Vector{Int}
    mz2::Vector{Float64}
    max_expansion_order::Int
    cutoff::Int
    cutoff_touched::Bool
    warmup_sweeps::Int
    seed::UInt64
end

Base.length(trace::SSETrace) = length(trace.n)

struct AutocorrelationEstimate
    tau_int::Float64
    standard_error::Float64
    effective_samples::Float64
    sample_variance::Float64
    asymptotic_variance::Float64
    window::Int
    positive_pairs::Int
end

struct BlockingPoint
    block_size::Int
    blocks::Int
    samples::Int
    estimate::Float64
    standard_error::Float64
end

"""
    sample_sse_trace(model, beta; ...)

Run the transparent SSE kernel and retain one raw measurement after every full
Monte Carlo sweep. The cutoff may grow only during warmup and is frozen during
measurement, matching `run_sse`.
"""
function sample_sse_trace(model::SquareLatticeTFIM, beta::Real;
                          warmup::Integer=5_000,
                          sweeps::Integer=50_000,
                          seed::Integer=0x5eed,
                          cutoff::Union{Nothing,Integer}=nothing,
                          validate_every::Integer=100)
    beta > 0 || throw(ArgumentError("SSE requires beta > 0"))
    warmup >= 0 || throw(ArgumentError("warmup must be nonnegative"))
    sweeps > 1 || throw(ArgumentError("at least two measurement sweeps are required"))
    validate_every >= 0 ||
        throw(ArgumentError("validate_every must be nonnegative"))

    seed_u = UInt64(seed)
    rng = Xoshiro(seed_u)
    state = initialize_sse(model, beta, rng; cutoff)

    for sweep in 1:Int(warmup)
        sweep!(state, model, beta, rng)
        _warmup_cutoff_guard!(state)
        if validate_every > 0 && sweep % validate_every == 0
            validate_configuration(state, model)
        end
    end

    state.max_n_observed = state.n
    state.cutoff_touched = state.n == length(state.operators)
    measurement_sweeps = Int(sweeps)
    n = Vector{Int}(undef, measurement_sweeps)
    nJ = Vector{Int}(undef, measurement_sweeps)
    n0 = Vector{Int}(undef, measurement_sweeps)
    nflip = Vector{Int}(undef, measurement_sweeps)
    nh = Vector{Int}(undef, measurement_sweeps)
    mz2 = Vector{Float64}(undef, measurement_sweeps)

    for sweep in 1:measurement_sweeps
        sweep!(state, model, beta, rng)
        measurement = raw_measurement(state, model)
        n[sweep] = measurement.n
        nJ[sweep] = measurement.nJ
        n0[sweep] = measurement.n0
        nflip[sweep] = measurement.nflip
        nh[sweep] = measurement.nh
        mz2[sweep] = measurement.mz2

        if validate_every > 0 && sweep % validate_every == 0
            validate_configuration(state, model)
        end
    end

    return SSETrace(n,
                    nJ,
                    n0,
                    nflip,
                    nh,
                    mz2,
                    state.max_n_observed,
                    length(state.operators),
                    state.cutoff_touched,
                    Int(warmup),
                    seed_u)
end

function _observable_estimator(model::SquareLatticeTFIM, beta::Real,
                               observable::Symbol)
    N = nsites(model)
    Nb = nbonds(model)
    beta_f = Float64(beta)
    deflated_shift = model.J * Nb
    standard_shift = deflated_shift + model.h * N
    count_samples(values) = values[1]
    mean_column(values, column) = values[column] / count_samples(values)

    if observable === :u
        return values ->
            (deflated_shift - mean_column(values, 9) / beta_f) / N
    elseif observable === :c
        return values -> begin
            mean_m = mean_column(values, 9)
            mean_m2 = mean_column(values, 10)
            (mean_m2 - mean_m^2 - mean_m) / N
        end
    elseif observable === :mx
        iszero(model.h) &&
            throw(ArgumentError("mx count estimator is undefined at h=0"))
        return values ->
            mean_column(values, 8) / (beta_f * model.h * N)
    elseif observable === :u_standard
        return values ->
            (standard_shift - mean_column(values, 2) / beta_f) / N
    elseif observable === :c_standard
        return values -> begin
            mean_n = mean_column(values, 2)
            mean_n2 = mean_column(values, 3)
            (mean_n2 - mean_n^2 - mean_n) / N
        end
    elseif observable === :mx_standard
        iszero(model.h) &&
            throw(ArgumentError("mx count estimator is undefined at h=0"))
        return values ->
            -1 + mean_column(values, 5) / (beta_f * model.h * N)
    elseif observable === :bond_correlation
        (iszero(model.J) || iszero(Nb)) &&
            throw(ArgumentError("bond estimator requires J>0 and at least one bond"))
        return values ->
            -1 + mean_column(values, 4) / (beta_f * model.J * Nb)
    elseif observable === :mz2
        return values -> mean_column(values, 6)
    end
    throw(ArgumentError("unsupported observable: $observable"))
end

function _trace_sums(trace::SSETrace, samples::Integer=length(trace))
    count = Int(samples)
    1 <= count <= length(trace) ||
        throw(ArgumentError("samples must lie between 1 and trace length"))
    sum_n = sum(view(trace.n, 1:count))
    return Float64[
        count,
        sum_n,
        sum(value^2 for value in view(trace.n, 1:count)),
        sum(view(trace.nJ, 1:count)),
        sum(view(trace.nh, 1:count)),
        sum(view(trace.mz2, 1:count)),
        sum(view(trace.n0, 1:count)),
        sum(view(trace.nflip, 1:count)),
        sum(trace.n[sample] - trace.n0[sample] for sample in 1:count),
        sum((trace.n[sample] - trace.n0[sample])^2 for sample in 1:count),
    ]
end

"""
    observable_estimate(trace, model, beta, observable)

Evaluate one of `:u`, `:c`, `:mx`, `:bond_correlation`, or `:mz2` from the
whole raw trace. The primary `:u`, `:c`, and `:mx` estimators analytically
deflate the sampled `hN*I` constant. The corresponding original operator-count
estimators remain available as `:u_standard`, `:c_standard`, and
`:mx_standard` for variance audits.
"""
function observable_estimate(trace::SSETrace, model::SquareLatticeTFIM,
                             beta::Real, observable::Symbol)
    estimator = _observable_estimator(model, beta, observable)
    return estimator(_trace_sums(trace))
end

"""
    observable_influence(trace, model, beta, observable)

Return a zero-mean, per-sweep influence series for asymptotic error analysis.
For primary heat capacity this is the joint `(m,m²)` delta-method influence
function, where `m=n-n0`; for `:c_standard` it remains `(n,n²)`. Thus the
covariance of the two moments is retained in both variants.
"""
function observable_influence(trace::SSETrace, model::SquareLatticeTFIM,
                              beta::Real, observable::Symbol)
    N = nsites(model)
    beta_f = Float64(beta)

    if observable === :u
        m = trace.n .- trace.n0
        mean_m = mean(m)
        return Float64[-(value - mean_m) / (beta_f * N) for value in m]
    elseif observable === :c
        m = trace.n .- trace.n0
        mean_m = mean(m)
        mean_m2 = mean(value^2 for value in m)
        return Float64[
            ((value^2 - mean_m2) + (-2mean_m - 1) * (value - mean_m)) / N
            for value in m
        ]
    elseif observable === :mx
        iszero(model.h) &&
            throw(ArgumentError("mx count estimator is undefined at h=0"))
        mean_nflip = mean(trace.nflip)
        return Float64[
            (value - mean_nflip) / (beta_f * model.h * N)
            for value in trace.nflip
        ]
    elseif observable === :u_standard
        mean_n = mean(trace.n)
        return Float64[-(value - mean_n) / (beta_f * N) for value in trace.n]
    elseif observable === :c_standard
        mean_n = mean(trace.n)
        mean_n2 = mean(value^2 for value in trace.n)
        return Float64[
            ((value^2 - mean_n2) + (-2mean_n - 1) * (value - mean_n)) / N
            for value in trace.n
        ]
    elseif observable === :mx_standard
        iszero(model.h) &&
            throw(ArgumentError("mx count estimator is undefined at h=0"))
        mean_nh = mean(trace.nh)
        return Float64[
            (value - mean_nh) / (beta_f * model.h * N)
            for value in trace.nh
        ]
    elseif observable === :bond_correlation
        Nb = nbonds(model)
        (iszero(model.J) || iszero(Nb)) &&
            throw(ArgumentError("bond estimator requires J>0 and at least one bond"))
        mean_nJ = mean(trace.nJ)
        return Float64[
            (value - mean_nJ) / (beta_f * model.J * Nb)
            for value in trace.nJ
        ]
    elseif observable === :mz2
        mean_mz2 = mean(trace.mz2)
        return Float64[value - mean_mz2 for value in trace.mz2]
    end
    throw(ArgumentError("unsupported observable: $observable"))
end

@inline function _autocovariance(centered::Vector{Float64}, lag::Int)
    count = length(centered)
    return dot(view(centered, 1:(count - lag)),
               view(centered, (lag + 1):count)) / count
end

"""
    autocorrelation_estimate(samples; max_lag=nothing)

Estimate integrated autocorrelation time with Geyer's initial monotone
sequence. The convention is `tau_int = 1/2 + sum(rho[t])`, giving
`SE² = 2*tau_int*var/N`. For a conservative readiness test, `tau_int` is
capped below at `1/2`.
"""
function autocorrelation_estimate(samples::AbstractVector{<:Real};
                                  max_lag::Union{Nothing,Integer}=nothing)
    count = length(samples)
    count >= 4 || throw(ArgumentError("at least four samples are required"))
    centered = Float64.(samples)
    centered .-= mean(centered)
    gamma0 = dot(centered, centered) / count

    if iszero(gamma0)
        return AutocorrelationEstimate(0.5, 0.0, Float64(count), 0.0,
                                       0.0, 0, 0)
    end

    lag_limit = isnothing(max_lag) ?
                min(count - 1, max(100, ceil(Int, 10sqrt(count)))) :
                min(count - 1, Int(max_lag))
    lag_limit >= 1 || throw(ArgumentError("max_lag must be positive"))

    pair_sums = Float64[]
    previous = Inf
    pair_index = 0
    while 2pair_index + 1 <= lag_limit
        even_lag = 2pair_index
        odd_lag = even_lag + 1
        gamma_even = iszero(even_lag) ?
                     gamma0 : _autocovariance(centered, even_lag)
        gamma_odd = _autocovariance(centered, odd_lag)
        pair_sum = gamma_even + gamma_odd
        pair_sum > 0 || break
        monotone_pair = min(pair_sum, previous)
        push!(pair_sums, monotone_pair)
        previous = monotone_pair
        pair_index += 1
    end

    raw_asymptotic_variance =
        isempty(pair_sums) ? gamma0 : -gamma0 + 2sum(pair_sums)
    raw_tau = raw_asymptotic_variance / (2gamma0)
    tau_int = max(0.5, raw_tau)
    asymptotic_variance = 2tau_int * gamma0
    standard_error = sqrt(asymptotic_variance / count)
    effective_samples = count / (2tau_int)
    window = isempty(pair_sums) ? 0 : 2length(pair_sums) - 1

    return AutocorrelationEstimate(tau_int,
                                   standard_error,
                                   effective_samples,
                                   gamma0,
                                   asymptotic_variance,
                                   window,
                                   length(pair_sums))
end

function _block_sums(trace::SSETrace, block_size::Int, blocks::Int)
    sums = zeros(Float64, blocks, 10)
    for block in 1:blocks
        first_sample = (block - 1) * block_size + 1
        last_sample = block * block_size
        for sample in first_sample:last_sample
            n = trace.n[sample]
            sums[block, 1] += 1
            sums[block, 2] += n
            sums[block, 3] += n^2
            sums[block, 4] += trace.nJ[sample]
            sums[block, 5] += trace.nh[sample]
            sums[block, 6] += trace.mz2[sample]
            sums[block, 7] += trace.n0[sample]
            sums[block, 8] += trace.nflip[sample]
            m = n - trace.n0[sample]
            sums[block, 9] += m
            sums[block, 10] += m^2
        end
    end
    return sums
end

"""
    blocking_curve(trace, model, beta, observable; min_blocks=8)

Compute binned-jackknife standard errors for power-of-two block lengths. Any
trailing samples that do not fill a complete block are excluded and reported
through the `samples` field.
"""
function blocking_curve(trace::SSETrace, model::SquareLatticeTFIM, beta::Real,
                        observable::Symbol; min_blocks::Integer=8)
    min_blocks >= 2 || throw(ArgumentError("min_blocks must be at least two"))
    estimator = _observable_estimator(model, beta, observable)
    points = BlockingPoint[]
    block_size = 1

    while div(length(trace), block_size) >= min_blocks
        blocks = div(length(trace), block_size)
        samples = blocks * block_size
        estimate = _jackknife(_block_sums(trace, block_size, blocks), estimator)
        push!(points,
              BlockingPoint(block_size,
                            blocks,
                            samples,
                            estimate.value,
                            estimate.error))
        block_size *= 2
    end
    return points
end
