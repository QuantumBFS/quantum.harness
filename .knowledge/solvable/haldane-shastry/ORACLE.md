# Haldane–Shastry chain — exact-solution oracle

Technique: T3 (Bethe ansatz / Yang–Baxter, Yangian) · Tier: B (integrable) · Script: S

## Hamiltonian & conventions

$$ H = J \sum_{i<j} \frac{\mathbf{S}_i\cdot\mathbf{S}_j}{d_{ij}^{\,2}}, \qquad d_{ij} = \frac{N}{\pi}\left|\sin\frac{\pi(i-j)}{N}\right| $$

Conventions: spin-1/2 `S`-operators (`S^a = σ^a/2`), `J = 1` antiferromagnetic, `N` even, periodic ring. The couplings use the **chord distance** `d_ij` between two sites placed on a circle of circumference `N` (equivalently the coupling is `J(π/N)² / sin²(π(i−j)/N)`); every pair `i<j` is coupled once, so the exchange is genuinely long-ranged (`∝ 1/r²` at short range). See `.knowledge/conventions.md`.

No dedicated model-zoo sibling under `.knowledge/models/`; the nearest physics card is `.knowledge/models/heisenberg` (same `S`-operator convention, nearest-neighbour `1/r²→` short-range limit). The `κ`-deformation that interpolates this card with the nearest-neighbour XXX chain is the sibling oracle card `inozemtsev-chain`.

## Solvability statement

T3 (Bethe ansatz / Yang–Baxter, Yangian): the `1/r²` chord exchange is the point where the antiferromagnetic ground state is known **exactly and in closed form**. Haldane [@HaldaneHS1988] and Shastry [@Shastry1988] showed independently (1988) that the singlet ground state is a **Jastrow–Gutzwiller wavefunction** — the `U→∞` (Gutzwiller-projected) filled Fermi sea, i.e. Anderson's resonating-valence-bond state — with an exactly evaluable energy. The finite-`N` ground energy is the closed form `E0(N) = −J(π²/24)(N + 5/N)`; per site `e0(N) = −(π²/24)(1 + 5/N²) → −π²/24` as `N→∞`. The full spectrum organises into **"supermultiplet" degeneracies**, observed in [@HaldaneHS1988] as the signature of a hidden continuous symmetry and later identified as a `Y(su(2))` **Yangian** present already at finite `N` (Haldane–Ha–Talstra–Bernard–Pasquier 1992, standard); the elementary excitations are **spinons obeying semionic (half-)statistics** and are non-interacting (free) in this model — the `1/r²` chain is the archetypal "ideal spinon gas" (Haldane 1991, standard). **Tier B, not A:** although the ground state and static structure factor are closed-form, the complete finite-`T`/dynamical solution still goes through the Yangian/asymptotic-Bethe machinery, so we treat it as integrable rather than fully closed.

## The 1/r² miracle

Put the `N` sites at the complex roots of unity `z_a = e^{2\pi i x_a/N}`; the Gutzwiller-projected wavefunction assigns amplitude `Ψ({x}) = \prod_{a<b}(z_a − z_b)^2 \prod_a z_a` to the down-spin positions `{x_a}` (`M=N/2` of them), a Jastrow form with exponent `2`. Acting with `H` on this state, the `1/r²` chord couplings arrange so that the two- and three-body terms telescope, leaving `HΨ = E0Ψ` — an **exact eigenstate**, not a variational bound [@HaldaneHS1988; @Shastry1988]. The same projected-Fermi-sea picture explains the spinons: removing one particle from the filled sea and repacking creates a pair of `S=1/2` objects that scatter only through a statistical (semionic) phase, never dynamically — hence the flat, free-particle spinon dispersion and the exact "supermultiplet" counting. The Yangian generators that commute with `H` at finite `N` are what promote these degeneracies from accidental to symmetry-protected.

## Exact results

- Finite-`N` ground energy (closed form): `E0(N) = −J(π²/24)(N + 5/N)`, GS a total-spin singlet [@HaldaneHS1988; @Shastry1988]
- Ground energy per site: `e0(N) = −(π²/24)(1 + 5/N²)`; thermodynamic limit `e0 = −π²/24 ≈ −0.4112335` [@HaldaneHS1988]
- Ground state is the `U→∞` Gutzwiller-projected filled Fermi sea (Jastrow exponent `2`) = RVB state [@HaldaneHS1988; @Shastry1988]
- Spectrum in "supermultiplet" degeneracies signalling a hidden continuous symmetry [@HaldaneHS1988]; identified as a finite-`N` `Y(su(2))` Yangian, with free semionic spinons (later literature, standard — not load-bearing for this card's numbers)
- Exact static spin structure factor / ground-state correlators are known in closed form [@Shastry1988] (**exact but not scripted** — this card computes only the ground energetics)

## Oracle script

`python oracle.py --N 12` → prints `e0_per_site` (closed form `−(π²/24)(1+5/N²)`) and `e0_thermodynamic` (`−π²/24`). Importable: `compute(N=12)`; `e0_total(N)`, `e0_per_site(N)`, and the ground-truth ED builder `hs_hamiltonian(N)` are module-level.

Self-test anchors: (1) **ground truth** — the closed form `E0(N)` equals dense ED of `H = Σ_{i<j} S_i·S_j/d_ij²` (chord couplings, exact) at `N∈{6,8,10}` to `1e-10` (verified: the closed form matches ED to `~1e-15` at these sizes); (2) `N→∞` consistency — `e0_per_site(N=10⁴)` reaches `−π²/24` within `1e-6`; (3) the thermodynamic constant equals the literal `−π²/24`.

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|
| `e0_thermodynamic` | `J=1`, `N→∞` | `−π²/24 ≈ −0.4112335` | [@HaldaneHS1988] |
| `e0_per_site` | `J=1`, `N=12` | `−0.4255125` (`= −(π²/24)(1+5/144)`) | [@HaldaneHS1988] |
| `E0` (total, closed form = ED) | `J=1`, `N=10` | `−4.3179519255` (`= −(π²/24)(10+1/2)`) | [@HaldaneHS1988; @Shastry1988] |
| `E0` (total, closed form = ED) | `J=1`, `N=8` | `−3.5468890816` | [@HaldaneHS1988; @Shastry1988] |

## Verification recipes

- To check an ED/DMRG run of the `1/r²` chord chain (PBC): compare `e0_per_site` from `oracle.py --N <N>` (exact) at your `N`, tolerance `1e-8`. A mismatch usually means a coupling-convention slip — using `1/|i−j|²` (linear, not chord distance), dropping the `(π/N)²` chord factor, or Pauli-vs-`S` operators (a factor `4`).
- The finite-`N` energy sits *below* `−π²/24` per site and rises toward it as the `1/N²` correction `−(π²/24)(5/N²)`; do **not** compare a finite-`N` number directly to the thermodynamic constant.
- To check the ground state itself: it should be a total-spin singlet (`S²=0`, `S^z=0`) and, up to normalisation, the Gutzwiller-projected free-fermion sea; the exact static structure factor [@Shastry1988] is a further (unscripted) check.

## Key reference

[@HaldaneHS1988] — Haldane, "Exact Jastrow–Gutzwiller resonating-valence-bond ground state of the spin-½ antiferromagnetic Heisenberg chain with 1/r² exchange", PRL **60**, 635 (1988): the closed-form ground state and the `E0 = −(π²/24)(N+5/N)` energy, plus the supermultiplet/Yangian structure. Shastry [@Shastry1988] (PRL **60**, 639 (1988)) is the independent simultaneous solution with the explicit correlators; the `κ`-elliptic interpolation to the nearest-neighbour XXX chain is Inozemtsev [@Inozemtsev1990] (see sibling card `inozemtsev-chain`). Rendered: _(Wave 3)_.
