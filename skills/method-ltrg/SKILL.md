---
name: method-ltrg
description: Use when a finite-temperature Linearized Tensor Renormalization Group (LTRG) reproduction needs method-level route and tool selection — Trotterized classical tensor network, layer-by-layer boundary contraction, thermodynamic observables.
---

# Method LTRG

LTRG is the finite-temperature tensor-network track: it maps a `d`-dimensional quantum lattice model to a `(d + 1)`-dimensional classical tensor network by Trotter-Suzuki decomposition, then contracts the network layer by layer while truncating the growing boundary with SVD. Use it to decide whether the target genuinely needs LTRG, then hand off to the tool skill for implementation mechanics.

## Sources

- Tool skill: `/using-itensors`

## Route

1. Use LTRG when the figure is a finite-temperature thermodynamic quantity (free energy, internal energy, specific heat, susceptibility) of a local quantum lattice model represented as a Trotterized classical network.
2. Fix the Trotter split, transfer-tensor construction, contraction direction, normalization accounting, and observable route before setup — the method card owns these decisions.
3. Recommend `/using-itensors` for ITensors.jl setup, index mechanics, SVD/truncation keywords, and runtime troubleshooting.
4. If the target is a ground-state property, route to `/method-mps` or `/method-peps` instead; LTRG is a finite-temperature method.

## Tool Handoff

Invoke `/using-itensors` after the LTRG route is fixed. `/using-itensors` owns tensor construction, index management, SVD, truncation, and runtime troubleshooting; the method card owns the Trotter split, contraction order, normalization bookkeeping, and convergence plan.

## Details

LTRG maps a `d`-dimensional quantum lattice model at finite temperature into a
`(d + 1)`-dimensional classical tensor network by Trotter-Suzuki
decomposition, then contracts the network layer by layer while truncating the
growing boundary with SVD.

This card is generic methodology. Paper-specific Hamiltonian choices, figure
protocols, caption and axis reading, and target claims belong in
`reproduce-paper` protocols, not here.

Primary source: Li, Ran, Gong, Zhao, Xi, Ye, and Su, "Linearized tensor
renormalization group algorithm for the calculation of thermodynamic
properties of quantum lattice models," `.knowledge/literature/ltrg/`.

### Scope

Use this card for:

- Finite-temperature quantum lattice problems represented as a Trotterized
  classical tensor network.
- Layer-by-layer contraction of the transfer network with a truncated boundary
  tensor network.
- Thermodynamic observables derived from the partition function, tensor
  insertions, or controlled derivatives.
- LTRG reproductions where the calculation itself must be LTRG, not an analytic
  or exact-solution shortcut.

Do not use this card as the full recipe for:

- Paper-specific figure protocols, axis labels, or plotted-curve contracts.
- ITensor installation or syntax troubleshooting.
- Ground-state MPS algorithms that do not build and contract the finite-
  temperature transfer network.

### Notation

- `d`: spatial dimension of the quantum lattice model.
- `β`: inverse temperature.
- `τ`: Trotter step.
- `K`: number of Trotter steps, with `β = Kτ`.
- `Dc`: retained SVD dimension for boundary compression.
- `q`: local Hilbert-space dimension.
- Boundary tensor network: the partially contracted region of the classical
  tensor network.
- Log scale factors: accumulated normalizations needed to recover the final
  partition function and free energy.

### Algorithm

1. Start from a local quantum Hamiltonian.
2. Split the Hamiltonian into local pieces suitable for Trotter-Suzuki
   decomposition.
3. Approximate `Z = Tr exp(-βH)` by a product of imaginary-time gates, with
   `β = Kτ`.
4. Insert complete local bases between imaginary-time layers.
5. Interpret the resulting expression as a `(d + 1)`-dimensional classical
   tensor network.
6. Build local transfer tensors from the imaginary-time gate matrix elements.
7. Factor local transfer tensors by SVD when the chosen network geometry
   requires it.
8. Initialize the boundary tensor network representing the contracted region.
9. Absorb one uncontracted layer into the boundary.
10. Reshape the enlarged local objects for SVD.
11. Keep the largest `Dc` singular values and update the boundary tensors.
12. Normalize tensors or singular values and store the log scale factors.
13. Repeat layer absorption and compression until the full imaginary-time
    extent is contracted.
14. Contract the remaining boundary tensor network.
15. Compute thermodynamic observables from the final contraction and accumulated
    normalizations.

### Knobs

| Knob | Meaning |
|---|---|
| `τ` | Trotter step; controls decomposition error and number of layers. |
| `K` | Number of imaginary-time steps; fixes `β = Kτ`. |
| `Dc` | Number of singular values retained during boundary compression. |
| Contraction direction | Direction in which layers are absorbed into the boundary. |
| Gate order | Ordering of local imaginary-time gates in the Trotter product. |
| Normalization convention | How local scales are removed and later restored. |
| Observable route | Direct partition-function quantity, tensor insertion, or controlled derivative. |

### Cost Estimate

Runtime grows with the number of layers `K = β / τ`, the number of local tensors
absorbed per layer, and the SVD cost of compressing the boundary to `Dc`.
Memory is dominated by the boundary tensor network and retained singular
spaces. Before a full reproduction run, estimate cost from the intended `τ`,
target `β`, local Hilbert dimension `q`, boundary geometry, and `Dc` sweep.

For uncertain implementations, run a small smoke calculation at reduced `β` and
`Dc` to measure one-layer absorption and compression time. Treat that as a
timing probe, not a scientific result.

### Observables

Free energy comes from the final contraction plus accumulated log scale factors.
Other thermodynamic quantities require an observable-specific route supplied by
the caller: tensor insertion, a derivative of free energy, or another explicit
estimator. Do not substitute an analytic solution for the LTRG calculation; use
analytic or external data only as a benchmark after the LTRG result exists.

### Verification

- Sweep `τ` and check the expected approach as Trotter error decreases.
- Sweep `Dc` and check observable stability and discarded weight.
- Confirm that a reduced-size or reduced-temperature smoke run gives finite,
  stable log normalization factors before scaling up.
- Check that log scale factors are included exactly once in the final quantity.
- Check high- and low-temperature limits when the caller supplies them.
- Compare against the caller-provided benchmark only after producing the LTRG
  observable.

### Pitfalls

- Dropping or double-counting normalization factors changes free energy.
- Confusing local Hilbert dimension `q` with truncation dimension `Dc` changes
  both cost estimates and tensor shapes.
- A smaller `τ` increases the number of layers; report cost as a function of
  both `τ` and `Dc`.
- Derivatives of free energy amplify numerical noise; verify the underlying free
  energy curve before trusting derivative observables.
- Boundary representation is geometry-dependent. Keep the algorithm in terms of
  boundary tensor networks unless a caller-supplied geometry fixes a more
  specific representation.

### Citations

- `.knowledge/literature/ltrg/1011.0155_linearized-tensor-renormalization-group-algorithm-for-the-ca.md` - Li et al., original LTRG paper.
- ITensors.jl stack and setup are handled by `/using-itensors`.
