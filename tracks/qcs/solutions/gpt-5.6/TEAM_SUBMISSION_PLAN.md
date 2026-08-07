# Challenge 113 team submission plan

Status: prepared for clean official sync; public packages remain independent.

## Directory layout

Copy the files listed in `team_submission_allowlist.txt` under the official
solution root:

```text
tracks/qcs/solutions/gpt-5.6/
├── core-sim-to-real/   # finite-shot synthetic CNOT confirmation
├── robustness/         # neutral-atom transfer/failure-boundary study
├── README.md
├── EVIDENCE_MATRIX.md
├── TEAM_SYNTHESIS.md
└── DEFENSE_OUTLINE_ZH.md
```

The two validated numerical directions are intentionally independent. Their
statistics, gates, dimensions, thresholds, and dependencies must not be
pooled.

## Environment isolation

- `core-sim-to-real/`: audited with Python 3.13, JAX 0.4.38, NumPy 2.2.6,
  SciPy 1.15.3.
- `robustness/comparison/`: audited with Python 3.12, JAX/JAXlib 0.11.0,
  NumPy 2.5.1, SciPy 1.18.0, Matplotlib 3.11.1.

Use a separate virtual environment for each package. Do not merge the two
requirements files.

## Team closure check

The pure-standard-library validator checks the explicit manifest, forbidden
files and paths, both evidence summaries, core source seals, final report
contract, and dependency separation:

```bash
python tools/validate_team_package.py
```

For an extracted candidate containing only allowlisted files:

```bash
python tools/validate_team_package.py --strict-closure
```

## Minimum numerical verification

Core:

```bash
python core-sim-to-real/code/attempt50_result_audit.py --verify-only
python core-sim-to-real/code/attempt51_queries_to_target.py --verify-only
python core-sim-to-real/code/attempt52_gap_invariant_audit.py --verify-only
python core-sim-to-real/run_challenge.py --mwe
python core-sim-to-real/tests/test_final_contract.py
```

Robustness baseline:

```bash
JAX_ENABLE_X64=true MPLCONFIGDIR=/tmp/hessian-loop-mpl python \
  robustness/comparison/code/hessian_loop_failure_map.py \
  --baseline-only --run-dir /tmp/ql1f-robustness-baseline
```

The archived full robustness result is read from
`robustness/comparison/summary.json`. A clean baseline and full rerun were
completed on 29 July 2026 and sealed in
`robustness/comparison/FRESH_RUN_SEAL.json`. Both package validators passed,
and the scientific comparator checked 3,951 numerical plus 402 categorical
values against the archived evidence with zero mismatches at
`rtol=1e-8`, `atol=1e-10`. A second full rerun is therefore not required
during official sync unless a sealed source or dependency file changes.
The allowlisted `fresh-run-evidence/` subset lets the root validator rerun
that comparison from a clean candidate without the numerical stack.

The team allowlist intentionally excludes `robustness/AGENTS.md` and the two
unused paper-reference screenshots `paper-fig1.png` and `paper-fig5.png`.
They are neither generated evidence nor required for reproduction.

The public `reproduce/` workspace is also excluded from the fallback
allowlist. Its merged Figures 1--4 package passed 28/28 isolated unit tests,
the Figure 1 MWE/full run, and the Figures 2--4 MWE, but the available evidence
is a partial theoretical reconstruction with synthetic interfaces rather than
a complete experimental reproduction. It also retains licensing, native
Windows, frozen-output, and Figure 1 validation-boundary work. These are
documented in `TEAM_REVIEW_PR2.md`; none blocks the default candidate.

The public `Cold_Atom Gate Simu_Platform/` workspace is likewise excluded from
the fallback allowlist. It is an independent Cs/Rb digital-twin and
experiment-facing engineering platform, not evidence for the frozen synthetic
CNOT or perfect-blockade CZ headline. It may be shown as future integration
infrastructure only with its own model and calibration boundaries intact.

## Claim firewall

- The robustness package is a deterministic/exploratory CZ failure study.
- The core package is a preregistered finite-shot synthetic CNOT confirmation.
- None is real hardware or cesium-specific evidence.
- Attempt 52 supports a conditional local endpoint/Hessian-rank invariant,
  not a universal rank or resource-scaling law.

## Sync safety

Use a clean worktree, copy only allowlisted files, and stage explicit paths.
Never edit, copy, or stage the protected upstream
`neural_schrodinger.ipynb`. The official PR is updated only after all package
checks and the rendered report pass.
