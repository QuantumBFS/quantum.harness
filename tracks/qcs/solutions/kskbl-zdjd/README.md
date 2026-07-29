# Occam's Circuit — Exact Arithmetic Networks in 355 Gates

This submission recovers all four hidden arithmetic functions in
[challenge #71](https://github.com/QuantumBFS/quantum.harness/issues/71),
generates official-format Boolean circuits, and predicts every withheld output
by evaluating those circuits.

Our focus is not merely recognizing the four formulas. We reduce the exact
circuits from a 385-gate arithmetic baseline to **355 gates**, while preserving
zero error on every input in each complete finite domain. The main result is a
**156-gate exact 6-by-6 multiplier**: two gates below Sergeev's published
158-gate construction under the challenge's unit-cost, free-inversion model.

## Team

| Field | Value |
|---|---|
| Team | `kskbl-zdjd` |
| Member | Zong-yue Liu |
| Track | `qcs` |
| Challenge | Occam's Circuit, issue #71 |

## Results

Inputs contain two equal-width unsigned integers, `x` followed by `y`, with
both input blocks and the output encoded LSB-first.

| Instance | Recovered function | Input to output bits | Baseline gates | Final gates | Reduction | Full-domain verification |
|---|---|---:|---:|---:|---:|---:|
| mystery-A | `x + y` | 16 to 9 | 37 | **37** | 0 | 65,536 / 65,536 |
| mystery-B | `abs(x - y)` | 14 to 7 | 53 | **49** | 4 | 16,384 / 16,384 |
| mystery-C | `x * y` | 12 to 12 | 168 | **156** | 12 | 4,096 / 4,096 |
| mystery-D | `x² + y²` | 10 to 11 | 127 | **113** | 14 | 1,024 / 1,024 |
| **Total** | Four exact functions | — | **385** | **355** | **30** | **87,040 / 87,040** |

All 5,100 training rows match. The four generated `test_outputs.csv` files
also match the SHA-256 commitments anchored in issue #71:

- **6,124 / 6,124 withheld rows exactly correct**;
- **56,864 / 56,864 withheld output bits correct**;
- **87,040 / 87,040 full-domain circuit-versus-formula cases correct**;
- no dead gates, constant wires, or duplicate/complement-equivalent internal
  wires in any retained circuit.

The checked-in predictions are produced by reparsing and evaluating the
submitted netlists, rather than by writing the recovered formulas directly.

## Main Finding: Reachability Beats Purely Local Optimization

The most important result is the reduction of the multiplier from the
published 158-gate construction to 156 gates.

We first reproduced Sergeev's 6-bit multiplier directly from its compressor
components:

- 36 partial-product gates;
- 6 half adders;
- 3 ordinary three-input full adders;
- 1 encoded-input Stockmeyer full adder;
- 10 modified double full adders;
- 11 XOR gates for encoded bit pairs.

This gives exactly 158 gates and passes all 4,096 multiplier inputs. A
full-domain semantic pass then found that the four-gate cone driving the most
significant product bit is over-general when its boundary wires are treated as
independent. Only a constrained subset of those boundary assignments is
reachable from the twelve primary inputs.

On every reachable multiplier state, the output simplifies to:

```text
g36 AND (g29 OR g154)
```

The OR uses one NAND with complemented inputs, followed by one AND. Replacing
the old four-gate cone by these two gates produces the exact **156-gate**
circuit.

This demonstrates a concrete limitation of conventional local resynthesis:
optimizing a cut under all formal boundary assignments can hide reductions
that become valid once global reachability constraints are restored.

The 156-gate network is the smallest exact 6-by-6 multiplier found in our
literature, public-submission, and independent-tool audit under this exact gate
model. It is a new constructive upper bound, not a proof of global minimality.

## How the Other Reductions Work

### B: polarity-aware full subtractors

The initial conditional two's-complement circuit used 53 gates. Rewriting a
full subtractor as a full adder with complemented inputs and a complemented
sum exploits the challenge's free inversion rule. Fifty symmetry-derived
seeds converged to the retained **49-gate** circuit.

### D: topology islands and joint-region synthesis

The sum-of-squares circuit was reduced from 127 to **113 gates** in five
stages:

1. deterministic `resyn3`, `drwsat2`, and high-effort `mfs2` rewrites reached
   122 gates;
2. 200 randomized exact square-sum topologies escaped that local basin and
   reached 117 gates;
3. two non-contiguous graph-tensor replacements reduced 117 to 115 gates;
4. a seven-input, five-output joint region was reduced from 26 to 25 gates;
5. an eight-input, six-output convex region was reduced from 27 to 26 gates,
   producing the final 113-gate network.

Every local replacement passed exhaustive boundary evaluation before
embedding. Every complete candidate then passed all 1,024 primary-input
assignments. Follow-up semantic resubstitution, larger joint regions, and
whole-network ABC flows did not find a 112-gate circuit within their declared
budgets.

### A: a stable ripple-carry reference

The 37-gate adder is one half adder followed by seven five-gate full adders.
Fifty symmetry-distinct seeds and the tested exact-window and resynthesis flows
all returned 37 gates. This is a bounded negative result, not a global
minimality proof.

## Search Strategy

The final circuits combine several levels of optimization:

1. infer arithmetic semantics from training rows only;
2. construct exact arithmetic baselines;
3. rewrite arithmetic cells to exploit free input and output polarity;
4. run ABC rewriting, refactoring, SAT-derived don't-care optimization, and
   stochastic topology search;
5. retain equal-size but structurally distinct parents to avoid premature
   convergence;
6. synthesize multi-output graph and tensor regions;
7. use complete-domain semantics to expose globally reachable cut states;
8. promote a candidate only after boundary checks, full-domain verification,
   training verification, and structural audit.

The search log records successful reductions, timeouts, tool failures, and
negative results. In particular, a bundled ABC revision was found to swap the
truth-table axes when exporting asymmetric two-input gates. Independent
full-domain verification caught the defect; no candidate is accepted from tool
exit status alone.

## Reproduce

From this directory, Python 3.11 or newer is sufficient for the core checks:

```bash
python validate_formulas.py
python score_circuits.py
python generate_test_outputs.py --check
```

Expected final checkpoint:

```text
mystery-A: gates=37, exhaustive=65536/65536, training=2000/2000
mystery-B: gates=49, exhaustive=16384/16384, training=1500/1500
mystery-C: gates=156, exhaustive=4096/4096, training=1200/1200
mystery-D: gates=113, exhaustive=1024/1024, training=400/400
```

Rebuild and verify the 158-to-156 multiplier path:

```bash
python build_sergeev_multiplier.py abc-work/sergeev-158/mystery-C.txt
python optimize_sergeev_multiplier.py
python normalize_netlist.py abc-work/sergeev-156/mystery-C.txt abc-work/sergeev-156/mystery-C.txt
python score_circuits.py mystery-C --directory abc-work/sergeev-156
```

Regenerate the four deterministic arithmetic baselines:

```bash
python build_exact_circuits.py
```

The official Julia verifier provides an independent format and training check:

```bash
julia package/occam-circuit/verify.jl mystery-A.txt package/occam-circuit/datasets/mystery-A/train.csv
```

Repeat the Julia command for B, C, and D.

## Deliverables

- `mystery-A.txt` through `mystery-D.txt`: retained official-format circuits;
- `predictions/*/test_outputs.csv`: circuit-evaluated withheld predictions;
- `validate_formulas.py`, `score_circuits.py`, and
  `generate_test_outputs.py`: independent semantic, exhaustive, and commitment
  checks;
- `normalize_netlist.py`: deterministic conversion to the official `w<number>`
  internal-wire syntax;
- `build_exact_circuits.py`: reproducible 385-gate baseline construction;
- `build_sergeev_multiplier.py` and `optimize_sergeev_multiplier.py`:
  reproducible 158-to-156 multiplier construction;
- the remaining Python scripts: ABC, semantic, graph-region, tensor-region,
  and topology-portfolio search procedures;
- `OPTIMIZATION_LOG.md`: full chronological evidence, including negative
  results and limitations;
- `CIRCUIT_PORTFOLIO.md`: retained parent topologies and promotion policy;
- `report/report.html` and `report/report.json`: bilingual visual report.

## Scope and Limitations

This submission establishes four exact constructive upper bounds under the
challenge gate model. It does not claim:

- a general solver for arbitrary partial Boolean functions;
- globally minimal circuits for A, B, C, or D;
- that solver timeouts prove the absence of smaller circuits;
- that conclusions automatically transfer to a different gate library or
  non-free inversion model.

For C, the next high-value direction is constrained multi-output synthesis
across partial products and adjacent compressor columns. For D, the retained
113-, 114-, 115-, and 117-gate parent topologies provide distinct starting
points for larger reachability-aware regions.

## References

- [Occam's Circuit challenge #71](https://github.com/QuantumBFS/quantum.harness/issues/71)
- [Sergeev, *On the circuit complexity of multiplying integers*](https://arxiv.org/abs/1602.02362)
- [*Smaller Circuits for Bit Addition*, STACS 2026](https://doi.org/10.4230/LIPIcs.STACS.2026.46)
- [SPbSAT Simplifier](https://github.com/SPbSAT/simplifier)

Addresses #71.
