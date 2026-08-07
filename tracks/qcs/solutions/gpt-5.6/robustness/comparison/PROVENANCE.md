# Robustness package provenance

## Archived evidence boundary

The checked-in `data/`, `figs/`, and `summary.json` are historical evidence
from the 28 July 2026 study run. They predate the machine-readable provenance
contract implemented in the current source:

- explicit input settings in `summary.json`;
- SHA-256 records for the simulation script and pinned requirements;
- wall-time semantics that disclose uncontrolled JAX warm/cold state;
- a non-self-contained `artifact_manifest.json` with relative paths, byte
  counts, and SHA-256 values.

Those fields cannot be reconstructed honestly from the archived files alone.
The existing evidence is therefore preserved unchanged. In particular, this
engineering update does not edit or relabel the checked-in arrays, tables,
figures, or summary.

`FIGURE_NOTES.pdf` is also an archived rendering. Its LaTeX source now points
to the package-local simulation entry point; the PDF should be rebuilt only
as part of a separately reviewed documentation refresh.

## What a sealed fresh run contains

A fresh baseline or full run writes only to a user-supplied new or empty
directory. The final directory contains:

- generated `data/` and `figs/`;
- `summary.json` with input, environment, source-hash, and timing records;
- `artifact_manifest.json`, which covers every stable generated artifact;
- transient `progress.json`, intentionally excluded from the manifest.

The manifest excludes itself to avoid a recursive hash and excludes temporary
atomic-write files. The standard-library validator requires exact closure:
there may be no undeclared stable artifacts and no declared missing files.
The two paper-reference images in this source handoff are not simulation
outputs and must never appear in a generated manifest.

## Required refresh procedure

1. Use the pinned Python 3.12 WSL/Linux environment from `README.md`.
2. Run the baseline-only command into a new temporary directory.
3. Validate that directory in baseline mode.
4. Run the full command into a different new temporary directory.
5. Validate that directory in full mode.
6. Compare regenerated numerical tables with the archived tables at declared
   scientific tolerances. Do not use PNG byte equality as a scientific gate.
7. Record the source commit and retain the validated run directory or an
   archive of it before proposing any replacement of historical evidence.

## Completed fresh-run seal

The refresh procedure was completed on 29 July 2026 against source commit
`7bc049f8302e9b42c8f64590732291de92bef3a7`:

- baseline validator: 32/32 checks passed;
- full validator: 33/33 checks passed;
- full scope: 240 core, 100 noise, 6 pathology, and 10
  Hamiltonian-error trials;
- full process-local wall time: 60.37 seconds on the recorded WSL2 CPU
  environment;
- scientific comparison with the checked-in historical evidence:
  3,951 numerical and 402 categorical values compared, zero mismatches at
  `rtol=1e-8`, `atol=1e-10`.

`FRESH_RUN_SEAL.json` records the source, requirements, comparison-script,
summary, and generated-manifest SHA-256 values. Text-source hashes are
verified after normalizing line endings so that Windows and Linux checkouts
have the same identity. The fresh run verifies the historical scientific
evidence without silently replacing it. Runtime and rendered-image byte
identity remain outside the scientific acceptance gate.

The small `fresh-run-evidence/` directory makes the scientific audit portable:
it contains both run summaries and manifests, the full fresh scientific
tables consumed by the comparator, and the resulting comparison JSON. The
large duplicate NPZ and rendered figures are omitted, but their byte hashes
remain in the generated manifests. The root team validator verifies those
records and reruns the 4,353-field comparison in every clean candidate.
