<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Quantum-Circuit Simulation — State-Vector, Tensor Network, Stabilizer (circuit-sim)

Classical simulation of quantum circuits using three complementary engines: exact state-vector evolution, tensor-network contraction, and stabilizer/Clifford simulation; together they cover the full spectrum from shallow low-entanglement circuits to near-Clifford circuits.

## Method card

### What it is

Classical circuit simulation chooses an engine based on circuit structure and entanglement. **State-vector:** maintains the full `2ⁿ`-amplitude complex vector and applies gates as sparse unitary multiplications; exact for any circuit but exponential in `n`. **Tensor-network (TN):** represents the state or the full circuit as a TN and contracts it; the cost is `exp(treewidth)` of the contraction graph (Markov–Shi), which is polynomial for low-depth or area-law circuits (MPS/TEBD for 1D, hyper-optimized slicing for 2D). **Stabilizer:** tracks a Clifford stabilizer tableau of size `O(n)` per generator; Clifford gates are exactly polynomial (Gottesman–Knill, Aaronson–Gottesman); non-Clifford T-gates enter via stabilizer-rank decomposition costing `~2^{αt}` with `α≈0.396` (Qassim–Pashayan–Gosset 2021).

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Sampling from the output distribution · expectation values of Pauli observables · VQE energy minimization · Hamiltonian-dynamics simulation · circuit fidelity estimation | Cost set by entanglement/depth generated and whether the circuit is near-Clifford. |
| M2 regime | T=0 / circuit-time (no thermal ensemble by default) | Thermal states via imaginary-time circuits or purification; real-time dynamics natively. |
| M3 accuracy class | State-vector: numerically exact, deterministic. TN: controlled bias (bond-dim truncation; a variational upper bound only for VQE energy minimization, not for dynamics/sampling). Stabilizer (Clifford): exact; stabilizer rank (T-gates): stochastic sampling. | Engine choice sets the accuracy class. |
| M4 dimension fit (A1) | Not lattice-dimension-gated; governed by circuit topology and entanglement | MPS/TEBD efficient for 1D/brickwork circuits; 2D circuits need hyper-optimized TN slicing [@gray_2021_hyper]. |
| M5 statistics & local dim (A3) | Qubits (`d=2`) primarily; qudits via generalization | State-vector cost doubles per qubit; stabilizer cost scales as `O(n²)` per measurement. |
| M6 entanglement regime (B5) | **Entanglement / circuit structure is the spine.** State-vector: volume-law tolerated. TN: cost = `exp(treewidth)` of contraction graph; polynomial for area-law / low-depth / 1D-like. Stabilizer: polynomial for near-Clifford (low T-gate count). | Choice of engine must match the circuit's entanglement profile. |
| M7 sign-problem dependence (C12) | Sign-immune (state-vector, TN, Clifford); stabilizer rank sampling can suffer phase cancellation for large T-count | No sign problem in state-vector or Clifford; near-Clifford regime is also stable. |
| M8 symmetry exploitation (C9/C10) | Symmetry sectors reduce state-vector dim; TN block structure; Clifford symmetries reduce tableau | TensorCircuit-NG and cotengra exploit circuit symmetry for hyper-optimized contraction. |
| M9 time complexity | State-vector: `O(gates·2ⁿ)` time, `O(2ⁿ)` memory. TN: `O(exp(treewidth))` (→ polynomial when B5 area-law/low-depth, Markov–Shi [@markov_2008_simulating]). Stabilizer: `O(n)` per Clifford gate, `O(n²)` per measurement (Aaronson–Gottesman); exponential in #non-Clifford T-gates via stabilizer rank `~2^{αt}`, `α≈0.396` (Qassim–Pashayan–Gosset 2021). | Use TN/stabilizer whenever applicable; state-vector is the fallback. |
| M10 memory | State-vector: `O(2ⁿ)`. TN: varies with treewidth. Stabilizer: `O(n²)` (tableau). | State-vector hits ~100 GB at `n≈40` (double precision). |
| M11 control knob | TN bond dimension `χ` (controls truncation error) / stabilizer T-count `t` (controls approximation) | State-vector: no approximation. |
| M12 scale frontier | State-vector: `n≈30–50` on HPC (memory-limited). TN: polynomial cost when treewidth is small; random 2D circuits beyond `~53` qubits require slicing + HPC. Stabilizer: Clifford circuits → any `n`; near-Clifford up to ~50 qubits with small T-count. | Frontier set by engine-specific wall. |
| M13 primary approximation / bias | State-vector: none. TN: MPS truncation (bond dim `χ`). Stabilizer rank: exponential approximation for large T-count. | Clifford (T=0) is exact. |
| M14 hard blocker / failure mode | State-vector: `O(2ⁿ)` memory wall. TN: high-depth / high-entanglement 2D circuits have large treewidth → exponential. Stabilizer: T-gate count `t` makes cost `~2^{0.396t}` — non-Clifford universality is hard to simulate classically by design. | No single engine covers all regimes. |

### Cost & scaling

- Time: state-vector `O(gates·2ⁿ)`; TN `O(exp(treewidth))` (polynomial for low-depth / 1D); stabilizer `O(n)` per Clifford gate, `O(n²)` per measurement (Aaronson–Gottesman), + `O(2^{αt})` in the number of non-Clifford T-gates, `α≈0.396`
- Memory: State-vector `O(2ⁿ)`; TN varies; stabilizer `O(n²)`
- Control knob: TN bond dimension `χ` (truncation error) / T-gate count `t` (stabilizer rank)
- Scale frontier: state-vector `n≈30–50`; TN polynomial for low-depth; stabilizer any `n` for Clifford

### Accuracy & guarantees

- Class: state-vector exact; TN controlled bias (bond-dim truncation; variational only for VQE); stabilizer exact for Clifford; exponential in T-count beyond Clifford
- Primary approximation & its control: TN truncation controlled by `χ`; stabilizer approximation controlled by T-count `t`
- Error scaling: state-vector machine precision; TN truncation error `~exp(−χ²/ξ)` for 1D area-law; stabilizer rank grows as `2^{αt}` with `α≈0.396`

### Tasks it computes

- Output probability sampling (the quantum supremacy task)
- Expectation values `⟨ψ|O|ψ⟩` of Pauli strings and local observables
- VQE: variational energy minimization via parametrized circuits
- Hamiltonian simulation: `e^{−iHt}|ψ₀⟩` via Trotter or QSVT circuits
- Circuit noise modeling and fidelity estimation

### Recommended for (models / regimes)

- **State-vector:** small-`n` circuits (`n ≲ 30`) where exactness is required; debugging and validating quantum algorithms
- **TN / MPS:** 1D brickwork circuits, shallow 2D circuits, VQE with low entanglement [@vidal_2003_slightly]; hyper-optimized for random 2D circuits up to Google Sycamore scale [@gray_2021_hyper]
- **Stabilizer:** Clifford circuits of any size (QEC, stabilizer state prep); near-Clifford approximations when T-count is small
- Per `method-property-map.md`: choose engine by matching circuit entanglement to the engine's efficiency regime

### Key reference

[@markov_2008_simulating] — proves that classical simulation cost equals `exp(treewidth)` of the circuit's contraction graph; the foundational complexity result for TN-based circuit simulation.
Rendered: `../../literature/quantum-circuit-simulation/quant-ph-0511069_simulating-quantum-computation-by-contracting-tensor-network.md` _(reused)_.

[@vidal_2003_slightly] — introduces MPS/TEBD for efficient simulation of slightly entangled (area-law) quantum computations; the basis for 1D circuit TN simulation.
Rendered: `../../literature/quantum-circuit-simulation/quant-ph-0301063_efficient-classical-simulation-of-slightly-entangled-quantum.md` _(reused)_.

[@gray_2021_hyper] — hyper-optimized tensor network contraction (cotengra) for large 2D random circuits; state-of-the-art slicing + contraction-order optimization.
Rendered: `../../literature/quantum-circuit-simulation/2002.01935_hyper-optimized-tensor-network-contraction.md` _(reused)_.

### Benchmarks

- State-vector frontier: `n=53` Google Sycamore (2019); `n≈50` routine on HPC clusters.
- TN treewidth result: Markov–Shi (2008) proved cost = `exp(treewidth)` [@markov_2008_simulating]; verified in `method-survey.md` §7.5.
- Stabilizer rank exponent: `α≈0.396` (Qassim–Pashayan–Gosset 2021) — verified in `method-survey.md` §7.5.
- MPS VQE for 1D circuits: polynomial cost for area-law entanglement [@vidal_2003_slightly].

## How it is used / Operational

**Owning skill:** `/method-qcs` (primary); `/using-tensorcircuit-ng` (TensorCircuit-NG implementation).

**Default workflow:**
1. Choose engine: state-vector (`n ≲ 30`) → TN/MPS (`n > 30`, low entanglement) → stabilizer (Clifford-heavy).
2. State-vector: construct circuit as gate sequence; apply gates with TensorCircuit-NG's `tc.Circuit`; measure expectation values.
3. TN: build contraction graph; use cotengra (`gray_2021_hyper`) for hyper-optimized order; contract with GPU acceleration.
4. Stabilizer: represent state as Clifford tableau; apply Clifford gates in `O(n)` each; T-gates via stabilizer-rank decomposition.
5. For VQE: define parametrized circuit; differentiate expectation value via parameter-shift rule; optimize with gradient descent.

**Verification pointers:**
- Cross-check state-vector vs TN at small `n` where both are feasible.
- Verify Clifford circuits with stabilizer formalism against state-vector (exact agreement expected).
- For VQE, check energy convergence and compare with ED at small system sizes.

**Cross-links:**
- Survey: `method-survey.md` §7.5 (Quantum-circuit simulation)
- Model↔method gate: `method-property-map.md` (circuit-sim profile)
- Complementary methods: TEBD (same MPS engine for lattice dynamics), VMC/NQS (variational, no circuit structure required)
