# Issue 119 OLE G2 runner

This directory contains the reproducible BP-TN path for the 49-qubit,
648-entangler operator Loschmidt echo baseline. It delegates state evolution,
belief propagation, simple-update SVD truncation, and expectation values to
TensorNetworkQuantumSimulator.jl 0.4.4 at commit `b5d4089`.

From this directory:

```bash
julia --project=. -e 'using Pkg; Pkg.instantiate()'
julia --project=. scripts/fetch_inputs.jl
julia --project=. scripts/validate_small.jl
python3 tests/test_array_entrypoint.py
```

Inspect an exact run setup without starting the 49-qubit calculation:

```bash
julia --project=. scripts/run_bp.jl --seed 1 --chi 64 --delta 0.15
julia --project=. scripts/run_bp.jl --seed 1 --chi 64 --delta 0
```

The dry run prints a token that hashes the full setup. Only after the setup and
resource choice have been ratified should a calculation be started:

```bash
julia --project=. scripts/run_bp.jl \
  --seed 1 --chi 64 --delta 0.15 \
  --execute --confirm TOKEN_FROM_DRY_RUN
```

Each seed writes a TOML result under `runs/`, including all 73 layer records,
truncation errors, a one-sweep BP fixed-point residual, norm defects, wall
time, and peak RSS. A `.partial` file is updated after every layer so an
interrupted long run remains diagnosable.

After at least two seeds have completed:

```bash
julia --project=. scripts/analyze.jl \
  runs/baseline-49x648/delta-0p15/chi-512/summary.toml \
  0.821658489 \
  runs/baseline-49x648/delta-0p15/chi-512/seed-*.toml
```

The analyzer applies the G2 criterion
`|mean − 0.821658489| ≤ max(0.002, 3 SE)`.

The completed 20-seed reproduction, paired χ comparison, and measured Slurm
resources are recorded in `G2_RESULTS.md`. Cluster-array cells are selected
from a generic run specification by `scripts/run_bp_array_cell.py`; it calls
this same audited runner rather than reimplementing the tensor-network
calculation.

## Active 49×1296 feasibility gate

The G5 active configuration keeps the baseline observable, seed namespace,
dtype, cutoff, normalization, and BP rules unchanged. It switches only to the
audited L=6 Tracker circuit and an active-only output directory.

```bash
julia --project=. scripts/fetch_inputs.jl configs/active-49x1296.toml
julia --project=. scripts/run_bp.jl \
  --config configs/active-49x1296.toml \
  --seed 1 --chi 64 --delta 0.15
```

The dry run must report 49 active qubits, 145 layers, 1296 CZ gates, and
QASM SHA-256
`3748e2c026c118f9d6c7499093ea43e41a45251b6bf8d3adb6fb056f718f6cc0`.
It writes no tensors until its printed confirmation token is supplied.

From the repository root, the G5 pilot is planned as a 60-cell
Cartesian grid: the same 20 deterministic seeds at χ=64,128,192 and raw
δ=0.15.

```bash
OLE_ROOT=tracks/qcs/solutions/CCB-LV.999/issue-119-ole
python3 scripts/parameter_scan.py plan \
  --axes "$OLE_ROOT/configs/g5-active-pilot-axes.json" \
  --settings "$OLE_ROOT/configs/g5-active-pilot-settings.json" \
  --provenance "$OLE_ROOT/configs/g5-active-pilot-provenance.json" \
  --run-id issue119-ole-g5-active-pilot \
  --run-dir results/issue119-ole-g5-active-pilot
```

G6 is not planned or submitted until this pilot supplies measured time,
memory, BP stability, truncation, and paired χ-drift evidence for the
documented go/no-go gate.

After all 60 manifests have been fetched:

```bash
python3 scripts/parameter_scan.py collect \
  --run-spec results/issue119-ole-g5-active-pilot/run_spec.json \
  --success-field status --success-value success \
  --value-field result.sample_value \
  --value-field result.wall_seconds \
  --value-field result.peak_rss_bytes
python3 "$OLE_ROOT/scripts/analyze_active_g5.py" \
  --run-dir results/issue119-ole-g5-active-pilot
```

The exact predeclared drift and resource rules are recorded in
`G5_ANALYSIS_PROTOCOL.md`. The first 1 h Slurm attempt completed 24/60 cells.
Walltime-only retries (`415961`, `415977`) raised this to 58/60: χ=128 seed 20
timed out at layer 136/145 after 2 h, and χ=192 seed 5 timed out at layer
137/145 after 5 h. The resulting NO-GO classification, paired-drift
diagnostics, resource observations, and exact two-cell recovery are recorded
in `G5_ACTIVE_PILOT_REPORT.md`. G6 remains blocked until the original 60-cell
grid is complete and the resource gate passes.

## Deterministic PEPO cross-check

The PEPO route is an independent Heisenberg-picture calculation of the same
operator Loschmidt echo. It evolves the three-site observable `Z52 Z59 Z72`
backward and contracts a normalized trace directly, so it has no sampled
initial state, random seed, or sampling error.

From the repository root, create the isolated, locked Python environment and
run its local tests:

```bash
OLE_ROOT=tracks/qcs/solutions/CCB-LV.999/issue-119-ole
uv sync --project "$OLE_ROOT/pepo" --frozen
uv run --project "$OLE_ROOT/pepo" pytest "$OLE_ROOT/pepo/tests" -q
```

Inspect the seven-site dense-oracle validation before executing it:

```bash
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/validate_pepo_small.py"
```

The inspection prints a confirmation token. To create or refresh the oracle
certificate, repeat the command with `--execute --confirm TOKEN` and the
default output directory. The full 49-qubit runner requires a successful
certificate whose QASM hash, pinned quimb revision, and numerical-core digest
all match the current source. In particular, an existing local certificate
from before a dependency-lock or core-source change is intentionally rejected
as stale; rerun this exact-oracle validation rather than bypassing the gate.

`Dop` is the maximum virtual bond retained during PEPO operator evolution,
whereas `χenv` is the maximum intermediate bond retained while contracting the
closed final tensor network. They control distinct approximations and should
not be reported as one generic PEPO bond dimension.

If the small-oracle certificate is stale, this command exits nonzero at the
certificate gate *before* printing a setup or confirmation token, and it
starts no PEPO evolution. With the current certificate, the same command is a
side-effect-free full-system inspection: it prints the confirmed setup and
token but still starts no PEPO evolution. It deliberately has no `--seed`
option because the PEPO trace is deterministic.

```bash
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/run_pepo.py" \
  --dop 2 --chi-env 16 --delta 0.15 \
  --output results/issue119-pepo-dry-run/manifest.json
```

Runtime certificates, dry runs, scan cells, manifests, and figures live under
the workspace-root `results/issue119-pepo-*/` tree. That tree is ignored by
Git; do not place PEPO runtime results in this issue directory or add them to
a source commit.

Plan the initial two-axis scan, then inspect each planned cell before any
remote execution:

```bash
python3 scripts/parameter_scan.py plan \
  --axes "$OLE_ROOT/configs/pepo-pilot-axes.json" \
  --settings "$OLE_ROOT/configs/pepo-settings.json" \
  --provenance "$OLE_ROOT/configs/pepo-provenance.json" \
  --run-id issue119-pepo-49q-pilot \
  --run-dir results/issue119-pepo-49q-pilot
for selector in 1 2 3 4; do
  uv run --project "$OLE_ROOT/pepo" \
    python "$OLE_ROOT/scripts/run_pepo_array_cell.py" \
    --run-spec results/issue119-pepo-49q-pilot/run_spec.json \
    --selector "$selector" --inspect-only
done
```

After the selected cells have completed, collect the generic manifest table
and produce the PEPO convergence assessment:

```bash
python3 scripts/parameter_scan.py collect \
  --run-spec results/issue119-pepo-49q-pilot/run_spec.json \
  --success-field status --success-value success \
  --value-field result.value_real
uv run --project "$OLE_ROOT/pepo" \
  python "$OLE_ROOT/scripts/analyze_pepo.py" \
  --run-dir results/issue119-pepo-49q-pilot \
  --output-dir results/issue119-pepo-49q-pilot
```

The durable reports are `PEPO_SMALL_VALIDATION.md` for the seven-site exact
oracle and `PEPO_49Q_VALIDATION.md` for the completed 49-qubit remote scan.
The latter records the direct `Dop=512,χenv=16/32/64` slice. Its combined
empirical change is below `10⁻³`, but the environment sequence is nonmonotonic
and its newest change grows, so the cross-method conclusion remains
diagnostic. Machine-readable assessment and figures live under
`results/issue119-pepo-49q-dop512-full-chi-analysis/`.
