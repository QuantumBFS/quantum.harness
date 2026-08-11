# Theory and conventions

## Model

All baselines use an open chain and \(\hbar=k_B=1\):

\[
H_0=-J\sum_{i=1}^{N-1}Z_iZ_{i+1}
    +\frac{\Omega}{2}\sum_{i=1}^N X_i ,
\qquad
H(t)=H_0+\epsilon_d\cos(\omega_dt)S_N .
\]

The bath couples through

\[
S_N=\eta_N\sum_iZ_i.
\]

The default `bounded` normalization is \(\eta_N=1/N\). `kac` means
\(\eta_N=1/\sqrt N\), and `collective` means \(\eta_N=1\).
An optional counterterm is specified by its explicit coefficient
`counterterm_strength`; setting it to \(\Lambda\) adds \(+\Lambda S_N^2\).

The zero-temperature Ohmic convention is

\[
J_B(\omega)=\alpha\omega e^{-\omega/\omega_c},\qquad
C_B(t)=\frac{\alpha\omega_c^2}{(1+i\omega_ct)^2}.
\]

OQuPy defines its power-law spectral density with a factor of two. The wrapper
therefore passes `alpha/2`; this is tested and recorded in every PT-TEMPO result.

## N=2

Exchange symmetry decomposes the Hilbert space as

\[
\mathcal H=\mathcal H_{\rm triplet}\oplus\mathcal H_{\rm singlet}.
\]

The singlet is dark:

\[
S_2|s\rangle=0,\qquad H(t)|s\rangle=J|s\rangle.
\]

In the triplet, define \(E=\sqrt{J^2+\Omega^2}\). The three energies are
\(-E,-J,+E\), so the two allowed gaps and weights are

\[
\Delta_{\rm low/high}=E\mp J,
\]

\[
W_{\rm low/high}=2\eta_2^2(1\pm J/E).
\]

All four formulas are compared with numerical diagonalization for multiple
values of \(J\) at machine precision.

## N=3

Reflection \(1\leftrightarrow3\) gives

\[
\mathcal H=\mathcal H_{R=+}\oplus\mathcal H_{R=-},\qquad 8=6+2.
\]

The odd sector is the edge singlet times the central spin. The Ising term
vanishes in this sector, so its gap is exactly \(\Omega\) for every \(J\). The
even sector contains the collective physics. At strong ferromagnetic coupling,
the lowest bright transition obeys

\[
\Delta_{\rm cat}=\frac{\Omega^3}{4J^2}+O(J^{-4}),
\]

and its normalized bright weight tends to one.

## Heat-current convention

For the period-averaged collective correlation

\[
\bar C(\tau)=T^{-1}\int_0^Tdt\,
\langle S(t+\tau)S(t)\rangle ,
\]

the continuous heat-current density is

\[
\bar j_{\rm con}(\omega)=2J_B(\omega)\omega
\int_0^\infty d\tau\left[
\cos(\omega\tau)\operatorname{Re}C_{\rm con}(\tau)
+(1+2n_B)\sin(\omega\tau)\operatorname{Im}C_{\rm con}(\tau)
\right].
\]

The factorized asymptotic part is never windowed into fake finite-width peaks.
If

\[
\langle S(t)\rangle=\sum_nm_ne^{-in\omega_dt},
\]

its positive-frequency coherent correlation weight is \(2|m_n|^2\), and the
heat delta weight is

\[
\pi J_B(n\omega_d)n\omega_d\,2|m_n|^2.
\]

The JSON schema stores these peaks separately under `delta_peaks`.
