# THEOREM_CONTRACT — RG × bundle-selection joint model
(G0 artifact, written BEFORE solver code. Numerical gates are echoes of
these statements, never substitutes. Inherits LAW.md; extends
cg_hybrid/THEOREM_CONTRACT.md §1/§4, which remain in force.)

## §1 Spaces and ordered bases

Setting: N-site spin-1/2 ring, H = Σ h_{i,i+1}, h = ¼Σ_a σᵃσᵃ, energies
per site. Canonical words = QMBCertify `reduce!` classes (translation,
mirror, S₃ Pauli permutation, sign symmetry) at commit be63c27.

- **Mandatory basis** 𝔅(N) = get_basis families at BASE_CONFIG
  (1-site; 2-site sep ≤ r(N); 3-site three_type; 4-site a2).
- **Bundle closures** cl(B) for B in the pool: the orbit of B's defining
  words under translation, reflection, Hermitian conjugation, spin-
  component (S₃) orbit, Pauli quotient — represented by CANONICAL
  REPRESENTATIVES only (never materialized ×N).
- **Coefficient space** V_pool(N) = span{ [u†v] : u,v ∈ 𝔅(N) ∪ ⋃_B cl(B) }
  / ideal (Pauli algebra + ring symmetry). Ordered basis: sorted
  canonical words (the tsupp order of the builder). V_S(N) analogous
  with only S's closures. y ∈ ℝ^{V}: TI moment vector, y_∅ = 1;
  physical value y_w = ⟨w⟩_ρ.
- **Level-3 compressed space** X₃(N): coordinates x³ = Hermitian-basis
  coefficients of ω-objects obtained by applying the D=4 parity-resolved
  VUMPS chain map C (vumps_A_D4.json, unmodified) to 3-cluster physical
  objects. dim X₃ is N-independent (map-rank bounded), code-generated.

## §2 Operators (domains → codomains; matrices code-generated, hashed)

- Q₂ : ℝ^{V} → Herm(O_S)-coords — picks y-entries for the level-2
  selected moment matrix Γ_{2,S}(Q₂y)[u,v] = c_{uv}·y_{[u†v]}, u,v ∈
  O_S = 𝔅₂(N) ∪ ⋃_{B∈S} cl(B), with c_uv the reduce! coefficient of
  u†v (algebra coefficient; realification per source conventions).
- B₂ : Herm(O_S)-coords → ℝ^{L} — boundary/overlap functionals of the
  level-2 data that the compressed level-3 object must reproduce
  (rows = Hermitian coordinates of traced windows, exactly the T2
  pattern of cg_hybrid/THEOREM_CONTRACT §2).
- T₃ : X₃ → ℝ^{L} — the corresponding functionals of x³ through the
  compression map.
- Compatibility identity (code echo, gate G2): ‖B₂C₁T₃ − T₃′C₂‖_max ≤
  1e-12 where C₁,C₂ are the map's parity-resolved cluster actions — the
  algebraic statement that both routes compute the SAME physical
  overlap.

## §3 The four arms and feasible-set inclusions

F_base(N) ⊇ F_sel(N,S) , F_base(N) ⊇ F_RG(N) , and
F_joint(N,S) = F_sel ∩ F_RG. Each optional family is a VALID constraint
system for physical TI states:

**Lemma A (selection validity).** For physical ρ, Γ_{2,S}(Q₂y) is a
principal submatrix (in the canonical-class quotient) of the full moment
matrix M(y) ⪰ 0, hence ⪰ 0. ∎

**Lemma B (RG validity).** x³(ρ) = coords(C M₃(ρ) C†) with M₃(ρ) ⪰ 0 and
C the fixed chain map: congruence preserves PSD, so Γ₃(x³) ⪰ 0; the link
B₂Q₂y = T₃x³ holds because both sides evaluate the same traced physical
overlaps (Lemma 1 + Lemma 2 of cg_hybrid/THEOREM_CONTRACT, applied to
the D=4 parity-resolved map; n_levels ≤ N−1 respected). ∎

**Theorem (orderings).** F_physical ⊆ F_joint ⊆ F_sel/F_RG ⊆ F_base ⇒
L_base ≤ L_RG ≤ L_joint, L_base ≤ L_sel ≤ L_joint, L_joint ≤ E0/N.
Monotone in S: S ⊆ S′ ⇒ L_sel(S) ≤ L_sel(S′), L_joint(S) ≤ L_joint(S′)
(within ε_cmp numerically; gate G3). ∎

**Neutrality (gate G1b).** On V_pool with S = ∅ and RG off, the extra
coordinates appear in NO constraint and NO objective term ⇒ the optimum
equals the stock-adapter value exactly (≤1e-8 numerically).

## §4 Exact dual identity implemented (the ONLY seam)

At the GSB_cg coefficient-matching seam (cons == 0 over tsupp of the
arm's coefficient space), the extension is the KKT dual of §3's primal:

- Γ_{2,S}(Q₂y) ⪰ 0  →  new Gram-type PSD variable G_S ⪰ 0;
  cons[w] += Σ_{(u,v): [u†v]=w} c_uv · G_S[u,v]   («gramblocks» field:
  entries (w,i,j,c); hard error if w ∉ tsupp).
- link rows B₂Q₂y − T₃x³ = 0 → free multipliers μ;
  cons[w] += (Q₂*B₂*μ)_w  («ycoef» field, existing consumer).
- Γ₃(x³) ⪰ 0 → dual block Z₃ := mat(−T₃*… μ) ⪰ 0 in the real Hermitian
  embedding («zblocks» field, existing consumer; minus sign per the
  cg_hybrid KKT derivation, unchanged).
- Objective unchanged (homogeneous rows; y_∅ coefficient rides in
  cons[1]); brows emitted explicitly (expected empty).

Weak duality ⇒ every reported number is a numerical SDP lower bound up
to solver residuals; all Δ classification via ε_cmp (LAW.md).

## §5 Bundle definitions and dimension formulas (exact counts
code-generated at build; asserted at G3)

| bundle | defining words | canonical classes (pre-closure) |
|---|---|---|
| B_pair_edge | σᵃᵢσᵃᵢ₊ₛ, s=r(N)+1 | 1 (S₃+translation quotient) |
| B_half | σᵃᵢσᵃᵢ₊⌊N/2⌋ | 1 |
| B_bond_edge | bᵢbᵢ₊ₛ, s=r(N)+1 | ≤3 σ-classes (aa·aa / aa·bb quotient) |
| B_bond_half | bᵢbᵢ₊⌊N/2⌋ | ≤3 |

Non-collapse: pair separations r(N)+1 > r(N) and ⌊N/2⌋ > r(N) for all
N ∈ {10,12,14,200} (2-body mandatory reach is r(N)); bond-bond words are
4-body on site sets {i,i+1,i+s,i+s+1}, disjoint-from-a2 (consecutive
quadruples) whenever s ≥ 3 = r+1 ✓, and not 3-body/1-site. Pairwise
distinct: s = r(N)+1 ≠ ⌊N/2⌋ at every N in use (3≠5,3≠6,3≠7,25≠100).
CODE re-asserts all of this at pool build (gates.json).

Γ_{2,S} block dimension |O_S| ≤ |𝔅₂| + Σ_{B∈S}|cl(B)| — tens of rows at
K ≤ 3. Cost driver is |V(S)| (new product classes), code-generated per
S with: Gram rows, PSD scalars, coefficient entries, affine nnz,
largest-block delta.

## §6 Production complexity statement

All builder objects are indexed by canonical representatives (reduce!
quotient). Build cost and memory are polynomial in the representative
count; N enters only through separation arithmetic (r(N), ⌊N/2⌋) and
ring modular arithmetic — never through 2^N/4^N objects (gate G1c
asserts the counters). Dense ED appears exclusively in N ≤ 14
validation references. The N=200 path executes the identical code with
different separations and the S*-restricted space V_{S*}(200).
