---
name: magic
description: Use when the user is asking about many-body magic, nonstabilizerness, stabilizer Rényi entropies, Pauli weight distribution, long-range magic, mutual magic, Pauli-MPS lift, Bell magic, stabilizer nullity, or any nonstabilizerness monotone — including any "how non-Clifford is this state?" question across spin / fermion / gauge models.
---

# Magic

Diagnose nonstabilizerness on a concrete model. Compute the relevant magic measure, place it in context (peak / crossing / plateau / extremum), and identify what physical structure it is detecting (criticality, topological phase, confinement transition, or a basis-dependent baseline).

## Diagnose

Infer the diagnostic framing from the user's prompt and propose it for ratification.

**Canonical framing:** "You're asking about magic in [model on lattice] across [parameter range]. I'll treat this as: pick the partition mode (full / disjoint-bipartite / increment), pick `n` (default `n=1` for a strict monotone in any regime; `n=2` for experimental relevance), run Pauli-Markov sampling, then place the result against the limit checks. The model skill driving the wavefunction is [model skill]."

If the user already has data, adjust: "You have [observable at sizes / parameter values]. I'll evaluate it against the magic checklist and recommend the next computation."

Do not ask 5 questions. Propose the framing; let the user correct if wrong.

**Default partition mode:** *full state* `M_n` for a generic "is this state magic?" question; *disjoint bipartite* `L(ρ_AB)` whenever criticality is the question (long-range magic is UV-finite and works across 1D Ising, Potts, and spin-1 XXZ where full-state magic fails); *halving increment* whenever volume-law `M_n>1` makes the direct estimator exponentially expensive.

## Evidence to gather

For each item, the relevant model skill drives the wavefunction calculation; this skill specifies *what to compute* and *what to look for*. Definitions live in `knowledge-base/magic-conventions.md`.

- **`m_n` density across the parameter axis** — peak, plateau, crossing, or featureless. Match against the expected critical / topological structure of the model.
- **Long-range magic `L(ρ_AB)`** — extremum (peak or minimum) at criticality; decays away from criticality. Use disjoint subsystems with separation greater than the correlation length away from the critical regime. Also called *mutual magic* in the literature.
- **Increment / subleading term `c_N`** — `c_N = 2 M_n(N/2) − M_n(N)` in 1D, with higher-D analogues. Cancels volume-law to expose `O(log N)` or `O(1)` substructure with polynomial sample cost.
- **Single-site / single-qudit baseline** — analytic magic of a product state of single qudits in the same basis; the difference is the genuinely many-body magic content.

**Alternative monotones** (orthogonal to SRE; access via the deterministic Pauli-basis MPS lift on `knowledge-base/methods/pauli-markov.md`):

- **Bell magic** — additive monotone defined on the Bell-pair-doubled state; vanishes on stabilizer states and is *strictly monotone* under stochastic free operations including for orders below the SRE-monotonicity threshold. Captures total nonstabilizer content with a different normalization than `M_n`. Useful when the question is monotone-rigorous (`α < 2` regimes where `M_α` is contested) or when the wavefunction is already MPS and the Pauli-basis lift is cheaper than the Markov chain.
- **Stabilizer nullity `ν(ρ)`** — integer-valued: counts the dimension of the maximal stabilizer subgroup that fixes `|ψ⟩` minus `N`; equivalently, `2N − rank` of the Pauli expectation matrix. Vanishes iff `ρ` is stabilizer; captures a *discrete* aspect of nonstabilizerness orthogonal to the continuous `M_n` density. Useful for stabilizer-group identification (which Pauli operators stabilize the state) and for parity-style classifications across phase boundaries where `M_n` is featureless.
- **Mutual magic across subsystems** — synonym / generalization of `L(ρ_AB)` to multiple disjoint regions; documented under the disjoint-bipartite partition mode in `knowledge-base/magic-conventions.md`. The same Pauli-MPS lift accesses higher-order mutual-magic combinations without rerunning the chain.

How they complement SRE:

- `M_n` is a continuous *density* and dominated by the bulk; alternative monotones expose structure that `m_n` averages over.
- Bell magic gives a strict-monotone safety net when the workflow uses `M_α` with `α < 2` (the contested regime flagged in `magic-conventions.md`).
- Stabilizer nullity gives a hard "is this state a stabilizer?" yes/no when the SRE is small but uncertain.
- Mutual magic is the natural critical diagnostic in 1D where full-state magic fails (spin-1 XXZ Haldane transitions are the canonical case).

How to compute each: see the relevant model skill and the algorithm card `knowledge-base/methods/pauli-markov.md` (Markov-chain protocol for `M_n` / `L(ρ_AB)` / increment construction; deterministic Pauli-basis MPS lift variant for Bell magic / stabilizer nullity / mutual magic). Use `knowledge-base/methods/ttn.md` as the wavefunction backbone for large `N` or 2D PBC; see its TTN-vs-MPS break-even table when choosing.

## Cross-checks

| Competing explanation | Test that rules it out |
|---|---|
| Magic is artifact of basis choice (single-qudit baseline) | Compare to the analytic single-qudit magic of the same family; subtract or document. |
| Magic peak is finite-size only | Run at multiple `L`; a critical peak narrows but persists; an artifact disappears with `L`. |
| `L(ρ_AB)` value is a sampling fluctuation | Verify with reblocked errors and a second chain (different seed); confirm `τ_int` is not blowing up at the parameter point. |
| Wegner-duality-equivalent target was confused with the original | If the model is `Z_2` lattice gauge in 2D, the actual computation runs on the dual 2D Ising (SREs preserved) — confirm the dual is built correctly. |
| Volume-law `M_n>1` swamping a sub-leading scaling signature | Switch to the increment estimator (1D) or the higher-D subsystem-difference linear combination (topological-entanglement-entropy family). |
| `M_α` is in the contested `α < 2` regime where strict monotonicity is not guaranteed | Cross-check with Bell magic (strict monotone for any `α`) via the Pauli-basis MPS lift (`knowledge-base/methods/pauli-markov.md`); agreement gates the SRE-density-level conclusion. |
| State *looks* like a near-stabilizer state but `m_n` reports small-but-nonzero | Compute stabilizer nullity `ν(ρ)` via the Pauli-basis MPS lift; integer-valued, gives a hard yes/no on stabilizer status that the continuous `M_n` cannot. |
| Sampling chain is biased by symmetry-restricted Pauli proposals | Re-run with the deterministic Pauli-basis MPS lift (no Markov chain); independent error budget. See `knowledge-base/methods/pauli-markov.md` deterministic-lift variant. |

## Interpretation rules

- A non-zero magic density in a generic many-body state is *not* a phase indicator on its own — most ground states are non-stabilizer. The diagnostic content is the *parameter dependence* (peak / crossing / extremum / plateau) and the *partition dependence* (full vs disjoint).
- For 1D systems where full-state `m_n` features no critical signature (notable case: spin-1 XXZ across the Haldane transitions), the answer is to switch to `L(ρ_AB)`, not to declare "no critical magic." Long-range magic is the UV-finite diagnostic.
- For 2D confinement-deconfinement transitions, magic exhibits a *crossing* (Binder-cumulant-like), not a peak; the deconfined and confined phases are both volume-law in magic. Hand off to `confinement` for the broader cross-check toolkit.
- `M_α` is a strict monotone only for `α ≥ 2`. When using `M_α` with `α < 2` (including `M_1`) to draw a monotonicity-style conclusion, flag this — `M_1` is still the standard density-level diagnostic and remains useful.
- Negative extrema of `L(ρ_AB)` are physical: SRE is not subadditive. Do not flip signs to make `L ≥ 0`.
- The deterministic Pauli-basis MPS lift (`methods/pauli-markov.md` runtime variant) gives access to additional monotones (Bell magic, stabilizer nullity). Route there when those are the question and the wavefunction is MPS.

## Verification

Standard magic-skill verification, auto-run as part of any magic calculation. Failures are surfaced; passes are summarized as one tag in the report.

- **Single-qudit limit** — analytic `m_n(θ)` from `knowledge-base/magic-conventions.md` qudit examples; see `knowledge-base/magic-benchmarks.md` "Single-qudit limit" row.
- **Stabilizer-state limit** — for any state in the stabilizer family (e.g., GHZ, Néel-product on a Z-basis lattice, `|+…+⟩` on an X-basis lattice), `m_n = 0` exactly. Markov-chain estimator returns 0 within statistical error.
- **2D ferromagnet / paramagnet endpoint limits** — auto-listed for any 2D variant the calling model skill exposes:
  - `h ≪ J` (deep ordered phase) — ground state is the all-aligned ferromagnet `|↑…↑⟩`, a +1 eigenstate of all `σ^z` operators on the dual basis. Stabilizer state; `m_n → 0` analytically.
  - `h ≫ J` (deep disordered phase) — ground state is the all-aligned paramagnet `|+…+⟩`, a +1 eigenstate of all `σ^x` operators. Stabilizer state; `m_n → 0` analytically.
  - These two endpoints constrain the `m_n(h)` curve to vanish at both extremes; the *crossing* lives between them. Disagreement at either endpoint indicates a sign-convention or Pauli-basis bookkeeping error.
- **`χ`-convergence** — `m_n(χ)` asymptotes; this is the Fig-13-class diagnostic. Auto-emitted alongside the standard `E(χ)` curve when a magic calculation runs.
- **`N_S`-convergence** — reblocked error `~ 1/√N_S` once the chain is past `~10 × τ_int`.
- **Cross-method between estimators** — when the calculation is critical or in a frontier regime, auto-pair Pauli-Markov with the deterministic Pauli-basis MPS lift (`methods/pauli-markov.md` variant). Disagreement → setup error or insufficient convergence in one. This is the canonical magic-internal cross-check; the `magic` ↔ `Binder` cross-check (for confinement-deconfinement) is the cross-diagnostic case handled by `physics/confinement`.
- **Benchmark range** — compare against the relevant row in `knowledge-base/magic-benchmarks.md`; report the literature *range*, never a trophy number.

When 2D limit checks fail (the `m_n → 0` endpoint test does not hold), do not interpret the crossing — the failure mode is upstream and must be fixed before the magic crossing is meaningful.

## Frontier flag

Magic in many-body systems is an active research area. The connection between magic and physical phenomena is poorly mapped outside criticality and the 2D `Z_2` confinement-deconfinement case. When the user is asking about a regime not yet in the established list (`knowledge-base/magic-benchmarks.md`):

1. Run the diagnostic plan above and report constraints honestly.
2. Invoke `arxiv-search` with a tailored query (e.g., `<model> magic`, `<lattice> stabilizer Rényi`) to surface the current state of the literature.
3. Cite the literature *range* of plausible interpretations alongside the harness result. Do not claim closure where the field has none.

**Established benchmark coverage** (auto-gated against `knowledge-base/magic-benchmarks.md`): 1D TFIM, 1D `q`-state Clock / Potts (`q ∈ {2,3,4}`), 1D spin-1 XXZ with single-ion `D`, 2D `Z_2` lattice gauge ↔ 2D Ising (Wegner-dual route), single-qudit limit. Outside these rows the regime is frontier — invoke `arxiv-search` before interpretation.

`M_α` monotonicity for `α < 2` is itself contested in the literature; surface the caveat when relevant.

## Estimator choice

Default routing (skill picks; user ratifies):

| Question | Default estimator | Default partition |
|---|---|---|
| Is the magic density large/small/peaked? | `M_1` (Markov-chain, `Π = Ξ_P`) | Full state |
| Where is the critical point? (1D) | `L(ρ_AB)` | Disjoint bipartite (default `A = {1..L/4}`, `B = {L/2+1..3L/4}` on a ring; lattice analogues otherwise) |
| Recover `M_2` cheaply against volume-law | Increment-trick on `M_2` | Halving increment + recursion |
| Where is the confinement-deconfinement transition? (2D) | `m_1` | Full state (cross with `physics/confinement`) |
| Bell magic / stabilizer nullity / stabilizer-group identification | Deterministic Pauli-basis MPS lift (variant on `methods/pauli-markov.md`) | Full state |
| Experimental shot-budget question | Markov chain in finite-shot mode | Full state; sweep `(N_M, N_S)` jointly |

## Model hooks

`transverse-field-ising` (1D and 2D-via-Wegner-duality), `heisenberg` (1D XXZ as a special case; spin-1/2), `spin-1-xxz` (Néel / Haldane / large-`D`), `potts-clock` (qudit `d`-state), and any other model skill with a magic branch-table row.

## Related skills

- `criticality` — when magic is being used as a critical diagnostic; magic peaks/extrema land in the same finite-size-scaling toolkit.
- `confinement` — when magic is being used to detect a confinement-deconfinement transition; the magic-crossing is one diagnostic in a broader cross-check.
- `arxiv-search` — for frontier-regime literature framing.
