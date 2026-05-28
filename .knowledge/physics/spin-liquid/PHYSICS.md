# Spin Liquid

Evaluate a spin-liquid hypothesis on a concrete model. Do not label a state a spin liquid without ruling out competing explanations.

## Diagnose

Infer the diagnostic framing from the user's prompt and propose it for ratification.

**Canonical framing:** "You're asking whether [model on lattice] is a spin liquid. I'll treat this as: rule out magnetic order first, then check for positive SL signatures (topological entanglement, gap structure, ground-state degeneracy). The model card driving the calculation is `heisenberg` (or `j1-j2`). No data yet — I'll produce the phased plan below."

If the user already has data, adjust: "You have [observables]. I'll evaluate those against the SL checklist below, then recommend what to compute next."

Do not ask 5 questions. Propose the framing; let the user correct if wrong.

## Evidence to gather

For each item, the relevant model card drives the calculation; this skill specifies *what to compute* and *what to look for*.

- **Magnetic order**: spin-spin correlations and structure factor `S(q)`. Look for the absence of a Bragg peak in the thermodynamic-limit extrapolation (or in cylinder scaling).
- **Spin / singlet gap**: behavior with system size. Power-law decay → gapless candidate; exponential decay → gapped candidate.
- **Entanglement entropy**: bipartite entanglement vs subsystem size. Topological entanglement entropy `γ` (subleading constant): `γ = log D` for topological order with quantum dimension `D`.
- **Symmetry-protected long-range order proxies**: dimer-dimer correlations (rule out VBS), chiral order parameter (for chiral SL candidates).
- **Ground-state degeneracy on torus**: e.g., 4-fold for Z₂ topological order. Hard to verify directly with DMRG but accessible via cylinder topology in some setups.

How to compute each: see the relevant model card and method card (`skills/method-mps/SKILL.md` etc.).

## Cross-checks

| Competing explanation | Test that rules it out |
|---|---|
| Magnetic order | Structure factor's peak weight goes to zero with size (or with cylinder width), not to a finite value. |
| Valence-bond crystal | Dimer-dimer correlations decay rather than ordering at a finite wavevector. |
| Long-range entangled but trivial | Topological entanglement entropy ≈ 0 (vs `log 2` for Z₂). |
| Insufficient sizes / bond dimension | Cylinder-width scan + ED cross-check on small clusters confirm trends. |
| Conventional symmetry-broken state we missed | Check full symmetry-broken candidate order parameters (Néel, stripe, columnar VBS, plaquette, …). |

## Interpretation rules

- **"No detected magnetic order at this size" ≠ "spin liquid."** It only constrains.
- A **positive identification** requires at least one of:
  - Topological entanglement signature consistent with a known SL.
  - Ground-state degeneracy structure consistent with a known topological order.
  - Fractionalized excitation signatures (e.g., spinon continuum in spectroscopy).
- If only constraints are met (no order detected, gap unclear), report as **candidate spin liquid pending positive identification**, not as a confirmed SL.
- For frontier problems (kagome Heisenberg, J1-J2 square at intermediate `J2/J1`), report the literature *range* of plausible identifications and your evidence's position within that range. Do not claim closure where the field has none.

## Frontier flag

The harness explicitly does not claim coverage of contested SL identifications. When the user is in a frontier regime (kagome, J1-J2 square `~0.5`, organic triangular salts), surface this and offer:

1. The diagnostic plan above (recommended).
2. A constraint-only report ("at this size, no Néel order; gap inconclusive") with no SL labelling.
3. A pointer to the relevant literature range with citations from `.knowledge/benchmark-numbers.md`.

Before interpreting evidence in a frontier regime, invoke the `arxiv-search` skill with a tailored query (e.g., `kagome Heisenberg spin liquid recent`, `J1-J2 square 0.5 spin liquid`) to surface the current state of the debate. Cite recent findings alongside the diagnostic plan, do not work in isolation from the literature.

## Model hooks

- `heisenberg` — drives the actual calculations.
- `j1-j2` — frustrated NN+NNN, the canonical 2D SL candidate.
- `frustration` — call first if the source of degeneracy or competition is unclear.
