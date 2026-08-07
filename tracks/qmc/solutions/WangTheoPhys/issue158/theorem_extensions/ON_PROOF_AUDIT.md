# Proof audit: a finite-volume infrared theorem for classical hard-spin \(O(n)\) models

## 1. Scope

This document proves a finite-volume infrared theorem for classical unit
vectors
\[
   \mathbf S_x\in S^{n-1},\qquad n\ge2,
\]
with bilinear, translation-invariant, ferromagnetic pair interactions.  The
number \(n\) counts spin components; the lattice volume is denoted by
\(V=L^d\).

The theorem is not a statement about every continuous field theory.  In its
present form it does not cover:

- \(n=1\), where there is no continuous transverse rotation;
- unbounded soft-spin or continuum fields;
- a general compact target manifold without an appropriate family of
  measure-preserving generators;
- frustrated or sign-changing interactions;
- multibody interactions;
- quantum systems.

The abstract criterion is valid in arbitrary spatial dimension.  Two
dimensions enter only through the corollaries that verify divergence of the
infrared integral.

## 2. Finite-volume model

Let
\[
   \mathbb T_L^d=(\mathbb Z/L\mathbb Z)^d,\qquad V=L^d,
\]
and let \(\mathcal Q_L\) be its reciprocal grid in a fixed Brillouin zone.
At each site \(x\), the spin is integrated with the normalized rotation
invariant surface measure \(d\omega(\mathbf S_x)\) on \(S^{n-1}\).

Assume
\[
   J_L(R)=J_L(-R)\ge0,\qquad J_L(0)=0.
\]
The Hamiltonian in a field pointing along component \(1\) is
\[
   H_{L,h}(\mathbf S)
   =
   -\frac12\sum_{x\in\mathbb T_L^d}\sum_R
       J_L(R)\,\mathbf S_x\cdot\mathbf S_{x+R}
   -h\sum_x S_x^1.                                      \tag{2.1}
\]
The factor \(1/2\) compensates the directed-pair sum.  Define
\[
   E_L(q)=\sum_RJ_L(R)\,[1-\cos(q\cdot R)]               \tag{2.2}
\]
and
\[
   \mathbf M_L=\frac1V\sum_x\mathbf S_x,\qquad
   m_{L,h}=\langle M_L^1\rangle_{L,h}.                  \tag{2.3}
\]

For fixed \(h>0\), the Gibbs measure is
\[
   d\mu_{L,h}
   =Z_{L,h}^{-1}
    e^{-\beta H_{L,h}}
    \prod_xd\omega(\mathbf S_x),\qquad \beta=T^{-1}.     \tag{2.4}
\]

## 3. The theorem

### Theorem 1 (hard-spin \(O(n)\) finite-volume infrared criterion)

Let \(n\ge2\), and let the model (2.1) satisfy the assumptions above.  Suppose
there is a continuous nonnegative function \(E_\infty\) on the Brillouin zone
such that
\[
   \sup_{q\in\mathrm{BZ}}|E_L(q)-E_\infty(q)|
   \longrightarrow0,                                   \tag{3.1}
\]
where the periodic interpolation of \(E_L\) is understood.  Suppose also
that the regulated integral
\[
   I(h)=
   \int_{\mathrm{BZ}}\frac{d^dq}{(2\pi)^d}
   \frac{1}{h+E_\infty(q)}                              \tag{3.2}
\]
satisfies
\[
   I(h)\longrightarrow\infty\qquad(h\downarrow0).       \tag{3.3}
\]
Then, for every finite \(T>0\),
\[
   \lim_{h\downarrow0}\limsup_{L\to\infty}m_{L,h}=0,    \tag{3.4}
\]
and
\[
   \lim_{L\to\infty}
   \left\langle|\mathbf M_L|^2\right\rangle_{L,0}=0.    \tag{3.5}
\]

The quantitative finite-volume estimate is
\[
   1\ge
   (n-1)T\,m_{L,h}^{\,2}
   \frac1V\sum_{q\in\mathcal Q_L}
   \frac{1}{h+E_L(q)}.                                  \tag{3.6}
\]

The proof occupies Sections 4--9.  It contains no thermodynamic
symmetry-breaking assumption and no spin-wave approximation.

## 4. Rotation generators and sphere integration by parts

For each transverse component \(a=2,\ldots,n\), define at site \(x\)
\[
   \mathcal L_x^{1a}
   =
   S_x^1\frac{\partial}{\partial S_x^a}
   -
   S_x^a\frac{\partial}{\partial S_x^1}.                 \tag{4.1}
\]
This notation means the derivative along the rotation orbit in the
\((1,a)\) plane, not an ambient Cartesian derivative applied without the
sphere constraint.  If \(R_{1a}(t)\in SO(n)\) denotes this rotation, then
\[
   \mathcal L^{1a}f(\mathbf S)
   =
   \left.\frac{d}{dt}f(R_{1a}(t)\mathbf S)\right|_{t=0}.
                                                                    \tag{4.2}
\]
In particular,
\[
   \mathcal L^{1a}S^1=-S^a,\qquad
   \mathcal L^{1a}S^a=S^1.                             \tag{4.3}
\]

The surface measure is invariant under \(R_{1a}(t)\).  Hence, for every
smooth \(f\),
\[
\begin{split}
   \int_{S^{n-1}}\mathcal L^{1a}f\,d\omega
   &=
   \left.\frac{d}{dt}
   \int_{S^{n-1}}f(R_{1a}(t)\mathbf S)\,d\omega(\mathbf S)
   \right|_{t=0} \\
   &=0.                                                  \tag{4.4}
\end{split}
\]
Equation (4.4) is the required integration-by-parts statement.  No curvature
term is missing: the generator is a divergence-free Killing field for the
invariant measure.  A generic local coordinate derivative would not have
this property.

Introduce the Fourier combinations
\[
   D_q^a=\sum_xe^{iq\cdot x}\mathcal L_x^{1a},\qquad
   A_q^a=\sum_xe^{-iq\cdot x}S_x^a.                     \tag{4.5}
\]
The complex notation is only a compact way of pairing the cosine and sine
variations; \(D_{-q}^a\) is the complex conjugate variation on real
observables.

Applying (4.4) to the product Gibbs measure gives
\[
   \langle D_q^aF\rangle
   =
   \beta\langle F D_q^aH_{L,h}\rangle                  \tag{4.6}
\]
and
\[
   \left\langle D_{-q}^aD_q^aH_{L,h}\right\rangle
   =
   \beta\left\langle|D_q^aH_{L,h}|^2\right\rangle
   \ge0.                                                \tag{4.7}
\]
The nonnegativity in (4.7) is an averaged Gibbs identity.  The configuration
by configuration expression derived below need not be nonnegative.

## 5. Classical Bogoliubov inequality

Choose \(F=A_q^a\) in (4.6).  Cauchy--Schwarz and (4.7) give
\[
\begin{split}
   |\langle D_q^aA_q^a\rangle|^2
   &=
   \beta^2|\langle A_q^aD_q^aH\rangle|^2 \\
   &\le
   \beta^2\langle|A_q^a|^2\rangle
   \langle|D_q^aH|^2\rangle \\
   &=
   \beta\langle|A_q^a|^2\rangle
   \langle D_{-q}^aD_q^aH\rangle .
                                                               \tag{5.1}
\end{split}
\]
Equivalently,
\[
   \langle|A_q^a|^2\rangle
   \langle D_{-q}^aD_q^aH\rangle
   \ge
   T|\langle D_q^aA_q^a\rangle|^2.                    \tag{5.2}
\]

The numerator is independent of \(q\) and \(a\):
\[
   D_q^aA_q^a
   =
   \sum_xS_x^1,
\qquad
   \langle D_q^aA_q^a\rangle=Vm_{L,h}.                 \tag{5.3}
\]

## 6. Exact second variation of the pair energy

This is the step at which the \(O(n)\) proof differs most visibly from the
single-angle XY derivation: the result is a projection onto a selected two-dimensional internal plane.

Take one pair \(s,t\in S^{n-1}\), one transverse direction \(a\), and set
\[
   B=s_1t_a-s_at_1,\qquad
   C=s_1t_1+s_at_a.                                    \tag{6.1}
\]
Writing \(\mathcal L_s\) and \(\mathcal L_t\) for the generators acting on
the two spins, direct differentiation gives
\[
\begin{array}{ll}
   \mathcal L_s(s\cdot t)=B,&
   \mathcal L_t(s\cdot t)=-B,\\[2mm]
   \mathcal L_sB=-C,&
   \mathcal L_tB=C.
\end{array}                                             \tag{6.2}
\]
For complex numbers \(u,v\),
\[
\begin{split}
   &(\bar u\mathcal L_s+\bar v\mathcal L_t)
    (u\mathcal L_s+v\mathcal L_t)(-J\,s\cdot t)\\
   &\hspace{25mm}
   =J\big(|u|^2+|v|^2-\bar uv-\bar vu\big)C\\
   &\hspace{25mm}
   =J|u-v|^2(s_1t_1+s_at_a).                            \tag{6.3}
\end{split}
\]
With \(u=e^{iq\cdot x}\), \(v=e^{iq\cdot(x+R)}\),
\[
   |u-v|^2=2[1-\cos(q\cdot R)].                         \tag{6.4}
\]
Combining (6.3) with the factor \(1/2\) in (2.1), the complete interaction
contribution is
\[
   \sum_{x,R}J_L(R)[1-\cos(q\cdot R)]
   \big(
       S_x^1S_{x+R}^1+S_x^aS_{x+R}^a
   \big).                                               \tag{6.5}
\]
The field contributes
\[
   h\sum_xS_x^1.                                       \tag{6.6}
\]
Therefore
\[
\begin{split}
   D_{-q}^aD_q^aH_{L,h}
   &=
   h\sum_xS_x^1\\
   &\quad+
   \sum_{x,R}J_L(R)[1-\cos(q\cdot R)]
   \big(
       S_x^1S_{x+R}^1+S_x^aS_{x+R}^a
   \big).                                               \tag{6.7}
\end{split}
\]

For unit spins, Cauchy--Schwarz in the selected two-dimensional internal
plane gives
\[
   S_x^1S_y^1+S_x^aS_y^a
   \le
   \sqrt{(S_x^1)^2+(S_x^a)^2}
   \sqrt{(S_y^1)^2+(S_y^a)^2}
   \le1.                                                \tag{6.8}
\]
This projection can be negative.  Positivity of \(J_L\) is what permits the
upper bound, not a false assertion that every term in (6.7) is positive.
Using also \(S_x^1\le1\),
\[
   \left\langle D_{-q}^aD_q^aH_{L,h}\right\rangle
   \le V[h+E_L(q)].                                    \tag{6.9}
\]

Equations (5.2), (5.3), and (6.9) imply, separately for every
\(a=2,\ldots,n\),
\[
   \langle|A_q^a|^2\rangle
   \ge
   \frac{TVm_{L,h}^{\,2}}{h+E_L(q)}.                   \tag{6.10}
\]

## 7. The \(n-1\) transverse channels

For the Fourier convention (4.5), Parseval's identity is
\[
   \sum_{q\in\mathcal Q_L}|A_q^a|^2
   =
   V\sum_x(S_x^a)^2.                                   \tag{7.1}
\]
Sum (6.10) first over \(q\), then over all \(n-1\) transverse directions.
The left side has the shared budget
\[
\begin{split}
   \sum_{a=2}^n\sum_q\langle|A_q^a|^2\rangle
   &=
   V\sum_x
   \left\langle\sum_{a=2}^n(S_x^a)^2\right\rangle\\
   &=
   V\sum_x\langle1-(S_x^1)^2\rangle\\
   &\le V^2.                                            \tag{7.2}
\end{split}
\]
The right side contains \(n-1\) identical lower bounds.  Consequently,
\[
   1\ge
   (n-1)T\,m_{L,h}^{\,2}
   \frac1V\sum_{q\in\mathcal Q_L}
   \frac{1}{h+E_L(q)},                                  \tag{7.3}
\]
which proves (3.6).

For \(n=2\), there is one transverse component, and (7.2) becomes the usual
XY identity \(V\sum_x\sin^2\theta_x\le V^2\).  Thus the general formula has
the correct XY normalization.

The factor \(n-1\) does not follow by multiplying one inequality without
changing its left side.  It follows because all transverse spectral weights
can be summed and their combined Parseval budget remains at most \(V^2\).

## 8. Fixed-field thermodynamic limit

Fix \(h>0\).  Uniform convergence (3.1) implies uniform convergence of
\[
   \frac{1}{h+E_L(q)}
   \quad\hbox{to}\quad
   \frac{1}{h+E_\infty(q)},                              \tag{8.1}
\]
because the denominators are bounded below by \(h\).  Standard periodic
Riemann sums then give
\[
   \frac1V\sum_{q\in\mathcal Q_L}\frac{1}{h+E_L(q)}
   \longrightarrow I(h).                               \tag{8.2}
\]
It follows from (7.3) that
\[
   \limsup_{L\to\infty}m_{L,h}^{\,2}
   \le
   \frac{1}{(n-1)T I(h)}.                               \tag{8.3}
\]
Letting \(h\downarrow0\) and using (3.3) proves (3.4).

The order of limits is essential: \(L\to\infty\) is taken at fixed
\(h>0\), and only afterward is the field removed.

## 9. Bridge to the zero-field second moment

The finite-volume Gibbs measure at \(h=0\) is \(SO(n)\)-invariant.  Therefore
the second-moment tensor is proportional to the identity:
\[
   \langle M_L^\alpha M_L^\beta\rangle_{L,0}
   =
   \frac{\delta_{\alpha\beta}}{n}
   \langle|\mathbf M_L|^2\rangle_{L,0}.                 \tag{9.1}
\]
In particular,
\[
   \langle(M_L^1)^2\rangle_{L,0}
   =
   \frac1n\langle|\mathbf M_L|^2\rangle_{L,0}.           \tag{9.2}
\]
For \(n\ge2\), a rotation by \(\pi\) in the \((1,2)\) plane sends
\(M_L^1\) to \(-M_L^1\), so its distribution is symmetric.  Reflections are
not needed.

We record the scalar probability lemma used below.

### Lemma 2 (bounded symmetric exponential tilt)

Let \(X\in[-1,1]\) have a symmetric distribution.  For \(t\ge0\), define
\[
   \mathbb E_t[f(X)]
   =
   \frac{\mathbb E[f(X)e^{tX}]}{\mathbb E[e^{tX}]}.
\]
Then
\[
   \mathbb E_t[X]\ge\tanh(t)\,\mathbb E[X^2].           \tag{9.3}
\]

### Proof

By symmetry,
\[
   \mathbb E_t[X]
   =
   \frac{\mathbb E[X\sinh(tX)]}
        {\mathbb E[\cosh(tX)]}.                         \tag{9.4}
\]
For \(0\le x\le1\), concavity of \(\tanh\) and \(\tanh(0)=0\) imply
\[
   \tanh(tx)\ge x\tanh(t).                              \tag{9.5}
\]
Hence
\[
   x\sinh(tx)\ge x^2\tanh(t)\cosh(tx).                  \tag{9.6}
\]
Both \(x^2\) and \(\cosh(tx)\) are increasing functions of \(x\ge0\).
Their covariance under the law of \(|X|\) is nonnegative, so
\[
   \mathbb E[X^2\cosh(tX)]
   \ge
   \mathbb E[X^2]\mathbb E[\cosh(tX)].                  \tag{9.7}
\]
Equations (9.4)--(9.7) prove the lemma. \(\square\)

In the spin system, set \(X=M_L^1\) and \(t=\beta hV\).  Tilting the zero-field
measure by \(e^{tX}\) produces exactly the field-\(h\) Gibbs measure.  Lemma 2
and (9.2) therefore give
\[
   m_{L,h}
   \ge
   \tanh(\beta hV)\langle(M_L^1)^2\rangle_{L,0}
   =
   \frac1n\tanh(\beta hV)
   \langle|\mathbf M_L|^2\rangle_{L,0}.                 \tag{9.8}
\]
At fixed \(h>0\), \(\tanh(\beta hV)\to1\).  Thus
\[
   \limsup_{L\to\infty}
   \langle|\mathbf M_L|^2\rangle_{L,0}
   \le
   n\limsup_{L\to\infty}m_{L,h}.                        \tag{9.9}
\]
Combining (9.9) with (8.3), and then taking \(h\downarrow0\), proves
(3.5).  This closes the finite-volume route from the infrared estimate to
the zero-field observable used in Monte Carlo studies.

## 10. Two-dimensional corollaries

### 10.1 Finite second moment

Suppose a fixed infinite-volume interaction satisfies
\[
   \sum_RJ(R)|R|^2<\infty.                              \tag{10.1}
\]
Since \(1-\cos u\le u^2/2\),
\[
   E_\infty(q)
   \le
   \frac{|q|^2}{2}\sum_RJ(R)|R|^2
   =C|q|^2.                                             \tag{10.2}
\]
In \(d=2\),
\[
   I(h)\ge
   c\int_0^\delta\frac{k\,dk}{h+Ck^2}
   \longrightarrow\infty,                              \tag{10.3}
\]
so Theorem 1 excludes \(O(n)\) long-range order.

### 10.2 Marginal \(1/r^4\) interaction

Let
\[
   J_\infty(R)=\frac{A}{|R|^4},
   \qquad R\in\mathbb Z^2\setminus\{0\}.                \tag{10.4}
\]
Split the kernel at \(|R|=|q|^{-1}\).  In the near region,
\[
\begin{split}
   \sum_{0<|R|\le|q|^{-1}}
   \frac{A[1-\cos(q\cdot R)]}{|R|^4}
   &\le
   \frac{A|q|^2}{2}
   \sum_{0<|R|\le|q|^{-1}}\frac1{|R|^2}\\
   &\le C_1|q|^2\log\frac{C_2}{|q|}.                   \tag{10.5}
\end{split}
\]
In the far region,
\[
   \sum_{|R|>|q|^{-1}}
   \frac{A[1-\cos(q\cdot R)]}{|R|^4}
   \le
   2A\sum_{|R|>|q|^{-1}}\frac1{|R|^4}
   \le C_3|q|^2.                                       \tag{10.6}
\]
Therefore
\[
   E_\infty(q)
   \le C|q|^2\log\frac{C'}{|q|}.                        \tag{10.7}
\]
The two-dimensional infrared integral obeys
\[
   \int_{|q|<\delta}\frac{d^2q}{E_\infty(q)}
   \ge
   c\int_0^\delta
   \frac{dk}{k\log(C'/k)}
   =\infty.                                             \tag{10.8}
\]
The divergence is of \(\log\log\) type.  It is slow but sufficient for
Theorem 1.

For the square-lattice interaction, the sharper asymptotic is
\[
   E_\infty(q)
   =
   \frac{\pi A}{2}|q|^2\log\frac1{|q|}
   +O(|q|^2).                                           \tag{10.9}
\]
The exact coefficient is useful for numerical certification but is not
needed for the no-order theorem.

### 10.3 Minimum-image, size-normalized sequence

For the sequence used in the numerical application,
\[
   J_L(R)=\frac{c_L}{|R_{\mathrm{MI}}|^4},
\qquad
   \sum_{R\ne0}J_L(R)=4.                                \tag{10.10}
\]
The omitted two-dimensional tail is \(O(L^{-2})\).  Consequently,
\[
   c_L-c_\infty=O(L^{-2}),\qquad
   \|J_L-J_\infty\|_{\ell^1}=O(L^{-2}),                 \tag{10.11}
\]
after extending the minimum-image interaction by zero outside its
fundamental cell.  Since
\[
   \sup_q|E_L(q)-E_\infty(q)|
   \le2\|J_L-J_\infty\|_{\ell^1},                       \tag{10.12}
\]
the uniform-kernel hypothesis (3.1) follows.  Equations (10.7)--(10.8)
verify the remaining hypothesis.  Thus, for every finite \(n\ge2\) and
every \(T>0\),
\[
   \lim_{L\to\infty}
   \langle|\mathbf M_L|^2\rangle_{L,0}=0.               \tag{10.13}
\]

### 10.4 Quantitative finite-size envelope at marginality

The finite-volume inequality also controls the approach to zero.  Define
\[
   A_L(h)=\frac1{L^2}\sum_{q\in\mathcal Q_L}
   \frac1{h+E_L(q)}                                    \tag{10.14}
\]
and choose the size-dependent field
\[
   h_L=\frac{T}{L^2}.                                  \tag{10.15}
\]
For every fixed \(T>0\), there are constants \(a_T>0\) and
\(L_T<\infty\) such that
\[
   A_L(h_L)\ge a_T\log\log L                           \tag{10.16}
\]
for every even \(L\ge L_T\).

Indeed, the uniform minimum-image estimate (10.12) and the marginal upper
bound (10.7) give constants \(B,C,K>0\) such that
\[
   E_L(q)
   \le \frac{B}{L^2}+C|q|^2\log\frac K{|q|},
   \qquad0<|q|\le\frac12,                              \tag{10.17}
\]
uniformly for all sufficiently large even \(L\).  Write the torus momenta
as \(q_k=2\pi k/L\), with \(k\) in the centered integer square.  Fix
\(0<\alpha<(4\pi\sqrt2)^{-1}\) and introduce the max-norm shells
\[
   \mathcal S_m=\{k:\|k\|_\infty=m\},
   \qquad1\le m\le\lfloor\alpha L\rfloor.             \tag{10.18}
\]
For \(m<L/2\), each shell contains exactly \(8m\) points, and on the range
(10.18),
\[
   \frac{2\pi m}{L}\le |q_k|
   \le\frac{2\pi\sqrt2m}{L}\le\frac12.               \tag{10.19}
\]
After enlarging a constant \(D_T<\infty\), Eqs. (10.15), (10.17), and
(10.19) imply the uniform shell bound
\[
   h_L+E_L(q_k)
   \le
   \frac{D_T}{L^2}m^2\log\frac{K'L}{m}.               \tag{10.20}
\]
Consequently,
\[
\begin{split}
   A_L(h_L)
   &\ge
   \frac8{D_T}
   \sum_{m=1}^{\lfloor\alpha L\rfloor}
   \frac1{m\log(K'L/m)}\\
   &\ge
   \frac8{D_T}
   \left[
      \log\log(K'L)
      -\log\log\left(\frac{2K'}{\alpha}\right)
   \right].                                           \tag{10.21}
\end{split}
\]
The second line is comparison with the integral of
\([x\log(K'L/x)]^{-1}\); enlarge \(K'\) if necessary so that this function
is decreasing on the summation interval.  Equation (10.16) follows.  The
discarded zero mode is exactly
\[
   \frac1{L^2h_L}=\frac1T,                             \tag{10.22}
\]
so it is only an \(L\)-independent constant and is not the source of the
double logarithm.

Apply the finite-volume master inequality (7.3) at the same field:
\[
   m_{L,h_L}
   \le
   \frac1{\sqrt{(n-1)T A_L(h_L)}}.                    \tag{10.23}
\]
The tilt bridge (9.8) is a finite-volume statement and therefore permits
this \(L\)-dependent choice.  Because
\[
   \beta h_LL^2=1,                                    \tag{10.24}
\]
it gives
\[
   \langle|\mathbf M_L|^2\rangle_{L,0}
   \le\frac{n}{\tanh(1)}m_{L,h_L}.                    \tag{10.25}
\]
Combining (10.16), (10.23), and (10.25), for every finite \(n\ge2\) and
fixed \(0<T<\infty\) there are \(C_{n,T},L_{n,T}<\infty\) such that
\[
   \boxed{
   \langle|\mathbf M_L|^2\rangle_{L,0}
   \le\frac{C_{n,T}}{\sqrt{\log\log L}}}
   \qquad(L\ge L_{n,T}\text{ even}).                 \tag{10.26}
\]
This is a rigorous asymptotic upper envelope.  It is not a matching bound,
an exact decay rate, or a sharp numerical prediction at accessible sizes.

### 10.5 Why this is not a theorem for all long-range models

For
\[
   J(R)\asymp |R|^{-(2+\sigma)},\qquad0<\sigma<2,
\]
one has \(E(q)\asymp|q|^\sigma\).  Then
\[
   \int_0^\delta\frac{k\,dk}{k^\sigma}<\infty.          \tag{10.27}
\]
The hypothesis of Theorem 1 fails.  The theorem is silent in this regime,
and continuous-symmetry long-range order is not excluded.

## 11. \(O(n)\) subtleties relative to XY

| Point | XY, \(n=2\) | General hard-spin \(O(n)\) |
|---|---|---|
| Single-site coordinates | one periodic angle | sphere \(S^{n-1}\) |
| Derivative | \(\partial_{\theta_x}\) | Killing generator \(\mathcal L_x^{1a}\) |
| Measure identity | periodic integration by parts | rotation-invariant sphere integration by parts |
| Transverse channels | one | \(n-1\) |
| Pair second variation | planar dot product | selected-plane projection \(S_x^1S_y^1+S_x^aS_y^a\) |
| Parseval budget | \(V\sum_x\sin^2\theta_x\) | \(V\sum_x[1-(S_x^1)^2]\) |
| Zero-field moment | factor \(1/2\) | factor \(1/n\) |
| Theorem conclusion | no ferromagnetic LRO | no \(O(n)\)-vector LRO |
| Remaining phase | BKT or logarithmic alternatives may be relevant | the theorem alone gives no common correlation law |

There is no odd--even obstruction in this proof.  Every transverse
\((1,a)\) plane is treated separately and the inequalities are added only
after they have been established.  Odd--even effects that can occur in
soft-spin fluctuation spectra or in mode-coupling analyses concern a
different question and do not alter (7.3).

The \(n\)-dependence also should not be overinterpreted.  The factor \(n-1\)
strengthens the displayed upper bound on a field-selected component, but the
theorem does not determine the finite-temperature correlation length,
topological defects, or the nature of a nonordered phase.  In particular,
the BKT mechanism specific to \(O(2)\) is not automatically inherited by
\(O(3)\) or higher.

## 12. Relation to earlier rigorous work

Mermin's 1967 classical inequality established a direct classical route to
absence of ordering for several spin systems.  The rotation generator
\[
   L_{\alpha\beta}
   =
   S_\alpha\partial_{S_\beta}
   -
   S_\beta\partial_{S_\alpha}
\]
and its invariant-measure integration by parts are also displayed in
Nussinov's treatment of classical \(O(n)\) systems.  Parts of that
presentation specialize to \(n=2\); Sections 6--7 above supply the full
transverse-channel accounting needed here.

The current finite-volume argument is useful because it reaches the
zero-field quantity
\(\langle|\mathbf M_L|^2\rangle_{L,0}\) directly for a
size-dependent torus sequence.  It is consistent with broader
infinite-volume Gibbs-state invariance results based on recurrent
interaction walks, but does not require an ergodic-decomposition step for
its stated finite-volume conclusion.

## 13. Dependency audit

The proof uses the following implications:

1. rotation-invariant sphere measure
   \(\Rightarrow\) Gibbs integration by parts;
2. integration by parts plus Cauchy--Schwarz
   \(\Rightarrow\) classical Bogoliubov inequality;
3. hard-spin constraint plus \(J_L\ge0\)
   \(\Rightarrow\) denominator upper bound;
4. \(n-1\) transverse channels plus Parseval
   \(\Rightarrow\) finite-volume estimate (3.6);
5. uniform kernel convergence
   \(\Rightarrow\) fixed-\(h\) Riemann-sum limit;
6. infrared divergence
   \(\Rightarrow\) vanishing field-selected magnetization;
7. \(SO(n)\) invariance plus bounded exponential tilt
   \(\Rightarrow\) vanishing zero-field second moment.

The deterministic code in `issue158/on_proof.py` and
`scripts/on_theorem_audit.py` checks the finite-dimensional rotation algebra,
the projected-pair identity, transverse Parseval accounting, and the stated
scope.  Those checks are regression evidence.  The analytic proof above,
not the numerical residuals, establishes the theorem.
