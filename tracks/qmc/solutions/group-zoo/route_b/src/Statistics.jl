struct BinnedStats
    mean::Float64
    stderr::Float64
    tau_int::Float64
    ess::Float64
    nbins::Int
    binsize::Int
    bins::Vector{Float64}
end

function _initial_positive_tau(bins::Vector{Float64})
    n = length(bins)
    n < 2 && return 0.5
    centered = bins .- mean(bins)
    gamma0 = sum(abs2, centered) / n
    gamma0 == 0 && return 0.5
    rho = Float64[]
    for lag in 1:(n - 1)
        push!(rho, sum(centered[1:(n - lag)] .* centered[(lag + 1):n]) / n / gamma0)
    end
    tau = 0.5
    index = 1
    while index <= length(rho)
        next = index < length(rho) ? rho[index + 1] : 0.0
        rho[index] + next > 0 || break
        tau += rho[index] + next
        index += 2
    end
    return max(0.5, tau)
end

function binned_stats(values::AbstractVector{<:Real}; binsize::Integer)
    binsize > 0 || throw(ArgumentError("binsize must be positive"))
    isempty(values) && throw(ArgumentError("values must not be empty"))
    all(isfinite, values) || throw(ArgumentError("values must be finite"))
    length(values) % binsize == 0 ||
        throw(ArgumentError("values length must be divisible by binsize"))
    bins = Float64[
        mean(Float64.(values[first:last])) for
        first in 1:binsize:length(values) for last in (first + binsize - 1,)
    ]
    n = length(bins)
    n >= 2 || throw(ArgumentError("at least two bins are required"))
    average = mean(bins)
    tau = _initial_positive_tau(bins)
    variance = sum(abs2, bins .- average) / (n - 1)
    stderr = sqrt(max(0.0, variance * 2tau / n))
    return BinnedStats(average, stderr, tau, n / (2tau), n, Int(binsize), bins)
end
