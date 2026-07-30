# Burgers Research Implementation and Evidence Status

**Snapshot date:** 2026-07-30

**Program phase:** convergence evidence collection

**Scientific destination:** transferable hydrodynamic field classification

## 1. Research deliverable

The package converts the Issue #265 question into an executable,
preregistered experiment. It preserves the machine-discovered Burgers fit as
the finite-window benchmark and tests its transfer across amplitudes,
orientations, initial shapes, backgrounds, observables, environments, and
future times.

The implementation supports four registered descriptions:

1. a shared scalar Burgers closure;
2. independent opposite-chirality Burgers modes;
3. a coupled stochastic two-mode open system;
4. a memory or additional-mode extension.

Every destination corresponds to a positive scientific classification and a
specific evidence pattern.

## 2. Completed implementation

| Component | State | Evidence |
|---|---|---|
| public profile analysis | ready | coefficients, profile difference, width and moment exponents |
| moment bridge | ready | \(A_W=0.741842\), \(A_B/A_W=0.999154\) |
| scalar weak/strong fitting | ready | synthetic and public-data recovery |
| two-mode deterministic fit | ready | chiral and coupled parameterizations |
| stochastic solver budget | frozen | 1,024 screening and at least 2,048 final trajectories |
| condition matrix | frozen | amplitudes, signs, widths, shapes, backgrounds, controls |
| observable panel | frozen | profiles, currents, responses, correlations, FCS |
| time splits | frozen | train, validation, sealed confirmation |
| convergence controller | ready | three-resolution audit and continuation |
| one-time confirmation controller | ready | hash-bound preview, authorization, and record |
| Production-B controller | ready | transaction record and registered forecast |
| automated checks | ready | 170 tests |

## 3. Quantum backend

The TeNPy backend implements infinite-temperature purification with conserved
\(S^z\), second-order real-time evolution, and backward ancilla evolution. It
records:

- local magnetization;
- local and complete-cut physical current;
- connected \(C^{zz}\);
- two-measurement transfer full counting statistics;
- truncation, norm, energy, and checkpoint metadata.

Dense small-chain comparisons establish the backend quantitatively:

- spin-flip agreement within \(2\times10^{-15}\) of exact;
- total magnetization conservation within \(10^{-14}\);
- lattice-continuity agreement within \(4.17\times10^{-4}\);
- dense \(L=6\) observable agreement at \(10^{-9}\) scale or finer;
- grouped \(J_2=0.1\) wall-orientation agreement within
  \(8.3\times10^{-10}\);
- grouped and ordinary \(J_2=0\) agreement within \(1.0\times10^{-8}\);
- checkpoint continuation reproducing the compared arrays bit for bit;
- exact preservation of the registered 1,001-point output grid.

The source-attestation layer binds each dataset to the validated runner,
backend, configuration, and manifest hashes.

## 4. Registered data program

The base manifest contains 74 rows:

- 12 three-resolution convergence runs;
- 31 Production-A runs through \(t=200\);
- 31 sealed Production-B forecasts through \(t=400\).

Production-v2 contains 34 logical rows per production stage and expands the
joint-observable coverage. Production A uses 32 fresh executions plus two
attested fine-data reuse paths. Production B uses 34 fresh executions.

The scientific matrix includes:

- \(\mu=0.02,0.05,0.10,0.20\) with both wall orientations;
- tanh widths \(1,2,4,8\);
- erf, double-wall, Gaussian, and sinusoidal shapes;
- backgrounds \(m_0=\pm0.05\);
- equilibrium and opposite-sign local pulses;
- \(\Delta=0.8\), \(\Delta=1.2\), and
  \(\Delta=1,J_2=0.1\) environment controls;
- current, connected response, correlation, and FCS observables.

## 5. Time and evidence partition

The executable masks define three disjoint scoring intervals:

```text
training:             50 <= t <= 150
validation:          150 <  t <= 200
sealed confirmation: 200 <  t <= 400
```

The training interval estimates parameters. The validation interval selects
the registered model family using time, condition, and orientation holdouts.
The sealed interval evaluates one hash-bound forecast after explicit human
authorization.

## 6. SCNet evidence

### Convergence campaign

Twelve convergence jobs were launched on SCNet:

```text
23009466  23009467  23009468  23009469
23009470  23009471  23009472  23009473
23009474  23009475  23009476  23009477
```

The archived launch record shows initial checkpoints for all twelve tasks and
clean startup logs. Controller `23009668` links the three-resolution groups,
continues resource-limited slices from checkpoints, and produces the frozen
convergence summary.

The accepted resolution is chosen from profile and width consistency:

\[
\delta_{L^2}<0.002,
\qquad
\delta_W<0.003.
\]

The resulting convergence artifact is the entry record for Production A.

### \(J_2\) compute-node qualification

Committed record
`results_research_program/hpc/j2_validation_20260730.json` carries the
successful qualification:

- job `23015027` completed with exit code `0:0` in 48 seconds;
- exact \(J_2\) orientation, symmetry, FCS, grouped-equivalence, and
  checkpoint checks reached their registered thresholds;
- source hashes match the registered code and manifest;
- all 31 base Production-A rows carry a ready source qualification.

This qualification and the convergence summary are complementary gates. The
first certifies the implementation; the second selects the production
resolution.

## 7. Frozen model selection

The same held-out folds compare the scalar, independent chiral, and coupled
two-mode descriptions. Two-mode selection requires:

- at least \(30\%\) held-out improvement over the leading scalar model;
- a positive paired-bootstrap \(95\%\) lower endpoint;
- exact spin-flip and orientation checks;
- one shared parameter set for profiles, currents, responses, and FCS.

The coupled model additionally requires at least \(10\%\) improvement over
the independent two-mode manifold and \(\Delta\mathrm{BIC}\ge10\).

The bootstrap uses 2,000 paired blocks of 10 time units. Selection records
bind the dataset hashes, model identity, parameters, random seeds, software
hashes, and timestamps.

## 8. Next execution sequence

1. Materialize the twelve final convergence datasets and their summary.
2. Select the accepted resolution through the frozen profile and width gates.
3. Launch Production A across the registered matrix through \(t=200\).
4. Fit on \(50\le t\le150\) and score all registered holdouts on
   \(150<t\le200\).
5. Create the hash-bound model-selection record.
6. Preview the one-time confirmation transaction.
7. Apply explicit human authorization and launch the surviving forecast on
   \(200<t\le400\).
8. Publish the future-time prediction score together with the field identity,
   coefficient-transfer law, and higher-observable comparison.

## 9. Completion criterion

The research task reaches its decisive result when a converged quantum dataset
has passed the registered train, validation, and sealed future-time stages.
The final paper can then state which field carries the Burgers structure, the
time and condition range of transfer, and the observable panel organized by
the selected hydrodynamic description.
