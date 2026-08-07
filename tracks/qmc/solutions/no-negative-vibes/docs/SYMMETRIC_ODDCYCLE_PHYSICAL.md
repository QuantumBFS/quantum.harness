# Physical transfer for the fixed symmetric-oddcycle atom

Let

\[
\Gamma_\wedge(B)=\bigoplus_{k=0}^{5}\wedge^kB
\]

be the vacuum-normalized, number-conserving Fock implementer in the
orthonormal occupation basis.  It obeys
\(\Gamma_\wedge(B_1)\Gamma_\wedge(B_2)=\Gamma_\wedge(B_1B_2)\) and

\[
\operatorname{Tr}_{\mathcal F}\Gamma_\wedge(W)=\det(I+W).
\]

For the fixed matrix \(B\), put

\[
T=19I_{\mathcal F}+\Gamma_\wedge(B)+\Gamma_\wedge(B)^{\mathsf T}.
\]

Exact row arithmetic gives

\[
\max_i\left(\sum_{j\ne i}|S_{ij}|-S_{ii}\right)=18,\qquad
S=\Gamma_\wedge(B)+\Gamma_\wedge(B)^{\mathsf T}.
\]

Row 19 in zero-based indexing is one maximizing row (the complete list is
19, 23, 29, and 30).  Thus \(T\) is real symmetric, strictly diagonally
dominant with minimum row margin one, and positive definite.  The normalized transfer

\[
\widetilde T=\frac{T}{21}
=\frac{19}{21}I_{\mathcal F}
 +\frac1{21}\Gamma_\wedge(B)
 +\frac1{21}\Gamma_\wedge(B^{\mathsf T})
=e^{-H}
\]

therefore defines a Hermitian, number-conserving five-mode Hamiltonian.
For every integer \(L\),

\[
\operatorname{Tr}e^{-LH}
=\sum_{s_1,\ldots,s_L}
\left(\prod_\ell q_{s_\ell}\right)
\det\!\left(I+B_{s_L}\cdots B_{s_1}\right),
\]

where \((B_0,B_+,B_-)=(I,B,B^{\mathsf T})\) and
\((q_0,q_+,q_-)=(19,1,1)/21\).  Identity letters can be deleted, so the
arbitrary-word theorem for \(\{B,B^{\mathsf T}\}\) makes every
configuration weight strictly positive.

This is genuinely interacting.  A Gaussian transfer would have to obey
\(T_0T_2=\wedge^2T_1\).  Here \(T_0=21\), and the exact difference has
58 nonzero entries; its first entry is

\[
\left(21T_2-\wedge^2T_1\right)_{00}=42.
\]

Finally,

\[
\det B=8,\qquad
p_B(\lambda)=\lambda^5-2\lambda^4+\lambda^3-7\lambda^2+16\lambda-8.
\]

For \(t>0\), every coefficient of
\(p_B(-t)=-t^5-2t^4-t^3-7t^2-16t-8\) is negative.  Hence the spectrum
avoids the nonpositive real axis, the real principal
\(A=\operatorname{Log}B\) exists, and
\(\Gamma_\wedge(B)=e^{d\Gamma(A)}\).  The three-term identity is
therefore an exact positive-coefficient discrete Gaussian auxiliary-field
decomposition of an interacting Hermitian transfer.

The statement is grand-canonical: individual fixed-particle-number
traces need not be positive.  It also defines a five-mode cluster model;
locality or a connected-lattice extension is not claimed here.
