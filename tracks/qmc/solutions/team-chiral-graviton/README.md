# Symmetric Neural-Network Ansatz for the Chiral Graviton in ν = 1/3 FQH State

**Team**: Shawn Zhang, Wenqi-Yang-HKU, xuexinqiu
**Track**: Quantum Monte Carlo / Neural Quantum States
**Challenge**: [#15](https://github.com/QuantumBFS/quantum.harness/issues/15)

## Overview

We implement a **SO(3)-equivariant neural quantum state (NQS)** on the Haldane sphere to compute the neutral gap Δ = E(L=2) − E(L=0) of the chiral graviton mode in the ν = 1/3 fractional quantum Hall liquid.

### Architecture

```
Ψ(θ, φ) = Ψ_J(r) × exp(f_NN({r_ij}))
```

- **Ψ_J**: Laughlin Jastrow factor (m=3) — handles fermionic antisymmetry analytically
- **f_NN**: Permutation-invariant, SO(3)-equivariant neural network correction (chord-distance features)
- **L = 0 ground state**: Optimized via variational Monte Carlo with minSR
- **L = 2 excitation**: Computed via single-mode approximation (SMA) + variational excited-state optimization

### Results

| N | E(L=0) [e²/εℓ_B] | E(L=2) [e²/εℓ_B] | Δ [e²/εℓ_B] | ⟨L²⟩ |
|---|---|---|---|---|
| 4 | | | | 6 |
| 6 | | | | 6 |
| 7 | | | | 6 |
| 8 | | | | 6 |

*Results to be filled after training.*

## Dependencies

- Python ≥ 3.10
- PyTorch ≥ 2.0
- NumPy
- SciPy

## Usage

```bash
# Ground state calculation
python run.py --mode ground --n_elec 6 --steps 10000

# Excited state (L=2)
python run.py --mode excited --n_elec 6 --steps 10000

# Full pipeline: ground → excited → report
python run.py --mode full --n_elec 6 --steps 10000

# Equivariance test
python run.py --mode test_symmetry --n_elec 6
```

## File Structure

```
src/
├── haldane_sphere.py    # Haldane sphere geometry, spinor coordinates
├── lauglin_wf.py        # Laughlin (m=3) Jastrow factor
├── ansatz.py            # SO(3)-equivariant neural network ansatz
├── hamiltonian.py       # Chord-distance Coulomb interaction
├── sampler.py           # Metropolis-Hastings on sphere
├── vmc.py               # VMC optimization loop (minSR)
├── excitations.py       # L=2 excitation (SMA + variational)
├── ed_crosscheck.py     # Exact diagonalization for small N
└── utils.py             # Utilities
run.py                   # Main entry point
tests/
└── test_symmetries.py  # Equivariance and antisymmetry tests
```

## References

- S.-F. Liou et al., *Chiral Gravitons in FQH Liquids*, PRL **123**, 146801 (2019), [arXiv:1904.12231](https://arxiv.org/abs/1904.12231)
- F. D. M. Haldane, *Fractional Quantization of the Hall Effect*, PRL **51**, 605 (1983)
- R. B. Laughlin, *Anomalous Quantum Hall Effect*, PRL **50**, 1395 (1983)
