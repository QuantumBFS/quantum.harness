# Kitaev chain (p-wave wire)

The spinless p-wave superconducting wire — the minimal model of a 1D topological superconductor. A BdG-quadratic (free-fermion) model, exactly solvable, hosting unpaired Majorana zero modes at its ends in the topological phase. Maps to the transverse-field Ising chain by Jordan–Wigner.

## Physics card

### Hamiltonian

$$ H = \sum_i \left[ -t\left(c^\dagger_i c_{i+1} + \text{h.c.}\right) - \mu\left(n_i - \tfrac12\right) + \Delta\left(c_i c_{i+1} + \text{h.c.}\right) \right] $$

Conventions: spinless fermions on a chain; `t > 0` hopping (energy unit `t = 1`), `μ` chemical potential (written particle-hole-symmetrically via `n_i − ½`), `Δ` the p-wave (nearest-neighbor) pairing amplitude (taken real). Topological for `|μ| < 2t` (with `Δ ≠ 0`), trivial for `|μ| > 2t`; bulk gap closes at `μ = ±2t`. The "sweet spot" `μ = 0, t = Δ` gives perfectly localized end Majoranas. See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | 1D chain | The defining model of a 1D topological superconductor. |
| A2 boundary conditions | OBC (Majorana end modes, ground-state parity degeneracy) · PBC (BdG Bloch bands, Z2 invariant) | OBC is essential to expose the Majorana zero modes; PBC for the bulk invariant. |
| A3 statistics & local dim | spinless fermion; `d = 2` per site; **BdG-quadratic** | Solved by Bogoliubov–de Gennes diagonalization (pairing → particle-hole-doubled single-particle problem). |
| A4 interaction range | short-range: NN hopping + NN p-wave pairing | Local; no interactions. |
| B5 entanglement scaling | area law (constant, gapped); ground-state fermion-parity (Majorana) degeneracy under OBC | Free-fermion ground state; the topological degeneracy is the entanglement/edge signature. |
| B6 spectral gap | gapped (bulk BdG gap) except at the transition `μ = ±2t` where the gap closes | Gap closing at `|μ| = 2t` is the topological phase transition. |
| B7 ground-state order | **1D topological superconductor** (class **D**, Z2 invariant) for `|μ| < 2t` vs trivial for `|μ| > 2t` | Topological phase: **Majorana zero modes** localized at the two ends; near-degenerate even/odd-parity ground states. |
| B8 frustration | none (free fermions) | — |
| C9 global symmetry | **fermion parity Z2** (`P = ∏(1−2n_i)`) — pairing breaks charge U(1); particle-hole (BdG) symmetry; time-reversal → class D | No charge conservation: superconducting pairing breaks U(1) down to Z2 parity. The two Majorana-degenerate ground states differ by total fermion parity. |
| C10 spatial symmetry | translation (`k`, PBC); inversion | Bulk Z2 invariant defined from the BdG Bloch Hamiltonian. |
| C11 integrability | **free-fermion / quadratic → exactly solvable** (BdG / Bogoliubov diagonalization, `O(N³)`) | Quadratic in the fermions; exact spectrum, edge modes, and phase diagram. |
| C12 sign problem | N/A — free fermions, no Monte Carlo required | — |
| D13 regime | ground state (`T=0`) default; quench / braiding dynamics also exactly tractable (quadratic) | Parity-resolved ground states and the Majorana spectrum are the targets. |
| D14 filling / doping | controlled by `μ` (no fixed filling — pairing does not conserve particle number); `μ = 0` is the particle-hole-symmetric sweet spot | `μ` is the tuning parameter across the topological transition, not a filling constraint. |
| D15 disorder | clean by default; on-site disorder (preserving class D) shifts but does not immediately destroy the topological phase | — |
| D16 hermiticity | Hermitian / closed | — |

### Phases & order parameters

- Topological superconductor (`|μ| < 2t`, `Δ ≠ 0`) : Z2 invariant nontrivial; under OBC, two **Majorana zero modes** (one at each end) combine into a single delocalized fermion → near-degenerate even/odd fermion-parity ground states. Diagnose by the bulk Z2 invariant, the OBC zero-mode spectrum, and the ground-state parity (near-)degeneracy.
- Trivial phase (`|μ| > 2t`) : trivial Z2 invariant; no Majorana end modes, unique ground state.
- Transition (`μ = ±2t`) : bulk gap closes.

### Canonical observables

- Bulk BdG band structure / gap; Z2 topological invariant.
- OBC end-mode spectrum (zero-energy Majoranas) and Majorana localization length.
- Ground-state fermion-parity (near-)degeneracy energy splitting (exponentially small in `N`).
- Majorana wavefunction profiles (perfectly localized at the sweet spot `μ=0, t=Δ`).

### Recommended methods

- Primary: **exact BdG / free-fermion diagonalization** — quadratic Hamiltonian solved in `O(N³)` (Bogoliubov transformation; Bloch BdG bands for the invariant, real-space Nambu matrix for the Majorana end modes), per `method-property-map.md` C11 free-fermion row.
- Cross-check: **ED** small-`N` (resolve the parity sectors and degeneracy); **DMRG/MPS** for the interacting Kitaev chain (NN repulsion breaks the free-fermion solution) and to confirm the topological degeneracy via entanglement. The Jordan–Wigner map to the transverse-field Ising chain (`transverse-field-ising`) gives an independent analytic benchmark.

### Key reference

[@kitaev_2000_unpaired] — Kitaev, "Unpaired Majorana fermions in quantum wires": the defining paper introducing the model, the topological vs trivial phases, the Majorana end modes, the bulk Z2 invariant, and the Jordan–Wigner connection to the Ising chain.
Rendered: `./cond-mat-0010440_unpaired-majorana-fermions-in-quantum-wires.md`.

### Benchmarks

- Topological phase: `|μ| < 2t` (with `Δ ≠ 0`); trivial for `|μ| > 2t`; bulk gap closes at `μ = ±2t` (convention `H = Σ −t(c†c+h.c.) − μ(n−½) + Δ(cc+h.c.)`) — Kitaev [@kitaev_2000_unpaired].
- OBC topological phase: a Majorana zero mode at each end; the two fermion-parity ground states are degenerate up to a splitting `∝ e^{−N/ξ}` (exponentially small in chain length).
- Sweet spot `μ = 0, t = Δ`: the end Majoranas are perfectly localized on the two terminal sites (zero localization length), exact zero-energy modes for any `N`.
- Jordan–Wigner: the chain maps onto the 1D transverse-field Ising model — the topological (`|μ|<2t`) phase corresponds to the Ising ordered (ferromagnetic) phase, the transition at `|μ|=2t` to the Ising critical point.

## How it is studied / Operational

**Canonical defaults (Diagnose):** spinless fermion chain, `(t, μ, Δ)` from the user's prompt (default `t = Δ = 1, μ = 0` — the sweet spot, deep topological), OBC to expose the Majorana end modes (plus a PBC run for the bulk Z2 invariant), `N = 40` sites, target the bulk gap + Z2 invariant + end-mode spectrum + ground-state parity degeneracy. If only "Kitaev chain" is given, propose one topological (`|μ|<2t`) and one trivial (`|μ|>2t`) parameter set and contrast their invariants and end spectra. The model is quadratic → all of this is an exact `O(N³)` BdG calculation; no variational or sampling method is needed.

| Regime | Method | Card |
|---|---|---|
| Bulk invariant / BdG bands / Majorana end modes (any size) | exact BdG / free-fermion diagonalization (`O(N³)`) | `skills/method-ed/SKILL.md` (quadratic / BdG) |
| Small-`N` cross-check, parity-resolved spectrum | ED | `skills/method-ed/SKILL.md` |
| Interacting Kitaev chain (NN repulsion) — free-fermion solution breaks | DMRG/MPS | `skills/method-mps/SKILL.md` |
| Independent analytic benchmark (Jordan–Wigner) | map to transverse-field Ising | `.knowledge/models/transverse-field-ising/MODEL.md` |

Verification pointers:

- Limit checks: sweet spot `μ=0, t=Δ` → perfectly localized terminal Majoranas, exact zero modes; `Δ=0` → ordinary free-fermion wire (no Majoranas); `|μ| ≫ t` → trivial. See `.knowledge/limits.md`.
- The bulk Z2 invariant (PBC) must match the OBC Majorana-end-mode count (bulk–boundary correspondence) — the central self-consistency check.
- Fermion parity `P` is conserved; in the topological phase the even/odd-parity ground states must be degenerate up to `e^{−N/ξ}` (check the splitting decays with `N`).
- Cross-check the phase boundary `|μ|=2t` and energies against the Jordan–Wigner-equivalent transverse-field Ising chain.
