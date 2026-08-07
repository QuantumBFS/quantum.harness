# Proof-Carrying Trotter Bound Paper Design

## Objective

Create an independent 22--30 page English research manuscript that develops
the Issue 128 result into a general scientific narrative.  The manuscript will
present a proof-carrying, model-aware compiler for rigorous Trotter resource
bounds and use the certified `393 -> 97` Heisenberg result as its principal
case study.  It will not modify the frozen certificate or promote the
conditional fivefold arithmetic to a certified claim.

## Audience and publication posture

The primary audience is researchers in quantum algorithms, Hamiltonian
simulation, computational many-body physics, and computer-assisted proof.
The initial format is a self-contained generic LaTeX article suitable for an
arXiv `quant-ph` release.  Its structure will support later adaptation to
Physical Review Research or Quantum without rewriting the scientific core.

The paper will make a strong but scoped claim: for the fixed periodic
`L=12` square-lattice Heisenberg benchmark, fixed five-copy fourth-order
Suzuki formula, uniform operator-norm target, and fixed compilation model, the
submitted exact certificate reduces the accepted resource count from 11,791
to 2,911 merged group exponentials.  The paper will call this a best-known
certified bound only with an explicit "to the best of our knowledge" qualifier.

## Scientific narrative

The paper is organized around a compiler pipeline rather than a chronological
competition report.  Its source language is a local Pauli Hamiltonian,
fragmentation, product formula, evolution time, tolerance, and cost model.
Its intermediate representations are free associative words, homogeneous Lie
defects, concrete symplectic Pauli ledgers, and rational norm certificates.
Its output is an independently checkable adjacent-step error certificate and
an integer resource count.

Every optimization stage will use the same explanatory pattern:

1. identify the conventional relaxation;
2. explain what structural information it discards;
3. define the replacement transformation;
4. state and justify its soundness;
5. describe the implementation and data representation;
6. identify what the independent verifier checks; and
7. quantify the contribution to the final result where an isolated number is
   available.

## Claim taxonomy

All statements will be labeled conceptually as one of three classes:

- **Certified:** exact rational or outward interval statements verified from
  frozen artifacts, including the `r=97` pass, `r=96` rejection, resource
  arithmetic, D4 partition, D5 sidecar identity, and small-system enclosure.
- **Empirical cross-check:** dense small-system numerical error and any timing
  or implementation measurements that are not used in the theorem.
- **Conditional research direction:** the `r=78` fivefold arithmetic,
  processor candidates, shorter product formulas, and delayed-tail proposals.

No conditional item may appear in the abstract or conclusion as an achieved
resource improvement.

## Planned manuscript structure

1. **Abstract.** State the fixed benchmark, proof-compiler contribution,
   `393 -> 97` boundary, exact ratio, and trust model.
2. **Introduction.** Motivate the gap between general commutator bounds and
   finite-instance resource estimates; list contributions and limitations.
3. **Problem formulation.** Define the Hamiltonian, fragmentation, product
   formula, operator-norm objective, and compilation cost.
4. **Baseline reconstruction.** Separate the published Childs--Su--Tran--
   Wiebe--Zhu theorem from the paper's pinned interval instantiation; explain
   the 31-center scan and the `r=393` control.
5. **Compiler overview.** Present inputs, intermediate representations,
   outputs, invariants, and the discovery/trust boundary.
6. **Exact product-formula algebra.** Define sparse free-word series,
   truncated multiplication, formal logarithms, symmetry, and order checks.
7. **Lie projection.** Define the Dynkin--Specht--Wever projection and its use
   for degree-five and degree-seven defects.
8. **Concrete Pauli evaluation.** Define symplectic Pauli multiplication,
   local commutator expansion, support filtering, and translation cells.
9. **Norm-last optimizations.** Explain translation canonicalization, exact
   coefficient aggregation, and cancellation before norm inequalities.
10. **Certified anticommuting partitions.** Define the graph, clique cover,
    Euclidean group norm, exact coverage checks, and rational square-root
    enclosure; report the D4 statistics and reduction.
11. **Heisenberg local lemma.** Prove the 16-case bond commutator result and
    explain its cumulative use in higher-degree propagation.
12. **Finite-step certificate.** Derive the right logarithmic generator,
    degrees D4--D7, Duhamel integration, support growth, and rational
    geometric tail.
13. **Resource compilation.** Prove `G(r)=30r+1`, derive bond and CNOT counts,
    and establish the adjacent integer boundary.
14. **Proof-carrying verification.** Specify certificate schemas, hashes,
    independent verifier checks, negative tests, and trusted arithmetic.
15. **Results and ablations.** Present the error ledger, resource table,
    direct-versus-grouped D4 norm, recursive-order audit, negative routes,
    and small-system cross-check.
16. **Related work and positioning.** Distinguish worst-case commutator bounds,
    model-specific symbolic bounds, low-energy/average-case analyses,
    MPF/LCU/error mitigation, formula optimization, and ordering methods.
17. **Limitations and research frontier.** Quantify the D4/D5/D6/D7/tail
    bottlenecks at `r=78` and explain why tenfold requires an order lift.
18. **Reproducibility.** Provide exact commands, artifact identities, platform
    metadata, and a claim-to-evidence matrix.
19. **Conclusion.** Restate the scoped certified contribution.
20. **Appendices.** Include formal-series identities, verifier pseudocode,
    certificate schema, local Pauli table, detailed ledgers, and additional
    literature-comparison tables.

## Figures and tables

The paper will include at least the following visuals:

- compiler pipeline from formula to certificate;
- trusted versus untrusted computation boundary;
- baseline and candidate resource bars;
- stacked D4--tail error ledger at `r=97`;
- D4 norm reduction from termwise l1 to certified grouped l2;
- fivefold bottleneck ledger at `r=78` with certified/non-certified labeling;
- method comparison matrix across operator norm, changed circuit, state
  restrictions, and machine verification;
- claim-to-evidence table and main artifact hashes.

Figures will be generated from frozen numerical values or from deterministic
source data embedded with explicit provenance.  Decorative figures will not
be used.

## File architecture

The manuscript will live under `docs/manuscript/` and remain separate from
the competition report:

```text
docs/manuscript/
  main.tex
  references.bib
  sections/
    abstract.tex
    introduction.tex
    problem.tex
    baseline.tex
    compiler.tex
    free_lie.tex
    pauli.tex
    norm_certificate.tex
    finite_step.tex
    verification.tex
    results.tex
    related_work.tex
    limitations.tex
    reproducibility.tex
    conclusion.tex
    appendices.tex
  figures/
  scripts/
  output/pdf/issue128-proof-carrying-trotter-paper.pdf
```

Each section file will have one clear responsibility.  The manuscript will
reference, but not duplicate or rewrite, the frozen JSON certificates.

## Evidence policy

Numerical claims must be sourced from one of:

- `certificates/issue128-certificate.json`;
- `certificates/issue128-d4-groups.json`;
- `certificates/issue128-d5-groups.json.gz`;
- `certificates/issue128-small-crosscheck.json`;
- `artifacts/issue128-summary.json`;
- `artifacts/verification-transcript.txt`; or
- the committed fivefold audit.

Literature claims require primary-source citations.  The bibliography will
cover the 2021 commutator-scaling baseline, model-specific bounds,
low-energy and average-case results, multi-product formulas, randomized
corrections, interpolation and error mitigation, optimized compositions,
ordering strategies, practical BCH estimation, and nested-commutator
compensation.

## Verification and quality gates

The manuscript is complete only when all of the following hold:

1. LaTeX compiles without errors, unresolved references, or unresolved
   citations.
2. The PDF has at least 15 substantive pages.
3. Every page is rendered to an image and visually checked for clipping,
   overlap, broken equations, illegible plots, and bad page breaks.
4. Automated text checks find no `TODO`, placeholder citation, or accidental
   fivefold certified claim.
5. All copied resource and error numbers match the frozen JSON artifacts.
6. The manifest-bound competition package still passes unchanged.
7. The final handoff identifies the manuscript as a local follow-up document,
   not as a post-deadline mutation of the judged PR.

## Non-goals

- Do not alter the frozen `4.050498x` certificate or its manifest.
- Do not claim an accepted `r=78` certificate.
- Do not invent multi-model numerical results that have not been computed.
- Do not present the current method as an asymptotic improvement over all
  Hamiltonian-simulation algorithms.
- Do not commit the unrelated in-progress HPC files as part of the paper.
