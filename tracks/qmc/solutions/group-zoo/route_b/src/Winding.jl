struct _LoopEdge
    id::Int
    target::Tuple{Int,Int,UInt8}
    du::Int
    dv::Int
    temporal::Bool
end

function _add_loop_edge!(adjacency, left, right, du::Int, dv::Int, id::Int; temporal::Bool)
    push!(get!(adjacency, left, _LoopEdge[]), _LoopEdge(id, right, du, dv, temporal))
    push!(get!(adjacency, right, _LoopEdge[]), _LoopEdge(id, left, -du, -dv, temporal))
    return id + 1
end

function _down_leg(state::WorldlineState, kink::Kink, site::Int)
    before = _spin_before(state, site, kink.tau)
    return (kink.id, site, UInt8(before == -1 ? 0 : 1))
end

function _periodic_midpoint(left::Float64, right::Float64, beta::Float64)
    distance = mod(right - left, beta)
    return mod(left + distance / 2, beta)
end

function _down_loop_graph(state::WorldlineState)
    adjacency = Dict{Tuple{Int,Int,UInt8},Vector{_LoopEdge}}()
    edge_id = 1

    for kink in sort!(collect(values(state.kinks)); by=kink -> kink.id)
        left, right = state.lattice.bonds[kink.bond]
        left_leg = _down_leg(state, kink, left)
        right_leg = _down_leg(state, kink, right)
        directed = _directed_for(state, left, kink.bond)
        edge_id = _add_loop_edge!(
            adjacency,
            left_leg,
            right_leg,
            directed.du,
            directed.dv,
            edge_id;
            temporal=false,
        )
    end

    for site in 1:state.lattice.nsites
        events = state.site_events[site]
        isempty(events) && continue
        for index in eachindex(events)
            current_id = events[index]
            next_id = events[mod1(index + 1, length(events))]
            current = state.kinks[current_id]
            following = state.kinks[next_id]
            midpoint = _periodic_midpoint(current.tau, following.tau, state.beta)
            spin_at(state, site, midpoint) == -1 || continue
            after_leg = (current_id, site, UInt8(1))
            before_leg = (next_id, site, UInt8(0))
            edge_id = _add_loop_edge!(
                adjacency,
                after_leg,
                before_leg,
                0,
                0,
                edge_id;
                temporal=true,
            )
        end
    end
    return adjacency
end

function _first_oriented_edge(node, edges::Vector{_LoopEdge})
    length(edges) == 2 || error("down-loop leg does not have degree two")
    side = node[3]
    preferred_temporal = side == UInt8(1)
    index = findfirst(edge -> edge.temporal == preferred_temporal, edges)
    index === nothing && error("down-loop leg has no forward-oriented edge")
    return edges[index]
end

function _trace_loop!(visited::Set{Int}, adjacency, start)
    current = start
    incoming_edge = 0
    total_u = 0
    total_v = 0
    first_step = true

    while true
        edges = adjacency[current]
        edge = if first_step
            _first_oriented_edge(current, edges)
        else
            candidates = filter(candidate -> candidate.id != incoming_edge, edges)
            only(candidates)
        end
        first_step = false
        push!(visited, edge.id)
        total_u += edge.du
        total_v += edge.dv
        incoming_edge = edge.id
        current = edge.target
        current == start && break
    end
    return total_u, total_v
end

function winding_vectors(state::WorldlineState)
    isempty(state.defects) || throw(ArgumentError("winding is defined only in the Z sector"))
    validate_state(state) || throw(ArgumentError("winding requires a valid worldline state"))
    adjacency = _down_loop_graph(state)
    all(length(edges) == 2 for edges in values(adjacency)) ||
        error("down-loop graph is not two-regular")

    windings = Tuple{Int,Int}[]
    visited = Set{Int}()
    for start in sort!(collect(keys(adjacency)))
        all(edge.id in visited for edge in adjacency[start]) && continue
        total_u, total_v = _trace_loop!(visited, adjacency, start)
        rem(total_u, state.lattice.L) == 0 ||
            error("noninteger primitive winding in direction one")
        rem(total_v, state.lattice.L) == 0 ||
            error("noninteger primitive winding in direction two")
        push!(windings, (div(total_u, state.lattice.L), div(total_v, state.lattice.L)))
    end

    for site in 1:state.lattice.nsites
        isempty(state.site_events[site]) || continue
        state.base_spins[site] == -1 && push!(windings, (0, 0))
    end
    sort!(windings)
    return windings
end

function wrapping_observables(state::WorldlineState)
    windings = winding_vectors(state)
    wrap_1 = Int(any(winding[1] != 0 for winding in windings))
    wrap_2 = Int(any(winding[2] != 0 for winding in windings))
    signed = (
        sum(winding[1] for winding in windings; init=0),
        sum(winding[2] for winding in windings; init=0),
    )
    absolute = (
        sum(abs(winding[1]) for winding in windings; init=0),
        sum(abs(winding[2]) for winding in windings; init=0),
    )
    return (
        I_wrap_1=wrap_1,
        I_wrap_2=wrap_2,
        I_wrap_any=Int(wrap_1 == 1 || wrap_2 == 1),
        R_down=(wrap_1 + wrap_2) / 2,
        signed_winding=signed,
        absolute_winding=absolute,
        loop_count=length(windings),
    )
end
