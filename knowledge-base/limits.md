# Exact Limits and Reductions

Authoritative limit and mapping facts for sanity checks. Skills cite this card to verify a calculation behaves correctly in known limits.

## Spin-model limits

### Isotropic Heisenberg via XXZ

`H_XXZ = J Σ [Δ S^z_i S^z_j + (S^x_i S^x_j + S^y_i S^y_j)]` reduces to isotropic Heisenberg at `Δ = 1`. At `Δ → ∞` it becomes the classical Ising model (S^z eigenstates). At `Δ = 0` it is the XX (free-fermion via Jordan-Wigner in 1D) model.

### Ferromagnetic Heisenberg ground state

For `J < 0` (ferromagnetic), the ground state of the isotropic Heisenberg model on any lattice is the fully polarized state with `S_total = N S` and `E_FM/N = J z S² / 2` where `z` is the coordination number.

### Trivial-coupling limits

- `J = 0` Heisenberg → uncoupled spins, `2^N`-fold degenerate ground state.
- `J' = 0` in J1-J2 → reduces to NN Heisenberg.
- `J = 0` t-V → free fermions on the lattice.

### 1D antiferromagnetic Heisenberg (Bethe ansatz)

For S=1/2 NN Heisenberg chain with `J > 0`, the exact ground-state energy per site in the thermodynamic limit:
```
E/N = -ln 2 + 1/4 ≈ -0.443147 J
```
(Pauli-σ convention: `E/N = 4 × (-ln 2 + 1/4) = -1.7726`. Cross-check the convention before comparing.)

The system is gapless with `z = 1` dynamical exponent.

### Large-S (semiclassical) limit

As `S → ∞`, the Heisenberg model maps to a classical spin model on the lattice. Quantum corrections appear at `1/S` (linear spin-wave theory).

## Hubbard / fermion limits

### `U = 0` Hubbard

Free fermions on the lattice. Ground-state energy is the sum of single-particle energies up to the Fermi level. Tight-binding band structure is exact.

### `U → ∞` Hubbard, finite hole density

Project out double occupancy. Effective Hamiltonian is the t-J model:
```
H_{tJ} = -t P (c†_{iσ} c_{jσ} + h.c.) P + J Σ_{<ij>} (S_i · S_j - n_i n_j / 4)
J = 4 t² / U  (leading order in t/U)
```
The `-n n / 4` term is sometimes absorbed; check convention in `conventions.md`.

### Half-filled bipartite Hubbard, `U ≫ t`

Reduces to spin-1/2 Heisenberg antiferromagnet on the bipartite lattice with `J = 4 t² / U`. Néel order on square lattice; gapless on chain (1D).

### Particle-hole symmetry

Half-filled Hubbard on a bipartite lattice at any U is particle-hole symmetric. Use this to verify code: `n↑ = n↓ = 1/2`, `⟨n_i n_j⟩` constraints.

### Atomic limit (`t = 0`)

Each site is independent; ground state has `N_e` particles distributed to minimize `U Σ n↑ n↓`. At half-filling and `U > 0`, single occupancy on every site (Mott insulator at all `U > 0` in atomic limit; the kinetic energy stabilizes the Mott phase only above a critical `U_c` in the Hubbard model proper).

## Anderson impurity limits

### `V = 0` (no hybridization)

Impurity decouples from bath. Local levels filled per `μ` and `U`. Trivial.

### `U = 0`

Resonant level model; exactly solvable.

### Kondo regime

Local-moment regime: `U/Γ ≫ 1` (where `Γ` is hybridization width) and `ε_d` near `-U/2`. Develops an exponentially small Kondo scale `T_K ~ Γ exp(-π U / 8 Γ)` (symmetric Anderson, Haldane formula). Crossover from local moment to Kondo singlet as `T < T_K`.

## Geometric / dimensional limits

- 1D systems: Mermin-Wagner forbids continuous-symmetry breaking at `T = 0` for short-range interactions (no Néel order in 1D Heisenberg). Algebraic correlations.
- 2D Heisenberg AFM (square): has Néel order at `T = 0`; `E/N` and staggered moment known to high precision from QMC.
- Frustrated 2D (triangular, kagome): no exact reductions to simpler problems; rely on numerics and scaling.

## Using these limits

For verification:
- Set the relevant parameter (J, U, V, S) to its limiting value.
- Check that the calculation reproduces the known answer above (or its scaling form).
- Discrepancy at the limit indicates a setup error (sign convention, sector, factor of 2).
