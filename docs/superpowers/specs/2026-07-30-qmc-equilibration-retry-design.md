# Issue 147 QMC Equilibration Retry Design

## Failure evidence

The beta=0.5 pilot completed all twelve requested cells, but the fixed 1000
Wolff-cluster thermalization budget did not equilibrate the larger Trotter
systems. The M=64 chains relaxed from energies near -20 to approximately -3
during measurement. The M=128 chains relaxed from approximately -85 to -3 and
had lag-one bin correlations near 0.999. These cells are retained as failed
equilibration evidence and must not enter the Trotter fit.

## Chosen retry

Keep the Wolff update, the 8000 measurement cluster flips, and the 80-bin
measurement layout unchanged. Scale the number of thermalization cluster flips
as

```
thermal_sweeps(M) = 1000 * (M / 32)^2
```

This gives 1000, 4000, and 16000 thermalization flips for M=32, 64, and 128.
The scaling follows the observed relaxation time and leaves a large runtime
margin: the failed M=128 cells completed 9000 total flips in about ten seconds.

Run all three M values and all four chains in a new
`issue147-qmc-pilot-equilibrated` run. Do not overwrite the first pilot.

## Interface change

Add an optional `--thermal-sweeps` override to the QMC CLI. The run-spec may
declare `thermal_sweeps` in per-cell settings, and `run_cell.py` passes the
merged setting to the QMC CLI. The default remains the value in
`qmc-reference.json`, so existing runs and tests keep their behavior.

The manifest must record the effective per-cell thermalization count. The new
run-spec is the source of the shared settings, per-cell overrides, parameters,
and protocol provenance.

## Rejected alternatives

- Redefining one sweep as enough Wolff clusters to flip one complete space-time
  volume changes the runtime and statistical meaning of every existing budget.
- Discarding the drifting bins leaves too few equilibrated M=128 samples and
  hides a failed thermalization protocol.

## Verification

Local tests must prove that the CLI override is optional, positive, recorded in
the runtime manifest, and propagated by `run_cell.py`. The retry is accepted
only when all twelve cells have success manifests and 80 finite bins, the four
chains at each M show no material split-half drift, chain R-hat is close to one,
and a chain-stratified block bootstrap gives a linear fit in `(beta / M)^2`
with reduced chi-squared below 4. Failed gates remain visible and are not used
as a QMC reference.
