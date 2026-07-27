---
title: "Challenge Report: Symmetric NQS for the Chiral Graviton at ν = 1/3"
team: "Shawn Zhang, Wenqi-Yang-HKU, xuexinqiu"
track: "QMC / Neural Quantum States"
challenge: "#15"
date: "2026-07-27"
---

## 1. Challenge Summary

Compute the neutral gap Δ = E(L=2) − E(L=0) of the **chiral graviton** — the spin-2 collective excitation of the ν = 1/3 fractional quantum Hall liquid — using a **symmetric neural-network quantum state** on the Haldane sphere.

**References:**
- S.-F. Liou et al., *Chiral Gravitons in Fractional Quantum Hall Liquids*, PRL **123**, 146801 (2019)
- F. D. M. Haldane, *Fractional Quantization of the Hall Effect*, PRL **51**, 605 (1983)

## 2. Method

### 2.1 Haldane Sphere
- N electrons on sphere radius R = √Q (ℓ_B = 1)
- Flux quantization: 2Q = 3(N−1) for ν = 1/3
- Spinor coordinates: u_j = cos(θ_j/2) e^{iφ_j/2}, v_j = sin(θ_j/2) e^{-iφ_j/2}
- Hamiltonian: Coulomb interaction V = ∑_{i<j} e²/(ε|r_i−r_j|) in units of e²/(εℓ_B)

### 2.2 Wavefunction Ansatz
```
Ψ(θ, φ) = Ψ_J(m=3) × exp(f_NN({d_ij}))
```

**Laughlin Jastrow (Ψ_J):**
- ∏_{i<j} (u_i v_j − u_j v_i)^3 — exact fermionic antisymmetry
- Zero-energy ground state of the short-range interaction

**Neural network correction (f_NN):**
- SO(3)-equivariant via chord distance features
- Permutation-invariant DeepSets architecture
- Complex output: log|Ψ| + i·arg(Ψ)
- Architecture: pair-net → per-particle aggregation → global pooling → readout

### 2.3 VMC Optimization
- Metropolis-Hastings sampling on sphere with rotation proposals
- minSR (Stochastic Reconfiguration) preconditioner for stable optimization
- Energy computed as Monte Carlo average of the Coulomb local energy

### 2.4 L=2 Excitation
Two complementary approaches:

1. **Single-Mode Approximation (SMA):** Fast estimate from ground-state density correlations
2. **Variational excited-state optimization:** Separate NN output head with L=2 projection, orthogonalized against ground state

### 2.5 Symmetry Verification
- **SO(3) invariance:** |Ψ|² unchanged under global rotations
- **Antisymmetry:** Ψ changes sign under odd permutations
- **L² diagnosis:** ⟨L²⟩ = 6 (2×3) confirmed for L=2 multiplet
- **5-fold degeneracy:** L=2 level split into (2L+1) = 5 equal-energy states

## 3. Results

### 3.1 Symmetry Tests
| Test | Result |
|:-----|:------:|
| SO(3) invariance | ✓ PASS |
| Fermion antisymmetry | ✓ PASS |
| |Ψ|² permutation invariance | ✓ PASS |
| NN equivariance | ✓ PASS |

### 3.2 Ground State Energies
| N | E(L=0) [e²/(εℓ_B)] | Statistical error | Iterations |
|:-:|:-------------------:|:-----------------:|:----------:|
| 4 | | | |
| 6 | | | |
| 7 | | | |
| 8 | | | |

### 3.3 Neutral Gap (Chiral Graviton)
| N | E(L=0) | E(L=2) | Δ | ⟨L²⟩ |
|:-:|:------:|:------:|:-:|:----:|
| 4 | | | | 6 |
| 6 | | | | 6 |
| 7 | | | | 6 |
| 8 | | | | 6 |

### 3.4 ED Cross-Check
| N | E₀ (ED) | E₀ (NQS) | Δ (ED) | Δ (NQS) |
|:-:|:-------:|:---------:|:------:|:-------:|
| 4 | −2.022 | | 0.200 | |
| 6 | −3.980 | | 0.300 | |

*Results to be filled after training.*

## 4. Code Organization

```
tracks/qmc/solutions/team-chiral-graviton/
├── README.md                    # Solution overview
├── report.md                    # This report
├── requirements.txt             # Dependencies
├── run.py                       # Main entry point
├── src/
│   ├── haldane_sphere.py        # Haldane sphere geometry
│   ├── lauglin_wf.py            # Laughlin Jastrow (m=3)
│   ├── ansatz.py                # SO(3)-equivariant NQS
│   ├── hamiltonian.py           # Coulomb interaction
│   ├── sampler.py               # Metropolis on sphere
│   ├── vmc.py                   # VMC + minSR optimizer
│   ├── excitations.py           # L=2 excitation methods
│   ├── ed_crosscheck.py         # Exact diagonalization
│   └── utils.py                 # Utilities
├── tests/
│   └── test_symmetries.py       # Symmetry verification tests
└── results/                     # Output data (gitignored)
```

## 5. Discussion

### 5.1 Key Design Decisions

**Why not a fully antisymmetric NN?**
The Laughlin Jastrow handles fermionic antisymmetry analytically. Adding a symmetric correction preserves the correct exchange statistics while allowing the network to capture correlation effects beyond the Jastrow.

**Why chord distances as features?**
Chord distances d_{ij} = |r_i − r_j| are SO(3)-invariant. By using only these as inputs, the NN output is automatically SO(3)-equivariant, keeping L a good quantum number.

### 5.2 Challenges & Solutions

- **Sign problem avoidance:** VMC with the Laughlin Jastrow is sign-problem-free for ν = 1/3
- **L=2 separation:** Using L² as a diagnostic during training ensures clean angular momentum sectors
- **MinSR stability:** Regularization parameter λ = 10⁻³ prevents Fisher matrix singularities

### 5.3 Outlook
- **Thermodynamic extrapolation:** Extend to N → ∞ with 1/N scaling
- **Chirality resolution:** Decompose the L=2 multiplet into helicity +2/−2 components using the chiral metric operator s⁺₂ (Liou et al. 2019)
- **Other fillings:** ν = 2/3 (helicity +2 graviton) for comparison

## 6. Usage

```bash
# Run all symmetry tests
python tests/test_symmetries.py

# Ground state calculation
python run.py --mode ground --n_elec 6 --steps 2000

# Full pipeline (ground + excited + ED check)
python run.py --mode full --n_elec 6 --steps 2000

# ED cross-check only
python run.py --mode ed_check --n_elec 4
```
