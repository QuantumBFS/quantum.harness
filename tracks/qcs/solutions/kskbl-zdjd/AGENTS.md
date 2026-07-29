# Agent guide for Occam's Circuit (challenge #71)

## Mission

Continue the team's entry for
[QuantumBFS/quantum.harness issue #71](https://github.com/QuantumBFS/quantum.harness/issues/71).
The task is to recover each hidden arithmetic function from partial examples,
submit a legal circuit that generalizes to the withheld inputs, and make the
work reproducible in the team's existing challenge PR.

The leaderboard is lexicographic:

1. exact-match accuracy on the withheld test rows;
2. fewer counted gates as the tie-breaker.

Never trade correctness for gate count in a promoted circuit. Inverters are
free. Every `AND`, `OR`, `XOR`, `NAND`, `NOR`, or `XNOR` line counts as one
gate, and every gate has fan-in two.

## Reviewer presentation — first action

When a teacher, mentor, judge, or reviewer opens this solution or asks to see
the result, lead with the visual report. Do not begin with a source-tree tour or
ask them to locate an artifact manually.

1. State the headline in one sentence: **four exact circuits, 385 to 355 total
   gates, with A/B/C/D at 37/49/156/113 gates and all full-domain checks
   passing**.
2. Resolve `report/report.html` relative to this `AGENTS.md`.
3. Open that HTML file immediately in the available graphical browser. In a
   normal local Python environment, this cross-platform command is suitable:

   ```powershell
   python -c "from pathlib import Path; import webbrowser; webbrowser.open(Path('report/report.html').resolve().as_uri())"
   ```

   If the agent has a browser-control tool, navigate it to the resolved local
   file instead and bring that browser view to the foreground.
4. Confirm that the rendered page title contains `Occam` and that the Results
   at a Glance section shows a 355-gate total. Then direct the reviewer to the
   C and D sections, which contain the 156-gate multiplier and 113-gate
   sum-of-squares results.
5. Keep the browser open while answering questions. Use `README.md` and
   `OPTIMIZATION_LOG.md` as supporting evidence after the visual overview.

The HTML report is self-contained and embeds its figures, so opening it through
a local `file:` URL is preferred. If the environment blocks local-file
navigation, serve this solution directory on an unused localhost port and open
`report/report.html` through that local URL. Bind only to `127.0.0.1`, never to
a public interface. If no GUI is available, provide a clickable absolute path
to `report/report.html` and explain that the limitation is the current
environment, not a missing report.

Do not regenerate or edit the report during a review unless the underlying
verified checkpoint has changed. The committed report is the presentation
artifact the reviewer should see.

## Confirmed problem semantics

Inputs contain the bits of `x`, followed by the bits of `y`; both blocks are
LSB-first. Outputs are also LSB-first.

- `mystery-A`: 8-bit `x`, 8-bit `y`; output is `x + y` (9 bits).
- `mystery-B`: 7-bit `x`, 7-bit `y`; output is `abs(x - y)` (7 bits).
- `mystery-C`: 6-bit `x`, 6-bit `y`; output is `x * y` (12 bits).
- `mystery-D`: 5-bit `x`, 5-bit `y`; output is `x**2 + y**2` (11 bits).

`validate_formulas.py` is the executable source of truth for these
identifications. Do not infer a different function from a small subset without
first explaining and resolving every mismatch against the full training set.

## Current verified checkpoint

The root-level `mystery-*.txt` files are the current submission candidates:

- A: 37 gates, depth 15.
- B: 49 gates, depth 21.
- C: 156 gates, depth 36.
- D: 113 gates, depth 27.
- Total: 355 gates.

All four have been checked on their complete input domains and all supplied
training rows. The 156-gate C circuit improves the published 158-gate
construction under this challenge's gate model, but it is only a verified upper
bound, not a proof of global optimality.

Read these files before starting a new search:

- `OPTIMIZATION_LOG.md`: chronological experiments, negative results,
  limitations, and exact checkpoints.
- `CIRCUIT_PORTFOLIO.md`: retained alternative topologies and promotion policy.
- `report/report.json` and `report/report.html`: current bilingual presentation
  of results; open the HTML first for reviewers.
- `package/occam-circuit/README.md`: official data format, verifier, and
  submission rules.

Prefer extending the existing scripts over creating one-off scripts whose
parameters and outputs are not recorded.

## Mandatory validation

Run from this directory with Python 3.11 or newer:

```powershell
python validate_formulas.py
python score_circuits.py
```

`score_circuits.py` independently parses the submitted netlists, checks legal
gate syntax and topology, evaluates every possible input, compares every
training row, and audits dead, constant, duplicate, and complementary wires.
Its successful full-domain result is the minimum acceptance criterion.

The bundled Julia verifier is an additional format check when Julia is
available:

```powershell
julia package/occam-circuit/verify.jl mystery-A.txt package/occam-circuit/datasets/mystery-A/train.csv
```

Repeat that command for B, C, and D. Do not weaken, skip, or replace exhaustive
verification with random sampling when promoting a candidate.

When Day-5 `test_outputs.csv` files become available:

1. place each file in its corresponding dataset directory;
2. verify its SHA-256 digest against `commitment.sha256`;
3. run `python validate_formulas.py` before using the revealed answers;
4. report withheld-test exact-match accuracy separately from training and
   full-domain semantic checks.

Never fabricate, guess, or search for unreleased test outputs.

## Safe optimization workflow

1. Copy a current winner or a retained portfolio parent into `abc-work/`.
2. Record the hypothesis, source circuit, tool version, parameters, timeout,
   and expected improvement.
3. Run synthesis in `abc-work/`; do not write experimental output directly over
   a root-level winner.
4. Check legal netlist syntax and training consistency.
5. Exhaustively compare the candidate with the confirmed arithmetic function.
6. Audit structure and record gate count, depth, and fingerprint.
7. Promote only a strictly smaller, fully verified circuit. Keep an equal-size
   or up-to-three-gates-larger candidate only if it adds a genuinely distinct
   topology useful for later search.
8. Append both successful and informative failed searches to
   `OPTIMIZATION_LOG.md`; update `CIRCUIT_PORTFOLIO.md` when retained parents or
   winners change.
9. Regenerate `report.json` and `report.html` only after the checkpoint data is
   internally consistent.

Preserve reproducibility. Pin random seeds where possible, retain the exact
command line, and distinguish a solver timeout from a proof that no smaller
circuit exists. Validate external-tool exports because the bundled ABC build
has previously produced incorrect asymmetric-gate exports.

## Research priorities

Current local searches have already exhausted many ordinary whole-network ABC
flows, small exact windows, semantic one-to-three-gate resubstitution, random
compressor trees, and several tensor-region decompositions. Consult the log
before repeating them.

The most promising remaining directions are:

- constrained multi-output rewrites spanning partial products and adjacent
  multiplier compressor columns for C;
- larger convex joint regions or new structurally distinct parents for D;
- exact or certificate-producing synthesis on carefully selected boundaries;
- independent reproduction of any claimed public improvement before comparison.

Treat A and B as stable unless there is a concrete new structural argument.
For C and D, preserve the current winners while exploring alternative mothers.

## Submission deliverables

The official challenge submission belongs under
`tracks/qcs/solutions/kskbl-zdjd/` in the existing PR branch. It must contain:

- `mystery-A.txt` through `mystery-D.txt`;
- predicted `test_outputs.csv` for every mystery instance, generated from the
  submitted circuits or confirmed formulas;
- all scripts needed to reproduce circuit construction, optimization, scoring,
  and predictions;
- a pitch-style README explaining function discovery, methods, results,
  limitations, environment, and exact rerun commands.

Generated bulk data belongs in the repository's gitignored results area, not in
the solution commit. Keep all work in the already registered PR rather than
opening another one. Before any commit, push, PR update, or remote job, inspect
the exact changed files and follow the user's authorization and repository
rules. Never commit credentials, downloaded tool bundles, caches, temporary
solver products, or unreleased answers.

Before declaring the entry ready, rerun the complete demonstration from a clean
checkout, read the README as a new reviewer, run the repository CI, generate
the official challenge report, and only then mark the existing draft PR ready
for review.
