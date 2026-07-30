# Machine-verifiable XXZ thermodynamic energy certificates

## Team

| | |
|---|---|
| Team name | Ranger |
| Members | Chenxi Wan, Yedi Shen, Junkai Wang |
| Challenge | [#230: Certified energy-density bounds vs. Bethe ansatz](https://github.com/QuantumBFS/quantum.harness/issues/230) |
| Track | `polyopt` |

## Current verdict

This is a validated **hope-signal submission**, not a record claim.

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
Bethe data is not used to construct or repair either endpoint.

The provisional record target used during the search is \(3\times10^{-4}\).
This submission does not meet that target and does not claim to improve the
best normalization-matched rigorous literature interval.

## What is included

- an independent certificate schema and verifier;
- Bethe-ansatz interval enclosures used only as a correctness oracle;
- LTI, reflection, SU(2), U(1), RG, rational-repair, and MPS implementations;
- unit and equivalence tests for the symmetry-reduced formulations;
- 27 compact certificates over
  \(\Delta\in\{-2,-1,-0.5,0,0.5,0.9,1,1.1,2\}\);
- the self-contained depth-47 XXX certificate;
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

- [certificate specification](docs/issue-230/specification.md);
- [detailed reproduction instructions](docs/issue-230/reproduce.md);
- [results and verification evidence](docs/issue-230/results.md).

## Claim boundary

The submission establishes a reproducible, machine-verifiable two-sided
thermodynamic certificate and records which constraint families and numerical
paths were effective. It does not promote floating-point candidates, solver
status strings, inactive cluster resources, or Bethe-calibrated corrections
to proofs. The unresolved task is to tighten both endpoints enough to cross
the record-width gate.
