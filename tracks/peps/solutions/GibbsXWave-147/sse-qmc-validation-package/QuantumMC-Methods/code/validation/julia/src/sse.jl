const IDENTITY = UInt8(0)
const BOND_DIAGONAL = UInt8(1)
const SITE_DIAGONAL = UInt8(2)
const SITE_FLIP = UInt8(3)

struct SSEOperator
    kind::UInt8
    target::Int
end

SSEOperator() = SSEOperator(IDENTITY, 0)

mutable struct SSEState
    spins::Vector{Int8}
    operators::Vector{SSEOperator}
    n::Int
    max_n_observed::Int
    cutoff_touched::Bool
end

"""
    initialize_sse(model, beta, rng; cutoff=nothing)

Create a random σᶻ state and an identity operator string. The automatic cutoff
is deliberately generous; it may still be grown during warmup.
"""
function initialize_sse(model::SquareLatticeTFIM, beta::Real,
                        rng::AbstractRNG=Random.default_rng();
                        cutoff::Union{Nothing,Integer}=nothing)
    beta > 0 || throw(ArgumentError("SSE requires beta > 0"))
    N = nsites(model)
    scale = Float64(beta) * (2model.J * nbonds(model) + model.h * N)
    M = isnothing(cutoff) ? max(16, ceil(Int, 1.5scale + 16)) : Int(cutoff)
    M > 0 || throw(ArgumentError("cutoff must be positive"))
    spins = Int8[rand(rng, Bool) ? 1 : -1 for _ in 1:N]
    return SSEState(spins, fill(SSEOperator(), M), 0, 0, false)
end

function grow_cutoff!(state::SSEState; factor::Real=4 / 3, margin::Integer=16)
    target = max(length(state.operators) + Int(margin),
                 ceil(Int, factor * max(state.n, 1)) + Int(margin))
    append!(state.operators, fill(SSEOperator(), target - length(state.operators)))
    return state
end

@inline function _bond_weight(model::SquareLatticeTFIM,
                              spins::Vector{Int8}, bond::Int)
    i, j = model.bonds[bond]
    return spins[i] == spins[j] ? 2model.J : 0.0
end

"""
    diagonal_update!(state, model, beta, rng)

Uniform-proposal fixed-length SSE insertion/removal sweep. Flip operators only
propagate the basis state during this pass.
"""
function diagonal_update!(state::SSEState, model::SquareLatticeTFIM,
                          beta::Real, rng::AbstractRNG=Random.default_rng())
    beta > 0 || throw(ArgumentError("SSE requires beta > 0"))
    propagated = copy(state.spins)
    Nd = nbonds(model) + nsites(model)
    M = length(state.operators)

    for p in eachindex(state.operators)
        operator = state.operators[p]

        if operator.kind == IDENTITY
            if state.n == M
                # Reaching M even transiently means the fixed-length cutoff
                # constrained this update. Record it at the event, not only at
                # the end of the sweep.
                state.cutoff_touched = true
                continue
            end
            candidate = rand(rng, 1:Nd)
            if candidate <= nbonds(model)
                weight = _bond_weight(model, propagated, candidate)
                proposed = SSEOperator(BOND_DIAGONAL, candidate)
            else
                site = candidate - nbonds(model)
                weight = model.h
                proposed = SSEOperator(SITE_DIAGONAL, site)
            end

            if weight > 0
                probability = min(1.0, Float64(beta) * Nd * weight / (M - state.n))
                if rand(rng) < probability
                    state.operators[p] = proposed
                    state.n += 1
                    state.max_n_observed =
                        max(state.max_n_observed, state.n)
                    state.cutoff_touched |= state.n == M
                end
            end
        elseif operator.kind == BOND_DIAGONAL
            weight = _bond_weight(model, propagated, operator.target)
            weight > 0 ||
                error("invalid zero-weight bond vertex at operator position $p")
            probability = min(1.0, (M - state.n + 1) /
                                     (Float64(beta) * Nd * weight))
            if rand(rng) < probability
                state.operators[p] = SSEOperator()
                state.n -= 1
            end
        elseif operator.kind == SITE_DIAGONAL
            model.h > 0 || error("site operator present at h=0")
            probability = min(1.0, (M - state.n + 1) /
                                     (Float64(beta) * Nd * model.h))
            if rand(rng) < probability
                state.operators[p] = SSEOperator()
                state.n -= 1
            end
        elseif operator.kind == SITE_FLIP
            propagated[operator.target] *= -1
        else
            error("unknown SSE operator kind $(operator.kind)")
        end
    end

    propagated == state.spins ||
        error("operator string violates imaginary-time periodicity")
    state.max_n_observed = max(state.max_n_observed, state.n)
    state.cutoff_touched |= state.n == M
    return state
end

mutable struct _DisjointSet
    parent::Vector{Int}
    rank::Vector{UInt8}
end

_DisjointSet() = _DisjointSet(Int[], UInt8[])

function _new_element!(set::_DisjointSet)
    index = length(set.parent) + 1
    push!(set.parent, index)
    push!(set.rank, 0)
    return index
end

function _find_root!(set::_DisjointSet, element::Int)
    root = element
    while set.parent[root] != root
        root = set.parent[root]
    end
    while set.parent[element] != element
        next = set.parent[element]
        set.parent[element] = root
        element = next
    end
    return root
end

function _union!(set::_DisjointSet, left::Int, right::Int)
    root_left = _find_root!(set, left)
    root_right = _find_root!(set, right)
    root_left == root_right && return root_left

    if set.rank[root_left] < set.rank[root_right]
        root_left, root_right = root_right, root_left
    end
    set.parent[root_right] = root_left
    if set.rank[root_left] == set.rank[root_right]
        set.rank[root_left] += 1
    end
    return root_left
end

"""
    quantum_cluster_update!(state, model, rng)

All-cluster Sandvik update. Temporal links and the four legs of each bond
vertex define connected components; every component is flipped with
probability one half.
"""
function quantum_cluster_update!(state::SSEState, model::SquareLatticeTFIM,
                                 rng::AbstractRNG=Random.default_rng())
    M = length(state.operators)
    N = nsites(model)
    set = _DisjointSet()
    first_lower = zeros(Int, N)
    last_upper = zeros(Int, N)
    lower1 = zeros(Int, M)
    upper1 = zeros(Int, M)
    lower2 = zeros(Int, M)
    upper2 = zeros(Int, M)

    function attach_worldline!(site::Int, lower::Int, upper::Int)
        if iszero(first_lower[site])
            first_lower[site] = lower
        else
            _union!(set, last_upper[site], lower)
        end
        last_upper[site] = upper
        return nothing
    end

    for p in eachindex(state.operators)
        operator = state.operators[p]
        operator.kind == IDENTITY && continue

        if operator.kind == BOND_DIAGONAL
            i, j = model.bonds[operator.target]
            legs = ntuple(_ -> _new_element!(set), 4)
            lower1[p], lower2[p], upper1[p], upper2[p] = legs
            attach_worldline!(i, lower1[p], upper1[p])
            attach_worldline!(j, lower2[p], upper2[p])
            _union!(set, lower1[p], lower2[p])
            _union!(set, lower1[p], upper1[p])
            _union!(set, lower1[p], upper2[p])
        elseif operator.kind == SITE_DIAGONAL || operator.kind == SITE_FLIP
            lower1[p] = _new_element!(set)
            upper1[p] = _new_element!(set)
            attach_worldline!(operator.target, lower1[p], upper1[p])
            # Deliberately no internal union: a cluster branch terminates at a
            # diagonal/flip site vertex.
        else
            error("unknown SSE operator kind $(operator.kind)")
        end
    end

    for site in 1:N
        if !iszero(first_lower[site])
            _union!(set, last_upper[site], first_lower[site])
        end
    end

    root_flip = fill(UInt8(2), length(set.parent))
    for leg in eachindex(set.parent)
        root = _find_root!(set, leg)
        if root_flip[root] == 2
            root_flip[root] = rand(rng, Bool) ? UInt8(1) : UInt8(0)
        end
    end

    flipped(leg::Int) = root_flip[_find_root!(set, leg)] == 1

    for p in eachindex(state.operators)
        operator = state.operators[p]
        if operator.kind == SITE_DIAGONAL || operator.kind == SITE_FLIP
            if flipped(lower1[p]) ⊻ flipped(upper1[p])
                new_kind = operator.kind == SITE_DIAGONAL ? SITE_FLIP : SITE_DIAGONAL
                state.operators[p] = SSEOperator(new_kind, operator.target)
            end
        end
    end

    for site in 1:N
        if iszero(first_lower[site])
            rand(rng, Bool) && (state.spins[site] *= -1)
        elseif flipped(first_lower[site])
            state.spins[site] *= -1
        end
    end

    return state
end

function sweep!(state::SSEState, model::SquareLatticeTFIM, beta::Real,
                rng::AbstractRNG=Random.default_rng())
    diagonal_update!(state, model, beta, rng)
    quantum_cluster_update!(state, model, rng)
    return state
end

"""
    validate_configuration(state, model)

Throw on any mismatch in expansion order, local matrix-element constraint, or
imaginary-time periodicity. Return `true` otherwise.
"""
function validate_configuration(state::SSEState, model::SquareLatticeTFIM)
    count(operator -> operator.kind != IDENTITY, state.operators) == state.n ||
        error("stored expansion order does not match operator string")

    propagated = copy(state.spins)
    for (p, operator) in pairs(state.operators)
        if operator.kind == IDENTITY
            iszero(operator.target) || error("identity at $p has a target")
        elseif operator.kind == BOND_DIAGONAL
            1 <= operator.target <= nbonds(model) ||
                error("bond target out of bounds at $p")
            _bond_weight(model, propagated, operator.target) > 0 ||
                error("zero-weight bond vertex at $p")
        elseif operator.kind == SITE_DIAGONAL
            1 <= operator.target <= nsites(model) ||
                error("site target out of bounds at $p")
            model.h > 0 || error("site vertex at h=0")
        elseif operator.kind == SITE_FLIP
            1 <= operator.target <= nsites(model) ||
                error("site target out of bounds at $p")
            model.h > 0 || error("flip vertex at h=0")
            propagated[operator.target] *= -1
        else
            error("unknown operator kind $(operator.kind) at $p")
        end
    end

    propagated == state.spins || error("operator string is not periodic")
    return true
end

function raw_measurement(state::SSEState, model::SquareLatticeTFIM)
    nJ = 0
    n0 = 0
    nflip = 0
    for operator in state.operators
        if operator.kind == BOND_DIAGONAL
            nJ += 1
        elseif operator.kind == SITE_DIAGONAL
            n0 += 1
        elseif operator.kind == SITE_FLIP
            nflip += 1
        end
    end
    nh = n0 + nflip
    m = nJ + nflip
    state.n == nJ + nh ||
        error("operator-type counts do not sum to expansion order")
    mz = sum(state.spins) / nsites(model)
    return (; n=state.n,
            n2=state.n^2,
            nJ,
            n0,
            nflip,
            nh,
            m,
            m2=m^2,
            mz,
            mz2=mz^2)
end
