# QMC Track + Challenge #15 — Plasma-Team

**Two workstreams, one repo.**

| | Workstream A | Workstream B |
|---|---|---|
| **What** | QMC track reproduction | Challenge #15 |
| **Target** | CPMC-Lab: Hubbard model constrained-path QMC | Chiral graviton gap Δ = E(L=2)−E(L=0) at ν=1/3 |
| **Paper** | [Nguyen et al., CPC 185, 3344 (2014)](https://arxiv.org/abs/1407.7967) | [Liou et al., PRL 123, 146801 (2019)](https://arxiv.org/abs/1904.12231) |
| **Method** | Constrained Path Monte Carlo (MATLAB) | SO(3)-projected NQS (Python: NumPy/SciPy/SymPy) |
| **Verification** | Energy vs U/t vs ED; sign problem stability | ⟨L²⟩=6, 5-fold degeneracy, ED cross-check |

- **Team:** Plasma-Team (Chenzhuo Xue)
- **PR:** [#208](https://github.com/QuantumBFS/quantum.harness/pull/208) · **Solution dir:** `tracks/qmc/solutions/Plasma-Team/`

See [`AGENTS.md`](AGENTS.md) for the full project brief, environment details, and subagent coordination rules.
