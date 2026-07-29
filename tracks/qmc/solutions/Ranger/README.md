# Ranger — completed challenge #15 submission

## Team

| Field | Value |
|---|---|
| Team | Ranger |
| Members | Chenxi Wan, Yedi Shen, Junkai Wang |
| Challenge | [#15 — Symmetric neural-network ansatz for the chiral graviton at ν = 1/3](https://github.com/QuantumBFS/quantum.harness/issues/15) |
| Track | `qmc` — from the issue's `Variational Monte Carlo / Neural Quantum States` method |
| Public implementation | [`JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton`](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/tree/codex/competition-showcase) |
| License | AGPL-3.0-only |

This is the completed public submission rather than a registration-only
placeholder.  It addresses the challenge's symmetry and finite-size gap
requirements, then extends the neural calculation into a controlled
state-to-probe-to-interaction discovery pipeline.

![Neural Graviton Microscope: state, probe, interaction, and identifiability boundary](https://raw.githubusercontent.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/codex/competition-showcase/results/competition_showcase/final/showcase.svg)

## Challenge

Can an exchange-antisymmetric, SO(3)-equivariant neural quantum state find the
ν = 1/3 chiral graviton on the Haldane sphere, certify its spin-two multiplet,
and learn which microscopic probe and leading nonlinear output belong to that
mode?

The headline observable is

```text
Δ = E(L=2) − E(L=0)
```

in units of `e²/(εℓ_B)` at flux `2Q = 3(N−1)`.

## Primary acceptance: catch the state

The controlled `N=4`, strict-lowest-Landau-level neural irrep gives

```text
E(L=0) = 1.8711384121456025
E(L=2) = 2.0029951670726263
Δ       = 0.13185675492702376
```

The maximum absolute difference from dense exact diagonalization is
`2.66e-15`.  Fermionic antisymmetry and rotational covariance are exact by
construction.  The five components `M = 2, 1, 0, −1, −2` satisfy:

| Certificate | Result |
|---|---:|
| multiplet dimension | 5 |
| target `⟨L²⟩` | 6 |
| maximum `⟨L²⟩` error | `6.22e-15` |
| maximum energy spread | `4.44e-16` |

This is a symmetry-complete small-system neural prototype and a controlled
finite-size result.  The full irrep basis uses the complete `N=4` Hilbert
space, so it is not presented as the beyond-ED scaling method or as a
thermodynamic gap extrapolation.

## Neural Graviton Microscope

### 1. Learn the microscopic probe

A permutation-shared neural Casimir filter is trained from overlap and first
and second Hamiltonian moments.  No target eigenvector, exact pole residue,
experimental peak, or full-sector eigensystem enters its loss.

| System | Bare non-dominant weight | Neural weight | Removed | Metric fidelity |
|---:|---:|---:|---:|---:|
| `N=4` | 0.0148821 | 0.00673337 | 54.76% | 0.998389 |
| `N=5` | 0.0906955 | 0.0568488 | 37.32% | 0.994852 |

An independent two-copy circular-operator calculation at `N=4` gives
chirality contrast `−0.996955`.  Chirality is not inferred from the unsigned
angular-momentum label or from magnetic quantum number `M`.

### 2. Learn the leading nonlinear output

The spin-two operators fail to close on a multistate graviton code.  Rotation
symmetry identifies the first missing representation as `L=4`.  Direct
spin-four sources and symmetrized two-graviton composites span the same
finite-size space:

| System | Direct rank | Two-graviton rank | Direct-unique rank | Minimum subspace cosine |
|---:|---:|---:|---:|---:|
| `N=4` | 3 | 3 | 0 | `1 − 2.64e-14` |
| `N=5` | 6 | 6 | 0 | `1 − 1.98e-14` |

Every resolved exact `L=4` pole has unit composite coverage to the recorded
precision.  A shared-trunk neural spin-two/spin-four operator tower then
reduces two-graviton closure leakage from

```text
0.499178073 → 1.9864e-7
```

and learns a normalized finite-size `g₂₂₄ = −0.419946827` prototype without
putting exact excited states into the loss.

### 3. Certify the identifiability boundary

Two distinct microscopic orderings become indistinguishable after restriction
to every tested low-energy graviton code,

```text
minimum on-shell subspace cosine = 0.999999999999999,
```

but generic off-shell Fock-state probes separate them,

```text
minimum off-shell subspace cosine = 0.001970776.
```

The neural learner can therefore identify an on-shell effective-operator
equivalence class, but a single-code loss cannot select a unique microscopic
ordering.  This is an information-theoretic boundary of the supplied
low-energy data, not a failure remediable by increasing network size.

## Evidence and reproduction

The competition-facing artifact is fail-closed: it reads seven frozen source
summaries, checks every native or explicit legacy verification gate, records
their SHA-256 digests, rejects claims beyond each source's capability, and
only then renders the report and figure.

```bash
git clone --recurse-submodules \
  --branch codex/competition-showcase \
  https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton.git
cd symmetric-neural-network-ansatz-chiral-graviton
uv sync --frozen

uv run python scripts/run_competition_showcase.py \
  configs/competition_showcase.json --overwrite
uv run python scripts/run_competition_checks.py
```

Review anchors:

- [competition narrative and 15-minute presentation map](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/competition-showcase/docs/competition-showcase.md)
- [machine-readable verified summary](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/competition-showcase/results/competition_showcase/final/summary.json)
- [generated report](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/competition-showcase/results/competition_showcase/final/report.md)
- [fail-closed collector](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/competition-showcase/src/chiral_graviton/showcase.py)
- [focused claim regression](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/competition-showcase/scripts/run_competition_checks.py)

## Validation

- competition-focused state/probe/interaction/identifiability regression:
  `65 passed`;
- showcase collector and runner tests: `14 passed`;
- higher-spin bootstrap and neural-tower tests: `8 passed`;
- clean-clone dependency installation, artifact generation, and verification:
  passed;
- two consecutive renders produced identical Markdown and SVG SHA-256
  digests;
- the Harness repository test command reached `234 passed, 9 skipped`, with
  one unrelated environment failure in
  `test_shim_refuses_to_overwrite_runner_copy` because Julia is not installed;
- `git diff --check`: clean.

The 65-test command is deliberately labeled a competition-claim regression;
it is not represented as the repository's complete scientific test suite.

## Scope boundary

This submission claims a controlled finite-size graviton state, a target-free
neural probe improvement, a finite-size two-graviton composite channel, and
an on-shell identifiability result.  It does **not** claim:

- a thermodynamic graviton gap or thermodynamic effective field theory;
- a physical linewidth or irreversible lifetime from a discrete spectrum;
- an elementary spin-four particle;
- a unique microscopic operator ordering;
- an automatically inferred parton count.

The scalable coordinate-space shared NQS and `N=8` response calculations are
included in the public research repository, but they are kept separate from
the exact `N=4` acceptance claim.

## Reviewer checklist

- [ ] Confirm the strict-LLL state is exactly antisymmetric and SO(3)
      covariant.
- [ ] Confirm all five `L=2` components have `⟨L²⟩ = 6` and degenerate
      energy.
- [ ] Reproduce the cached fail-closed showcase and its source digests.
- [ ] Check that the neural-probe loss contains no target-pole information.
- [ ] Inspect direct versus two-graviton `L=4` ranks at `N=4,5`.
- [ ] Confirm the on-shell/off-shell ordering distinction and all explicit
      non-claims.
