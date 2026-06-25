---
source: "https://arxiv.org/abs/cond-mat/0301188"
type: "arxiv"
canonical_id: "cond-mat/0301188"
title: "Exact solution of the Falicov-Kimball model with dynamical mean-field theory"
authors: "J. Freericks, V. Zlatić"
year: "2003"
arxiv_id: "cond-mat/0301188"
doi: "10.1103/RevModPhys.75.1333"
full_text: yes
---

# Exact solution of the Falicov-Kimball model with dynamical mean-field theory

**Authors:** J. Freericks, V. Zlatić

**Citation:** preprint, 2003

**arXiv:** [cond-mat/0301188](https://arxiv.org/abs/cond-mat/0301188)

**DOI:** [10.1103/RevModPhys.75.1333](https://doi.org/10.1103/RevModPhys.75.1333)

## Abstract

The Falicov-Kimball model was introduced in 1969 as a statistical model for metal-insulator transitions; it includes itinerant and localized electrons that mutually interact with a local Coulomb interaction and is the simplest model of electron correlations. It can be solved exactly with dynamical mean-field theory in the limit of large spatial dimensions which provides an interesting benchmark for the physics of locally correlated systems. In this review, we develop the formalism for solving the Falicov-Kimball model from a path-integral perspective, and provide a number of expressions for single and two-particle properties. We examine many important theoretical results that show the absence of fermi-liquid features and provide a detailed description of the static and dynamic correlation functions and of transport properties. The parameter space is rich and one finds a variety of many-body features like metal-insulator transitions, classical valence fluctuating transitions, metamagnetic transitions, charge density wave order-disorder transitions, and phase separation. At the same time, a number of experimental systems have been discovered that show anomalies related to Falicov-Kimball physics [including YbInCu4, EuNi2(Si1−xGex)2, NiI2 and TaxN].

## Full Text

## Exact solution of the Falicov-Kimball model with dynamical mean-field theory

J. K. Freericks [∗]


Department of Physics, Georgetown University, Washington, DC 20057


V. Zlati´c [†]


Institute of Physics, Zagreb, Croatia


(Dated: October 22, 2018)


The Falicov-Kimball model was introduced in 1969 as a statistical model for metal-insulator transitions; it includes itinerant and localized electrons that mutually interact with a local Coulomb
interaction and is the simplest model of electron correlations. It can be solved exactly with dynamical mean-field theory in the limit of large spatial dimensions which provides an interesting
benchmark for the physics of locally correlated systems. In this review, we develop the formalism
for solving the Falicov-Kimball model from a path-integral perspective, and provide a number of
expressions for single and two-particle properties. We examine many important theoretical results
that show the absence of fermi-liquid features and provide a detailed description of the static and
dynamic correlation functions and of transport properties. The parameter space is rich and one
finds a variety of many-body features like metal-insulator transitions, classical valence fluctuating
transitions, metamagnetic transitions, charge density wave order-disorder transitions, and phase
separation. At the same time, a number of experimental systems have been discovered that show
anomalies related to Falicov-Kimball physics [including YbInCu4, EuNi2(Si1−xGex)2, NiI2 and
TaxN].


PACS numbers: 71.10.-W, 71.30.+h, 71.45.-d, 72.10.-d



Contents


I. Introduction 1
A. Brief History 1
B. Hamiltonian and Symmetries 3
C. Outline of the Review 4


II. Formalism 5
A. Limit of Infinite Spatial Dimensions 5
B. Single-Particle Properties (Itinerant Electrons) 6
C. Static Charge, Spin, or Superconducting Order 10
D. Dynamical Charge Susceptibility 13
E. Static and Dynamical Transport 16
F. Single-Particle Properties (Localized Electrons) 19
G. Spontaneous Hybridization 23


III. Analysis of Solutions 24
A. Charge-Density-Wave Order and Phase Separation 24
B. Mott-like Metal-Insulator Transitions 27
C. Falicov-Kimball-like Metal-Insulator Transitions 28
D. Intermediate-Valence 29
E. Transport Properties 30
F. Magnetic-Field Effects 31
G. Static Holstein Model 33


IV. Comparison with Experiment 34
A. Valence-Change Materials 34
B. Electronic Raman Scattering 39
C. Josephson Junctions 40
D. Resistivity Saturation 42
E. Pressure-Induced Metal-Insulator Transitions 43


∗Electronic address: [freericks@physics.georgetown.edu;](mailto:freericks@physics.georgetown.edu)
[URL: http://www.physics.georgetown.edu/~jkf](http://www.physics.georgetown.edu/~jkf)
[†Electronic address: zlatic@ifs.hr](mailto:zlatic@ifs.hr)



V. New Directions 43
A. 1/d Corrections 43
B. Hybridization and f -Electron Hopping 46
C. Nonequilibrium Effects 46


VI. Conclusions 47


Acknowledgments 48


List of Symbols 48


References 48


I. INTRODUCTION


A. Brief History


The Falicov-Kimball model (Falicov and Kimball,
1969) was introduced in 1969 to describe metal-insulator
transitions in a number of rare-earth and transition-metal
compounds [but see Hubbard’s earlier work (Hubbard,
1963) where the spinless version of the Falicov-Kimball
model was introduced as an approximate solution to
the Hubbard model; one assumes that one species
of spin does not hop and is frozen on the lattice].
The initial work by Falicov and collaborators focused
primarily on analyzing the thermodynamics of the
metal-insulator transition with a static mean-field theory approach (Falicov and Kimball, 1969; Ramirez et al.,
1970). The resulting solutions displayed both continuous and discontinuous metal-insulator phase transitions,
and they could fit the conductivity of a wide variety
of transition-metal and rare-earth compounds with their


results. Next, Ramirez and Falicov (1971) applied the
model to describe the α − γ phase transition in Cerium.
Again, a number of thermodynamic quantities were approximated well by the model, but it did not examine any
effects associated with Kondo screening of the f -electrons

[and subsequently was discarded in favor of the Kondo
volume collapse picture (Allen and Martin, 1982)].
Interest in the model waned once Plischke (1972)
showed that when the coherent-potential-approximation
(CPA) (Soven, 1967; Velick´y et al., 1968) was applied to
it, all first-order phase transitions disappeared and the
solutions only displayed smooth crossovers from a metal
to an insulator [this claim was strongly refuted by Falicov’s group (Gon¸calves da Silva and Falicov, 1972) but
interest in the model was limited for almost 15 years].
The field was revitalized by mathematical physicists in
the mid 1980’s, who realized that the spinless version of
this model is the simplest correlated system that displays
long-range order at low temperatures and for dimensions
greater than one. Indeed, two groups produced independent proofs of the long-range order (Brandt and Schmidt,
1986, 1987; Kennedy and Lieb, 1986; Lieb, 1986). The
work by Kennedy and Lieb rediscovered Hubbard’s
original approximation that yields the spinless FalicovKimball model, and also provided a new interpretation
of the model for the physics of crystallization. A number
of other exact results followed including (i) a proof of
no quantum-mechanical mixed valence (or spontaneous
hybridization) at finite T (Subrahmanyam and Barma,
1988) [based on the presence of a local gauge symmetry and Elitzur’s theorem (Elitzur, 1975)]; (ii) proofs of
phase separation and of periodic ordering in one dimension (with large interaction strength) (Lemberger, 1992);
(iii) proofs about ground-state properties in two dimensions (also at large interaction strength) (Haller, 2000;
Haller and Kennedy, 2001; Kennedy, 1994, 1998); (iv) a
proof of phase separation in one dimension and small
interaction strength (Freericks et al., 1996); and (v) a
proof of phase separation for large interaction strength
and all dimensions (Freericks et al., 2002a,b). Most of
these rigorous results have already been summarized in
reviews (Gruber, 1999; Gruber and Macris, 1996). In
addition, a series of numerical calculations were performed in one and two dimensions (de Vries et al., 1993,
1994; Freericks and Falicov, 1990; Gruber et al., 1994;
Michielsen, 1993; Watson and Lema´nski, 1995). While
not providing complete results for the model, the numerics do illustrate a number of important trends in the
physics of the FK model.
At about the same time, there was a parallel development of the dynamical mean-field theory (DMFT),
which is what we concentrate on in this review.
The DMFT was invented by Metzner and Vollhardt
(1989). Almost immediately after the idea that in
large spatial dimensions the self energy becomes local, Brandt and collaborators showed how to solve
the static problem exactly (requiring no quantum
Monte Carlo), thereby providing the exact solution of



2


the Falicov-Kimball model (Brandt and Fledderjohann,
1992; Brandt et al., 1990; Brandt and Mielsch, 1989,
1990, 1991; Brandt and Urbanek, 1992). This work is
the extension of Onsager’s famous solution for the transition temperature of the two-dimensional Ising model to
the fermionic case (and large dimensions). These series of
papers revolutionized Falicov-Kimball model physics and
provided the only exact quantitative results for electronic
phase transitions in the thermodynamic limit for all values of the interaction strength. They showed how to
solve the infinite-dimensional DMFT model, illustrated
how to determine the order-disorder transition temperature for a checkerboard (and incommensurate) chargedensity-wave phase, showed how to find the free energy
(including a first study of phase separation), examined
properties of the spin-one-half model, and calculated the
f -particle spectral function.
Further work concentrated on static properties such
as charge-density-wave order (van Dongen, 1991a,
1992; van Dongen and Vollhardt, 1990; Freericks,
1993a,b; Gruber et al., 2001) and phase separation (Freericks et al., 1999; Freericks and Lema´nski,
2000; Letfulov, 1999). The original FalicovKimball problem of the metal-insulator transition (Chung and Freericks, 1998) was solved, as
was the problem of classical intermediate valence (Chung and Freericks, 2000) [both using the
spin-one-half generalization (Brandt et al., 1990;
Freericks and Zlati´c, 1998)]. The “Mott-like” metalinsulator transition (van Dongen and Leinung, 1997)
and the non-fermi-liquid behavior (Si et al., 1992) were
also investigated. Dynamical properties and transport have been determined ranging from the charge
susceptibility (Freericks and Miller, 2000; Shvaika,
2000, 2001), to the optical conductivity (Moeller et al.,
1992), to the Raman response (Devereaux et al., 2003;
Freericks and Devereaux, 2001a,b; Freericks et al.,
2001a), to an evaluation of the f -spectral function (Brandt and Urbanek, 1992; Si et al., 1992;
Zlati´c et al., 2001). Finally, the static susceptibility for spontaneous polarization was also determined (Portengen et al., 1996a,b; Si et al., 1992;
Subrahmanyam and Barma, 1988; Zlati´c et al., 2001).
These solutions have allowed the FK model to be
applied to a number of different experimental systems ranging from valence-change-transition materials (Zlati´c and Freericks, 2001a,b) like YbInCu4 and
EuNi2(Si1−xGex)2 to materials that can be doped
through a metal-insulator transition like TaxN [used as
a barrier in Josephson junctions (Freericks et al., 2001b,
2002c; Miller and Freericks, 2001)], to Raman scattering
in materials on the insulating side of the metal-insulator
transition (Freericks and Devereaux, 2001b) like FeSi or
SmB6. The model, and some straightforward modifications appropriate for double-exchange, have been
used to describe the CMR materials (Allub and Alascio,
1996, 1997; Letfulov and Freericks, 2001; Ramakrishnan,
2003).


Generalizations of the FK model to the static Holstein model were first carried out by Millis et al. (1995,
1996) and also applied to the CMR materials. Later
more fundamental properties relating to the transition temperature for the harmonic (Blawid and Millis,
2000; Ciuchi and de Pasquale, 1999) and anharmonic
cases (Freericks et al., 2000) and relating to the gap ratio for the harmonic (Blawid and Millis, 2001) and anharmonic cases (Freericks and Zlati´c, 2001a) were completed. Modifications to examine diluted magnetic semiconductors have also appeared (Chattopadhyay et al.,
2001; Hwang et al., 2002). A new approach to DMFT,
which allows the correlated hopping Falicov-Kimball
model to be solved has also been completed recently (Schiller, 1999; Shvaika, 2002).


B. Hamiltonian and Symmetries


The Falicov-Kimball model is the simplest
model of correlated electrons. The original version (Falicov and Kimball, 1969) involved spin-onehalf-electrons. Here, we will generalize to the case of
an arbitrary degeneracy of the itinerant and localized
electrons. The general Hamiltonian is then




  H = −t

⟨ij⟩



2�s+1



2�s+1 
c [†] iσ [c][jσ][ +]
σ=1 i



2�S+1

Efηfiη [†] [f][iη]
η=1



i



2�S+1

c [†] iσ [c][iσ][f][ †] iη [f][iη]
η=1




 + U


i



2�s+1


σ=1




 +


i



2�S+1

Uηη [ff][′] [f][ †] iη [f][iη][f][ †] iη [′] [f][iη][′]
ηη [′] =1




  gµBH


i



2�s+1

mσc [†] iσ [c][iσ]
σ=1



3


(of strength U ) which represents the local Coulomb interaction when itinerant and localized electrons occupy
the same lattice site (we could make U depend on σ or
η, but this complicates the formulas and is not normally
needed). The fourth term is the ff Coulomb interaction
energy of strength Uηη [ff][′][ (which can be chosen to depend]
on η if desired; the term with η = η [′] is unnecessary and
can be absorbed into Efη). Finally, the fifth and sixth
terms represent the magnetic energy due to the interaction with an external magnetic field H, with µB the
Bohr magneton, g (gf ) the respective Land´e g-factors,
and mσ (mη) the z-component of spin for the respective
states. Chemical potentials µ and µf are employed to adjust the itinerant and localized electron concentrations,
respectively (in cases where the localized particle is fixed
independently of the itinerant electron concentration, the
localized particle chemical potential µf can be absorbed
into the site-energy Ef ; in cases where the localized particles are electrons, they share a common chemical potential with the conduction electrons µ = µf ).
The spinless case corresponds to the case where s =
S = 0 and there is no ff interaction term because of the
Pauli exclusion principle. The original Falicov-Kimball
model corresponds to the case where s = S = 1/2, with
spin-one-half electrons for both itinerant and localized
cases (and the limit U [ff] →∞).
The Hamiltonian in Eq. (1) possesses a number of different symmetries. The partial particle-hole symmetry
holds on a bipartite lattice in no magnetic field (H = 0),
where the lattice sites can be organized into two sublattices A and B, and the hopping integral only connects
different sublattices. In this case, one performs a partial
particle-hole symmetry transformation on either the itinerant or localized electrons (Kennedy and Lieb, 1986).
The transformation includes a phase factor of (−1) for
electrons on the B sublattice. When the partial particlehole transformation is applied to the itinerant electrons,


ciσ → c [h] iσ [†][(][−][1)][p][(][i][)][,] (2)

with p(i) = 0 for i ∈ A and p(i) = 1 for i ∈ B and h
denoting the hole operators, then the Hamiltonian maps
onto itself (when expressed in terms of the hole operators
for the itinerant electrons), up to a numerical shift, with
U →−U, Efη → Efη + U, and µ →−µ. When applied
to the localized electrons,

fiη → fiη [h][†][(][−][1)][p][(][i][)][,] (3)

the Hamiltonian maps onto itself (when expressed in
terms of the hole operators for the localized electrons),
up to a numerical shift with U →−U, µ → µ + U,
Efη →−Efη − [�] η [′][ U][ ff] ηη [′][ −] [�] η [′][ U][ ff] η [′] η [, and][ µ][f][ →−][µ][f] [.]
These particle-hole symmetries are particularly useful
when Efη = 0, [�] η [′][ U][ ff] ηη [′][ does not depend on][ η][, and we]

work in the canonical formalism with fixed values of ρe
and ρf, the total itinerant and localized electron densities. Then, one can show that the ground-state energies




  gf µBH


i



2�S+1

mηfiη [†] [f][iη][.] (1)
η=1



The symbols c [†] iσ [(][c][iσ][) denote the itinerant electron cre-]
ation (annihilation) operators at site i in state σ (the
index σ takes 2s + 1 values). Similarly, the symbols fiη [†]
(fiη) denote the localized electron creation (annihilation)
operators at site i in state η (the index η takes 2S +1 values). Customarily, we identify the index σ and η with the
z-component of spin, but the index could denote other
quantum numbers in more general cases. The first term is
the kinetic energy (hopping) of the conduction electrons
(with t denoting the nearest-neighbor hopping integral);
the summation is over nearest neighbor sites i and j (we
count each pair twice to guarantee hermiticity). The second term is the localized electron site energy (which we
allow to depend on the index η to include crystal-field effects [without spin-orbit coupling for simplicity]); in most
applications the site-energy is taken to be η-independent.
The third term is the Falicov-Kimball interaction term


of H are simply related

Eg.s.(ρe, ρf, U ) = Eg.s.(2s + 1 ρe, ρf, U )
               -               = Eg.s.(ρe, 2S + 1 ρf, U )
                -                 = Eg.s.(2s + 1 ρe, 2S + 1 ρf, U ),
               -               (4)


(up to constant shifts or shifts proportional to ρe or ρf )
and one can restrict the phase space to ρe ≤ s + 2 [1] [and]

[1]



and one can restrict the phase space to ρe ≤ s + 2 [and]

ρf ≤ S + 2 [1] [.]



ρf ≤When one or more of the Coulomb interactions are in-S + 2 [.]

finite, then there are additional symmetries to the Hamiltonian (Freericks et al., 1999, 2002b). In the case where
all U [ff] = ∞, then we are restricted to the subspace
ρf 1. This system is formally identical to the case
of spinless localized electrons, and we will develop a full ≤
solution of this limit using DMFT below. The extra symmetry is precisely that of Eq. (4), but now with S = 0 (
regardless of the number of η states). Similarly, when
both U [ff] = ∞ and U = ∞, then Eq. (4) holds for
s = S = 0 as well (regardless of the number of σ and
η states). These infinite-U symmetries are also related
to particle-hole symmetry, but now restricted to the lowest Hubbard band in the system, since all upper Hubbard
bands are pushed out to infinite energy.
The Falicov-Kimball model also possesses a local symmetry, related to the localized particles. One can easily
show that [H, fiη [†] [f][iη][] = 0, implying that the][ local occu-]
pancy of the f -electrons is conserved. Indeed, this leads
to a local U (1) symmetry, as the phase of the localized
electrons can be rotated at will, without any effect on
the Hamiltonian. Because of this local gauge symmetry,
Elitzur’s theorem requires that there can be no quantummechanical mixing of the f -particle number at finite
temperature (Elitzur, 1975; Subrahmanyam and Barma,
1988), hence the system can never develop a spontaneous
hybridization (except possibly at T = 0).
There are a number of different ways to provide a physical interpretation of the Falicov-Kimball model. In the
original idea (Falicov and Kimball, 1969), we think of
having itinerant and localized electrons, that can change
their statistical occupancy as a function of temperature
(maintaining a constant total number of electrons). This
is the interpretation that leads to a metal-insulator transition due to the change in the occupancy of the different
electronic levels, rather than via a change in the character of the electronic states themselves (the Mott-Hubbard
approach). Another interpretation (Kennedy and Lieb,
1986), is to consider the localized particles as ions, which
have an attractive interaction with the electrons. Then
one can examine how the Pauli principle forces the system to minimize its energy by crystallizing into a periodic arrangement of ions and electrons (as seen in
nearly all condensed-matter systems at low temperature). Finally, we can map onto a binary alloy problem (Freericks and Falicov, 1990), where the presence of
an “ion” denotes the A species, and the absence of an
“ion” denotes a B species, with U becoming the difference in site energies for an electron on an A or a B site.



4


In these latter two interpretations, the localized particle
number is always a constant, and a canonical formalism
is most appropriate. In the first interpretation, a grand
canonical ensemble is the best approach, with a common
chemical potential (µ = µf ) for the itinerant and localized electrons.
In addition to the traditional Falicov-Kimball model,
in which conduction electrons interact with a discrete set
of classical variables (the localized electron-number operators), there is another class of static models that can
be solved using the same kind of techniques—the static
anharmonic Holstein model (Holstein, 1959; Millis et al.,
1995). This is a model of classical phonons interacting
with conduction electrons and can be viewed as replacing
the discrete spin variable of the FK model by a continuous classical field. The phonon is an Einstein mode, with
infinite mass (and hence zero frequency), but nonzero
spring constant. One can add any form of local anharmonic potential for the phonons into the system as well.
The Hamiltonian becomes (in the spin one-half case for
the conduction electrons, with one phonon mode per site)




  HHol = −t




- 
c [†] iσ [c][jσ][ +][ g][ep]
⟨ij⟩σ iσ



xi(c [†] iσ [c][iσ][ −] [ρ][eσ][)]
iσ




 
[1]

2 [κ]




  x [3] i [+][ α][an]
i i



x [4] i [,] (5)
i



+ [1]




  x [2] i [+][ β][an]
i i



where, for concreteness, we assumed a quartic phonon potential. The phonon coordinate at site i is xi, gep is the
electron-phonon interaction strength (the so-called deformation potential), and the coefficients βan and αan measure the strength of the (anharmonic) cubic and quartic
contributions to the local phonon potential. Note that
the phonon couples to the fluctuations in the local electronic charge (rather than the total charge). This makes
no difference for a harmonic system, where the shift in
the phonon coordinate can always be absorbed, but it
does make a difference for the anharmonic case, where
such shifts cannot be transformed away. The particlehole symmetry of this model is similar to that of the
discrete Falicov-Kimball model, described above, except
the particle-hole transformation on the phonon coordinate requires us to send xi xi. Hence, the presence
of a cubic contribution to the phonon potential →− βan = 0,
breaks the particle-hole symmetry of the system (Hirsch, ̸
1993); in this case the phase diagram is not symmetric about half filling for the electrons. We will discuss
some results of the static Holstein model, but we will not
discuss any further extensions (such as including double exchange for colossal magnetoresistance materials or
including interactions with classical spins to describe diluted magnetic semiconductors).


C. Outline of the Review


The Falicov-Kimball model (and the static Holstein
model) become exactly solvable in the limit of infinite


5



spatial dimensions (or equivalently when the coordination number of the lattice becomes large). This occurs
because both the self energy and the (relevant) irreducible two-particle vertices are local. The procedure involves a mapping of the infinite-dimensional lattice problem onto a single-site impurity problem in the presence of
a time-dependent (dynamical) mean field. The path integral for the partition function can be evaluated exactly
via the so-called static approximation (in an arbitrary
time-dependent field). Hence the problem is reduced
to one of “quadratures” to determine the correct selfconsistent dynamical mean field for the quantum system.
One can next employ the Baym-Kadanoff conserving approximation approach to determine the self energies and
the irreducible charge vertices (both static and dynamic).
Armed with these quantities, one can calculate essentially
all many-body correlation functions imaginable, ranging
from static charge-density order to a dynamical Raman
response. Finally, one can also calculate the properties of
the f -electron spectral function, and with that, one can
calculate the susceptibility for spontaneous hybridization
formation. The value of the Falicov-Kimball model lies
in the fact that all of these many-body properties can be
determined exactly, and thereby form a useful benchmark
for the properties of correlated electronic systems.
In Section II, we review the formalism that develops
the exact solution for all of these different properties employing DMFT. Our attempt is to provide all details of
the most important derivations, and summarizing formulae for some of the more complicated results, which are
treated fully in the literature. We believe that this review
provides a useful starting point for interested researchers
to then understand that literature. Section III presents
a summary of the results for a number of different properties of the model, concentrating mainly on the spinless
and spin-one-half cases. In Section IV, we provide a number of examples where the Falicov-Kimball model can be
applied to model real materials, concentrating mainly on
valence-change systems like YbInCu4. We discuss a number of interesting new directions in Section V, followed
by our conclusions in Section VI.


II. FORMALISM


A. Limit of Infinite Spatial Dimensions


In 1989, Metzner and Vollhardt demonstrated that
the many-body problem simplified in the limit of large
dimensions (Metzner and Vollhardt, 1989); equivalently,
this observation could be noted to be a simplification when the coordination number Z on a lattice becomes large. Such ideas find their origin in the justification of the inverse coordination number 1/Z as
the small parameter governing the convergence of the
coherent potential approximation (Schwartz and Siggia,
1972). Metzner and Vollhardt (1989) introduced an im


portant scaling of the hopping matrix element



where we used the number of neighbors Z = 4d and the
scaling in Eq. (6).
The foundation for DMFT comes from two facts: first
the self energy is a local quantity (possesses temporal
but not spatial fluctuations) and second it is a functional
of the local interacting Green’s function. These observations hold for any “impurity” model as well, where
the self energy can be extracted by a functional derivative of the Luttinger-Ward skeleton expansion for the
self-energy generating functional (Luttinger and Ward,
1960). Hence, a solution of the impurity problem provides the functional relationship between the Green’s
function and the self energy. A second relationship is
found from Dyson’s equation, which expresses the local Green’s function as a summation of the momentumdependent Green’s functions over all momenta in the
Brillouin zone. Since the self energy has no momentum dependence, this relation is a simple integral relation



t = t [∗] /2√



2Z (6)



d = t [∗] /√



where d is the spatial dimension. In the limit where
d →∞, the hopping to nearest neighbors vanishes, but
the coordination number becomes infinite—this is the
only scaling that produces a nontrivial electronic density of states in the large dimensional limit. Since there
is a noninteracting “band”, one can observe the effects
of the competition of kinetic-energy delocalization, with
potential energy localization, which forms the crux of
the many-body problem. Hence, this limit provides an
example where the many-body problem can be solved exactly, and these solutions can be analyzed for correlatedelectron behavior.
Indeed, the central limit theorem shows that the noninteracting density of states on a hybercubic lattice ρhyp(ǫ)
satisfies (Metzner and Vollhardt, 1989)


1
ρhyp(ǫ) = exp( ǫ [2] /t [∗][2] ), (7)
t [∗][√] πΩuc              

which follows from the fact that the band structure is
a sum of cosines, which are distributed between −1 and
1 for a “general” wave-vector in the Brillouin zone (Ωuc
is the volume of the unit cell, which we normally take
to be equal to one). Adding together d cosines will produce a sum that typically grows likethe hopping is chosen to scale like 1/√√dd, which is why. The central

limit theorem then states that the distribution of these
energies is in a Gaussian [an alternate derivation relying on tight-binding Green’s functions and the properties of Bessel functions can be found in M¨uller-Hartmann
(1989a)]. Another common lattice that is examined is the
infinite-coordination Bethe lattice (which can be thought
of as the interior of a large Cayley tree). The noninteracting density of states is (Economou, 1983)



1
ρBethe(ǫ) =
2πt [∗][2] Ωuc





4t [∗][2]  - ǫ [2], (8)


6



(called the Hilbert transformation) of the noninteracting
density of states. Combining these two ideas together,
in a self-consistent fashion provides the basic strategy of
DMFT.


FIG. 1 Skeleton expansion for the itinerant electron self energy Σij through fourth order. The wide solid lines denote
itinerant electron Green’s functions and the thin solid lines
denote localized electron Green’s functions; the dotted lines
denote the Falicov-Kimball interaction U . The series is identical to that of the Hubbard model, except we must restrict
the localized electron propagator to be diagonal in real space
(which reduces the number of off-diagonal diagrams significantly). The first diagrams in the second and third rows are
the only diagrams that contribute when i ̸= j for the FalicovKimball model.


For the Falicov-Kimball model, we need to establish
these two facts. The locality of the self energy is established most directly from an examination of the perturbation series, where one can show nonlocal self ener-gies are smaller by powers of 1/√d. The skeleton ex
pansion for the self energy (determined by the functional
derivative of the Luttinger-Ward self-energy generating
functional with respect to G), appears in Fig. 1 through
fourth order in U . This expansion is identical to the expansion for the Hubbard model, except we explicitly note
the localized and itinerant Green’s functions graphically.
Since the localized electron propagator is local (i.e. no
off-diagonal spatial components), many of the diagrams
in Fig. 1 are also purely local. The only nonlocal diagrams through fourth order are the first diagrams in
the second and third rows. If we suppose i and j cor


respond to nearest neighbors, then we immediately con-clude that the diagram has three factors of Gij 1/√d [3]
∝

√



with Nfi the total number of f -electrons at site i. Since
the Grassman variables are antiperiodic on the interval
0 ≤ τ ≤ β, we can expand them in Fourier modes,



(each 1/√



d [3]



(each 1/ d factor comes from tij). Summing over all

of the 2scales like 1d nearest neighbors, still produces a result that/√d in the large dimensional limit, which van
ishes. A similar argument can be extended to all nonlocal diagrams (Brandt and Mielsch, 1989; Metzner, 1991).
Hence, the self energy is local in the infinite-dimensional
limit. The functional dependence on the local Green’s
function then follows from the skeleton expansion, restricted to the local self energy (i = j).



B. Single-Particle Properties (Itinerant Electrons)


We start our analysis by deriving the set of equations
satisfied by the single-particle lattice Green’s function
for the itinerant electrons defined by the time-ordered
product



Gijσ (τ ) =
    - [1]



L Trcf ⟨e [−][β][(][H−][µN] [−][µ][f] [N][f] [)] Tτ ciσ(τ )c [†] jσ [(0)][⟩][,]
Z



(9)
where β = 1/T is the inverse temperature, 0 ≤ τ ≤ β
is the imaginary time, ZL is the lattice partition function, N is the total itinerant electron number, Nf is the
total localized electron number, and Tτ denotes imaginary time ordering (earlier times to the right). The time
dependence of the electrons is



ciσ(τ ) = e [τ] [(][H−][µN] [)] ciσ(0)e [−][τ] [(][H−][µN] [)], (10)


and the trace is over all of the itinerant and localized
electronic states. It is convenient to introduce a pathintegral formulation using Grassman variables ψ [¯] iσ(τ ) and
ψiσ(τ ) for the itinerant electrons at site-i with spin σ.
Using the Grassman form for the coherent states, then
produces the following path integral



Gijσ (τ ) =
    - [1]



Trf e [−][β][(][H][f] [−][µ][f][ N][f] [)]
L
Z

[−]




- L
ψ [¯] ψψiσ(τ ) ψ [¯] jσ (0)e [−][S][L], (11)
D D



for the Green’s function, where Hf denotes the f electron-only piece of the Hamiltonian [corresponding to
the second, fourth and sixth terms in Eq. (1)]. The lattice action associated with the Hamiltonian in Eq. (1)
is




- β




 S [L] =



2�s+1



dτ [′][ ¯] ψiσ(τ [′] )
0




             + δij(UNfi µ gµBHmσ)
d - 


ij



σ=1



�ij σ=1
× δij ∂τ∂ [′][ −] 2 [t] √ij [∗]



ψjσ(τ [′] ), (12)
×


indexed by the fermionic Matsubara frequencies iωn =
iπT (2n + 1):



7


many-body-variant of the cavity method (Georges et al.,
1996; Gruber et al., 2001), where we separate the path
integral into pieces that involve site-i only and all other
terms. The action, is then broken into three pieces: (i)
the local piece at site i, Sn(i, i); (ii) the piece that couples
to site i, Sn(i, j); and the piece that does not involve site
i at all, Sn(cavity) (called the cavity piece). Hence,


Sn = Sn(i, i) + Sn(i, j) + Sn(cavity) (17)


with


2�s+1



�∞

e [−][iω][n][τ] ψiσ(iωn) (13)
n=−∞


�∞

e [iω][n][τ][ ¯] ψiσ(iωn). (14)
n=−∞



and



ψiσ(τ ) = T


ψ¯iσ(τ ) = T



In terms of this new set of Grassman variables, the lattice
action becomes S [L] = T [�][∞] n=−∞ [S] n [L][, with]



Sn(i, i) =



σ=1 (−iωn − µ − gµBHmσ + UNfi)




 Sn [L] [=]

ij




  
2�s+1



ψ¯iσ(iωn)ψiσ(iωn), (18)
×



σ=1



(−iωn − µ − gµBHmσ + UNfi)δij




   Sn(i, j) =
    
[∗]




- 2t√ [∗] ijd



�=1
ψ¯iσ(iωn)ψjσ(iωn) (15)



2�s+1


σ=1



2t√ [∗] ijd



and the Fourier component of the local Green’s function
becomes



[ ψ [¯] iσ(iωn)ψjσ(iωn) + ψ [¯] jσ(iωn)ψiσ(iωn)],
×
(19)



j,t [∗] ij [=0]




      - β
Giiσ(iωn) =



and



dτe [iω][n][τ] Giiσ(τ )
0



= −� [T]



Trf e [−][β][(][H][f] [−][µ][f][ N][f] [)]
L
Z




 - ZL
ψ [¯] ψψiσ(iωn) ψ [¯] iσ(iωn)e [−][T][ �] n [′][ S] n [L][′] .
× D D



(16)


Now we are ready to begin the derivation of the DMFT
equations for the Green’s functions. We start with the



Sn(cavity) = Sn Sn(i, i) Sn(i, j). (20)
           -           
Let Zcavity and ⟨−⟩cavity denote the partition function
and path-integral average associated with the cavity action Scavity = T [�] n [S][n][(cavity) (the path-integral average]

for the cavity is divided by the cavity partition function).
Then the Green’s function can be written as



Giiσ(iωn) = T
    - [Z][cavity] L








 exp T




         
[cavity] Trf e [−][β][(][H][f] [−][µ][f] [N][f][ )] ψ [¯] i ψiψiσ(iωn) ψ [¯] iσ(iωn)e [−][T][ �] n [∞][′′] =−∞ [S][n][′′] [(][i,i][)]

L D D
Z ∞ 2s+1



�∞



. (21)

cavity







2�s+1



×



n [′] =−∞



j,t [∗] ij [=0]



2t√ [∗] ij




               - [�]

[ ψ [¯] iσ′ (iωn′)ψjσ′ (iωn′) + ψ [¯] jσ′ (iωn′)ψiσ′ (iωn′ )]
d



σ [′] =1



A simple power-counting argument, shows that only the second moment of the exponential factor in the cavity average
contributes as d →∞ (Georges et al., 1996), which then becomes




         
[cavity] Trf e [−][β][(][H][f] [−][µ][f][ N][f] [)] ψ [¯] i ψiψiσ(iωn) ψ [¯] iσ(iωn)

L D D
Z ∞ 2s+1



Giiσ(iωn) = T
    - [Z][cavity] L



�∞



2�s+1



iωn′ + µ + gµBHmσ′ UNfi λiσ′ (iωn′) ψ [¯] iσ′ (iωn′)ψiσ′ (iωn′)]. (22)
σ [′] =1{ - - }



× exp[T



n [′] =−∞



withBethe lattice, one finds λiσ(iωn) the function that results from the second-moment average that is called the dynamical mean field. On a λiσ(iωn) = t [∗][2] Giiσ(iωn), while on a general lattice, one finds λiσ(iωn) = [�] jk [t][ij] [t][ik][[][G][jkσ] [(][iω][n][)][−]

Gjiσ(iωn)Gikσ (iωn)/Giiσ(iωn)] (Georges et al., 1996). But the exact form is not important for deriving the DMFT
equations. Instead we simply need to note that after integrating over the cavity, we find an impurity path integral
for the Green’s function (after defining the impurity partition function via Zimp = ZL/Zcavity)



Giiσ(iωn) =
    - ∂λ [∂] [ln] iσ [ Z] (iω [imp] n) [,]


           Zimp = Trf e [−][β][(][H][f] [−][µ][f][ N][f] [)] Dψ [¯] iDψi exp[T



�∞


n=−∞



8


2�s+1

σ=1 {iωn + µ + gµBHmσ − UNfi − λiσ(iωn)}ψ [¯] iσ(iωn)ψiσ(iωn)].

(23)



The impurity partition function is easy to calculate, because the effective action is quadratic in the Grassman
variables. Defining 0σ(µ) by
Z



�∞
0σ(µ) = 2e [βµ/][2]
Z

n=−∞



iωn + µ λnσ
    -, (24)

iωn



allows us to re-express Eq. (27) as


w0 w1
Gnσ = (30)
G [−] 0σ [1][(][iω][n][) +] G [−] 0σ [1][(][iω][n][)][ −] [U,]


which is a form that often appears in the literature.
Dyson’s equation for the impurity self energy is

Σnσ = Σσ(iωn) = [G0σ(iωn)] [−][1]  - [Gσ(iωn)] [−][1] . (31)

This impurity self energy is equated with the local self
energy of the lattice (since they satisfy the same skeleton expansion with respect to the local Green’s function).
We can calculate the local Green’s function directly from
this self energy by performing a spatial Fourier transform of the momentum-dependent Green’s function on
the lattice:




[where we used the notation λnσ = λiσ(iωn) and adjusted
the prefactor to give the noninteracting result] allows us
to write the partition function as

Zimp = Tr2�s+1f exp[−β(Hfi − µf Nfi)]



×



0σ(µ + gµBHmσ UNfi). (25)
σ=1 Z 



[Z0σ is the generating functional for the U = 0 impurity
problem and satisfies the relation Z0σ = DetG [−] 0σ [1][, with]
G [−] 0σ [1] [defined below in frequency space in Eq. (29).] It]
is cumbersome to write out the trace over the fermionic
states in Eq. (25) for the general case. The spin-one-half
case appears in Brandt et al. (1990). Here we consider
only the strong-interaction limit, where U [ff] →∞, so
that there is no double occupancy of the f -electrons. In
this case, we find




  Gnσ =



Gnσ(k)

k




 =



1
iωn + µ + gµBHmσ − Σnσ − ǫk



�k
1
= dǫρ(ǫ)
iωn + µ + gµBHmσ − Σnσ − ǫ [(32)]



k



where ǫk is the noninteracting bandstructure. This relation is called the Hilbert transformation of the noninteracting density of states. Equating the Green’s function in Eq. (32) to that in Eq. (30) is the self consistency relation of DMFT. Substituting Eq. (31) into
Eq. (30) to eliminate the bare Green’s function, produces a quadratic equation for the self energy, solved
by Brandt and Mielsch (1989, 1990)



Σnσ = [1]

2



Zimp =


+


×



2�s+1

0σ(µ + gµBHmσ)
Z
σ=1

2�S+1

e [−][β][(][E][fη][−][µ][f][ −][g][f][ µ][B] [Hm][η] [)]

η=1

2�s+1

0σ(µ + gµBHmσ U ). (26)
σ=1 Z 


��
1
U
  - Gnσ



�2
U
+ 4w1
Gnσ






,





1
U
 - Gnσ ±



Evaluating the derivative yields


w0
Gnσ =
iωn + µ + gµBHmσ λnσ
w1             + (27)
iωn + µ + gµBHmσ − λnσ − U [,]

with


2�s+1



w0 =



0σ(µ + gµBHmσ)/ imp, (28)
Z Z
σ=1



(33)
which is the exact summation of the skeleton expansion
for the self energy in terms of the interacting Green’s
function (the sign in front of the square root is chosen
to preserve analyticity of the self energy). Note that
because w1 is a complicated functional of Gn and Σn,
Eq. (33) actually corresponds to a highly nonlinear functional relation between the Green’s function and the self
energy.
There are two independent strategies that one can
employ to calculate the FK model Green’s functions.
The original method of Brandt and Mielsch is to
substitute Eq. (33) into Eq. (32), which produces
a transcendental equation for Gnσ in the complex
plane (Brandt and Mielsch, 1989, 1990) (for fixed w1).
This equation can be solved by a one-dimensional complex root-finding technique (typically Newton’s method



and w1 = 1 − w0. The weight w1 equals the average f electron concentration ρf . If we relaxed the restriction
U [ff] →∞, then we would have additional terms corresponding to wi, with 1 < i 2S + 1. Defining the
≤
effective medium (or bare Green’s function) via

[G0σ(iωn)] [−][1] = iωn + µ + gµBHmσ − λnσ, (29)


or Mueller’s method is employed), as long as one pays attention to maintaining the analyticity of the self energy
by choosing the proper sign for the square root [for large
U, the sign changes at a critical value of the Matsubara frequency (Freericks, 1993a)]. The other technique is
the iterative technique first introduced by Jarrell (1992),
which is the most commonly used method. One starts the
algorithm either with Σnσ = 0 or with it chosen appropriately from an earlier calculation. Evaluating Eq. (32)
for Gnσ then allows one to calculate G0 from Eq. (31). If
we work at fixed chemical potential and fixed Ef, then we
must determine w0 and w1 from Eq. (28); this step is not
necessary if w0 and w1 are fixed in a canonical ensemble.
Eq. (30) is employed to find the new Green’s function,
and Eq. (31) is used to extract the new self energy. The
algorithm then iterates to convergence by starting with
this new self energy. Typically, the algorithm converges
to eight decimal points in less than 100 iterations, but for
some regions of parameter space the equations can either
converge very slowly, or not converge at all. Convergence
can be accelerated by averaging the last iteration with
the new result for determining the new self energy, but
there are regions of parameter space where the iterative
technique does not appear to converge.
Once w0, w1, and µ are known from the imaginary-axis
calculation, one can employ the analytic continuation of
Eqs. (30 32) (with iωn ω + i0 [+] ) to calculate Gσ(ω)

   - →
on the real axis. In general, the convergence is slower on
the real axis, than on the imaginary axis, with the spectral weight slowest to converge near correlation-induced
“band edges”. A stringent consistency test of this technique is a comparison of the Green’s function calculated
directly on the imaginary axis to that found from the
spectral formula

          Aσ(ω)
Gσ(z) = dω (34)
z ω + i0 [+][,]
             
with

          Aσ(ω) = dǫρ(ǫ)Aσ(ǫ, ω), (35)


and


1

Aσ(ǫ, ω) =
     - π [1] [Im] ω + µ + gµBHmσ Σσ(ω) ǫ + i0 [+]

               -                - (36)

[the infinitesimal 0 [+] is needed only when ImΣσ(ω) = 0].
Note that this definition of the interacting DOS has the
chemical potential located at ω = 0.
In zero magnetic field, one need perform these calculations for one σ state only, since all Gnσ’s are equal,
but in a magnetic field, one must perform 2s + 1 parallel
calculations to determine the Gnσ’s.
Our derivation of the single-particle Green’s functions
has followed a path-integral approach throughout. One
could have used an equation of motion approach instead.
This technique has been reviewed in Zlati´c et al. (2001).



9


The formalism for the static Holstein model is similar (Millis et al., 1996). Taking η to be a continuous
variable (x) and H = 0, we find



where f (ǫ) = 1/[1 + exp(βǫ)] is the Fermi-Dirac distribution function. This form has the itinerant electron energy
(plus interactions) and the localized electron energy on
the first line [the shift by µ is needed because A(ǫ) is
defined to have ǫ = 0 lie at the chemical potential µ],
the itinerant electron entropy on the second and third
lines, and the localized electron entropy on the fourth
line. Note that the total energy does not need the standard many-body correction to remove double counting of
the interaction because the localized particles commute
with the Hamiltonian (Fetter and Walecka, 1971).
The Brandt-Mielsch approach is different (Brandt and Mielsch, 1991) and is based on
the equality of the impurity and the lattice LuttingerWard self-energy generating functionals Φ. A general
conserving analysis (Baym, 1962) shows that the lattice
free energy satisfies

     FHelm.(lattice) = T Φlatt T ΣnσGnσ
             - nσ




    - ∞
Zimp = −∞ dx



0σ(µ gepx)
Z  σ=1



2�s+1



exp( β[ [1]
× - 2



(37)
2 [κx][2][ +][ β][an][x][3][ +][ α][an][x][4][])][,]



and




   - ∞ w(x)
Gnσ = dx, (38)

−∞ iωn + µ gepx λnσ
          -           

2�s+1



w(x) =



0σ(µ gepx)
Z  σ=1



exp( β[ [1]
× - 2



2 [κx][2][ +][ β][an][x][3][ +][ α][an][x][4][])][/][Z][imp][.][(39)]



These equations (37–39) and Eqs. (31) and (32) are all
that are needed to determine the Green’s functions by
using the iterative algorithm.
The final single-particle quantity of interest is the
Helmholtz free energy per lattice site FHelm.. We restrict our discussion to the case of zero magnetic field
H = 0 and to Efη = Ef (no η dependence to Ef ).
There are two equivalent ways to calculate the free energy. The original method uses the noninteracting functional form for the free energy, with the interacting density of states A(ǫ) replacing the noninteracting density of
states ρ(ǫ) (Plischke, 1972; Ramirez et al., 1970)




           FHelm.(lattice) = (2s + 1) dǫf (ǫ)A(ǫ)(ǫ + µ) + Ef nf




     -      + (2s + 1)T dǫ f (ǫ) ln f (ǫ)




        + [1 − f (ǫ)] ln[1 − f (ǫ)] A(ǫ)
+ T [w1 ln w1 + w0 ln w0 − w1 ln(2S + 1)], (40)


 + T


nσ




- 1
dǫρ(ǫ) ln
iωn + µ + gµBHmσ − Σnσ − ǫ



+ µρe + µf w1 (41)



while the impurity (or atomic) free energy satisfies (Brandt and Mielsch, 1991)




     FHelm.(impurity) = T Φimp T
           



 + T



ΣnσGnσ
nσ



ln Gnσ + µρe + µf w1. (42)
nσ



The first two terms on the right hand side of Eqs. (41)
and (42) are equal, so we immediately learn that




     FHelm.(lattice) = T ln imp T
        - Z        - nσ




dǫρ(ǫ)



× ln[(iωn + µ + gµBHmσ − Σnσ − ǫ)Gnσ] + µρe + µf w1
(43)


since FHelm.(impurity) = −T ln Zimp + µρe + µf w1. The
equivalence of Eqs. (40) and (43) has been explicitly
shown (Shvaika and Freericks, 2002). When calculating
these terms numerically, one needs to use caution to ensure that sufficient Matsubara frequencies are employed
to guarantee convergence of the summation in Eq. (43).


C. Static Charge, Spin, or Superconducting Order


The FK model undergoes a number of different phase
transitions as a function of the parameters of the system.



10


Many of these transitions are continuous (second-order)
transitions, that can be described by the divergence of
a static susceptibility at the transition temperature Tc.
Thus, it is useful to examine how one can calculate different susceptibilities within the FK model. In this section,
we will examine the charge susceptibility for arbitrary
spin, and then will consider the spin and superconducting
susceptibilities for the spin-one-half model. In addition,
we will examine how one can perform an ordered phase
calculation when such an ordered phase exists. Our discussion follows closely that of Brandt and Mielsch (1989,
1990); Freericks and Zlati´c (1998) and we consider only
the case of vanishing external magnetic field H = 0 and
the case when Efη has no η dependence.

We begin with the static itinerant-electron charge susceptibility in real space defined by (our extra factor of
2s + 1 makes the normalization simpler)



1
χ [cc] (Ri Rj) =
   - 2s + 1




- β



β dτ [Trcf ⟨e [−][β][H] n [c] i [(][τ] [)][n][c] j [(0)][⟩]

0 L

[H] [c] [−][β][H] Z [c]



Trcf ⟨e [−][β][H] n [c] i [⟩] Trcf ⟨e [−][β][H] n [c] j [⟩] ], (44)

- L L
Z Z



where Z�L 2s+1is the lattice partition function,
n [c] i = σ=1 [c] iσ [†] [c][iσ] and n [c] i [(][τ] [)] = exp[τ (H −
µN )]n [c] i [(0) exp[][−][τ] [(][H −] [µN] [)].] If we imagine introducing a symmetry breaking field − [�] i [h][¯][i][n] i [c] [to the]
Hamiltonian, then we can evaluate the susceptibility as
a derivative with respect to this field (in the limit where
h¯ = 0)






σ







klσ [(][iω][n][)]
Gjkσ(iωn) [dG][−][1]

dh [¯] i

kl



T
χ [cc] (Ri Rj) =
   - 2s + 1






n



dGjjσ (iωn) T

=
dh [¯] i  - 2s + 1




- 

n σ



Gljσ (iωn). (45)
dh [¯] i



Since G [−] klσ [1] [= [][iω][n][ +][ µ][ + ¯][h][k][ −] [Σ][kkσ][(][iω][n][)]][δ][kl][ −] [t] kl [∗] [/][2] √







d, we find



Gjkσ(iωn)Gkjσ (iωn) [d][Σ][kkσ][(][iω][n][)]

dGkkσ′ (iωm

m



dh [¯] i








- Gijσ (iωn)Gjiσ(iωn) +

 


dGkkσ′ (iωm)

[d][Σ][kkσ][(][iω][n][)]

dGkkσ′ (iωm) dh [¯] i



T
χ [cc] (Ri Rj) =
   - 2s + 1







n




,



σ



k






σ [′]



where we used the chain rule to relate the derivative of
the local self energy with respect to the field to a derivative with respect to G times a derivative of G with respect
to the field (recall, the self energy is a functional of the
local Green’s function). It is easy to verify that both
GijσGjiσ and dGjjσ /dh [¯] i are independent of σ (indeed,
this is why we set the external magnetic field to zero). If
we now perform a spatial Fourier transform of Eq. (46),
we find Dyson’s equation


    χ [cc] n [(][q][) =][ χ] n [cc][0][(][q][)][ −] [T] χ [cc] n [0][(][q][)Γ] nm [cc] [χ][cc] m [(][q][)][,] (47)

m



where we have defined



(46)


dGiiσ(iωn)

e [i][q][·][(][R][i][−][R][j] [)],
dh [¯] j



1
χ [cc] n [(][q][) =]
V



Ri−Rj











σ



1
2s + 1







χ [cc] n [0][(][q][) =][ −] [1]

V



Ri−Rj







Gijσ(iωn)Gjiσ(iωn)
σ



1
2s + 1



× e [i][q][·][(][R][i][−][R] - [j] [)],



1 1
Γ [cc] nm [=]
T 2s + 1







σσ [′]



dΣσ(iωn)
(48)
dGσ [′] (iωm) [,]



V is the number of lattice sites and χ [cc] (q) =


T [�] n [χ] n [cc][(][q][).] The fact that we have taken a Fourier
transform, implies that we are considering a periodic lattice here (like the hypercubic lattice); we will discuss
below where these results are applicable to the Bethe
lattice. Note that it seems like we have made an assumption that the irreducible vertex is local. Indeed,
the vertex for the lattice is not local, because the second functional derivative of the lattice Luttinger-Ward
functional with respect to G does have nonlocal contributions as d →∞. These nonlocal corrections are only
for a set of measure zero of q-values (Georges et al., 1996;
Hettler et al., 2000; Zlati´c and Horvati´c, 1990), and one
can safely replace the vertex by its local piece within any
momentum summations, which is why Eqs. (47) and (48)
are correct.
The local irreducible vertex function Γ can be determined by taking the relevant derivatives of the skeleton expansion for the impurity self energy in Eq. (33).
The self energy depends explicitly on Gn and implicitly
through w1. It is because w1 has G dependence that the
vertex function differs from that of the coherent potential
approximation (where the derivative of w1 with respect
to G would be zero). The irreducible vertex becomes



11


Substituting the irreducible vertex into the Dyson equation [Eq. (47)], then yields


χ [cc] n [(][q][) =][ χ] n [cc][0][(][q][) 1][ −] [(][∂][Σ][nσ][1] [/∂w][1][)][G][nσ][1] [γ][(][q][)], (50)

1 + χ [cc] n [0][(][q][)(][∂][Σ][nσ] 1 [/∂G][nσ] 1 [)][w] 1


with the function γ(q) defined by



∂w1
=
∂Gn 



 γ(q) =




- 
χ [cc] n [(][q][)]
n σ




- ∂w1

, (51)

∂Gnσ



σ



and we have chosen a particular spin state σ1 to evaluate the derivatives in Eq. (50) since they do not depend on σ1. Multiplying Eq. (50) by [�] σ [(][∂w][1][/∂G][nσ][)]
and summing over n yields an equation for γ(q). Defining Znσ = iωn + µ − λnσ = G [−] nσ [1] [+ Σ][nσ][ and noting that]
∂w1/∂Gn = [�] m [[][∂w][1][/∂Z][m][][][∂Z][m][/∂G][n][], allows us to re-]

place ∂w1/∂Gn by








- 1 G [2] n ∂G∂Σnn
 






G [2] n



∂w1
∂Zn




1 m ∂Z∂wm1
 - [�]



w1








-, (52)



1
Γ [cc] nm [=]
(2s + 1)T



��


∂Σnσ








∂Σm



∂w1



Gn



δσσ′ δmn
w1



∂Gnσ




- [�]



σσ [′]




∂w1




 ∂Σnσ
+







and solve the equation for γ(q) to yield



∂w1



Gnσ



. (49)



∂Gmσ′




  nσ [∂w][1][/∂Z][nσ][[1][ −] [G] n [2] [(][∂][Σ][n][/∂G][n][)][w] 1 []][/][[1 +][ G][n][η][n][(][q][)][ −] [G][2] n [(][∂][Σ][n][/∂G][n][)][w] 1 []]
γ(q) = (53)
1 − [�] nσ [∂w][1][/∂Z][nσ][G][n][η][n][(][q][)(][∂][Σ][n][/∂w][1][)][G][n] [/][[1 +][ G][n][η][n][(][q][)][ −] [G] n [2] [(][∂][Σ][n][/∂G][n][)][w][1] []] [,]



with ηn(q) defined by


ηn(q) = Gn



and





= UG [2] n (58)
Gn 1 + Gn(2Σn U ) [.]
        



 
1

 - G [1][2] n - χ [cc] n [0][(][q][)]




 
 - G [1]




, (54)



G [2] n




∂Σn

∂w1



and we have dropped the explicit σ dependence for G
and Σ. The full charge-density-wave susceptibility then
follows




  χ [cc] (q) = −T

n




[1 − γ(q)(∂Σn/∂w1)Gn ]G [2] n .
1 + Gnηn(q) G [2] n(∂Σn/∂Gn)w1
      


(55)
The derivatives needed in Eqs. (53) and (55) can be
determined straightforwardly:



2�s+1


σ=1



∂w1 = (2s + 1)w1(1 − w1)UG [2] n (56)
∂Znσ (1 + GnΣn)[1 + Gn(Σn U )] [,]
             






= [(1 +][ G][n][Σ][n][)[1 +][ G][n][(Σ][n][ −] [U] [)]]
w1 1 + Gn(2Σn U )



,
1 + Gn(2Σn U )
     


1 G [2] n
 



∂Σn

∂Gn



(57)



The final expression for the susceptibility and for γ(q)
appears in Table I.
The mixed cf susceptibilities can be calculated by
taking derivatives of w1 with respect to h [¯] i as shown
in Brandt and Mielsch (1989) and Freericks and Zlati´c
(1998). We won’t repeat the details here, just the end result in Table I. The calculation of the ff susceptibilities
is similar. By recognizing that we could have calculated
the cf susceptibility by adding a local f -electron chemical potential and taking the derivative of the itinerant
electron concentration with respect to the local field, we
can derive a relation between the cf and ff susceptibilities. These results are also summarized in the table.
In addition to charge susceptibilities, we also can calculate spin and pair-field susceptibilities for s > 0. We
consider the spin-one-half case in detail. The spin susceptibility vertex simplifies, since the off-diagonal terms


now cancel, and one finds a relatively simple result.
The mixed cf spin susceptibility vanishes (because the
Green’s function depends only on the total f -electron
concentration). The ff spin susceptibility is difficult to
determine in general, but it assumes a Curie form for
q = 0. The pair-field susceptibility is determined by employing a Nambu-Gor’kov formalism and taking the limit
where the pair-field vanishes. There is an off-diagonal
dynamical mean field analogous to λn and w1 depends
quadratically on this off-diagonal field. Hence, in the
normal state, the irreducible pair-field vertex is diagonal
in the Matsubara frequencies, just like the spin vertex.
This means the susceptibility is easy to calculate as a
function of the bare pair-field susceptibility



χ¯ [cc] n [0][(][q][) =][ −] [1]

V





Gij↑(iωn)Gji↓( iωn)e [i][q][·][(][R][i][−][R][j] [)] .

      Ri−Rj



(59)
The result appears in Table I.
The cc charge susceptibility diverges whenever γ(q) diverges, which happens when the denominator in Table I
vanishes. Since this denominator is identical for the cc,
cf, and ff susceptibilities, all three diverge at the same
transition temperature as we would expect. This yields
the same result as found in Brandt and Mielsch (1989,
1990) for the spinless case, except there is an additional
factor of 2s + 1 multiplying the sum in the denominator
arising from the 2s + 1 derivatives of w1, which are all
equal. This factor “essentially” increases Tc by 2s + 1
over that found in the spinless case. The existence of
a Tc is easy to establish, since the summation in the denominator goes to zero like 1/T [4] for large T and diverges
like C/T for small T . If C > 0, then there is a transition.
The q-dependence of the charge susceptibility comes
entirely from ηn(q) and hence from the bare susceptibility




  χ [cc] n [0][(][q][) =][ −]



Gn(k + q)Gn(k)

k



1
= − √1




- ∞



�1 − X [2]



ρ(ǫ)
dǫ
−∞ iωn +� µ Σn ǫ
       -       



- − −∞ n
iωn + µ − Σn − Xǫ
√1 X [2]



12


�d
in a single parameter X(q) = limd→∞ i=1 [cos][ q][i][/d]
�(M¨uller-Hartmann, 1989a) and we use F∞(z) =
dǫρ(ǫ)/(z − ǫ) to denote the Hilbert transform. The
results for χ [cc] n [0][(][q][) and][ η][n][(][q][) simplify for three gen-]
eral cases (Brandt and Mielsch, 1989): X = −1, which
corresponds to the “checkerboard” zone-boundary point
Q = (π, π, π, ...); X = 1, which corresponds to the uniform zone-center point q = 0; and X = 0, which corresponds to a general momentum vector in the Brillouin
zone [since the value of the cosine will look like a random
number for a general wave vector and the summation willgrow like √d, implying X → 0; only a set of measure zero

of momenta have X(q) ̸= 0]. The results for χ [cc] n [0][(][q][) and]
ηn(q) appear in Table II for the hypercubic lattice. Both
the uniform (X = 1) and the “checkerboard” (X = −1)
susceptibilities can be defined for the Bethe lattice, but
there does not seem to be any simple way to extend the
definition to all X. Indeed, higher-period ordered phases
on the Bethe lattice seem to have first-order (discontinuous) phase transitions (Gruber et al., 2001) so such a
generalization is not needed.


We will find that near half filling, the X = −1 charge
susceptibility diverges and far away from half filling the
X = 1 charge susceptibility diverges. The X = 0 susceptibility never diverges at finite T . This is also true
for the spin and pair-field susceptibilities. They are always finite at finite T . One can easily understand why
the spin susceptibility does not diverge—it arises simply
from the fact that the spins are independent of each other
and do not interact. Similarly, one can understand why
the pair-field susceptibility does not diverge—Anderson’s
theorem (Anderson, 1959; Bergmann and Rainer, 1974)
states that one cannot have superconductivity with a
static electron-electron interaction; the interaction must
be dynamic.


Since the (X = −1) “checkerboard” charge susceptibility diverges, we can also examine the ordered
state (Brandt and Mielsch, 1990). In this case, we have
a charge-density wave, with different electronic densities
on each of the two sublattices of the bipartite lattice.
Hence both G [A] nσ [(][G] nσ [B] [) and Σ][A] nσ [(Σ] nσ [B] [) are different on the]
two sublattices. Evaluating the momentum-dependent
Green’s functions yields



F∞
×



1 − X [2]




- n
, (60)



where all of the q-dependence can be summarized



G [A,B] nσ [(][q][) =] iωn + µ + gµBHmσ − Σ [B,A] nσ [+][ ǫ][q], (61)
(iωn + µ + gµBHmσ − Σ [A] nσ [)(][iω][n] [+][ µ][ +][ gµ][B][Hm][σ] [−] [Σ] nσ [B] [)][ −] [ǫ] q [2]


which can be summed over q to yield




    -    G [A] nσ [=] - dǫ Z¯nσρ( −ǫ) ǫ iωn + µ + gµZ¯nσBHmσ − Σ [B] nσ, G [B] nσ [=] dǫ Z¯nσρ( −ǫ) ǫ iωn + µ + gµZ¯nσBHmσ − Σ [A] nσ,




  Z¯nσ =



(iωn + µ + gµBHmσ − Σ [A] nσ [)(][iω][n] [+][ µ][ +][ gµ][B][Hm][σ] [−] [Σ] nσ [B] [)][.] (62)


13


TABLE I Static charge, spin, and pair-field susceptibilities for the Falicov-Kimball model. The charge susceptibility is given
for the general case, the spin susceptibility for spin-one-half (and only q=0 for the ff spin susceptibility), and the pair-field
susceptibility only for spin-one-half in the cc channel. Note that the cf charge susceptibility is equal to γ(q).



Charge χ [cc] (q) = T [�][∞] n=−∞ [1+Gn(2Σn −[1+U )]GGnn(2Σηn(nq−)+(1+U )−γG(nqΣ)Un])[1+G [2] n Gn(Σn−U )]
          χ [cf] (q) = γ(q)




      - ∞
n=−∞ [(2][s][+1)][w][1] [(1][−][w][1][)][UG][2] n [/][{][[1+][G][n][(2Σ][n][−][U] [)]][G][n][η][n][(][q][)+(1+][G][n][Σ][n][)[1+][G][n][(Σ][n][−][U] [)]][}]

= 1− [�] [∞] n=−∞ [(2][s][+1)][w][1] [(1][−][w][1][)][U] [2][G][3] n [η][n][(][q][)][/][(1+][G][n][Σ][n][)[1+][G][n][(Σ][n][−][U] [)]][{][[1+][G][n][(2Σ][n] [−][U] [)]][G][n][η][n][(][q][)+(1+][G][n][Σ][n][)[1+][G][n][(Σ][n][−][U] [)]][}]

χ [ff] (q) = 1− [�] [∞] n=−∞ [(2][s][+1)][w][1] [(1][−][w][1][)][U] [2][G][3] n [η][n][(][q][)][/][(1+][G][n][Σ][n][)[1+] w [G] 1 [n] (1 [(Σ] - [n] w [−] 1 [U] )/T [)]][{][[1+][G][n][(2Σ][n] [−][U] [)]][G][n][η][n][(][q][)+(1+][G][n][Σ][n][)[1+][G][n][(Σ][n][−][U] [)]][}]



=



Spin χ [′][cc] (q) = T [�][∞] n=−∞ [1+Gn(2Σn−U )]GGn [2] nη [[1+] n(q [G] )+(1+ [n][(2Σ][n] G [−] n [U] Σ [)]] n)[1+Gn(Σn−U )]
          χ [′][cf] (q) = 0
χ [′][ff] (q = 0) = w1/2T


              -               Pair-field χ¯ [cc] (q) = T [�][∞] n=−∞ [χ][¯] n [cc][0][(][q][)] 1 − |1+Gn(Σn−w[11−(1w−1w]U1))|U [2] [(1 [2] |1+−wG1n)Σ|1+n|G [2] |n1+(ΣGnn−(ΣUn)|− [2] +Uw)|1 [2] |1+Gn Σn| [2] ]


TABLE II Values of χ [cc] n [0][(][q][) and][ η][n][(][q][) for the special][ X]
points 1, 0, and −1 on the hypercubic lattice.



X(q) χ [cc] n [0][(][q][)] ηn(q)
−1 −Gn/(iωn + µ − Σn) λn
0 G [2] n 0
1 2[1−   - (iωn + µ − Σn)Gn]   - G [1] n [+] 2λ1n


The algorithm to solve for the Green’s functions is modified to the following: (i) start with a guess for Σ [A] nσ
and Σ [B] nσ [(or set both to zero); (ii) evaluate Eq. (62) to]
find G [A] nσ [and then determine][ G] 0 [A] σ [(][iω][n][) from Eq. (31)]
evaluated on the A sublattice [Σ [A] nσ [=][ {][G] 0 [A] σ [(][iω][n][)][}][−][1][ −]
(G [A] nσ [)][−][1][]; (iii) determine][ w] 0 [A] [and][ w] 1 [A] [from the appropri-]
ate A-sublattice generalization of Eq. (28); (iv) evaluate
Eq. (30) on the A-sublattice to find G [A] nσ [and Eq. (31) to]
find Σ [A] nσ [; (v) now find][ G][B] nσ [from Eq. (62) and][ G] 0 [B] σ [(][iω][n][)]
from Eq. (31); (vi) determine w0 [B] [and][ w] 1 [B] [from Eq. (28)]
on the B-sublattice; and (vii) evaluate Eq. (30) on the
B-sublattice to find G [B] nσ [and Eq. (31) to find Σ] nσ [B] [. Now]
repeat (ii–vii) until convergence is reached. We will need
to adjustculations are then finished and the order parameter is Ef − µf until (w1 [A] [+][ w] 1 [B][)][/][2 =][ w][1][. The cal-]
(for the static Holstein model (Ciuchi and de Pasquale,w1 [A] [−] [w] 1 [B][)][/][2. A similar generalization can be employed]
1999). Since the skeleton expansion for the self energy
in terms of the local Green’s function is unknown for the
static Holstein model (and hence it is not obvious how
to determine Γ), this is the most direct way to search for
the ordered checkerboard phase.



with iνl = 2iπlT the bosonic Matsubara frequency. Once
again we assume we are in zero magnetic field H = 0 and
the f -electron site-energy is η-independent Efη = Ef .
Our analysis follows the path-integral approach–one can
also employ a strong-coupling perturbation theory to derive these formulae (Shvaika, 2000, 2001). The dynamical susceptibilities of the FK model have some subtle
properties to them that arise from the fact that the local f -electron number is conserved. In particular, the
isothermal susceptibilities (calculated by adding an external field to the system, and determining how it modifies the system in the limit where the field vanishes)
and the so-called isolated (Kubo) susceptibilities [which
assume the system starts in equilibrium at zero field,



D. Dynamical Charge Susceptibility


We now examine the dynamical charge susceptibility (Freericks and Miller, 2000; Shvaika, 2000, 2001), defined by



1
χ [cc] (q, iνl) =
2s + 1




- β



dτe [iν][l][τ][ 1]
0 V



V







e [q][·][(][R][i][−][R][j] [)]

Ri−Rj




  Trcf ⟨e [−][β][H] n [c] i [(][τ] [)][n][c] j [(0)][⟩]
× L
Z

[−][β][H] [c] [−][β]



Trcf ⟨e [−][β][H] n [c] i [⟩] Trcf ⟨e [−][β][H] n [c] j [⟩]

- L L
Z Z




, (63)


then is removed from the thermal bath (isolated) and
the field is turned on slowly] differ from each other (the
response of the isolated system to the field is the isolated susceptibility) due to the conserved nature of the
f -electrons (Shvaika, 2001; Wilcox, 1968). In particular, the isolated susceptibility vanishes for the ff and
mixed cf susceptibilities [due to the fact that the local
f -electron number is conserved (i.e., [H, n [f] i [] = 0)], but]
is nonzero for the cc susceptibility. The divergence of
the static charge susceptibility arises entirely from the
coupling between the itinerant and localized electronic
systems; the pure itinerant electron response (isolated
susceptibility) never diverges. Hence the isothermal susceptibility is discontinuous at zero frequency (i.e., it is
not analytic). The continuous (analytic) susceptibility
is the isolated susceptibility, and we will spend our time
discussing it for the conduction electrons.
If we express the susceptibility as a matrix in Matsubara frequency space, we find the following Dyson equation:



14


which reduces to our static results for l = 0. The bare
dynamical susceptibility simplifies in three cases that are
summarized in Table III. Note that one needs to evaluate χ [cc][0] with l’Hˆopital’s rule whenever the denominator
vanishes and we dropped the spin subscripts in the Table. The irreducible charge vertex is calculated for the
impurity, and it satisfies



1
Γ(iωm, iωn; iνl) =
2s + 1






σ



1 δΣσ(iωm, iωm+l)
T δGσ(iωn, iωn+l) [,][ (66)]



χ [cc] (q, iωm, iωn; iνl)  = χ [cc][0] (q, iωm; iνl)δmn T
          - [′]



χ [cc][0] (q, iωm; iνl)
n [′]



Γ(iωm, iωn [′] ; iνl)χ [cc] (q, iωn [′], iωn; iνl), (64)
×



and the susceptibility is found by summing
Tover [�] mnthe [χ][cc][(][q] Matsubara [, iω][m][, iω][n][;][ iν][l][).] frequenciesOnce again,χ [cc] (q, iνthe barel) =
susceptibility depends only on the momentum parameter X, and takes the form



1
χ [cc][0] (X, iωm; iνl) =
      - 2s + 1







Gmσ(k)Gm+lσ(k+q)

kσ




- ∞



1
= − √1



�1 − X [2]



ρ(ǫ)
dǫ
−∞ iωm + µ �Σm ǫ
       -       


where we now have both a self energy and a Green’s
function that depend on two Matsubara frequencies, because these functions are not time-translation-invariant
in imaginary time. This occurs because we need to add a

               - β
time-dependent charge field 0 [dτχ][(][τ] [)][ �] σ [c] σ [†] [(][τ] [)][c][σ][(][τ] [)]
          to the action in order to evaluate the dynamic charge susceptibility and this time-dependent field removes timetranslation invariance from the system (it does not depend on the time difference of the arguments of the
fermionic variables).


TABLE III Values of χ [cc][0] (X, iωm; iνl) for the special X
points 1, 0, and −1 on the hypercubic lattice.

X(q) χ [cc][0] (X, iωm; iνl)
−1 −(Gm + Gm+l)/(iωm + iωm+l + 2µ − Σm − Σm+l)
0 GmGm+l

   1 −(Gm − Gm+l)/(iνl + Σm − Σm+l)


It is not easy to perform calculations for Green’s functions that depend on two time variables. The original
work by Brandt and Urbanek (1992) illustrates how to
proceed. We start with the definition of an auxiliary
Green’s function



F∞
×




- − −∞ m
iωm+l + µ − Σm+l − Xǫ
√1 X [2]



1 − X [2]




- m
, (65)




        -        -        ��          - β
gσ [aux] (τ, τ [′] ) = − TrcTτ e [−][β][H][0] �exp σ¯ 0 [d] �� [τχ][¯] β [(¯][τ] [)][c] σ [†] ¯ [(¯][τ] [)] �� [c][σ][¯] 2 [(¯] s [τ] +1 [)] cσ(τ )c [†] σ [(][τ][ ′][)], (67)

1 + e [βµ] exp 0 [d][τχ][¯] [(¯][τ] [)]



dτ [′] e [iω][m][τ] gσ [aux] (τ, τ [′] )e [−][iω][n][τ][ ′],(68)
−β+τ



where H0 = −µ [�] σ [c] σ [†] [c][σ] [and the time-dependence is]

with respect to H0 [the auxiliary time-dependent field
χ(τ ) = [�] l [χ][(][iν][l][) exp(][−][iν][l][τ] [) should not be confused with]

any susceptibility]. It is easy to show that this auxiliary
Green’s function is antiperiodic with respect to either τ
variable being increased by β. Hence, we can perform a
double Fourier transform to yield


gσ [aux] (iωm, iωn)



T
gσ [aux] (iωm, iωn) =
      Z [aux]




  - β
= T



β - τ

dτ
0 


and this is the same Matsubara-frequency dependence
as in Eq. (66). Substituting in the fermionic Grassman
variables from Eq. (13) and restricting ourselves to χ
fields that satisfy χ(iν0) = 0 produces the following pathintegral form for the auxiliary Green’s function:




Dψ [¯] Dψψmσψ [¯] nσ


× exp




 T



m [′] n [′]



(iωm′ + µ)δm′n′
{
σ [′]







+ χ(iωn′ iωm′) ψ [¯] n′σ′ ψm′σ′
    - }



, (69)



15


matrices, and the −1 superscript denotes the inverse of
the corresponding matrix.
Eq. (73) can be rearranged by multiplying on the left
or the right by matrices like G [−][1], G [−] 0 [1][, and][ G] 0 [−][1] - U to
produce the following two matrix equations (with matrix
indices and spin indices suppressed)


G [−] 0 [2] (U + G [−][1] )G [−] 0 [1] + (1 w1)UG [−][1] = 0, (74)

   -   

G [−] 0 [2]  - G [−] 0 [1][(][U][ +][ G][−][1][) + (1][ −] [w][1][)][UG][−][1][ = 0][.] (75)

Adding these two equations together and collecting terms
results in

- �2
G [−] 0 [1] - [1] 2 [(][U][ +][ G][−][1][)] - 4 [1] [(][U] [+][G][−][1][)][2][+(1][−][w][1][)][UG][−][1][ = 0][.]

(76)
Now we substitute the matrix self energy Σ for G0, with
the self energy defined by Dyson’s equation


Σ(iωm, iωn) = [G [−] 0 [1][]][mn][ −] [[][G][−][1][]][mn][,] (77)


to yield a matrix quadratic equation



where Z [aux] = [1+e [βµ] ] [2][s][+1] is the auxiliary partition function for χ(iν0) = 0. We calculate the Green’s function by
adding an infinitesimal field T ¯χmnσψ [¯] nσψmσ and noting
that gσ [aux] (iωm, iωn) = ∂ ln /∂χ¯mnσ. We will restrict
Z [aux]
our discussion to the case where only one Fourier component χ(iνl) is nonzero. The matrix then has a nonzero
diagonal, and one nonzero off-diagonal, whose elements
are all equal to χ(iνl). Now the partition function is the
determinant of the matrix that appears in the action of
Eq. (69), which assumes the simple form of the product of
all diagonal elements (multiplied by a constant to assure
the correct limiting behavior)



�2

[1] 2 [(][U][ +][ G][−][1][)] - 4 [1]



4 [(][U] [+][G][−][1][)][2][+(1][−][w][1][)][UG][−][1][ = 0][.]



�2s+1

. (70)



Z [aux] =





�∞
2e [βµ/][2]


n=−∞



iωn + µ

iωn



When we add the extra field ¯χσ to the action, the eigenvalues of the matrix change only for m = n, m + l = n,
and the σ value of the ¯χσ field. The former case is the diagonal matrix element, which is simply shifted by ¯χmmσ.
The shift in the latter case can be worked out via perturbation theory to lowest order in ¯χ. We find the mth and
m + lth eigenvalues change to iωm + µ - χ¯m+lmχ(iνl)/iνl
and iωm+l + µ + ¯χm+lmχ(iνl)/iνl, respectively. Taking
the relevant derivatives to calculate the auxiliary Green’s
function, then yields




[1] �2 = [1]

2 [(][G][−][1][ −] [U] [)] 4




Σ + [1]



4 [[][U][ 2][ + 2(2][w][1][ −] [1)][UG][−][1][ +][ G][−][2][]][,]



δmn
gσ [aux] (iωm, iωn) = �iωm + µ [+][ δ][m][+][ln] iν [χ] l [(][iν][l][)]



iνl




. (71)




 - m l
1 1
× iωm+l + µ iωm + µ

[−]



(78)
that relates the self energy to the Green’s function. In
the case where only one Fourier component l ̸= 0 of χ is
nonzero, both the self energy and the Green’s function
are nonzero on the diagonal m = n and on the diagonal shifted by l units m + l = n. Substituting into
the quadratic equation, and solving for the shifted diagonal component of the self-energy [to first order in χ(iνl)]
yields the amazingly simple result



As before, we define G0 by adding a λσ field to the
action in Eq. (69) T λnσψ [¯] nσψnσ (and change the partition function normalization accordingly). It is easy
to show (Brandt and Urbanek, 1992; Zlati´c et al., 2001)
that due to the fact that one can write the partition
function of a path integral with a quadratic action as
Z = det g [−][1], with g the corresponding Green’s function,
one discovers


G [−] 0 [1] = [g [aux] ] [−][1] λ11. (72)

          
The full Green’s function involves an additional trace
over f -states. The “itinerant-electron” piece of the impurity Hamiltonian equals −µ [�] σ [c] σ [†] [c][σ][ when][ n][f][ = 0 and]
equals (U − µ) [�] σ [c] σ [†] [c][σ] [when][ n][f][ = 1. It is a straightfor-]

ward exercise to then show that


Gσ(iωm, iωn) = w0G0σ(iωm, iωn) + w1[G [−] 0σ [1] mn [,]

[−] [U] [1][1]][−] (73) [1]
with w0 given by Eq. (28) for H = 0 and w1 = 1 − w0.
Note that all of the Green’s functions in Eq. (73) are



after some tedious algebra. In Eq. (79), the symbols Σm
and Gm denote the diagonal components of the self energy and the Green’s function, respectively, which are
equal to the results we already calculated for the self energy and Green’s function when χ(iνl) = 0.
We can now calculate the irreducible dynamical charge
vertex from Eq. (66), which yields


1 Σm Σm+l
Γ(iωm, iωn; iνl=0) = δmn     - . (80)
T Gm Gm+l
                
The dynamical charge vertex is then a relatively simple object for l ̸= 0 [the static vertex is much more
complicated, as can be inferred from Eqs. (48), (49),
and (52)]. The original derivation, based on the atomic
limit (Shvaika, 2000, 2001), produced a much more complicated looking result for the vertex, but some tedious
algebra shows that the two forms are indeed identical (Freericks and Miller, 2000). Using this result for the



Σ(iωm, iωm+l) = G(iωm, iωm+l) [Σ][m][ −] [Σ][m][+][l], (79)

Gm Gm+l
               

vertex, we immediately derive the final form for the dynamical charge susceptibility on the imaginary axis




   χ [cc] (X; iνl=0) = T

m



.

[Σ][m][−][Σ][m][+][l]

Gm−Gm+l



χ [cc][0] (X, iωm; iνl)



1 + χ [cc][0] (X, iωm; iνl) [Σ][m][−][Σ][m][+][l]



(81)
Note, that if we evaluate the uniform, dynamical charge
susceptibility q = 0 (X = 1), we find




    χ [cc] (X = 1, iνl=0) = T
        
m



Gm Gm+l
  - = 0, (82)

iνl



16


illustrate here how to determine the optical conductivity, the thermopower, the thermal conductivity, and the
response to inelastic light scattering.
The Kubo formula relates the response function to the
corresponding current-current correlation functions. Before we discuss how to calculate such correlation functions, it makes sense to describe the different transport
currents that we consider. Each current (except the heat
current) takes the generic form



2�s+1


σ=1





γa(k + q/2)c [†] k+qσ [c][k][σ][,] (83)
k



which is what we expect, because the total conduction
electron charge commutes with the Hamiltonian, and
hence has no τ -dependence, implying only the static response can be nonzero. Note that χ [cc][0] (X = 1) ̸= 0,
the vertex corrections are needed to produce a vanishing
total susceptibility.
In general, one is interested in the dynamical charge
response on the real axis. To find the real (dynamical)
response, we need to perform an analytical continuation
of Eq. (81) to the real axis. Since the isothermal susceptibility is discontinuous at νl = 0, we can perform
the analytic continuation only for the isolated susceptibility. The procedure is straightforward: we divide the
complex plane into regions where the Green’s functions,
self energies, and susceptibilities are all analytic, and we
express the Matsubara summations as contour integrals
over the poles of the Fermi-Dirac distribution function.
Then, under the assumption that there are no poles in
the integrands other than those determined by the fermi
factors, we deform the contours until they are parallel to
the real axis. After replacing any fermi factors of the form
f (ω+iνl) by f (ω), we can make the analytic continuation
iνl ν + i0 [+] . The final expressions are straightforward,
but cumbersome. We summarize them for → X = −1 and
X = 0 in Table IV. Only the X = −1 result is meaningful for the Bethe lattice. Note that one could just as
easily calculate the incommensurate dynamical charge
response, but the equations become significantly more
complicated. We will calculate a similar result when we
examine inelastic X-ray scattering below.
One can test the accuracy of the analytic continuation by employing the spectral formula for the dynamical charge susceptibility and calculating the charge susceptibility at each of the bosonic Matsubara frequencies.
Comparing the spectral form with the result found directly from Eq. (81) is a stringent self-consistency test.
In most calculations, these two forms agree to at least
one part in a thousand.


E. Static and Dynamical Transport


Some of the most important many-body correlation
functions to determine are the correlation functions related to transport properties via their corresponding
Kubo formulas (Greenwood, 1958; Kubo, 1957). Transport can also be solved exactly in the FK model, and we



If Eq. (85) is satisfied, then the corresponding currentcurrent correlation function is given by the bare bubble
depicted by the first diagram on the right-hand-side of
Fig. 2 (a).
One case where there are no vertex corrections is the
optical conductivity, which is constructed from a q = 0
current-current correlation function. We consider the
case where the only effect of the magnetic field is from the
Zeeman splitting of the states (which is accurate in large



ja(q) =



with γa(k) the corresponding current vertex function.
The heat-current operator takes the form



γ¯Q(k, k [′] )c [†] kσ [c][k][′][σ]
kk [′]



��







jQ(0) =



2�s+1


σ=1




   γQ(k)c [†] kσ [c][k][σ][ +]
k kk [′]



(84)
with γQ(k) the vertex that arises from the kinetic energy
and ¯γQ(k, k [′] ) the vertex from the potential energy. For
conventional charge, and thermal transport, we are interested only in the q → 0 (uniform) limit of the current
operators, but the finite-q dependence is important for
inelastic (Raman) scattering of X-ray light. The current
vertex functions are summarized in Table V.
The Dyson equation for any current-current correlation
function takes the form shown in Fig. 2, which is similar
to that given by Eq. (64), but the bare and interacting
susceptibilities are now different due to the corresponding γa factors. Note that there are two coupled equations
illustrated in Figs. 2 (a) and (b); these equations differ by
the number of γa factors in them (of course, there is only
one equation when γa = 1 as we saw for the dynamical
charge susceptibility). Note further, that one could evaluate mixed current-current correlation functions where
there is a γa on the left vertex and a γb on the right vertex, but we don’t describe that case in detail here. The
irreducible vertex function Γ is the dynamical charge vertex of Eq. (80) which has the full symmetry of the lattice. If the vertex factor γa does not have a projection
onto the full symmetry of the lattice, then there are no
vertex corrections from the local dynamical charge vertex (Khurana, 1990). This occurs whenever







γa(k + [q]

2

k



2 [)][G][nσ][(][k][)][G][n][+][lσ][(][k][ +][ q][) = 0][.] (85)


17


TABLE IV Dynamical charge susceptibility on the real axis for X = −1 and X = 0 (the dynamical susceptibility vanishes for
X = 1).



X Dynamical susceptibility χ [cc] (X, ν)



−1 2iπ �−∞∞ [dω]







f (ω) 1−[G(ω)+G(ω+ν[)][Σ(G(ωω)+)−GΣ((ωω++ν)]ν)]/[2/[2ωω+2+2µµ++ν+Σ(ν+Σ(ωω)−)−Σ(Σ(ωω++ν)]ν)][G(ω)−G(ω+ν)]



f (ω + ν) 1−[G [∗] (ω)+G [∗] (ω+ν[)][ΣG [∗] ( [∗] ω(ω)+)−GΣ [∗] ( [∗] ω(ω++ν)]ν)]/[2/[2ωω+2+2µµ++ν+Σν+Σ [∗] ( [∗] ω(ω)−)−ΣΣ [∗] ( [∗] ω(ω++ν)]ν)][G [∗] (ω)−G [∗] (ω+ν)]









[f (ω) f (ω + ν)] 1−[G [∗] (ω)+G(ω+ν[)][ΣG [∗] ( [∗] ω(ω)+)−GΣ((ωω++ν)]ν)]/[2/[2ωω+2+2µµ++ν+Σν+Σ [∗] ( [∗] ω(ω)−)−Σ(Σ(ωω++ν)]ν)][G [∗] (ω)−G(ω+ν)]

- 


0 2iπ �−∞∞ [dω]







f (ω) 1−G(ω)G(ω+ν)[Σ(Gω()ω−)GΣ((ωω++νν))]/[G(ω)−G(ω+ν)] 1−G [∗] (ω)G [∗] (ω+ν)[ΣG [∗] ( [∗] ω()ω−)GΣ [∗][∗] ((ωω++νν))]/[G [∗] (ω)−G [∗] (ω+ν)]

[−] [f] [(][ω]                                       - [ +][ ν][)]




[f (ω) f (ω + ν)] 1−G [∗] (ω)G(ω+ν)[ΣG [∗] ( [∗] ω()ω−)GΣ((ωω++νν))]/[G [∗] (ω)−G(ω+ν)]

   -    

TABLE V Current vertex functions for use in Eqs. (83) and
(84). The symbols e [I] α [and][ e] α [O] [are the polarization vectors for]
the incident and outgoing light, respectively, and a denotes
the lattice spacing. An overall factor depending on properties
of the incident and outgoing light is neglected for the inelastic
light scattering vertex.



Current type vertex function γa(k)
Charge γn(k) = iea ǫ(k)/ℏ
∇
Heat γQ(k) = ia ǫ(k)[ǫ(k) µ]/ℏ
∇        γ¯Q(k, k [′] ) = iaU [ ǫ(k) + ǫ(k [′] )]W (k k [′] )/2ℏ
∇ ∇         W (k) = [�] [exp(] [i][k] [ R][j][)][ �] [f][ †] [f][jη][/V]



j [exp(][−][i][k][ ·][ R][j][)][ �]

[2]



Inelastic γL(k) = [�]



Inelastic γL(k) = αβ [e] α [I] ∂∂k [2] αǫ∂(kk)β [e] β [O][∗]

light scattering



η [f] jη [ †] [f][jη][/V]



dimensions, because the phase factors induced in the hopping matrix occurs only in one dimension). We illustrate
here how to calculate the optical conductivity on the
hypercubic lattice (Moeller et al., 1992; Pruschke et al.,
1993a,b, 1995). The starting point is the current-current
correlation function on the imaginary lattice, which is
equal to the bare bubble diagram in Fig. 2 (a)




  
e [2]

da [d][−][2] ℏ [2]






n





sin [2] (k1)Gnσ(k)Gn+lσ(k),

k







FIG. 2 Coupled Dyson equations for current-current correlation functions described by the vertex function γa. Panel
(a) depicts the Dyson equation for the interacting correlation function, while panel (b) is the supplemental equation
needed to solve for the correlation function. The symbol Γ
stands for the local dynamical irreducible charge vertex given
in Eq. (80). In situations where Eq. (85) is satisfied, there
are no charge vertex corrections, and the correlation function
is simply given by the first diagram on the right hand side of
panel (a).


1
× iωn+l + µ + gµBHmσ − Σn+lσ − ǫ [.][(87)]

Note that the optical conductivity is a 1/d correction.
The analytic continuation is performed in the same fashion as was done for the dynamic charge susceptibility. The optical conductivity is defined to be σ(ω) =
Imχ [nn] (ν)/ν, so the final result is



e [2]
χ [nn] (iνl) =



σ



(86)
where we have chosen the 1 direction for the velocity operator and the n superscript denotes the particle-number
(charge) current operator (note our energy unit t [∗] equals
1 so it is suppressed). The average of sin [2] (k1) (times a
function of ǫk) is equal to 1/2 times the integral over ǫ
of the function times the density of states. Hence, the
current-current correlation function becomes




- ∞

dǫρ(ǫ)
−∞



e [2]
χ [nn] (iνl) =

2da [d][−][2] ℏ [2]



2�s+1



σ=1




- ∞



∞ - ∞

dǫρ(ǫ)
−∞ −∞



�∞


n=−∞



1
× iωn + µ + gµBHmσ − Σnσ − ǫ



σ(ν) = σ0



2�s+1


σ=1



dωAσ(ǫ, ω)Aσ(ǫ, ω + ν)
−∞


[f] [(][ω][)][ −] [f] [(][ω][ +][ ν][)], (88)
× ν



18


L12

S = [k][B], (94)

e T L11
| |



with σ0 = e [2] π [2] /hda [d][−][2] (which is approximately 4.3 ×
10one factor of [3] Ω [−][1] -cm [−][1] ℏinis needed to construct the dimensionless d = 3 with a ≈ 3 × 10 [−][8] cm). Note that
energy unit when multiplied by ν in the denominator,
which is why only one factor of h appears in σ0.
Eq. (88) can be simplified further by performing the
integral over ǫ. This is done by using Eq. (36) to rewrite
both spectral functions as an imaginary part of a Green’s
function, and noting that the imaginary part of z is (z −
z [∗] )/2i. The integral over ǫ can then be performed after
expanding each integrand by partial fractions to yield



and



κe = [k] B [2]
T




L22
  - [L][12] L11 [L][21]




, (95)



with kB the Boltzmann constant. The individual transport coefficients are determined by the zero-frequency
limit of the analytic continuation of the relevant polarization operators Lij = limν→0 Re[iL [¯] ij(ν)/ν] with



, (96)
L
Z




Gσ(ω) − G [∗] σ [(][ω][ +][ ν][)]
ν + Σ� σ(ω) − Σ [∗] σ(ω + ν)




     - β
L¯11(iνl) =




- ∞

dωRe
−∞



σ0
σ(ν) =
2π [2]



2�s+1


σ=1



β τ e [−][β][H] jn(τ )jn(0)

dτe [iν][l][τ] Trcf ⟨T ⟩
0 L



Gσ(ω) Gσ(ω + ν)
     
- ν + Σσ(ω) Σσ(ω + ν)
      



f (ω) − f (ω + ν)



(89).
ν




     - β
L¯12(iνl) =



β τ e [−][β][H] jn(τ )jQ(0)

dτe [iν][l] [τ] Trcf ⟨T ⟩
0 L



, (97)
L
Z



On another lattice, the optical conductivity takes the
form of Eq. (88) but with an extra factor of v [2] (ǫ). Enforcing the optical sum rule (which relates the integral
of the optical conductivity to the average kinetic energy)
(Chattopadhyay et al., 2000; Maldague, 1977) produces
a differential equation for v [2] (ǫ)


d
(90)
dǫ [[][v][2][(][ǫ][)][ρ][(][ǫ][)] +][ ǫρ][(][ǫ][) = 0][,]

with the boundary condition that v [2] (ǫ) → 0 at the band
edges (where appropriate). On the hypercubic lattice
one needs to sum the optical conductivity over all d
axis directions to be able to be put in the above form;
solving the differential equation gives v [2] (ǫ) = 1/2 as
expected. For the infinite coordination Bethe lattice,
one finds v [2] (ǫ) = (4 − ǫ [2] )/3. This agrees with the
conjectured result (Chung and Freericks, 1998; Velick´y,
1969), but it relies on enforcing the sum rule for the
Bethe lattice, which has not been established independently (van Dongen and Bl¨umer, 2002).
If we take the limit ν → 0 on the hypercubic lattice,
we find



and




     - β
L¯ 22(iνl) =



, (98)
L
Z



β τ e [−][β][H] jQ(τ )jQ(0)

dτe [iν][l] [τ] Trcf ⟨T ⟩
0 L




- 2�s+1

τσ(ω), (91)
σ=1



where the subscripts n and Q denote the number
(charge) and heat currents respectively (and we suppressed the Cartesian vector indices). All of these correlation functions are determined by their corresponding bare bubbles, because there are no vertex corrections for any of them. Note that our sign convention for
the thermopower is that of Ashcroft and Mermin (1976),
where the coefficient multiplying L12/L11 is positive for
negatively charged carriers. This leads to the situation where electron-like transport has a positive thermopower, and hole-like transport has a negative thermopower at low temperature. (The sign of the thermopower varies depending on what convention is used
for the definition of S in terms of the transport coefficients.) A theorem by Jonson and Mahan (1980, 1990)
says that even in a correlated system, there is a simple relation between these different transport coefficients

[that they reproduce the so-called Mott noninteracting
form (Chester and Thellung, 1961)]




- ∞



σdc = σ0



∞ 
dω
−∞ - [df] dω [(][ω][)]



dω




- 2�s+1

τσ(ω)ω [i][+][j][−][2] . (99)
σ=1



with the spin-dependent relaxation time equal to

τσ(ω) = [Im][G][σ][(][ω][)]

ImΣσ(ω) [+ 2]

2Re [ω + µ + gµBHmσ Σσ(ω)]Gσ(ω)(92).

   - {   - }

In addition, one is often interested in thermal transport
quantities such as the thermopower S and the electronic
contribution to the thermal conductivity κe. These three
quantities are usually expressed in terms of three different
transport coefficients L11, L12 = L21 and L22 as follows:


σdc = e [2] L11, (93)



Lij = [σ][0]

e [2]




- ∞



∞ 
dω
−∞ - [df] dω [(][ω][)]



dω



What is remarkable, is that in the case of the FK
model, one can explicitly calculate the relevant correlation functions and verify directly the Jonson-Mahan theorem (Freericks and Zlati´c, 2001b, 2002a). The derivation is too long to reproduce here. Note that we have
taken the more modern definitions of the Lij coefficients here, which has one less power of T than the normalization used by Freericks and Zlati´c (2001b, 2002a);
Jonson and Mahan (1980, 1990).


19



The final transport property we determine is the scattering of inelastic light. When optical photons are used,
this corresponds to conventional electronic Raman scattering: inelastic light scattering off of the charge excitations of the many-body system. When higher-energy
(X-rays) are employed, one scatters the photon off of the
momentum and frequency-dependent charge excitations
of the system. The Raman scattering limit results in the
limit q → 0. For simplicity, we consider only the spinless
case, with H = 0.
Inelastic light scattering depends on the polarizations
of the incident and outgoing light. As such, it provides
some additional symmetry resolution over and above the
elastic scattering of an optical conductivity measurement. There are traditionally three main symmetries
considered in Raman scattering experiments: (i) A1g
which has the full symmetry of the lattice; (ii) B1g which
has a d-wave symmetry and (iii) B2g which is another
d-wave symmetry. Each symmetry is chosen by different
polarizations for the incident and scattered light. Here
we concentrate on nonresonant Raman scattering, where
the vertex functions are not functions of the photon energies. If we sum over the d pairs of polarizations, where
e [I] = e [O] and each vector points along each of the different
Cartesian axes, then we have the A1g sector. If we choose
e [I] = (1, 1, 1, ...) and e [O] = (1, −1, 1, −1, ...), then we have
the B1g sector. And if we choose e [I] = (1, 0, 1, 0, ...)
and e [O] = (0, −1, 0, −1, ...) then we have the B2g sector. If we have just nearest-neighbor hopping, then the
B2g response vanishes because γB2g = 0. Following the
form given in Table V, we find γA1g (q) = ǫ(q) and
               γB1g (q) = t [∗] [�][∞] j=1 [cos][ q] j [(][−][1)][j][/] √d.

A straightforward calculation, using Eq. (85), shows
that the B1g response has no vertex corrections on the
zone diagonal q = (q, q, q, q, ...). Hence, the zonediagonal B1g response is the bare bubble. The A1g response (and the B1g off of the zone diagonal), on the
other hand, does have vertex corrections, and is more
complicated. The calculation of each response function
is straightforward, but tedious. One needs to first solve
the coupled equations depicted in Fig. 2 on the imaginary
axis and then perform the analytic continuation as we
have done previously for other response functions. The
end result is quite long and is summarized in Tables VI
and VII.
It is interesting to take the limit of conventional Raman
scattering with optical photons, where� q → 0 (X → 1).
In this case, one finds χ0 = − dǫρ(ǫ)/[ω + µ − Σ(ω) −
ǫ][ω +ν +µ−Σ(ω +ν)−ǫ] and the B1g response simplifies
to



Now using the definition of the spectral function
in Eq. (36), and taking the imaginary part of
Eq. (100) produces the so-called Shastry-Shraiman relation (Shastry and Shraiman, 1990, 1991) which relates
the imaginary part of the nonresonant B1g Raman response function to the optical conductivity


ImχB1g (ν) νσ(ν), (101)
∝

which was first proved in Freericks and Devereaux
(2001b).
Another interesting limit is the q = (π, π, π, ...) (X =
−1) limit, where we find χ [′] 0 [= ˜][χ] 0 [′] [= 0, ¯][χ][0][ =][ χ][0][/][2, and]
χ˜¯0 = ˜χ0/2. In this case, the renormalization due to the
dynamical charge vertex exactly cancels in the numerator and denominator, and one finds the same result for
the inelastic X-ray scattering in the A1g and B1g sectors. Hence, a polarized measurement of the inelastic
X-ray scattering at the zone boundary determines the
relative importance of nonlocal charge fluctuations to the
strongly correlated system. This is quantified by comparing the scattering in the two different symmetry sectors;
the difference in the results is a measure of the nonlocal
correlations.
We have produced results for inelastic X-ray scattering only along the zone diagonal. One could choose other
directions as well. In general, we find that the symmetries from different channels then mix, and both A1g and
B1g channels are renormalized by the irreducible dynamic
charge vertex. The formulas in that case are complicated
and will not be presented here.
One could also study resonant (or mixed) Raman response functions. The formalism is similar to the nonresonant case, except it is better to work directly on
the real axis. These calculations have not yet been
completed by anyone. But a simple power-counting
analysis of the different symmetry sectors can be performed (Freericks and Devereaux, 2001b). What is found
is that the A1g sector has contributions from the nonresonant, the mixed diagrams, and the resonant diagrams.
The B1g sector is either nonresonant or resonant, but the
mixed contributions disappear as 1/d. The B2g response
is purely resonant.


F. Single-Particle Properties (Localized Electrons)


We now study f -electron properties. Since the local
f -electron number is conserved, one might believe that
the localized particle dynamics are trivial. Indeed, this
is true for the particle number, but the fermionic electron degrees of freedom are nontrivial, even if they are



1
f (ω + ν)

- ω + µ Σ [∗] (ω) ǫ

  
        -        



  
        -        
1
× ω + ν + µ Σ [∗] (ω + ν) ǫ
      -       


1

- ω + ν + µ Σ(ω + ν) ǫ
      -       


��
. (100)



i
χB1g (ν) = 4π




- ∞



∞ - ∞

dω
−∞ −∞



dǫρ(ǫ)
−∞




 - −∞ −∞
1
f (ω)
× ω + ν + µ Σ(ω + ν) ǫ

  
         -         



  1 1
× ω + µ Σ(ω) ǫ ω + µ Σ [∗] (ω) ǫ
     -     - [−]     -     





20


TABLE VI Response functions for inelastic X-ray scattering by a photon of momentum q = (q, q, q, ...) along the zone diagonal
described by the parameter X(q) = cos q for the A1g and B1g sectors. The symbols with χ0 appear in Table VII and ∗ denotes
complex conjugation.



Scattering response function
χ�A1g (q, ν) = 2iπ �−∞∞ [dω]



( [ω] ω [+] + [ν] ν [)] ) [[][χ][0][(][ω][;][X,ν][)¯][χ][0][(][ω][;][X,ν][)][−][χ] 0 [′][2][(][ω][;][X,ν][)]] χ¯ [∗] 0 [(][ω][;][X,ν][)+][ Σ] G [∗][∗] [(] ( [ω] ω [)] ) [−] - [Σ] G [∗][∗][(] ( [ω] ω [+] + [ν] ν [)] )

f (ω + ν)
G [Σ(] ( [ω] ω [)] ) [−] - [Σ(] G( [ω] ω [+] + [ν] ν [)] ) [χ][0][(][ω][;][X,ν][)] - 1+ G [Σ][∗][∗][(] ( [ω] ω [)] ) [−] 


f (ω) χ¯0(ω;X,ν)+ G [Σ(] ( [ω] ω [)] ) [−] - [Σ(] G( [ω] ω [+] + [ν] ν [−][)] )



G [Σ(] ( [ω] ω [)] ) [−] - [Σ(] G( [ω] ω [+] + [ν] ν [)] ) [[][χ][0][(][ω][;][X,ν][)¯][χ][0][(][ω][;][X,ν][)][−][χ] 0 [′][2][(][ω][;][X,ν][)]]



G [∗] [(] ( [ω] ω [)] ) [−] - [Σ] G [∗][(] ( [ω] ω [+] + [ν] ν [)] ) [[][χ] 0 [∗][(][ω][;][X,ν][)¯][χ][∗] 0 [(][ω][;][X,ν][)][−][χ][′∗] 0 [2] (ω;X,ν)]



1+ [Σ(][ω][)][−][Σ(][ω][+][ν][)]



1+ [Σ][∗][∗][(][ω][)][−][Σ][∗][∗][(][ω][+][ν][)]



G [∗] (ω)−G [∗] (ω+ν) [χ] 0 [∗][(][ω][;][X,ν][)]




[f (ω) f (ω + ν)] χ˜¯0(ω;X,ν)+ G [Σ][∗][∗] [(] ( [ω] ω [)] ) [−]  - [Σ(] G( [ω] ω [+] + [ν] ν [)] )

- - 1+ G [Σ][∗][∗] ( [(] ω [ω] ) [)] - [−]







G [Σ][∗] [(] ( [ω] ω [)] ) [−] - [Σ(] G( [ω] ω [+] + [ν] ν [)] ) [[ ˜][χ][0][(][ω][;][X,ν][)˜¯][χ][0][(][ω][;][X,ν][)][−][χ][˜] 0 [′][2][(][ω][;][X,ν][)]]



1+ [Σ][∗][∗][(][ω][)][−][Σ(][ω][+][ν][)]



G [∗] (ω)−G(ω+ν) [χ][˜][0][(][ω][;][X,ν][)]



χB1g (q, ν) = 4iπ �−∞∞ [dω][ {][f] [(][ω][)][χ][0][(][ω][;][ X, ν][)][ −] [f] [(][ω][ +][ ν][)][χ] 0 [∗][(][ω][;][ X, ν][)][ −] [[][f] [(][ω][)][ −] [f] [(][ω][ +][ ν][)]˜][χ][0][(][ω][;][ X, ν][)][}]



TABLE VII Symbols χ0, χ [′] 0 [, ¯][χ][0][, ˜][χ][0][, ˜][χ][′] 0 [, and ˜¯][χ][0] [that appear in Table VI]



Symbol



χ0(ω; X, ν) = − �−∞∞ [dǫρ][(][ǫ][)] ω+µ−Σ(1 ω)−ǫ √1−1







1−X [2][ F][∞]




ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



1−X [2]











χ˜0(ω; X, ν) = − �−∞∞ [dǫρ][(][ǫ][)] ω+µ−Σ1 [∗] (ω)−ǫ √1−1




- 1−X
ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



1−X [2]



1 1

[ω+µ−Σ(ω)−ǫ] [2] √1



1−X [2][ F][∞]




    χ [′] 0 [(][ω][;][ X, ν][) =][ −]




     
X - ∞

8 −∞ [dǫρ][(][ǫ][)]



1+X



1�−X

ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



���







1−X [2][ F][∞]



1−X [2]



+ ω+µ−Σ(1 ω)−ǫ 1−2X [2]




1 + [ω][+][ν][+][µ][−][Σ(][ω][+][ν][)]

 - √1−X [2]



1−�X

X - ∞ 1 1

8 −∞ [dǫρ][(][ǫ][)] [ω+µ−Σ [∗] (ω)−ǫ] [2] √1



F∞
1−X [2]




- 1−X
ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



1−X [2]




    χ˜ [′] 0 [(][ω][;][ X, ν][) =][ −]



1+X




ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



���







1−X [2]




- 1−X
ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



1−X [2][ F][∞]



+ ω+µ−Σ1 [∗] (ω)−ǫ 1−2X [2]




1 + [ω][+][ν][+][µ][−][Σ(][ω][+][ν][)]

 - √1−X [2]



1−X  - 1−X

[X]  - ∞ 1 1

4 −∞ [dǫρ][(][ǫ][)] [ω+µ−Σ(ω)−ǫ] [3] √1−



F∞
1−X [2]



1−X [2]



��



χ¯0(ω; X, ν) = [1]




[1]

2 [χ][0][(][ω][;][ X, ν][)][ −] [1+] 4 [X]




ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]




- 1−
ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



1−X [2][ F][∞]



+ [ω+µ−Σ(1 ω)−ǫ] [2] 1−2X [2]




 1 + [ω][+][ν][+][µ][−][Σ(][ω][+][ν][)]

 - √1−X [2]




- 1−X
+ [2][{][ω][+][ν][−][Σ(][ω][+][ν][)][−][Xǫ][}]
√1−X [2]




- ��
}







1−X [2]




[ω][+][ν][)][−][Xǫ][}] 1 + [ω][+][ν][+][µ][−][Σ(][ω][+][ν][)]

1−X [2] {− √1−X [2]




- 1−X
ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



1−X    - 1−

[X]  - ∞ 1 1

4 −∞ [dǫρ][(][ǫ][)] [ω+µ−Σ [∗] (ω)−ǫ] [3] √1−



F∞
1−X [2]



+ ω+µ−Σ(1 ω)−ǫ (1−X1 [2] ) [3][/][2]




F∞

 


1−X [2]




ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



��



F∞
1−X [2]



χ˜¯0(ω; X, ν) = [1]




[1]

2 [χ][˜][0][(][ω][;][ X, ν][)][ −] [1+] 4 [X]




- 1−X
ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



1−X [2]



1−X [2][ F][∞]



+ [ω+µ−Σ1 [∗] (ω)−ǫ] [2] 1−2X [2]




1 + [ω][+][ν][+][µ][−][Σ(][ω][+][ν][)]

 - √1−X [2]




- 1−
ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]




- ��
}




- 1−X
+ [2][{][ω][+][ν][−][Σ(][ω][+][ν][)][−][Xǫ][}]
√1−X [2]



1−X [2]




[ω][+][ν][)][−][Xǫ][}] 1 + [ω][+][ν][+][µ][−][Σ(][ω][+][ν][)]

1−X [2] {− √1−X [2]




- 1−X
ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



F∞
1−X [2]



+ ω+µ−Σ1 [∗] (ω)−ǫ (1−X1 [2] ) [3][/][2]




F∞

 


1−X [2]




ω+ν+µ−Σ(ω+ν)−Xǫ
√1−X [2]



F∞
1−X [2]



restricted to be local. As a first step in our analysis,
we can imagine writing the statistical factor for the f occupancy in terms of an effective f -level Ef [∗] [(Czycholl,]
1999)


1
w1 = (102)
1 + exp[ β(Ef [∗]

        - [−] [µ][f] [)]]

which we have written explicitly for the spinless case,
with suitable generalizations for higher-spin cases. Notice that in many cases, either w1 changes as a function
of T, or µf changes as a function of T, or both. Hence,
Ef [∗] [typically has temperature dependence.] If we view
this energy as the centroid of the f -spectral function, we
can immediately learn about how the f -spectral function
may change as a function of T . Of course one can only
learn so much from a single number.



What is more interesting is to evaluate the local f -electron Green’s function following the work of
Brandt and Urbanek (1992) and Zlati´c et al. (2001) [see
also Janis (1994) which examined the corresponding Xray edge problem]. The local f -electron Green’s function
on the imaginary axis is defined by



for τ > 0 in the interaction representation [Zimp is given
by Eq. (26) with H = 0]. The impurity Hamiltonian in
zero magnetic field is Himp = −µn [c] + [�] η [(][E][fη][ −] [µ][f] [)][n] η [f] [+]



Fη(τ ) = Trcf
    



- e [−][β][H][imp] S(λ)fη(τ )fη [†][(0)]

, (103)
imp
Z


Un [c] n [f] and the evolution operator satisfies











β - β

dτ
0 0



β

dτ [′][ �]
0



c [†] σ [(][τ] [)][λ][σ][(][τ][ −] [τ][ ′][)][c][σ][(][τ][ ′][)]
σ



S(λ) = Tτ exp




 - β

- 0



,



21


which is equal to the product of the diagonal elements of
the corresponding matrix


Mmn = (iωm + µ)δmn + χm−n, (111)


up to an overall normalization factor. Hence, the determinant of the matrix in Eq. (111) is simply a product
of the diagonal elements! This is surprising, since one
would naively expect that the determinant depended on
the higher Fourier modes of χ. We can show this result
explicitly, by checking that



(104)
with λσ(τ ) = T [�] n [exp(][−][iω][n][τ] [)][λ][nσ][.] The field λnσ is
the discrete function that satisfies Eqs. (27–32). Since
fη(τ ) = exp(τ imp)fη(0) exp( τ imp), we find
H    - H











d
dτ [f][η][(][τ] [) =]




   (Efη µf ) U

- - 


c [†] σ [(][τ] [)][c][σ][(][τ] [)]
σ



fη(τ ),



dτ [′] [χ(τ [′] ) χ0]
0 - }



(105)
which can be integrated to yield




    - β
φm [(][m][′][)] = T



β - τ

0 dτe [(][iω][m][−][iω][m][′][ )][τ] exp{ 0



fη(τ ) = e [−][(][E][fη][−][µ][f][ )][τ]




- τ











dτ [′] c [†] σ [(][τ][ ′][)][c][σ][(][τ][ ′][)]
0



fη(0).


(106)



(112)
is the m [′] -th eigenvector, with eigenvalue iωm′ + µ + χ0.
The verification, is straightforward, provided one first
writes χm−n in terms of the integral over τ, and notes
that χ(τ ) − χ0 times the last exponential factor in
Eq. (112) is equal to the negative τ derivative of the exponential factor. The eigenvalue can then be determined
by evaluating the integral by parts; we need to subtract
the χ0 factor from the exponent in order for the boundary terms to vanish when one performs the integration
by parts.
Knowing an explicit form for the eigenvectors then allows us to determine the auxiliary Green’s function in the
general case. As before, we imagine adding an infinitesimal field ¯χmn = ¯χδmm0δnn0 to the matrix Mmn. The
auxiliary Green’s function is determined by taking the
logarithmic derivative of the partition function with respect to ¯χ: gσ [aux] (iωn0, iωm0) = ∂ ln ( χτ )/∂χ¯. This
Z [aux]                  derivative is easy to calculate, because it says we need
only determine the shift in each of the eigenvalues for
( χτ ) to first order in ¯χ. In the presence of ¯χ, it is
Z [aux] easy to show that


E [(][m][′][)] = iωm′ + µ + χ0 + ¯χφ [(] m [m] 0 [′][)][∗] φn [(][m] 0 [′][)] + O(¯χ [2] ), (113)


which leads then to



× Tτ exp




 −U

σ




 −U



If we define a time-dependent field

χτ (τ [′], τ [′′] ) = Uθ(τ τ [′] )δ(τ [′] τ [′′] ), (107)
        -         -         
then the f -electron Green’s function becomes



1
Fη(τ ) = e [−][(][E][fη][−][µ][f][ )][τ] Trc τ e [−][β][H][0] S(λ χτ ),
    - imp T ⟨    - ⟩
Z



(108)
with H0 = −µn [c], because the trace over f states is restricted to n [f] = 0 for τ > 0 propagation [the operator
f (0)f [†] (0) projects onto n [f] = 0 and all of the remaining
operators are composed of f [†] f pairs which do not change
the total f -electron number].
The strategy for evaluating the trace over itinerantelectron states is the same as in Section II.D. The trace
involves operator averages that are not time-translation
invariant because the χτ field is not a function of τ [′] - τ [′′]

only. We start with the auxiliary Green’s function in
Eq. (69) and note that the double Fourier transform of
the χτ field [analogous to Eq. (68)] becomes




      - β
χτ (iνl) = T



dτ [′] e [iν][l][τ][ ′] χτ (τ [′] )
0



�∞



=




- 0
U
iνlβ [(1][ −] [e][iν][l][τ] [)][, l][ ̸][= 0;]

 - [Uτ] β [,] l = 0,



(109)
β [,] l = 0,



m [′] =−∞



gσ [aux] (iωn, iωm) =




  - β
= T



β - β

dτ
0 0



φ [(] m [m][′][)][∗] φn [(][m][′][)]
iωm′ + µ + χ0



dτ [′] e [iω][n][τ] [−][iω][m][τ][ ′]
0



where our choice for normalizing the Fourier transform
has an extra factor of T for convenience here [in other
words χτ (iνl) has dimensions of energy] and the bosonic
Matusbara frequency arises from the difference of two
fermionic Matsubara frequencies. Since χτ (iν0) = 0, we
̸
now have ( χτ ) = [1+exp(βµ Uτ )] [2][s][+1] . The parZ [aux]     -     tition function can also be expressed as the determinant
of the matrix that appears in the exponent in Eq. (69).
In the general case, we can write the partition function
as an infinite product




   - τ    - τ ′
e 0 [d][τ][¯][[][χ][(¯][τ] [)][−][χ][0][]] e 0
× �∞ [−][iω] [′] [(]



0 dτ˜[χ [∗] (˜τ )−χ [∗] 0 []]



�∞



e [−][iω][m][′] [(][τ] [−][τ][ ′][)]



× T



m [′] =−∞



. (114)
iωm′ + µ + χ0




      

( χτ ) =
Z [aux] 


�∞
2e [β][(][µ][+][χ][0][)][/][2]


n=−∞



iωn + µ + χ0

iωn



Note that if we choose χ(τ ) = χ(iνl) exp( iνlτ ), with

            χ(iνl) real, then evaluating Eq. (114) to first order
in χ(iνl) reproduces Eq. (71) as it must. For our
case, we are interested in the real χ field of Eq. (107).
Substituting this field into Eq. (114) and performing some tedious algebra, then yields the results for
the diagonal and off-diagonal auxiliary Green’s function
shown in Table VIII. These results generalize those



�2s+1


,


(110)


22



TABLE VIII Auxiliary Green’s function gσ [aux] (iωn, iωm) = T ξ0Anm + T (ξ0 − 1)Bnm for n ̸= m and gσ [aux] (iωn, iωn) = T ξ0Cnn +
T (ξ0 − 1)Dnn for n = m. Here ξ0 = 1/[1 + exp(Uτ − βµ)].



e [i][(][ωn] [+][µ][)][τ] [−][βµ]

(iωm+µ)(iωn+µ) [+][ (][e][−][(][iωm] [+] ( [µ] iω [)][τ] m [ +] + [e] µ [−] )( [βµ] iω [)(] n [e] + [(][iωn] µ−U [+] ) [µ][)][τ][ −][e][Uτ][ )]



1 e [i][(][ωn] [+][µ][)][τ] [−][βµ]
Anm i(ωm−ωn)(iωm+µ−U ) (iωm+µ)(iωn+

[e][−][(][iωm][+][µ][)][τ][ [][i][(][ω] [−][ω] [−][)][e][Uτ][ −][(][iω] [+][µ][−][U]




[µ][)][τ][ +][e][−][βµ][)(][e][(][iωn] [+][µ][)][τ][ −][e][Uτ][ )]

1 e [−][i][(][ωm] [−][ωn][)][τ]
(iωm+µ)(iωn+µ−U ) - i(ωm−ωn)(iωn+µ) [+] i(ωm−ωn)(iωm



i(ωm−ωn)(iωm+µ−U ) (iωm+µ)(iωn+µ) (iωm+µ)(iωn+µ−U ) i(ωm−ωn)(iωn+µ) i(ωm−ωn)(iωm+µ)

+ [e][−][(][iωm][+][µ][)][τ][ [][i][(][ω][m][−][ω][n][)][e][Uτ][ −][(][iω][m][+][µ][−][U] [)][e][(][iωn] [+][µ][)][τ][ ]]



i(ωm −ωn)(iωm+µ−U )(iωn+µ−U )
−1 e [−][i][(][ωm] [−][ωn][)][τ]
Bnm i(ωm−ωn)(iωn+µ−U ) i(ωm−ωn)(iωn+µ)

[−]

+ [e][−][i][(][ωm][−] i [ωn] (ωm [)][τ]   - [ [][iω] ωn [n] )( [+] iω [µ][−] m [U] + [+] µ [i]   - [(][ω] U [m] )( [−] iω [ω] n [n] + [)][e] µ [(][iωm] −U )

Cnn (iωn+µ−U )τ −1+e [−][(][iωn][2] [+][µ][−][U] [)][τ] + [1][−][e][−][(]



( [µ] iω [−][U] n+ [)][τ] µ [ +] )( [e] iω [−][βµ] n+ [(][e] µ [(] - [iωn] U ) [+][µ][)][τ][ −][e][Uτ][ )] + [(][iω][n][+][µ][)(][β][−][τ] ( [)] iω [−] n [1] + [−] µ [e][−] ) [2][βµ][+(][iωn] [+][µ][)][τ]



e [−][i][(][ωm] [−][ωn][)][τ]

i(ωm−ωn)(iωn+µ) (iωm+µ−U )(iωn+µ)

[+][i][(][ω] [−][ω] [)][e][(][iωm] [+][−][µ][−][−][U][e][)][τ][iωnτ][ ]] [ (][e][−][iωmτ][ −][e][(][µ][−][U] [)][τ][ )][−][e][βµ][(][e][−][(][iωm] [+][µ][)][τ][ −][e][−][Uτ][ )]



(iω [e][(] m [µ][−] + [U] µ [)] - [τ][ )] U [−] )( [e] iω [βµ] n [(] + [e][−] µ [(] ) [iωm] [+][µ][)][τ][ −][e][−][Uτ][ )] + [iω][n] i [+] (ω [µ] m [−] - [i][(] ω [ω] n [m] )( [−] iω [ω][n] m [)] + [e][βµ] µ)( [−] iω [(][iωm] n+µ [+] ) [µ][)][τ]



i(ωm−ωn)(iωn+µ−U ) i(ωm−ωn)(iωn+µ) (iωm+µ−U )(iωn+µ) i(ωm−ωn)(iωm +µ)(iωn+µ)

+ [e][−][i][(][ωm][−][ωn] [)][τ][ [][iω][n][+][µ][−][U] [+][i][(][ω][m][−][ω][n][)][e][(][iωm] [+][µ][−][U] [)][τ][ ]]



(iω)τn−+1+µ−e [−] U [(] ) [iωn][2] [+][µ][−][U] [)][τ] + [1][−][e][−][(][iωn] [+] ( [µ] iω [−][U] n+ [)][τ] µ [ +] )( [e] iω [−][βµ] n+ [(][e] µ [(] - [iωn] U ) [+][µ][)][τ][ −][e][Uτ][ )]

(iωU )nτ+−µ1+−Ue [(] ) [iωn][2] [+][µ][−][U] [)][τ] + [1][−][e][(][iωn] [+][µ][−] (iω [U] [)] n [τ] + [ +] µ [e] )( [βµ] iω [(][e] n [−] + [(] µ [iωn] −U [+] ) [µ][)][τ][ −][e][−][Uτ][ )]



(iωn+µ) [2]

[β][)][−][1][−][e][βµ]

(iωn+µ) [2]



Dnn −(iωn+µ−U )τ −1+e [(][iωn][2] [+][µ][−][U] [)][τ]




[−] (iω [U] [)] n [τ] + [ +] µ [e] )( [βµ] iω [(][e] n [−] + [(] µ [iωn] −U [+] ) [µ][)][τ][ −][e][−][Uτ][ )] + [(][iω][n][+][µ][)(][τ] [−] ( [β] iω [)][−] n [1] + [−] µ [e] ) [βµ][2] [−][(][iωn] [+][µ][)][τ]



of Brandt and Urbanek (1992) off of half filling and correct some typos in Zlati´c et al. (2001).
Once gσ [aux] is known, then we follow the same procedure as before to calculate the relevant averages. The
object of interest is Trc τ exp( β 0)S(λ χτ ), which
T ⟨          - H          - ⟩
can be viewed as the partition function corresponding
to a particle moving in both the λ and χτ fields. Since
the partition function is the determinant of the inverse
of the Green’s function, and since the Green’s function
gσ(iωn, iωm) associated with the λ − χτ field is related
to the auxiliary Green’s function via


[gσ] [−][1] = [gσ [aux] ] [−][1] λnσδnm, (115)

         

we immediately conclude that



One is also interested in the f -electron Green’s function on the real axis. Unfortunately, there is no obvious
way to analytically continue Eq. (117) from the imaginary to the real axis. Instead, one is forced to re-evaluate
the f -electron Green’s function directly on the real axis.
Since there is no time-translation invariance to the effective fields, it is most convenient to employ a Keldysh
formalism, even though the f -electron is in equilibrium.
In the Keldysh formalism, we need to perform the path
integral in the time domain over the contour illustrated
in Fig. 3 to determine the contour-ordered Green’s function. The Keldysh (greater) Green’s function for real
time t becomes


e [−][β][H][imp] Sc(λ)fη(t)fη [†][(0)][⟩]
Fη [>][(][t][) =][ −][Tr][cf] ⟨ (118)
imp
Z



Trc τ exp( β 0)S(λ χτ )
T ⟨  - 2Hs+1  - ⟩







= ( χτ )
Z [aux]  


2�s+1



Det[δnm gσ [aux] (iωn, iωm)λmσ(116)].
σ=1 


with fη(t) = exp(it imp)fη(0) exp( it imp) and
H      - H



Sc(λ) = Tc exp



.



��



dt [¯][′][ �]
c



c [†] σ [(¯][t][)][λ][(¯][t,][ ¯][t][′][)][c][σ][(¯][t][′][)]
σ




  dt [¯]
c



Substituting into Eq. (108) yields our final result for the
f -electron Green’s function


1
Fη(τ ) = e [−][(][E][fη][−][µ][f][ )][τ] ( χτ )
�2σs=1+1 −Det[Zimpδnm gσ [aux] (iωnZ, iω [aux] m)−λmσ].(117)
            
One needs to recall that ( χτ ) changes with τ beZ [aux]           cause the χτ field depends on τ . One can easily verify in the case where Efη has no η dependence, and in
the limit where τ 0 [+], then gσ [aux] δnm/(iωn + µ)
→ →
and the f -electron Green’s function can be evaluated explicitly, producing Fη(0 [+] ) = −w0 as it must. Similarly,
for τ β [−] one finds gσ [aux] δnm/(iωn + µ U ) and
→ →  Fη(β [−] ) = w1.
    
**t**


**-i** β


FIG. 3 Contour c used in integrating the action in the
Keldysh formalism.



dt [¯][′′] gσ [aux] (t, [¯] t [¯][′′] )λσ(t [¯][′′], t [¯][′] )], (122)
c



(119)
One can directly determine λ(ω) on the real axis. Using
this function one then finds




- ∞



λ(t, [¯] t [¯][′] ) =
   - π [1]



λ(t, [¯] t [¯][′] ) =
   - π [1]



−∞ dωImλ(ω) exp[−iω(t [¯] - t [¯][′] )]



[f (ω) θc(t [¯] t [′] )] (120)
× - - [¯]



where θc(t [¯] t [′] ) = 0 if t [¯][′] is in front of t [¯] on the contour c
     - [¯]
and 1 if it is behind.
Using an equation of motion, similar to Eq. (105), leads
us to introduce a time-dependent field


χt(t, [¯] t [¯][′] ) = iUθc(t t)δc(t [¯] t [′] ). (121)
         -          - [¯]          - [¯]

The derivation of the Green’s function follows as before
resulting in the analogue of Eq. (117)



1
Fη [>][(][t][) =][ −] imp e [−][i][(][E][fη] [−][µ][)][t] Z [aux] (−χt)
Z



2�s+1



×



Det[δ(t [¯]   - t [¯][′] )
σ=1



�σ
+



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-21-0.png)
TABLE IX gσ [aux] (t, [¯] t [¯][′] ) for different orderings of t, t [¯], and t [¯][′]

along the contour c. The symbol ξ [¯] 0 satisfies ξ [¯] 0 = 1/[1 +
exp(iUt − βµ)].

ξ¯0 exp[iµ(¯t − t¯ [′] )] t < t < [¯] t [¯][′]

ξ¯0 exp[iUt + i(µ − U )¯t − iµt¯ [′] ] t < t <¯ ¯t [′]

ξ¯0 exp[i(µ − U )(¯t − t¯ [′] )] t <¯ ¯t [′] < t
(ξ [¯] 0 1) exp[iµ(t [¯] t [′] )] t < t [¯][′] < t [¯]
  -  - [¯]
(ξ [¯] 0 1) exp[ iUt + iµt [¯] i(µ U )t [¯][′] ] t¯ [′] < t < ¯t
  -  -  -  (ξ [¯] 0 1) exp[i(µ U )(t [¯] t [′] )] t¯ [′] < ¯t < t
  -  -  - [¯]


except now, the determinant is of a continuous matrix
operator.
The function gσ [aux] (t, [¯] t [¯][′] ) can be found directly from its
operator definition



23


- sinh(βω)Im{F [>] (t)} sin(ωt)] (128)



and



A [fo] η [(][ω][) =][ −] [1]

π




- ∞



π



0 dt[−sinh(βω)Re{Fη [>][(][t][)][}][ cos(][ωt][)]



+ (coshβω + 1)Im{F [>] (t)} sin(ωt)]. (129)



At half filling, we have that A [fo] η [(][ω][) = 0, so that]
Eqs. (128) and (129) reduce to



A [f] η [(][ω][) =][ −] [2]

π




- ∞

0 dtRe{Fη [>][(][t][)][}][ cos(][ωt][)][.] (130)



1
gσ [aux] (t, [¯] t [¯][′] ) = σ [(¯][t][′][)][⟩]
     - ( χt) [Tr][c][⟨T][c][e][−][β][H][0][S][c][(][−][χ][t][)][c][σ][(¯][t][)][c][†]
Z [aux]     


This then determines the localized electron spectral function on the real axis.


G. Spontaneous Hybridization


Sham and coworkers proposed that correlations can
lead to a spontaneous ferroelectricity via the creation
of a dynamically correlated hybridization in the FK
model (Portengen et al., 1996a,b). Such an effect is
necessarily a subtle one, because it is well known that
Elitzur’s theorem (Elitzur, 1975) applies to the FK
model (Subrahmanyam and Barma, 1988) and no such
spontaneous hybridization can occur at any finite temperature. Numerical and analytical calculations in
finite-dimensions (Farkasovˇsk´y, 1997, 1999, 2002) and
in infinite-dimensions (Czycholl, 1999) indicated that
such spontaneous hybridization did not occur in the FK
model, but they did not cover all of the available parameter space. An alternate way to test these ideas is to
directly calculate the susceptibility toward spontaneous
hybridization formation (Zlati´c et al., 2001).
Because the f -electron dynamics are local, only the
local susceptibility toward spontaneous hybridization is
relevant. We will restrict ourselves to the spinless case
for simplicity. The local spontaneous hybridization susceptibility is defined by

     - β 1
χhyb = − 0 dτ imp

Z
× Trcf ⟨Tτ exp(−βHimp)S(λ)f (τ )d [†] (τ )d(0)f [†] (0)⟩.
(131)


If we introduce the time-dependent field λ(τ, τ [′] ) that couples the itinerant electron at τ [′] to its Hermitian conjugate
at time τ [in equilibrium, we have λ(τ, τ [′] ) = λ(τ − τ [′] )],
then we can express the susceptibility in terms of a functional derivative



(123)
noting that we order the times along the contour c and
that ( χt) = [1 + exp(βµ iUt)] [2][s][+1] . The result is
Z [aux]   -   shown in Table IX for the six different possible orderings
of t, t [¯], and t [¯][′] along the contour c. Brandt and Urbanek
(1992) show how to calculate the discretized determinant
in an efficient manner. If we use a quadrature rule

       



  dtI(t) =
c



WiI(ti) (124)
i



with weights Wi for the discrete set of times {ti} on the
contour c, then the continuous determinant can be approximated by the discrete determinant




 
[δ][ij] +

∆tc



Det[Wi [δ][ij]
{ ∆t



gσ [aux] (ti, tk)Wkλσ(tk, tj) ] (125)
}
k



for each σ (1/∆tc is the approximation to the delta function on contour c with ∆tc the width of the interval that
includes the delta function; for a (midpoint) rectangular
quadrature rule, one takes ∆tc = 1/Wi).
Now the Keldysh Green’s function satisfies the following spectral formula

      - ∞
Fη [>][(][t][) =] −∞ dωe [−][iωt] [f (ω) − 1]A [f] η [(][ω][)] (126)


because it involves the product of the spectral function
A [f] η [(][ω][) with the relevant distribution function [][f] [(][ω][)][ −] [1].]
The (greater) Green’s function obviously satisfies

Fη [>][(][t][) =][ F] η [ >][∗] (−t). (127)

We break the spectral density into its even and odd
pieces: A [fe] η [(][ω][) = [][A] η [f] [(][ω][) +][ A][f] η [(][−][ω][)]][/][2 and][ A][fo] η [(][ω][) =]

[A [f] η [(][ω][)][ −] [A][f] η [(][−][ω][)]][/][2.] Then we use Eq. (127) to show
that




 - β
=



β dτ [e][−][(][E][f] [−][µ][f][ −][U][)][τ] [Z] [aux][(][−][χ][τ] [)]

0 imp




     - β
χhyb = − 0



dτ [δF] [(][τ] [)]
0 δλ(τ,



δλ(τ, 0)



imp
Z



δDet[1 g [aux] λ]
   - .

δλ(τ, 0)

(132)



A [fe] η [(][ω][) =][ −] [1]

π




- ∞



0 dt[(coshβω + 1)Re{Fη [>][(][t][)][}][ cos(][ωt][)]


Noting that DetA = exp[Tr(ln A)], allows us to immediately compute


δDet[1 g [aux] λ]
   - = Det[1 g [aux] λ][(1 g [aux] λ) [−][1] g [aux] ]0τ,

δλ(τ, 0)   -   -   
(133)
where matrix multiplication is understood. Substituting
Eq. (133) into Eq. (132) then immediately yields




   - β
χhyb =



β - β

dτ
0 0



0 dτ [′] F (τ )(1 − g [aux] λ) [−] 0τ [1][′] [g] τ [aux][′] τ [,] (134)



where one must recall that g [aux] must be recomputed for
each τ value, since it depends explicitly on χτ . Reexpressing Eq. (134) in terms of Fourier transformed quantities produces




   - β
χhyb =



(1 − g [aux] λ) [−] mn [1] [g][aux][(][iω][n][, τ] [)][,]
mn



β 
dτF (τ )T
0



(135)
where the partial Fourier transform of the auxiliary
Green’s function satisfies




   g [aux] (iωn, τ ) = T



g [aux] (iωn, iωm)e [iω][m][τ] . (136)
m



24


of the effective bandwidth (≈ 4t [∗] ) and at half filling for
large U it behaves like Tc t [∗][2] /4U [as expected for
≈
the equivalent (Ising) spin model] and for small U it appears to grow like Tc U [2] ln U [which is different from
≈ | |
the expected exponentially growing behavior that occurs
in most nested systems at weak coupling] (van Dongen,
1992; van Dongen and Vollhardt, 1990). As we move
away from half filling, the checkerboard phase is suppressed (disappearing at small and large U ) and the
phase separation is enhanced (especially at large U ).
Near the band edge [panel (b)], there is no checkerboard instability, but the phase separation becomes even
stronger. We see that the spinodal temperature for phase
separation does not depend too strongly on the electron
filling, and surprisingly, the curves cross as a function of
U .


FIG. 4 Tc for CDW order in the spinless FK model (a) near
half filling and (b) near the band edge. The solid lines denote
checkerboard order and the dashed lines denote the spinodal
decomposition temperature for phase separation (the true
first-order transition temperature is always higher than the
spinodal temperature). The labels denote the electron filling
ρe [which runs from top to bottom for the dashed lines in
panel (a) as 0.3, 0.35, 0.4, and 0.45, the spinodal temperature
for 0.5 vanishes; in panel (b) the lines are for 0.05, 0.1, 0.15,
and 0.2—note how the curves cross as a function of U ]; the
ion filling is fixed at ρf = 0.5.


We can also examine the transition temperature for
fixed U as a function of electron concentration (with
ρf = 0.5 again) as shown in Fig. 5. For small U [panel
(a)], we see that the region of the checkerboard phase
increases as U increases, as does the region of phase separation. For large U [panel (b)], we see that the Tc curve



Note that this final result for the spontaneous hybridization susceptibility in Eq. (135) requires the matrix inverse of [1 − g [aux] λ] which is straightforward to compute
numerically for a finite truncation of the matrix.


III. ANALYSIS OF SOLUTIONS


A. Charge-Density-Wave Order and Phase Separation


The first problem examined in the FK model with
DMFT was the problem of ordering into a two-sublattice
charge density wave (CDW) at half filling on a hypercubic lattice (Brandt and Mielsch, 1989). Because the
hypercubic lattice is bipartite, we expect a transition at
finite temperature for all U (Kennedy and Lieb, 1986)
and indeed this is true. Since the original work, a number of other studies of CDW order and phase separation
followed (Brandt and Mielsch, 1990, 1991; van Dongen,
1992; van Dongen and Vollhardt, 1990; Freericks,
1993a,b; Freericks et al., 1999; Freericks and Lema´nski,
2000; Gruber et al., 2001; Letfulov, 1999) on both the
hypercubic and the Bethe lattices. We concentrate on
the spinless FK model here.
Since the DMFT is in the thermodynamic limit, we
can determine the transition temperature for a continuous transition by simply finding the temperature at which
the susceptibility diverges. Using the results of Table I,
we find that the susceptibility diverges whenever the denominator of γ(q) vanishes. In Fig. 4, we plot the Tc
for checkerboard CDW order (X = −1) and the spinodal temperature for phase separation (X = 1) near half
filling (a) and near the band edge (b). Note that the transition temperature has a maximum that is about 1/40th



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-23-1.png)
for the checkerboard phase develops a cusp at half filling (Freericks and Lema´nski, 2000), and that the region
of stability shrinks as U increases further. Phase separation dominates for large U, as expected.


FIG. 5 Tc for CDW order in the spinless FK model (a) for
small U and (b) for large U . The solid lines denote checkerboard order and the dashed lines denote the spinodal decomposition temperature for phase separation (the true first-order
transition temperature is always higher than the spinodal
temperature). The labels denote the value of U ; the ion filling
is fixed at ρf = 0.5.


It turns out, that for small U, the system also has instabilities to CDW phases with incommensurate values
of X (i.e., X changes continuously with the electron concentration). These results are summarized with a projected phase diagram (Freericks, 1993a) in Fig. 6, which
plots the regions of stability for different CDW phases
as determined by the ordering wavevector of the initial
ordered phase as T is lowered to the first (continuous)
instability at Tc (as determined by the divergence of the
relevant susceptibility). This is an approximation of the
zero-temperature phase diagram—the phase boundaries
may change as one reduces the temperature from Tc to
zero, but we are not able to study the ordered phase of incommensurate states. They may also change if there are
first-order phase transitions. Note how the system segregates at large U for all fillings except ρe = 0.5 where it
is degenerate with the checkerboard phase.
In order to understand the incommensurate order better, we plot Tc(X) for different electron fillings at U = 0.5
in Fig. 7. Near half filling, these curves are peaked at
X = −1, but as the system is doped sufficiently far from



25


FIG. 6 Projected phase diagram for the spinless FK model
with ρf = 0.5. The shaded region near half filling denotes the
region of stability of the checkerboard phase (X = −1), the
shaded region near the band edge denotes the region of stability for the segregated phase (as determined by the spinodal
decomposition temperature), and the white region shows the
incommensurate phases at small U (the solid lines are lines of
constant X).


half filling, the curves develop a peak at an intermediate value of X which evolves towards X = 0 as Tc 0
(ρe = 0.35 and 0.3). Then, if doped further from half fill- →
ing, Tc rises again and the ordering wavevector evolves
smoothly toward X = 1 (ρe = 0.2 and 0.15). Note that
the region of stability for positive (incommensurate) X
is much smaller than that of negative (incommensurate)
X. In the large U case, the maximum always appears
at X = −1 or X = 1 and the incommensurate order
disappears (see Fig. 6).
It is interesting to also examine the dynamical charge
susceptibility (Freericks and Miller, 2000; Shvaika, 2000,
2001). We don’t expect the dynamical susceptibility to
show any signs of the CDW instability because it is an
isolated susceptibility, and the divergence of the static
susceptibility arises solely from the coupling to the static
electrons which produced an additional contribution to
the (isothermal) static susceptibility. Indeed this is the
case, as can be seen for the checkerboard (X = −1) dynamical charge susceptibility at U = 4 shown in Fig. 8.
We plot the imaginary part of the susceptibility only.
Note how at high temperature there is a low-energy peak
and a charge-transfer peak (centered at ν ≈ U = 4),
but as the temperature is lowered, the low-energy peak
rapidly disappears and the susceptibility has little further temperature dependence in the homogeneous phase
(even though we have passed through Tc which occurs
at 0.0547). We also find that as we move from the zone
corner toward the zone center, the higher-energy (chargetransfer peak) loses spectral weight but does not have
much dispersion or peak narrowing, while the low-energy



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-24-2.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-24-3.png)
![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-25-0.png)

FIG. 7 CDW transition temperature as a function of the
ordering wavevector described by X. The numbers label
the electron filling with the filling changing in steps of 0.05
(U = 0.5 and ρf = 0.5). The results for ρe = 0.25 are too low
to be seen on this figure.


peak shows an appreciable dispersion toward lower energy and narrows as we approach the zone center (not
shown). At the zone center, the dynamical charge susceptibility vanishes.


FIG. 8 Imaginary part of the dynamical charge susceptibility
at X = −1 and U = 4. Note the low-energy spectral weight
which rapidly disappears as T is lowered, and note further
that there is no signal of the CDW order (which sets in at
Tc = 0.0547) in the isolated susceptibility.


The results on the Bethe lattice are similar to those
on the hypercubic lattice except for the incommensurate
order. We will concentrate on discussing the Bethe lattice case for the remainder of this section. We begin by
examining the ordered checkerboard phase at half filling. In Fig. 9, we plot the electronic density of states for
U = 1 above Tc, and below Tc in steps down to T = 0.
Inset in the figure is a plot of the “normalized” order
order parameter takes a BCS-like form, being flat for lowparameter w1 [A] [−] [w] 1 [B] [as a function of temperature. The]
temperatures and having a square-root dependence as
Tc is approached [this behavior changes as U → 0, see
van Dongen (1992)]. The density of states evolves with



26


temperature in the ordered phase because of this temperature dependence in the order parameter. Each sublattice has a sharp peak in the density of states (which
becomes singular at T = 0) as expected. Note the interesting behavior of the subgap states, which split into
two subbands then shrink and disappear as T is reduced.
In the limit as U →∞, the bandwidth of the subbands
goes to zero, and the density of states becomes a delta
function on each sublattice (van Dongen, 1992).


FIG. 9 Density of states above and below Tc = 0.06614 in
the spinless FK model at half filling on a Bethe lattice with
U = 1. The DOS is plotted for T = 0.07, T = 0.065, T = 0.06,
T = 0.045, T = 0.03, and T = 0. Note that in the ordered
phase, there are two DOS plots, one for each sublattice (solid
and dotted lines); these DOS are mirror images of each other.
The inset plots the “normalized” order parameter as a function of temperature, which has a BCS-like shape. The exact
form is known for U →∞ and U → 0 (van Dongen, 1992),
and one expects, for smaller U, that the shape will change
dramatically since the order parameter becomes very small in
the range 0.5Tc < T < Tc.


In addition to the checkerboard phase, we can also
examine the phase-separated (segregated) phase, where
the itinerant electrons avoid the localized ions. If we
take the limit U →∞, where the phase separation
is the strongest, we find the plot projected onto the
w1 = (1 − ρe)/2 plane (which corresponds to relative
half filling of the lower Hubbard band) shown in Fig. 10.
The solid line denotes the first-order phase transition line
calculated by performing a Maxwell construction on the
free energy (Freericks et al., 1999). The dotted line is the
spinodal decomposition temperature calculated from the
divergence of the susceptibility. Note how the two temperatures track well with one another and how they meet
at the maximal Tc as they must because that is the temperature where the first-order phase transition becomes
second order.
Finally, we examine higher-period ordered phases on
the Bethe lattice (Gruber et al., 2001). Since the Bethe
lattice does not have the same periodicity properties of
regular lattices, one must construct higher-period ordered phases with care. This is done by working directly
in real space and repeating quasi-one-dimensional patterns of charge density waves according to the different



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-25-3.png)
![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-26-4.png)

FIG. 10 Phase diagram for the first-order phase separation
transition on a Bethe lattice with w1 = (1−ρe)/2 and U →∞.
The solid line is the first-order transition temperature and the
dotted line is the spinodal temperature.


levels of the tree that forms the Bethe lattice. A periodtwo phase is the conventional checkerboard phase with
alternating charge densities on each level. There is a region of parameter space where the period-three phase has
been shown to be stable. This is illustrated in Fig. 11 (a),
which is a restricted phase diagram at T = 0 that compares the ground-state energy of the segregated phase,
the period-two phase, the period-three phase and the homogeneous phase. Note the wide region of stability for
the period-three phase (this region can shrink as additional phases are added to the phase diagram; in particular, we conjecture that the homogeneous phase stability
will disappear as higher-period phases are added to the
diagram). To examine in more detail, we plot the free
energy of the homogeneous phase, the period-two phase,
and the period three phase for U = 3, ρf = 2/3, and
µ = 0.84861 (ρe 0.332). Note how at low temperature the period-three phase is lowest in energy, but how ≈
there must be a higher-period phase that intervenes between the period-two and period three phases for the
free energy to be continuous. We expect the phase transition from the period-three phase to be first order. Note
further how the period-two phase free energy smoothly
joins the homogeneous-phase free energy, as expected for
a continuous (second-order) phase transition.


B. Mott-like Metal-Insulator Transitions


The FK model is not a fermi liquid (Si et al., 1992)
whenever ρf is not equal to 0 or 1 (when ρf = 0 or
1, the FK model is a noninteracting fermi gas). This
is because the f -electrons appear like disorder scatterers
(with an annealed averaging rather than the conventional
quenched averaging). These scatterers always produce a
finite lifetime at the fermi surface, so rigorously quasiparticles do not exist and the system is a non-fermi-liquid.
If U is small, one can still view the system as a “dirty
fermi liquid”, but the system rapidly changes character



27


FIG. 11 (a) Restricted phase diagram on the Bethe lattice
for ρf = 2/3 and (b) free energy versus temperature for µ =
0.84861. Note the large region of stability of the period-three
phase in (a) and how the shape of the free-energy curves in
(b) suggest that phase transitions to higher-period phases will
be first order.


as U increases further. The non-fermi-liquid character
can also be seen in the self energy on the real axis. The
imaginary part does have a quadratic behavior, but the
curvature is the wrong sign and the intercept at ω = 0
does not go to zero as T → 0 as it must in a fermi liquid.
Similarly, the real part of the self energy is linear, but
the slope has the wrong sign near ω = 0.
It is known in a fermi liquid with a local self energy that the fermi surface and the DOS at the fermi
level (at T = 0) are unchanged as the correlations increase (M¨uller-Hartmann, 1989b). But because the FK
model is not a fermi liquid there is no restriction on the
DOS. van Dongen and Leinung (1997) studied the Mottlike metal-insulator transition on the Bethe lattice in detail; in this study, one continues the homogeneous phase
down to T = 0, ignoring any possible CDW phases. They
found a simple cubic equation for the interacting DOS
on the Bethe lattice which produces the results shown in
Fig. 12. One can see that for weak coupling, the DOS is
essentially unchanged from the noninteracting case, but
as U is increased further, the DOS first develops a pseudogap, where spectral weight is depleted near the chemical potential, and then it gets fully reduced to zero. As U



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-26-6.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-26-13.png)
![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-27-2.png)

FIG. 12 Itinerant electron DOS for the spinless FK model on
the Bethe lattice for different values of U ranging from 0.5
to 3.0 in steps of 0.5 (ρe = ρf = 0.5). The metal-insulator
transition occurs at U=2. It is preceded by a pseudogap phase
for (1 < U < 2).


is increased further, the system splits into lower and upper Hubbard bands, and the bandwidth of each subband
decreases as U increases, while the separation increases
between the two bands. This is precisely the kind of
metal-insulator transition that Mott envisioned, where
the DOS within a single band is suppressed to zero, but
unlike Mott’s prediction that the transition would generically be a discontinuous first-order transition, here it is
a continuous second-order transition.
The metal-insulator transition occurs precisely at the
point where the self energy develops a pole and diverges
at ω = 0. This forces the DOS at the chemical potential
to equal 0 on any lattice. On lattices where the noninteracting DOS has band edges, the interacting DOS can
remain zero within a correlation-induced gap. But on
the hypercubic lattice, which has an infinite bandwidth,
with an exponentially small DOS for large frequency,
there is no precise gap, rather the DOS is exponentially
small in the “gap region” and then becomes of order one
within the Hubbard subbands. Indeed, on the hypercubic lattice, the DOS looks much like that in Fig. 12,
but the metal-insulator transition occurs at U ≈ 1.5 for
ρe = ρf = 0.5.
The DOS of the FK model does have a curious
property—it is independent of temperature in the homogeneous phase (van Dongen, 1992) (which was proved
by mapping the FK model onto a coordination-three
noninteracting Bethe lattice problem, which then has
a temperature-independent DOS). The temperatureindependence holds only in canonical formulations, where
both ρe and ρf are separately fixed as functions of T [ignoring the trivial shift of the DOS with µ(T )]. In cases
where the total electron concentration is fixed, but can
vary between itinerant and localized electrons, the DOS
will vary with T since ρf generally varies with T .
One can also examine the spectral function of the localized electrons (Brandt and Urbanek, 1992), which is
temperature dependent! The DOS shares similar behavior with the conduction-electron DOS, having a gap



28


when the correlation energy is large. We plot results for
U = 2.5 where the localized electron DOS develops a
pseudogap and then a gap region as T is lowered. Note
how the gap develops as T is reduced below 0.4.


FIG. 13 Single particle DOS of the f -electrons for the spinless FK model at half filling on a Bethe lattice with U = 2.5.
Note how the gap opens up as T is reduced even though
the calculations are above the CDW transition temperature
(which occurs at T = 0.113746). The DOS is symmetric due
to particle-hole symmetry.


C. Falicov-Kimball-like Metal-Insulator Transitions


The original work of Falicov, Kimball, and
Ramirez (Falicov and Kimball, 1969; Ramirez et al.,
1970) studied a different type of metal-insulator
transition—one where the character of the electronic
states was unchanged, but their statistical occupancy
fluctuated with temperature or pressure. As occupancy
shifted from the itinerant to localized bands, the system
underwent a charge-transfer metal-insulator transition.
One of the main points of interest of this model was that
the presence of a Coulomb interaction U between the
two types of electrons could make the transition become
discontinuous (first-order). The original approximations
used a mean-field theory which showed these first-order
transitions. Later, Plischke (1972) proposed that when
the coherent-potential approximation was applied to the
FK model, the first-order transitions disappeared. This
was refuted by Gon¸calves da Silva and Falicov (1972).
In the Falicov and Kimball approach to the metalinsulator transition, one works with spin-one-half electrons and fixes the total electron concentration (usually
at ρtotal = ρe + ρf = 1). Alternatively, one can perform
a partial particle-hole transformation on the f -electrons,
and have a system where ρe = ρf and U is negative (attractive). There is a gap ∆to creating an electron-hole
pair. We will concentrate on the electronic picture here
(where one has Ef = U − ∆ - 2t [∗] ) and the choice ∆= t [∗]

which most closely represents the original FK problem.
We work on an infinite-coordination Bethe lattice.
This model for metal-insulator transitions was solved
in infinite dimensions by Chung and Freericks (1998). It


![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-28-2.png)

FIG. 14 Conduction electron density as a function of 1/T for
the spin-one-half FK model on a Bethe lattice with ∆= 1.
The different curves correspond to different values of U .


requires a fine tuning of the Coulomb interaction in order
to have a first-order phase transition. This is illustrated
in Fig. 14, where we plot the conduction electron density
ρe versus inverse temperature 1/T for different values of
U (recall Ef also varies with U, since ∆is fixed at 1).
The states that have ρe 0 as T 0 are insulators,
while those with finite ρ →e are metallic. We say a metal- →
insulator transition occurs when there is a discontinuous
jump in the electron density, which goes from the metallic
phase at high temperature to the insulating phase at low
T . This occurs for 2.12 < U < 2.155 when ∆= 1. The
shape of these curves is remarkably similar to those found
in the mean-field-theory solution of Ramirez et al. (1970)
and verifies that first-order metal-insulator transition do
occur within the CPA.
The interacting electronic DOS is plotted in Fig. 15 for
four different values of U (Chung and Freericks, 1998). In
panel (a) we show the metallic case U = 2.16, where the
DOS is large at the chemical potential (ω = 0) and does
not depend strongly on T . As U is reduced to 2.15, where
there is a discontinuous metal-insulator phase transition,
we see a huge reconstruction of the DOS at the transition, where the DOS at the chemical potential becomes
small and decreases to zero as T → 0. In panel (c), we
see the evolution of the insulating phase for the strongly
correlated insulator U = 2.12. Here the conduction electron occupation does not evolve in a simple exponential
fashion, but has a much sharper increase as T increases.
The DOS has upper and lower Hubbard bands, with the
lower band losing spectral weight as T → 0. Finally,
in panel (d), we show the DOS for a weakly correlated
insulator. Here the conduction electron density evolves
in an exponential fashion and there is no DOS at the
chemical potential, since all of the electronic occupation
is thermally activated.


D. Intermediate-Valence


The FK model does not have any hybridization between the itinerant and localized electrons, so it can


29


FIG. 15 Conduction-electron DOS for the spin-one-half FK
model on a Bethe lattice with ∆= 1. The different panels
are for different values of U, and the results are plotted for a
number of different temperatures [the dashed lines are used
in panel (b) for clarity]. The DOS has T dependence because
ρf varies with T .


not have any quantum-mechanical mixed valence at finite
temperature (Subrahmanyam and Barma, 1988) which is
quantified by having a nonzero average ⟨c [†] f ⟩. Nevertheless, one can have a classical intermediate-valence state,
where the average f -electron occupancy lies between 0
and 1 for T → 0. In many such cases, one would expect
CDW order (or phase separation) to take over in the
ground state, but there are regions of parameter space
where the system appears to remain in a homogeneous
classical intermediate-valence state all the way to T = 0.
We study such systems here.
The intermediate-valence problem, and the possibility of the FK model having an instability to a
spontaneously generated hybridization, was first proposed by Portengen et al. (1996a,b). Calculations in
infinite-dimensions (Czycholl, 1999) and one dimension (Farkasovˇsk´y, 1997, 1999) showed that a spontaneously generated hybridization was unlikely over a wide
range of parameter space, but they did not rule out the
possibility everywhere.
The first step to examining the intermediate-valence
problem is to study the phase diagram of the FK model
to see what different types of phases occur. We pick the
spin-one-half model on the Bethe lattice again. We also
pick ρe + ρf = 1 for the total electron concentration.
Since the conduction electron fermi level is at 0 when
there are no f -electrons, if we pick −2 < Ef < 0, then
the fermi level is pinned to Ef at U = 0, and one of two



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-28-7.png)
![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-29-3.png)

FIG. 16 Intermediate-valence phase diagram for the spin-onehalf FK model on a Bethe lattice with ρe + ρf = 1. Note
how the classical intermediate valence state occupies only a
small part of the phase diagram, being taken over by phaseseparated, metallic, and insulating phases over most of the
phase diagram.


things can occur as U is increased: (i) either the classical intermediate-valence state survives, or (ii) it phase
separates into a mixture of a state with ρf = 0 and
ρf = 1. The former occurs for Ef > −1 and the latter for Ef < −1. As the interaction strength is increased
further, then we find only two different stable solutions,
a metallic phase, where ρf = 0 and an insulating phase
where ρf = 1. The zero-temperature phase diagram is
summarized in Fig. 16 (Chung and Freericks, 2000). In
the phase-separated region, there are more possibilities:
either the system remains phase separated in mixtures of
two integer-valent states, or the phase separation has at
least one intermediate-valence state in its mixture. The
line of circles represents an approximate crossover line
between these two possibilities (the intermediate-valence
mixtures lie above the circles). Note how the metallic
and insulator phases take over the phase diagram as U
increases. In fact, the classical intermediate-valence state
only occupies a small region of phase space, because
it is unstable to phase separation over a wide region.
This could explain why there are not too many classical
intermediate-valence states seen in real materials.
We conclude this section with a discussion about the
possibility for spontaneous hybridization (Zlati´c et al.,
2001). We confine our discussion to the spinless model
with ρe + ρf = 0.5 for simplicity. If we repeat the above
analysis, then the region of stability for intermediate valence at small U is the same as above −1 < Ef < 0.
But as U is increased, it appears that the intermediatevalence state should be stable for all U when Ef = −0.75
(but we have not performed a free-energy analysis to rule
out the possibility of phase separation). We plot the inverse of the hybridization susceptibility from Eq. (135)
in Fig. 17. Note that it remains finite for all T . But
we can get an analytic form when U = 0 (Zlati´c et al.,
2001), which says that the susceptibility has a term proportional to | ln T |, which does diverge at T = 0. But
this divergence does not guarantee that the ground state



30


FIG. 17 Inverse of the hybridization susceptibility for the
spinless FK model on a Bethe lattice with ρe + ρf = 0.5
and Ef = −0.75. Note how the susceptibility monotonically
increases with increasing U which suggests that it continues
to diverge at T = 0.


has spontaneous hybridization, in fact, it is known in this
case that the ground state has ⟨c [†] f ⟩ = 0 (Farkasovˇsk´y,
2002), even though the susceptibility diverges. Here we
find, down to the lowest temperature that we can calculate, that the hybridization susceptibility increases with
U, which would imply that it continues to diverge at
T = 0 for all U . In this case, we do not know whether
the ground state would possess a spontaneous hybridization, or not, but the results of Si et al. (1992) suggest
that spontaneous hybridization is indeed possible. In any
case, since a real material will always have a nonzero hybridization (although it may be quite small), one could
expect a quantum-mechanical intermediate valence transition to occur at low temperature in regions of parameter space where the hybridization susceptibility is large
for the FK model. Alternatively, spontaneous hybridization may also occur if the f -electrons are allowed to
hop (Batista, 2002).


E. Transport Properties


The optical conductivity, calculated from Eq. (89), is
plotted in Fig. 18, for the spinless FK model on the hypercubic lattice with w1 = 0.5. Panel (a) is the half-filled
case (ρe = 0.5) and panel (b) shows the behavior for doping away from half filling. Both calculations are at low
temperature T = 0.005 in the homogeneous phase (ignoring any possible CDW phases).
At half filling, the data behaves as expected. For small
U, the system has a Drude like peak, whose width is determined by the scattering rate at low temperature (note
the scattering rate does not vanish even at T = 0 because
the FK model is not a fermi liquid). As U increases, we
see a charge-transfer peak develop, centered at ν ≈ U,
and the low-energy spectral weight is suppressed because
the system becomes a correlated (Mott-like) insulator
(the metal-insulator transition occurs at U ≈ 1.5 here).
One can see that the transition is continuous, with σdc



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-29-4.png)
FIG. 18 Optical conductivity of the spinless FK model with
w1 = 0.5 on a hypercubic lattice at T = 0.005: panel (a) is
the half filling case (ρe = 0.5) with different values of U and
panel (b) is the U = 2 case doped away from half filling. The
numbers in panel (a) label the value of U, while the numbers
in panel (b) show ρe.


smoothly approaching zero as the correlations increase.
We concentrate on the U = 2 case as we dope away
from half filling. One can see that as the system is doped,
it becomes metallic, because the chemical potential now
lies within the lower Hubbard band. As a result there
is a transfer of spectral weight from the charge-transfer
peak down to a Drude-like feature as the system is doped.
What is remarkable, is that there is an isosbestic point
present (which is defined to be a point where the optical
conductivity is independent of doping and all the curves
cross and typically occurs at ν ≈ U/2). The occurrence
of such isosbestic points is present in a wide variety of
models, but its origin is not well understood.
We also plot the dc-conductivity, thermopower, and
electronic contribution to the thermal conductivity, as
derived in Eqs. (93–98) for a correlated system (U = 2,
solid line) with ρe = 1 − w1 and five different w1 values (Freericks and Zlati´c, 2002b). For these parameters,
there is always a region of exponentially small DOS near
the chemical potential at low temperature [but in this region τ (ω) decreases only as a power law]. As the localized
electron concentration w1 moves away from 0.5, the hightemperature thermopower increases in magnitude due to
the asymmetry in the DOS (it must vanish at 0.5 due to
particle-hole symmetry) and the low-temperature ther


31


FIG. 19 (a) DC conductivity, (b) thermopower, and (c) electronic contribution to the thermal conductivity, for the spinless FK model with ρe = 1 − w1 and U = 2. Five fillings are
shown: (i) w1 = 0.5 (solid line); (ii) w1 = 0.4 (dashed line);
(iii) w1 = 0.3 (chain-dotted); (iv) w1 = 0.2 (dotted); and (v)
w1 = 0.1 (chain-triple-dotted).


mopower shows a sharp peak for fillings close to half filling (the sign is hole-like, because the DOS from the lower
Hubbard band dominates the transport coefficients at
low temperature); the dc conductivity and thermal conductivity both vanish at low T due to the “gap” as well.
The thermoelectric figure-of-merit ZT = T σdcS [2] /κel is
plotted in Fig. 20—we find it is larger than one at high
T for w1 < 0.22, and for fillings close to half filling, there
is a low-temperature spike in ZT that can become larger
than one over a narrow temperature range. The spike at
low T is due to the large peak in S and the small thermal
conductivity; but the phonon contribution to the thermal conductivity can sharply reduce ZT if the phonon
thermal conductivity is much larger than the electronic
thermal conductivity (this all electronic calculation provides only an upper bound to ZT ). The Lorenz number
is also plotted in Fig. 20. It gets huge at half filling, but
becomes more metallic (≈ π [2] /3) as the filling moves further away from half filling. It is not a constant even at
low temperature because the system is not a fermi liquid.


F. Magnetic-Field Effects


The magnetic field brings new features to the solution, which we illustrate for the model with a fixed total
number of particles and relatively large Falicov-Kimball
interaction on a hypercubic lattice. We restrict the number of f -particles per site to less than one, taking the


32



elements in the subspace without the f -particles and
Zimp = ZL/Zcavity, we obtain



�2
m [z] f [⟩] [=] σ=1 [Z][0][σ][(][µ][ +][ gµ][B][H][ −] [U] [)]
⟨ imp




 ×

η

ρf
=
f
Z



imp
Z



⟨η|m [z] f [|][η][⟩][e][−][β][(][E][fη][(][H][)][−][µ][f][ )]
η







⟨η|m [z] f [|][η][⟩][e][−][β][(][E][fη][(][H][)][−][µ][f][ )][,] (139)
η



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-31-1.png)

FIG. 20 (a) Lorenz number LkB [2] [/e][2][ =][ κ][el][/σ][dc][T][ and (b) elec-]
tronic thermoelectric figure of merit ZT = T σdcS [2] /κel for the
spinless FK model with ρe = 1 − w1 and U = 2. Five fillings
are shown: (i) w1 = 0.5 (solid line); (ii) w1 = 0.4 (dashed
line); (iii) w1 = 0.3 (chain-dotted); (iv) w1 = 0.2 (dotted);
and (v) w1 = 0.1 (chain-triple-dotted).


limit U [ff] −→∞, and choose the position of the f level such that there is a rather sharp crossover from
the high-temperature state with a large concentration of
f -electrons and a gap in the single particle DOS to the
low-temperature state with a metallic conduction band
(i.e., a fermi gas) and no f -electrons. That is, model
parameters are such that the renormalized f -electron
level is slightly above the chemical potential at T = 0.
This is the regime that yields an anomalous magnetic response (Freericks and Zlati´c, 1998) and is closely related
to experimental materials like YbInCu4 which exhibit a
valence-change transition.
The average of the z-component of the f -electron magnetization is


(e [−][β][[][H−][µN] [−][µ][f] [N][f] []] m [z] f [)]
m [z] f [⟩] [= Tr][cf] (137)
⟨ L
Z

where only the states with one f -electron in the presence
of the magnetic field are considered. This lattice trace
can be evaluated by using the cavity method again, where
the lattice trace becomes equal to an impurity trace in
the presence of an additional time-dependent dynamical
mean field

⟨m [z] f [⟩] [=][ Z][cavity] L Trcf (e [−][β][[][H][imp][−][µN] [−][µ][f][ N][f] []] S(λ)m [z] f [) (138)]

Z

where S(λ) is defined in Eq. (104). The trace is performed by using the basis set |η⟩ which diagonalizes simultaneously Himp and m [z] f [.] Since m [z] f [has no matrix]



where Zf = [�] η [exp[][−][β][{][E][fη][(][H][)][ −] [µ][f] [}][] is the parti-]
tion function of an isolated f -ion, Efη(H) are the fielddependent eigenstates, and µf = µ is the common chemical potential for the itinerant and localized electrons.
The average magnetization is the product of a single-ion
response and the average f -filling 0 ρf 1, i.e., the
magnetic response of independent f ≤-ions (Dzero, 2002; ≤
Dzero et al., 2000, 2002) is modified by the interaction
between the f -electrons and the conduction sea. This
reduces the high-temperature Curie constant and introduces additional temperature and field dependences.
We illustrate these features for the spin-1/2 model
(s = S = 1/2) and plot in Fig. 21 the temperature dependence of ρf as a function of various parameters (including the magnetic field). The results can be explained



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-31-3.png)

FIG. 21 The effect of the magnetic field on the f -electron
concentration is shown for the spin 1/2 FK model with
ρtotal = 1.5, U = 3, and Ef = −0.5, with gµBH = 0.07
(dotted line) and gµBH = 0.17 (chain-dotted line).


by noting that the renormalized f -level is just above
the chemical potential and that a finite temperature induces an entropy driven “transition” (or crossover) into
the magnetically degenerate state (the crossover temperature is denoted Tv). The field pushes the renormalized
f -level closer to the chemical potential, which enhances
the f -occupation, reduces the cross-over temperature and
makes the transition sharper. For large enough fields,
the concentration of f -electrons remains finite down to
T=0, i.e., the system goes through a field-induced metamagnetic transition. This is shown in Fig. 22 where the
magnetization obtained from Eq. (139) is plotted versus magnetic field for various temperatures. Below the


![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-32-3.png)

FIG. 22 Localized electron magnetization for the spin 1/2
FK model with ρtotal = 1.5, U = 4 and Ef = −0.5 plotted as
a function of magnetic field for various values of temperature,
as indicated in the figure.


crossover temperature, the low-field response is negligibly small (the Pauli susceptibility of the conduction electrons is neglected) but at large enough fields the magnetization curves go through an inflection point, which
indicates a crossover to a magnetic state (and is a metamagnetic transition). Above the crossover, the curvature
of the magnetization is positive and typical of a welldefined local moment. The effect of the magnetic field
on transport properties is equally drastic. The magnetoresistance is plotted as a function of field in Fig. 23
and it shows that the low-temperature metallic state is
destroyed above some critical field Hc. Thus, the metamagnetic transition in the f -subsystem is accompanied
by metal-insulator transition in the conduction band.
Taking the inflection point of the magnetization or the


FIG. 23 Magnetoresistance as a function of magnetic field
plotted for several values of temperature.


magnetoresistance, calculated for several values of U and
Ef as an estimate of Hc(T ), we obtain the phase boundary which is shown in Fig. 24, together with the ana-�
lytic form Hc(T )/Hc(0) = 1 − (T/Tv [∗] ) [2] . The crossover

temperature is renormalized by Tv [∗] [=][ T][v][/][2. Note that]



33


the Tv [∗] [values in Fig. 24 differ by more than an order of]
magnitude, while the ratio kBTv [∗][/µ][B][H][c][(0) is only weakly]
parameter dependent.


FIG. 24 Normalized critical field plotted as a function of reduced temperature T/Tv [∗] [for several values of] - [ E] f [and][ U] [. The]
solid line represents the analytic form 1 − (T/Tv [∗][)][2][ with]

Tv [∗] [=][ T][v][/][2.]


G. Static Holstein Model


The static Holstein model (Holstein, 1959; Millis et al.,
1995, 1996) can be viewed as a generalization of the FK
model to the continuous-spin case. Like the FK model, it
also displays metal-insulator transitions and CDW order
phase transitions. We discuss both possibilities here.
The phonon distribution function w(x) in Eq. (39) becomes sharply peaked as T → 0. If gep is small enough, it
approaches δ(x), and the ground state is a noninteracting fermi gas (at half filling, the critical gep is 0.8432 on
the hypercubic lattice and 1.0854 on the Bethe lattice).
Beyond this critical value of gep, the phonon distribution
function shows a double-peaked structure (becoming two
delta functions at T = 0), and the “quasiparticles” scatter off of the local phonon even at T = 0. This creates
a non-fermi-liquid state, and the DOS develops a pseudogap. As gep is increased further, the pseudogap phase
becomes fully gapped (when the self energy develops a
pole), and a metal-insulator transition takes place. These
results are illustrated for the spin-one-half model on the
hypercubic lattice in Fig. 25 [similar to what was done
in Millis et al. (1996)].
The other area of interest is the CDW ordered phase
at half filling. Since a static model does not superconduct, we need not worry about that order at all. One
interesting puzzle in real materials is that the ratio of
twice the CDW gap to the transition temperature is
surprisingly large, usually much larger than the BCS
prediction of 3.5 (Blawid and Millis, 2001). The CDW
transition temperature can be calculated by performing ordered-phase calculations and extrapolating them
to the point where the order disappears to produce
Tc (Ciuchi and de Pasquale, 1999). These calculations



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-32-6.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-32-10.png)
FIG. 25 Plot of the electronic DOS (per spin) for the harmonic static Holstein model at half filling on the hypercubic
lattice at T = 0. Different values of gep have different thicknesses of the lines. Note how the metal-insulator transition is
continuous here too.


show that even in the weak coupling limit, one finds a
large ratio of 2∆/kBTc. Since CDW systems involve a
distortion of the lattice to produce the ordered phase,
one expects that anharmonic terms may play an important role in describing the physics behind them. So it is
important to also examine what happens in the presence
of anharmonic interactions.
A surprising result was found when this system was
analyzed on the hypercubic lattice. There was a universal scaling law for the transition temperature, when
Tc was plotted against an extrapolated approximation to
the wavefunction renormalization parameter (also called
the quasiparticle Z factor, when one is in a fermi liquid),
which is defined on the imaginary axis by



Z(0) = 1
    - [3] 2



ImΣ(iπT )

[3] 2 πT




[1] ImΣ(3iπT )

2 3πT



iπT ) + [1]

πT 2



. (140)
3πT



34


FIG. 26 Scaling plot of (a) the CDW transition temperature
and (b) the CDW gap ratio versus the wavefunction renormalization extrapolated at Tc for the static Holstein model at
half filling on the hypercubic lattice. In panel (a), we have
also included some results for a quantum Holstein model, with
a phonon frequency equal to 0.5, and for the attractive Hubbard model (which is the infinite-phonon-frequency limit).


IV. COMPARISON WITH EXPERIMENT


A. Valence-Change Materials


The FK model can be used to describe the anomalous features of rare earth intermetallic compounds that
have an isostructural valence-change transition, as observed in the YbInCu4 and EuNi2(Si1−xGex)2 family
of compounds. These intermetallics have been attracting a lot of attention recently (Felner and Novik, 1986;
Figueroa et al., 1998; Garner et al., 2000; Levin et al.,
1990; Sarrao, 1999; Wada et al., 1997; Zhang et al., 2002)
and we describe the most typical features briefly.
The temperature-dependent properties of YbInCu4,
which have been studied most thoroughly and which we
take as our example, are dominated at ambient pressure by a first-order valence-change transition at about
40 K. The valence of Yb ions changes abruptly from
Yb [3+] above the transition temperature, Tv, to Yb [2][.][85+]

below Tv (Dallera et al., 2002; Felner and Novik, 1986).
The specific heat data shows at Tv a first-order transition with an entropy change of about ∆S ≃ R ln 8
corresponding to a complete loss of magnetic degeneracy
in the ground state (Sarrao, 1999). Neutron scattering



The scaling law is plotted in Fig. 26 (a) (Freericks et al.,
2000). The results for Tc for a variety of coupling
strengths and even for the case of quantum-mechanical
phonons, all collapse onto the same curve. The results
for an attractive Hubbard model (X symbols) do not, indicating that this scaling curve breaks down when the
phonon frequency is made large enough.
The other quantity of interest to examine is the ratio
of the CDW order parameter at T = 0 to the transition
temperature. Since one might have expected the scaling
theory for Tc would have produced a universal plot there,
that result might not have been so surprising. But, when
anharmonicity is included, its effects should be stronger
at low temperature, since the phonon distortion won’t
be allowed to be as large in the anharmonic case, and
hence one would naively expect a smaller order parameter. But, as shown in panel (b), we see that the ratio of
2∆/kBTc still satisfies an approximate scaling law when
anharmonicity is included (Freericks and Zlati´c, 2001a).
Hence, one should expect, generically, that this ratio will
be much larger than 3.5 except in extremely weak coupling cases (since it does approach 3.5 as gep 0).
→



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-33-3.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-33-11.png)
does not provide any evidence for long-range order below Tv (Lawrence et al., 1997). At the transition, the
f -occupation becomes non-integral (Dallera et al., 2002)
and the lattice expands by about 5%. The crystal structure remains in the C15(b) class and the volume expansion estimated from the known atomic radii of Yb [3+] and
Yb [2+] ions is compatible with the valence change estimated from the LIII -edge data (Cornelius et al., 1997;
Felner and Novik, 1986).
The low-temperature phase shows anomalies typical
of a valence-fluctuating intermetallic compound. The
electronic specific heat and the susceptibility are enhanced (Sarrao, 1999), the electrical resistance and
the Hall constant are small and metallic, and the
low-temperature slope of the thermoelectric power is
large (Oˇcko and Sarrao, 2002). The optical conductivity is Drude like, with an additional structure in
the mid-infrared range which appears quite suddenly at
Tv (Garner et al., 2000). The ESR data (Rettori et al.,
1997) indicate a large density of states at the fermi level
EF . Neither the susceptibility, nor the resistivity, nor
the Hall constant show any temperature dependence below Tv, i.e., the system behaves as a fermi liquid with
a characteristic energy scale TF L Tv. The magnetic
moment of the rare earth ions is quenched in the ground ≫
state by the f −d hybridization but the onset of the highentropy phase cannot be explained by the usual Anderson
model in which the low- and high-temperature scales are
the same and the spin degeneracy is not expected to be
recovered below TF L. The valence-change systems, however, recover the f -moment at Tv which is a much lower
temperature than TF L.
The high-T phase of YbInCu4 sets in at Tv and is also
anomalous. The Yb ions are in the stable 3+ configuration with one f -hole and with the magnetic moment�
close to the free ion value gL J(J + 1)µB = 4.53µB

(gL = 8/7 is the Land´e factor and J = 7/2 is the total
angular momentum of the 4f [13] hole). The magnetic response is Curie-Weiss like with a small Curie–Weiss temperature Θ, which does not seem to be connected with Tv
in any simple way (Felner and Novik, 1986; Sarrao, 1999)
(of course one does not expect a first-order transition
temperature to be related to the Curie-Weiss temperature, but this observation shows that the two phenomena
are not governed by the same microscopic physics). The
dynamical susceptibility obtained from neutron scattering data (Goremychkin and Osborn, 1993) is typical of
isolated local moments, with well resolved crystal-field
excitations (Murani et al., 2002). However, neither the
line shape of the dynamical response nor the temperature dependence of the static susceptibility can be explained by the Kondo model assuming TK Tv. The
≃
Hall constant is large and negative, typical of a semimetal (Figueroa et al., 1998), the electrical resistance
is also very large and not changed much by magnetic
field up to 30 T (Immer et al., 1997). In typical Kondo
systems, on the other hand, one expects a logarithmic
behavior on the scale T/TK and large negative mag


35


netoresistance. The high temperature optical conductivity (Garner et al., 2000) shows a pronounced maximum of the optical spectral weight at a charge-transfer
peak near 1 eV and a strongly suppressed Drude peak.
The high-temperature ESR data for Gd [3+] embedded in
YbInCu4 resemble those found in integer-valence semimetallic or insulating hosts (Altshuler et al., 1995).
The anomalous properties of the high-temperature
phase become most transparent if the valence-fluctuating
phase is suppressed completely by pressure or doping as in Yb1−xYxInCu4, where a substitution of
15% Y ions stabilizes the high-temperature phase
down to T=0 K (Mitsuda et al., 2002; Oˇcko and Sarrao,
2002; Zhang et al., 2002). The experimental results for the resistivity, susceptibility and the thermopower (Oˇcko and Sarrao, 2002) are shown in Fig. 27.
The susceptibility data show that the Curie-Weiss temperature for all the samples is about the same and much
less than Tv, i.e., the magnetic response of the hightemperature phase can be represented by a single universal curve, provided one scales the data by an effective
concentration of magnetic f -ions, ρf, which is always
smaller than the nominal concentration of f -ions. The
functional form of the susceptibility above 10 K agrees
well with the “single-ion” crystal field (CF) theory. At
lower temperatures the susceptibility deviates appreciably from the CF theory and shows a significant reduction
of the Curie constant ρf which is not of the Kondo type.
The resistivity in the high-temperature phase of
Yb1−xYxInCu4 exhibits a weak maximum and the thermopower has a minimum above 100 K but neither quantity shows much structure at low temperatures, where the
susceptibility drops below the single-ion CF values. That
is, despite the presence of the well-defined local moments,
there are no Kondo-like anomalies in transport or thermodynamic properties of the high-temperature phase.
On general grounds, one can argue that the discontinuity of the thermoelectric power at the valence transition is a trivial consequence of the different thermoelectric properties of the two phases: the thermopower
of the valence-fluctuating phase has an enhanced slope
and grows rapidly up to Tv, where it suddenly drops to
the values characteristic of the high-temperature phase.
The hydrostatic pressure, doping and the magnetic
field also have, like the temperature, a strong effect
on the properties of the valence-change materials. The
critical temperature of YbInCu4 decreases with pressure (Immer et al., 1997) but the data are difficult to
explain with the Kondo volume collapse model (Sarrao,
1999). Doping the Yb sites with Y [3+] or Lu [3+] ions
reduces Tv despite the fact that Y has a bigger and
Lu a smaller ionic radius (Zhang et al., 2002); doping the In sites by smaller Ag ions enhances Tv as
in YbIn1−xAgxCu4 for x ≤ 0.3 (Cornelius et al., 1997;
Lawrence et al., 1999). Thus, doping cannot be explained in terms of a chemical pressure. The lowtemperature phase is easily destabilized by an external
magnetic field: a critical field Hc(T ) induces a meta

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-35-3.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-35-8.png)

FIG. 27 Panel (a) shows the resistivity and the magnetic
susceptibility of Yb1−xYxInCu4 as functions of temperature for various concentrations of Y ions (Oˇcko and Sarrao,
2002). Note, all the “high-temperature” data can be collapsed onto a single universal curve, by normalizing the susceptibility with respect to an effective Yb-concentration (not
shown). Panel (b) shows the thermopower of Yb1−xYxInCu4
as a function of temperature for various concentrations of Y
ions (Oˇcko and Sarrao, 2002).


magnetic transition which is clearly seen in the magnetoresistance and the magnetization data. The experimental values of Hc(T ) define the H T phase bound               ary and the analysis of many systems with different
Tv [0] [(zero-field transition temperature) and][ H][c][(0) (zero-]
temperature critical field) reveal the following universal

      behavior: Hc(T ) = Hc(0) 1 − (2T/Tv [0] ) [2] . Despite the

differences in Tv and Hc, the data give a constant ratio
kBTv [0][/µ][B][H][c][(0) = 1][.][8.]
In summary, the Yb systems switch at the valencechange transition from a low-entropy valence-fluctuating
phase to a high-entropy magnetic semi-metallic phase.
The transition is accompanied by the transfer of holes
from the conduction band to the 4f shell and a metalinsulator transition (or crossover). The high-temperature
phase has degenerate local moments which interact with
the conduction band (and, hence, get reduced) but the
interaction is not of the usual Kondo type and no logarithmic anomalies are seen. Such a behavior can be
qualitatively understood by assuming that (i) the chemical potential of the metallic phase is close to the location
of the dip or gap in the DOS, which arises from manybody interactions, and that (ii) the energy of the localized



36


magnetic configuration is above the non-magnetic one as
T → 0. The metallic phase is destabilized by magnetic
fluctuations when the entropy gain due to additional (localized) magnetic states overcomes the energy loss due
to the change of the ionic configuration and the entropy
loss due to the reduction of the number of holes in the
conduction band. Once the chemical potential is brought
close enough to the band edge, by doping, pressure, temperature or magnetic field, the entropy of the band states
is suppressed and the magnetic entropy of the localized
states becomes sufficient to compensate the energy loss
and destabilize the metallic phase. This behavior is observed in many systems and it is not likely to be due to
band-structure effects alone. Rather, the gap or pseudogap which is a necessary ingredient of the above scenario
seems to be due to many-body interactions.
The valence-change transition is also found in many
Eu-based systems, and EuNi2(Si1−xGex)2 (Wada et al.,
1997) provides a typical and well-studied example. The
thermodynamic anomalies are similar as in Yb systems
but the transition temperature is higher and Eu ions undergo an almost complete valence change between the
high-temperature, f [7] and the low-temperature f [6] configuration. That is, the transition is from a free-spin
system at high temperatures to a simple metal at low
temperatures. The electron transport is similar as in
YbInCu4 but the intrinsic data are more difficult to
measure because the volume change at the transition
is large and samples typically crack when thermally cycled. In EuNi2(Si1−xGex)2 (Sakurai et al., 2000) the sign
of the thermopower is reversed with respect to Yb systems, which indicates an electron-like rather than holelike transport.
The high-temperature behavior of YbInCu4 and
EuNi2(Si1−xGex)2-like compounds can be well described by the FK model (Freericks and Zlati´c, 1998;
Zlati´c and Freericks, 2001b, 2003; Zlati´c et al., 2001).
We describe the f -ions by two energetically close configurations which differ in their f -count by one, we take
a common chemical potential for the conduction and localized electrons (which is adjusted at each temperature
to conserve the total number of electrons), we take the
FK Coulomb repulsion between the conduction electrons
(or holes) and the additional f -electron (or hole) large
enough to open a gap in the conduction band. For realistic modeling we should also take into account the actual
crystal-field structure including the splittings and the degeneracy of the ionic energy levels. For Yb ions, the state
with no f -holes has unit degeneracy, while the single-hole
case has a degeneracy of 8 (corresponding to J = 7/2).
The two-hole case is forbidden due to the mutual repulsion of two holes being too large. The 8-fold degeneracy
of a single f -hole is further reduced by CF splittings and
in a cubic environment we expect 4 doublets (unless there
is some accidental degeneracy). The external field further
splits these CF states. For Eu ions, we take into consideration the 4f [6] (3 [+] ) configuration with a non-magnetic
ground state and two excited magnetic states, and the


magnetic 4f [7] (2 [+] ) configurations. Since these states are
pure spins states, there are Zeeman splittings but no CF
splittings. All other states of Eu ions are higher in energy
and neglected.
To find the thermodynamic and transport properties
we need the weights of the ionic 4f configurations, i.e. we
need the partition function of a more general FK model.
Since the trace over f states still separates into a sum
over the states which differ by one f -electron, the end
result can be written as,




  imp = n0f
Z Z




   0σ(µ) + n0f [±][1]
Z Z
σ σ



0σ(µ U ) (141)
Z σ



37


FIG. 28 (a) Localized electron filling and (b) normalized
spin susceptibility for eightfold degenerate (S = 7/2) FalicovKimball model with ρtotal = 1.5, U = 2, and various Ef .


In what follows, we discuss a case that is similar to
that of Yb: the case of an S = 7/2 magnetic particle in
the high-temperature phase and of a magnetically inert
unoccupied state in the low-temperature phase; we neglect CF splitting but do consider Zeeman splitting. The
generalization to Yb ions with the magnetic f [13] states
split by the cubic CF, or to Eu ions with excited magnetic states in the low-temperature f [6] configuration, is
straightforward. We choose the Coulomb repulsion to be
U = 2, which is large enough to open a small gap in the
interaction DOS (see below) and we tune the bare f -level
to bring the renormalized f -level slightly above the chemical potential. Thus, at T = 0, there are no f -electrons
in the ground state but as T increases, the f -occupancy
increases, producing a local-moment response. Since the
filling of the f electrons is entropically driven, the filling
increases rapidly with T as the degeneracy increases. In
Fig. 28, we plot the average f -occupation and the spin
susceptibility (normalized by the total m [2] z [which equals]
42 for spin-seven-halves). Panel (a) of Fig. 28 shows that
as Ef is reduced, the high temperature value of ρf increases, the “transition temperature” decreases, and the
transition becomes sharper. Panel (b) shows the spin sus


where Z0σ(µ) is defined by Eq. ( 24) and Zn0f [and][ Z][n] f [0] [±][1]
are the partition functions of an isolated f -ion with n [0] f
and n [0] f

[±][ 1][ f] [-electrons, respectively. In the case of Yb]
ions, the n [0] f [= 14 configuration is non-magnetic, such]
that Zn0f [=14][ = 1, and the][ n] f [0] [−] [1 configuration has one]
magnetic hole in the J = 7/2 spin-orbit state, such that
the partition function becomes,



Zn0f [=13][ =]



�8

e [−][β][[][E][fη][(][H][)][−][µ][f][ ]] . (142)

η=1



The excitation energies Efη(H) of a single magnetic hole
are split into multiplets belonging to different irreducible
representations of the crystal.
In the case of Eu ions, the f [6] configuration has a nonmagnetic ground state and two magnetic S = 1 and S =
2 excitations. Assuming the usual Zeeman coupling with
the magnetic field gives the ionic partition function,


�1
Zn0f [=6][ = 1 +][ e][−][βE][S][=1] e [−][βgµ][B] [Hm]

m=−1

�2
+ e [−][βE][S][=2] e [−][βgµ][B] [Hm] . (143)


m=−2


The f [7] configuration is the magnetic Hund’s rule state
(S = 7/2) and its partition function is simply



Zn0f [=7][ =][ e][−][βE][S][=7][/][2]



�7/2

e [−][β][[][gµ][B] [Hm][s][−][µ][f][ ]] . (144)

ms=−7/2



The weights of the two ionic configurations are given by



n0f
w0 = Z
imp
Z





0σ(µ) (145)
Z
σ



and



n0f [±][1]
w1 = Z
imp
Z





0σ(µ U ) (146)
Z  σ



which enter the Green’s function formalism.



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-36-2.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-36-9.png)
![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-37-4.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-37-12.png)

FIG. 29 (a) DC resistivity and (b) thermopower for the (S =
7/2) Falicov-Kimball model with ρtotal = 1.5 and U = 2. The
different curves correspond to different values of Ef .


ceptibility, which is Curie-like but with a temperaturedependent concentration of local f -moments. Hence it
has a peaked form, with a sharp reduction of the magnetic response as T → 0. Defining Tv as the temperature
at which the spin susceptibility drops to half of the maximum value, we find Tv = 0.05, 0.03, 0.007 and 0.001 for
Ef = −0.4, −0.5, −0.6, and −0.65, respectively. In all
these cases we are dealing with a crossover rather than
a sharp phase transition. In the case Ef = −0.2 the
peak is too broad for the transition to be defined, and
for Ef = −0.7 the occupation of f -states remains finite
down to lowest temperatures. A first-order phase transition is possible for Ef between −0.65 and −0.7 but details
of this transition cannot be obtained by the iterative numerical procedure, which becomes unstable. The effect
of the f -level position on transport properties is shown in
Fig. 29. Panel (a) shows that the resistivity has a maximum at an effective temperature T [∗] which is much larger
than Tv and that the peak sharpens and moves to somewhat lower temperatures as Ef is reduced. Effects at Tv
are not visible, except for Ef = −0.65, which lies close
to the first-order transition. The thermopower results
shown in panel (b) are somewhat similar, except that the
transition at Tv cannot be detected. In addition, there
is a sign change in S that occurs at higher temperature.
The transport anomalies are due to the development of
a gap and the renormalization of the single-particle DOS
at high temperature, driven by the increased f -electron



38


FIG. 30 Interacting DOS for the (S = 7/2) Falicov-Kimball
model with ρtotal = 1.5, U = 2, Ef = −0.6 and for various
temperatures.


occupation and the Falicov-Kimball interaction.
The theoretical results shown in Figs. 28 and 29, obtained for ρtotal = 1.5, U = 2 and Ef close to −0.6,
exhibit most of the qualitative features seen in the experimental data. However, the model parameters and
the absolute value of the temperature scale used for the
static response functions cannot be determined unless
one compares the dynamic properties of the model to
experimental data.


FIG. 31 Optical conductivity for the (S = 7/2) FalicovKimball model with ρtotal = 1.5, U = 2, Ef = −0.6, and
for various temperatures.


The interacting conduction DOS is plotted in Fig. 30 as
a function of frequency, for the case ρtotal = 1.5, U = 2,
Ef = −0.6, and for various temperatures. Note, the
temperature-induced shift in the chemical potential from
the metallic region, with a high density of states, into the
gap-region. Unfortunately, direct comparison with the
photoemission spectra is not possible because the bulk
and surface effects in valence-fluctuating systems are difficult to separate.



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-37-6.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-37-18.png)
Fig. 31 shows the optical conductivity. We find a
characteristic high-frequency hump at ν = U, which
is almost Ef -independent, and a temperature-induced
transfer of spectral weight between the high- and lowfrequency regions. A Drude peak grows as ν → 0 for
T Tv. Thus, while the static transport is domi≤
nated by a pseudo-gap on the order of T [∗], the optical
conductivity is sensitive to the valence-change transition. The high-frequency peak in σ(ν) allows an estimate of the value of the FK Coulomb interaction, yielding U 1 eV (Garner et al., 2000) for YbInCu4. Using
≈
Tv = 42 K we find U/Tv ≈ 250 which can be used to
narrow the choice of the model parameters. The experimental features can be reproduced by taking the f -level
position at Ef = −0.6 but the procedure is not completely unique, because U/Tv is not independent of the
total number of particles. As an additional constraint on
the parameters one should demand that the theory reproduces the peaks in the high-temperature transport properties in the right temperature range. Clearly, a proper
quantitative description should also incorporate the CF
splittings of J=7/2 Yb states, which would provide the
field-induced anisotropies of the magnetization. This has
not yet been worked out in detail for either the Yb or Eu
compounds.


B. Electronic Raman Scattering


FIG. 32 Experimental Raman scattering results for (a)
SmB6 (Nyhus et al., 1995b, 1997) and (b) FeSi (Nyhus et al.,
1995a). The labels mark the different temperatures.


Experimental Raman scattering data on a wide variety
of different correlated insulators shows three distinctive
features: (i) as the temperature increases, there is a sudden transfer of spectral weight from a high-energy chargetransfer peak to lower energies; (ii) there is an isosbestic
point, where the Raman response is independent of temperature at a special frequency, and all Raman scattering curves cross; and (iii) if one takes the ratio of twice



39


the spectral range where spectral weight is depleted at
low temperature (representative of the insulating gap) to
the temperature at which the low-energy spectral weight
is restored (representative of Tc), then 2∆/kBTc 3.5.
≫
These features are shown in Fig. 32 where we plot the Raman response for (a) SmB6 (Nyhus et al., 1995b, 1997)
and (b) FeSi (Nyhus et al., 1995a).
Using the results of Tables VI and VII at X = 1 allows
us to calculate the Raman response in the A1g and B1g
channels. Since the Raman response ultimately is a complicated functional of the interacting density of states,
and since all insulators have the same qualitative feature of a gap near the chemical potential, we expect the
Raman response to depend only weakly on the microscopic features of the insulating phase. Hence, we perform our calculations for the simplest possible system
that goes through a Mott-like metal-insulator transition:
the spinless FK model at half filling (ρe = w1 = 0.5) on
a hypercubic lattice (Freericks and Devereaux, 2001a,b;
Freericks et al., 2001a).


FIG. 33 Theoretical calculation of the nonresonant Raman
response in the (a) A1g channel and the (b) B1g channel at
T = 0.5 and for various values of U .


We begin with a plot of the Raman response at fixed
temperature T = 0.5 and for a variety of values of U in
the two symmetry channels (Fig. 33). Note how for weak
correlations we have a linear onset, and a higher-energy
cutoff (from the band) as expected. As the correlations
increase, we see the response separates into a chargetransfer peak centered at U and a low-energy peak (in
the B1g sector only). The vertex corrections in the A1g
sector suppress the low-energy features and we simply see
the evolution of the charge-transfer peak, which is more
asymmetric in shape.
We choose to examine the inelastic light scattering for
U = 2 in more detail, because it is a correlated insulator that lies close to the metal-insulator transition. We
plot in Fig. 34 the inelastic X-ray scattering response
function along the zone diagonal for a variety of different
temperatures (Devereaux et al., 2003). The response at



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-38-1.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-38-3.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-38-5.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-38-8.png)
40


FIG. 34 Theoretical calculation of nonresonant inelastic X-ray scattering in the (a) A1g channel and the (b) B1g channel for
U = 2 along the zone diagonal for a range of different temperatures. The thickness of the lines determines the temperature
which ranges from 1.0 to 0.5 to 0.25 to 0.1. The individual curves for different X values have been shifted for clarity. The
X = 1 curves correspond to conventional electronic Raman scattering.



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-39-0.png)

the zone center is the Raman response. We find that it
displays all of the three features seen in experiment: (i)
there is a low-temperature depletion of low-energy spectral weight, (ii) there is an isosbestic point, and (iii) the
ratio of 2∆/kBTc (as extracted from the Raman response
curves) is on the order of 10–20. These three features are
generic to the plots at all X, except for X = 1 in the A1g
sector, where the low-energy spectral weight disappears.
This occurs because the finite-q vector mixes the different symmetries and the low-energy spectral weight is seen
in the other symmetries. Note that the results are independent of symmetry channel for X = −1, which makes
for the possibility of an interesting experimental probe of
nonlocal correlations. In general, we see a small amount
of dispersion of the peaks and a generic broadening of
the peaks as we move from zone center to zone boundary, but the isosbestic behavior remains for all q. So
far resonant inelastic X-ray scattering experiments have



been performed mainly at room temperature and with
polarizers only on the incident beam of light, so direct
comparison with theory is not yet feasible.


C. Josephson Junctions


Another area where the FK model has been applied
to real materials is in the field of Josephson junctions

[see Freericks et al. (2002c) for a review]. A Josephson
junction is a sandwich of two superconductors surrounding a barrier material that can be a normal metal, an
insulator, or something in between (Josephson, 1962).
In rapid single flux quantum (RSFQ) logic (Likharev,
2000), one tries to maximize the switching speed of the
Josephson junction, while maintaining a nonhysteretic
(single-valued) I − V characteristic. Since the integral of
a voltage pulse over time is equal to a flux quantum for a
Josephson junction, the height of the voltage pulse is in

versely proportional to the width of the pulse; hence one
wants to maximize the characteristic voltage to achieve
the fastest switching speeds. The characteristic voltage
is a product of the critical current at zero voltage Ic with
the normal-state resistance Rn (slope of the I − V characteristic at high voltage).
In conventional tunnel junctions, the barrier material
is an insulator, so Ic is low and Rn is high; in proximityeffect junctions, the barrier material is a normal metal,
so Ic is high and Rn is low. Is it possible that one can
maximize the product of IcRn by choosing a material
to lie close to the metal-insulator transition, where both
Ic and Rn can be large? We can examine this question
by describing the barrier material with the spin-one-half
FK model on a cubic lattice in the local approximation
with w1 = 0.5 and ρe = 1. This system has a metalinsulator transition in the bulk at U ≈ 4.9t. To simulate the properties of a Josephson junction, we must
solve an inhomogeneous DMFT problem as first done by
Potthoff and Nolting (1999) and generalized to the superconducting state by Miller and Freericks (2001). Using the FK model to describe the barrier material was
performed in Freericks et al. (2001b, 2003) and has been
reviewed elsewhere (Freericks et al., 2002c).


FIG. 35 Figure of merit as a function of the FK correlation
strength in a Josephson junction with a barrier of (a) one and
(b) five planes. The dotted line is the Ambegaokar-Baratoff
prediction for an ideal tunnel junction. The plots are at two
temperatures T = Tc/11 (open symbols) and T = Tc/2 (filled
symbols). ∆(0) is the superconducting gap at T = 0.


In Fig. 35, we plot the figure of merit IcRn versus U
for two cases: (a) a single-plane barrier and (b) a fiveplane barrier. Notice how the IcRn is maximized in a
ballistic metal for N = 1 at low T, but then is maximized in the tunnel junctions as T increases. The flatness of the curves in panel (a) for U > 5 is a verification
of the Ambegaokar and Baratoff (1963) analysis which



41


says IcRn is independent of the properties of the barrier
for thin tunnel junctions. Our result is somewhat lower
than the Ambegaokar-Baratoff prediction due to fermisurface effects, proximity and inverse proximity effects,
etc. What is interesting is that in panel (b) there is a
marked increase in the figure of merit at low temperature
near the metal-insulator transition. Indeed, we find IcRn
is maximized on the insulating side of the metal-insulator
transition, and the optimization remains for a wide range
of temperature (the reduction in IcRn arises mainly from
the temperature dependence of Rn for a correlated insulator). These results are consistent with experiments
performed on junctions made out of NbTiN for the superconductor and TaxN for the barrier (Kaul et al., 2001).
As tantalum is removed from TaN, it creates tantalum
vacancies, which are strongly interacting with the conduction electrons and can trap them at the vacancy site.
Such physics is described well by the FK model, with the
tantalum vacancy sites serving as the “f -electrons” that
scatter the conduction electrons.


FIG. 36 Critical current as a function of temperature for a
variety of different Josephson junctions. Note how the correlated insulator (solid triangles) is parallel to the thin insulator
(solid line) for a wide range of T .


In Fig. 36, we plot the critical current as a function
of temperature. Once again, our calculations produce
the Ambegaokar and Baratoff (1963) results for thin tunnel junctions. As junctions are made more metallic, or
thicker, the critical current drops more rapidly as a function of temperature. But the correlated barrier, just on
the insulating side of the transition, has a thermal slope
dIc(T )/dT that is essentially equal to that of the thin
tunnel junction in the range 0.4Tc < T < 0.7Tc which is
a typical operating range for a junction. Hence these correlated metal barriers (or SCmS junctions) may be the
optimal choice for the barrier in a Josephson junction,
enabling ultrafast superconductor-based digital electronics.



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-40-4.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-40-5.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-40-11.png)
D. Resistivity Saturation


The semiclassical Boltzmann equation approach to
transport indicates that the resistivity of a material
should continue to rise as the temperature rises. However, the theory breaks down once the mean free path of
the electrons becomes shorter than the interatomic spacing. Hence, there is an expectation for the resistivity to
slow its increase once the mean free path becomes too
small. An interesting set of materials that have been investigated a quarter century ago are the so-called A15
compounds such as V3Si and Nb3Ge (Fisk and Webb,
1976). These materials sparked much interest as being
the highest temperature superconductors of their day,
and they were widely studied, but a number of features
about these materials remain unsolved.
In conventional electron-phonon scattering metals, the
resistivity behaves like


ρ(T ) = AρT + Bρ (147)


at high temperature. Here Aρ is proportional to the
electron-phonon coupling strength and Bρ is proportional
to the impurity concentration. What was found in the
A15 materials was that Aρ was much smaller than expected, given the known strength of the electron-phonon
coupling and Bρ was sizable, even in very pure samples.
This behavior was called resistivity saturation, since it
implies a slow turnover of the high-temperature resistivity.
In 1999, Millis et al. (1999) solved an important puzzle in the resistivity saturation problem. They examined
the static harmonic Holstein model at high temperature
and saw the characteristic shape seen in resistivity saturation for strongly coupled systems. This analysis neglects the quantum-mechanical nature of the phonons,
since their kinetic energy is neglected, but this should be
a good approximation if the phonons are at a temperature much higher than the Einstein frequency of the Holstein model (estimated to be about the Debye frequency
of a real material). Note that the resistivity formula used
in Millis et al. (1999) does not properly have the velocity
factors for the Bethe lattice. This does not change the
results much near half filling, but would have a larger
effect for fillings closer to the band edge.
We illustrate this phenomenon in Fig. 37, where we
plot the resistivity at half filling ρe = 1 for the spin-onehalf static harmonic Holstein model on the hypercubic
lattice. We examine coupling strengths ranging from a
weakly coupled system (that is a fermi gas at T = 0) to
a strongly coupled insulator, that develops a gap in the
conduction electron DOS (see Fig. 25).
The theory behind the resistivity form in Eq. (147) depends on three assumptions: (i) the temperature is much
higher than the phonon energy scale, so the ions can be
approximated by classical oscillators and the equipartition theorem says x [2] i
interaction can be treated in second-order perturbation ⟨ [⟩≈] [T/κ][; (ii) the electron-phonon]
theory so the scattering rate is gep [2] [⟨][x][2] i

[⟩][; and (iii) Boltz-]



42


FIG. 37 (a) Resistivity as a function of temperature for the
half filled static harmonic Holstein model on the hypercubic
lattice and (b) parameters Aρ (solid line) and Bρ (dashed line)
fit for the range of temperature 0.2 < T < 1. Note how there
is a wide range of temperature where the resistivity appears
linear, but with a large intercept. Note further how Aρ grows
slower than gep [2]

[∝] [λ][.]


mann transport theory can relate the scattering rate
to the resistivity. Assumptions (i) and (ii) imply that
the scattering rate is linear in temperature. Millis et al.
(1999) find that the scattering rate actually increases like
√T due to the breakdown of the second-order perturba
tion theory for strong coupling. This is the key to resistivity saturation, as can be seen in Fig. 37. Indeed,
forcing the square root behavior to fit to a linear form
necessarily produces all of the observed resistivity saturation phenomena. Note further that even for an insulating
phase, we see the same kind of “resistivity saturation” at
high enough temperatures.


It is interesting as well that there are a variety of materials (mainly the doped fullerenes and the high-Tc superconductors) where the resistivity obeys the linear form
of Eq. (147) with small or vanishing Bρ up to very high
temperatures, where a naive estimate of the mean free
path is much less than a lattice spacing. The DMFT
analysis given here does not shed light onto that puzzle,
but recent work using other techniques has made much
progress (Calandra and Gunnarsson, 2001).



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-41-3.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-41-6.png)
E. Pressure-Induced Metal-Insulator Transitions


Nickel iodide (NiI2) is a transition-metal halide
that undergoes an isostructural metal-insulator transition at room temperature as a function of pressure (Pasternak et al., 1990). Nickel iodide crystallizes in
the CdCl2 structure, which consists of alternating hexagonal planes of nickel and iodine. The nickel ions have
a 2+ valence and the iodine ions have a 1− valence;
the neutral sandwich I [−] -Ni [++] -I [−] is stacked vertically to
form the crystal. In the insulating state, the S = 1
nickel spins order in a helical spin density wave, that
is closely approximated by ferromagnetic nickel planes,
stacked in an antiferromagnetic fashion. At ambient pressure TN = 75 K, and TN increases by a factor of four to
310 K at 19 GPa, where the system undergoes a metalinsulator transition and becomes metallic. The physical
picture is as follows: the d-electrons in the nickel band are
strongly correlated and form a Mott-like insulating state
(which can be approximated by dispersionless localized
electrons), and the iodine p-bands are completely filled
by the transfer of an electron to each iodine. As pressure increases, the relative position of the iodine p-bands
and the nickel d-bands changes, with the iodine p-bands
moving closer to the fermi level. Once the p-bands reach
the fermi level, electrons spill from the p-bands to the
nickel d-bands, quenching the magnetic moment (changing Ni [++] to Ni [+] ), stopping the antiferromagnetic transition, and allowing hole conduction within the p-bands.
Hence there is a transfer of charge from the iodine to the
nickel as the pressure increases causing a metal-insulator
transition. This is precisely the kind of transition envisioned in the original Falicov-Kimball model and optical
experiments confirm this picture (Chen et al., 1993).
Indeed, one can add spin interaction terms to the FK
model, to more accurately approximate this system, and
perform an analysis of the thermodynamics and map
out a phase diagram. This has already been done with
a mean-field-theory calculation (Freericks and Falicov,
1992), which shows antiferromagnetic insulating phases,
paramagnetic insulating phases, and metallic phases and
is depicted in Fig. 38. The phase diagram also shows
a classical critical point, where the first-order metalinsulator transition disappears. Unfortunately, the critical point is estimated to lie around 1400 K, which is beyond the disintegration temperature for NiI2. It would
be interesting to repeat the analysis of NiI2 with DMFT,
to see if the estimate of the critical point is reduced in
temperature and to examine properties like optical conductivity which have been measured.


V. NEW DIRECTIONS


A. 1/d Corrections


The dynamical mean field theory is exact in the
infinite-dimensional limit. But the real world is finite



43


FIG. 38 Mean-field theory phase diagram for NiI2
calculated within the Falicov-Kimball model picture (Freericks and Falicov, 1992). The shaded region
is the antiferromagnetic insulator, the region above the
chain-dotted line is the paramagnetic insulator. The paramagnetic metallic phase lies to the right of the nearly vertical
solid line. The first order transition line from an insulator
to a metal ends in a classical critical point (above that
temperature, one can continuously crossover from the metal
to the insulator). The symbol ∆denotes the difference
in energy from the localized Ni electrons to the bottom
of the I bands. It varies with an external parameter like
pressure. The dotted lines denote the regions of phase space
where three solutions of the mean-field theory equations are
stabilized.


dimensional, and so it is important to understand how
the infinite-dimensional limit relates to finite dimensions.
The simplest approximation for finite dimensions that
one can take is the so-called local approximation, where
one performs the DMFT, but uses the correct finitedimensional noninteracting DOS in the relevant Hilbert
transform. Such an approach was adopted for the FK
model by Freericks (1993b). Since we expect HartreeFock theory to be asymptotically exact in the limit as
U → 0 (for d > 1), and since the DMFT uses the correct
noninteracting susceptibility in determining CDW order,
the local approximation is asymptotically exact at weak
coupling. Deviations are expected to be much stronger in
the large coupling limit (where the model can be mapped
onto an effective Ising model at half filling), due to the
renormalization of Tc from spatial spin-wave fluctuations
that are neglected in the local approximation. In fact,
the situation at weak coupling is somewhat more complicated, because it is well known that the Hartree-Fock
approximation to the Hubbard model is renormalized due
to local quantum fluctuations by factors on the order of
three to five (van Dongen, 1991b, 1994). The 1/d corrections to this renormalization are typically small for the
Hubbard model (on the order of a few percent in two
and three dimensions). This weak-coupling perturbative
analysis has not been carried out for the FK model, and
there may be surprises there, because the DMFT Tc at
weak coupling does not take the conventional exponen


![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-42-0.png)
tial form. But the general thrust of this analysis is that
one expects DMFT and the local approximation to be
reasonably good at weak coupling, with larger deviations
as the coupling is made stronger.
The first attempt at a systematic expansion in 1/d
that can include nonperturbative effects was made
by Schiller and Ingersent (1995). They constructed a
generic self-consistent two-site impurity problem, which
had feedback into an auxiliary single-site impurity problem to calculate both the local and nearest-neighbor contributions to the self energy (i.e. the self energy is allowed to have an additional momentum dependence proportional to ǫk). This approach suffered from two difficulties. First, their self-consistent equations encountered
convergence problems when U was made large, and they
were only able to achieve converged results for small U
(where one does not expect there to be large corrections).
Second, one can immediately see that in regions where
the local contribution to the self energy is small, one
might lose causality (the imaginary part of the self energy can have the wrong sign) if the coefficient of the
ǫk term is too large. Indeed, the numerical calculations
suffered from negative DOS at the band edges as well.
A number of different approximate methods were also
attempted to improve upon the situation. The first
method is called the dynamical cluster approximation
(DCA) (Hettler et al., 2000, 1998) and we will describe
it in detail below. The second one is based on a truncation of a memory function expansion (which uses the Liouville operator space and continued-fraction techniques
to determine Green’s functions) (Minh-Tien, 1998; Tran,
1999). This technique is approximate and it includes
static nonlocal correlations and dynamic local correlations, which results in some pathologic behavior, such as
the interacting DOS remains temperature independent
in the canonical ensemble, just like DMFT. The third
method is based on a moment analysis of the Green’s
function and uses a self-consistent feedback of the f electron charge susceptibility onto the conduction electron Green’s function (Laad and van den Bossche, 2000).
This technique also requires a number of uncontrolled approximations in order to have numerical tractability. One
of the controversial predictions of the moment approach
is that the FK model in two dimensions has the Mott-like
metal-insulator transition occur at U = 0. The first two
techniques predict that it occurs at a finite value of U on
the order of half of the bandwidth.
We will concentrate our discussion here on the dynamical cluster approximation, which is a systematic technique in the thermodynamic limit for incorporating nonlocal correlations into the many-body problem. It is not
a formal expansion in 1/d, but rather is an expansion in
1/Nc, where Nc is the size of the self-consistent cluster
employed in the computational algorithm. From a physical point of view, one should view the DCA as an expansion in the spatial size over which spatial fluctuations
are included, so it allows large momentum (short-range)
spatial fluctuations, but does not properly describe long



44


wavelength fluctuations. The basic idea is to allow the
self energy to have momentum dependence in a coarsegrained fashion. The Brillouin zone is divided into Nc
equally sized regions, and the self energy assumes constant values within each of these regions (but can vary
from region to region). It turns out that one can guarantee causality is preserved with this technique.
We now describe the DCA algorithm in detail. We begin by dividing the Brillouin zone into Nc coarse-grained
cells, labeled by the central point of the cell K. In this
fashion, every wavevector in the Brillouin zone can be
written as k = K + k [˜] with k [˜] ranging over the coarsegrained cell. The K points are chosen to correspond
to the wavevectors of the Nc-site cluster with periodic
boundary conditions. The algorithm proceeds then as
follows: (i) we choose our initial guess for the coarsegrained self energy Σ(K, ω); (ii) we construct the coarsegrained Green’s function via



(iii) we extract the effective medium for the cluster
G [−] 0 [1][(][K][, ω][) = ¯][G][−][1][(][K][, ω][) + Σ(][K][, ω][); (iv) we solve the]
cluster problem for the cluster Green’s functions Gc given
the effective medium G0 and determine the cluster self
energy via Σc(K, ω) = G [−] 0 [1][(][K][, ω][)][ −] [G] c [−][1][(][K][, ω][); (v) we]
equate the cluster self energy with the coarse-grained self
energy Σ(K, ω) = Σc(K, ω) and substitute into step (ii)
to repeat the process. The algorithm is iterated until it
converges. Once converged, one can then evaluate the
irreducible vertex functions on the cluster using analogous Dyson equations; equating the cluster irreducible
vertex functions to the coarse-grained irreducible vertex
functions on the lattice then allows one to compute susceptibilities.
Under the assumption that the technique used to solve
the cluster Green’s functions given the effective medium
G0 is a causal procedure, then the cluster Green’s functions and self energies are manifestly causal. Forming
the coarse-grained Green’s function on the lattice from
the causal cluster self energy maintains the causality of
the Green’s function. The only place where noncausality
could enter the algorithm is in the step where we extract the effective medium, if the imaginary part of G [¯][−][1]

is smaller in magnitude than the imaginary part of the
coarse-grained self energy. But one can prove that this
never occurs, hence the algorithm is manifestly causal.
The DCA was applied to the FK model using two
different techniques. When the cluster size was small
enough (Nc 16), one could use exact enumeration to
≤
determine the weights for every possible configuration of
localized electrons on the lattice, and since the action is
quadratic in the fermions, one can determine the partition function exactly. For larger clusters, one needs to
determine the weights via a statistical sampling procedure, including the weights that are largest in the partition sums and neglecting those that are too small. We
will describe the exact enumeration method only here.



1
; (148)
ω + µ Σ(K, ω) ǫK+˜k
   -   


G¯(K, ω) = [N][c]

N






k˜


We let f denote a configuration {n [f] 1 [, n][f] 2 [, ..., n][f] Nc [}][ of]
the localized electrons (we consider only the spinless FK
model for simplicity). Then, the partition function for
the cluster becomes




 Zc =



2 [N][c] e [βµN][c][/][2] e [−][β][(][E][f] [−][µ][f] [)][N][ f] c

{f }



45


FIG. 40 Phase diagram for the half-filled FK model on a
square lattice with the DCA (Hettler et al., 2000). The different lines correspond to different size clusters. The 2 × 2
cluster determines Tc from the ordered phase, while the other
clusters employ a susceptibility analysis. Also included in the
figure is the Ising model Tc for the effective spin model with
J = t [2] /2U .


We also plot the phase diagram in Fig. 40 at half filling (Hettler et al., 2000). Included in the plot are the
local approximation, cluster calculations from susceptibilities on clusters up to Nc = 36, and an Ising model Tc
for J = 2t [2] /U which the FK model maps onto at strong
coupling; note that the 2 × 2 lattice result comes from an
ordered-phase calculation with exact enumeration, rather
than a susceptibility calculation. There are a number of
interesting comments to make about this phase diagram.
First, as expected we find the Tc is hardly changed on
the weak-coupling side of the diagram, indicating that
the local approximation determines the majority of the
many-body correlations in this regime. In the large-U
regime, one can see that the DCA does converge towards
the correct Ising model result, albeit slowly. The 2 × 2
data is surprising, as it is much lower than the results
for other clusters, but one can perhaps understand why
this would be by realizing that a four-site square lattice cluster with periodic boundary conditions is identical to a four-site one-dimensional chain cluster, except
for a change in the overall normalization of the hopping.
Since the Tc for a one-dimensional chain is equal to zero,
the suppression of Tc for the four-site cluster could be
arising from the two possible interpretations of the cluster. Hettler et al. (2000) argue in a similar vein, where
they observe that the fermi-surface points on a four-site
cluster occur at the van-Hove singularities, which have
uncommonly large scattering rates and hence are unfavorable for CDW order.
It is possible to explore dynamical susceptibilities
within the DCA as well. One simply needs to extract the
frequency and coarse-grained momentum irreducible susceptibilities and use the relevant Bethe-Salpeter equation
to calculate the full susceptibility. Unlike in the DMFT,
where the irreducible vertex only renormalizes symmetry
channels that have the full symmetry of the lattice, the
vertex now renormalizes all channels, because it contains



×



�∞


n=−∞



Det[G [−] 0 [1][(][i, j, iω][n][)][ −] [Un] i [f] [δ][ij] []]
(149)

[iωn] [N][c]



where the symbol Nc [f] [denotes the total number of lo-]
calized electrons in the configuration f and i and j are
spatial indices on the cluster. The determinant is over
the spatial indices i and j. The weight for the configuration f is the corresponding term in Eq. (149) divided by
c; we denote that weight by wf . The cluster Green’s
Z
function on the imaginary or real axis is then simply

   Gc(i, j, z) = wf [G [−] 0 [1][(][i, j, z][)][ −] [Un] i [f] [δ][ij][]][−][1][.] (150)

{f }


The weights are determined solely from the Green’s functions evaluated on the imaginary axis, while the Green’s
functions on the real axis are trivial to determine once
the weights are known. The convergence of the iterative
algorithm is much slower on the real axis though.


FIG. 39 Many-body density of states for the half-filled FK
model on a square lattice using the DCA on a 4 × 4 cluster
with U = 4 (Hettler et al., 2000). Note how the DOS now
has temperature dependence, and how a pseudogap develops
and deepens as T is lowered. Once a CDW opens, the system
will open a true gap.


One of the interesting features of the DCA is that
it restores temperature dependence to the conductionelectron DOS. This is shown in Fig. 39 where we plot the
DOS at five different temperatures (all above the CDW
Tc) for an intermediate value of U = 4t on a 4 4 square×
lattice cluster at half filling (Hettler et al., 2000). Note
how the pseudogap deepens as the temperature is lowered. Of course a true gap will develop in the CDW
phase at the lowest temperatures. There is no obvious
way of “turning off” the CDW phase below Tc anymore,
because the f configurations with the highest weight will
be those that correspond to the CDW ordered state below Tc.



![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-44-0.png)

![](.figures/arxiv__cond-mat-0301188/cond-mat-0301188.pdf-44-4.png)
momentum dependence. This remains one of the open
problems of interest for the DCA.


B. Hybridization and f -Electron Hopping


The FK model in infinite dimensions admits a simple solution, because the Hilbert space of the impurity
problem generated by the DMFT mapping is a direct
product of invariant subspaces with a fixed f -occupation.
In each subspace we can easily find the itinerant electron Green’s function and the generalized partition function [the generating functional of Kadanoff and Baym,
Z = Det(G [−] 0 [1][)]. In the absence of quantum fluctuations]
in the f -particle number each f -state has an infinite lifetime but the f -spectral function acquires a finite width
due to the f − c coupling which acts as an effective timedependent potential for the f -electrons and the broadening is due to the statistical averaging over all possible
states. In this respect the FK problem is a lattice generalization of the X-ray edge problem. Actually, as long
as the coherent scattering of conduction electrons on f electrons is neglected, we can drop the self-consistency
condition Eq.(31) and use the X-ray edge model solution
for the lattice problem (Si et al., 1992). At lower temperatures, the system becomes coherent and the single-site
X-ray solution has to be replaced by the DMFT selfconsistency (effective medium), so as to keep track of all
the other f -sites on the lattice. Despite its simplicity,
the DMFT solution of the FK model has some interesting features and can be used to describe physical systems
in which quantum fluctuations can be neglected, like the
high-temperature phase of Yb- and Eu-compounds with
a valence-change transition or the charge-transfer metalinsulator transition in NiI2.
However, if the f -particle dynamics are important,
which is often the case at low enough temperature, one
should consider a more general model. For example, in
the Yb-systems discussed in Section IV.A, the valence
of Yb ions below Tv is much larger than predicted by
the FK model and the reduction of the local moment
does not follow from ρf (T ) but is due to quantum fluctuations and lifetime effects. If the ground state is a
mixture of 2+ and 3+ states one should not neglect the
f −c hybridization and a better description would be provided by a periodic Anderson model with an additional
FK term. The actual situation pertaining to Yb ions is
quite complicated, as one should consider an extremely
asymmetric limit of the Anderson model, in which there
is no Kondo resonance (the ground state is not Kondolike) and there is no single universal energy scale which is
relevant at all temperatures (Krishnamurty et al., 1980).
We believe such a generalized model would behave as
the FK model at high temperatures and as a periodic
Anderson model at low temperatures. Indeed, incoherent scattering of conduction electrons on the FK ions
favors the gap opening even in the presence of hybridization; and if the width of the f -level is large due to the



46


FK interaction, the additional effects due to quantum
mixing should be irrelevant. This is supported by the
scaling arguments (Withoff and Fradkin, 1990) and the
numerical renormalization group analysis of various impurity models (Vojta and Bulla, 2002) which show that,
as long as the chemical potential is close to the gap and
the hybridization is below some critical value, the f -level
decouples from the conduction sea. On the other hand,
at low temperature, the chemical potential shifts away
from the gap in the DOS. For a flat conduction band
and the f -level close to the chemical potential, the hybridization effects are important and they can drive the
system towards a valence-fluctuating fixed point. The
most likely effect of the FK correlation at low temperatures is to renormalize the parameters of the Anderson
model.
A generalized FK model might also be needed
to describe the electronic ferroelectrics proposed by
Portengen et al. (1996a,b). The Bose-Einstein condensation (BEC) of f − c excitons and a spontaneous polarization can be obtained by a mean-field treatment of
the hybridized model. This picture is further supported
by the examination of the spontaneous hybridization for
the spinless FK model on the Bethe lattice, where it is
found that as the temperature is lowered the system appears to have a logarithmic divergence in the spontaneous
hybridization susceptibility at T = 0. Normally we cannot reach such a state because the system will have a
phase transition to either a phase separated state or a
charge-density wave, but we can tune the system so that
it remains in a classical intermediate-valence state down
to T = 0. When this occurs, effects of even a small hybridization will take the system away from the FK fixed
point at low enough temperature.
Another generalization is obtained by allowing direct
f − f hopping, t [f] ij [, which leads, for][ t][f] ij [=][ t] ij [c] [, to the rich]
physics of the Hubbard model (Hubbard, 1963). The
casef − tf hopping induces an [f] ij [≪] [t] ij [c] [is also interesting, because even a small] f − c coherence and gives
a ground state (for large U ) which is either a BEC of
electron-hole pairs (f − c excitons) or an orbitally ordered state (Batista, 2002). Unfortunately, as soon as the
f -electron dynamics is restored, the evolution operator
connects all sectors of the Hilbert space and the resulting
DMFT equations describe a two-level system with each
level coupled to an arbitrary external field. This problem
(or the equivalent Anderson impurity problem) is much
more difficult to solve than the FK impurity problem
with a single external field coupled to an electron.


C. Nonequilibrium Effects


Equilibrium properties in the DMFT have been studied extensively. Much less effort has been placed on
nonequilibrium calculations, where the correlated manybody system is driven away from equilibrium by large
amplitude external fields or driving voltages. The formal

ism for DMFT in a nonequilibrium situation has been addressed by Schmidt and Monien (2002). They considered
the case of a Hubbard model that interacts with a large
amplitude electromagnetic field with a constant driving
frequency ω. The formalism employs Keldysh techniques
to derive the three Green’s functions of relevance: the
advanced, retarded, and so-called lesser Green’s function.
They find that in the steady state, one can perform calculations in frequency space, if the driving frequency is
uniform. They applied their calculations to the Hubbard model, and used the iterated perturbation theory
to evaluate the impurity-problem dynamics. Nevertheless, their formalism is general, and can be used for FK
model problems as well. In addition, one could choose
to perform calculations purely in the time domain. This
would allow one to calculate the response of the system
to large amplitude, and fast (i.e. femtosecond) electromagnetic pulses. In this case, one would be interested in
the transient response that brings the system back to the
equilibrium state after being disturbed.


There is another class of problems that are ideal for
being considered with Keldysh techniques. Namely, the
problem of the steady-state current response to a voltage applied over an inhomogeneous device. One can
imagine stacking correlated planes (described by the FK
model) in between a semi-infinite number of noninteracting metallic planes (above and below) that form ballistic current leads for the device. One enforces current
conservation from plane to plane, which then determines
the change in the voltage from plane to plane in the device. In this fashion, one can calculate the self-consistent
current-voltage characteristic of a nonlinear device that
contains correlated materials (and also the voltage profile throughout the device). The leads can be described
by a wide class of Hamiltonians, including the HartreeFock description of a ferromagnet, or a Bardeen-CooperSchrieffer superconductor, or a diffusive FK metal, and
the barrier material (of arbitrary width) can be described
by the FK model tuned through the metal-insulator transition. Then, since the total action is quadratic in the
fermionic variables (although it is not time-translationinvariant) the path integral over the Keldysh contour
can be evaluated by taking the determinant of the corresponding continuous (matrix) operator. Discretizing
the operator as was done when we described the localized electron spectral function, will then allow for the
response to be solved exactly. We believe this will be
the first example of a correlated electronic system that
can undergo a metal-insulator transition, and have it’s
nonequilibrium response determined exactly. The calculation is nontrivial, but is likely to produce a series of
interesting results. One can apply such a formalism to a
wide variety of devices such as Josephson junctions, spinvalve transistors, ballistic spin filters, or thermoelectric
coolers. The choices are endless, as long as one always
restricts the effective actions to remain quadratic in the
fermionic variables. Generalization to more complicated
systems is also possible, but usually requires one to re


47


sort to approximate methods to solve the corresponding
impurity problems.


VI. CONCLUSIONS


It has been over thirty years since Falicov and Kimball
introduced their model to describe the physics behind
rare-earth and transition-metal metal-insulator transitions. The model has a rich history and much effort
has been devoted to solving the model and illustrating
its properties. The field was dramatically advanced fourteen years ago when Brandt and Mielsch showed that
the model could be solved exactly in the limit of large
dimensions. Since then much work has been done on
investigating the solutions of the model.


In this review we have covered the exact solution of
the Falicov-Kimball model (and the related static Holstein model) with dynamical mean-field theory. Our focus was on developing the formalism with a path-integral
approach that concentrated on the Matsubara frequency
representation of the fermions. Falicov-Kimball model
physics is a mature field where nearly all thermodynamic properties of the solutions have been worked out
in the limit of large spatial dimensions. This includes
charge-density-wave transitions, metal-insulator transitions, phase separation, electrical and thermal transport,
inelastic light scattering, and so on. The model has also
been employed in more applied problems such as investigating thermodynamic properties of Josephson junctions.


These exact solutions are useful for two reasons. First,
there is a growing list of materials that appear to be able
to be described by FK model physics, including YbInCu4,
EuNi2(Si1−xGex)2, TaxN, and NiI2. Similar models have
been also applied to the doped manganites and to diluted magnetic semiconductors. Second, exact solutions
are useful benchmarks for illustrating the phenomena associated with strong correlations and for testing different
approximation methods for their accuracy.


The newer frontiers that will be examined in the future
include a thorough investigation of equilibrium properties
in finite-dimensional systems, the addition of hybridization or itineracy of the f -electrons and the examination
of nonequilibrium effects in all dimensions. The success
to date with this model, indicates that the time is ripe
for more applications in the near future. It seems likely
the FK model can be employed to determine a number of
interesting applications in correlated devices, which can
lay the groundwork for later efforts in more complicated
correlated systems. We look forward to seeing how the
field will develop in the ensuing years and hope that this
review will encourage others to enter the field and rapidly
contribute to its future development.


Acknowledgments


Our work on the Falicov-Kimball model and related
models has been supported over the past few years by the
National Science Foundation under grants DMR-9973225
and DMR-0210717 and by the Office of Naval Research
under grants N00014-96-1-0828 and N00014-99-1-0328.
V.Z. acknowledges support from the Swiss National Science Foundation grant no. 7KRPJ65554, the Alexander
von Humboldt foundation and the Ministry of Science of
Croatia. In addition, we are grateful to the many useful discussions and collaborations with colleagues on the
properties of the Falicov-Kimball model. While we cannot list everyone who has influenced us, we especially
would like to thank P. Anderson, J. Annett, I. Aviani,
D. Belitz, U. Brandt, A. Chattopadhyay, A. Chen, W.
Chung, S.L. Cooper, G. Czycholl, T. Devereaux, L. Falicov, P. Farsakovˇsk´y, Z. Fisk, C. Geibel, A. Georges, Ch.
Gruber, R. Hackl, Z. Hasan, M. Hettler, J. Hirsch, V.
Janis, M. Jarrell, J. Jedrezejewski, T. Kirkpatrick, T.
Klapwijk, M. Klein, G. Kotliar, R. Lema´nski, E. Lieb, N.
Macris, G. Mahan, J. Mannhart, M. Mihjak, P. Miller,
A. Millis, E. M¨uller-Hartmann, N. Newman, B. Nikoli´c,
M. Oˇcko, P. Nozi´eres, Th. Pruschke, J. Rowell, J. Sarrao, D. Scalapino, J. Serene, L. Sham, S. Shastry, Z.-X.
Shen, A. Schiller, A. Shvaika, F. Steglich, N. TahvildarZadeh, D. Ueltschi, P. van Dongen, T. van Duzer, and
D. Vollhardt. We also thank P. van Dongen for a critical
reading of this manuscript.


List of Symbols


References


Allen, J. W., and R. M. Martin, 1982, Phys. Rev. Lett. 49,
1106.
Allub, R., and B. Alascio, 1996, Solid St. Commun. 99, 66.
Allub, R., and B. Alascio, 1997, Phys. Rev. B 55, 14113.
Altshuler, T., M. Bresler, M. Schlott, B. Elschner, and
E. Graty, 1995, Z. Phys. B 99, 57.
Ambegaokar, V., and A. Baratoff, 1963, Phys. Rev. Lett. 10,
486.
Anderson, P. W., 1959, J. Phys. Chem. Solids 11, 26.
Ashcroft, N. W., and N. D. Mermin, 1976, Solid State Physics
(Holt, Rinehart and Winston, Philadelphia).
Batista, C. D., 2002, Phys. Rev. Lett. 89, 166403.
Baym, G., 1962, Phys. Rev. 127, 1391.
Bergmann, G., and D. Rainer, 1974, Z. Phys. 174, 445.
Blawid, S., and A. J. Millis, 2000, Phys. Rev. B 62, 2424.
Blawid, S., and A. J. Millis, 2001, Phys. Rev. B 63, 115114.
Brandt, U., and A. Fledderjohann, 1992, Z. Phys. B 87, 111.
Brandt, U., A. Fledderjohann, and G. Hulsenbeck, 1990, Z.
Phys. B 81, 409.
Brandt, U., and C. Mielsch, 1989, Z. Phys. B 75, 365.
Brandt, U., and C. Mielsch, 1990, Z. Phys. B 79, 295.
Brandt, U., and C. Mielsch, 1991, Z. Phys. B 82, 37.
Brandt, U., and R. Schmidt, 1986, Z. Phys. B 63, 45.
Brandt, U., and R. Schmidt, 1987, Z. Phys. B 67, 43.
Brandt, U., and M. P. Urbanek, 1992, Z. Phys. B 89, 297.



48


A1g, B1g, B2g symmetries for inelastic light scattering
Aρ (Bρ) coefficients for resistivity saturation
Aσ(ω) interacting conduction electron DOS
Aσ(ǫ, ω) spectral function
Det determinant
Efη localized electron site energy
Ef [∗] renormalized f -level
FHelm Helmholz free energy
Fη(z) localized electron Green’s function
F∞(z) Hilbert transform
G(z) local conduction electron Green’s function
G0(z) effective medium
H magnetic field
K¯ cluster momentum
Lij transport coefficients
S thermopower
2S + 1 number of η states
SL (Simp) lattice (impurity) action
T temperature
Tv valence-change transition temperature
Tτ time-ordering operator
Tr trace
U FK interaction
Uηη [ff][′] f f Coulomb interaction
      
V number of lattice sites
Wi integral weight factors
X(q) momentum parameter
Znσ argument (iωn + µ − Σnσ)
ZT thermal transport figure-of-merit
Z(0) wavefunction renormalization factor
c [†] iσ [(][c][iσ][)] creation (annihilation) operator of itinerant
electron at site i with spin σ
e electric charge
exp exponential
fiη [†] [(][f][iη][)] creation (annihilation) operator of localized
electron at site i with spin η
f (ω) Fermi-Dirac distribution
g gyromagnetic ratio (conduction electrons)
g [aux] auxiliary Green’s function
gep electron-phonon coupling (deformation potential)
gf gyromagnetic ratio (itinerant electrons)
jn (jQ) number (heat) current operator
kB Boltzmann constant
ln natural logarithm


Calandra, M., and O. Gunnarsson, 2001, Phys. Rev. Lett. 87,
266601.
Chattopadhyay, A., S. Das Sarma, and A. J. Millis, 2001,
Phys. Rev. Lett. 87, 227202.
Chattopadhyay, A., A. J. Millis, and S. Das Sarma, 2000,
Phys. Rev. B 61, 10738.
Chen, A. L., P. Y. Yu, and R. D. Talyor, 1993, Phys. Rev.


Lett. 71, 4011.
Chester, G. V., and A. Thellung, 1961, Proc. Phys. Soc. London 77, 1005.
Chung, W., and J. K. Freericks, 1998, Phys. Rev. B 57, 11955.
Chung, W., and J. K. Freericks, 2000, Phys. Rev. Lett. 84,
2461.
Ciuchi, S., and F. de Pasquale, 1999, Phys. Rev. B 59, 5431.
Cornelius, A. L., J. M. Lawrence,, J. Sarrao, Z. Fisk, M. F.
Hundley, G. H. Kwei, J. D. Thompson, C. H. Booth, and
F. Bridges, 1997, Phys. Rev. B 56, 7993.
Czycholl, G., 1999, Phys. Rev. B 59, 2642.
Dallera, C., M. Grioni, A. Shukla, G. Vank´o, J. L. Sarrao,
J. P. Rueff, and D. L. Cox, 2002, Phys. Rev. Lett. 88,
196403.
de Vries, P., K. Michielsen, and H. De Raedt, 1993, Phys.
Rev. Lett. 70, 2463.
de Vries, P., K. Michielsen, and H. De Raedt, 1994, Z. Phys.
B 95, 475.
Devereaux, T. P., G. E. D. McCormack, and J. K. Freericks,
2003, Phys. Rev. Lett. 90, XXXXXX.
van Dongen, P. G. J., 1991a, Mod. Phys. Lett. B 5, 861.
van Dongen, P. G. J., 1991b, Phys. Rev. Lett. 67, 757.
van Dongen, P. G. J., 1992, Phys. Rev. B 45, 2267.
van Dongen, P. G. J., 1994, Phys. Rev. B 50, 14016.
van Dongen, P. G. J., and N. Bl¨umer, 2002, unpublished.
van Dongen, P. G. J., and C. Leinung, 1997, Ann. Phys.
(Leipzig) 6, 45.
van Dongen, P. G. J., and D. Vollhardt, 1990, Phys. Rev.
Lett. 65, 1663.
Dzero, M. O., 2002, J. Phys.: Condens. Matter 14, 631.
Dzero, M. O., L. Gor’kov, and A. K. Zvezdin, 2000, J. Phys.:
Condens. Matter 12, L711.
Dzero, M. O., L. Gor’kov, and A. K. Zvezdin, 2002, Physica
B 312 & 313, 321.
Economou, E. N., 1983, Green’s Functions in Quantum
Physics (Springer-Verlag, Berlin).
Elitzur, S., 1975, Phys. Rev. D 12, 3978.
Falicov, L. M., and J. C. Kimball, 1969, Phys. Rev. Lett. 22,
997.
Farkasovˇsk´y, P., 1997, Z. Phys. B 104, 553.
Farkasovˇsk´y, P., 1999, Phys. Rev. B 59, 9707.
Farkasovˇsk´y, P., 2002, Phys. Rev. B 65, 081102.
Felner, I., and I. Novik, 1986, Phys. Rev. B 33, 617.
Fetter, A. L., and J. D. Walecka, 1971, Quantum Theory of
Many-Particle Systems (McGraw-Hill, New York).
Figueroa, E., J. M. Lawrence, J. Sarrao, Z. Fisk, M. F. Hundley, and J. D. Thompson, 1998, Solid State Commun. 106,
347.
Fisk, Z., and G. W. Webb, 1976, Phys. Rev. Lett. 36, 1084.
Freericks, J. K., 1993a, Phys. Rev. B 47, 9263.
Freericks, J. K., 1993b, Phys. Rev. B 48, 14797.
Freericks, J. K., and T. P. Devereaux, 2001a, Condens. Mat.
Phys. 4, 149.
Freericks, J. K., and T. P. Devereaux, 2001b, Phys. Rev. B
64, 125110.
Freericks, J. K., T. P. Devereaux, and R. Bulla, 2001a, Acta
Phys. Pol. B 32, 3219.
Freericks, J. K., and L. M. Falicov, 1990, Phys. Rev. B 41,
2163.
Freericks, J. K., and L. M. Falicov, 1992, Phys. Rev. B 45,
1896.
Freericks, J. K., C. Gruber, and N. Macris, 1996, Phys. Rev.
B 53, 16189.
Freericks, J. K., C. Gruber, and N. Macris, 1999, Phys. Rev.



49


B 60, 1617.
Freericks, J. K., and R. Lema´nski, 2000, Phys. Rev. B 61,
13438.
Freericks, J. K., E. H. Lieb, and D. Ueltschi, 2002a, Phys.
Rev. Lett. 88, 106401.
Freericks, J. K., E. H. Lieb, and D. Ueltschi, 2002b, Commun.
Math. Phys. 227, 243.
Freericks, J. K., and P. Miller, 2000, Phys. Rev. B 62, 10022.
Freericks, J. K., B. N. Nikoli´c, and P. Miller, 2001b, Phys.
Rev. B 64, 054511.
Freericks, J. K., B. N. Nikoli´c, and P. Miller, 2002c, Int. J.
Modern Phys. B 16, 531.
Freericks, J. K., B. N. Nikoli´c, and P. Miller, 2003, Appl.
Phys. Lett. XX, XXXXX.
Freericks, J. K., and V. Zlati´c, 1998, Phys. Rev. B 58, 322.
Freericks, J. K., and V. Zlati´c, 2001a, Phys. Rev. B 64,
073109.
Freericks, J. K., and V. Zlati´c, 2001b, Phys. Rev. B 64,
245118.
Freericks, J. K., and V. Zlati´c, 2002a, Phys. Rev. B 66,
249901, erratum.
Freericks, J. K., and V. Zlati´c, 2002b, eprint condmat/0211385.
Freericks, J. K., V. Zlati´c, and M. Jarrell, 2000, Phys. Rev.
B 61, 838.
Garner, S. R., J. Hancock, Y. Rodriguez, Z. Schlesinger,
B. Bucher, Z. Fisk, and J. L. Sarrao, 2000, Phys. Rev.
B 63, R4778.
Georges, A., G. Kotliar, W. Krauth, and M. J. Rozenberg,
1996, Rev. Mod. Phys. 68, 13.
Gon¸calves da Silva, C. E. T., and L. M. Falicov, 1972, J. Phys.
C: Solid State Phys. 5, 906.
Goremychkin, E. A., and R. Osborn, 1993, Phys. Rev. B 47,
14280.
Greenwood, D. A., 1958, Proc. Phys. Soc. (London) 71, 585.
Gruber, C., 1999, Mathematical Results in Statistical Mechanics (World Scientific, Singapore), p. 199.
Gruber, C., and N. Macris, 1996, Helv. Phys. Acta 69, 850.
Gruber, C., N. Macris, P. Royer, and J. K. Freericks, 2001,
Phys. Rev. B 63, 165111.
Gruber, C., D. Ueltschi, and J. Jedrzejewski, 1994, J. Stat.
Phys. 76, 125.
Haller, K., 2000, Commun. Math. Phys. 210, 703.
Haller, K., and T. Kennedy, 2001, J. Stat. Phys. 102, 15.
Hettler, M. H., M. Mukherjee, M. Jarrell, and H. R. Krishnamurthy, 2000, Phys. Rev. B 61, 12739.
Hettler, M. H., N. Tahvildar-Zadeh, M. Jarrell, T. Pruschke,
and H. R. Krishnamurthy, 1998, Phys. Rev. B 58, R7475.
Hirsch, J. E., 1993, Phys. Rev. B 47, 5351.
Holstein, T., 1959, Ann. Phys. (New York) 8, 325.
Hubbard, J., 1963, Proc. Roy. Soc. (London) A276, 238.
Hwang, E. H., A. J. Millis, and S. Das Sarma, 2002, 65,
233206.
Immer, C. D., J. Sarrao, Z. Fisk, A. Lacerda, C. Mielke, and
J. D. Thompson, 1997, Phys. Rev. B 56, 71.
Janis, V., 1994, Phys. Rev. B 49, 1612.
Jarrell, M., 1992, Phys. Rev. Lett. 69, 168.
Jonson, M., and G. D. Mahan, 1980, Phys. Rev. B 21, 4223.
Jonson, M., and G. D. Mahan, 1990, Phys. Rev. B 42, 9350.
Josephson, B. D., 1962, Phys. Lett. 1, 251.
Kaul, A., S. Whitely, T. van Duzer, L. Yu, N. Newman, and
J. Rowell, 2001, Appl. Phys. Lett. 78, 99.
Kennedy, T., 1994, Rev. Math. Phys. 6, 901.
Kennedy, T., 1998, J. Stat. Phys. 91, 829.


Kennedy, T., and E. Lieb, 1986, Physica 138A, 320.
Khurana, A., 1990, Phys. Rev. Lett. 64, 1990.
Krishnamurty, H. B., J. W. Wilkins, and K. G. Wilson, 1980,
Phys. Rev. B 21, 1044.
Kubo, R., 1957, J. Phys. Soc. Japan 12, 570.
Laad, M. S., and M. van den Bossche, 2000, J. Phys.: Conden.
Matter 12, 2209.
Lawrence, J. M., R. Osborn, J. L. Sarrao, and Z. Fisk, 1999,
Phys. Rev. 59, 1134.
Lawrence, J. M., S. M. Shapiro, J. L. Sarrao, and Z. Fisk,
1997, Phys. Rev. 55, 14467.
Lemberger, P., 1992, J. Phys. A 25, 715.
Letfulov, B. M., 1999, Europhys. J. B11, 423.
Letfulov, B. M., and J. K. Freericks, 2001, Phys. Rev. B 64,
174409.
Levin, E., B. S. Kuzhel, O. Bodak, B. D. Belan, and I. Stets,
1990, Phys. Stat. Sol. (b) 161, 783.
Lieb, E., 1986, Physica 140A, 240.
Likharev, K., 2000, Applications of Superconductivity
(Kluwer, Dordrecht), chapter 5.
Luttinger, J. M., and J. C. Ward, 1960, Phys. Rev. 118, 1417.
Maldague, P. F., 1977, Phys. Rev. B 16, 2437.
Metzner, W., 1991, Phys. Rev. B 43, 8549.
Metzner, W., and D. Vollhardt, 1989, Phys. Rev. Lett. 62,
324.
Michielsen, K., 1993, Int. J. Mod. Phys. B 7, 2571.
Miller, P., and J. K. Freericks, 2001, J. Phys.: Conden. Matter
13, 3187.
Millis, A. J., J. Hu, and S. Das Sarma, 1999, Phys. Rev. Lett.
82, 2354.
Millis, A. J., P. B. Littlewood, and B. I. Shraiman, 1995,
Phys. Rev. Lett. 74, 5144.
Millis, A. J., R. Mueller, and B. I. Shraiman, 1996, Phys. Rev.
B 54, 5389.
Minh-Tien, T., 1998, Phys. Rev. B 58, R15965.
Mitsuda, A., T. Goto, K. Yoshimura, W. Zhang, N. Sato,
K. Kosige, and H. Wada, 2002, Phys. Rev. Lett. 88, 137204.
Moeller, G., A. Ruckenstein, and S. Schmitt-Rink, 1992,
Phys. Rev. B 46, 7427.
M¨uller-Hartmann, E., 1989a, Z. Phys. B 74, 507.
M¨uller-Hartmann, E., 1989b, Int J. Mod. Phys. B 3, 2169.
Murani, A., D. Richard, and R. Bewley, 2002, Physica B 312
& 313, 346.
Nyhus, P., S. Cooper, and Z. Fisk, 1995a, Phys. Rev. B 51,
R15626.
Nyhus, P., S. Cooper, Z. Fisk, and J. Sarrao, 1995b, Phys.
Rev. B 52, R14308.
Nyhus, P., S. Cooper, Z. Fisk, and J. Sarrao, 1997, Phys. Rev.
B 55, 12488.
Oˇcko, M., and J. L. Sarrao, 2002, Physica B 312 & 313, 341.
Pasternak, M. P., R. D. Taylor, A. Chen, C. Meade, L. M.
Falicov, A. Giesekus, R. Jeanloz, and P. Y. Yu, 1990, Phys.
Rev. Lett. 65, 790.
Plischke, M., 1972, Phys. Rev. Lett. 28, 361.
Portengen, T., T. Oestreich, and L. J. Sham, 1996a, Phys.
Rev. Lett. 76, 2284.
Portengen, T., T. Oestreich, and L. J. Sham, 1996b, Phys.
Rev. B 54, 17452.
Potthoff, M., and W. Nolting, 1999, Phys. Rev. B 59, 2549.
Pruschke, T., D. L. Cox, and M. Jarrell, 1993a, Europhys.
Lett. 21, 593.
Pruschke, T., D. L. Cox, and M. Jarrell, 1993b, Phys. Rev. B



50


47, 3553.
Pruschke, T., M. Jarrell, and J. K. Freericks, 1995, Adv. Phys.
44, 187.
Ramakrishnan, T. V., 2003, Concepts in Electron Correlation
(Kluwer, Dordrecht), volume XX of Nato Science Series II.
Mathematics, Physics, and Chemistry, p. XXX.
Ramirez, R., and L. M. Falicov, 1971, Phys. Rev. B 3, 2425.
Ramirez, R., L. M. Falicov, and J. C. Kimball, 1970, Phys.
Rev. B 2, 3383.
Rettori, C., S. B. Oseroff, D. Rao, P. G. Pagliuso, G. E. Barberis, J. Sarrao, Z. Fisk, and M. F. Hundley, 1997, Phys.
Rev. B 56, 7993.
Sakurai, J., S. Fukuda, A. Mitsuda, H. Wada, and M. Shiga,
2000, Physica B 281 & 282, 134.
Sarrao, J. L., 1999, Physica B 259 & 261, 129.
Schiller, A., 1999, Phys. Rev. B 60, 15660.
Schiller, A., and K. Ingersent, 1995, Phys. Rev. Lett. 75, 113.
Schmidt, P., and H. Monien, 2002, eprint cond-mat/0202046.
Schwartz, L., and E. Siggia, 1972, Phys. Rev. B 5, 383.
Shastry, B. S., and B. I. Shraiman, 1990, Phys. Rev. Lett. 65,
1068.
Shastry, B. S., and B. I. Shraiman, 1991, Int. J. Mod. Phys.
B 5, 365.
Shvaika, A. M., 2000, Physica C 341-348, 177.
Shvaika, A. M., 2001, J. Phys. Stud. 5, 349.
Shvaika, A. M., 2002, eprint cond-mat/0205322.
Shvaika, A. M., and J. K. Freericks, 2002, eprint condmat/0211451.
Si, Q., G. Kotliar, and A. Georges, 1992, Phys. Rev. B 46,
1261.
Soven, P., 1967, Phys. Rev. 156, 809.
Subrahmanyam, V., and M. Barma, 1988, J. Phys. C 21, L19.
Tran, M.-T., 1999, Phys. Rev. B 60, 16371.
Velick´y, B., 1969, Phys. Rev. 184, 614.
Velick´y, B., S. Kirkpatrick, and H. Ehrenreich, 1968, Phys.
Rev. 175, 747.
Vojta, M., and R. Bulla, 2002, Phys. Rev. B 65, 014511.
Wada, H., A. Nakamura, A. Mitsuda, M. Shiga, T. Tanaka,
H. Mitamura, and T. Goto, 1997, J. Phys.: Condens. Matter 9, 7913.
Watson, G., and R. Lema´nski, 1995, J. Phys. Conden. Matter
7, 9521.
Wilcox, R. M., 1968, Phys. Rev. 174, 624.
Withoff, D., and E. Fradkin, 1990, Phys. Rev. Lett. 64, 1835.
Zhang, W., N. Sato, K. Yoshimura, A. Mitsuda, T. Goto, and
K. Kosuge, 2002, Phys. Rev. B 66, 024112.
Zlati´c, V., and J. K. Freericks, 2001a, Acta Phys. Pol. B 32,
3253.
Zlati´c, V., and J. K. Freericks, 2001b, Open Problems in
Strongly Correlated Electron Systems (Kluwer, Dordrecht),
volume 15 of Nato Science Series II. Mathematics, Physics,
and Chemistry, p. 371.
Zlati´c, V., and J. K. Freericks, 2003, Concepts in Electron
Correlation (Kluwer, Dordrecht), volume XX of Nato Science Series II. Mathematics, Physics, and Chemistry, p.
XXX.
Zlati´c, V., J. K. Freericks, R. Lema´nski, and G. Czycholl,
2001, Phil. Mag. B 81, 1443.
Zlati´c, V., and B. Horvati´c, 1990, Solid State Commun. 75,
263.


51



mσ (mη) z-component of spin of electrons
2s + 1 number of σ states
t hopping
t [∗] rescaled hopping
v(ǫ) velocity operator
w(x) phonon distribution function
w0 = 1 − w1 empty site density
w1 localized electron (ion) density
xi phonon coordinate at site i
Γ [cc] irreducible charge vertex
∆ superconducting gap at T = 0
Σ self energy
Ωuc unit cell volume
αan anharmonic phonon potential (quartic)
β 1/T
βan anharmonic phonon potential (cubic)
γ(q) parameter in charge susceptibility
η(q) deviation from local susceptibility
ξ0 (ξ [¯] 0) parameters for Fη calculation
κ spring constant
λ(z) dynamical mean field
µ chemical potential, conduction electrons
µB Bohr magneton
µf chemical potential, localized electrons
iνl = iπT 2l bosonic Matsubara frequency
ψ ( ψ [¯] ) fermionic Grassman variable
ρ(ǫ) bare conduction electron DOS
ρdc dc resistivity
ρe itinerant electron density
ρf localized electron density
σ(ν) optical conductivity
σ0 conductivity unit
σdc dc conductivity
τ imaginary time
τσ(ω) relaxation time
χ [′] spin susceptibility
χ [cc] conduction electron charge susceptibility
χ¯ [cc] pair-field susceptibility
χ [cf] mixed charge susceptibility
χ [ff] localized electron charge susceptibility
χhyb hybridization susceptibility
χ0 bare susceptibility
χτ time-dependent conduction electron field
iωn = iπT (2n + 1) fermionic Matsubara frequency
H Hamiltonian
L Lorenz number
Z partition function
