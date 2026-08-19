module SquareJ1J2Prototype

export Site,
       Bond,
       SquarePatch,
       PauliWord,
       square_patch,
       validate_inner_buffer,
       multiply_words,
       pauli_word,
       enumerate_pauli_words,
       operator_word_count_by_degree,
       operator_word_count,
       full_state_basis_count_by_degree,
       full_state_basis_count,
       one_symbol_lift_count,
       dense_complex_matrix_bytes,
       real_embedding_matrix_bytes,
       format_bytes

"""Integer coordinate on the infinite square lattice."""
struct Site
    x::Int
    y::Int
end

"""A unique undirected bond in the local patch."""
struct Bond{T<:Real}
    i::Int
    j::Int
    kind::Symbol
    coupling::T

    function Bond(i::Int, j::Int, kind::Symbol, coupling::T) where {T<:Real}
        i == j && throw(ArgumentError("self-bonds are not allowed"))
        kind in (:J1, :J2) || throw(ArgumentError("bond kind must be :J1 or :J2"))
        new{T}(min(i, j), max(i, j), kind, coupling)
    end
end

"""
Square local-consistency window for the infinite J1-J2 model.

`outer = [-L,L]^2`, `inner = [-(L-1),L-1]^2`. The one-layer erosion is
sufficient for both nearest-neighbour and diagonal next-nearest-neighbour
interactions.
"""
struct SquarePatch{T<:Real}
    L::Int
    sites::Vector{Site}
    site_to_id::Dict{Site,Int}
    inner_ids::Vector{Int}
    bonds::Vector{Bond{T}}
end

Base.isless(a::Site, b::Site) = (a.x, a.y) < (b.x, b.y)

const NN_DISPLACEMENTS = ((1, 0), (0, 1))
const NNN_DISPLACEMENTS = ((1, 1), (1, -1))
const ALL_INTERACTION_DISPLACEMENTS = (
    (1, 0), (-1, 0), (0, 1), (0, -1),
    (1, 1), (1, -1), (-1, 1), (-1, -1),
)

"""
Build a deterministic patch. `g` should preferably be rational, e.g.
`1//2` or `107//200`, so the Hamiltonian metadata remains exact.
"""
function square_patch(L::Int; g::T=0//1) where {T<:Real}
    L >= 1 || throw(ArgumentError("L must be at least 1"))

    sites = sort([Site(x, y) for x in -L:L for y in -L:L])
    site_to_id = Dict(site => i for (i, site) in enumerate(sites))
    inner_ids = [
        site_to_id[site]
        for site in sites
        if max(abs(site.x), abs(site.y)) <= L - 1
    ]

    bonds = Bond{T}[]
    seen = Set{Tuple{Symbol,Int,Int}}()
    for (kind, coupling, displacements) in (
        (:J1, one(T), NN_DISPLACEMENTS),
        (:J2, g, NNN_DISPLACEMENTS),
    )
        for site in sites, (dx, dy) in displacements
            other = Site(site.x + dx, site.y + dy)
            j = get(site_to_id, other, 0)
            j == 0 && continue
            i = site_to_id[site]
            key = (kind, min(i, j), max(i, j))
            key in seen && error("duplicate bond generated: $key")
            push!(seen, key)
            push!(bonds, Bond(i, j, kind, coupling))
        end
    end
    sort!(bonds; by=b -> (b.kind == :J1 ? 1 : 2, b.i, b.j))

    patch = SquarePatch(L, sites, site_to_id, inner_ids, bonds)
    validate_inner_buffer(patch) ||
        error("constructed patch does not have the required interaction buffer")
    return patch
end

"""
Check that every J1/J2 interaction touching an inner site is contained in the
outer patch. This is the condition needed for local commutators to match the
infinite-system derivation.
"""
function validate_inner_buffer(patch::SquarePatch)
    outer = Set(patch.sites)
    for i in patch.inner_ids
        site = patch.sites[i]
        for (dx, dy) in ALL_INTERACTION_DISPLACEMENTS
            Site(site.x + dx, site.y + dy) in outer || return false
        end
    end
    return true
end

# Axis codes are fixed and serialized in X,Y,Z order.
const X_AXIS = UInt8(1)
const Y_AXIS = UInt8(2)
const Z_AXIS = UInt8(3)
const AXIS_FROM_SYMBOL = Dict(:X => X_AXIS, :Y => Y_AXIS, :Z => Z_AXIS)

"""
Canonical Pauli string. `ops` is sorted by site and contains at most one
nonidentity factor per site. Scalar phases are deliberately external.
"""
struct PauliWord
    ops::Vector{Tuple{Int,UInt8}}

    function PauliWord(ops::Vector{Tuple{Int,UInt8}})
        issorted(ops; by=first) || throw(ArgumentError("Pauli factors must be site-sorted"))
        all(op -> op[1] > 0 && op[2] in (X_AXIS, Y_AXIS, Z_AXIS), ops) ||
            throw(ArgumentError("invalid Pauli factor"))
        length(unique(first.(ops))) == length(ops) ||
            throw(ArgumentError("canonical Pauli word has duplicate sites"))
        new(ops)
    end
end

PauliWord() = PauliWord(Tuple{Int,UInt8}[])
Base.:(==)(a::PauliWord, b::PauliWord) = a.ops == b.ops
Base.hash(a::PauliWord, h::UInt) = hash(Tuple(a.ops), h)
Base.length(word::PauliWord) = length(word.ops)

function Base.show(io::IO, word::PauliWord)
    isempty(word.ops) && return print(io, "I")
    axis_names = ("X", "Y", "Z")
    print(io, join((axis_names[Int(a)] * string(i) for (i, a) in word.ops), " "))
end

"""Reduce an arbitrary ordered factor list to phase times canonical word."""
function pauli_word(factors::AbstractVector{<:Tuple})
    coefficient = Complex{Int}(1, 0)
    word = PauliWord()
    for factor in factors
        length(factor) == 2 || throw(ArgumentError("factor must be (site, axis)"))
        site = Int(factor[1])
        axis = factor[2] isa Symbol ? get(AXIS_FROM_SYMBOL, factor[2], UInt8(0)) : UInt8(factor[2])
        axis == 0 && throw(ArgumentError("axis must be :X, :Y, or :Z"))
        local_word = PauliWord([(site, axis)])
        phase, word = multiply_words(word, local_word)
        coefficient *= phase
    end
    return coefficient, word
end

"""Return `(phase, axis)` for an ordered same-site Pauli product."""
function multiply_axes(a::UInt8, b::UInt8)
    a == b && return Complex{Int}(1, 0), UInt8(0)
    if (a, b) in ((X_AXIS, Y_AXIS), (Y_AXIS, Z_AXIS), (Z_AXIS, X_AXIS))
        axis = a == X_AXIS ? Z_AXIS : (a == Y_AXIS ? X_AXIS : Y_AXIS)
        return Complex{Int}(0, 1), axis
    end
    axis = a == Y_AXIS ? Z_AXIS : (a == Z_AXIS ? X_AXIS : Y_AXIS)
    return Complex{Int}(0, -1), axis
end

"""Multiply two canonical Pauli words exactly."""
function multiply_words(left::PauliWord, right::PauliWord)
    coefficient = Complex{Int}(1, 0)
    factors = Dict{Int,UInt8}(left.ops)
    for (site, right_axis) in right.ops
        if !haskey(factors, site)
            factors[site] = right_axis
            continue
        end
        phase, result_axis = multiply_axes(factors[site], right_axis)
        coefficient *= phase
        if result_axis == 0
            delete!(factors, site)
        else
            factors[site] = result_axis
        end
    end
    ops = sort!([(site, axis) for (site, axis) in factors]; by=first)
    return coefficient, PauliWord(ops)
end

"""Exact number of canonical bare Pauli words at each degree `0:d`."""
function operator_word_count_by_degree(nsites::Int, d::Int)
    nsites >= 0 || throw(ArgumentError("nsites must be nonnegative"))
    d >= 0 || throw(ArgumentError("d must be nonnegative"))
    counts = zeros(BigInt, d + 1)
    for k in 0:min(nsites, d)
        counts[k + 1] = binomial(BigInt(nsites), k) * BigInt(3)^k
    end
    return counts
end

operator_word_count(nsites::Int, d::Int) =
    sum(operator_word_count_by_degree(nsites, d))

"""
Enumerate canonical bare Pauli words through degree `d`.

This is intended for tests and small prototypes. Production size estimates
use the exact combinatorial counter above and do not allocate all words.
"""
function enumerate_pauli_words(nsites::Int, d::Int)
    nsites >= 0 || throw(ArgumentError("nsites must be nonnegative"))
    d >= 0 || throw(ArgumentError("d must be nonnegative"))
    words = PauliWord[PauliWord()]
    max_degree = min(nsites, d)

    function choose_sites!(chosen::Vector{Int}, next_site::Int, remaining::Int)
        if remaining == 0
            axes = fill(X_AXIS, length(chosen))
            function choose_axes!(position::Int)
                if position > length(axes)
                    push!(words, PauliWord([(chosen[i], axes[i]) for i in eachindex(chosen)]))
                    return
                end
                for axis in (X_AXIS, Y_AXIS, Z_AXIS)
                    axes[position] = axis
                    choose_axes!(position + 1)
                end
            end
            choose_axes!(1)
            return
        end
        final_start = nsites - remaining + 1
        for site in next_site:final_start
            push!(chosen, site)
            choose_sites!(chosen, site + 1, remaining - 1)
            pop!(chosen)
        end
    end

    for degree in 1:max_degree
        choose_sites!(Int[], 1, degree)
    end
    return words
end

function truncated_convolution(left::Vector{BigInt}, right::Vector{BigInt}, d::Int)
    result = zeros(BigInt, d + 1)
    for i in 0:min(d, length(left) - 1)
        for j in 0:min(d - i, length(right) - 1)
            result[i + j + 1] += left[i + 1] * right[j + 1]
        end
    end
    return result
end

"""
Exact degree counts for the full formal basis

    ζ(w1)...ζ(wk) v

through degree `d`, before optional symmetry quotienting. The generating
function is `(1+3t)^n Π_(w≠I)(1-t^deg(w))^-1`.
"""
function full_state_basis_count_by_degree(nsites::Int, d::Int)
    operator_counts = operator_word_count_by_degree(nsites, d)
    scalar_state_counts = zeros(BigInt, d + 1)
    scalar_state_counts[1] = 1

    for degree in 1:min(nsites, d)
        number_of_variables = operator_counts[degree + 1]
        number_of_variables == 0 && continue
        factor = zeros(BigInt, d + 1)
        for multiplicity in 0:div(d, degree)
            # Number of multisets of this multiplicity drawn from N symbols.
            factor[multiplicity * degree + 1] =
                binomial(number_of_variables + multiplicity - 1, multiplicity)
        end
        scalar_state_counts =
            truncated_convolution(scalar_state_counts, factor, d)
    end

    return truncated_convolution(operator_counts, scalar_state_counts, d)
end

full_state_basis_count(nsites::Int, d::Int) =
    sum(full_state_basis_count_by_degree(nsites, d))

"""
Count a deliberately incomplete but deterministic structured lift containing
each selected bare word `w` and one scalar row `ζ(w)` for every nonidentity
word. This is a sizing baseline, not the complete hierarchy.
"""
function one_symbol_lift_count(nsites::Int, d::Int)
    count = operator_word_count(nsites, d)
    return 2 * count - 1
end

"""Raw storage lower bound for one dense `ComplexF64` square matrix."""
dense_complex_matrix_bytes(dimension::Integer) =
    BigInt(16) * BigInt(dimension)^2

"""Raw storage for a conventional `2m × 2m` real embedding."""
real_embedding_matrix_bytes(dimension::Integer) =
    BigInt(8) * (2 * BigInt(dimension))^2

function format_bytes(bytes::Integer)
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
    value = Float64(bytes)
    unit = units[1]
    for candidate in units
        unit = candidate
        value < 1024 && break
        candidate == units[end] && break
        value /= 1024
    end
    return string(round(value; sigdigits=4), " ", unit)
end

end
