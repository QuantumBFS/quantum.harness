# Project: QMC Track + Challenge #15 (Chiral Graviton NQS)

**Two workstreams — one track.** (1) Reproduce the QMC track's target paper (CPMC-Lab). (2) Solve challenge #15 (chiral graviton NQS).

## Workstream A: QMC Track Reproduction

Reproduce figures from the Constrained Path Monte Carlo (CPMC) package paper:

- **Paper:** Nguyen, Shi, Xu, Zhang, "CPMC-Lab: A Matlab package for Constrained Path Monte Carlo calculations," *Comput. Phys. Commun.* **185**, 3344 (2014), [arXiv:1407.7967](https://arxiv.org/abs/1407.7967).
- **Physics:** Single-band repulsive Hubbard model. CPMC controls the fermion sign problem by constraining the random walk with a trial wavefunction — trading exponential-cost exactness for polynomial-cost, systematically biased ground-state energy.
- **Target figures (chosen interactively):** sign problem stability, energy vs U/t benchmarked against ED, or finite-size scaling to the thermodynamic limit.
- **Reference text:** S. Zhang, "Auxiliary-Field Quantum Monte Carlo at Zero- and Finite-Temperature," in *Many-Body Methods for Real Materials* (2019), [manuscript](https://www.cond-mat.de/events/correl19/manuscripts/zhang.pdf).

## Workstream B: Challenge #15 — Chiral Graviton NQS

- **Team:** Plasma-Team (Chenzhuo Xue)
- **PR:** [#208](https://github.com/QuantumBFS/quantum.harness/pull/208)
- **Solution dir:** `tracks/qmc/solutions/Plasma-Team/`
- **Challenge issue:** [QuantumBFS/quantum.harness#15](https://github.com/QuantumBFS/quantum.harness/issues/15) (released by Lei Wang, IOP CAS)

### Physics target

Compute the neutral gap **Δ = E(L=2) − E(L=0)** in units of e²/εℓ_B for N electrons at ν=1/3 on the Haldane sphere (flux 2Q = 3(N−1)), chord-distance Coulomb interaction.

The L=2 state is the **chiral graviton** — a spin-2 collective excitation, the quantum of the FQH fluid's internal metric fluctuations (emergent gravity analogue).

### Two hard symmetry constraints

1. **Fermionic antisymmetry** — enforced via Slater determinant + backflow + Jastrow.
2. **SO(3) rotational equivariance** — enforced via monopole harmonics Y_{Qlm} + Clebsch-Gordan tensor products `(f⊗g)^{(L)}_M = Σ C^{LM}_{l₁m₁,l₂m₂} f^{(l₁)}_{m₁} g^{(l₂)}_{m₂}`.

Breaking either constraint mixes L sectors and makes Δ uninterpretable.

### Verification checklist

- [ ] ⟨L²⟩ = 6 on L=2 excited state (confirms spin-2)
- [ ] 5-fold degeneracy of L=2 manifold (2L+1 = 5)
- [ ] ED cross-check at small N (N ≤ 8)
- [ ] Chirality decomposition via s⁺₂ operator (bright helicity −2 vs dark +2)
- [ ] N → ∞ extrapolation (stretch goal)

### Key reference

Liou, Haldane, Yang, Rezayi, *Chiral Gravitons in Fractional Quantum Hall Liquids*, Phys. Rev. Lett. 123, 146801 (2019), [arXiv:1904.12231](https://arxiv.org/abs/1904.12231).

## Environment

| Tool | Status | Notes |
|------|--------|-------|
| Python (NetKet / JAX / PyTorch) | ✅ working | `.venv` in repo root, pip/uv OK |
| Julia | ❌ broken | Binary artifact downloads blocked; use Python |
| Git / GitHub CLI | ✅ working | SSH via proxy tunnel; `HTTPS_PROXY=http://127.0.0.1:7890` for gh |
| MATLAB | ⚠️ unknown | Needed for CPMC-Lab reproduction (Workstream A) |
| Cluster (GCE) | ⚠️ available | `instance-20260414-113155.us-central1-f.mumax3` (34.133.218.188) |

## Agent coordination

**Main agent dispatches subagents.** Decompose each specific task into parallel subtasks and dispatch subagents. Subagents should:

1. **Read this file first** — it carries both workstreams' targets, constraints, and environment state.
2. **Work independently** — no cross-talk unless results must be merged.
3. **Report structured results** — what was computed, value, verification status, issues.
4. **Write code to `tracks/qmc/solutions/Plasma-Team/`** — keep solution code under the team directory.
5. **Never commit outside the solution folder** — results, data, plots go to `tracks/qmc/results/` (gitignored).

The main agent handles: task decomposition, parallelism decisions, merging subagent results, quality gate before reporting.

## Repository layout (what matters)

```
tracks/qmc/solutions/Plasma-Team/   ← our code (committed)
tracks/qmc/results/                 ← run outputs (gitignored)
tracks/qmc/README.md                ← QMC track specification
skills/take-challenge/SKILL.md      ← registration workflow
skills/                             ← harness skills (read-only)
```
