struct LatticeGeometry
    lattice::Symbol
    L::Int
    nsites::Int
    bonds::Vector{Tuple{Int,Int}}
    coordination::Vector{Int}
end

function beta_for_aspect(h::Real, L::Integer; c::Real = 1.0)
    iszero(h) && throw(ArgumentError("h must be nonzero when fixing beta*abs(h)/L"))
    L > 0 || throw(ArgumentError("L must be positive"))
    c > 0 || throw(ArgumentError("c must be positive"))
    return float(c) * L / abs(float(h))
end

function lattice_geometry(lattice::Symbol, L::Integer)
    if lattice === :triangle
        L >= 3 || throw(ArgumentError("triangle rhombic torus requires L >= 3"))
        nsites = L^2
        triangle_site(x, y) = 1 + mod(x, L) + L * mod(y, L)
        bonds = Tuple{Int,Int}[]
        for y in 0:L-1, x in 0:L-1
            i = triangle_site(x, y)
            push!(bonds, (i, triangle_site(x, y + 1)))
            push!(bonds, (i, triangle_site(x + 1, y)))
            push!(bonds, (i, triangle_site(x + 1, y + 1)))
        end
    elseif lattice === :honeycomb
        L >= 2 || throw(ArgumentError("honeycomb rhombic torus requires L >= 2"))
        nsites = 2L^2
        honeycomb_site(x, y, sublattice) =
            sublattice + 2 * (mod(x, L) + L * mod(y, L))
        bonds = Tuple{Int,Int}[]
        for y in 0:L-1, x in 0:L-1
            a = honeycomb_site(x, y, 1)
            b = honeycomb_site(x, y, 2)
            push!(bonds, (a, b))
            push!(bonds, (b, honeycomb_site(x, y + 1, 1)))
            push!(bonds, (b, honeycomb_site(x + 1, y, 1)))
        end
    else
        throw(ArgumentError("unsupported lattice: $lattice"))
    end

    coordination = zeros(Int, nsites)
    for (i, j) in bonds
        coordination[i] += 1
        coordination[j] += 1
    end

    return LatticeGeometry(lattice, Int(L), nsites, bonds, coordination)
end
