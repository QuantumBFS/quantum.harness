# Symmetric oddcycle interval family

Define

\[
B(z)=
\begin{pmatrix}
0&0&2&0&0\\
2&0&0&0&0\\
0&2&0&1&0\\
0&0&0&1&1\\
0&0&-z&0&1
\end{pmatrix},
\qquad
I=\left[\frac{99}{100},\frac{101}{100}\right].
\]

The alphabet is the continuum

\[
\mathcal A_I=\{B(z),B(z)^{\mathsf T}:z\in I\}.
\]

The parameter is not shared by a word.  At every time slice, the
orientation and \(z_i\in I\) may be chosen independently.  The exact
certificate proves

\[
\boxed{\det(I+W)>0\quad\text{for every finite }W\in\langle\mathcal A_I\rangle.}
\]

## Exact interval semantics

Every atom entry is affine in its own \(z_i\).  The verifier represents an
interval endpoint by an integer numerator over 100.  After \(n\) letters,
all propagated matrix intervals have the shared denominator \(100^n\).
Thus every bound is integer interval arithmetic; no floating-point result
is promoted.

This per-letter propagation is stronger than substituting one shared
symbolic \(z\) into a whole word.  It encloses all independently varying
sequences \(z_1,\ldots,z_n\).

## Lengths one through twelve

The verifier propagates grades 1 through 4 for all 8,190 nonempty binary
orientation words through length 12.  Adding the exact scalar grades
\(\chi_0=1\) and \(\chi_5=8^n\), the global lower bounds are

\[
\det(I+W)\geq\frac{3499}{100},\qquad
\chi_0+\chi_2+\chi_3+\chi_5\geq\frac{1699}{100}.
\]

Both minima occur at the one-letter word `0`.  These are simultaneous
interval bounds over every independent choice of the letter parameters.

## Grade-three/four tail

With \(D=\operatorname{diag}(1,1,1,-1,1)\),

\[
D(\wedge^4B(z))D=
\begin{pmatrix}
8&8&0&4&0\\
0&8&0&4&0\\
0&0&0&4&0\\
0&0&0&0&4\\
4z&4z&4&2z&0
\end{pmatrix}\geq0
\]

throughout \(I\), and both orientations retain the common weight-8 loop at
state zero.

Exact interval propagation of every one of the 8,192 orientation blocks of
length 13 proves

\[
100\sup_{z_1,\ldots,z_{13}\in I}
\lVert\wedge^3W\rVert_F^2
<
\inf_{z_1,\ldots,z_{13}\in I}
\bigl(D\wedge^4W D\bigr)_{00}^2.
\]

The worst certified word is `0000001111111`.  With the common denominator
\(100^{26}\), its strict raw numerator margin is

```text
17885432888260091992976094678617191678771759066816123079705733862324608427900
```

Every remainder of length at most 12 obeys the corresponding factor-10
bound; the empty remainder saturates it, while the smallest nonempty margin
is \(3502563/10000\).

The same block concatenation argument as at the fixed point therefore gives

\[
\chi_3(W)+\chi_4(W)>0\qquad(|W|\geq13)
\]

uniformly over the continuum alphabet.

## Low-sector tail

Exact interval evaluation of all leading principal minors proves,
uniformly on \(I\),

\[
6I-B(z)^{\mathsf T}B(z)\succ0,
\qquad
29I-(\wedge^2B(z))^{\mathsf T}\wedge^2B(z)\succ0.
\]

The smallest certified leading-minor lower bounds are respectively 2 and
13.  Hence every independently varying word satisfies

\[
|\chi_1(W)|\leq5(\sqrt6)^n,\qquad
|\chi_2(W)|\leq10(\sqrt{29})^n.
\]

At \(n=6\),

\[
8^6-5\cdot6^3-10\cdot29^3=17174>0,
\]

and the normalized ratios decrease thereafter.  Thus

\[
\chi_0+\chi_1+\chi_2+\chi_5>0\qquad(n\geq6).
\]

Combining this with the grade-three/four bound covers every \(n\geq13\);
the exact interval enumeration covers the remaining lengths.

## Physical realization

\(\det B(z)=8\), and

\[
\det(-xI-B(z))
=-x^5-2x^4-x^3+(z-8)x^2-16x-8<0
\]

for \(x>0\) and \(z\in I\).  Therefore no \(B(z)\) has a negative real
eigenvalue, so every atom admits a real logarithm.  Pairing each atom with
its transpose gives the real Hermitian inverse construction used by the
fixed candidate, now for a genuine continuum of independently selectable
auxiliary-field letters.
