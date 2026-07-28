# M2 shared machinery — toric-code iPEPS on the composite (vertex + E,N edges) lattice.
#
# Role: single source of truth for spaces, the exact toric-code tensor (V/P
# construction), the Hamiltonian as a PEPSKit LocalOperator, and the simple-update
# (SU) circuit builder. Included by scripts/groundstate_h0.jl, tests/runtests.jl,
# and the inspection/ probes. All quantities use the conventions below; do not
# duplicate them elsewhere (see FINDINGS.md for the validation evidence).
#
# Conventions (PLAN.md §2 as amended at M2):
#   H = −Jₑ Σₛ Aₛ − Jₘ Σₚ B_p − hₓ Σᵢ Xᵢ − h_z Σᵢ Zᵢ ,  Jₑ = Jₘ = 1
#   Composite site (r,c) = vertex (r,c) + its east edge E(r,c) + north edge N(r,c).
#   Rows r increase downward (PEPSKit grid), N(r,c) is the vertical edge (r,c)–(r−1,c).
#   Physical leg: fused pair (pE, pN), dim 4, basis |00⟩,|10⟩,|01⟩,|11⟩ (pE fast),
#   trivially Z₂-graded (all states charge 0) — required for the exact tensor to be
#   an intertwiner (PLAN §4 amendment).
#   Virtual legs: Z2Space(0=>⌈D/2⌉, 1=>⌊D/2⌋); charge = loop-occupancy bit.
#   Star:   A(r,c) = X_E X_N on (r,c) · X_E on (r,c−1) · X_N on (r+1,c)
#   Plaquette: B(r,c) = Z_E Z_N on (r,c) · Z_E on (r−1,c) · Z_N on (r,c+1)
#   (face above-right of vertex (r,c)); both are 3-site L-shaped terms.
# Unit cell: (2,2) supercell of composite sites (8 physical spins), required by the
# simple-update cluster machinery; N = 8 spins per cell, E₀(cell) = −8 at h = 0.
#
# Sections: spaces → physical Pauli operators → exact tensor (V/P + closed form)
# → Hamiltonian LocalOperator → SU circuit/weights → ungraded (dense) variants.
# All operator/tensor constructors take an optional space argument `P` (and `V`);
# defaults are the Z₂-graded spaces, `ℂ^4`/`ℂ^D` give the ungraded variants.

using LinearAlgebra
using TensorKit
using PEPSKit
using MPSKit

# ---------- spaces ----------
"Virtual bond space at bond dimension D (Z₂-graded, balanced degeneracy)."
vspace(D::Int) = Z2Space(0 => cld(D, 2), 1 => fld(D, 2))

"Fused physical space of one composite site: two qubits, both trivially graded.
Basis order (probed): index = pE + 2·pN + 1 (pE fast), i.e. |00⟩,|10⟩,|01⟩,|11⟩."
const PSPACE = fuse(Z2Space(0 => 2), Z2Space(0 => 2))   # = Z2Space(0 => 4), single leg

"CTMRG environment space, balanced Z₂-graded."
envspace(χ::Int) = Z2Space(0 => χ ÷ 2, 1 => χ ÷ 2)

# ---------- Pauli operators on the fused physical space ----------
# Layout conventions (verified by probe): TensorKit dense conversion is
# first-leg-fastest; Julia kron puts its FIRST factor on the SLOW index.
# Fused physical basis |pE pN⟩: pE fast (index pE + 2·pN + 1), so
#   X on pE = kron(I, X),  X on pN = kron(X, I).
# Multi-site ops on sites (1,2,3) with site 1 fastest: mat = kron(op3, op2, op1).
const _X = ComplexF64[0 1; 1 0]
const _Z = ComplexF64[1 0; 0 -1]
const _I = ComplexF64[1 0; 0 1]

XE_mat() = kron(_I, _X)          # X on east-edge qubit (fast index)
XN_mat() = kron(_X, _I)          # X on north-edge qubit (slow index)
ZE_mat() = kron(_I, _Z)
ZN_mat() = kron(_Z, _I)
PX_mat() = kron(_X, _X)          # X_E X_N (star factor on a composite site)
PZ_mat() = kron(_Z, _Z)          # Z_E Z_N (plaquette factor)

"Dense matrix → TensorMap on n fused physical sites (site 1 fastest).
Space `P` defaults to the graded PSPACE; pass `ℂ^4` for the ungraded variant."
function phys_tmap(mat::AbstractMatrix, n::Int = 1, P = PSPACE)
    Pn = n == 1 ? P : P^n
    return TensorMap(ComplexF64.(mat), Pn, Pn)
end

# Pauli products of the stabilizers, in TensorKit leg order (site 1 = fastest):
#   star sites [(r,c−1), (r,c), (r+1,c)]:   A = X_E(site1) · PX(site2) · X_N(site3)
#   plaquette sites [(r−1,c), (r,c), (r,c+1)]: B = Z_E(site1) · PZ(site2) · Z_N(site3)
STAR_A_mat() = kron(XN_mat(), PX_mat(), XE_mat())
PLAQ_B_mat() = kron(ZN_mat(), PZ_mat(), ZE_mat())

# ---------- exact toric-code tensor (V/P construction, PLAN §4.2 as amended) ----------
# Vertex simplex tensor V[n,e,s,w] = 1 iff n⊕e⊕s⊕w = 0 (parity enforcer).
# Edge copy tensor copies the virtual occupancy bit to the physical spin in the
# X basis: P[p,a,b] = (−1)^{p·a} δ_{a,b} / √2.
# RATIONALE: the Z-basis copy (δ_{p,a}δ_{a,b}) would build the Z-basis CYCLE gas —
# the toric code with stars↔plaquettes swapped (dual placement), for which our
# ⟨A_s⟩ = 0 (verified on finite patches). The X-basis copy gives the cycle gas in
# the X basis = the cut gas in the Z basis = ∏_s(1+A_s)|0⟩, the true TC ground
# state of our Hamiltonian (⟨A_s⟩ = ⟨B_p⟩ = 1).
# Merging the east/north copy tensors into the vertex gives the composite tensor
#   T[pE,pN,n,e,s,w] = (−1)^{pE·e + pN·n} · (n⊕e⊕s⊕w == 0)   [× normalization]

"Dense vertex simplex tensor V[n,e,s,w], indices ∈ {1,2} for bits {0,1}."
function simplex_V_dense()
    V = zeros(Float64, 2, 2, 2, 2)
    for n in 0:1, e in 0:1, s in 0:1, w in 0:1
        V[n + 1, e + 1, s + 1, w + 1] = iszero(n ⊻ e ⊻ s ⊻ w) ? 1.0 : 0.0
    end
    return V
end

"Dense edge copy tensor in the X basis: P[p,a,b] = (−1)^{p·a} δ_{a,b} / √2."
function copy_P_dense()
    P = zeros(Float64, 2, 2, 2)
    for p in 0:1, a in 0:1, b in 0:1
        P[p + 1, a + 1, b + 1] = (a == b) ? (-1.0)^(p * a) / sqrt(2) : 0.0
    end
    return P
end

"Contract V with two X-basis copy tensors (east and north edges) → composite tensor."
function exact_tensor_dense_VP()
    V = simplex_V_dense()
    P = copy_P_dense()
    T = zeros(Float64, 2, 2, 2, 2, 2, 2)  # [pE, pN, n, e, s, w]
    for pE in 0:1, pN in 0:1, n in 0:1, e in 0:1, s in 0:1, w in 0:1
        # merge east copy: sum over vertex e-leg a with P[pE,a,e]; north copy: P[pN,b,n]
        val = 0.0
        for a in 0:1, b in 0:1
            val += V[b + 1, a + 1, s + 1, w + 1] * P[pE + 1, a + 1, e + 1] * P[pN + 1, b + 1, n + 1]
        end
        T[pE + 1, pN + 1, n + 1, e + 1, s + 1, w + 1] = val
    end
    return T
end

"Closed-form composite tensor: T[pE,pN,n,e,s,w] = (−1)^{pE·e+pN·n}·δ_{n⊕e⊕s⊕w,0}/2."
function exact_tensor_dense()
    T = zeros(Float64, 2, 2, 2, 2, 2, 2)
    for pE in 0:1, pN in 0:1, n in 0:1, e in 0:1, s in 0:1, w in 0:1
        ok = iszero(n ⊻ e ⊻ s ⊻ w)
        T[pE + 1, pN + 1, n + 1, e + 1, s + 1, w + 1] = ok ? (-1.0)^(pE * e + pN * n) / 2 : 0.0
    end
    return T
end

"Exact composite tensor as a PEPSTensor (P ← N⊗E⊗S'⊗W', Z₂ self-dual).
Spaces default to the graded D=2 variant; pass (ℂ^4, ℂ^2) for ungraded."
function exact_peps_tensor(P = PSPACE, V = vspace(2))
    T = exact_tensor_dense_VP()  # user's V/P construction is primary
    @assert T ≈ exact_tensor_dense() "V/P contraction disagrees with closed form"
    # physical fused index order: (pE, pN) with pE fastest; reshape to (4, 2,2,2,2)
    A = reshape(T, 4, 2, 2, 2, 2)
    data = reshape(A, 4, 16)     # domain legs (n,e,s,w), n fastest
    return TensorMap(ComplexF64.(data), P, V ⊗ V ⊗ V' ⊗ V')
end

"Exact toric-code iPEPS on the (2,2) composite cell (all four tensors identical)."
exact_peps(P = PSPACE, V = vspace(2)) = InfinitePEPS(fill(exact_peps_tensor(P, V), 2, 2))

# ---------- Hamiltonian as PEPSKit LocalOperator on the (2,2) cell ----------
# Term ops are built in SORTED site order (add_term! sorts lexicographically).
#   star term on sites [(r,c−1), (r,c), (r+1,c)]:   −Jₑ · X_E ⊗ (X_E X_N) ⊗ X_N
#   plaquette term on sites [(r−1,c), (r,c), (r,c+1)]: −Jₘ · Z_E ⊗ (Z_E Z_N) ⊗ Z_N
#   field term on site (r,c): −hₓ (X_E+X_N) − h_z (Z_E+Z_N)

star_op(Je = 1.0, P = PSPACE) = phys_tmap(-Je .* STAR_A_mat(), 3, P)
plaq_op(Jm = 1.0, P = PSPACE) = phys_tmap(-Jm .* PLAQ_B_mat(), 3, P)
field_op(hx, hz, P = PSPACE) = phys_tmap(-hx .* (XE_mat() + XN_mat()) .- hz .* (ZE_mat() + ZN_mat()), 1, P)

"Empty LocalOperator on `lattice` (avoids a PEPSKit constructor recursion with zero terms)."
empty_localoperator(lattice) = LocalOperator{Any, eltype(lattice)}(lattice)

"""
Toric-code Hamiltonian on the (2,2) composite cell as a `LocalOperator`.
Returns (H, term_table) with the term table listing every term's kind, sites and
coefficient for cross-checks against the M1 incidence (ed_checks.jl).
"""
function toric_code_hamiltonian(hx, hz; Je = 1.0, Jm = 1.0, P = PSPACE)
    lattice = fill(P, 2, 2)
    H = empty_localoperator(lattice)
    table = NamedTuple[]
    s_op, p_op, f_op = star_op(Je, P), plaq_op(Jm, P), field_op(hx, hz, P)
    for r in 1:2, c in 1:2
        star_sites = [CartesianIndex(r, c - 1), CartesianIndex(r, c), CartesianIndex(r + 1, c)]
        PEPSKit.add_term!(H, copy(star_sites), s_op)  # add_term! sorts/shifts its argument in place
        push!(table, (kind = :star, center = (r, c), sites = Tuple(Tuple.(star_sites)), coeff = -Je))
        plaq_sites = [CartesianIndex(r - 1, c), CartesianIndex(r, c), CartesianIndex(r, c + 1)]
        PEPSKit.add_term!(H, copy(plaq_sites), p_op)
        push!(table, (kind = :plaquette, center = (r, c), sites = Tuple(Tuple.(plaq_sites)), coeff = -Jm))
        if hx != 0 || hz != 0
            PEPSKit.add_term!(H, [CartesianIndex(r, c)], f_op)
            push!(table, (kind = :field, center = (r, c), sites = ((r, c),), coeff = -hx))
        end
    end
    return H, table
end

# ---------- simple-update circuit ----------
# Star/plaquette gates are 3-site gates on L-shaped nearest-neighbor paths:
#   star path:      [(r,c−1), (r,c), (r+1,c)]  (bend at (r,c))
#   plaquette path: [(r−1,c), (r,c), (r,c+1)]  (bend at (r,c))
# The exponentiated Pauli-product gate is exact in closed form: for A² = I,
# exp(−dt·(−J·A)) = cosh(dt·J) + A·sinh(dt·J). At h = 0 all terms commute, so the
# circuit ordering carries no Trotter error; the only simple-update error is the
# bond truncation. Gates are converted to 3-site MPOs via PEPSKit's gate_to_mpo
# (the NNN code path); no BraidingTensor insertion is needed because the gate acts
# on all three path sites.

"Closed-form imaginary-time gate exp(dt·J·A) for a Pauli product A (A² = I), 3-site."
function pauli_gate3(A_op::TensorMap, dt, J)
    idop = TensorKit.id(domain(A_op))
    return cosh(dt * J) * idop + sinh(dt * J) * A_op
end

"Build the full SU circuit (stars + plaquettes + fields) for step dt on the (2,2) cell."
function build_su_circuit(dt; hx = 0.0, hz = 0.0, Je = 1.0, Jm = 1.0, P = PSPACE)
    lattice = fill(P, 2, 2)
    gates = Pair{Vector{CartesianIndex{2}}, Any}[]
    A_star = phys_tmap(STAR_A_mat(), 3, P)
    A_plaq = phys_tmap(PLAQ_B_mat(), 3, P)
    g_star = PEPSKit.gate_to_mpo(pauli_gate3(A_star, dt, Je))
    g_plaq = PEPSKit.gate_to_mpo(pauli_gate3(A_plaq, dt, Jm))
    for r in 1:2, c in 1:2
        star_path = [CartesianIndex(r, c - 1), CartesianIndex(r, c), CartesianIndex(r + 1, c)]
        push!(gates, star_path => g_star)
        plaq_path = [CartesianIndex(r - 1, c), CartesianIndex(r, c), CartesianIndex(r, c + 1)]
        push!(gates, plaq_path => g_plaq)
        if hx != 0 || hz != 0
            push!(gates, [CartesianIndex(r, c)] => exp(-dt * field_op(hx, hz, P)))
        end
    end
    return PEPSKit.LocalCircuit(lattice, gates)
end

"Initial SUWeight (unit Schmidt weights) for a PEPS on the (2,2) cell with bond space V."
function init_suweight(psi, V = vspace(2))
    one_wt() = DiagonalTensorMap(ones(dim(V)), V)
    wtx = [one_wt() for _ in 1:2, _ in 1:2]
    wty = [one_wt() for _ in 1:2, _ in 1:2]
    return PEPSKit.SUWeight(wtx, wty)
end

# ---------- ungraded (dense) variants for the symmetry-free SU test ----------
const UPSPACE = ℂ^4                # ungraded fused physical space (same layout)
uspace(D::Int) = ℂ^D               # ungraded virtual space
uenv(χ::Int) = ℂ^χ                 # ungraded CTMRG environment space

"""
Merged composite tensor from random vertex/projection tensors (user's split
construction, contracted): T[pE,pN,n,e,s,w] = Σ_{a,b} V[b,a,s,w]·PE[pE,a,e]·PN[pN,b,n].
All tensors drawn once and tiled uniformly (translation-invariant random init).
D=2 legs only (arrays sized 2); the general-D variant is inspection/d_sweep.jl's
`random_merged_tensor_VP_D`.
"""
function random_merged_tensor_VP(V_arr, PE_arr, PN_arr, P, Vsp)
    T = zeros(Float64, 2, 2, 2, 2, 2, 2)
    for pE in 0:1, pN in 0:1, n in 0:1, e in 0:1, s in 0:1, w in 0:1
        val = 0.0
        for a in 0:1, b in 0:1
            val += V_arr[b + 1, a + 1, s + 1, w + 1] *
                   PE_arr[pE + 1, a + 1, e + 1] * PN_arr[pN + 1, b + 1, n + 1]
        end
        T[pE + 1, pN + 1, n + 1, e + 1, s + 1, w + 1] = val
    end
    data = reshape(reshape(T, 4, 2, 2, 2, 2), 4, 16)
    return normalize!(TensorMap(ComplexF64.(data), P, Vsp ⊗ Vsp ⊗ Vsp' ⊗ Vsp'), Inf)
end
