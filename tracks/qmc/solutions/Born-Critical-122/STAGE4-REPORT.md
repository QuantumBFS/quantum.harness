# Stage 4 report: weak self-dual Born critical point

## Outcome

Stage 4 is complete. The production run contains 512/512 successful,
checksum-verified trajectory cells at
\(L=6,8,10,12,16,20,24,30\), with 64 independent replicas per size and
171,966,464 measured circuit cycles in total. The predeclared primary fit,

\[
h_L=h_\infty-\frac{\pi c_{\rm Casimir}}{6L^2}+\frac{b_4}{L^4},
\]

uses M1 and the first residual-qualified window, \(L_{\min}=6\). It gives

\[
c_{\rm Casimir}=0.4477180,\qquad
{\rm CI}_{68\%}=[0.4472843,0.4481650],\qquad
{\rm CI}_{95\%}=[0.4468820,0.4485672].
\]

The analytic weighted-fit estimate is 0.4477264 and the reduced
\(\chi^2\) is 0.8111. The 95% interval intersects the challenge target
\(0.447\pm0.001\). All production, density, isotropy, fit-stability,
cross-check, bootstrap, and regression gates passed. The combined
machine-readable verdict is
`tracks/qmc/results/born-critical/stage4-acceptance.json`.

## Model and estimator

At \(\theta=\pi/4\),

\[
\tanh\beta=\sin\theta,\qquad
\tanh\beta'=\cos\theta,
\]

so \(\beta=\beta'=\log(1+\sqrt2)\). A circuit cycle applies all periodic
\(M_Z\) weak-parity gates followed by all onsite \(M_X\) gates. For local
involution \(A\), branch \(s=\pm1\) is

\[
K_s=\frac{\exp(s\beta A/2)}{\sqrt{2\cosh\beta}},\qquad
p_s=\frac{1+s\tanh\beta\,\langle A\rangle}{2}.
\]

The state is a pure real Majorana covariance matrix. Each sampled outcome is
drawn from its normalized conditional probability and updates the covariance
by the Gaussian rank-two formula. Thus Born disorder is generated
sequentially rather than treated as iid. A separate Majorana transfer basis is
QR-stabilized every eight cycles to retain the Lyapunov diagnostics.

The main observable is the Rao–Blackwell conditional binary entropy. One
cycle contains equal \(M_Z\) and \(M_X\) square-lattice sublayers, so Shannon
and log-norm rates are divided by \(2L\) per cycle. Blocks contain 2,048
cycles. Burn-in is \(50L\), no checkpoint is shared between independent
replicas, and uncertainty is taken across complete trajectory means.

## Production statistics

| \(L\) | replicas | cycles / replica | \(h_L\) | replica SE | \(\rho_e\) | \(\rho_m\) |
|---:|---:|---:|---:|---:|---:|---:|
| 6  | 64 | 786,432 | 0.636556898 | 1.580e-6 | 0.37498643 | 0.37503797 |
| 8  | 64 | 262,144 | 0.639441974 | 1.869e-6 | 0.37504541 | 0.37502606 |
| 10 | 64 | 327,680 | 0.640767192 | 1.837e-6 | 0.37500076 | 0.37507240 |
| 12 | 64 | 262,144 | 0.641489926 | 1.524e-6 | 0.37503127 | 0.37502303 |
| 16 | 64 | 262,144 | 0.642201972 | 1.451e-6 | 0.37498232 | 0.37503837 |
| 20 | 64 | 262,144 | 0.642534859 | 1.172e-6 | 0.37500601 | 0.37501072 |
| 24 | 64 | 262,144 | 0.642712560 | 1.092e-6 | 0.37496224 | 0.37501890 |
| 30 | 64 | 262,144 | 0.642859405 | 0.890e-6 | 0.37500382 | 0.37500831 |

Every Shannon-rate SE is below the frozen \(2\times10^{-6}\) target. Across
all sizes the largest \(e\)-vortex displacement from \(3/8\) is 1.249
standard errors and the largest \(m\)-vortex displacement is 1.904 standard
errors. Pairing adjacent 2,048-cycle blocks into 4,096-cycle blocks changes
the ensemble means only at floating-point roundoff.

All conditional pairs sum to one at recorded precision. The maximum QR
orthogonality error is \(2.55\times10^{-15}\). The maximum accumulated
pure-covariance residual is \(1.36\times10^{-7}\); it remains finite and does
not accompany probability-normalization or QR drift, and it is recorded
rather than silently excluded.

## Bootstrap and window stability

The frozen analysis resamples all 64 independent trajectory means within each
size 10,000 times and refits every declared window. There are zero failed
bootstrap fits.

| model | \(L_{\min}\) | bootstrap median \(c\) | bootstrap SE | 95% interval | \(\chi^2/{\rm dof}\) |
|---|---:|---:|---:|---:|---:|
| M1 | 6  | 0.4477180 | 0.0004350 | [0.4468820, 0.4485672] | 0.811 |
| M1 | 8  | 0.4480526 | 0.0008377 | [0.4464524, 0.4497087] | 0.961 |
| M1 | 10 | 0.4467690 | 0.0015476 | [0.4437871, 0.4498164] | 0.963 |
| M1 | 12 | 0.4483162 | 0.0025056 | [0.4434139, 0.4532737] | 1.151 |
| M0 | 12 | 0.4484886 | 0.0005352 | [0.4474567, 0.4495438] | 0.769 |
| M0 | 16 | 0.4487061 | 0.0010901 | [0.4465978, 0.4508591] | 1.129 |
| M0 | 20 | 0.4463758 | 0.0019842 | [0.4425587, 0.4502449] | 0.373 |

The primary-to-adjacent M1 shift is 0.354 combined standard deviations. The
primary-to-predeclared M0 \(L_{\min}=16\) shift is 0.842 combined standard
deviations. Both are below the 1.5-standard-deviation stability gate. All
design condition numbers are below \(10^{10}\), and the primary window was
selected only by the frozen residual rule, not by proximity to the target.

## Independent correctness checks

Small-circuit enumeration in Slurm regression job `18120` compares the dense
spin Hilbert-space oracle with the Gaussian circuit:

- \(L=2,T=2\): total variation \(2.36\times10^{-16}\);
- \(L=4,T=1\): total variation \(2.51\times10^{-16}\);
- 20,000 sequential samples: zero simultaneous-interval violations and
  maximum chain log-probability error \(3.55\times10^{-15}\).

The independent local-record Metropolis check is job `17613`. Its target
weight is evaluated by a dense spin transfer contraction, without covariance
updates, and a local flip is accepted with
\(\min[1,\exp(2\Delta\log|Z|)]\). After 500 thermalization sweeps, 4,000
stored records were compared with 4,000 independent sequential Born records:

| \(L\) | acceptance | \(\tau_{\rm int}(h)\) | Shannon difference / combined SE |
|---:|---:|---:|---:|
| 6 | 0.7597 | 0.5 | 0.636 |
| 8 | 0.7933 | 0.5 | 0.039 |

Log-norm rate and negative-outcome density also agree within one combined
standard error. Dense and Gaussian fixed-record log weights agree within
\(5.33\times10^{-15}\).

At \(\theta=\pi/4\), the independent isotropy check finds
\(\tanh\beta/\tanh\beta'=0.9999999999999997\). One cycle is explicitly two
equal square-lattice sublayers, and the independent clean square-lattice
normalization benchmark (job `17178`) reproduced \(c=1/2\) to 0.236%.
Together these support the frozen \(\alpha=1\) convention.

## Slurm execution and reproducibility

No numerical workload ran on `ws0`. Every submission first used
`audit_slurm_resources.py`; CPU-only work retained four Slurm CPUs per
unallocated GPU, and the user QOS limits were respected. Because the cluster
has no shared project filesystem, each job copied an immutable source/spec
snapshot to node-local scratch and atomically returned its cell directory.

Production cells ran on `ws1` (152), `ws2` (101), `ws3` (228), and `ws5`
(31). The run began at `2026-07-28T14:36:55Z` and the last cell finished at
`2026-07-29T07:16:41Z`. Aggregation is job `18119`; the final 61-test
regression is job `18120`; combined acceptance is job `18122`.

Reproduction inputs and outputs:

- production spec:
  `tracks/qmc/results/born-critical/selfdual-production-v1/run_spec.json`;
- frozen analysis declaration:
  `configs/selfdual-production-analysis.json`;
- cell runner: `scripts/run_selfdual_array_cell.py`;
- aggregate command: `scripts/aggregate_selfdual_production.py`;
- size table, all fits, bootstrap samples, and SVGs:
  `tracks/qmc/results/born-critical/selfdual-production-v1/aggregate/`;
- combined verdict:
  `tracks/qmc/results/born-critical/stage4-acceptance.json`.
