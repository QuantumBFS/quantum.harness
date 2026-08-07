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

The prototype first represents a supported Hermitian DFPT perturbation as a
one-body operator `D` in a declared localized low-energy subspace and decomposes
it as

```text
D = D_global_charge + D_site_charge + D_internal + D_nonlocal.
```

- `D_global_charge` is the single identity component across the complete declared
  projection basis. It is an algebraic label, not by itself the full-system
  conserved total-charge direction.
- `D_site_charge` contains block-identity shifts relative to the global average.
  It changes relative site or sublattice potentials without splitting orbitals
  inside a block.
- `D_internal` is the traceless part inside a site block. It changes relative
  orbital energies within that block.
- `D_nonlocal` contains matrix elements between site blocks. It changes bonds,
  hopping, or other inter-site structure.

The four components are mutually orthogonal in the Hilbert--Schmidt inner
product. Only `global_charge` can be protected, and only when the original
unprojected operator is independently verified as a strict uniform `q=0`
full-space common shift under a fixed energy-zero/chemical-potential convention.
The condition `P_c D P_c` proportional to identity is not sufficient because the
discarded and cross-subspace blocks can differ. `site_charge`, `internal`, and `nonlocal` are all correction
risk channels. "Proportional to a block identity" does not mean that every Bloch band shifts
by the same number: different Bloch states have different local weights and
phases. It only states which operator is applied inside the declared local
subspace.

The current Hermitian API applies to a real-space displacement derivative, a
Gamma perturbation, or a real standing-wave combination of `q` and `-q`. For a
general fixed momentum, `D(q)^dagger = D(-q)`; a continuous finite-`q` paired
interface has not been implemented.

The working hypothesis is that a verified full-space uniform `q=0`
`global_charge` perturbation is the exact control, whereas appreciable `site_charge`, `internal`,
`nonlocal`, or dynamic content signals the need for a targeted correction or an
abstention. Derivatives such as `dU/du` and `dJ/du` are two-body vertices in a
separate operator space, not extra pieces of this one-body decomposition.

The quantitative MVP assumes that a fixed localized, symmetry-adapted one-body
operator basis has already been declared. If `c_DFPT` and `c_reference` are
coefficients of the DFPT and reference inverse-Green-function vertices in that
same basis, it fits a small response matrix `K`:

```text
c_reference = K c_DFPT + residual.
```

This is a coefficient-space hypothesis, not a claim that the complete
electron-phonon matrix is low rank. Diagonal entries rescale a channel;
off-diagonal entries allow channel mixing. External-leg factors `Z^(1/2)` and
quasiparticle-state rotations are applied separately before comparing a physical
scattering observable. Anchors from papers that use different vertex conventions
cannot be mixed without an explicit conversion.

## Why This Is Useful

The result turns a vague question—"is this material too correlated for
DFPT?"—into a calculation-specific decision:

1. classify the supported one-body perturbation as `global_charge`,
   `site_charge`, `internal`, and `nonlocal`, while recording any separate
   two-body vertex;
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

## When It Can Be Faster

The present correction layer is **not faster than a single DFPT calculation**.
It needs `c_DFPT` at every prediction point and adds fitting and reconstruction.
Its immediate computational target is instead to replace a dense set of
beyond-DFPT vertices with a small number of higher-level anchors:

```text
DFPT only       = campaigns * full grid * DFPT cost
dense reference = campaigns * full grid * (DFPT + high-level cost)
corrected path  = training + high-level anchors
                + campaigns * full grid * (DFPT + inference cost).
```

For the bundled normalized assumptions these costs are `100.000`, `600.000`,
and `122.000`. Thus the dense higher-level path costs `4.918` times as much as the
corrected path, while the corrected path costs `22.000` more than DFPT alone.
This is an accounting example, not a measured runtime result. Beating DFPT itself
would require a separate surrogate that predicts the missing DFPT coefficient
vectors and must be tested against symmetry-reduced DFPT plus Wannier/EPW
interpolation.

## Why the Result Is Credible

Credibility has three separate levels. Passing one level does not prove the
next.

### 1. Exact mathematical and software checks

The tests verify that the implemented decomposition:

- reconstructs the input operator exactly;
- separates the global identity from relative block-identity shifts;
- makes the four one-body channels mutually Hilbert--Schmidt orthogonal;
- gives zero trace to every local internal block;
- preserves Hermiticity;
- gives channel weights invariant under local unitary basis rotations;
- returns the original DFPT operator when all channel kernels equal one;
- recovers identity and off-diagonal response matrices from sufficient anchors;
- predicts the bundled synthetic held-out coefficient vectors to floating-point
  precision;
- reports whether a sparse higher-level correction beats a dense higher-level
  reference and separately reports its overhead relative to DFPT alone;
- rejects malformed blocks, matrices, kernels, weights, and missing evidence.

These properties establish that the code implements its stated finite-matrix
software model correctly. They do not establish a real-material response matrix
or any physical prediction.

The synthetic held-out example gives relative RMSE `2.653e-16` because its
targets were generated exactly from a declared synthetic matrix. It verifies
the fit-predict-score path and nothing about physical transferability. Its three
coefficients are `global_charge`, `internal`, and `nonlocal`;
`site_charge` is not excited, so it is not a full four-channel physical test.

### 2. Primary-source numerical evidence

The hypothesis was chosen because several qualitatively different calculations
line up with the channel and frequency distinction:

| Case | Same-paper comparison | What it supports | What it does not prove |
|---|---|---|---|
| uniform electron gas | close complete static DFPT-like and many-body vertices for `r_s = 1...5` and transfers through `2 k_F`, with backscattering the least-controlled exception | the total ratio `K_total = z Gamma_rho [1-(v+f_xc)chi_s]/[1-v P_MB]` is approximately one in that calibration domain | a second `P_MB/chi_s` correction to screened DFPT or transferability to multi-orbital crystals |
| SrVO3 Jahn-Teller | 44 -> 87 meV | a traceless orbital-splitting mode can receive a large correction | that all internal modes behave identically |
| SrVO3 breathing | 58 -> 50 meV | in the cited 2x2x2 real-displacement supercell/standing-wave representation, the R-point phase alternation makes this a finite-q `site_charge`-like mode that changes much less | classification from a single primitive-cell `diag(g,g,g)` block, `global_charge` protection, or any general finite-q theorem |
| CaCuO2 half breathing | 70 -> 76 meV at `U = 3.1 eV` | a moderate static correction is possible in a correlated system | absence of dynamical effects |
| CaCuO2 full breathing | 53 -> 45 meV at `U = 3.1 eV` | the static value can remain close in the cited convention | a universal error bound |
| CaCuO2 dynamic case | within roughly one phonon-energy window at `U = 4.7 eV`, the reported coupling spans about zero to twice its zero-frequency value | a static comparison can miss the physical-frequency dependence | a universal dynamic threshold |
| CoO DFPT+U | ordinary DFPT and DFPT+U differ because the reference state and Hubbard occupation response change | the validity of the starting state must be checked before correcting its derivative | that one scalar kernel repairs a wrong reference state |
| Ba1-xKxBiO3 GWPT | the self-energy derivative supplies a nonlocal, energy-dependent correction route | a concrete beyond-DFT route exists when a local static model is insufficient | reducibility to the current four one-body channels |

The Abramovitch rows are same-paper controls within its declared fixed basis and
many-body setup; they are not independent cross-code accuracy benchmarks. The
values above retain the source observable and convention; they are not
silently converted into linewidths, mass-enhancement parameters, or differently
normalized matrix elements. Exact tables, figures, caveats, and citations are
recorded in `knowledge/material_cases.yaml` and `knowledge/references.bib`.

### 3. Scientific guardrails

Every knowledge claim is labeled as established theory, an exact constraint,
numerical evidence, working hypothesis, or open question. The decision gate abstains when the
source is not traceable, the reference electronic state is invalid, the
electronic relaxation scale is missing, the perturbation signal is zero, or a
`global_charge` input is not explicitly verified as a uniform `q=0` full-space
common shift before projection. The Ward identity is used only for that strict conserved-charge control;
it is not presented as a proof for generic finite-q orbital, bond, or phonon
vertices.

The recorded 82 unit tests and 14/14 evaluation, the synthetic RMSE, and the
normalized cost ratio check declared software logic and grounding. They are not
external-agent or material benchmarks, do not determine a real-material `K`, and
do not establish physical accuracy or measured acceleration.

## What Is Not Yet Proven

The submission does not yet provide:

- a response matrix fitted to convention-matched real-material DFPT and
  beyond-DFPT anchors;
- a separate two-body operator-space implementation for `dU/du` or `dJ/du`;
- a paired `q/-q` interface for a general finite-momentum perturbation;
- a production parser for DFPT or Wannier outputs;
- a universal value for the current decision thresholds;
- a held-out material benchmark demonstrating no significant loss of accuracy;
- a measured speed comparison with a converged DFPT plus interpolation baseline.

Therefore `dfpt-safe` means a **calibration candidate under the supplied
evidence**, not a guarantee that ordinary DFPT is quantitatively exact.

## Falsification Tests

The physical hypothesis must be revised or rejected if a controlled,
convention-matched benchmark finds any of the following:

1. channel weights do not correlate with the size or character of the
   beyond-DFPT correction;
2. `site_charge`-dominated or other nonuniform density modes repeatedly show
   large corrections not captured by the fitted response;
3. each matrix element needs an unrelated correction, so a small set of channel
   kernels has no predictive compression;
4. frequency dependence dominates broadly enough that no useful static regime
   remains.

The first final target is a held-out finite-momentum uniform-electron-gas test of
the complete physical-to-DFPT ratio, including the approach to `2 k_F`. It tests
whether the complete screened DFPT vertex remains accurate in that scalar-density
domain; it does not validate multiplying screened DFPT by a separate proper-vertex
factor. Until a paired `q/-q` or real-space interface exists, this is a theory/data
calibration rather than an executable continuous-fixed-`q` result. A positive
result is necessary calibration evidence, not sufficient proof for real materials.

## Bottom Line

The present result is a transparent research triage framework plus a quantitative
software MVP: it can fit, predict, score, and account for cost in a declared
channel basis. Its implementation and evidence bookkeeping are reproducible;
real-material predictive accuracy and measured acceleration remain the next
experiments, and the submission states exactly what would count against them.
