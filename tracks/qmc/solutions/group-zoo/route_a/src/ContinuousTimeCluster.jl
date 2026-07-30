struct Worldline
    spin0::Int8
    cuts::Vector{Float64}

    function Worldline(spin0::Integer, cuts::AbstractVector{<:Real})
        spin0 in (-1, 1) || throw(ArgumentError("worldline spin must be plus or minus one"))
        normalized = Float64.(cuts)
        all(isfinite, normalized) || throw(ArgumentError("cut times must be finite"))
        all(>(0), normalized) || throw(ArgumentError("cut times must be positive"))
        issorted(normalized) || throw(ArgumentError("cut times must be sorted"))
        all(diff(normalized) .> 0) || throw(ArgumentError("cut times must be unique"))
        iseven(length(normalized)) ||
            throw(ArgumentError("a periodic worldline must have an even number of cuts"))
        return new(Int8(spin0), normalized)
    end
end

struct Estimate
    mean::Float64
    stderr::Float64
    bins::Int
end

struct BinRecord
    energy_per_site::Float64
    m_time2::Float64
    m_time4::Float64
    m_equal2::Float64
    m_equal4::Float64
    cuts_mean::Float64
    cut_histogram::CutHistogramBin
end

BinRecord(
    energy_per_site::Real,
    m_time2::Real,
    m_time4::Real,
    m_equal2::Real,
    m_equal4::Real,
    cuts_mean::Real,
) = BinRecord(
    Float64(energy_per_site),
    Float64(m_time2),
    Float64(m_time4),
    Float64(m_equal2),
    Float64(m_equal4),
    Float64(cuts_mean),
    CutHistogramBin(Int[], Int[], Float64[], Float64[]),
)

mutable struct DisjointSets
    parent::Vector{Int}
    size::Vector{Int}
end

DisjointSets(n::Integer) = DisjointSets(collect(1:n), ones(Int, n))

function find_root!(sets::DisjointSets, x::Int)
    while sets.parent[x] != x
        sets.parent[x] = sets.parent[sets.parent[x]]
        x = sets.parent[x]
    end
    return x
end

function union_sets!(sets::DisjointSets, a::Int, b::Int)
    root_a = find_root!(sets, a)
    root_b = find_root!(sets, b)
    root_a == root_b && return root_a
    if sets.size[root_a] < sets.size[root_b]
        root_a, root_b = root_b, root_a
    end
    sets.parent[root_b] = root_a
    sets.size[root_a] += sets.size[root_b]
    return root_a
end

mutable struct CWAState{R<:AbstractRNG}
    geometry::LatticeGeometry
    beta::Float64
    J::Float64
    h_input::Float64
    h_simulated::Float64
    worldlines::Vector{Worldline}
    rng::R
end

function CWAState(
    geometry::LatticeGeometry;
    J::Real,
    h::Real,
    beta::Real,
    seed::Integer,
)
    beta > 0 || throw(ArgumentError("beta must be positive"))
    J >= 0 || throw(ArgumentError("the cluster update requires ferromagnetic J >= 0"))
    rng = Xoshiro(seed)
    worldlines = [Worldline(rand(rng, Bool) ? 1 : -1, Float64[]) for _ in 1:geometry.nsites]
    return CWAState(
        geometry,
        Float64(beta),
        Float64(J),
        Float64(h),
        abs(Float64(h)),
        worldlines,
        rng,
    )
end

function poisson_times(rng::AbstractRNG, rate::Float64, beta::Float64)
    iszero(rate) && return Float64[]
    times = Float64[]
    time = randexp(rng) / rate
    while time < beta
        push!(times, time)
        time += randexp(rng) / rate
    end
    return times
end

function foreach_overlap(callback, breaks_a::Vector{Float64}, breaks_b::Vector{Float64})
    ia = 1
    ib = 1
    while ia < length(breaks_a) && ib < length(breaks_b)
        left = max(breaks_a[ia], breaks_b[ib])
        right = min(breaks_a[ia+1], breaks_b[ib+1])
        right > left && callback(ia, ib, right - left)
        if breaks_a[ia+1] < breaks_b[ib+1]
            ia += 1
        elseif breaks_b[ib+1] < breaks_a[ia+1]
            ib += 1
        else
            ia += 1
            ib += 1
        end
    end
    return nothing
end

function cluster_update!(state::CWAState)
    breaks = Vector{Vector{Float64}}(undef, state.geometry.nsites)
    segment_spins = Vector{Vector{Int8}}(undef, state.geometry.nsites)
    offsets = zeros(Int, state.geometry.nsites + 1)

    for site in 1:state.geometry.nsites
        line = state.worldlines[site]
        candidate_cuts = sort!(vcat(line.cuts, poisson_times(state.rng, state.h_simulated, state.beta)))
        site_breaks = vcat(0.0, candidate_cuts, state.beta)
        spins = Int8[
            spin_at(line, (site_breaks[k] + site_breaks[k+1]) / 2) for
            k in 1:length(site_breaks)-1
        ]
        breaks[site] = site_breaks
        segment_spins[site] = spins
        offsets[site+1] = offsets[site] + length(spins)
    end

    sets = DisjointSets(offsets[end])
    for site in 1:state.geometry.nsites
        nsegments = length(segment_spins[site])
        if nsegments > 1
            union_sets!(sets, offsets[site] + 1, offsets[site] + nsegments)
        end
    end

    for (site_a, site_b) in state.geometry.bonds
        foreach_overlap(breaks[site_a], breaks[site_b]) do segment_a, segment_b, duration
            if segment_spins[site_a][segment_a] == segment_spins[site_b][segment_b]
                bridge_probability = -expm1(-2 * state.J * duration)
                if rand(state.rng) < bridge_probability
                    union_sets!(
                        sets,
                        offsets[site_a] + segment_a,
                        offsets[site_b] + segment_b,
                    )
                end
            end
        end
    end

    cluster_spins = Dict{Int,Int8}()
    for site in 1:state.geometry.nsites
        spins = segment_spins[site]
        for segment in eachindex(spins)
            root = find_root!(sets, offsets[site] + segment)
            spins[segment] = get!(cluster_spins, root) do
                rand(state.rng, Bool) ? Int8(1) : Int8(-1)
            end
        end

        cuts = Float64[]
        for segment in 2:length(spins)
            if spins[segment-1] != spins[segment]
                push!(cuts, breaks[site][segment])
            end
        end
        state.worldlines[site] = Worldline(spins[1], cuts)
    end
    return state
end

function worldline_segments(line::Worldline, beta::Float64)
    breaks = vcat(0.0, line.cuts, beta)
    spins = Int8[
        spin_at(line, (breaks[k] + breaks[k+1]) / 2) for k in 1:length(breaks)-1
    ]
    return breaks, spins
end

function pair_spin_integral(line_a::Worldline, line_b::Worldline, beta::Float64)
    breaks_a, spins_a = worldline_segments(line_a, beta)
    breaks_b, spins_b = worldline_segments(line_b, beta)
    total = Ref(0.0)
    foreach_overlap(breaks_a, breaks_b) do segment_a, segment_b, duration
        total[] += spins_a[segment_a] * spins_b[segment_b] * duration
    end
    return total[]
end

function binned_estimate(values::AbstractVector{<:Real})
    length(values) >= 2 || throw(ArgumentError("at least two bins are required"))
    return Estimate(mean(values), std(values) / sqrt(length(values)), length(values))
end

function rebin_series(values::AbstractVector{<:Real}, factor::Integer)
    factor > 0 || throw(ArgumentError("rebin factor must be positive"))
    length(values) % factor == 0 ||
        throw(ArgumentError("series length must be divisible by the rebin factor"))
    return [mean(@view values[i:i+factor-1]) for i in 1:factor:length(values)]
end

function binder_from_bins(
    m2_bins::AbstractVector{<:Real},
    m4_bins::AbstractVector{<:Real},
)
    length(m2_bins) == length(m4_bins) ||
        throw(ArgumentError("m2 and m4 must have the same number of bins"))
    n = length(m2_bins)
    n >= 2 || throw(ArgumentError("at least two bins are required"))
    sum_m2 = sum(m2_bins)
    sum_m4 = sum(m4_bins)
    full = (sum_m2 / n)^2 / (sum_m4 / n)
    leave_one = [
        ((sum_m2 - m2_bins[i]) / (n - 1))^2 /
        ((sum_m4 - m4_bins[i]) / (n - 1)) for i in 1:n
    ]
    leave_mean = mean(leave_one)
    stderr = sqrt((n - 1) / n * sum((leave_one .- leave_mean) .^ 2))
    return Estimate(full, stderr, n)
end

function thermalize!(state::CWAState, sweeps::Integer)::CWAState
    sweeps >= 0 || throw(ArgumentError("thermalization must be nonnegative"))
    for _ in 1:sweeps
        cluster_update!(state)
    end
    return state
end

function measure_bin!(state::CWAState, binsize::Integer)::BinRecord
    binsize > 0 || throw(ArgumentError("binsize must be positive"))
    energy_per_site = 0.0
    m_time2 = 0.0
    m_time4 = 0.0
    m_equal2 = 0.0
    m_equal4 = 0.0
    cuts_mean = 0.0
    cut_counts = Int[]
    cut_m2 = Float64[]
    cut_m4 = Float64[]
    N = state.geometry.nsites

    for _ in 1:binsize
        cluster_update!(state)
        integrated_magnetization =
            sum(line -> integrated_spin(line, state.beta), state.worldlines) /
            (N * state.beta)
        cuts = sum(line -> length(line.cuts), state.worldlines)
        interaction_integral = 0.0
        for bond in state.geometry.bonds
            interaction_integral += pair_spin_integral(
                state.worldlines[bond[1]],
                state.worldlines[bond[2]],
                state.beta,
            )
        end
        energy =
            -state.J * interaction_integral / (state.beta * N) -
            cuts / (state.beta * N)
        equal_time_magnetization = sum(line -> line.spin0, state.worldlines) / N
        integrated_magnetization2 = integrated_magnetization^2
        integrated_magnetization4 = integrated_magnetization^4
        energy_per_site += energy / binsize
        m_time2 += integrated_magnetization2 / binsize
        m_time4 += integrated_magnetization4 / binsize
        m_equal2 += equal_time_magnetization^2 / binsize
        m_equal4 += equal_time_magnetization^4 / binsize
        cuts_mean += cuts / binsize
        push!(cut_counts, cuts)
        push!(cut_m2, integrated_magnetization2)
        push!(cut_m4, integrated_magnetization4)
    end

    return BinRecord(
        energy_per_site,
        m_time2,
        m_time4,
        m_equal2,
        m_equal4,
        cuts_mean,
        CutHistogramBin(cut_counts, cut_m2, cut_m4),
    )
end

function run_bins!(state::CWAState, nbins::Integer, binsize::Integer)::Vector{BinRecord}
    nbins > 0 || throw(ArgumentError("nbins must be positive"))
    binsize > 0 || throw(ArgumentError("binsize must be positive"))
    return [measure_bin!(state, binsize) for _ in 1:nbins]
end

function run_cwa(
    geometry::LatticeGeometry;
    J::Real = 1.0,
    h::Real,
    beta::Real,
    thermalization::Integer,
    sweeps::Integer,
    binsize::Integer,
    seed::Integer,
)
    thermalization >= 0 || throw(ArgumentError("thermalization must be nonnegative"))
    sweeps > 0 || throw(ArgumentError("sweeps must be positive"))
    binsize > 0 || throw(ArgumentError("binsize must be positive"))
    sweeps % binsize == 0 || throw(ArgumentError("sweeps must be divisible by binsize"))

    state = CWAState(geometry; J, h, beta, seed)
    thermalize!(state, thermalization)
    records = run_bins!(state, sweeps ÷ binsize, binsize)
    energy_bins = getfield.(records, :energy_per_site)
    m_time2_bins = getfield.(records, :m_time2)
    m_time4_bins = getfield.(records, :m_time4)
    m_equal2_bins = getfield.(records, :m_equal2)
    m_equal4_bins = getfield.(records, :m_equal4)
    cut_bins = getfield.(records, :cuts_mean)

    return (
        energy_per_site = binned_estimate(energy_bins),
        m_time2 = binned_estimate(m_time2_bins),
        m_time4 = binned_estimate(m_time4_bins),
        binder_time = binder_from_bins(m_time2_bins, m_time4_bins),
        m_equal2 = binned_estimate(m_equal2_bins),
        m_equal4 = binned_estimate(m_equal4_bins),
        binder_equal = binder_from_bins(m_equal2_bins, m_equal4_bins),
        mean_cuts = binned_estimate(cut_bins),
        bins = (
            energy_per_site = energy_bins,
            m_time2 = m_time2_bins,
            m_time4 = m_time4_bins,
            m_equal2 = m_equal2_bins,
            m_equal4 = m_equal4_bins,
            mean_cuts = cut_bins,
        ),
        final_state = state,
    )
end

function spin_at(line::Worldline, tau::Real)
    tau >= 0 || throw(ArgumentError("imaginary time must be nonnegative"))
    flips = searchsortedlast(line.cuts, tau)
    return iseven(flips) ? line.spin0 : -line.spin0
end

function integrated_spin(line::Worldline, beta::Real)
    beta > 0 || throw(ArgumentError("beta must be positive"))
    all(<(beta), line.cuts) || throw(ArgumentError("all cuts must lie below beta"))

    total = 0.0
    left = 0.0
    spin = line.spin0
    for cut in line.cuts
        total += spin * (cut - left)
        left = cut
        spin = -spin
    end
    total += spin * (beta - left)
    return total
end
