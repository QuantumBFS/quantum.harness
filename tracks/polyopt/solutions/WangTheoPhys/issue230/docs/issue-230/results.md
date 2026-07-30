# Issue #230 current certified results

## Strongest XXX certificate

For

\[
h=(XX+YY+ZZ)/4,
\qquad
e_B=\frac14-\log 2,
\]

the strongest selected proof currently gives

| quantity | certified decimal |
|---|---:|
| lower endpoint | `-0.443976567` |
| Bethe interval lower | `-0.443147180559945341737915214253007434308528900146484375` |
| Bethe interval upper | `-0.443147180559945230715612751737353391945362091064453125` |
| upper endpoint | `-0.4428702958784947210360110613724028607783` |
| interval width | `0.001106271121505278963988938628` |
| conservative lower error | `0.0008293864400546582620847857470` |
| conservative upper error | `0.0002768846814505096796016903650` |

The lower proof is a depth-47, D=6 U(1)-blocked RG dual. A zero-margin
candidate was convexly interpolated with a solver-enforced strict-margin
candidate until every reconstructed floating slack had at least
\(2\times10^{-6}\) margin. The result was rounded at denominator \(10^{10}\),
repaired using exact rational arithmetic, and checked blockwise by exact LDL.
The upper proof is a bond-32 rational MPS block of 1000 sites with explicit
boundaries. Bethe data was not used to construct, interpolate, or repair either
proof.

## Independent verification evidence

The level-17 JSON was verified from its self-contained payload in this
repository on 2026-07-29:

```text
PASS outputs/final/xxx_best/level_17_rg_d6_mps_d32_block_1000.json
1905.70 seconds wall time
259,342,336 bytes maximum resident set size
```

The selected level-23 payload subsequently passed the same public CLI:

```text
PASS outputs/final/xxx_best/level_23_rg_d6_mps_d32_block_1000.json
781.69 seconds wall time
847,216,640 bytes maximum resident set size
```

The depth-47 witness was independently reconstructed and passed exact
charge-block LDL verification before publication:

```text
exact lower = -443976567/1000000000
verify_rg_dual_witness(Fraction(1), witness) = True
944.65 seconds wall time
266,436,608 bytes maximum resident set size
```

The resulting self-contained level-47 JSON then passed the complete public
CLI, including exact lower and upper reconstruction:

```text
PASS outputs/final/xxx_best/level_47_rg_d6_mps_d32_block_1000.json
2256.59 seconds wall time
180,289,536 bytes maximum resident set size
```

The migrated level-13 payload independently passed as well (`2104.79` seconds,
`1,097,089,024` bytes maximum resident set size). The level-9 and level-11 XXX
proofs passed individually. All 27 selected XXZ grid certificates at
\(\Delta\in\{-2,-1,-0.5,0,0.5,0.9,1,1.1,2\}\) passed the same public verifier.

## Symmetry-adapted RG development

The current branch adds:

- exact inference and validation of U(1) virtual charges;
- deterministic charge-sector splitting and reconstruction;
- blockwise log-determinants, inverses, eigenvalue checks, and Hessian actions;
- elimination of forbidden cross-sector and redundant symmetric parameters;
- U(1)-constrained MPS flow optimization;
- hard rejection of non-finite, indefinite, failed, or locally dominated RG
  candidates before exact repair;
- a direct U(1)-blocked conic formulation with explicit strict slack margins;
- exact charge-block reconstruction and LDL verification for RG witnesses.

The parameter reduction is substantial:

| tensor/depth | dense variables | U(1) variables | retained |
|---|---:|---:|---:|
| D=4, depth 12 | 18,449 | 2,058 | 11.2% |
| D=6, depth 12 | 93,329 | 6,882 | 7.4% |

Small-instance tests prove equality of the block and dense objective,
directional derivative, and Hessian quadratic form. The constrained
variational energies improve from `-0.39062500000000033` at D=4 to
`-0.43683420094259673` at D=6 and `-0.4416296141778561` at D=10. The D=6,
depth-5 RG dual is strictly feasible at `-0.4672746445819207`. The useful
odd-depth sequence then reaches raw values `-0.451557586734983` at depth 9,
`-0.4474244180594897` at depth 13, `-0.44644270925755863` at depth 15,
`-0.445773298274977` at depth 17, `-0.44528580759513053` at depth 19,
`-0.44496401878922665` at depth 21, and `-0.4447111086144071` at depth 23.
Strict-margin exact witnesses improve monotonically from `-0.445955592`
(depth 17) through `-0.445503996` (depth 19) and `-0.4451779599` (depth 21)
to `-0.4450613894` (depth 23), `-0.4447274666` (depth 31), and
`-0.4442863301` (depth 39). At depth 47, convex interpolation between the
strict and zero-margin conic duals gives the selected exact witness
`-0.443976567`.

## Remaining acceptance gate

This result does not yet beat the normalization-matched rigorous
interval-width scale discussed in the research analysis. The certified width
is `0.001106271121505278963988938628`, versus the provisional target
`0.0003`. Both endpoints now matter: the conservative lower and upper errors
are respectively `0.0008293864400546582620847857470` and
`0.0002768846814505096796016903650`. Completion of the record goal therefore
requires a stronger exact lower witness and a tighter rigorous upper endpoint;
an unverified numerical estimate cannot close either gap.
