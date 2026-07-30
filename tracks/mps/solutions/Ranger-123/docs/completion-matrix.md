# Completion matrix

| Requirement | Evidence | Status |
|---|---|---|
| Reproducible Python/Julia package | `pyproject.toml`, `uv.lock`, pinned source in `julia/Project.toml` | Complete |
| \(N=2\) singlet dark sector | `tests/test_symmetry_n2.py` | Complete |
| \(N=2\) exact gaps and weights | `tests/test_spectra_n2.py`, `figures/n2_exact.*` | Complete |
| \(N=3\) \(6\oplus2\) reflection split | `tests/test_symmetry_n3.py` | Complete |
| \(N=3\) odd-sector \(J\)-independence | projected operator hashes and zero curve difference | Complete |
| \(N=3\) cat-gap coefficient | `tests/test_spectra_n3.py` | Complete |
| Closed Floquet solver | `tests/test_floquet.py` | Complete |
| Public uniform process-tensor backend | pinned UniformTEMPO revision, Julia runner | Complete |
| Extended-state multi-time insertions | Julia runner and backend tests | Complete |
| Delta/continuum separation | correlation and heat-current tests | Complete |
| Atomic, content-addressed cache | convergence/backend tests | Complete |
| Nested compression/timestep/phase controller | adaptive tests and per-point evidence | Complete |
| \(N=3\) even/odd heat grid | `figures/paper/n3_sector_heat.*`, audited local manifest | 6/6 converged |
| Odd-sector spectral invariance | relative maximum difference 0 | Complete |
| \(N=2\) exact-vs-Markov grid | `error_map_manifest.json` | 9/9 converged |
| Three Markov-error metrics | all nine cells | Complete |
| Floquet dark-channel diagnostics | \(|m|\le40\), Parseval tests | Complete diagnostic |
| Independent drive/bath normalization | model and projected-sector regression tests | Complete |
| Floquet transfer eigenvalues and residuals | Julia Krylov extraction plus real \(N=1\) smoke | Complete |
| Observable pole-residue fit and mode tracking | synthetic exact-recovery and matching tests | Complete |
| Fixed-frequency \(N=1,2,3\) coherent-destruction scan | `docs/heat-valve-result-zh.md`, hero figure | Complete |
| \(N=3\) pole-resolved heat-valve pilot | report, hero figure, and audited local manifest | 3/3 executed; claim gates rejected |
| Nine-point \(N=1,2,3\) heat-valve grid | go/no-go required threefold heat and residue suppression | Intentionally not run: pilot failed |
| Bounded normalization/counterterm variants | full adaptive evidence | 2/2 converged |
| Kac normalization/counterterm variants | passed compression evidence | Local endpoint complete; full timestep/phase requires cluster |
| Independent single-spin validation | `validation/uniform_tempo_single_spin.json` | Passed |
| Independent OQuPy cross-check | `validation/uniform_tempo_oqupy_crosscheck.json` | Diagnostic, not convergence |
| Publication PNG/PDF figures | `figures/paper` | Visually checked |
| Pole-resolved hero figure | `figures/heat-valve/heat_valve_hero.{png,pdf}` | Visually checked; labeled candidate/rejected |
| Chinese report | `docs/report-zh.md` | Complete |
| Heat-valve negative-result report | `docs/heat-valve-result-zh.md` | Complete |
| \(N=4\), continuum, critical exponent | Outside approved \(N=2,3\) scope | Not claimed |

## Final gates

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts/run_uniform_validation.py
.venv/bin/mypy src
.venv/bin/python -m floquet_if_manybody.cli audit results
.venv/bin/python -m floquet_if_manybody.cli paper-audit results/paper
```

`paper-audit` requires all six \(N=3\) points and all nine error-grid points to
be converged. It also requires both bounded model variants to be fully
converged. The two Kac variants are accepted only as an explicitly declared
timestep resource ceiling after a passed compression comparison; they are
never re-labeled as converged.

The additional command

```bash
.venv/bin/python -m floquet_if_manybody.cli \
  heat-valve-audit results/heat-valve
```

is expected to return nonzero for the archived pilot. This is a scientific
result, not a software failure: heat is not suppressed against both flanks,
the visible pole residue increases, the full nine-point grid was therefore
not authorized by the predeclared resource gate, and the figure is labeled
`candidate; claim gates not met`.
