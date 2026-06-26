---
source: "https://arxiv.org/abs/cond-mat-0404055"
type: "arxiv"
canonical_id: "cond-mat-0404055"
title: "Quantum cluster theories"
authors: "Thomas A. Maier, M. Jarrell, Thomas Pruschke, M. Hettler"
year: "2004"
venue: "Reviews of Modern Physics"
arxiv_id: "cond-mat-0404055"
doi: "10.1103/RevModPhys.77.1027"
full_text: yes
---

# Quantum cluster theories

**Authors:** Thomas A. Maier, M. Jarrell, Thomas Pruschke, M. Hettler

**Citation:** Reviews of Modern Physics, vol. 77, pp. 1027-1080, 2004

**arXiv:** [cond-mat-0404055](https://arxiv.org/abs/cond-mat-0404055)

**DOI:** [10.1103/RevModPhys.77.1027](https://doi.org/10.1103/RevModPhys.77.1027)

## Abstract

Quantum cluster approaches offer new perspectives to study the complexities of macroscopic correlated fermion systems. These approaches can be understood as generalized mean-field theories. Quantum cluster approaches are non-perturbative and are always in the thermodynamic limit. Their quality can be systematically improved, and they provide complementary information to finite size simulations. They have been studied intensively in recent years and are now well established. After a brief historical review, this article comparatively discusses the nature and advantages of these cluster techniques. Applications to common models of correlated electron systems are reviewed.

## Full Text

## Quantum Cluster Theories

Thomas Maier [∗]


Computational Science and Math Division, Oak Ridge National Laboratory, Oak Ridge, TN 37831-6114


Mark Jarrell


Department of Physics, University of Cincinnati, Cincinnati, Ohio 45221-0011


Thomas Pruschke


Theoretical Physics, University of G¨ottingen, Tammannstr. 1, 37077 G¨ottingen, Germany


Matthias H. Hettler


Forschungszentrum Karlsruhe, Institut f¨ur Nanotechnologie, Postfach 3640, 76021 Karlsruhe, Germany


(Dated: 2nd November 2018)


Quantum cluster approaches offer new perspectives to study the complexities of macroscopic correlated fermion systems. These approaches can be understood as generalized mean-field theories.
Quantum cluster approaches are non-perturbative and are always in the thermodynamic limit.
Their quality can be systematically improved, and they provide complementary information to
finite size simulations. They have been studied intensively in recent years and are now well established. After a brief historical review, this article comparatively discusses the nature and
advantages of these cluster techniques. Applications to common models of correlated electron
systems are reviewed. [1]



Contents


I. Introduction 1
A. Brief history 1
B. Corrections to Curie-Weiss theory 3


II. Quantum cluster theories 5
A. Cluster approximation to the locator expansion 6
B. Cluster approximation to the grand potential 9
1. Cluster perturbation theory 9
2. Cellular dynamical mean-field theory 10
3. Dynamical cluster approximation 11
4. Self-consistency scheme 12
C. Discussion 12
1. Conservation and thermodynamic consistency 13
2. Causality 13
3. Reducible and irreducible quantities 13
4. Comparison 14
D. Effective cluster model 17
E. Phases with broken symmetry 18
1. Uniform magnetic field – Ferromagnetism 18
2. Superconductivity 19
3. Antiferromagnetic order 20
F. Calculation of susceptibilities 21
G. Disordered systems 22
H. Alternative cluster methods 24
1. Self-energy functional theory 24
2. Fictive impurity models 25
3. Non-local effects via spectral density approximation25


4. Non-local corrections via projection technique 25
5. Two-site correlations with composite operators 26


III. Quantum cluster solvers 26


[∗Electronic address: maierta@ornl.gov](mailto:maierta@ornl.gov)
1This article has been submitted to Reviews of Modern Physics.



A. General remarks 26
B. Perturbative techniques 27
1. Second order perturbation theory 27
2. Fluctuation exchange approximation 28
3. Non-crossing approximation 28
C. Non-perturbative techniques 30
1. Quantum Monte Carlo 30
2. Exact diagonalization 33
3. Wilson’s numerical renormalization group 33


IV. Applications to strongly correlated models 34
A. Complementarity of finite size and quantum cluster simulations35


B. 2D Falicov-Kimball model 36
C. 1D Hubbard model 37
D. 2D Hubbard model 39
1. Metal-insulator transition 39
2. Antiferromagnetism and precursors 41
3. Pseudogap at finite doping 43
4. Superconductivity 45
5. Phase diagram 48
6. Studies of related models 48


V. Conclusions and perspectives 49


Acknowledgments 50


References 50


I. INTRODUCTION


A. Brief history


The theoretical description of interacting manyparticle systems remains one of the grand challenges
in condensed matter physics. Especially the field of
strongly correlated electron systems has regained theoretical and experimental interest with the discovery of


heavy Fermion compounds and high-temperature superconductors. In this class of systems the strength of the
interactions between particles is comparable to or larger
than their kinetic energy, i.e. any theory based on a perturbative expansion around the non-interacting limit is
at least questionable. Theoretical tools to describe these
systems are therefore faced with extreme difficulties, due
to the non-perturbative nature of the problem. A large
body of work has been devoted to a direct (numerically)
exact solution of finite size systems using exact diagonalization or Quantum Monte Carlo methods. Exact diagonalization however is severely limited by the exponential growth of computational effort with system size,
while Quantum Monte Carlo methods suffer from the sign
problem at low temperatures. Another difficulty of these
methods arises from their strong finite size effects, often ruling out the reliable extraction of low energy scales
that are important to capture the competition between
different ground states often present in strongly correlated systems.
Mean-field theories are defined in the thermodynamic
limit and therefore do not face the finite size problems.
With applications to a wide variety of extended systems
from spin models to models of correlated electrons and/or
bosons, mean-field theories are extremely popular and
ubiquitous throughout science. The first mean-field theory which gained wide acceptance was developed by P.
Weiss for spin systems (Weiss, 1907). The Curie-Weiss
mean-field theory reduces the complexity of the thermodynamic lattice spin problem by mapping it onto that
of a magnetic impurity embedded in a self-consistently
determined mean magnetic field.
Generally, mean-field theories divide the infinite number of degrees of freedom into two sets. A small set of
degrees of freedom is treated explicitly, while the effects
of the remaining degrees of freedom are summarized as
a mean-field acting on the first set. Here, by mean-field
theory, we refer to the class of approximations which account for the correlations between spatially localized degrees of freedom explicitly, while treating those at longer
length scales with an effective medium. Such local approximations become exact in the limit of infinite coordination number or equivalently infinite dimensions D
(Itzykson and Drouffe, 1989); however non-local corrections become important in finite dimensions. The purpose of this review is to discuss methods for incorporating
non-local corrections to local approximations.
Many different local approximations have been developed for systems with itinerant degrees of freedom.
Early attempts focused on disordered systems, and included the virtual crystal approximation (Nordheim,
1931a,b; Parmenter, 1955; Schoen, 1969) and the
average-T matrix approximation (Beeby and Edwards,
1962; Schwartz et al., 1971). However, the most successful local approximations for disordered systems is
the Coherent Potential Approximation (CPA) developed
by Soven (1967) and others (Shiba, 1971; Taylor, 1967).
This method is distinguished from the others in that it



2


becomes exact in both the limit of dilute and concentrated disordered impurity systems, as well as the limit
of infinite dimensions.
There have been many attempts to extend the CPA
formalism to correlated systems, starting with the Dynamical CPA (DCPA) of Kakehashi (2002); Sumi (1974),
the XNCA of Kim et al. (1990); Kuramoto (1985) and
the LNCA of Grewe (1987); Grewe et al. (1988). A great
breakthrough was achieved with the formulation of the
Dynamical Mean-Field Theory (DMFT) (for a review see
Georges et al., 1996; Pruschke et al., 1995) in the limit of
infinite dimensions by Metzner and Vollhardt (1989) and
M¨uller-Hartmann (1989b). The DCPA and the DMFT
have been the most successful approaches and employ the
same mapping between the cluster and the lattice problems. They differ mostly in their starting philosophy.
The DCPA employs the CPA equations to relate the impurity solution to the lattice whereas in the DMFT the
irreducible quantities calculated on the impurity are used
to construct the lattice quantities.
Despite the success of these mean-field approaches,
they share the critical flaw of neglecting the effects of
non-local fluctuations. Thus they are unable to capture
the physics of, e.g. spin waves in spin systems, localization in disordered systems, or spin-liquid physics in
correlated electronic systems. Non-local corrections are
required to treat even the initial effects of these phenomena and to describe phase transitions to states described
by a non-local order parameter.
The first attempt to add non-local corrections to meanfield theories was due to Bethe (1935) by adding corrections to the Curie-Weiss mean-field theory. This was
achieved by mapping the lattice problem onto a selfconsistently embedded finite-size spin cluster composed
of a central site and z nearest neighbors embedded in a
mean-field. For small z, the resulting theory provides a
remarkably large and accurate correction to the transition temperature (Kikuchi, 1951; Suzuki, 1986).
Many attempts have been made to apply similar ideas
to disordered electronic systems (Gonis, 1992). Most approaches were hampered by the difficulty of constructing
a fully causal theory, with positive spectral functions.
Several causal theories were developed including the embedded cluster method (Gonis, 1992) and the molecular CPA (MCPA) by Tsukada (1969) (for a review see
Ducastelle, 1974). These methods generally are obtained
from the local approximation by replacing the impurity
by a finite size cluster in real space. As a result these approaches suffer from the lack of translational invariance,
since the cluster has open boundary conditions and only
the surface sites couple to the mean-field.
Similar effort has been expended to find cluster extensions to the DMFT, including most notably the Dynamical Cluster Approximation (DCA) (Hettler et al.,
2000, 1998) and the Cellular Dynamical Mean-Field Theory (CDMFT) (Kotliar et al., 2001). Both cluster approaches reduce the complexity of the lattice problem by
mapping it to a finite size cluster self-consistently em

bedded in a mean-field. As in the classical case, the
self-consistency condition reflects the translationally invariant nature of the original lattice problem. The main
difference with their classical counterparts arises from the
presence of quantum fluctuations. Mean-field theories for
quantum systems with itinerant degrees of freedom cut
off spatial fluctuations but take full account of temporal fluctuations. As a result the mean-field is a timeor respectively frequency dependent quantity. Even an
effective cluster problem consisting of only a single site
(DMFT) is hence a highly non-trivial many-body problem. CDMFT and DCA mainly differ in the nature of the
effective cluster problem. The CDMFT shares an identical mapping of the lattice to the cluster problem with the
MCPA, and hence also violates translational symmetries
on the cluster. The DCA maps the lattice to a periodic
and therefore translationally invariant cluster.
A numerically more tractable cluster approximation to the thermodynamic limit was developed by
Gros and Valenti (1994). In this formalism the selfconsistent coupling to a mean-field is neglected. This
leads to a theory in which the self-energy of an isolated
finite size cluster is used to approximate the lattice propagator. As shown by S´en´echal et al. (2000), this cluster
extension of the Hubbard-I approximation is obtained as
the leading order approximation in a strong-coupling expansion in the hopping amplitude and hence this method
was named Cluster Perturbation Theory (CPT).
Generally, cluster formalisms share the basic idea to
approximate the effects of correlations in the infinite lattice problem with those on a finite size quantum cluster.
We refer to this class of techniques as quantum cluster
theories. In contrast to Finite System Simulations (FSS),
these techniques are built for the thermodynamic limit.
In this review we focus on the three most established
quantum cluster approaches, the DCA, the CDMFT and
the CPT formalisms. The CDMFT approach was originally formulated for general, possibly non-orthogonal basis sets. In this review we restrict the discussion to the
usual, completely localized orthogonal basis set and refer
the reader to Kotliar et al. (2001) for the generalization
to arbitrary basis sets.
The organization of this article is as follows: To familiarize the reader with the concept of cluster approaches,
we develop in section I.B a cluster generalization of the
Curie-Weiss mean-field theory for spin systems. Section
II sets up the theoretical framework of the CDMFT,
DCA and CPT formalisms by presenting two derivations
based on different starting philosophies. The derivation
based on the locator expansion in Sec. II.A is analogous
to the cluster generalization of the Curie-Weiss meanfield method and thus is physically very intuitive. The
derivation based on the cluster approximation to diagrams defining the grand potential in Sec. II.B is closely
related to the reciprocal space derivation of the DMFT
by M¨uller-Hartmann (1989b). The nature of the different
quantum cluster approaches together with their advantages and weaknesses are assessed in Sec. II.C. Discus


3


sions of the effective cluster problem, generalizations to
symmetry broken states and the calculation of response
functions are presented in Secs. II.D, II.E and II.F. The
remainder of this section is devoted to describe the application of the DCA formalism to disordered systems in
Sec. II.G and to a brief discussion of alternative methods
proposed to introduce non-local corrections to the DMFT
method in Sec. II.H. In Sec. III we review the various
perturbative and non-perturbative techniques available
to solve the effective self-consistent cluster problem of
quantum cluster approaches. We include a detailed assessment of their advantages and limitations. Although
numerous applications of quantum cluster approaches to
models of many-particle systems are found in the literature, this field is still in its footsteps and currently very
active. A large body of work has been concentrated on
the Hubbard model. We review the progress made on
this model in Section IV together with applications to
several other strongly correlated models. Finally, Sec. V
concludes the review by stressing the limitations of quantum cluster approaches and proposing possible directions
for future research in this field.


B. Corrections to Curie-Weiss theory


As an intuitive example of the formalism developed in
the next sections we consider a systematic cluster extension of the Curie-Weiss mean-field theory for a lattice
of classical interacting spins. This discussion is especially helpful to illustrate many new aspects of cluster
approaches as compared to finite size simulations. The
quality of this approach, and its convergence and critical
properties will be demonstrated with a simple example,
the one-dimensional Ising model




  σiσi+1 h
i - i




  H = −J



σi (1)
i



where σi = ±1 are classical spins, h is an external magnetic field and the exchange integral J > 0 acts between
nearest neighbors only, favoring ferromagnetism. The
generalization of this approach to higher dimensions and
quantum spin systems is straightforward.
We start by dividing the infinite lattice into N/Nc clusters of size Nc (see Fig. 3) with origin ˜x and the exchange
integral Jij into intra- (Jc) and inter-cluster (δJ) parts


J(˜xi − x˜j) = Jcδx˜i,x˜j + δJ(˜xi − x˜j) (2)

where each of the terms is a matrix in the Nc cluster sites.
The central approximation of cluster theories is to retain
correlation effects within the cluster and neglect them
between the clusters. A natural formalism to implement
this approximation is the locator expansion. The spinsusceptibility χij = β(⟨σiσj⟩−⟨σi⟩⟨σj ⟩), where β = 1/T
is the inverse temperature, can be written as a locator
expansion in the inter-cluster part δJ of the exchange


interaction, around the cluster limit **χ** [o] = **χ** (δJ = 0) as

**χ** (˜xi − x˜j) = **χ** [o] δx˜i,x˜j + **χ** [o][ �] l δJ(˜xi − x˜l) **χ** (˜xl − x˜j) (3)


where we used again a matrix notation in the Nc cluster
sites. By using the translational invariance of quantities
in the superlattice ˜x, this expression can be simplified in
the reciprocal space ˜q of ˜x to


**χ** (˜q) = **χ** [o] + **χ** [o] δJ(˜q) **χ** (˜q) . (4)


This locator expansion has two well-defined limits. For
an infinite size cluster it recovers the exact result since
the surface to volume ratio vanishes making δJ irrelevant,
and thus **χ** = **χ** [o] . For a single site cluster, Nc = 1,
it recovers the Curie-Weiss mean-field theory. This is
intuitively clear since for Nc = 1 fluctuations between all
sites are neglected. With the susceptibility of a single
isolated site χ [o] = 1/T and δJ(˜q = 0) = J(q = 0) = J,
we obtain for the uniform susceptibility


1 1
χ(q = 0) = (5)
1/χ [o] J(q = 0) [=] T Tc

       -        
the mean-field result with critical temperature Tc = J.
For cluster sizes larger than one, translational symmetry within the cluster is violated since the clusters
have open boundary conditions and δJ only couples sites
on the surface of the clusters. As detailed in the next
section, this shortcoming can be formally overcome and
translational invariance restored by considering an analogous expression to the locator expansion (4) in the
Fourier space Q of the cluster


χ(Q, ˜q) = χ [o] (Q) + χ [o] (Q)δJ(Q, ˜q)χ(Q, ˜q)

1
= (6)
1/χ [o] (Q) δJ(Q, ˜q) [,]
            
with analogous relations for the intra- and inter-cluster
parts of J



4


cluster sites is obtained by averaging or coarse-graining
over the superlattice wave-vectors ˜q



χ¯(Q) = [N][c]

N





1
χ(Q, ˜q) = (9)
1/χ [o] (Q) Γ(Q) [.]
q˜  


with the hybridization function



Nc



Γ(Q) =



1 + [N][c]




 
Nc

N q˜ [δJ] [2][(][Q,][ ˜][q][)][χ][(][Q,][ ˜][q][)]




[c]   - (10)

N q˜ [δJ][(][Q,][ ˜][q][)][χ][(][Q,][ ˜][q][)][ .]



This follows from the fact that the isolated cluster susceptibility χ [o] (Q) does not depend on the integration variable
q˜ in Eq. (9).
This expression defines the effective cluster model




  Hc = −



J¯(Q)σ(Q)σ(−Q) − hσ(Q = 0)
Q




 



δJ(Q, ˜q)σ(Q)⟨σ(−Q − q˜)⟩, (11)
Q,q˜



δJ(Q, ˜q) = J(Q + ˜q) − J [¯] (Q) (7)



J¯(Q) = [N][c]







where σ(Q) (σ(q)) denotes the cluster (lattice) Fourier
transform of σi and ⟨. . .⟩ the expectation value calculated with respect to the cluster Hamiltonian c. As in
H
the Curie-Weiss theory, the cluster model is used to selfconsistently determine the order parameter ⟨σ(Q + ˜q)⟩ =
⟨σ(Q)⟩δ(˜q) in the ferromagnetic state. In the paramagnetic state, the susceptibility calculated in the cluster
model takes the same form as the coarse-grained result
Eq. (9) obtained from the locator expansion.
The uniform susceptibility χ(Q = 0, ˜q = 0) contains
information about the nature of this cluster approach, its
critical properties and its convergence with cluster size.
The sum in Eq. (8) may be solved analytically


J¯(Q = 0) = J(Nc/π) sin(π/Nc) . (12)


The isolated cluster susceptibility χ [o] (Q) can also be calculated analytically by using the transfer matrix method
to give (Goldenfeld, 1992)

χ [o] (Q = 0) = β exp(2K) [1][ −] [(tanh(][K][))][N][c] (13)

1 + (tanh(K)) [N][c][,]


where K = βJ [¯] (Q = 0) = βJ(Nc/π) sin(π/Nc).
With these expressions the uniform lattice susceptibility
Eq. (6) becomes


1
χ(T ) = (14)
1/χ [o] (Q = 0) − δJ(Q = 0, ˜q = 0)

1
=
1/χ [o] (Q = 0) J (1 (Nc/π) sin(π/Nc)) [.]
           -            
The cluster estimate of the lattice susceptibility interpolates between the Curie-Weiss result and the exact lattice
result as Nc increases. It may be used to reveal some of
the properties of cluster approximations and to compare
the cluster results to both the finite-size calculation and
the exact result in the thermodynamic limit.



N



J(Q + ˜q) . (8)

q˜



Here, ˜q is a vector in the reciprocal space of ˜x, and Q
is a vector in the reciprocal space of the cluster sites.
The Fourier transform of the exchange integral is given
by J(Q + ˜q) = J cos(Q + ˜q), the intra-cluster exchange
is J [¯] (Q), while the inter-cluster exchange is δJ(Q, ˜q). As
we will see in the next section, the resulting formalism
is analogous to the dynamical cluster approximation for
itinerant fermion systems.
In analogy to the Curie-Weiss theory, the lattice system can now be mapped onto an effective cluster model
embedded in a mean-field since correlations between the
clusters are neglected. The susceptibility restricted to


5



5


4


3


2


1



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-4-0.png)



0

Nc



Figure 1 The cluster and finite-size estimates of the uniform
lattice susceptibility versus cluster size when J = 1 and T =
0.7.


First, both the cluster mean-field result Eq. (14) and
the finite-size result Eq. (13) with K = βJ may be regarded as an approximation to the thermodynamic result. However, as illustrated in Fig. 1, the cluster meanfield result converges more quickly as a function of cluster
size Nc than the finite size result. This reflects the superior starting point of the cluster approximation compared
to the finite-size calculation. The cluster approximation
is an expansion about the mean-field result, whereas the
finite-size calculation is an expansion about the atomic
limit.
It is instructive to explore the convergence of the cluster result analytically. For large Nc, the character of the
susceptibility Eq. (14) can be split into three regimes. At
very high temperatures



T −Tc
build like ξ ��� Tc
∼



Tc



�2 1 π
120 Nc

 


1
χ(T ) for T J (15)
≈ T Θ ≫
    


with the critical temperature Tc > 0, whereas the exact
susceptibility in this regime χ(T ) ≈ β exp (2βJ) does not
diverge until zero temperature. This discrepancy is expected in cluster approximations, since they treat long
length scales which drive the transition in a mean-field
way and therefore neglect long wave-length modes which
eventually suppress the transition. Hence, cluster approximations generally predict finite transition temperatures independent of dimensionality due to their residual
mean-field character. With increasing cluster size however, the transitions are expected to be systematically
suppressed by the inclusion of longer-ranged fluctuations.
For cluster sizes larger than one, all three regions are
evident in the plot of the cluster mean-field estimate of
the inverse susceptibility, shown in the inset to Fig. 2.
For Nc = 8 and Nc = 16, the high and low temperature parts are seen as straight lines on the plot in the
inset, with the crossover region in between. In numerical simulations with significant sources of numerical noise
especially close to the transition, it is extremely difficult
to resolve the true low-temperature mean-field behavior. Exponents extracted from fits to the susceptibility
in these simulations will more likely reflect the properties
of the intermediate temperature regime.
Despite the large deviations of the cluster result from
the exact result low temperatures, we may still extract the correct physics through finite size extrapolation. In general, for a system where the correlations

−ν

build like ξ ��� T −TcTc ���, we expect Tc Tc [∗] c,
∼ ∼ [−] [aL][−][1][/ν]

where Tc [∗] is the exact transition temperature, Lc is
the linear cluster size, and a is a positive real constant (Suzuki, 1986). However, for the 1D Ising system,
ξ ∼ 21 [exp (][βJ][), so more care must be taken.] Fortunately, an analytic expression for the transition temperature may be extracted from Eq. (14). For large clus


�4 [�]
. This behavior





  1 π
6 Nc



ters, Tc JNc
≈



is shown in the main frame of Fig. 2 with the circles depicting the numerical values for Tc and the solid line their
asymptotic behavior.




 
[J] π

6 Nc



�2
. At intermediate temperatures,



where Θ 2J + [J] 6
≈




    χ(T ) βe [2][βJ] 1
≈   - [βJ] 3




π

Nc



for J ≫ T ≫ Tc .



�2 [�]



(16)
The true critical behavior of the system can be resolved
by studying the properties of this intermediate temperature regime. At both high and intermediate temperatures, the susceptibility differs from the exact result by
corrections of order O(1/Nc [2][). In general, cluster meth-]
ods with periodic boundary conditions have corrections
of order (1/L [2] c [), where][ L][c] [=][ N][ 1] c [/D] is the linear size of
O
the cluster.
At low temperatures, very close to the transition to
the ferromagnetic state, deviations from the exact result
are far larger. Here, for large clusters


Nc
χ(T ), (17)
∼ T Tc
            


II. QUANTUM CLUSTER THEORIES


In this section we provide two derivations of quantum
cluster approaches for systems with itinerant quantum
degrees of freedom. The locator expansion in Sec. II.A
is analogous to the cluster extension of the Curie-Weiss
mean-field theory developed in the preceding section.
Sec. II.B provides a microscopic derivation based on cluster approximations to the thermodynamic grand potential. A detailed discussion of the nature of quantum
cluster approaches and the effective cluster model is presented in Secs. II.C and II.D. Generalizations for symmetry broken phases, the calculation of susceptibilities
and the application to disordered systems is explained in
Secs. II.E, II.F and II.G and a brief discussion of alternative cluster methods is presented in Sec. II.H.


1


0.75


0.5


0.25







0





|T/J<br>0 1 2 3<br>1.5<br>1<br>0.5 1/χ(T)<br>N=1<br>0 c<br>N=2<br>c<br>-0.5 N c=8<br>N=16<br>c<br>-1|Col2|Col3|Col4|Col5|
|---|---|---|---|---|
|0<br>1<br>2<br>3<br>T/J<br>-1<br>-0.5<br>0<br>0.5<br>1<br>1.5<br>1/χ(T)<br>Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|
|0<br>1<br>2<br>3<br>T/J<br>-1<br>-0.5<br>0<br>0.5<br>1<br>1.5<br>1/χ(T)<br>Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|Nc=1<br>Nc=2<br>Nc=8<br>Nc=16||
|0<br>1<br>2<br>3<br>T/J<br>-1<br>-0.5<br>0<br>0.5<br>1<br>1.5<br>1/χ(T)<br>Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|Nc=1<br>Nc=2<br>Nc=8<br>Nc=16||
|0<br>1<br>2<br>3<br>T/J<br>-1<br>-0.5<br>0<br>0.5<br>1<br>1.5<br>1/χ(T)<br>Nc=1<br>Nc=2<br>Nc=8<br>Nc=16|Nc=1<br>Nc=2<br>Nc=8<br>Nc=16||||


1/Nc



Figure 2 Transition temperature for the 1D Ising model versus the inverse cluster size when J = 1 obtained with the
cluster mean-field approach. For large clusters, Tc 1/Nc,
∼
shown as a solid line. Inset: The inverse susceptibility versus temperature. The Curie-Weiss behavior at low T where
1/χ(T ) is linear in T, illustrates that the transition is always
mean-field like. The true critical behavior of the transition is
seen in the crossover region near T = J.


A. Cluster approximation to the locator expansion


In this section, we derive a number of cluster formalisms for itinerant many body systems using an analogous approach to that discussed in Sec. I.B for classical
spin systems. For simplicity we assume in this section
that no symmetry breaking occurs; the treatment of symmetry broken phases is discussed in Sec. II.E. The basic
idea is to write down a locator expansion, i.e. an expansion in space around a finite-size cluster. This approach
is not only intuitive but also allows us to assess the nature
of quantum cluster approximations. As with their classical counterparts, quantum cluster theories approximate
the lattice problem with many degrees of freedom by an
effective cluster problem with few degrees of freedom embedded in an external bath or mean-field created from the
remaining degrees of freedom. By neglecting correlations
that extend beyond the cluster size, one can then formulate a theory in which the lattice system is replaced
by an effective cluster embedded in a mean-field host.
While the formalism derived here is analogous to the formalism discussed in Sec. I.B for spin systems, there are
significant differences. Since we are dealing with itinerant fermions, the theory is built upon the single-particle
Green function instead of the two-particle spin correlation function, and the mean-field is dynamical due to the
itinerant nature of the particles.
This derivation is illustrated on the example of the
extended Hubbard model



6


niσ = c [†] iσ [c] iσ [is their corresponding number density, and]
Uij denotes the Coulomb repulsion between electrons on
sites i and j. The hopping amplitude between sites i and
j is denoted by tij, its local contribution tii = ǫo and
its Fourier transform to reciprocal space is the dispersion
ǫk. In this section we limit the discussion to the regular
Hubbard model with a purely local interaction Uij =
U (1 δσσ′ )δij . The more general case of finite non-local
  interactions Uij for i ̸= j is discussed in Sec. II.B.
The central quantity upon which we build the locator expansion is the single-particle thermodynamic Green
function (τ is the imaginary time, Tτ the corresponding
time ordering operator, β = 1/T the inverse temperature
and ωn are the fermionic Matsubara frequencies)

Gij,σ(τ ) = −⟨Tτ ciσ(τ )c [†] jσ [⟩] (19)



�β



Gij,σ(iωn) =



dτe [iω][n][τ] Gij,σ(τ ) ; ωn = [(2][n][ + 1)][π]

β

0



(20)
β



or respectively its analytical continuation Gij,σ(z) =
⟨⟨ciσ, c [†] jσ [⟩⟩][z][ to complex frequencies][ z][.]
To set up a suitable notation for cluster schemes, we
divide the D-dimensional lattice of N sites into a set of
finite-size clusters each with Nc sites of linear size Lc such
that Nc = L [D] c [, and resolve the first Brillouin zone into]
a corresponding set of reduced zones which we call cells.
This notation is illustrated in Fig. 3 for Nc = 4 site clusters. For larger cluster sizes and more complex cluster
geometries we refer the reader to Jarrell et al. (2001b).
Care should be taken so that the point group symmetry
of the clusters does not differ too greatly from that of
the original lattice (Betts and Stewart, 1997). We use
the coordinate ˜x to label the origin of the clusters and
X to label the Nc sites within a cluster, so that the site
indices of the original lattice x = X + ˜x. The points ˜x
form a superlattice with a reciprocal space labeled by k [˜] .
The reciprocal space corresponding to the sites X within
a cluster shall be labeledinteger nα. Then the wave-vectors in the full Brillouin K, with Kα = nα · 2π/Lc and
zone are given by k = K + k [˜] .
With these conventions, the Fourier transforms of a
given function f (X, ˜x) for intra- and inter-cluster coordinates are defined as



f (X, ˜x) = [N][c]

N



f (X, ˜x) = [N][c]

N

  f (X, k [˜] ) =





e [i][k][˜][·][x][˜] f (X, k [˜] ) (21)
k˜



e [−][i][k][˜][·][x][˜] f (X, ˜x) (22)

x˜








 H =



2



1
f (X, k [˜] ) =
Nc

  f (K, k [˜] ) =



e [−][i][(][K][+˜][k][)][·][X] f (X, k [˜] ) . (24)

X



e [i][(][K][+˜][k][)][·][X] f (K, k [˜] ) (23)

K



tij c [†] iσ [c] jσ [+ 1]

2

ij,σ





Uijniσnjσ′ . (18)
ij,σσ [′]



Here i and j are lattice site indices, the operators c [†] iσ
(ciσ) create (destroy) an electron with spin σ on site i,



To separate out the cluster degrees of freedom, the
hopping amplitude t and the self-energy Σ (defined from


7



quantum cluster approaches are good approximations to
systems with significant screening, where non-local correlations are expected to be short-ranged. Quantum cluster approaches are particularly powerful because the remaining self-energy term Σc(z) implicitly contained in
the propagator g(z) in Eq. (30) is restricted to the cluster degrees of freedom. Hence it can be calculated nonperturbatively in an effective cluster model as a functional Σc(z) = [ G [¯] (z)], where
F



G¯ (z) = [N][c]

N







G(k [˜], z) (31)
k˜



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-6-0.png)

Figure 3 Definition of the coordinates in real (left) and reciprocal (right) space illustrated for Nc = 4 site clusters. The
origin of a cluster is labeled by ˜x, the sites within a cluster by X. The reciprocal space to X is labeled by K, the
wave-vectors of the superlattice, i.e. within a cell by k [˜] .


the Green function via the Dyson equation G [−][1] = G [−] 0 [1]
Σ with the non-interacting Green function G0) is split [−]
into intra- and inter-cluster parts

t(˜xi − x˜j) = tcδx˜i,x˜j + δt(˜xi − x˜j ) (25)
Σ(˜xi − x˜j, z) = Σc(z)δx˜i,x˜j + δΣ(˜xi − x˜j, z) . (26)

All the quantities are Nc×Nc matrices in the cluster sites,
tc = t(˜x = 0) and Σc(z) = Σ(˜x = 0, z) are the intracluster hopping and self-energy, while δt(˜x) and δΣ(˜x, z)
are the corresponding inter-cluster quantities only finite
for ˜x ̸= 0.
With these definitions we write the Green function
using a locator expansion, an expansion in δt and δΣ
around the cluster limit. In matrix notation in the Nc
cluster sites it reads



is the k [˜] -averaged or coarse-grained G(k [˜], z), i.e. the
Green function restricted to the cluster. As discussed
in the next section this approximation is consistent with
neglecting inter-cluster momentum conservation, i.e. neglecting the phase factors e [i][k][˜][·][x][˜] on the vertices of the selfenergy diagrams.
Using the expression (30) for the lattice Green function
and the fact that g(z) does not depend on k [˜], the coarsegrained Green function G [¯] can be written as

G¯ (z) = [g [−][1] (z) − Γ(z)] [−][1], (32)

with a hybridization function Γ defined by



N



−1


















Γ(z) =


×










1 + [N][c]



δt(k [˜] )G(k [˜], z)
k˜





 [N][c]

N



δt(k [˜] )G(k [˜], z)δt(k [˜] )
k˜







 . (33)




     G(˜xi − x˜j, z) = g(z)δx˜ix˜j + g(z)




[δt(˜xi x˜l)
l 


+ δΣ(˜xi x˜l, z)]G(˜xl x˜j, z) (27)
            -            
where the Nc × Nc matrix

g(z) = [(z + µ) 1 tc Σc(z)] [−][1] (28)
            -             
is the Green function of the cluster decoupled from the remainder of the system (µ is the chemical potential). Since
translational invariance in the superlattice ˜x is preserved,
this expression may be simplified by Fourier transforming
the inter-cluster coordinates to give


G(k [˜], z) = g(z) + g(z)[δt(k [˜] ) + δΣ(k [˜], z)]G(k [˜], z) . (29)


The central approximation that unites all cluster formalisms is to truncate the self-energy to the cluster, by
neglecting δΣ to arrive at


G(k [˜], z) = g(z) + g(z)δt(k [˜] )G(k [˜], z)

= [g [−][1] (z) − δt(k [˜] )] [−][1] . (30)

As we discuss below, this approximation corresponds to
truncating the potential energy to the cluster while keeping all the contributions to the kinetic energy. Therefore



Its physical content is that of an effective amplitude for
fermionic hopping processes from the cluster into the host
and back again into the cluster. The denominator in
Eq. (33) is a correction that excludes the cluster from
the effective medium. Γ(z) thus plays an analogous role
to that of the internal magnetic field in mean-field approximations of spin systems. However, due to the itinerant character of the fermionic degrees of freedom, it is
a dynamical quantity.
Both the CPT and the CDMFT formalisms may be
defined at this point. A self-consistent set of equations
is formed from G as a functional of Σc using Eq. (30)
together with Eq. (28), and with an appropriate choice
of a cluster solver (see Sec. III), Σc as a functional of
G¯ . In the CDMFT approximation the hybridization Γ is
determined self-consistently with Eq. (33), i.e. from the
translational invariance of the super-lattice. The resulting self-consistency cycle is discussed in Sec. II.B.4. The
CPT formalism is obtained when Γ is neglected. The
Green function g(z) then becomes the Green function
of an isolated cluster and the CPT result for the lattice Green function is obtained immediately via Eq. (30)
without self-consistency. Thus the renormalization of the
cluster degrees of freedom due to the coupling to the host


described by Γ is neglected in the CPT but included in
the CDMFT formalism.
The DCA formalism may be motivated by the demand to restore translational invariance within the cluster. Since the inter-cluster hopping δt(k [˜] ) is finite for
sites on the surface of the cluster and zero for bulk sites,
only surface sites hybridize with the host. Hence translational invariance with respect to the cluster sites X is
violated. The cause of this violation can be seen by representing the hopping integral t(k [˜] ) as the intra-cluster
Fourier transform of the dispersion ǫK+˜k using Eq. (23),



8


Along the lines presented above, the DCA cluster selfenergy Σc(K, z) is calculated as a functional of the
coarse-grained Green function



G¯(K, z) = [N][c]

N





G(K + k [˜], z)
k˜



1
= (42)
g [−][1] (K, z) − Γ(K, z)

which defines the DCA hybridization function



Nc



1 + [N][c]




 
NNc k˜ [δt][2][(][K][ + ˜][k][)][G][(][K][ + ˜][k][, z][)]




 - . (43)
N [c] k˜ [δt][(][K][ + ˜][k][)][G][(][K][ + ˜][k][, z][)]




[t(k [˜] )]XiXj = [1]

Nc





e [i][(][K][+˜][k][)][·][(][X][i][−][X][j] [)] ǫK+˜k . (34)
K



Γ(K, z) =



The violation of translational symmetry is caused by the
phase factors e [i][k][˜][·][(][X][i][−][X][j] [)] associated with the superlattice
wave-vectors k [˜] . Thus translational symmetry can be restored by neglecting these phase-factors, or equivalently,
by multiplying [t(k [˜] )]XiXj with the k [˜] -dependent phase
e [−][i][k][˜][·][(][X][i][−][X][j] [)],




[tDCA(k [˜] )]XiXj = [t(k [˜] )]XiXj e [−][i][k][˜][·][(][X][i][−][X][j] [)]



1
=
Nc







e [i][K][·][(][X][i][−][X][j] [)] ǫK+˜k . (35)
K



Since tDCA is fully cyclic in the cluster sites, the DCA
intra- and inter-cluster hopping integrals can be written
as cluster Fourier transforms



1

[tc,DCA]XiXj =
Nc








  -  δtDCA(k [˜] )


with



1
XiXj [=] Nc







e [i][K][·][(][X][i][−][X][j] [)] ¯ǫK (36)

K


e [i][K][·][(][X][i][−][X][j] [)] δt(K + k [˜] )(37)

K



The self-consistent procedure to determine the DCA cluster self-energy Σc(K, z) is analogous to CDMFT and discussed in detail in Sec. II.B.4.
This locator expansion yields a very natural physical interpretation of cluster approximations. We note
that the potential energy may be written as Tr (ΣG)
(Fetter and Walecka, 1971), where the trace runs over
cluster sites, superlattice wave-vectors, frequency and
spin. As detailed above, the central approximation of cluster expansions is the neglect of the term
δΣ(k [˜], z)G(k [˜], z) in Eq. (29). Thus the approximation
δΣ(z) = 0 essentially neglects the inter-cluster corrections to the potential energy in all calculated lattice
quantities. On the other hand, the kinetic energy is identified as Tr (tG). Since its inter-cluster contribution is
not neglected, the kinetic and potential energy contributions are not treated on equal footing. Indeed this is the
essential difference between cluster mean-field approximations and finite size calculations. In the former the
potential energy of the lattice is truncated to that of the
cluster whereas the kinetic energy is not. This leads to a
self-consistent theory, generally (but not always) with a
single-particle coupling between the cluster and the host.
In the latter both the kinetic and potential energies of
the lattice are truncated to their cluster counterparts.
Therefore we might expect cluster methods to converge
more quickly as a function of cluster size, compared to
finite size techniques, for metallic systems with extended
states and significant screening. That this is indeed the
case was illustrated in the previous section for classical
spin systems (see Fig. 1).
For completeness we note that non-local interaction
terms, e.g. a nearest neighbor Coulomb repulsion Uij can
be treated in a similar manner by splitting it into intra(Uc) and inter-cluster (δU ) parts. A similar locator expansion to Eq. (30) or respectively Eq. (40) is then written down with respect to the inter-cluster part δU for
the corresponding susceptibility (in this case this would
be the charge susceptibility). As a result, an additional
coarse-grained interaction Uc acts within the cluster (see
also Sec. II.B), and the locator expansion in δU leads to
an additional self-consistency on the two-particle level.
For a cluster size of Nc = 1 this formalism corresponds
to the extended DMFT (Smith and Si, 2000). A first ap


ǫ¯K = [N][c]

N





ǫK+˜k (38)
k˜



δt(K + k [˜] ) = ǫK+˜k ¯ǫK . (39)
              
Since the DCA intra- and inter-cluster hopping integrals retain translational invariance within the cluster,
the DCA cluster self-energy Σc and hybridization function Γ are translationally invariant. The lattice Green
function, Eq. (30) hence becomes diagonal in cluster
Fourier space


G(K + k [˜], z) = g(K, z) + g(K, z)δt(K + k [˜] )G(K + k [˜], z)

1
= (40)
g [−][1] (K, z) − δt(K + k [˜] )

with the Green function decoupled from the host


g(K, z) = [z − ǫ¯K + µ − Σc(K, z)] [−][1] . (41)


plication of this extended cluster algorithm to the 2D t-J
model for Nc > 1 was discussed in Maier (2003).


B. Cluster approximation to the grand potential


In this section we provide a microscopic derivation of
the CPT, the CDMFT and the DCA formalisms based
on different cluster approximations to the diagrammatic
expression for the grand potential. The advantage of
this approach is that it allows us to employ almost all of
the diagrammatic technology which has been developed
in the past several decades to a new set of cluster formalisms. Furthermore we are able to asses the quality of
cluster approximations regarding their thermodynamic
properties. The most significant disadvantage is that the
formalism developed here only applies to systems which
are amenable to a diagrammatic expansion.
The following ideas will be illustrated on the extended
Hubbard model Eq. (18). We use the notation introduced
in Sec. II.A, Fig. 3, i.e. the cluster centers are denoted
by ˜x and sites within the cluster by X. The wave-vectors
k˜ and K are their respective conjugates.
Baym and Kadanoff (1961) (see also Baym, 1962)
showed that thermodynamically consistent approximations may be constructed by requiring that the singleparticle self-energy Σ fulfills

G [−] 0 [1]    - G [−][1] = Σ = [δ][Φ[] δG [G][]], (44)


i.e. is obtained as a functional derivative of the BaymKadanoff Φ-functional with respect to the Green function
G and that the approximation is self-consistent (via the
left hand identity). The Baym-Kadanoff generating functional Φ[G, U] is diagrammatically defined as a skeletal
graph sum over all distinct compact closed connected diagrams constructed from the Green function G and the
interaction U. Thus, the diagrammatic form of the approximate generating functional together with an appropriate set of Dyson and Bethe-Salpeter equations, completely defines the diagrammatic formalism.
As described in standard textbooks (Abrikosov et al.,
1963) the relation between the grand potential functional
Ωand the Φ-functional is expressed in terms of the linked
cluster expansion as


Ω[G, U] = kBT Φ[G, U] Tr ln( G) Tr(ΣG),
     - {      -      -      - }
(45)
where the trace indicates summation over cluster sites X,
superlattice wave-vectors k [˜], frequency and spin. With
the condition (44), the grand potential is stationary with
respect to G, i.e. δΩ/δG = 0. Such approximations
are thermodynamically consistent, i.e. observables calculated from the Green function G agree with those calculated as derivatives of the grand potential Ω. As shown
by Baym (1962) the requirement (44) together with momentum and energy conservation at the vertices also assures that the approximation preserves Ward identities,
i.e. satisfies conservation laws.



9


Prominent examples of conserving approximations include the Hartree-Fock theory and the fluctuation exchange approximation (Bickers et al., 1989). As exemplified by these theories, the typical approach to construct
a conserving approximation is to restrict the diagrams in
Φ to a certain sub-class, usually the lowest-order (in the
interaction U) diagrams. The resulting weak-coupling
approximations however usually fail for systems where
the interaction U is of the same order or larger than the
bandwidth.
Quantum cluster approaches go a different route: Instead of neglecting classes of diagrams in Φ, quantum
cluster approaches reduce the infinite number of degrees
of freedom over which Φ is evaluated to those of a finite size cluster. In contrast to perturbative approaches
however, all classes of diagrams are kept.


1. Cluster perturbation theory


The simplest way to reduce the degrees of freedom in
Φ[G] is to replace the full lattice Green function G(k [˜], z)
by the Green function g(z) = [(z + µ) 1 tc Σc(z)] [−][1]
                 -                  
of an isolated cluster of size Nc. Consequently, the selfenergy Σc = δΦ[g]/δg obtained from Φ is the self-energy
of an isolated finite size cluster. This however leads to a
theory which lacks self-consistency. Moreover one has to
make the ad-hoc assumption that the lattice self-energy
is identical to the one obtained from the cluster, Σc. The
left hand side of Eq. (44) then yields the form for the CPT
lattice Green function

G(k [˜], z) = [G [−] 0 [1][(˜][k][, z][))][ −] [Σ][c][(][z][)]][−][1][,] (46)

where all the quantities are Nc × Nc matrices in the cluster sites. Since the bare lattice Green function is given
by G0(k [˜], z) = [(z + µ) 1 t(k [˜] )] [−][1] and the hopping can
           be split into intra- and inter-cluster parts (see Eq. (25)),
t(k [˜] ) = tc + δt(k [˜] ), we obtain

G(k [˜], z) = [g [−][1] (z) − δt(k [˜] )] [−][1] (47)

with g [−][1] (z) = (z + µ) 1 tc Σc(z). This form was derived in Sec. II.A from the locator expansion Eq. (30) by − ignoring the hybridization Γ between cluster and host.
According to Eq. (46), the CPT can be viewed as the approximation that is obtained by replacing the self-energy
in the Dyson equation of the lattice Green function G by
the self-energy of an isolated cluster Σc. This idea was
first developed by Gros and Valenti (1994) and applied
to the 3-band Hubbard model. A different approach to
derive the CPT was taken by Pairault et al. (1998) (see
also Pairault et al., 2000; S´en´echal et al., 2002). They
showed that Eq. (47) is obtained as the leading order
term in a strong coupling expansion in the hopping δt
between sites on different clusters. This derivation of the
CPT provided a fundamental theoretical basis to assess
the nature of the approximation as well as to systematically improve the quality of the approach by including
higher order terms in the perturbative expansion.


The CPT becomes exact in the weak coupling limit
U/t = 0 and the strong-coupling limit t/U = 0 as well as
in the infinite cluster size limit Nc (S´en´echal et al.,
2002). The limit t/U = 0 is reproduced exactly since the →∞
CPT is the perturbative result in the hopping. In this
limit, all the sites in the lattice are decoupled, and the
system is solved exactly by the single-site Green function gc. In the opposite limit U/t = 0, the cluster selfenergy Σc in Eq. (46) vanishes and G(k [˜] ) = G0(k [˜] ) is
the exact solution. In the limit Nc, the cluster Green function gc becomes the exact Green func- →∞
tion of the full system. At finite t/U and cluster size
Nc = 1, the CPT recovers the Hubbard-I approximation (Hubbard, 1963) where the self-energy is approximated by the self-energy U [2] /4ω (at half-filling) of an
isolated atom (Gros and Valenti, 1994; S´en´echal et al.,
2000, 2002).
According to the derivation of the CPT, the cluster
Green function gc is to be calculated on a cluster with
open boundary conditions. Since the hopping tc between
sites inside the cluster is treated exactly whereas the
inter-cluster hopping δt between surface sites on different
clusters is treated perturbatively, translational invariance
for sites X in the cluster is violated while it is preserved
for sites ˜x in the superlattice. As a result, the cluster
wave-vector K is not a good quantum number and we
have as a generalization of the Fourier transform Eq. (24)
(we omit the frequency dependence for convenience)





e [−][i][k][·][X][i] G(Xi, Xj, k)e [i][k][′][·][X][j]
Xi,Xj



1
G(k, k [′] ) =
Nc






Q



× δ(k − k [′]       - Q) . (48)

where k and k [′] are wave-vectors in the full Brillouin zone
and Q is a wave-vector in the cluster reciprocal space.
Here we used the relation G(k [˜] ) = G(k) which follows
from Eq. (22) by replacing k [˜] by k = k [˜] + K. To restore
translational invariance in the full lattice Green function,
the CPT approximates G(k, k [′] ) by the Q = 0 contribution to obtain



10


hopping δt (Dahnken et al., 2002). However, as discussed by S´en´echal et al. (2002), periodic boundary conditions lead to less accurate spectra for the 1D Hubbard
model than open boundary conditions. This a-posteriori
argument for open boundary conditions is substantiated
by calculations within Potthoff’s self-energy functional
approach (see Sec. II.H) which show that the grand potential of the system is only stationary in the limit of
open boundary conditions (Potthoff et al., 2003).


2. Cellular dynamical mean-field theory


A superior approximation may be obtained if, instead
of the isolated cluster Green function g, the full lattice
Green function G restricted to cluster sites is used to
evaluate the functional Φ. This approximation can be
motivated microscopically by approximating the momentum conservation on internal vertices in the diagrams
defining Φ. Momentum conservation at each vertex is
described by the Laue function


 ∆= e [i][x][·][(][k][1][+][k][2][+][···][,][−][k] 1 [′] [−][k][′] 2 [−···][)] = Nδk1+k2+···,k′1 [+][k][′] 2 [+][···][,]

x

(50)
where k1, k2 (k [′] 1 [,][ k][′] 2 [) are the momenta entering (leav-]
ing) the vertex. M¨uller-Hartmann (1989b) showed that
the DMFT may be derived by completely ignoring momentum conservation at each internal vertex by setting
∆= 1. Then one may freely sum over all of the internal momentum labels, and the Green functions in
the diagrams are replaced by the local Green function
Gii = 1/N [�] k [G][(][k][).]

The CDMFT and DCA (see below) techniques may
also be defined by their respective approximations to the
Laue function. In the CDMFT the Laue function is approximated by


  ∆CDMF T = e [i][X][·][(][K][1][+˜][k][1][+][K][2][+˜][k][2][+][···−][K] 1 [′] [−][k][˜][′] 1 [−][K][′] 2 [−][k][˜][′] 2 [−···][)] .

X

(51)
Thus the CDMFT omits the phase factors e [i][k][˜][·][x][˜] resulting
from the position of the cluster in the original lattice,
but keeps the phase factors e [i][k][˜][·][X] . The latter are directly
responsible for the violation of translational invariance.
Consequently, all quantities in the CDMFT are functions
of two cluster momenta K1, K2 or two sites X1, X2
respectively.
If the CDMFT Laue function Eq. (51) is applied to
diagrams in Φ, each Green function leg is replaced by the
CDMFT coarse-grained Green function (the frequency
dependence is dropped for notational convenience)



GCP T (k) = [1]

Nc





e [−][i][k][·][(][X][i][−][X][j] [)] G(Xi, Xj, k), (49)
Xi,Xj



as the translational invariant propagator used to calculate spectra. With this approximation, the CPT provides
a very economical method to calculate the lattice Green
function of an infinite size (N →∞) Hubbard-like model
from the Green function (or equivalently self-energy) of
one can calculate single-particle quantities such as pho-an isolated cluster of finite size Nc ≪ N . From GCP T (k)
toemission spectra, kinetic and potential energies, double
occupancy, etc.
To reduce the numerical cost, it was suggested to use
periodic boundary conditions on the CPT cluster by
adding the appropriate hopping terms to the intra-cluster
hopping tc and subtracting them from the inter-cluster



G¯(X1, X2) = G(X1, X2; ˜x = 0) =

 1
N [2] e [i][(][K][1][+˜][k][1][)][·][X][1] G(K1, K2; k [˜]



e [i][(][K][1][+˜][k][1][)][·][X][1] G(K1, K2; k [˜] 1, k [˜] 2)e [−][i][(][K][2][+˜][k][2][)][·][X][2] =



K1,K2
k˜1,k˜2


NNc [2][2] - G(X1, X2, k [˜] 1, k [˜] 2), (52)

k˜1,k˜2



11


and Green function legs in Φ are replaced by the DCA
coarse grained Green function





G(K + k [˜], z), (59)
k˜



or in matrix notation for the cluster sites X1 and X2



G¯(K, z) = [N][c]

N



since Green functions can be freely summed over the
N/Nc wave-vectors k [˜] of the superlattice. Similarly, the
interactions are replaced by the DCA coarse grained interaction



G¯ (z) = [N][c]

N





G(k [˜], z), (53)
k˜



since G is diagonal in k [˜] 1, k [˜] 2 due to the translational invariance of the superlattice. Similarly each interaction
line is replaced by its coarse-grained result





U (K + k [˜] ) . (60)
k˜



As with the CDMFT, the effect of coarse-graining the
interaction is to reduce the effect of non-local interactions
to within the cluster. This collapse of the diagrams in the
Φ functional onto those of an effective cluster problem is
illustrated in Fig. 4 for a second order contribution.


Figure 4 A second-order term in the generating functional
Φ of the Hubbard model. The dashed line represents the
interaction U, and the solid line on the left hand side (right
hand side) the lattice (coarse-grained) single-particle Green
function G ( G [¯] ). When the DCA Laue function is used to
describe momentum conservation at the internal vertices, the
wave-vectors collapse onto those of the cluster and each lattice
Green function is replaced by its coarse-grained average.


The resulting compact graphs are functionals of the
coarse grained Green function G¯(K) and interaction
U¯ (K), and thus depend on the cluster momenta K only.
For example, when Nc = 1, only the local part of the
interaction survives the coarse graining. As with the
CDMFT, within the DCA it is important that both the
interaction and the Green function are coarse-grained
(Hettler et al., 2000). As a consequence of the collapse
of the Φ-diagrams, the DCA self-energy

Σc(K, z) = [δ][Φ[ ¯][G][(][K][, z][)][,][ ¯][U] []] (61)

δG [¯] (K, z)


only depends on the cluster momenta K.
To obtain the DCA estimate of the lattice grand potential, we substitute the DCA approximate generating
functional Φ[ G [¯] (K), U [¯] (K)] into Eq. (45). The grand potential is stationary with respect to G when


δΩ[ G [¯] (K), U [¯] (K)]

= Σc(K) Σ(k) = 0, (62)
δG(k)      


U¯ (K) = [N][c]

N



U¯ = [N][c]

N





U(k [˜] ) . (54)
k˜



The summations over the cluster sites X within each
diagram remain to be performed. As a consequence of
coarse-graining the propagators in Φ, the CDMFT selfenergy

Σc(z) = [δ][Φ[ ¯][G][(][z][)][,][ ¯][U][]] (55)

δG [¯] (z)


is restricted to cluster sites and consequently independent
of k [˜] . Note that by definition, G [¯] and U [¯] are truncated outside the cluster, i.e. if the interaction U is non-local, U [¯]
includes only interactions within, but not between clusters.
The CDMFT estimate of the lattice grand potential is
obtained by substituting the CDMFT approximate generating functional Φ[ G [¯], U [¯] ] into Eq. (45). From the condition that the grand potential is stationary with respect
to the lattice Green function, δΩ/δG = 0, one obtains
a relation between the lattice self-energy and the cluster
self-energy


Σ(K1, K2; k [˜] 1, k [˜] 2) =

  
e [−][i][(][K][1][+˜][k][1][)][·][X][1] Σc(X1, X2)e [i][(][K][2][+˜][k][2][)][·][X][2] . (56)
X1,X2


With Eq. (52) the left hand side of Eq. (44) then becomes
the coarse-graining relation



G¯ (z) = [N][c]

N





[G [−] 0 [1][(˜][k][, z][)][ −] [Σ][c][(][z][)]][−][1] (57)
k˜



with the bare Green function G0(z) = [(z +µ) 1 t(k [˜] )] [−][1] .

             

3. Dynamical cluster approximation


In the DCA the phase factors e [i][k][˜][·][X] are omitted too,
so that the DCA approximation to the Laue function
becomes


∆DCA = NcδK1+K2+···,K [′] 1 [+][K][′] 2 [+][···] (58)



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-10-0.png)
which means that Σ(k) = Σc(K) is the proper approximation for the lattice self-energy corresponding to
Φ[ G [¯] (K), U [¯] ]. The self-consistency condition on the left
hand side of Eq. (44) then becomes the coarse-graining
relation



G¯(K, z) = [N][c]

N





[G [−] 0 [1][(][K][ + ˜][k][)][ −] [Σ][c][(][K][, z][)]][−][1][ .] (63)
k˜



with the bare Green function G0(K + k [˜], z) = [z − ǫK+˜k +
µ] [−][1] .
Both the CDMFT and the DCA have well defined
limits. In the infinite size cluster limit Nc, the
→∞
CDMFT and DCA approximations to the Laue function
recover the exact Laue function, Φ is evaluated with the
full lattice Green function and interactions and thus the
exact result is recovered. When Nc = 1, both the Laue
functions reduce to ∆= 1, Φ is evaluated with the local
Green function and local contributions of the interactions, and the DMFT result is recovered.


4. Self-consistency scheme


The two equations (44) form a non-linear set of equations which have to be solved self-consistently to determine the cluster self-energy Σc[ G [¯] ] with the use of a suitable cluster solver. For cluster solvers that sum up all
diagrams of Σc, i.e. in contrast to a skeletal expansion of
Σc, an additional step is necessary in the self-consistent
cycle. In order to not overcount self-energy diagrams, Σc
is to be calculated as a functional of the corresponding
bare propagator to G [¯], the cluster excluded Green function


(z) = [ G [¯] [−][1] (z) + Σc(z)] [−][1] (64)
**G**

This equation [1] unambiguously defines the self-consistent
iteration procedure illustrated in Fig. 5:


1. The iteration is started by guessing an initial cluster self-energy Σc(z), usually zero or the result from
second order perturbation theory, to


2. Calculate the coarse grained quantities



12


4. The self-energy Σc(z) or respectively the cluster
Green function Gc(z) is calculated in the effective
cluster model (see Sec. II.D) by using any of the
quantum cluster solvers discussed in Sec. III.


5. For techniques that produce the cluster Green function Gc rather than the self-energy, the new estimate of the cluster self-energy is calculated as
Σc(z) = (z) Gc−1(z).
**G** [−][1]      
The iteration closes by re-calculating the coarse-grained
Green function G [¯] (z) in step (2) with the new estimate
of the cluster self-energy. This procedure is repeated until the cluster Green function Gc(z) equals the coarsegrained Green function G [¯] (z) to within the desired accuracy.


Figure 5 Sketch of the CDMFT and DCA embedded cluster
algorithms. The iteration starts with computing the coarse
grained Green function G [¯] using an initial guess for the cluster
self-energy Σc. The cluster excluded Green function is then
**G**
used to define the effective cluster problem which yields a new
estimate of Σc.


C. Discussion


In contrast to the DMFT, a unique setup for the embedded cluster theory does not exist. Depending on the
treatment of e.g. boundary conditions (see Sec. II.A
and Biroli and Kotliar, 2002) differences in the coupling
of the cluster to its environment arise (see comparison
in Sec. II.C.4 below). In fact, there exist infinitely
many realizations of embedded cluster theories for
any given model Hamiltonian (Biroli and Kotliar, 2002;
Okamoto et al., 2003; Potthoff, 2003b; Potthoff et al.,
2003), two of which we focus on in this review.
The fundamental approximation common to all approaches is that they try to go beyond conventional mean-field approximations and introduce non-local
physics by replacing the unsolvable lattice Hamiltonian
by some manageable finite portion – possibly with effective model parameters – and reintroduce the thermodynamic limit by a mean-field type treatment of the re


G¯ (z) = [N][c]

N








[G [−] 0 [1][(˜][k][, z][)][−][Σ][c][(][z][)]][−][1][,][ ¯][U][ =][ N][c]

N

k˜



N





U(k [˜] )
k˜



3. The effective cluster problem is then set up with
the cluster excluded Green function **G** (z) and U [¯] .


1 A unifying matrix notation is used. In the CDMFT, the
quantities are matrices in the Nc cluster sites and in particular [G [−] 0 [1][(˜][k][, z][)]][X] i [X] j [= (][z][ +][ µ][)][δ][X] i [X] j [−] [[][t][(˜][k][)]][X] i [X] j [.] For the
DCA, the matrices are diagonal in the cluster momenta K and

[G [−] 0 [1][(˜][k][, z][)]][KK][ =][ z][ +][ µ][ −] [ǫ] K+k [˜][.]



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-11-0.png)
maining system. Thus, the influence of truly long-ranged
correlations, i.e. those beyond the cluster size, is still not
incorporated, but short-ranged correlations and in particular the local dynamics with respect to the cluster can
ideally be treated exactly. That this can already lead
to substantial renormalizations has been demonstrated
in Sec. I.B and is also well-known from the DMFT.
The combination of short- to medium-ranged correlations
with mean-field treatment of long-ranged physics enables
the investigation of a system’s tendency to certain types
of order not accessible by conventional mean-field theory.
One can thus more clearly identify the possible existence
of long-ranged correlations which are normally hard to
establish in conventional finite-system calculations. On
the other hand, it is this mean-field likeness that practically disables a proof for the appearance of a phase
transition in the real model, even though the behavior
of transition temperatures etc. with cluster size can give
valuable hints about the system (see Sec. I.B).


1. Conservation and thermodynamic consistency


Both the DCA and CDMFT approximations are selfconsistent and are Φ-derivable since they satisfy Eq. (44).
Thus, they are thermodynamically consistent in the
Baym-Kadanoff sense. Observables calculated from the
lattice Green function G agree with those calculated as
derivatives of the lattice grand potential Ω. Since the
CPT is not self-consistent, it is not thermodynamically
consistent. However, none of these approaches is conserving in the Baym-Kadanoff sense since they all violate momentum conservation. Thus, each of these approaches is likely to violate some set of the Ward identities (Hettler et al., 2000).


2. Causality


One problem in any formation of an embedded cluster
theory is the manifestation of causality, i.e. a physical
Green function cannot have poles anywhere except on the
real axis. In particular, for the fundamental quantity of
the theory, the single particle Green function, this means
that the proper self-energy in momentum space has to
obey ℑmΣ(k, ω + i0 [+] ) < 0. Early attempts to formulate cluster extensions to DMFT (Schiller and Ingersent,
1995) ran into exactly this problem, which e.g. manifests itself in negative single-particle spectral functions.
Explicit proofs for causality can be given for the DCA
(Hettler et al., 2000) and the CDMFT (Kotliar et al.,
2001; see also Biroli et al., 2003). More precisely, any
embedded cluster theory consistent with the locator expansion (or a suitably defined cavity construction) obeys,
due to Eqs. (28) and (32), causality. A closer look at Eqs.
(28) and (32) also reveals how problems can arise. It is,
for example, tempting to replace the well defined cluster
quantity Σc(z) in (28) by some approximation to Σ(z),



13


i.e. the full self-energy. As has been discussed in some detail by Okamoto et al. (2003) (see also Sec. II.H.2), such
a procedure will in general introduce ringing phenomena
and lead to acausal behavior. How strongly such a violation of causality will eventually influence the interesting
low-energy results is quite likely a question of the model
parameters under investigation. In any case, it must be
taken as serious reason to at least doubt the quantitative
accuracy of such results.


3. Reducible and irreducible quantities


Fundamental quantities like the one-particle selfenergy Σ(z), or its many-particle counterparts entering
e.g. susceptibilities, carry the whole fragile information
about the many-body physics of a given model. In the
language of diagrammatic perturbation theory they are
built of so-called irreducible diagrams. Hence they are
also frequently called irreducible quantities; in contrast,
the single-particle Green function or a susceptibility is a
reducible quantity. It is an important aspect, that the
cluster theories discussed use approximants for these irreducible quantities only, i.e. the quantities obtained as
derivatives of the Baym-Kadanoff Φ functional. In fact,
in the formulation in Sec. II.B any attempt to replace
reducible quantities like the one-particle Green function
directly by approximants is at least dangerous.
To see this, consider the grand potential functional
Eq. (45). It is expressed as a sum over all closed
connected distinct graphs constructed from the Green
function G and interaction U. The subset of compact
graphs comprise the Baym-Kadanoff generating functional Φ[G, U] which is expressed as a skeletal graph
sum over all distinct compact closed connected graphs.
Compact diagrams have no internal parts representing
corrections to the Green function G.


Figure 6 Non-compact (left) and compact (right) non-local
corrections to the grand potential. Here the upper (lower)
circle is meant to represent a set of graphs which are closed
except for the external lines shown, and restricted to site n
(the origin).


In quantum cluster theories the graphs for Φ are
approximated by their cluster counterparts. As an
example, consider the limit of infinite dimensions,
used by Metzner and Vollhardt to derive the DMFT
(Metzner and Vollhardt, 1989). In this limit most closed



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-12-0.png)
connected graphs are local since the Green function falls
off quickly with distance r, G(r) ∼ D [−][r/][2] . In fact, only
a small set of graphs, corresponding to non-compact corrections, remain finite. To see this, consider the simplest
non-local corrections to non-compact and compact parts
of the grand potential of a Hubbard-like model, illustrated in Fig. 6. Here the upper (lower) circle is a set of
graphs composed of intra-site propagators restricted to
site n (the origin). Consider all such non-local corrections
on the shell of sites which are n mutually orthogonal unit
translations from the origin. In the limit of high dimensions, there are 2 [n] D!/((D − n)!n!) ∼O(D [n] ) such sites.
Since as D →∞, G(r) ∼ D [−][r/][2] (Metzner and Vollhardt,
1989), the legs on the compact correction contribute a
factor O(D [−][2][n] ) whereas those on the non-compact correction contribute O(D [−][n] ). Therefore the compact nonlocal correction falls as D [−][n] and vanishes as D →∞;
whereas, the non-compact correction remains of order
one, regardless of how far site n is from the origin. As
a result, the generating functional, which is composed of
only compact graphs, is a functional of the local Green
function and interaction in this limit


Φ[G, U] = Φ[Gii, Uii] + (1/D) . (65)
O

A similar analysis was done for the DCA cluster problem
by Aryanpour et al. (2002). They find that the corrections from sites outside the cluster associated with compact diagrams are quite small (i.e. high order in the linear
cluster size 1/Lc) justifying the approximation

Φ[G, U] ≈ Φ[ G [¯] (K), U [¯] (K)], (66)

while those associated with non-compact diagrams are
large and cannot be neglected. The same analysis may
be done for the CDMFT, simply by replacing the DCA
graphs by those for the CDMFT.
Thus, the essential approximation for the DMFT, the
DCA and the CDMFT is to approximate the lattice generating functional Φ by its cluster counterpart in the
estimate of the lattice grand potential, Eq. (45). Concommittantly the derivatives of Φ, i.e. the lattice selfenergy and vertex functions are approximated by their
respective cluster counterparts. This once more underlines why in embedded cluster theories it is necessary to
always work with the cluster irreducible quantities; they
are the only quantities compatible with the cluster and
any attempt to include more information by e.g. Fourier
transformation will lead to consistency problems, which
eventually express themselves as causality violation. Irreducible quantities are also those important to discuss the
convergence behavior of a cluster method with increasing
cluster size as discussed in the next section.


4. Comparison


Detailed comparisons of the DCA and CDMFT algorithms were presented in Maier and Jarrell (2002),



14


Maier et al. (2002b), Biroli and Kotliar (2002) and
Biroli et al. (2003). Both approximations share the underlying idea and general algorithm, and differ only in the
form used for the hopping matrix t (see Eq. (35)). The
purpose of this section is to convey the consequences of
this, at first sight, small difference on the effective cluster problem, convergence properties and the calculation
of the lattice self-energy.


a. Nature of effective cluster problem. For notational convenience, we use a 1D model with nearest neighbor hopping t only, set the on-site energy ǫo = 0 and denote the
cluster size by Lc. The generalization to higher dimension or longer-ranged hopping terms is straightforward.
The CDMFT uses the original form for the hopping
matrix t(k [˜] ) which is obtained e.g. as an inter-cluster
Fourier transform (see Eq. (22)) of t(˜x).Only entries between neighboring sites inside the cluster [t(k [˜] )]Xi,Xi±1 =
−t and between neighboring sites on the surface of the
cluster [t(k [˜] )]Xi,Xi±(Lc−1) = −te [∓][i][kL][˜] [c] are finite. The former entries form the intra-cluster hopping matrix tc =
Nc/N [�] k˜ [t][(˜][k][) while the latter entries form the inter-]
cluster hopping matrix δt(k [˜] ) = t(k [˜] ) tc. Both ampli                tudes are given by the original hopping t. For the effective cluster problem this translates to the fact that only
sites on the surface of the cluster couple to the effective
medium, while sites inside the cluster only couple to their
neighboring sites in the cluster. Hence the cluster problem has open boundary conditions and translational invariance is violated within the cluster. The lattice Green
function G(k [˜] ) (see Eq. (30)) is a matrix in the cluster
sites and cannot be diagonalized by going over to cluster
K-space. Therefore the coarse-graining step Eq. (31) is
done in real space.
The DCA restores translational invariance by setting

[tDCA(k [˜] )]XiXj = [t(k [˜] )]Xi Xj e [−][i][k][˜][·][(][X][i][−][X][j] [)] (see Eq. (35)).
As a consequence, its matrix elements become identical and are given by −te [∓][i][k][˜] between sites Xj = Xi ∓ 1
and Xj = Xi ± (Lc − 1). Hence the DCA hopping matrix tDCA(k [˜] ) is fully cyclic with respect to the cluster
sites and the lattice Green function G(k [˜] ) is diagonalized by going over to cluster K-space. The DCA intracluster hopping matrix tc,DCA = Nc/N [�] k˜ [t] DCA [(˜][k][) is]
also cyclic with finite matrix-elements



between sites Xj = Xi ± 1 and Xj = Xi ± (Lc − 1) and
the DCA cluster problem therefore has periodic boundary conditions. At finite cluster size Lc, the intra-cluster
hopping is reduced by the factor 1/6(π/Lc) [2] + ((π/Lc) [4] )
O
compared to its lattice counterpart t. In the infinite cluster size limit it becomes t. This reduction in the intracluster coupling is compensated by the inter-cluster hop



[tc,DCA]Xi,Xj = t [L][c]
       - π



(67)
Lc




[c]

π [sin][ π] L


ping which is of long-ranged nature,




[x][ ∓] [1)][π/L][c][]]

(˜x 1)π/Lc - [sin(] π/L [π/L] c [c][)]
∓




[δtDCA(˜x)]XiXj = t[ [sin[(˜][x][ ∓] [1)][π/L][c][]]
        - (˜x 1)π/Lc



δx,˜ 0]
π/Lc



15


since each of the Nc terms contributes a term of the order
O(1/L [2] c [).]
It can further be shown that Γ acts as the small parameter in these theories: The approximation performed
by the DCA and the CDMFT is to replace the lattice
Green function G by its coarse-grained quantity G [¯] in diagrams for the generating functional Φ (see Sec. II.B).
Both Green functions differ by the inter-cluster hopping δt(k [˜] ), the self-energy and the hybridization function Γ. Since the diagrams in Φ are summed over k [˜],
the terms having the same order as δt(k [˜] ) vanish since
Nc/N [�] k˜ [δ][t][(˜][k][) = 0. If we assume that the self-energy]
has corrections of the same or higher order in 1/Lc as
Γ, the convergence of Φ is entirely determined by Γ.
With the scaling relations (70) and (71) we find for the
CDMFT that ΦCDMF T Φ + (1/Lc) while the DCA
≈ O
it converges withconverges like ΦDCA Lc ≈ as the corresponding Φ confirmingΦ + O(1/L [2] c [). Since][ Σ][ =][ δ][Φ][/δ][G][,]
the assumption. The generating functional Φ and hence
the grand potential thus converges faster in the DCA
than in the CDMFT with increasing cluster size.


c. Numerical comparison. The scaling behavior Eqs. (70)
and (71) of the CDMFT and DCA average hybridization strengths was verified numerically in the 1D FKM
in Maier and Jarrell (2002) (see also Maier et al., 2002b).
Here we review the effects of the different scaling behaviors of the average hybridization on the phase transition
in this model. The Hamiltonian of the FKM is discussed
in Sec. IV.B, Eq. (182). It can be considered as a simplified Hubbard model with only one spin-species being
allowed to hop. However it still shows a complex phase
diagram including a Mott gap for large U at half filling, an Ising-like charge ordering with the corresponding
transition temperature Tc being zero in 1D, and phase
separation in all dimensions. Since the 1D FKM is in the
1D Ising universality class we expect similar scaling behavior as observed in the results for the 1D Ising model
in Sec. I.B. In particular, we expect finite transition temperatures within both cluster approximations due to their
residual mean-field character. The CDMFT and DCA effective cluster models were solved with a QMC approach
described in Hettler et al. (2000).
The DCA transition temperature Tc was determined
from the divergence of the lattice charge susceptibility
χ(Q) calculated from the particle-hole correlation function as detailed in Sec. II.F. In the CDMFT formalism the calculation of lattice susceptibilities is difficult if
not impossible due to the lack of translational invariance.
Here Tc is determined from the calculation of the charge
order parameter m as detailed in Sec. II.E. For the DCA
both techniques are illustrated in the inset to Fig. 7.
As for the 1D Ising model (see Fig. 2 in Sec. I.B), the
DCA result for Tc scales to zero almost linearly in 1/Nc
for large Nc. Moreover, Tc obtained from DCA is smaller
and thus closer to the exact result than the Tc obtained
from CDMFT. The CDMFT does not show any scaling



(68)
between sitesimportant to note that Xj = Xi ∓ δt1 andDCA couples Xj = X alli ± the sites in the (Lc − 1). It is
cluster to sites in the effective medium. It vanishes for
x˜ = 0 and decreases as 1/x˜ with increasing ˜x. We also
notice that


δtDCA 1/Lc (69)
∼

for large linear cluster sizes Lc and emphasize that this
result holds generally in any dimension D.
The restoration of translational invariance in the DCA
is achieved by mapping the lattice onto a cluster with
periodic boundary conditions with reduced hopping integrals tc,DCA and coupling every site in the cluster to
a neighboring site in the effective medium through longranged hopping integrals δtDCA(˜x). The sum of all finite intra- and inter-cluster couplings for a given site is
again given by the original value t. Similar conclusions
about the nature of the effective CDMFT and DCA cluster problems were reached in a study of the large U limit
of the Falicov-Kimball model (FKM, see Eq. (182)), i.e.
the classical Ising model (Biroli et al., 2003).
We stress that clusters with linear size Lc = 2 are
special. Here both terms in the intra-cluster hopping Eq. (67) give a contribution to the same matrixelement. Hence the nearest-neighbor hopping is given by
2t (Lc/π) sin (π/Lc), i.e. with the prefactor 2t instead

- of −t for larger clusters. This reflects the fact that every
site sees its nearest neighbor twice due to the periodic
boundary conditions. Non-local fluctuations are thus enhanced in clusters with linear size Lc = 2 as seen e.g. in
an over-proportional suppression of transition temperatures (see Secs. IV.B and IV.D.2).



δtDCA 1/Lc (69)
∼



b. Convergence with cluster size. The differences in
boundary conditions translate directly to different
asymptotic behaviors for large cluster sizes Nc. In leading order the hybridization with the mean-field, Γ vanishes like δt [2] as the cluster size increases (see Eqs. (33)
and (43)). In the CDMFT the magnitude of δt is of order one for the sites on the surface of the cluster and zero
otherwise. The average hybridization per cluster site in
the CDMFT thus scales like



¯ΓCDMF T = [1]



), (70)
Lc




[1] Tr [ΓCDMF T ] ( [1]

Nc ∼O L



where the trace runs over cluster sites and frequency.
This behavior is evident since only the 2D(Lc [D][−][1] ) sites
on the surface contribute to the sum and Nc = L [D] c [. In]
the DCA, δt = (1/Lc) (see Eq. (69)). The average
O
hybridization of the DCA cluster to the effective medium
hence scales faster to zero as




[1] Tr [ΓDCA] ( [1]

Nc ∼O L



¯ΓDCA = [1]



) (71)
L [2] c


![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-15-0.png)



0.03


0.02


0.01













0





1/Nc



Figure 7 Transition temperature versus inverse cluster size
calculated with DCA/QMC (circles) and CDMFT/QMC
(squares) when U = W = 4t = 1. Inset: DCA order parameter m(T ) and inverse charge susceptibility χ(Q) [−][1] versus
temperature. Taken from Maier et al. (2002b).


behavior and in fact seems to tend to a finite value for Tc
as Nc . As explained above, this striking difference
can be attributed to the different boundary conditions. →∞
The open boundary conditions of the CDMFT cluster
result in a large surface contribution so that Γ [¯] CDMF T >
¯ΓDCA. This engenders pronounced mean-field behavior
that stabilizes the finite temperature transition for the
cluster sizes treated in Fig. 7. For larger cluster sizes the
bulk contribution to the CDMFT grand potential should
dominate so that Tc is expected to fall to zero.
Complementary results are found in simulations of
finite size systems. In general, systems with open
boundary conditions are expected to have a surface
contribution in the grand potential of order (1/Lc)
O
(Fisher and Barber, 1972). This term is absent in systems with periodic boundary conditions. As a result,
simulations of finite size systems with periodic boundary
conditions converge much more quickly than those with
open boundary conditions (Landau, 1976).
The DCA converges faster than the CDMFT for critical properties as well as extended cluster quantities due
to the different boundary conditions and the coupling
to the mean-field. As detailed above, each site in the
DCA cluster experiences the same coupling to the effective medium, while in the CDMFT only the sites on the
boundary of the cluster couple to the mean-field host.
Provided that the system is far from a transition, the
sites in the center of the CDMFT cluster couple to the
mean-field only through propagators which fall exponentially with distance. Local results such as the singleparticle density of states thus converge more quickly
in the CDMFT when measured on a central site (see
Maier et al., 2002b).


d. Calculation of the lattice self-energy. Another significant difference between the two cluster techniques ap


16


pears in the calculation on the lattice self-energy. The
DCA approximates the lattice self-energy by a constant
within a DCA cell in momentum space, Σ(K + k [˜], z) =
Σc(K, z). Therefore the self-energy is a step function
in k-space. In order to obtain smooth non-local quantities such as the Fermi surface or the band structure,
an interpolated Σ(k, z) may be used. Bilinear interpolation in 2D is guaranteed to preserve the sign of the
function however leads to kinks in Σ(k, z). Yielding the
smoothest possible interpolation of Σ(K, z), the use of an
Akima spline which does not overshoot is consistent with
the DCA assumption that the self-energy is a smoothly
varying function in k-space. However it is important to
note that this interpolated self-energy should not be used
in the self-consistent loop as this can lead to violations
of causality as discussed above.
In the CDMFT, the lattice self-energy is given by the
Fourier transform of the cluster self-energy (see Eq. (56))





e [−][i][k][·][X][i] Σc(Xi, Xj, z)e [i][k][′][·][X][j]
Xi,Xj



1
Σ(k, k [′], z) =
Nc






Q



× δ(k − k [′]       - Q) . (72)

Since the CDMFT cluster violates translational invariance, the lattice self-energy depends on two momenta k
and k [′] which can differ by a wave-vector Q of the cluster reciprocal space. To restore translational invariance,
the CDMFT approximates the lattice self-energy by the
Q = 0 contribution to give (Kotliar et al., 2001)



Σ(k, z) = [1]

Nc





e [−][i][k][·][(][X][i][−][X][j] [)] Σc(Xi, Xj, z) . (73)
Xi,Xj



In real space, the lattice self-energy



Σ(xi, xj, z) = [1]

Nc





Σc(Xi, Xj)δXi−Xj,xi−xj (74)
Xi,Xj



is thus obtained by averaging over those cluster selfenergy elements Σ(Xi, Xj) where the distance Xi
Xj equals the distance xi − xj. As explained in −
Biroli and Kotliar (2002), the factor 1/Nc leads to an
underestimation of non-local self-energy contributions at
small cluster sizes, since the number of contributions
for fixed xi − xj > 0 in the sum Eq. (74) is always
smaller than Nc. As a possible solution to this problem,
Biroli and Kotliar (2002) suggested to replace the form
(74) for the lattice self-energy by a weighted sum which
preserves causality. One could e.g. weight the terms in
the sum by their number instead of Nc to achieve better
results.
It is important to note that as in the DCA, the lattice self-energy Eq. (73) or (74) does not enter the selfconsistent loop. Biroli et al. (2003) however realized that
a translational invariant formulation of the CDMFT algorithm can be obtained by replacing the cluster self-energy
Σc(z) by the translationally invariant lattice self-energy
Σ(k [˜] ), Eq. (73) in the coarse-graining step Eq. (53). Despite the dependence on k [˜], this form of Σ(k [˜] ) can be
shown to preserve causality (Biroli et al., 2003).


D. Effective cluster model


Quantum cluster approaches reduce the complexity of
the lattice problem with infinite degrees of freedom to
a (numerically) solvable system with Nc degrees of freedom. As detailed in Sec. II.B this is achieved through
the approximation of Φ[G, U], the exact Baym-Kadanoff
functional of the exact Green function G and interaction
U, by a spatially localized quantity Φ[ G [¯], U [¯] ] which is a
functional by the corresponding (coarse-grained) quantities restricted to the cluster sites, G [¯] = Nc/N [�] k˜ [G][(˜][k][)]
and U [¯] = Nc/N [�] k˜ [U][(˜][k][).]
Φ[ G [¯], U [¯] ] may be calculated non-perturbatively as the
solution of a quantum cluster model


Hc = Hc,0 + Hc,I . (75)

Hc consists of a non-interacting term Hc,0 describing the
bare cluster degrees of freedom and their coupling to a
host. The interacting term Hc,I is related to the corresponding term in the original lattice model through the
coarse-grained interaction U [¯] . This ensures that the functional dependencies of the cluster functional Φc and its
lattice counterpart Φ are identical.
The non-interacting term Hc,0 is fixed by the requirement that the Green function Gc of the cluster model
equals the coarse-grained Green function G [¯] of the original model


Gc G = [ Σc] [−][1], (76)
≡ [¯] **G** [−][1]        
and hence is specified by the cluster-excluded Green function **G** (see Eq. (64)).
For Green function or respectively action based cluster
solvers, like e.g. perturbation theory or QMC, Hc,0 can
hence be encoded in the cluster-excluded Green function
**G** . The corresponding cluster action Sc for the fermionic
cluster degrees of freedom represented by the Grassman
variables γ, γ [∗] reads in imaginary time and cluster real
space



17


Hc,0, it is convenient to use Eq. (32) for the CDMFT or
respectively (42) for the DCA together with Eq. (76) to
represent the cluster excluded Green function **G** . In the
CDMFT, we have with Eq. (28)


(z) = [(z + µ) 1 tc Γ(z)] [−][1], (78)
**G**     -     
and the matrix-elements of the intra-cluster hopping tc
are given by the hopping amplitudes of the original lattice, tij as detailed in Sec. II.C.4. The non-interacting
problem is thus split into two parts, cluster degrees of
freedom with hopping integrals tij and their coupling to
a dynamic host described by the hybridization function
Γ(z). The CDMFT cluster model can hence be written
as (see also Bolech et al., 2003)



ij (z) = [(z + µ) 1 tc Γc(z)] [−] ij [1] (80)
G - - 



    Hc = Hc,0 + Hc,I =



ij,σ(tij − µδij)c [†] iσ [c] jσ




 +



λijk˜ [a [†] ik [˜] σ [a][j][k][˜][σ] [+][ h.c.][]]
ij,k [˜],σ


[Vij (k [˜] )c [†] iσ [a] jk˜σ [+][ h.c.][]]
ij,k [˜],σ




 +




 +


ij,σσ [′]



U¯ij

iσ [c][†] jσ [′] [c] jσ [′] [c] iσ [.] (79)
2 [c][†]



The first part describes the isolated cluster degrees of
freedom with fermionic creation (destruction) operators
c [†] iσ [(][c] iσ [). The second term simulates the host degrees]
of freedom as a non-interacting conduction band with
the help of auxiliary operators a [†]
ik [˜] σ [(][a] ik [˜] σ [) and energy]
levels λijk˜. The coupling between the cluster states and
the bath with an amplitude Vij (k [˜] ) is described by the
third term and the interacting term is given by the last
term. The sums over k [˜] run over the N/Nc wave-vectors
of the superlattice. Integrating out the auxiliary degrees
of freedom yields an action of the form (77) with



�β

Sc[γ, γ [∗] ] = dτ
     
0



dτ [′][ �]
0 ij,σ



�β



γiσ [∗] [(][τ] [)][G][ij,σ] [(][τ][ −] [τ][ ′][)][γ][jσ][(][τ][ ′][)]
ij,σ




  Γc,ij(z) =



Vil [∗][(˜][k][)[][z] 1   - λ(k [˜] )] [−] lm [1][V][mj] [(˜][k][)][ .] (81)
lm,k [˜]



�β



Self-consistency then requires that the auxiliary parameters λijk and Vij(k [˜] ) are chosen in a way such that the
cluster hybridization function Γc(z) is identical to its lattice counterpart Γ(z) defined in Eq. (78). It is important
to note that, while the isolated cluster parameter tc can
be deduced directly from the non-interacting part of the
lattice system, the energy levels λk and coupling constants Vij (k) of the auxiliary particles are not known
a-priori, but determined by the self-consistency condition Γc = Γ. Since Γij is only finite on the surface of
the cluster (see discussion in Sec. II.C.4), the coupling
Vij (k [˜] ) between the cluster and the host is only finite for
sites i on the surface of the cluster which effectively reduces the number of baths. This was numerically verified



+




 dτ
0 ij,σσ [′]



ij,σσ [′]



U¯ij

iσ [(][τ] [)][γ] jσ [∗] [′] [(][τ] [)][γ] jσ [′] [(][τ] [)][γ] iσ [(][τ] [)][,] (77)
2 [γ][∗]



where we used the short hand notation i, j for the cluster
sites Xi, Xj . Note that for the CDMFT the quantities
Gij and U [¯] ij are given by Eqs. (64) and (54) respectively,
while for the DCA they are given by the cluster Fourier
transforms of (K) = [ G [¯][−][1] (K, z) + Σc(K, z)] [−][1] and reG
spectively of U [¯] (K) (see Eq. (60)).
For Hamiltonian-based techniques, like e.g. the noncrossing approximation, exact diagonalization or numerical renormalization group, the need for an explicit formulation of Hc,0 is inevitable. To setup the bare part


in CDMFT exact diagonalization studies by Bolech et al.
(2003).
For the DCA we have with Eqs. (41) and (42)


G(K, z) = [z − ǫ¯K + µ − Γ(K, z)] [−][1], (82)

and hence the DCA effective cluster model is best represented in cluster K-space as



Hc = H�c,0 + Hc,I



λka [†] kσ [a] kσ
k,σ




 =


K,σ

 +




- 
K,σ(¯ǫK − µ)c [†] Kσ [c] Kσ [+] k,σ




[VK(k [˜] )c [†] Kσ [a] K+k [˜] σ [+][ h.c.][]]
K,k [˜],σ




 +


K,K [′]
Q






σσ [′]



U¯ (Q)

c [†] K+Qσ [c] K [†] [′] −Qσ [′] [c] K [′] σ [′] [c] Kσ [.][ (83)]
2Nc



The operators c [†] Kσ [(][c] Kσ [) create (destroy) an electron]
with momentum K and spin σ on the cluster. U [¯] (Q) is
the Coulomb repulsion between electrons on the cluster
defined in Eq. (60) and the sum over k [˜] in the coupling
term again is restricted to the N/Nc wave-vectors of the
superlattice. Analogous to the CDMFT case it is easy to
see that the DCA cluster model yields an action of the
form (77) (in cluster Fourier space) with a G of the form
(82) and the cluster hybridization function



|VK(k [˜] )| [2] . (84)

z λK+˜k
 


18


ordered phases can be identified by the computation of
response functions. However, to explore the nature as
well as possible coexistence of symmetry-broken states,
generalizations of the cluster algorithms that explicitly
account for the possibility of symmetry-breaking on the
single-particle level are necessary.
The applicability and modifications required to treat
symmetry broken phases depend on the cluster approach.
The CPT formalism is not amenable to the description
of ordered phases because its self-energy is that of a
finite isolated cluster in which spontaneous symmetry
breaking cannot occur. However, Dahnken et al. developed a variational extension of the CPT (Dahnken et al.,
2003) based on the self-energy functional approach by
Potthoff (2003b) which yields a self-consistent scheme to
study ordered phases (for details see Sec. II.H). The
CDMFT formalism can describe ordered phases which
are identifiable by a broken translational symmetry (such
as antiferromagnetism) by construction, since the translational symmetry of the CDMFT cluster is already
broken (see Biroli et al., 2003; Maier and Jarrell, 2002;
Maier et al., 2002b). Hence translational invariant solutions are often found to be unstable against the ordered
one (Biroli et al., 2003). The DCA formalism is translationally invariant by construction, and therefore generalizations of the algorithm are necessary to treat ordered phases. To keep this section concise, we exemplify
the necessary generalizations of the DCA formalism to
a selection of relevant types of symmetry-broken phases
along with the mapping onto the corresponding cluster
models. The adoption of the presented concepts to the
CDMFT approach is straightforward.
Once the equations are generalized to account for symmetry breaking, the requisite algorithmic changes are relatively simple. A finite conjugate external field is used to
initialize the calculation and break the symmetry. The
field is then switched off after a few iterations and the
system relaxes to its equilibrium state in the absence of
external fields. On the other hand, if the field remains
small and finite, the dependence of the order parameter
on the field can be determined and used as an alternate
way to calculate the susceptibility (by extrapolation to
zero field). This approach is especially useful for cluster solvers such as the non-crossing approximation or the
fluctuation-exchange approximation where the computation of two-particle correlation functions is numerically
too expensive.


1. Uniform magnetic field – Ferromagnetism


We first consider the formalism necessary to treat ferromagnetism. A finite homogeneous external magnetic
field h is introduced which acts on the spin σ of the
fermions according to the Zeeman term


    
      - h σc [†] iσ [c] iσ [.] (85)

i,σ



Γc(K, z) = [N][c]

N






k˜



The auxiliary parameters of the DCA cluster model are
then determined by the condition Γc(K) = Γ(K).
For Nc = 1 both the CDMFT and the DCA cluster
models reduce to the single-impurity Anderson model.
If self-consistency is also established on the two-particle
level (see discussion at the end of Sec. II.A) via a susceptibility, an additional coupling to a bosonic field representing the corresponding fluctuations has to be considered in the cluster model (for details see Maier, 2003).
For Nc = 1 the cluster model then reduces to the effective impurity model used in the EDMFT approach
(Smith and Si, 2000).
As detailed in Sec. II.A, the CPT formalism sets the
hybridization function Γ to zero, i.e considers an isolated
cluster without the coupling to a host. Thus the CPT
cluster model is identical to the original lattice model
restricted to cluster sites, i.e. given by the first and last
terms of the CDMFT cluster model Eq. (79).


E. Phases with broken symmetry


For simplicity, in the preceding sections the selfconsistent equations of quantum cluster theories have
been derived assuming the absence of symmetrybreaking. In Sec. II.F we review how instabilities to


The effect of h on the motion of the spatial degree of
freedom of the electrons, i.e. the diamagnetic term, is
neglected for simplicity [2] .
In the presence of finite h or a uniform magnetization,
the single-particle Green functions for up- and downelectrons are not equivalent. To account for this SU (2)
symmetry-breaking, the spin-index of the Green function
Gσ, self-energy Σσ and effective medium Gσ (and hence
Γσ) in the derivation of the DCA-equations has to be retained. For a finite uniform magnetic field h the DCA
lattice Green function reads



1
Gσ(k, z) = (86)
z − ǫK+˜k + µ + hσ − Σc,σ(K, z)



and the coarse grained and corresponding clusterexcluded Green function



G¯σ(K, z) = [N][c]

N







Gσ(K + k [˜], z), (87)
k˜



19


phases with coexisting superconducting and antiferromagnetic order. The extension to an integrated formalism is straightforward and has been discussed in
Lichtenstein and Katsnelson (2000).
We consider superconducting phases where the electrons are paired in spin singlet or triplet states with
Sz = 0 indicated by finite values of the order parameter ∆k := ⟨ck↑c−k↓⟩ for some k. In addition to the
normal Green function G(k, τ ) it is therefore necessary
to introduce the anomalous Green function F (k, τ ) =
Tτ ck↑(τ )c−k↓ . The spatial and temporal symmetry
−⟨ ⟩
of the pairing state can then be inferred from the symmetries of F . Since F describes the pairing of fermions,
it necessarily is antisymmetric under the exchange of two
particles. The spatial symmetry of the pairing state
is determined by the k-dependence of the anomalous
Green function F (k, τ ). If we assume conventional evenfrequency pairing F (k, −τ ) = F (k, τ ), in the case of
spin-singlet pairing, F has to be symmetric in k, i.e.
F (−k, τ ) = F (k, τ ) as is the case for even parity order parameters such as e.g. s-wave and d-wave. In the
case of spin-triplet pairing F is antisymmetric in k. i.e.
F (−k, τ ) = −F (k, τ ) as e.g. in a p-wave state.
The allowed symmetry of the pairing state is restricted by the cluster geometry. It depends upon the kdependence of the dispersion ǫk and the K-dependence of
the cluster self-energy Σ(K, τ ). When Nc = 1, Σ is local
and the k-dependence of F (k, τ ) is entirely through ǫk.
Hence only pairing states with the symmetry of the lattice such as s-wave and extended s-wave can be described
by this formalism (Jarrell, 1992; Jarrell and Pruschke,
1993). Larger cluster sizes are necessary to describe
order-parameters with a symmetry less than the lattice
symmetry, e.g. simulations with Nc = 4 are necessary
to describe phases with a dx2−y2 -wave order parameter
which transforms according to cos kx cos ky.
By utilizing the concept of Nambu-spinors −

Ψ [†] k [:= (][c] k [†] ↑ [, c] −k↓ [) ; Ψ][k][ = (Ψ][†] k [)][†] (92)


the self-consistent equations can be written in a more
compact form, since the corresponding Green function
matrix in Nambu space



Gσ [−][1][(][K][, z][) =][ G] σ [−][1][(][K][, z][) + Σ][c,σ][(][K][, z][)] (88)



become spin-dependent.
The action of the effective cluster model is identical
to the action in the paramagnetic state, Eq. (77), but
the spin indices have to be explicitly retained. It then
describes electrons in an external magnetic field h coupled to a spin-dependent host and self-consistency is established by equating the Green function of the cluster
model with the coarse-grained Green function (87).
In analogy, for Hamiltonian based cluster solvers, an
additional term




 
- h



σc [†] Kσ [c] Kσ (89)
K,σ



is added to the cluster Hamiltonian, Eq. (83), in the presence of a finite external magnetic field h. The coarsegrained Green function G [¯], Eq. (86), is then used to calculate the magnetization m := 1/N [�] iσ [σ][⟨][n][iσ][⟩] [according]

to



m = [1]

Nc







σG [¯] σ(K, τ = 0 [−] ) (90)

K,σ



and after analytical continuation







dωf (ω) mG [¯] σ(K, ω + iδ) . (91)
ℑ
−∞



�+∞



1

m =
  - π [1] Nc







σ

Kσ




        G(k, z) F (k, z)
G(k, z) := ⟨⟨Ψk; Ψ [†] k [⟩⟩][z][ =] F [∗] (k, z [∗] ) G [∗] ( k, z [∗] )
            -             -             


(93)
contains information about both the normal and anomalous Green functions. In the presence of an external pairing field η(k) = η [′] (k) + iη [′′] (k) which couples to c−k↓ck↑,
the non-interacting part of the Hubbard Hamiltonian can
be written as H0 = [�] k [Ψ] k [†] [[][ǫ][k][σ][3][ −] [η][′][(][k][)][σ][1][ +][ η][′′][(][k][)][σ][2][]Ψ] k
so the the DCA lattice Green function in the superconducting state becomes


G(k, z) = [zσo (ǫk µ)σ3
         -         η [′] (k)σ1 η [′′] (k)σ2 Σc(K, z)] [−][1], (94)

     -     -     
where k = K + k [˜] and σi are the Pauli-spin matrices.
The diagonal parts of the Nambu-matrix Σc(K, z) de


2. Superconductivity


In this and the next section we generalize the DCA
formalism to treat phases with superconducting and antiferromagnetic order, respectively. For better readability, we refrain from discussing the description of


2 In 2D systems the magnetic field can be applied parallel to the
plane to avoid orbital effects.



G(k, z) = [zσo (ǫk µ)σ3
       -       η [′] (k)σ1 η [′′] (k)σ2 Σc(K, z)] [−][1], (94)

    -    -    

scribe quasiparticle renormalizations and the off-diagonal
parts contain information about the K- and frequency dependence of the pairing state. Again, the coarse-grained
Green function



G¯ (K, z) = [N][c]

N







G(K + k, z)
k˜



20


3. Antiferromagnetic order


In this section we derive the DCA cluster formalism for
antiferromagnetism on a bipartite lattice. This formalism
is appropriate when Nc > 1. A formalism suitable for the
case when Nc = 1 is discussed in detail in Georges et al.
(1996) in the context of DMFT.
The antiferromagnetically ordered state is characterized by a spatial variation of the magnetization according
to


m(x) = me [i][Q][·][x], (101)


where x denotes the sites in the lattice and Q is the
antiferromagnetic wave-vector (Q = (π, π) in 2D). Hence
bipartite lattices can be divided into two inequivalent
sublattices according to

     1 : x A sub-lattice
e [i][Q][·][x] = ∈ (102)
1 : x B sub-lattice [.]

     - ∈

The magnetic ordering thus reduces the translational
symmetry of the original lattice. The volume of the magnetic unit cell is doubled compared to the structural unit
cell. Accordingly, the volume of the first Brillouin zone
in the antiferromagnetic state is reduced to half the original volume and Q = (π, π) becomes a reciprocal lattice
vector. Hence in neutron scattering experiments Bragg
peaks are found at the wave-vector Q corresponding to
a period of two lattice spacings.
As a consequence of the translational symmetry breaking, the correlation function

Gσ(k, k + Q; τ ) = −⟨Tτ ckσ(τ )c [†] k+Qσ [⟩] (103)

becomes finite. Along the lines of the formalism for the
superconducting state it is thus convenient to introduce
spinors


Ψ [†] kσ [= (][c] k [†] σ [, c] k [†] +Qσ [) ; Ψ][k][σ][ = (Ψ] k [†] σ [)][†] (104)


for the antiferromagnetic state. In the presence of a
staggered external magnetic field h(x) = h exp(iQ · x)
the non-interacting part of the Hamiltonian for bipartite lattices with ǫk+Q = ǫk then becomes H0 =
�′ kσ [Ψ] k [†] σ [(][ǫ][k][σ][3][ −] [σ][ h] 2 [σ][1][)Ψ] kσ [where the prime on the sum]

indicates summation over the reduced Brillouin zone
only. The corresponding Green function




 G¯(K, z) F¯(K, z)
=
F¯ [∗] (K, z [∗] ) −G¯ [∗] (−K, −z [∗] )




(95)



is used to calculate the cluster-excluded Green function

(K, z) = [ G [¯] [−][1] (K, z) + Σc(K, z)] [−][1] (96)
**G**

which together with the coarse-grained interaction U [¯] (K)
defines the action of the corresponding effective cluster
model



dτ [′][ �]
0 ij



�β



Sc = −



�β

dτ

0



**ψ** [†] i [(][τ] [)] **[G]** [ij][(][τ][ −] [τ][ ′][)] **[ψ]** j [(][τ][ ′][)]
ij



�β




- �� **ψ** [†] i [(][τ] [)][σ][3] **[ψ]** i [(][τ] [)] ( **ψ** [†] j [(][τ] [)][σ][3] **[ψ]** j [(][τ] [)] (97).



+




 dτ


ij

0



ij



U¯ij

2



As in the normal state case (see Eq. (77)), the cluster
action is represented in cluster real space and all the
quantities are cluster Fourier transforms of the corresponding quantities in cluster K-space. The spinors of
Grassmann-variables **ψ** [†] i [= (][γ] i [∗] ↑ [, γ] i↓ [) and] **[ψ]** i [= (] **[ψ]** i [†][)][†][ gen-]
erate coherent states corresponding to the cluster Fourier
transform of the Nambu-spinors Eq. (92). In analogy,
the corresponding cluster Hamiltonian in the superconducting state is obtained from the normal state cluster
Hamiltonian Eq. (83) by representing it with the Nambuspinors (92) and adding a U(1) symmetry breaking term




 



Ψ [†] K [[¯][η][′][(][K][)][σ][1][ −] [η][¯][′′][(][K][)][σ][2][]Ψ] K [,] (98)
K



where ¯η(K) = Nc/N [�] k˜ [η][(][K][ + ˜][k][) is the coarse-grained]
pair-field.
After self-consistency is established by requiring that
the Green function of the effective cluster model calculated with the action Eq. (97) equals the coarse-grained
Green function Eq. (95), the order parameter ∆k can be
calculated. Within the DCA the resolution in k-space is
restricted to the cluster K-points and the order parameter is coarse-grained



= [zσo (ǫk µ)σ3 σ [h]
   -    -    - 2



2 [σ][1][ −] [Σ][c][(][K][, z][)]][−][1][,]



¯∆K = [N][c]

N





cK+˜k↑c−(K+˜k)↓ = F [¯] (K, τ = 0 [+] ) (99)
⟨ ⟩
k˜



Gσ(k, z) = Ψkσ; Ψ [†] kσ [⟩⟩][z] (105)
⟨⟨



and given by the equal-time coarse-grained anomalous
Green function F [¯] as (after analytical continuation)



with k = K + k [˜], is coarse-grained over the DCA cells



F¯(K, τ = 0 [+] ) = [1]

β





F¯(K, iωn)
n







Gσ(K + k [˜] ) (106)
k˜



G¯ σ(K) = [N][c]

N




 = G¯σ(K, K) G¯σ(K, K + Q)
G¯σ(K + Q, K) G¯σ(K + Q, K + Q)




ℑmF [¯] (K, ω + iδ) . (100)



= [1]

π



�∞ 
βω
dω tanh

2

0



�∞



2




,


where we dropped the frequency argument for convenience. The cluster excluded Green function

σ(K, z) = [ G [¯] [−] σ [1][(][K][, z][) +][ Σ][c,σ][(][K][, z][)]][−][1][ .] (107)
**G**

then has two elements, σ(K, K) and σ(K, K + Q). As
G G
a result, its Fourier transform to real space



1
ij,σ =
G Nc


1
+
Nc







e [i][K][·][(][X][i][−][X][j] [)] e [−][i][Q][·][x][j] σ(K, K + Q)
G
K



e [i][K][·][(][X][i][−][X][j] [)] σ(K) (108)
G
K







breaks translational symmetry. The action of the corresponding cluster model in the antiferromagnetic state
is then formally identical to the action in the paramagnetic state, Eq. (77). As in the superconducting state the
corresponding cluster model is obtained from the paramagnetic cluster model Eq. (83) by changing the representation to the Nambu spinors Eq. (104) and adding a
symmetry breaking term




 



σ [h]

2

Kσ



2 [Ψ] K [†] σ [σ][1][Ψ] Kσ [,] (109)



21


where we adopt the conventional notation
(Abrikosov et al., 1963) k = (k, iωn), k [′] = (k, iωn′ ),
q = (q, iνn) and Tτ is the time ordering operator.
χσσ′ (q, k, k [′] ) and the irreducible two-particle vertex
function Γσσ′ (q, k, k [′] ) (not to be confused with the singleparticle hybridization function) are related to each other
through the Bethe-Salpeter equation


χσσ′ (q, k, k [′] ) = χ [0] σσ [′] [(][q, k, k][′][) +][ χ] σσ [0] [′′] [(][q, k, k][′′][)]
Γσ′′σ′′′ (q, k [′′], k [′′′] )χσ′′′σ′ (q, k [′′′], k [′] ) (111)
×

where χ [0] σσ [′] [(][q, k, k][′′][) is the non-interacting susceptibility]
constructed from a pair of fully-dressed single-particle
Green functions. As usual, a summation is to be made
for repeated indices.
We now make the DCA substitution Γσσ′ (q, K +
k˜, K [′] + ˜k [′] ) → Γcσσ′ (q, K, K [′] ) in Eq. (111) where Γc is
the irreducible two-particle vertex calculated on the cluster (frequency labels have been suppressed). Note that
only the bare and dressed two-particle Green functions
χ depend upon the superlattice wave-vectors k [˜] . Since χ
and χ [0] in the product on the RHS of Eq. (111) share no
common momentum labels, we may freely sum over the
wave-vectors k [˜], yielding


χ¯σσ′ (q, K, K [′] ) = ¯χ [0] σσ [′] [(][q, K, K] [′][) + ¯][χ][0] σσ [′′] [(][q, K, K] [′′][)]
Γcσ′′σ′′′ (q, K [′′], K [′′′] )¯χσ′′′σ′ (q, K [′′′], K [′] ) . (112)
×

By coarse-graining the Bethe-Salpeter equation, we have
greatly reduced its complexity; each of the matrices
above is sufficiently small that they may be easily manipulated using standard techniques.
In contrast with the single-particle case where the
coarse-grained quantities are identical to those of the
cluster, the cluster quantity χcσσ′ (q, K, K [′] ) is not equal
to ¯χσσ′ (q, K, K [′] ). This is because the self-consistency is
established only at the single-particle level. Unlike the
single-particle case where both Σc(K) and G [¯] (K) are directly calculated, neither Γcσσ′ (q, K, K [′] ) nor the coarsegrained susceptibility ¯χσσ′ (q, K, K [′] ) are calculated during the self-consistency. Instead, the coarse-grained noninteracting susceptibility ¯χ [0] σσ [′] [(][q, K, K] [′][) is calculated in]
a separate program after the DCA converges using the
relation



to account for the external staggered magnetic field h.
After convergence, the sub-lattice magnetization m =
1/N [�] iσ [e][i][Q][·][x][i][σ][⟨][n][iσ][⟩] [may be calculated from the off-]
diagonal component of the Green function matrix
Eq. (106) according to



1
m =
Nc





σG [¯] σ(K, K + Q; τ = 0 [−] ) (110)
Kσ



�+∞



=
 - N [1] cπ







Kσ



dωf (ω)σ mG [¯] σ(K, K + Q; ω + iδ) .
ℑ
−∞



F. Calculation of susceptibilities


A convenient way to identify continuous phase transitions is to search for divergences of susceptibilities. One particular advantage of quantum cluster
theories is that they allow us to consistently calculate these susceptibilities from the corresponding cluster
susceptibility(Hettler et al., 2000). Unfortunately, the
calculation of two-particle correlation functions in the
CDMFT formalism is strongly hampered by the violation of translational invariance on the cluster. So, in this
section, we will restrict our attention to the calculation of
two-particle quantities in th DCA following Hettler et al.
(2000) and Jarrell et al. (2001b).
As a specific example, we describe here the calculation
of the two-particle Green function



χ¯ [0] σσ [′] [[(][q][, iν][n][); (][K][, iω][n][); (][K][′][, iω][n][′][)] =][ δ][σσ][′] [δ][KK][′] [δ][ω] n [ω] n [′]



× [N] N [c]







Gσ(K + k [˜], iωn)Gσ(K + k [˜] + q, iωn + νn) (113).
k˜




       - β       - β
χσσ′ (q, k, k [′] ) =

0 0




- β


0




- β

dτ1dτ2dτ3dτ4
0



× e [i][((][ω][n][+][ν][)][τ][1][−][ω][n][τ][2][+][ω][n][′] [τ][3][−][(][ω][n][′] [+][ν][)][τ][4][)]

× ⟨Tτ c [†] k+qσ [(][τ][1][)][c][k][σ][(][τ][2][)][c] k [†] [′] σ [′] [(][τ][3][)][c][k][′][+][q][σ][′] [(][τ][4][)][⟩] [,]



The corresponding cluster susceptibility is calculated by
the cluster solver, e.g. the QMC process, as discussed in
Sec. III.C.1 and the vertex function is extracted by inverting the cluster two-particle Bethe-Salpeter equation


0 0
χcσσ′ (q, K, K [′] ) = χcσσ [′] [(][q, K, K] [′][) +][ χ][c] σσ [′′] [(][q, K, K] [′′][)]
Γcσ′′σ′′′ (q, K [′′], K [′′′] )χcσ′′′σ′ (q, K [′′′], K [′] )(114) .
×

If we combine Eqs. (114) and (112), then the coarsegrained susceptibility may be obtained after elimination


of Γcσσ′ (q, K, K [′] ) between the two equations. It reads


**χ** ¯ [−][1] = **χ** [−] c [1] **χ** c [0][−][1] + ¯ **χ** [0][−][1], (115)

        
where, for example, **χ** ¯ is the matrix formed from
χ¯σ,σ′ (q, K, K [′] ) for fixed q. The charge (ch) and spin (sp)
susceptibilities χch,sp(q, T ) are deduced from ¯χ according
to



22


Figure 8 A few low-order diagrams in the irreducible selfenergy of a quenched diagonally disordered system. Each circle represents the scattering of a state k from sites denoted
by X and a dotted line. The correlations between the electrostatic potentials on different sites are denoted by the wavy
line.


shown in Fig. 8 which makes a contribution to the selfenergy

   1

Vi [2][V] j [ 2]

N [4] i=j,k1,k2,k3⟨ [⟩][G][(][k][1][)][G][(][k][2][)][G][(][k][3][)]

× e [i][x][i][·][(][k][1][−][k][+][k][3][−][k][2][)] e [i][x][j] [·][(][k][2][−][k][1][+][k][′][−][k][3][)] (118)

After averaging over the disorder configurations,becomes a function of xi xj . We identify this average ⟨Vi [2][V] j [ 2][⟩]
as Dij [22][. With translational invariance restored, we may] complete the Fourier transform, and obtain



χch,sp(q, T ) = [(][k] N [B][T] c [2][ )][2]




 
λσσ′ ¯χσσ′ (q, K, K [′] ),(116)
KK [′] σσ [′]



where λσσ′ = 1 for the charge channel and λσσ′ = σσ [′]

for the spin channel. The calculation of particle-particle
(i.e. pairing) susceptibilities follows from a straightforward generalization of this formalism. The reader is referred to prior articles on cluster QMC for more details
on these topics (Jarrell et al., 2001b).


G. Disordered systems



In this section, we describe cluster approximations for
disordered systems. The mapping between the lattice
and the cluster in the CDMFT and the molecular CPA
(MCPA) is identical, and when the CDMFT is applied
to disordered systems, it becomes identical to the MCPA
(Ducastelle, 1974; Tsukada, 1969). The MCPA and related techniques for disordered systems are extensively
reviewed in Gonis (1992) and will not be discussed here.
In the remainder of this section we describe a DCA for
disordered systems that recovers the CPA for Nc = 1 and
becomes exact when Nc . This is an extension of
→∞
the formalism introduced by Jarrell and Krishnamurthy
(2001), modified to include the effects of correlated disorder (Jarrell and Johnson, 2004). We consider an Anderson model with diagonal disorder, described by the
Hamiltonian



δkk′ 
N [3]



δkk′



D [22] (q)G(k1)G(k2)G(k3)

k1,k2,k3,q




  H = −t

<ij>,σ




- - c [†] iσ [c][jσ][ +][ c][†] jσ [c][iσ] +



iσ (Vi − µ)niσ (117)



(Nδq+k2+k,k1+k3 1) . (119)
                
It is easy to extend this argument to all orders in perturbation theory. All graphs are composed of sums of
products of Laue functions (e.g. ∆= Nδq+k2+k,k1+k3),
and Green functions G(k) and D [nm] (q), where D [nm] (q)
is the Fourier transform ofA hierarchy of approximations may then be con- Dij [nm] = ⟨Vi [n][V] j [ m][⟩][.]
structed by approximating the Laue functions within the
graphs. These include the CPA where conservation of
the internal momentum labels is completely neglected.
Here, all of the Laue functions involving the internal momentum labels are set to one, ∆= Nδk1+k2··· 1. In
→
this case we may freely sum over all internal momentum
labels, and all terms describing non-local correlations,
such as those on the bottom of Fig. 8 vanish, whereas
the CPA graphs shown on top remain. Different cluster approximations, including the MCPA and the DCA
may be constructed by systematically restoring momentum conservation through the appropriate choice of Laue
function, as discussed in Sec. II.B
For the DCA, we divide the lattice into clusters as
described in Fig. 3, write wave-vectors as k = K + k [˜] and
employ the DCA Laue function Eq. (58),


∆DCA = NcδK1+K2,K3+K4..., (120)


such that momentum conservation is preserved only
within the cluster reciprocal space K. With this choice



where c [†] iσ [creates a quasiparticle on site][ i][ with spin][ σ][ and]
niσ = c [†] iσ [c][iσ][. The disorder occurs in the site occupancies]
labeled by ξi and in the local orbital energies Vi which
describe the electrostatic potential at site i. We assume
that Vi are quenched random variables distributed according to some specified probability distribution which
includes the effects of intersite correlations.
The effect of the disorder potential [�] iσ [V][i][n][i,σ][ may be]
described using standard diagrammatic perturbation theory (although we eventually sum to all orders). We perturb around the ordered state, described by the first term
in Eq. (117).
Translational invariance and momentum conservation
are restored by averaging over all allowed values of the
site occupancies ξi and the corresponding disorder po{ }
tentials Vi. We study this effect, e.g., on the sixth graph


for the Laue function, we may freely sum over superlattice wave-vectors k [˜] within each DCA coarse-graining cell
(see Fig. 3). This leads to the replacement of the lattice propagators G(k) and D [nm] (k) with coarse-grained
propagators G [¯] (K) and D [¯] [nm] (K), respectively,



23


system without configurational correlations. On a hypercubic lattice of dimension D



g [βγ] (k) = g [0][,βγ] δk,0 + α (2δβγ − 1)



�D

cos(kl) . (129)

l=1



G¯(K, z) = [N][c]

N





G(K + k [˜], z), (121)
k˜



D [nm] (K + k [˜] ), (122)
k˜



The corresponding coarse-grained result is



�D

cos(Kl) (130)

l=1



D¯ [nm] (K) = [N][c]

N



g¯ [βγ] (K) = g [0][,βγ] δK,0 + α (2δβγ − 1) R



The first of these sums is straightforward; however, the
second requires some investigation due to the powers of
the potential.
Here, we calculate D [¯] [nm] (K) for a binary A,B alloy
where the concentration of A atoms is c and that of B
atoms is 1−c. This calculation can be generalized to multicomponent alloys and may easily be extended for more
complex alloys. For the binary alloy, we employ an idempotent formalism where the idempotent ξi = 1 indicating
that the site is occupied by an A atom, or ξi = 0 indicating a B atom site. If we associate Vi = VA or VB for an
A or B atom, respectively, then Vi = ξiVA + (1 − ξi)VB.
Then, since ξi [n] [=][ ξ][i][ and (1][ −] [ξ][i][)][n][ = 1][ −] [ξ][i][,]

⟨Vi [n][V] j [ m][⟩] [=][ ⟨][(][ξ][i][V][A] [+ (1][ −] [ξ][i][)][V][B][)][n][(][ξ][j][V][A] [+ (1][ −] [ξ][j][)][V][B][)][m][⟩]
= ⟨(ξiVA [n] [+ (1][ −] [ξ][i][)][V] B [ n][)(][ξ][j] [V] A [ m] [+ (1][ −] [ξ][j][)][V] B [ m][)][⟩]

= Vα [n][V] β [ m][g] ij [βγ] (123)


where repeated indices in the last line are summed over
and


gij [AA] = ξiξj (124)
⟨ ⟩

gij [AB] = ξi(1 ξj) (125)
⟨           - ⟩

gij [BB] = (1 ξi)(1 ξj ) (126)
⟨           -           - ⟩

are the joint probabilities for occupation of sites i and j
by atoms of the designated types.
This formalism may be generalized to a multicomponent alloy α = A, B, C, . . .. Since a site may only be
occupied by an atom of one type only, in general

⟨Vi [n][V] j [ m][⟩] [=][ V] α [ n][V] β [ m][g] ij [βγ] [.] (127)

all⟨Vi n [n][V] andj [ m][⟩] m [is a] . Thus, the effect of coarse-graining [ linear][ function of the probabilities] D [ g][nm] ij [βγ] (fork)
is equivalent to coarse-graining g [βγ] (k) for all n and m.
As an example, consider a binary alloy with only nearneighbor configurational correlations. Here we may write

gij [βγ] [=][ g][0][,βγ][ +][ α][ (2][δ][βγ][ −] [1)][ δ][i][+][ǫ,j] (128)


where ǫ indexes the near-neighbors to site i, and g [0][,AA] =
c [2], g [0][,BB] = (1 − c) [2] and g [0][,AB] = c(1 − c) are the joint
probabilities for the occupation of different sites for a



where R = (Lc/π) sin(π/Lc) is a coarse-graining factor
(Lc = Nc [1][/D] is the linear cluster size). If we transform
back to the cluster coordinates, then

g¯ij [βγ] [=][ g][0][,βγ][ +][ Rα][ (2][δ][βγ][ −] [1)][ δ][i][+][ǫ,j] (131)


are the configurational probabilities for the cluster, where
ǫ labels the sites adjacent to i. In the CPA limit, Lc = 1
and thus R vanishes indicating the lack of any configurational correlations. In the limit as Nc = L [D] c,
→∞
R = 1, so correlations are systematically restored.
The cluster problem generated by the substitution
∆ → ∆DCA may be solved numerically. Each of the
diagrams in Fig. 8 representing Nc independent scatters, or less, remain finite; however, scattering diagrams
for greater than Nc scatters vanish. The complexity of
the problem is further reduced since the nontrivial sums
involve only the cluster momenta K ( numbering Nc
instead of N ). Furthermore, since these diagrams are
the same as those from a finite-sized periodic cluster of
Nc sites, we can easily sum this series to all orders by
numerically solving the corresponding cluster problem.
The resulting algorithm is identical to that presented in
Sec. II.B.4, except that: 1. In the coarse-graining step we
must calculate both the coarse-grained correlation function



2. We then solve the cluster problem by performing a
weighted average of the cluster Green function (in matrix
notation in the cluster sites)

�� �−1 [�]
G = **G** [−][1]       - V (134)


over all disorder configurations. The weighting of each
configuration is determined by the Fourier transform of
g¯ [βγ] (K) to obtain the cluster configurational probabilities
g¯ij [βγ][. After convergence is reached, the irreducible cluster]
quantities may be used to calculate the properties of the
lattice.



g¯ [βγ] (K) = [N][c]

N





g [βγ] (K + k [˜] ). (132)
k˜



and the coarse-grained cluster Green function



1
(133)
z + µ ǫK+˜k Σc(K, z)
   -   


G¯(K, z) = [N][c]

N






k˜


H. Alternative cluster methods


In this review we decided to focus on the three, in
our view most established cluster methods. This section
reviews several other ideas proposed to introduce nonlocal correlations, some of which are complementary to
the approaches discussed.


1. Self-energy functional theory


The self-energy-functional approach developed by
Potthoff (2003b) (see also Potthoff et al., 2003) is a very
general unifying concept for existing cluster approaches
and in addition provides the power to construct novel
cluster algorithms. Similar to the formalism presented in
Sec. II.B, this approach views the grand potential Ωas
the central quantity. Here, the self-energy Σ is considered
the basic dynamic variable and a self-energy functional
Ω[Σ] = Tr ln( (G [−] 0 [1]
the Legendre-transform− [−] [Σ] F [)] [ [−] Σ [1] ] = Φ[ [)+] [F] [[][Σ] G [] is constructed from] [Σ]] - Tr(ΣG[Σ]) of
the Φ[G] functional. This approach proceeds with setting up a general variational scheme to use dynamical
information from a (numerically) solvable reference system H [′] = H0(t [′] ) + H1(U) to approximate the physics
of the original system H = H0(t) + H1(U). While the
single-particle parts H0 are generally different, the interaction part H1(U) is kept fixed, to ensure that the
functionals F [Σ] of the reference system and the original system share the same functional dependence. It can
then be shown that the grand potential of the original
system Ωt[Σ] can be evaluated exactly according to


Ωt[Σ(t [′] )] = Ω [′] + Tr ln( (G [−] 0 [1] Σ(t [′] )) [−][1] )

         -         
      - Tr ln(−G [′] ) (135)

from the grand potential Ω [′], the trial self-energy Σ(t [′] )
and Green function G [′] of the reference system. Variation is then performed with respect to the single-particle
parameters t [′] of the reference system and the stationary
point is determined by ∂Ωt[Σ(t [′] )]/∂t [′] = 0.
The choice of a suitable and solvable reference system
H [′] given the original Hamiltonian H is in principle arbitrary. Within the SFT, cluster approximations are constructed from a reference system H [′] that represents decoupled clusters of size Nc which are optionally coupled
to additional nb uncorrelated bath sites. A schematic
illustration for the Hubbard model is shown in Fig. 9.
A set of decoupled sites as a reference system H [′] (not
shown) yields the Hubbard-I approximation. Non-local
correlations can be included by considering a system of
decoupled clusters of size Nc > 1. This approach is identical to the CPT when the intra-cluster parameters t [′] are
fixed to the original values t : The self-energy of the ref−1 ′−1
erence system, Σ(t [′] ) = G [′] 0 G is calculated once
            and used to approximate the Green function of the original lattice model, G [−][1] = G [−] 0 [1] Σ(t [′] ). This yields the

         expression (47) of the CPT, G [−][1] = G [′−][1] - δt, since the



24


Figure 9 Taken from Potthoff et al. (2003). Various reference systems H [′] for the 2D Hubbard model on a square lattice. The solid and dashed lines represent the intra- and intercluster hopping respectively, the filled circles the on-site interaction U . Additional nb bath sites are depicted by open
circles, while the shaded circles represent nb = ∞ bath sites.


bare Green-functions of the original and reference systems only differ by the inter-cluster hopping δt.
Alternatively within the SFT the intra-cluster hopping
t [′] can be treated variationally. Calculations for the 1D
Hubbard model (Potthoff et al., 2003) however show that
the SFT functional Eq. (135) is stationary for t [′] slightly
larger but very close to the original value t, with the difference becoming smaller as Nc increases. The SFT can
also be used to find the correct boundary conditions of
the CPT cluster. Calculations with fixed intra-cluster
hopping t [′] = t and additional variational hopping tr
between the surface sites to simulate periodic boundary
conditions show that the self-energy functional is only
stationary at tr = 0 (open boundary conditions), not at
tr = t (periodic boundary conditions) (Potthoff et al.,
2003).
One shortcoming of the CPT is its inability to describe
phases with broken symmetry due to the finite size of the
clusters. The SFT can be used to construct a variational
CPT, an extension of the CPT to account for long-range
order (Dahnken et al., 2003). This is done by adding a
fictitious symmetry breaking single-particle term to the
reference system and subtracting it in the inter-cluster
part so that it has no effect on the original lattice Hamiltonian. The magnitude of this term is then optimized in
the SFT variational treatment. Calculations for the 2D
Hubbard model show very good agreement with variational Monte Carlo and auxiliary field Quantum Monte
Carlo results for the ground-state energy and the staggered magnetization (Dahnken et al., 2003).
Embedded cluster approximations are constructed if
additional nb uncorrelated bath sites are introduced. The
DMFT is obtained by choosing as a reference system a set
of decoupled sites coupled to nb = ∞ uncorrelated bath
sites. The CDMFT is identical to a system of decoupled
clusters coupled to nb = ∞ bath sites with the intra


![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-23-0.png)
cluster parameters being fixed at the original values t and
the bath parameters being treated as variational. It can
then be shown (Potthoff et al., 2003) that the SFT selfenergy functional is stationary at the bath parameters
that fulfill the CDMFT self-consistency. A corresponding
analysis of the DCA formalism within this approach is
still lacking.
Intermediate approximations can be constructed by
considering a finite number 0 < nb < ∞ of bath sites.
This approach is superior to the CPT and inferior to the
CDMFT. For a reference system with Nc = 1 and nb = 1
this approach can be used to study the Mott transition in
the Hubbard model (Potthoff, 2003a) analytically and it
was shown to yield the same qualitative picture as the full
DMFT (Nc = 1, nb = ∞) analysis (see Georges et al.,
1996).


2. Fictive impurity models


Similar to the SFT approach discussed above, this very
general approach by Okamoto et al. (2003) is centered
on the self-energy Σ as the basic dynamic variable. It
is based on the idea that the cluster model is merely
an algorithm to calculate coefficients in an orthogonal
function expansion of the momentum dependence of the
electronic self-energy


     Σapprox(k, z) = Φi(k)Σi(z) . (136)

i=0...n


The coefficients Σi(z) can then be obtained from the solution of a n+1-site fictive impurity model involving n+1
mean-fields which are fixed by the requirement that the
impurity model Green functions Gi equal the corresponding integrals over the lattice Green function


  Gi(z) = Φi(k)[G [−]  - [1][(][k][, z][)][ −] [Σ][approx][(][k][, z][)]][−][1][ .][ (137)]

k


To include local and nearest neighbor correlations, the
momentum dependence of the self-energy may be expanded up to second order using the orthogonal functions
Φ0(k) = 1 and Φ1(k) = e [ika] . Since in general the orthogonal functions Φi(k) change sign over the Brillouin zone
except for the local term i = 0, causality is not guaranteed when the expansion is truncated at low order.
However it is shown that simple filtering of the higherorder terms may be used to circumvent these problems
(Okamoto et al., 2003).
The DCA may be viewed as a specific example of this
approach, where the indices i correspond to the centers
K of the DCA cells and the functions ΦK(k) are set to 1
if k is contained in the cell represented by K and 0 otherwise (see Fig. 3). Causality problems are thus avoided
by using orthogonal functions which are non-negative everywhere. The resulting approximants however have discontinuities in momentum space.



25


3. Non-local effects via spectral density approximation


Laad and van den Bossche (2000) proposed to include
non-local 1/D-corrections by combining DMFT with the
Spectral Density Approximation (SDA) (Roth, 1969) and
applied this approach to the FKM (see Eq. (182)) for
which it becomes particularly simple. In the SDA, the
moments of the spectral function are determined (via repeated evaluation of commutators with the Hamiltonian)
by complicated but static correlators. For the FKM,
to order 1/D the SDA self-energy of the d electrons,
Σ0,d(k, z) can be expressed in terms of the static susceptibility of the f -electrons. This self-energy is purely
real, but momentum dependent and is used to approximate the bath self-energy in the hybridization function




 Γ(z) =


k



t [2]

(138)
z − ǫk + µ − Σ0,d(k, z)



for the effective impurity problem in D = ∞. The impurity self energy, Σimp,d(z) (see Brandt and Mielsch, 1989)
combines with the bath self-energy Σ0,d(k, z) to a dynamical, non-local self-energy of the form

      Σd(k, z) = Σimp,d(z)+Σ0,d(k, z) Σ0,d(k, z) . (139)

          
k


This finally determines the Green function of the mobile d- electrons of the usual form, Gd(k, z) = [z − ǫk +
µ Σd(k, z)] [−][1], which is used together with Σd(k, z)
 to estimate the susceptibility of the f -electrons (see
Laad and van den Bossche, 2000 for details). Σ0,d(k, z)
can then be recalculated to close the self-consistency
loop.
With this method, Laad and van den Bossche studied the DOS and the spectral function A(k, ω) of the
FKM on a 2D square lattice. Their results agree well
with known results and other studies like Hettler et al.
(2000). On the other hand, the FKM is a particularly
gentle test bed for their method, due to its effective impurity nature (mobile electrons in a static background).
For a model with true dynamics like the Hubbard model,
it is unclear whether the method is even feasible (due
to the additional spin-flip and pair-hopping correlators),
and the limitation of a purely real bath self-energy is
likely to be too restrictive.


4. Non-local corrections via projection technique


Using the projection technique Tien has developed
a cluster extension of the DMFT by taking into
account both local and non-local contributions to
the dynamics within a relevant subspace of Liouville
or operator space (Minh-Tien, 1998, 1999a,b, 2001;
Tanh-Hai and Minh-Tien, 2001). The information of
a given subspace is stored in static susceptibility and
frequency functions while the effects of the remaining subspace are collected in a dynamic memory function. The idea of Tien’s approach is to approximate


this memory function by a local quantity. Hence, nonlocal correlations are taken into account through static
quantities (susceptibilities), while dynamical correlations
are approximated by a local memory function. If the
relevant subspace is spanned by operators acting on
the same or nearest-neighbor sites only, these quantities can be calculated in an effective impurity model
(Minh-Tien, 1998, 1999a) or, in an improved version,
in a two-site cluster model (Minh-Tien, 1999b, 2001;
Tanh-Hai and Minh-Tien, 2001).
This approach has not been rigorously proven to
be causal, however its application to the FalicovKimball (Minh-Tien, 1998, 1999b) and Hubbard model
(Minh-Tien, 2001) shows that the spectral function is
positive definite and the sum-rules of the first few moments of the spectral densities are preserved. The neglect of non-local dynamical correlations however leads
to spurious behavior at low temperatures: A Kondo resonance emerges in the in 2D half-filled Hubbard model
at low temperatures similar to the behavior observed in
DMFT simulations but inconsistent with other cluster
calculations which show a pseudogap down to the lowest
temperatures (see Sec. IV.D.2). This shortcoming is due
to the fact that the nearest-neighbor static correlations
are proportional to the band-dispersion ǫk. At the Fermi
energy, ǫk = 0, hence non-local correlations vanish and a
Kondo-resonance is generated due to the local nature of
the dynamical correlations.


5. Two-site correlations with composite operators


A dynamical non-perturbative two-site approximation
for the Hubbard model based on the composite operator method was developed by Matsumoto and Mancini
(1997) and later adopted and improved by Stanescu and
Phillips (Stanescu and Phillips, 2001, 2003a). By using
Hubbard operators as a local basis which exactly diagonalize the interaction part of the Hamiltonian, this
approach recovers both the weak coupling U ≪ t and
strong coupling U ≫ t limits of the Hubbard model.
The memory function δm(k, ω) which collects the effects
of dynamical correlations is expanded in a two-site approximation as δm(k, ω) = δm0(ω) + αkδm1(ω) where
αk = (cos kx + cos ky)/2 and δm0 (δm1) are the local (nearest-neighbor) contributions. Hence this method
contains on-site and nearest-neighbor dynamical correlations. Unknown quantities are expressed in terms of resolvents for the eigenstates of a two-site impurity system.
The renormalization of these resolvents due to their coupling to the surrounding of the two-site system is treated
within the non-crossing approximation.
The application of this technique to the Hubbard
model shows qualitative agreement of the single-particle
spectra (Matsumoto and Mancini, 1997) in 2D with finite size QMC results and high accuracy of specific heat
results (Stanescu and Phillips, 2001) as compared to the
Bethe ansatz solution in 1D. Although this technique



26


includes only on-site and nearest-neighbor correlations,
it already captures important signatures of correlations
consistent with DCA/QMC results for larger clusters
such as the existence of a Mott-Hubbard gap in the
2D Hubbard model for all values of U > 0 at low T
(Stanescu and Phillips, 2001) and the emergence of a
pseudogap in the density of states due to antiferromagnetic correlations (Stanescu and Phillips, 2003a; see also
Sec. IV.D).


III. QUANTUM CLUSTER SOLVERS


Cluster techniques map the lattice system onto a selfconsistently embedded quantum cluster model. This
chapter discusses the most promising numerical approaches used to solve this cluster problem. After stressing some general difficulties faced by potential cluster
solvers in Sec. III.A, we present several perturbative
techniques, including second order perturbation theory
in Sec. III.B.1, the fluctuation-exchange approximation
in Sec. III.B.2, and the non-crossing approximation in
Sec. III.B.3. Section III.C reviews the application of
non-perturbative, (numerically) exact techniques including Quantum Monte Carlo in Sec. III.C.1, Exact Diagonalization (ED) in Sec. III.C.2 and the numerical renormalization group in Sec. III.C.3.


A. General remarks


The fundamental difference between a finite size cluster and the effective cluster problem of quantum cluster
theories is the existence of additional quantum mechanical bath degrees of freedoms in the latter. The simplest
realization of such a system is of course the well-known
Anderson impurity model (Anderson, 1961). In general,
its ground state is a nontrivial many-body state, which is
not perturbatively connected to states of simpler starting
points like a non-interacting or a free impurity. Furthermore, the excitations also are of many-body character
and typically involve dynamically generated low-energy
scales which depend non-analytically on system parameters. Consequently, any perturbation theory is faced
with severe limitations concerning its region of applicability and the most successful techniques used to solve
this fundamental problem of solid state theory are nonperturbative (Hewson, 1993).
Nevertheless, a variety of tools to approximately or numerically solve this model have been developed over the
last 25 years (Hewson, 1993). Since the physics of the Anderson impurity model is very well understood (Hewson,
1993), this knowledge can be employed to judge the quality of results and region of applicability of these various
analytical or computational techniques at hand, a priori
as well as a posteriori. This statement does also apply to
a large extent to the DMFT, where an effective Anderson impurity model plays the central role (Georges et al.,


1996; Pruschke et al., 1995).


The situation becomes much more involved for quantum cluster problems. First, from a purely technical
point of view, the complexity of the system can limit the
applicability of a method on principal grounds or even
rule it out as a potential cluster solver altogether. This
aspect will be discussed for every technique in detail in
the following sections.


Similarly important is a novel complexity of the physics
entering already on the level of the bare cluster and
largely complicating the task to judge the reliability and
quality of results obtained with a certain method. With
increasing cluster size not only high-energy states (charging energies) – which are the only one present in the impurity case – will couple to the quantum bath but also
medium- and to some extent low-energy states (e.g. nonlocal spin fluctuations). Moreover, the latter already can
and in general will contain interesting many-body effects.
The coupling to the bath can then lead to a subtle interplay or even competition between such intrinsic manybody effects and those introduced by quantum fluctuations in the external bath. A well-established example is the occurrence of a quantum phase-transition in
the two-impurity Kondo model (Jones and Varma, 1987;
Jones et al., 1988) driven by the competition between the
RKKY magnetic interaction favoring a non-local singlet
and the Kondo effect with its local singlet formation.


In contrast to the single impurity case where the qualitative results to be expected from a calculation can in
principle be read off the input parameters, such a vital possibility of a plausibility check for a given method
does not exist in case of quantum cluster models. Experience tells that even at first sight physically plausible results need to be checked carefully. Again, the
two-impurity Kondo model can serve as a pedagogical example. The original, quite intuitive result by
Jones et al. (1988) has later been reexamined by others
and found to be valid only under very special circumstances (Sakai and Shimizu, 1992; Sakai et al., 1990). A
fully satisfactory understanding of the physics of this simplest quantum cluster model is in fact lacking until today.
Things are further complicated for the case of cluster
mean-field theories due to the “backflow” of the complex
local physics via the effective bath. An a priori understanding of the behavior of the system is, at least given
the current level of knowledge, virtually impossible, but
also an a posteriori plausibility check is rather based on
subjective physical intuition than on solid understanding
of the basic physics.


Thus, in order to obtain a reliable and consistent understanding of the physics of correlated electron systems
in the framework of cluster mean-field theories, it is vital
to employ a variety of complementary and possibly nonperturbative tools to solve the effective quantum cluster
model. We therefore discuss in detail different computational and analytical tools regarding their applicability
and reliability.



27


B. Perturbative techniques


The numerical effort to compute the cluster self-energy
increases rapidly with the cluster size, in principle exponentially for exact methods. This calls for simpler
methods for which the complexity of the problem can
be reduced. This can be achieved by perturbation theory in its many variations. One example is the standard
weak-coupling perturbation theory in the electronic interaction U . Second Order Perturbation Theory (SOPT)
and the more elaborate Fluctuation Exchange Approximation (FLEX) are discussed in the following sections. A
complementary strong-coupling approach handles the interaction exactly, but treats the coupling to the host Γ in
a perturbative expansion. An example for this approach
is the Non-Crossing Approximation (NCA), discussed in
Sec. III.B.3.


1. Second order perturbation theory


Second order perturbation theory has proven very useful to solve the effective impurity problem of the DMFT.
This iterated perturbation theory (IPT) becomes exact in the weak coupling limit U/t ≪ 1 and coincidently at half-filling even in the strong coupling limit
U/t ≫ 1 (Georges et al., 1996). The IPT was shown
to give results in good qualitative agreement with nonperturbative DMFT results, e.g. it captures the Motttransition at half-filling.
The application of second order perturbation theory in
the context of quantum cluster theories follows immediately from the formulation in Sec. II.B by considering the
first and second order diagrams in the cluster functional
Φ[ G [¯] ] and neglecting higher-order diagrams. Here we illustrate the formalism for the Hubbard model with local
interaction U . For the DCA, an expression for the cluster
self-energy Σc = δΦ[ G [¯] ]/δG [¯] may be obtained by introducing the bare particle-hole susceptibility, i.e. the ”bubble”.
With the notation K = (K, iωm), Q = (Q, iνn) we have



We ignored the constant (first order) Hartree term which
just shifts the chemical potential. Physically, the selfenergy accounts for the interaction of electrons with
virtually excited electron-hole fluctuations described by
χph. Eq. (141) is a convolution of the susceptibility and



χph(Q) =
    - [UT] Nc





G¯(K + Q) ¯G(K), (140)

K



where T is the temperature and G [¯] is the coarse-grained
Green function defined in Eq. (59). Note that ωm is
a fermionic Matsubara frequency, while νn is of bosonic
type. The cluster self-energy to second order in U is then
given by



Σc(K) = [UT]

Nc





χph(Q) G [¯] (K Q) . (141)
      Q


the Green function in both momentum and Matsubara
frequencies, and thus can be readily computed via Fast
Fourier transform (FFT). FFTs scale only logarithmically with size, so a much larger range of cluster sizes is
available for perturbative studies of this kind. For real
frequencies, the use of FFT is less appealing, since FFT
also requires an equidistant grid of frequencies. Compared to the usual expression for a finite size system, in
the DCA we use the coarse-grained Green function G [¯] for
evaluating the susceptibility and the self-energy, so the
momentum sums run over the Nc cluster momenta K, Q.
For the CDMFT, one can formulate similar expressions,
but, as discussed in Sec. II, the self-energy and Green
function are matrices in cluster real space. The matrix
inversions needed during the iteration become costly as
the cluster size is increased.
It must be emphasized that simple minded application
of FFT to Green functions (in particular with fermionic
Matsubara frequencies) is likely to incur large errors, due
the discontinuity at zero imaginary time that leads to the
slow 1/iωn decay of the Green functions and self-energies.
The way to deal with this is to manually subtract the
slowly decaying parts before application of the FFT. This
is possible as the high frequency behavior can be analytically determined. The subtraction leads to functions that
decay sufficiently fast to have a numerically well defined
transform, even though one has to cut off the Matsubara
sums in Eqs. (140,141) at a finite value. Details on this
subtraction technique can be found in Deisz et al. (2003).


2. Fluctuation exchange approximation


FLEX (Bickers et al., 1989; Bickers and White, 1990)
extends the second order perturbation theory through
higher order diagrams. It rests on the assumption that
the interacting electron system can be considered as a
problem of electrons exchanging self-consistently determined fluctuations of various kinds, i.e. density, spin
and pair fluctuations. In the context of quantum cluster theories, the FLEX was first applied within the DCA
by Aryanpour et al. (2003a). Here we briefly review the
corresponding formalism. The generating functional Φ of
the FLEX is a sum of the three fluctuation contributions
(Bickers et al., 1989)

Φ = Φ [df] ph [+ Φ] ph [sf] [+ Φ][pp][,] (142)


where



28

and the trace T r denotes (T/Nc) [�] Q �n [. In addition to]
the particle-hole bubble Eq. (140), the particle-particle
susceptibility χpp also appears and is defined by



χpp(Q) = [UT]

Nc





G¯(Q − K) ¯G(K) . (146)
K



With the generating functional of Eq. (142) the cluster
self-energy can be written as




V [(][ph][)] (Q) G [¯] (K − Q)



Σc(K) = [UT]

Nc







Q




            −V [(][pp][)] (Q) G [¯] (Q − K), (147)



where the so called FLEX potentials are given by



χph

[1] + [3]

2 1 + χph 2



V [(][ph][)] = χph + [1]
    - 2



χph

[3], (148)

2 1 χph
  


Φ [df] ph [=][ −] [1]



2 [Tr [ln(1 +][ χ][ph][)][ −]



2 [1] [Tr [][χ][ph][]][2][ + 1]



χph + [1] ph []][,] (143)

2 [χ][2]



Φ [sf] ph [= 3]



ph []][,] (144)
2 [χ][2]



2 [Tr [ln(1][ −] [χ][ph][) +][ χ][ph][ + 1] 2



and

V [(][pp][)] = χpp + χpp . (149)
          - 1 + χpp


The FLEX potentials constitute an infinite sum of fluctuation diagrams similar to the series of density fluctuations
also known as the Random Phase Approximation, which
is in fact a subset of the FLEX. However, the FLEX
also includes significant spin and pair fluctuations. Note
that second order perturbation theory is reproduced by
expanding Eq. (148) to first order in χph.
Naturally, the drawback of using these weak-coupling
methods lies in the fact that some strong coupling phenomena such as the opening of a Mott gap at half-filling
simply cannot be described by e.g. the FLEX approach.
Also, quite often the self-consistent evaluation simply
does not converge, particularly at low temperatures. This
is due to divergences showing up in perturbatively evaluated response functions. As a result, the variety of systems that can be studied is limited.
To obtain real time (or frequency) data, an analytic
continuation of the Green function or self-energy is necessary. For the FLEX, this is achieved by means of Pad´e approximation (Vidberg and Serene, 1977). Real frequency
results and details on the implementation of the Pad´e approximation can be found in Aryanpour et al. (2003b).


3. Non-crossing approximation


The Non-Crossing Approximation (NCA) (Grewe,
1983; Keiter and Czycholl, 1983; Keiter and Kimball,
1971; Kuramoto, 1983) was originally developed for the
single-impurity Anderson model and is based on a diagrammatic perturbation theory (Keiter and Kimball,
1970; Kuramoto, 1983) around the atomic limit of this
model. A comprehensive and detailed description of
the NCA and its limitations can be found in the review by Bickers (1987). The NCA has been extensively applied as an approximate solution of the effective impurity model in the DMFT context to study the



Φpp = Tr [ln(1 + χpp) χpp + [1] pp []][,] (145)
          - 2 [χ][2]


single-band Hubbard model (Pruschke et al., 1993a,b),
the three-band Hubbard model (Lombardo et al., 1996;
Schmalian et al., 1996; Maier et al., 1999a,b; Z¨olfl et al.,
2000) and the Anderson lattice model (Kim et al., 1990;
Kuramoto, 1985). Within quantum cluster theories, the
NCA has been extended to solve the effective cluster
problem of the DCA by Maier et al. (2000b). The aim of
this section is to convey the general concepts of the NCA
method and discuss the extensions necessary to solve the
effective cluster model of quantum cluster theories.
The perturbation theory used to construct the NCA
is based on a resolvent technique and is in general
applicable to problems where a discrete level system
not representable by standard fermionic or bosonic operators is coupled to continuous degrees of freedom
(Becker and Keller, 1987; Kuramoto, 1983). The discrete
level system in the context of the DCA is given by the
eigenstates of the local part of the cluster Hamiltonian,
Eq. (83),

  Hc,loc = Kσ (¯ǫK − µ)c [†] Kσ [c] Kσ (150)




 +


K,K [′]
Q






σσ [′]



U¯ (Q)

c [†] K+Qσ [c] K [†] [′] −Qσ [′] [c] K [′] σ [′] [c] Kσ [.]
2Nc



The perturbative expansion is performed with respect to
the coupling

   Hhyb = [VK(k [˜] )c [†] Kσ [a] K+k [˜] σ [+][ h.c.][]] (151)

K,k [˜],σ



29


Feynman diagram technique cannot be used for a perturbational expansion and the concept of resolvents must
be introduced instead (Kuramoto, 1983). The matrixelements of these resolvents in the space of the local
eigenstates have the form


Rmn [−][1] [(][z][) = (][z][ −] [E][m][)][δ][mn] mn [(][z][)][,] (155)

[−] [Σ][R]

where the resolvent self-energy Σ [R] (z) collects renormalization effects of the individual molecular states {|m⟩}
due to the hybridization Eq. (154) to the host. We note
that Σ [R] (z) and hence R(z) reduce to diagonal matrices
if the hybridization term Hhyb commutes with the local part Hc,loc of the cluster Hamiltonian. While this
is the case in the paramagnetic state we stress that the
non-diagonal elements become essential in the symmetrybroken phases (Maier, 2001; Maier et al., 2000a).


Figure 10 Non-crossing diagrams for the resolvent self-energy
Σ [R] . The dashed line stands for the dressed resolvent R defined in Eq. (155), the full line for the host electrons.


Keeping only the lowest order, self-consistent diagrams
for the resolvent self-energy Σ [R] illustrated in Fig. 10 defines the NCA. Since the hybridization with the host degrees of freedom enters the expressions only in the form
of a density of states



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-28-0.png)





![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-28-1.png)

VK(k [˜] ) δ(ω λK+˜k) =
| | [2]   -   - π [1]
k˜



(156)
π

[ℑ][m][Γ][c][(][K][, ω][)][,]



to the continuous degrees of freedom, i.e. the auxiliary non-interacting fermions akσ (a [†] kσ [). Hence the NCA]
should be an especially useful approximation where the
local energy scales (in this case U [¯] ) exceeds the magnitude
of the coupling V to the host.
To apply the resolvent technique, the fermionic cluster operators cKσ, (c [†] Kσ [) are expanded in terms of the]
Hubbard-operators Xmn = |m⟩⟨n|



1
N




 cKσ =




- 
CK [mn] σ [X][mn], c [†] Kσ [=]
m,n m,n



CK [mn] σ ∗Xnm (152)
m,n



there is no need to explicitly calculate the auxiliary host
parameters VK(k [˜] ) and λk of the cluster Hamiltonian,
Eq. (83). To ensure that the solution of the cluster problem is also the solution of the coarse-grained lattice problem, Γc(K, z) is replaced with the hybridization function
Γ(K, z) (see Eq. (82)) determined from coarse-graining
the lattice Green function. After observing energy, momentum and spin conservation, the analytical expression
for the resolvent self-energy within the NCA reads



where {|m⟩} are the eigenstates of the local Hamiltonian,
Eq. (150),

    Hc,loc = EmXmm (153)

m


with eigenenergies Em and CK [mn] σ [=][ ⟨][m][|][c][K][σ][|][n][⟩][. In this]
representation, the hybridization term Eq. (151) becomes





× (157)
l,l [′]



Σ [R] mn [(][z][) =][ −] [1]

π






K,σ










�+∞



∗
dεf (ε) mΓ(K, ε)CK [ml] σ [R][ll][′] [(][z][ +][ ε][)][C] K [nl] σ [′]
ℑ
−∞






 .



�+∞

dεf ( ε) mΓ(K, ε)CK [lm] σ ∗Rll′ (z ε)CKl [′] nσ

   - ℑ   −∞




  Hhyb =

K,k [˜],σ





[VK(k [˜] )CK [mn] σ ∗XnmaK+˜kσ + h.c.] . (154)
m,n



+



Since the Hubbard operators Xmn do not obey standard fermionic commutation relations, the conventional



The coupled equations (155) and (157) are solved selfconsistently to compute the matrix-elements of the resolvent R(z). By using the expansion Eq. (152), the cluster


Green function Gc(K, z) = ⟨⟨cKσ; c [†] Kσ [⟩⟩][z][ is written in]
terms of Hubbard operators

   - ∗
Gc(K, z) = CK [mm] σ [′] [C] K [nn] σ [′] Xmm′ ; Xn′n z .

⟨⟨ ⟩⟩
m,n,m [′],n [′]

(158)
Within the NCA, the correlation function on the right
hand side reduces to a convolution between resolvents



30


(like for instance uncoupled sites in a cluster calculation). An inclusion of these so-called vertex corrections
to the bare NCA defined by Eq. (157) has up to now been
possible only for the single impurity model with finite U
(Pruschke and Grewe, 1989), because the complexity and
number of the additional diagrams rather fast exceeds all
practical limits (Heindl et al., 2000).
Neglecting vertex corrections in practice means that
the magnitude of a possible Fermi liquid scale will be
grossly underestimated. However, in the case of strong
non-local fluctuations, as one would expect in 2D problems, such a scale will in general be extremely small or
even zero anyway. Here, the influence of vertex corrections can be expected to be less severe and the NCA even
quantitatively reliable.
Even with these restrictions, the NCA still becomes
formidable as the cluster size Nc increases. The number
of eigenstates and hence number of coupled equations
(155, 157) that have to be solved self-consistently grows
like n [N] imp [c] [, where][ n][imp][ is the number of Fock states of]
the isolated impurity (e.g. nimp = 4 in the Hubbard
model, nimp = 3 in the t-J model). Thus, although the
study of larger clusters is in principle possible, the NCA
technique is very limited in cluster size and so far has
only been applied to Nc = 4 size clusters.


C. Non-perturbative techniques


Non-perturbative techniques solve the effective cluster
problem (numerically) exact. This advantage comes at
the expense that only small cluster sizes can be treated.
The size restriction on the cluster QMC technique described in the following section is basically the same as in
the case of FSS QMC. For the ED and NRG approaches
discussed in the next sections, however, a Hamiltonian
for both the cluster and host degrees of freedom needs to
be explicitly simulated, further limiting the usefulness of
these methods.


1. Quantum Monte Carlo


a. Introduction. Quantum Monte Carlo (QMC) is a
powerful and general technique for quantum cluster problems. QMC has several advantages including the ability
to treat relatively large clusters, the simplicity of the required code, and the fact that only the cluster excluded
Green function G and the coarse-grained interaction U [¯]
are required as inputs. QMC is also numerically exact
with small and controllable sources of systematic and
statistical error. Its disadvantages include the fact that
there is a minus sign problem which is unpredictable,
difficulties in calculating real-frequency results, and the
numerical expense of the approach.
The QMC algorithm for clusters is based on the Hirsch
and Fye algorithm which was developed to simulate the
Anderson impurity problem (Hirsch and Fye, 1986). It



1
Xmm′ ; Xn′n z =
⟨⟨ ⟩⟩ Zc



�+∞

dεe [−][βε] [ρnm(ε)Rm′n′(ε + ω)

−∞



−ρm′n′(ε)Rnm [∗] [(][ε][ −] [ω][)]][,] (159)

where ρnm(ω) = −1/πℑmRnm(ω + iδ� +) is the spectral∞
density of the resolvents, Zc = [�] n −∞ [dεe][−][βε][ρ][nn][(][ε][)]
the cluster partition function and β = 1/T the inverse
temperature.
Although the application of the NCA was illustrated
for the DCA cluster model, the NCA can in principle
also be applied to solve the CDMFT cluster problem,
Eq. (79). The fact that in the CDMFT the hybridization
function Γ is a matrix in the Nc cluster sites however
complicates this task considerably.
One of the great advantages of this resolvent perturbation theory and the NCA as approximation is that it
can be solved for real frequencies, i.e. a cumbersome and
problematic analytic continuation as in the case of QMC
simulations is not necessary. Moreover, one can show
analytically that it can produce a low-energy scale depending non-analytically on the bare model parameters
(M¨uller-Hartmann, 1984) and that certain general features like universality in this energy scale are present,
too (Fischer, 1997). Surprisingly, the NCA is capable
of recovering a variety of complex features in thermodynamic and dynamic quantities of the single impurity
Anderson model at U = ∞ (Bickers, 1987). However it
was realized rather quickly from the numerical solution
of the NCA equations (Grewe, 1983; Kuramoto, 1983) as
well as an approximate analytical treatment at T = 0
(M¨uller-Hartmann, 1984) that the NCA shows serious
deficiencies in its low temperature/low energy behavior. More precisely, it generates unphysical power-law
structures in the low-energy behavior of physical quantities (M¨uller-Hartmann, 1984). Nevertheless there exists a finite window from high down to temperatures
of the order of an effective Fermi liquid scale where
the NCA produces reliable and physically sensible results (Bickers, 1987; Cox and Grewe, 1987; Fischer, 1997;
Pruschke et al., 1993b).
A rather different question is whether these results are
only qualitatively or even quantitatively correct. Here,
the answer critically depends on the system under consideration. Going beyond a single Anderson impurity
grams beyond the lowest order NCA (Bickersat U = ∞ introduces the necessity to include dia- et al., 1987;
Pruschke and Grewe, 1989) to at least ensure a correct
reproduction of energy scales or exactly known limits


�Nl


l=1



31



αγi [∗],l,σ [σs][i][,l][γ][i][,l][−][1][,σ] (162)
σ



was later generalized to solve the DMFT and DCA effective impurity problems by Jarrell (1992) and Jarrell et al.
(2001b), respectively. Although the algorithm is formulated using a path integral in imaginary time, the Maximum Entropy Method may be used to analytically continue the QMC data to obtain real-frequency spectra
(Jarrell and Gubernatis, 1996).
The QMC algorithm uses the action of the effective
cluster model, Eq. (77) as a starting point and therefore can be equally applied within the CDMFT and the
DCA. It thus requires as inputs the initial bare Green
function G, and the form of the coarse-grained interaction [3][ ¯] U . This is an advantage, since due to the required
self-consistency of embedded cluster techniques, we generally do not know the auxiliary parameters of the cluster
Hamiltonian.
Several steps are required to evaluate the path integrals
of this action using QMC. We first introduce HubbardStratonovich (HS) fields required to decouple the interaction, transforming a problem of interacting electrons
and bosons to one of non-interacting particles coupled
to time-dependent HS fields. The fermionic and bosonic
fields are then integrated out, and the integrals over the
decoupling fields are performed with a Monte Carlo algorithm. Measurements of any diagrammatic quantity are
accomplished by decomposing the associated operators
using Wick’s theorem (both connected and disconnected
contractions must be included) and then averaging the
result over the Monte Carlo generated field configurations.


b. QMC for the simple Hubbard Model. As a specific example, we consider the simple Hubbard model with a
local interaction of strength U . Since this interaction
is local, it is unaffected by coarse-graining, so U [¯] = U .
To approximate the time-integrals in the action, we introduce a discrete time grid of length L and time step
∆τ = β/L. The interacting part of the action is then
decoupled by mapping it to an auxiliary Ising field via
a discrete Hirsch-Hubbard-Stratonovich (HHS) transformation (Hirsch, 1983),







�Nc


i=1



whereii′ (τl l denotes the time sliceτl′ ) the cluster excluded Green function defined τl and G(i, l; i [′], l [′] ) ≡
G in Eq. (76). Now we integrate out the remaining cluster Grassmann variables. The partition function then
becomes




   Z ∝ D[γ]D[γ [∗] ]e [−][S][c][[][γ,γ][∗][]]




  = T r{si,l}




   - �−1
det Gcσ;si,l (163)
σ



e [−][∆][τU][ �] i [(][n][i][↑][−][1][/][2)(][n][i][↓][−][1][/][2)]




[1]

2 [e][−][∆][τU/][4][ �]



e [αs][i][(][n][i][↑][−][n][i][↓][)], (160)

si=±1







= [1]



where factors which are fixed during the QMC process
have been ignored. �Gcσ;sil �−1 is the inverse cluster
Green function matrix with elements

   - �−1
Gcσ;sil i,j,l,l [′][ =][ G] i,j,l,l [−][1] [′][ −] [δ][i,j][δ][l][′][,l][−][1][ασs][i,l][ .] (164)


A Monte Carlo algorithm is used to perform the remaining integral over the HHS fields. The Markov
process in this algorithm proceeds by suggesting local
changes of the HHS fields at one point in space-time.
These changes are accepted or rejected according to the
change in their Boltzmann weight, the argument of the
trace in Eq. (163). If the change is accepted, the Green
function must be updated accordingly. Several approximations, i.e. changes to these equations that are beyond
linear order in ∆τ, are necessary to obtain an efficient
algorithm. First, we re-exponentiate the first term on
the right-hand side of Eq. (164), obtaining in a simple
matrix notation in space-time

              -               Gc−σ 1 = T e [V][σ] 1, (165)
G [−][1]           -           
where T is δi,jδl−1,l′ and Vσ(i, l) αsi,lσ. Note that the
≡
term in the parenthesis is beyond zeroth order in ∆τ .
Therefore, to first order in ∆τ, we may write

           - ��            Gc−σ 1 = + 1 e [V][σ] 1, (166)
G [−][1] G [−][1]         -         
since G [−][1] - 1 = −T + O(∆τ ). Therefore, the inverse
Green functions for two different field configurations,
{sil} and {s [′] il [}][, are related by]

Gc′σ −1e−Vσ [′] = Gc−σ 1 [e][−][V][σ][ −] [e][−][V][σ][ +][ e][−][V] σ [ ′] . (167)


Or, after multiplying by e [V] σ [ ′], and collecting terms


Gc′σ −1 Gc−σ 1 = (Gc−σ 1 1)e [−][V][σ] (e [V] σ [ ′] e [V][σ] ) . (168)
     -     -     
Multiplying from the left by Gc and from the right by
Gc′, we find


Gc′σ [=][ G][c] σ [+ (][G][c] σ σ [−][V][σ] 1)Gc′σ (169)

[−] [1)(][e][V][ ′]                      
or

GcσGc′σ −1 = 1 + (1 Gcσ)(eVσ [′] [−][V][σ] 1) . (170)
           -           


i



where cosh(α) = e [∆][τU/][2] and the index i denotes the
cluster sites. With this change, the cluster action takes
the form

   Sc[γ, γ [∗] ] = γi,l,σ [∗] [G][−][1][(][i, l][;][ i][′][, l][′][)][γ][i][′][,l][′][,σ] [(161)]

i,l;i [′],l [′],σ


3 It is also possible to treat the interaction in a self-consistent
manner, as was described in (Hettler et al., 2000)


The QMC algorithm proposes changes in the Hubbardcepts these changes with the transition probabilityStratonovich field configuration {si,l} →{s [′] i,l [}][, and ac-] Ps→s′ .
Thus, to implement the algorithm, we need Ps→s′ and a
relation between the cluster Green functions Gc and Gc′

for the two different auxiliary field configurations. To
simplify the notation, we introduce a combined spacetime index i = (i, l), and consider only local changes
in the fieldsfrom Eq. (163), the probability of a configuration sm → s [′] m [=][ −][s][m][.] As can be inferredsi
−1 −1 { }
is Ps det(Gc↑{si} [) det(][G][c] ↓{si} [);][ 4][ on the other hand]
∝
detailed balance requires Ps [′] Ps [′] →s = PsPs→s [′] for all s [′] .
We may satisfy this requirement either by defining the
transition probability Ps [′] →s = R/(1 + R), where



′ ′
↑ [) det(][G][c] ↓ [)]

R (171)
≡ P [P] s [s] ′ [= det(] det( [G] G [c] c↑) det(Gc↓)



32


c. Measurements. Several points must be considered
when making measurements in the QMC procedure.
First, for a given configuration of the HHS fields, the
problem is non-interacting. Thus, the estimators of any
correlation function may be constructed by taking all allowed Wick’s contractions (both connected and disconnected). Therefore, any quantity which may be represented in terms of the Green functions (and perhaps the
HHS fields themselves), may be measured. Second, great
care must be taken when constructing the estimators of
the measurements. Different estimators may yield different results due the systematic and statistical error in the
QMC procedure. It is important to choose the optimal
form of the estimator of each measurement, and then use
all the prior knowledge (exact limits, symmetries, etc.)
that we have to reduce the error.
For example, one difficulty encountered with the QMC
algorithm is that a reliable transform from imaginarytime quantities to Matsubara frequencies is required. A
careful treatment of the frequency summation or the
imaginary-time integration is crucial in order to ensure
the accuracy and the stability of the algorithm and
to maintain the correct high-frequency behavior of the
Green function. We need to evaluate the following integral

         - β
Gc(K, iωn) = dτe [iω][n][τ] Gc(K, τ ) . (174)

0


But from the QMC, we know the function Gc(K, τ ) only
at a discrete subset of the interval [0, β]. As may be readily seen by discretizing the above equation, the estimation
of Gc(K, iωn) becomes inaccurate at high-frequencies.
This is formalized by Nyquist’s theorem which tells us
that above the frequency ωc = ∆πτ [unpredictable results]
are produced by conventional quadrature techniques. For
example, a rectangular approximation to the integral in
Eq. (174) yields a Gc(K, iωn) that is periodic in ωn. This
presents a difficulty since causality requires that


1
lim . (175)
ωn→∞ [G][c][(][K][, iω][n][) =] iωn


This problem may be avoided by using the high frequency information from other sources. For example, the
second-order perturbation theory result, Eq. (141) has
the correct asymptotic behavior. Alternatively, we can
use the Green function from the previous iteration which
has the correct high frequency behavior. We then compute the Matsubara-frequency Green function from the
imaginary-time QMC Green function as (Jarrell et al.,
1993)


Gc(K, iωn) = Gc,pt(K, iωn) + (176)

       - β

dτe [iω][n][τ] (Gc(K, τ ) Gc,pt(K, τ )) .
0           

where Gc,pt is any Green function with the correct highfrequency behavior. The integral is computed by first



is the relative weight of two configurations, or by setting
Ps′→s = minimum(R, 1). The first choice is called the
“heat bath” algorithm, and the second the “Metropolis”
algorithm which is generally, but not always, superior. If
the difference between two configuration is due to a flip of
a single Hubbard Stratonovich field at the mth location in
the cluster space-time (Hirsch and Fye, 1986), we obtain
from Eq. (170)

  R = [1 + (1 Gcσ,mm)(e [−][ασ][(][s][m][−][s] m [′] [)] 1)] [−][1] . (172)

        -        σ


For either the Metropolis or the heat bath algorithm, if
the change is accepted, we must update the Green function accordingly. The relationship between Gc and Gc′

is given by Eq. (169)


Gc′σ,ij [=][ G][c] σ,ij

(Gcσ,im δim)(e [−][ασ][(][s][m] [−][s] m [′] [)] 1)
+   -   - (173)
1 + (1 Gcσ,mm)(e [−][ασ][(][s][m][−][s][′][m][)] 1) [G][cσ,mj][ .]
        -        
The QMC procedure is initialized by setting Gcσ,ij =
ij, and choosing the corresponding field configuration
G
with all si = 0. Then we use Eq. (173) to create a
Green function corresponding to a meaningful field configuration (i.e. si = ±1, for each i = (i, l) or the {si}
from a previous run or iteration) and proceed by stepping through the space-time of the cluster, proposing local changesgreater than a random number between zero and one and si →−si. We accept the change if Ps [′] →s is
update the Green function according to Eq. (173). After
roughly one hundred warm-up sweeps through the spacetime lattice of the cluster, the system generally comes
into equilibrium and we begin to make measurements.


4 If Ps is not positive definite, then |Ps| is used as the sampling
weight, and its sign is appended to the measurement. I.e. for a
measurement m and sign S, ⟨m⟩P = ⟨mS⟩|P | / ⟨S⟩|P |.


interpolating the difference Gc(K, τ ) Gc,pt(K, τ ) us               ing an Akima spline, and then integrating the spline
(a technique often called oversampling). The smooth
Akima spline suppresses spurious high frequency behavior so that Gc(K, iωn) = Gc,pt(K, iωn) when ωn ωc.
The resulting self-energy, extracted from Σc(K, iω ≫n) =
1/ (K, iωn) 1/Gc(K, iωn) is still not accurate at high
G  frequencies since it reflects either the perturbation theory or the previous iteration. However, the exact high
frequency form is known. Thus, we can fit the high frequency self energy, at frequencies at or below the Nyquist
cutoff π/(∆τ ), to the form

Σc(K, iωn) ≈ a(K)/(iωn) + b(K)/ωn [2] [.] (177)

In some cases a and b are known exactly. We may
then append this form onto the self-energy at frequencies higher than π/(∆τ ).


2. Exact diagonalization


The Lanczos ED method (Haydock et al., 1975) provides a numerical way to diagonalize the Hamiltonian of
a finite size system. Since the cluster model in the CPT
formalism is identical to the model of a finite size system
with open boundary conditions, the regular Lanczos ED
method can be applied in this case without modification
(S´en´echal et al., 2000). For the cluster model of embedded cluster theories however, it needs to be generalized
to account for the self-consistent coupling to the host.
ED has been used to solve the impurity problem of the
DMFT (Caffarel and Krauth, 1994; Si et al., 1994). It
is natural that it can be extended to be used as a cluster solver in quantum cluster theories. This was demonstrated by Bolech et al. (2003) in an application of the
CDMFT to the 1D Hubbard model. The general method
of exact diagonalization (Haydock et al., 1975) need not
be reviewed here. We only outline the specific implementation necessary for a cluster theory.
ED is a wave function based method, i.e. it is applied
to diagonalize the effective cluster Hamiltonian, e.g. the
Hamiltonian in Eq. (79). To this end, the hybridization
function Γ(z) (see Eq. (78)) is fitted to the form

  Γij (z) = Vil(k [˜] )[z 1   - λ(k [˜] )] [−] lm [1][V] mj [ ∗] [(˜][k][)][,] (178)

lm,k [˜]


to obtain estimates for the auxiliary parameters of the
host, λij (k [˜] ) and Vij (k [˜] ). In order to apply ED to the
cluster Hamiltonian, the auxiliary host degrees of freedom, i.e. the sum over k [˜], must be discretized to a finite
set of Nh orbitals. Applying ED to the resulting Hamiltonian, one can then compute a cluster self-energy Σ [c]

(Caffarel and Krauth, 1994), and from the cluster selfenergy a new estimate of the coarse grained Green function G [¯] to close the self-consistency loop.
The Hilbert space of the resulting Hamiltonian increases exponentially with the cluster size Nc and the



33


number of wave-vectors Nh representing the host. For
ED to be feasible, the total number of ”sites” N =
Nc + Nh must be of the order of N ∼ 20. Furthermore,
for the distinction of the lattice into cluster and host to
make sense, Nh Nc. This size limitation is possibly
prohibitive for anything but 1D systems. Moreover, by ≥
applying ED to solve the cluster model one abandons
the thermodynamic limit, i.e. one of the advantages of
cluster mean-field theories. Still, ED is an exact method
and can deal with more complicated interactions than
the simple on-site Hubbard repulsion, as exemplified in
Bolech et al. (2003), where nearest neighbor interactions
were considered.


3. Wilson’s numerical renormalization group


Over the past ten years, Wilson’s numerical renormalization group (NRG) (Krishnamurthy et al., 1980a,b;
Wilson, 1975) has become a major computational tool to
study quantum impurity problems. Its advantages are
that it is (i) non-perturbative, (ii) can handle exponentially small energy scales with unprecedented accuracy
and (iii) does not suffer from any principle limitations
regarding the parameter space of the model. In addition,
through the inspection of the flow of the spectrum of the
Hamiltonian under the renormalization group transformation, the method provides direct very detailed information about the structure of the low-energy spectrum.
Originally, its application was limited to static quantities (Krishnamurthy et al., 1980a,b; Wilson, 1975),
but the calculation of dynamical properties is also
possible (for a comprehensive overview of the early
work see e.g. Hewson, 1993) and thus its application
to the DMFT impurity problem (Sakai and Kuramoto,
1994; Shimizu and Sakai, 1995). The direct calculation of the one-particle self-energy from the NRG
(Bulla et al., 1998) triggered a variety of applications
within the DMFT framework (Bulla, 1999; Bulla et al.,
2001; Pruschke et al., 2000; Pruschke and Zitzler, 2003;
Zitzler et al., 2002, 2003) at both T = 0 and finite temperatures.


Figure 11 Schematic setup of the NRG. The energy axis is
partitioned into exponentially decreasing intervals.


Given this tremendous success, the obvious question is
if one can extend the NRG to become useful for quan


![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-32-0.png)
tum cluster problems. Let us therefore briefly repeat the
basic steps in the NRG scheme. The procedure starts by
picking a number Λ > 1 and an interval on the energy
axis that contains the support of the density of states of
the bath degrees of freedom. As depicted in Fig. 11 this
interval is then partitioned into exponentially decreasing intervals ]Λ [−][(][n][+1)], Λ [−][n] ] for ǫ > 0 with n = 0, 1, . . .;
likewise for ǫ < 0. Within each interval, a Fourier decomposition of the bath operators is performed; the fundamental approximation of the NRG consists of neglecting
all Fourier components except for the homogeneous one.
After tri-diagonalization, the resulting Hamiltonian reads



34

temperature scales ∝ √Λ [−][N] . This exponential decrease

of successive energy scales explains why the NRG is suitable for studies of problems with extremely small dynamical energy scales. This however comes at the price of a
loss of accuracy in high energy features (Hewson, 1993).
Up to now the discussion was restricted to spin degeneracy only. However, it is obvious that additional degrees
of freedom do not influence the general lines of argument.
In fact, for a problem with L ≥ 1 internal degrees of freedom in addition to the spin (like cluster sites or several
orbitals per site), the result (179) acquires the form



HQI ≈ HImp + (179)



HQI ≈ HImp + (181)



+








- ε [l] n [a][†] nlσ [a] nlσ [+][ t] n [l] −1 [a][†] n−1lσ [a] nlσ [+ h.c.]



�∞



�L



l=1



�∞




- εna [†] nσ [a] nσ [+][ t][n][−][1][a] n [†] −1σ [a] nσ [+ h.c.]




 +



n=1



σ



σ



n=1



where HImp denotes the Hamiltonian of the “impurity”
and the operators a [(] nσ [†][)] [represent the bath degrees of]
freedom. Note that the Hamiltonian (179) represents
a semi-infinite chain with the impurity at its left end.
Wilson (1975) showed that the quantities tn Λ [−][n/][2] . If
t¯n = √Λ [n] tn and ¯εn = √Λ [n] εn, one can cast the Hamil- ∝



Λ [n] tn and ¯εn = √



t¯n = Λ [n] tn and ¯εn = Λ [n] εn, one can cast the Hamil
tonian into a recurrency form




 Λ H [¯] N +



H¯N +1 = √



(180)



where HImp is again of arbitrary structure. Likewise,
the recurrency relation (180) can be set up and the algorithm extended. However, a simple example demonstrates that for L > 1 the technique can easily become
useless. For a typical application to the single impurity Anderson model (SIAM) one chooses a Λ = 2 and
NNRG = 1000. This is sufficient to obtain very accurate results for all relevant physical quantities. Let us
now consider the next step, i.e. an orbitally degenerate
problem with L = 2. Without coupling between the orbitals, this corresponds to two independent SIAM we try
to solve in a single calculation. Obviously, to obtain the
same accuracy as in the true single impurity case, one
needs at least NNRG = 1000 [2] or Λ = 2 [2] (for a more detailed discussion of the issue of the accuracy of the NRG
see Paula et al. (1999) and references therein).
While NNRG = 1000 [2] is beyond all numerical possibilities, a strongly increasing Λ introduces a huge
loss in accuracy, both at high and low energies
(Oliveira and Oliveira, 1994). As long as L = 2 the
problem can be partially compensated by respecting the
additional symmetries in the system (Sakai et al., 1989)
or other numerical tricks (Oliveira and Oliveira, 1994).
However, as a generic tool to solve the effective quantum
cluster problem arising in embedded cluster techniques
much larger values of L must be accessible. Thus, while
for a study of qualitative effects of non-local correlations
with Nc = 2 the NRG is still applicable (see results in
section IV.D.1), the preceding discussion makes it clear
that already for Nc = 4 the method is currently not feasible.


IV. APPLICATIONS TO STRONGLY CORRELATED
MODELS


In this section we review the application of various
quantum cluster approaches to a selection of standard
models of strongly correlated electron systems. We put
special emphasis on the capabilities and advantages of
these techniques over both finite system simulations and




 +


σ




- t¯N a [†] Nσ [a] N +1σ [+ h.c.] .



ε¯N +1a [†] N +1σ [a] N +1σ
σ



Given the eigenvalues and eigenvectors of H [¯] N, H [¯] N +1 can
be constructed straightforwardly. Since at each of these
steps the dimension of the Hilbert space increases by a
factor of four, the practical use would be limited even
more severely as conventional exact diagonalization, because the construction of H [¯] N +1 requires the knowledge
of theHowever, the multiplication of whole set of eigenvectors and eigenvalues of H [¯] N with √Λ > 1 expandsH [¯] N .

the bandwidth of the spectrum and, because t [¯] N = O(1),
the low energy properties of H [¯] N +1 are determined by a
restricted set of low-lying states of H [¯] N only. This observation is put into a practical computational scheme by
the following algorithm: (i) At step N ≥ 0 (N = 0 corresponds to HImp), diagonalize H [¯] N and calculate all interesting local properties for that particular chain length.
(ii) Use a suitable number NNRG of the lowest eigenstates
of H [¯] N to construct the next Hamiltonian H [¯] N +1 according to (180). (iii) Continue with (i) until the desired
accuracy for the ground state is reached. Note that step
(ii) ensures that, no matter how long the chain becomes,
the dimension of the Hamilton matrix to diagonalize can
be fixed to a manageable number.
As was discussed extensively in the literature (Hewson,
1993; Krishnamurthy et al., 1980a,b; Wilson, 1975), the
knowledge of the local properties at chain length N provides a means to calculate physical interesting quantities
(thermodynamics and dynamics) at energy respectively


35



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-34-0.png)

τ/β



DMFT. In Sec. IV.A we show that quantum cluster approaches are complementary to FSS, i.e. that taken together the information obtained from both techniques
can yield conclusive results. The effects of non-local correlations on single- and two-particle spectra as well as
phase diagrams are emphasized throughout the discussions of the Falicov-Kimball model in Sec. IV.B, the 1D
Hubbard model in Sec. IV.C and the 2D Hubbard model
in Sec. IV.D. Due to space restrictions we have to omit
recent applications of the CPT and DCA to electronphonon systems and refer the reader to the articles by
Hohenadler et al. (2003) and Hague (2003), respectively.


A. Complementarity of finite size and quantum cluster
simulations


FSS and quantum cluster approaches yield exact solutions in the infinite cluster size limit. At finite cluster size
Nc quantum cluster approaches differ from FSS by the
coupling to a self-consistent dynamic host. At cluster size
Nc = 1 this difference is most pronounced: While FSS
reduce to the atomic limit, quantum cluster approaches
reduce to the DMFT, i.e. a highly non-trivial approximation to the infinite size lattice. Thus it is instructive
to compare quantum cluster results with those obtained
from FSS systematically as a function of cluster size.
This has been done in the half-filled 2D Hubbard model
using the DCA/QMC algorithm, i.e. DCA combined
with QMC as a cluster solver, by Huscroft et al. (2001)
and Moukouri and Jarrell (2001) and with DCA/FLEX
by Aryanpour et al. (2003a).
In the 2D Hubbard model at half-filling, the antiferromagnetic correlation length ζ increases with decreasing
temperature and diverges at T = 0. In FSS, i.e. in
a finite size lattice with periodic boundary conditions,
the system freezes when the correlation length exceeds
the system size and a gap to excitations opens. As the
system size is increased this tendency is reduced. Correlation induced gaps are thus generally overestimated in
FSS for smaller clusters since the system is artificially
closer to criticality. In contrast, in quantum cluster approaches the system is in the thermodynamic limit with
correlations restricted to the cluster size. Hence the system never freezes. As the cluster size is increased, longer
ranged correlations are progressively included. The effects of correlations therefore increase with cluster size.
This behavior is illustrated in Fig. 12, where we
reproduce the results obtained from DCA/QMC and
FSS/QMC simulations for the imaginary time Green
function G(k, τ ) at the Fermi wave-vector k = (π, 0)
for different cluster sizes Nc. This quantity has a more
rapid decay from its maximum at τ = β/2 when correlation effects are stronger so the gap is more pronounced.
With increasing cluster size, the DCA and FSS results
for G(k, τ ) converge from opposite directions. Consistent
with the expectation that correlation effects are overestimated in FSS but underestimated in the DCA, the decay



0.0


−0.1


−0.2


−0.3


−0.4


−0.5





Figure 12 The imaginary time Green function G(k, τ ) at
k = (π, 0) in the half-filled 2D Hubbard model, calculated with finite size QMC (filled symbols) and DCA
(empty symbols) when U = 4.4t and β = 4/t. Taken
from Moukouri and Jarrell (2001). See also Aryanpour et al.
(2003a).


-0.32



-0.34


-0.36


-0.38



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-34-1.png)



-0.4


2
1/L


Figure 13 The imaginary time Green function G(k, τ ) at k =
(π, 0), τ = β/2 in the half-filled 2D Hubbard model, calculated
with FSS/FLEX (circles) and DCA/FLEX (squares) when
U = 1.57t for various cluster sizes Nc = L×L). Both methods
scale as 1/L [2] and converge to a single value as L →∞. Taken
from Aryanpour et al. (2003a).


is stronger for smaller system sizes in FSS, while the DCA
results show the opposite behavior. Since the two techniques become identical in the infinite cluster size limit,
the exact G(k, τ ) curve is bracketed by the FSS and DCA
curves. For methods like the FLEX (see Sec. III.B.2) for
which calculations with much larger clusters are feasible, scaling of the results to the infinite system is possible (see Fig. 13). The extrapolations of FSS/FLEX and
DCA/FLEX to the infinite system (1/L [2] → 0) coincide
within numerical uncertainties, thus allowing the determination of the infinite lattice result with unprecedented
accuracy.
This complementarity is also seen in results for the
spectral gap in the 2D half-filled Hubbard model (see
Huscroft et al., 2001 and Aryanpour et al., 2003a). In


the DCA the gaps converge from small to large as the
cluster size increases, while the converse occurs in FSS.
Although we have only shown results of the DCA, we expect the CDMFT to show similar size dependence, since
DCA and CDMFT share the same nature of the approximation (see discussion in Sec. II.C). Results obtained
with the CPT algorithm however can be viewed to some
extent as a periodic continuation of FSS. Thus it is an
open question if the CPT method shows similar complementarity.


B. 2D Falicov-Kimball model


The usefulness of the discussed cluster theories was
first demonstrated by the application of the DCA to the
2D FKM by Hettler et al. (2000, 1998). While the FKM
is a particularly gentle test bed for novel approaches, it
allows the study of the effects of non-local fluctuations.
The FKM can be considered as a simplified Hubbard
model in which one spin species has zero hopping amplitude. The Hamiltonian reads




- 
d [†] i [d][j][ +][ U]
<i,j> i




  H = −t



i (n [d] i [−] 2 [1]



2 [1] [)(][n] i [f] [−] [1] 2



(182)
2 [)][,]



36


within the DCA by a combination of QMC methods and
exact enumeration for small clusters. Since the DMFT
is a single-site theory (Nc = 1), it yields an unphysical
temperature-independent DOS of the mobile d-electrons
(Brandt and Mielsch, 1989) due to the constraint of half
filling (one electron per site of either the d or f variety). In a cluster theory with Nc > 1 this artifact is
absent, since a redistribution of Boltzmann weight with
temperature is possible among the various configurations
of d or f electrons on the cluster sites, while maintaining the condition of half filling on average. This temperature dependence is demonstrated in Fig. 14, where
a pseudogap develops in the local DOS with decreasing
temperature. This pseudogap can be interpreted as a
precursor of the eventual transition to a CDW phase,
which features a full gap at the Fermi level. In addition
to the gap, there is fine structure in the DOS, related to
an exchange energy Jeff . This is better observed in the
momentum resolved spectral function (see Hettler et al.,
2000; Laad and van den Bossche, 2000).
As stated above, the FKM has an instability to a phase
with CDW order. As discussed in Sec. I.B, embedded
cluster theories exhibit phase transitions at some temperature that, due to their residual mean-field character, lies above the exact Tc of the infinite system. As
the cluster size increases, one expects the effect of the
mean-field to decrease, leading to a decreasing Tc with
increasing cluster size. The Nc dependence of the transition temperature Tc is shown in Fig. 15, together with
a comparison with the Tc obtained from FSS methods
(de Vries et al., 1993a,b, 1994) and Tc of the 2D Ising
model with exchange coupling J = 1/(2U ).The extrapolated cluster results agree with the FSS estimates and,
for large values of U, also with the results obtained from
the 2D Ising model. For smaller U however, charge fluctuations begin to play a larger role, suppressing the Tc
compared to that of the Ising model which lacks charge
fluctuations.
The effect of different boundary conditions in the DCA
cluster is illustrated in the inset [5] . In small clusters the
effect is strong, but already in a 6 × 6- cluster the bulk of
the cluster dominates and the boundaries play a minor
role.
When Nc = 1 only charge fluctuations with an energy scale U are present. In a cluster theory the nonlocal “spin” fluctuations with an effective energy scale
Jeff (∝ 1/2U for large U ) must also be observable in
thermodynamic quantities like the entropy and the specific heat. In Hettler et al. (2000) the entropy and specific heat was computed from the total energy of the
cluster via a maximum-entropy method (Huscroft et al.,
2000). For better comparison, the calculations were per

5 According to the derivation of the DCA formalism (see Secs. II.A,
II.B and Fig. 3) the DCA cluster has periodic boundary conditions. By shifting the set of cluster K-points however, different
boundary conditions can be simulated.



with n [d] i [=][ d] i [†][d] i [and][ n] i [f] [=][ f][ †] i [f] i [. For a 2D square lattice]
the bandwidth of the noninteracting system is W = 8t.
At half filling and D ≥ 2 the system has a second order phase transition from a homogeneous high temperature phase to a charge density wave with ordering vector Q = (π, π) for any nonzero U (Brandt and Schmidt,
1986, 1987). The universality class is that of the 2D
FKM. In HettlerIsing model, the strong coupling limit et al. (2000) the FKM was evaluated U/t ≫ 1 of the


0.20



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-35-0.png)



0.15


0.10


0.05


0.00





−6 −4 −2 0 2 4 6
**Frequency** ω



Figure 14 DOS of the 2D FKM for a 4 × 4–cluster at various temperatures calculated with DCA. The DOS develops
a pseudogap as the temperature approaches Tc 0.189t
≈
(U = 4t) due to the non-local CDW fluctuations present in
the DCA (Nc > 1). In the DMFT (Nc = 1), there is no T –
dependence of the DOS above Tc. Figure from Hettler et al.
(2000).


37



0.35


0.3


0.25


0.2


0.15


0.1


0.05



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-36-0.png)

0 0.2 0.4 0.6
**Inverse Linear Dimension 1/L**











![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-36-1.png)





3


2


1



0





Figure 15 Tc in the 2D FKM as a function of the inverse linear
cluster size for U/t = 8, 12, 16 calculated with DCA. The
Ising limit, and FSS estimates of Tc are shown for comparison.
The inset shows that the influence of the cluster boundary
conditions on Tc disappears rapidly with increasing cluster
size. Figure from Hettler et al. (2000).


formed in the uniform phase, even at temperatures below
the CDW ordering Tc by not allowing for the symmetry
breaking. The results for a 2 × 2- cluster are shown in
Fig. 16, where the ratio of specific heat C over the temperature T is plotted for the DMFT and the DCA on a
2 × 2- cluster. The appearance of the a second peak at
lower temperature is a clear indication for the additional
non-local fluctuations present on the cluster. The effect
on the entropy is also strong, as shown in the inset.


C. 1D Hubbard model


In this section we discuss the application of quantum
cluster approaches to the 1D Hubbard model (in usual
notation)



0.01 0.10 1.00 10.00 100.00
T




- 
(c [†] i+1σ [c] iσ [+][ h.c.][) +][ U]
i,σ i




 H = −t



ni↑ni↓, (183)
i



Figure 16 Specific heat versus temperature for single site and
2 × 2- clusters calculated with DCA and exact enumeration
when U = 8t. For Nc = 1, there is a single peak with integrated weight ln(2) associated with the suppression of local charge fluctuations. For Nc = 4, there is an additional
peak at lower temperatures associated with critical fluctuations near the charge ordering transition temperature. Tc for
Nc = 4 is indicated by an arrow. In the inset the entropy
S(T ) = �0T [dT][ ′][ C] T [(][T][′][ ′][)] is shown in units of ln(2). Figure from

Hettler et al. (2000).


the results with those obtained from the DMFT and
DMRG approaches. As an example of this study we show
in Fig. 17 a comparison of the exact result with that obtained from DMFT (referred to as LISA for “Local Impurity Self-consistent Approximation”) and CDMFT for
the single-particle spectral gap ∆(U ) as a function of the
on-site Coulomb repulsion U in the half-filled case. The
total number of sites in the effective cluster model including cluster and bath sites was fixed to six in the ED
approach (see Sec. III.C.2).


Figure 17 Spectral gap in the half-filled 1D Hubbard model as
a function of U/t calculated with DMFT (LISA) and CDMFT
for a 2-site cluster, Nc = 2 compared to the exact result.
Taken from Bolech et al. (2003).



which provides a non-trivial test ground for these techniques. In 1D quantum fluctuations are stronger than in
higher dimensions. Hence quantum cluster approaches
which cut off correlations beyond the length-scale set
by the cluster size are expected to be less efficient than
in higher dimensions. Therefore if quantum cluster approaches accurately describe the physics in 1D, they are
highly likely to capture the physics in 2D and 3D. In
addition, since the exact ground-state of the 1D Hubbard model is known from the Bethe ansatz solution
(Lieb and Wu, 1968), a quantitative comparison of certain static quantities is possible. Fairly reliable results
for dynamical quantities can be obtained from the density matrix renormalization method.
Bolech et al. (2003) applied the CDMFT/ED method
to the 1D Hubbard model and systematically compared



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-36-2.png)
The behavior of the cluster results (CDMFT for Nc =
2) is fundamentally different from the single-impurity result (LISA, Nc = 1): When Nc = 1, the spectral gap is
reduced to values much smaller than the exact value and
even vanishes at finite U . The existence of this Motttransition in 1D for Nc = 1 is a well known artifact
of the DMFT method, reflecting the physics of infinite
dimensions where the Mott-transition is indeed present
(Georges et al., 1996). In contrast, the Nc = 2 result
follows the exact result quite accurately yielding an insulating solution for all finite values of U > 0 in agreement with the well known physics of the 1D model. This
excellent reproduction of the exact gap for Nc = 2 is
quite encouraging since larger cluster sizes should produce even better results. And indeed, a comparison of
the nearest neighbor Green function with DMRG results
shows systematic improvements with increasing cluster
size (Bolech et al., 2003).
A related fundamental feature in 1D correlated systems is the breakdown of the Fermi-liquid picture because of spin-charge separation as described in the concept of Luttinger-liquids (see e.g. Voit, 1994). In a Fermiliquid, the spectral weight A(k, ω) is centered around a
single quasiparticle peak at ω = ǫk, while in a Luttingerliquid, A(k, ω) is distributed between two singularities
associated respectively with spin- and charge-excitations
(spinons and holons). S´en´echal et al. (2000) have calculated A(k, ω) in the 1D Hubbard model using the CPT
formalism. Fig. 18 shows a comparison of this quantity
at the Fermi wave-vector k = π/2 as calculated by ordinary ED and its infinite lattice extension within the CPT
method for various cluster sizes N when U = 8t (bottom)
and U = 16t (top).


Figure 18 The spectral function A(k, ω) at k = π/2 in the
half-filled 1D Hubbard model when U = 16t (top) and U = 8t
(bottom), calculated with ordinary ED and with CPT for
cluster sizes N = 4, 8, 12. Taken from S´en´echal et al. (2000).


While no sign of spin-charge separation is seen in
the pure ED results, the CPT method reveals the two



38


branches of the spectral weight indicative of spin-charge
separation. The two-peak structure resolves more clearly
as the cluster size increases. Since propagation between
clusters requires the spinon and holon to recombine, spincharge separation can only exist on length- and timescales limited by the cluster size. Consequently it takes
fairly large clusters to clearly resolve this feature.


Figure 19 The spectral function A(k, ω) in the half-filled 1D
Hubbard model when U = 4t, calculated with CPT for Nc =
12. Taken from (S´en´echal et al., 2000).


The analysis of the k-dependent spectral function in
Fig. 19 reveals the dispersion of the two branches. The
spinon- and holon-branches show different dispersions
and can be clearly identified together with the gap at
the chemical potential at k = π/2. These T = 0 simulations were extended to finite low temperatures T > 0
by Aichhorn et al. (2003) who implemented a novel lowtemperature Lanzcos algorithm which connects the exact ground-state Lanczos method with the established finite temperature Lanzcos method (Jakliˇc and Prelovˇsek,
2000). They showed that the spin-charge separation observed in the T = 0 results persists at finite, low temperatures.


As exemplified by these studies, quantum cluster approaches have been proven very useful to explore the
complex behavior of the 1D Hubbard model. Even studies with small cluster sizes are consistent with well-known
results such as the opening of a Mott gap at half-filling
for all U > 0 and the existence of spin-charge separation
reflected in the two branches in the electronic dispersion.
This success in the 1D case shows great promise for applications of cluster methods in 2D or 3D where cluster
methods are expected to be even more efficient since correlations are less pronounced.



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-37-0.png)

![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-37-1.png)
D. 2D Hubbard model


The interest in the 2D Hubbard model (in usual notation)




- 
tijc [†] iσ [c] jσ [+][ U]
ij,σ i




 H =



ni↑ni↓ (184)
i



39


antiferromagnetic ordering at T = 0 is merely the result
of the Mott-transition at higher temperatures.
Different scenarios however exist for the weak-coupling
regime (U ≪ W ): In the weak coupling point of view, a
spin density wave forms at T = 0 due to the nesting of the
Fermi surface and leads to the doubling of the unit cell.
Hence the gap in the spectrum is a direct consequence
of the antiferromagnetism at T = 0. This perturbative
point of view is referred to as Slater mechanism. It is in
contrast to the second opinion due to Anderson (1997a,b)
who has argued that the 2D half-filled Hubbard model is
always in the strong-coupling regime, so that a Mott gap
is present for all U > 0 as in 1D (see Sec. IV.C). As the
temperature decreases, local moments develop because of
the opening of the Mott gap which then order at T = 0.
Thus the antiferromagnet at T = 0 is a consequence of
the Mott transition.
The MIT in the half-filled Hubbard model has been
extensively studied within the DMFT (for a review see
Georges et al., 1996). In the DMFT one can easily disentangle the effects leading to antiferromagnetic and
Mott gaps. The DMFT equations for the paramagnetic state of the bipartite Bethe lattice are identical
with the equations of the fully frustrated infinite dimensional model (Georges et al., 1996). This justifies the
study of the paramagnetic solution within the antiferromagnetic phase of the unfrustrated model which shows
a first order Mott MIT ending at a finite temperature
critical point (Georges et al., 1996). Although this justification does not hold for Nc > 1, one can still study
the paramagnetic solution by enforcing the spin symmetry and hence avoiding the opening of a full spectral
gap due entirely to magnetic ordering. Following this
approach, Moukouri and Jarrell (2001) studied the MIT
in the unfrustrated 2D half-filled Hubbard model using
DCA/QMC systematically as a function of cluster size
Nc. The MIT can be identified by analyzing the behavior of the double occupancy D = n↑n↓ . This quantity
⟨ ⟩ ⟨ ⟩
is shown in Fig. 20 for different values of the Coulomb
repulsion U and cluster size Nc.
When Nc = 1 the double occupancy displays evidence
for a MIT when U is of the order of the bandwidth
W = 8t = 2: ⟨D⟩ is monotonically increasing with
temperature when U = 3, but displays a minimum for
U = 0.5 and 1 indicating the emergence of quasiparticle states at the chemical potential at low temperatures.
When Nc > 1 the situation is radically different: In the
strong coupling regime (U = 3), local fluctuations dominate and ⟨D⟩ is essentially independent of Nc except at
very low temperatures. In contrast, in the weak coupling
regime, the minimum found for Nc = 1 flattens progressively asdownturn in Nc ⟨ increases from 8 to 16. WhenD⟩ appears at low temperatures. By open- Nc ≥ 36 a
ing a gap and hence localizing the moments, the system
can gain free energy by taking advantage of the shortranged magnetic correlations.
The results for the DOS shown in Fig. 21 support
the evidence from the double occupancy. The quasi


has been revived recently in particular since it is believed
to capture the physics of the superconducting planes in
high-temperature superconductors (HTSC) (Anderson,
1997b; Zhang and Rice, 1988, 1990). This section reviews various applications of quantum cluster approaches
to the 2D Hubbard model at half-filling and at finite doping, including results for a possible Mott-Hubbard transition, antiferromagnetism and its precursors, pseudogap
phenomena and superconductivity.


1. Metal-insulator transition


The study of a possible metal-insulator transition
(MIT) in the 2D Hubbard model at half-filling (ǫo =
tii = −U/2) is under active research. This problem
was studied in the unfrustrated model, i.e. with only
nearest neighbor hopping tij = ǫoδij tδ⟨ij⟩ within
DCA/QMC by Moukouri and Jarrell (2001) and with the −
two-site composite operator method (see Sec. II.H) by
Stanescu and Phillips (2001). The frustrated case (additional next-nearest neighbor hopping t [′] δ⟨⟨ij⟩⟩) was investigated by Parcollet et al. (2003).
Numerical calculations have shown that the ground
state of the unfrustrated model is an antiferromagnetic
insulator with the N´eel temperature TN = 0 constrained
by the Mermin-Wagner theorem. A spectral gap hence
exists at T = 0. However the central question about the
origin of the gap and its relation to antiferromagnetic ordering is less understood. Is the gap a direct consequence
of the antiferromagnetic ordering at T = 0 or does it arise
from strong correlations at higher temperatures?
To appreciate the significance of this issue it is important to understand the fundamental difference between
antiferromagnetic insulators, i.e. insulators due to magnetic ordering and Mott insulators, i.e. insulators due to
electronic correlations. Antiferromagnetic insulators result from the doubling of the unit cell in the ordered state
and are therefore adiabatically connected to band insulators which have an even number of electrons per unit
cell. In contrast, paramagnetic Mott insulators have an
odd number of electrons per unit cell and are therefore
fundamentally different from band insulators.
At strong coupling (U ≫ W ) the situation is well understood: A charge gap of order U develops in the spectrum below temperatures T ≈ U due entirely to strong
electronic correlations. The spins are coupled by the exchange interaction J = 4t [2] /U and govern the low-energy
physics. As a result spin and charge are separated. Systems in this regime are hence Mott insulators and the


40



0.25


0.2


0.15


0.1


0.05


0


|k<br>y<br>K<br>M<br>π<br>k’<br>k<br>M<br>0<br>k<br>x<br>1. BZ|Col2|
|---|---|
|M<br>0<br>k’<br>1. BZ<br>k|k’<br>k|



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-39-0.png)

0 0.2 0.4 0.6 0.8 1
T

























Figure 20 Double occupancy as a function of temperature
for different values of U in the half-filled 2D Hubbard model
calculated with DCA/QMC for various cluster sizes Nc. Here,
t = 0.25, so the lines for U = 0.5, 1, 2 correspond to U/t =
2, 4, 12. Taken from Moukouri and Jarrell (2001).



0.8

0.4

0

0.8

0.4

0

0.8

0.4

0

0.8

0.4

0



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-39-1.png)









−3 −2 −1 0 1 2 3
ω



Figure 21 DOS when U/t = 4 for different temperatures in
the half-filled 2D Hubbard model calculated with DCA/QMC
for various cluster sizes Nc. Taken from Moukouri and Jarrell
(2001).


particle Kondo-like resonance at the chemical potential
for Nc = 1 is destroyed by non-local correlations when
Nc > 1. As Nc increases, a gap opens at the chemical
potential and the Hubbard sidebands become more pronounced consistent with the suppression of ⟨D⟩. Given
the fact that DCA always underestimates correlation induced spectral gaps (see Sec. IV.A), these simulations
indicate the absence of a weak-coupling regime in the
unfrustrated 2D Hubbard model at half-filling consistent
with Anderson’s point of view.
Another interesting aspect is whether this result
changes at zero temperature, T = 0 and the MIT predicted by DMFT returns. As evidence that even at
T = 0 one must expect a gap in the spectra for any
U > 0, we show here first DCA results at T = 0 obtained with Wilson’s NRG for a cluster size of Nc = 2.



Figure 22 Tiling of the first Brillouin zone for Nc = 2.


The appropriate tiling of the Brillouin zone is shown in
Fig. 22 and the resulting coarse-grained spectral functions A [¯] (K, w) = − π [1] [ℑ][m][ ¯][G][(][K][, w][) for the two cluster][ K][-]

points are shown in Fig. 23. Even for small values of U


Figure 23 DCA coarse-grained spectral functions for different
values of U obtained from Nc = 2 DCA/NRG calculations at
T = 0. Apparently, no finite critical value of U for a conventional Mott-Hubbard transition seems to exist. In contrast,
for all U > 0 a gap exists at the Fermi energy.


a well defined gap exists in the spectrum at the Fermi
energy. Note that all calculations were done in the paramagnetic phase, i.e. the concept of a Slater insulator does
not apply here. The gap quickly increases with increasing
U and at the same time the system gains more spectral
weight in the incoherent parts of the spectrum, i.e. begins
to resemble what one expects from Mott localized states.
The DCA results were confirmed in a similar cluster
study by Stanescu and Phillips (2001) using the two-site
composite operator method discussed in Sec. II.H. Figure
24 shows the results of this study for the temperature dependence of the value of the DOS at the chemical potential, ρ(0) in the 1D and 2D models for small U = 2t. As
a consequence of the shape of the non-interacting DOS,
the 2D result for ρ(0) is enhanced over the 1D result.
However, in both 1D and 2D, ρ(0) falls to zero as the
temperature decreases indicating the absence of a metal


![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-39-2.png)
0.2


0.15


0.1


0.05



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-40-0.png)







0

T / t


Figure 24 DOS as a function of temperature at the chemical
potential in the 1D and 2D half-filled Hubbard model when
U = 2t calculated with a two-site composite operator approximation. Taken from Stanescu and Phillips (2001).


lic state at half-filling even for small U .
To elucidate the role of antiferromagnetic correlations
in the opening of the Mott gap, the frustrated Hubbard model may be studied. In the t-t [′] Hubbard model,
a next-nearest neighbor hopping t [′] between sub-lattices
strongly frustrates antiferromagnetic correlations. This
model was studied by Parcollet et al. (2003) for t [′] = t on
a 2 × 2 cluster using CDMFT/QMC. We reproduce their
results for the U dependence of the double occupancy
docc = 1/4 [�][4] i=1 [⟨][n][i][↑][n][i][↓][⟩] [for different temperatures in]
Fig. 25. Similar to the behavior found in DMFT, docc
displays a downturn at a critical value Uc, indicating a
transition from a metallic to an insulating state. An inspection of the spectral weight A(k, 0) at the chemical
potential reveals that the gap opens first in the region
around k = (π, 0) (Parcollet et al., 2003). These results


Figure 25 Double occupancy as a function of U in the frustrated 2D Hubbard model with t [′] = t for different temperatures (from top to bottom) T/t = 1/5, 4/30, 1/10, 1/11, calculated with CDMFT/QMC. Taken from Parcollet et al. (2003).


were substantiated by a CPT study of the frustrated



41


2D Hubbard model (S´en´echal and Tremblay, 2003) for
t [′] = −0.4t. Although not the focus of this study, the
results show further evidence of a Mott transition at a
finite value of U in the filling dependence of the chemical
potential.
The existence of the Mott transition in the frustrated
Hubbard model and its absence in the unfrustrated model
seems to indicate that antiferromagnetic correlations play
a key role in the opening of a Mott gap at weak coupling.
Since the opening of the gap occurs in the paramagnetic
solution, it cannot be attributed to the existence of antiferromagnetic ordering. Thus the conclusion reached
from these cluster studies is that a symbiosis of local moment formation and short-ranged antiferromagnetic correlations cause the gap to open at finite temperatures
(Moukouri and Jarrell, 2001).


2. Antiferromagnetism and precursors


If the simulations are performed without enforcing the
spin symmetry or frustrating the lattice, the system is
given the possibility to transform to a state with antiferromagnetic order. Since the system is two-dimensional,
we know from the Mermin-Wagner theorem that the true
N´eel temperature TN is necessarily zero. As found in infinite dimensions (Jarrell et al., 1993), the DMFT predicts a finite temperature transition even in 2D due to
its mean-field character. As discussed in Sec. I.B, cluster approaches restore non-local fluctuations and thus are
expected to drive the N´eel temperature systematically to
zero as the cluster size increases.
As discussed in Secs. II.F and II.E, phase transitions
can be identified from the disordered (here: paramagnetic) state by calculating the corresponding susceptibility, or from the ordered state by computing the order
parameter. The calculation of order parameters is exemplified in Fig. 26 where we plot the DCA/NCA result for
the sub-lattice magnetization m = 1/N [�] i,σ [e][i][Q][·][x][i] [σn][iσ]
(see Eq. (110)) as a function of the reduced temperature
t = T/TN in the 2D half-filled Hubbard model for the
cluster sizes Nc = 1 and Nc = 4 when U = 4t. The
Nc = 4 N´eel temperature TN = 0.208t is reduced from
the Nc = 1 result TN = 0.304t and the order parameter is strongly suppressed. As expected, non-local spin
fluctuations suppress antiferromagnetism.
Figure 27 shows the DCA/QMC result for the temperature dependence of the inverse antiferromagnetic susceptibility 1/χAF at U = 6t for various cluster sizes Nc
in the paramagnetic state. At high temperatures the
susceptibility is independent of Nc due to the lack of
non-local fluctuations. In contrast to FSS, the low temperature susceptibility diverges at T = TN indicating the
instability to the antiferromagnetic state. When Nc = 1
the susceptibility diverges with a critical exponent γ ≈ 1
as expected for a mean-field theory. Consistent with the
NCA results the susceptibility diverges at lower temperatures when Nc > 1 with larger exponents indicative of



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-40-1.png)
![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-41-0.png)

Figure 26 Sublattice magnetization as a function of temperature in the half-filled 2D Hubbard model calculated with
DCA/NCA for cluster sizes Nc = 1, 4 when U = 4t. Inset:
Ne´el-temperature versus doping. Taken from Maier (2001).


fluctuation effects. However as discussed in Sec. I.B these
critical exponents reflect the behavior at intermediate
temperatures. Very close to the transition, there must
a region of mean-field behavior. However, this region is
very difficult to resolve with DCA/QMC, due to numerical noise, which is especially large near the transition.


0.5



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-41-1.png)



0.4


0.3


0.2


0.1





0


T



Figure 27 Inverse antiferromagnetic susceptibility versus temperature in the half-filled 2D Hubbard model calculated with
DCA/QMC for various cluster sizes Nc when U = 6t. The
lines are fits to the function (T − TN) [γ] . Inset: Corresponding
Ne´el-temperatures as a function of the cluster size. Taken
from Jarrell et al. (2001b).


As shown in the inset, the transition temperatures fall
very slowly with the cluster size Nc, but the Nc = 4
falls off the curve. As detailed in Sec. II.C.4, fluctuation effects in clusters with linear size L = 2 are overproportionally enhanced since its coordination number
is reduced compared to the original system. Hence the
Nc = 4 result does not fall on the curve, similar to the
behavior seen in DCA studies of the FKM (Hettler et al.,
2000).
The question arises of whether the same non-local fluc


42


tuations which are responsible for suppressing the antiferromagnetism result in precursers of the antiferromagnetic phase transition. The onset of antiferromagnetic correlations on short time- and length-scales may
be signaled by a pseudogap in the DOS as a precursor to the antiferromagnetic gap. This was predicted
by Kampf and Schrieffer (1990) using a phenomenological ansatz for the weak coupling Hubbard model
based on the presence of strong antiferromagnetic spinfluctuations. On a microscopic level, this question has
been addressed by FSS/QMC in the 2D Hubbard model
in Vekic and White (1993) and Creffield et al. (1995) and
by approximate many-body techniques in Deisz et al.
(1996) and Moukouri et al. (1999). But the results have
been inconclusive as to the existence of a pseudogap at
low temperatures, due to the limitations of these techniques.
Within quantum cluster approaches the pseudogap
phenomenon was first studied by Maier et al. (2000b)
within the DCA/NCA formalism. In contrast to Nc = 1
where a Kondo-like quasiparticle peak emerges at the
chemical potential as the temperature is decreased (reminiscent of the D = ∞ DMFT result (Georges et al.,
1996)), a pseudogap was found when non-local correlations were included in Nc = 4 simulations. For larger


and imaginaryFigure 28 Spectral functionous temperatures at ℑmΣ( kk = (, ω) parts of the self-energy for vari-π, A 0) in the 2D half-filled Hubbard(k, ω) and the real ℜeΣ(k, ω)
model for U = 5.2t calculated with DCA/QMC for a 64-site
cluster (Nc = 64). Taken from Huscroft et al. (2001).


cluster sizes, the emergence of the pseudogap in the DOS
was explored by DCA/QMC in Huscroft et al. (2001) and
DCA/FLEX in Aryanpour et al. (2003a). Figure 28 displays the DCA/QMC results for the spectral function
A(k, ω) and the self-energy Σ(k, ω) at the Fermi wavevector k = (π, 0) in the paramagnetic state for a 64-site
cluster (Nc = 64) at various temperatures. With decreasing temperature a pseudogap develops in A(k, ω) at the
Fermi wave-vector k = (π, 0). Simultaneously the slope
of ℜeΣ(k, 0) becomes positive at k = (π, 0) signaling



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-41-2.png)
the appearance of two new solutions in the quasiparticle
equation ω − ǫk + µ −ℜeΣ(k, ω) = 0. In addition to the
strongly damped solution at ω = 0 which is also present
in the non-interacting system these two new quasiparticle
solutions appear on both sides of ω = 0. A consequence
of the antiferromagnetic order on short time- and lengthscales, they can be viewed as precursers of the doubling
of the unit cell in the antiferromagnetic state. The pseudogap is generated by the local minimum in ℑmΣ(k, ω)
which signals the breakdown of Fermi-liquid behavior.
By studying the system on a triangular lattice,
Imai and Kawakami (2002) investigated the effects of
frustration on the pseudogap in the half-filled 2D Hubbard model using the DCA/NCA and DCA/FLEX approaches. Figure 29 schematically illustrates the triangular lattice and the choice of cluster wave-vectors in the
corresponding Brillouin zone for Nc = 4.


Figure 29 Illustration of the triangular lattice with hopping
amplitudes t and t [′] (a) and DCA coarse-graining cells (b) in
the first Brillouin zone (dashed line) of the triangular lattice
when Nc = 4. Cluster K-points are indicated by the dots.
Taken from Imai and Kawakami (2002).


For t [′] = 0 this setup corresponds to the unfrustrated
system and the effects of frustration can be systematically studied as t [′] is increased to its maximal value
t [′] = t. Figure 30 reproduces the results for the DOS
and coarse-grained spectra A [¯] (K, ω) for different values
of the frustration t [′] . As the geometrical frustration increases from t [′] = 0 to t [′] = t, antiferromagnetic spin fluctuations are suppressed. Consequntly the pseudogap in
the unfrustrated system diminishes and a quasiparticle
peak develops at the chemical potential. The change in
the DOS mainly originates in the region in momentum
space around K = (π, π/√3) where the Fermi surface is

located. These results are thus consistent with an antiferromagnetic spin fluctuation driven pseudogap.


3. Pseudogap at finite doping


The properties of the Hubbard model away from halffilling are of great interest especially in the context of
HTSC. Contrary to Fermi-liquid theory, low-energy spinexcitations in HTSC are suppressed at low temperatures
as evidenced by Knight-shift experiments. Concomitantly, the Fermi surface is gapped along certain directions in the Brillouin zone as indicated in ARPES experi


43


Figure 30 The DOS (a) and coarse-grained single-particle
spectral functions A¯(K, ω) in the 2D half-filled frustrated
Hubbard model for K = (0, 0) (b), K = (π, π/√3) (c) and

K = (0, 2π/√3) (d) for various values of the frustration t [′]

when U = 6t and T = 0.6t. Taken from Imai and Kawakami
(2002).


ments. This pseudogap phenomenon [6] has proven a great
challenge for theories of strongly correlated systems.
DMFT has provided great insight into the evolution
of spectra in doped Mott-insulators. Exact results based
on the self-consistent mapping onto an Anderson impurity model show that the system is a Fermi-liquid in
the metallic state in the absence of symmetry breaking below a coherence temperature reminiscent of the
Kondo-temperature (Georges and Kotliar, 1992). Hence
the spin-susceptibility becomes finite at low temperatures
in contrast to the experimental results in underdoped
cuprates. Furthermore M¨uller-Hartmann (1989a) showed
that because the self-energy is momentum independent,
volume and shape of the Fermi surface are identical to
the non-interacting Fermi-surface. Thus DMFT does not
include the effects that lead to the emergence of a pseudogap in the spin- and quasiparticle spectrum and cluster
extensions are necessary.
Within quantum cluster approaches the pseudogap
phenomenon in the doped 2D Hubbard model was studied with DCA/NCA in Maier et al. (2000b) and Maier
(2001), with DCA/QMC in Jarrell et al. (2001a) and
Maier et al. (2002a), with the two-site composite operator method in Stanescu and Phillips (2003a,b) and with
the CPT in S´en´echal and Tremblay (2003).
Figure 31 shows the DCA/NCA result for the lowenergy DOS in the 2D Hubbard model at 5% doping
(δ = 0.05) around the chemical potential (ω = 0) cal

6 For a review on the pseudogap phenomenon see
Timusk and Statt (1999).



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-42-0.png)

![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-42-1.png)
44



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-43-0.png)

ω



culated on a 4-site cluster (Nc = 4). At high temperature T > 0.3t no pseudogap is seen in the DOS. As the
temperature is lowered the DOS distorts at the chemical potential and a pseudogap emerges at ω = 0 when
T ≲ 0.3t.


Figure 31 DOS for various temperatures in the 2D Hubbard
model at 5% doping when U = 12t near the chemical potential
(ω = 0) calculated with DCA/NCA for a 4-site cluster, Nc =
4. Taken from Maier (2001).


These perturbative results [7] were confirmed in
DCA/QMC simulations by Jarrell et al. (2001a) which
we reproduce in Fig. 32. At low temperatures a pseudogap is observed in the DOS at dopings δ ≲ 0.2. This depression of quasiparticle states at the chemical potential
is accompanied by a downturn of the uniform magnetic
susceptibility shown in the inset. For low to intermediate
doping it develops a maximum defining a crossover temperature T [∗] . Below T [∗] quasiparticle and low-energy spin
excitations are suppressed by non-local correlations similar to what is observed in the experiment. At the same
time, the charge susceptibility (not shown) displays qualitatively different behavior forming a strong low-energy
peak at low temperatures (see Maier et al., 2004, 2002a
and Fig. 38) which signals the emergence of coherent
charge excitations below T [∗] . The Nc = 4 DCA results
are thus consistent with a spin-charge separated picture
as in Anderson’s RVB theory. This is not surprising since,
as we discussed in Sec. IV.D.2, fluctuations are enhanced
in the Nc = 4 cluster due to the “too small” coordination
number. It is known that small coordination numbers
favor the spin-charge separated RVB state (Anderson,


7 The NCA is perturbative in the coupling to the host, not in the
interaction, as detailed in Sec. III.B.3.



Figure 32 DOS for various dopings δ in the 2D Hubbard
model at T = 0.092t and U = 8t calculated with DCA/QMC
for a 4-site cluster, Nc = 4. Inset: Uniform spin-susceptibility
as a function of temperature. Taken from Jarrell et al.
(2001a).


1987) over the N´eel state. Indeed the RVB state was
shown to be the ground state of a 2×2 Heisenberg model
with periodic boundary conditions with a large gap to
the first excited state (Dagotto and Moreo, 1988).


Figure 33 The spectral function A(k, ω) near the chemical
potential in the 2D Hubbard model at T = 0.088t and U =
8t along high-symmetry directions in the first Brillouin-zone
between Γ = (0, 0), X = (π, 0) and M = (π, π) calculated
with DCA/QMC for a 4-site cluster Nc = 4.


The corresponding 4-site DCA/QMC result for the momentum resolved spectral function A(k, ω) in the pseudogap regime is displayed in Fig. 33 for energies near
the chemical potential between points of high symmetry



1


0.8


0.6


0.4


0.2


0











![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-43-1.png)

![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-43-2.png)
Γ = (0, 0), X = (π, 0) and M = (π, π) in the first Brillouin zone. The overall dispersion of the band crossing
the chemical potential ω = 0 follows that of the noninteracting system ǫk. While coherent quasiparticles exist along Γ → M, the pseudogap is seen near X = (π, 0) at
the chemical potential ω = 0. The anisotropy of the pseudogap is thus consistent with that observed in ARPES
measurements on underdoped hole-doped cuprates.
Qualitatively similar results for the emergence of the
quasiparticle spectrum in the doped 2D Hubbard model
were obtained by Stanescu and Phillips (2003b) using
the two-site composite operator approach discussed in
Sec. II.H (see also Stanescu and Phillips, 2003a). Figure
34 illustrates their results for the doping dependence of
the chemical potential µ, the imaginary part of the selfenergy ℑmΣ and the U dependence of the low-energy
DOS. At half-filling the chemical potential has a dis


8


6


4


2


0



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-44-1.png)



















Filling n



Figure 34 The doping dependence of the chemical potential in
the 2D Hubbard model calculated with the two-site composite
operator method for T = 0.15t (dashed line) and T = 0.07t
(solid line). Right inset: DOS for various values of U at 5%
doping (n = 0.95). Left inset: Imaginary part of the selfenergy evaluated at a Fermi momentum (0.3,2.10) for n =
0.97, (0.3,1.84) for n = 0.80 and (0.3,1.06) for n = 0.3. Taken
from Stanescu and Phillips (2003b).


continuity indicating the absence of mid-gap states. In
agreement with DCA/QMC (Jarrell et al., 2001a,b) and
DCA/NCA (Maier, 2001) results, |ℑmΣ| is large in the
underdoped pseudogap regime (n = 0.97) and acquires
Fermi-liquid behavior at larger doping n ≤ 0.80 indicated
by the parabolic minimum at the chemical potential. As
illustrated in the inset, the depth of the pseudogap decreases as U increases suggesting a pseudogap scale compatible with t [2] /U .
S´en´echal and Tremblay (2003) recently investigated
the difference in pseudogap behavior between electron
and hole doped HTSC using CPT for the 2D t − t [′] - t [′′]

Hubbard model. As illustrated in the Fermi-surface plots
in Fig. 35, their results at U = 8t demonstrate that the
pseudogap in hole-doped systems (right side) occurs near
X = (π, 0) at optimal doping consistent with the results



45


discussed above. In electron-doped systems (left side)
however, the pseudogap appears at the crossing points
of the Fermi surface with the antiferromagnetic Brillouin
zone boundary at moderate interaction U = 4t. When U
is large however (not shown), the Fermi surface only survives in the neighborhood of (π, 0) and (0, π). As shown
in the lower panels of Fig. 35 the pseudogap in both cases
is generated by a large scattering rate |ℑmΣ(k, 0)| at
the chemical potential. A unified picture of the spectral


Figure 35 Intensity plot of the spectral function A(k, 0) (top)
and imaginary part of the self-energy ℑmΣ(k, 0) (bottom) of
the 2D Hubbard model calculated with CPT on a 3 × 4-site
cluster. The left side shows the results in the first quadrant
of the Brillouin zone for the 17% electron-doped system at
U = 4t and the right side for the 17% hole-doped system at
U = 8t. Taken from S´en´echal and Tremblay (2003).


properties of the electron- and hole-doped cuprates thus
emerges from these results if the interaction strength U
is allowed to be doping dependent. To reproduce the
experimental observations in optimally doped cuprates,
large values of U seem necessary in hole-doped (U ≈ 8t)
systems, while smaller values of U describe the electrondoped systems (U ≲ 6t) (S´en´echal and Tremblay, 2003).


4. Superconductivity


FSS QMC simulations for the doped 2D Hubbard
model in the intermediate coupling regime U ∼ W support the idea of a spin-fluctuation driven interaction
mediating d-wave superconductivity (for a review see
Scalapino, 1999). However the fermion sign problem limits these calculations to temperatures too high to study
a possible transition. These calculations are also restricted to relatively small system sizes, making statements for the thermodynamic limit problematic, and inhibiting studies of the low-energy physics. These shortcomings do not apply to embedded cluster theories which



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-44-0.png)
are built for the thermodynamic limit. Cluster sizes
larger than one are necessary however, to describe a possible transition to a state with a non-local (d-wave) order
parameter as discussed in Sec. II.E.
It is well known from weak coupling FSS FLEX results (Bickers et al., 1989) and phenomenological theories
(Monthoux et al., 1991; Scalapino, 1999) that antiferromagnetic spin-fluctuations mediate pairing with d-wave
symmetry and cause a pseudogap in underdoped systems.
In optimally doped cuprates, these spin-fluctuations are
known to be short-ranged, extending over a few lattice spacings. Hence quantum cluster approaches should
provide an adequate methodology to study superconductivity in these systems. Pairing in the 2D Hubbard model was studied using DCA/NCA by Maier et al.
(2000a), and with DCA/QMC by Jarrell et al. (2001a,b)
and Maier et al. (2004). The possible coexistence of superconductivity with antiferromagnetic order was investigated by Lichtenstein and Katsnelson (2000).
The results of 4-site (Nc = 4) DCA simulations for
the doped 2D Hubbard model show an instability to a
superconducting phase with a dx2−y2-wave order parameter at low enough temperatures. As a typical example
of this transition, Fig. 36 shows the DCA/NCA result
for the DOS and the coarse-grained anomalous Green
function G [¯] 12(K, ω) F (K, ω) defined in Eq. (95) at
≡ [¯]
different cluster K-points near the chemical potential in
the superconducting state. G¯12(K, ω) vanishes at the


Figure 36 DOS near the chemical potential (a) and coarsegrained anomalous Green function G [¯] 12(K, ω) ≡ F [¯] (K, ω) for
different DCA cells (b-c) in the superconducting state of the
2D Hubbard model at 19% doping, T = 0.047t, U = 12t
calculated with DCA/NCA for a 4-site cluster, Nc = 4. Taken
from Maier et al. (2000a).


cluster K = (0, 0) and (π, π) but is finite at (π, 0) and
(0, π) with opposite signs. Since the K-dependence of the
coarse-grained order parameter ∆ [¯] K is given by the Kdependence of the coarse-grained anomalous Green function (see Eq. (99)), this result is consistent with a dx2−y2 symmetry of the order parameter. The finite pair ampli


46


tude is also reflected in the DOS depicted in the upper
left part where the lower subband of the full spectrum
is shown. It displays the superconducting pseudogap at
zero frequency as expected for a d-wave order parameter.
Jarrell et al. (2001a,b) used DCA/QMC to search for
many different types of superconductivity, including s, extended s-, p- and d-wave, of both even and odd
frequency. Of these, only the odd-frequency s-wave
and even-frequency d-wave pair-field susceptibilities were
strongly enhanced, and only the d-wave susceptibility diverged. This is illustrated in Fig. 37 where the pair-field



2


1.5


1


0.5



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-45-0.png)











0


T



Figure 37 Pair-field susceptibilities versus temperature in the
even frequency s-wave, extended s-wave (xs), d-dave and oddfrequency s-wave channels in the 2D Hubbard model at 5%
doping, U = 8t calculated with DCA/QMC for a 4-site cluster, Nc = 4. Inset: Inverse d-wave pair-field susceptibility versus temperature for different dopings and cluster sizes. The
line is a fit to b(T − Tc) [γ] with Tc = 0.084t and γ = 0.72.
Taken from Jarrell et al. (2001a).


susceptibilities are plotted versus temperature at 5% doping. The behavior of the inverse d-wave pair-field susceptibility as a function of temperature for Nc = 1 and 4 and
δ = 0 and 0.5 is shown in the inset. For Nc = 1 there
is no tendency towards pairing. As detailed in Sec. II.E,
the DMFT is not able to describe pairing with symmetries lower than the lattice symmetry (i.e., p-, d-wave,
etc.). For Nc = 4 and δ = 0 the inverse susceptibility rises abruptly as the temperature is lowered and the
Mott gap opens in the DOS. The Mott gap becomes more
pronounced as Nc increases (see Sec. IV.D.1), so that for
larger clusters the gap prevents superconductivity even
for U < W . If charge excitations are gapped, then pairing is suppressed. At half-filling, for U = 8t the gap
is of order U, and thus much larger than the magnetic
exchange energy J ∼ 4t [2] /U = 0.5t. Hence the opening
of the Mott gap suppresses any magnetically mediated
pairing. Away from half-filling the width of the pseudogap in the charge excitation spectrum is much smaller,
of the order of J (see Sec. IV.D.3), so that magnetically
mediated pairing is possible.



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-45-1.png)
More insight in the nature of pairing was gained from
further DCA/QMC studies of the 2D Hubbard model
(Maier et al., 2004). Figure 38 shows the DCA/QMC re


47


energies, Tr(tG) and Tr(ΣG) respectively, of the superconducting (SC) and normal state (NS) solution as a
function of temperature at low doping δ = 0.05 (left) and
optimal doping δ = 0.20 (right). For both doping levels,



1.2


1


0.8


0.6


0.4


0.2


0



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-46-0.png)

-0.4 -0.2 0 0.2 0.4

ω [eV]



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-46-1.png)

0 0.2 0.4 0.6 0.8 1

ω [eV]



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-46-2.png)

0 0.2 0.4 0.6 0.8 1

ω [eV]









![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-46-3.png)

![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-46-5.png)

0 0.01 0.02 0.03 0.04



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-46-4.png)

![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-46-6.png)

0 0.01 0.02 0.03 0.04

T







30


25


20


15


10


5


0



0.6


0.5


0.4


0.3


0.2


0.1


0



-0.270

-0.272

-0.274

-0.276

-0.278


-0.380

-0.382

-0.384

-0.386

-0.388







Figure 38 DOS (left), local dynamic spin susceptibility (center) and local dynamic charge susceptibility (right) in the 2D
Hubbard model at 5% doping at different temperatures above
and below the critical temperature Tc = 0.0218 = 0.087t calculated with DCA/QMC for a 4-site cluster, Nc = 4. Taken
from Maier et al. (2004).


sult for the evolution of the DOS, the local dynamic spinand local dynamic charge-susceptibility [8] as the temperature decreases below the critical temperature Tc. As discussed in Sec. IV.D.3, the normal state low-temperature
DOS and spin-susceptibility display a pseudogap, i.e. a
depression of low-energy quasiparticle and spin excitations. Both quantities evolve smoothly across the superconducting transition with the pseudogap changing to
a superconducting gap [9] below Tc. However since the
charge susceptibility is peaked at zero frequency even
slightly above Tc, it changes abruptly upon pairing to
show the same behavior as the spin-susceptibility, including the superconducting gap at low frequencies. Remarkably, well below Tc all quantities display narrow peaks at
ω ≈ 0.1eV, delimiting the superconducting gap. This result clearly indicates the formation of quasiparticles below Tc. The absence of quasiparticles in the normal state
however undermines the very foundation of the BCS theory of conventional superconductors where pairing is a
result of a Fermi surface instability that relies on the
existence of quasiparticles in a Fermi-liquid (Schrieffer,
1993).
DCA/QMC results for the condensation energy further
establish the unconventional character of superconductivity in the 2D Hubbard model (Maier et al., 2004). Figure 39 presents the kinetic (top) and potential (bottom)


8 Note that in the DCA, local quantities are identical in the lattice
and on the cluster and thus are easily calculated.
9 Note that due to the finite resolution in momentum space, the
DCA underestimates low-energy spectral weight in superconductors where the gap has nodes on the Fermi surface. As a result,
a fully developed gap is found at low temperatures instead of a
DOS that vanishes linearly in frequency as expected for a d-wave
superconductor.



Figure 39 Kinetic (top) and potential (bottom) energies versus temperature in the normal (NS) and superconducting
(SC) states in the 2D Hubbard model at 5% (left) and 20%
(right) doping for U = 8t. Tc is indicated by the vertical
dotted lines. Taken from Maier et al. (2004).


the kinetic energy in the superconducting state is reduced
compared to the normal state, while the potential energies are almost identical. This result is in agreement with
recent optical experiments which show that the superconducting transition in the cuprates is due to a lowering of
the electronic kinetic energy (Molegraaf et al., 2002). It
further supports the evidence that pairing in the Hubbard model is fundamentally different from BCS pairing
which occurs through a reduction of the electronic potential energy accompanied by a slight increase in the
kinetic energy.


The possibility of coexisting d-wave superconducting
and antiferromagnetic order in the 2D Hubbard model
was investigated by Lichtenstein and Katsnelson (2000)
using a 4-site cluster approach similar to the DCA/QMC
method (see Fig. 40(a)). In this approach, an 8 × 8
matrix representation of the Green function is required
to account for both the antiferromagnetic order parameter ⟨c [†] i↑ [c] j↓ [⟩] [and the superconducting order parameter]
ci↓cj↑ . Figure 40(c) reproduces the results for the two
⟨ ⟩
order parameters as a function of doping at fixed temperature in the weak coupling regime (U = 4.8t). The
authors find that the antiferromagnetic order parameter
coexists with the d-wave superconducting order parameter over a wide range of doping. Consistent with the
DCA/QMC results, the antiferromagnetic order parameter is maximal at zero doping where the superconducting
order parameter vanishes due to the opening of the gap.





-0.306

-0.308

-0.310

-0.312

-0.314


-0.244

-0.246

-0.248

-0.250

-0.252





T


48


|3 2<br>0 1|Col2|Col3|Col4|(a)|
|---|---|---|---|---|
|||∆<br>QMC||DMFT|
||−∆||−∆||
|||∆|||
||||||



![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-47-3.png)

δ







![](.figures/arxiv__cond-mat-0404055/cond-mat-0404055.pdf-47-0.png)









T( [K] )





















M



0.6


0.4







0.1


0.08


0.06


0.04


0.02


0





F(0)
0.04


0.02



0.2















Figure 40 (a) Schematic representation of an antiferromagnetic d-wave 2 × 2 periodically repeated cluster. (b) Generic
phase diagram of HTSC. (c) Magnetic (M) and d-wave superconducting (F) order parameters versus hole-doping in the
2D Hubbard model at βt = 15, t [′] = −0.15t, U = 4.8t calculated with a 4-site cluster approach similar to the DCA/QMC.
Taken from Lichtenstein and Katsnelson (2000).


5. Phase diagram


The results reviewed in the preceding sections illustrate that quantum cluster approaches applied to the 2D
Hubbard model are able to capture the complex behavior observed in HTSC. The qualitative agreement with
experiments is summarized in the Nc = 4 DCA/QMC
temperature-doping (T -δ) phase diagram of the 2D Hubbard model in the intermediate coupling regime U = W
shown in Fig. 41. The phase boundaries were determined
by the instabilities of the paramagnetic phase as indicated by the divergence of the corresponding susceptibilities. Therefore these results do not allow any conclusions about a possible coexistence of the antiferromagnetic and d-wave superconducting phases for δ < 0.5.
The results by Lichtenstein and Katsnelson (2000) however suggest this coexistence at least for weak coupling
(see Fig. 40(c)).
The pseudogap crossover temperature T [∗] determined
by the peak in the uniform spin susceptibility (see
Fig. 32) serves as a boundary separating the observed
Fermi liquid and non-Fermi liquid behavior. For T < T [∗]

the self-energy shows non-Fermi liquid character for the
parts on the Fermi surface near k = (π, 0) (see Fig. 34).
Quasiparticle and low-energy spin excitations are suppressed as indicated by the pseudogap in the DOS and
the spin-susceptibility (see Fig. 38). At δ ≳ 0.2 Fermiliquid behavior is recovered (see Fig. 34). At low temperatures, the systems is antiferromagnetic near half-filling.
The d-wave superconducting phase at finite doping has
its maximum transition temperature at δ ≈ 0.05.
As indicated in Sec. IV.D.3, the Nc = 4 DCA cluster
favors the spin-charge separated RVB state. The Nc = 4
results may thus be interpreted within the RVB picture
(Anderson, 1987): The pairing of spins in singlets below the crossover temperature T [∗] results in the suppression of low-energy spin excitations and consequently in



Figure 41 Temperature-doping phase diagram of the 2D Hubbard model when U = 8t calculated with DCA/QMC for a
4-site cluster, Nc = 4. The error bars on T [∗] result from
the difficulty in locating the maximum in the uniform spin
susceptibility. Regions of antiferromagnetism, d-wave superconducting and pseudogap behavior are seen.


a pseudogap in the density of states. Charge excitations
are quasi-free as indicated by the zero-frequency peak in
the charge susceptibility (see Fig. 38). Well below the
transition spin and charge degrees of freedom recombine,
forming electrons which pair. Frustrated kinetic energy
is recovered as indicated by the reduction of the kinetic
energy as the system goes superconducting (see Fig. 39).
Although the properties of HTSC are well described
by the Nc = 4 results, it is important to ask the question whether the phase diagram and in particular the
observed RVB nature of the results are stable when the
cluster size is increased. While the pseudogap temperature T [∗] may be expected to persist with increasing
Nc, the transition temperatures to the antiferromagnetic
and superconducting state are expected to fall to zero,
as discussed in Sec. I.B (see also Fig. 27). This has
been confirmed through simulations of larger clusters
(Jarrell et al., 2004). A finite inter-planar coupling between an infinite set of Hubbard planes may then be used
to stabilize the transitions at larger Nc, at least to the antiferromagnetic state (Jarrell et al., 2001b). The stability
of the RVB behavior and even the superconductivity is
less clear and more complex models may be necessary for
them to persist in larger clusters.


6. Studies of related models


a. Stripes in the t-J-model. Several numerical studies
indicate that there is a tendency for doped holes to
form stripes separated by antiferromagnetic domains in
strongly correlated systems (for a review see Dagotto,
1994). CPT is the quantum cluster method of choice
to study the large unit cells in the inhomogeneous stripe
phase, which complicate if not preclude the application of


the numerically more expensive embedded cluster techniques (CDMFT, DCA). A thorough study of stripes
in the large U limit of the Hubbard model, the t-J
model, was conducted by Zacher et al. (2002a,b) within
the CPT. To implement the CPT for this problem, the
authors divided the lattice into alternating clusters of
metallic stripes and antiferromagnetic domains. The
inter-cluster hopping linking these clusters was treated
perturbatively within the CPT. The enforced stripe pattern in this implementation prohibits to explore the stability of stripes, but allows to investigate the effects of the
stripe pattern on the single-particle excitations. In systems with less than 12% doping the technique was shown
to reproduce salient ARPES features in selected HTSC
if a site-centered 3+1 stripe pattern, i.e. half-filled antiferromagnetic three-leg ladders separated by doped oneleg chains, was chosen (Zacher et al., 2002b). At higher
dopings the comparison with ARPES indicates that the
weight of bond-centered stripes with a 2+2 pattern increases in which excess holes proliferate out of the stripes
into the antiferromagnetic domain (Zacher et al., 2002a).


b. Spectral properties of the three-band Hubbard model. In
the context of HTSC, the single-band Hubbard model can
be viewed as a low-energy approximation of the more
complex and more realistic three-band Hubbard model
(Emery, 1987; Emery and Reiter, 1988). The three-band
Hubbard model takes into account the px and py oxygen
orbitals in addition to the Cu d degrees of freedom in
the superconducting CuO2 planes. The CPT study of
its spectral properties by Dahnken et al. (2002) shows
very good agreement with ARPES data on HTSC at halffilling as well as in the doped system including a holelike Fermi surface at high doping which splits into an
electron- and hole-like branch when a bilayer hopping t⊥
is included.


c. Cluster simulations of the periodic Anderson model. The
periodic Anderson model (PAM) is widely considered to
be a paradigm for a variety of rare-earth and actinide
compounds including the heavy Fermion systems. It is
composed of a strongly hybridizing band of d electrons
and a weakly hybridizing band of correlated f -electrons
described by the Hamiltonian




- 
(d [†] iσ [d] jσ [+][ h.c.][) +]
ij,σ i




  H = −t




   ǫf (n [f] i↑ [+][ n][f] i↓ [) +][ U]
i i



ǫd(n [d] i↑ [+][ n][d] i↓ [)]
i




 +



n [f] i↑ [n][f] ↓ (185)
i



49


half filled, the system becomes more metallic, and the
Kondo scale is strongly suppressed compared to that of
the SIAM. In both the insulator and metal, the temperature dependence of the impurity susceptibility and many
other low temperature quantities deviate strongly from
that of the SIAM (Tahvildar-Zadeh et al., 1997).
Non-local corrections were studied by Shimizu (2002)
who used the DCA together with the NCA as a cluster solver to study the single-particle spectra. He finds
large deviations from the DMFT result due to the effects of RKKY exchange. At half filling, where the
RKKY exchange is strong and antiferromagnetic, he finds
a large gap of the order of the RKKY exchange energy.
When the filling of the conduction band is small and the
RKKY exchange is weaker and ferromagnetic, the coherence peak is restored.


V. CONCLUSIONS AND PERSPECTIVES


In this review we tried to convey the message that
quantum cluster approaches provide powerful theoretical tools to study the rich phenomenology in systems
dominated by strong electronic interactions, such as most
notably transition metal oxides, heavy Fermion and onedimensional systems including superconducting and magnetic compounds. Quantum cluster approaches are nonperturbative in nature, their quality can be systematically improved by increasing the cluster size, and they
provide complementary information to finite size simulations. By mapping the lattice problem to a finite size
cluster they describe short-ranged correlations within
the cluster accurately while approximating longer-ranged
physics on the mean-field level. Of the various attempts
to add non-local corrections to local approximations such
as DMFT, we focused in this review on three established
quantum cluster approaches which we believe to play the
major role in the description of many-particle systems.
The cluster perturbation theory provides a very economic way to calculate the single-particle dynamics by
continuing the results of an isolated finite size cluster to
the thermodynamic limit. For a cluster consisting of a
single site only this method is identical to the Hubbard-I
approximation, while it recovers the exact result in the
infinite size cluster limit. When combined with the selfenergy functional approach, the CPT can also be used to
study instabilities to symmetry broken phases.
Both embedded cluster techniques, the dynamical cluster approximation and the cellular dynamical mean field
theory are superior to the CPT in that they map the
lattice to an embedded cluster instead of the CPT’s isolated cluster. This leads to a self-consistent theory with
a single-particle coupling between the cluster and the
host. As a result both DCA and CDMFT naturally allow
for the study of phase-transitions and they provide thermodynamically consistent results on the one- and twoparticle level.
CDMFT can be viewed as a direct generalization of



DMFT simulations of the PAM reveal an antiferromagnetic insulating phase at half filling of both the f and
d bands. The gap is set by the Kondo coherence scale
T0 which is strongly enhanced compared to the singleimpurity model (SIAM) scale. When the d-band is doped
away from half filling while the f -band remains roughly


DMFT to a cluster in real space. The mapping between
lattice and cluster problems is identical to that of the
long established MCPA for disordered systems. It leads
to a cluster with open boundary conditions which violates translational symmetries. In contrast the DCA
cluster is defined in cluster reciprocal space. Hence the
DCA cluster has periodic boundary conditions and therefore preserves the translational symmetries of the lattice.
This difference in boundary conditions translates directly
to different asymptotic behaviors for large linear cluster
sizes Lc, and the decision which method to use for a given
problem strongly depends on the quantities of interest:
Local quantities, such as the local density of states when
defined on central cluster sites converge faster in the
CDMFT since they do not directly couple to the meanfield. Due to the large mean-field coupling of the surface
sites however, the CDMFT converges slowly, with corrections of order (1/Lc), for quantities extended over the
O
cluster. The DCA converges more quickly, as O(1/L [2] c [),]
due to the periodic boundary conditions on the cluster.
Quantum cluster approaches reduce the complexity of
the infinite lattice problem by mapping it to a cluster
with fewer degrees of freedom. The numerous methods
employed to solve the DMFT equations are in principle available to study the effective cluster model. However as the complexity of this task rapidly increases
with cluster size, potential cluster solvers are faced with
severe size limitations. As the most promising techniques we reviewed perturbative approaches including
the fluctuation-exchange approximation and the noncrossing approximation as well as non-perturbative techniques including quantum Monte Carlo and numerical
renormalization group.
We discussed the application of quantum cluster approaches to a wide range of problems in condensed matter
physics. The information gained from these studies has
led to significant progress in the field of strongly correlated electron systems. Even studies using small cluster
sizes opened up new insight in problems such as onedimensional systems, the Mott-Hubbard transition in two
dimensions and high-temperature superconductivity.
To gain conclusive evidence however, larger cluster size
studies are inevitable to verify the information obtained
from small clusters. This task is severely hampered by
the rapidly increasing complexity with cluster size. Future progress therefore is closely linked to improvements
in the efficiency and flexibility of the techniques used
to solve the effective cluster problem. Within quantum
cluster approaches we explore a coarse-graining approximation in k-space. To further reduce the complexity,
the same idea could be transfered to the frequency domain. By coarse-graining the frequency dependence of
irreducible quantities, correlations on long time scales are
neglected, while the short time scale behavior is described
accurately. An important aspect in this context is again
the causality question. First test results are encouraging; they show that coarse-graining in Matsubara space
leads to acausalities, while coarse-graining the real fre


50


quency axis does not face this problem (Aryanpour et al.,
2003a).
Another route to defeat the cluster size problem is
to develop hybrid algorithms that treat different lengthscales in the problem with different accuracy. As a
promising step in this direction, Hague et al. (2003) have
developed a hybrid technique which maps the infinite lattice onto two embedded clusters of different size, thus
dividing the problem into three length-scales. Shortranged correlations described by the small cluster are
treated accurately within QMC, correlations of intermediate length-scale are treated perturbatively in the large
cluster using FLEX, and the long-ranged physics beyond
the size of the larger cluster is again approximated on
the mean-field level.
To improve comparisons with experiments and to
achieve predictive capability, the inclusion of the specifics
of the actual materials is required. Along the lines of the
LDA+DMFT approach, one can use electronic structure
calculations to parameterize the models studied by quantum cluster approaches. First steps in this direction have
been made by Poteryaev et al. (2003). A more integrated
approach to the ab-initio description of strongly correlated systems by combining the ideas of density functional theory and quantum cluster approaches remains
an important and challenging task.


Acknowledgments


It is a pleasure to acknowledge useful discussions
with H. R. Krishnamurthy, J. Keller, H. Keiter,
E. M¨uller-Hartmann P. van Dongen A. Gonis, B. Gyorffy, M. Mukherjee, A. N. Tavildar-Zadeh, G. Baskaran,
M. Vojta, R. Bulla, A. Lichtenstein, K. Aryanpour and
G. Kotliar. This work was supported in part by NSF
grants DMR-0312680, DMR-0113574, and DMR-0073308
and by the DFG through SFB 484. We acknowledge supercomputer support by the Leibniz Computer Center,
the Max-Planck Computer Center Garching under grant
h0301, the Ohio Supercomputer Center, the Pittsburgh
Supercomputer Center (NSF) and the Center for Computational Sciences at the Oak Ridge National Laboratory.
Part of this research was performed by TM as Eugene P.
Wigner Fellow and staff member at the Oak Ridge National Laboratory, managed by UT-Battelle, LLC, for the
U.S. Department of Energy under Contract DE-AC0500OR22725.


References


Abrikosov, A., L. Gorkov, and I. Dzyaloshinski, 1963, Methods
of Quantum Field Theory in Statistical Physics (Dover).
Aichhorn, M., M. Daghofer, H. Evertz, and W. v.d. Linden,
2003, Phys. Rev. B 67, 161103.
Anderson, P., 1961, Phys. Rev. 124, 41.
Anderson, P., 1997a, Adv. Phys. 46, 3.
Anderson, P. W., 1987, Science 235, 1196.


Anderson, P. W., 1997b, The Theory of Superconductivity in
the High-Tc Cuprates (Princeton University Press, Princeton, NJ).
Aryanpour, K., M. H. Hettler, and M. Jarrell, 2002, Phys.
Rev. B 65, 153102.
Aryanpour, K., M. H. Hettler, and M. Jarrell, 2003a, Phys.
Rev. B 67, 085101.
Aryanpour, K., T. A. Maier, and M. Jarrell, 2003b, preprint
cond-mat/0301460 .
Baym, G., 1962, Phys. Rev. 127, 1391.
Baym, G., and L. Kadanoff, 1961, Phys. Rev. 124, 287.
Becker, K., and J. Keller, 1987, Z. Phys. B 36, 2036.
Beeby, J. L., and S. F. Edwards, 1962, Proc. Roy. Soc. (London) A274, 395.
Bethe, H. A., 1935, Proc. R. Soc. London A150, 552.
Betts, D., and G. Stewart, 1997, Can. J. Phys. 75, 47.
Bickers, N., 1987, Rev. Mod. Phys. 59, 845.
Bickers, N., D. Cox, and J. Wilkins, 1987, Phys. Rev. B 36,
2036.
Bickers, N., D. Scalapino, and S. White, 1989, Phys. Rev.
Lett. 62, 961.
Bickers, N., and S. R. White, 1990, Phys. Rev. B 43, 8044.
Biroli, G., and G. Kotliar, 2002, Phys. Rev. B 65, 155112.
Biroli, G., O. Parcollet, and G. Kotliar, 2003, preprint conmat/0307587 .
Bolech, C., S. Kancharla, and G. Kotliar, 2003, Phys. Rev. B
67, 075110.
Brandt, U., and U. Mielsch, 1989, Z. Phys. B 75, 365.
Brandt, U., and R. Schmidt, 1986, Z. Phys. B 63, 45.
Brandt, U., and R. Schmidt, 1987, Z. Phys. B 67, 43.
Bulla, R., 1999, Phys. Rev. Lett. 83, 136.
Bulla, R., T. Costi, and D. Vollhardt, 2001, Phys. Rev. B 64,
045103.
Bulla, R., A. Hewson, and T. Pruschke, 1998, J. Phys.: Condens. Matter 10, 8365.
Caffarel, M., and W. Krauth, 1994, Phys. Rev. Lett. 72, 1545.
Cox, D., and N. Grewe, 1987, Z. Phys. B 71, 321.
Creffield, C., E. Klepfish, E. Pike, and S. Sarkar, 1995, Phys.
Rev. Lett. 75, 517.
Dagotto, E., 1994, Rev. Mod. Phys 66, 763.
Dagotto, E., and A. Moreo, 1988, Phys. Rev. B 38, 5078.
Dahnken, C., M. Aichhorn, W. Hanke, E. Arrigoni, and
M. Potthoff, 2003, preprint cond-mat/0309407 .
Dahnken, C., E. Arrigoni, and W. Hanke, 2002, J. Low Temp.
Phys. 126, 949.
Deisz, J., D. Hess, and J. Serene, 1996, Phys. Rev. Lett. 76,
1312.
Deisz, J., D. Hess, and J. Serene, 2003, Recent Progress in
many Body Theories, volume 4 (Plenum, New York).
Ducastelle, F., 1974, J. Phys C 7, 1795.
Emery, V., 1987, Phys. Rev. Lett. 58, 2794.
Emery, V., and G. Reiter, 1988, Phys. Rev. B 38, 4547.
Fetter, A., and J. Walecka, 1971, Quantum Theory of ManyParticle Systems, International Series in Pure and Applied
Physics (McGraw-Hill, New York).
Fischer, K., 1997, Phys. Rev. B 55, 13575.
Fisher, M., and M. Barber, 1972, Phys. Rev. Lett. 28, 1516.
Georges, A., and G. Kotliar, 1992, Phys. Rev. B 45, 6479.
Georges, A., G. Kotliar, W. Krauth, and M. Rozenberg, 1996,
Rev. Mod. Phys. 68, 13.
Goldenfeld, N., 1992, Lectures on Phase Transitions and
the Renormalization Group, Frontiers in Physics (Addison
Wesley, Reading, Massachusetts).
Gonis, A., 1992, Green Functions for Ordered and Disordered



51


Systems, Studies in Mathematical Physics (North-Holland,
Amsterdam).
Grewe, N., 1983, Z. Phys. B 53, 271.
Grewe, N., 1987, Z. Phys. B 67, 323.
Grewe, N., H. Keiter, and T. Pruschke, 1988, Z. Phys. B 71,
75.
Gros, C., and R. Valenti, 1994, Annalen der Phys. 3, 460.
Hague, J., 2003, J. Phys.: Cond. Mat. 15, 2535.
Hague, J., M. Jarrell, and T. Schulthess, 2003, preprint condmat/0312155 .
Haydock, R., V. Heine, and M. J. Kelly, 1975, J. Phys. C 8,
2591.
Heindl, W., T. Pruschke, and J. Keller, 2000, J. Phys.: Condens. Matter 12, 2245.
Hettler, M. H., M. Mukherjee, M. Jarrell, and H. R. Krishnamurthy, 2000, Phys. Rev. B 61, 12739.
Hettler, M. H., A. N. Tahvildar-Zadeh, M. Jarrell, T. Pruschke, and H. R. Krishnamurthy, 1998, Phys. Rev. B 58,
R7475.
Hewson, A., 1993, The Kondo Problem to Heavy Fermions,
Cambridge Studies in Magnetism (Cambridge UNiversity
Press, Cambridge).
Hirsch, J., 1983, Phys. Rev. B 28, 4059.
Hirsch, J., and R. Fye, 1986, Phys. Rev. Lett. 56, 2521.
Hohenadler, M., M. Aichhorn, and W. v.d. Linden, 2003,
Phys. Rev. B 68, 184304.
Hubbard, J., 1963, Proc. Royal. Soc. London 276, 238.
Huscroft, C., R. Gass, and M. Jarrell, 2000, Phys. Rev. B 61,
9300.
Huscroft, C., M. Jarrell, T. Maier, S. Moukouri, and
A. Tahvildarzadeh, 2001, Phys. Rev. Lett. 86, 139.
Imai, Y., and N. Kawakami, 2002, Phys. Rev. B 65, 233103.
Itzykson, C., and J.-M. Drouffe, 1989, Statistical Field Theory
(Cambridge University Press).
Jakliˇc, J., and P. Prelovˇsek, 2000, Adv. Phys. 49, 1.
Jarrell, M., 1992, Phys. Rev. Lett. 69, 168.
Jarrell, M., H. Akhlaghpour, and T. Pruschke, 1993, Quantum Monte Carlo Methods in Condensed Matter Physics
(Worl Scientific, Singapore), chapter Quantum Monte
Carlo in the Infinite Dimensional Limit, pp. 221–234.
Jarrell, M., and J. Gubernatis, 1996, Physics Reports 269,
133.
Jarrell, M., and D. Johnson, 2004, in preparation .
Jarrell, M., and H. R. Krishnamurthy, 2001, Phys. Rev. B 63,
125102.
Jarrell, M., T. Maier, M. H. Hettler, and A. N. Tahvildarzadeh, 2001a, Europhys. Lett. 56, 563.
Jarrell, M., T. Maier, C. Huscroft, and S. Moukouri, 2001b,
Phys. Rev. B 64, 195130.
Jarrell, M., T. Maier, and T. Schulthess, 2004, in preparation
.
Jarrell, M., and T. Pruschke, 1993, Z. Phys. B 90, 187.
Jones, B., and C. Varma, 1987, Phys. Rev. Lett. 58, 843.
Jones, B., C. Varma, and J. Wilkins, 1988, Phys. Rev. Lett.
61, 125.
Kakehashi, Y., 2002, Phys. Rev. B 66, 104428.
Kampf, A., and J. Schrieffer, 1990, Phys. Rev. B 42, 7967.
Keiter, H., and C. Czycholl, 1983, J. Magn. and Magn. Mat.
31–34, 477.
Keiter, H., and J. Kimball, 1970, Phys. Rev. Lett. 25, 672.
Keiter, H., and J. Kimball, 1971, Int. J. Magn. 1, 233.
Kikuchi, R., 1951, Phys. Rev. 81, 988.
Kim, C., Y. Kuramoto, and T. Kasoya, 1990, J. Phys. Soc.
Jpn. 59, 2414.


Kotliar, G., S. Savrasov, G. Pallson, and G. Biroli, 2001,
Phys. Rev. Lett. 87, 186401.
Krishnamurthy, H., J. Wilkins, and K. Wilson, 1980a, Phys.
Rev. B 21, 1003.
Krishnamurthy, H., J. Wilkins, and K. Wilson, 1980b, Phys.
Rev. B 21, 1044.
Kuramoto, Y., 1983, Z. Phys. B 53, 37.
Kuramoto, Y., 1985, Springer Series in Sol. State, 152.
Laad, M. S., and M. van den Bossche, 2000, J. Phys.: Condens. Matter 12, 2209.
Landau, D., 1976, Phys. Rev. B 13, 2997.
Lichtenstein, A. I., and M. I. Katsnelson, 2000, Phys. Rev. B
62, R9283.
Lieb, E., and F. Wu, 1968, Phys. Rev. Lett. 20, 1445.
Lombardo, P., M. Avignon, J. Schmalian, and K. Bennemann,
1996, Phys. Rev. B 54, 5317.
Maier, T., 2001, Nonlocal Dynamical Correlations in Strongly
Interacting Fermion Systems (Logos Verlag Berlin, Berlin,
Germany).
Maier, T., 2003, preprint cond-mat/0312447 .
Maier, T., and M. Jarrell, 2002, Phys. Rev. B 65, 041104.
Maier, T., M. Jarrell, A. Macridin, and C. Slezak, 2004, Phys.
Rev. Lett. 92, 027005.
Maier, T., M. Jarrell, A. Macridin, and F.-C. Zhang, 2002a,
preprint cond-mat/0208419 .
Maier, T., M. Jarrell, T. Pruschke, and J. Keller, 2000a, Phys.
Rev. Lett. 85, 1524.
Maier, T., M. Jarrell, T. Pruschke, and J. Keller, 2000b, Eur.
Phys. J B 13, 613.
Maier, T., M. Z¨olfl, T. Pruschke, and J. Keller, 1999a, Eur.
Phys. J. B 7, 377.
Maier, T., M. Z¨olfl, T. Pruschke, and J. Keller, 1999b, Physica
B 259, 747.
Maier, T. A., O. Gonzalez, M. Jarrell, and T. Schulthess,
2002b, Two Quantum Cluster Approximations, Springer
Proceedings in Physics.
Matsumoto, H., and F. Mancini, 1997, Phys. Rev. B 55, 2095.
Metzner, W., and D. Vollhardt, 1989, Phys. Rev. Lett. 62,
324.
Minh-Tien, T., 1998, Phys. Rev. B 58, R15965.
Minh-Tien, T., 1999a, Europhys. Lett. 47, 582.
Minh-Tien, T., 1999b, Phys. Rev. B 60, 16371.
Minh-Tien, T., 2001, Phys. Rev. B 63, 165117.
Molegraaf, H. J. A., C. Presura, D. van der Marel, P. H. Kes,
and M. Li, 2002, Science 295, 2239.
Monthoux, P., A. Balatsky, and D. Pines, 1991, Phys. Rev.
Lett. 67, 3448.
Moukouri, S., S. Allen, F. Lemay, B. Kyong, D. Poulin,
Y. Vilk, and A.-M. Tremblay, 1999, Phys. Rev. B 61, 7887.
Moukouri, S., and M. Jarrell, 2001, Phys. Rev. Lett. 87,
167010.
M¨uller-Hartmann, E., 1984, Z. Phys. B 57, 293.
M¨uller-Hartmann, E., 1989a, Z. Phys. B 76, 211.
M¨uller-Hartmann, E., 1989b, Z. Phys. B 74, 507.
Nordheim, J., 1931a, Ann. Physik 9, 607.
Nordheim, J., 1931b, Ann. Physik 9, 641.
Okamoto, S., A. Millis, H. Monien, and A. Fuhrmann, 2003,
Phys. Rev. B 68, 195121.
Oliveira, W., and L. Oliveira, 1994, Phys. Rev. B 49, 11986.
Pairault, S., D. S´en´echal, and A.-M. Tremblay, 1998, Phys.
Rev. Lett. 80, 5389.
Pairault, S., D. S´en´echal, and A.-M. Tremblay, 2000, Eur.
Phys. J. B 16, 85.
Parcollet, O., G. Biroli, and G. Kotliar, 2003, preprint cond


52


mat/0308577 .
Parmenter, R. H., 1955, Phys. Rev. 97, 587.
Paula, C., M. Silva, and L. Oliveira, 1999, Phys. Rev. B 59,
85.
Poteryaev, A., A. Lichtenstein, and G. Kotliar, 2003, preprint
cond-mat/0311319 .
Potthoff, M., 2003a, preprint cond-mat/0309407 .
Potthoff, M., 2003b, Eur. Phys. J. B 32, 429.
Potthoff, M., M. Aichhorn, and C. Dahnken, 2003, Phys. Rev.
Lett. 91, 206402.
Pruschke, T., R. Bulla, and M. Jarrell, 2000, Phys. Rev. B
61, 12799.
Pruschke, T., D. Cox, and M. Jarrell, 1993a, Europhys. Lett.
21, 593.
Pruschke, T., D. Cox, and M. Jarrell, 1993b, Phys. Rev. B
47, 3553.
Pruschke, T., and N. Grewe, 1989, Z. Phys. B 74, 439.
Pruschke, T., M. Jarrell, and J. Freericks, 1995, Adv. in Phys.
44, 187.
Pruschke, T., and R. Zitzler, 2003, J. Phys. Chem. 15, 7867.
Roth, L. M., 1969, Phys. Rev. 184, 461.
Sakai, O., and Y. Kuramoto, 1994, Solid State Commun. 89,
307.
Sakai, O., and Y. Shimizu, 1992, J. Phys. Soc. Jpn. 61, 2333.
Sakai, O., Y. Shimizu, and T. Kasuya, 1989, J. Phys. Soc.
Jpn. 59, 3666.
Sakai, O., Y. Shimizu, and T. Kasuya, 1990, Solid State
Comm. 75, 81.
Scalapino, D., 1999, J. Low Temp. Phys. 117(3-4), 179.
Schiller, A., and K. Ingersent, 1995, Phys. Rev. Lett. 75, 113.
Schmalian, J., P. Lombardo, M. Avignon, and K. Bennemann,
1996, Physica B 222–224, 602.
Schoen, J. M., 1969, Phys. Rev. 184, 858.
Schrieffer, J., 1993, Theory of Superconductivity (Addison
Wesley, Reading, MA).
Schwartz, L., F. Brouers, A. V. Vedyayev, and H. Ehrenreich,
1971, Phys. Rev. B 4, 3383.
S´en´echal, D., D. Perez, and M. Pioro-Ladri´ere, 2000, Phys.
Rev. Lett. 84, 522.
S´en´echal, D., D. Perez, and D. Plouffe, 2002, Phys. Rev. B
66, 075129.
S´en´echal, D., and A.-M. Tremblay, 2003, preprint condmat/0308625 .
Shiba, H., 1971, Prog. Theo. Phys. 46, 77.
Shimizu, Y., 2002, Journal of the Physical Society of Japan
71, 1166.
Shimizu, Y., and O. Sakai, 1995, Computational Physics as a
New Frontier in Condensed Matter Research (The Physical
Society of Japan), p. 42.
Si, Q., M. J. Rozenberg, G. Kotliar, and A. E. Ruckenstein,
1994, Phys. Rev. Lett. 72, 2761.
Smith, J., and Q. Si, 2000, Phys. Rev. B 61, 5184.
Soven, P., 1967, Phys. Rev. 156, 809.
Stanescu, T. D., and P. Phillips, 2001, Phys. Rev. B 64,
235117.
Stanescu, T. D., and P. Phillips, 2003a, preprint condmat/0301254 .
Stanescu, T. D., and P. Phillips, 2003b, Phys. Rev. Lett. 91,
017002.
Sumi, H., 1974, J. Phys. Soc. Jpn. 36, 770.
Suzuki, M., 1986, J. Phys. Soc. Jpn 55, 4205.
Tahvildar-Zadeh, A., M. Jarrell, and J. Freericks, 1997, Phys.
Rev. B 55, R3332.
Tanh-Hai, D., and T. Minh-Tien, 2001, J. Phys.: Condens.


Matter 13, 5625.
Taylor, D., 1967, Phys. Rev. 156, 1017.
Timusk, T., and B. Statt, 1999, Rep. Prog. Phys. 62, 61.
Tsukada, M., 1969, J. Phs. Soc. Jpn 26, 684.
Vekic, M., and S. White, 1993, Phys. Rev. B 47, 1160.
Vidberg, H. J., and J. W. Serene, 1977, J. Low. Temp. Phys.
19, 179.
Voit, J., 1994, Rep. Prog. Phys. 57, 977.
de Vries, P., K. Michelsen,, and H. De Raedt, 1993a, Z. Phys.
B 92, 353.
de Vries, P., K. Michelsen, and H. De Raedt, 1993b, Phys.
Rev. Lett. 70, 2463.
de Vries, P., K. Michelsen, and H. De Raedt, 1994, Z. Phys.
B 95, 475.
Weiss, P., 1907, J. Phys. Radium 6, 661.



53


Wilson, K., 1975, Rev. Mod. Phys. 47, 773.
Zacher, M. G., R. Eder, E. Arrigoni, and W. Hanke, 2002a,
Phys. Rev. B 65, 045109.
Zacher, M. G., R. Eder, E. Arrigoni, and W. Hanke, 2002b,
Phys. Rev. Lett. 85, 2585.
Zhang, F., and T. Rice, 1988, Phys. Rev. B 37, 3759.
Zhang, F., and T. Rice, 1990, Phys. Rev. B 41, 7243.
Zitzler, R., T. Pruschke, and R. Bulla, 2002, Eur. Phys. J. B
27, 473.
Zitzler, R., N. Tong, T. Pruschke, and R. Bulla, 2003, preprint
cond-mat/0308202 .
Z¨olfl, M., T. Maier, T. Pruschke, and J. Keller, 2000, Eur.
Phys. J. B 13, 47.
