module SquareSymmetryD4

using ..SquareJ1J2Prototype: PauliWord
using ..GenericGapModel:
    LocalPatch,
    GapProblem,
    BasisManifest,
    StateMonomial,
    basis_manifest,
    canonical_word_string

export D4Element,
       d4_matrices,
       is_d4_closed,
       d4_site_perm,
       d4_site_perms,
       apply_site_perm,
       pauli_word_orbit,
       state_monomial_orbit,
       basis_orbits,
       orbit_fingerprint,
       conjugacy_class,
       fix_count,
       irrep_multiplicities

"""
One element of the square point-group D4, as a 2x2 signed-permutation matrix
acting on integer patch coordinates (x,y) -> M * [x,y]. The eight elements are
exactly the 2x2 matrices with entries in {0,+1,-1} and one nonzero per row and
column. `name` labels the conventional element.
"""
struct D4Element
    M::Matrix{Int}
    name::String

    function D4Element(M::Matrix{Int}, name::String)
        size(M) == (2, 2) ||
            throw(ArgumentError("D4 element must be a 2x2 matrix"))
        all(M .∈ Ref((-1, 0, 1))) ||
            throw(ArgumentError("D4 matrix entries must be in {-1,0,1}"))
        new(M, name)
end
end

function apply_coord(el::D4Element, x::Int, y::Int)
    return (el.M[1, 1] * x + el.M[1, 2] * y, el.M[2, 1] * x + el.M[2, 2] * y)
end

"""
The eight D4 elements: identity e, two axis reflections, 180 rotation, the
diagonal reflection, the 90/270 rotations, and the anti-diagonal reflection.
"""
function d4_matrices()
    return D4Element[
        D4Element([1 0; 0 1], "e"),
        D4Element([1 0; 0 -1], "sig_y"),
        D4Element([-1 0; 0 1], "sig_x"),
        D4Element([-1 0; 0 -1], "r2"),
        D4Element([0 1; 1 0], "sig_d"),
        D4Element([0 1; -1 0], "r3"),
        D4Element([0 -1; 1 0], "r1"),
        D4Element([0 -1; -1 0], "sig_dp"),
    ]
end

function matrix_key(el::D4Element)
    return tuple(el.M[1, 1], el.M[1, 2], el.M[2, 1], el.M[2, 2])
end

"""
Verify the eight matrices form a closed group under multiplication and that each
element's inverse is in the set. Returns (closed, missing_products).
"""
function is_d4_closed(elements::Vector{D4Element} = d4_matrices())
    keys = Set(matrix_key(el) for el in elements)
    missing_products = String[]
    for a in elements, b in elements
        product = a.M * b.M
        product_key = tuple(product[1, 1], product[1, 2], product[2, 1], product[2, 2])
        product_key in keys || push!(missing_products, "$(a.name)*$(b.name)")
    end
    return (isempty(missing_products), missing_products)
end

"""
Permutation of site ids induced by one D4 element on a patch. `perm[i]` is the
image of site `i`. Every site must map to a site in the patch.
"""
function d4_site_perm(patch::LocalPatch, el::D4Element)
    coord_to_id = Dict{Tuple{Int,Int},Int}(
        (s.x, s.y) => i for (i, s) in enumerate(patch.sites)
    )
    perm = Vector{Int}(undef, length(patch.sites))
    for (i, s) in enumerate(patch.sites)
        nx, ny = apply_coord(el, s.x, s.y)
        haskey(coord_to_id, (nx, ny)) ||
            error("D4 element $(el.name) maps site $i out of the patch")
        perm[i] = coord_to_id[(nx, ny)]
    end
    return perm
end

function d4_site_perms(patch::LocalPatch, elements::Vector{D4Element} = d4_matrices())
    return [d4_site_perm(patch, el) for el in elements]
end

"""
Apply a site-id permutation to a Pauli word: relabel each factor's site, keep
the Pauli axis, and re-sort (spatial symmetry does not rotate spin, so the phase
is +1 and no axis mixing occurs).
"""
function apply_site_perm(perm::Vector{Int}, word::PauliWord)
    new_ops = sort!([(perm[site], axis) for (site, axis) in word.ops]; by = first)
    return PauliWord(new_ops)
end

function apply_site_perm(perm::Vector{Int}, monomial::StateMonomial)
    new_state = [apply_site_perm(perm, w) for w in monomial.state_symbols]
    new_op = apply_site_perm(perm, monomial.operator_word)
    return StateMonomial(new_state, new_op)
end

function pauli_word_orbit(word::PauliWord, perms::Vector{Vector{Int}})
    images = Set{PauliWord}()
    for perm in perms
        push!(images, apply_site_perm(perm, word))
    end
    return sort!(collect(images); by = canonical_word_string)
end

function state_monomial_orbit(monomial::StateMonomial, perms::Vector{Vector{Int}})
    images = Set{StateMonomial}()
    for perm in perms
        push!(images, apply_site_perm(perm, monomial))
    end
    return sort!(collect(images); by = state_monomial_key)
end

function state_monomial_key(m::StateMonomial)
    return (
        length(m.state_symbols),
        join(canonical_word_string.(m.state_symbols), "|"),
        canonical_word_string(m.operator_word),
    )
end

"""
Partition a basis into D4 orbits. Returns a vector of orbits (each a sorted
vector of basis indices) plus the orbit-size histogram. A basis entry that maps
outside the basis under D4 is flagged (it would mean the basis is not
D4-invariant -- the reduction requires an invariant basis).
"""
function basis_orbits(entries::Vector{StateMonomial}, perms::Vector{Vector{Int}})
    index = Dict{StateMonomial,Int}(entry => i for (i, entry) in enumerate(entries))
    visited = falses(length(entries))
    orbits = Vector{Int}[]
    escaped = Int[]
    for i in eachindex(entries)
        visited[i] && continue
        orbit_images = Set{Int}([i])
        fully_inside = true
        for perm in perms
            image = apply_site_perm(perm, entries[i])
            if haskey(index, image)
                push!(orbit_images, index[image])
            else
                fully_inside = false
            end
        end
        fully_inside || push!(escaped, i)
        orbit = sort!(collect(orbit_images))
        for j in orbit
            visited[j] = true
        end
        push!(orbits, orbit)
    end
    histogram = Dict{Int,Int}()
    for orbit in orbits
        histogram[length(orbit)] = get(histogram, length(orbit), 0) + 1
    end
    return (orbits, histogram, escaped)
end

function orbit_fingerprint(orbits::Vector{Vector{Int}}, histogram::Dict{Int,Int})
    parts = String[
        "orbits=$(length(orbits))",
        ["size$k=$v" for (k, v) in sort!(collect(histogram))]...,
    ]
    return join(parts, ";")
end

"""
D4 conjugacy classes (5): :E (identity), :C4 (90/270 rotations), :C2 (180),
:sigmav (axis reflections), :sigmad (diagonal reflections). Classified from the
signed-permutation matrix so the result is robust to element ordering/naming.
"""
function conjugacy_class(el::D4Element)
    M = el.M
    if M == [1 0; 0 1]
        return :E
    end
    is_diagonal = iszero(M[1, 2]) && iszero(M[2, 1])
    if is_diagonal
        trace = M[1, 1] + M[2, 2]
        trace == -2 && return :C2
        trace == 0 && return :sigmav
        error("unexpected diagonal D4 matrix")
    end
    determinant = M[1, 1] * M[2, 2] - M[1, 2] * M[2, 1]
    determinant == 1 && return :C4
    determinant == -1 && return :sigmad
    error("unexpected off-diagonal D4 matrix")
end

const D4_CLASS_SIZE = Dict(:E => 1, :C4 => 2, :C2 => 1, :sigmav => 2, :sigmad => 2)

const D4_CHARACTER_TABLE = Dict{Symbol,Dict{Symbol,Int}}(
    :A1 => Dict(:E => 1, :C4 => 1, :C2 => 1, :sigmav => 1, :sigmad => 1),
    :A2 => Dict(:E => 1, :C4 => 1, :C2 => 1, :sigmav => -1, :sigmad => -1),
    :B1 => Dict(:E => 1, :C4 => -1, :C2 => 1, :sigmav => 1, :sigmad => -1),
    :B2 => Dict(:E => 1, :C4 => -1, :C2 => 1, :sigmav => -1, :sigmad => 1),
    :E => Dict(:E => 2, :C4 => 0, :C2 => -2, :sigmav => 0, :sigmad => 0),
)

"""Number of basis entries fixed by a site permutation (== trace of U(g))."""
function fix_count(entries::Vector{StateMonomial}, perm::Vector{Int})
    return count(
        i -> apply_site_perm(perm, entries[i]) == entries[i],
        eachindex(entries),
    )
end

"""
Irrep multiplicities of the permutation representation U(g) on `entries`.
Returns n_lambda for lambda in {A1,A2,B1,B2,E}. The block-diagonal PSD has one
block per irrep: A1/A2/B1/B2 of dimension n_lambda, and E of dimension n_E
(the E-isotypic subspace is C^2 (x) C^{n_E}, and by Schur's lemma the PSD
constraint reduces to a single n_E x n_E block). Sanity:
`n_A1 + n_A2 + n_B1 + n_B2 + 2*n_E == length(entries)`.
"""
function irrep_multiplicities(
    entries::Vector{StateMonomial},
    elements::Vector{D4Element},
    perms::Vector{Vector{Int}},
)
    fix_by_class = Dict{Symbol,Int}()
    for (el, perm) in zip(elements, perms)
        fix_by_class[conjugacy_class(el)] = fix_count(entries, perm)
    end
    multiplicities = Dict{Symbol,Int}()
    for (irrep, chars) in D4_CHARACTER_TABLE
        total = 0
        for cls in keys(chars)
            total += D4_CLASS_SIZE[cls] * chars[cls] * fix_by_class[cls]
        end
        multiplicities[irrep] = div(total, 8)
    end
    return multiplicities
end

end
