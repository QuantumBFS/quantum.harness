# Phase 9 sigma=0.4 MPO-bias qualification

Both fits use `alpha=0.5` and `r_fit=2048`. Errors are measured against the
exact periodic Hurwitz-zeta finite-ring coupling.

| K | L | maximum relative error | RMS relative error | maximum location |
|---:|---:|---:|---:|---:|
| 24 | 64 | 6.0040% | 4.4170% | 32 |
| 32 | 64 | 5.9999% | 4.4140% | 32 |
| 24 | 96 | 7.0612% | 5.1810% | 48 |
| 32 | 96 | 7.0564% | 5.1775% | 48 |

K=32 improves the infinite-kernel fit but does not materially reduce the
periodized central-distance residual. It fails the preregistered approximate
1% finite-ring error threshold. Therefore no sigma=0.4 DMRG validation is
authorized, no K is selected for that branch, and sigma=0.4 remains a
documented MPO-limited validation.

The distance-resolved comparison is provided in
`coupling-error-K24-K32.png` and `coupling-error-K24-K32.pdf`.
