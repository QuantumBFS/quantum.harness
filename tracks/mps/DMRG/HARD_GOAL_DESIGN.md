# Issue #28 Hard Goal: 3D Spin-Glass MPS-VMCRG Design

## Document status

- Scope: Stage 0 scientific design, Stage 1 conceptual self-review, and the
  Stage 2 decision record.
- Date: 2026-07-28.
- Repository task: QuantumBFS/quantum.harness Issue #28, registered by PR #154.
- Working branch observed at design time: `challenge/issue28-pure-neural`.
- Approval state: the user confirmed all five Stage 2 scientific/planning
  choices on 2026-07-28. This authorizes Stage 3 planning, not a production job,
  commit, push, or PR-state change. Exact Stage 7 resources remain a separate
  pre-submission approval gate.
- The existing two-dimensional Ising/XY/LTRG work is not Hard Goal evidence.
  The Hard Goal requires a trainable local MPS/Tensor Train (TT) in the actual
  three-dimensional neural bias.

This document deliberately separates facts fixed by primary sources from design
choices. `CONFIRMED` means fixed by a cited source or by the challenge request.
`PROVISIONAL` identifies values that Stage 6 must still freeze from measured
pilot evidence, rather than silent implementation defaults.

## 1. Scientific question and evidence contract

The Hard Goal asks two related but logically independent questions:

1. Can a local, disorder-conditioned MPS/TT variational bias learn the
   coarse-grained **overlap-field effective Hamiltonian** of a 45 x 45 x 45
   three-dimensional spin glass more accurately than a fair finite-coupling
   VMCRG baseline?
2. Where is the thermodynamic spin-glass transition, as determined by
   equilibrated, unbiased finite-size observables rather than by neural loss?

The calculation therefore has two evidence arms.

| Evidence arm | Samples | Primary outputs | Permitted claim |
|---|---|---|---|
| Neural VMCRG | Biased two-copy PT, with a frozen local TT bias | Target-distribution error, projected effective couplings, one- and later two-step RG flow | An independently estimated RG-flow change and an MPS-vs-baseline representation comparison |
| Finite-size scaling (FSS) | Separate unbiased two-ladder PT, or an exact reweighting that passes overlap/ESS gates | Binder ratio, chi_SG(k), xi_L, xi_L/L | The final Tc interval |

Neural training samples cannot be silently reused as unbiased FSS samples.
Agreement between the two arms is a success requirement, not an assumption.

## 2. Source audit and model lock

### 2.1 What the public task fixes

- Issue #28 and PR #154 specify a three-dimensional spin glass at linear size
  45, but do not specify the Hamiltonian, bond distribution, boundary
  conditions, disorder ensemble, temperature grid, sample count, or Tc
  estimator.
- Wu and Car, arXiv:1707.08683, supplies the VMCRG variational principle and a
  two-dimensional clean Ising demonstration. It does not select a
  three-dimensional spin-glass model.
- The challenge request fixes the two-copy overlap construction, 3 x 3 x 3
  majority blocking, the 45 -> 15 -> 5 geometry, and the requirement that a
  trainable MPS/TT be part of the actual neural bias.

Consequently, the following model is a reasoned proposal, not a fact inferred
from Issue #28.

### 2.2 Confirmed primary model

**CONFIRMED MODEL: symmetric bimodal Edwards-Anderson Ising spin glass.**

For sites x on a cubic L x L x L lattice,

```text
s_x in {-1,+1}
H_J(s) = - sum_{x,mu in {x,y,z}} J_{x,mu} s_x s_{x+mu}
P(J_{x,mu}=+1) = P(J_{x,mu}=-1) = 1/2
```

- Bonds are iid, not constrained to contain exactly half positive bonds in
  each finite sample.
- The sum contains each nearest-neighbor bond once.
- Periodic boundary conditions apply in all three directions.
- There is no external field.
- `k_B=1` and `|J|=1`; temperature is dimensionless, beta=1/T, and the
  dimensionless sampling action is beta H_J.
- A disorder realization J is generated once and then held fixed during all
  thermal sampling. Thermal averages are taken first, followed by the
  quenched disorder average.

This convention matches the standard iid symmetric bimodal model in
Katzgraber, Koerner, and Young, arXiv:cond-mat/0602212, and Hasenbusch,
Pelissetto, and Vicari, arXiv:0809.3329. The latter reports beta_c=0.902(8),
or Tc=1.109(10), after correction-to-scaling analysis. The earlier study finds
Tc=1.120(4) from xi_L/L but 1.088(6) from a simple Binder analysis, a warning
that Binder corrections cannot be ignored. These values are validation
anchors, never fit targets.

### 2.3 Rejected alternatives and consequences of reopening the model

| Choice requiring confirmation | Consequence if selected |
|---|---|
| iid equal-probability +/-J (proposed) | Binary disorder tokens, multispin opportunities, benchmark Tc around 1.11; this document's template counts apply directly. |
| Exactly half +J bonds in every sample | A globally constrained finite-size disorder ensemble, as used in the early Hukushima-Nemoto simulation; likely the same thermodynamic limit but different finite-size corrections and disorder generator. Moreover, L=45 has `3L^3=273,375` bonds, an odd number, so literal equal halves are impossible. The author would need to define a nearest-balanced convention; it must not be mislabeled iid. |
| Gaussian J with mean 0 and variance 1 | Continuous disorder features, a different numerical Tc (about 0.951 in the cited study), different equilibration identities, no binary lookup/multispin assumption, and a new performance pilot. |
| Another three-dimensional spin glass | Invalidates the present Hamiltonian, literature anchors, input encoding, and possibly the order parameter; design must return to Stage 0. |

The challenge author or user must select one row before Stage 3. No code or
configuration may hide this choice behind a default.

## 3. Two-copy overlap field

For each fixed J and temperature, introduce two real replicas a and b:

```text
q_x = s_x^(a) s_x^(b)
q = (1/N) sum_x q_x,       N=L^3.
```

In the unbiased physical ensemble, a and b are independent Markov chains with
independent random streams and the same J and T. In the biased VMCRG ensemble,
the term V(q',J) couples the two configurations; they remain two separately
updated copies, but they are no longer statistically independent under the
biased stationary measure. This distinction is recorded in every artifact.

The quenched average is ordered as

```text
[ <O(s^a,s^b)>_{T,J} ]_J,
```

never as a pooled average over measurements from different J. Ordinary
magnetization is not a spin-glass order parameter and is not a primary Tc
observable.

## 4. RG prescription

Let lattice coordinates run from 0 to L-1. With a recorded block origin, the
first deterministic RG map partitions the overlap field into disjoint
3 x 3 x 3 blocks and defines

```text
q'_R = sign(sum_{d_x,d_y,d_z=0}^2 q_{3R+d}).
```

There are 27 inputs, so no tie is possible. The baseline block origin is
`(0,0,0)`; all 27 origins are a preregistered sensitivity check and are never
treated as independent disorder samples.

- First RG: every listed production size supports L -> L/3; in particular,
  45 -> 15.
- Second RG: allowed only for L divisible by 9 and only after first-RG
  correctness, target-matching, and cost gates pass; in particular, 45 -> 15
  -> 5.
- Incremental sampling caches each block sum. One microscopic flip changes
  one q_x and can change at most one first-level block spin, then at most one
  second-level block spin.
- Each RG level has its own effective model. Reusing or warm-starting TT cores
  across levels is an optimization experiment, not an equality assumption.
- Disorder features at level n are derived from the exact microscopic bond
  preimage of that level's local stencil. They are not invented by assigning
  a single ad hoc bond to a coarse link.

## 5. VMCRG variational functional and sign

For fixed J and beta, write a paired microscopic state
`X=(s^a,s^b)`, its action

```text
A_{J,beta}(X) = beta [H_J(s^a) + H_J(s^b)],
tau(X) = q',
```

and the exact overlap-field effective Hamiltonian, up to a constant, as

```text
exp[-H'_{q,J,beta}(q')]
    = sum_X 1[tau(X)=q'] exp[-A_{J,beta}(X)].
```

For a normalized target distribution p_t(q'), add a bias V(q',J):

```text
Z_{V,J} = sum_X exp[-A_{J,beta}(X) - V(tau(X),J)]

Omega_J[V] = log(Z_{V,J}/Z_{0,J})
             + sum_{q'} p_t(q') V(q',J).
```

The functional derivative, and for a differentiable parameter theta the
parameter gradient, are

```text
d Omega_J / d theta
  = E_{p_t}[dV_theta/dtheta]
    - E_{biased,J}[dV_theta/dtheta].
```

The sign follows directly from differentiating `log Z_V`. At the unrestricted
minimum,

```text
p_{V*}(q'|J) = p_t(q')
H'_{q,J,beta}(q') = -V*(q',J) - log p_t(q') + constant.
```

The preferred target is independent uniform coarse overlap spins,
`p_t(q')=2^(-N')`. Therefore

```text
H'_{q,J,beta}(q') = -V*(q',J) + constant.
```

This is the renormalized effective Hamiltonian of the **two-replica overlap
field conditional on J and beta**. It is not the complete original
single-replica Edwards-Anderson Hamiltonian. With a restricted local TT, the
equation is approximate and target-distribution mismatch measures
representation/training error.

For shared parameters, training minimizes a disorder expectation
`E_J[Omega_J[V_theta]]`; train/validation/test splits are made by whole
disorder realizations. The functional is convex in the unrestricted function
V, but an MPS core parameterization is nonconvex and gauge-redundant. Multiple
initializations, canonicalization, and held-out validation are required.

The additive gauge is fixed by centering each local density over uniform q for
its fixed local J environment. For a binary TT this target mean can be
contracted exactly by summing each q physical leg; it does not require
enumerating all coarse configurations.

There is also a useful exact check before blocking. For a specified microscopic
overlap q, write `s^b_x=q_x s^a_x` and sum over `s^a`:

```text
exp[-H_{q,J,beta}(q)]
  = sum_{s^a} exp{beta sum_<xy> J_xy s^a_x s^a_y (1+q_x q_y)}.
```

This proves three design facts directly: global q -> -q is exact; fixed-J
overlap physics is generally sample dependent; and bond-sign dependence after
the spin sum occurs through frustration loops, not through a gauge-dependent
isolated bond sign. Blocking q to q' adds another constrained sum but does not
remove these facts.

## 6. Local shared MPS/TT bias

The global lattice is never serialized into one MPS. Instead,

```text
V_theta(q',J) = sum_R f_theta(X_R),
```

where X_R is a bounded local sequence around coarse site/cell R and the same
cores are shared over positions and disorder samples. A TT density with n
binary tokens has open-boundary cores

```text
G_1: 1 x 2 x chi,
G_i: chi x 2 x chi,
G_n: chi x 2 x 1,
f(X) = G_1[X_1] G_2[X_2] ... G_n[X_n].
```

For constant interior rank, its parameter count is
`P(n,chi)=4 chi + 2(n-2) chi^2`. Boundary ranks may be reduced to their exact
maximum, in which case the implementation records the smaller actual count.
Mandatory ranks are chi=2,4,8; chi=16 is an extension only.

### 6.1 Disorder encoding and local gauge symmetry

Raw local +/-J bonds are not valid scalar features: under the exact Ising
gauge transformation

```text
s_x^(a,b) -> epsilon_x s_x^(a,b),
J_xy -> epsilon_x epsilon_y J_xy,
q_x -> q_x,
```

the physics and q are unchanged while individual bond signs change. For each
connected local bond graph, the conditioned routes use one of two equivalent,
tested encodings:

1. deterministic spanning-tree gauge fixing, with tree bonds set to +1 and
   the remaining chord signs retained; or
2. an independent set of loop/plaquette flux products.

For a connected graph with V vertices and E bonds, there are E-V+1 independent
binary loop variables. Spatial transformations act on raw q and J together,
after which gauge canonicalization is repeated. This guarantees joint
covariance and avoids treating a gauge convention as physical information.

### 6.2 Candidate local templates

All proposed +/-J tokens have physical dimension d=2. Q and disorder tokens
are separate in the initial implementation; a paired d=4 token is only an
ablation because it changes parameter counts.

| Template | Sequence and conditioned content | q-only n | conditioned n | Changed densities for one changed q' | Assessment |
|---|---|---:|---:|---:|---|
| 3D cross | Center q, then +/-x, +/-y, +/-z q in a fixed shell order; interleave 12 adjacent elementary plaquette fluxes by plane and lexicographic offset | 7 | 19 | 7 | Natural centered stencil and cheap q dynamics, but the six star bonds alone contain no gauge-invariant disorder information; surrounding loops are essential. |
| Face/edge stencil | Center, six axial nearest q, twelve face-diagonal q; interleave 12 selected local plaquette fluxes anchored to their first site | 19 | 31 | 19 | Better angular/range coverage, but exact symmetry and accepted-update refresh are materially more expensive. |
| 2 x 2 x 2 cube | Eight q corners in a Gray/serpentine cube path; interleave five chord bits after gauge-fixing a fixed seven-edge spanning tree of the 12-edge cube | 8 | 13 | 8 | Smallest closed 3D object with a complete internal frustration encoding; lookup is feasible and this is the recommended first benchmark template. |
| Factorized 3 x 3 x 3 | Twenty-seven q in a 3D serpentine order; interleave 28 gauge-fixed chord bits from the 54 internal bonds (`54-27+1=28`) at their spatial anchors | 27 | 55 | 27 | Largest receptive field and no exponential table, but the slowest and highest-memory option; use only if smaller stencils demonstrably underfit. |

Binary-token parameter counts are:

| Template | Route A q-only P for chi=2/4/8/16 | Routes B/C conditioned P for chi=2/4/8/16 |
|---|---:|---:|
| Cross | 48 / 176 / 672 / 2,624 | 144 / 560 / 2,208 / 8,768 |
| Face/edge | 144 / 560 / 2,208 / 8,768 | 240 / 944 / 3,744 / 14,912 |
| 2 x 2 x 2 cube | 56 / 208 / 800 / 3,136 | 96 / 368 / 1,440 / 5,696 |
| Factorized 3 x 3 x 3 | 208 / 816 / 3,232 / 12,864 | 432 / 1,712 / 6,816 / 27,200 |

For a direct contraction, recomputing a local density is O(n chi^2). If a
changed q' occurs in m translated stencils, a simple exact delta is
O(m n chi^2) before symmetry cost. Left/right environments can make a proposal
O(m chi^2), but refreshing them after acceptance costs O(m n chi^2) and their
memory multiplies by temperatures and disorder batches. The pilot compares
both approaches.

Small templates may use an exact frozen lookup: 2^13=8,192 entries for the
conditioned cube and 2^19=524,288 for the conditioned cross. The 31- and
55-token tables are forbidden. In particular, a full 3 x 3 x 3 q lookup alone
already has 2^27 states before disorder and is not an implementation route.

### 6.3 Trainability and numerical controls

Every MPS arm must implement and test:

- deterministic left-canonical normalization after a configured update
  interval, with represented values unchanged within float64 tolerance;
- exact uniform-target centering to remove the additive constant;
- global gradient clipping and separately logged unclipped/clipped norms;
- total/core parameter norms, singular-value or transfer-spectrum summaries,
  output range, acceptance, and target mismatch;
- immediate NaN/Inf rejection for inputs, cores, contractions, gradients,
  optimizer state, and checkpoints;
- atomic checkpoints containing cores, optimizer state, RNG states, config and
  source hashes, disorder split, beta, RG level, and training step;
- multiple preregistered initializations and a frozen held-out evaluation;
- chi=2,4,8 under matched protocols; chi=16 only after the pilot shows an
  unresolved capacity trend and adequate cost.

## 7. Three model routes

| Route | Physics and sample sharing | Parameters and update cost | Symmetry | Stability and 45^3 feasibility | Role |
|---|---|---|---|---|---|
| A: q-only disorder-averaged shared TT | Learns an average over disorder mixtures, not H'_{q,J} for a fixed sample. Shares all parameters across J. | Lowest token count and cheapest local deltas. | Exact q Z2 and cubic symmetry are straightforward, but absence of J is not a gauge-invariance solution to fixed-J conditioning. | Stable, small memory, and feasible. Scientifically incomplete for the requested conditional effective Hamiltonian. | Ablation and diagnostic fallback only. |
| B: disorder-conditioned shared TT | Inputs q plus gauge-canonical J/flux information; can approximate H'_{q,J} while sharing cores across samples. | More tokens and symmetry work; no per-sample trainable parameter block. Direct local cost remains independent of L apart from the number of translated densities. | Exact joint q/J spatial covariance, q Z2, and gauge covariance can be structural. | More difficult nonconvex optimization, but cube/cross versions are feasible; full 3^3 is pilot-gated. | Scientific fallback if residual decomposition in C is unstable. |
| C: finite-coupling VMCRG baseline plus conditioned TT residual | `V=V_linear(q',J)+V_TT(q',J)`. The finite even-overlap basis gives interpretable projections; the conditioned TT learns omitted local structure. | Adds a small fixed operator vector to Route B. Local traditional deltas are cached; TT dominates incremental cost. | Both branches must obey the same exact Z2/cubic/gauge rules; the residual is centered and projected against the baseline basis to control non-identifiability. | Staged baseline -> residual -> optional joint tuning should be more diagnosable, but this is a hypothesis to benchmark, not a guaranteed win. | **Recommended main route.** |

The traditional basis is frozen in Stage 3 before Hard Goal production data are
seen. It contains even overlap operators allowed by q -> -q (for example,
preregistered short-range pair shells and a local four-q plaquette) and a small
orbit-summed set of the same operators multiplied by gauge-invariant local loop
fluxes. Constants are omitted. Both a q-only literature-style linear ablation
and this disorder-conditioned finite linear model are reported; the latter is
the primary fair baseline, so the TT cannot win merely because it alone sees J.
Route C trains the baseline first, freezes it while testing the residual, and
permits joint tuning only after stability. Residual target means and projections
onto the linear basis are removed or reported so a TT cannot claim improvement
merely by relearning the baseline.

Fair comparisons use identical disorder splits, initial physical states,
proposal counts, frozen measurement lengths, and hardware. Results are shown
under both matched spin-proposal budget and matched wall time. Primary
representation metrics are frozen held-out VMCRG objective difference,
small-stencil marginal TV/JS distance, standardized residuals of a held-out
operator set, and a cubic-invariant two-sample/MMD statistic. Improvement must
have a disorder-bootstrap interval excluding zero on at least one
preregistered primary metric without a material regression on the others.

**Recommendation:** begin Stage 5 with Route C using the conditioned 2 x 2 x 2
cube at chi=2,4,8, and compare the cross stencil. Use Route B as the scientific
fallback if the linear/residual decomposition or joint optimizer is unstable.
Route A can diagnose whether disorder conditioning is the difficulty, but it
cannot by itself satisfy the Hard Goal claim.

## 8. Exact symmetry contract

Only structural guarantees are called exact.

| Transformation | Required behavior | Enforcement |
|---|---|---|
| Replica exchange a <-> b | q_x is unchanged | Automatic because the model receives q, not ordered replica labels |
| Global flip of both replicas | q_x is unchanged | Automatic for the same reason |
| Global flip of one replica | q_x -> -q_x and H'_q must be even at zero field | Exact evenization `f(q,J)=[f_raw(q,J)+f_raw(-q,J)]/2`, or joint orbit canonicalization |
| Cubic rotations/reflections O_h | `V(gq,gJ)=V(q,J)` for all 48 operations | Exact group averaging or deterministic canonical representative of the joint discrete orbit; data augmentation alone is insufficient |
| Spatial translation | A fixed J is not translation invariant; translating q and J together must leave the shared construction covariant | Shared local density with jointly translated inputs; never claim fixed-J translation symmetry |
| Local +/-J gauge transform | q is unchanged while J transforms | Gauge-canonical chord/loop features; raw J input is forbidden |

Naive group averaging costs up to 48 x 2 TT contractions. It is the
correctness-first definition, and a frozen cube/cross lookup amortizes that
cost. Canonicalizing the joint `O_h x Z2` orbit and contracting one
representative defines a different, still exactly invariant parameterization;
it is benchmarked against group averaging for held-out accuracy and cost, not
asserted to give the same value for identical raw cores. If neither is
feasible, the fallback is a smaller stencil with explicit averaging, not
symmetry-by-augmentation.

## 9. Monte Carlo and parallel tempering

### 9.1 Unbiased FSS arm

For every J, maintain two independent PT ladders A and B, each containing one
configuration at every temperature. Local sweeps and exchanges use independent
random streams. The overlap at temperature T_m pairs the configurations
currently occupying T_m in the two ladders.

For a local spin flip in one replica, standard Metropolis or heat-bath updates
use beta_m Delta H. Since every proposed production L is divisible by 3, an
exact three-color schedule `(x+y+z) mod 3` gives independent update sets for
the **unbiased nearest-neighbor Hamiltonian** under periodic boundaries,
including odd L=45. A two-color checkerboard is invalid for odd periodic L. A
random-sequential reference kernel validates the colored kernel.

Three colors are not sufficient once V(q',J) is present: multiple same-color
microscopic flips can change one majority block or overlapping TT densities.
The biased kernel therefore starts from random-sequential updates vectorized
over independent J/temperature/walker states. Any later within-state parallel
kernel must color the full proposal conflict graph induced by the RG blocks and
TT receptive field, and match the sequential transition kernel on small exact
tests.

### 9.2 Biased VMCRG arm

A state at one PT position is the pair X=(s^a,s^b), updated under

```text
pi_m(X) proportional to
  exp[-beta_m (H_J(s^a)+H_J(s^b)) - V_m(q'(X),J)].
```

A local flip accepts with

```text
min(1, exp[-beta_m Delta H_pair - Delta V_m]).
```

Swapping whole paired states X_m and X_n uses

```text
Delta_swap = A_m(X_n) + A_n(X_m) - A_m(X_m) - A_n(X_n),
accept = min(1, exp[-Delta_swap]),
A_m(X) = beta_m E_pair(X) + V_m(q'(X),J).
```

The correctness-first protocol trains one target-beta bias per ladder and uses
that same frozen/current V at every auxiliary temperature, so the V terms
cancel in a swap. If a later beta-conditioned model uses different V_m, the
cross-bias terms above are mandatory and are tested numerically for detailed
balance. Only the target-beta slot contributes to that VMCRG gradient.

Training is nonstationary. Optimization samples are separated from a frozen
checkpoint validation run. Multiple independent paired ladders supply gradient
blocks and convergence diagnostics.

At zero field, randomly flipping every spin in one whole real replica is an
exact unit-acceptance move: H is unchanged and q -> -q. Because the bias is
structurally even, it is also unit acceptance in the biased arm. This move is
included to sample both overlap-sign sectors and is tested independently; it
does not substitute for temperature round trips among glassy basins.

### 9.3 Temperature ladder

The provisional range is T in [0.80, 2.0], with denser points around
1.0-1.2 and permission to raise T_max toward 2.4 if round trips do not erase
low-temperature memory. The number and spacing of temperatures are selected
by Stage 6 pilot acceptance and round-trip measurements, not hardcoded from a
smaller size. A planning range of roughly 48-128 temperatures is not a frozen
protocol.

A Slurm cell owns an entire temperature ladder. Splitting individual
temperatures into independent jobs would destroy replica exchange and is not
allowed. Odd/even adjacent exchange attempts alternate after local sweeps.

### 9.4 Exact reweighting rule

Because `P_V proportional to P_0 exp(-V)`, unbiased expectations from a frozen
biased run would use weights `w=exp(V)`:

```text
<O>_0 = <O exp(V)>_V / <exp(V)>_V.
```

This route is accepted only with stable log-sum-exp evaluation, agreement with
a separate unbiased control, no influential single weight, and a
preregistered weight ESS threshold. The default final FSS evidence remains
the separate unbiased arm.

## 10. Equilibration and sample acceptance

The symmetric +/-J model does not have the Gaussian energy/link-overlap
equilibration identity. Every disorder sample and temperature must pass all
applicable gates below before entering an observable or fit.

| Diagnostic | Provisional gate; exact numeric thresholds freeze after Stage 6 |
|---|---|
| Adjacent exchange | Record every edge. Target 0.20-0.50; any persistent bottleneck below 0.15 is a pilot failure. Acceptance above 0.50 is inefficient but not a correctness failure. |
| Temperature travel | Provisionally at least 10 complete low-to-high-to-low round trips per production chain, with no replica trapped in a subrange; threshold is increased if this is insufficient for chain agreement. |
| Forgetting at T_max | Configurations returning from T_max must lose detectable dependence on their prior low-temperature basin; otherwise raise T_max or no-go. |
| Logarithmic binning | Successive run lengths double. The final three bins for energy, q^2, q^4, chi_SG(0), and chi_SG(k_min) agree within combined 2-standard-error intervals and show no monotone drift. |
| First/second half | Estimates agree within their autocorrelation-aware combined uncertainty. |
| Independent chains | At least four independent chain pairs in pilots; split-Rhat <=1.05 and compatible disorder-conditioned means for primary observables. |
| IAT and ESS | Automatic-window integrated autocorrelation times are finite and stable. Provisionally ESS >=200 per primary observable per sample/temperature, and aggregate thermal uncertainty contributes less than 25% of the disorder-sampling error. |
| Bias validation | Frozen biased chains meet the same stationarity checks and target statistics are stable across initializations. |

Energy and overlap time series, temperature labels, exchange acceptances,
round-trip counts, IAT windows, ESS, bin estimates, and gate decisions are
stored. A failed sample is not replaced by a new random J. The same sample is
extended from its checkpoint or marked failed. A Tc claim additionally
requires at least 95% of preregistered samples to pass at every fitted size,
with no detected association between failure and pilot hardness metrics;
otherwise the protocol is extended or the result is no-go. All failures stay
visible.

## 11. Physical observables and disorder averaging

With normalized Fourier overlap

```text
q(k) = (1/N) sum_x q_x exp(i k dot x),
chi_SG(k) = N [ <|q(k)|^2>_{T,J} ]_J,
chi_SG = chi_SG(0) = N [<q^2>]_J,
```

average the three minimal axial wavevectors
`(2 pi/L,0,0)`, `(0,2 pi/L,0)`, and `(0,0,2 pi/L)` before forming

```text
xi_L = 1/[2 sin(pi/L)] * sqrt(chi_SG(0)/chi_SG(k_min) - 1),
R_xi = xi_L/L.
```

The Binder convention is fixed as

```text
g = 1/2 * (3 - [<q^4>]_J / [<q^2>]_J^2).
```

The positions of thermal and disorder averages are part of the data schema.
Changing to a per-sample ratio is a different estimator and requires a new
analysis label.

The independent disorder realization is the uncertainty unit. Bootstrap or
jackknife resamples an entire J record, preserving all temperatures, chains,
time bins, and observables for that J. Measurements within one J are never
counted as independent disorder samples. Neural train/test splits and paired
baseline comparisons use whole J records. Bootstrap seeds and indices are
saved.

## 12. Finite-size plan and Tc determination

### 12.1 Sizes and provisional sample floors

The initial production candidate set is

```text
L = {6, 9, 12, 15, 18, 24, 27, 45}.
```

All sizes support one 3x3x3 RG step, the subset `{9,18,27,45}` supports two,
and the set contains both even and odd periodic lattices. This permits a
parity/correction check rather than extrapolating to odd L=45 from even sizes
alone. Add L=36 if the Stage 6 correction/parity fits are unstable. L=3 or
smaller appears only in exact/small validation and is not assumed to lie in
the asymptotic FSS window.

Provisional minimum unique-disorder counts are:

| Size | Unique J samples |
|---|---:|
| L <= 12 | 8,192 |
| L=15,18 | 4,096 |
| L=24,27 | 2,048 |
| L=45 | 1,024, organized as four independently seeded 256-sample batches |

These are budget placeholders, not a guarantee of power. Stage 6 freezes the
counts using measured disorder variance and a target Tc precision. Chain seeds
for one J do not increase the disorder count.

### 12.2 Crossing and fit contract

1. Plot raw R_xi and g for every size and obtain bootstrap pair-crossing
   distributions. No claim is made from only two sizes.
2. Freeze T windows, minimum L, polynomial order, parity treatment, and
   exclusion rules before the final L=45 batches are unblinded.
3. Fit each dimensionless observable to a correction-aware form such as

   ```text
   R(L,T) = F0(x) + L^(-omega) F1(x) + analytic/parity corrections,
   x = (T-Tc) L^(1/nu).
   ```

   The literature value omega about 1.0 may define a sensitivity prior, but
   free-omega and fixed-window alternatives are reported. It is not used to
   force the answer.
4. Run separate R_xi and Binder fits, then a joint shared-Tc fit with distinct
   scaling functions and correction amplitudes. Chi_SG scaling is a supporting
   exponent/consistency check.
5. Repeat across preregistered L_min and T-window variants. The spread of
   accepted fits is the finite-size systematic, not hidden by a single best
   chi-squared selection.

The primary Tc interval comes from the correction-aware R_xi analysis and
joint dimensionless fit. Success requires the R_xi and Binder Tc intervals to
overlap after statistical plus finite-size systematic error, and the
independent VMCRG flow-change interval to overlap that result. A literature
value near 1.11 is an external validation check only.

### 12.3 Neural RG-flow criterion

For target temperatures spanning the crossing window, compare one-step
effective models in a common centered gauge using:

- the frozen traditional coupling projection;
- preregistered even overlap correlations and loop-conditioned summaries;
- held-out target-distribution distances; and
- a flow coordinate defined and frozen from pilot data, not selected after
  L=45 results are visible.

Bootstrap over J to locate the temperature interval where the flow changes
between high- and low-temperature basins or approaches a fixed point. Only
after one-step validation may the same comparison use two steps. Compare a
directly trained composite two-step model with the iterated model to quantify
error accumulation. Route C must show whether the TT residual reduces that
error relative to the same finite-coupling baseline.

Neural loss, TT norm, or one core entry is never by itself a Tc estimator.

## 13. Error budget

| Error source | Measurement and propagation |
|---|---|
| Disorder statistics | Whole-J bootstrap/jackknife, preserving temperature covariance; report effective completed sample count by size. |
| Thermal autocorrelation | IAT/ESS and time-block resampling inside each J; propagate as a nested component when non-negligible. |
| Non-equilibration | Per-sample fail-closed gates, completion fraction, extension history, and sensitivity to censored samples. |
| Finite size/scaling correction | L_min, T-window, polynomial, omega, and parity sensitivity; include accepted-fit spread. |
| Neural representation | chi/stencil curve, held-out target mismatch, traditional projection residuals, one-vs-two-step accumulation. |
| Neural optimization | Multiple initializations and disorder splits; report failed runs and between-seed dispersion. |
| Reweighting | Log-weight range, weight ESS, influence diagnostics, and unbiased-control agreement; reject collapsed weights. |
| RG prescription | Block-origin sensitivity and direct-composite versus iterated RG comparison. |
| Model definition | Separate result namespace for iid +/-J, exact-half +/-J, or Gaussian; no cross-model pooling. |

All four headline uncertainties are reported separately: statistical,
finite-size, neural-representation, and residual non-equilibration risk.

## 14. Compute and memory feasibility

For L=45,

```text
N = 45^3 = 91,125 sites
number of stored positive-direction bonds = 3N = 273,375
first coarse lattice = 15^3 = 3,375 sites
second coarse lattice = 5^3 = 125 sites.
```

Two int8 spin copies across 128 temperatures require about 22.2 MiB per J
before energies, RNG, caches, duplicate chains, and batching. TT parameters are
kilobytes to hundreds of kilobytes; spin-update throughput, exact symmetry
evaluation, temperature ladders, and local caches dominate. A cache of TT
environments for every temperature and symmetry image can exceed useful device
memory even though one model is small, so memory is benchmarked on the actual
batch layout.

Pre-pilot planning envelope:

| Stage | Scope | Planning envelope | Go/no-go measurement |
|---|---|---|---|
| Stage 4 | Existing 2D 45x45 MPS-VMCRG regression | Local minutes to a few GPU-hours | Exact gradients, local deltas, symmetry, checkpoint, and known 2D behavior pass |
| Stage 5 | 3D exact/tiny and L=6-12 checks | Less than a few GPU-hours | Energy/overlap observables, PT detailed balance, gradient and cache agreement |
| Stage 6 | Medium-size ladder/stencil/sample pilot | Roughly 8-24 accelerator-hours | Measured flips/s, round trips, IAT, TT cost, variance and output bytes freeze protocol |
| Stage 7 | Full multi-size production including L=45 | Plausibly 10^3-10^4 A800-equivalent GPU-hours and 0.2-1 TB of checkpointed compact summaries | Budget and projected precision approved from measured pilot throughput |

The Stage 7 range is deliberately broad and is not authorization. If the
pilot extrapolation exceeds the approved budget, production is no-go or the
sample/power contract is renegotiated explicitly; it is never silently
reduced.

The active `qdeshell` profile exposes one-node jobs with up to 64 CPU cores,
about 2 TB host memory, 8 A800 GPUs, a required request of at least one A800,
a 24-hour hard walltime, and array limit 200. It has recently been heavily
allocated. The `scnet` profile exposes up to 128 CPU cores, about 510 GB, and
8 Hygon DCUs per node with a much larger recorded node pool, but code/runtime
compatibility and user authorization are not confirmed. Queue state must be
re-probed immediately before any submission.

## 15. Slurm decomposition and immutable outputs

A scheduler cell is

```text
(L, disorder_batch, evidence_arm, target_beta/model/chi, algorithm_seed)
```

and contains the complete temperature ladder. Within the maximum array size,
cells batch enough J samples to amortize startup while retaining deterministic
per-J RNG streams. Training gradient shards, frozen neural validation, and
unbiased FSS are distinct arms and output namespaces.

Every cell writes a hash-linked manifest, per-J equilibration status, compact
time-bin summaries, checkpoint, resource telemetry, and terminal
classification. Jobs checkpoint comfortably inside 24 hours and resume only
the same missing/unfinished cells; successful immutable summaries are never
overwritten. Compute nodes require a fully staged environment because they
have no confirmed internet.

Before Stage 7 submission, the exact CPU, accelerator, memory, walltime,
array size, temperature count, J count, output estimate, source/config hashes,
and recovery procedure are shown to the user for approval. Scheduler
completion is not scientific success; fetched manifests and equilibration
gates are.

## 16. Stage gates

| Stage | Required result | Go/no-go condition |
|---|---|---|
| 0: design | This document: model, overlap RG, VMCRG, MPS routes, PT/FSS, cost, success | All required topics explicit; ambiguities labeled provisional |
| 1: self-review | Conceptual audit in Section 18 | Every discovered issue corrected in the design, not merely listed |
| 2: user/author confirmation | Model distribution, budget, evidence contract, route and sizes ratified | No production code or job before explicit confirmation |
| 3: writing plan | File/test/config tasks and milestone plan | Each milestone has measurable go/no-go; no hidden production defaults |
| 4: 2D regression | 45x45 Easy Goal or equivalent end-to-end MPS regression | VMCRG sign/gradient, MPS bias, incremental updates, statistics pass; not Hard Goal evidence |
| 5: 3D small validation | Exact enumeration/transfer checks plus high-quality small L | PT detailed balance/equilibration, q observables, xi/Binder, neural gradients match references |
| 6: medium pilot | Frozen temperature grid, sweeps, walkers, chi/stencil and J counts | Round trips/equilibration and measured resource/power targets pass |
| 7: L=45 production | Approved Slurm arrays finish and fetch | Actual L=45 samples pass equilibration; generated scripts alone do not pass |
| 8: statistics | Immutable-summary bootstrap and correction-aware fits | R_xi and Binder intervals consistent; RG interval overlaps |
| 9: report/handoff | Report, plots, README, configs, failure analysis, tests, diff | User reviews before commit, push, or PR-ready action |

## 17. Minimum success standard

1. Record a complete 3D spin-glass Hamiltonian and disorder distribution.
2. Pass exact or reliable literature benchmarks at small sizes.
3. Demonstrate PT equilibration with round trips and autocorrelation evidence.
4. Show an MPS neural VMCRG improvement on at least one preregistered metric
   over a fair finite-coupling baseline.
5. Actually complete and equilibrate L=45 production data.
6. Obtain compatible Tc intervals from xi_L/L and Binder evidence.
7. Obtain an RG-flow Tc interval statistically compatible with FSS.
8. Cover multiple independent algorithm seeds and enough unique J samples.
9. Report statistical, finite-size, neural, and non-equilibration uncertainty.
10. Report negative results, failed convergence, and initialization dependence
    without replacing seeds or moving thresholds.

## 18. Stage 1 conceptual self-review and corrections

The following errors were actively sought and corrected in the design.

1. **Silent model choice.** Issue #28 does not choose +/-J or Gaussian.
   Correction: iid +/-J was presented provisionally with separate alternative
   consequences, then explicitly confirmed by the user in Stage 2.
2. **Confusing overlap with magnetization.** A single-copy magnetization can
   vanish without diagnosing glass order. Correction: all primary RG/FSS
   objects use two-copy q; magnetization is diagnostic only.
3. **Calling biased replicas independent.** V(q') couples a and b.
   Correction: independence is required for the unbiased physical arm;
   biased pairs are separately updated but jointly distributed.
4. **Treating a q-only shared TT as fixed-J physics.** Fixed disorder breaks
   ordinary translation symmetry and changes the effective action.
   Correction: Route A is an averaged ablation; Routes B/C condition on local
   gauge-invariant disorder.
5. **Feeding raw J signs.** Raw bonds change under local gauge transforms.
   Correction: use tested spanning-tree/loop canonical features and transform
   q/J together under spatial operations.
6. **Overstating variational convexity.** Omega is convex in the unrestricted
   function V, not generally in TT cores. Correction: canonicalization,
   multiple initializations, held-out splits, and failure reporting are
   mandatory.
7. **Wrong PT acceptance with a neural bias.** Temperature-dependent biases
   do not cancel in exchanges. Correction: use the full cross-action formula;
   default to one target-beta bias shared over its auxiliary ladder.
8. **Using biased chains for final Tc.** Neural bias can alter crossings and
   failed reweighting can look precise. Correction: independent unbiased PT is
   the default; exact reweighting has explicit ESS/control gates.
9. **Using two-color updates at odd L.** A 45-site periodic direction is not
   bipartite. Correction: exact three-color updates plus a random-sequential
   reference for the unbiased arm. A further correction is that three colors
   do not decouple the neural bias; biased within-state parallelism must use
   the full conflict graph or remain sequential.
10. **Applying the Gaussian equilibration identity to +/-J.** It does not
    apply to bimodal bonds. Correction: logarithmic bins, stationarity,
    independent chains, IAT/ESS, and temperature travel are the core gates.
11. **Enumerating a 3^3 patch.** There are 2^27 q patterns before disorder.
    Correction: direct TT contractions/caches for the factorized stencil;
    lookup is restricted to demonstrably small cross/cube inputs.
12. **Breaking quenched statistics.** Measurements within one J are
    correlated and temperatures share J. Correction: resample whole disorder
    records and preserve their temperature/chain structure.
13. **Declaring a crossing from two sizes or ignoring corrections.** Published
    Binder and xi estimates visibly differ without careful corrections.
    Correction: eight candidate sizes, parity checks, correction-aware fits,
    and fit-window systematics.
14. **Dropping hard-to-equilibrate samples.** Censoring can bias the disorder
    ensemble. Correction: fixed sample IDs, checkpoint extensions, completion
    thresholds, and no replacement.
15. **Splitting a PT ladder by temperature in Slurm.** Independent temperature
    jobs cannot round-trip. Correction: a scheduler cell owns the full ladder.
16. **Calling H'_q the original Hamiltonian.** The recovered object is a
    two-replica overlap marginal. Correction: its conditional definition and
    distinction from H_J are explicit in Section 5.
17. **Assuming repeated-RG comparability.** TT gauge, additive constants,
    block origins, and representation error can fake a flow. Correction:
    centered gauges, fixed projections, origin sensitivity, and direct versus
    iterated two-step comparisons.
18. **Using an unfair disorder-blind linear baseline.** A conditioned TT could
    improve solely because it sees J. Correction: the primary finite-coupling
    comparator includes a preregistered, gauge-invariant flux-conditioned
    linear basis under the same sampling budget.
19. **Requesting exact-half bonds at L=45.** The lattice has an odd number of
    bonds. Correction: iid p=1/2 remains the recommendation; any constrained
    alternative needs an explicit nearest-balanced rule and separate label.

No unresolved item above is waived. Items depending on model or budget remain
Stage 2 confirmation questions.

## 19. Failure and downgrade plan

| Failure | Response |
|---|---|
| Route C residual/joint optimization is unstable | Keep the frozen fair baseline and switch to direct conditioned Route B under the same stencil/rank budget. |
| Conditioned cube/cross underfits | Test the preregistered face/edge stencil, then factorized 3^3 only if target-error improvement justifies measured cost. |
| Exact symmetry averaging is too slow | Benchmark the separately labeled exact orbit-canonical parameterization, or use a smaller explicitly averaged stencil. Never claim it is numerically identical to group averaging, and never replace exact symmetry with augmentation. |
| MPS does not beat the baseline | Report a scientific negative result. Route A may diagnose the cause but cannot be relabeled as Hard Goal success. |
| PT fails at medium/L=45 | Densify bottleneck temperatures, raise T_max, lengthen the same sample checkpoints, and re-pilot. If budget or round trips still fail, do not quote Tc. |
| L=45 disorder power is insufficient | Request an explicit larger budget or report an underpowered/no-go result; do not count thermal measurements as new disorder samples. |
| qdeshell queue is impractical | Re-probe alternatives; use SCNet only after runtime compatibility, resource preview, and user approval. |
| User selects Gaussian/exact-half disorder | Return affected encodings, benchmarks, equilibration checks, and sample generator to the appropriate earlier gate before implementation. |

## 20. Stage 2 confirmation record

On 2026-07-28 the user accepted all five proposed decisions:

1. iid equal-probability +/-J Edwards-Anderson disorder;
2. final Tc from unbiased correction-aware xi_L/L plus Binder FSS, with neural
   RG flow as independent consistency evidence;
3. Route C as the main model and Route B as the scientific fallback, beginning
   with conditioned cube/cross benchmarks;
4. the candidate sizes and provisional J-sample floors as the input to a
   Stage 6 power calculation; and
5. the resource-gated supercomputer workflow, including Stage 6 evaluation of
   qdeshell and SCNet compatibility.

The exact Stage 7 CPU/GPU/memory/walltime/array/storage request is intentionally
not approved yet. It must be computed from the pilot and shown for confirmation
immediately before submission.

## References

1. QuantumBFS/quantum.harness, Issue #28,
   <https://github.com/QuantumBFS/quantum.harness/issues/28>.
2. QuantumBFS/quantum.harness, PR #154,
   <https://github.com/QuantumBFS/quantum.harness/pull/154>.
3. D. Wu and R. Car, "Variational Approach to Monte Carlo Renormalization
   Group," Phys. Rev. Lett. 119, 220602 (2017), arXiv:1707.08683.
4. H. G. Katzgraber, M. Koerner, and A. P. Young, "Universality in
   three-dimensional Ising spin glasses: A Monte Carlo study," Phys. Rev. B
   73, 224432 (2006), arXiv:cond-mat/0602212.
5. M. Hasenbusch, A. Pelissetto, and E. Vicari, "Critical behavior of
   three-dimensional Ising spin glass models," Phys. Rev. B 78, 214205
   (2008), arXiv:0809.3329.
6. K. Hukushima and K. Nemoto, "Exchange Monte Carlo Method and Application
   to Spin Glass Simulations," J. Phys. Soc. Jpn. 65, 1604 (1996),
   arXiv:cond-mat/9512035.
