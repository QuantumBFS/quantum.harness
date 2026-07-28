## Team

| | |
|---|---|
| **Team name** | Agent of My Agent Is Not My Agent |
| **Members** | Zhu-YanZhang |

## Challenge

| Row | |
|---|---|
| **Challenge** | Test whether long-range universality in the 1D transverse-field Ising chain crosses over at σ*=7/4 or σ*=2 by measuring critical exponents with MPS and using QMC as an independent cross-check. |
| **Catalog issue** | `Addresses #86` — “Where does long-range universality end? Three adversarial tests of the sigma*=7/4 vs 2 dispute,” released by Kun Chen, Institute of Theoretical Physics, Chinese Academy of Sciences. |
| **Track** | `tracks/mps/` — our call: issue #86 spans MPS, QMC, and VMC-NQS; MPS is our primary method and QMC is an independent cross-check. |

## Workflow

The implementation uses **Python 3.11**, **TeNPy**, and the **MPS/DMRG**
method. The primary calculation uses a custom compact matrix-product-operator (MPO)
representation of the periodic long-range transverse-field Ising chain. The
finite-size reference coupling is the pinned Hurwitz-zeta image sum

```text
J_L(r) = L^(-1-σ) [ζ(1+σ, r/L) + ζ(1+σ, 1-r/L)].
```

The infinite-line power law is approximated by a sum of exponentials, and each
exponential is periodized analytically before it enters the MPO. The workflow
keeps Hamiltonian-approximation error (finite exponential count `K`) separate
from MPS-truncation error (finite bond dimension `χ` and discarded weight).
SSE is reserved for a later independent cross-check and is not part of the
initial MPO implementation.

### Environment

Use the existing conda environment:

```bash
conda run -n mps python <script> [arguments]
```

It must provide TeNPy, NumPy, and SciPy. The current verified environment is
Python 3.11.15, TeNPy 1.1.0 from `~/tenpy`, NumPy 2.4.6, and SciPy 1.17.1.
No project-local TeNPy installation is required.

Phase 1 validation:

```bash
cd tracks/mps/solutions/agent-of-my-agent-is-not-my-agent
conda run -n mps python -m pytest -q
conda run -n mps python scripts/validate_couplings.py \
  --length 64 --sigma 1.75
```

Phase 2 exponential-fit validation:

```bash
conda run -n mps python scripts/validate_exponential_fit.py \
  --length 64 --sigma 1.75 --r-fit 512 \
  --k-values 8 12 16 20 24 --output-dir results/phase2
```

The fit uses only the infinite-chain kernel `r^(-1-σ)`. The exact periodic
Hurwitz-zeta values enter only after fitting, when the exponential sum is
periodized analytically. The command writes maximum/RMS error summaries and
distance-resolved CSV profiles for both validation layers.

## Development milestones

1. **Exact Hurwitz-zeta coupling validation** — compare the finite-ring formula
   with converged direct image sums and verify positivity, periodic symmetry,
   and pair-counting conventions.
2. **Exponential fitting validation** — fit the infinite-line power law for
   `K = 8, 12, 16` and report distance-resolved coupling errors after analytic
   periodization.
3. **Periodized MPO construction** — encode forward and wrapped exponential
   channels and verify that the MPO reconstructs the intended coefficient
   table.
4. **MPO observable validation** — compare the compact MPO with the exact
   pairwise Hamiltonian on small systems using the ground-state energy, first
   excitation gap, and correlation functions.
5. **DMRG scaling calculations** — independently converge `χ` at each `K`,
   then study the stability of `Γ_c(K)` and `z(K)` with increasing exponential
   count.

## Layout

| Path | Purpose |
|---|---|
| `src/` | Reusable coupling, fitting, MPO, and analysis modules. |
| `scripts/` | Runnable validation and production entry points. |
| `tests/` | Deterministic unit, regression, and small-system tests. |
| `docs/methodology.md` | Mathematical conventions, algorithms, and error budget. |
| `results/phase2/` | Phase 2 JSON summaries and distance-resolved CSV profiles. |

Later production data, plots, and reports belong under
`tracks/mps/results/<timestamped-run>/`; the small Phase 2 validation artifacts
are kept locally in this solution folder for review.
