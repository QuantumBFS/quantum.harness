# Transverse-Field Ising

Solve transverse-field Ising ground-state problems. Lattice and `Γ/J` ratio determine method choice and what physics is accessible.

## Physics card

### Hamiltonian

$$ H = -J \sum_{\langle ij\rangle} \sigma^z_i \sigma^z_j - \Gamma \sum_i \sigma^x_i $$

Conventions: Pauli-matrix notation (`σ^a`, not `S^a`); `J > 0` ferromagnetic Ising coupling, `Γ ≥ 0` transverse field; `J = 1` sets the scale and `Γ/J` is the control parameter (some references write `h` for `Γ`). See `.knowledge/conventions.md` (Pauli vs `S` factor of 4 per bond).

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain (`Z=2`) · 2D square (`Z=4`) · higher-D | The canonical 1D quantum-critical model; 2D is Wilson–Fisher 3D-Ising universality. |
| A2 boundary conditions | OBC (DMRG) · PBC (ED, free-fermion) · cylinder (2D) | PBC matters for the exact Jordan–Wigner mapping. |
| A3 statistics & local dim | spin-1/2; `d = 2` | Maps to free fermions in 1D via Jordan–Wigner. |
| A4 interaction range | short-range (nearest-neighbor); long-range `1/r^α` variant | Long-range version inflates bond dimension (use TDVP). |
| B5 entanglement scaling | gapped phases: area law (const in 1D) · 1D critical `Γ=J`: area+log, `c=1/2` | `c=1/2` is the Ising-CFT central charge (one Majorana). |
| B6 spectral gap | gapped FM (`Γ<J`) and PM (`Γ>J`) · gapless at the QCP `Γ=J` (1D) | Quantum critical point separates ordered and disordered phases. |
| B7 ground-state order | FM (`Γ<J`): `Z_2` SSB · PM (`Γ>J`): trivial paramagnet | Order parameter `⟨σ^z⟩` onsets below the critical field. |
| B8 frustration | none on bipartite FM · geometric if AFM on triangular | Default FM is unfrustrated. |
| C9 global symmetry | `Z_2` spin-flip (`P = Π_i σ^x_i`, parity) | The symmetry whose breaking defines the FM phase. |
| C10 spatial symmetry | translation (`k`), inversion/parity | Conserved momentum in PBC. |
| C11 integrability | free-fermion / quadratic (1D, exact via Jordan–Wigner) · 2D non-integrable | 1D diagonalizable in `O(N)`/`O(N³)`; the textbook exactly-solvable QPT. |
| C12 sign problem | sign-free (ferromagnetic / bipartite → QMC applicable) | SSE/QMC works at scale; 1D is exact anyway. |
| D13 regime | ground state (`T=0`) + gap; dynamics/finite-T out of card scope | `E/N` and gap are canonical targets. |
| D14 filling / doping | N/A (spin model) | After Jordan–Wigner: free fermions at fixed filling. |
| D15 disorder | clean by default; random-bond/field → infinite-randomness fixed point | Disordered 1D TFIM is the canonical strong-disorder RG example. |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Ferromagnet (`Γ < J`) : `Z_2`-broken; order parameter `⟨σ^z⟩ ≠ 0` (magnetization).
- Paramagnet (`Γ > J`) : trivial, field-polarized along `x`, `⟨σ^z⟩ = 0`.
- Quantum critical point (1D `Γ = J`) : Ising CFT, `c = 1/2`, exponents `ν = 1`, `β = 1/8`, `z = 1`.

### Canonical observables

- `E/N`; spectral gap `Δ` (closes at the QCP).
- Magnetization `⟨σ^z⟩` (order parameter); longitudinal correlations `⟨σ^z_i σ^z_j⟩`.
- Central charge `c` from entanglement scaling at criticality.

### Recommended methods

- Primary (1D): **DMRG/MPS** — area-law / area+log ground state, near-exact; `Z_2` parity sector reduces cost (per `method-property-map.md` §MPS).
- Primary (2D): **sign-free QMC** (SSE) — unfrustrated, exact at scale; or DMRG on cylinders.
- Cross-check: **ED** small clusters; 1D **free-fermion** exact diagonalization (Jordan–Wigner) as an analytic oracle.

### Key reference

[@dutta_2010_quantum] — comprehensive downloadable review of quantum phase transitions in transverse-field spin models (1D exact solution, scaling, higher-D, dynamics, quantum information), preferred over the Sachdev textbook for an all-details source.
Rendered: `./1012.0653_quantum-phase-transitions-in-transverse-field-spin-models-fr.md`.

### Benchmarks

- 1D chain QCP: `Γ_c/J = 1` exactly (self-dual / Jordan–Wigner); at criticality `c = 1/2`, `ν = 1`, `β = 1/8`. Ground-state energy density at `Γ = J = 1`: `E/N = −4/π ≈ −1.2732` (Pauli convention `H = −J Σ σ^z σ^z − Γ Σ σ^x`; from the free-fermion dispersion, consistent with this card's Verification note).
- 2D square FM TFIM: critical field `(Γ/J)_c = 3.04438(2)`, 3D-Ising universality (Blöte & Deng, Phys. Rev. E 66, 066110 (2002)).

## Diagnose

Infer setup from the user's prompt and propose for ratification.

**Canonical defaults:** 1D chain, ferromagnetic J=1, Γ=1 (critical point), OBC, N=20, target E/N + gap.

**Proposal pattern:** "Going with: 1D chain, J=1, Γ=1 (critical), OBC, N=20, target E/N and gap. Override any, or pick: Γ/J scan (phase diagram), 2D square lattice."

Build per `.knowledge/conventions.md`: `H = -J Σ σ^z_i σ^z_j - Γ Σ σ^x_i`.

## Workflow

1. Set up sites (Z2 symmetry sector, parity) and Hamiltonian per conventions.
2. Pick method per the table.
3. First short run; verify the parity sector and that the calculation respects Z2 if no field-breaking term is present.
4. Sweep convergence parameter until the target observable stabilizes.
5. Verify (next section).
6. If the target is critical behavior, hand off to `criticality`.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| 1D chain (any N) | DMRG | `skills/method-mps/SKILL.md` |
| Tiny cluster (N ≲ 24), exact spectrum, debugging | ED | `skills/method-ed/SKILL.md` |
| Cylinder (square / triangular strips) | DMRG | `skills/method-mps/SKILL.md` |
| Imaginary-time approach | TEBD | `skills/method-mps/SKILL.md` |

## Branch table

| Condition | Action |
|---|---|
| Question is about quantum critical behavior at `Γ ≈ J` (1D) or the equivalent transition | Run the calculation here, then call `criticality`. |
| Question is about confinement / deconfinement (2D `Z_2` lattice gauge theory ↔ 2D Ising via Wegner duality) | Run on the dual 2D Ising here (Wegner duality preserves the relevant diagnostics); hand off to `.knowledge/physics/confinement/PHYSICS.md`. |
| Long-range Ising (e.g., `1/r^α`) | Stay here; flag that bond dimension grows; document. |
| User asks about dynamics | Out of current scope. |
| User asks about finite-T | Out of current scope. |

## Verification

Default checks (all auto-run; results aggregated into the report's verification line):

- **Limit checks** via `.knowledge/limits.md`:
  - 1D: at `Γ = 0`, ground state is a classical Ising ferromagnet (or antiferromagnet) with energy `E/N = -J z / 2` (`z` = coordination); at `J = 0`, ground state is fully polarized along `x` with `E/N = -Γ`.
  - 2D: at `h ≪ J`, ground state is the all-aligned ferromagnet `|↑…↑⟩` (a +1 eigenstate of all `σ^z`); at `h ≫ J`, ground state is the all-aligned paramagnet `|+…+⟩` (a +1 eigenstate of all `σ^x`). Energy limits track the dominant single-site contribution at each endpoint.
- **Symmetry**: Z2 (`σ^z → -σ^z`) should be respected; spontaneous breaking shows only with explicit symmetry-breaking field at finite size.
- **Convergence**: bond-dim sweep gives a monotonic, asymptoting energy curve.
- **Internal consistency**: energy variance small relative to E².
- **Cross-method validation (auto-paired when available)** — use TEBD, DMRG, or TTN cross-checks first. Use an ED cross-check via `/method-ed`.

Optional check:

- Compare against published literature for canonical lattices when a reference exists. For 1D chain at criticality (`Γ = J`): exact `E/N = -4/π ≈ -1.2732` (free-fermion via Jordan-Wigner; convention-dependent).

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then render it via `/report`. See AGENTS.md "Writeup handoff".

## Related skills

`criticality` (for the QPT at `Γ = J` and its higher-D analogues).
