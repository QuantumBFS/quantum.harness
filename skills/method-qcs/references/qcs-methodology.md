# Quantum Circuit Simulation (QCS) — Methodology Reference

Reproduction-grade reference for **classical simulation of quantum circuits** as used in
this harness: full state-vector simulation, tensor-network (contraction-path-optimized)
simulation, MPS / bond-dimension-truncated circuit simulation, and differentiable circuits
for VQE/VQA. This card is *method/algorithm* content. The TensorCircuit-NG API (how to call
it) lives in `skills/using-tensorcircuit-ng/references/`; the route/tool-selection logic lives
in `skills/method-qcs/SKILL.md`.

Notation: n = number of qubits; |ψ⟩ = state; χ = MPS bond dimension; θ = variational
parameters; ⟨H⟩ = ⟨ψ|H|ψ⟩; W = contraction width; C = contraction cost (total scalar ops).

---

## Overview — the task and the three regimes

**The task.** Given a circuit U = G_L ⋯ G_2 G_1 acting on n qubits from |0⟩^⊗n, compute one
of: (a) the full output state |ψ⟩ = U|0⟩^⊗n, (b) a single amplitude ⟨x|U|0⟩^⊗n or an
expectation ⟨ψ|H|ψ⟩, or (c) samples x ~ |⟨x|ψ⟩|². No method does all three cheaply; the
right representation depends on which output you need and on how much entanglement the circuit
generates.

| Regime | Object stored | Memory | Time (per output) | Exact? | Wins when |
|---|---|---|---|---|---|
| State vector | dense 2ⁿ amplitude array | 2ⁿ × 16 B (complex128) | O(2ⁿ) per gate layer | exact | n ≲ 30–35; need full state or many samples; arbitrary entanglement |
| Tensor-network contraction | network of small gate tensors; contract on demand | 2^W (largest intermediate) | 2^C (∝ contraction width) | exact | few amplitudes/expectations of wide-but-shallow or low-treewidth circuits; n up to 100s |
| MPS (χ-truncated) | n rank-3 tensors, bonds ≤ χ | n·χ²·d × 16 B | O(n·χ³) per 2-qubit gate | approximate (χ) | 1D / low-entanglement / shallow circuits; n into the hundreds |

Memory/time scaling, side by side:

- **State vector**: 2ⁿ scaling is the hard wall. n=30 ≈ 16 GB (complex128); each added qubit
  doubles memory. Time is exact: applying one gate touches all 2ⁿ amplitudes.
- **Tensor network**: cost is set not by n but by the **contraction width** W (log₂ of the
  largest intermediate tensor) — memory ≈ 2^W, time ≈ 2^C. W is governed by the circuit's
  **treewidth**; a shallow or geometrically local circuit can have W ≪ n. Finding the order in
  which to contract that minimizes W and C is the central algorithmic problem (below).
- **MPS**: cost is polynomial in n but exponential in entanglement, because the bond dimension
  needed to stay exact grows as χ ≈ 2^S where S is the half-chain entanglement entropy. Capping
  χ trades a controlled truncation error for tractability.

Rule of thumb for choosing: need the *whole* state or thousands of samples and n ≤ ~30 →
state vector. Need a *handful* of amplitudes/expectations of a large circuit → tensor-network
contraction. Circuit is 1D-ish / low-entanglement and n is large → MPS. Differentiable
energy minimization (VQE) → any of the three as the forward engine, wrapped in autodiff.

---

## State-vector simulation

**Representation.** Store the full wavefunction as a complex array ψ of length 2ⁿ, indexed by
the bitstring (q_{n−1} … q_1 q_0). Equivalently, a rank-n tensor ψ[i_0, i_1, …, i_{n−1}] with
each index of dimension 2. Initialize ψ = |0⟩^⊗n (a 1 in position 0, else 0).

**Applying a 1-qubit gate** G (2×2) on qubit k: for every pair of basis states that differ
only in bit k, mix the two amplitudes by G. As a tensor contraction, this is
ψ'[…, i_k, …] = Σ_{j} G[i_k, j] · ψ[…, j, …] — contract G's input leg against axis k. Cost
O(2ⁿ) (touch each amplitude once); no extra memory (in-place).

**Applying a 2-qubit gate** G (4×4) on qubits (a,b): contract the rank-4 gate tensor
G[o_a, o_b, i_a, i_b] against axes a, b of ψ. Cost O(2ⁿ) per gate (4 ops per amplitude).
Whole-circuit cost ≈ (#gates) × 2ⁿ. **Controlled gates are not special** here — they are just
4×4 tensors. Always apply gates as small contractions on the state; never build the 2ⁿ×2ⁿ full
unitary (that is 4ⁿ memory and the classic blunder).

```text
state_vector_run(circuit, n):
    psi = zeros(2**n, complex);  psi[0] = 1
    reshape psi -> tensor of shape (2,)*n
    for gate in circuit:                       # in circuit order
        psi = tensordot(gate.tensor, psi, axes=gate.qubits)
        # move the new output axes back to their qubit positions
    return psi.reshape(2**n)
```

**Measurement / sampling.** Probabilities are p(x) = |ψ[x]|². To sample a bitstring, either
(a) draw from the categorical distribution over all 2ⁿ entries, or (b) sample qubit by qubit:
p(q_0=0) = Σ over states with bit0=0 of |ψ|², draw q_0, collapse/renormalize, repeat — O(n·2ⁿ)
for one shot but no 2ⁿ-vector enumeration of outcomes. Expectations: ⟨H⟩ = ψ† H ψ; for a Pauli
string P, apply P as gates to a copy and take the overlap ⟨ψ|Pψ⟩ (avoids any dense H).

**Cost summary.** Memory 2ⁿ·16 B is the binding constraint; time is (#gates)·2ⁿ, exact to
machine precision. Practical ceiling on a single node ≈ n = 30–35.

---

## Tensor-network simulation

**Circuit → tensor network.** Lay the circuit out as a network: rank-1 tensors for input and
output qubit states, rank-2 tensors for 1-qubit gates, rank-4 tensors for 2-qubit gates;
wires shared between gates become contracted edges. The scalar you want determines the
network's open legs:

- **Single amplitude** ⟨x|U|0⟩: fix all input legs to |0⟩ and all output legs to the bits of
  x → a fully closed network whose contraction is one complex number.
- **Expectation** ⟨ψ|H|ψ⟩: glue U, the operator (Pauli string or MPO), and U† → closed network.
- **Sampling**: contract marginals qubit by qubit, conditioning on already-drawn bits.

A **2-qubit gate can be SVD-split** across the qubit cut: g[o_a,i_a,o_b,i_b] = Σ_ξ
l[o_a,i_a,ξ]·r[o_b,i_b,ξ], ξ = 1…χ_gate. CZ has an exact χ=2 split; a generic/fSim gate has no
exact low-rank split (keeping the 2 dominant singular values is an *approximation* whose error
compounds over many gates). Splitting lowers tensor ranks and helps the path finder; whether to
split is a method decision, not a free lunch.

**The contraction-ordering problem.** The result is independent of contraction order, but cost
is *not*. A contraction order is a rooted binary **contraction tree** B over the tensors. Its
two costs (Gray & Kourtis 2021):

- **Contraction width** W = max over tree vertices of the log₂-size of the intermediate tensor
  there (the "edge congestion"). Memory ≈ 2^W. This is the binding resource.
- **Contraction cost** C = Σ over tree vertices of 2^(vertex congestion), i.e. total scalar
  multiply-adds. Time ≈ 2^C (× 2 for real, × 8 for complex FLOPs).

The optimal W equals the **treewidth** of the circuit's (line) graph plus structure — Markov &
Shi (2008) proved a circuit of treewidth d simulates in time exp[O(d)], polynomial when
d = O(log T). So path optimization = minimizing a treewidth-like quantity. Finding the exact
optimum is #P-hard in general; for n beyond ~20 tensors, exhaustive/dynamic-programming
(`opt_einsum`'s `Optimal`) is infeasible and heuristics are mandatory.

**Hyper-optimized contraction-path search (Gray & Kourtis 2021, `cotengra`).** The harness's
canonical method. Build the contraction tree with one of several *drivers*, then
hyper-optimize over drivers and their parameters with Bayesian optimization. Drivers:

1. **Hyper-graph partitioning (`Hyper-Par`)** — *the workhorse*. Recursively bipartition the
   tensor (hyper)graph top-down; each cut is one contraction, its cost = product of cut bond
   dims. Uses **KaHyPar**; respects edge weights (bond dims) and hyperedges; an **imbalance**
   parameter ε (|V_i| ≤ (1+ε)|V|/k) controls how balanced the partitions are. Best on dense /
   irregular / random-circuit graphs.
2. **Greedy / agglomerative (`Hyper-Greedy`)** — bottom-up; score each pairwise contraction by
   cost(T_i,T_j) = size(T_k) − α·(size(T_i)+size(T_j)) and pick via a Boltzmann factor
   exp(−cost/τ). Fast; strong on planar / 2D-lattice graphs. Knobs α, τ.
3. **Community detection (`Hyper-GN`)** — Girvan–Newman edge-betweenness dendrogram; contract
   within communities first. Edge weights via betweenness; no native hyperedges.
4. **Line-graph tree decomposition** — `QuickBB` (branch-and-bound, small graphs) and
   `FlowCutter` (top-down, large graphs); target leading cost only, ignore edge weights.
5. **Exhaustive `Optimal`** — dynamic programming over connected subgraphs; exact but only for
   small networks.

```text
hyper_optimize_path(tensor_network, target=W or C, budget):
    simplify(tensor_network)                  # see simplifications below
    best = None
    repeat until budget exhausted:            # any-time, parallel
        driver, params = bayes_suggest()      # GP over (driver, α, τ, k, ε, ...)
        tree   = build_tree(driver, params)   # Hyper-Par / Greedy / GN / ...
        score  = W(tree) or C(tree)           # proxy congestion measures
        bayes_update(driver, params, score)
        best   = min(best, tree by score)
    return best
```

Random restarts + Bayesian tuning (`baytune`, Gaussian-process surrogate) over the *score*
(W or C) make all heuristic drivers any-time parallel searches; reported paths reach near-
optimal and beat established methods by orders of magnitude (≈10⁴× speedup estimated for the
Sycamore "supremacy" circuits).

**Pre-contraction simplifications** (applied iteratively until fixed point, default order
{antidiagonal-gauging, diagonal-reduction, column-reduction, rank-simplification,
split-simplification}):
- *diagonal-reduction* (collapse a tensor axis that is diagonal → introduces a hyperedge),
- *rank-simplification* (absorb rank-1/2 tensors into neighbors),
- *antidiagonal-gauging* (flip an index to expose a diagonal),
- *column-reduction* (project an index onto a single basis state),
- *split-simplification* (SVD-split a tensor when it lowers cut weight — the one step that adds
  tensors). COPY tensors (controlled gates, SAT) → hyperedges for freer hypergraph partitioning.

**Slicing (memory control).** When W is too large to fit memory, pick a set of indices
s_sliced to sum over *last* (outside the contraction). This produces d_sliced = ∏ w(e)
independent, smaller contractions (each with those edges removed) — **embarrassingly parallel**.
Each slice has reduced width W_s but the *total* cost rises somewhat above C (redundant repeated
work), so slicing trades a small FLOP increase for a large memory reduction. Choose sliced
indices greedily to hit a target W_s while minimizing C_s, *inside* the Bayesian loop so the
path is chosen to slice well. Reference anchor: a single Sycamore-53 (m=20) amplitude could be
sliced from W≈55 down to W_s≈27 (fits a 5 GB consumer GPU) for a <10× FLOP cost — a ≈16,000×
memory reduction.

**Cost summary.** Memory ≈ 2^(W or W_s), time ≈ 2^C. *Independent of n* — set entirely by the
circuit geometry/treewidth and the quality of the path. Exact (no truncation) unless a gate was
SVD-truncated.

---

## MPS / bond-dimension circuit simulation

**Representation.** Write |ψ⟩ as a Matrix Product State: n rank-3 tensors A^[k][i_k]
(physical index i_k = 0,1; left/right bonds ≤ χ), so ψ[i_0…i_{n−1}] = A^[0] A^[1] … A^[n−1].
Memory n·χ²·2·16 B. Exact representation needs χ = 2^(half-chain entanglement entropy S); the
method's power is *capping* χ.

**Applying gates with SVD truncation.**
- *1-qubit gate*: contract into the local tensor; bonds unchanged. Cheap.
- *2-qubit gate on adjacent sites (a, a+1)*: contract the two A tensors and the gate into one
  two-site block, then **SVD** across the bond and **keep the χ largest singular values**
  (or drop those below a cutoff). This restores MPS form; the discarded singular weight is the
  per-gate truncation error. Cost O(d²·χ³) per gate. Non-adjacent 2-qubit gates need SWAPs
  (or a swap network) to bring sites together.

```text
mps_apply_2q(A_a, A_{a+1}, gate, chi_max):
    theta = contract(A_a, A_{a+1}, gate)      # two-site block
    U, S, V = svd(theta, group legs by site)
    keep = min(chi_max, #{S > cutoff})
    A_a, A_{a+1} = U[:keep], diag(S[:keep]) @ V[:keep]   # gauge as needed
    trunc_err += sum(S[keep:]**2)             # accumulate discarded weight
```

**The entanglement-growth limit (Vidal 2003).** A circuit is efficiently MPS-simulable iff
its entanglement stays bounded: keeping χ fixed is exact only while S ≤ log₂χ. Generic deep
circuits grow S linearly in depth, so the required χ blows up exponentially and the truncation
error becomes uncontrolled — MPS then fails. MPS wins precisely for 1D-local, shallow, or
otherwise low-entanglement circuits, where it scales to hundreds of qubits. χ is the single
accuracy knob; converge results in χ.

---

## Differentiable circuits / VQE

**Parameterized circuit.** Gates carry parameters θ (typically rotation angles in
R_P(θ) = exp(−i θ P/2), P a Pauli). The ansatz prepares |ψ(θ)⟩ = U(θ)|0⟩^⊗n. The VQE
objective is the energy E(θ) = ⟨ψ(θ)|H|ψ(θ)⟩, minimized over θ; by the variational principle
E(θ) ≥ E₀ (ground-state energy) always — a result *below* E₀ signals a bug.

**Energy evaluation.** Decompose H = Σ_j c_j P_j into Pauli strings; then
E(θ) = Σ_j c_j ⟨ψ(θ)|P_j|ψ(θ)⟩. Use sparse / Pauli-sum / MPO-like H, **never** a dense 2ⁿ×2ⁿ
matrix (the dominant memory blunder). The forward engine can be any of the three above
(state-vector for small exact n; tensor-network or MPS for large n).

**Gradients — two routes:**

1. **Reverse-mode automatic differentiation (the harness default).** Treat the whole forward
   contraction as a differentiable program (JAX/TF/PyTorch backend) and backpropagate. Cost of
   ∇_θ E is O(1)× the cost of E — **independent of the number of parameters** — because one
   reverse sweep yields all components. This is the decisive advantage over hardware: a quantum
   device cannot backprop. JIT-compile the value-and-gradient kernel; complex-valued SVD in MPS
   circuits is itself differentiable, so gradients flow through χ-truncation too.

2. **Parameter-shift rule (Mitarai 2018, Schuld et al. 2019).** For a gate generated by a Pauli
   (two-eigenvalue generator, e.g. R_P(θ) = exp(−iθP/2)), the *exact* gradient is a difference
   of two shifted expectations:

   ∂E/∂θ_j = ½ [ E(θ_j + π/2) − E(θ_j − π/2) ]

   (general two-eigenvalue generator: ∂E/∂θ = r[E(θ+s) − E(θ−s)] with r = (λ₁−λ₂)/(2 sin((λ₁−λ₂)s))).
   This is **exact**, not a finite difference, but costs 2 circuit evaluations per parameter
   → O(n_params) forward passes. Use it when AD is unavailable (e.g. on hardware, or to
   cross-check AD); reverse-mode AD strictly dominates it for classical simulation.

   *Do not confuse with finite difference* [E(θ+h)−E(θ−h)]/(2h), which is only approximate and
   ill-conditioned — use finite difference solely as an independent gradient check.

**Optimization loop.**

```text
vqe(ansatz, H_pauli_terms, theta0, optimizer, steps):
    value_and_grad = jit(autodiff(lambda th: energy(ansatz(th), H_pauli_terms)))
    theta = theta0
    for step in range(steps):
        E, g = value_and_grad(theta)          # one fwd + one reverse sweep
        theta = optimizer.update(theta, g)    # Adam / SGD / L-BFGS (scipy_interface)
        if step % progress_every == 0: log(step, E)   # flush stdout
    return theta, E
```

Report **compile time, path-search time, warm runtime, and optimizer-loop time separately** —
they are different costs and conflating them misleads.

---

## Key parameters & convergence

| Knob | Regime | Controls | Convergence target |
|---|---|---|---|
| n (qubits) | all | problem size | — (fixed by problem) |
| nothing | state vector | — | exact to machine precision |
| path-search budget; driver/α/τ/ε; slicing target W_s | tensor network | W (memory), C (time) | exact result; tune to fit memory/time |
| χ (max bond dim); SVD cutoff | MPS | truncation error | sweep χ until ⟨H⟩ / observables plateau |
| ansatz depth; seed; optimizer + lr; steps | VQE | reachable energy | E plateaus, multiple seeds agree |
| AD vs parameter-shift; finite-diff h | gradients | gradient accuracy | AD == finite-diff on a parameter subset |

What controls accuracy: state-vector and full tensor-network contraction are **exact** (only
floating-point error). MPS accuracy is set by **χ** (truncation). VQE accuracy is set by the
**ansatz expressivity + optimizer convergence** (the energy is variational, so always an upper
bound on E₀).

---

## Validation / benchmarks

- **Small-circuit cross-check vs state vector.** For n ≤ ~20, run the tensor-network or MPS
  engine and the dense state-vector engine on the *same* circuit; amplitudes/⟨H⟩ must agree to
  machine precision (TN) or to the truncation budget (MPS).
- **GHZ / Bell expectations.** Build a Bell pair → ⟨Z⊗Z⟩ = +1, ⟨X⊗X⟩ = +1; build an n-qubit
  GHZ → ⟨Z_i Z_j⟩ = +1 for all pairs, ⟨X^⊗n⟩ = +1. Cheap exact anchors for the gate set and
  index conventions.
- **VQE on a small Hamiltonian.** Run VQE on a small transverse-field Ising or Heisenberg chain
  (or H₂ molecule via a Pauli-sum H) and compare the optimized energy to exact diagonalization;
  E_VQE ≥ E₀ must hold, and a sufficiently expressive ansatz should approach E₀.
- **Gradient check.** Finite-difference a few parameters and compare to the AD / parameter-shift
  gradient.
- **Convergence sweeps.** MPS: ⟨H⟩ vs χ asymptotes. VQE: energy vs depth and across seeds.
  Tensor network: confirm the reported value is path-independent (two different paths agree).

---

## Reproduction-sufficiency assessment

**Verdict: sufficient for tensor-network contraction; sufficient-with-web-fill for the other
three regimes.**

- **Tensor-network contraction + path optimization — fully sufficient from the KB.** Gray &
  Kourtis 2021 (`2002.01935`) gives the complete method: contraction-tree formalism, the W/C
  cost measures, all five drivers (Hyper-Par/KaHyPar, Hyper-Greedy, Hyper-GN, QuickBB/FlowCutter,
  Optimal), Bayesian hyper-optimization, the simplification suite, slicing, and the circuit→TN
  mapping with gate SVD splitting. This is the strong core of the KB.
- **State-vector fundamentals — thin in KB, filled from canonical knowledge.** The KB papers
  (TensorCircuit / -NG) are contraction-first and treat state-vector simulation only as a
  baseline; the gate-as-tensor-contraction mechanics, in-place application, and qubit-by-qubit
  sampling are standard textbook material supplied here.
- **MPS circuit simulation — adequate in KB, augmented.** `2602.14167` documents the
  differentiable `MPSCircuit` with SVD truncation and the precision/scale trade-off; the
  per-gate two-site SVD-truncation algorithm and the entanglement-growth limit were sharpened
  with Vidal 2003 (the foundational efficiency criterion).
- **Autodiff / VQE — adequate in KB, parameter-shift formula filled.** The KB covers the
  VQE loop, Pauli-sum energies, and reverse-mode AD vs parameter-shift trade-off (`2205.10091`,
  `2602.14167`). The KB only *mentions* parameter-shift; its exact analytic form
  (½[E(θ+π/2)−E(θ−π/2)] and the general two-eigenvalue rule) was filled from Mitarai 2018 /
  Schuld et al. 2019.
- **Treewidth foundation — filled.** Markov & Shi 2008 (the exp[O(treewidth)] result) underpins
  why path optimization works; cited by Gray & Kourtis but not in the KB, so added.

Net: a reader can reproduce all four regimes from this card. New canonical method references
(Markov–Shi, Vidal, Mitarai, Schuld) are listed below for ingestion.

---

## Source links

KB (relative to repo root):
- `.knowledge/literature/quantum-circuit-simulation/2002.01935_hyper-optimized-tensor-network-contraction.md` — Gray & Kourtis, the contraction-path method (core).
- `.knowledge/literature/quantum-circuit-simulation/2602.14167_tensorcircuit-ng-a-universal-composable-and-scalable-platfor.md` — TensorCircuit-NG (MPSCircuit, AD/JIT/VMAP, engines).
- `.knowledge/literature/quantum-circuit-simulation/2205.10091_tensorcircuit-a-quantum-software-framework-for-the-nisq-era.md` — TensorCircuit (VQE, gradients, Pauli-sum H).
- `.knowledge/literature/quantum-circuit-simulation/tensorcircuit-tensorcircuit-ng.md` — official repo/docs entry.

Web (filled gaps):
- Markov & Shi, *Simulating Quantum Computation by Contracting Tensor Networks*, SIAM J. Comput. 38, 963 (2008), arXiv:quant-ph/0511069 — treewidth simulation bound.
- Vidal, *Efficient Classical Simulation of Slightly Entangled Quantum Computations*, PRL 91, 147902 (2003), arXiv:quant-ph/0301063 — MPS / entanglement-bounded simulation.
- Mitarai, Negoro, Kitagawa, Fujii, *Quantum Circuit Learning*, PRA 98, 032309 (2018), arXiv:1803.00745 — parameter-shift gradients.
- Schuld, Bergholm, Gogolin, Izaac, Killoran, *Evaluating analytic gradients on quantum hardware*, PRA 99, 032331 (2019), arXiv:1811.11184 — parameter-shift rule (exact form).
