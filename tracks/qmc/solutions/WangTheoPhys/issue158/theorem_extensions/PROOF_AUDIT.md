# General finite-volume infrared criterion and marginal $1/r^4$ corollary

## 0. Result, novelty, and scope

This note separates a reusable finite-volume theorem from its marginal
long-range application.

The **General finite-volume infrared criterion** applies to ferromagnetic
classical XY models on tori in arbitrary dimension. It assumes uniform
kernel convergence and divergence of a regulated infrared integral. It
concludes directly that the zero-field second moment measured in simulations
vanishes:

$$
\boxed{
\lim_{L\to\infty}
\left\langle |\mathbf M_L|^2\right\rangle_{L,0}=0
}.
$$

The two-dimensional minimum-image interaction is then treated as the
**marginal $1/r^4$ corollary**. Explicit lattice estimates verify the general
hypotheses for the exact size-dependent sequence used in the Monte Carlo
study.

The proof is finite-volume and classical. It uses:

1. periodic Gibbs integration by parts;
2. Cauchy--Schwarz and discrete Parseval;
3. uniform convergence of Fourier kernels at fixed field;
4. divergence of the regulated infrared integral;
5. a one-variable exponential-tilt inequality.

The general result is XY-specific: it uses angular derivatives and the
two-component rotational identity at zero field. It is not an $O(n)$ theorem.
Extending it to general spheres would require a separate proof
with rotation generators and transverse-component bookkeeping.

The proof does not use Bruno's quantum theorem, a formal
$$
S\to\infty
$$
limit, or an unpublished finite-torus adaptation of an infinite-volume
correlation theorem. Numerical calculations check conventions and floating
point implementation; they are not proof premises.

### Hypothesis map

| Layer | Assumption | Role |
|---|---|---|
| General geometry | \(T_L=(\mathbb Z/L\mathbb Z)^d\), \(N=L^d\) | finite-volume Fourier analysis |
| Spin space | \(\theta_x\in S^1\) | periodic integration by parts |
| Couplings | translation invariant, \(J_L(R)=J_L(-R)\ge0\) | denominator upper bound |
| Kernel limit | \(E_L\to E_\infty\) uniformly on the Brillouin zone | fixed-field Riemann limit |
| Infrared condition | \(I(h)\to\infty\) as \(h\downarrow0\) | vanishing field magnetization |
| Zero-field symmetry | exact \(O(2)\) invariance | component-to-vector second moment |
| Limit order | fixed \(h>0\), then \(L\to\infty\), then \(h\downarrow0\) | spontaneous-order limit |
| Marginal application | \(d=2\), \(J_L(R)=c_L|R_{\rm MI}|^{-4}\) | verifies the general hypotheses |
| Independent check | recurrent normalized coupling walk | ISV Theorem 2 |

---

## I. General finite-volume infrared criterion

### Definition 1 (ferromagnetic XY torus sequence)

Fix a positive integer dimension \(d\). For each even \(L\), let

$$
T_L=(\mathbb Z/L\mathbb Z)^d,
\qquad
N=L^d.
$$

Choose one integer representative for every torus displacement. Let

$$
J_L(R)=J_L(-R)\ge0,
\qquad
R\in T_L\setminus\{0\},
$$

be a translation-invariant coupling. No finite-range or power-law assumption
is imposed in the general theorem.

In a field \(h\ge0\) along the first spin component, define

$$
H_{L,h}(\theta)
=
-\frac12
\sum_{x\in T_L}\sum_{R\ne0}
J_L(R)\cos(\theta_x-\theta_{x+R})
-h\sum_{x\in T_L}\cos\theta_x.
$$

The factor \(1/2\) fixes pair counting, including self-inverse torus
displacements. At temperature

$$
0<T<\infty,
\qquad
\beta=T^{-1},
$$

write

$$
\langle F\rangle_{L,h}
=
\frac{
\int F(\theta)e^{-\beta H_{L,h}(\theta)}
\prod_xd\theta_x/(2\pi)
}{
\int e^{-\beta H_{L,h}(\theta)}
\prod_xd\theta_x/(2\pi)
}.
$$

The magnetization and the field-selected component are

$$
\mathbf M_L
=
\frac1N\sum_x(\cos\theta_x,\sin\theta_x),
\qquad
m_{L,h}
=
\left\langle M_L^{(1)}\right\rangle_{L,h}.
$$

For torus momentum

$$
q=\frac{2\pi}{L}n,
\qquad
n\in T_L,
$$

define the excitation kernel

$$
E_L(q)
=
\sum_{R\ne0}
J_L(R)[1-\cos(q\cdot R)].
$$

Using the chosen integer representatives, the same expression defines a
continuous \(2\pi\)-periodic trigonometric polynomial on the fixed
Brillouin zone

$$
\mathrm{BZ}=[-\pi,\pi]^d.
$$

### Assumption A (uniform kernel convergence)

There is a continuous nonnegative periodic function

$$
E_\infty:\mathrm{BZ}\to[0,\infty)
$$

such that

$$
\boxed{
\sup_{q\in\mathrm{BZ}}
|E_L(q)-E_\infty(q)|
\longrightarrow0
}.
$$

### Assumption B (regulated infrared divergence)

For \(h>0\), define the regulated infrared integral

$$
I(h)
=
\int_{\mathrm{BZ}}
\frac{d^dq}{(2\pi)^d}
\frac1{h+E_\infty(q)}.
$$

Assume

$$
\boxed{
\lim_{h\downarrow0}I(h)=\infty
}.
$$

For every fixed \(h>0\), the integral is finite because its integrand is
continuous and bounded by \(h^{-1}\).

### Lemma 1 (finite-volume classical Bogoliubov inequality)

For every torus momentum \(q\), every \(h>0\), and every \(T>0\),

$$
\left\langle|A_q|^2\right\rangle_{L,h}
\left\langle D_{-q}D_qH_{L,h}\right\rangle_{L,h}
\ge
T\left|
\left\langle D_qA_q\right\rangle_{L,h}
\right|^2,
$$

where

$$
D_q
=
\sum_xe^{iq\cdot x}\frac{\partial}{\partial\theta_x},
\qquad
A_q
=
\sum_xe^{-iq\cdot x}\sin\theta_x.
$$

Consequently,

$$
\boxed{
1
\ge
Tm_{L,h}^2
\frac1N\sum_q\frac1{h+E_L(q)}
}.
$$

#### Proof

All angle variables are periodic. Integration by parts in the finite Gibbs
measure gives

$$
\left\langle D_qA_q\right\rangle
=
\beta\left\langle A_qD_qH\right\rangle.
$$

Applying the same identity to \(D_qH\) gives

$$
\left\langle D_{-q}D_qH\right\rangle
=
\beta
\left\langle D_{-q}H\,D_qH\right\rangle
=
\beta\left\langle|D_qH|^2\right\rangle.
$$

Cauchy--Schwarz therefore yields

$$
\left|
\left\langle D_qA_q\right\rangle
\right|^2
\le
\beta^2
\left\langle|A_q|^2\right\rangle
\left\langle|D_qH|^2\right\rangle
=
\beta
\left\langle|A_q|^2\right\rangle
\left\langle D_{-q}D_qH\right\rangle.
$$

Multiplication by \(T=\beta^{-1}\) proves the first inequality.

Direct differentiation gives

$$
D_qA_q=\sum_x\cos\theta_x,
$$

and hence

$$
\left\langle D_qA_q\right\rangle_{L,h}
=Nm_{L,h}.
$$

The pair-counting convention gives the exact identity

$$
\begin{aligned}
D_{-q}D_qH_{L,h}
={}&
h\sum_x\cos\theta_x\\
&+
\sum_{x,R}
J_L(R)[1-\cos(q\cdot R)]
\cos(\theta_x-\theta_{x+R}).
\end{aligned}
$$

Because \(J_L(R)\ge0\), \(m_{L,h}\le1\), and \(\cos u\le1\),

$$
\left\langle D_{-q}D_qH_{L,h}\right\rangle_{L,h}
\le
N[h+E_L(q)].
$$

The preceding estimates imply

$$
\left\langle|A_q|^2\right\rangle_{L,h}
\ge
\frac{TNm_{L,h}^2}{h+E_L(q)}.
$$

There are exactly \(N\) torus momenta. Discrete Parseval gives

$$
\sum_q|A_q|^2
=
N\sum_x\sin^2\theta_x
\le N^2.
$$

Summing the lower bound over \(q\) and dividing by \(N^2\) proves the boxed
inequality. \(\square\)

### Lemma 2 (fixed-field thermodynamic bound)

Under Assumption A, for every fixed \(h>0\),

$$
\boxed{
\limsup_{L\to\infty}m_{L,h}^2
\le
\frac1{T I(h)}
}.
$$

#### Proof

At fixed \(h>0\), the map

$$
x\longmapsto\frac1{h+x}
$$

is Lipschitz on \([0,\infty)\), with Lipschitz constant \(h^{-2}\).
Assumption A therefore implies

$$
\sup_{q\in\mathrm{BZ}}
\left|
\frac1{h+E_L(q)}
-
\frac1{h+E_\infty(q)}
\right|
\le
\frac{\|E_L-E_\infty\|_\infty}{h^2}
\longrightarrow0.
$$

The limiting reciprocal kernel is continuous and periodic. Hence the torus
momentum average is a Riemann sum:

$$
\frac1N\sum_q\frac1{h+E_L(q)}
\longrightarrow
\int_{\mathrm{BZ}}
\frac{d^dq}{(2\pi)^d}
\frac1{h+E_\infty(q)}
=I(h).
$$

Apply Lemma 1 and take \(\limsup\). This argument does not assume that

$$
\lim_{L\to\infty}m_{L,h}
$$

exists. \(\square\)

### Lemma 3 (exponential-tilt bridge)

Let \(X\in[-1,1]\) have a probability law symmetric under

$$
X\mapsto-X.
$$

For \(t\ge0\), define

$$
\mathbb E_t[f(X)]
=
\frac{\mathbb E[f(X)e^{tX}]}{\mathbb E[e^{tX}]}.
$$

Then

$$
\boxed{
\mathbb E_tX
\ge
\tanh(t)\,\mathbb EX^2
}.
$$

#### Proof

Let \(Q=|X|\). Symmetry gives

$$
\mathbb E_tX
=
\frac{\mathbb E[Q\sinh(tQ)]}{\mathbb E[\cosh(tQ)]}
=
\mathbb E_w[Q\tanh(tQ)],
$$

where

$$
d\mathbb P_w
=
\frac{\cosh(tQ)}{\mathbb E[\cosh(tQ)]}\,d\mathbb P.
$$

Both functions

$$
f(Q)=Q\tanh(tQ),
\qquad
w(Q)=\cosh(tQ)
$$

are nondecreasing on \([0,1]\). For independent copies \(Q,Q'\),

$$
2\operatorname{Cov}(f(Q),w(Q))
=
\mathbb E[
(f(Q)-f(Q'))(w(Q)-w(Q'))
]
\ge0.
$$

Therefore

$$
\mathbb E_w[Q\tanh(tQ)]
\ge
\mathbb E[Q\tanh(tQ)].
$$

Concavity of \(\tanh\) on \([0,\infty)\), together with
\(\tanh(0)=0\), implies

$$
\tanh(tQ)\ge Q\tanh(t),
\qquad
0\le Q\le1.
$$

It follows that

$$
\mathbb E_tX
\ge
\tanh(t)\mathbb EQ^2
=
\tanh(t)\mathbb EX^2.
$$

\(\square\)

### Theorem 1 (General finite-volume infrared criterion)

Consider the ferromagnetic XY torus sequence of Definition 1 in arbitrary
dimension \(d\). If Assumptions A and B hold, then, for every

$$
0<T<\infty,
$$

the field-selected magnetization satisfies

$$
\boxed{
\lim_{h\downarrow0}
\limsup_{L\to\infty}m_{L,h}=0
},
$$

and the zero-field second moment satisfies

$$
\boxed{
\lim_{L\to\infty}
\left\langle|\mathbf M_L|^2\right\rangle_{L,0}=0
}.
$$

#### Proof

Lemma 2 and Assumption B give

$$
\limsup_{L\to\infty}m_{L,h}
\le
[TI(h)]^{-1/2}
\longrightarrow0
\qquad
(h\downarrow0).
$$

This proves the first statement with the physical order of limits fixed.

It remains to connect the field-selected one-point function to the
zero-field observable. At \(h=0\), global \(O(2)\) invariance makes the law of

$$
X=M_L^{(1)}
$$

symmetric. The same invariance exchanges the two spin components, so

$$
\left\langle(M_L^{(1)})^2\right\rangle_{L,0}
=
\left\langle(M_L^{(2)})^2\right\rangle_{L,0}.
$$

Because

$$
|\mathbf M_L|^2
=(M_L^{(1)})^2+(M_L^{(2)})^2,
$$

one has the exact identity

$$
\left\langle X^2\right\rangle_{L,0}
=
\frac12
\left\langle|\mathbf M_L|^2\right\rangle_{L,0}.
$$

The field term changes the zero-field Gibbs density by

$$
\exp\left(
\beta h\sum_x\cos\theta_x
\right)
=
\exp(\beta hN X).
$$

Thus the field measure is exactly the exponential tilt in Lemma 3 with

$$
t=\beta hN=\beta hL^d.
$$

Lemma 3 gives

$$
m_{L,h}
\ge
\frac12\tanh(\beta hL^d)
\left\langle|\mathbf M_L|^2\right\rangle_{L,0}.
$$

Fix \(h>0\) and let \(L\to\infty\). Since

$$
\tanh(\beta hL^d)\longrightarrow1,
$$

$$
\limsup_{L\to\infty}
\left\langle|\mathbf M_L|^2\right\rangle_{L,0}
\le
2\limsup_{L\to\infty}m_{L,h}.
$$

Now let \(h\downarrow0\). The right-hand side vanishes by the first part.
The left-hand side is nonnegative and independent of \(h\), so it is zero.
For a nonnegative sequence, zero limsup implies the asserted limit.
\(\square\)

### Corollary 1 (vanishing volume-averaged correlation)

Let

$$
C_L(R)
=
\left\langle
\mathbf S_0\cdot\mathbf S_R
\right\rangle_{L,0}.
$$

Translation invariance gives

$$
\left\langle|\mathbf M_L|^2\right\rangle_{L,0}
=
\frac1N\sum_{R\in T_L}C_L(R).
$$

Under the hypotheses of Theorem 1,

$$
\boxed{
\frac1N\sum_{R\in T_L}C_L(R)\longrightarrow0
}.
$$

This is a volume-average statement. The general theorem does not by itself
assert a pointwise correlation law.

---

## II. Marginal two-dimensional minimum-image application

### Definition 2 (the exact simulated sequence)

Set \(d=2\), let \(L\ge8\) be even, and choose

$$
D_L
=
\{-L/2,-L/2+1,\ldots,L/2-1\}^2.
$$

For \(R\in D_L\setminus\{0\}\), define

$$
J_L(R)=\frac{c_L}{|R|^4},
\qquad
c_L=\frac{\kappa}{S_L},
\qquad
S_L=\sum_{R\in D_L\setminus\{0\}}\frac1{|R|^4},
\qquad
\kappa=4.
$$

The fixed infinite-volume interaction is

$$
J_\infty(R)=\frac{c_\infty}{|R|^4},
\qquad
c_\infty=\frac{\kappa}{S_\infty},
\qquad
S_\infty
=
\sum_{R\in\mathbb Z^2\setminus\{0\}}|R|^{-4}.
$$

For the square lattice,

$$
S_\infty
=
4\zeta(2)\beta_{\rm Dir}(2),
\qquad
c_\infty
=
\frac6{\pi^2G},
$$

where \(G\) is Catalan's constant.

Extend \(J_L\) by zero outside \(D_L\) and denote the extension by \(J_L^0\).
Define

$$
E_L(q)
=
\sum_RJ_L^0(R)[1-\cos(q\cdot R)],
$$

and

$$
E_\infty(q)
=
\sum_RJ_\infty(R)[1-\cos(q\cdot R)].
$$

### Lemma 4 (explicit lattice tail)

For every \(r\ge2\),

$$
\boxed{
\sum_{\substack{R\in\mathbb Z^2\\|R|>r}}
|R|^{-4}
\le
\frac{8\pi}{(r-1)^2}
}.
$$

#### Proof

Let

$$
m=\lfloor r/\sqrt2\rfloor+1.
$$

If \(|R|>r\), then

$$
\|R\|_\infty>r/\sqrt2.
$$

The square shell \(\|R\|_\infty=n\) has \(8n\) points, all satisfying
\(|R|\ge n\). Hence

$$
\begin{aligned}
\sum_{|R|>r}|R|^{-4}
&\le
8\sum_{n=m}^\infty n^{-3}\\
&\le
8\left(
m^{-3}+\int_m^\infty x^{-3}\,dx
\right)\\
&\le
\frac{12}{m^2}
<
\frac{24}{r^2}
\le
\frac{8\pi}{(r-1)^2}.
\end{aligned}
$$

\(\square\)

### Lemma 5 (normalization and interaction convergence)

The exact normalization satisfies

$$
0<c_L-c_\infty=O(L^{-2}),
$$

and

$$
\boxed{
\|J_L^0-J_\infty\|_{\ell^1(\mathbb Z^2)}
=
2c_\infty(S_\infty-S_L)
=
O(L^{-2})
}.
$$

#### Proof

Because \(D_L\subset\mathbb Z^2\),

$$
S_L<S_\infty,
\qquad
c_L>c_\infty.
$$

Every omitted point has

$$
|R|>L/2-1.
$$

Lemma 4 therefore gives

$$
0<S_\infty-S_L
\le
\frac{8\pi}{(L/2-2)^2}
=O(L^{-2}).
$$

Since the four nearest neighbours give \(S_L\ge4\),

$$
c_L-c_\infty
=
\frac{\kappa(S_\infty-S_L)}{S_LS_\infty}
=O(L^{-2}).
$$

On \(D_L\), \(J_L^0-J_\infty\ge0\); outside \(D_L\), it equals
\(-J_\infty\). Using

$$
c_LS_L=c_\infty S_\infty=\kappa,
$$

$$
\begin{aligned}
\|J_L^0-J_\infty\|_1
&=
(c_L-c_\infty)S_L
+c_\infty(S_\infty-S_L)\\
&=
2c_\infty(S_\infty-S_L).
\end{aligned}
$$

\(\square\)

### Corollary 2 (uniform kernel convergence)

For every even \(L\ge8\),

$$
\boxed{
\sup_{q\in[-\pi,\pi]^2}
|E_L(q)-E_\infty(q)|
\le
2\|J_L^0-J_\infty\|_1
=O(L^{-2})
}.
$$

#### Proof

Use

$$
|1-\cos(q\cdot R)|\le2
$$

term by term and apply Lemma 5. \(\square\)

This proves Assumption A of the general theorem.

### Lemma 6 (marginal kernel upper bound)

Let

$$
J_\infty(R)=A|R|^{-4},
\qquad
A>0.
$$

For \(0<|q|\le1/2\),

$$
\boxed{
E_\infty(q)
\le
4A|q|^2
\left[
1+\log\frac2{|q|}+16\pi
\right]
}.
$$

Equivalently, for finite constants

$$
C=4A,
\qquad
K=2e^{1+16\pi},
$$

$$
E_\infty(q)
\le
C|q|^2\log\frac K{|q|}.
$$

#### Proof

Split the sum into

$$
|R|\le|q|^{-1}
$$

and its complement. In the near region,

$$
1-\cos(q\cdot R)
\le
\frac12|q|^2|R|^2.
$$

For \(M\ge1\), square-shell counting gives

$$
\sum_{0<|R|\le M}|R|^{-2}
\le
8\sum_{n=1}^{\lceil M\rceil}n^{-1}
\le
8[1+\log(2M)].
$$

Therefore

$$
E_{<}(q)
\le
4A|q|^2
\left[
1+\log\frac2{|q|}
\right].
$$

In the far region, Lemma 4 and \(1-\cos u\le2\) give

$$
E_{>}(q)
\le
\frac{16\pi A}{(|q|^{-1}-1)^2}
\le
64\pi A|q|^2.
$$

Adding the two contributions proves the claim. \(\square\)

### Lemma 7 (exact leading logarithmic coefficient)

As \(q\to0\),

$$
\boxed{
E_\infty(q)
=
\frac{\pi A}{2}|q|^2\log(1/|q|)
+O(|q|^2)
}.
$$

#### Proof

For

$$
F_{ij}(x)=\frac{x_ix_j}{|x|^4},
$$

comparison of each unit lattice cell with its continuum integral gives

$$
\sum_{0<|R|\le M}\frac{R_iR_j}{|R|^4}
=
\int_{1\le|x|\le M}
\frac{x_ix_j}{|x|^4}\,d^2x
+O(1).
$$

Indeed,

$$
|\nabla F_{ij}(x)|=O(|x|^{-3}),
$$

so the total cell-comparison error outside a fixed disk is bounded by

$$
\sum_{n=1}^\infty O(n)\,O(n^{-3})
<
\infty.
$$

Rotational integration gives

$$
\int_{1\le|x|\le M}
\frac{x_ix_j}{|x|^4}\,d^2x
=
\pi\delta_{ij}\log M.
$$

Set \(M=|q|^{-1}\). In the near region,

$$
1-\cos(q\cdot R)
=
\frac12(q\cdot R)^2
+O(|q|^4|R|^4).
$$

The Taylor remainder contributes

$$
A|q|^4
\sum_{|R|\le|q|^{-1}}O(1)
=O(|q|^2).
$$

The quadratic contribution is

$$
\begin{aligned}
\frac A2q_iq_j
\sum_{0<|R|\le|q|^{-1}}
\frac{R_iR_j}{|R|^4}
&=
\frac A2q_iq_j
\left[
\pi\delta_{ij}\log(1/|q|)+O(1)
\right]\\
&=
\frac{\pi A}{2}|q|^2\log(1/|q|)
+O(|q|^2).
\end{aligned}
$$

The far region is \(O(|q|^2)\) by Lemma 4. This completes the expansion.
\(\square\)

### Lemma 8 (regulated infrared divergence)

For the marginal kernel,

$$
\boxed{
\lim_{h\downarrow0}
\int_{[-\pi,\pi]^2}
\frac{d^2q}{(2\pi)^2}
\frac1{h+E_\infty(q)}
=\infty
}.
$$

More explicitly, fix \(0<q_0\le1/2\) and set \(r_h=\sqrt h\). For all
sufficiently small \(h\),

$$
I(h)
\ge
\frac1{4\pi C}
\log
\left[
\frac{\log(K/\sqrt h)}{\log(K/q_0)}
\right].
$$

#### Proof

For sufficiently small \(h\),

$$
r_h<q_0,
\qquad
C\log(K/r_h)\ge1.
$$

On the annulus

$$
r_h\le|q|\le q_0,
$$

one has

$$
h\le C|q|^2\log(K/|q|).
$$

Lemma 6 therefore implies

$$
h+E_\infty(q)
\le
2C|q|^2\log(K/|q|).
$$

Radial integration gives

$$
\begin{aligned}
I(h)
&\ge
\frac1{4\pi C}
\int_{r_h}^{q_0}
\frac{dq}{q\log(K/q)}\\
&=
\frac1{4\pi C}
\log
\left[
\frac{\log(K/r_h)}{\log(K/q_0)}
\right].
\end{aligned}
$$

The right-hand side diverges as \(h\downarrow0\). \(\square\)

### Corollary 3 (zero-field no-LRO for the simulated sequence)

For the minimum-image, size-normalized two-dimensional \(1/r^4\) XY torus
sequence and every finite temperature,

$$
\boxed{
\lim_{L\to\infty}
\left\langle|\mathbf M_L|^2\right\rangle_{L,0}=0
}.
$$

Also,

$$
\boxed{
\lim_{h\downarrow0}
\limsup_{L\to\infty}m_{L,h}=0
}.
$$

#### Proof

Corollary 2 verifies uniform kernel convergence. Lemma 8 verifies the
regulated infrared divergence. All remaining hypotheses of Theorem 1 follow
from Definition 2 and the ferromagnetic cosine Hamiltonian. Apply Theorem 1.
\(\square\)

The exact coefficient in Lemma 7 is physically useful and is audited
numerically, but the weaker upper bound in Lemma 6 already suffices for the
corollary.

---

## III. Independent infinite-volume routes

### Lemma 9 (recurrence of the interaction-induced walk)

Normalize the fixed coupling by

$$
p(R)=\frac{J_\infty(R)}{\kappa},
\qquad
\sum_Rp(R)=1.
$$

Its characteristic function satisfies

$$
1-\widehat p(q)
=
\frac{E_\infty(q)}{\kappa}.
$$

By Lemma 6,

$$
\int_{\mathrm{BZ}}
\frac{d^2q}{1-\widehat p(q)}
\ge
c\int_0^{q_0}
\frac{dq}{q\log(K/q)}
=\infty.
$$

The Chung--Fuchs criterion therefore makes the walk recurrent.
\(\square\)

### Theorem 2 (ISV symmetry theorem applied to the fixed model)

Every infinite-volume DLR Gibbs state of the fixed

$$
J_\infty(R)=c_\infty|R|^{-4}
$$

XY model at finite temperature is \(SO(2)\)-invariant.

#### Source and hypothesis map

Apply Theorem 2 of Ioffe, Shlosman, and Velenik,
*Communications in Mathematical Physics* **226**, 433 (2002),
<https://doi.org/10.1007/s002200200627>.

| ISV hypothesis | Present model |
|---|---|
| compact spin space | \(S^1\) |
| compact connected symmetry group | \(SO(2)\) |
| invariant single-site measure | Haar measure |
| invariant continuous pair energy | \(-\cos(\theta_x-\theta_y)\) |
| summable normalized coupling | \(p(R)\propto|R|^{-4}\) |
| recurrent associated walk | Lemma 9 |

This theorem is an independent fixed-model statement. It is not used to
derive the finite-torus zero-field second moment in Corollary 3.

### MMR Theorem 1(c) pointwise upper bound

Theorem 1(c) of Messager, Miracle-Solé, and Ruiz,
*Annales de l'Institut Henri Poincaré A* **40**, 85 (1984),
<https://www.numdam.org/item/AIHPA_1984__40_1_85_0/>, gives in its published
fixed-interaction thermodynamic-limit scope

$$
|C(R)|
\le
B_2(\beta)
[\log|R|]^{-\lambda_2(\beta)},
\qquad
\lambda_2(\beta)>0.
$$

This is a pointwise upper bound, not an exact asymptotic equality. A BKT
power law also obeys a sufficiently slow logarithmic upper bound. The result
is therefore not used to claim exact logarithmic QLRO.

---

## IV. Dependency graph and conclusion boundaries

The general route is

$$
\begin{gathered}
E_L\to E_\infty\text{ uniformly}
\quad+\quad
I(h)\to\infty\\
\Downarrow\\
\text{Bogoliubov fixed-field bound}\\
\Downarrow\\
\lim_{h\downarrow0}\limsup_{L\to\infty}m_{L,h}=0\\
\Downarrow\quad\text{exponential-tilt bridge}\\
\lim_{L\to\infty}
\langle|\mathbf M_L|^2\rangle_{L,0}=0.
\end{gathered}
$$

The marginal application verifies the two kernel hypotheses through

$$
\|J_L^0-J_\infty\|_1=O(L^{-2})
$$

and

$$
E_\infty(q)\le C|q|^2\log(K/|q|).
$$

### What is proved

| Statement | Status |
|---|---|
| general finite-volume XY infrared criterion | proved |
| zero-field minimum-image \(\langle|\mathbf M_L|^2\rangle\) plateau | excluded |
| field-selected spontaneous magnetization | excluded |
| volume-averaged correlation plateau | excluded |
| recurrence of the fixed \(1/r^4\) coupling walk | proved |
| all fixed-model Gibbs states are \(SO(2)\)-invariant | ISV theorem |
| MMR logarithmic-power pointwise upper bound | cited in published scope |
| low-temperature exponential clustering | excluded by Corollary 4 below |
| exact \(C(R)\sim[\log R]^{-p}\) | not proved |
| eventual BKT versus logarithmic QLRO | unresolved |
| general \(O(n)\) version | not proved |

### What would falsify the direct proof

At least one of the following would have to fail:

1. the finite Hamiltonian is not the registered symmetric pair-counted XY
   Hamiltonian;
2. the coupling used in the denominator estimate is not nonnegative;
3. periodic Gibbs integration by parts is invalid;
4. the exact second directional derivative is not the stated kernel form;
5. the uniform kernel limit does not hold;
6. the regulated infrared integral does not diverge;
7. the finite-field measure is not the exponential tilt of the zero-field
   measure with \(t=\beta hL^d\);
8. the zero-field law is not \(O(2)\)-invariant;
9. the order of limits is changed.

A positive intercept from finitely many sizes does not falsify any of these
statements.

---

## V. Low-temperature massless comparison

This section uses a second, independent comparison argument to strengthen
the low-temperature conclusion.  Here

$$
C_L(x)
=
\left\langle
\cos(\theta_0-\theta_x)
\right\rangle_{L,0}
$$

for a lattice displacement \(x\ne0\) represented in a sufficiently large
torus.  The word **massless** below has the precise restricted meaning that
the infinite-volume two-point function does not decay exponentially.  It
does not refer to a separately constructed spectral gap.

### Lemma 10 (embedded free nearest-neighbor box)

Fix \(x\in\mathbb Z^2\setminus\{0\}\).  Choose \(n\) so that the square

$$
\Lambda_n=[-n,n]^2\cap\mathbb Z^2
$$

contains \(0\) and \(x\), and identify this fixed square with its image in
every sufficiently large torus.  Then

$$
\boxed{
C_L(x)
\ge
C_{\Lambda_n,\beta c_\infty}^{\rm NN,free}(0,x)
}.
$$

On the right, the nearest-neighbor coupling is one and its effective
inverse temperature is \(\beta c_\infty\).

#### Pair-counting and proof

The Hamiltonian convention in Definition 1 is

$$
-\frac12\sum_u\sum_{R\ne0}
J_L(R)\cos(\theta_u-\theta_{u+R}).
$$

For an unordered nearest-neighbor pair \(\{u,v\}\), the two directed terms
\((u,v-u)\) and \((v,u-v)\) each carry the factor \(1/2\).  Their sum is
therefore

$$
-c_L\cos(\theta_u-\theta_v),
$$

not \(-c_L\cos(\theta_u-\theta_v)/2\).  Thus the unordered
nearest-neighbor pair coefficient of the torus model is exactly \(c_L\).
Lemma 5 gives

$$
c_L\ge c_\infty.
$$

On the same torus vertex set, retain only the nearest-neighbor edges whose
two endpoints lie in \(\Lambda_n\), lower their coefficients to
\(c_\infty\), delete every other edge, and leave all vertices outside
\(\Lambda_n\) isolated.  The original and comparison couplings are all
nonnegative; every deleted coupling is nonnegative, and the retained
couplings are lowered from \(c_L\) to the nonnegative value \(c_\infty\).
The comparison model is therefore one free nearest-neighbor box plus
isolated torus vertices.

Classical Ginibre coupling monotonicity now gives the claimed inequality.
The isolated-spin integrals factor from both the partition function and
the two-point numerator, leaving exactly the free-boundary box correlation.
\(\square\)

### Corollary 4 (non-exponential low-temperature correlations)

The quantifiers are essential.  Fix a nonzero lattice displacement \(x\).
Next fix a free box \(\Lambda_n\) containing \(0\) and \(x\).  First take
the torus limit \(L\to\infty\) at this fixed \(n\); only after that take
\(n\to\infty\).  Lemma 10 gives

$$
C_L(x)
\ge
C_{\Lambda_n,\beta c_\infty}^{\rm NN,free}(0,x).
$$

Consequently,

$$
\liminf_{L\to\infty} C_L(x)
\ge
C_{\Lambda_n,\beta c_\infty}^{\rm NN,free}(0,x).
$$

As \(n\) increases, Ginibre monotonicity makes the right-hand side
nondecreasing and bounded.  Its limit is, by the free-boundary definition,
the infinite-volume nearest-neighbor correlation.  Hence

$$
\boxed{
\liminf_{L\to\infty} C_L(x)
\ge
C_{\mathbb Z^2,\beta c_\infty}^{\rm NN}(0,x)
}.
$$

No nearest-neighbor periodic-boundary thermodynamic-limit theorem is
assumed in this step.

Theorem 1(ii) of van Engelenburg--Lis states that the unit-coupling
nearest-neighbor square-lattice XY model has a finite
\(\beta_c^{\rm NN}\) and, in the source's lattice-norm convention,

$$
C_{\mathbb Z^2,\beta'}^{\rm NN}(0,x)
\ge
\frac1{8|x|}
\qquad
(\beta'\ge\beta_c^{\rm NN}).
$$

Substituting \(\beta'=\beta c_\infty\) yields

$$
\boxed{
\beta\ge\frac{\beta_c^{\rm NN}}{c_\infty}
\quad\Longrightarrow\quad
\liminf_{L\to\infty} C_L(x)
\ge\frac{1}{8|x|}
}.
$$

Every local weak subsequential limit of the torus measures inherits this
fixed-\(x\) bound, since the two-point observable is bounded and local.
The lower bound is incompatible with exponential clustering as
\(|x|\to\infty\).  Combining it with Corollary 3 gives a nonempty
low-temperature regime with no finite-temperature ferromagnetic LRO in the
finite-volume second-moment sense and with non-exponential two-point decay.
\(\square\)

The proof dependencies are the classical coupling monotonicity of Ginibre
(1970) and Theorem 1(ii) of van Engelenburg--Lis (2023).
Fröhlich--Spencer (1981) is the historical
multiscale route to a low-temperature power-law lower bound, but it is not
a logical premise here.

This comparison does not determine whether the true asymptotics are a
standard BKT power law, a logarithmic law, or a crossover between them.  In
particular, it does not imply a uniform finite-\(L\) correlation bound for
all separations, exact power-law asymptotics, a universal stiffness jump,
or either endpoint of the eventual-BKT versus logarithmic-QLRO question.
