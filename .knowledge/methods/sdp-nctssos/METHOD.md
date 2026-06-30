<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Certified Bounds — SDP / Moment-SOS Relaxations (NPA, NCTSSOS) & Bootstrap (sdp-nctssos)

Rigorous certified LOWER bounds on ground-state energies (and bounds on observables) via semidefinite relaxations of the noncommutative moment problem — the sign-immune complement to variational upper bounds.

## Method card

### What it is

The method constructs a hierarchy of semidefinite programs (SDPs) whose optimal values converge from below to the true ground-state energy. For a Hamiltonian `H` with local interactions, one writes the GS energy as a noncommutative polynomial optimization problem: minimize `⟨ψ|H|ψ⟩` subject to quantum-mechanical constraints. Truncating the moment hierarchy at level `k` (NPA/NCTSSOS) gives a relaxation whose solution is a rigorous LOWER bound. The moment matrix of size `O(N^k)` is the central SDP variable; interior-point solvers give the bound in polynomial time in the matrix size. Structured sparsity (NCTSSOS: term sparsity + correlative sparsity) and C9 symmetry block-diagonalize the problem, making large 1D/2D lattices tractable. The **bootstrap** variant additionally imposes positivity and crossing-equation consistency to two-sidedly constrain phase-diagram features without variational wavefunctions.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Rigorous GS energy lower bound · two-sided energy bracket (with VMC upper bound) · certified bounds on local observables and correlations · Bell-inequality bounds · bootstrap phase-diagram constraints | Primary niche: certifying that a VMC/DMRG energy is near-optimal. |
| M2 regime | T=0 ground state (GS energy certification) | Finite-T moment relaxations possible but less developed. |
| M3 accuracy class | Certified LOWER bound on the GS energy (complement to variational UPPER bound) | Rigorous; tightness improves with relaxation level `k`. |
| M4 dimension fit (A1) | 1D and 2D feasible; **3D blows up** | Moment matrix `O(N^k)` grows too large in 3D at practically useful `k`. |
| M5 statistics & local dim (A3) | Any algebra: Pauli (spin), fermion, boson | The noncommutative polynomial framework handles any algebra. |
| M6 entanglement regime (B5) | Sign-immune — not sampling-based; entanglement structure irrelevant to the SDP | The SDP sees only the algebraic constraints, not a wavefunction representation. |
| M7 sign-problem dependence (C12) | **Sign-immune** — works in C12 sign-ful / B8 frustrated regimes (no sampling, no sign problem); key niche | This is the critical advantage over QMC-based methods. |
| M8 symmetry exploitation (C9/C10) | C9 symmetry block-diagonalizes the moment matrix → large speedup; translation symmetry (C10) further reduces blocks | Symmetry is the primary route to tractability at useful `k`. |
| M9 time complexity | Relaxation level `k` → moment-matrix size `~ #monomials of degree ≤k = O(N^k)`; SDP solve is high-polynomial in that matrix size (interior-point). Structured sparsity (NCTSSOS, term/correlative sparsity) + symmetry (C9) shrink the blocks. | Tighter bound = higher `k` = rapidly growing SDP. |
| M10 memory | `O(N^{2k})` (moment matrix + dual SDP variables) | Dominant bottleneck; structured sparsity reduces effective block sizes. |
| M11 control knob | Relaxation level `k` — higher `k` → tighter (larger) lower bound → larger SDP | Error: gap between lower and upper bound narrows with `k`. |
| M12 scale frontier | ~100 sites (1D) / ~10×10 (2D) at practically useful `k` with NCTSSOS sparsity + symmetry | `k=2` tractable for moderate `N`; `k=3` requires structured sparsity. |
| M13 primary approximation / bias | Relaxation level `k` — lower `k` gives looser (less tight) lower bound | Controlled: increasing `k` systematically tightens the bound. |
| M14 hard blocker / failure mode | 3D blows up (moment matrix too large); large `k` in 2D requires heavy HPC; gap between lower and upper bound may remain non-negligible at accessible `k` | Pair with VMC/DMRG for the upper bound to bracket the true GS energy. |

### Cost & scaling

- Time: high-polynomial in moment-matrix size `O(N^k)` (interior-point SDP); structured sparsity (NCTSSOS) reduces effective blocks
- Memory: `O(N^{2k})` for the moment matrix; structured sparsity critical for large systems
- Control knob: relaxation level `k` — controls bound tightness (systematic improvement)
- Scale frontier: ~100 sites (1D) / ~10×10 (2D) at useful `k` with symmetry + NCTSSOS sparsity

### Accuracy & guarantees

- Class: certified LOWER bound (rigorous, not variational)
- Primary approximation & its control: relaxation level `k`; increasing `k` monotonically tightens the bound
- Error scaling: bound gap closes as `k→∞` (convergent hierarchy, Pironio–Navascués–Acín 2010 [@pironio_2010_convergent] (noncommutative polynomial optimization convergence result, SIAM J. Optim. 20, 2157))

### Tasks it computes

- Rigorous GS energy lower bound (the certified complement to VMC/DMRG upper bounds)
- Two-sided energy bracket: `E_lower (SDP) ≤ E_GS ≤ E_upper (VMC)`
- Certified bounds on local observables (magnetization, correlation functions)
- Bell-inequality bounds and device-independent quantum information tasks
- Bootstrap phase-diagram constraints via positivity + consistency conditions

### Recommended for (models / regimes)

- **Frustrated magnets (B8) and sign-ful (C12) models:** the only method that certifies lower bounds without a sign problem (Heisenberg kagome, triangular, J₁-J₂ models)
- **Certification of variational results:** pair with VMC/NQS or DMRG to bracket the GS energy
- **1D/2D lattice models with symmetry:** use C9 block-diagonalization to make `k=2,3` tractable
- Per `method-property-map.md`: niche method for sign-immune certification; complements all variational methods

### Key reference

[@wang_2024_certifying] — demonstrates NCTSSOS-based certified lower bounds on GS energies of 1D and 2D Heisenberg models; the primary reference for the practical NCTSSOS + symmetry workflow.
Rendered: `../../literature/polynomial-optimization/2310.05844_certifying-ground-state-properties-of-many-body-systems.md` _(reused)_.

[@pironio_2010_convergent] — proves convergence of the NPA/moment relaxation hierarchy for noncommutative polynomial optimization; the mathematical foundation for the certified-lower-bound guarantee.
Rendered: `../../literature/polynomial-optimization/0903.4368_convergent-relaxations-of-polynomial-optimization-problems-w.md` _(reused)_.

### Benchmarks

- 1D Heisenberg chain: certified lower bound matches exact GS energy to `<0.01%` at `k=2` with NCTSSOS sparsity [@wang_2024_certifying].
- 2D `10×10` Heisenberg: tight two-sided bracket combining SDP lower + VMC upper bounds [@wang_2024_certifying].
- Convergence of NPA hierarchy: guaranteed by Pironio–Navascués–Acín (2010) [@pironio_2010_convergent]; verified in `method-survey.md` §7.6.

## How it is used / Operational

**Owning skill:** `/method-polyopt` (primary); `/using-nctssos` (NCTSSOS Julia package); `/using-qmbcertify` (QMB certification workflow).

**Default workflow:**
1. Express the Hamiltonian as a noncommutative polynomial in Pauli / fermion / boson operators.
2. Choose relaxation level `k`; enumerate monomials of degree `≤k` to build the moment matrix (size `O(N^k)`).
3. Apply NCTSSOS term-sparsity + correlative-sparsity reduction and C9 symmetry block-diagonalization.
4. Solve the SDP (MOSEK or SCS interior-point solver); extract the certified lower bound.
5. Pair with VMC/DMRG upper bound to form a two-sided energy bracket.

**Verification pointers:**
- At small `N`, compare SDP lower bound with ED exact GS energy.
- Verify monotone improvement: `E_lower(k) ≤ E_lower(k+1) ≤ E_GS` as `k` increases.
- Check SDP feasibility and dual certificate for numerical reliability.

**Cross-links:**
- Survey: `method-survey.md` §7.6 (Certified bounds — SDP / moment-SOS relaxations)
- Model↔method gate: `method-property-map.md` (sdp-nctssos profile)
- Complementary methods: VMC/NQS (variational upper bound, pairs with SDP lower bound), ED (oracle for small-system verification), AFQMC (sign-ful ground states where SDP certifies)
