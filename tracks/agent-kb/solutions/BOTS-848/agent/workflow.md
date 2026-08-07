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
- exactly one status: `established-theory`, `exact-constraint`,
  `numerical-evidence`, `working-hypothesis`, or `open-question`;
- `source_ids` and a location inside the source;
- scope: momentum, frequency, material, mode, and observable;
- limitations and normalization caveats;
- `source_traceable: true` only after the cited source actually supports the claim.

Numerical agreement is evidence, not an explanation. A proposed physical mechanism remains a `working-hypothesis` until a comparison separates it from alternatives.

## 3. Apply the Exact Limits Narrowly

For a conserved charge vertex, the Ward-Takahashi relation has the schematic form

`q_mu Gamma^mu(k+q,k) = G^{-1}(k+q) - G^{-1}(k)`.

The uniform dynamic limit relates the charge vertex to the frequency derivative of the self-energy. Ordinary adiabatic phonons follow a static path, so this limit does not prove universal DFPT accuracy. In a uniform electron gas, translational invariance diagonalizes the response in q; it does not remove finite q. Only rho(q=0) is the conserved total number, while Fermi-surface scattering spans 0 <= q <= 2 k_F. For the scalar convention used here, compare the complete screened vertices through

`K_total = z Gamma_rho [1 - (v + f_xc) chi_s] / [1 - v P_MB]`.

With `P_MB = chi_s / (1 - f_xc chi_s)` and
`z Gamma_rho = P_MB / chi_s`, this total ratio is approximately one. The UEG
result therefore supports the complete DFPT vertex in its calibration domain; it
does not supply `P_MB/chi_s` as a second factor to multiply onto screened DFPT.

## 4. Validate the Reference State

Set `reference_valid` only after checking that the underlying electronic state represents the intended phase. A derivative around a qualitatively wrong metal, insulator, magnetic state, or orbital order cannot be repaired reliably by multiplying the final electron-phonon matrix element. If the reference is not validated, return `abstain` and propose a reference-state correction first.

## 5. Decompose the Perturbation

Project a supported Hermitian self-consistent DFPT perturbation into an explicitly
declared orthonormal localized subspace. A general momentum-space derivative is
not itself Hermitian: `D(q)^dagger = D(-q)`. The executable API therefore accepts
only a real-space derivative, Gamma perturbation, or a real standing-wave
combination of `q` and `-q`.

For total basis size `N` and site block `I` of size `n_I`, define
`a = Tr(D)/N` and `a_I = Tr(D_II)/n_I`:

- `D_global_charge = a I_N`;
- `D_site_charge,II = (a_I - a) I_I`;
- `D_internal,II = D_II - a_I I_I`;
- `D_nonlocal` contains the off-site hopping and hybridization blocks.

These are mutually Hilbert--Schmidt orthogonal. Here `global_charge` is an
identity only inside the declared projection. It is a candidate for Ward
protection only when the original unprojected operator is independently verified
as a full-space common shift and `uniform_q_zero` is explicitly true. Fix the
energy-zero/chemical-potential convention before comparing weights.
`site_charge` represents relative site or sublattice density shifts and is not protected.

Use the target low-energy states as `basis_vectors` when available. The resulting weights measure which part of the operator the selected subspace samples. A common local operator can still give different band matrix elements because Bloch states have different orbital weights and phases.

Derivatives of `U`, `J`, or other interaction parameters are two-body vertices.
Record them in a separate future operator space rather than folding them into the
one-body Hilbert--Schmidt channels.

Before fitting, separate any analytic long-range polar field from the localized
short-range operator. Declare the operator basis explicitly; coefficient vectors
from different projectors, gauges, momenta, frequencies, or phonon normalizations
are not interchangeable anchors.

## 6. Select the Correction Level

Supply all of:

```json
{
  "source_traceable": true,
  "reference_valid": true,
  "adiabatic_ratio": 0.01,
  "uniform_q_zero": true,
  "full_space_common_shift": true
}
```

`adiabatic_ratio` is phonon energy divided by the relevant electronic relaxation energy. The reference thresholds are calibration choices:

| Decision | Minimum condition | Meaning |
|---|---|---|
| `dfpt-safe` | `global_charge` weight >= 0.80, correction-channel weight <= 0.20, adiabatic ratio < 0.10, `uniform_q_zero: true`, and `full_space_common_shift: true` verified before projection | Prioritize DFPT as a strict-common-shift calibration candidate and validate on held-out data. |
| `static-correction` | `site_charge` plus `internal` plus `nonlocal` weight > 0.20, adiabatic ratio < 0.10 | Estimate source-backed static one-body channel kernels. |
| `dynamic-correction` | adiabatic ratio >= 0.10 | Compare at the physical phonon frequency. |
| `abstain` | missing evidence (including strict `q=0` status for a nominally safe case), invalid reference, zero signal, or uncalibrated mixture | Acquire the named missing evidence first. |

These rules triage research effort. They are not accuracy bounds.

## 7. Fit and Test a Static Response Matrix

Only enter this step when the decision and evidence support a static correction.
The fitted target is the fixed-basis one-body inverse-Green-function vertex
`Lambda^(1) = -partial G^(-1)/partial u`, with the starting-point subtraction and
sign convention declared. Represent every anchor in the same declared operator basis and split anchors into
training and held-out sets before fitting. Use
`src.response_model.fit_response_matrix` for the training coefficient vectors and
`predict_coefficients` plus `error_metrics` for the held-out vectors.

Interpret the model as

`c_reference = K c_DFPT + residual`.

Diagonal entries of `K` rescale channels; off-diagonal entries mix them. This is a
low-dimensional working hypothesis, not a Ward-identity consequence and not a
claim that the full band-momentum vertex is low rank. Reject the static model if
held-out errors violate the predeclared tolerance or vary systematically with
momentum, frequency, or basis choice.

Do not absorb quasiparticle external-leg residues or state rotations into `K`.
Apply `Z^(1/2)` on the external legs and rotate to the declared quasiparticle
states only after the fixed-basis vertex is predicted. A UEG vertex including
external legs and a DFT+DMFT fixed-Wannier inverse-Green-function vertex are not
interchangeable training targets without an explicit convention conversion.

Use `src.cost_model.compare_corrected_to_baselines` to compare three explicitly
declared costs: DFPT alone at every target point, DFPT plus a higher-level
calculation at every point, and DFPT at every point plus sparse higher-level
anchors, fitting, and inference. The current response model still needs
`c_DFPT` at every predicted point, so it cannot be reported as faster than DFPT
alone. Its possible saving is relative to a dense higher-level correction.
Low channel dimension alone is not evidence of speed.
Unless actual matched-accuracy timing data were supplied, output:

```json
{
  "measured_runtime": false,
  "physical_accuracy_established": false
}
```

A synthetic held-out case validates software behavior only. A future surrogate
that also predicts the DFPT coefficients would need a separate implementation
and a measured comparison with converged, symmetry-reduced DFPT plus its normal
interpolation workflow.

## 8. Design One Discriminating Calculation

Hold material, geometry, q, phonon normalization, basis, and observable fixed. Change only the theoretical ingredient that represents the suspected missing channel. Examples include DFPT versus DFPT+U for occupation response, static versus frequency-dependent DMFT vertices, or DFPT versus GW perturbation theory for nonlocal self-energy response.

State both predictions before running the calculation. For example: if the
channel hypothesis is useful, the finite-R SrVO3 breathing mode represented in
the phase-correct 2x2x2 real supercell/standing-wave basis may change less than an
`internal` orbital-splitting mode under the same many-body treatment. This is a
same-setup empirical contrast, not Ward protection.

## 9. Report a Falsification Criterion

Every result must include a `falsification` field. Reject or revise the hypothesis if held-out tests show that:

- channel weights do not correlate with correction magnitude or sign;
- `site_charge`-dominated or other nonuniform density modes have large
  unexplained corrections;
- an independent kernel is needed for nearly every band-momentum element, eliminating compression; or
- dynamic corrections dominate so broadly that the static gate has no useful regime.

End with residual uncertainty and the next measurement needed to reduce it. Never turn `abstain` into a guessed physical conclusion.
