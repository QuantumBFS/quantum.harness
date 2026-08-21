struct DirectedBond
    bond::Int
    src::Int
    dst::Int
    du::Int
    dv::Int
end

struct Lattice
    name::Symbol
    L::Int
    nsites::Int
    bonds::Vector{Tuple{Int,Int}}
    directed::Vector{DirectedBond}
    incident::Vector{Vector{Int}}
end
