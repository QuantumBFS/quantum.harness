# Route D+ Phase 6A result: jobs 23019901 and 23020184

## Outcome

Phase 6A passed at clean implementation revision
`1b086e4cdf467d7d5cf894ddefd266f91ecd6352`. Job `23019901` produced the
isolated numerical profile and job `23020184` independently finalized and
read back the schema-valid certificate. Neither job read or executed ED.

## Coordinate and performance certificate

- N=6, 2Q=15, two random continuous configurations
- Compact reproducing quadrature: 128 nodes
- LLL reconstruction error: `4.223980065980164e-15`
- Maximum proof/production error: `3.4668342425655455e-22`
- Mean ground amplitude cost: `0.03000093623995781 s`
- Mean five-component tower cost: `2.8278693333268166 s`
- Cache cold/hit/batch: `0.0296487 / 0.0000647791 / 0.0295101 s`
- Cache value error: `0`
- Delayed correction acceptance: `1.0`
- Delayed-chain ESS: `15.508666047604159`
- Delayed-chain ESS/s: `1.7591278863248758`
- Delayed-chain R-hat: `1.0125621648514533`

All eight Phase 6A gates passed: strict LLL quadrature, continuous backend
agreement, exact cache, delayed-acceptance equivalence, finite performance,
GPU allocation, clean source, and blind boundary.

## Slurm evidence

Profile job `23019901`:

- `xhcs3/xhhgnormal`, node `e01r04`, one RTX 3080
- four CPUs, 12 GiB, 30 seconds, `COMPLETED 0:0`
- raw result SHA-256:
  `c37db42de739cb9bfc8543beeb70929710d0921cd01b534f9e519d8aff983b2f`
- stdout SHA-256:
  `df8370d4670942f2fd27ca21f3aafe7e9ea024010b3ef3080f134c0b1987b7c9`
- stderr SHA-256:
  `956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09`
- sacct evidence SHA-256:
  `5be4681c53019f203ab37cfbf13cd73cfe232d364e77b1ef6b89bd45059dc79b`

Readback job `23020184`:

- `xhcs3/xhhgnormal`, node `e12r04`, one RTX 3080
- two CPUs, 6 GiB, 27 seconds, `COMPLETED 0:0`
- final certificate SHA-256:
  `eda5507e6e9f67171b6e2fbb1e6356438627c923a233a11ebe7880dd88540abd`
- readback SHA-256:
  `90474f9332670c3160c23b9d3fb023832d26c6db2223cd7ee9b35711a9e63653`
- stdout SHA-256:
  `8b31ad2d4016a738ca497303f714750e419c8dff354e922b5a2f8ae941c0e6dd`
- stderr SHA-256:
  `956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09`

The independent readback passed certificate, revision, clean-worktree, source
hash, raw-result hash, stdout/stderr hash, and sacct-evidence hash checks.

## Gate implication

Phase 6A is complete. This does not authorize Phase 7. Phase 6B still needs
the shared frozen architecture and three statistically adequate seed runs;
Phase 6C still needs complete continuous symmetry, blind-access, checkpoint,
log/hash, stopping-condition, and aggregate readback gates.
