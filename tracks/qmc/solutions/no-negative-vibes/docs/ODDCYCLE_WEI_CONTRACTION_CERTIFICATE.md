# Exact common-\(R\) contraction certificate

This note records an exact novelty audit for the continuum alphabet
\(\{B(z),B(z)^{\mathsf T}\}\), \(99/100\le z\le101/100\).  It is independent
of the arbitrary-depth determinant proof.

Let

\[
w=(4,4,1,-5,5)^{\mathsf T},\qquad
R={2ww^{\mathsf T}\over83}-I .
\]

Then \(R=R^{\mathsf T}\), \(R^2=I\), \(\det R=1\), and \(R\) has signature
\((1,4)\).  Direct exact expansion gives the leading principal minors of
\(D_0=R-B(z)^{\mathsf T}R B(z)\):

\[
{153\over83},\quad {41769\over6889},\quad
{-3(1727z^2-48480z-4491)\over6889},
\]
\[
{-25487z^2+106080z-40329\over6889},\quad
{-3(16493z^2-51480z+18964)\over6889}.
\]

For \(D_1=R-B(z)R B(z)^{\mathsf T}\), they are

\[
{273\over83},\quad {41769\over6889},\quad
{153732\over6889},\quad {192843\over6889},
\]

followed by the same determinant as \(D_0\).

Substitute \(z=99/100+t/50\), \(0\le t\le1\).  The smallest degree-two
Bernstein coefficient for each nonconstant polynomial above is, in order,

\[
{1523807019\over68890000},\quad
{397103913\over68890000},\quad
{475092321\over68890000},\quad
{475092321\over68890000}.
\]

All are strictly positive.  Sylvester's criterion therefore proves
\(D_0\succ0\) and \(D_1\succ0\) uniformly on the full interval.  Thus both
orientations belong to one strict real common-\(R\) contraction class; the
oddcycle alphabet is not outside that Wei-type mechanism, although its
independent determinant theorem remains valid.

The identities and interval bounds are replayed without floating point by
`oracle/oddcycle_wei_contraction.py` and
`tests/test_oddcycle_wei_contraction.py`.
