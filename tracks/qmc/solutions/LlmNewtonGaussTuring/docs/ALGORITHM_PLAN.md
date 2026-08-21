# Challenge 148 Master Plan: Color-Parallel Line-Update SSE

Date: 2026-07-30
Status: active — C++ cluster-versus-loop-versus-line algorithm benchmark track
Chinese companion note: `notes/Harnessing Quantum 2026/PLAN-2026-07-30 并行 Line Update.md`

---

## 1. Executive summary

### Current objective (2026-07-30 update)

The √5 precision target is retired for this local-compute campaign. The
deliverable is a dependency-free C++17 comparison of cluster, merge--unmerge
loop, and true worldline-segment line updates. All must share the same Hamiltonian,
lattice builder, diagonal update, estimators, RNG policy, and Sokal-window
ESS/s analysis. The first C++ pilot is recorded under
`data/processed/tfim-cpp-loop-line-benchmark-20260730/`; it is a one-chain,
1,000-measurement-sweep directional result, not a final efficiency estimate.

Next work is repeated independent C++ chains at the two fixed critical-field
benchmark points, followed by a size sweep. The √5 FSS material remains only
as a documented negative result and must not be resumed without new compute
resources.

Challenge 148 asks whether the ratio of the transverse-field Ising critical
fields on the triangular and honeycomb lattices is exactly √5, with a total
uncertainty target of sigma_R <= 1.2e-5. Our conventional route (cluster-update
SSE, sizes up to L=64, full sampling gates) is honest but stalled: the
honeycomb lattice has no accepted finite-size fit, and the achievable
statistical precision on this workstation is two to three orders of magnitude
short of the target. More statistics alone cannot win inside the remaining
time.

The remaining time is therefore invested in the part of the problem that is
actually novel: **the update algorithm itself**. State-of-the-art TFIM QMC
updates (Sandvik cluster, Blöte–Deng continuous-time cluster) build global
clusters and are intrinsically serial per Markov chain. Our group owns two
alternatives:

- the **merge–unmerge loop update** (arXiv:2409.17835, group publication),
  already generalized in this repository to triangular and honeycomb lattices
  and validated against ED — its unique strength is a nonzero longitudinal
  field, which cluster updates cannot handle;
- the **line update** (undergraduate thesis, `sse_new` reference code), a
  strictly local worldline-segment flip whose conflict graph is the lattice
  graph itself — which makes it **parallelizable by graph coloring**.

The pitch of this work: **the two lattices of Challenge 148 are exactly the
minimal pair that exhibits the coloring structure — the bipartite honeycomb
lattice parallelizes with 2 colors, while the non-bipartite triangular lattice
needs exactly 3 colors** (explicit coloring c = (x+2y) mod 3, valid when
Lx, Ly ≡ 0 mod 3). Even if the parallel line update does not beat the cluster
update in effective samples per second, the measured comparison — same
lattice, same diagonal update, same estimators — is a publishable-grade
methodological result and a concrete roadmap for breaking the serial-update
wall of this challenge class.

Implementation status as of this document: serial and color-parallel line
update are **implemented, smoke-tested, benchmarked, and exercised in a bounded
production pilot** in Julia. All 12 update smoke checks, all 33 dedicated FSS
estimator checks, and all 18 finite-temperature ED comparisons pass. The line
kernel wins the measured single-thread ESS/s comparison and scales across
eight threads. The paper-matched `L=12/24/48` pilot completed but failed its
sampling and unique-crossing gates, so it produces no new critical-field or
ratio claim; detailed results are in `../REPORT.md` and §7.

---

## 2. Scientific conventions (fixed)

### 2.1 Hamiltonian sign dictionary

This repository simulates

    H_code = J * sum_<ij> sigma^z_i sigma^z_j  -  B * sum_i sigma^z_i  -  Gamma * sum_i sigma^x_i .

The challenge and the Blöte–Deng reference use

    H_challenge = -J' * sum_<ij> sigma^z_i sigma^z_j  -  h * sum_i sigma^x_i ,   J' > 0 (ferromagnetic).

The dictionary is exact:

| challenge quantity | this repository |
|---|---|
| J' = 1 (FM), field h | J = -1, Gamma = h, B = 0 |
| h_c(triangular) = 4.76811(9) | Gamma_c at J = -1, triangular |
| h_c(honeycomb) = 2.13250(4) | Gamma_c at J = -1, honeycomb |

Why this matters and must never be silently flipped:

- The honeycomb lattice is bipartite: a sublattice rotation maps J → -J, so
  |Gamma_c| is sign-independent and a sign mistake is invisible there.
- The triangular lattice is **not** bipartite: J = +1 in this code is the
  frustrated antiferromagnet (clock order, order-by-disorder, different
  universality) — a completely different problem. The algorithm note
  `docs/三角晶格TFIM_loop算法note.md` benchmarks that AFM case on purpose
  (it is the regime of the loop-update paper); Challenge 148 runs must use
  J = -1.
- Neither sign has a QMC sign problem (the transverse-field off-diagonal
  elements are non-positive after the standard shift, independent of J), so
  "it runs without negative weights" is *not* evidence the sign is right.
  The only reliable guards are the explicit dictionary above plus the
  benchmark anchors Gamma_c ≈ 4.77 / 2.13.

### 2.2 Weight table (shared by every update)

Bond diagonal operators carry weight

    w_b(s_i, s_j) = -J sigma_i sigma_j + (B/z)(sigma_i + sigma_j) + C_b,
    C_b = |J| + 2|B|/z + eps,  eps = 0.5 ,

single-site operators (constant and off-diagonal) both carry weight Gamma.
`eps > 0` is **required** by the line update: at eps = 0 an aligned FM bond has
w = 2|J| and an anti-aligned bond w = 0, so any segment flip that creates an
anti-aligned bond would be rejected with probability 1 and the ordered phase
would freeze. eps is a tunable efficiency knob (larger eps → higher segment
acceptance but more bond operators, i.e. longer operator strings). The matched
line-vs-loop benchmark uses eps = 0.5; the completed scan selects production
defaults of 0.5 (triangular) and 1.0 (honeycomb), see §7.4.

---

## 3. Algorithm portfolio

| update | origin | move structure | parallelism | B ≠ 0 | status here |
|---|---|---|---|---|---|
| cluster | Sandvik 2003 | global multi-branch cluster | none within a chain | no | production code in training worktree (C++) |
| loop (merge–unmerge) | group paper arXiv:2409.17835 | worm; spatial motion via merge/unmerge | none within a chain | **yes** | Julia (validated vs ED); C++ port 1.15–1.61× faster |
| **line** | thesis / `sse_new`; this work | flip one worldline segment of one site | **graph coloring, N/k sites concurrently** | yes (B enters bond weights) | **Julia implementation, ED-validated and benchmarked** |

Naming warning: the existing C++ port under `cpp/` is algorithmically the
merge–unmerge **loop** update (its `line_update()` function name refers to the
data layout it borrowed from `sse_new`). The true segment-flip line update is
the new `src/TIM_lattice_line.jl`.

---

## 4. Architecture

### 4.1 Module layout and reuse boundary

```
src/
  TIM_lattice_QMC.jl      # shared core (UNCHANGED, upstream-hash-pinned)
  |   build_lattice(...)  #   lattice graphs: bond[2,Nb], site_bonds[z,N]
  |   mutable struct Sim  #   operator list opl[2,ll], conf[N], weights, RNG
  |   dupdate!(s)         #   diagonal update (inserts/removes const + bond ops)
  |   lupdate!(s)         #   merge–unmerge loop update (baseline algorithm)
  |   measure(s)          #   E, m_x, m^2, m^4 (imaginary-time averaged)
  |   run(...)            #   anneal + bins driver for the loop algorithm
  |
  lattice_coloring.jl     # NEW: proper vertex coloring
  |   color_lattice(lattice, Lx, Ly, N, bond) -> (colors, classes)
  |   verify_coloring(colors, bond) -> Bool
  |
  TIM_lattice_line.jl     # NEW: line update, includes both files above
      build_site_lists!   #   per-site operator position tables
      update_site_lines!  #   all segment flips of one site (the local kernel)
      line_sweep!         #   serial or color-parallel full sweep
      check_config        #   worldline-consistency invariant (test oracle)
      run_line(...)       #   driver, CLI-compatible with run(...)

benchmarks/
  test_line_smoke.jl      # NEW: coloring + J=0 analytic + consistency + parallel
  test_fss_observables.jl # NEW: momentum shell + Dirichlet estimators + direct oracle
  bench_updates.jl        # ED gate + tau_int / ESS + scaling + epsilon profiles
  run_line_fss.jl         # bounded L=12/24/48 pilot, independent run namespace
  analyze_line_fss.py     # blocked bootstrap + sampling/crossing diagnostics
  plot_update_benchmarks.py # figures from processed benchmark CSVs
```

Design rule: the two QMC algorithms **share** the lattice builder, the Sim
state, the diagonal update, and every estimator. A loop-vs-line comparison is
then a comparison of transition kernels only — nothing else differs. The
upstream Julia files remain byte-identical (SOURCE.md hashes still hold).

### 4.2 Data model of the line update

For one sweep, one pass over the operator list builds per-site tables:

    lists[i] = [(p, leg), ...]   ordered by imaginary-time slot p
        leg = 0      : single-site operator on site i   (types 5..8)
        leg = 1 or 2 : bond operator at slot p, site i sits on that leg

Single-site entries ("delimiters") cut site i's worldline into segments.
Type encodings make every flip an XOR:

    bond type   tp-1 = s1 + 2*s2      -> flip leg L:  tp' = ((tp-1) XOR L) + 1
    single-site tp-5 = s_in + 2*s_out -> flip out-bit: XOR 2; in-bit: XOR 1

### 4.3 The segment move (local kernel)

```
for each consecutive delimiter pair (a, b) around the time circle:
    R = product over bond entries strictly between a and b of
        w_b(flipped leg) / w_b(current)          # O(#bond ops in segment)
    accept with heat-bath probability R / (1 + R)
    on accept:
        XOR the leg bit of every bond entry in (a, b)
        XOR out-bit of delimiter a, in-bit of delimiter b
        if the segment wraps past tau = 0: conf[i] ^= 1
special cases:
    K = 1 delimiter  -> a == b: both bits of the same operator toggle (XOR 3)
    K = 0, ops exist -> whole-worldline flip, same heat-bath rule
    no ops at all    -> free spin, flip with probability 1/2
```

Cost per sweep is O(total operator entries) = O(n), same order as the loop
update. Delimiter toggles convert constant operators (weight Gamma) into
off-diagonal ones (weight Gamma) and back — ratio 1, so only bond weights
enter R. The diagonal update only inserts/removes constant single-site and
bond operators; off-diagonal operators are created and destroyed exclusively
by these delimiter toggles. Ergodicity = diagonal update × segment flips.

**Acceptance rule — a real lesson.** The thesis-era Metropolis rule
min(1, R) is broken in exactly the regime that matters at criticality: a
segment containing zero bond operators has R = 1 and is then flipped
*deterministically every sweep*, so the relative operator pattern never
changes (the J = 0 smoke gate catches this immediately: m_x stays at 0
instead of tanh(beta*Gamma); the 1D reference code masks it only because its
parameters keep bond operators dense on every segment). The fix is the
heat-bath (Glauber) rule R/(1+R): detailed balance for every R, and at R = 1
it is exactly the 1/2-probability resampling of a free interval. This bug
class — "valid-looking Metropolis kernel that silently loses ergodicity in a
limit" — is worth a paragraph in any write-up; our J = 0 gate is the
regression test for it.

### 4.4 Concurrency model

```
line_sweep!(s, scratch, classes; nt):
    build_site_lists!(s)                  # serial O(M) pass
    for each color class C (barrier between classes):
        split C into nt chunks
        @spawn one task per chunk:
            for i in chunk: update_site_lines!(s, i, lists[i], ds[t], rngs[t])
```

Race-freedom argument (the reason coloring is *sufficient*, not heuristic):
`update_site_lines!(s, i, ...)` writes only (a) `conf[i]`, (b) single-site
operators of site i, (c) the leg bits of bond operators incident on i. Two
sites of the same color are never adjacent, hence share no incident bond, so
their write sets are disjoint; reads are confined to the same sets. The color
barrier serializes the only remaining dependency (bond operators shared by
neighbors). Per-task RNGs are independent MersenneTwisters; chunks are static,
so results are reproducible at fixed (seed, nt).

Serial fractions and honest Amdahl accounting: `dupdate!` (O(M)) and
`build_site_lists!` (O(M)) stay serial in this iteration. Both are
parallelizable later (the thesis already demonstrates a time-slice
decomposition of the diagonal update; the list build is a chunked counting
pass whose chunk concatenation preserves time order), but the first scaling
numbers must be reported with the serial parts included, not idealized away.

### 4.5 Coloring subsystem

- honeycomb: colors = A/B sublattice parity (2 classes, exact, any L);
- triangular with Lx, Ly ≡ 0 (mod 3): c(x, y) = (x + 2y) mod 3 — the three
  neighbor directions (1,0), (0,1), (-1,1) advance c by 1, 2, 1 (mod 3), so
  all six neighbors differ; periodic wrap consistency is exactly the mod-3
  condition on Lx, Ly. This constraint is real and propagates to production
  size choices: L ∈ {12, 24, 48} qualify, the legacy L = 40, 64 grids do not;
- anything else: greedy fallback over the bond list (triangular non-multiples
  of 3 come out 4-colored, classes stay balanced enough for threading);
- `verify_coloring` re-checks every bond and is part of the smoke suite, so
  an invalid coloring can never silently produce racy (i.e. subtly biased)
  parallel runs — miscolored parallelism would not crash, it would corrupt
  detailed balance, which is why this check is a hard gate.

### 4.6 Correctness instrumentation

`check_config(s)` propagates conf through the whole operator string and
verifies (a) every bond-operator type matches the spins on both legs at its
time slot, (b) every single-site in-bit matches the worldline below it,
(c) periodicity closes after a full wrap. Run every `check_every` sweeps in
tests, it converts "subtle bit error somewhere in an XOR" into an immediate
failure — this is the invariant that makes fearless iteration on the kernel
possible.

---

## 5. Validation ladder

| gate | oracle | status |
|---|---|---|
| coloring validity (6 lattice cases, exact + greedy) | graph check | **pass** |
| J = 0 analytic limit, both lattices | E/N = -Gamma tanh(beta Gamma), m_x = tanh(beta Gamma) | **pass** (z < 1.8; this gate caught the ergodicity bug) |
| worldline consistency under FM criticality params | check_config every 100 sweeps | **pass** |
| parallel nt = 4 consistency, both lattices | check_config + no crash | **pass** |
| finite-T ED, FM J = -1, triangular 3×3 + honeycomb 2×2 | TIM_lattice_ED.jl, z-scores on E, m_x, m_z² | **pass** (18/18, max z = 3.18) |
| line vs loop cross-check at identical points | shared measure() | **pass** (ED gate + critical-point means agree) |
| parallel vs serial statistical identity | independent chains against the same ED oracle | **pass** (nt = 1 and 4) |

The FM ED gate deliberately mirrors the AFM gates already passed by the loop
update (its note benchmarks J = +1); the line update must pass at the
challenge sign J = -1.

---

## 6. What is already done today (evidence)

- `src/lattice_coloring.jl`, `src/TIM_lattice_line.jl`,
  `benchmarks/test_line_smoke.jl` implemented; upstream files untouched.
- Full smoke suite passes with `julia -t 4` (12/12):
  exact 2-coloring (honeycomb 2×2, 4×4), exact 3-coloring (triangular 3×3,
  6×6), greedy 4-coloring (triangular 4×4, 5×5), J = 0 both lattices,
  worldline consistency at (triangular, Gamma = 4.768) and (honeycomb,
  Gamma = 2.1325) with J = -1, and nt = 4 parallel runs on triangular 6×6 /
  honeycomb 4×4.
- Measured segment acceptance at the critical couplings, 3×3, beta = 4:
  ~0.33 (triangular) and ~0.32 (honeycomb) — consistent with the a-priori
  estimate ~z/(2*Gamma) bond operators per segment (0.63 / 0.70), i.e. the
  update is *not* frozen at criticality, which was the main efficiency risk.
- Serial throughput at that toy size: ~4.3×10⁴ sweeps/s including
  measurement.
- At the planned critical benchmark sizes, the serial line kernel improves
  ESS/s by 3.12–5.67× across E, m_x, m², and m⁴ relative to merge–unmerge.
- At eight threads, the color kernel reaches 4.90× (triangular) / 2.51×
  (honeycomb), while the Amdahl-honest full sweep reaches 1.66× / 1.20×.
- The epsilon scan selects lattice-specific defaults: 0.5 triangular and 1.0
  honeycomb. CSVs, raw series, figures, and metadata are under
  `data/processed/tfim-lineupdate-julia-20260730/`.
- The independent FSS estimator suite passes 33/33 checks: the sixfold
  shortest-momentum shell, periodic worldline closure, Dirichlet convexity,
  empty strings, and optimized-vs-direct propagation on both lattices.
- The paper-matched bounded pilot (`c_tau = beta*h/L = 1`) completed for both
  lattices at `L=12,24,48`, three fields, four independent chains per cell,
  1,000 thermalization sweeps and 2,000 saved sweeps per chain. All 14,400
  bins are finite and worldline-checked. The result is deliberately negative:
  the minimum independent-block count is 2 (gate: 8), honeycomb has a 5.90
  sigma random/ordered discrepancy (gate: 5), all Q central curves and both
  24/48 xi/L curves lack a unique root. The isolated triangular 12/24 xi/L
  root is not accepted because the sampling gate fails. Raw and derived artifacts are under
  `data/processed/tfim-lineupdate-julia-fss-pilot-ctau1-20260730/`.

---

## 7. Remaining plan

### 7.1 Priorities under the clock

P0 (must land in git today): this plan, the implemented + smoke-tested code,
updated repo docs, clean pushed tree. **Done when this commit lands.**

P1 results: **complete**, including the explicitly bounded production pilot.

### 7.2 Statistical-efficiency benchmark (the honest number)

**Complete.** For each (lattice, algorithm) at the literature critical point, matched
lattice sizes (triangular L = 12, honeycomb Lx = Ly = 8, beta = 2L), single
thread: record per-sweep series of E, m_x, m², m⁴; estimate tau_int with the
Sokal windowed estimator; report **effective samples per CPU-second**
(1 / (2 tau_int t_sweep)) for each observable. Expectation to test: line loses
on tau_int (local update) but is cheaper per sweep; the product decides.
Deliverables: `efficiency.csv`, `efficiency_series.csv`, `efficiency.png`, and
the conclusion in `../REPORT.md`. The line update wins measured ESS/s for all
eight lattice/observable comparisons.

### 7.3 Strong scaling of the color-parallel sweep

**Complete.** Fixed problem (triangular L = 24, beta = 48; honeycomb Lx = Ly = 12), threads
1→8, report wall-clock speedup of (a) the color sweep alone and (b) the full
sweep including serial dupdate! + list build (Amdahl-honest). Compare 2-color
vs 3-color efficiency at matched sites-per-class. Success is a clean measured
curve, not a marketing number. Measured eight-thread speedups are 4.90× / 2.51×
for the color kernel and 1.66× / 1.20× for the full triangular / honeycomb
sweeps.

### 7.4 Efficiency knob and production readiness

- **Complete:** eps scan (0.25 / 0.5 / 1.0) at criticality; freeze 0.5 for
  triangular and 1.0 for honeycomb.
- **Complete, inconclusive by design gates:** a bounded pilot on the
  `L = 12,24,48` triangular / honeycomb grids using the existing pipeline's
  paper-matched `c_tau = beta*h/L = 1`, in the independent run-ID branch
  `tfim-lineupdate-julia-fss-pilot-ctau1-20260730`. It is never mixed with
  cluster or loop production data. The pilot establishes that the production
  path works end to end, but its 2,000 sweeps per chain are insufficient for a
  critical-field claim: minimum independent blocks are 2 rather than 8, and
  most central curves have no unique crossing. No ratio is formed.
- Independent of the outcome, wire the loop update's B ≠ 0 capability into
  the report as the second innovation axis (cluster updates cannot do this).

### 7.5 Write-up

**Complete:** single English `REPORT.md` in the project root: problem, sign dictionary,
architecture (§4), the ergodicity lesson, measured tables from 7.2/7.3, and
the three-way conclusion template (win / crossover-at-k-cores / measured
negative result) — each branch is a legitimate deliverable.

---

## 8. Risks

| risk | mitigation |
|---|---|
| tau_int of line update blows up at criticality | that outcome is itself a measured result; report it with the crossover core-count |
| Julia threading overhead dominates at small L | benchmark at L ≥ 24; report per-class task granularity |
| mod-3 size constraint collides with legacy grids | production benchmarks use L = 12/24/48; greedy 4-coloring covers other sizes |
| convention slip between J and J' | dictionary in §2.1; anchors Gamma_c ≈ 4.77/2.13 asserted in benchmarks |
| provenance confusion with cluster-update data | new run-ID namespace, separate data directory, no silent pooling |
