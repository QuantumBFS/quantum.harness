<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Cluster Monte Carlo / Wang–Landau / Parallel Tempering (cluster-mc)

Non-local cluster updates (Swendsen–Wang, Wolff) and extended-ensemble algorithms (Wang–Landau, parallel tempering) that defeat critical slowing down for unfrustrated classical spin models and glassy energy landscapes.

## Method card

### What it is

Cluster algorithms (Swendsen–Wang 1987; Wolff 1989) build clusters of aligned spins via the Fortuin–Kasteleyn (FK) bond-percolation representation and flip entire clusters at once, dramatically reducing the autocorrelation time near a continuous phase transition. Swendsen–Wang decomposes the whole lattice into FK clusters and flips each independently; Wolff grows a single cluster from a random seed and flips it. Both require the FK construction to be valid — i.e. ferromagnetic / unfrustrated couplings. Wang–Landau sampling and parallel tempering are complementary extended-ensemble methods: Wang–Landau [@wang_2001_efficient] builds the density of states `g(E)` iteratively to allow flat-histogram sampling at all temperatures; parallel tempering [@hukushima_1996_exchange] runs multiple replicas at different temperatures and exchanges configurations to overcome free-energy barriers, targeting glassy or rough landscapes (B8/D15) at the cost of the number of replicas.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Same thermodynamic observables as Metropolis MC: energy, magnetization, susceptibility, Binder cumulants, structure factors, correlation functions; Wang–Landau additionally returns the full density of states `g(E)` | Cluster updates are most valuable for making large-`L` critical-region measurements affordable. |
| M2 regime | Finite temperature (thermal equilibrium) | Classical models; or quantum models with a sign-free classical representation. |
| M3 accuracy class | Numerically exact (Boltzmann statistics), stochastic | Statistical error `∝ 1/√(N_s/τ_auto)`; cluster MC's win is that `τ_auto` is orders of magnitude smaller than Metropolis near `T_c`. |
| M4 dimension fit (A1) | Any (1D / 2D / 3D / ∞-D) | SW and Wolff are most impactful in 2D and 3D where critical slowing down is severe; applicable to any dimension where the FK mapping holds. |
| M5 statistics & local dim (A3) | Classical spin models (Ising, Heisenberg O(n), Potts) with ferromagnetic / unfrustrated couplings | FK cluster construction requires non-negative bond weights; does not apply to general antiferromagnetic or frustrated models. |
| M6 entanglement regime (B5) | N/A — classical model | Same as Metropolis MC. |
| M7 sign-problem dependence (C12) | Requires sign-free / unfrustrated (Fortuin–Kasteleyn construction requires ferromagnetic couplings) | Frustration breaks the FK bond construction — this is the hard blocker (see M14). |
| M8 symmetry exploitation (C9/C10) | Global spin-flip symmetry exploited by Wolff (projects a random direction, builds the cluster in that projected space); SW flips each cluster independently | Translation / point-group symmetry used for structure-factor estimators. |
| M9 time complexity | `O(N)` per sweep (amortized over cluster size); near `T_c`: `τ_auto ~ L^z` with Swendsen–Wang `z ≈ 0.22` and Wolff: `~ ln L` equilibrium-autocorrelation; nonequilibrium-relaxation fits give a larger effective `z ≈ 1.2` for Wolff | Near-`O(N)` effective cost at criticality — the decisive advantage over Metropolis (`z = 2.1665(12)`). Parallel tempering multiplies total cost by `N_replicas`. |
| M10 memory | `O(N)` — spin configuration; cluster labels `O(N)` (union-find) | Cluster label array adds a small constant factor over plain Metropolis. |
| M11 control knob | `N_s` (sweeps/cluster updates) — controls statistical error; for Wang–Landau: the modification factor `f → 1` controls flatness of `g(E)`; for parallel tempering: `N_replicas` and temperature grid | Statistical error `∝ 1/√(N_s/τ_auto_eff)` where `τ_auto_eff ≪ τ_auto(Metropolis)` near `T_c`. |
| M12 scale frontier | Millions of sites even near `T_c` (SW/Wolff make large-`L` critical-region sampling affordable); parallel tempering / Wang–Landau: hundreds of sites (limited by `N_replicas × L^d`) | Cluster algorithms enable finite-size scaling studies at `L ~ 10³–10⁴` near `T_c` that are prohibitive with Metropolis. |
| M13 primary approximation / bias | None — samples from exact Boltzmann distribution (for cluster MC); Wang–Landau has a systematic `ln(f)` bias that vanishes as `f → 1` | Finite-size effects remain; Wang–Landau convergence must be checked by flatness criterion. |
| M14 hard blocker / failure mode | Frustration (B8) breaks the Fortuin–Kasteleyn cluster construction — SW/Wolff do not apply; frustrated/spin-glass systems require parallel tempering or simulated annealing (at higher cost and with no `z` suppression); sign-ful quantum models inaccessible | Parallel tempering is a workaround for glassy landscapes but does not reduce `z`; it incurs an `N_replicas` overhead. |

### Cost & scaling

- Time: `O(N)` per cluster sweep (union-find construction); effective critical cost `O(N · L^z)` with `z ≈ 0.22` (SW) vs `z ≈ 2.17` (Metropolis); parallel tempering: `× N_replicas`
- Memory: `O(N)` — spin configuration + cluster label array
- Control knob: `N_s` (sweeps) + `N_replicas` (parallel tempering) — controls statistical error and barrier crossing
- Scale frontier: millions of sites near `T_c` for SW/Wolff; hundreds of sites for parallel tempering with many replicas

### Accuracy & guarantees

- Class: numerically exact (Boltzmann statistics), stochastic
- Primary approximation & its control: none intrinsic (cluster MC); Wang–Landau `ln(f)` systematic bias → vanishes as `f → 1`
- Error scaling: statistical error `∝ 1/√(N_s/τ_auto_eff)`; at criticality `τ_auto_eff ~ L^{0.22}` (SW) vs `L^{2.17}` (Metropolis) — a factor `~L^2` improvement

### Tasks it computes

- Same thermodynamic observables as Metropolis MC: energy, magnetization, susceptibility, specific heat, Binder cumulants, structure factors
- Large-`L` finite-size scaling near `T_c`: critical-region data that is statistically impossible with Metropolis at `L ≳ 100`
- Density of states `g(E)` across all temperatures simultaneously (Wang–Landau)
- Free energy and entropy by integration of `g(E)`
- Thermodynamics of glassy / rough landscapes across multiple free-energy basins (parallel tempering)

### Recommended for (models / regimes)

- **Ferromagnetic or unfrustrated classical models** (Ising, Potts, O(n)) near their continuous phase transitions — SW and Wolff are the standard choice
- **Large-`L` finite-size scaling at criticality (B6)**: SW/Wolff make `L ~ 10³–10⁴` routine where Metropolis is stuck
- **Glassy or rough free-energy landscapes (B8, D15)**: parallel tempering and Wang–Landau for landscape exploration
- Per `method-property-map.md`: classical models, sign-free, B8 unfrustrated (for SW/Wolff); B8 frustrated → parallel tempering only (no `z` suppression)

### Key reference

[@wolff_1989_collective] — original Wolff single-cluster algorithm with the demonstration that `z` is effectively `~ ln L` for 2D Ising, making large-`L` critical simulations affordable.
Rendered: _(none — bib stub; see literature INDEX)_.

[@swendsen_wang_1987_nonuniversal] — original Swendsen–Wang multi-cluster algorithm; measured `z ≈ 0.22` for 2D Ising, establishing the near-elimination of critical slowing down.
Rendered: _(none — bib stub; see literature INDEX)_.

### Benchmarks

- Swendsen–Wang dynamical critical exponent: `z ≈ 0.22` for 2D Ising model (equilibrium-autocorrelation convention) [verified in `method-survey.md` §2.2].
- Wolff: `~ ln L` equilibrium-autocorrelation for 2D Ising; nonequilibrium-relaxation fits give a larger effective `z ≈ 1.2` for Wolff [verified in `method-survey.md` §2.2].
- Comparison at `L = 512`, 2D Ising at `T_c`: SW requires `~L^{0.22}` effective sweeps vs Metropolis `~L^{2.1665}` sweeps per independent sample — roughly 10⁵ speedup (ratio `L^{z_M − z_SW} = L^{1.95} ≈ 1.3×10⁵` at L=512).
- 2D Ising `T_c/J = 2.2692` (Onsager): cluster MC locates to sub-0.01% at `L = 1024` with `O(10⁴)` cluster updates [@swendsen_wang_1987_nonuniversal].

## How it is used / Operational

**Owning skill:** No dedicated classical-MC harness skill exists. Cluster MC is typically implemented via custom code (Python/C/Fortran/Julia) or the ALPS package. For frustrated-magnet regime classification see `method-property-map.md`. The `/method-qmc` skill is for *quantum* MC only. For regime selection among cluster algorithms vs parallel tempering vs MCRG, consult `method-survey.md` §2.2.

**Default workflow (SW/Wolff):**
1. Initialize lattice; set `T` near `T_c`.
2. Build FK bond graph: activate bond `(i,j)` with probability `p = 1 − e^{−2βJ}`.
3. Find connected components (union-find, `O(N·α(N))`).
4. Flip each component's spins independently (SW) or flip the single grown cluster (Wolff).
5. Repeat `N_s` times; estimate `τ_auto` from the autocorrelation function of the order parameter; collect statistics.
6. Perform finite-size scaling: plot Binder cumulant crossings vs `L` to locate `T_c`; extract critical exponents from power-law fits of `χ ~ L^{γ/ν}`, `⟨m⟩ ~ L^{−β/ν}`.

**Default workflow (parallel tempering):**
1. Initialize `N_replicas` configurations at temperatures `T_1 < T_2 < … < T_{N_r}`.
2. Perform `N_sweep` local/cluster updates at each `T`.
3. Propose swaps between adjacent replicas with probability `min(1, e^{(β_i−β_j)(E_i−E_j)})`.
4. Collect statistics at each temperature after equilibration; verify replica flow (random walk in `T`).

**Verification pointers:**
- For 2D Ising (SW/Wolff): verify `z ≈ 0.22` / `~ ln L` by measuring integrated autocorrelation of `⟨m²⟩` vs `L` at `T_c`; cross-check `T_c` with Onsager.
- For parallel tempering: verify replica acceptance rates `~ 20–40%`; check that energy histograms at adjacent `T` overlap.

**Cross-links:**
- Survey: `method-survey.md` §2.2 (Cluster algorithms — Swendsen–Wang, Wolff, Wang–Landau, parallel tempering)
- Model↔method gate: `method-property-map.md` (classical models, B6 criticality, B8 frustration)
- Complementary methods: metropolis-mc (simple local updates; same observables), MCRG (extracts critical exponents from cluster-MC configurations), LTRG (quantum finite-T tensor networks)
