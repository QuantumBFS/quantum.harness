module SquareSymmetryBlock

using ..SquareJ1J2Prototype: PauliWord
using ..GenericGapModel: StateMonomial, canonical_word_string
using ..SquareSymmetryD4:
    D4Element,
    d4_matrices,
    d4_site_perms,
    apply_site_perm,
    conjugacy_class,
    basis_orbits,
    D4_CHARACTER_TABLE,
    D4_CLASS_SIZE

export permutation_matrix,
       irrep_projector,
       rational_column_basis,
       symmetry_adapted_basis,
       D4SymmetryBasis,
       verify_block_structure,
       block_label

"""
Permutation matrix U(g) for the action of one site permutation on a basis:
`U[j,k] = 1` iff applying the permutation to basis entry `k` yields entry `j`.
`U` represents the left action on coefficient vectors, so an invariant matrix M
satisfies `U(g)' * M * U(g) == M`.
"""
function permutation_matrix(entries::Vector{StateMonomial}, perm::Vector{Int})
    n = length(entries)
    index = Dict{StateMonomial,Int}(entries[i] => i for i in 1:n)
    U = zeros(Int, n, n)
    for k in 1:n
        image = apply_site_perm(perm, entries[k])
        haskey(index, image) ||
            error("basis entry escapes the group action (not D4-closed)")
        U[index[image], k] = 1
    end
    return U
end

function irrep_dimension(irrep::Symbol)
    return irrep == :E ? 2 : 1
end

"""
Exact rational projector onto the lambda-isotypic subspace of the permutation
representation: `P_lambda = (d_lambda / |G|) * sum_g chi_lambda(g) * U(g)`.
Entries are rationals with denominator dividing 8.
"""
function irrep_projector(
    entries::Vector{StateMonomial},
    elements::Vector{D4Element},
    perms::Vector{Vector{Int}},
    irrep::Symbol,
)
    n = length(entries)
    chars = D4_CHARACTER_TABLE[irrep]
    d = irrep_dimension(irrep)
    P = zeros(Rational{BigInt}, n, n)
    for (el, perm) in zip(elements, perms)
        chi = chars[conjugacy_class(el)]
        iszero(chi) && continue
        U = permutation_matrix(entries, perm)
        P .+= (chi // 1) .* U
    end
    P .*= (d // 8)
    return P
end

"""
Exact column basis of the image of P via full rational Gauss-Jordan elimination.
Returns (basis, pivot_columns) where `basis = P[:, pivot_columns]`.
"""
function rational_column_basis(P::Matrix{<:Rational})
    rows, cols = size(P)
    work = copy(P)
    pivot_cols = Int[]
    pivot_row = 1
    for c in 1:cols
        pivot_row > rows && break
        idx = findfirst(!iszero, @view work[pivot_row:end, c])
        idx === nothing && continue
        pr = pivot_row + idx - 1
        if pr != pivot_row
            row_tmp = copy(@view work[pivot_row, :])
            @views work[pivot_row, :] .= work[pr, :]
            work[pr, :] .= row_tmp
        end
        piv = work[pivot_row, c]
        @views work[pivot_row, :] .= work[pivot_row, :] ./ piv
        for r in 1:rows
            r == pivot_row && continue
            f = work[r, c]
            iszero(f) && continue
            @views work[r, :] .= work[r, :] .- f .* work[pivot_row, :]
        end
        push!(pivot_cols, c)
        pivot_row += 1
    end
    return P[:, pivot_cols], pivot_cols
end

struct D4SymmetryBasis
    entries::Vector{StateMonomial}
    Q::Matrix{Rational{BigInt}}
    block_irreps::Vector{Symbol}
    block_ranges::Vector{UnitRange{Int}}
    rank_total::Int
end

function block_label(basis::D4SymmetryBasis)
    parts = String[]
    for (i, irrep) in enumerate(basis.block_irreps)
        r = basis.block_ranges[i]
        push!(parts, "$(irrep)=$(length(r))")
    end
    return join(parts, ",")
end

"""
Build the exact rational symmetry-adapted basis Q via the orbit-sum / partner-
function construction (no Gauss-Jordan elimination, so it stays fast). For each
orbit representative i and irrep lambda, the vector v = P_lambda e_i is built
directly as a signed sum over the group; for the 2-dim E irrep the two partners
use the natural representation matrices D^E(g) = el.M. Vectors from different
orbits (disjoint support) and different irreps (orthogonal projectors) are
mutually orthogonal, so the collection is linearly independent and spans V.
"""
function symmetry_adapted_basis(
    entries::Vector{StateMonomial},
    elements::Vector{D4Element},
    perms::Vector{Vector{Int}},
)
    n = length(entries)
    index = Dict{StateMonomial,Int}(entries[i] => i for i in 1:n)
    orbits, _, _ = basis_orbits(entries, perms)
    reps = [orbit[1] for orbit in orbits]

    block_columns = Matrix{Rational{BigInt}}[]
    block_irreps = Symbol[]
    block_dims = Int[]
    for irrep in (:A1, :A2, :B1, :B2, :E)
        d = irrep_dimension(irrep)
        chars = D4_CHARACTER_TABLE[irrep]
        cols = Vector{Rational{BigInt}}[]
        if irrep == :E
            # E is the unique D4 irrep odd under the 180 rotation r2 (all four
            # 1-dim irreps have chi(r2)=+1), so P_E == (1/2)(I - U(r2)) exactly.
            # A basis of im(P_E) is {(e_j - e_{r2.j})/2} for one representative
            # per {j, r2.j} pair. Yields exactly 2*n_E vectors, no elimination,
            # and is correct for multi-copy orbits (the global pairing captures
            # every E copy, unlike a per-orbit representative sum).
            r2_idx = findfirst(el -> conjugacy_class(el) == :C2, elements)
            r2_perm = perms[r2_idx]
            for j in 1:n
                k = index[apply_site_perm(r2_perm, entries[j])]
                (k == j || j > k) && continue
                v = zeros(Rational{BigInt}, n)
                v[j] = 1 // 2
                v[k] = -(1 // 2)
                push!(cols, v)
            end
        else
            for rep in reps
                v = zeros(Rational{BigInt}, n)
                for (el, perm) in zip(elements, perms)
                    chi = chars[conjugacy_class(el)]
                    iszero(chi) && continue
                    gi = index[apply_site_perm(perm, entries[rep])]
                    v[gi] += (chi // 1)
                end
                v .*= (d // 8)
                any(!iszero, v) && push!(cols, v)
            end
        end
        isempty(cols) && continue
        mat = reduce(hcat, cols)
        push!(block_columns, mat)
        push!(block_irreps, irrep)
        push!(block_dims, size(mat, 2))
    end
    Q = reduce(hcat, block_columns)
    if size(Q, 1) != size(Q, 2)
        counts = ["$(block_irreps[i])=$(block_dims[i])" for i in eachindex(block_irreps)]
        println("[d4-block] DEBUG non-square Q $(size(Q)); orbit-reps=$(length(reps)); blocks: $(join(counts, ", "))")
    end
    @assert size(Q, 1) == size(Q, 2) "Q is not square: $(size(Q)); block dims sum to $(sum(block_dims))"
    ranges = UnitRange{Int}[]
    offset = 0
    for d in block_dims
        push!(ranges, (offset + 1):(offset + d))
        offset += d
    end
    return D4SymmetryBasis(entries, Q, block_irreps, ranges, offset)
end

"""
Verify the block structure in Float64 (Q's rational entries 1/2, 1/4, 1/8 are
exactly representable, so no precision is lost). For every group element g the
congruence Q' * U(g) * Q must be block-diagonal w.r.t. the irrep ranges. The
exact-equivalence claim does not depend on this Float64 check: it rests on the
four invariance/covariance gates (checked on the exact rational CoreMGK
tensors) plus the group-averaging theorem. Q is invertible because it is square
and its columns are mutually orthogonal by construction.
"""
function verify_block_structure(
    basis::D4SymmetryBasis,
    elements::Vector{D4Element},
    perms::Vector{Vector{Int}},
)
    n = length(basis.entries)
    Qf = Matrix{Float64}(basis.Q)
    qtf = transpose(Qf)
    max_off_block = 0.0
    for (el, perm) in zip(elements, perms)
        U = permutation_matrix(basis.entries, perm)
        B = qtf * U * Qf
        for (a, ra) in enumerate(basis.block_ranges), (b, rb) in enumerate(basis.block_ranges)
            a == b && continue
            m = maximum(abs.(B[ra, rb]); init = 0.0)
            m > max_off_block && (max_off_block = m)
        end
    end
    block_diag_ok = max_off_block < 1e-10
    return (
        n = n,
        Q_is_square = size(basis.Q, 1) == size(basis.Q, 2),
        block_diagonal_for_all_g = block_diag_ok,
        max_off_block_abs = max_off_block,
    )
end

end
