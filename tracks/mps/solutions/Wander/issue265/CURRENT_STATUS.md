# Current Status and Evidence Ledger — 2026-07-30

## Status at a glance

```text
public-trajectory result: finite-window surrogate supported
confirmatory program:     convergence datasets are the active evidence gate
confirmation interval:     sealed
next scientific selection: scalar / independent two-Burgers / coupled two-mode / memory
```

The public result and confirmatory result have different scopes. The
single-trajectory pilot has completed its registered analysis and establishes
the finite-window Burgers benchmark. The confirmatory program measures how a
shared closure transfers across conditions and observables. Converged
Production-A data create the registered model-selection record.

## Scientific evidence completed

### Public Heisenberg trajectory

- Route B2 ingests the public high-temperature \(\Delta=1\) domain-wall data.
- Weak and strong forms recover \(a\simeq0.230\) and
  \(D_{\rm cl}\simeq1.97\), close to the published values.
- The closed-loop profile audit reports \(0.167\%\) integrated relative
  difference.
- The measured-window width and moment-diffusivity exponents are \(0.6802\)
  and \(0.3372\), respectively.
- The moment bridge gives \(A_W=0.741842\) and
  \(A_B/A_W=0.999154\), quantitatively identifying the finite-window tangent
  mechanism.
- Long deterministic continuation exposes the scalar PDE's rarefaction flow:
  its local width exponent moves from approximately \(0.665\) near
  \(t=200\) to approximately \(0.851\) at \(t=5000\).

### Analytical interpretation

- Microscopic magnetization continuity is exact.
- Spin flip fixes the parity of a physical one-field current and supplies the
  field-identification gate.
- Nonlinear stochastic averaging retains variance/covariance currents.
- The equal-coupling two-field flux diagonalizes algebraically into
  opposite-chirality Burgers modes \(u_\pm=m\pm\phi\).
- The moment identity connects fitted Burgers parameters to the wall's
  scale-dependent broadening and predicts rolling coefficient powers
  \((-1/3,+1/3)\) under the tangent interpretation.

### Synthetic calibration

- Constant-Burgers ground truth \((a,D)=(0.24,1.9)\) is recovered as
  \((0.239529,1.898051)\).
- Its instantaneous practical diffusivity variation is \(0.052\%\) in relative
  range and \(0.015\%\) in relative standard deviation.
- A \(D(t)\propto t^{1/3}\) control recovers
  \(\gamma=0.332998\pm1.67\times10^{-5}\), with a \(29.446\%\) relative
  range.

## Protocol and implementation completed

- Protocol v1.2, the condition matrix, decision thresholds, and all time
  splits were frozen before Production-A results.
- The base manifest contains 74 rows: 12 convergence, 31 Production A, and 31
  sealed Production B.
- Production-v2 contains 34 logical rows in each stage. Production A uses 32
  new executions and two fine-row reuse paths; Production B uses 34 new
  executions.
- The Production-v2 observable panel includes seven logical FCS rows in A and
  three in B, plus equilibrium and opposite-sign pulse responses.
- The scalar, independent two-Burgers, and coupled two-mode fitting and
  cross-validation paths are implemented.
- The stochastic
  [`solver budget`](results_research_program/two_mode/solver_budget.json) is
  frozen at 1,024 screening trajectories and at least 2,048 final
  trajectories, selected from solver-convergence targets ahead of quantum
  model scoring.
- The one-time confirmation guard and Production-B transaction controller are
  implemented. The committed snapshot is at the sealed pre-authorization
  stage.

## Backend validation completed

- Infinite-temperature purification TEBD is implemented with conserved
  \(S^z\), second-order evolution, and a backward disentangler.
- Magnetization, local/complete-cut current, connected \(C^{zz}\), and genuine
  two-measurement transfer FCS are recorded.
- Small-chain spin-flip agreement is within \(2\times10^{-15}\) of exact, and
  total magnetization is conserved within approximately \(10^{-14}\).
- The original lattice-continuity smoke test reaches agreement within
  \(4.17\times10^{-4}\).
- Dense \(L=6\) evolution agrees at \(10^{-9}\) or better for the original
  validation observables.
- An actual interrupted HDF5 run resumes bit-identically through the compared
  interval.
- The grouped two-physical-spin implementation includes all
  next-nearest-neighbour terms crossing the physical current cut.
- At \(J_2=0.1\), both wall orientations agree with dense evolution within
  \(8.3\times10^{-10}\).
- At \(J_2=0\), grouped and ordinary backends agree within
  \(1.0\times10^{-8}\), below the frozen \(2\times10^{-7}\) threshold.
- Cross-version continuation preserves the exact 1,001-point output grid,
  canonical job identity, and all stored arrays with zero difference.
- The source gate recognizes the two fully validated runner/backend pairs and
  carries successful attestations for all 12 registered convergence rows.

## SCNet execution evidence

### Convergence campaign

Twelve jobs were submitted for four representative conditions at coarse,
medium, and fine resolution:

```text
23009466  23009467  23009468  23009469
23009470  23009471  23009472  23009473
23009474  23009475  23009476  23009477
```

The archived launch audit records all twelve as started with initial
checkpoints and clean startup logs. Controller `23009668` was registered with
dependencies on the twelve jobs. It can continue checkpointed
scheduler-resource slices and then run the frozen convergence audit. Human
review handles terminal states outside that resource-continuation path.

This public document treats those scheduler observations as a dated archive.
The next scheduler refresh creates a new dated record. Final datasets and the
generated convergence summary are the evidence that advances Production A.

### \(J_2\) compute-node validation

The latest committed record
`results_research_program/hpc/j2_validation_20260730.json` has status `pass`:

- SCNet job `23015027` completed with exit code `0:0` in 48 seconds;
- exact \(J_2\) up/down, symmetry, FCS, grouped-equivalence, and checkpoint
  summaries all passed;
- source hashes match the registered backend and manifest;
- the base Production-A \(J_2\) gate rebuilt to 31 ready rows;
- the submission record remains at its prepared stage while the convergence
  gate produces its accepted-resolution artifact.

## Evidence gates that remain in sequence

1. **Convergence acceptance**
   - validate the four three-resolution condition groups;
   - require profile difference below \(0.002\) and width difference below
     \(0.003\);
   - choose the accepted resolution from numerical-consistency observables
     ahead of model scoring.
2. **Production A**
   - run the registered amplitudes, orientations, widths, shapes,
     backgrounds, controls, equilibrium, responses, currents, correlations,
     and FCS through \(t=200\);
   - materialize the two fine-data reuse attestations.
3. **Frozen selection**
   - fit on \(50\le t\le150\);
   - evaluate time, condition, and orientation holdouts on
     \(150<t\le200\);
   - use 2,000 paired 10-time-unit bootstrap blocks;
   - create a hash-bound scalar/two-mode selection record.
4. **One-time confirmation**
   - preview the exact action;
   - require explicit `--confirm-unblind` human authorization;
   - record evidence hashes, model identity, parameters, seeds, and time.
5. **Production B**
   - run the surviving registered forecast once on \(200<t\le400\);
   - report future-time prediction independently of model development.

The machine-readable contracts store adjacent endpoint pairs, while the
executable masks assign `t=150` to training and `t=200` to validation.  This
makes the three scoring sets disjoint.

## Decisive scientific readouts

The confirmatory program answers five concrete questions:

| Question | Decisive evidence |
|---|---|
| How stable are the public coefficients across numerical resolution? | medium-to-fine profile and width gates |
| How broadly do they transfer across trajectories? | leave-one-condition/orientation-out prediction and coefficient spread |
| How precisely do they follow the finite-window moment tangent? | rolling \(a,D_{\rm cl},A_W,A_B,W_*\) and future-time width flow |
| Which physical or chiral field carries the Burgers current? | spin-flip, amplitude/orientation law, current and pulse-response prediction |
| Which scalar or two-mode closure organizes the full hydrodynamics? | joint profile/current/correlation/FCS holdouts and sealed Production B |

## Claim boundary for the current PR

The present package supports the following reviewer-facing statement:

> The machine-learned deterministic Burgers equation is a quantitatively
> accurate, trajectory-conditioned finite-window closure for the public weak
> domain-wall profile.  Exact field symmetry, nonlinear stochastic averaging,
> deterministic rarefaction, and higher-order observables define the tests
> required to identify a transferable scalar or two-mode hydrodynamic law.
> Those tests are preregistered, implemented, numerically preflighted, and
> progressing through the convergence evidence gate.

For the full reasoning and primary literature, see
[`SCIENTIFIC_CASE.md`](SCIENTIFIC_CASE.md).  For the immutable scientific
contract, see
[`docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md`](docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md).
