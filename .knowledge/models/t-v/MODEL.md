# t-V

Solve spinless-fermion t-V ground-state problems. Density-density repulsion `V` competes with kinetic delocalization, driving charge order at strong coupling.

Distinguish from `t-J`: t-V has no spin index; t-J has projected spinful fermions with no double occupancy.

## Physics card

### Hamiltonian

$$ H = -t \sum_{\langle ij\rangle} \left( c^\dagger_i c_j + \text{h.c.} \right) + V \sum_{\langle ij\rangle} n_i n_j $$

Conventions: spinless fermions (one species, no spin index); `t > 0` (energy unit `t = 1`), `V > 0` nearest-neighbor repulsion (`V < 0` attractive); `⟨ij⟩` = NN bonds counted once. Half-filling is `N_f = N/2`; the particle-hole-symmetric form subtracts `(Vz/2)Σ n_i` (`z` = coordination). Under a Jordan–Wigner transformation the 1D chain maps exactly to the spin-½ XXZ chain with `Δ = V/2t` and `J_{xy} = 2t`. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain / quasi-1D ladder / 2D square (`Z=4`) / triangular (frustrated) | 1D chain is the exactly-tractable reference (→ XXZ). |
| A2 boundary conditions | OBC (DMRG) · PBC (ED/QMC) · cylinder (2D) | OBC gives Friedel oscillations; PBC needed for clean momentum sectors. |
| A3 statistics & local dim | spinless fermion; `d = 2` per site (empty / occupied) | The smallest fermionic local space — cheap per-site cost. |
| A4 interaction range | short-range: NN hopping + NN repulsion `V` (extended adds `V'`) | Local — area-law compatible. |
| B5 entanglement scaling | 1D: area+log (Luttinger liquid, `c=1`) for `V < V_c`; area law (gapped CDW) for `V > V_c` · 2D: area law | At half-filling the 1D transition (`V_c = 2t`, i.e. XXZ `Δ=1`) is BKT-type. |
| B6 spectral gap | 1D half-filling: gapless metal (`|V| < 2t`) / gapped CDW (`V > 2t`) · away from half-filling: gapless Luttinger liquid | Maps to the XXZ gap: gapless XY phase `|Δ|<1`, gapped Ising-AFM `Δ>1`. |
| B7 ground-state order | Luttinger liquid (metal) · **charge-density wave** at half-filling for `V > V_c=2t` · phase separation for `V < -V_c` (attractive) | CDW = staggered density `⟨n_i⟩ = n̄ ± δ(-1)^i`; the XXZ Ising-AFM Néel state. |
| B8 frustration | none on bipartite (chain, square) · geometric on triangular · fermionic sign on doping/2D | Bipartite half-filling is unfrustrated and sign-free. |
| C9 global symmetry | U(1)_charge (`N_f` conserved); particle-hole at half-filling on bipartite lattices | No spin SU(2) (spinless); JW image has only U(1) `S^z` (XXZ has no SU(2) except `Δ=1`). |
| C10 spatial symmetry | translation (`k`), inversion/parity, sublattice exchange (bipartite) | CDW spontaneously breaks the `Z_2` sublattice (translation by one site). |
| C11 integrability | 1D: **Bethe-ansatz integrable** (exact map to XXZ via Jordan–Wigner) · 2D/3D: non-integrable | 1D gives exact ground-state energy, gap, and `V_c=2t` from the XXZ solution. |
| C12 sign problem | 1D and 2D bipartite at half-filling: **sign-free** (particle-hole / bipartite) · doped / frustrated / non-bipartite: sign problem can appear | Sign-free half-filled bipartite case is QMC-exact at scale. |
| D13 regime | ground state (`T=0`) default; finite-T / dynamics out of card scope | `E/N` + charge structure factor `N(q)` are canonical targets. |
| D14 filling / doping | half-filling (CDW reference) is the symmetric point; doping → incommensurate Luttinger liquid | Commensurate half-filling is where the CDW can lock in. |
| D15 disorder | clean by default | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Luttinger liquid (metal) : `|V| < V_c = 2t` at half-filling (and generically off half-filling) — power-law density correlations, no gap; characterized by `K_ρ`.
- Charge-density wave (insulator) : `V > V_c = 2t` at half-filling — staggered density order parameter `m_{CDW} = (1/N)Σ_i (-1)^i ⟨n_i⟩`, peak in `N(q=π)`, finite charge gap. Maps to the XXZ Néel state for `Δ > 1`.
- Phase separation : strong attraction `V < -2t`.

### Canonical observables

- Ground-state energy per site `E/N`; density profile `⟨n_i⟩`.
- Charge structure factor `N(q) = (1/N)Σ_{ij} e^{iq(i-j)}⟨n_i n_j⟩_c`; CDW order parameter `m_{CDW}`.
- Charge gap `Δ_c = E(N_f+1)+E(N_f-1)-2E(N_f)`; Luttinger parameter `K_ρ`, central charge `c` (1D).

### Recommended methods

- Primary (1D / ladder): **DMRG/MPS** — near-exact in 1D, U(1) `N_f` conservation, small `d=2` (per `method-property-map.md` §MPS).
- Primary (2D bipartite half-filling, large `N`): **sign-free QMC** — bipartite particle-hole symmetry → numerically exact at scale (§QMC, C12).
- Cross-check: **ED** small-cluster oracle (§ED); for 1D, validate against the exact XXZ Bethe-ansatz energy/gap (C11).

### Key reference

[@voit_1995_one] — the authoritative review of 1D Fermi (Luttinger) liquids, covering the Luttinger-liquid universality class, the exact Bethe-ansatz solution, spin-charge separation, and the CDW/Mott alternatives — the all-details source for the gapless and CDW physics of 1D spinless-fermion (t-V) and related models.
Rendered: `./cond-mat-9510014_one-dimensional-fermi-liquids.md`.

### Benchmarks

- 1D half-filling, CDW transition: exact via the XXZ map (Jordan–Wigner, `Δ = V/2t`). The metal→CDW (BKT) transition sits at `Δ = 1`, i.e. `V_c = 2t`; for `V > 2t` the CDW gap opens exponentially (XXZ Ising-AFM gap), the Yang–Yang exact result (C. N. Yang & C. P. Yang, Phys. Rev. 150, 321 (1966)). Convention `H = -t Σ(c†c+h.c.) + V Σ n_i n_j`.
- 1D, `V = 0` (free fermions): exact tight-binding band, `E/N = -2t/π·sin(πn) → -2t/π ≈ -0.6366 t` at half-filling (`n=1/2`), the free-fermion limit benchmark (Voit review [@voit_1995_one], Luttinger-liquid `V→0` endpoint).

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** 1D chain, half-filling (N_f = N/2), V/t from the user's prompt (if not given, default V/t=2 — near CDW transition), OBC, N=20, target E/N + charge structure factor N(q).

**Proposal pattern:** "Going with: 1D chain, spinless fermions, half-filling, V/t=[value], OBC, N=20, target E/N + N(q). Override any, or pick: V/t scan (CDW transition), 2D geometry."

Build per `.knowledge/conventions.md`: `H = -t Σ (c†c + h.c.) + V Σ n_i n_j`.

## Workflow

1. Set up sites with fixed-`N_f` sector; fermion ordering convention explicit.
2. Pick method per the table.
3. First run; confirm particle number conserved, fermionic signs handled.
4. Sweep convergence parameter; track target observable.
5. Verify (next section).
6. If competing-order or critical-point physics emerges, hand off.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| Small chain or 2D cluster (N ≲ 24) | ED | `skills/method-ed/SKILL.md` |
| 1D chain (any N), ladder | DMRG | `skills/method-mps/SKILL.md` |
| Imaginary-time approach | TEBD | `skills/method-mps/SKILL.md` |
| Sign-problem-free 2D bipartite cases | QMC may be applicable; check sign condition before recommending. | — |

## Branch table

| Condition | Action |
|---|---|
| Lattice has frustration (triangular t-V, etc.) | Call `frustration` for regime classification. |
| User asks about the metal-CDW transition explicitly | Run the calculation here, then call `criticality`. |
| User wants spinful-fermion physics or doped Mott | Switch to `hubbard` or `t-j`. |

## Verification

Default checks:

- **Limit checks** via `.knowledge/limits.md`: `V = 0` → free fermions (exact tight-binding band); large `V` at half-filling → frozen CDW (alternating occupied/empty), so every NN bond has `n_i n_j = 0` and `E/N → 0` in this Hamiltonian's convention (`H = -tΣ + VΣ n_i n_j`); the particle-hole-symmetric form `VΣ(n_i-½)(n_j-½)` instead gives `E/N → -Vz/8` (= `-V/4` for the chain); particle-hole symmetry on bipartite lattices at half-filling.
- **Symmetry**: particle number conservation; lattice translation; sublattice exchange (bipartite).
- **Convergence**: bond-dim or basis-size sweep monotonic and asymptoting.
- **Internal consistency**: variance, density profile near edges (Friedel oscillations expected for OBC).
- **Cross-method validation** (when feasible) — re-run a small fixed-`N_f` cluster with an independent method, and check sign-problem-free QMC agreement when applicable. Use an ED cross-check via `/method-ed`. See AGENTS.md "Verification practice".

Optional check:

- Compare against published literature for the V=0 free-fermion limit and known integrable points.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then render it via `/report`. See AGENTS.md "Writeup handoff".

## Related skills

`frustration`, `criticality`, `hubbard` (spinful analog).
