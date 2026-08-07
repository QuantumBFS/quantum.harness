# Ranger — Neural Graviton Landscape

## Team and challenge

| Field | Value |
|---|---|
| Team | Ranger |
| Members | Chenxi Wan, Yedi Shen, Junkai Wang |
| Challenge | `Addresses #15` — [Symmetric neural-network ansatz for the chiral graviton at nu = 1/3](https://github.com/QuantumBFS/quantum.harness/issues/15), released by Lei Wang (Institute of Physics, CAS) |
| Track | `qmc` — Variational Monte Carlo / Neural Quantum States |
| Public research repository | [`JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton`](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/tree/codex/neural-graviton-paper) |
| Manuscript | [Neural Graviton Landscape (PDF)](https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/blob/codex/neural-graviton-paper/paper/neural-graviton-microscope/neural-graviton-landscape.pdf) |
| License | AGPL-3.0-only |

Ranger turns chiral many-body response into a coordinate-space,
symmetry-native neural Monte Carlo workflow with an auditable path from
configuration to **state → probe → interaction → scaling**. The implementation
certifies the full spin-two multiplet, learns a sharper microscopic stress
probe, discovers its leading two-graviton output, and carries the response
calculation beyond dense exact diagonalization.

![Neural Graviton Microscope](https://raw.githubusercontent.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton/codex/competition-showcase/results/competition_showcase/final/showcase.svg)

## Headline certificates

| Result | Certificate |
|---|---:|
| `N=4` strict-LLL graviton gap | `0.13185675492702376` |
| maximum dense-oracle difference | `2.66e-15` |
| five-state multiplet dimension | `5` |
| maximum `L^2` error | `6.22e-15` |
| maximum multiplet energy spread | `4.44e-16` |
| `N=8` direct coordinate tangent | `0.1396847 +/- 0.0005706` |
| `N=8` stochastic one-mode frequency | `0.1399489 +/- 0.0008219` |
| independent-estimator agreement | `0.264` combined standard errors |
| neural closure leakage | `0.499178073 -> 1.9864e-7` |
| finite-size nonlinear coupling | `g_224=-0.419946827` |

The `N=4` strict-LLL neural irrep gives

```text
E(L=0) = 1.8711384121456025
E(L=2) = 2.0029951670726263
Delta   = 0.13185675492702376
```

Fermionic antisymmetry and rotational covariance are exact architectural
invariants.  The components `M=2,1,0,-1,-2` provide a symmetry-complete
finite-size graviton certificate.

## Five linked algorithmic advances

### 1. Symmetry-native shared neural state

One shared ground/tangent parameterization preserves exchange antisymmetry and
rotational covariance by construction. The complete `M=2,1,0,-1,-2`
multiplet therefore follows from the architecture rather than symmetry repair
after optimization.

### 2. Projector-free strict-LLL tangent VMC

The coordinate backend applies the holomorphic quadrupole directly to the
many-electron wave function with an `O(N^2)` generator.  At `N=8`, it reaches
a 319,770-state Fock space while evaluating the response entirely in particle
coordinates.  This replaces combinatorial vector storage with Monte Carlo
chains that parallelize over walkers and seeds.

### 3. Covariance-preserving common-bridge geometry estimator

Ground and tangent states share the mixture

```text
q(R) proportional to |Psi_0(R)|^2 + alpha |Psi_T(R)|^2.
```

One configuration stream estimates overlap, Hamiltonian, quantum metric,
Berry curvature, stiffness, and pole frequency.  Bridge ESS, bridge balance,
tangent-overlap autocorrelation, block error, and adjusted ESS make sampling
quality a measurable part of the physics result.

### 4. Target-free microscopic operator discovery

A permutation-shared neural Casimir filter trains exclusively on overlap and
first/second Hamiltonian moments.  It removes `54.76%` of non-dominant weight
at `N=4` and `37.32%` at `N=5`, with metric fidelities `0.998389` and
`0.994852`.  Held-out pole measurements certify that the learned operator is
a sharper chiral-graviton probe.

Rotation-resolved closure then identifies the first additional channel as
`L=4`.  Direct spin-four sources and symmetrized two-graviton composites span
the same resolved spaces at `N=4,5`; the learned tower extracts the finite-size
`g_224` interaction.

### 5. Outcome-complete higher-dimensional scaling

Direct complex-wave-function VMC encodes exchange and magnetic phase in
`Psi_theta` while sampling the positive density

```text
p_theta(R) = |Psi_theta(R)|^2 / Z_theta.
```

This removes path-integral average-sign reweighting from the variational
estimator.  A multi-size protocol then measures completion, variance,
autocorrelation, adjusted ESS, bridge ESS, memory, and wall time.

The production campaign preregisters 80 `N=10,12` chains. Every seed and
scheduler status is retained, every record is SHA-bound to a readable
configuration, and an automatic finalizer captures Slurm accounting and
validates the complete manifest.  Independent `N=4,8` anchors use the same
record contract.

## Why the new stack reaches farther

1. **Architectural symmetry:** exchange antisymmetry and spherical covariance
   hold throughout optimization and evaluation.
2. **Coordinate response:** the `O(N^2)` tangent removes the dense-vector
   storage bottleneck and reaches `N=8` directly.
3. **Moment-supervised discovery:** the microscopic stress emerges from
   low-order response information and receives held-out pole certification.
4. **Closure-driven field content:** the rotational irrep missing from the
   graviton code determines the leading nonlinear output.
5. **Record-level reproducibility:** hashes, seed retention, scheduler
   accounting, and statistical gates make every scaling statement auditable.

## Evidence and reproduction

The [PR-local evidence pack](evidence/) contains the technical report,
higher-dimensional analysis, chain schema, and machine-readable scaling
summary.  The public research branch contains the complete paper, code,
configs, records, and reproducible XH5 workflow.

```bash
git clone --recurse-submodules \
  --branch codex/neural-graviton-paper \
  https://github.com/JunkaiWang-TheoPhy/symmetric-neural-network-ansatz-chiral-graviton.git
cd symmetric-neural-network-ansatz-chiral-graviton
uv sync --frozen

uv run pytest -q \
  tests/test_fermion_scaling_schema.py \
  tests/test_build_fermion_scaling_report.py \
  tests/test_render_pr262_sign_response.py
uv run python scripts/audit_neural_graviton_citations.py
uv run python scripts/build_neural_graviton_paper.py
```

## Promising research trajectory

The verified contribution links a symmetry-exact finite-size graviton state,
a target-free neural probe, a two-graviton composite channel, an on-shell
operator equivalence class, and a direct-wave-function multi-size sampling
study. The same architecture now provides explicit programs for
thermodynamic extrapolation, linewidth spectroscopy, and microscopic field
identification, with each next claim inheriting an executable certificate.

## Reviewer checklist

- [ ] Reproduce the strict-LLL `N=4` energy and five-state multiplet.
- [ ] Inspect the `O(N^2)` coordinate tangent and independent `N=8` agreement.
- [ ] Confirm that the neural-probe training inputs are overlap and moments.
- [ ] Inspect the spin-two/spin-four closure and `g_224` extraction.
- [ ] Validate the chain/config SHA bindings and seed-preserving report.
- [ ] Read the APS-style manuscript and PR-local technical evidence.
