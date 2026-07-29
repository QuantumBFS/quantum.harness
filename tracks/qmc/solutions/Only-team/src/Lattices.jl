struct Lattice
    kind::Symbol
    NumL1::Int
    NumL2::Int
    N::Int
    neighbors::Vector{Vector{Int}}
    bonds::Vector{NTuple{2,Int}}
end

function _cell_index(x::Int, y::Int, NumL1::Int, NumL2::Int)
    return mod(x, NumL1) + 1 + NumL1 * mod(y, NumL2)
end

function _honeycomb_index(
    x::Int,
    y::Int,
    sublattice::Symbol,
    NumL1::Int,
    NumL2::Int,
)
    offset = sublattice === :A ? 1 : 2
    return 2 * (_cell_index(x, y, NumL1, NumL2) - 1) + offset
end

function _build_triangular_neighbors(NumL1::Int, NumL2::Int)
    neighbors = [Int[] for _ in 1:(NumL1 * NumL2)]
    offsets = ((-1, 0), (-1, 1), (0, 1), (1, 0), (1, -1), (0, -1))

    for y in 0:(NumL2 - 1), x in 0:(NumL1 - 1)
        site = _cell_index(x, y, NumL1, NumL2)
        for (dx, dy) in offsets
            push!(
                neighbors[site],
                _cell_index(x + dx, y + dy, NumL1, NumL2),
            )
        end
        sort!(neighbors[site])
    end

    return neighbors
end

function _build_honeycomb_neighbors(NumL1::Int, NumL2::Int)
    neighbors = [Int[] for _ in 1:(2 * NumL1 * NumL2)]

    for y in 0:(NumL2 - 1), x in 0:(NumL1 - 1)
        site_A = _honeycomb_index(x, y, :A, NumL1, NumL2)
        site_B = _honeycomb_index(x, y, :B, NumL1, NumL2)

        append!(
            neighbors[site_A],
            (
                _honeycomb_index(x, y, :B, NumL1, NumL2),
                _honeycomb_index(x - 1, y, :B, NumL1, NumL2),
                _honeycomb_index(x, y - 1, :B, NumL1, NumL2),
            ),
        )
        append!(
            neighbors[site_B],
            (
                _honeycomb_index(x, y, :A, NumL1, NumL2),
                _honeycomb_index(x + 1, y, :A, NumL1, NumL2),
                _honeycomb_index(x, y + 1, :A, NumL1, NumL2),
            ),
        )
        sort!(neighbors[site_A])
        sort!(neighbors[site_B])
    end

    return neighbors
end

function _build_bonds(neighbors::Vector{Vector{Int}})
    bond_set = Set{NTuple{2,Int}}()
    for site in eachindex(neighbors), neighbor in neighbors[site]
        push!(bond_set, minmax(site, neighbor))
    end
    return sort!(collect(bond_set))
end

function build_lattice(kind::Symbol, NumL1::Integer, NumL2::Integer)
    NumL1 >= 3 || throw(ArgumentError("NumL1 must be at least 3"))
    NumL2 >= 3 || throw(ArgumentError("NumL2 must be at least 3"))

    L1 = Int(NumL1)
    L2 = Int(NumL2)
    neighbors = if kind === :triangular
        _build_triangular_neighbors(L1, L2)
    elseif kind === :honeycomb
        _build_honeycomb_neighbors(L1, L2)
    else
        throw(
            ArgumentError(
                "lattice must be :triangular or :honeycomb; got $(repr(kind))",
            ),
        )
    end

    lattice = Lattice(kind, L1, L2, length(neighbors), neighbors, _build_bonds(neighbors))
    validate_lattice(lattice)
    return lattice
end

function validate_lattice(lattice::Lattice)
    lattice.NumL1 >= 3 || throw(ArgumentError("NumL1 must be at least 3"))
    lattice.NumL2 >= 3 || throw(ArgumentError("NumL2 must be at least 3"))

    expected_N, expected_degree, expected_bonds = if lattice.kind === :triangular
        (lattice.NumL1 * lattice.NumL2, 6, 3 * lattice.N)
    elseif lattice.kind === :honeycomb
        (2 * lattice.NumL1 * lattice.NumL2, 3, 3 * lattice.N ÷ 2)
    else
        throw(ArgumentError("unsupported lattice kind $(repr(lattice.kind))"))
    end

    lattice.N == expected_N ||
        throw(ArgumentError("lattice site count does not match its dimensions"))
    length(lattice.neighbors) == lattice.N ||
        throw(ArgumentError("neighbor table length does not match lattice.N"))

    adjacency_bonds = Set{NTuple{2,Int}}()
    for site in 1:lattice.N
        site_neighbors = lattice.neighbors[site]
        length(site_neighbors) == expected_degree ||
            throw(ArgumentError("site $site has an invalid degree"))
        length(unique(site_neighbors)) == length(site_neighbors) ||
            throw(ArgumentError("site $site has duplicate neighbors"))

        for neighbor in site_neighbors
            1 <= neighbor <= lattice.N ||
                throw(ArgumentError("site $site has an out-of-range neighbor"))
            neighbor != site ||
                throw(ArgumentError("site $site has a self connection"))
            site in lattice.neighbors[neighbor] ||
                throw(ArgumentError("adjacency is not symmetric at sites $site and $neighbor"))
            push!(adjacency_bonds, minmax(site, neighbor))
        end
    end

    length(lattice.bonds) == length(unique(lattice.bonds)) ||
        throw(ArgumentError("bond table contains duplicate bonds"))
    all(first(bond) < last(bond) for bond in lattice.bonds) ||
        throw(ArgumentError("bonds must be ordered pairs of distinct sites"))
    Set(lattice.bonds) == adjacency_bonds ||
        throw(ArgumentError("bond table does not match the neighbor table"))
    length(lattice.bonds) == expected_bonds ||
        throw(ArgumentError("lattice has an invalid number of bonds"))

    return nothing
end
