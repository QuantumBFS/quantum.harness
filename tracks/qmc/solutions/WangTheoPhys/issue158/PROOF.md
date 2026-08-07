# Issue #158 rigorous theorem-to-Monte-Carlo audit

Date: 2026-07-29.

## Verdict

For the two-dimensional classical XY model with positive coupling

$$
J_R=\frac{c_\infty}{|R|^4},
$$

and for the normalized minimum-image torus sequence used in the numerical
work, the following conclusions can be established:

1. the infinite-lattice kernel obeys

   $$
   E(k)=\frac{\pi c_\infty}{2}|k|^2\log\frac1{|k|}
        +O(|k|^2);
   $$

2. the infrared integral diverges as a log-log;
3. a direct classical Bogoliubov inequality excludes finite-temperature
   spontaneous magnetization;
4. the recurrent-random-walk theorem of Ioffe, Shlosman and Velenik implies
   that every infinite-volume Gibbs state is $SO(2)$-invariant;
5. a block-averaging/Jensen argument then also forces the **diagonal torus
   observable**

   $$
   \left\langle |M_L|^2\right\rangle_{\Lambda_L}
   $$

   to vanish as $L\to\infty$.

Thus the distinction between the field-defined spontaneous magnetization and
the zero-field Monte Carlo measurement of $M^2$ does not provide an escape
from the theorem.  A positive fitted intercept at accessible sizes can only be
a finite-size/extrapolation result, not the true thermodynamic limit, provided
the stated interaction convention is used.

The theorem does **not** by itself prove the sharper low-temperature law

$$
g(r)\sim[\log r]^{-p(T)}.
$$

That decay is a spin-wave/RG candidate and still requires control of nonlinear
and vortex effects.

## 1. Model and normalization

Let

$$
\Lambda_L=(\mathbb Z/L\mathbb Z)^2,\qquad N=L^2,
$$

and consider

$$
H_{L,h}(\theta)
=-\sum_{\{x,y\}\subset\Lambda_L}J^{(L)}_{x-y}
  \cos(\theta_x-\theta_y)
-h\sum_x\cos\theta_x,
\qquad h>0.
$$

The infinite square-lattice interaction is

$$
J_R=c_\infty |R|^{-4},\qquad R\in\mathbb Z^2\setminus\{0\},
$$

with total coupling fixed to four.  The Epstein-zeta identity

$$
\sum_{(m,n)\ne(0,0)}\frac1{(m^2+n^2)^2}
=4\zeta(2)\beta_{\rm Dir}(2)
=\frac{2\pi^2}{3}G
$$

gives

$$
c_\infty=\frac{6}{\pi^2G}
=0.6637008046138535\ldots ,
$$

where $G$ is Catalan's constant.

## 2. Marginal lattice kernel

Define

$$
E(k)=\sum_{R\ne0}J_R[1-\cos(k\cdot R)].
$$

Set $R_*=\lfloor |k|^{-1}\rfloor$ and divide the sum into
$|R|\le R_*$ and $|R|>R_*$.

For the near part,

$$
1-\cos(k\cdot R)
=\frac12(k\cdot R)^2+O(|k|^4|R|^4).
$$

After multiplication by $|R|^{-4}$, the summed remainder is

$$
O\!\left(
|k|^4\#\{R:|R|\le R_*\}
\right)
=O(|k|^4R_*^2)
=O(|k|^2).
$$

Circular-cutoff square-lattice symmetry gives

$$
\sum_{0<|R|\le R_*}\frac{R_aR_b}{|R|^4}
=\frac{\delta_{ab}}2
\sum_{0<|R|\le R_*}\frac1{|R|^2},
$$

and the lattice-shell estimate is

$$
\sum_{0<|R|\le R_*}|R|^{-2}
=2\pi\log R_*+O(1).
$$

Therefore,

$$
E_{<}(k)
=\frac{\pi c_\infty}{2}|k|^2\log\frac1{|k|}
+O(|k|^2).
$$

For the far part,

$$
0\le E_{>}(k)
\le 2c_\infty\sum_{|R|>R_*}|R|^{-4}
=O(R_*^{-2})
=O(|k|^2).
$$

Consequently,

$$
\boxed{
E(k)
=\rho_{\log}|k|^2\log\frac1{|k|}
+O(|k|^2),
\qquad
\rho_{\log}=\frac{\pi c_\infty}{2}
=1.0425387859782584\ldots
}
$$

The coefficient is positive.  Short-distance lattice corrections can change
the non-logarithmic $O(k^2)$ term but cannot cancel the leading logarithm.

## 3. Infrared divergence

For sufficiently small $k$,

$$
E(k)\le C|k|^2\log(C'/|k|).
$$

Hence

$$
\int_{|k|<\epsilon}\frac{d^2k}{E(k)}
\ge
\frac{2\pi}{C}
\int_0^\epsilon
\frac{dk}{k\log(C'/k)}
=\infty.
$$

With finite-size cutoff $k_{\min}\asymp L^{-1}$, the divergence is

$$
I_L\asymp\log\log L.
$$

Its extremely slow growth explains why the theorem can be hard to see
numerically, but it does not change the thermodynamic conclusion.

## 4. Direct classical infrared inequality

Define

$$
D_k=\sum_xe^{ik\cdot x}\frac{\partial}{\partial\theta_x},
\qquad
A_k=\sum_xe^{-ik\cdot x}\sin\theta_x,
$$

and

$$
m_{L,h}
=\frac1N\sum_x\langle\cos\theta_x\rangle_{L,h}.
$$

Periodic integration by parts under the finite-volume Gibbs measure gives

$$
\langle D_kA_k\rangle
=\beta\langle A_kD_kH\rangle,
$$

and

$$
\langle D_{-k}D_kH\rangle
=\beta\langle|D_kH|^2\rangle.
$$

Cauchy--Schwarz yields the classical Bogoliubov inequality

$$
\langle|A_k|^2\rangle
\langle D_{-k}D_kH\rangle
\ge
T|\langle D_kA_k\rangle|^2.
$$

Direct differentiation gives

$$
\langle D_kA_k\rangle=Nm_{L,h}
$$

and

$$
\begin{aligned}
D_{-k}D_kH
={}&h\sum_x\cos\theta_x\\
&+2\sum_{x<y}J^{(L)}_{x-y}
[1-\cos(k\cdot(x-y))]
\cos(\theta_x-\theta_y).
\end{aligned}
$$

Since $\cos(\theta_x-\theta_y)\le1$,

$$
\langle D_{-k}D_kH\rangle
\le N[h+E_L(k)].
$$

Thus

$$
\langle|A_k|^2\rangle
\ge
\frac{TNm_{L,h}^2}{h+E_L(k)}.
$$

Parseval's identity,

$$
\sum_k|A_k|^2
=N\sum_x\sin^2\theta_x
\le N^2,
$$

then gives

$$
\boxed{
1\ge
Tm_{L,h}^2
\frac1N\sum_k\frac1{h+E_L(k)}.
}
$$

No quantum commutator or $S\to\infty$ limit appears in this derivation.

For fixed $h>0$, take $L\to\infty$.  The regulator makes the momentum
integrand bounded and continuous, so the Riemann sum converges:

$$
1\ge
Tm_h^2
\int_{\rm BZ}\frac{d^2k}{(2\pi)^2}
\frac1{h+E(k)}.
$$

Monotone convergence and the marginal kernel imply that the integral diverges
as $h\downarrow0$.  More quantitatively, if $k_h$ solves

$$
k_h^2\log(C'/k_h)\asymp h,
$$

then

$$
\int\frac{d^2k}{h+E(k)}
\gtrsim\log\log\frac1{k_h}
\asymp\log\log\frac1h.
$$

Therefore,

$$
m_h^2
\lesssim
\frac1{T\log\log(1/h)}
\longrightarrow0.
$$

This proves the absence of field-defined finite-temperature spontaneous
magnetization.

## 5. Recurrent random walk and all Gibbs states

Normalize

$$
p(R)=\frac{J_R}{\sum_{R'}J_{R'}}=\frac{J_R}{4}.
$$

Then

$$
1-\widehat p(k)=\frac{E(k)}4.
$$

The Chung--Fuchs recurrence integral is

$$
\int_{\rm BZ}\frac{d^2k}{1-\widehat p(k)}
\asymp
\int_0^\epsilon\frac{dk}{k\log(1/k)}
=\infty.
$$

Thus the interaction-induced random walk is recurrent.

[Theorem 2 of Ioffe, Shlosman and
Velenik](https://arxiv.org/abs/math/0110127) states that, for a recurrent
symmetric walk, continuous invariant two-body interaction and invariant
single-spin measure, all Gibbs states are invariant under the compact
continuous symmetry group.  Here:

- the spin space is $S^1$;
- the group is $SO(2)$;
- $U(\theta,\phi)=-\cos(\theta-\phi)$ is continuous and invariant;
- the single-spin measure is Haar measure;
- the walk is recurrent.

Therefore every Gibbs state of the infinite-volume $R^{-4}$ XY model is
$SO(2)$-invariant.

This theorem is independent of Bruno's quantum-spin argument and is stronger
than the statement $m_h\to0$.

## 6. Minimum-image thermodynamic limit

Represent the minimum-image displacements by

$$
Q_L=[-L/2,L/2)^2\cap\mathbb Z^2
$$

and extend the finite coupling by zero:

$$
J_L^{\rm MI}(R)
=c_L|R|^{-4}\mathbf 1_{\{R\in Q_L\setminus0\}},
\qquad
\sum_RJ_L^{\rm MI}(R)=4.
$$

The omitted tail obeys

$$
\sum_{R\notin Q_L}|R|^{-4}=O(L^{-2}).
$$

Writing

$$
S_L=\sum_{R\in Q_L\setminus0}|R|^{-4},
\qquad
c_L=\frac4{S_L},
$$

gives

$$
c_L-c_\infty=O(L^{-2}).
$$

Moreover,

$$
\begin{aligned}
\sum_R|J_L^{\rm MI}(R)-J_R|
&\le
|c_L-c_\infty|
\sum_{R\in Q_L\setminus0}|R|^{-4}\\
&\quad+
c_\infty\sum_{R\notin Q_L}|R|^{-4}\\
&=O(L^{-2}).
\end{aligned}
$$

Consequently,

$$
\sup_k|E_L^{\rm MI}(k)-E(k)|
\le
2\sum_R|J_L^{\rm MI}(R)-J_R|
=O(L^{-2}).
$$

Every local weak subsequential limit of the translation-invariant torus Gibbs
measures is therefore a Gibbs state of the fixed infinite-volume interaction.

At the lowest momentum,

$$
E(2\pi/L)\asymp L^{-2}\log L,
$$

so the uniform absolute estimate permits a relative convention effect

$$
\frac{E_L^{\rm MI}(2\pi/L)-E(2\pi/L)}
     {E(2\pi/L)}
=O\!\left(\frac1{\log L}\right).
$$

Thus minimum image and periodic image have the same thermodynamic model but
can differ precisely at the slow scale that contaminates inverse-logarithmic
intercept fits.

## 7. From all-Gibbs-state invariance to the Monte Carlo $M^2$

This step requires care because the numerical observable uses a block whose
size grows together with the torus.  The required uniform bridge follows from
convexity.

For a fixed square block $Q_R$ and a torus with $L>2R$, define its translated
block magnetization

$$
B_{R,x}=\frac1{|Q_R|}\sum_{u\in Q_R}S_{x+u}.
$$

Every torus site occurs equally often in the translated blocks, so

$$
M_L=\frac1N\sum_xS_x
=\frac1N\sum_xB_{R,x}.
$$

By Jensen's inequality,

$$
|M_L|^2
\le
\frac1N\sum_x|B_{R,x}|^2.
$$

The zero-field torus Gibbs measure is translation invariant, hence

$$
\left\langle|M_L|^2\right\rangle_L
\le
\left\langle|B_{R,0}|^2\right\rangle_L.
$$

Take any subsequence realizing

$$
\limsup_{L\to\infty}
\left\langle|M_L|^2\right\rangle_L
$$

and then a locally weakly convergent subsubsequence with limit $\mu$.  For
each fixed $R$,

$$
\limsup_{L\to\infty}
\left\langle|M_L|^2\right\rangle_L
\le
\left\langle|B_{R,0}|^2\right\rangle_\mu.
$$

The translation-ergodic components of $\mu$ are themselves Gibbs states.
The Ioffe--Shlosman--Velenik theorem makes each of them $SO(2)$-invariant, so
its vector magnetization is zero.  The mean ergodic theorem therefore gives

$$
\lim_{R\to\infty}
\left\langle|B_{R,0}|^2\right\rangle_\mu=0.
$$

Since the preceding upper bound holds for every fixed $R$,

$$
\boxed{
\lim_{L\to\infty}
\left\langle|M_L|^2\right\rangle_L=0.
}
$$

This closes the apparent loophole between a theorem stated in terms of
spontaneous symmetry breaking and a Monte Carlo extrapolation of the
zero-field squared magnetization.

## 8. Quantum scope

[Bruno's Theorem
2](https://doi.org/10.1103/PhysRevLett.87.137203) is a finite-spin quantum
statement.  Its key estimate has the form

$$
\Delta(k)
\le |B|S+2S(S+1)\widetilde E(k),
$$

and the denominator direction is the one required by the Bogoliubov
inequality.  For positive ferromagnetic coupling,

$$
\widetilde E(k)=E(k).
$$

With classical scaling

$$
J_Q=J_{\rm cl}/S^2,
\qquad
B_Q=h/S,
$$

the denominator tends regularly to

$$
h+2E_{\rm cl}(k).
$$

No decisive error is exposed at the quantum level.  More importantly, the
classical proof and recurrent-walk theorem above do not depend on taking this
limit.

## 9. Exact scope of the conclusion

What is proved:

$$
m(T)=0,\qquad
\lim_{L\to\infty}\langle|M_L|^2\rangle_L=0
\quad
\text{for every }T>0.
$$

What is strongly motivated but not proved here:

$$
g(r)\sim[\log r]^{-p(T)},\qquad p(T)>0.
$$

What the public Monte Carlo analysis must therefore decide is not whether
true $g_0>0$ can coexist with the theorem, but whether accessible sizes can
distinguish zero asymptote from extremely slow logarithmic decay.
