# Numerical methods and evidence labels

## Exact finite-system layer

`exact_diagonalization` constructs the operators in the full computational
basis and projects them with orthonormal isometries obtained from the exact
swap/reflection operators. Tests require sector leakage below \(10^{-13}\).
The resulting physical dimensions are \(d=3\) for the \(N=2\) triplet,
\(d=6\) for the \(N=3\) reflection-even sector, and \(d=2\) for the
reflection-odd sector.

`closed_unitary` uses midpoint time ordering,

\[
U(T)\approx\prod_n\exp[-iH(t_{n+1/2})\delta t],
\]

and supplies Floquet modes and Fourier matrix elements. Tests cover unitarity,
the static limit, quasienergy-zone placement, and second-order timestep
convergence.

## Uniform influence-functional backend

The production method label is `uniform_tempo_floquet_multitime`.
[UniformTEMPO.jl](https://github.com/uniformTEMPO/UniformTEMPO.jl) is pinned in
`julia/Project.toml` pins the package source to revision
`b76a018c32e5415989761d902b1b0e95f1a337da`.

For the zero-temperature Ohmic bath,

\[
J_B(\omega)=\alpha\omega e^{-\omega/\omega_c},\qquad
C_B(t)=\frac{\alpha\omega_c^2}{(1+i\omega_ct)^2}.
\]

The Julia runner builds or reloads a serialized uniform process tensor, forms
the periodic influence-functional transfer sequence, solves its extended
Floquet fixed point, and evaluates two-time correlations by inserting
left-acting system operators into the extended state. It does not apply the
quantum regression theorem to a reduced density matrix.

The period average uses phase samples across one drive cycle. The correlation
is decomposed as

\[
\bar C(\tau)=C_{\rm dec}(\tau)+C_{\rm coh}(\tau).
\]

Only \(C_{\rm dec}\) is numerically Fourier integrated. Fourier coefficients
of \(\langle S(t)\rangle\) are stored separately as analytic coherent delta
weights, preventing finite-window broadening.

## Nested convergence controller

The publication schedule is:

| control | ladder |
|---|---|
| steps per period | \(60,90,120\) |
| uniform compression tolerance | \(3\times10^{-7},10^{-7},3\times10^{-8}\) |
| phase samples | \(3,15\) |

The inexpensive \(N=2\) error grid may continue the tolerance ladder through
\(10^{-8}\) and \(3\times10^{-9}\).

At each timestep grid the controller first establishes compression
convergence. A timestep comparison is accepted only if compression passed on
both participating grids. Phase refinement is performed only after a
timestep comparison passes. The residual limits are

\[
r_\rho\le0.05,\qquad r_C\le0.08,\qquad r_j\le0.08.
\]

Final physical gates require:

- fixed-point residual \(\le10^{-3}\);
- trace and Hermiticity errors \(\le5\times10^{-3}\);
- connected-correlation tail \(\le0.05\);
- minimum density eigenvalue \(\ge-5\times10^{-3}\).

Every comparison records the coarse/refined fingerprints, steps, tolerance,
phase count, bond dimensions, three residuals, and pass/fail status. The cache
uses atomic replacement so interrupted calculations can be resumed safely.

## Production outcomes

### \(N=3\) sector grid

All six points pass the nested controller and physical gates:

| sector | \(J/\Omega\) | final steps | bond | timestep \(r_j\) | tail |
|---|---:|---:|---:|---:|---:|
| even | 0.25 | 90 | 40 | 0.00844 | 0.02792 |
| even | 0.50 | 90 | 43 | 0.02799 | 0.00562 |
| even | 1.00 | 120 | 46 | 0.04890 | 0.01077 |
| odd | 0.25, 0.50, 1.00 | 90 | 16 | 0.00151 | 0.03986 |

The projected odd-sector Hamiltonian and coupling are exactly \(J\)
independent; the three production spectra have relative maximum difference
zero.

### \(N=2\) exact-vs-Markov grid

The calibration grid contains all nine combinations of
\(\alpha=0.025,0.05,0.1\) and
\(\omega_d/\Delta_g=0.75,1,1.25\). All nine exact points pass the production
gates. The weak-coupling delay window grows as
\(\max(4,\lceil0.3/\alpha\rceil)\) periods.

The three reported errors are:

\[
D_\rho=\tfrac12\|\rho_{\rm IF}-\rho_{\rm ME}\|_1,
\]

\[
\epsilon_C=\frac{\int d\tau\,|C_{\rm IF}-C_{\rm ME}|}
{\int d\tau\,|C_{\rm IF}|},\qquad
\epsilon_j=\frac{\int d\omega\,|\bar j_{\rm IF}-\bar j_{\rm ME}|}
{\int d\omega\,|\bar j_{\rm IF}|}.
\]

Across the grid, \(D_\rho=0.9968\)–\(0.9997\),
\(\epsilon_C=1.10\)–\(1.86\), and
\(\epsilon_j=5.03\)–\(68.84\). These large values are a result, not a
convergence failure: the uniform-TEMPO reference points themselves are
converged.

### \(N=3\) same-model exact-vs-Markov grid

The six converged \(N=3\) sector points are also compared to
Floquet-Markov/QRT without changing the Hamiltonian, drive, bath, sector, or
frequency and delay grids. In the even sector, the heat-spectrum error is
9.02–11.72 and the trace distance is 0.992–1.000. In the exactly
\(J\)-independent odd sector, all three rows reproduce the same errors:
\(D_\rho=0.4753\), \(\epsilon_C=0.5666\), and \(\epsilon_j=0.3920\).
This closes the same-model comparison required by Tier 3 rather than using the
\(N=2\) calibration as a proxy.

### Model-definition variants

At \(N=3,J/\Omega=0.5,\alpha=0.1\), the bounded variants
\(S=M_z/3\), with and without \(+\alpha\omega_cS^2\), pass compression,
timestep, phase, and physical gates (final bond dimension 45).

The Kac variants \(S=M_z/\sqrt3\) pass the compression comparison:

| variant | refined bond | compression \(r_j\) |
|---|---:|---:|
| Kac, no counterterm | 82 | 0.02373 |
| Kac, counterterm | 81 | 0.00502 |

Their next timestep and phase layers are intentionally not run by the local
default because the larger coupling raises the process-tensor cost sharply.
They are labeled `local_resource_ceiling`, not converged. `--full-kac`
continues the same auditable ladder on a cluster.

## Independent validation

`scripts/run_fig3_validation.py` downloads the immutable author archive from
Zenodo, verifies MD5 `0f3f9d9d8538aa96aee089973df7d9c2`, and independently
recomputes all three transversal-drive curves in Fig. 3 (bottom) at
\(\omega_d/\Omega=1,1.5,2\). All three points pass the same density, fixed-point,
Hermiticity, trace, and correlation-tail gates. The normalized shape
\(L^1\) discrepancies are 0.0562, 0.2736, and 0.3718 respectively; these are
reported as quantitative structural reproduction, not bitwise identity.

`scripts/run_uniform_validation.py` performs:

- a single-spin UniformTEMPO smoke calculation that passes its declared
  physical gates (bond 19, fixed-point residual \(1.40\times10^{-4}\));
- a coarse reflection-odd UniformTEMPO–OQuPy comparison.

The latter has heat \(L^1\) difference 0.517 and is retained as an independent
implementation diagnostic, not as a convergence claim. It also verifies the
projected odd-sector \(J\)-invariance exactly.

## Benchmark and legacy backends

`floquet_markov` / `floquet_markov_qr` implement a Born-Markov, fully secular
periodic Lindblad benchmark with QRT correlations. They are never labeled
non-Markovian.

The in-repository finite-memory QUAPI code exposes the exponential
\(O[(d^2)^{K+1}]\) wall and is used for regression tests. OQuPy 0.5.0 remains
available as an independent PT-TEMPO validation backend. Neither supplies the
production values in `results/paper`.

## N=4 convergence-gated extension

The generic reflection projector produces \(10\oplus6\) blocks for \(N=4\).
At \(J/\Omega=0.25\), the odd-sector point passes nested compression,
timestep, phase, and physical gates at 60 steps per period, tolerance
\(3\times10^{-6}\), and 15 phases (bond 8, connected tail 0.0368). Its same-model
Floquet-Markov/QRT heat-spectrum error is 3.405. The exact continuous spectrum
has its three largest peaks at 0.4725, 0.9600, and 1.4400 \(\Omega\), whereas
the selected drive frequency is 0.9256 \(\Omega\).

The even-sector three-period endpoint missed only the connected-tail gate
(0.0552 against 0.05). Without weakening the gate, the production point was
rerun with six delay periods. It then passed every layer at bond 13 with tail
0.0213; its same-model heat-spectrum error is 5.494.
