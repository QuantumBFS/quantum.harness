# Stage 2 report: clean critical Ising benchmark

## Outcome

Stage 2 is complete. Slurm job `17178` ran on `ws5` and returned a successful
manifest. All 48 repository tests passed, including five new clean-Ising
tests. The finite-size Casimir analysis reproduced the exact central charge
\(c=1/2\) with both declared fit models:

| Analysis | Fitted sizes | Result |
|---|---|---:|
| Main M0, \(\phi_\infty+A_2L^{-2}\) | \(L=16,20,24,32,48,64\) | \(c=0.5011803410\) |
| M0 after removing two smallest sizes | \(L=24,32,48,64\) | \(c=0.5005792860\) |
| Correction M1, \(\phi_\infty+A_2L^{-2}+A_4L^{-4}\) | \(L=12,16,20,24,32,48,64\) | \(c=0.4999790414\) |

The main M0 relative error is 0.2361%, the M0/M1 difference is 0.2403% of the
exact \(c\), and removing the two smallest main-window sizes shifts \(c\) by
0.0006011. All are below the predeclared 0.5% systematic tolerance.

## Frozen model and transfer convention

The benchmark is the isotropic square-lattice Ising model at

\[
K_c=\frac12\log(1+\sqrt 2)
\]

on an infinitely long cylinder with periodic circumference \(L\). The
symmetric row transfer matrix is

\[
T(s,s')=\exp\left[
\frac{K_c}{2}E_h(s)+K_c\sum_i s_i s'_i+\frac{K_c}{2}E_h(s')
\right],
\qquad
E_h(s)=\sum_i s_i s_{i+1}.
\]

There are exactly \(L\) directed horizontal bond slots. Consequently \(L=2\)
has two parallel periodic bonds, as frozen in stage 0. The positive
log-partition density and Casimir convention are

\[
\phi_L=\frac{\log\lambda_0(L)}{L}
=\phi_\infty+\frac{\pi c}{6L^2}+O(L^{-4}).
\]

At criticality the independent free-fermion expression used for validation is

\[
\log\lambda_0(L)
=\frac{L}{2}\log 2
+\frac12\sum_{r=0}^{L-1}
2\operatorname{asinh}\left|\sin\frac{(2r+1)\pi}{2L}\right|.
\]

The analytic bulk limit is
\(\phi_\infty=\tfrac12\log2+2G/\pi=0.9296953983416103\), with \(G\) Catalan's
constant.

## Independent correctness checks

For \(L=2,4,6,8,10\), the code constructs the full positive
\(2^L\times2^L\) transfer matrix. A residual-controlled power iteration finds
its Perron root, which is compared with the critical free-fermion expression.

| \(L\) | \(\log\lambda_0\) | absolute cross-check error | relative eigen-residual |
|---:|---:|---:|---:|
| 2 | 2.010105077484762 | 0 | \(9.06\times10^{-15}\) |
| 4 | 3.787136564095917 | \(4.44\times10^{-16}\) | \(1.38\times10^{-14}\) |
| 6 | 5.622572120314250 | 0 | \(9.04\times10^{-15}\) |
| 8 | 7.470596587282104 | \(8.88\times10^{-16}\) | \(1.62\times10^{-14}\) |
| 10 | 9.323288953175850 | 0 | \(1.26\times10^{-14}\) |

A separate tiny-torus test directly enumerates all spin configurations and
matches \(\log\operatorname{Tr}T^N\). Tests also enforce transfer symmetry and
positivity, the antiperiodic momentum sector, the sign of the Casimir
coefficient, and convergence of \(\phi_L\) to its analytic bulk limit.

## Finite-size analysis

The production table uses the frozen sizes

\[
L=4,6,8,10,12,16,20,24,32,48,64.
\]

All values come from the exact critical dispersion, not noisy synthetic data.
No Monte Carlo error bar is therefore invented. The ordinary least-squares
residual scale is retained in `fits.json` as a truncation diagnostic, while the
declared 0.5% acceptance band is used as the systematic stability tolerance.

The complete \(L_{\min}\) scan is retained rather than hiding non-asymptotic
windows. In particular, M1 at \(L_{\min}=4\) gives \(c=0.4983383\), showing
that a single \(L^{-4}\) term does not absorb all higher corrections at the two
smallest sizes. The stable reporting windows are M0 at \(L_{\min}=16\) and M1
at \(L_{\min}=12\). This selection follows the predeclared window scan and the
onset of the stability plateau.

## Slurm and artifact record

The successful run used:

- job: `17178`;
- node: `ws5`;
- partition: `gpu`, with no GPU requested;
- resources: 2 CPU cores, 4 GiB memory, 10-minute limit;
- elapsed scheduler time: 4 seconds;
- Python 3.11.15 and NumPy 2.0.1 from the node-local `torch` environment;
- source SHA-256:
  `6590df10f6b2e537d47a02f2e5ec1ed193e6d9b06882abff85a2275d8cb6490f`.

Because the cluster has no shared storage, the batch script copied the source
from `ws0` to node-local storage and atomically returned results to
`tracks/qmc/results/born-critical/stage2-clean-ising/job-17178/`.

Artifacts:

- `manifest.json`: run identity and success state;
- `metrics.json`: headline values and pass/fail gates;
- `fits.json`: all M0/M1 windows and residual diagnostics;
- `size-data.csv`: exact finite-size data;
- `explicit-crosscheck.csv`: dense-matrix/free-fermion comparison;
- `ising-casimir.svg`: Casimir fit and \(L_{\min}\)-stability panels;
- `unittest.log` and `runner.log`: complete execution logs.

## Retained failed attempts

Failures are not silently discarded:

- job `17176`: all 48 tests passed, but JSON artifact generation rejected a
  NumPy boolean scalar; fixed by converting gate values to standard booleans;
- job `17177`: all 48 tests and the transfer cross-check passed, but the first
  reporting choice (`M0 L_min=12`, `M1 L_min=4`) failed two finite-size
  stability gates. The complete output is retained. The declared window scan
  identified the asymptotic plateaus used in job `17178`.

These runs remain under adjacent `job-17176/` and `job-17177/` result
directories with failed manifests.

## Stage boundary

This stage verifies the clean transfer normalization, boundary sector,
Casimir sign, \(L^{-2}\) unit conversion, and finite-size fit machinery. It
does not yet claim a disordered-QMC result. Stage 3 will implement and validate
the Nishimori random-bond Ising transfer calculation before any production
sampling.
