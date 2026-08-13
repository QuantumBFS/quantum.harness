# Remote continuation checkpoint — 2026-07-30

## State

Continuation started from `REMOTE_SEARCH_CHECKPOINT_2026-07-29.md`.  The
saved WSL and CPU SHA-256 values matched exactly, neither remote search
process was live, and the completed searches were not repeated.

The shared branch is:

```text
work/zibo/representation-cones
```

The production-packaging commit is:

```text
0527038e003bc7c5b0e2f43ef888a9f0feee7c80
```

Read-only `ls-remote` verification returned that same SHA for
`shared/work/zibo/representation-cones`.

## Completed in this continuation

`cell-4321` is now frozen as a source-controlled, one-command exact
certificate:

```text
protocols/oddcycle-robust-candidate-v1/frozen-certificate.json
oracle/oddcycle_robust_certificate.py
tests/test_oddcycle_robust_certificate.py
```

The verifier reconstructs and checks:

- four exact split-inertia gates;
- all 16 exact path-metric Stein gaps;
- coherent exact time orientation;
- exact dual cancellation and trace-one normalization;
- all four exact positive-definite dual multipliers;
- the exact 32-dimensional positive-field Hermitian transfer;
- real logarithms for all four nonidentity letters; and
- the 58-entry non-Gaussian grade-two mismatch.

The TDD cycle and the focused six-file regression ran on WSL before the
source commit.  The final recorded regression result was `47 passed in
1.54s`.  The earlier two pending checkpoint runners separately returned
`85 passed in 12.22s`.

The paper draft and challenge audit now compare the original alphabet with
`cell-4321`.  The decision is frozen:

- keep `(1/1000,4/5,q=r=1)` as the main theorem because it has simpler exact
  constants and larger primal and physical margins;
- use `cell-4321` as an independent exact robustness result because its
  floating dual minimum eigenvalue is about three orders of magnitude
  larger;
- do not broaden the claim to exclude common nonquadratic cones or the full
  Wei/Majorana framework.

## Packaging defects found and fixed

The first verifier implementation counted only the two base matrices in the
real-log summary.  It now records both matrices and both transposes.

The normalized grade-two mismatch initially divided the raw identity by
`41` rather than `41^2`.  The corrected first normalized mismatch is
`4/41`.  These were verifier-summary defects, not failed scientific gates.

## Current infrastructure boundary

After the source commit was pushed, the current Codex Windows execution
context returned "Windows Subsystem for Linux has no installed
distributions" for both ordinary and elevated `wsl.exe` calls.  Therefore a
fresh clean-worktree replay at exact commit `0527038` and the tracked
`result.json` were not fabricated or run on local Windows.

This is the only incomplete step in the robust-certificate packaging.  It
does not invalidate the earlier WSL regression, but that regression
preceded the final source commit and is not represented as a clean
submission-commit replay.

## Non-repetition boundary

Do not rerun:

- the 12,325-cell oddcycle frontier;
- the 6,266-survivor dual ranking;
- the top-five exact dual promotion;
- either `cell-4321` discovery/promotion solver;
- the completed long-word or Hodge enumerations.

The 1,964 dual `SolverError` cells remain inconclusive and unretired.  No
secondary-solver retry or adaptive TP-boundary scan was started in this
continuation.

## Exact resume commands

Once the existing WSL distribution is visible again, create a new clean
worktree rather than modifying or deleting the preserved dirty verification
clone:

```bash
cd /home/zibojin/code/nnv-final-verify
git fetch shared work/zibo/representation-cones
git worktree add \
  /home/zibojin/code/nnv-robust-verify-0527038 \
  0527038e003bc7c5b0e2f43ef888a9f0feee7c80
cd /home/zibojin/code/nnv-robust-verify-0527038/tracks/qmc/solutions/no-negative-vibes
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
  /home/zibojin/miniforge3/envs/quantum_harness/bin/python -m pytest -q \
  tests/test_oddcycle_robust_certificate.py \
  tests/test_oddcycle_final_certificate.py \
  tests/test_oddcycle_path_metric.py \
  tests/test_oddcycle_metric_dual.py \
  tests/test_oddcycle_pair_physical.py \
  tests/test_oddcycle_pair_domain_runner.py
env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0 \
  /home/zibojin/miniforge3/envs/quantum_harness/bin/python \
  -m oracle.oddcycle_robust_certificate \
  > /home/zibojin/code/oddcycle-robust-result-0527038.json
sha256sum /home/zibojin/code/oddcycle-robust-result-0527038.json
```

Verify that the JSON reports source commit
`0527038e003bc7c5b0e2f43ef888a9f0feee7c80`, copy it to
`protocols/oddcycle-robust-candidate-v1/result.json`, record its SHA-256 in
the experiment log, and commit and push that archival artifact.  Then move
to the next research decision without repeating any completed scan.

## Later theory continuation

While the WSL distribution remained invisible, the publication-critical
Majorana/Wei audit advanced without local scientific computation or a new
scan.

Primary-source review and an exact proof design are committed in:

```text
3ac8509bd4f3c07588c1e926e5af7eaa26e54197
4f60575c7356426e216092a26330d6980afa268e
```

The second commit corrects the Nambu adjoint convention after a manual
pressure audit.  For \(\Psi=(c,c^\dagger)\), use

\[
G(B)=\operatorname{diag}(B^{-1},B^{\mathsf T}),
\]

not \(\operatorname{diag}(B,B^{-\mathsf T})\).

The exact no-go design and TDD execution plan are:

```text
docs/superpowers/specs/2026-07-30-oddcycle-majorana-wei-no-go-design.md
docs/superpowers/plans/2026-07-30-oddcycle-majorana-wei-no-go.md
```

The proposed proof pulls any fixed-complex-basis Wei metric into Nambu
space, uses the frozen positive-definite dual to force all nonstrict gaps to
the group boundary, proves the four-letter commutant is scalar, and obtains
the only possible boundary form

\[
\eta=\begin{pmatrix}0&kI_5\\\bar kI_5&0\end{pmatrix}.
\]

That form gives
\(\eta\Omega^{-1}\eta^{\mathsf T}=|k|^2\Omega\), whereas a pulled-back
orthogonal skew Majorana structure requires
\(\eta\Omega^{-1}\eta^{\mathsf T}=-\Omega\).

This remains a theorem draft until the no-solver exact replay in the plan
passes on WSL.  Do not upgrade the paper abstract before that GREEN gate.
The replay is now the first research task when WSL returns, followed by the
previously pending robust `result.json`.  It supersedes any nonconvex search
over \(O,J_1,J_2\), but does not authorize or repeat a frontier scan.
