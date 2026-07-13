# Gaudin central-spin model — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter) · Tier: B (integrable) · Script: S

## Hamiltonian & conventions

$$ H = \sum_{j=1}^{N_b} A_j\,\mathbf{S}_0\cdot\mathbf{S}_j, \qquad A_j = \frac{1}{j}, \qquad H_i = \sum_{k\ne i}\frac{\mathbf{S}_i\cdot\mathbf{S}_k}{u_i-u_k},\ \ u=(0,-1,\dots,-N_b) $$

Conventions: spin-1/2 `S`-operators (`S^a=σ^a/2`) on `L=N_b+1` sites — a central spin `S_0` coupled to `N_b` bath spins with inhomogeneous couplings `A_j=1/j`. This is the **central-spin (Gaudin) model**: a rational Gaudin magnet. The `H_i` are the `N_b+1` rational Gaudin Hamiltonians for inhomogeneities `u=(u_0,u_1,\dots,u_{N_b})=(0,-1,\dots,-N_b)`; since `u_0-u_j=j`, the central-spin `H` is **exactly** the single Gaudin charge `H_0`. See `.knowledge/conventions.md`.

Model-zoo sibling: the central-spin/Kondo-like impurity physics is discussed in `.knowledge/models/anderson-impurity` and `.knowledge/models/kondo-lattice`; those are lattice/bath impurity models, whereas this card is the exactly-integrable rational-Gaudin central spin with `1/j` couplings.

## Solvability statement

T3 (Bethe ansatz / Yang–Baxter, rational Gaudin): the central-spin model is a rational Gaudin magnet — an integrable system whose `N_b+1` Gaudin Hamiltonians `H_i=\sum_{k\ne i}(\mathbf{S}_i\cdot\mathbf{S}_k)/(u_i-u_k)` mutually commute [@Gaudin1976]. This card ships the **conserved-charge construction**: with the inhomogeneities `u=(0,-1,\dots,-N_b)` the central-spin Hamiltonian is exactly one of these commuting charges, `H=H_0` (because `A_j=1/(u_0-u_j)=1/j`), so its integrability is proven in-card by verifying that all pairwise commutators `[H_i,H_j]` vanish numerically, and its ground-state energy is supplied by exact diagonalization of `H` (the exact numbers), with `[H,\mathbf{S}^2_{\mathrm{tot}}]=0` organising the spectrum into total-spin multiplets. This is Tier B (integrable): the exact structure (commuting charges + Bethe/Gaudin eigenstates) is scripted, but the ground energy at generic `1/j` couplings is an ED number, not a closed form — only the **uniform**-coupling limit has the closed form below.

## The Gaudin story

The scripted exactness is the **integrable structure**, chiral-Potts style: rather than solve the field-free Gaudin/Bethe root equations (numerically delicate), the card builds the `N_b+1` Gaudin charges directly and verifies (i) `H` is literally the charge `H_0`, (ii) `[H_i,H_j]=0` for every pair (the tower of conserved quantities — integrability), and (iii) `[H,\mathbf{S}^2_{\mathrm{tot}}]=0` (SU(2), so eigenstates group into total-spin multiplets). A **second, closed-form coupling set** anchors the physics: for **uniform** coupling `A_j=A`, `H=A\,\mathbf{S}_0\cdot\mathbf{S}_{\mathrm{bath}}` with `\mathbf{S}_{\mathrm{bath}}=\sum_j\mathbf{S}_j`, which is diagonal in total spin — `H=\tfrac{A}{2}(\mathbf{S}^2_{\mathrm{tot}}-\mathbf{S}_0^2-\mathbf{S}^2_{\mathrm{bath}})` — with ground energy `-\tfrac{A}{4}(N_b+2)` (maximal bath spin `S_b=N_b/2`, total `S=S_b-\tfrac12`). The ED ground energies for the `1/j` couplings are the pinned exact numbers.

## Exact results

- The central-spin model is a rational Gaudin magnet: `N_b+1` mutually commuting Gaudin charges `H_i=\sum_{k\ne i}(\mathbf{S}_i\cdot\mathbf{S}_k)/(u_i-u_k)` [@Gaudin1976]
- With `u=(0,-1,\dots,-N_b)` the `1/j` central-spin `H` equals the single Gaudin charge `H_0` (verified in-card, residual `<10^{-12}`)
- Integrability: all pairwise commutators `[H_i,H_j]=0` (measured `<10^{-12}`) — an in-card proof of the conserved-charge tower [@Gaudin1976]
- SU(2): `[H,\mathbf{S}^2_{\mathrm{tot}}]=0` — eigenstates form total-spin multiplets
- Uniform-coupling closed form: `A_j=A\Rightarrow E_0=-\tfrac{A}{4}(N_b+2)` (exact, from total-spin decomposition)

## Oracle script

`python oracle.py --N_bath 5` → prints `e0` (ED ground energy of the `1/j` central-spin `H`), `route` (`"conserved-charges"`), `N_bath`, `couplings`, `inhomogeneities`. Importable: `compute(N_bath=5)`; helpers `central_spin_H(N_bath)`, `gaudin_charges(N_bath)`, `total_spin_squared(N_bath)`, `uniform_e0_closed_form(N_bath, A)`.

Self-test anchors: (1) the central-spin `H` **is** the Gaudin charge `H_0` (residual `<10^{-12}`) for `N_b\in\{4,5\}`; (2) **integrability** — all `N_b+1` Gaudin charges mutually commute (`<10^{-12}`); (3) **degeneracy sanity** — `[H,\mathbf{S}^2_{\mathrm{tot}}]=0` (`<10^{-12}`); (4) ED cross-check — `H` is Hermitian (`<10^{-12}`) and the ED ground energies of `H` and of `H_0` agree (`1e-10`); (5) **second coupling set** — uniform `A_j=1` gives `E_0=-\tfrac14(N_b+2)`, matched to ED at `1e-10`.

## Benchmarks

`e0` = ground-state energy. Spin-1/2, `L=N_b+1`, central spin at site 0, dense/Lanczos ED.

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0` (`A_j=1/j`) | `N_b=5` | `-0.9148146832` | this card (ED = Gaudin charge `H_0`) |
| `e0` (`A_j=1/j`) | `N_b=4` | `-0.8853708830` | this card (ED = Gaudin charge `H_0`) |
| `E_0` (uniform `A=1`) | `N_b=5` | `-\tfrac14(N_b+2)=-1.75` | [@Gaudin1976] (SU(2) closed form) |
| `E_0` (uniform `A=1`) | `N_b=4` | `-\tfrac14(N_b+2)=-1.5` | [@Gaudin1976] (SU(2) closed form) |
| max commutator | `[H_i,H_j]`, `N_b\in\{4,5\}` | `\sim10^{-16}` (integrable) | this card (measured) |

The `1/j` energies are exact ED numbers for the integrable central-spin Hamiltonian (equal to the Gaudin charge `H_0`); the uniform-coupling rows are the closed-form total-spin values. The vanishing commutators are the in-card proof that the `N_b+1` Gaudin charges form a commuting (integrable) tower.

## Verification recipes

- To check a central-spin ED: build `H=\sum_{j=1}^{N_b}(1/j)\,\mathbf{S}_0\cdot\mathbf{S}_j` (`S=σ/2`, central spin at site 0) and reproduce `e0(N_b=5)=-0.9148146832`, `e0(N_b=4)=-0.8853708830` to `1e-8`. A mismatch usually means a `σ`-vs-`S` factor (a factor 4), a coupling-order slip (`A_j=1/j` vs `1/(j+1)`), or including a self-term `j=0`.
- To confirm integrability (the conserved-charge structure): build the `N_b+1` Gaudin charges `H_i=\sum_{k\ne i}(\mathbf{S}_i\cdot\mathbf{S}_k)/(u_i-u_k)` with `u=(0,-1,\dots,-N_b)`, and check `[H_i,H_j]=0` for all pairs and `H=H_0`. Nonzero commutators mean an inhomogeneity slip (the `u_j` must be distinct, and `u_0-u_j=j` reproduces `A_j=1/j`).
- To check the uniform-coupling limit: set all `A_j=A`; then `H=A\,\mathbf{S}_0\cdot\mathbf{S}_{\mathrm{bath}}` and `E_0=-\tfrac{A}{4}(N_b+2)` exactly (maximal bath spin, total spin `S_b-\tfrac12`).

## Key reference

[@Gaudin1976] — M. Gaudin, "Diagonalisation d'une classe d'hamiltoniens de spin", J. Physique **37**, 1087 (1976): the rational Gaudin magnets and their `N+1` commuting spin Hamiltonians `H_i=\sum_{k\ne i}(\mathbf{S}_i\cdot\mathbf{S}_k)/(u_i-u_k)`, the integrable structure this card scripts (the central spin is the charge `H_0`). The `1/r`-family pairing cousin is `richardson-pairing`. Rendered: _(Wave 3)_.
