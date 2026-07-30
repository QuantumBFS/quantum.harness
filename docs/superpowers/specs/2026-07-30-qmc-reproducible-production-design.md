# Issue 147 QMC Reproducible Production Design

## Provenance repair

The accepted long-chain statistics were produced from deliberately shipped
files in a dirty remote checkout. The runtime manifest recorded the remote
checkout's older HEAD but not the shipped file hashes, so that commit alone
could not reconstruct the calculation.

The final run records SHA-256 for the QMC driver, mapping, dispatcher, and
reference configuration in both the run spec and every runtime manifest. It
also records whether the remote checkout is dirty. Acceptance requires exact
agreement between planned and observed source hashes.

## Trajectory contract

Each cell declares its exact expected seed. The final 128000-measurement run
uses the same seeds and thermalization as `issue147-qmc-production`, whose
32000 updates must be the trajectory prefix. Acceptance regroups each prefix
run's 80 bins four at a time and compares them with the first 20 final-run bins
to absolute tolerance `1e-12`.

All Hamiltonian, lattice, boundary, Trotter, chain, thermalization,
measurement, bootstrap, R-hat, split-half, and fit settings remain unchanged.
