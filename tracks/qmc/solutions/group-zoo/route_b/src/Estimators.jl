struct Measurement
    R_down::Union{Missing,Float64}
    I_wrap_1::Union{Missing,Int}
    I_wrap_2::Union{Missing,Int}
    I_wrap_any::Union{Missing,Int}
    signed_winding::Union{Missing,Tuple{Int,Int}}
    loop_count::Union{Missing,Int}
    kink_count::Int
    hopping_kinks::Int
    pairing_kinks::Int
    mz_rotated::Float64
    mx_original::Float64
    field_energy_per_site::Float64
    bond_energy_per_site::Float64
    total_energy_per_site::Float64
    m2::Float64
    m4::Float64
    in_green_sector::Bool
end

struct RawBin
    R_down::Float64
    I_wrap_1::Float64
    I_wrap_2::Float64
    I_wrap_any::Float64
    signed_winding_u::Float64
    signed_winding_v::Float64
    loop_count::Float64
    kink_count::Float64
    hopping_kinks::Float64
    pairing_kinks::Float64
    mz_rotated::Float64
    mx_original::Float64
    bond::Float64
    energy::Float64
    rotated_m2::Float64
    rotated_m4::Float64
    z_visits::Int
    g_visits::Int
end

mutable struct _BinAccumulator
    sums::Vector{Float64}
    z_visits::Int
    g_visits::Int
end

_BinAccumulator() = _BinAccumulator(zeros(16), 0, 0)

function _record_step!(accumulator::_BinAccumulator, state::WorldlineState; h::Real)
    if !isempty(state.defects)
        accumulator.g_visits += 1
        return accumulator
    end
    observation = measure(state; h=h)
    winding_u, winding_v = observation.signed_winding
    values = (
        observation.R_down,
        observation.I_wrap_1,
        observation.I_wrap_2,
        observation.I_wrap_any,
        winding_u,
        winding_v,
        observation.loop_count,
        observation.kink_count,
        observation.hopping_kinks,
        observation.pairing_kinks,
        observation.mz_rotated,
        observation.mx_original,
        -observation.bond_energy_per_site,
        observation.total_energy_per_site,
        observation.m2,
        observation.m4,
    )
    for index in eachindex(values)
        accumulator.sums[index] += values[index]
    end
    accumulator.z_visits += 1
    return accumulator
end

function _finish_bin(accumulator::_BinAccumulator)
    accumulator.z_visits > 0 || throw(ArgumentError("a raw bin requires a Z-sector visit"))
    means = accumulator.sums ./ accumulator.z_visits
    return RawBin(means..., accumulator.z_visits, accumulator.g_visits)
end

function _raw_bin_record(bin::RawBin)
    return (
        R_down=bin.R_down,
        I_wrap_1=bin.I_wrap_1,
        I_wrap_2=bin.I_wrap_2,
        I_wrap_any=bin.I_wrap_any,
        signed_winding_u=bin.signed_winding_u,
        signed_winding_v=bin.signed_winding_v,
        loop_count=bin.loop_count,
        kink_count=bin.kink_count,
        hopping_kinks=bin.hopping_kinks,
        pairing_kinks=bin.pairing_kinks,
        mz_rotated=bin.mz_rotated,
        mx_original=bin.mx_original,
        bond=bin.bond,
        energy=bin.energy,
        rotated_m2=bin.rotated_m2,
        rotated_m4=bin.rotated_m4,
        z_visits=bin.z_visits,
        g_visits=bin.g_visits,
    )
end

function _valid_raw_bin(bin::RawBin)
    bin.z_visits > 0 || return false
    bin.g_visits >= 0 || return false
    return all(isfinite, values(_raw_bin_record(bin)))
end

function _time_moments(state::WorldlineState)
    points = Float64[0.0, state.beta]
    for kink in values(state.kinks)
        push!(points, kink.tau)
    end
    for defect in state.defects
        push!(points, defect.tau)
    end
    sort!(unique!(points))
    total_m = 0.0
    total_m2 = 0.0
    total_m4 = 0.0
    for index in 1:(length(points) - 1)
        left, right = points[index], points[index + 1]
        midpoint = (left + right) / 2
        magnetization = sum(spin_at(state, site, midpoint) for site in 1:state.lattice.nsites) /
                        state.lattice.nsites
        duration = right - left
        total_m += duration * magnetization
        total_m2 += duration * magnetization^2
        total_m4 += duration * magnetization^4
    end
    return total_m / state.beta, total_m2 / state.beta, total_m4 / state.beta
end

function measure(state::WorldlineState; h::Real=0.0)
    validate_state(state) || throw(ArgumentError("cannot measure an invalid state"))
    field = _finite_float("h", h)
    mz, m2, m4 = _time_moments(state)
    hopping = count(kink.kind == HoppingKink for kink in values(state.kinks))
    pairing = count(kink.kind == PairingKink for kink in values(state.kinks))
    total_kinks = hopping + pairing
    bond_energy = -total_kinks / (state.beta * state.lattice.nsites)
    winding = isempty(state.defects) ? wrapping_observables(state) : nothing
    return Measurement(
        winding === nothing ? missing : winding.R_down,
        winding === nothing ? missing : winding.I_wrap_1,
        winding === nothing ? missing : winding.I_wrap_2,
        winding === nothing ? missing : winding.I_wrap_any,
        winding === nothing ? missing : winding.signed_winding,
        winding === nothing ? missing : winding.loop_count,
        total_kinks,
        hopping,
        pairing,
        mz,
        mz,
        -field * mz,
        bond_energy,
        -field * mz + bond_energy,
        m2,
        m4,
        !isempty(state.defects),
    )
end
