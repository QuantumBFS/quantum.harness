# THEOREM_CONTRACT — soundness of the NPA + ω-tower hybrid

Blocking artifact before any M2 arm (plan correction 2). Numerical gates in
`tower.jl` are echoes of these statements, never substitutes.

Setting: N-site spin-1/2 ring, H = Σᵢ h_{i,i+1}, h = ¼ Σ_a σᵃ⊗σᵃ (J₂ = 0
case; the J₁-J₂ extension replaces h by the 3-site density and changes
nothing structural). Energies per site. Words w are canonical Pauli words
(translation/mirror/algebra canonicalization = QMBCertify `reduce!`); y_w
denotes the moment ⟨w⟩ of a translation-invariant (TI) state, y_∅ = 1.

## §1 Shared primal baseline

GSB at knob vector κ (chain, energy mode) assembles the SOHS-side model
(RECON M0-A); its primal is the moment SDP

    E_base(κ) = min_y  Σ_w h_w y_w
                s.t.   y_∅ = 1,
                       M_b(y) ⪰ 0  for every Gram block b of κ
                       (incl. the rdm-k U(1) blocks when rdm ∈ {8,10},
                        and the pso blocks when pso > 0),
                       A_lso y = 0  when lso = true.

F_base(κ) ⊂ ℝ^{tsupp} is its feasible set. Both stock and hybrid arms in M2
use the SAME κ-baseline (same tsupp, same blocks); the hybrid only adds
constraints. Weak duality: any feasible point of GSB's dual has value
≤ E_base(κ); Mosek's reported optimum is such a value up to the feasibility
residuals folded into ε_cmp.

## §2 F_physical ⊆ F_hybrid

**Tower data.** A tensor family {B: ℂ^m ⊗ ℂ^d → ℂ^m} (uMPS tensor, [B]
Eq. 2.13) defines chain maps W_k: (ℂ^d)^⊗k → ℂ^m ⊗ ℂ^m (open boundary
bonds) and the CP maps 𝒞_M(X) = (I_d ⊗ W_{M−2} ⊗ I_d) X (·)† ([B] Eq. 2.14).
The lossless oracle replaces W₂ by an explicit unitary (χ = d² = 4).

**Tower variables and constraints** (all linear; [B] Eqs. 2.15/2.16 as
decoded from the rendered equations):

    (T0) ρ₂, ρ₃ Hermitian, ρ₂ = P₂(y), ρ₃ = P₃(y)   [P_M = Pauli expansion
         of the M-site contiguous marginal; every word touched must exist in
         tsupp — build-time hard assert, no silent drops]
    (T1) Tr_L ρ₃ = Tr_R ρ₃ = ρ₂
    (T2) Tr_{J,μ_M}(ω₄) = (I ⊗ 𝒲_R)(ρ₃),  Tr_{I,μ₁}(ω₄) = (𝒲_L ⊗ I)(ρ₃)
         where 𝒲_R(·) = Tr_J[W₂ (·) W₂†] on sites (2,3), mirror for 𝒲_L
    (T3) for 4 ≤ M < n_tower:
         Tr_{right pair}(ω_{M+1}) = 𝓡(ω_M),  Tr_{left pair}(ω_{M+1}) = 𝓛(ω_M)
         with 𝓡(X) = Tr_out[B X_{(J,μ_M)} B†] (one B tensor), mirror 𝓛
    (T4) ρ₂, ρ₃, ω_M ⪰ 0 for M = 4 … n_tower

**Lemma 1 (ring marginals satisfy chain-LTI).** Let ρ be any TI state of the
N-ring and, for M ≤ N−1, let ρ_M be its marginal on M consecutive sites
(well-defined by translation invariance). Then Tr_L ρ_M = Tr_R ρ_M = ρ_{M−1}
for 3 ≤ M ≤ N−1. *Proof:* Tr_L ρ_M and Tr_R ρ_M are both marginals of ρ on
M−1 consecutive sites, related by a one-site translation; TI identifies
them with ρ_{M−1}. ∎ (No M = N wraparound is ever used; the generator
asserts n_tower ≤ N−1.)

**Lemma 2 (flow composition).** W_{k+1} = (B acting on the right bond ⊗ new
site) ∘ (W_k ⊗ I_d), and the mirror identity on the left. *Proof:*
associativity of tensor contraction of the B-chain. Verified in code as a
matrix identity, residual gate ≤ 1e-12 — the gate checks the CODE's index
conventions, the identity itself is exact. ∎

**Theorem 1 (validity).** For every TI state ρ of the N-ring with
n_tower ≤ N−1, the assignment y = moments(ρ), ρ_M = marginal_M(ρ),
ω_M = 𝒞_M(ρ_M) satisfies (T0)–(T4). *Proof:* (T0) by definition of
marginals; (T1) Lemma 1; (T2)/(T3): apply 𝒞 to both sides of Lemma 1's
equalities and use Lemma 2 to re-express the traced coarse maps — these are
exactly [B] 2.15/2.16; (T4): CP maps preserve positivity (no isometry or
trace preservation needed for validity). ∎

**Corollary (F_physical ⊆ F_hybrid).** F_hybrid(κ, tower) := {y : ∃ ω with
(y, ω) satisfying F_base(κ) ∧ (T0–T4)} contains every physical TI moment
vector. Since ground states of TI ring Hamiltonians may be chosen TI
(translation-averaging preserves energy), min over F_hybrid ≤ E0/N. ∎

## §3 E_base ≤ E_hybrid ≤ E0

F_hybrid(κ, tower) ⊆ F_base(κ) (the hybrid adds constraints and projects
out ω). Minimization over a smaller set can only increase:
E_base(κ) ≤ E_hybrid(κ, tower). With the §2 corollary:

    E_base(κ)  ≤  E_hybrid(κ, tower)  ≤  E0/N.

This is the exact-arithmetic ground for M2's sign rules: ΔCG8 ≥ 0 and
ΔCG10 ≥ 0 (same κ, tower added). Δreplace compares different κ (rdm=8+tower
vs rdm=10, neither feasible set contains the other) and carries NO sign
constraint — a negative value is a valid measurement.

## §4 The implemented dual extension is the dual of this primal tower

Write the tower equalities (T0–T3) as A_y y + A_ω vec(ω) = 0 (rows indexed
by tower-constraint entries; T0's inhomogeneous part is absorbed by y_∅ = 1
through the shared `cons[1]` slot). Extended primal Lagrangian with
multipliers μ (free, per row), dual blocks Z_M ⪰ 0 for ω_M ⪰ 0, and the
existing GSB dual structure gives the KKT stationarity:

  * ∂/∂y_w:  the coefficient-matching identity per word w acquires the term
    (A_yᵀ μ)_w — implemented as `add_to_expression!(cons[bfind(tsupp,w)], …)`
    at the RECON §M0-B insertion point (between `bound_gsp.jl:578` and
    `:579`);
  * ∂/∂vec(ω_M):  (A_ωᵀ μ)|_M + vec(Z_M) = 0, i.e. the μ-affine matrix
    Z_M := −mat_M(A_ωᵀ μ) is constrained ⪰ 0 — the "new PSD dual blocks";
  * the objective is unchanged (homogeneous rows), and any inhomogeneous
    row must contribute its b·μ term explicitly (generator-emitted, never
    assumed zero).

**Weak duality (soundness of every reported number):** for any dual-feasible
point (Gram, fr, μ, Z), its value ≤ E_hybrid ≤ E0/N. Solver output is
therefore a numerical SDP lower bound up to feasibility residuals; all Δ
classification goes through ε_cmp, never a bare tolerance.

**Non-claims (carried from LITERATURE_CONTRACT):** nothing here accelerates
the stock rdm=10 construction; no challenge-target claim follows from this
contract; the tower is a "constraint-family complementarity hypothesis"
until M2 measures it.
