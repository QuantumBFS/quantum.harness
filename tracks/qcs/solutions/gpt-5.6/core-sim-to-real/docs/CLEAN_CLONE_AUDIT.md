# Attempt 50 clean-clone audit

Date: 2026-07-29

## Audited source

- Repository: `thy10817/Sim-to-real-simulation`
- Detached commit:
  `1f66292b1646fc3bfe2598dbe6e297e54d349f48`
- Clone location: a fresh directory under the WSL user's home; no files or
  virtual environment from the development checkout were reused.

## Fresh environment

The host's current `/usr/bin/python3` was Python 3.14 without `ensurepip`, so
the isolated audited environment was created with `uv` and CPython 3.13.14:

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python \
  -r core-sim-to-real/requirements.txt
```

Installed numerical versions matched the pinned contract:

```text
jax==0.4.38
jaxlib==0.4.38
matplotlib==3.11.1
numpy==2.2.6
scipy==1.15.3
```

## Acceptance results

| Check | Result |
|---|---|
| Python compilation of entry point, audit, builder, and tests | PASS |
| Simulator-free Attempt-50 result audit | PASS, 18/18 |
| `run_challenge.py --mwe` | PASS, 7/7 |
| MWE run count and complete ledgers | PASS, 3 runs and 66/166/166 rows |
| `run_challenge.py --full` | PASS, 15/15 |
| Full replay grid | PASS, 288/288 without exception |
| Archived Attempt-49 summary exact match | PASS |
| Generated outputs remain ignored | PASS |
| Git status after both run modes | clean |

The full replay is public-seed reproducibility evidence. It is not counted as
a second independent fresh confirmation.

## Minimal submission closure

A separate 37-file candidate archive was built from public commit `925e2d3a`
using only the runtime, audit, final-report, and provenance dependencies later
listed in `submission_allowlist.txt`. Without access to any other public-repo
files, it passed:

- final artifact tests: 5/5;
- simulator-free audit: 18/18;
- MWE: 7/7; and
- full public replay: 15/15, 288/288 runs, exact archived summary match.

This establishes that the formal confirmation runtime does not depend on the
historical development tree. A later deliverable audit intentionally adds a
small sealed subset of Attempts 25–34 as mechanism provenance.

## Expanded final allowlist

After the official-Issue compliance audit added the simulator-free
queries-to-target deliverable, a new 45-entry package was archived from public
commit `c54f334`, extracted outside the repository, and tested with a fresh
CPython 3.13.14 `uv` environment. It passed:

- Python compilation of all final entry points;
- Attempt-50 result audit: 18/18;
- Attempt-51 queries-to-target audit: 11/11;
- final artifact contract: 6/6;
- MWE: 7/7; and
- full public replay: 15/15, 288/288 runs, exact archived summary match.

The expanded package contained no files outside
`submission_allowlist.txt`.

## Failure/invariant and team-package closure

A 61-entry core candidate was archived from public commit `2f1b987`, extracted
outside the repository, and tested without access to the remaining history.
It passed:

- Python compilation;
- Attempt-50 result audit: 18/18;
- Attempt-51 queries-to-target audit: 11/11;
- Attempt-52 failure/invariant audit: 22/22;
- final artifact contract: 7/7 with three embedded figures;
- MWE: 7/7 with complete 66/166/166 ledgers; and
- full public replay: 15/15, 288/288 runs, exact archived summary match.

The original corresponding 111-entry team candidate contained exactly 111
files, no `neural_schrodinger.ipynb`, and no personal absolute path. The
later 112-entry closure added the standard-library team validator, which
checks the same closure automatically. The current 109-entry fallback closure also
includes the robustness validator, scientific comparator, provenance record,
fresh-run seal, and the small fresh scientific evidence subset required to
rerun that comparison. In separate clean Python-3.12 environments:

- the Liu-et-al. reconstruction MWE returned rank 5, reduced/full difference
  `4.93e-13`, and principal-curvature relative error `6.43e-5`; and
- the robustness baseline-only run completed on CPU/x64 with baseline
  infidelity `6.600e-6`, active rank 5, and `accepted=True`.

The fresh robustness full run also completed all 240 core, 100 noise, 6
pathology, and 10 Hamiltonian-error trials. Comparison against the archived
tables passed for 3,951 numerical and 402 categorical values with zero
mismatches. A 116-entry strict candidate built from public commit `b5cac3c`
passed all 23 team checks; its archive SHA-256 is
`3B6D9614E036166ADC07ADF595E2B0C94982EE4238D1E0CED85DEAED255F3821`.

The robustness working notes, optional paper workspace, and two unused
paper-reference screenshots are excluded from
`team_submission_allowlist.txt`. The two validated numerical packages retain
separate requirements and are not statistically pooled.

The first strict team-candidate validator run also caught that
`final/run.json` labeled the formal JSON seal as a binary hash. Windows CRLF
and Git-archive LF bytes then differed despite identical canonical text. The
final builder and contract test now use a canonical UTF-8/LF SHA-256 for this
text artifact; no formal result or scientific number was changed.

## Non-blocking host messages

WSL printed the known warnings about a Windows localhost proxy and
untranslatable `F:\` `PATH` entries. Git access, dependency installation,
CPU/x64 JAX execution, the MWE, and the full replay all completed, so these
messages are not package failures.
