# Issue 147 QMC Long-Chain Extension Design

## Trigger

The 32000-measurement production run passed the chain R-hat and Trotter-fit
gates. One M=128 chain had split-half z=3.074, just above the fixed limit of
3.0; all other chains passed, and all three M values had R-hat 1.0. The gate
is retained unchanged.

## Extension

Repeat the complete twelve-cell grid with the same seeds, Hamiltonian,
boundaries, M values, four chains, thermalization, estimator, and 80 bins, but
set `measure_sweeps=128000`. With the same seed and thermalization, the first
32000 updates are the previous trajectory prefix; the longer run adds samples
instead of selecting a favorable independent rerun. A new run id is required
because the resumable checkpoint hash includes the measurement budget.

Apply the unchanged 8-bin chain-stratified bootstrap and the same split-half
z, R-hat, and reduced-chi-squared gates.
