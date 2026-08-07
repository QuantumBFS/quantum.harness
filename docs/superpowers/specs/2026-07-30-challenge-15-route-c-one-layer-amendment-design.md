# Challenge #15 Route C One-Layer Amendment Design

> Status: approved direction, written-spec review pending
>
> Date: 2026-07-30
>
> Attempt: `scalable-v1-s02c-a02`
>
> Parent attempt: `scalable-v1-s02c-a01` at
> `7eb2825f79ca35476272e72d3b8e9c42c68f908e`

## 1. Decision

Route C keeps the Challenge-compliant physical shape introduced in a01:

- genuine JK/Girvin--Jach projected `L=0` and reduced `L=2` CF seeds;
- one reduced `L=2` object generating all five `M=-2,...,2` states;
- exact electronic-LLL projected-density scalars `S_ell` with
  `ell in {2,3,4}`;
- one shared neural descriptor trunk for `L=0` and `L=2`, with only scalar
  sector heads allowed;
- no ED, direct/full-basis, JK1/JKk, GMP, coordinate-backflow, stochastic
  amplitude, or coefficient-only CF fallback in the candidate path.

The only capacity change is

```text
operator_layers: 2 -> 1
density_ranks:    [2, 3, 4]  (unchanged)
hidden_width:     64         (unchanged)
```

so that the candidate becomes

```text
Psi_theta^(LM) =
    [I + sum_{ell=2,3,4} a_theta,ell^(L) S_ell]
    Psi_seed^(LM).
```

Physics, training seeds, optimizer updates, sample budgets, thresholds,
oracle-isolation rules, and resource ceilings do not change. The protocol
byte change creates a new SHA-256 and a new common comparison-base commit.

## 2. Why one layer is a bounded amendment

Attempt a01 established that depth two requires exact mixed JK-seed
derivatives through order eight. The available exact backends exceeded the
frozen workload before training: the contracted derivative envelopes contained
`9,969` terms at `N=6` and `34,113` at `N=8`, while exact interpolation required
about `983,040` and `16,397,920` seed evaluations per configuration.

One layer needs only the three quantities

```text
S_2 Psi_seed, S_3 Psi_seed, S_4 Psi_seed,
```

and therefore derivatives through rank four on each active particle pair. The
estimated shared derivative envelopes fall to `265` terms at `N=6` and `481`
at `N=8`. This reduction makes exact correctness and resource feasibility
decidable before model or VMC work begins.

The amendment does not by itself establish Challenge compliance. It only
reopens a bounded implementation attempt. The route must still pass the
complete frozen construction, symmetry, VMC, reproducibility, resource,
oracle-isolation, N=8 smoke, and post-freeze ED gates.

## 3. Exact-action approaches considered

### 3.1 Recommended: JK-specific contracted rank-4 jet

Use the exact pair-Casimir identity

```text
S_ell = c_ell N I + sum_{i<j} p_ell(J_i dot J_j),
```

where `p_ell` is the degree-`ell` Racah polynomial fixed by `Q` and the
projected-density normalization. For a spinor polynomial,

```text
J_z = (u d/du - v d/dv) / 2,
J_+ = u d/dv,
J_- = v d/du,
J_i dot J_j = J_zi J_zj + (J_+i J_-j + J_-i J_+j) / 2.
```

The backend compiles `p_ell(J_i dot J_j)` into a finite Weyl-operator stencil
and contracts it against a truncated derivative jet of the existing raw JK
polynomial. Only the active pair's four spinor variables are lifted. The
per-particle derivative degree is capped at four and all arithmetic remains
`complex128`.

The raw seed is division-free. Its pair factors, Jastrow derivatives,
projected orbitals, and determinant are lifted into the jet algebra. The
determinant uses a division-free recurrence rather than inverse-matrix
derivatives, so a zero or small constant-term pivot cannot silently corrupt a
probe near a node.

This is the production candidate because it computes an exact point value,
supports deterministic amplitude ratios, and has a fixed derivative envelope
at the approved ranks.

### 3.2 Reference only: nested JAX JVP

Automatic directional derivatives provide a compact small-`N` reference.
They are retained only for correctness probes because a01 showed unacceptable
tracing/execution constants at depth two. They cannot be selected as the
production backend unless the same frozen N=6/N=8 microbenchmark independently
passes.

### 3.3 Reference only: pair-Casimir spectral interpolation

Exact interpolation supplies a second implementation-independent reference on
small fixtures. It is not a production fallback: if its number of seed
evaluations fails the frozen microbenchmark, it remains test-only rather than
weakening the resource gate.

## 4. Component boundaries

The implementation is split into the following route-local units:

- `pair_casimir.py`: derive and cache `c_ell` and `p_ell` from one- and
  two-particle fixed-LLL tensor algebra; it never constructs an `N`-electron
  basis.
- `jets.py`: immutable sparse/truncated `complex128` multi-index arithmetic
  and a division-free determinant over the jet ring.
- `coordinate_action.py`: lift the existing JK seed, compile the pair Weyl
  stencils, evaluate all three `S_ell Psi`, and expose the
  `connected_scalar_action`/pointwise-action contract.
- `microbenchmark.py`: exactness, wall-time, memory, and projected-workload
  measurement for N=6 batch 512 and N=8 batch 256.
- `model.py`: shared descriptor MLP, sector heads, identity initialization,
  and the one-layer pointwise amplitude.
- existing `sampler.py`, `adapter.py`, and `train.py` plan boundaries remain
  unchanged and may start only after the action microbenchmark passes.

Production modules may import `projected_density.py`, `scalar_operators.py`,
`seeds.py`, and the common scalable-v1 contracts. They may not import any
`benchmark_v0` ED/full-basis module or read any benchmark result path.

## 5. Data flow

For each coordinate batch and sector:

1. validate normalized spinors using the existing `JKCFSeedFamily` contract;
2. evaluate the raw JK seed and the exact rank-4 pair jets;
3. contract the precomputed `p_ell(J_i dot J_j)` stencils to obtain
   `S_2 Psi`, `S_3 Psi`, and `S_4 Psi`;
4. evaluate the shared descriptor trunk once for descriptors `(1,2)`, `(1,3)`,
   `(1,4)`;
5. apply the `L=0` or `L=2` scalar head; all five `L=2` components use the
   same coefficients;
6. return the stable dressed point value and log amplitude without converting
   to a full occupation basis.

The operator action is independent of neural parameters, so VMC gradients
differentiate only the shared trunk and scalar heads. This avoids differentiating
through the jet engine while preserving the exact primal wavefunction.

## 6. Nontrivial-dressing boundary

The route must not claim success merely because the MLP has positive parameter
count. Before training/freeze, route tests must establish all of the following:

- `S_ell Psi_seed` is not globally proportional to `Psi_seed` on independent
  non-node probes for at least one approved `ell` in each sector;
- the pointwise ratio matrix of
  `{Psi_seed, S_2 Psi_seed, S_3 Psi_seed, S_4 Psi_seed}` has rank greater than
  one, certified by `sigma_2 / sigma_1 >= 1e-8` on the probe matrix;
- changing a scalar head coefficient changes amplitude ratios, not only a
  global normalization;
- the final checkpoint is rejected if
  `max_ell(abs(a_theta,ell^(L))) <= 1e-8` in either sector;
- the implementation evaluates operator action per configuration and does not
  precompute an ED-sized or fixed CF diagonalization basis.

This remains a finite one-layer operator span. The report will describe it
exactly as such, not as an unlimited coordinate neural ansatz. If the Challenge
review contract classifies every finite operator span as coefficient-only even
when it is generated by exact LLL operators outside the input CF basis, Route C
is ineligible and must be reported as a gate-specific failure rather than
relabelled as compliant.

## 7. Microbenchmark gate

Model, sampler, adapter, and training work are blocked until the exact-action
backend passes these checks:

### Correctness

- pair-Casimir coefficients reconstruct the direct two-particle scalar matrices
  for `2Q=3,9,15,21` and `ell=2,3,4` with relative residual at most `1e-10`;
- the contracted jet agrees with two independent small-`N` references at
  non-node probes with relative residual at most `1e-10`;
- raw and log-scaled paths agree away from nodes;
- local spinor gauge, exchange, finite rotation, and `L=2` ladder residuals do
  not regress from the existing seed/operator tolerances;
- AST/import audit confirms no ED/full-basis production dependency.

### Resources

- measure N=6 batch 512 and N=8 batch 256 using two warmups and five measured
  repetitions, matching the protocol smoke shape;
- record median and worst wall time, peak RSS, backend/dtype, and device
  fingerprint;
- project one training seed as
  `2 sectors * 2048 updates * measured N=6 batch action time`;
- the projected action time for each independently launched training seed may
  consume at most half of the selected placement wall ceiling, leaving the
  other half for proposals, local energy, optimizer, logging, and checkpointing;
- measured peak RSS must be at most 75 percent of the selected placement
  ceiling, reserving 25 percent for optimizer, sampler, and checkpoint state;
- an actual N=8 batch must complete; an asymptotic estimate alone is not a
  smoke pass.

If no currently available placement passes, a02 closes `inconclusive` or
`failed` with the microbenchmark artifact. It does not start training or change
the frozen budgets.

## 8. Error handling

- Invalid flux, rank, batch shape, dtype, non-finite coordinate, or
  non-normalized spinor fails before jet construction.
- A non-finite jet coefficient, determinant, dressed amplitude, or ratio raises
  `CoordinateActionNumericalError`; it never becomes a zero residual or
  accepted sample.
- Exact nodes are represented explicitly. Log amplitude returns negative
  infinity only when the raw exact amplitude is zero; near-node finite values
  use scaling and cannot be rounded to a false node.
- Microbenchmark output is written atomically and contains the source commit,
  protocol SHA-256, command, device fingerprint, and all measured repetitions.
- Any correctness mismatch blocks the resource classification, because a fast
  incorrect action is not a candidate.

## 9. Protocol and attempt lifecycle

The common amendment commit will:

1. change only `cf_operator_nqs.operator_layers` from `2` to `1` in
   `protocol.json`;
2. add loader validation that rejects a Route C mapping other than the approved
   one-layer/ranks/width tuple;
3. update the common design and protocol tests;
4. record the old and new protocol SHA-256 values and the amendment commit SHA
   in the a02 journal and scalable-v1 index.

No Task 4/5 route implementation begins from the old two-layer protocol hash.
No other route capacity, physics field, threshold, seed, sample budget, or
resource ceiling may change in the same amendment.

Attempt a02 may end in only one of these states:

- `route-frozen`: one-layer candidate trained, frozen, audited, and all
  pre-reveal gates including N=8 smoke pass;
- `failed`: a named correctness/resource/Challenge-eligibility gate is false;
- `inconclusive`: the exact gate could not be decided inside the attempt
  boundary without changing the protocol.

It cannot declare `route-stopped`; attempts a03 through a05 remain unless a
later terminal five-attempt report is reached. ED reveal remains blocked by the
common synchronization barrier.
