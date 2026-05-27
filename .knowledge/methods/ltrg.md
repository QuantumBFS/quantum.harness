# Linearized Tensor Renormalization Group

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

## Setup

Recommended stack:

1. `itensors` (`skills/itensors/stack.toml`) - explicit tensor construction,
   contraction, SVD, and truncation.

```
make install julia
make install itensors
```

Activate the environment with `julia --project=julia-env`.

Use `/itensors` for Julia setup, ITensor index mechanics, SVD keyword details,
and runtime troubleshooting. The LTRG method card owns the algorithmic choices:
Trotter split, transfer tensor construction, contraction direction,
normalization accounting, observable route, and convergence plan.

## Scope

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

## Notation

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

## Algorithm

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

## Code Shape (Julia / ITensors.jl)

The exact index layout and ITensor constructor details should be checked against
the installed ITensors docs before writing a production script. The geometry is
fixed by the caller's model and Trotter decomposition; the harness-level shape
is:

```julia
using ITensors

# 1. Build local basis indices and primed copies for adjacent imaginary-time
#    layers. Use explicit tags so contractions are auditable.
s1 = Index(q, "site1")
s2 = Index(q, "site2")
s1p = prime(s1)
s2p = prime(s2)

# 2. Build a local Hamiltonian tensor h on the chosen local term and exponentiate
#    the imaginary-time gate.
h = ITensor(s1, s2, s1p, s2p)
# fill h from the caller's local Hamiltonian convention
gate = exp(-tau * h)

# 3. Interpret gate matrix elements as a local transfer tensor.
T = gate

# 4. If the chosen network geometry requires a local factorization, reshape and
#    SVD the transfer tensor into local factors.
U, S, V = svd(T, (s1, s2); maxdim = q^2)

# 5. Repeatedly absorb transfer tensors into the current boundary tensor network,
#    SVD-compress to Dc, normalize, and append log scale factors.
log_scales = Float64[]
for layer in 1:K
    # boundary = absorb_layer(boundary, local_factors)
    # boundary, spectrum = compress_boundary(boundary; maxdim = Dc)
    # scale = normalize_boundary!(boundary)
    # push!(log_scales, log(scale))
end

# 6. Contract the remaining boundary and combine it with log_scales to obtain
#    the partition function or free energy in the chosen normalization.
```

This is a shape, not a reusable library function. Production scripts should keep
index tags explicit, write intermediate convergence data incrementally, and
record the normalization convention alongside the output.

## Knobs

| Knob | Meaning |
|---|---|
| `τ` | Trotter step; controls decomposition error and number of layers. |
| `K` | Number of imaginary-time steps; fixes `β = Kτ`. |
| `Dc` | Number of singular values retained during boundary compression. |
| Contraction direction | Direction in which layers are absorbed into the boundary. |
| Gate order | Ordering of local imaginary-time gates in the Trotter product. |
| Normalization convention | How local scales are removed and later restored. |
| Observable route | Direct partition-function quantity, tensor insertion, or controlled derivative. |

## Cost Estimate

Runtime grows with the number of layers `K = β / τ`, the number of local tensors
absorbed per layer, and the SVD cost of compressing the boundary to `Dc`.
Memory is dominated by the boundary tensor network and retained singular
spaces. Before a full reproduction run, estimate cost from the intended `τ`,
target `β`, local Hilbert dimension `q`, boundary geometry, and `Dc` sweep.

For uncertain implementations, run a small smoke calculation at reduced `β` and
`Dc` to measure one-layer absorption and compression time. Treat that as a
timing probe, not a scientific result.

## Observables

Free energy comes from the final contraction plus accumulated log scale factors.
Other thermodynamic quantities require an observable-specific route supplied by
the caller: tensor insertion, a derivative of free energy, or another explicit
estimator. Do not substitute an analytic solution for the LTRG calculation; use
analytic or external data only as a benchmark after the LTRG result exists.

## Verification

- Sweep `τ` and check the expected approach as Trotter error decreases.
- Sweep `Dc` and check observable stability and discarded weight.
- Confirm that a reduced-size or reduced-temperature smoke run gives finite,
  stable log normalization factors before scaling up.
- Check that log scale factors are included exactly once in the final quantity.
- Check high- and low-temperature limits when the caller supplies them.
- Compare against the caller-provided benchmark only after producing the LTRG
  observable.

## Pitfalls

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

## Citations

- `.knowledge/literature/ltrg/1011.0155_linearized-tensor-renormalization-group-algorithm-for-the-ca.md` - Li et al., original LTRG paper.
- ITensors.jl stack and setup are handled by `/itensors`.
