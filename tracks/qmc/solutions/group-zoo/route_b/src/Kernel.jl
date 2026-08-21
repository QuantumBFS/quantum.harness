mutable struct WormKernel
    state::WorldlineState
    rng::CounterRNG
    J::Float64
    h::Float64
    parameters::WormParameters
    proposed::Dict{ProposalFamily,Int}
    accepted::Dict{ProposalFamily,Int}
    illegal::Dict{ProposalFamily,Int}
end

function WormKernel(
    state::WorldlineState,
    rng::CounterRNG,
    J::Real,
    h::Real,
    parameters::WormParameters,
)
    coupling = _positive_coupling(J)
    field = _finite_float("h", h)
    maximum((parameters.tau_a, parameters.tau_b, parameters.tau_c)) <= state.beta ||
        throw(ArgumentError("worm proposal windows must not exceed beta"))
    return WormKernel(
        state,
        rng,
        coupling,
        field,
        parameters,
        Dict(family => 0 for family in instances(ProposalFamily)),
        Dict(family => 0 for family in instances(ProposalFamily)),
        Dict(family => 0 for family in instances(ProposalFamily)),
    )
end

function select_family(
    in_green_sector::Bool,
    uniform::Real,
    parameters::WormParameters,
)
    draw = _finite_float("uniform", uniform)
    0 <= draw < 1 || throw(ArgumentError("uniform must satisfy 0 <= u < 1"))
    in_green_sector || return CreateDefects
    draw < parameters.A_annihilate && return AnnihilateDefects
    draw < parameters.A_annihilate + parameters.A_move && return MoveDefect
    draw < parameters.A_annihilate + parameters.A_move + parameters.A_kink &&
        return InsertKink
    return DeleteKink
end

function _random_delta(rng::CounterRNG, window::Float64)
    while true
        delta = window * (rand_float!(rng) - 0.5)
        delta != 0 && return delta
    end
end

function _random_proposal(kernel::WormKernel, family::ProposalFamily)
    state = kernel.state
    parameters = kernel.parameters
    acceptance_draw = rand_float!(kernel.rng)
    if family == CreateDefects
        return propose_create(
            state,
            parameters;
            J=kernel.J,
            h=kernel.h,
            site=rand_int!(kernel.rng, state.lattice.nsites),
            tau_i=state.beta * rand_float!(kernel.rng),
            delta=_random_delta(kernel.rng, parameters.tau_a),
            uniform=acceptance_draw,
        )
    elseif family == AnnihilateDefects
        return propose_annihilate(
            state,
            parameters;
            J=kernel.J,
            h=kernel.h,
            uniform=acceptance_draw,
        )
    elseif family == MoveDefect
        return propose_move(
            state,
            parameters;
            J=kernel.J,
            h=kernel.h,
            delta=_random_delta(kernel.rng, parameters.tau_b),
            uniform=acceptance_draw,
        )
    end

    masha = _masha(state)
    incident = state.lattice.incident[masha.site]
    bond = incident[rand_int!(kernel.rng, length(incident))]
    if family == InsertKink
        return propose_insert(
            state,
            parameters;
            J=kernel.J,
            h=kernel.h,
            bond=bond,
            delta=_random_delta(kernel.rng, parameters.tau_c),
            uniform=acceptance_draw,
        )
    end

    eligible = _window_kinks(state, bond, masha.tau, parameters.tau_c)
    selected = isempty(eligible) ? nothing : eligible[rand_int!(kernel.rng, length(eligible))]
    return propose_delete(
        state,
        parameters;
        J=kernel.J,
        h=kernel.h,
        bond=bond,
        kink_id=selected,
        uniform=acceptance_draw,
    )
end

function step!(kernel::WormKernel; debug::Bool=false)
    in_green_sector = !isempty(kernel.state.defects)
    family = select_family(in_green_sector, rand_float!(kernel.rng), kernel.parameters)
    kernel.proposed[family] += 1
    proposal = _random_proposal(kernel, family)
    if proposal isa IllegalProposal
        kernel.illegal[family] += 1
    elseif proposal.record.accepted
        kernel.accepted[family] += 1
    end
    apply_proposal!(kernel.state, proposal)
    debug && !validate_state(kernel.state) &&
        error("worm kernel violated state invariants")
    return proposal
end
