# Prospective G1 v2 preregistration for issue #121

- Team: `Genshin_Impact`
- Issue: `QuantumBFS/quantum.harness#121`
- Amendment scope: the large-lattice CTQMC G1 validation protocol only
- New protocol ID: `issue121-triangular-large-lattice-v2`
- Status: frozen prospectively after the terminal v1 audit and before any v2 result is generated

The repository commit that first adds this document is the v2 freeze commit.
No v2 chain, exact-diagonalization output, pilot output, or gate may be generated
before that commit exists. After that commit, every choice below is immutable.
Any later change requires a separately named prospective protocol; it may not be
silently folded into v2.

## 1. Frozen v1 evidence

The v1 executable and result identity are:

- executable commit: `382e64e03798d3a629ee369c2f6a28e6f7605564`
  (short form `382e64e`);
- result root:
  `tracks/qmc/results/Genshin_Impact-121/20260730-large-lattice-382e64e/`;
- `index.json` SHA256:
  `48e4105356bcac107994d8a7b96a95bcc6070525a16d38d76edb7cf87d7b39e0`;
- `gates/G1.json` SHA256:
  `8d110898750476dde97f5ecfb605c16b9f301b4642e7e76e0c11063827e4e3ff`.

The terminal v1 workflow facts are:

- G0 Slurm job `43389`: `PASS`;
- G1 probe job `43391` and remaining-array job `43394`: all 32 of 32
  chains produced `CHAIN_COMPLETE`;
- independent G1 audit job `43434`: `INCONCLUSIVE`;
- the v1 protocol ID was `issue121-triangular-large-lattice-v1`.

The authoritative files are:

- `tracks/qmc/results/Genshin_Impact-121/20260730-large-lattice-382e64e/gates/G0.json`;
- `tracks/qmc/results/Genshin_Impact-121/20260730-large-lattice-382e64e/gates/G1.json`;
- `tracks/qmc/results/Genshin_Impact-121/20260730-large-lattice-382e64e/index.sha256`;
- `tracks/qmc/results/Genshin_Impact-121/20260730-large-lattice-382e64e/slurm/audit-g1.43434.out`;
- `tracks/qmc/results/Genshin_Impact-121/20260730-large-lattice-382e64e/exact/g1/L3-b0.json`;
- `tracks/qmc/results/Genshin_Impact-121/20260730-large-lattice-382e64e/manifests/g1/L3/beta-0p5/chain-0.json`.

### Exact v1 false leaf tests

There were exactly four false leaf tests in the v1 G1 gate. Parent `pass=false`
objects are aggregates of these leaves and are not additional failures.

| Kind | Cell and observable | Frozen v1 numbers | Why false in v1 |
|---|---|---|---|
| ED | `L3-b0`, `real_space_green["1,0"].one_body` | QMC = `[0.0032190527258243243, 0.0]`; ED = `[0.003530271749985057, 0.0]`; max absolute error = `0.0003112190241607326`; MCSE = `3.4617482465412555e-05`; allowance = `5×MCSE = 0.00017308741232706278` | `0.0003112190241607326 > 0.00017308741232706278` |
| acceptance | `L2-b3` | accepted/attempted = `75767/84003`; rate = `0.901955882528005` | outside v1 range `[0.1, 0.9]` |
| acceptance | `L3-b2` | accepted/attempted = `76215/83994`; rate = `0.9073862418744196` | outside v1 range `[0.1, 0.9]` |
| acceptance | `L3-b3` | accepted/attempted = `78601/84037`; rate = `0.9353142068374645` | outside v1 range `[0.1, 0.9]` |

The v1 ED discrepancy is not reinterpreted here as a pass. The v1 record lacked
a stored per-measurement trace for every real-space Green-function component,
so its reported MCSE did not include a component-specific autocorrelation term.
This motivates a new prospective measurement and uncertainty protocol; it does
not prove in advance that the v1 discrepancy was only an error-bar artifact.

Likewise, an upper acceptance-rate cutoff is not a correctness or mixing
criterion. High acceptance can be valid, but it also cannot establish
independence. v2 therefore uses acceptance only to detect a completely frozen
sampler and leaves convergence to R-hat and ESS.

## 2. Frozen v2 protocol

### 2.1 Protocol identity and independent randomness

- `protocol_id = "issue121-triangular-large-lattice-v2"`.
- `seed_base = 221000000`.
- The chain rule is
  `seed = 221000000 + 10000×L + 10×beta_index + chain_id`.
- `beta_index` remains `{1/2: 0, 1: 1, 2: 2, 4: 3}`.
- Each cell still has four chains: chain 0 and 1 cold, chain 2 and 3 hot,
  with the same v1 initialization rule.
- No v1 RNG state, checkpoint, or chain output may be reused in v2.

The new base is deliberately independent of the v1 base `121000000`. Seeds may
not be replaced after inspecting a chain.

### 2.2 G1 cells and fixed run length

The G1 fixtures remain the periodic triangular tori `L=2, N=4` and
`L=3, N=9` at `beta ∈ {1/2, 1, 2, 4}`. Physics parameters, boundary
conditions, measured displacements, momentum labels, and ED oracle are unchanged.

For every one of the 32 G1 chains, freeze:

| Parameter | v2 value |
|---|---:|
| total CTQMC steps | `300000` |
| warmup steps included in the total | `30000` |
| post-warmup measurements per chain | `270000` |
| measurement interval | `1` |
| checkpoint interval | `30000` |
| rebuild interval | `128` |
| chains per cell | `4` |
| post-warmup measurements per cell | `1080000` |

A checkpoint must bind the v2 protocol ID, seed, trace-storage mode, trace keys,
and trace lengths. Resume is allowed only from a valid v2 checkpoint for the
same chain. Missing, malformed, non-finite, or length-mismatched traces are a
hard validation failure. The fixed 300000-step result is terminal for v2; any
extension after seeing v2 output requires a new prospective protocol.

### 2.3 Real-space traces and autocorrelation-aware MCSE

For every `N≤9` chain and every preregistered displacement `(dx,dy)`, store
the complete post-warmup measurement trace of both real and imaginary components
of `real_space_green[dx,dy].one_body`. These traces must be present in the
checkpoint, serialized state, and final result without thinning or component
selection.

For each component `a ∈ {Re, Im}`, compute the same rank-normalized split-chain
diagnostics used by v1: split R-hat, bulk ESS, tail ESS, and the per-original-chain
integrated autocorrelation estimates. Let `s_pooled,a` be the ordinary sample
standard deviation of all four post-warmup component traces pooled together.
Define

`MCSE_corr,a = s_pooled,a / √max(1, ESS_bulk,a)`.

For each complex real-space observable, define the three error estimates as:

- `MCSE_correlated = max_a MCSE_corr,a`;
- `MCSE_between-chain = max_a [sd(chain means for a) / √4]`;
- `MCSE_naive = √(∑_c se_naive,c²) / 4`, retaining the v1 combined
  per-chain naive estimator;
- `MCSE_final = max(MCSE_correlated, MCSE_between-chain, MCSE_naive)`.

The ED comparison remains conservative and unchanged in form:

- `error = max_a |QMC_a - ED_a|`;
- `allowance = max(5×MCSE_final, 1e-10)`;
- the observable passes exactly when `error ≤ allowance`.

The gate output must record the real and imaginary component diagnostics and all
three MCSE candidates, so the selected maximum can be independently audited.
No trace, component, chain, or displacement may be excluded after inspection.

### 2.4 Acceptance is only a non-freezing gate

For G1, the G2 pilot, and G3 production, freeze the operational acceptance range
to `[0.05, 1.0]`, inclusive. The rate is `accepted / attempted`. A missing,
non-finite, or undefined rate, including `attempted = 0`, fails this operational
check. A rate below `0.05` means the sampler is operationally too frozen.

There is no high-acceptance failure: any finite rate up to and including `1.0`
passes this check. In particular, high acceptance is not evidence of a bug and
is not evidence of independent samples. The pilot uses this same pass range;
there is no separate upper pass/fail target.

The convergence gates remain hard and keep the v1 thresholds:

- rank-normalized split `R-hat ≤ 1.01`;
- bulk ESS `≥ 1000`;
- tail ESS `≥ 400`.

Acceptance cannot override an R-hat or ESS failure. The zero-weight,
negative-sign, fast-update residual, rebuild, provenance, and ED correctness
conditions also remain hard and unchanged.

### 2.5 Downstream production schedule is unchanged

Only the v2 clauses above change. The prospective production design remains:

- G2 pilot cells: `(L,beta) = (4,1/2), (8,2), (12,4)`;
- G3 full grid: `L ∈ {4,6,8,12,16}` crossed with
  `beta ∈ {1/2,1,2,4}`;
- four immutable-seed chains per cell, two cold and two hot;
- pilot-based resource capture and run-length freezing;
- equal extension of all four production chains under the existing
  preregistered rule;
- gate order `G0 → G1 → G2 → G3 → G4` and all existing dependency rules.

The Hamiltonian, local matrices, couplings, lattice geometry, boundary
conditions, `mu=0` interpretation limits, observables, full-grid cells,
positivity claim, and production resource policy are unchanged.

## 3. Prospective decision rule and non-retroactivity

v2 must write to a new result root and must never overwrite or edit the frozen
v1 root. Its index, executable commit, manifests, Slurm job IDs, completion
sentinels, gate files, and audit output must be recorded independently.

This amendment is prospective and post-v1:

1. It does not retroactively change any v1 threshold.
2. It does not delete or relabel any of the four v1 false leaf tests.
3. It does not reclassify the v1 `INCONCLUSIVE` audit as `PASS`.
4. It does not guarantee that v2 will pass.
5. If the longer independent run still violates ED, R-hat, ESS, positivity,
   residual, provenance, or operational acceptance gates, that v2 outcome is
   reported as observed. Thresholds, seeds, traces, and chain lengths may not be
   retuned after inspection.

A v2 pass would be new evidence under this frozen protocol only. It would not
make the v1 run a pass and would not by itself establish claims outside the
original fixed-`mu=0` benchmark scope.
