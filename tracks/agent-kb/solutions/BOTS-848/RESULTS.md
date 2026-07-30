# Why the BOTS:848 Result Is Useful and Credible

This file is the short, human-readable argument. The complete derivation,
definitions, references, and limitations are in [`report/main.pdf`](report/main.pdf).
Exact reproduction commands are in [`REPRODUCE.md`](REPRODUCE.md).

## Result in One Sentence

Our testable hypothesis is that the leading error of static DFPT is organized
more directly by the low-energy operator changed by a phonon, the response in
that operator channel, and the relevant momentum and frequency than by the
material-wide label "strongly correlated."

This is a proposed organizing rule, not a theorem or a universal accuracy
bound.

## Physical Picture

DFPT lets the electronic density relax self-consistently around a chosen
ground-state reference while the ions are displaced. In its usual adiabatic
form this is a static response: the electrons are treated as following the
ionic displacement without resolving a frequency-dependent many-body vertex.
That description can work well, but it does not guarantee that every phonon
perturbation is renormalized in the same way.

The prototype first represents the projected DFPT perturbation as a Hermitian
operator `D` in a declared localized low-energy subspace and decomposes it as

```text
D = D_charge + D_internal + D_nonlocal.
```

- `D_charge` is proportional to the identity inside each local site block. It
  changes the average local potential without splitting orbitals in that block.
- `D_internal` is the traceless part inside a site block. It changes relative
  orbital or sublattice energies.
- `D_nonlocal` contains matrix elements between site blocks. It changes bonds,
  hopping, or other inter-site structure.

"Proportional to the local identity" does not mean that every Bloch band shifts
by the same number: different Bloch states have different local weights and
phases. It only states which operator is applied inside the declared local
subspace.

The working hypothesis is that a charge-dominated, adiabatic perturbation is a
better candidate for inexpensive static treatment, whereas appreciable
internal, nonlocal, interaction-parameter, or dynamic content signals the need
for a targeted correction or an abstention.

## Why This Is Useful

The result turns a vague question—"is this material too correlated for
DFPT?"—into a calculation-specific decision:

1. classify the phonon perturbation by operator channel;
2. verify that the electronic reference state and literature evidence are
   adequate;
3. test whether the electronic relaxation scale is separated from the phonon
   scale;
4. return `dfpt-safe`, `static-correction`, `dynamic-correction`, or `abstain`;
5. recommend the cheapest calculation that can falsify that decision.

This is useful even before a universal correction kernel exists. It can avoid
running an expensive dynamical or nonlocal method for every mode, while making
clear why a selected mode still needs such a method. The decision is expressed
in inspectable matrices, weights, evidence fields, and thresholds rather than
hidden in a material label or a language-model answer.

The repository supplies more than a narrative: a reusable agent workflow, a
typed claim ledger, machine-readable material cases, a dependency-free
reference implementation, transparent examples, and an executable evaluation.

## Why the Result Is Credible

Credibility has three separate levels. Passing one level does not prove the
next.

### 1. Exact mathematical and software checks

The tests verify that the implemented decomposition:

- reconstructs the input operator exactly;
- gives zero trace to every local internal block;
- preserves Hermiticity;
- gives channel weights invariant under local unitary basis rotations;
- returns the original DFPT operator when all channel kernels equal one;
- rejects malformed blocks, matrices, kernels, weights, and missing evidence.

These properties establish that the code implements its stated finite-matrix
model correctly. They do not establish that the model predicts every material.

### 2. Primary-source numerical evidence

The hypothesis was chosen because several qualitatively different calculations
line up with the channel and frequency distinction:

| Case | Same-paper comparison | What it supports | What it does not prove |
|---|---|---|---|
| uniform electron gas | close static DFPT-like and many-body vertices for `r_s = 1...5` and transfers through `2 k_F`, with the difficult region near backscattering | a scalar-density model can remain well described beyond the strict `q=0` conserved-charge limit | transferability to multi-orbital crystals |
| SrVO3 Jahn-Teller | 44 -> 87 meV | a traceless orbital-splitting mode can receive a large correction | that all internal modes behave identically |
| SrVO3 breathing | 58 -> 50 meV | a charge-like mode in the same material changes much less | exact protection of a finite-q charge mode |
| CaCuO2 half breathing | 70 -> 76 meV at `U = 3.1 eV` | a moderate static correction is possible in a correlated system | absence of dynamical effects |
| CaCuO2 full breathing | 53 -> 45 meV at `U = 3.1 eV` | the static value can remain close in the cited convention | a universal error bound |
| CaCuO2 dynamic case | within roughly one phonon-energy window at `U = 4.7 eV`, the reported coupling spans about zero to twice its zero-frequency value | a static comparison can miss the physical-frequency dependence | a universal dynamic threshold |
| CoO DFPT+U | ordinary DFPT and DFPT+U differ because the reference state and Hubbard occupation response change | the validity of the starting state must be checked before correcting its derivative | that one scalar kernel repairs a wrong reference state |
| Ba1-xKxBiO3 GWPT | the self-energy derivative supplies a nonlocal, energy-dependent correction route | a concrete beyond-DFT route exists when a local static model is insufficient | reducibility to the current three scalar kernels |

The values above retain the source observable and convention; they are not
silently converted into linewidths, mass-enhancement parameters, or differently
normalized matrix elements. Exact tables, figures, caveats, and citations are
recorded in `knowledge/material_cases.yaml` and `knowledge/references.bib`.

### 3. Scientific guardrails

Every knowledge claim is labeled as an exact constraint, numerical evidence, a
working hypothesis, or an open question. The decision gate abstains when the
source is not traceable, the reference electronic state is invalid, the
electronic relaxation scale is missing, or the perturbation signal is zero.
The Ward identity is used only for the conserved long-wavelength charge vertex;
it is not presented as a proof for generic finite-q orbital, bond, or phonon
vertices.

The recorded 14/14 evaluation checks this declared logic and its grounding. It
is a deterministic contract test, not an external-agent benchmark and not a
physical-accuracy measurement.

## What Is Not Yet Proven

The submission does not yet provide:

- fitted charge, internal, or nonlocal kernels with a held-out accuracy bound;
- an explicit interaction-modulation channel such as `dU/du` or `dJ/du`;
- coupling between operator channels;
- a production parser for DFPT or Wannier outputs;
- a universal value for the current decision thresholds;
- a held-out material benchmark demonstrating no significant loss of accuracy.

Therefore `dfpt-safe` means a **calibration candidate under the supplied
evidence**, not a guarantee that ordinary DFPT is quantitatively exact.

## Falsification Tests

The physical hypothesis must be revised or rejected if a controlled,
convention-matched benchmark finds any of the following:

1. channel weights do not correlate with the size or character of the
   beyond-DFPT correction;
2. charge-dominated, adiabatic modes repeatedly show large corrections not
   explained by the reference state or momentum path;
3. each matrix element needs an unrelated correction, so a small set of channel
   kernels has no predictive compression;
4. frequency dependence dominates broadly enough that no useful static regime
   remains.

The first final target is a held-out finite-momentum uniform-electron-gas test,
including the approach to `2 k_F`. It cleanly tests the scalar charge channel
before crystal-specific orbital, bond, and phonon-normalization complications
are introduced. A positive result there is necessary calibration evidence, not
sufficient proof for real materials.

## Bottom Line

The present result is useful as a transparent research triage and hypothesis-
testing framework. Its implementation and evidence bookkeeping are directly
reproducible; its physical organizing hypothesis is source-motivated and
falsifiable. Quantitative predictive accuracy remains the next experiment, and
the submission states exactly what result would count against it.
