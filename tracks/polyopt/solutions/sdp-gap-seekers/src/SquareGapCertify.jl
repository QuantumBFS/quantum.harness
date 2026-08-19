module SquareGapCertify

# Square-lattice J1-J2 Heisenberg gap-certify scaffold.
#
# Context: SpectralGap.jl has turnkey certifiers for 1D TFIM and kagome
# Heisenberg, but NOT for the square J1-J2. The certify functions are generic
# SDP assembly (positivity + gap + stationarity blocks) once a *structured basis*
# is supplied; the basis is geometry-specific (get_basis = 1D chain,
# get_kagome_basis = 2D kagome triangles). For square, get_square_basis must be
# written -- that is the structured-basis R&D on Sihan's feature/structured-basis-assembly.
#
# This module delivers the square side that does NOT depend on the basis:
#   1. square_j1j2_terms  -- the H as SpectralGap ncpoly support/coefficient
#      arrays, bridged from SquareJ1J2Prototype.square_patch. Pure term
#      enumeration, no SDP stack needed -> testable now.
#   2. square_patch_geometry -- the (sites, inner, J1/J2 bonds) the basis must cover.
# The missing piece (get_square_basis) is specified in SQUARE_BASIS_SPEC.md.

using ..SquareJ1J2Prototype: square_patch, SquarePatch, Bond, Site

export square_j1j2_terms, square_patch_geometry

"""
    square_j1j2_terms(L; g=1//2, J1=1.0) -> (supp, coe, N, patch)

Enumerate the square J1-J2 Heisenberg Hamiltonian in SpectralGap.jl's ncpoly
encoding (site `i` -> `3i-2 = X_i`, `3i-1 = Y_i`, `3i = Z_i`):

    H = J1 * sum_{<ij> in J1} S_i.S_j  +  J2 * sum_{<<ij>> in J2} S_i.S_j,
    S_i.S_j = 1/4 (X_i X_j + Y_i Y_j + Z_i Z_j),   J2 = g*J1.

Returns `(supp, coe, N, patch)` where `supp::Vector{Vector{Int}}` and
`coe::Vector{Float64}` are ready for `SpectralGap.ncpoly(supp, coe)`, `N` is the
site count, and `patch` is the `SquarePatch`.

SpectralGap-agnostic (pure enumeration) so it is unit-testable without the SDP
stack. Couplings are exact-rational in the patch; the 0.25 spin-normalization is
applied here, matching certify_Heisenberg_kagome_gap's convention.
"""
function square_j1j2_terms(L::Int; g::T=1//2, J1::Real=1) where {T<:Real}
    patch = square_patch(L; g=g)
    N = length(patch.sites)
    supp = Vector{Int}[]
    coe = Float64[]
    for bond in patch.bonds
        i, j = bond.i, bond.j
        # bond.coupling is 1 (J1) or g (J2) in the patch; J1 is the energy prefactor.
        c = 0.25 * Float64(J1) * Float64(bond.coupling)
        for (a, b) in ((3i - 2, 3j - 2), (3i - 1, 3j - 1), (3i, 3j))  # XX, YY, ZZ
            push!(supp, a <= b ? [a, b] : [b, a])
            push!(coe, c)
        end
    end
    return supp, coe, N, patch
end

"""
    square_patch_geometry(L; g) -> (N, inner_ids, j1_bonds, j2_bonds, patch)

The square patch geometry that `get_square_basis` / `get_square_bulkbasis` must
cover: the outer site count `N`, the one-layer-eroded inner site IDs (where
stationarity/gap constraints live), and the J1 / J2 bond lists. Mirrors the
kagome (triples/edges, inner_triples/inner_edges) split that
certify_Heisenberg_kagome_gap consumes.
"""
function square_patch_geometry(L::Int; g::T=1//2) where {T<:Real}
    patch = square_patch(L; g=g)
    j1 = [(b.i, b.j) for b in patch.bonds if b.kind == :J1]
    j2 = [(b.i, b.j) for b in patch.bonds if b.kind == :J2]
    return length(patch.sites), patch.inner_ids, j1, j2, patch
end

end
