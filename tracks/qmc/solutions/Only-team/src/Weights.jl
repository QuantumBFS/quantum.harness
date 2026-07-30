@inline function tau_minus(tau::Int, LTrot::Int)::Int
    return tau == 1 ? LTrot : tau - 1
end

@inline function tau_plus(tau::Int, LTrot::Int)::Int
    return tau == LTrot ? 1 : tau + 1
end

function total_log_weight(
    spins::AbstractMatrix{<:Integer},
    lattice::Lattice,
    config::SimulationConfig,
)::Float64
    size(spins) == (lattice.N, config.LTrot) ||
        throw(DimensionMismatch("spins must have shape lattice.N × LTrot"))

    spatial_sum = 0
    temporal_sum = 0

    for tau in 1:config.LTrot
        for (site, neighbor) in lattice.bonds
            spatial_sum += spins[site, tau] * spins[neighbor, tau]
        end
        next_tau = tau_plus(tau, config.LTrot)
        for site in 1:lattice.N
            temporal_sum += spins[site, tau] * spins[site, next_tau]
        end
    end

    return -config.Dltau * config.J1 * spatial_sum -
           config.CpTau * temporal_sum
end

function local_terms(
    spins::AbstractMatrix{<:Integer},
    site::Int,
    tau::Int,
    lattice::Lattice,
    config::SimulationConfig,
)
    IsSpin = Int8(spins[site, tau])
    I1 = sum(neighbor -> spins[neighbor, tau], lattice.neighbors[site])
    I2 = 0
    I3 =
        spins[site, tau_minus(tau, config.LTrot)] +
        spins[site, tau_plus(tau, config.LTrot)]
    Rtp0 =
        -config.Dltau * (config.J1 * I1 + config.J2 * I2) -
        config.CpTau * I3
    return IsSpin, Rtp0
end
