@enum KinkKind::UInt8 begin
    HoppingKink = 1
    PairingKink = 2
end

@enum DefectRole::UInt8 begin
    Ira = 1
    Masha = 2
end

struct Kink
    id::Int
    bond::Int
    tau::Float64
    kind::KinkKind
end

struct Defect
    role::DefectRole
    site::Int
    tau::Float64
end

mutable struct WorldlineState
    lattice::Lattice
    beta::Float64
    base_spins::Vector{Int8}
    kinks::Dict{Int,Kink}
    site_events::Vector{Vector{Int}}
    bond_events::Vector{Vector{Int}}
    defects::Vector{Defect}
    next_event_id::Int
end

function WorldlineState(
    lattice::Lattice,
    beta::Real;
    initial_spins::AbstractVector{<:Integer},
)
    inverse_temperature = _finite_float("beta", beta)
    inverse_temperature > 0 || throw(ArgumentError("beta must be positive"))
    length(initial_spins) == lattice.nsites ||
        throw(ArgumentError("initial_spins length must equal lattice.nsites"))
    all(spin == 1 || spin == -1 for spin in initial_spins) ||
        throw(ArgumentError("initial spins must be +1 or -1"))

    return WorldlineState(
        lattice,
        inverse_temperature,
        Int8.(initial_spins),
        Dict{Int,Kink}(),
        [Int[] for _ in 1:lattice.nsites],
        [Int[] for _ in eachindex(lattice.bonds)],
        Defect[],
        1,
    )
end

function _valid_tau(state::WorldlineState, tau::Real)
    time = _finite_float("tau", tau)
    0 <= time < state.beta ||
        throw(ArgumentError("tau must satisfy 0 <= tau < beta"))
    return time
end

function _valid_site(state::WorldlineState, site::Integer)
    1 <= site <= state.lattice.nsites ||
        throw(ArgumentError("site index is out of range"))
    return Int(site)
end

function _spin_at(state::WorldlineState, site::Int, tau::Float64, include_tau::Bool)
    spin = state.base_spins[site]
    for id in state.site_events[site]
        event_tau = state.kinks[id].tau
        (event_tau < tau || (include_tau && event_tau == tau)) && (spin = -spin)
    end
    for defect in state.defects
        defect.site == site || continue
        (defect.tau < tau || (include_tau && defect.tau == tau)) && (spin = -spin)
    end
    return spin
end

function spin_at(state::WorldlineState, site::Integer, tau::Real)
    checked_site = _valid_site(state, site)
    checked_tau = _valid_tau(state, tau)
    return _spin_at(state, checked_site, checked_tau, true)
end

_spin_before(state::WorldlineState, site::Int, tau::Float64) =
    _spin_at(state, site, tau, false)

_kind_from_spins(left::Int8, right::Int8) =
    left == right ? PairingKink : HoppingKink

function _site_has_event_at(state::WorldlineState, site::Int, tau::Float64)
    any(state.kinks[id].tau == tau for id in state.site_events[site]) && return true
    return any(defect.site == site && defect.tau == tau for defect in state.defects)
end

function _sort_event_indexes!(state::WorldlineState, sites, bond::Int)
    for site in sites
        sort!(state.site_events[site]; by=id -> (state.kinks[id].tau, id))
    end
    sort!(state.bond_events[bond]; by=id -> (state.kinks[id].tau, id))
    return state
end

function insert_kink!(state::WorldlineState, bond::Integer, tau::Real)
    1 <= bond <= length(state.lattice.bonds) ||
        throw(ArgumentError("bond index is out of range"))
    checked_bond = Int(bond)
    checked_tau = _valid_tau(state, tau)
    left, right = state.lattice.bonds[checked_bond]
    (_site_has_event_at(state, left, checked_tau) ||
     _site_has_event_at(state, right, checked_tau)) &&
        throw(ArgumentError("a worldline event already exists at tau"))

    kind = _kind_from_spins(
        _spin_before(state, left, checked_tau),
        _spin_before(state, right, checked_tau),
    )
    id = state.next_event_id
    state.next_event_id += 1
    state.kinks[id] = Kink(id, checked_bond, checked_tau, kind)
    push!(state.site_events[left], id)
    push!(state.site_events[right], id)
    push!(state.bond_events[checked_bond], id)
    _sort_event_indexes!(state, (left, right), checked_bond)
    return id
end

function delete_kink!(state::WorldlineState, id::Integer)
    haskey(state.kinks, id) || throw(ArgumentError("unknown kink id"))
    checked_id = Int(id)
    kink = state.kinks[checked_id]
    left, right = state.lattice.bonds[kink.bond]
    filter!(!=(checked_id), state.site_events[left])
    filter!(!=(checked_id), state.site_events[right])
    filter!(!=(checked_id), state.bond_events[kink.bond])
    delete!(state.kinks, checked_id)
    return kink
end

function kink_kind(state::WorldlineState, id::Integer)
    haskey(state.kinks, id) || throw(ArgumentError("unknown kink id"))
    return state.kinks[Int(id)].kind
end

function set_defects!(state::WorldlineState, ira::Defect, masha::Defect)
    isempty(state.defects) || throw(ArgumentError("state already has defects"))
    ira.role == Ira || throw(ArgumentError("first defect must be Ira"))
    masha.role == Masha || throw(ArgumentError("second defect must be Masha"))
    for defect in (ira, masha)
        _valid_site(state, defect.site)
        _valid_tau(state, defect.tau)
        _site_has_event_at(state, defect.site, defect.tau) &&
            throw(ArgumentError("a worldline event already exists at defect tau"))
    end
    (ira.site, ira.tau) == (masha.site, masha.tau) &&
        throw(ArgumentError("defects must occupy distinct spacetime points"))
    append!(state.defects, (ira, masha))
    return state
end

function clear_defects!(state::WorldlineState)
    length(state.defects) == 2 || throw(ArgumentError("state does not have two defects"))
    empty!(state.defects)
    return state
end

function _in_forward_interval(tau::Float64, start::Float64, stop::Float64)
    return start < stop ? start <= tau < stop : (tau >= start || tau < stop)
end

function flip_periodic_segment!(
    state::WorldlineState,
    site::Integer,
    start::Real,
    stop::Real,
)
    checked_site = _valid_site(state, site)
    checked_start = _valid_tau(state, start)
    checked_stop = _valid_tau(state, stop)
    checked_start != checked_stop ||
        throw(ArgumentError("segment endpoints must be distinct"))

    checked_stop < checked_start &&
        (state.base_spins[checked_site] = -state.base_spins[checked_site])
    for id in state.site_events[checked_site]
        kink = state.kinks[id]
        _in_forward_interval(kink.tau, checked_start, checked_stop) || continue
        replacement = kink.kind == HoppingKink ? PairingKink : HoppingKink
        state.kinks[id] = Kink(kink.id, kink.bond, kink.tau, replacement)
    end
    return state
end

function _valid_defects(state::WorldlineState)
    isempty(state.defects) && return true
    length(state.defects) == 2 || return false
    Set(defect.role for defect in state.defects) == Set((Ira, Masha)) || return false
    for defect in state.defects
        1 <= defect.site <= state.lattice.nsites || return false
        isfinite(defect.tau) && 0 <= defect.tau < state.beta || return false
    end
    return (state.defects[1].site, state.defects[1].tau) !=
           (state.defects[2].site, state.defects[2].tau)
end

function _valid_event_indexes(state::WorldlineState)
    length(state.site_events) == state.lattice.nsites || return false
    length(state.bond_events) == length(state.lattice.bonds) || return false
    all(id < state.next_event_id for id in keys(state.kinks)) || return false

    for (id, kink) in state.kinks
        id == kink.id || return false
        1 <= kink.bond <= length(state.lattice.bonds) || return false
        isfinite(kink.tau) && 0 <= kink.tau < state.beta || return false
        left, right = state.lattice.bonds[kink.bond]
        count(==(id), state.site_events[left]) == 1 || return false
        count(==(id), state.site_events[right]) == 1 || return false
        count(==(id), state.bond_events[kink.bond]) == 1 || return false
    end

    for site in 1:state.lattice.nsites
        ids = state.site_events[site]
        all(haskey(state.kinks, id) for id in ids) || return false
        issorted(ids; by=id -> (state.kinks[id].tau, id)) || return false
        length(unique(state.kinks[id].tau for id in ids)) == length(ids) || return false
        for id in ids
            left, right = state.lattice.bonds[state.kinks[id].bond]
            site == left || site == right || return false
        end
    end

    for bond in eachindex(state.lattice.bonds)
        ids = state.bond_events[bond]
        all(haskey(state.kinks, id) && state.kinks[id].bond == bond for id in ids) ||
            return false
        issorted(ids; by=id -> (state.kinks[id].tau, id)) || return false
    end
    return true
end

function validate_state(state::WorldlineState)
    isfinite(state.beta) && state.beta > 0 || return false
    length(state.base_spins) == state.lattice.nsites || return false
    all(spin == 1 || spin == -1 for spin in state.base_spins) || return false
    _valid_defects(state) || return false
    _valid_event_indexes(state) || return false

    for site in 1:state.lattice.nsites
        defect_count = count(defect.site == site for defect in state.defects)
        iseven(length(state.site_events[site]) + defect_count) || return false
        times = Float64[state.kinks[id].tau for id in state.site_events[site]]
        append!(times, (defect.tau for defect in state.defects if defect.site == site))
        length(unique(times)) == length(times) || return false
    end

    for kink in values(state.kinks)
        left, right = state.lattice.bonds[kink.bond]
        expected = _kind_from_spins(
            _spin_before(state, left, kink.tau),
            _spin_before(state, right, kink.tau),
        )
        kink.kind == expected || return false
    end
    return true
end
