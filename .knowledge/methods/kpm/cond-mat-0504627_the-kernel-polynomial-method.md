---
source: "https://arxiv.org/abs/cond-mat/0504627"
type: "arxiv"
canonical_id: "cond-mat/0504627"
title: "The kernel polynomial method"
authors: "A. Weisse, G. Wellein, Andreas Alvermann, H. Fehske"
year: "2005"
venue: "Reviews of Modern Physics"
arxiv_id: "cond-mat/0504627"
doi: "10.1103/RevModPhys.78.275"
full_text: yes
---

# The kernel polynomial method

**Authors:** A. Weisse, G. Wellein, Andreas Alvermann, H. Fehske

**Citation:** Reviews of Modern Physics, vol. 78, pp. 275-306, 2005

**arXiv:** [cond-mat/0504627](https://arxiv.org/abs/cond-mat/0504627)

**DOI:** [10.1103/RevModPhys.78.275](https://doi.org/10.1103/RevModPhys.78.275)

## Abstract

Efficient and stable algorithms for the calculation of spectral quantities and correlation functions are some of the key tools in computational condensed matter physics. In this article we review basic properties and recent developments of Chebyshev expansion based algorithms and the Kernel Polynomial Method. Characterized by a resource consumption that scales linearly with the problem dimension these methods enjoyed growing popularity over the last decade and found broad application not only in physics. Representative examples from the fields of disordered systems, strongly correlated electrons, electron-phonon interaction, and quantum spin systems we discuss in detail. In addition, we illustrate how the Kernel Polynomial Method is successfully embedded into other numerical techniques, such as Cluster Perturbation Theory or Monte Carlo simulation.

## Full Text

## The Kernel Polynomial Method

Alexander Weiße


School of Physics, The University of New South Wales, Sydney, NSW 2052, Australia [∗]


Gerhard Wellein


Regionales Rechenzentrum Erlangen, Universit¨at Erlangen, 91058 Erlangen, Germany


Andreas Alvermann and Holger Fehske


Institut f¨ur Physik, Ernst-Moritz-Arndt-Universit¨at Greifswald, 17487 Greifswald, Germany


(Dated: April 3, 2006)


Efficient and stable algorithms for the calculation of spectral quantities and correlation functions
are some of the key tools in computational condensed matter physics. In this article we review basic properties and recent developments of Chebyshev expansion based algorithms and the Kernel
Polynomial Method. Characterized by a resource consumption that scales linearly with the problem dimension these methods enjoyed growing popularity over the last decade and found broad
application not only in physics. Representative examples from the fields of disordered systems,
strongly correlated electrons, electron-phonon interaction, and quantum spin systems we discuss
in detail. In addition, we illustrate how the Kernel Polynomial Method is successfully embedded
into other numerical techniques, such as Cluster Perturbation Theory or Monte Carlo simulation.


PACS numbers: 02.70.Hm, 02.30.Mv, 71.15.-m



Contents


I. Introduction 1


II. Chebyshev expansion and the Kernel Polynomial
Method (KPM) 3
A. Basic features of Chebyshev expansion 3
1. Chebyshev polynomials 3
2. Modified moments 4
B. Calculation of moments 4
1. General considerations 4
2. Stochastic evaluation of traces 5
C. Kernel polynomials and Gibbs oscillations 6
1. Expansions of finite order & simple kernels 6
2. Fej´er kernel 7
3. Jackson kernel 8
4. Lorentz kernel 9
D. Implementational details and remarks 10
1. Discrete cosine & Fourier transforms 10
2. Integrals involving expanded functions 11
E. Generalization to higher dimension 11
1. Expansion of multivariate functions 11
2. Kernels for multidimensional expansions 11
3. Reconstruction with cosine transforms 12


III. Applications of KPM 12
A. Densities of states 12
1. General considerations 12
2. Non-interacting systems: Anderson model of
disorder 13
3. Interacting systems: Double exchange 14
B. Static correlations at finite temperature 15
C. Dynamical correlations at zero temperature 16
1. General considerations 16


∗New address: Institut f¨ur Physik, Ernst-Moritz-Arndt-Universit¨at
Greifswald, 17487 Greifswald, Germany



2. One-particle spectral function 17
3. Optical conductivity 19
4. Spin structure factor 20
D. Dynamical correlations at finite temperature 20
1. General considerations 20
2. Optical conductivity of the Anderson model 21
3. Optical conductivity of the Holstein model 22


IV. KPM as a component of other methods 23
A. Monte Carlo simulations 23
B. Cluster Perturbation Theory (CPT) 24
1. General features of CPT 24
2. CPT for the Hubbard model 25
3. CPT for the Holstein model 26


V. KPM versus other numerical approaches 26
A. KPM and dedicated many-particle techniques 27
B. Close relatives of KPM 27
1. Chebyshev expansion and Maximum Entropy
Methods 27
2. Lanczos recursion 28
3. Projection methods 28


VI. Conclusions & Outlook 30


Acknowledgements 30


References 30


I. INTRODUCTION


In most areas of physics the fundamental interactions
and the equations of motion that govern the behavior of
real systems on a microscopic scale are very well known,
but when it comes to solving these equations they turn
out to be exceedingly complicated. This holds, in particular, if a large and realistic number of particles is in

volved. Inventing and developing suitable approximations and analytical tools has therefore always been a
cornerstone of theoretical physics. Recently, however,
research continued to focus on systems and materials,
whose properties depend on the interplay of many different degrees of freedom or on interactions that compete on similar energy scales. Analytical and approximate methods quite often fail to describe the properties
of such systems, so that the use of numerical methods remains the only way to proceed. On the other hand, the
available computer power increased tremendously over
the last decades, making direct simulations of the microscopic equations for reasonable system sizes or particle
numbers more and more feasible. The success of such
simulations, though, depends on the development and
improvement of efficient algorithms. Corresponding research therefore plays an increasingly important role.
On a microscopic level the behavior of most physical
systems, like their thermodynamics or response to external probes, depends on the distribution of the eigenvalues
and the properties of the eigenfunctions of a Hamilton operator or dynamical matrix. In numerical approaches the
latter correspond to Hermitian matrices of finite dimension D, which can become huge already for a moderate
number of particles, lattice sites or grid points. The calculation of all eigenvalues and eigenvectors then easily
turns into an intractable task, since for a D-dimensional
matrix in general it requires memory of the order of D [2],
and the number of operations and the computation time
scale as D [3] . Of course, this large resource consumption
severely restricts the size of the systems that can be studied by such a “naive” approach. For dense matrices the
limit is currently of the order of D ≈ 10 [5], and for sparse
matrices the situation is only slightly better.
Fortunately, alternatives are at hand: In the present
article we review basic properties and recent developments of numerical Chebyshev expansion and of the Kernel Polynomial Method (KPM). As the most time consuming step these iterative approaches require only multiplications of the considered matrix with a small set of
vectors, and therefore allow for the calculation of spectral properties and dynamical correlation functions with
a resource consumption that scales linearly with D for
sparse matrices, or like D [2] otherwise. If the matrix is
not stored but constructed on-the-fly dimensions of the
order of D ≈ 10 [9] or more are accessible.
The first step to achieve this favorable behavior is
setting aside the requirement for a complete and exact
knowledge of the spectrum. A natural approach, which
has been considered from the early days of quantum mechanics, is the characterization of the spectral density�
ρ(E) in terms of its moments µl = ρ(E)E [l] dE. By
iteration these moments can usually be calculated very
efficiently, but practical implementations in the context
of Gaussian quadrature showed that the reconstruction
of ρ(E) from ordinary power moments is plagued by substantial numerical instabilities (Gautschi, 1968). These
occur mainly because the powers E [l] put too much weight



2


to the boundaries of the spectrum at the expense of poor
precision for intermediate energies. The observation of
this deficiency advanced the development of modified
moment approaches (Gautschi, 1970; Sack and Donovan,
1972), where E [l] is replaced by (preferably orthogonal)
polynomials of E. With studies of the spectral density of harmonic solids (Blumstein and Wheeler, 1973;
Wheeler and Blumstein, 1972; Wheeler et al., 1974) and
of autocorrelation functions (Wheeler, 1974), which made
use of Chebyshev polynomials of second kind, these ideas
soon found their way into physics application. Later,
similar Chebyshev expansion methods became popular
also in quantum chemistry, where the focus was on
the time evolution of quantum states (Chen and Guo,
1999; Kosloff, 1988; Mandelshtam and Taylor, 1997;
Tal-Ezer and Kosloff, 1984) and on Filter Diagonalization (Neuhauser, 1990). The modified moment approach noticeably improved when kernel polynomials
were introduced to damp the Gibbs oscillations, which
for truncated polynomial series occur near discontinuities of the expanded function (Silver and R¨oder,
1994; Silver et al., 1996; Wang, 1994; Wang and Zunger,
1994). At this time also the name Kernel Polynomial Method was coined, and applications then included high-resolution spectral densities, static thermodynamic quantities as well as zero-temperature dynamical correlations (Silver and R¨oder, 1994; Wang, 1994;
Wang and Zunger, 1994). Only recently this range was
extended to cover also dynamical correlation functions at
finite-temperature (Weiße, 2004), and below we present
some new applications to complex-valued quantities, e.g.
Green functions. Being such a general tool for studying
large matrix problems, KPM can also be used as a core
component of more involved numerical techniques. As recent examples we discuss Monte Carlo (MC) simulations
and Cluster Perturbation Theory (CPT).


In parallel to Chebyshev expansion techniques and
to KPM also the Lanczos Recursion Method was
developed (Aichhorn et al., 2003; Benoit et al., 1992;
Haydock et al., 1972, 1975; Jakliˇc and Prelovˇsek, 1994;
Lambin and Gaspard, 1982), which is based on a recursive Lanczos tridiagonalization (Lanczos, 1950) of the
considered matrix and the expression of the spectral density or of correlation functions in terms of continued fractions. The approach, in general, is applicable to the same
problems as KPM and found wide application in solid
state physics (Dagotto, 1994; Jakliˇc and Prelovˇsek, 2000;
Ordej´on, 1998; Pantelides, 1978). It suffers, however,
from the shortcomings of the Lanczos algorithm, namely
loss of orthogonality and spurious degeneracies if extremal eigenstates start to converge. We will compare the
two methods in Sec. V and explain, why we prefer to use
Lanczos for the calculation of extremal eigenstates and
KPM for the calculation of spectral properties and correlation functions. In addition, we will comment on more
specialized iterative schemes, such as projection methods (Goedecker, 1999; Goedecker and Colombo, 1994;
Iitaka and Ebisuzaki, 2003) and Maximum Entropy ap

3



proaches (Bandyopadhyay et al., 2005; Silver and R¨oder,
1997; Skilling, 1988). Drawing more attention to KPM
as a potent alternative to all these techniques is one of
the purposes of the present work.
The outline of the article is as follows: In Sec. II we
give a detailed introduction to Chebyshev expansion and
the Kernel Polynomial Method, its mathematical background, convergence properties and practical aspects of
its implementation. In Sec. III we apply KPM to a variety of problems from solid state physics. Thereby, we
focus mainly on illustrating the types of quantities that
can be calculated with KPM, rather than on the physics
of the considered models. In Sec. IV we show how KPM
can be embedded into other numerical approaches that
require knowledge of spectral properties or correlation
functions, namely Monte Carlo simulation and Cluster
Perturbation Theory. In Sec. V we shortly discuss alternatives to KPM and compare their performance and
precision, before summarizing in Sec. VI.


II. CHEBYSHEV EXPANSION AND THE KERNEL
POLYNOMIAL METHOD (KPM)


A. Basic features of Chebyshev expansion


1. Chebyshev polynomials


Let us first recall the basic properties of expansions in
orthogonal polynomials and of Chebyshev expansion in
particular. Given a positive weight function w(x) defined
on the interval [a, b] we can introduce a scalar product


�b



and second kind turn out to be the best choice for most
applications, mainly due to the good convergence properties of the corresponding series and to the close relation
to Fourier transform (Cheney, 1966; Lorentz, 1966). The
latter is also an important prerequisite for the derivation
of optimal kernels (see Sec. II.C), which are required for
the regularization of finite-order expansions, and which
so far have not been derived for other sets of orthogonal
polynomials.
Both sets of Chebyshev polynomials are defined on the
interval [a, b] = [−1, 1], where the weight function w(x) =
(π√1 x [2] ) [−][1] yields the polynomials of first kind, Tn,



(π 1 x [2] ) [−][1] yields the polynomials of first kind, Tn,

   and the weight function w(x) = π√1 x [2] those of second



and the weight function w(x) = π 1 − x [2] those of second

kind, Un. Based on the scalar products



⟨f |g⟩1 =


⟨f |g⟩2 =



�1


−1

�1




 π

−1



f (x) g(x)
π√1 x [2][ dx,] (4)

  


1 − x [2] f (x) g(x) dx, (5)



the orthogonality relations thus read



Tn Tm 1 = [1+] 2 [δ][n,][0]
⟨ | ⟩



2 [n,][0] δn,m, (6)



Un Um 2 = [π] 2 [2]
⟨ | ⟩



2 [δ][n,m][ .] (7)



⟨f |g⟩ =



w(x)f (x)g(x) dx (1)

a



By substituting x = cos(ϕ) one can easily verify that they
correspond to the orthogonality relations of trigonometric functions, and that in terms of those the Chebyshev
polynomials can be expressed in explicit form,


Tn(x) = cos(n arccos(x)), (8)

Un(x) = [sin((][n][ + 1) arccos(][x][))] . (9)

sin(arccos(x))


These expressions can then be used to prove the recursion
relations,


T0(x) = 1, T−1(x) = T1(x) = x,
(10)
Tm+1(x) = 2 x Tm(x) Tm−1(x),
              
and


U0(x) = 1, U−1(x) = 0,
(11)
Um+1(x) = 2 x Um(x) Um−1(x),
               
which illustrate that Eqs. (8) and (9) indeed describe
polynomials, and which, moreover, are an integral part
of the iterative numerical scheme we develop later on.
Two other useful relations are


2 Tm(x)Tn(x) = Tm+n(x) + Tm−n(x), (12)

2 (x [2] 1) Um−1(x)Un−1(x) = Tm+n(x) Tm−n(x) .

  -   (13)


When calculating Green functions we also need Hilbert
transforms of the polynomials (Abramowitz and Stegun,



between two integrable functions f, g : [a, b] → R. With
respect to each such scalar product there exists a complete set of polynomials pn(x), which fulfil the orthogonality relations


⟨pn|pm⟩ = δn,m/hn, (2)

where hn = 1/⟨pn|pn⟩ denotes the inverse of the squared
norm of pn(x). These orthogonality relations allow for an
easy expansion of a given function f (x) in terms of the
pn(x), since the expansion coefficients are proportional
to the scalar products of f and pn,


�∞



f (x) =



αn pn(x) with αn = ⟨pn|f ⟩ hn . (3)
n=0



In general, all types of orthogonal polynomials can
be used for such an expansion and for the Kernel Polynomial approach we discuss in this article
(see e.g. Silver and R¨oder (1994)). However, as we
frequently observe whenever we work with polynomial expansions (Boyd, 1989), Chebyshev polynomials (Abramowitz and Stegun, 1970; Rivlin, 1990) of first


4


�1

f (x)Tn(x) dx . (23)

−1



1970),




  (y − x)



(14)
1 y [2][ =][ π U][n][−][1][(][x][)][,]
 


P



�1


−1



Tn(y) dy



with moments


µn = ⟨f |φn⟩2 =







P



�1


−1



1 y [2] Un−1(y) dy
 


= π Tn(x), (15)
(y x)  


where P denotes the principal value. Chebyshev polynomials have many more interesting properties, for a detailed discussion we refer the reader to text books such
as (Rivlin, 1990).


2. Modified moments


As sketched above, the standard way of expanding a
function f : [−1, 1] → R in terms of Chebyshev polynomials of first kind is given by



f (x) =



�∞

f Tn 1
⟨ | ⟩ Tn(x) = α0 + 2
Tn Tn 1

n=0

⟨ | ⟩



�∞

αn Tn(x) (16)
n=1



with coefficients

�1

αn = ⟨f |Tn⟩1 =

−1



(17)
1 x [2][ dx .]
 


f (x)Tn(x)



π√



However, the calculation of these coefficients requires integrations over the weight function w(x), which in practical applications to matrix problems prohibits a simple
iterative scheme. The solution to this problem follows
from a slight rearrangement of the expansion, namely







�∞







1
f (x) = π√1 − x [2]



µ0 + 2



µn Tn(x)
n=1



(18)



with coefficients



�1

µn = f (x)Tn(x) dx . (19)


−1



More formally this rearrangement of the Chebyshev series
corresponds to using the second scalar product ⟨.|.⟩2 and
expanding in terms of the orthogonal functions



Tn(x)
φn(x) =
π√1



(20)
1 x [2][,]
 


which fulfil the orthogonality relations



φn φm 2 = [1+][δ] 2 [n,][0] δn,m . (21)
⟨ | ⟩



The expansion in Eq. (18) is thus equivalent to



�∞


n=0







f (x) =



f φn 2
⟨ | ⟩ φn(x)
φn φn 2
⟨ | ⟩



�∞







1
= π√1 − x [2]



µ0 + 2



µn Tn(x)
n=1



(22)



The µn now have the form of modified moments that
we announced in the introduction, and Eqs. (18) and (19)
represent the elementary basis for the numerical method
which we review in this article. In the remaining sections
we will explain how to translate physical quantities into
polynomial expansions of the form of Eq. (18), how to
calculate the moments µn in practice, and, most importantly, how to regularize expansions of finite order.
Naturally, the moments µn depend on the considered
quantity f (x) and on the underlying model. We will
specify these details when discussing particular applications in Sec. III. Nevertheless, there are features which
are similar to all types of applications, and we start with
presenting these general aspects in what follows.


B. Calculation of moments


1. General considerations


A common feature of basically all Chebyshev expansions is the requirement for a rescaling of the underlying
matrix or Hamiltonian H. As we described above, the
Chebyshev polynomials of both first and second kind are
defined on the real interval [−1, 1], whereas the quantities we are interested in usually depend on the eigenvalues Ek of the considered (finite-dimensional) matrix.
{ }
To fit this spectrum into the interval [−1, 1] we apply a
simple linear transformation to the Hamiltonian and all
energy scales,

H˜ = (H − b)/a, (24)
E˜ = (E − b)/a, (25)


and denote all rescaled quantities with a tilde hereafter.
Given the extremal eigenvalues of the Hamiltonian, Emin
and Emax, which can be calculated, e.g. with the Lanczos
algorithm (Lanczos, 1950), or for which bounds may be
known analytically, the scaling factors a and b read


a = (Emax Emin)/(2 ǫ), (26)
           -           b = (Emax + Emin)/2 . (27)


The parameter ǫ is a small cut-off introduced to avoid
stability problems that arise if the spectrum includes or
exceeds the boundaries of the interval [−1, 1]. It can be
fixed, e.g. to ǫ = 0.01, or adapted to the resolution of
the calculation, which for an expansion of finite order N
is proportional 1/N (see below).
The next similarity of most Chebyshev expansions is
the form of the moments, namely their dependence on
the matrix or Hamiltonian H [˜] . In general, we find two


types of moments: Simple expectation values of Chebyshev polynomials in H [˜],


µn = ⟨β|Tn( H [˜] )|α⟩, (28)

where |α⟩ and |β⟩ are certain states of the system, or
traces over such polynomials and a given operator A,


µn = Tr[A Tn( H [˜] )] . (29)


Handling the first case is rather straightforward. Starting from the state |α⟩ we can iteratively construct the
states αn = Tn( H [˜] ) α by using the recursion relations
| ⟩ | ⟩
for the Tn, Eq. (10),



5


2. Stochastic evaluation of traces


The second case where the moments depend on a trace
over the whole Hilbert space, at first glance, looks far
more complicated. Based on the previous considerations
we would estimate the numerical effort to be proportional
to D [2], because the iteration needs to be repeated for all
D states of a given basis. It turns out, however, that
extremely good approximations of the moments can be
obtained with a much simpler approach: the stochastic evaluation of the trace (Drabold and Sankey, 1993;
Silver and R¨oder, 1994; Skilling, 1988), i.e., an estimate
of µn based on the average over only a small number
R ≪ D of randomly chosen states |r⟩,



α0 = α, (30)
| ⟩ | ⟩

α1 = H [˜] α0, (31)
| ⟩ | ⟩

αn+1 = 2 H [˜] αn αn−1 . (32)
| ⟩ | ⟩−| ⟩



µn = Tr[A Tn( H [˜] )]
≈ R [1]



R�−1

r A Tn( H [˜] ) r . (36)
⟨ | | ⟩
r=0



Scalar products with |β⟩ then directly yield

µn = ⟨β|αn⟩ . (33)


This iterative calculation of the moments, in particular
the application of H [˜] to the state αn, represents the
| ⟩
most time consuming part of the whole expansion approach and determines its performance. If H [˜] is a sparse
matrix of dimension D the matrix vector multiplication
is an order O(D) process and the calculation of N moments therefore requires O(ND) operations and time.
The memory consumption depends on the implementation. For moderate problem dimension we can store the
matrix and, in addition, need memory for two vectors
of dimension D. For very large D the matrix certainly
does not fit into the memory and has to be reconstructed
on-the-fly in each iteration or retrieved from disc. The
two vectors then determine the memory consumption of
the calculation. Overall, the resource consumption of
the moment iteration is similar or even slightly better
than that of the Lanczos algorithm, which requires a few
more vector operations (see our comparison in Sec. V).
In contrast to Lanczos, Chebyshev iteration is completely
stable and can be carried out to arbitrary high order.
The moment iteration can be simplified even further,
if |β⟩ = |α⟩. In this case the product relation (12) allows
for the calculation of two moments from each new αn,
| ⟩

µ2n = 2⟨αn|αn⟩− µ0, (34)
µ2n+1 = 2⟨αn+1|αn⟩− µ1, (35)


which is equivalent to two moments per matrix vector
multiplication. The numerical effort for N moments is
thus reduced by a factor of two. In addition, like many
other numerical approaches KPM benefits considerably
from the use of symmetries that reduce the Hilbert space
dimension.



The number of random states, R, does not scale with D.
It can be kept constant or even reduced with increasing
D. To understand this, let us consider the convergence
properties of the above estimate. Given an arbitrary barandom variablescal averagesis {|i⟩} and a set of independent identically distributed�� . . . �� ξfulfilri ∈ C, which in terms of the statisti

�� ��
�� ξri�� = 0, (37)
ξriξr′j = 0, (38)
�� ��
ξri [∗] [ξ] r [′] j = δrr′δij, (39)


a random vector is defined through


D�−1



Of course, this only shows that we obtain the correct
result on average. To assess the associated error we also
need to study the fluctuation of Θ, which is characterized



|r⟩ =



ξri i . (40)
| ⟩
i=0



We can now calculate the statistical expectation value of
the trace estimate Θ = R [1] �Rr=0−1

tian operator B with matrix elements [⟨][r][|][B][|][r] B [⟩] ij [for some Hermi-] = ⟨i|B|j⟩, and
indeed find,



D�−1


i,j=0



�� �� �� 1
Θ =

R



R�−1




- ��

r B r = [1]
⟨ | | ⟩ R
r=0



R



R�−1


r=0



�� ��
ξri [∗] [ξ] rj Bij



=



D�−1

Bii = Tr(B) . (41)
i=0


�� �� ��2
by (δΘ) [2] = Θ [2][��] - Θ . Evaluating



�� �� 1
Θ [2][��] =

R [2]



R�−1 ��

⟨r|B|r⟩⟨r [′] |B|r [′] ⟩
r,r [′] =0



D�−1


i,j,i [′],j [′] =0



= [1]

R [2]



R�−1


r,r [′] =0



�� ��
ξri [∗] [ξ] rj [ξ] r [∗][′] i [′] [ξ] r [′] j [′] Bij Bi′j′



= [1]

R [2]




- [R] - [−][1]


r,r [′] =0
r=r [′]



D�−1

δijδi′j′ Bij Bi′j′
i,j,i [′],j [′] =0



�� �� ξri [∗] [ξ] rj [ξ] ri [∗] [′] [ξ] rj [′] BijBi′j′



+



R�−1 D�−1


r i,j,i [′],j [′] =0



= [R][ −] [1]




[ −] [1]

(Tr B) [2] + [1]
R R



R




- [D] - [−][1]


j=0



��
ξrj Bjj [2]
| | [4][��]




   BijBji



D�−1


i,j=0
i=j



+



D�−1

BiiBjj +

i,j=0
i=j



6


��
|ξri| [4][��] . Presumably, the most natural choice are Gaus-��
sian distributed ξri, which lead to ξri = 2 and thus a
| | [4][��]
basis-independent fluctuation (δΘ) [2] . To summarize this
section, we think that the actual choice of the distribution of ξri is not of high practical significance, as long as
Eqs. (37)–(39) are fulfilled for ξri C, or
�� �� ∈
ξri = 0, (44)
�� ��
ξriξr′j = δrr′δij, (45)


hold for ξri R. Typically, within this article we
will consider Gaussian (Silver and R¨oder, 1994; Skilling, ∈
1988) or uniformly distributed variables ξri R.
∈


C. Kernel polynomials and Gibbs oscillations


1. Expansions of finite order & simple kernels


In the preceding sections we introduced the basic ideas
underlying the expansion of a function f (x) in an infinite
series of Chebyshev polynomials, and gave a few hints for
the numerical calculation of the expansion coefficients µn.
As expected for a numerical approach, however, the total
number of these moments will remain finite, and we thus
arrive at a classical problem of approximation theory.
Namely, we are looking for the best (uniform) approximation to f (x) by a polynomial of given maximal degree,
which in our case is equivalent to finding the best approximation to f (x) given a finite number N of moments
µn. To our advantage, such problems have been studied for at least 150 years and we can make use of results
by many renowned mathematicians, such as Chebyshev,
Weierstrass, Dirichlet, Fej´er, Jackson, to name only a
few. We will also introduce the concept of kernels, which
facilitates the study of the convergence properties of the
mapping f (x) fKPM(x) from the considered function
→
f (x) to our approximation fKPM(x).
Experience shows that a simple truncation of an infinite series,



D�−1 
Bjj [2]
j=0



= (Tr B) [2] + [1]

R




- ��
Tr(B [2] ) + ( ξri 2)
| | [4][��]            


(42)
we get for the fluctuation



D�−1 
Bjj [2] . (43)
j=0



(δΘ) [2] = [1]

R




- ��
Tr(B [2] ) + ( ξri 2)
| | [4][��]            


The trace of B [2] will usually be of order O(D), and the
relative error of the trace estimate, δΘ/Θ, is thus of order
O(1/√RD). It is this favorable behavior, which ensures

the convergence of the stochastic approach, and which
was the basis for our initial statement that the number
of random states R ≪ D can be kept small or even be
reduced with the problem dimension D.
Note also that the distribution of the elements of
r, p(ξri), has a slight influence on the precision of
| ⟩
the estimate, since it determines the expectation value��
��|ξri| [4][��] that enters Eq. (43). For an optimal distribution
��|ξri| [4][��] should be as close as possible to its lower bound
ξri = 1, and indeed, we find this result if we fix the
| | [2][��][2]
amplitude of the ξri and allow only for a random phase
φ ∈ [0, 2π], ξri = e [iφ] . Moreover, if we were working in the
eigenbasis of B this would cause δΘ to vanish entirely,
which led Iitaka and Ebisuzaki (2004) to conclude that
random phase vectors are the optimal choice for stochastic trace estimates. However, all these considerations depend on the basis that we are working in, which in practice will never be the eigenbasis of B (in particular, if B
corresponds to something like A Tn( H [˜] ), as in Eq. (36)).
A random phase vector in one basis does not necessarily correspond to a random phase vector in another basis, but the other basis may well lead to smaller value
of [�] j [D] =0 [−][1] [B] jj [2] [, thus compensating for the larger value of]



1
= π√1 − x [2]



N�−1 
µn Tn(x), (46)
n=1



1
f (x) ≈ π√1 − x [2]




µ0 + 2



leads to poor precision and fluctuations — also known
as Gibbs oscillations — near points where the function
f (x) is not continuously differentiable. The situation is
even worse for discontinuities or singularities of f (x), as
we illustrate below in Figure 1. A common procedure to
damp these oscillations relies on an appropriate modification of the expansion coefficients, µn gnµn, which
depends on the order of the approximation → N,



N�−1



fKPM(x) =



f φn 2
gn ⟨ | ⟩ φn(x)
φn φn 2
n=0
⟨ | ⟩



N�−1 
gnµn Tn(x) .
n=1



(47)




g0µ0 + 2



N�−1


In more abstract terms this truncation of the infinite series to order N together with the corresponding modification of the coefficients is equivalent to the convolution
of f (x) with a kernel of the form


N�−1



KN (x, y) = g0φ0(x)φ0(y) + 2


namely



gnφn(x)φn(y), (48)
n=1



(49)



fKPM(x) =



�1

 π

−1



1 y [2] KN (x, y) f (y) dy
 


7


Owing to the denominator in the expansion (46) convergence is not uniform in the vicinity of the endpoints
x = ±1, which we accounted for by the choice of a small
ǫ in the rescaling of the Hamiltonian H → H [˜] .
The more favorable uniform convergence is obtained
under very general conditions. Specifically, it suffices to
demand that:


1. The kernel is positive: KN (x, y) > 0 x, y [ 1, 1].
∀ ∈                        
               - 1
2. The kernel is normalized, −1 [K][(][x, y][)][ dx][ =][ φ][0][(][y][),]
which is equivalent to g0 = 1.

3. The second coefficient g1 approaches 1 as N →∞.

Then, as a corollary to Korovkin’s theorem (Korovkin,
1959), an approximation based on KN (x, y) converges
uniformly in the sense explicated for the Fej´er kernel.
The coefficients gn, n 2 are restricted only through
≥
the positivity of the kernel, the latter one being equivalent to monotonicity of the mapping f fKPM, i.e.
→
f ≥ f [′] ⇒ fKPM ≥ fKPM [′] [. Note also that the condi-]
tions 1 and 2 are very useful for practical applications:
The first ensures that approximations of positive quantities become positive, the second conserves the integral
of the expanded function,



= ⟨KN (x, y)|f (y)⟩2 .

The problem now translates into finding an optimal kernel KN (x, y), i.e., coefficients gn, where the notion of
“optimal” partially depends on the considered application.
The simplest kernel, which is usually attributed to
Dirichlet, is obtained by setting gn [D] [= 1 and evaluating]
the sum with the help of the Christoffel-Darboux identity (Abramowitz and Stegun, 1970),



N�−1

KN [D][(][x, y][) =][ φ][0][(][x][)][φ][0][(][y][) + 2] φn(x)φn(y)

n=1



(50)



�1 �1

fKPM(x) dx = f (x) dx . (54)

−1 −1



= [φ][N] [(][x][)][φ][N] [−][1][(][y][)][ −] [φ][N] [−][1][(][x][)][φ][N] [(][y][)] .

x − y



Obviously, convolution of KN [D] [with an integrable function]
f yields the above truncated series, Eq. (46), which for
N →∞ converges to f within the integral norm defined�
by the scalar product Eq. (5), ||f ||2 = ⟨f |f ⟩2, i.e. we

have


N →∞
f fKPM 2 0 . (51)
||              - || −−−−→

This is, of course, not particularly restrictive and leads
to the disadvantages we mentioned earlier.


2. Fej´er kernel


A first improvement is due to Fej´er (1904) who showed
that for continuous functions an approximation based on
the kernel



Applying the kernel, for example, to a density of states
thus yields an approximation which is strictly positive
and normalized.
For a proof of the above theorem we refer the reader
to the literature (Cheney, 1966; Lorentz, 1966). Let us
here only check that the Fej´er kernel indeed fulfils the
conditions 1 to 3: The last two are obvious by inspection
of Eq. (52). To prove the positivity we start from the
positive 2π-periodic function



2



p(ϕ) =



N�−1

aν e [i][ νϕ]

����� �����

ν=0



(55)



with arbitrary aν R. Straight-forward calculation then
shows ∈



N�−1 N�−1

aνaµ e [i(][ν][−][µ][)][ϕ] = aνaµ cos(ν − µ)ϕ
ν,µ=0 ν,µ=0



N�−1

a [2] ν [+ 2]
ν=0



KN [F] [(][x, y][) = 1]

N



�N



Kν [D][(][x, y][)][,] i.e., gn [F] [= 1][−] [n]
ν=1



N [,][ (52)]



p(ϕ) =


=



N�−1 N −�1−n

aνaν+n cos nϕ .

n=1 ν=0



converges uniformly in any restricted interval [−1+ ǫ, 1 ǫ]. This means that now the absolute difference between
the function f and the approximation fKPM goes to zero,


N →∞
f fKPM ∞ [=] max 0 .
|| - || [ǫ] −1+ǫ<x<1−ǫ [|][f] [(][x][)][ −] [f][KPM][(][x][)][|] −−−−→

(53)



Hence, with



gn =



(56)


N −�1−n

aνaν+n (57)
ν=0


8



the function



and aν, respectively, note that



2 [(][T][2][(][x][) +][ T][0][(][x][))][T][0][(][y][)][ −] [2][T][1][(][x][)][T][1][(][y][)]



p(ϕ) = g0 + 2



N�−1

gn cos nϕ (58)
n=1



(x y) [2] = (T1(x) T1(y)) [2]
 -  


= [1]



is positive and periodic in ϕ. However, if p(ϕ) is positive,
then the expression [1] 2 [[][p][(arccos] [x][+arccos][ y][)+][p][(arccos] [x][−]

arccos y)] is positive ∀ x, y ∈ [−1, 1]. Using Eq. (8) and
cos α cos β = 2 [1] [[cos(][α][ +][ β][) + cos(][α][ −] [β][)], we immediately]

observe that the general kernel KN (x, y) from Eq. (48) is
positivearbitrary coefficients1/√N yields the Fej´er kernel ∀ x, y ∈ [−1, a 1], if the coefficientsν ∈ R K via Eq. (57). SettingN [F] [(][x, y][), thus immediately] gn depend on aν =

proving its positivity.
In terms of its analytical properties and of the convergence in the limit N →∞ the Fej´er kernel is a major improvement over the Dirichlet kernel. However, as yet we
did not quantify the actual error of an order-N approximation: For continuous functions an appropriate scale is
given by the modulus of continuity,


wf (∆) = max (59)
|x−y|≤∆ [|][f] [(][x][)][ −] [f] [(][y][)][|][,]


in terms of which the Fej´er approximation fulfils

f fKPM ∞ wf (1/√N ) . (60)
||           - || ∼

For sufficiently smooth functions this is equivalent to anerror of order O(1/√N ). The latter is also an estimate for

the resolution or broadening that we will observe when
expanding less regular functions containing discontinuities or singularities, like the examples in Figure 1.


3. Jackson kernel


With the coefficients gn [F] [of the Fej´er kernel we have not]
fully exhausted the freedom offered by the coefficients aν
and Eq. (57). We can hope to further improve the kernel
by optimizing the aν in some sense, which will lead us to
recover old results by Jackson (1911, 1912).
In particular, let us tighten the third of the previously
defined conditions for uniform convergence by demanding
that the kernel has optimal resolution in the sense that



= [a][¯][2]

2



+ [1]



2 [T][0][(][x][)(][T][2][(][y][) +][ T][0][(][y][))][ .] (62)



Using the orthogonality of the Chebyshev polynomials
and inserting Eqs. (48) and (62) into (61), we can thus
rephrase the condition of optimal resolution as


!
Q = g0 − g1 = minimal w.r.t. aν . (63)

Hence, compared to the previous section, where we
merely required g0 = 1 and g1 → 1 for N →∞, our
new condition tries to optimize the rate at which g1 approaches unity.
g0 Minimizing1 = 0 yields the condition Q = g0 − g1 under the constraint C =
 
∂Q
= λ [∂C], (64)
∂aν ∂aν


where λ is a Lagrange multiplier. Using Eq. (57) and
setting a−1 = aN = 0 we arrive at


2aν − aν−1 − aν+1 = λaν (65)

which the alert reader recognizes as the eigenvalue problem of a harmonic chain with fixed boundary conditions.
Its solution is given by



aν = ¯a sin [πk][(][ν][ + 1)]



,
N + 1



(66)
πk
λ = 1 cos
   - N + 1 [,]



where ν = 0, . . ., (N − 1) and k = 1, 2, . . ., N . Given
aν and the abbreviation q = πk/(N + 1) we can easily
calculate the gn:



N�−1−n



gn =



�−1−n N�−n

aν aν+n = ¯a [2]
ν=0 ν=1



sin qν sin q(ν + n)

ν=1



N�−n




[cos qn − cos q(2ν + n)]
ν=1



(67)



N�−n







(N − n) cos qn − Re



= [a][¯][2]

2



= [a][¯][2]

2 [[(][N][ −] [n][ + 1) cos] [qn][ + sin][ qn][ cot][ q][]][ .]



�1

(x y) [2] KN (x, y) dx dy (61)
  −1




     
N�−n

e [i][ q][(2][ν][+][n][)]

ν=1



Q :=



�1


−1



is minimal. Since KN (x, y) will be peaked at x = y, Q is
basically the squared width of this peak. For sufficiently
smooth functions this more stringent condition will minimize the error f fKPM ∞, and in all other cases lead
||            - ||
to optimal resolution and smallest broadening of “sharp”
features.
To express the variance Q of the kernel in terms of gn



The normalization g0 = 1 is ensured through ¯a [2] =
2/(N + 1), and with g1 = cos q we can directly read off
the optimal value for


πk
Q = g0 g1 = 1 cos (68)
         -         - N + 1 [,]


9



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-8-0.png)

x



which is obtained for k = 1,


π
Qmin = 1 cos
         - N + 1 [≃] 2 [1]




π

N



�2
. (69)



20


15


10


5


0


-5





The latter result shows that for large N the resolution
√Q of the new kernel is proportional to 1/N . Clearly,
this is an improvement over the Fej´er kernel KN [F] [(][x, y][)]
which gives only Q = 1/√N .

[√]

With the above calculation we reproduced results
by Jackson (1911, 1912), who showed that with a similar kernel a continuous function f can be approximated
by a polynomial of degree N − 1 such that

f fKPM ∞ wf (1/N ), (70)
||            - || ∼

which we may interpret as an error of the order of
O(1/N ). Hereafter we are thus referring to the new optimal kernel as the Jackson kernel KN [J] [(][x, y][), with]

gn [J] [=] (N − n + 1) cos Nπn+1 [+ sin] Nπn+1 [cot] Nπ+1 . (71)
N + 1


Before proceeding with other kernels let us add a few
more details on the resolution of the Jackson kernel: The
quantity Qmin obtained in Eq. (69) is mainly a measure

[√]
for the spread of the kernel KN [J] [(][x, y][) in the][ x][-][y][-plane.]
However, for practical calculations, which may also involve singular functions, it is often reasonable to ask for
the broadening of a δ-function under convolution with
the kernel,


δKPM(x a) = KN (x, y) δ(y a) 2
     - ⟨ |     - ⟩

N�−1



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-8-1.png)

x



1


0.8


0.6


0.4


0.2


0


-0.2



FIG. 1 (Color in online edition) Order N = 64 expansions of
δ(x) (left) and a step function (right) based on different kernels. Whereas the truncated series (Dirichlet kernel) strongly
oscillate, the Jackson results smoothly converge to the expanded functions. The Lorentz kernel leads to relatively poor
convergence at the boundaries x = ±1, but otherwise yields
perfect Lorentz-broadened approximations.


Using the Jackson kernel, an order N expansion of a δfunction at x = 0 thus results in a broadened peak of
width σ = N [π] [, whereas close to the boundaries,][ a][ =][ ±][1,]

we find σ = Nπ [3][/][2][ . It turns out that this peak is a good]
approximation to a Gaussian,



1 
2πσ [2][ exp] - 2 [x] σ [2]



1
δKPM [J] [(][x][)][ ≈] √2




  , (76)
2 [x] σ [2][2]



= g0φ0(x)T0(a) + 2



gnφn(x)Tn(a) . (72)
n=1



which we illustrate in Figure 1.


4. Lorentz kernel


The Jackson kernel derived in the preceding sections
is the best choice for most of the applications we discuss
below. In some situations, however, special analytical
properties of the expanded functions become important,
which only other kernels can account for. The Green
functions that appear in the Cluster Perturbation Theory, Sec. IV.B, are an example. Considering the imaginary part of the Plemelj-Dirac formula which frequently
occurs in connexion with Green functions,



�� �� ��2
It can be characterized by the variance σ [2] = x [2][��] - x,
where we use x = T1(x) and x [2] = [T2(x) + T0(x)]/2 to
find



�1

x δKPM(x a) dx = g1T1(a), (73)
      −1



�� ��
x =


��
x [2][��] =



.
2



�1



x [2] δKPM(x a) dx = [g][0][T][0][(][a][) +][ g][2][T][2][(][a][)]
      - 2
−1





 - i πδ(x), (77)



(74)


Hence, for KN [J] [(][x, y][) the squared width of][ δ][KPM][(][x][ −] [a][) is]
given by




      1 1
lim
ǫ→0 x + i ǫ [=][ P] x



σ [2] = ��x [2][��] - ��x��2 = a�2(g2J [−] [(][g] 1 [J] [)][2][) + (] - [g] 0 [J] [−] [g] 2 [J] [)][/][2]







= [N][ −] [a][2][(][N][ −] [1)]




2π
1 cos
 - N + 1



2(N + 1)




.




 π
≃ N



N



�2 [�]
1 a [2] + [3][a][2][ −] [2]
  - N



N



(75)



the δ-function on the right hand side is approached in
terms of a Lorentz curve,


1 ǫ

δ(x) = (78)
     - π [1] ǫ [lim] →0 [Im] x + i ǫ [= lim] ǫ→0 π(x [2] + ǫ [2] ) [,]


which has a different and broader shape compared to
the approximations of δ(x) we get with the Jackson
kernel. There are attempts to approximate Lorentzian
like behavior in the framework of filter diagonalization (Vijay et al., 2004), but these solutions do not lead


to a positive kernel. Note that positivity of the kernel
is essential to guarantee basic properties of Green functions, e.g. that poles are located in the lower (upper) half
complex plane for a retarded (advanced) Green function.
Since we know that the Fourier transform of a Lorentz
peak is given by exp(−ǫ|k|), we can try to construct an
appropriate positive kernel assuming aν = e [−][λν/N] in
Eq. (57), and indeed, after normalization, g0 = 1, this
yields what we call the Lorentz kernel KN [L] [(][x, y][) hereafter,]


gn [L] [= sinh[][λ][(1][ −] [n/N] [)]] . (79)

sinh(λ)


The variable λ is a free parameter of the kernel which
as a compromise between good resolution and sufficient
damping of the Gibbs oscillations we empirically choose
to be of the order of 3 . . . 5. It is related to the ǫparameter of the Lorentz curve, i.e. to its resolution, via
ǫ = λ/N . Note also, that in the limit λ → 0 we recover
the Fej´er kernel KN [F] [(][x, y][) with][ g] n [F] [= 1][ −] [n/N] [, suggesting]
that both kernels share many of their properties.
In Figure 1 we compare truncated Chebyshev expansions — equivalent to using the Dirichlet kernel —
to the approximations obtained with the Jackson and
Lorentz kernels, which we will later use almost exclusively. Clearly, both kernels yield much better approximations to the expanded functions and, in particular,
the oscillations have disappeared almost completely. The
comparison with a Gaussian or Lorentzian, respectively,
illustrates the nature of the broadening of a δ-function
under convolution with the kernels, which later on will facilitate the interpretation of our numerical results. With
Table I we conclude this section on kernels, and, for the
sake of completeness, also list two other kernels that are
occasionally used in the literature. Both have certain disadvantages, in particular, they are not strictly positive.


D. Implementational details and remarks


1. Discrete cosine & Fourier transforms


Having discussed the theory behind Chebyshev expansion, the calculation of moments, and the various kernel
approximations, let us now come to the practical issues of
the implementation of KPM, namely to the reconstruction of the expanded function f (x) from its moments µn.
Knowing a finite number N of coefficients µn (see Sec. III
for examples and details), we usually want to reconstruct
f (x) on a finite set of abscissas xk. Naively we could sum
up Eq. (47) separately for each point, thereby making use
of the recursion relations for Tn, i.e.,



10


do much better, however, remembering the definition of
the Chebyshev polynomials Tn, Eq. (8), and the close
relation between KPM and Fourier expansion: First, we
may introduce the short-hand notation


µ˜n = µngn (81)


for the kernel improved moments. Second and more important, we make a special choice for our data points,


xk = cos [π][(][k][ + 1][/][2)] with k = 0, . . ., ( N [˜] 1), (82)

N˜         

which coincides with the abscissas of Chebyshev numerical integration (Abramowitz and Stegun, 1970). The
number N [˜] of points in the set xk is not necessarily
{ }
the same as the number of moments N . Usually we will
consider N [˜] ≥ N and a reasonable choice is, e.g. N [˜] = 2N .
All values f (xk) can now be obtained through a discrete
cosine transform,




  γk = π



1 − x [2] k [f] [(][x][k][)]




- (83)



N�−1



= ˜µ0 + 2



N�−1 
πn(k + 1/2)
µ˜n cos
n=1 N˜



N˜



which allows for the use of divide-and-conquer type algorithms that require only N [˜] log N [˜] operations — a clear
advantage over the above estimate N N [˜] .
Routines for fast discrete cosine transform are implemented in many mathematical libraries or Fast
Fourier Transform (FFT) packages, for instance, in
FFTW (Frigo and Johnson, 2005a,b) that ships with
most Linux distributions. If no direct implementation is
at hand we may also use fast discrete Fourier transform.
With




0 < n < N



λn =




- (2 δn,0) ˜µn exp i2 πnN [˜]
  


N (84)

0 otherwise



2 N [˜]



and the standard definition of discrete Fourier transform,




, (85)



λ˜k =



N�˜ −1 
2π i nk
λn exp
n=0 N˜



N�˜ −1



N˜



gnµn Tn(xk)
n=1







1
f (xk) = 


N�−1




 π



1 x [2] k
 


. (80)



after some reordering we find for an even number of data
points


γ2j = Re(λ [˜] j), (86)

γ2j+1 = Re(λ [˜] N ˜ −1−j [)][,] (87)

with j = 0, . . ., N/ [˜] 2 - 1. If we need only a discrete cosine
transform this setup is not optimal, as it makes no use
of the imaginary part which the complex FFT calculates.
It turns out, however, that the “wasted” imaginary part
is exactly what we need when we later calculate Green






g0µ0 + 2



For a set xk containing N [˜] points these summations
{ }
would require of the order of N N [˜] operations. We can


11



Name gn Parameters positive? Remarks
Jackson N1+1 [[(][N][ −] [n][ + 1) cos] Nπn+1 [+ sin] Nπn+1 [cot] Nπ+1 []] none yes best for most applications



Lorentz sinh[λ(1 − n/N )]/ sinh(λ) λ ∈ R yes best for Green functions
Fej´er 1 − n/N none yes mainly of academic interest




             Lanczos sin(πn/N)




             - �M
Lanczos sin(πn/Nπn/N) M ∈ N no M = 3 closely matches the Jack
son kernel, but not strictly positive (Lanczos, 1966)
Wang and Zunger exp[−(α [n] [)][β][]] α, β ∈ R no found empirically, not optimal (Wang,



Wang and Zunger exp[−(α N [n] [)][β][]] α, β ∈ R no found empirically, not optimal (Wang,

1994; Wang and Zunger, 1994)
Dirichlet 1 none no least favorable choice



TABLE I Summary of different integral kernels that can be used to improve the quality of an order N Chebyshev series. The
coefficients gn refer to Eq. (47) or (48), respectively.



functions and other complex quantities, i.e., we can use
the setup


γ2j = λ [˜] j, (88)

γ2j+1 = λ [˜][∗] N˜ −1−j [,] (89)


to evaluate Eq. (140).


2. Integrals involving expanded functions


We have already mentioned that our particular choice
of xk corresponds to the abscissas of numerical Chebyshev integration. Hence, Gauss-type numerical approximations (Press et al., 1986) to integrals of the form

- 1
−1 [f] [(][x][)][g][(][x][)][dx][ become simple sums,]



the scalar product ⟨.|.⟩2 to functions f, g : [−1, 1] [d] → R,



where we introduced a vector notation for indices, ⃗n =
n1, . . ., nd, and the following functions and coefficients
{ }

�d



�1



�1




     - �d
f (⃗x)g(⃗x)
−1 j=1



�d 
π

j=1




   1 x [2] j dx1 . . . dxd .
 


⟨f |g⟩2 =




   - · ·
−1



(91)
Here xj denote the d components of the vector ⃗x. Naturally, this scalar product leads to the expansion



�∞



(92)



f (⃗x) =


=



�∞ �d
⃗n= [⃗] 0 [µ][⃗n][h][⃗n] j=1 [T][n][j] [(][x][j] [)]

   �dj=1 [π] 1 x [2] j



,
1 x [2] j
 


⃗n= [⃗] 0



⟨f |φ⃗n⟩2 φ⃗n(⃗x)
φ⃗n φ⃗n 2
⟨ | ⟩



dx
1 − x [2]



√



�1

f (x)g(x) dx =

−1



�1


−1



1 − x [2] f (x)g(x)
√1 x [2]



φ⃗n(⃗x) =



φnj (xj ), (93)
j=1







=



≃ N [π] ˜



N�˜ −1


k=0



N˜



1 − x [2] k [f] [(][x][k][)][g][(][x][k][) = 1] N˜



N�˜ −1

γkg(xk),

k=0

(90)



µ⃗n = ⟨f |φ⃗n⟩2



�1



�1




   - �d
f (⃗x)
−1 j=1



�d 
Tnj (xj) dx1 . . . dxd, (94)
j=1




   - · ·
−1



where γk denotes the raw output of the cosine or Fourier
transforms defined in Eq. (83). We can use this feature,
for instance, to calculate partition functions, where f (x)
corresponds to the expansion of the spectral density ρ(E)
and g(x) to the Boltzmann or Fermi weight.


E. Generalization to higher dimension


1. Expansion of multivariate functions


For the calculation of finite-temperature dynamical
correlation functions we will later need expansions of
functions of two variables. Let us therefore comment
on the generalization of the previous considerations to ddimensional space, which is easily obtained by extending



1
h⃗n = =
φ⃗n φ⃗n 2
⟨ | ⟩



�d


j=1



2
. (95)
1 + δnj,0



2. Kernels for multidimensional expansions


As in the one-dimensional case, a simple truncation of
the infinite series will lead to Gibbs oscillations and poor
convergence. Fortunately, we can easily generalize our
previous results for kernel approximations. In particular,
we find that the extended kernel


�d



KN (⃗x, ⃗y) =



KN (xj, yj) (96)
j=1


�d

π sin(ϕkj )
j=1



maps an infinite series onto an truncated series,



12


(104)



fKPM(⃗x) = KN (⃗x, ⃗y) f (⃗y) 2
⟨ | ⟩



κ⃗n = ˜µ⃗nh⃗n = µ⃗ng⃗nh⃗n we find


γ⃗k = f (cos(ϕk1 ), . . ., cos(ϕkd))



=


=



=



�N −1 �d
⃗n= [⃗] 0 [µ][⃗n][h][⃗n] j=1 [g][n][j] [T][n][j] [(][x][j] [)]

   �dj=1 [π] 1 x [2] j



=1 [n][j] [n][j] [j] (97)

,
1 x [2] j
 


�d

cos(njϕkj )
j=1



N�−1

κ⃗n
⃗n= [⃗] 0



N�−1

cos(n1ϕk1 ) . . .
n1=0



where we can take the gn of any of the previously discussed kernels. If we use the gn [J] [of the Jackson kernel,]
KN [J] [(][⃗x, ⃗y][) fulfils generalizations of our conditions for an]
optimal kernel, namely


1. KN [J] [(][⃗x, ⃗y][) is positive][ ∀] [⃗x, ⃗y][ ∈] [[][−][1][,][ 1]][d][.]


2. KN [J] [(][⃗x, ⃗y][) is normalized with]



N�−1

cos(ndϕkd)κ⃗n .
nd=0



�1



�1



�1



�1



The last line shows that the multidimensional discrete
cosine transform is equivalent to a nesting of onedimensional transforms in every coordinate. With fast
implementations the computational effort is thus proportional to dN [˜] [d][−][1][ ˜] N log N [˜], which equals the expected
value for N˜ [d] data points, N˜ [d] log ˜N [d] . If we are not
using libraries like FFTW, which provide ready-to-use
multidimensional routines, we may also resort to onedimensional cosine transform or the above translation
into FFT to obtain high-performance implementations
of general d-dimensional transforms.


III. APPLICATIONS OF KPM


Having described the mathematical background and
many details of the implementation of the Kernel Polynomial Method, we are now in the position to present
practical applications of the approach. Already in the
introduction we have mentioned that KPM can be used
whenever we are interested in the spectral properties of
large matrices or in correlation functions that can be expressed through the eigenstates of such matrices. Apparently, this leads to a vast range of applications. In what
follows, we try to cover all types of accessible quantities
and for each give at least one example. We thereby focus
on lattice models from solid state physics.


A. Densities of states


1. General considerations


The first and basic application of Chebyshev expansion and KPM is the calculation of the spectral density of
Hermitian matrices, which could correspond to the densities of states of both interacting or non-interacting quantum models (Silver and R¨oder, 1994; Silver et al., 1996;
Skilling, 1988; Wheeler, 1974). To be specific, let us consider a D-dimensional matrix M with eigenvalues Ek,
whose spectral density is defined as




   - · · fKPM(⃗x) dx1 . . . dxd =
−1 −1




   - · · f (⃗x) dx1 . . . dxd .
−1 −1

(98)



3. KN [J] [(][⃗x, ⃗y][) has optimal resolution in the sense that]



�1



�1



Q =




   - · · (⃗x − ⃗y) [2] KN (⃗x, ⃗y) dx1 . . . dxd dy1 . . . dyd
−1 −1



= d(g0 g1)
     (99)
is minimal.


Note that for simplicity the order of the expansion, N,
was chosen to be the same for all spatial directions. Of
course, we could also define more general kernels,


�d



K ⃗N [(][⃗x, ⃗y][) =]



KNj (xj, yj), (100)
j=1



where the vector N [⃗] denotes the orders of expansion for
the different spatial directions.


3. Reconstruction with cosine transforms


Similar to the 1D case we may consider the function
f : [−1, 1] [d] → R on a discrete grid ⃗x⃗k with

x⃗k,j = cos(ϕkj ), (101)

ϕkj = [π][(][k][j][ + 1][/][2)], (102)

N˜

kj = 0, . . ., ( N [˜]              - 1) . (103)


Note again that we could define individual numbers of

points for each spatial direction, i.e., a vector N [⃗][˜] with
elements N [˜] j instead of a single N [˜] . For all grid points
⃗x⃗k the function f (⃗x⃗k) is obtained through multidimensional discrete cosine transform, i.e., with coefficients



As described earlier, the expansion of ρ(E) in terms of
Chebyshev polynomials requires a rescaling of M → M [˜],



ρ(E) = [1]

D



D�−1

δ(E Ek) . (105)
    k=0


13



such that the spectrum of M˜ = (M − b)/a lies within
the interval [−1, 1]. Given the eigenvalues E [˜] k of M [˜] the
rescaled density ˜ρ( E [˜] ) reads



0.12


0.08


0.04



|W = 3 t|W = 9 t|
|---|---|
|W = 16 t|extended<br>localized|


~~-10~~ ~~-5~~ ~~0~~ ~~5~~ ~~10~~
E / t





0.12


0.08


0.04


0

0.12


0.08


0.04


0



ρ˜( E [˜] ) = [1]

D



D�−1

δ( E [˜] Ek), (106)
    - [˜]
k=0



0

20


16


12


8


4


0



~~-10~~ ~~-5~~ ~~0~~ ~~5~~ ~~10~~
E / t



and according to Eq. (19) the expansion coefficients become



�1



(107)



µn =



ρ˜( E [˜] ) Tn( E [˜] ) dE [˜] = [1]

D

−1



D



D�−1

Tn( E [˜] k)

k=0



M )) .
D [Tr(][T][n][( ˜]



= [1]

D



D�−1



k Tn( M [˜] ) k = [1]
⟨ | | ⟩ D
k=0



This is exactly the trace form that we introduced in
Sec. II.B, and we can immediately calculate the µn using
the stochastic techniques described in Sec. II.B.2. Knowing the moments we can use the techniques of Sec. II.D
to reconstruct ˜ρ( E [˜] ) for the whole range [−1, 1], and a
final rescaling yields ρ(E).


2. Non-interacting systems: Anderson model of disorder


Applied to a generalized model of non-interacting
fermions c [(] i [†][)][,]



FIG. 2 (Color in online edition) Standard (dashed) and typical density of states (solid line), ρ(E) and ρtyp(E) respectively,
of the 3D Anderson model on a 50 [3] site cluster with periodic
boundary conditions. For ρ(E) we calculated N = 2048 moments with R = 10 start vectors and S = 240 realizations of
disorder, for ρtyp(E) these numbers are N = 8192, R = 32
and S = 200. The lower right panel shows the phase diagram
of the model we obtained from ρtyp(E)/ρ(E) → 0 (mobility
edge).


in the interval [−W/2, W/2]. With increasing strength
of disorder, W, the single-particle eigenstates of the
model tend to become localized in the vicinity of
a particular lattice site, which excludes these states
from contributing to electronic transport. Disorder
can therefore drive a transition from metallic behavior with delocalized fermions to insulating behavior
with localized fermions (Kramer and Mac Kinnon, 1993;
Lee and Ramakrishnan, 1985; Thouless, 1974). The disorder averaged density of states ρ(E) of the model can
be obtained as described, but it contains no information
about localization. The KPM method, however, allows
also for the calculation of the local density of states,



H =



D�−1

c [†] i [M] ij [c] j [,] (108)
i,j=0



the matrix of interest M is formed by the coupling constants Mij. Knowing the spectrum of M, i.e. the singleparticle density of states ρ(E), all thermodynamic quantities of the model can be calculated. For example, the
particle density is given by

         ρ(E)
n = (109)
1 + e [β][(][E][−][µ][)][ dE]


and the free energy per site reads



ρi(E) = [1]

D



D�−1

i k δ(E Ek), (112)
|⟨ | ⟩| [2]    k=0



f = nµ
   - β [1]




ρ(E) log(1 + e [−][β][(][E][−][µ][)] ) dE, (110)



where µ is the chemical potential and β = 1/T the inverse
temperature.
As the first physical example let us consider the Anderson model of non-interacting fermions moving in a
random potential (Anderson, 1958),




- 
c [†] i [c] j [+]
⟨ij⟩ i




 H = −t



ǫic [†] i [c] i [.] (111)
i



which is a measure for the contribution of a single lattice
site (denoted by the basis state |i⟩) to the complete spectrum. For delocalized states all sites contribute equally,
whereas localized states reside on just a few sites, or,
equivalently, a certain site contributes only to a few eigenstates. This property has a pronounced effect on the
distribution of ρi(E), which at a fixed energy E characterizes the variation of ρi over different realizations of
disorder and sites i. For energies that correspond to localized eigenstates the distribution is highly asymmetric and becomes singular in the thermodynamic limit,
whereas in the delocalized case the distribution is regular and centered near its expectation value ρ(E). Therefore a comparison of the geometric and the arithmetic
average of ρi(E) over a set of realizations of disorder
and over lattice sites reveals the position of the Anderson transition (Dobrosavljevi´c and Kotliar, 1997, 1998;



Here hopping occurs along nearest neighbor bonds
⟨ij⟩ on a simple cubic lattice and the local potential ǫi is chosen randomly with uniform distribution


Schubert et al., 2005a,b). The expansion of ρi(E) is even
simpler than the expansion of ρ(E), since the moments
have the form of expectation values and do not involve a
trace,



�1



(113)



µn =



ρ˜i(E) Tn(E) dE = [1]

D

−1



D



D�−1

i k Tn( E [˜] k)
|⟨ | ⟩| [2]
k=0



14


and three electrons in the resulting t2g-shell form the local spins. The remaining electrons occupy the eg-shell
and can become itinerant upon doping, causing these
materials to show ferromagnetic order (Zener, 1951). If
the ferromagnetic (Hund’s rule) coupling is large, at each
site only the high-spin states are relevant and we can describe the total on-site spin in terms of Schwinger bosons
a [(] iσ [†][)] (Auerbach, 1994). From the electrons only the
charge degree of freedom remains, which is denoted by
the spin-less fermions c [(] i [†][)] (see, e.g. (Weiße et al., 2001)
for more details). The full quantum model, Eq. (115),
is rather complicated for analytical or numerical studies,
and we expect major simplification by treating the spin
background classically (remember that S is quite large
for the systems of interest). The limit of classical spins,
S →∞, is obtained by averaging Eq. (115) over spin
coherent states,



M ) i .
D [⟨][i][|][T][n][( ˜] | ⟩



= [1]

D



D�−1



i Tn( M [˜] ) k k i = [1]
⟨ | | ⟩⟨ | ⟩ D
k=0



In Figure 2 we show the standard density of states ρ(E),
which coincides with the arithmetic mean of ρi(E), in
comparison to the typical density of states ρtyp(E), which
is defined as the geometric mean of ρi(E),

�� ��
ρtyp(E) = exp[ log(ρi(E)) ] . (114)


With increasing disorder, starting from the boundaries
of the spectrum, ρtyp(E) is suppressed until it vanishes
completely for W/t ≳ 16.5, which is known as the critical
strength of disorder where the states in the band center
become localized (Slevin and Ohtsuki, 1999). The calculation yields the phase diagram shown in the lower right
corner of Figure 2, which compares well to other numerical results.
Since the method requires storage only for the sparse
Hamiltonian matrix and for two vectors of the corresponding dimension, quite large systems can be studied on standard desktop computers (of the order of 100 [3]

sites). The recursion is stable for arbitrarily high expansion order. In the present case we calculated as many
as 8192 moments to achieve maximum resolution in the
local density of states. The standard density of states is
usually far less demanding.


3. Interacting systems: Double exchange


Coming to interacting quantum systems, as a second example we study the evolution of the quantum
double-exchange model (Anderson and Hasegawa, 1955)
for large spin amplitude S, which in terms of spin-less
fermions c [(] i [†][)] and Schwinger bosons a [(] iσ [†][)] [(][σ][ =][↑][,][ ↓][) is given]
by the Hamiltonian




[†] ↑ [+ sin(][ θ] 2 [) e][−] [i][ φ/][2][ a] ↓ [†] �2S




(2S)! |0⟩,



|Ω(S, θ, φ)⟩ =




cos( [θ]




[θ]

2 [) e][i][ φ/][2][ a] ↑ [†] [+ sin(][ θ] 2



(116)
where θ and φ are the classical polar angles and |0⟩ the
bosonic vacuum. The resulting non-interacting Hamiltonian reads,

    H = − tij c [†] i [c] j [+ H.c.][,] (117)

⟨ij⟩


with the matrix element (Kogan and Auslender, 1988)




    tij = t cos [θ] 2 [i]




[j]

2 [e][−] [i(][φ][i][−][φ][j] [)][/][2]




[i]

2 [cos][ θ] 2 [j]




[i]

2 [sin][ θ] 2 [j]



+ sin [θ][i]



2 [j] e [i(][φ][i][−][φ][j][)][/][2][ �], (118)



i.e., spin-less fermions move in a background of random
or ordered classical spins which affect their hopping amplitude.
To assess the quality of this classical approximation
we considered four electrons moving on a ring of eight
sites, and compared the densities of states obtained for
a background of S = 3/2 quantum spins and a background of classical spins. For the full quantum Hamiltonian, Eq. (115), the (canonical) density of states was
calculated on the basis of 400 Chebyshev moments. To
reduce the Hilbert space dimension and to save resources
we made use of the SU (2) symmetry of the model: With
the stochastic approach we calculated separate moments
µ [S] n [z] for each S [z] -sector,

µ [S] n [z] [= Tr][S][z] [[][T][n][( ˜][H][)]][,] (119)

and used the dimensions D [S][z] of the sectors to obtain the
total normalized µn from the average



t
H =
  - 2S + 1





a [†] iσ [a] jσ [c][†] i [c] j (115)
⟨ij⟩,σ



with the local constraint [�] σ [a] iσ [†] [a] iσ [= 2][S][ +][ c] i [†][c] i [. This]

model describes itinerant electrons on a lattice whose
spin is strongly coupled to local spins of amplitude S,
so that the motion of the electrons mediates an effective ferromagnetic interaction between these localized
spins. In the case of colossal magneto-resistant manganites (Coey et al., 1999), for instance, cubic site symmetry
leads to a crystal field splitting of the manganese d-shell,



S� [max]



µn = [1]

D [Tr[][T][n][( ˜][H][)] =]



n
S [z] =−S [max][ µ][S][z]



. (120)

S� [max]

S [z] =−S [max][ D][S][z]



S� [max]


15



0.3


0.2


0.1



D�−1

⟨k|A|k⟩ e [−][βE][k],
k=0



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-14-0.png)







erator A reads


1 1
A =
⟨ ⟩ ZD [Tr(][A][ e][−][βH] [) =] ZD





Z = [1]



D




[1]

D [Tr(e][−][βH][) = 1] D



(121)


D�−1

e [−][βE][k], (122)

k=0



where H is the Hamiltonian of the system, Z the partition function, and Ek the energy of the eigenstate |k⟩.
Using the function



0

E / t


FIG. 3 (Color in online edition) Density of nonzero eigenvalues of the quantum double-exchange model with S = 3/2
(dashed line) and running average (red dot-dashed), calculated for 4 electrons on a 8-site ring, compared to the classical
result S →∞ (green solid). Expansion parameters: N = 400
moments and R = 100 random vectors per S [z] sector.


Note, that such a setup can be used whenever the model
under consideration has certain symmetries.


On the other hand, we solved the effective noninteracting model (117) and calculated the distributions
of non-zero energies for a background of fully disordered
classical spins. As Figure 3 illustrates, the spectrum of
the quantum model with S = 3/2 closely matches that
of the system with classical spins, providing good justification, e.g. for studies of colossal magneto-resistive
manganites that make use of a classical approximation
for the spin background. Since for the finite cluster considered the spectrum of the quantum model is discrete,
at the present expansion order KPM starts to resolve
distinct energy levels (dashed line). Therefore a running
average (dot-dashed line) compares better to the classical
spin-averaged data (bold line).


B. Static correlations at finite temperature


Densities of states provide only the most basic information about a given quantum system, and much more
details can usually be learned from the study of correlations and the response of the system to an external
probe or perturbation. Starting with static correlation
functions, let us now extend the application range of the
expansion techniques to such more involved quantities.

Given the eigenstates |k⟩ of an interacting quantum
system the thermodynamic expectation value of an op


which can be evaluated with the stochastic approach,
Sec. II.B.2.
For interacting systems at low temperature the expression in Eq. (124) is a bit problematic, since the Boltzmann factor puts most of the weight on the lower end
of the spectrum and heavily amplifies small numerical
errors in ρ(E) and a(E). We can avoid these problems
by calculating the ground state and some of the lowest
excitations exactly, using standard iterative diagonalization methods like Lanczos or Jacobi-Davidson. Then we
split the expectation value of A and the partition function Z into contributions from the exactly known states



a(E) = [1]

D



D�−1

k A k δ(E Ek) (123)
⟨ | | ⟩   k=0



and the (canonical) density of states ρ(E), we can express
the thermal expectation value in terms of integrals over
the Boltzmann weight,



A = [1]
⟨ ⟩ Z



�∞

a(E) e [−][βE] dE, (124)

−∞



Z =



�∞

ρ(E) e [−][βE] dE . (125)

−∞



Of course, similar relations hold also for non-interacting
fermion systems, where the Boltzmann weight e [−][βE] has
to be replaced by the Fermi function f (E) = (1 +
e [β][(][E][−][µ][)] ) [−][1] and the single-electron wave functions play
the role of |k⟩.
Again, the particular form of a(E) suggests an expansion in Chebyshev polynomials, and after rescaling we
find



�1



(126)



µn =



a˜(E) Tn(E) dE = [1]

D

−1



D



D�−1

k A k Tn( E [˜] k)
⟨ | | ⟩
k=0



= [1]

D [Tr(][AT][n][( ˜][H][))][,]


0.2


0.1


0.0


-0.1


-0.2



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-15-0.png)





T


FIG. 4 (Color in online edition) Nearest-neighbor S [z] -S [z] correlations of the XXZ model on a square lattice. Lines represent the KPM results with separation of low-lying eigenstates
(bold solid and bold dashed) and without (thin dashed), open
symbols denote exact results from a complete diagonalization
of a 4 × 4 system.


and contributions from the rest of the spectrum,



16


Note, that in addition to the two vectors for the Chebyshev recursion we now need memory also for the eigenstates |k⟩. Otherwise the resource consumption is the
same as in the standard scheme.
We illustrate the accuracy of this approach in Figure 4
considering the nearest-neighbor S [z] -S [z] correlations of
the square-lattice spin-1/2 XXZ model as an example,


  H = (Si [x][S] i [x] +δ [+][ S] i [y][S] i [y] +δ [+ ∆][S] i [z][S] i [z] +δ [)][ .] (134)

i,δ


As a function of temperature and for an anisotropy
−1 < ∆ < 0 this model shows a quantum to classical crossover in the sense that the correlations are
anti-ferromagnetic at low temperature (quantum effect)
and ferromagnetic at high temperature (as expected
for the classical model). (Fabricius and McCoy, 1999;
Fehske et al., 2000; Schindelin et al., 2000) Comparing
the KPM results with the exact correlations of a 4 × 4
system, which were obtained from a complete diagonalization of the Hamiltonian, the improvement due to the
separation of only a few low-lying eigenstates is obvious.
Whereas for C = 0 the data is more or less random below
T ≈ 1, the agreement with the exact data is perfect, if the
ground state and one or two excitations are considered
separately. The numerical effort required for these calculations differs largely between complete diagonalization
and the KPM method. For the former, 18 or 20 sites are
practically the limit, whereas the latter can easily handle
30 sites or more.
Note that for non-interacting systems the above separation of the spectrum is not required, since for T → 0
the Fermi function converges to a simple step function
without causing any numerical problems.


C. Dynamical correlations at zero temperature


1. General considerations


Having discussed simple expectation values and static
correlations, the calculation of time dependent quantities
is the natural next step in the study of complex quantum
models. This is motivated also by many experimental setups, which probe the response of a physical system to
time dependent external perturbations. Examples are inelastic scattering experiments or measurements of transport coefficients. In the framework of linear response
theory and the Kubo formalism the system’s response
is expressed in terms of dynamical correlation functions,
which can also be calculated efficiently with Chebyshev
expansion and KPM. Technically though, we need to distinguish between two different situations: For interacting
many-particle systems at zero temperature only matrix
elements between the ground state and excited states
contribute to a dynamical correlation function, whereas
for interacting systems at finite temperature or for noninteracting systems with a finite particle density transi


1
A =
⟨ ⟩ ZD



C�−1



k A k e [−][βE][k] + [1]
⟨ | | ⟩ Z
k=0



Z



�∞

as(E) e [−][βE] dE,

−∞

(127)



ρs(E) e [−][βE] dE (128)

−∞



�∞



Z = [1]

D



C�−1



e [−][βE][k] +

k=0



The functions

as(E) = [1]

D


ρs(E) = [1]

D



D�−1

k A k δ(E Ek), (129)
⟨ | | ⟩   k=C

D�−1

δ(E Ek) (130)
    k=C



describe the rest of the spectrum and can be expanded
in Chebyshev polynomials easily. Based on the known
states we can introduce the projection operator



P = 1 −



C�−1

|k⟩⟨k|, (131)
k=0



and find for the expansion coefficients of ˜as(E)



1

µn = [1]

D [Tr(][PAT][n][( ˜][H][))][ ≈] RD



R�−1

r PATn( H [˜] )P r,
⟨ | | ⟩
r=0



(132)
and similarly for those of ˜ρs(E)



1

µn = [1]

D [Tr(][PT][n][( ˜][H][))][ ≈] RD



R�−1

r PTn( H [˜] )P r . (133)
⟨ | | ⟩
r=0


17



tions between all eigenstates — many-particle or singleparticle, respectively — contribute. We therefore split
the discussion of dynamical correlations into two sections,
starting here with interacting many-particle systems at
T = 0.
Given two operators A and B a general dynamical correlation function can be defined through



transform gives


Re⟨A; B⟩ω [±] ˜ [=]



=
 - π [1]

[P]







D�−1 
1
k=0 ⟨0|A|k⟩⟨k|B|0⟩P ω˜ Ek
∓ [˜]



�∞

µn Un−1(˜ω),
n=1



�1


−1



Im⟨A; B⟩ω [±] ˜ [′] dω [′] = 2
ω˜ ω˜ [′]    


1
⟨A; B⟩ω [±] [= lim] ǫ→0 [⟨][0][|][A] ω + i ǫ ∓ H [B][|][0][⟩]



(139)


where we used Eq. (14). The full correlation function



D�−1



⟨0|A|k⟩⟨k|B|0⟩



i µ0
⟨A; B⟩ω [±] ˜ [=] √−1







1 ω˜ [2][ −] [2]
 


= lim
ǫ→0



k=0



�∞



�∞ 
µn Un−1(˜ω) + [i][ T][n][(˜][ω][)]
n=1 √1 ω˜ [2]



�∞



, (135)
ω + i ǫ Ek
∓



�∞ 
µn exp(− i n arccos ˜ω)
n=1



1 − ω˜ [2]




µ0 + 2



where Ek is the energy of the many-particle eigenstate |k⟩
of the Hamiltonian H, |0⟩ its ground state, and ǫ > 0.
If we assume that the product ⟨0|A|k⟩⟨k|B|0⟩ is real
the imaginary part



i
= √1



1 − ω˜ [2]



Im⟨A; B⟩ω [±] [=][ −][π]



D�−1

0 A k k B 0 δ(ω Ek) (136)
⟨ | | ⟩⟨ | | ⟩ ∓
k=0



has a similar structure as, e.g., the local density of states
in Eq. (112), and in fact, with ρi(E) we already calculated
a dynamical correlation function. Hence, after rescaling
the Hamiltonian H → H [˜] and all energies ω → ω˜ we can
proceed as usual and expand Im⟨A; B⟩ω [±] [in Chebyshev]
polynomials,



�∞ 
µn Tn(˜ω) . (137)
n=1



(140)
can thus be reconstructed from the same moments µn
that we derived for its imaginary part, Eq. (138). In contrast to the real quantities we considered so far, the reconstruction merely requires complex Fourier transform,
see Eqs. (88) and (89). If only the imaginary or real part
of ⟨A; B⟩ω [±] [is needed, a cosine or sine transform, respec-]
tively, is sufficient.
Note again, that the calculation of dynamical correlation functions for non-interacting electron systems is not
possible with the scheme discussed in this section, not
even at zero temperature. At finite band filling (finite
chemical potential) the ground state consists of a sum
over occupied single-electron states, and dynamical correlation functions thus involve a double summation over
matrix elements between all single-particle eigenstates,
weighted by the Fermi function. Clearly, this is more
complicated than Eq. (135), and we postpone the discussion of this case to Sec. III.D, where we describe methods
for dynamical correlation functions at finite temperature
and — for the case of non-interacting electrons — finite
density.



1
Im⟨A; B⟩ω [±] ˜ [=][ −] √1 − ω˜ [2]




µ0 + 2



Again, the moments are obtained from expectation values



µn = [1]

π



�1

Im⟨A; B⟩ω [±] ˜ [T][n][(˜][ω][)][ d][ω][˜][ =][ ⟨][0][|][AT][n][(][∓][H][˜] [)][B][|][0][⟩] [,]
−1



(138)
and for A ̸= B [†] we can follow the scheme outlined in
Eqs. (30) to (33). For A = B [†] the calculation simplifies
to the one in Eqs. (34) and (35), now with B|0⟩ as the
starting vector.
In many cases, especially for the spectral functions and
optical conductivities studied below, only the imaginary
part of ⟨A; B⟩ω [±] [is of interest, and the above setup is all]
we need. Sometimes however — e.g., within the Cluster Perturbation Theory discussed in Sec. IV.B — also
the real part of a general correlation function A; B ω
⟨ ⟩ [±]
is required. Fortunately it can be calculated with almost no additional effort: The analytical properties of
⟨A; B⟩ω [±] [arising from causality imply that its real part is]
fully determined by the imaginary part. Indeed a Hilbert



2. One-particle spectral function


An important example of a dynamical correlation function is the (retarded) Green function in momentum space,


Gσ( [⃗] k, ω) = ⟨c⃗k,σ; c⃗k,σ [†] [⟩] ω [+] [+][ ⟨][c] ⃗k,σ [†] [;][ c] ⃗k,σ [⟩] ω [−] [,] (141)


and the associated spectral function



which characterizes the electron absorption or emission
of an interacting system. For instance, A [−] σ [can be mea-]
sured experimentally in angle resolved photo-emission
spectroscopy (ARPES).



Aσ( [⃗] k, ω) =
     - π [1]



π [Im][ G][σ][(][⃗k, ω][)]



π (142)

= A [+] σ [(][⃗k, ω][) +][ A] σ [−][(][⃗k, ω][)][,]


18



As the first application, let us consider the
one-dimensional Holstein model for spinless
fermions (Holstein, 1959a,b),



1.0

0.5




 H = −t



(c [†] i [c] i+1 [+ H.c.)]
i




- 
(b [†] i [+][ b] i [)][n][i][ +][ ω][0]
i,σ i




 gω0




b [†] i [b] i [,] (143)
i



0

1.0

0.5

0

1.0

0.5

0

1.0

0.5

0

1.0

0.5

0

1.0

0.5



which is one of the basic models for the study of electronlattice interaction. A single band of electrons is approximated by spinless fermions c [(] i [†][)][, the density of which]
couples to the local lattice distortion described by dispersionless phonons b [(] i [†][)][. At low fermion density, with]
increasing electron phonon interaction the charges get
dressed by a surrounding lattice distortion and form new,
heavy quasi-particles known as polarons. Eventually, for
strong coupling the width of the corresponding band is
suppressed exponentially, leading to a process called selftrapping. For a half-filled band, i.e., 0.5 fermions per site,
the model allows for the study of quantum effects at the
transition from a metal to a band (or Peierls) insulator,
marked by the opening of a gap at the Fermi wave vector
and the development of a matching lattice distortion.


Since the Hamiltonian (143) involves bosonic degrees
of freedom, the Hilbert space of even a finite system has
infinite dimension. In practice, nevertheless, the contribution of highly excited phonon states is found to be
negligible at low temperature or for the ground-state, and
the system is well approximated by a truncated phonon
dition, the translational symmetry of the model can bespace with [�] i [b] i [†][b] i [≤] [M][ (B¨auml][ et al.][, 1998).] In adused to reduce the Hilbert space dimension, and, moreover, the symmetric phonon mode with momentum q = 0
can be excluded from the numerics: Since it couples to
the total number of electrons, which is a conserved quantity, its contribution can be handled analytically (Robin,
1997; Sykora et al., 2005). Below we present results for
a cluster size of L = 8 or 10, where a cut-off M = 24
or 15, respectively, leads to truncation errors < 10 [−][6]

for the ground-state energy. Alternatively, for one or
two fermionic particles and low temperatures an optimized variational basis can be constructed for infinite
systems (Bonˇca et al., 1999), which would also be suitable for our numerical approach.


In Figure 5 we present KPM data for the spectral function of the spinless-fermion Holstein model and assess its
quality by comparing with results from Quantum Monte
Carlo (QMC) and Dynamical Density Matrix Renormalization Group (DDMRG) (Jeckelmann, 2002) calculations. Starting with the case of a single electron on a
ten-site ring, Figure 5 (a) illustrates the presence of a
narrow polaron band at the Fermi level and of a broad
range of incoherent contributions to the spectral func

|Col1|Col2|k=0|
|---|---|---|
||||
|||k=π/5|
||||
||||
|||k=2π/5|
||||
|||k=3π/5|
||||
|||k=4π/5|
||||
|k=π<br>(a) n = 0.1|k=π<br>(a) n = 0.1|k=π<br>(a) n = 0.1|
||||



0

-4 -2 0 2 4
ω / t


FIG. 5 (Color in online edition) One-particle spectral function and its integral for the Holstein model (a) on a 10-site ring
with one electron, εp = g [2] ω0 = 2.0t, ω0 = 0.4t, and (b) on a
8-site ring, band filling n = 0.5, εp = g [2] ω0 = 1.6t, ω0 = 0.1t.
For comparison, in (a) the blue dashed lines represent Quantum Monte Carlo data at βt = 8 (Hohenadler et al., 2005),
and green stars indicate the position of the polaron band in
the infinite system (Bonˇca et al., 1999). In (b) the blue and
green curves denote results of Dynamical DMRG for the same
lattice size and T = 0 (Jeckelmann and Fehske, 2006).


tion, which in the spinless case reads


  A [−] (k, ω) = l, Ne 1 ck 0, Ne

l |⟨              - | | ⟩| [2]

δ[ω + (El,Ne−1 E0,Ne )] (144)
×       






0



ω / t



2


1


0


1


0


1














19



and

  A [+] (k, ω) = l, Ne + 1 c [†] k

l |⟨ | [|][0][, N][e][⟩|][2]

δ[ω (El,Ne+1 E0,Ne)] . (145)
×       -       
Here |l, Ne⟩ denotes the lth eigenstate with Ne electrons and energy El,Ne. The photo-emission part A [−]

reflects the Poisson-like phonon distribution of the polaron ground state, whereas A [+] has most of its weight in
the vicinity of the original free electron band. In terms of
the overall shape and the integrated weight, both KPM
and QMC agree very well. QMC, however, is not able to
resolve all the narrow features of the spectral function,
and the polaron band is hardly observable. Nevertheless,
QMC has the advantage that larger systems can be studied, in particular at finite temperature. As a guide to the
eye we also show the position of the polaron band in the
infinite system, which was calculated with the approach
of Bonˇca et al. (1999). In Figure 5 (b) we consider the
case of a half-filled band and strong electron-phonon coupling, where the system is in an insulating phase with an
excitation gap at the Fermi momentum k = ±π/2. Below and above the gap the spectrum is characterized by
broad multi-phonon absorption. Compared to DDMRG,
again KPM offers the better resolution and unfolds all
the discrete phonon sidebands. Concerning numerical
performance DDMRG has the advantage of a small optimized Hilbert space, which can be handled with standard
workstations. However, the basis optimization is rather
time consuming and, in addition, each frequency value
ω requires a new simulation. The KPM calculations, on
the other hand, involved matrix dimensions between 10 [8]

and 10 [10], and we therefore used high-performance computers such as Hitachi SR8000-F1 or IBM p690 for the
moment calculation. For the reconstruction of the spectra, of course, a desktop computer is sufficient.


3. Optical conductivity


The next example of a dynamical correlation function
is the optical conductivity. Here the imaginary and real
parts of our general correlation functions ⟨A; B⟩ω change
their roles due to an additional frequency integration.
The so-called regular contribution to the real part of the
optical conductivity is thus given by,



2.5

2.0

1.5

1.0

0.5

0.0


2.0

1.5

1.0

0.5

0.0


2.0

1.5

1.0

0.5

0.0


2


1


0
2


1


0

2


1


0
2


1


0
2


1



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-18-0.png)





|Col1|Col2|
|---|---|
||U/2εp= 0.93|


|Col1|Mott ins<br>U/2ε<br>p|Col3|ulator<br>= 2.14|
|---|---|---|---|
||U/2εp<br>Mott ins|Mott ins|ulator|


0 2 4 6 8








|Col1|k=±π/2|Col3|
|---|---|---|
||k=±π/2||





![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-18-3.png)



0

-6 -4 -2 0 2 4 6
ω / t


FIG. 6 (Color in online edition) (a) The optical conductivity σ [reg] (ω) and its integral S [reg] (ω) for the Holstein Hubbard
model at half-filling with different ratios of the Coulomb interaction U to the electron-lattice coupling εp = g [2] ω0, ω0 = 0.1t,
and g [2] = 7. Black dotted lines denote excitations of the pure
Hubbard model. (b) The one-particle spectral function at the
transition point, i.e., for the same parameters as in the middle
panel of (a). The system size is L = 8.


state for the Chebyshev recursion. Back-scaling and dividing by ω then yields the final result.
In Figure 6 we apply this setup to the Holstein Hubbard model, which is the generalization of the Holstein
model to true, spin-carrying electrons that interact via
a screened Coulomb interaction, modelled by a Hubbard
U -term,



σ [reg] (ω) = [1]

ω





k J 0 δ(ω (Ek E0)), (146)
Ek>E0 |⟨ | | ⟩| [2] - 


where the operator

    J = − i qt i,σ (c [†] i,σ [c] i+1,σ [−] [H.c.)] (147)


describes the current. After rescaling the energy and
shifting the frequency, ω = ˜ω + E [˜] 0, the sum can be expanded as described earlier, now with J|0⟩ as the initial




 H = −t




- 
(c [†] i,σ [c] i+1,σ [+ H.c.) +][ U]
i,σ i




 gω0




ni↑ni↓
i



b [†] i [b] i [.] (148)
i




- 
(b [†] i [+][ b] i [)][n][iσ][ +][ ω][0]
i,σ i



For a half-filled band, which now denotes a density of one


1


|Col1|Col2|Col3|Col4|Col5|Col6|Col7|Col8|T T<br>1 2|Col10|Col11|Col12|Col13|Col14|Col15|Col16|Col17|Col18|Col19|Col20|Col21|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
||||||||||||||||||||||







0



1







20


of two branches of low-lying triplet excitations by neutron
scattering (Garrett et al., 1997), which was inconsistent
with the then prevailing picture of (VO)2P2O7 being a
spin-ladder or alternating chain compound.
Studying the low-energy physics of the model (149)
the KPM approach can be used to calculate the spin
structure factor and the integrated spectral weight,



0.5



0

1


|Col1|Col2|Col3|Col4|Col5|Col6|Col7|Col8|T S<br>1 1|Col10|Col11|Col12|S<br>2<br>T<br>2|Col14|Col15|Col16|Col17|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
||||||||||||||||||





0.5



0

1

0.5


|Col1|Col2|Col3|Col4|Col5|Col6|Col7|Col8|T<br>1|Col10|Col11|Col12|Col13|Col14|Col15|Col16|Col17|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
||||||||||||||||||






  S(⃗q, ω) = k S [z] (⃗q) 0 δ(Ek E0 ω), (150)

�kω |⟨ | [⃗] | ⟩| [2]     -     N (⃗q, ω) = dω [′] S(⃗q, ω [′] ), (151)

0



0

1

0.5


|Col1|Col2|Col3|Col4|Col5|Col6|Col7|Col8|Col9|Col10|Col11|Col12|T S T<br>1 1|Col14|Col15|3|Col17|Col18|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|||||||||||||||||||





0



|Col1|Col2|Col3|Col4|Col5|Col6|Col7|Col8|Col9|Col10|Col11|Col12|Col13|T T<br>1 3|δ = 0.3<br>J /J = 0.4<br>Ja/Jb= 0.425<br>x b|Col16|Col17|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
||||||||||||||||||


ω / J
b



where S [⃗] [z] (⃗q) = [�] i,j [e][i][ ⃗q][·][⃗r][i,j][ S] i,j [z] [.] Figure 7 shows these

quantities for a 4 × 8 cluster with periodic boundary conditions. The dimension of the sector Sz = 0, which contains the ground state, is rather moderate here being of
the order of D ≈ 4 · 10 [7] only. The expansion clearly resolves the lowest (massive) triplet excitations T1, a number of singlets and, in particular, a second triplet branch
T2. The shaded region marks the two-particle continuum obtained by exciting two of the elementary triplets
T1, and illustrates that T2 is lower in energy. Since the
system is finite in size, of course, the continuum appears
only as a set of broad discrete peaks, the density of which
increases with the system size.


D. Dynamical correlations at finite temperature


1. General considerations


In the preceding section we mentioned briefly that for
non-interacting electron systems or for interacting systems at finite temperature the calculation of dynamical
correlation functions is more involved, due to the required
double summation over all matrix elements of the measured operators. Chebyshev expansion, nevertheless, offers an efficient way for handling these problems. To
be specific, let us derive all new ideas on the basis of
the optical conductivity σ(ω), which will be our primary
application below. Generalizations to other dynamical
correlations can be derived without much effort.
For an interacting system the extension of Eq. (146) is
given by



FIG. 7 Spin structure factor at T = 0 calculated for the
model (149) which aims at describing the magnetic compound
(VO)2P2O7. For more details see (Weiße et al., 1999).


electron per site, the electronic properties of the model
are governed by a competition of two insulating phases: a
Peierls (or band) insulator caused by the electron-lattice
interaction and a Mott (or correlated) insulator caused
by the electron-electron interaction. Within the optical conductivity both phases are signalled by an excitation gap, which closes at the transition between the
two phases. We illustrate this behavior in Figure 6 (a),
showing σ [reg] (ω) at strong electron-phonon coupling and
for increasing U . The data for the one-particle spectral
function in Figure 6 (b) proves that simultaneously to the
optical gap also the charge gap vanishes at the quantum
phase transition point (Fehske et al., 2004, 2002).


4. Spin structure factor


Apart from electron systems, of course, the KPM approach works also for other quantum problems such as
pure spin systems. To describe the excitation spectrum and the magnetic properties of the compound
(VO)2P2O7, some years ago we proposed the 2D spin
Hamiltonian (Weiße et al., 1999)




  σ [reg] (ω) =


k,q



k J q (e [−][βE][k] e [−][βE][q] )
|⟨ | | ⟩| [2] - δ(ω ωqk),

ZD ω    



 H = Jb




- 
i,j (1 + δ(−1) [i] )S [⃗] i,j · S [⃗] i+1,j + Ja i,j



(152)
withforward expansion of the finite temperature conductiv- ωqk = Eq − Ek. Compared to Eq. (146) a straightity is spoiled by the presence of the Boltzmann weighting factors. Some authors (Iitaka and Ebisuzaki, 2003)
try to handle this problem by expanding these factors
in Chebyshev polynomials and performing a numerical
time evolution subsequently, which, however, requires a
new simulation for each temperature. A much simpler




 + J×



⃗Si,j ⃗Si,j+1
i,j 


i,j (S [⃗] 2i,j · S [⃗] 2i+1,j+1 + S [⃗] 2i+1,j · S [⃗] 2i,j+1), (149)



where S [⃗] i,j denote spin-1/2 operators on a square lattice.
With this model we aimed at explaining the observation


approach is based on the function



j(x, y) = [1]

D



j(x, y) = [1]





k J q δ(x Ek) δ(y Eq) (153)
|⟨ | | ⟩| [2]   -   k,q



which we may interpret as a matrix element density. Being a function of two variables, j(x, y) can be expanded
with two-dimensional KPM,



(154)
(1 − x [2] )(1 − y [2] )



˜j(x, y) =



N�−1


n,m=0



µnmhnmgngmTn(x)Tm(y)



π [2][�]



where [˜] j(x, y) refers to the rescaled j(x, y), gn are the
usual kernel damping factors (see Eq. (71)), and hnm
account for the correct normalization (see Eq. (95)). The
moments µnm are obtained from



�1







µnm =



�1


−1



˜j(x, y)Tn(x)Tm(y) dx dy



−1



= [1]

D



k J q Tn( E [˜] k) Tm( E [˜] q)
|⟨ | | ⟩| [2]
k,q



(155)



21


FIG. 8 (Color in online edition) The matrix element density
j(x, y) for the 3D Anderson model with disorder W/t = 2 and
12.


of j(x, y) and reduced the numerical precision. Only recently, one of the authors generalized the Jackson kernel
and obtained high resolution optical data for the Anderson model (Weiße, 2004). More results, in particular for
interacting quantum systems at finite temperature, we
present hereafter.


2. Optical conductivity of the Anderson model


Since the Anderson model describes non-interacting
fermions, the eigenstates |k⟩ occurring in σ(ω) now denote single-particle wave functions and the Boltzmann
weight has to be replaced by the Fermi function,



= [1]

D





k Tn( H [˜] )J q q Tm( H [˜] )J k
⟨ | | ⟩⟨ | | ⟩
k,q



= [1] �Tn( H [˜] )JTm( H [˜] )J�,

D [Tr]



and again the trace can be replaced by an average over a
relatively small number R of random vectors |r⟩. The
numerical effort for an expansion of order n, m < N
ranges between 2RDN and RDN [2] operations, depending on whether memory is available for up to N vectors
of the Hilbert space dimension D or not. Given the operator density j(x, y) we find the optical conductivity by
integrating over Boltzmann factors,



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-20-1.png)

σ [reg] (ω) = [1]

ω



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-20-0.png)

�∞

       -        j(y + ω, y) f (y) − f (y + ω) dy
−∞




 =


k,q



k J q (f (Ek) f (Eq))
|⟨ | | ⟩| [2] - δ(ω ωqk) .

ω     


1
σ [reg] (ω) =
Zω


  =


k,q



�∞

       j(y + ω, y) e [−][βy]   - e [−][β][(][y][+][ω][)][ �] dy
−∞

k J q (e [−][βE][k] e [−][βE][q] )
|⟨ | | ⟩| [2] - δ(ω ωqk),

ZDω    


(156)
and, as above, we get the partition function Z from an
integral over the density of states ρ(E). The latter can
be expanded in parallel to j(x, y). Note that the calculation of the conductivity at different temperatures is
based on the same operator density j(x, y), i.e., it needs
to be expanded only once for all temperatures.
Surprisingly, the basic steps of this approach
were suggested already ten years ago (Wang, 1994;
Wang and Zunger, 1994), but — probably overlooking
its potential — applied only to the zero-temperature response of non-interacting electrons. A reason for the poor
appreciation of these old ideas may also lie in the use of
non-optimal kernels, which did not ensure the positivity



(157)
Clearly, from a computational point of view this expression is of the same complexity for both, zero and finite
temperature, and indeed, compared to Sec. III.C, we
need the more advanced 2D KPM approach.
Figure 8 shows the matrix element density j(x, y) calculated for the 3D Anderson model on a D = 50 [3] site
cluster. The expansion order is N = 64, and the moment data was averaged over S = 10 disorder samples
and R = 10 random start vectors each. Starting from a
“shark fin” at weak disorder, with increasing W the density j(x, y) spreads in the entire energy plane, simultaneously developing a sharp dip along x = y. A comparison
with Eq. (157) reveals that this dip is responsible for the
decreasing and finally vanishing DC conductivity of the
model (Weiße, 2004). In Figure 9 we show the resulting
optical conductivity at W/t = 12 for different chemical
potentials µ and temperatures β = 1/T . Note that all
curves are derived from the same matrix element density
j(x, y), which is now based on a D = 100 [3] site cluster,
expansion order N = 2048, an average over S = 440
samples and only R = 1 random start vectors each.


0.014


0.012


0.01


0.008


0.006


0.004


0.002


0


|1D KPM|2D KPM|
|---|---|
|**ED**|**1D KPM**|



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-21-1.png)

ω / t



1


0



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-21-2.png)





![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-21-0.png)





22


-1


-2


-3


-4







-1
En



n



ω / t



0.014


0.012


0.01


0.008


0.006


0.004


0.002


0



FIG. 9 (Color in online edition) Optical conductivity of the
3D Anderson model at disorder W = 12 and for different
chemical potentials µ and temperatures β = 1/T .


3. Optical conductivity of the Holstein model


Having discussed dynamical correlations for noninteracting electrons, let us now come back to the case
of interacting systems. The setup described so far works
well for high temperatures, but as soon as T gets small we
experience the same problems as with thermal expectation values and static correlations. Again, the Boltzmann
factors put most of the weight to the margins of the domain of j(x, y), thus amplifying small numerical errors.
To properly approach the limit T → 0 we therefore have
to separate the ground state and a few lowest excitations from the rest of the spectrum in a fashion similar
to the static correlations in Sec. III.B. Since we start
from a 2D expansion, the correlation function (optical
conductivity) now splits into three parts: a contribution
from the transitions (or matrix elements) between the
separated eigenstates, a sum of 1D expansions for the
transitions between the separated states and the rest of
the spectrum (see Sec. III.C), and a 2D expansion for all
transitions within the rest of the spectrum,



FIG. 10 (Color in online edition) Left: Schematic setup for
the calculation of finite-temperature dynamical correlations
for interacting quantum systems, which requires a separation
into parts handled by exact diagonalization (ED), 1D Chebyshev expansion and 2D Chebyshev expansion. Right: The
lowest eigenvalues of the Holstein model on a six site chain
for different electron-phonon coupling εp. The shaded region
marks the lowest polaron band, which was handled separately
when calculating the spectra in Figure 11.



1


0.8


0.6


0.4


0.2


0


1


0.8


0.6


0.4


0.2


0



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-21-3.png)











0.1


0.08


0.06


0.04


0.02


0


0.1


0.08


0.06


0.04


0.02


0



ω / t



ω / t




- �� σ1D [reg][(][ω][)]



D�−1



σ [reg] (ω) =



C�−1

σk,q

k,q=0

- �� σED [reg] [(][ω][)]



+



C�−1



+



D�−1

σk,q

k,q=C

- �� σ2D [reg][(][ω][)]



,



FIG. 11 (Color in online edition) Finite temperature optical
conductivity of a single electron coupled to the lattice via a
Holstein type interaction. Different colors illustrate how, in
particular, the low-temperature spectra benefit from a separation of C = 0, 1 or 6 low-energy states (Schubert et al.,
2005c). The phonon frequency is ω0/t = 0.4.


For σ2D [reg][(][ω][) we follow the scheme outlined in III.D.1, but]
use projected moments


µnm = Tr(Tn( H [˜] )PJTm( H [˜] )PJ)/D . (161)


In Figure 10 we illustrate our setup schematically and
show the lowest forty eigenvalues of the Holstein model,
Eq. (143), with a band filling of one electron. Separating
up to six states from the rest of the spectrum we obtain
the finite-temperature optical conductivity of the system,
Figure 11. For high temperatures (T = t, see lower panels) the separation of low-energy states is not necessary,
the conductivity curves for C = 0, 1 and 6 agree very
well. For low temperatures (T = 0.1t, see upper panels),
the separation is crucial. Without any separated states
(C = 0) the conductivity has substantial numerical errors



k=0



(σk,q + σq,k)
q=C



(158)
with


σk,q = . (159)

[|⟨][k][|][J][|][q][⟩|][2][(e][−][βE][k] ZDω [ −] [e][−][βE][q] [)][ δ][(][ω][ −] [ω][qk][)]


The expansions required for σ1D [reg][(][ω][) are carried out in]
analogy to Sec. III.C.3, but the resulting conductivities
are weighted appropriately when all contributions are
combined to σ [reg] (ω). Using the projection operator defined in Eq. (131), the corresponding moments read


µ [k] n [=][ ⟨][k][|][JPT][n][( ˜][H][)][PJ][|][k][⟩] [.] (160)


23



and can even become negative, if large Boltzmann factors
amplify infinitesimal numerical round-off errors of negative sign. Splitting off the ground state (C = 1) or the
entire (narrow) polaron band (C = 6 for the present sixsite cluster), we obtain reliable, high-resolution spectra
down to the lowest temperatures. From a physics point
of view, at strong electron phonon coupling (right panels)
the conductivity shows an interesting transfer of spectral
weight from high to low frequencies, if the temperature is
increased (see Schubert et al. (2005c) for more details).
With this discussion of optical conductivity as a finite
temperature dynamical correlation function we conclude
the section on direct applications of KPM. Of course, the
described techniques can be used for the solution of many
other interesting and numerically demanding problems,
but an equally important field of applications emerges,
when KPM is embedded into other numerical or analytical techniques, which is the subject of the next section.


IV. KPM AS A COMPONENT OF OTHER METHODS


A. Monte Carlo simulations


In condensed matter physics some of the most intensely
studied materials are affected by a complex interplay of
many degrees of freedom, and when deriving suitable
approximate descriptions we frequently arrive at models, where non-interacting fermions are coupled to classical degrees of freedom. Examples are colossal magnetoresistant manganites (Dagotto, 2003) or magnetic semiconductors (Schliemann et al., 2001), where the classical variables correspond to localized spin degrees of freedom. We already introduced such a model when we discussed the limit S →∞ of the double-exchange model,
Eq. (117). The properties of these systems, e.g. a ferromagnetic ordering as a function of temperature, can be
studied by standard MC procedures. However, in contrast to purely classical systems the energy of a given
spin configuration, which enters the transition probabilities, cannot be calculated directly, but requires the solution of the corresponding non-interacting fermion problem. This is usually the most time consuming part, and
an efficient MC algorithm should therefore evaluate the
fermionic trace as fast and as seldom as possible.
The first requirement can be matched by using KPM
for calculating the density of states of the fermion system, which by integration over the Fermi function yields
the energy of the underlying spin configuration. Combined with standard Metropolis single-spin updates this
led to the first MC simulations of double-exchange systems (Motome and Furukawa, 1999, 2000, 2001) on reasonably large clusters (8 [3] sites), which were later improved by replacing full traces by trace estimates and
by increasing the efficiency of the matrix vector multiplications (Alvarez et al., 2005; Furukawa and Motome,
2004).
To fulfil the second requirement it would be advan


1


0.8


0.6


0.4


0.2


|H, L=6<br>eff<br>H, L=12<br>eff<br>Alonso et al. (2001), L=6<br>Alonso et al. (2001), L=12<br>Motome et al. (2000), L→∞<br>Cluster MC, L=6<br>Cluster MC, L=12|Col2|
|---|---|
||eff <br>Heff, L=12<br>Alonso et al. (2001), L=6<br>Alonso et al. (2001), L=12<br>Motome et al. (2000), L→<br>Cluster MC, L=6|
||<br>Cluster MC, L=12|



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-22-0.png)


     P˜(a b) = min 1, [W] [(][b][)][A][(][b][ →] [a][)]
→ W (a)A(a b)



W (a)A(a → b)









0





T / t



FIG. 12 (Color in online edition) Magnetization as a function of temperature for the classical double-exchange model
at doping n = 0.5. We compare data obtained from
the effective model Heff (see text), from a hybrid Monte
Carlo approach (Alonso et al., 2001), the Truncated Polynomial Expansion Method (Motome and Furukawa, 2000,
2001), and from a KPM based Cluster Monte Carlo technique (Weiße et al., 2005). L denotes the size of the underlying three-dimensional cluster, i.e., D = L [3] is the dimension
of the fermionic problem.


tageous to replace the above single-spin updates by updates of the whole spin background. The first implementation of such ideas was given in terms of an hybrid
Monte Carlo algorithm (Alonso et al., 2001), which combines an approximate time evolution of the spin system
with a diagonalization of the fermionic problem by Legendre expansion, and requires a much smaller number of
MC accept-reject steps. However, this approach has the
drawback of involving a molecular dynamics type simulation of the classical degrees of freedom, which is a bit
complicated and which may bias the system in the direction of the assumed approximate dynamics.
Focussing on the problem of classical double exchange, Eq. (117), we therefore proposed a third approach (Weiße et al., 2005), which combines the advantages of KPM with the highly efficient Cluster MC algorithms (Janke, 1998; Krauth, 2004; Wolff, 1989). In
general, for a classical MC algorithm the transition probability from state a to state b can be written as

P (a → b) = A(a → b) P [˜] (a → b), (162)

where A(a → b) is the probability of considering the move
a → b, and P [˜] (a → b) is the probability of accepting the
move a → b. Given the Boltzmann weights of the states
a and b, W (a) and W (b), detailed balance requires that

W (a)P (a → b) = W (b)P (b → a), (163)

which can be fulfilled with a generalized Metropolis algorithm




. (164)


In the standard MC approach for spin systems only a
single randomly chosen spin is flipped. Hence, A(a →
b) = A(b → a) and the probability P [˜] (a → b) is usually
much smaller than 1, since it depends on temperature
via the weights W (a) and W (b). This disadvantage can
be avoided by a clever construction of clusters of spins,
which are flipped simultaneously, such that the a priori
probabilities A(a → b) and A(b → a) soak up any difference in the weights W (a) and W (b). We then arrive at
the famous rejection-free cluster MC algorithms (Wolff,
1989), which are characterized by P [˜] (a → b) = 1.
For the double-exchange model (117) we cannot expect
to find an algorithm with P [˜] (a → b) = 1, but even a
method with P [˜] (a → b) = 0.5 would be highly efficient.
The amplitude of the hopping matrix element (118) is
given by the cosine of half the relative angle between
neighboring spins, or tij = (1 + S [⃗] i S [⃗] j)/2. Averaging
over the fermionic degrees of freedom, we thus arrive at | | [2] an effective classical spin model



24


other classical variables (Alvarez et al., 2005), and as yet
the potential of such combined approaches is certainly
not fully exhausted.
The next application, which makes use of KPM as a
component of a more general numerical approach, brings
us back to interacting quantum systems, in particular,
correlated electron systems with strong local interactions.


B. Cluster Perturbation Theory (CPT)


1. General features of CPT


Earlier in this review we have demonstrated the advantages of the Chebyshev approach for the calculation
of spectral functions, optical conductivities and structure factors of complicated interacting quantum systems.
However, owing to the finite size of the considered systems, quantities like the spectral function A( [⃗] k, ω) could
only be calculated for a finite set of independent momenta [⃗] k. The interpretation of this “discrete” data may
sometimes be less convenient, e.g. the [⃗] k-integrated one
             electron density ρ(ω) = dk [d] A( [⃗] k, ω) does not show
bands but only discrete poles which are grouped to bandlike structures. Although this does not substantially bias
the interpretation it is desirable to restore the translational symmetry of the lattice and reintroduce an infinite
momentum space.
With the Cluster Perturbation Theory
(CPT) (Gros and Valent [´] i, 1994; S´en´echal et al., 2000;
S´en´echal et al., 2002) a straightforward way to perform
this task approximatively has recently been devised.
To describe it in a nutshell, let us consider a model of
interacting fermions on a one-dimensional chain




  Heff = −Jeff

⟨ij⟩





1 + S [⃗] i · S [⃗] j, (165)



where the particle density n approximately defines the
coupling, Jeff n(1 n)/√2. Similar to a classical
≈     
Heisenberg model, the Hamiltonian Heff is a sum over
contributions of single bonds, and we can therefore construct a cluster algorithm with P [˜] (a → b) = 1. Surprisingly, the simulation of this pure spin model yields magnetization data, which almost perfectly matches the results for the full classical double-exchange model at doping n = 0.5, see Figure 12.
For simulating the coupled spin fermion model (117)
we suggested to apply the single cluster algorithm for
Heff until approximately every spin in the system has
been flipped once, thereby keeping track of all a priori
probabilities A(a → b) of subsequent cluster flips. Then
for the new spin configuration the energy of the electron
system is evaluated with the help of KPM. Note however, that for a reliable discrimination of Heff and the full
fermionic model (117) the energy calculation needs to be
very precise. For the moment calculation we therefore
relied on complete trace summations instead of stochastic estimates. The KPM step is thus no longer linear
in D, but still much faster than a full diagonalization
of the bilinear fermionic model. Based on the resulting
energy, the new spin configuration is accepted with the
probability (164). Figure 12 shows the magnetization
of the double-exchange model as a function of temperature for n = 0.5. Except for small deviations near the
critical temperature the data obtained with the new approach compares well with the results of the hybrid MC
approach (Alonso et al., 2001), and due to the low numerical effort rather large systems can be studied.
Of course, the combination of KPM and classical
Monte Carlo not only works for spin systems. We may
also think of models involving the coupling of electronic
degrees of freedom to adiabatic lattice distortions or



Here Ui denotes a local interaction, e.g. Ui = Uni↑ni↓
for the Hubbard model. CPT starts by breaking up the
infinite system into short finite chains of L sites each
(clusters), which all are equivalent due to translational
symmetry. From the Green function of a finite chain,
G [c] ij [(][ω][) with][ i, j][ = 0][, . . ., L][ −] [1, which is calculated ex-]
actly by a suitable numerical method, the Green function
G(k, ω) of the infinite chain is obtained by reintroducing the hopping between the segments. This inter-chain
hopping is treated on the level of a random phase approximation, which neglects correlations between different chains. The Green function G [nm] ij [(][ω][) is then given]
through a Dyson equation

    G [nm] ij [(][ω][) =][ δ][nm][G] ij [c] [(][ω][) +] G [c] ii [′] [(][ω][)][V] i [ nm][′] j [′][ G][′] [m] j [′] j [′][m][(][ω][)][,]

i [′],j [′],m [′]

(167)
where Vij [nm] = t(δn,m+1δi0δj,L−1 + δn,m−1δi,L−1δj0) de      scribes the inter-chain hopping and upper indices number the different clusters. A partial Fourier transform
of the inter-chain hopping, Vij (Q) = −t(e [i][ Q] δi0δj,L−1 +




    (c [†] i+1,σ [c] i,σ [+ H.c.) +]
iσ i




 H = −t



Ui . (166)
i


![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-24-0.png)

![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-24-1.png)



k=0


k=π


ω / t



ω / t



k=0


k=π



25


it turns out, the Jackson kernel is an inadequate choice
here, since already for the non-interacting tight-binding
model it introduces spurious structures into the spectra.
The failure can be attributed to the shape of the Jackson
kernel: Being optimized for high resolution, a pole in the
Green function will give a sharp peak with most of its
weight concentrated at the center, and rapidly decaying
tails. The reconstructed (cluster) Green function therefore does not satisfy the correct analytical properties required in the CPT step. To guarantee these properties,
instead, we use the Lorentz kernel, which we constructed
in Sec. II.C.4 to mimic the effect of a finite imaginary
part in the energy argument of a Green function. Using this kernel for the reconstruction of G [c] ij [(][ω][) the CPT]
works perfectly (cf. Figure 13).
To provide further examples we present results for two
different interacting models where the cluster Green function G [c] ij [(][ω][) has been calculated through a Chebyshev ex-]
pansion as in Eq. (140). Using G [c] ij [(][ω][) =][ G][c] ji [(][ω][) (no mag-]
netic field), for a L-site chain L diagonal and L(L − 1)/2
off-diagonal elements of G [c] ij [(][ω][) have to be calculated.]
The latter can be reduced to Chebyshev iterations for
the operators c [(] i [†][)] + c [(] j [†][)][, which allows application of the]
“doubling trick” (see the remark after Eq. (138)). However, the numerical effort can be further reduced by a
factor 1/L: If we keep the ground state |0⟩ of the system
we can calculate the moments µ [ij] n [=][ ⟨][0][|][c][i][T][n][( ˜][H][)][c] j [†][|][0][⟩] [for]
L elements i = 1, . . ., L of G [c] ij [(][ω][) in a single Chebyshev]
iteration. To achieve a similar reduction within the Lanczos recursion we had to explicitly construct the eigenstates to the Lanczos eigenvalues. Then the factor 1/L
is exceeded by at least ND additional operations for the
construction of N eigenstates of a D-dimensional sparse
matrix. Hence using KPM for the CPT cluster diagonalization the numerical effort can be reduced by a factor of
1/L in comparison to the Lanczos recursion.


2. CPT for the Hubbard model


As a first example we consider the 1D Hubbard model
(Eq. (148) with g = ω0 = 0), which is exactly solvable
by Bethe ansatz (Essler et al., 2005) and was also extensively studied with DDMRG (Jeckelmann et al., 2000).
It thus provides the opportunity to assess the precision
of the KPM-based CPT. The top left panel of Figure 14
shows the one-particle spectral function at half-filling,
calculated on the basis of L = 16 site clusters and an
expansion order of N = 2048. The matrix dimension is
D ≈ 1.7 - 10 [8] . Remember that the cluster Green function
is calculated for a chain with open boundary conditions.
The reduced symmetry compared to periodic boundary
conditions results in a larger dimension of the Hilbert
space that has to be dealt with numerically. In the top
right panel the dots show the Bethe ansatz results for a
L = 64 site chain, and the lines denote the L →∞ spinon
and holon excitations each electron separates into (spincharge separation). So far the Bethe ansatz does not



FIG. 13 Spectral function for non-interacting tight-binding
electrons. Based on the Lorentz kernel CPT exactly reproduces the infinite system result (left), the Jackson kernel does
not have the correct analytical properties, therefore CPT cannot close the finite size gap at k = π/2 (right).


e [−] [i][ Q] δi,L−1δj0), gives the infinite-lattice Green function
in a mixed representation




    G [c] (ω)
Gˆij(Q, ω) =
1 − V (Q)G [c] (ω)





(168)
ij



for a momentum vector Q of the super-lattice of finite
chains and cluster indices i, j. Finally, from this mixed
representation the infinite lattice Green function in momentum space is recovered in the CPT approximation as
a simple Fourier transform



G(k, ω) = [1]

L





exp(i(i j)k) G [ˆ] ij (Lk, ω) . (169)
     i,j



The reader should be aware that restoring translational
symmetry in the CPT sense is different from performing the thermodynamic limit of the interacting system.
The CPT may be understood as a kind of interpolation
scheme from the discrete momentum space of a finite
cluster to the continuous [⃗] k-values of the infinite lattice.
The amount of information attainable from the solution
of a finite cluster problem does however not increase. Especially finite-size effects affecting the interaction properties are by no means reduced, but still determined
through the size of the underlying cluster. Nevertheless,
CPT yields appealing presentations of the finite-cluster
data, which can ease its interpretation.
At present, all numerical studies within the CPT context use Lanczos recursion for the cluster diagonalization, thus suffering from the shortcomings we discussed
earlier. As an alternative, we prefer to use the formalism
introduced in Sec. III.C, which is much better suited for
the calculation of spectral properties in a finite energy
interval.
On applying the CPT crucial attention has to be paid
to the kernel used in the reconstruction of G [c] ij [(][ω][). As]


![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-25-1.png)

k=0


k=π


ω / t



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-25-2.png)



26


k=0



k=π


ω / t







![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-25-0.png)




|2 3 s -6|Col2|Col3|
|---|---|---|
||||
|DDMRG<br>CPT+KPM|||
|DDMRG<br>CPT+KPM|||
|DDMRG<br>CPT+KPM|||
|DDMRG<br>CPT+KPM|||
|DDMRG<br>CPT+KPM|||
|DDMRG<br>CPT+KPM|||
|DDMRG<br>CPT+KPM|||









|Col1|Col2|Col3|10<br>8<br>6<br>4<br>2|
|---|---|---|---|
|~~0~~<br>~~1~~<br>~~2~~<br>~~3~~<br>k = kh + ks<br>-6<br>-4<br>-2<br>0<br><br> <br><br>0.2<br>0.4<br>0.6<br>0.8<br>1<br>~~2~~<br>~~4~~<br>~~6~~<br>~~8~~<br>ω / t<br>-0.5<br>0<br>0.5<br>1<br>Gσ(k,ω)<br>DDMRG<br>CPT+KPM<br>k =π / 2<br>k =π<br>_-Im G_<br>_Re G_|~~0~~<br>~~1~~<br>~~2~~<br>~~3~~<br>k = kh + ks<br>-6<br>-4<br>-2<br>0<br><br> <br><br>0.2<br>0.4<br>0.6<br>0.8<br>1<br>~~2~~<br>~~4~~<br>~~6~~<br>~~8~~<br>ω / t<br>-0.5<br>0<br>0.5<br>1<br>Gσ(k,ω)<br>DDMRG<br>CPT+KPM<br>k =π / 2<br>k =π<br>_-Im G_<br>_Re G_|~~0~~<br>~~1~~<br>~~2~~<br>~~3~~<br>k = kh + ks<br>-6<br>-4<br>-2<br>0<br><br> <br><br>0.2<br>0.4<br>0.6<br>0.8<br>1<br>~~2~~<br>~~4~~<br>~~6~~<br>~~8~~<br>ω / t<br>-0.5<br>0<br>0.5<br>1<br>Gσ(k,ω)<br>DDMRG<br>CPT+KPM<br>k =π / 2<br>k =π<br>_-Im G_<br>_Re G_|~~0~~<br>~~1~~<br>~~2~~<br>~~3~~<br>k = kh + ks<br>-6<br>-4<br>-2<br>0<br><br> <br><br>0.2<br>0.4<br>0.6<br>0.8<br>1<br>~~2~~<br>~~4~~<br>~~6~~<br>~~8~~<br>ω / t<br>-0.5<br>0<br>0.5<br>1<br>Gσ(k,ω)<br>DDMRG<br>CPT+KPM<br>k =π / 2<br>k =π<br>_-Im G_<br>_Re G_|


~~2~~ ~~4~~ ~~6~~ ~~8~~
ω / t


FIG. 14 (Color in online edition) Spectral function of the
1D Hubbard model for half-filling and U = 4t. Top left:
CPT result with cluster size L = 16 and expansion order
N = 2048. For similar data based on Lanczos recursion
see S´en´echal et al. (2000). Top right: Within the exact Bethe
ansatz solution each electron separates into the sum of independent spinon (red dashed) and holon (green) excitations.
The dots mark the energies of a 64-site chain. Bottom: CPT
data compared to selected DDMRG results for a system with
L = 128 sites, open boundary conditions and a broadening of
ǫ = 0.0625t. Note that in DDMRG the momenta are approximate.


allow for a direct calculation of the structure factor, the
data thus represents only the position and density of the
eigenstates, but is not weighted with the matrix elements
of the operators c [(] kσ [†][)][. Although for an infinite system we]
would expect a continuous response, the CPT data shows
some faint fine-structure. A comparison with the finitesize Bethe ansatz data suggests that these features are
an artifact of the finite-cluster Greens function which the
CPT spectral function is based on. The fine-structure is
also evident in the lower panel of Figure 14, where we
compare with DDMRG data for a L = 128 site system.
Otherwise the CPT nicely reproduces all expected features, like the excitation gap, the two pronounced spinon
and holon branches, and the broad continuum. Note also,
that CPT is applicable to all spatial dimensions, whereas
DDMRG works well only for 1D models.



FIG. 15 Spectral function A [+] (k, ω) of a single electron in the
Holstein model (corresponding to Ne = 0 in Eq. (145)). For
weak electron-phonon coupling the original band is still very
pronounced (left), for intermediate-to-strong coupling many
narrow polaron bands develop (right). The cluster size is
L = 16 (left) or L = 6 (right) and the expansion order N =
2048. See Hohenadler et al. (2003) for similar data based on
Lanczos recursion.


3. CPT for the Holstein model


Our second example is the spectral function of a single
electron in the Holstein model, i.e., Eq. (148) with U = 0.
Here, as a function of the electron-phonon interaction,
polaron formation sets in and the band width of the resulting quasi particles becomes extremely narrow at large
coupling strength. Figure 15 illustrates this behavior for
two values of the electron-phonon coupling εp = g [2] ω0.
For weak coupling the original one-electron band is still
clearly visible (dot-dashed line), but the dispersion-less
phonon (dashed line) cuts in approximately at an energy
ω0 above the band minimum, causing the formation of
a polaron band (solid line; calculated with the approach
of Bonˇca et al. (1999)), an avoided-crossing like gap and
a number of finite-size features. For strong coupling the
spectral weight of the electron is distributed over many
narrow polaron bands separated approximately by the
bare phonon frequency ω0.
In all these cases, KPM works as a reliable highresolution cluster solver, and using the concepts from
Sec. III.D we could also extend these calculations to finite
temperature. Probably, CPT is not the only approximate
technique that profits from the simplicity and stability of
KPM, and the range of its applications can certainly be
extended.


V. KPM VERSUS OTHER NUMERICAL APPROACHES


After we have given a very detailed description of the
Kernel Polynomial Method and presented a wide range
of applications, let us now classify the method in the
context of numerical many-particle techniques and comment on a number of other numerical approaches that


|Col1|Col2|Col3|
|---|---|---|
||||


x



are closely related to KPM.


A. KPM and dedicated many-particle techniques


In the previous sections we already compared KPM
data and results of other numerical many-particle techniques. Nevertheless, it seems appropriate to add a
few comments about the general concept of such calculations and the role KPM-like methods play in the
field of many-particle physics and complex quantum systems. The numerical study of interacting quantum manyparticle systems is complicated by the huge Hilbert space
dimensions involved, which usually grow exponentially
with the number of particles or the system size. There
are different strategies to cope with this: In Monte
Carlo approaches only part of the Hilbert space is sampled stochastically, thereby trying to capture the essential physics with an appropriate weighting mechanism. On the other hand, variational methods, like
DMRG (Peschel et al., 1999; Schollw¨ock, 2005) or the
specialized approach of Bonˇca et al. (1999), aim at reducing the Hilbert space dimension in an intelligent way
by discarding unimportant states, which, for instance,
contribute only at high temperature. Compared to such
methods KPM is much more basic: It is designed only for
the fast and stable calculation of the spectral properties
of a given matrix and of related correlations. Choosing a
suitable Hilbert space or optimizing the basis is the matter of the user or of external programs. It is thus a more
general approach, which can be used directly or embedded into other methods, as we illustrated in the preceding section. Of course, this simplicity and general applicability come at a certain price: For interacting manyparticle models the system sizes that can be studied by
using KPM directly are usually much smaller, compared
to DMRG and Monte Carlo. Note however, that both of
the latter methods have limitations too: For many interesting models Monte Carlo methods are plagued by the
infamous sign problem, which is not present in KPM.
When it comes to the calculation of dynamical correlation functions Monte Carlo approaches rely on power moments. The reconstruction of correlation functions from
power moments is known to be an ill-conditioned problem, in particular, if the moments are subject to statistical noise. The resolution of Monte Carlo results is
therefore much smaller compared to the data obtained
with KPM. The DMRG method develops its full potential only in one spatial dimension and for short ranged
interactions. In addition, the calculation of dynamical
correlations is limited to zero temperature, with only
a few exceptions (Sirker and Kl¨umper, 2005). None of
these restrictions apply to KPM.



20


15


10


5


0



27


2


1.5


1


0.5


0



|KPM (Jackson kernel)<br>MEM (Silver, Röder 1997)<br>N = 512|Col2|Col3|Col4|
|---|---|---|---|
|KPM (Jackson kernel)<br>MEM (Silver, Röder 1997)<br>N = 512||||


x



FIG. 16 (Color in online edition) Comparison of a KPM and a
MEM approximation to a spectrum consisting of five isolated
δ-peaks, and to a step function. The expansion order is N =
512. Clearly, for the δ-peaks MEM yields a higher resolution,
but for the step function the Gibbs oscillations return.


B. Close relatives of KPM


Having compared KPM to specialized many-particle
methods, let us now discuss more direct competitors of
KPM, i.e., methods that share the broad application
range and some of its general concepts.


1. Chebyshev expansion and Maximum Entropy Methods


The first of these approaches, the combination of
Chebyshev expansion and Maximum Entropy (MEM), is
basically an alternative procedure to transform moment
data µn into convergent approximations of the considered
function f (x). To achieve this, instead of (or in addition
to) applying kernel polynomials, an entropy

     - 1
S(f, f0) = (f (x) f0(x) log(f (x)/f0(x))) dx (170)

−1      -      

is maximized under the constraint that the moments of
the estimated f (x) agree with the given data. The function f0(x) describes our initial knowledge about f (x),
and may in the worst case just be a constant. Being
related to Maximum Entropy approaches to the classical moment problem (Mead and Papanicolaou, 1984;
Turek, 1988), for the case of Chebyshev moments different implementations of the method have been suggested (Bandyopadhyay et al., 2005; Silver and R¨oder,
1997; Skilling, 1988). Since for a given set of N moments
µn the approximation to the function f (x) is usually not
restricted to a polynomial of degree N − 1, compared
to the KPM with Jackson kernel the Maximum Entropy
approach usually yields estimates of higher resolution.
However, this higher resolution results from adding a priori assumptions and not from a true information gain (see
also Figure 16). The resource consumption of Maximum
Entropy is generally much higher than the N log N behavior we found for KPM. In addition, the approach is


non-linear in the moments and can occasionally become
unstable for large N . Note also that as yet Maximum Entropy methods have been derived only for positive quantities, f (x) > 0, such as densities of states or strictly
positive correlation functions.
Maximum Entropy, nevertheless, is a good alternative
to KPM, if the calculation of the µn is particularly time
consuming. Based on only a moderate number of moments it yields very detailed approximations of f (x), and
we obtained very good results for some computationally
demanding problems (B¨auml et al., 1998).


2. Lanczos recursion


The Lanczos Recursion Method is certainly the
most capable competitor of the Kernel Polynomial
Method (Dagotto, 1994). It is based on the Lanczos
algorithm (Lanczos, 1950), a method which was initially developed for the tridiagonalization of Hermitian
matrices and later evolved to one of the most powerful methods for the calculation of extremal eigenstates
of sparse matrices (Cullum and Willoughby, 1985). Although ideas like the mapping of the classical moment
problem to tridiagonal matrices and continued fractions
have been suggested earlier (Gordon, 1968), the use of
the Lanczos algorithm for the characterization of spectral densities (Haydock et al., 1972, 1975) was first proposed at about the same time as the Chebyshev expansion approaches, and in principle Lanczos recursion is
also a kind of modified moment expansion (Benoit et al.,
1992; Lambin and Gaspard, 1982). Its generalization
from spectral densities to zero temperature dynamical
correlation functions was first given in terms of continued fractions (Gagliano and Balseiro, 1987), and later
also an approach based on the eigenstates of the tridiagonal matrix was introduced and termed Spectral Decoding
Method (Zhong et al., 1994). This technique was then
generalized to finite temperature (Jakliˇc and Prelovˇsek,
1994, 2000), and, in addition, some variants of the
approach for low temperature (Aichhorn et al., 2003)
and based on the micro-canonical ensemble (Long et al.,
2003) have been proposed recently.
To give an impression, in Table II we compare the
setup for the calculation of a zero temperature dynamical
correlation function within the Chebyshev and the Lanczos approach. The most time consuming step for both
methods is the recursive construction of a set of vectors
φn, which in terms of scalar products yield the moments
| ⟩
µn of the Chebyshev series or the elements αn, βn of the
Lanczos tridiagonal matrix. In terms of the number of
operations the Chebyshev recursion has a small advantage, but, of course, the application of the Hamiltonian
as the dominant factor is the same for both methods. As
a drawback, at high expansion order the Lanczos iteration tends to lose the orthogonality between the vectors
φn, which it intends to establish by construction. When
| ⟩
the Lanczos algorithm is applied to eigenvalue problems



28


this loss of orthogonality usually signals the convergence
of extremal eigenstates, and the algorithm then starts to
generate artificial copies of the converged states. For the
calculation of spectral densities or correlation functions
this means that the information content of the αn and
βn does no longer increase proportionally to the number of iterations. Unfortunately, this deficiency can only
be cured with more complex variants of the algorithm,
which also increase the resource consumption. Chebyshev expansion is free from such defects, as there is a
priori no orthogonality between the φn .
| ⟩
The reconstruction of the considered function from its
moments µn or coefficients αn, βn, respectively, is also
faster and simpler within the KPM, as it makes use of
Fast Fourier Transformation. In addition, the KPM is
a linear transformation of the moments µn, a property
we used extensively above when averaging moment data
instead of the corresponding functions. Continued fractions, in contrast, are non-linear in the coefficients αn,
βn. A further advantage of KPM is our good understanding of its convergence and resolution as a function
of the expansion order N . For the Lanczos algorithm
these issues have not been worked out with the same
rigor.
We therefore think that the Lanczos algorithm is an
excellent tool for the calculation of extremal eigenstates
of large sparse matrices, but for spectral densities and
correlation functions the Kernel Polynomial Method is
the better choice. Of course, the advantages of both algorithms can be combined, e.g. when the Chebyshev
expansion starts from an exact eigenstate that was calculated with the Lanczos algorithm.


3. Projection methods


Projection methods were developed mainly in the context of electronic structure calculations or tight-binding
molecular dynamics, which both require knowledge of
the total energy of a non-interacting electron system or
of related expectation values (Goedecker, 1999; Ordej´on,
1998). The starting point of these methods is the density matrix F = f (H), where f (E) again represents
the Fermi function. Thermal expectation values, total
energies and other quantities of interest are then expressed in terms of traces over F and corresponding operators (Goedecker and Colombo, 1994). For instance,
the number of electrons and their energy are given by
Nel = Tr(F ) and E = Tr(FH), respectively. To obtain
a numerical approach that is linear in the dimension D
of H, F is expanded as a series of polynomials or other
suitable functions in the Hamiltonian H,



and the above traces are replaced by averages over random vectors |r⟩. Chebyshev polynomials are a good basis



1
F =
1 + e [β][(][H][−][µ][)][ =]



N�−1

αipi(H), (171)
i=0


29


Chebyshev / KPM complexity Lanczos recursion complexity
Initialization: Initialization:



H˜ = (H − b)/a

|φ0⟩ = A|0⟩, |φ1⟩ = H [˜] |φ0⟩
µ0 = ⟨φ0|φ0⟩, µ1 = ⟨φ1|φ0⟩


Recursion for 2N moments µn:


|φn+1⟩ = 2 H [˜] |φn⟩−|φn−1⟩
µ2n+2 = 2⟨φn+1|φn+1⟩− µ0
µ2n+1 = 2⟨φn+1|φn⟩− µ1




        β0 = ⟨0|A [†] A|0⟩

|φ0⟩ = A|0⟩/β0, |φ−1⟩ = 0


O(ND) Recursion for N coefficients αn, βn:



|φn+1⟩ = |φ [′′] ⟩/βn+1



|φ [′] ⟩ = H|φn⟩− βn|φn−1⟩, αn = ⟨φn|φ [′] ⟩




       |φ [′′] ⟩ = |φ [′] ⟩− αn|φn⟩, βn+1 =



⟨φ [′′] |φ [′′] ⟩



O(ND)


O(NM )



→ very stable → tends to lose orthogonality
Reconstruction in three simple steps: O(M log M ) Reconstruction via continued fraction



Apply kernel: ˜µn = gnµn
Fourier transform: ˜µn → f [˜] (˜ωi)

f˜[(ωi − b)/a]
Rescale: f (ωi) = π a [2]        - (ωi − b) [2]



z − α1 − β2 [2]
z − α2 − . . .
where z = ωi + i ǫ




[1] β0 [2]

π [Im]



f (z) = − [1]



z − α0 − β1 [2]



→ procedure is linear in µn → procedure is non-linear in αn, βn
→ well defined resolution ∝ 1/N → ǫ is somewhat arbitrary


TABLE II Comparison of Chebyshev expansion and Lanczos recursion for the calculation of a zero-temperature dynamical
correlation function f (ω) = [�] n [|⟨][n][|][A][|][0][⟩|][2][δ][(][ω][ −] [ω][n][). We assume][ N][ matrix vector multiplications with a][ D][-dimensional sparse]

matrix H, and a reconstruction of f (ω) at M points ωi.



for such an expansion of F (Goedecker and Teter, 1995),
and the corresponding approaches are thus closely related
to the KPM setup we described in Sec. III.A. Note however, that the expansion in Eq. (171) has to be repeated
whenever the temperature 1/β or the chemical potential µ is modified. This is particularly inconvenient, if µ
needs to be adjusted to fix the electron density of the system. To compensate for this drawback, at least partially,
we can make use of the fact that in Eq. (171) the expanded function and its expansion coefficients are known
in advance: Using implicit methods (Niklasson, 2003) the
order N approximation of F can be calculated with only
O(log N ) matrix vector operations involving the Hamiltonian H. The total computation time for one expansion
is thus proportional to D log N, compared to DN if the
sum in Eq. (171) is evaluated iteratively, e.g., on the basis
of the recursion relation Eq. (10).


Projection methods can also be used for the calculation of dynamical correlation functions. In this case the
expansion of the density matrix, which accounts for the
thermodynamics, is supplemented by a numerical time
evolution. Hence, a general correlation function is writ


0.01


0.001



![](.figures/arxiv__cond-mat-0504627/cond-mat-0504627.pdf-28-0.png)



ω / t


FIG. 17 (Color in online edition) The optical conductivity of
the Anderson model, Eq. (111), calculated with KPM and a
projection method (Iitaka, 1998). The disorder is W ≈ 15;
temperature and chemical potential read T = 0 and µ = 0.


ten as


A; B ω = lim
⟨ ⟩ ǫ→0



�∞

e [i(][ω][+i][ ǫ][)][t] Tr(e [i][ Ht] A e [−] [i][ Ht] BF ) dt,

0



(172)
and the e [±][ i][ Ht] terms are handled by standard
methods, such as Crank-Nicolson (Press et al.,
1986), Suzuki-Trotter (de Vries and De Raedt,
1993), and, very efficiently, Chebyshev expansion (Dobrovitski and De Raedt, 2003). Of course,
not only the fermionic density matrix F but also its
interacting counterpart, exp(−βH), can be expanded
in polynomials, which leads to similar methods for
interacting quantum systems (Iitaka and Ebisuzaki,
2003).
To give an impression, in Figure 17 we compare the
optical conductivity of the Anderson model calculated
with KPM (see Sec. III.D.2) and with a projection approach (Iitaka, 1998). Over a wide frequency range the
data agrees very well, but at low frequency the projection results deviate from both KPM and the analytically
expected power law σ(ω) σ0 ω [α] . Presumably this
           - ∼
discrepancy is due to an insufficient resolution or a too
short time-integration interval. There is no fundamental
reason for the projection approach to fail here.
In summary, the projection methods have a similarly
broad application range as KPM, and can also compete
in terms of numerical effort and computation time. For
finite-temperature dynamical correlations the projection
methods are characterized by a smaller memory consumption. However, in contrast to KPM they require a
new simulation for each change in temperature or chemical potential, which represents their major disadvantage.


VI. CONCLUSIONS & OUTLOOK


In this review we gave a detailed introduction to the
Kernel Polynomial Method, a numerical approach that
on the basis of Chebyshev expansion allows for an efficient calculation of the spectral properties of large matrices and of the static and dynamic correlation functions,
which depend on them. The method has a wide range
of applications in different areas of physics and quantum chemistry, and we illustrated its capability with numerous examples from solid state physics, which covered
such diverse topics as non-interacting electrons in disordered media, quantum spin models, or strongly correlated electron-phonon systems. Many of the considered quantities are hardly accessible with other methods, or could previously be studied only on smaller systems. Comparing with alternative numerical approaches,
we demonstrated the advantages of KPM measured in
terms of general applicability, speed, resource consumption, algorithmic simplicity and accuracy of the results.
Apart from further direct applications of the KPM outside the fields of solid state physics and quantum chemistry, we think that the combination of KPM with other



30


numerical techniques will become one of the major future
research directions. Certainly not only classical MC simulations and CPT, but potentially also other cluster approaches (Maier et al., 2005) or quantum MC can profit
from the concepts outlined in this review.


Acknowledgements


We thank A. Basermann, B. B¨auml, G. Hager,
M. Hohenadler, E. Jeckelmann, M. Kinateder, G. Schubert, and in particular R.N. Silver for fruitful discussions and technical support. Most of the calculations could only be performed with the generous grant
of resources by the John von Neumann-Institute for
Computing (NIC J¨ulich), the Leibniz-Rechenzentrum
M¨unchen (LRZ), the High Performance Computing Center Stuttgart (HLRS), the Norddeutscher Verbund f¨ur
Hoch- und H¨ochstleistungsrechnen (HLRN), the Australian Partnership for Advanced Computing (APAC)
and the Australian Centre for Advanced Computing and
Communications (ac3). In addition, we are grateful for
support by the Australian Research Council, the Gordon
Godfrey Bequest, and the Deutsche Forschungsgemeinschaft through SFB 652.


References


Abramowitz, M., and I. A. Stegun (eds.), 1970, Handbook of
Mathematical Functions with formulas, graphs, and mathematical tables (Dover, New York).
Aichhorn, M., M. Daghofer, H. G. Evertz, and W. von der
Linden, 2003, Phys. Rev. B 67, 161103.
Alonso, J. L., L. A. Fern´andez, F. Guinea, V. Laliena, and
V. Mart [´] in-Mayor, 2001, Nucl. Phys. B 596, 587.
Alvarez, G., C. Sen, N. Furukawa, Y. Motome, and
E. Dagotto, 2005, Comp. Phys. Comm. 168, 32.
Anderson, P. W., 1958, Phys. Rev. 109, 1492.
Anderson, P. W., and H. Hasegawa, 1955, Phys. Rev. 100,
675.
Auerbach, A., 1994, Interacting Electrons and Quantum
Magnetism, Graduate Texts in Contemporary Physics
(Springer-Verlag, Heidelberg).
Bandyopadhyay, K., A. K. Bhattacharya, P. Biswas, and
D. A. Drabold, 2005, Phys. Rev. E 71, 057701.
B¨auml, B., G. Wellein, and H. Fehske, 1998, Phys. Rev. B
58, 3663.
Benoit, C., E. Royer, and G. Poussigue, 1992, J. Phys. Condens. Matter 4, 3125.
Blumstein, C., and J. C. Wheeler, 1973, Phys. Rev. B 8, 1764.
Bonˇca, J., S. A. Trugman, and I. Batisti´c, 1999, Phys. Rev.
B 60, 1633.
Boyd, J. P., 1989, Chebyshev and Fourier Spectral Methods, number 49 in Lecture Notes in Engineering (SpringerVerlag, Berlin).
Chen, R., and H. Guo, 1999, Comp. Phys. Comm. 119, 19.
Cheney, E. W., 1966, Introduction to Approximation Theory
(McGraw-Hill, New York).
Coey, J. M. D., M. Viret, and S. von Moln´ar, 1999, Adv.
Phys. 48, 167.


Cullum, J. K., and R. A. Willoughby, 1985, Lanczos Algorithms for Large Symmetric Eigenvalue Computations, volume I & II (Birkh¨auser, Boston).
Dagotto, E., 1994, Rev. Mod. Phys. 66, 763.
Dagotto, E., 2003, Nanoscale Phase Separation and Colossal
Magnetoresistance: The Physics of Manganites and Related
Compounds, volume 136 of Springer Series in Solid-State
Sciences (Springer, Heidelberg).
Dobrosavljevi´c, V., and G. Kotliar, 1997, Phys. Rev. Lett. 78,
3943.
Dobrosavljevi´c, V., and G. Kotliar, 1998, Philos. Trans. Roy.
Soc. Lond., Ser. A 356, 57.
Dobrovitski, V. V., and H. De Raedt, 2003, Phys. Rev. E 67,
056702.
Drabold, D. A., and O. F. Sankey, 1993, Phys. Rev. Lett. 70,
3631.
Essler, F. H. L., H. Frahm, F. G¨ohmann, A. Kl¨umper, and
V. E. Korepin, 2005, The One-Dimensional Hubbard Model
(Cambridge University Press, Cambridge).
Fabricius, K., and B. M. McCoy, 1999, Phys. Rev. B 59, 381.
Fehske, H., C. Schindelin, A. Weiße, H. B¨uttner, and D. Ihle,
2000, Brazil. Jour. Phys. 30, 720.
Fehske, H., G. Wellein, G. Hager, A. Weiße, and A. R. Bishop,
2004, Phys. Rev. B 69, 165115.
Fehske, H., G. Wellein, A. P. Kampf, M. Sekania, G. Hager,
A. Weiße, H. B¨uttner, and A. R. Bishop, 2002, in High
Performance Computing in Science and Engineering, Munich 2002, edited by S. Wagner, W. Hanke, A. Bode, and
F. Durst (Springer-Verlag, Heidelberg), pp. 339–350.
Fej´er, L., 1904, Math. Ann. 58, 51.
Frigo, M., and S. G. Johnson, 2005a, Proceedings of the IEEE
93(2), 216, special issue on ”Program Generation, Optimization, and Platform Adaptation”.
Frigo, M., and S. G. Johnson, 2005b, FFTW fast fourier trans[form library, URL http://www.fftw.org/.](http://www.fftw.org/)
Furukawa, N., and Y. Motome, 2004, J. Phys. Soc. Jpn. 73,
1482.
Gagliano, E., and C. Balseiro, 1987, Phys. Rev. Lett. 59,
2999.
Garrett, A. W., S. E. Nagler, D. Tennant, B. C. Sales, and
T. Barnes, 1997, Phys. Rev. Lett. 79, 745.
Gautschi, W., 1968, Math. Comp. 22, 251.
Gautschi, W., 1970, Math. Comp. 24, 245.
Goedecker, S., 1999, Rev. Mod. Phys. 71, 1085.
Goedecker, S., and L. Colombo, 1994, Phys. Rev. Lett. 73,
122.
Goedecker, S., and M. Teter, 1995, Phys. Rev. B 51, 9455.
Gordon, R. G., 1968, J. Math. Phys. 9, 655.
Gros, C., and R. Valent [´] i, 1994, Ann. Phys. (Leipzig) 3, 460.
Haydock, R., V. Heine, and M. J. Kelly, 1972, J. Phys. C 5,
2845.
Haydock, R., V. Heine, and M. J. Kelly, 1975, J. Phys. C 8,
2591.
Hohenadler, M., M. Aichhorn, and W. von der Linden, 2003,
Phys. Rev. B 68, 184304.
Hohenadler, M., D. Neuber, W. von der Linden, G. Wellein,
J. Loos, and H. Fehske, 2005, Phys. Rev. B 71, 245111.
Holstein, T., 1959a, Ann. Phys. (N.Y.) 8, 325.
Holstein, T., 1959b, Ann. Phys. (N.Y.) 8, 343.
Iitaka, T., 1998, in High Performance Computing in RIKEN
1997 (Inst. Phys. Chem. Res. (RIKEN), Japan), volume 19
of RIKEN Review, pp. 136–143.
Iitaka, T., and T. Ebisuzaki, 2003, Phys. Rev. Lett. 90,
047203.



31


Iitaka, T., and T. Ebisuzaki, 2004, Phys. Rev. E 69, 057701.
Jackson, D., 1911, ¨Uber die Genauigkeit der Ann¨aherung
stetiger Funktionen durch ganze rationale Funktionen
gegebenen Grades und trigonometrische Summen gegebener
Ordnung, Ph.D. thesis, Georg-August-Universit¨at
G¨ottingen.
Jackson, D., 1912, Trans. Amer. Math. Soc. 13, 491.
Jakliˇc, J., and P. Prelovˇsek, 1994, Phys. Rev. B 49, 5065.
Jakliˇc, J., and P. Prelovˇsek, 2000, Adv. Phys. 49, 1.
Janke, W., 1998, Math. and Comput. in Simul. 47, 329.
Jeckelmann, E., 2002, Phys. Rev. B 66, 045114.
Jeckelmann, E., and H. Fehske, 2006, in Polarons in
Bulk Materials and Systems with Reduced Dimensionality, edited by G. Iadonisi, J. Ranninger, and G. D. Filippis (IOS Press, Amsterdam), volume 161 of International
School of Phyics Enrico Fermi, p. ?, in press, see also
[http://arXiv.org/abs/cond-mat/0510637.](http://arXiv.org/abs/cond-mat/0510637)
Jeckelmann, E., F. Gebhard, and F. H. L. Essler, 2000, Phys.
Rev. Lett. 85, 3910.
Kogan, E. M., and M. I. Auslender, 1988, Phys. Status Solidi
B 147, 613.
Korovkin, P. P., 1959, Linejnye Operatory i teorija priblizenij
(Gos. Izd. Fiziko-Matematiceskoj Literatury, Moscow).
Kosloff, R., 1988, J. Phys. Chem. 92, 2087.
Kramer, B., and A. Mac Kinnon, 1993, Rep. Prog. Phys. 56,
1469.
Krauth, W., 2004, in New Optimization Algorithms in
Physics, edited by A. K. Hartmann and H. Rieger (WileyVCH, Berlin), chapter 2, pp. 7–22.
Lambin, P., and J.-P. Gaspard, 1982, Phys. Rev. B 26, 4356.
Lanczos, C., 1950, J. Res. Nat. Bur. Stand. 45, 255.
Lanczos, C., 1966, Discourse on Fourier series (Hafner, New
York).
Lee, P. A., and T. V. Ramakrishnan, 1985, Rev. Mod. Phys.
57, 287.
Long, M. W., P. Prelovˇsek, S. El Shawish, J. Karadamoglou,
and X. Zotos, 2003, Phys. Rev. B 68, 235106.
Lorentz, G. G., 1966, Approximation of Functions (Holt,
Rinehart and Winston, New York).
Maier, T., M. Jarrell, T. Pruschke, and M. Hettler, 2005, Rev.
Mod. Phys. 77, 1027.
Mandelshtam, V. A., and H. S. Taylor, 1997, J. Chem. Phys.
107, 6756.
Mead, L. R., and N. Papanicolaou, 1984, J. Math. Phys. 25,
2404.
Motome, Y., and N. Furukawa, 1999, J. Phys. Soc. Jpn. 68,
3853.
Motome, Y., and N. Furukawa, 2000, J. Phys. Soc. Jpn. 69,
3785.
Motome, Y., and N. Furukawa, 2001, J. Phys. Soc. Jpn. 70,
3186, erratum.
Neuhauser, D., 1990, J. Chem. Phys. 93, 2611.
Niklasson, A. M. N., 2003, Phys. Rev. B 68, 233104.
Ordej´on, P., 1998, Comp. Mater. Sci. 12, 157.
Pantelides, S. T., 1978, Rev. Mod. Phys. 50, 797.
Peschel, I., X. Wang, M. Kaulke, and K. Hallberg (eds.),
1999, Density-Matrix Renormalization. A New Numerical
Method in Physics., number 528 in Lecture Notes in Physics
(Springer-Verlag, Heidelberg).
Press, W. H., B. P. Flannery, S. A. Teukolsky, and W. T.
Vetterling, 1986, Numerical Recipes (Cambridge University
Press, Cambridge).
Rivlin, T. J., 1990, Chebyshev polynomials: From Approximation Theory to Algebra and Number Theory, Pure and


Applied Mathematics (John Wiley & Sons, New York), 2
edition.
Robin, J. M., 1997, Phys. Rev. B 56, 13634.
Sack, R. A., and A. F. Donovan, 1972, Numer. Math. 18, 465.
Schindelin, C., H. Fehske, H. B¨uttner, and D. Ihle, 2000, Phys.
Rev. B 62, 12141.
Schliemann, J., J. K¨onig, and A. H. MacDonald, 2001, Phys.
Rev. B 64, 165201.
Schollw¨ock, U., 2005, Rev. Mod. Phys. 77, 259.
Schubert, G., A. Weiße, and H. Fehske, 2005a, Phys. Rev. B
71, 045126.
Schubert, G., A. Weiße, G. Wellein, and H. Fehske, 2005b, in
High Performance Computing in Science and Engineering,
Garching 2004, edited by A. Bode and F. Durst (SpringerVerlag, Heidelberg), pp. 237–250.
Schubert, G., G. Wellein, A. Weiße, A. Alvermann, and
H. Fehske, 2005c, Phys. Rev. B 72, 104304.
S´en´echal, D., D. Perez, and M. Pioro-Ladri`ere, 2000, Phys.
Rev. Lett. 84, 522.
S´en´echal, D., D. Perez, and D. Plouffe, 2002, Phys. Rev. B
66, 075129.
Silver, R. N., and H. R¨oder, 1994, Int. J. Mod. Phys. C 5,
935.
Silver, R. N., and H. R¨oder, 1997, Phys. Rev. E 56, 4822.
Silver, R. N., H. R¨oder, A. F. Voter, and D. J. Kress, 1996,
J. of Comp. Phys. 124, 115.
Sirker, J., and A. Kl¨umper, 2005, Phys. Rev. B 71,
241101(R).
Skilling, J., 1988, in Maximum Entropy and Bayesian Meth


32


ods, edited by J. Skilling (Kluwer, Dordrecht), Fundamental Theories of Physics, pp. 455–466.
Slevin, K., and T. Ohtsuki, 1999, Phys. Rev. Lett. 82, 382.
Sykora, S., A. H¨ubsch, K. W. Becker, G. Wellein, and
H. Fehske, 2005, Phys. Rev. B 71, 045112.
Tal-Ezer, H., and R. Kosloff, 1984, J. Chem. Phys. 81, 3967.
Thouless, D. J., 1974, Physics Reports 13, 93.
Turek, I., 1988, J. Phys. C 21, 3251.
Vijay, A., D. J. Kouri, and D. K. Hoffman, 2004, J. Phys.
Chem. A 108, 8987.
de Vries, P., and H. De Raedt, 1993, Phys. Rev. B 47, 7929.
Wang, L.-W., 1994, Phys. Rev. B 49, 10154.
Wang, L.-W., and A. Zunger, 1994, Phys. Rev. Lett. 73, 1039.
Weiße, A., 2004, Eur. Phys. J. B 40, 125.
Weiße, A., G. Bouzerar, and H. Fehske, 1999, Eur. Phys. J.
B 7, 5.
Weiße, A., H. Fehske, and D. Ihle, 2005, Physica B 359–361,
702.
Weiße, A., J. Loos, and H. Fehske, 2001, Phys. Rev. B 64,
054406.
Wheeler, J. C., 1974, Phys. Rev. A 9, 825.
Wheeler, J. C., and C. Blumstein, 1972, Phys. Rev. B 6, 4380.
Wheeler, J. C., M. G. Prais, and C. Blumstein, 1974, Phys.
Rev. B 10, 2429.
Wolff, U., 1989, Phys. Rev. Lett. 62, 361.
Zener, C., 1951, Phys. Rev. 82, 403.
Zhong, Q., S. Sorella, and A. Parola, 1994, Phys. Rev. B 49,
6408.
