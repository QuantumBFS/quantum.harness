---
title: "POLARON PROBLEM BY DIAGRAMMATIC QUANTUM MONTE CARLO"
authors: "N. Prokof'ev, B. Svistunov"
year: 1998
doi: "10.1103/PhysRevLett.81.2514"
arxiv: "cond-mat/9804097"
full_text: yes
---

Polaron Problem by Diagrammatic Quantum Monte Carlo


Nikolai V. Prokof’ev and Boris V. Svistunov
Russian Research Center “Kurchatov Institute”, 123182 Moscow, Russia



We present a precise solution of the polaron problem by
a novel Monte Carlo method. Basing on conventional diagrammatic expansion for the Green function of the polaron,
G(k, τ ), we construct a process of generating continuous random variables k and τ, with the distribution function exactly
coinciding with G(k, τ ). The polaron spectrum is extracted
from the asymptotic behavior of the Green function. We compare our results for the polaron energy with the variational
treatment of Feynman, and for the first time present precise
dispersion curve which features an ending point at finite momentum.


PACS numbers: 71.38.+i, 02.70.Lq, 05.20.-y


The polaron problem has a very long history starting
from the work by Landau [1]. In the most general form it
is formulated as what happens to the particle when it is
coupled to the environment, and what are the properties
of the resulting object, called polaron, which consists of
the bare particle dressed by environmental excitations.
This problem arises over and over again not only because it is of fundamental importance both for the highenergy and for the condensed matter physics, but also
because the notion of what we call “particles” becomes
more diverse and new kinds of environments appear. In
this paper we describe how the polaron problem can be
solved numerically without systematic errrrs using diagrammatic Monte Carlo method, and present the solution
of the notorious Fr¨ohlich model (see, e.g., Refs. [2,3]).
First, we explain in detail how this model fits into the
general Monte Carlo scheme [4,5] dealing with distribution functions of continuous variables. We then describe
the procedure of extracting the polaron spectrum, E(k),
from the asymptotic decay of the Green function. Although for small electron-phonon couplings the polaron
energy, E0, and the effective mass, m∗, i.e., the bottom
of the polaron band, are rather well given by the perturbation theory, the perturbative approach fails to describe
the spectrum near the threshold E(k) E0 ωp, where
                 - ≈
ωp is the frequency of the optical phonon. In fact, the
threshold features an ending point [6,7]


E(k) = E0 + ωp (k < kc), (1)
         - [(][k][ −] 2m [k] c [c][)][2]


analogous to the ending point of the excitation spectrum
in [4] He described by Pitaevskii [8]. Our numerical data
unambiguously confirm this conclusion.
We start by considering the underlying mathematics.
Suppose that for a certain random variable/set of variables, y, the distribution function,Q(y), is given in terms



of a series of integrals with ever increasing number of integration variables:






ξm




dx1 · · · dxm F (ξm, y, x1, . . ., xm) .


(2)



Q(y) =



�∞


m=0



Here ξm indexes different terms of the same order m.
The term m = 0 is understood as a certain function of y.
In Refs. [4,5] it was shown how to arrange a Metropolistype stochastic process simulating the distribution Q(y)
exactly. The process has very much in common with
the Monte Carlo simulation of a distribution given by a
multi-dimensional integral. Nevertheless, there is an essential difference associated with the fact that integration
multiplicity in the expansion Eq. (2) is varying.


FIG. 1. A typical diagram contributing to the polaron
Green function.


Projection onto the polaron problem is as follows. Let
us interpret the Matsubara (imaginary time) Green function of the polaron in the momentum-time representation, G(k, τ ), as the distribution function for the random
variables k and τ . We thus identify G with Q, and (k, τ )
with y. Equation (2) is then identified with the diagrammatic expansion of G(k, τ ) in terms of free-electron
and phonon propagators within the framework of conventional Matsubara technique at T = 0. Then, the variables x1, x2, . . ., xm are the internal times and independent momenta of the diagram ξm. A typical diagram is
presented in Fig. 1. Solid lines denote the free-electron
propagators, G [(0)] (p, τ2 τ1) = exp[ (p [2] /2 µ)(τ2 τ1)],
           -           -           -           where µ is the chemical potential. (Plank’s constant and
electron mass are set equal to unity). Dashed lines and
points stand for phonon propagators, D(q, τ2 τ1), and
vertexes of the electron-phonon coupling, V ( −q), respectively. Without loss of generality, one may fix the left end



1


of the diagram at the origin of imaginary time, ascribing
thus the time τ to the right end.
In this paper we confine ourselves to the Fr¨ohlich model

[2] where phonons are considered to be dispersionless,
and the electron-phonon coupling has the form

   -   -   He-ph = V (q) b [†] q a [†] k−q [a][k][,] (3)

k,q [−] [b][−][q]



�1/2 1
2απ



V (q) = i �2√



q [.] (4)



variables ⃗x (with a certain probability Prem(⃗x)), or rejects this modification. For the pair of complimentary
sup-processes to be balanced, the following Metropolislike prescription should be fulfilled [5]:

    R(⃗x)/W (⃗x), if R(⃗x) < W (⃗x),
Pacc(⃗x) = 1, otherwise, (5)


    W (⃗x)/R(⃗x), if R(⃗x) > W (⃗x),
Prem(⃗x) = 1, otherwise, (6)


where



In Eq. (3) ak and bq are the annihilation operators for
the electron with momentum k and for the phonon with
momentum q, respectively; α is a dimensionless coupling
constant. In the Fr¨ohlich model the phonon propagator is
independent of momentum: D(q, τ2 τ1) = exp[ ωp(τ2

          -           -           τ1)]. It is convenient, however, to attribute the vertex
factors to the dashed lines, so that a dashed line with
the momentum q contributes the factor D [˜] (q, τ2 τ1) =
                    V (q) D(τ2 τ1) to the diagram. The function F is thus
| | [2] expressed as a product of G [(0)] ’s and D [˜] ’s, in accordance
with the standard diagrammatic rules.
Simulating the distribution Q(y) is the process of sequential stochastic generation of diagrams, identical to
functions F . (In our case these are the diagrams like
that in Fig. 1, with certain fixed times and momenta.)
The global process is constituted by a number of elementary sub-processes falling into two qualitatively different classes: (I) those which do not change the type
of the diagram (change the values of variables of corresponding function F, but not the function itself), and (II)
those which do change the structure of the diagram. The
processes of the class I are rather straightforward, being
identical to those of simulating continuous distribution
corresponding to the given function F . In this paper we
use only one process of this type, namely, shifting in time
the right end of the diagram Fig. 1.
In the heart of the method are the sub-processes of
type II. The generic rules for
constructing them are as follows [5]. Suppose a certain
sub-process transforms a diagram F (ξm, y, x1, . . ., xm)
A
into F (ξm+n, y, x1, . . ., xm, xm+1, . . ., xm+n), and, correspondingly, its counterpart B performs the inverse transformation. For n new variables we introduce vector notation: ⃗x = xm+1, xm+2, . . ., xm+n . The process
{ } A
involves two steps. First, it proposes a change, selecting
a new type of diagram, ξm+n, and a particular value of ⃗x.
The vector ⃗x is selected with a certain distribution function W (⃗x). There are no requirements strictly fixing the
form of W (⃗x), but to render the algorithm most efficient,
it is desirable that W (⃗x) be chosen in accordance with
some a priori knowledge of coarse-grained statistics of the
vector ⃗x. Upon proposing the modification, the process
either accepts it, with probability, Pacc(⃗x), or rejects.
A
The process B either accepts a modification, removing



R(⃗x) = [p][B]

pA



F (ξm+n, y, x1, . . ., xm, ⃗x)

(7)
F (ξm, y, x1, . . ., xm)



and pA and pB are the probabilities of addressing to the
sub-processes A and B, which, in principle, may differ.
For solving the polaron problem it is sufficient to have
only one pair of complementary processes of type II: the
sub-process A adding a new phonon propagator to the diagram, and its counterpart B removing one phonon propagator from the diagram.
Consider the algorithm for the process A. First we
select the position τ1 for the left-hand end of the extra
phonon propagator. This is done by choosing at random (with equal probabilities) one of the free-electron
propagators, and by taking for τ1 any time (with equal
probability density) within this propagator. Then we select the position τ2 for the right-hand end of the phonon
propagator, in accordance with the distribution function
exp[ ωp(τ2 τ1)]. After that, we select the momentum
∝ - for this propagator, using the distribution (1+q/q0) [−][2],
∝
where q0 [2][/][2 =][ ω][p][. Now the proposing stage is completed,]
and we are ready to perform accept/reject step, following the above prescription, Eq. (5). The corresponding
function W (⃗x) (⃗x τ1, τ2, q ) reads
≡{ }



W (⃗x)
∝ τ [1] 0



1
(8)
(1 + q/q0) [2][ e][−][ω][p][(][τ][2][−][τ][1][)][,]



where τ0 is the length of the free-electron propagator,
where the point τ1 is selected. As mentioned earlier, this
form of W is by no means the unique one. Apart from
the factor pB/pA which will be discussed later, the ratio
(7) is now completely defined.
Consider now the algorithm for the process B. We
simply select at random (with equal probabilities) some
phonon propagator and with the probabilities given in
Eqs. (6), (8) remove it.
To complete the description of the sub-processes A and
, we should define the ratio pB/pA. It is quite reaB
sonable to address to the creation and annihilation procedures with equal probabilities. At the first glance it
might seem that this immediately leads to pB/pA = 1,
but this is not true. The point is that when we select an
electron propagator for placing the point τ1, we have Ne



2


equal chances, where Ne is the number of free-electron
propagators in the diagram being modified [denominator
of Eq. (7) ], and when we select a phonon propagator
for removing, we have Nph equal chances, where Nph is
the number of phonon propagators in the diagram from
which we try to remove the propagator [numerator of Eq.
(7) ]. These Ne and Nph are straightforwardly related to
each other:


Nph = (Ne + 1)/2 . (9)


We thus get


pB Nph
= [N][e][ + 1] = (10)
pA 2Ne 2Nph 1 [.]

               
As for the processes of type I, these may include
(i) selection of the time τ anywhere on the interval
(τ2Nph, ) according to the simple exponential distribu∞
tion of G [(0)] (k, τ τ2Nph) [obviously, the role of the chem       ical potential is to make this distribution normalizable,
and the whole diagram not to diverge to τ →∞; in fact,
we use µ as a tuning parameter to probe different timescales since the typical length of the diagram in time is
controlled by the inverse of E(k)−µ ], and (ii) the change
of the diagram momentum from k to k + p according to
the distribution function exp[−(k [¯] + p) [2] τ/2m], where k [¯]
is the average electron momentum of the diagram, i.e.,
k¯ = τ [−][1] [�] 0 [τ] [dτ][ ′][ k][(][τ][ ′][). We find it more convenient how-]
ever, to select the incoming momentum at will and keep
it fixed, since in this case we collect all the statistics to
the value of k we are interested in, instead of spreading
it over the entire k-histogram.



such that ωp = 1. After initial drop at short times we observe a pure exponential decay of G(k, τ ) at longer times
(provided we are below the threshold of Cherenkov radiation, E(k)− E0 < ωp, so that the polaron state is stable).
From the exponential asymptotic of the Green function
we readily extract the polaron energy:


G(k, τ ωp [−][1][)][ →] [Z][k] [exp[][−][(][E][(][k][)][ −] [µ][)][τ] []][ .] (11)
≫

By fine-tuning the chemical potential very close to E(k)
we may extend the time-scale for G(k, τ ) which is given
by 1/(E(k) − µ). Typically, we had reliable statistics
on the time-scale of order 100/ωp, and were thus able
to deduce the polaron energy to accuracy better than
0.01ωp. Apart from the polaron energy, the asymptotic
behavior of the Green function (11) gives us one more important physical characteristic of the polaron, the factor
Zk, which shows the fraction of the bare-electron state in
the true eigenstate of the polaron:


Zk = |⟨free particle k| polaron k⟩| [2] . (12)


0.0


-1.0


-2.0


-3.0


-4.0


-5.0


-6.0


-7.0


-8.0

0.0 1.0 Coupling strength2.0 3.0 4.0 5.0 6.0


FIG. 3. Polaron energy E0 as a function of coupling
strength. Solid line is the Feynman’s variational result.



1.0


0.9


0.8


0.7


0.6


0.5


0.4


0.3


0.2


0.1


0.0



Imaginary time







FIG. 2. Polaron Green function G(k = 0, τ ) for α = 2 and
µ = −2.2. Solid line is the exponential fit.


In Fig. 2 we show the typical data for the polaron
Green function. Following Ref. [3], we use energy units



In Fig. 3 we present our results for the bottom of the
band E0 as a function of the coupling strength α in the
most interesting intermediate region 0 < α ≤ 6. As expected, our precise data are below the solid line which
gives the upper bound for E0 (known to be the lowest
ever obtained for this problem) as derived from the Feynman’s variational treatment [3]. We cannot but note the
remarkable accuracy of the Feynman’s approach to the
polaron energy.
However, the most interesting and instructive data are
for the polaron spectrum at relatively large k. The perturbation theory result for the dispersion law, E(k) ≈
k [2] /2 − α(√2/k) sin [−][1] (k/√2) (the solid line in Fig. 4),



2/k) sin [−][1] (k/√



2) (the solid line in Fig. 4),



3


clearly demonstrates that the first-order correction is singular near the threshold of emitting the optical phonon
and even develops an unphysical maximum (by assumption, the threshold point was defined as E(kc) = E0 + ωp;
the maximum on the dispersion curve at k < kc is in contradiction with this assumption). One is bound to admit
then that near the threshold the perturbation theory for
the Fr¨ohlich model fails at any α because of the singular phonon density of states, which is δ-functional when
one ignores the curvature of the phonon dispersion law
ωp(q) ≈ ωp = const [6,7] The formalism dealing with
such cases was developed by Pitaevskii [8] for the ending
point in [4] He (a similar approach based on the TammDankoff approximation was suggested in Refs. [2,9] and
developed further in [6,7]). By applying it to the Fr¨ohlich
model we arrive at the following equation for the dispersion law

        dx
ω˜ a(k kc) + bω˜
 - - x [2] ω˜ [+][ R][(][k][ −] [k][c][,][ ˜][ω][) = 0][,][ (13)]

       
where ˜ω w (E0 +ωp), R is a smooth function of k kc
≡    -    and ˜ω, and a and b are some coefficients depending on
α and kc. This equation features an ending point at
kc, with the parabolic dependence Eq. (1) at k < kc.
The Monte Carlo data obtained for α = 1 are shown in
Fig.4. We see how an almost perfect agreement with the
perturbation theory for the band bottom transforms into
non-perturbative behavior near kc predicted by Eq. (1).


E(k)
0.0



-0.2


-0.4


-0.6


-0.8


-1.0





-1.2
0.0 0.5 1.0 1.5



k



FIG. 4. Polaron dispersion law for α = 1. Solid line is the
first-order perturbation theory result.


Apparently, the ending-point is an artifact of the dispersionless phonon spectrum. With the non-zero curvature of ωp(q) being taken into account, the ending point
will transform into sharp crossover from zero to finite
damping of the polaron state. We estimate the crossover�
region as ∆k/kc m/M where M is the mass of the
∼

host-lattice atoms.



In summary, we have presented the solution of the
polaron problem by the diagrammatic quantum Monte
Carlo method. The method directly simulates the polaron Green function (in the 4D momentum-time continuum), dealing with its conventional diagrammatic expansion. The polaron spectrum, extracted from the asymptotic behavior of the Green function, demonstrates essentially non-perturbative behavior at sufficiently large
momenta.
It is worth noting that diagrammatic Monte Carlo approach applies to any model dealing with one/few degrees
of freedom, either continuous or discrete, coupled to the
thermal bath. Series of the form Eq. (2) naturally represent the partition function in the interaction picture

[4,5], and this approach was used recently to calculate
the smearing of the Coulomb staircase in quantum dots
at strong tunneling conductance [10]. More generally, diagrammatic Monte Carlo solves any problem which can
be reduced to Eq. (2). The efficiency, however, severely
depends on the sign problem, and the convergence becomes very poor if F -functions are not positive definite.
It is thus of crucial importance to work in the representation in which the sign problem is absent.
We would like to thank N. Nagaosa, A. Furusaki, and
Yu. Kagan for many fruitful discussions. We also would
like to mention that the polaron problem was brought to
our attention and suggested for solution by N. Nagaosa.
We acknowledge the support from the Russian Foundation for Basic Research (Grant 98-02-16262).


[1] L.D. Landau, Sov. Phys., 3, 664 (1933).

[2] H. Fr¨ohlich, H. Pelzer, and S. Zienau, Phil. Mag., 41, 221
(1950).

[3] R.P. Feynman, Statistical Mechanics, Reading, Benjamin
(1972); see also R.P. Feynman, Phys. Rev., 97, 660
(1955); T.D. Schultz, Phys. Rev., 116, 526 (1959).

[4] N.V. Prokof’ev, B.V. Svistunov, and I.S. Tupitsyn,
Pis’ma v Zh. Eksp. Teor. Fiz. 64, 853 [Sov. Phys. JETP
Lett. 64, 911] (1996).

[5] N.V. Prokof’ev, B.V. Svistunov, and I.S. Tupitsyn,
[to appear in Zh. Eksp. Teor. Fiz. (May 1998); cond-](http://arxiv.org/abs/cond-mat/9703200)
[mat/9703200.](http://arxiv.org/abs/cond-mat/9703200)

[6] G.D. Whitfield and R. Puff, in Polarons and Exitons, eds.
C.G. Kuper and G.D. Whitfield, Plenum Press, N.Y., 171
(1962); Phys. Rev., 139, A338 (1965).

[7] D.M. Larsen, Phys. Rev., 144, 697 (1966).

[8] L.P. Pitaevskii, Zh. Eksp. Teor. Fiz., 36, 1168 (1959).

[9] D. Pines, in Polarons and Exitons, eds. C.G. Kuper and
G.D. Whitfield, Plenum Press, N.Y., 155 (1962).

[10] G. G¨oppert, H. Grabert, N. Prokof’ev, and B.V. Svistunov, submitted to Phys. Rev. Lett. (February 1998),
[cond-mat/9802248.](http://arxiv.org/abs/cond-mat/9802248)



4


