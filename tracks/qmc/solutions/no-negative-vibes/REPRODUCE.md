# Reproducing the No Negative Vibes submission

## Environment

The recorded reference environment is WSL2 Linux x86_64 with Python 3.13.12,
NumPy 2.4.4, SciPy 1.18.0, SymPy 1.14.0, mpmath 1.3.0, pytest 9.1.1,
pandas 3.0.2, and matplotlib 3.10.8. Python 3.11+ with current compatible
versions is expected to work.

```bash
python -m venv .venv-nnv
source .venv-nnv/bin/activate
python -m pip install numpy scipy sympy mpmath pytest pandas matplotlib
cd tracks/qmc/solutions/no-negative-vibes
export PYTHONPATH="$PWD"
```

## One-command exact publication replay

```bash
python -m oracle.oddcycle_final_certificate
```

This replays the exact path-metric theorem, exact no-common-metric separation,
exact interacting transfer, and exact Majorana/Wei novelty audit. It prints a
JSON summary with the Git state and a digest of the exact payload.

Focused regression:

```bash
pytest -q \
  tests/test_oddcycle_path_metric.py \
  tests/test_oddcycle_metric_dual.py \
  tests/test_oddcycle_pair_physical.py \
  tests/test_oddcycle_majorana_wei_audit.py \
  tests/test_oddcycle_final_certificate.py
```

## Exact negative controls and broad mechanism tests

```bash
pytest -q \
  tests/test_exact_fixtures.py \
  tests/test_families.py \
  tests/test_az_families.py \
  tests/test_majorana_exact.py \
  tests/test_frontier_candidates.py \
  tests/test_speculative_candidates.py
```

## Teammate branch constructions and reductions

```bash
pytest -q \
  tests/test_fock_cp.py \
  tests/test_fock_cp_screen.py \
  tests/test_tensor_square.py \
  tests/test_tensor_square_effective.py \
  tests/test_gauge_cocycle.py \
  tests/test_grade_charge_model.py \
  tests/test_odd_block_tn_stoquastic.py \
  tests/test_orthogonal_contraction_candidate.py \
  tests/test_orthogonal_contraction_exclusion.py
```

## Orthogonal-contraction QNC candidate

```bash
pytest -q \
  tests/test_orthogonal_contraction_physics.py \
  tests/test_orthogonal_contraction_lattice.py \
  tests/test_orthogonal_contraction_exclusion.py \
  tests/test_orthogonal_contraction_candidate.py \
  tests/test_revival_no_go.py \
  tests/test_odd_block_tn_stoquastic.py
```

This replays arbitrary-depth orthogonal-word positivity, overlapping-plaquette
locality and sign frustration, common-orbital and generalized-JW exclusions,
the doubled-Majorana identity, the six-mode `so(6)`/sector-algebra audit, and
4/6/8-mode Hodge-resolved ED/Wick diagnostics. The result is a strong QNC
candidate boundary, not a general classical-hardness proof.

## Tensor-square phase program

```bash
cd tensor-square-phase-diagram
python -m pip install -e .
pytest -q
```

The committed scientific closeout is
[tensor-square-phase-diagram/STATUS.md](tensor-square-phase-diagram/STATUS.md).
Generated CSV/JSON/PNG/PDF artifacts are stored outside Git at
`tracks/qmc/results/no-negative-vibes/tensor-square-phase-diagram/`.

## Survivor A exact transfer

```bash
pytest -q \
  tests/test_oddcycle_survivor_a.py::test_loader_binds_survivor_a_to_its_frozen_source \
  tests/test_oddcycle_survivor_a.py::test_reconstruction_replays_the_exact_spd_transfer
```

The two high-precision Hamiltonian-analysis specifications in that module are
marked expected-failure until `analyze_hamiltonian` is implemented. They are
not evidence for the present submission.

## Protocols, seeds, and generated output

- Frozen protocols and seed axes:
  `tracks/qmc/solutions/no-negative-vibes/protocols/`
- Exact and compact fixtures:
  `tracks/qmc/solutions/no-negative-vibes/fixtures/`
- Oracle and replay code:
  `tracks/qmc/solutions/no-negative-vibes/oracle/`
- Large cells and generated reports:
  `tracks/qmc/results/no-negative-vibes/` (ignored by Git)

Each protocol directory records the applicable axes, settings, provenance,
result summary, or checkpoint. See
[CHALLENGE_REPORT.md](CHALLENGE_REPORT.md) for the evidence-grade table and
links to route-specific reproduction details.

## Regenerate the offline challenge report

From the repository root:

```bash
python skills/report/render_report.py \
  tracks/qmc/results/no-negative-vibes/submission-20260730
```

This consumes the ignored `report.json` and writes a self-contained
`report.html`. The tracked Markdown report is the stable PR-facing copy.
