# Grounded DFPT Research Workflow

This is the detailed operating contract for `dfpt-channel-research-agent`. Its purpose is not to make every calculation look compatible with the working hypothesis. Its purpose is to find the smallest source-backed statement that the evidence permits and to design a calculation that could prove that statement wrong.

## 1. Freeze the Target

Record the following before comparing papers or numbers:

```json
{
  "material": "...",
  "phonon_mode": "...",
  "q_point": "...",
  "frequency_or_limit": "omega=0 or physical phonon frequency",
  "observable": "matrix element, deformation potential, linewidth, lambda, or transport rate",
  "electronic_reference": "DFT functional and any U, GW, or DMFT settings",
  "low_energy_basis": "projector or Wannier construction",
  "normalization": "units and phonon eigenvector convention"
}
```

Do not combine results that differ in any of these fields without an explicit conversion.

## 2. Build the Claim Ledger

Search the machine-readable records first, then consult the cited primary papers. For each claim record:

- `claim_id` and plain-language statement;
- exactly one status: `exact-constraint`, `numerical-evidence`, `working-hypothesis`, or `open-question`;
- `source_ids` and a location inside the source;
- scope: momentum, frequency, material, mode, and observable;
- limitations and normalization caveats;
- `source_traceable: true` only after the cited source actually supports the claim.

Numerical agreement is evidence, not an explanation. A proposed physical mechanism remains a `working-hypothesis` until a comparison separates it from alternatives.

## 3. Apply the Exact Limits Narrowly

For a conserved charge vertex, the Ward-Takahashi relation has the schematic form

`q_mu Gamma^mu(k+q,k) = G^{-1}(k+q) - G^{-1}(k)`.

The uniform dynamic limit relates the charge vertex to the frequency derivative of the self-energy. Ordinary adiabatic phonons follow a static path, so this limit does not prove universal DFPT accuracy. In a uniform electron gas, translational invariance diagonalizes the response in q; it does not remove finite q. Only rho(q=0) is the conserved total number, while Fermi-surface scattering spans 0 <= q <= 2 k_F.

## 4. Validate the Reference State

Set `reference_valid` only after checking that the underlying electronic state represents the intended phase. A derivative around a qualitatively wrong metal, insulator, magnetic state, or orbital order cannot be repaired reliably by multiplying the final electron-phonon matrix element. If the reference is not validated, return `abstain` and propose a reference-state correction first.

## 5. Decompose the Perturbation

Project the self-consistent DFPT perturbation into an explicitly declared orthonormal localized subspace. For site block `I`:

- `D_charge,II = Tr(D_II) / n_I` times the identity;
- `D_internal,II = D_II - D_charge,II`;
- `D_nonlocal` contains the off-site hopping and hybridization blocks.

Use the target low-energy states as `basis_vectors` when available. The resulting weights measure which part of the operator the selected subspace samples. A common local operator can still give different band matrix elements because Bloch states have different orbital weights and phases.

The three-channel prototype does not yet represent derivatives of U, J, or other interaction parameters. Record such a contribution as missing evidence rather than folding it into an unrelated channel.

## 6. Select the Correction Level

Supply all of:

```json
{
  "source_traceable": true,
  "reference_valid": true,
  "adiabatic_ratio": 0.01
}
```

`adiabatic_ratio` is phonon energy divided by the relevant electronic relaxation energy. The reference thresholds are calibration choices:

| Decision | Minimum condition | Meaning |
|---|---|---|
| `dfpt-safe` | charge weight >= 0.80, other weight <= 0.20, adiabatic ratio < 0.10 | Prioritize DFPT and validate on held-out data. |
| `static-correction` | internal plus nonlocal weight > 0.20, adiabatic ratio < 0.10 | Estimate source-backed static channel kernels. |
| `dynamic-correction` | adiabatic ratio >= 0.10 | Compare at the physical phonon frequency. |
| `abstain` | missing evidence, invalid reference, zero signal, or uncalibrated mixture | Acquire the named missing evidence first. |

These rules triage research effort. They are not accuracy bounds.

## 7. Design One Discriminating Calculation

Hold material, geometry, q, phonon normalization, basis, and observable fixed. Change only the theoretical ingredient that represents the suspected missing channel. Examples include DFPT versus DFPT+U for occupation response, static versus frequency-dependent DMFT vertices, or DFPT versus GW perturbation theory for nonlocal self-energy response.

State both predictions before running the calculation. For example: if channel-selective protection is correct, a charge-dominated breathing mode should change less than a traceless orbital-splitting mode under the same many-body treatment.

## 8. Report a Falsification Criterion

Every result must include a `falsification` field. Reject or revise the hypothesis if held-out tests show that:

- channel weights do not correlate with correction magnitude or sign;
- charge-dominated modes have large unexplained corrections;
- an independent kernel is needed for nearly every band-momentum element, eliminating compression; or
- dynamic corrections dominate so broadly that the static gate has no useful regime.

End with residual uncertainty and the next measurement needed to reduce it. Never turn `abstain` into a guessed physical conclusion.
