# Machine-verifiable XXZ thermodynamic energy certificates

## Team

| | |
|---|---|
| Team name | Ranger |
| Members | Chenxi Wan, Yedi Shen, Junkai Wang |
| Challenge | [#230: Certified energy-density bounds vs. Bethe ansatz](https://github.com/QuantumBFS/quantum.harness/issues/230) |
| Track | `polyopt` |

## Certified result and challenge status

This submission delivers a validated **hope signal** and a complete calibration
frontier. The challenge's literature-record comparison is the next proof gate.

For the spin-\(\tfrac12\) XXX Hamiltonian normalized as

\[
h=(XX+YY+ZZ)/4,
\qquad
e_{\mathrm B}=\frac14-\log 2,
\]

the strongest self-contained certificate in this submission proves

\[
\boxed{
-0.443976567
\le e_0
\le -0.4428702958784947210360110613724028607783
}.
\]

The interval has width

\[
0.001106271121505278963988938628
\]

and contains the independently enclosed Bethe value. The lower endpoint is a
depth-47, bond-dimension-6, U(1)-blocked RG dual verified after exact rational
repair and blockwise LDL checks. The upper endpoint is the exact contraction
of a rational bond-32 MPS block with 1,000 sites and explicit boundaries.
Bethe data is reserved for the final independent containment test.

Issue #230 defines three evaluation outcomes:

1. **Success gate:** every certified level contains the Bethe value, and the top
   computable level improves the best normalization-matched published rigorous
   Heisenberg-chain bound.
2. **Hope signal:** valid intervals plus a profile of which constraint families
   tighten fastest form a useful calibration dataset.
3. **Pivot signal:** any persistent Bethe exclusion triggers a soundness audit.

All published levels pass the hard containment check, and the 27-certificate
dataset fulfills the hope-signal objective. The \(3\times10^{-4}\) width used
during the sprint is an internal engineering target; the official success gate
is the normalization-matched literature comparison above.

## What is included

- an independent certificate schema and verifier;
- Bethe-ansatz interval enclosures used only as a correctness oracle;
- LTI, reflection, SU(2), U(1), RG, rational-repair, and MPS implementations;
- unit and equivalence tests for the symmetry-reduced formulations;
- 27 compact certificates over
  \(\Delta\in\{-2,-1,-0.5,0,0.5,0.9,1,1.1,2\}\);
- the self-contained depth-47 XXX certificate;
- a 1,000--16,000-site exact rational-MPS contraction frontier;
- a Chinese technical report in Markdown, LaTeX, and audited PDF form;
- exact decimal summary, record-gate arithmetic, and SHA-256 data manifest;
- machine-readable lower-bound, iTEBD, and ablation search logs.

Large superseded intermediate certificates are intentionally omitted. The
selected payload and the compact benchmark grid are sufficient to reproduce
the claims made here.

Selected certificate SHA-256:

```text
1f7c684b3c2f62506f9b30f11e80197045f26a3cfcf464b608f1d2cab998e0c7
```

## Reproduce

From this directory:

```bash
python3 -m venv .venv
.venv/bin/pip install -e . pytest
.venv/bin/pytest -q --ignore=tests/test_published_outputs.py
.venv/bin/xxzcert verify \
  outputs/final/xxx_best/level_47_rg_d6_mps_d32_block_1000.json
```

The final verification is deliberately independent of the numerical solver
and may take tens of minutes because it reconstructs the exact RG witness and
the 1,000-site rational MPS contraction.

See:

- [technical report (PDF)](docs/issue-230/technical-report-zh.pdf);
- [technical report (Markdown)](docs/issue-230/technical-report-zh.md);
- [audited certificate summary](outputs/final/certificate-summary.csv);
- [exact upper-contraction frontier](outputs/final/upper-contraction-frontier.csv);
- [data manifest](outputs/final/DATA_MANIFEST.txt);
- [certificate specification](docs/issue-230/specification.md);
- [detailed reproduction instructions](docs/issue-230/reproduce.md);
- [results and verification evidence](docs/issue-230/results.md).

`DATA_MANIFEST.txt` uses the documented four-column
`SHA256  BYTES  ROLE  PATH` layout. Its authoritative deterministic check is
`.venv/bin/pytest tests/test_delivery.py -q`; it is intentionally richer than
the two-column input accepted by `shasum -c`.

## Research contribution

The submission establishes a reproducible, machine-verifiable two-sided
thermodynamic certificate and records which constraint families and numerical
paths are most effective. Native U(1) charge blocks reduce the D=6, depth-12
optimization from 93,329 dense variables to 6,882 variables (13.6x
compression); strict-margin interpolation and exact blockwise LDL turn solver
candidates into independently replayable witnesses; integer FLINT contraction
extends the exact rational-MPS upper frontier from 1,000 to 16,000 sites and
shrinks its Bethe-referenced upper gap by 3.20x. Formal certificate claims are
drawn only from payloads that pass the public verifier, preserving a clean path
from numerical exploration to mathematical proof.
