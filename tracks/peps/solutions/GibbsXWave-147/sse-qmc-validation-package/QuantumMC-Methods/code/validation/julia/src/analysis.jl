struct Estimate
    value::Float64
    error::Float64
end

function Base.show(io::IO, estimate::Estimate)
    print(io, estimate.value, " ± ", estimate.error)
end

struct SSEResult
    energy::Estimate
    heat_capacity::Estimate
    transverse_magnetization::Union{Estimate,Nothing}
    bond_correlation::Union{Estimate,Nothing}
    mz2::Estimate
    standard_energy::Estimate
    standard_heat_capacity::Estimate
    standard_transverse_magnetization::Union{Estimate,Nothing}
    mean_expansion_order::Float64
    mean_deflated_expansion_order::Float64
    max_expansion_order::Int
    cutoff::Int
    cutoff_touched::Bool
    warmup_sweeps::Int
    measurement_sweeps::Int
    bin_size::Int
    bins::Int
    seed::UInt64
end

function _jackknife(bin_sums::Matrix{Float64}, estimator)
    bins, columns = size(bin_sums)
    bins >= 2 || throw(ArgumentError("jackknife requires at least two bins"))
    totals = vec(sum(bin_sums; dims=1))
    full = estimator(totals)
    leave_one_out = Vector{Float64}(undef, bins)

    for bin in 1:bins
        reduced = Vector{Float64}(undef, columns)
        for column in 1:columns
            reduced[column] = totals[column] - bin_sums[bin, column]
        end
        leave_one_out[bin] = estimator(reduced)
    end

    loo_mean = mean(leave_one_out)
    value = bins * full - (bins - 1) * loo_mean
    error = sqrt((bins - 1) / bins *
                 sum((sample - loo_mean)^2 for sample in leave_one_out))
    return Estimate(value, error)
end

function _warmup_cutoff_guard!(state::SSEState)
    M = length(state.operators)
    if state.cutoff_touched || 4state.max_n_observed > 3M
        grow_cutoff!(state)
        # A warmup event has now been accommodated by the larger string. Only
        # measurement-time touches are retained as scientific diagnostics.
        state.cutoff_touched = false
    end
    return state
end

"""
    run_sse(model, beta; ...)

Run the transparent SSE kernel and return binned jackknife estimates. Columns
accumulated per bin are `(count, n, n², nJ, nh, mz², n0, nflip, m, m²)`,
where `n0` counts the explicitly sampled `hN*I` site constants and
`m = n - n0`. Energy, heat capacity, and transverse magnetization use the
constant-deflated counts, which are exactly equivalent in expectation and have
lower variance.
"""
function run_sse(model::SquareLatticeTFIM, beta::Real;
                 warmup::Integer=5_000,
                 sweeps::Integer=50_000,
                 bin_size::Integer=500,
                 seed::Integer=0x5eed,
                 cutoff::Union{Nothing,Integer}=nothing,
                 validate_every::Integer=100)
    beta > 0 || throw(ArgumentError("SSE requires beta > 0"))
    warmup >= 0 || throw(ArgumentError("warmup must be nonnegative"))
    sweeps > 0 || throw(ArgumentError("sweeps must be positive"))
    bin_size > 0 || throw(ArgumentError("bin_size must be positive"))
    sweeps % bin_size == 0 ||
        throw(ArgumentError("sweeps must be divisible by bin_size"))
    bins = div(sweeps, bin_size)
    bins >= 2 || throw(ArgumentError("at least two bins are required"))

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

    # Freeze cutoff and diagnostics at the measurement boundary.
    state.max_n_observed = state.n
    state.cutoff_touched = state.n == length(state.operators)
    bin_sums = zeros(Float64, bins, 10)

    for bin in 1:bins
        for within_bin in 1:Int(bin_size)
            sweep!(state, model, beta, rng)
            measurement = raw_measurement(state, model)
            bin_sums[bin, 1] += 1
            bin_sums[bin, 2] += measurement.n
            bin_sums[bin, 3] += measurement.n2
            bin_sums[bin, 4] += measurement.nJ
            bin_sums[bin, 5] += measurement.nh
            bin_sums[bin, 6] += measurement.mz2
            bin_sums[bin, 7] += measurement.n0
            bin_sums[bin, 8] += measurement.nflip
            bin_sums[bin, 9] += measurement.m
            bin_sums[bin, 10] += measurement.m2

            sweep_number = (bin - 1) * Int(bin_size) + within_bin
            if validate_every > 0 && sweep_number % validate_every == 0
                validate_configuration(state, model)
            end
        end
    end

    N = nsites(model)
    Nb = nbonds(model)
    beta_f = Float64(beta)
    # Sum_i h*I is a global constant hN*I. Its operator count is an
    # independent Poisson variable and can be factored from Z exactly:
    # H = J*Nb*I - [sum_b J(1+zz)_b + sum_i h*x_i].
    deflated_shift = model.J * Nb
    count_samples(values) = values[1]
    mean_column(values, column) = values[column] / count_samples(values)

    energy = _jackknife(bin_sums,
        values -> (deflated_shift - mean_column(values, 9) / beta_f) / N)
    heat_capacity = _jackknife(bin_sums, values -> begin
        mean_m = mean_column(values, 9)
        mean_m2 = mean_column(values, 10)
        (mean_m2 - mean_m^2 - mean_m) / N
    end)
    mx = iszero(model.h) ? nothing :
         _jackknife(bin_sums,
            values -> mean_column(values, 8) / (beta_f * model.h * N))
    standard_shift = deflated_shift + model.h * N
    standard_energy = _jackknife(bin_sums,
        values -> (standard_shift - mean_column(values, 2) / beta_f) / N)
    standard_heat_capacity = _jackknife(bin_sums, values -> begin
        mean_n = mean_column(values, 2)
        mean_n2 = mean_column(values, 3)
        (mean_n2 - mean_n^2 - mean_n) / N
    end)
    standard_mx = iszero(model.h) ? nothing :
                  _jackknife(bin_sums,
                     values -> -1 + mean_column(values, 5) /
                                       (beta_f * model.h * N))
    bond_correlation = iszero(model.J) || iszero(Nb) ? nothing :
         _jackknife(bin_sums,
            values -> -1 + mean_column(values, 4) / (beta_f * model.J * Nb))
    mz2 = _jackknife(bin_sums, values -> mean_column(values, 6))

    mean_n = sum(bin_sums[:, 2]) / sum(bin_sums[:, 1])
    mean_m = sum(bin_sums[:, 9]) / sum(bin_sums[:, 1])
    return SSEResult(energy,
                     heat_capacity,
                     mx,
                     bond_correlation,
                     mz2,
                     standard_energy,
                     standard_heat_capacity,
                     standard_mx,
                     mean_n,
                     mean_m,
                     state.max_n_observed,
                     length(state.operators),
                     state.cutoff_touched,
                     Int(warmup),
                     Int(sweeps),
                     Int(bin_size),
                     bins,
                     seed_u)
end
