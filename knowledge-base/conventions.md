# Conventions

Harness-default conventions for Hamiltonians, observables, and notation. Skills assume these unless the user states otherwise. Common alternatives are noted so the agent can translate.

## Spin operators

Harness default: spin-`S` operators `S^a` with `[S^a, S^b] = i ε_{abc} S^c` and eigenvalues `m ∈ {-S, ..., S}`. For S=1/2, `S^a = σ^a / 2` where `σ^a` are Pauli matrices.

Software default (Julia/ITensors): `op("Sz", s)` returns `S^z` (not `σ^z`). When citing a Hamiltonian written in Pauli notation, divide each operator by 2 in code (or absorb factor 4 into the coupling for two-spin terms).

Common alternative: Pauli-matrix notation `H = J Σ σ_i^a σ_j^a` with `σ^a` Pauli. Used in many condensed-matter papers. Distinguish from `H = J Σ S_i^a S_j^a` by a factor of 4 per bilinear.

## Heisenberg-family Hamiltonians

```
H = J Σ_{<ij>} S_i · S_j        (S-operator convention; antiferromagnetic for J > 0)
```

XXZ generalization:
```
H = J Σ [Δ S^z_i S^z_j + (S^x_i S^x_j + S^y_i S^y_j)]
```
At Δ = 1, recovers isotropic Heisenberg. At Δ = 0, XX (XY) model.

`<ij>` denotes nearest-neighbor pairs counted once (no double counting).

## Hubbard-family Hamiltonians

```
H = -t Σ_{<ij>,σ} (c†_{iσ} c_{jσ} + h.c.) + U Σ_i n_{i↑} n_{i↓}
```

`t > 0` for the standard hopping convention. Particle-hole symmetric form at half-filling adds `-(U/2) Σ_i n_i + const`; the standard form above puts the chemical potential at `μ = U/2` for half-filling.

t-J reduction: at large `U/t` and finite hole density, project out double occupancy; the effective model is `H_{tJ} = -t P (c†c + h.c.) P + J Σ S_i · S_j` with `J = 4t²/U` and `P` the no-double-occupancy projector.

## Lattice and boundary conditions

- Site index `i` is integer; coordinates depend on lattice.
- Default boundary: open (OBC) for DMRG-driven workflows; periodic (PBC) for ED and QMC where supported.
- Cylinder geometries (used in 2D DMRG): periodic in the short direction, open in the long direction. Width `L_y` should be small enough for the bond-dim budget.

## Observable conventions

- Energy-per-site `E/N` is the canonical reported quantity.
- Spin correlations: `⟨S_i · S_j⟩` (full SU(2)-invariant) unless `⟨S^z_i S^z_j⟩` is specified.
- Structure factor `S(q) = (1/N) Σ_{ij} e^{iq·(r_i - r_j)} ⟨S_i · S_j⟩`.

## Energy units

Default: set the largest coupling to 1 (e.g., `J = 1` for Heisenberg, `t = 1` for Hubbard). All other parameters dimensionless ratios. Report energies in these units unless the user requests otherwise.
