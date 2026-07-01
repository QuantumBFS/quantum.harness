---
name: physics-electron-phonon-coupling
description: Use when interpreting electron-phonon coupling and superconductivity results — alpha2F(omega), lambda, omega_log, McMillan/Allen-Dynes Tc, and the imaginary-frequency diagnostic. This card covers the mechanism and the interpretation rules that turn spectral evidence into a qualified Tc.
---

# Physics: electron-phonon coupling and superconductivity

Cross-model mechanism + interpretation card for electron-phonon superconductivity: it turns `alpha2F(omega)` into a qualified superconducting `Tc` estimate. The data-collection mechanics and the `alpha2f.x` failure-map / common-mistakes tables live in using-quantum-espresso; the convergence-comparison judgment lives in method-dfpt.

## Diagnose

The mechanism is electron-phonon coupling driving superconductivity, diagnosed through the Eliashberg spectral function `alpha2F(omega)` and the derived `lambda`, `omega_log`, and McMillan/Allen-Dynes `Tc`.

## Evidence to gather

The list of quantities to collect after `alpha2f.x` succeeds (`lambda`, `omega_log`, the `alpha2F(omega)` data file, the integration check, `Tc(mu*)`, imaginary-frequency status) lives with the data-collection mechanics. -> using-quantum-espresso "Phase 4 - Interpret results".

## Cross-checks

The full convergence-comparison set (q-grid, dense-k, structural sensitivity, direct-vs-integrated `alpha2F`) is method-dfpt "Convergence judgment". The imaginary-frequency diagnostic rows (`read_lam: Imaginary frequency`; reporting `Tc` after `alpha2f.x` reports imaginary frequencies) live in the using-quantum-espresso failure map and common-mistakes tables.

## Interpretation rules

Use this McMillan/Allen-Dynes form when the project does not specify another
convention:

```text
Tc = (omega_log / 1.2) *
     exp[-1.04 * (1 + lambda) /
         (lambda - mu_star * (1 + 0.62 * lambda))]
```

Convert `omega_log` to Kelvin before reporting `Tc`.

The convergence-qualified reporting rule — report `Tc` only with its q-grid, dense k-grid, structure, imaginary-frequency status, and remaining convergence caveats — is stated verbatim in the method-dfpt "Operating principle" block.

## Model hooks

-> concrete material/structure content in using-quantum-espresso/references/.
-> package mechanics, input keywords, failure map in using-quantum-espresso.
-> method understanding and convergence judgment in method-dfpt.
