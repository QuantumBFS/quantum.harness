abstract type AbstractWormProposal end

struct WormProposal{T<:NamedTuple} <: AbstractWormProposal
    record::ProposalRecord
    data::T
end

struct IllegalProposal <: AbstractWormProposal
    family::ProposalFamily
    reason::Symbol
end

_masha(state::WorldlineState) = only(defect for defect in state.defects if defect.role == Masha)
_ira(state::WorldlineState) = only(defect for defect in state.defects if defect.role == Ira)

function _checked_delta(state::WorldlineState, delta::Real, window::Float64)
    displacement = _finite_float("delta", delta)
    displacement != 0 || throw(ArgumentError("delta must be nonzero"))
    abs(displacement) <= window / 2 ||
        throw(ArgumentError("delta lies outside the proposal window"))
    window <= state.beta ||
        throw(ArgumentError("proposal time window must not exceed beta"))
    return displacement
end

function _arc_from_delta(state::WorldlineState, tau::Float64, delta::Float64)
    endpoint = mod(tau + delta, state.beta)
    endpoint != tau || throw(ArgumentError("delta maps to the same periodic time"))
    return delta > 0 ? (tau, endpoint, endpoint) : (endpoint, tau, endpoint)
end

function _nonwrapping_spin_time(
    state::WorldlineState,
    site::Int,
    start::Float64,
    stop::Float64,
)
    start == stop && return 0.0
    points = Float64[start, stop]
    append!(points, (
        state.kinks[id].tau for id in state.site_events[site]
        if start < state.kinks[id].tau < stop
    ))
    append!(points, (
        defect.tau for defect in state.defects
        if defect.site == site && start < defect.tau < stop
    ))
    sort!(unique!(points))
    total = 0.0
    for index in 1:(length(points) - 1)
        left, right = points[index], points[index + 1]
        midpoint = (left + right) / 2
        total += spin_at(state, site, midpoint) * (right - left)
    end
    return total
end

function _segment_spin_time(
    state::WorldlineState,
    site::Int,
    start::Float64,
    stop::Float64,
)
    if start < stop
        return _nonwrapping_spin_time(state, site, start, stop)
    end
    return _nonwrapping_spin_time(state, site, start, state.beta) +
           _nonwrapping_spin_time(state, site, 0.0, stop)
end

function _directed_for(state::WorldlineState, site::Int, bond::Int)
    edge = only(edge for edge in state.lattice.directed if edge.bond == bond && edge.src == site)
    return edge
end

function _periodic_signed_delta(from::Float64, to::Float64, beta::Float64)
    forward = mod(to - from, beta)
    return forward <= beta / 2 ? forward : forward - beta
end

function _window_kinks(
    state::WorldlineState,
    bond::Int,
    center::Float64,
    window::Float64,
)
    half = window / 2
    return [
        id for id in state.bond_events[bond]
        if begin
            delta = _periodic_signed_delta(center, state.kinks[id].tau, state.beta)
            -half <= delta < half
        end
    ]
end

function propose_create(
    state::WorldlineState,
    parameters::WormParameters;
    J::Real,
    h::Real,
    site::Integer,
    tau_i::Real,
    delta::Real,
    uniform::Real,
)
    isempty(state.defects) || throw(ArgumentError("create requires the Z sector"))
    checked_site = _valid_site(state, site)
    checked_tau = _valid_tau(state, tau_i)
    displacement = _checked_delta(state, delta, parameters.tau_a)
    start, stop, tau_m = _arc_from_delta(state, checked_tau, displacement)
    (_site_has_event_at(state, checked_site, checked_tau) ||
     _site_has_event_at(state, checked_site, tau_m)) &&
        return IllegalProposal(CreateDefects, :event_collision)

    delta_spin_time = -2 * _segment_spin_time(state, checked_site, start, stop)
    weight = log_ratio(
        J;
        delta_kinks=0,
        h=h,
        delta_spin_time=delta_spin_time,
    )
    volume = state.beta * state.lattice.nsites
    record = ProposalRecord(
        CreateDefects;
        direction=Int(sign(displacement)),
        directed_bond=0,
        log_forward_density=-log(volume) - log(parameters.tau_a),
        log_reverse_density=log(parameters.A_annihilate),
        log_jacobian=-log(volume),
        log_weight_ratio=weight,
        uniform=uniform,
    )
    return WormProposal(record, (
        site=checked_site,
        tau_i=checked_tau,
        tau_m=tau_m,
        start=start,
        stop=stop,
    ))
end

function propose_annihilate(
    state::WorldlineState,
    parameters::WormParameters;
    J::Real,
    h::Real,
    uniform::Real,
)
    length(state.defects) == 2 ||
        throw(ArgumentError("annihilate requires the G sector"))
    ira, masha = _ira(state), _masha(state)
    ira.site == masha.site || return IllegalProposal(AnnihilateDefects, :different_sites)
    delta = _periodic_signed_delta(ira.tau, masha.tau, state.beta)
    abs(delta) <= parameters.tau_a / 2 ||
        return IllegalProposal(AnnihilateDefects, :outside_time_window)
    start, stop = delta > 0 ? (ira.tau, masha.tau) : (masha.tau, ira.tau)
    delta_spin_time = -2 * _segment_spin_time(state, ira.site, start, stop)
    weight = log_ratio(
        J;
        delta_kinks=0,
        h=h,
        delta_spin_time=delta_spin_time,
    )
    volume = state.beta * state.lattice.nsites
    record = ProposalRecord(
        AnnihilateDefects;
        direction=-Int(sign(delta)),
        directed_bond=0,
        log_forward_density=log(parameters.A_annihilate),
        log_reverse_density=-log(volume) - log(parameters.tau_a),
        log_jacobian=log(volume),
        log_weight_ratio=weight,
        uniform=uniform,
    )
    return WormProposal(record, (site=ira.site, start=start, stop=stop))
end

function propose_move(
    state::WorldlineState,
    parameters::WormParameters;
    J::Real,
    h::Real,
    delta::Real,
    uniform::Real,
)
    length(state.defects) == 2 || throw(ArgumentError("move requires the G sector"))
    masha = _masha(state)
    displacement = _checked_delta(state, delta, parameters.tau_b)
    start, stop, new_tau = _arc_from_delta(state, masha.tau, displacement)
    _site_has_event_at(state, masha.site, new_tau) &&
        return IllegalProposal(MoveDefect, :event_collision)
    delta_spin_time = -2 * _segment_spin_time(state, masha.site, start, stop)
    weight = log_ratio(
        J;
        delta_kinks=0,
        h=h,
        delta_spin_time=delta_spin_time,
    )
    record = ProposalRecord(
        MoveDefect;
        direction=Int(sign(displacement)),
        directed_bond=0,
        log_forward_density=-log(parameters.tau_b),
        log_reverse_density=-log(parameters.tau_b),
        log_jacobian=0.0,
        log_weight_ratio=weight,
        uniform=uniform,
    )
    return WormProposal(record, (
        site=masha.site,
        old_tau=masha.tau,
        new_tau=new_tau,
        start=start,
        stop=stop,
    ))
end

function propose_insert(
    state::WorldlineState,
    parameters::WormParameters;
    J::Real,
    h::Real,
    bond::Integer,
    delta::Real,
    uniform::Real,
)
    length(state.defects) == 2 || throw(ArgumentError("insert requires the G sector"))
    masha = _masha(state)
    bond in state.lattice.incident[masha.site] ||
        throw(ArgumentError("bond is not incident to Masha"))
    checked_bond = Int(bond)
    edge = _directed_for(state, masha.site, checked_bond)
    displacement = _checked_delta(state, delta, parameters.tau_c)
    start, stop, kink_tau = _arc_from_delta(state, masha.tau, displacement)
    (_site_has_event_at(state, edge.src, kink_tau) ||
     _site_has_event_at(state, edge.dst, kink_tau)) &&
        return IllegalProposal(InsertKink, :event_collision)
    nk = length(_window_kinks(state, checked_bond, masha.tau, parameters.tau_c))
    delta_spin_time = -2 * (
        _segment_spin_time(state, edge.src, start, stop) +
        _segment_spin_time(state, edge.dst, start, stop)
    )
    weight = log_ratio(
        J;
        delta_kinks=1,
        h=h,
        delta_spin_time=delta_spin_time,
    )
    degree = length(state.lattice.incident[masha.site])
    record = ProposalRecord(
        InsertKink;
        direction=Int(sign(displacement)),
        directed_bond=findfirst(==(edge), state.lattice.directed),
        log_forward_density=-log(degree) - log(parameters.tau_c),
        log_reverse_density=-log(degree) - log(nk + 1),
        log_jacobian=0.0,
        log_weight_ratio=weight,
        uniform=uniform,
    )
    return WormProposal(record, (
        old_site=edge.src,
        new_site=edge.dst,
        masha_tau=masha.tau,
        bond=checked_bond,
        kink_tau=kink_tau,
        start=start,
        stop=stop,
    ))
end

function propose_delete(
    state::WorldlineState,
    parameters::WormParameters;
    J::Real,
    h::Real,
    bond::Integer,
    kink_id::Union{Nothing,Integer},
    uniform::Real,
)
    length(state.defects) == 2 || throw(ArgumentError("delete requires the G sector"))
    masha = _masha(state)
    bond in state.lattice.incident[masha.site] ||
        throw(ArgumentError("bond is not incident to Masha"))
    checked_bond = Int(bond)
    edge = _directed_for(state, masha.site, checked_bond)
    eligible = _window_kinks(state, checked_bond, masha.tau, parameters.tau_c)
    isempty(eligible) && return IllegalProposal(DeleteKink, :no_eligible_kink)
    kink_id === nothing && return IllegalProposal(DeleteKink, :no_selected_kink)
    Int(kink_id) in eligible || throw(ArgumentError("kink is not eligible for deletion"))
    checked_id = Int(kink_id)
    kink_tau = state.kinks[checked_id].tau
    delta = _periodic_signed_delta(masha.tau, kink_tau, state.beta)
    start, stop = delta > 0 ? (masha.tau, kink_tau) : (kink_tau, masha.tau)
    delta_spin_time = -2 * (
        _segment_spin_time(state, edge.src, start, stop) +
        _segment_spin_time(state, edge.dst, start, stop)
    )
    weight = log_ratio(
        J;
        delta_kinks=-1,
        h=h,
        delta_spin_time=delta_spin_time,
    )
    degree = length(state.lattice.incident[masha.site])
    nk = length(eligible)
    record = ProposalRecord(
        DeleteKink;
        direction=-Int(sign(delta)),
        directed_bond=findfirst(==(edge), state.lattice.directed),
        log_forward_density=-log(degree) - log(nk),
        log_reverse_density=-log(degree) - log(parameters.tau_c),
        log_jacobian=0.0,
        log_weight_ratio=weight,
        uniform=uniform,
    )
    return WormProposal(record, (
        old_site=edge.src,
        new_site=edge.dst,
        masha_tau=masha.tau,
        bond=checked_bond,
        kink_id=checked_id,
        start=start,
        stop=stop,
    ))
end

function _replace_masha!(state::WorldlineState, site::Int, tau::Float64)
    index = findfirst(defect -> defect.role == Masha, state.defects)
    index === nothing && error("Masha is absent")
    old = state.defects[index]
    for id in state.site_events[site]
        state.kinks[id].tau == tau && throw(ArgumentError("Masha collides with a kink"))
    end
    for (other_index, defect) in pairs(state.defects)
        other_index == index && continue
        (defect.site, defect.tau) == (site, tau) &&
            throw(ArgumentError("Masha collides with Ira"))
    end
    state.defects[index] = Defect(Masha, site, tau)
    return old
end

function _restore_state!(state::WorldlineState, backup::WorldlineState)
    state.lattice = backup.lattice
    state.beta = backup.beta
    state.base_spins = backup.base_spins
    state.kinks = backup.kinks
    state.site_events = backup.site_events
    state.bond_events = backup.bond_events
    state.defects = backup.defects
    state.next_event_id = backup.next_event_id
    return state
end

function _apply_accepted!(state::WorldlineState, proposal::WormProposal)
    data = proposal.data
    family = proposal.record.family
    if family == CreateDefects
        set_defects!(
            state,
            Defect(Ira, data.site, data.tau_i),
            Defect(Masha, data.site, data.tau_m),
        )
        flip_periodic_segment!(state, data.site, data.start, data.stop)
    elseif family == AnnihilateDefects
        flip_periodic_segment!(state, data.site, data.start, data.stop)
        clear_defects!(state)
    elseif family == MoveDefect
        _replace_masha!(state, data.site, data.new_tau)
        flip_periodic_segment!(state, data.site, data.start, data.stop)
    elseif family == InsertKink
        _replace_masha!(state, data.new_site, data.masha_tau)
        insert_kink!(state, data.bond, data.kink_tau)
        flip_periodic_segment!(state, data.old_site, data.start, data.stop)
        flip_periodic_segment!(state, data.new_site, data.start, data.stop)
    elseif family == DeleteKink
        flip_periodic_segment!(state, data.old_site, data.start, data.stop)
        flip_periodic_segment!(state, data.new_site, data.start, data.stop)
        delete_kink!(state, data.kink_id)
        _replace_masha!(state, data.new_site, data.masha_tau)
    else
        error("unsupported proposal family")
    end
    return state
end

apply_proposal!(state::WorldlineState, ::IllegalProposal) = state

function apply_proposal!(state::WorldlineState, proposal::WormProposal)
    proposal.record.accepted || return state
    backup = deepcopy(state)
    try
        _apply_accepted!(state, proposal)
        validate_state(state) || error("accepted proposal violated worldline invariants")
    catch
        _restore_state!(state, backup)
        rethrow()
    end
    return state
end
