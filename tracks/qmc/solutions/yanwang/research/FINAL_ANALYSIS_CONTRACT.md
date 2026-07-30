# Final analysis controller contract

Status: **drafted and tested before final production data exist**.

The sealed input is assembled without cross-lattice arithmetic:

```bash
python3 scripts/assemble-final-analysis-bundle.py \
  --manifest experiments/final-production/bundle-manifest.json \
  --out results/final/sealed-analysis-input.json
```

The assembler requires a clean frozen commit; exact hashes for the two
dedicated-SSE lattice exports, the shared ALPS/looper route export, every
analysis report/run manifest/environment/scheduler inventory, both route code
artifacts, and both arithmetic implementations; distinct method identities;
complete ordered variant rosters; production-only labels; and at least 50,000
successful draws per accepted fit. It copies index-preserving evidence but
does not calculate or print a cross-lattice quantity. The output is confined
to a new file under ignored `results/`.

The one-command controller is:

```bash
python3 scripts/final-ratio-gate.py blind \
  --bundle results/final/sealed-analysis-input.json \
  --out-dir results/final/blind

python3 scripts/final-ratio-gate.py open \
  --bundle results/final/sealed-analysis-input.json \
  --blind-record results/final/blind/blind-record.json \
  --freeze-commit FULL_GIT_SHA \
  --out-dir results/final/open
```

`blind` validates, without publishing a critical field or ratio:

- the exact production data class and frozen Git commit;
- the reviewed preregistration digest;
- separate code hashes and implementation IDs for dedicated SSE and
  ALPS/looper;
- successful per-route and per-lattice quality gates;
- exact run-manifest, environment, scheduler-inventory, analysis-report, and
  source-code hashes plus the reproducible analysis command for each lattice
  and route;
- at least 50,000 successful bootstrap draws for every accepted fit, with
  configured, successful, and failed counts recorded separately (the current
  frozen lattice plans configure 100,000);
- the complete required variant roster, including explicitly rejected fits;
- provenance declarations that neither the ratio nor sqrt(5) selected a
  field window, fit, seed, or retained result;
- the independently validated arithmetic-candidate hash.

It emits only checksums, counts, and Boolean readiness gates. The sealed input
remains under ignored `results/` storage and must not be inspected before
`open`.

`open` refuses a dirty worktree, changed input, changed blind record or blind
checksum inventory, changed arithmetic validator, wrong freeze commit,
non-production input, missing/reordered variants, absent bootstrap draws,
failed route, an output path outside the project's ignored `results/` tree, or
a reused output directory. Every configured fit-bootstrap index is retained;
failed refits are explicit `null` entries rather than silently discarded.
It recomputes the ratio only at indices where both lattice fits succeeded,
requires at least 50,000 such joint draws, and records the configured,
successful, and failed joint counts. The systematic ratio uncertainty is the
largest shift over the
Cartesian product of all accepted, predeclared triangular and honeycomb
variants. This deliberately conservative product preserves both cancellation
and reinforcement without pairing variants after seeing their values.

The independent route must agree with the dedicated SSE field on each lattice
within two combined total standard deviations. Its ratio sign is used only by
the preregistered evidence-against gate. Disagreement is retained and forces
an inconclusive verdict; the two routes are never averaged.

The ALPS/looper analyzer produces its own opt-in
`sealed-independent-bootstrap.json`. Its route-local bootstrap refits every
accepted predeclared variant, retains failed refits at their configured
indices, and does not import the dedicated-SSE sealed exporter or the final
ratio controller. Ordinary independent-analysis output remains unchanged when
the export is disabled.

The opened directory contains:

- `verdict.json`, matching `research/schema/verdict-record.schema.json`;
- `verdict-input.json`, the exact arithmetic-validator input;
- `joint-robustness.json`, every accepted joint variant and uncertainty;
- `cross-method-check.csv`, both computational routes and comparison tags;
- `SHA256SUMS`.

The production arithmetic candidate is also independently scored with:

```bash
research/validator/validate final-arithmetic --out report.json
```

At opening, its output must agree key-for-key and numerically with the
separately stored trusted reference candidate before any verdict file is
accepted.

This contract does not authorize production. The production run manifest,
field windows, lattice sizes, seeds, beta policy, and resource plan are frozen
only after the currently running baseline analyses pass.
