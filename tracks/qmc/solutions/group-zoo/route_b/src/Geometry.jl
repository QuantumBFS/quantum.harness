const _LATTICE_DEGREES = Dict(
    :chain => 2,
    :square => 4,
    :honeycomb => 3,
    :triangle => 6,
)

_cell_site(L::Int, u::Int, v::Int) = mod(u, L) + L * mod(v, L) + 1
_honeycomb_site(L::Int, u::Int, v::Int, sublattice::Int) =
    2 * (mod(u, L) + L * mod(v, L)) + sublattice + 1

function _lattice_spec(name::Symbol, L::Int)
    haskey(_LATTICE_DEGREES, name) ||
        throw(ArgumentError("unsupported lattice: $name"))

    minimum_L = name == :honeycomb ? 2 : 3
    L >= minimum_L ||
        throw(ArgumentError("$name lattice requires L >= $minimum_L"))

    if name == :chain
        return L, ((1, 0),)
    elseif name == :square
        return L^2, ((1, 0), (0, 1))
    elseif name == :triangle
        return L^2, ((1, 0), (0, 1), (1, -1))
    end

    return 2L^2, ((0, 0), (-1, 0), (0, -1))
end

function _push_bond!(
    bonds::Vector{Tuple{Int,Int}},
    directed::Vector{DirectedBond},
    incident::Vector{Vector{Int}},
    src::Int,
    dst::Int,
    du::Int,
    dv::Int,
)
    bond = length(bonds) + 1
    push!(bonds, (src, dst))
    push!(directed, DirectedBond(bond, src, dst, du, dv))
    push!(directed, DirectedBond(bond, dst, src, -du, -dv))
    push!(incident[src], bond)
    push!(incident[dst], bond)
    return bond
end

function build_lattice(name::Symbol, L::Integer)
    size = Int(L)
    nsites, directions = _lattice_spec(name, size)
    bonds = Tuple{Int,Int}[]
    directed = DirectedBond[]
    incident = [Int[] for _ in 1:nsites]

    if name == :chain
        for u in 0:(size - 1)
            src = _cell_site(size, u, 0)
            dst = _cell_site(size, u + 1, 0)
            _push_bond!(bonds, directed, incident, src, dst, 1, 0)
        end
    elseif name == :honeycomb
        for v in 0:(size - 1), u in 0:(size - 1)
            src = _honeycomb_site(size, u, v, 0)
            for (du, dv) in directions
                dst = _honeycomb_site(size, u + du, v + dv, 1)
                _push_bond!(bonds, directed, incident, src, dst, du, dv)
            end
        end
    else
        for v in 0:(size - 1), u in 0:(size - 1)
            src = _cell_site(size, u, v)
            for (du, dv) in directions
                dst = _cell_site(size, u + du, v + dv)
                _push_bond!(bonds, directed, incident, src, dst, du, dv)
            end
        end
    end

    lattice = Lattice(name, size, nsites, bonds, directed, incident)
    validate_lattice(lattice) || error("internal error: invalid $name lattice")
    return lattice
end

function reverse_displacement(lattice::Lattice, edge::DirectedBond)
    1 <= edge.bond <= length(lattice.bonds) ||
        throw(ArgumentError("directed edge has an invalid bond index"))
    forward = lattice.directed[2edge.bond - 1]
    reverse = lattice.directed[2edge.bond]

    if edge.src == forward.src && edge.dst == forward.dst
        return (reverse.du, reverse.dv)
    elseif edge.src == reverse.src && edge.dst == reverse.dst
        return (forward.du, forward.dv)
    end
    throw(ArgumentError("directed edge endpoints do not match its bond"))
end

function _is_connected(lattice::Lattice)
    seen = falses(lattice.nsites)
    queue = Int[1]
    seen[1] = true
    cursor = 1

    while cursor <= length(queue)
        site = queue[cursor]
        cursor += 1
        for bond in lattice.incident[site]
            left, right = lattice.bonds[bond]
            neighbor = left == site ? right : left
            if !seen[neighbor]
                seen[neighbor] = true
                push!(queue, neighbor)
            end
        end
    end
    return all(seen)
end

function validate_lattice(lattice::Lattice)
    expected_degree = get(_LATTICE_DEGREES, lattice.name, 0)
    expected_degree > 0 || return false
    lattice.L > 0 || return false
    lattice.nsites == length(lattice.incident) || return false
    length(lattice.directed) == 2length(lattice.bonds) || return false
    all(length(edges) == expected_degree for edges in lattice.incident) || return false

    canonical = Set{Tuple{Int,Int}}()
    for (bond, (left, right)) in enumerate(lattice.bonds)
        1 <= left <= lattice.nsites || return false
        1 <= right <= lattice.nsites || return false
        left != right || return false
        key = minmax(left, right)
        key in canonical && return false
        push!(canonical, key)

        count(==(bond), lattice.incident[left]) == 1 || return false
        count(==(bond), lattice.incident[right]) == 1 || return false
        forward = lattice.directed[2bond - 1]
        reverse = lattice.directed[2bond]
        forward.bond == reverse.bond == bond || return false
        (forward.src, forward.dst) == (left, right) || return false
        (reverse.src, reverse.dst) == (right, left) || return false
        (forward.du, forward.dv) == (-reverse.du, -reverse.dv) || return false
    end

    return _is_connected(lattice)
end
