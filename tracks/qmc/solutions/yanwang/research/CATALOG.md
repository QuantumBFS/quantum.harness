# Literature Catalog

Survey cutoff: **2026-07-27**. Searches covered APS, arXiv, Crossref,
Semantic Scholar citation links, OpenAlex, and SciPost using combinations of
“transverse-field Ising”, “triangular”, “honeycomb”, “critical field”,
`4.76811`, `2.13250`, “cluster Monte Carlo”, “SSE”, and cited/citing-paper
traversal from Blöte and Deng (2002).

## Hamiltonian and conversion rule

The target convention is

\[
H=-J\sum_{\langle i,j\rangle}\sigma_i^z\sigma_j^z
  -h\sum_i\sigma_i^x ,
\]

with Pauli eigenvalues \(\pm1\). If a paper instead uses spin-\(\tfrac12\)
operators \(S^\alpha=\sigma^\alpha/2\) while setting the coefficient of
\(S_i^zS_j^z\) to one, its quoted field is not directly comparable. Every
converted value below states the algebraic map.

## Direct numerical estimates

| Work | Method and geometry | Sizes / truncation | Reported estimate in target convention | Reported uncertainty | Identified systematic limitations | Status |
|---|---|---:|---:|---:|---|---|
| Blöte & Deng, PRE 66, 066110 (2002), DOI `10.1103/PhysRevE.66.066110` | Continuous-time Wolff cluster QMC, PBC, Binder ratio \(Q=\langle m^2\rangle^2/\langle m^4\rangle\), imaginary-time physical length \(M_p=\beta h=L\) | final-fit cutoffs: triangular \(L_{\min}=6,L_{\max}=20\); honeycomb \(L_{\min}=10,L_{\max}=20\); complete rosters not reported | triangular `4.76811(9)`; honeycomb `2.13250(4)` | Least-squares fit uncertainties \(9\times10^{-5}\), \(4\times10^{-5}\); confidence level and separate systematic budget not reported | Fixed then-current 3D-Ising exponents; limited \(L_{\max}=20\); correction ansatz and size-window dependence not separately budgeted | **Trusted baseline; still the most precise direct estimates found** |
| Zimmer, Schmidt & Maziero, PRE 93, 062116 (2016), DOI `10.1103/PhysRevE.93.062116`, arXiv:1604.03486 | Quantum correlated cluster mean-field theory | six-site honeycomb cluster embedded in self-consistent fields; thermodynamic-limit approximation | honeycomb `2.105` | none quoted | Cluster mean-field approximation, no FSS, classical mean-field critical behavior | Context only |
| Dai et al., PRB 95, 214409 (2017), DOI `10.1103/PhysRevB.95.214409`, arXiv:1611.10072 | Thermal iPEPS with ancillas; zero-temperature field inferred by fitting the finite-temperature phase boundary | infinite honeycomb; bond dimension \(D=2\), environment \(M=32\), imaginary-time step \(J\,d\beta=10^{-3}\); 20 phase-boundary points | honeycomb `2.144(3)` from \(a=2.298(7)\) and \(h_c/J=\sqrt{2a}\) | `0.003` | Extrapolation of an empirical phase-boundary curve to \(T=0\); tensor/environment truncation; no direct QCP FSS | Independent but not competitive |
| Vecsei, Flindt & Lado, PR Research 5, 033116 (2023), DOI `10.1103/PhysRevResearch.5.033116`, arXiv:2301.09923 | Neural-network quantum states plus Lee–Yang-zero/cumulant analysis, PBC | honeycomb \(L_{\max}=8\), \(N_{\max}=128\); triangular \(L_{\max}=10\), \(N_{\max}=100\) | honeycomb `2.14`; triangular `4.78` | no critical-field error quoted | Sampling errors shown, but authors note additional variational ground-state error; small size range; no controlled error on \(h_c\) | Independent low-precision check |
| Schamriß, Walther & Schmidt, SciPost Physics 17, 094 (2024), DOI `10.21468/SciPostPhys.17.3.094`, arXiv:2402.18989 | deepCUT gap scaling, ferromagnetic triangular benchmark | perturbative/deepCUT orders through 10; iteration grid \(10^{-3}\) in \(J/h\) | triangular \(J_c/h=0.20953\), hence \(h/J\approx4.772\) | no final error bar; paper estimates induced \(J_c/h\) discretization near \(10^{-4}\) | order/truncation extrapolation, finite-difference and coupling-grid error; the precise `0.20973(2)` comparison value is earlier literature | Independent method benchmark, not competitive |

The literature search found no post-2002 direct calculation that improves the
precision of both Blöte–Deng values in the same Pauli/J convention. This is a
search conclusion at the stated cutoff, not a proof of nonexistence.

### Frozen Table-I details for the triangular reproduction

The attempt-014 source audit returned to the primary 2002 paper rather than
inferring its correction model from the target value. Table I reports for the
triangular lattice \(L_{\min}=6\), \(L_{\max}=20\),
\(Q^\star=0.6238(7)\), \(h_c/J=4.76811(9)\), and nonzero
\(a_1,a_2,a_3,b_1,b_2\) coefficients. Equation (23) defines
\(y_2=d-2y_h\). The historical exponent source used by that analysis is
Blöte, Luijten & Heringa, J. Phys. A 28, 6289 (1995), DOI
`10.1088/0305-4470/28/22/007`, arXiv:cond-mat/9509016, which reports
\(y_h=2.4815(15)\). Thus attempt-014 freezes
\(y_2=3-2(2.4815)=-1.9630\), with the source uncertainty implying
\(\sigma_{y_2}=0.0030\). Neither the triangular critical-field central value
nor \(\sqrt5\) is used to derive this exponent.

## Independent estimates requiring an exact map

Kott et al., SciPost Physics 17, 053 (2024), DOI
`10.21468/SciPostPhys.17.2.053`, arXiv:2402.15389, use order-10 linked-cluster
series for a toric-code field whose exactly mapped TFIM field is

\[
(h_c/J)_{\rm TFIM}=\frac{1}{2h_{\rm toric}}.
\]

They average selected near-diagonal DLogPadé approximants and quote the sample
standard deviation:

| Mapped lattice | Toric-code series value | Converted TFIM value | Interpretation |
|---|---:|---:|---|
| honeycomb | `0.2352(9)` | `2.1259(81)` | independent order-10 series check |
| triangular ferromagnet | `0.10491(13)` | `4.7660(59)` | independent order-10 series check |

Their more precise values `0.234467(5)` and `0.104863(2)` are explicitly
re-expressions of Blöte–Deng, not new QMC estimates. The series uncertainty is
the spread of accepted DLogPadé approximants; approximants with nearby
unphysical poles are discarded. These results are useful cross-method
evidence but are orders of magnitude too imprecise for the ratio verdict.

## Convention trap

Li, von Delft & Xiang, PRB 86, 195137 (2012), DOI
`10.1103/PhysRevB.86.195137`, arXiv:1209.2387, write the Hamiltonian with spin
operators \(S^\alpha\). Their cited honeycomb QMC value `1.06625(2)` is exactly
half of `2.13250(4)` because the field coefficient changes under
\(\sigma=2S\) after normalizing the bond term. It is not an independent,
different critical point. Their own Bethe/tree-tensor estimate near `1.115`
is an approximate result for a different/tree geometry and is excluded from
the precision comparison.

## Method and scaling references

| Work | Relevance |
|---|---|
| Sandvik, PRE 68, 056701 (2003), DOI `10.1103/PhysRevE.68.056701`, arXiv:cond-mat/0303597 | Sign-problem-free stochastic-series-expansion cluster algorithm for transverse Ising models with arbitrary interactions; basis for the primary QMC route. |
| Blöte, Luijten & Heringa, J. Phys. A 28, 6289 (1995), DOI `10.1088/0305-4470/28/22/007`, arXiv:cond-mat/9509016 | Historical 3D-Ising exponents used to bind the triangular Table-I correction: \(y_t=1.587(2)\), \(y_h=2.4815(15)\), hence \(y_2=3-2y_h=-1.9630(30)\). |
| Kos et al., JHEP 08, 036 (2016), DOI `10.1007/JHEP08(2016)036`, arXiv:1603.04436; Simmons-Duffin, JHEP 03, 086 (2017), DOI `10.1007/JHEP03(2017)086`, arXiv:1612.08471 | Precision 3D-Ising universality data. The preregistration uses \(\nu=0.629971(4)\) and \(\omega=\Delta_{\epsilon'}-3=0.82968(23)\) as external priors/fixed sensitivity values, while also testing the older \(\omega=0.815(4)\) used by Blöte–Deng. |
| Schamriß, Walther & Schmidt, SciPost Physics 17, 094 (2024), DOI `10.21468/SciPostPhys.17.3.094`, arXiv:2402.18989 | deepCUT benchmark on the ferromagnetic triangular TFIM. Its tabulated high-precision literature value is traced back to earlier QMC; its own deepCUT result is a method benchmark, not a replacement precision estimate. |

## Baseline arithmetic

Using the 2002 central values and treating the two quoted errors as independent,

\[
R_{2002}=2.2359249706916766,\quad
\sigma_{R,2002}=5.9499059\times10^{-5},
\]

\[
R_{2002}-\sqrt5=-1.4300681\times10^{-4},
\]

which is only `2.40` propagated standard deviations. This motivates the test;
it is not a verdict and will not be used to center production windows more
tightly than independently justified pilot crossings.

## Screening and exclusion rules

- Include a number in the comparison only when the Hamiltonian convention and
  lattice are reconstructable.
- Label mapped or cited values; do not count them as independent estimates.
- Approximate mean-field, tensor, neural, or series values remain useful for
  gross sanity checks but cannot validate \(10^{-5}\)-level precision.
- Conference abstracts, unsourced web summaries, and papers on frustrated
  antiferromagnets are excluded from the ferromagnetic critical-field table.
- A later publication date alone does not make an estimate stronger.
