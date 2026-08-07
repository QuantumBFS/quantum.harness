# Mathematical and provenance contract

## Figure 1 three-level perfect-blockade model

Figure 1 uses the seven-state perfect-blockade reduction of two identical
three-level atoms. The computational indices are |00⟩, |01⟩, |10⟩, |11⟩;
the leakage partners are |0r⟩, |r0⟩, and
|W⟩=(|1r⟩+|r1⟩)/√2. The |rr⟩ state is excluded.

In units where the Rabi amplitude is one,

`H(t)=½ Σj [Ω̃(t)|r⟩j⟨1|+Ω̃*(t)|1⟩j⟨r|]`.

The single-excitation sectors have coupling Ω̃/2 and the |11⟩↔|W⟩ sector
has coupling √2 Ω̃/2. The published analytic ansatz is

`Ω̃(t)=exp[iφ(t)]`,

`φ(t)=A cos(ωt−φ₀)+δ₀t`,

with `A=2π×0.1122`, `ω=1.0431`, `φ₀=−0.7318`, `δ₀=0`, and
`T=2π×1.215`.

After eliminating the symmetric correctable local-Z phase, the leading
infidelity contains two complex leakage channels and one real controlled-phase
channel. Its real Hessian rank is therefore five. Figure 1(g) is a mechanistic
reconstruction from the computed two-cycle Hessian trajectory, explicitly
labelled as such because the corresponding experimental trajectory was not
published; the combined output contains panels a–i.

## Closed-system theory

The ideal model is the 10-dimensional perfect-blockade reduction in the
ordered basis

`|00>, |W'>, |01>, |0r>, |r'1>, |10>, |r0>, |1r'>, |11>, |W>`.

With time in μs and angular frequency in rad/μs,

`H(t)=+Δr Πr' + ½[Ω(t)σ+ + Ω*(t)σ-]`,

where `Ω₀=2π×6.0`, `Δr=2π×16.1`, `T=0.55`, and

`σ+=|0r><01|−|r'1><01|+|r0><10|−|1r'><10|`
`   −√2|W'><00|+√2|W><11|`.

This model has no double-Rydberg state and therefore no finite blockade,
decay, Doppler shift, laser noise, or MQDT pair-state physics.

## Propagation contract

The fixed-grid route composes exact matrix exponentials evaluated at interval
midpoints. The independent route uses adaptive SciPy DOP853. Uniform grids
contain 101, 201, and 401 time nodes. Acceptance requires:

- Hamiltonian Hermiticity residual below `1e-12`;
- propagator unitarity residual below `1e-10`;
- JAX/NumPy normalized unitary difference below `1e-10`;
- midpoint error ratios consistent with second order.

## Fidelity contract

For the projected computational block `M=V† P U P`,

`Favg=(|Tr M|²+Tr(MM†))/20`.

The code reports:

1. fixed `V=diag(1,1,1,−1)`;
2. a symmetric virtual-Z determined once at nominal intensity and then fixed;
3. a pointwise symmetric virtual-Z removal, explicitly called
   CZ-equivalent/echoed.

Local-Z diagnostics contain the two single-excitation phases, their
difference, their circular mean/resultant, and a return-amplitude stability
flag. The nonlinear CZ residual uses the normalized complex invariant
`−A11 A00 (A01 A10)*`, reporting both its imaginary part and
`1−Re`, so the false sine root is excluded. Infidelity and leakage are never
clipped; excursions beyond the declared floating-point tolerance fail.

## Equivalent control optimization

The default backend uses 16 cubic B-spline coefficients for each amplitude
and phase channel. Four amplitude coefficients are eliminated to impose zero
amplitude and slope at both endpoints; the phase gauge fixes one coefficient.
An optional direct time-bin backend uses the same endpoint constraints.

The sequence is coarse nominal optimization, coarse AR channel solve,
fine-grid AR polish, then fine-grid feasible-manifold smoothing. Default seeds
are a smooth constant-envelope/simple-phase seed plus random smooth seeds.
The paper-shaped seed is diagnostic-only and disabled by default.

The root contains four complex nominal leakage amplitudes, branch-safe
nonlinear CZ phase residuals, four complex derivatives of terminal leakage
under global field-amplitude scaling, and the nonlinear phase derivative.
The symmetric local-Z derivative is not zeroed in the echoed root but is
reported, together with fixed-Z and echoed fidelity curvatures.

The authors' pulse array, initial values, regularization weights, and optimizer
details are not public. All resulting pulses are therefore classified as
equivalent numerical reoptimization.

## Hessian contract

The default paper coordinate system is additive tapered laboratory I/Q:

`Ωdist(t)=Ωideal(t)+|Ωideal(t)|[sx(t)+i sy(t)]`.

The diagnostic local frame is
`Ωdist=Ωideal(1+sx+i sy)`. In the continuous limit the two frames are related
by a time-dependent orthogonal rotation; finite constant bins are not assumed
to be identical.

Appendix C is implemented as

`1−F=½α00+α01+½α11+εθ`,

`εθ=(θ01−θ11/2)²/5+θ11²/10`.

The code reports signed eigenvalues, the first 14 modes, `λ10/|λ11|`, minimum
eigenvalue, PSD violation, several numerical rank tolerances, multiple bin/node
resolutions, both quadratures of all ten principal modes, and the four channel
contributions. Finite differences use `+ε` and `−ε` for four ε values, test
modes 1–14 and random null combinations, and retain negative/raw results.

## Synthetic and experimental boundary

The synthetic AOM is a declared plant model. Calibration updates the command,
passes it through the plant, and compares a Hessian quadratic prediction with
full Schrödinger propagation. Scan ranges may use curvature, hardware bounds,
shot statistics, and previous fit uncertainty, but never the hidden
distortion. All ideal, command, before/after output, correction, represented
distortion, and unrepresented additive residual arrays are serialized
consistently.

Experimental panels accept raw CSV inputs through separate contracts. With no
raw input they remain unavailable. Figure 4(f) is a literal Appendix-E
transcription; an independent simulation requires the unpublished pulse,
MQDT pair-state data, decay branching, thermal position distribution, and
laser phase/amplitude noise spectra.

## Microscopic-input contract

Schema-v2 `input.in` records the physical metadata and external arrays needed
to extend the Appendix-C effective model: explicit atomic-state labels and
quantum numbers; arbitrary laser beams and polarizations; magnetic-field and
geometry metadata; the pulse waveform; Zeeman and polarization calibrations;
MQDT pair eigenenergies and product-state overlaps versus distance; thermal
distance samples; decay branching; and phase/amplitude noise spectra.

The contract preserves a strict model boundary. These inputs are validated
and summarized, but the current Hessian remains

`H(t)=+Δr Πr' + ½[Ω(t)σ+ + Ω*(t)σ-]`

in the ten-state perfect-blockade basis. No microscopic input changes that
Hamiltonian until an explicit full-model stage consumes it and records the
new basis, Hamiltonian, fidelity definition, and provenance.
