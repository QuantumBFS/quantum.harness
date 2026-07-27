# 2D-TN-Team — 2D finite-temperature tensor networks

Registration for [challenge #147](https://github.com/QuantumBFS/quantum.harness/issues/147) — *2D finite-temperature tensor networks*, released by Wei Li (ITP CAS). Track: `peps`.

## Team

| | |
|---|---|
| **Team name** | 2D-TN-Team |
| **Members** | 杨婧 (Yang Jing), 彭鹏 (Peng Peng) |

## Challenge

| | |
|---|---|
| **Challenge** | Extend PEPO or METTS to 2D finite-temperature tensor networks — 10×10 transverse-field Ising model, compute thermodynamics across the quantum-critical fan βJ ∈ [0.1, 1.0], validate against QMC |
| **Catalog issue** | [#147](https://github.com/QuantumBFS/quantum.harness/issues/147) — released by Wei Li, ITP CAS |
| **Track** | `peps` — PEPS Based Algorithm |

## Model

Transverse-field quantum Ising model on a 10×10 square lattice (open boundary conditions):

H = −J Σ_⟨i,j⟩ σᶻ_i σᶻ_j − h Σ_i σˣ_i ,   J = 1 ,   h/J ∈ {2.5, 3.0, 3.5}

Field chosen near the quantum critical point h_c/J ≈ 3.044, where the small gap and diverging correlation length make thermal tensor-network compression genuinely hard.

## Plan

- Implement a PEPO- or METTS-based 2D finite-temperature algorithm (Trotter + variational compression, or stochastic PEPS sampling).
- Compute thermodynamics over βJ ∈ [0.1, 1.0]: free-energy density f, internal-energy density u, specific heat C. (Bonus: uniform susceptibility χ.)
- Convergence study: bond dimension D (PEPO) or sample count (METTS), with plots.
- Validate every quantity against sign-free QMC (SSE/worm) reference on the same 10×10 lattice; ED on 4×4 as a development sanity check.
- (Bonus) Beat-or-match tanTRG / MPO-LTRG at equal accuracy-vs-cost.
- Open-source code + one-command reproduction script.

## Deliverables

| # | Deliverable | Mandatory |
|---|-------------|-----------|
| 1 | Thermodynamic curves f(T), u(T), C(T) over βJ ∈ [0.1, 1.0] | Yes |
| 2 | Convergence analysis (in D or sample count) with plots | Yes |
| 3 | Validation against QMC reference data | Yes |
| 4 | Source code + technical document + one-command test script | Yes |
| 5 | tanTRG comparison: accuracy, timing, memory | Bonus |
| 6 | Uniform susceptibility χ(T) | Bonus |

Addresses #147
