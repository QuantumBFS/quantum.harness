# Challenge 81 Solver Design

## Acceptance target

Build a deterministic, fully purified finite-temperature solver for the
particle-hole-symmetric spinful single-impurity Anderson model with

\[
D=1,\qquad U=0.8,\qquad \Gamma=0.1,\qquad \epsilon_d=-U/2,\qquad \mu=0.
\]

The first acceptance gate is a finite-bath comparison of impurity occupancy,
double occupancy, and \(G(\tau)\) against an independent exact thermal trace to
maximum error \(10^{-6}\). The continuous-bath \(\beta=16\) or \(32\) run and
its CT-HYB comparison follow only after this gate passes.

## Scientific conventions

- Fermionic mode order in the ED oracle is
  \((d_\uparrow,d_\downarrow,c_{1\uparrow},c_{1\downarrow},\ldots)\).
- The hybridization convention is
  \(\Gamma(\omega)=\pi\sum_k |V_k|^2\delta(\omega-\epsilon_k)\).
- This project fixes the bath-orbital phase freedom to the real nonnegative
  gauge \(V_k=\sqrt{\mathrm{weight}_k/\pi}\). The ED oracle therefore rejects
  negative or complex couplings rather than silently changing gauge.
- The semicircular bath is discretized with Gauss-Chebyshev quadrature of the
  second kind:
  \[
  \epsilon_k=D\cos\frac{k\pi}{N_b+1},\qquad
  V_k^2=\frac{\Gamma D}{N_b+1}\sin^2\frac{k\pi}{N_b+1}.
  \]
- The finite-bath Hamiltonian is grand canonical. No fixed-particle-number
  projection is applied to the thermal trace.
- For \(0\le\tau\le\beta\),
  \[
  G_\sigma(\tau)=
  -Z^{-1}\operatorname{Tr}\left[
  e^{-(\beta-\tau)K}d_\sigma e^{-\tau K}d_\sigma^\dagger
  \right].
  \]
- The MPS state contains interleaved physical and ancilla `Electron` sites.
  The \(\beta=0\) state is a product over sites of normalized local identity
  pairs. Only physical sites evolve under \(e^{-\beta K/2}\).

## Components

1. A dedicated Julia project under this solution folder pins ITensors,
   ITensorMPS, and KrylovKit.
2. A minimal purification smoke test checks normalization and the exact
   one-site interacting thermal density matrix.
3. A Python bath module serializes both finite bath parameters and the realized
   hybridization on a common frequency grid.
4. A Python ED oracle constructs the fermionic Hamiltonian with explicit
   Jordan-Wigner signs and computes exact thermal observables.
5. TRIQS/CT-HYB lives in an isolated environment and produces comparison
   artifacts only; it is not an implementation dependency of the MPS solver.

## Failure policy

- Every generated artifact records parameters, conventions, software versions,
  and hashes of upstream inputs.
- Canonical JSON bytes are deterministic for a fixed locked runtime. Python and
  NumPy versions are part of provenance because cross-runtime floating-point
  eigensolver bytes are not claimed to be identical.
- Dense ED is limited by both Hilbert dimension and a conservative byte-level
  peak-memory guard that includes eigensolver workspace and Lehmann temporaries.
- If the ordinary partition function exceeds finite `float64` range, the
  artifact retains finite `logZ` and records `Z: null` with
  `Z_status: "overflow"`.
- Particle-hole symmetry must give \(n_d=1\) within numerical tolerance.
- The \(U=0\), \(V=0\), Hermiticity, anticommutation, and \(\beta=0\) limits are
  mandatory tests.
- Production MPS results are not accepted from a single bond dimension or time
  step. The final report separates bath, chain-length, truncation, and
  time-step/residual errors.
