# Symmetric neural quantum state for challenge 15

This submission computes the finite-sphere neutral gap at ν = 1/3 with a shared neural network in exact angular-momentum sectors. The completed benchmark covers N = 4, 5, 6. An explicit Slater-determinant expansion enforces fermionic antisymmetry, and Hamiltonian-independent intertwiners enforce SO(3) equivariance. The implementation enumerates the finite Hilbert space and supports N = 2 through 6.

The main results and uncertainty discussion are in [REPORT.md](REPORT.md). The challenge and its acceptance criteria are recorded in the upstream issue. [Challenge 15](https://github.com/QuantumBFS/quantum.harness/issues/15)

## Reproduce

Run these commands from the harness root. The first command creates an isolated, pinned Python 3.13 environment and runs all three sizes, all three training seeds, and the independent MC measurements. `uv` can supply Python 3.13 when needed.

```sh
uv run --isolated --no-project --python 3.13 \
  --with-requirements tracks/qmc/solutions/desitterf-15/requirements.txt \
  tracks/qmc/solutions/desitterf-15/run.py

uv run --isolated --no-project --python 3.13 \
  --with-requirements tracks/qmc/solutions/desitterf-15/requirements.txt \
  -m pytest tracks/qmc/solutions/desitterf-15/test_graviton.py -q
```

A two-electron end-to-end smoke run takes the same entry point.

```sh
uv run --isolated --no-project --python 3.13 \
  --with-requirements tracks/qmc/solutions/desitterf-15/requirements.txt \
  tracks/qmc/solutions/desitterf-15/run.py \
  --electrons 2 --seeds 3 --steps 10 --samples 128 --measurements 1000 \
  --output tracks/qmc/solutions/desitterf-15/results/smoke
```

The default output directory is `results/` next to `run.py`. It is ignored by Git under the harness submission rules. It contains `summary.json`, network checkpoints `N*_seed*.npz`, and `gap.png` and `gap.pdf`. The JSON records all seeds, checkpoint energies, training traces, coefficients, sampling settings, source hashes, package versions, multiplet diagnostics, and wall times. Each completed size is saved atomically. `--output PATH` selects another directory. `--help` lists the supported controls.

## Hamiltonian and conventions

The electrons are spin polarized and restricted to the LLL. Write F = 2Q = 3(N−1), R = √Q ℓB, and let γᵢⱼ denote the angle between two position vectors. In units e²/(εℓB),

```math
H = P_{\mathrm{LLL}}\sum_{i<j}\frac{1}{2\sqrt Q\sin(\gamma_{ij}/2)}P_{\mathrm{LLL}}.
```

Orbitals are ordered by m = −Q,…,Q. With k = m+Q, their normalized spinor polynomials are

```math
\phi_k(u,v)=\sqrt{\frac{F+1}{4\pi}{F\choose k}}\,u^k v^{F-k}.
```

The wavefunctions are homogeneous of degree F in every particle's spinor and therefore remain within the LLL. The program reports total electron–electron energies. A uniform neutralizing background would add the same constant −N²/(2√Q) to each state at fixed N and F, leaving Δ unchanged.

### Finite-sphere Coulomb matrix elements

The code computes the finite-sphere pseudopotential Vⱼ indexed by the pair's total angular momentum J. Fix particle 1 at the north pole, trace the pair projector over its 2J+1 magnetic components, and write t = sin²(γ/2). Only the m₁ = Q orbital survives at that pole. The remaining density is a sum of binomial factors (1−t)ᵏtᶠ⁻ᵏ. Its Coulomb expectation gives

```math
V_J=\frac{(F+1)^2}{(2J+1)2\sqrt Q}
\sum_{k=0}^{F}|\langle Q,Q;Q,k-Q\mid J,k\rangle|^2
{F\choose k}\,B(F-k+\tfrac12,k+1).
```

For ordered pair orbitals a < b, the antisymmetric pair coefficient is √2 times the Clebsch–Gordan coefficient. Consequently,

```math
V_{ab,cd}=2\sum_{J:\,F-J\,\mathrm{odd}}
\langle Q,m_a;Q,m_b\mid J,M\rangle
\langle Q,m_c;Q,m_d\mid J,M\rangle V_J.
```

The Fock-space embedding applies c†ₐc†ᵦc_d c_c with explicit fermion signs. A two-electron J = 0 pair provides the analytic normalization check V₀ = (F+1)/[(2F+1)√Q]. The regression tests also check the unique Laughlin zero mode of the V₁ parent interaction.

## Shared neural ansatz and exact symmetries

In the M = L occupation block, the kernel of L₊ contains precisely the highest-weight copies of the L irrep. Denote its orthonormal columns by Cᴸᴸ. Generate the remaining magnetic components with

```math
C^{L,M-1}=\frac{L_- C^{L,M}}{\sqrt{(L+M)(L-M+1)}}.
```

After lowering, an orthogonal projector onto L² = L(L+1) removes amplified floating-point contamination from higher-L states. It acts on the already-lowered columns and retains their common multiplicity gauge. All this preprocessing uses angular-momentum operators alone.

One real MLP takes a one-hot input for L = 0 or 2, has a shared width-16 tanh hidden layer, and outputs the multiplicity coefficients. The output is sliced to the dimension of the requested sector and normalized,

```math
h_L=\tanh(W_1 e_L+b_1),\qquad
c_\theta^L=\frac{[W_2 h_L+b_2]_{1:d_L}}
{\|[W_2 h_L+b_2]_{1:d_L}\|}.
```

With Φₓ the normalized Slater determinants, the full wavefunction is

```math
\Psi_\theta^{L,M}(\Omega)=
\sum_{x,\alpha}\Phi_x(\Omega)C^{L,M}_{x\alpha}c^L_{\theta,\alpha}.
```

Every determinant changes sign under particle exchange. Every column of C has exactly the target angular momentum. The coefficients are independent of M, so the five L = 2 components share one coefficient vector. For a common spinor rotation U = exp(−iθ n·σ/2), the vector ordered by ascending M obeys

```math
\boldsymbol\Psi_\theta^L(U\Omega)=
\exp(-i\theta\,\mathbf n\cdot\mathbf L)\boldsymbol\Psi_\theta^L(\Omega).
```

The coordinate check evaluates both sides on eight random electron configurations with independently chosen rotation axes and angles. It also swaps two electron coordinates.

The two sector inputs can generate linearly independent hidden activations. A shared output matrix can then assign arbitrary real coefficient vectors to these inputs. Thus the parameterization can cover each complete real multiplicity space in these finite systems. Real coefficients suffice for the real Coulomb matrices in the chosen basis. The same network represents both sectors within one N. Each system size receives its own trained network.

## Optimization and uncertainty

Training minimizes the state-averaged energy (E₀+E₂)/2 with Adam. At every step and in each sector, 4096 independent occupation configurations are sampled from |C cθ|². The local energy is (Hψ)ₓ/ψₓ. Its covariance with ∂θ log|ψₓ| gives the VMC gradient, with the n/(n−1) finite-sample covariance correction. At exact discrete nodes, the enumerated basis supplies the analytic gradient contribution 2Σₓ Cₓα(Hψ)ₓ over ψₓ = 0. An analytic normalization Jacobian propagates this gradient through the shared MLP. The network receives no ED eigenvectors or labels during training.

The finite basis permits direct Born draws and exact Rayleigh energies for monitoring. The lowest monitored state-averaged energy selects a checkpoint, followed by selection among seeds 11, 23, 37. This uses full finite-basis information and contributes to the exponential resource cost. Exact diagonalization runs after optimization and checkpoint selection to provide a reference.

Each selected sector is measured with 262144 fresh independent Born draws and a separate measurement seed. Its standard error is the sample local-energy standard deviation divided by √n. Independent ground- and excited-state measurements give

```math
\mathrm{SE}(\Delta)=\sqrt{\mathrm{SE}(E_0)^2+\mathrm{SE}(E_2)^2}.
```

The report separates these sampling errors from numerical precision and the ED-measured signed gap bias δE₂−δE₀. The energy variance and eigenstate residual quantify convergence. All three training seeds are retained in the JSON and checkpoints.

## Files

| File | Responsibility |
|---|---|
| `sphere.py` | LLL basis, finite-sphere Coulomb interaction, angular momentum, intertwiners, coordinate wavefunction |
| `nqs.py` | Shared MLP, exact and sampled gradients, stochastic Adam, independent MC estimator |
| `run.py` | Reproduction entry point, seed selection, ED comparison, symmetry certification, outputs and plots |
| `test_graviton.py` | Physics, gradient, convergence, estimator, and command-line regression tests |
| `REPORT.md` | Measured results, uncertainty budget, spin-2 checks, scope and limitations |

The finite-basis construction and direct Born sampler retain exponential scaling. Reaching sizes beyond ED requires a different representation and sampler. The present calculations establish the small-system spin-2 benchmark. A helicity-resolved metric-operator response and a thermodynamic extrapolation remain open extensions. The reference paper defines chirality through separate operator spectral weights. [Liou et al., PRL 123, 146801 (2019)](https://arxiv.org/abs/1904.12231)
