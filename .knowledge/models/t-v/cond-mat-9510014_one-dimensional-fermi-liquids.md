---
source: "https://arxiv.org/abs/cond-mat/9510014"
type: "arxiv"
canonical_id: "cond-mat/9510014"
title: "One-dimensional Fermi liquids"
authors: "J. Voit"
year: "1995"
venue: "Reports on Progress in Physics"
arxiv_id: "cond-mat/9510014"
doi: "10.1088/0034-4885/58/9/002"
full_text: yes
---

# One-dimensional Fermi liquids

**Authors:** J. Voit

**Citation:** Reports on Progress in Physics, vol. 58, pp. 977-1116, 1995

**arXiv:** [cond-mat/9510014](https://arxiv.org/abs/cond-mat/9510014)

**DOI:** [10.1088/0034-4885/58/9/002](https://doi.org/10.1088/0034-4885/58/9/002)

## Abstract

We review the progress in the theory of one-dimensional (ID) Fermi liquids which has occurred over the past decade. The usual Fermi liquid theory, based on a quasi-particle picture, breaks down in one dimension because of the Peierls divergence in the particle-hole bubble, producing anomalous dimensions of operators, and because of charge-spin separation. Both are related to the importance of scattering processes transferring finite momentum. A description of the low-energy properties of gapless 1D quantum systems can be based on the exactly solvable Luttinger model which incorporates these features, and whose correlation functions can be calculated. Special properties of the eigenvalue spectrum, parameterized by one renormalized velocity and one effective coupling constant per degree of freedom, fully describe the physics of this model. Other gapless 1D models share these properties in a low-energy subspace. The concept of a Luttinger liquid implies that their low-energy properties are described by an effective Luttinger model, and constitutes the universality class of these quantum systems. Once the mapping on the Luttinger model is achieved, one has an asymptotically exact solution of the 1D many-body problem. Lattice models identified as Luttinger liquids include the 1D Hubbard model off half-filling, and variants such as the t-J- or the extended Hubbard model. In addition, 1D electron-phonon systems or metals with impurities can be Luttinger liquids, as well as the edge states in the quantum Hall effect.

## Full Text

One-dimensional Fermi liquids
arXiv:cond-mat/9510014v1 29 Sep 1995




                                                                   Johannes Voit

                                              Bayreuther Institut für Makromolekülforschung (BIMF)
                                                            and Theoretische Physik 1
                                                               Universität Bayreuth
                                                          D-95440 Bayreuth (Germany)1

                                                             and Institut Laue-Langevin
                                                             F-38042 Grenoble (France)



                                                   submitted to Reports on Progress in Physics on
                                                                 November 19, 1994

                                                             last revision and update on
                                                                  November 26, 2024




                                       1
                                           Present address
Abstract

We review the progress in the theory of one-dimensional (1D) Fermi liquids which has
occurred over the past decade. The usual Fermi liquid theory based on a quasi-particle
picture, breaks down in one dimension because of the Peierls divergence in the particle-
hole bubble producing anomalous dimensions of operators, and because of charge-spin
separation. Both are related to the importance of scattering processes transferring ﬁnite
momentum. A description of the low-energy properties of gapless one-dimensional quan-
tum systems can be based on the exactly solvable Luttinger model which incorporates
these features, and whose correlation functions can be calculated. Special properties of
the eigenvalue spectrum, parameterized by one renormalized velocity and one eﬀective
coupling constant per degree of freedom fully describe the physics of this model. Other
gapless 1D models share these properties in a low-energy subspace. The concept of a
“Luttinger liquid” implies that their low-energy properties are described by an eﬀective
Luttinger model, and constitutes the universality class of these quantum systems. Once
the mapping on the Luttinger model is achieved, one has an asymptotically exact solution
of the 1D many-body problem. Lattice models identiﬁed as Luttinger liquids include the
1D Hubbard model oﬀ half-ﬁlling, and variants such as the t − J- or the extended Hub-
bard model. Also 1D electron-phonon systems or metals with impurities can be Luttinger
liquids, as well as the edge states in the quantum Hall eﬀect.
    We discuss in detail various solutions of the Luttinger model which emphasize diﬀerent
aspects of the physics of 1D Fermi liquids. Correlation functions are calculated in detail
using bosonization, and the relation of this method to other approaches is discussed. The
correlation functions decay as non-universal power-laws, and scaling relations between
their exponents are parameterized by the eﬀective coupling constant. Charge-spin sepa-
ration only shows up in dynamical correlations. The Luttinger liquid concept is developed
from perturbations of the Luttinger model. Mainly specializing to the 1D Hubbard model,
we review a variety of mappings for complicated models of interacting electrons onto Lut-
tinger models, and thereby obtain their correlation functions. We also discuss the generic
behaviour of systems not falling into the Luttinger liquid universality class because of
gaps in their low-energy spectrum. The Mott transition provides an example for the tran-
sition from Luttinger to non-Luttinger behaviour, and recent results on this problem are
summarized. Coupling chains by interactions or tunneling allows transverse coherence
to establish in the single- or two-particle dynamics, and drives the systems away from a
Luttinger liquid. We discuss the inﬂuence of charge-spin separation and of the anomalous
dimensions on the transverse dynamics of the electrons. The edge states in the quan-

                                            i
tum Hall eﬀect provide a realization of a modiﬁed, chiral Luttinger liquid whose detailed
properties diﬀer from those of the standard model. The article closes with a summary
of experiments which can be interpreted in favour of Luttinger liquid-correlations in the
“normal” state of quasi-1D organic conductors and superconductors, charge density wave
systems, and semiconductors in the quantum Hall regime.




                                           ii
Contents

1 Introduction                                                                             1
  1.1 Motivation . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .   1
  1.2 Purpose and structure of this review . . . . . . . . . . . . . . . . . . . . .       5

2 Fermi liquid theory and its failure in one dimension                                 8
  2.1 The Fermi liquid . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 8
  2.2 Breakdown of Fermi liquid theory in one dimension . . . . . . . . . . . . . 10

3 The Luttinger model                                                                      14
  3.1 Low-energy phenomenology in 1D – the Luttinger model . . . . . . . . . .             14
      3.1.1 Ground state and elementary excitations of 1D fermions . . . . . .             14
      3.1.2 Tomonaga-Luttinger Hamiltonian . . . . . . . . . . . . . . . . . . .           15
      3.1.3 Symmetries and conservation laws . . . . . . . . . . . . . . . . . . .         16
  3.2 Boson solution of the Luttinger model . . . . . . . . . . . . . . . . . . . .        18
      3.2.1 Diagonalization of Hamiltonian . . . . . . . . . . . . . . . . . . . .         19
      3.2.2 Bosonization . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .     24
  3.3 Physical Properties of the Luttinger Model – Thermodynamics and Corre-
      lation Functions . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .   27
      3.3.1 Thermodynamics and transport . . . . . . . . . . . . . . . . . . . .           28
      3.3.2 Single- and two-particle correlation functions . . . . . . . . . . . . .       30
  3.4 Dynamical correlations: the spectral properties of Luttinger liquids . . . .         36
  3.5 Alternative methods . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .      38
      3.5.1 Green function methods . . . . . . . . . . . . . . . . . . . . . . . .         38
      3.5.2 Other bosonic schemes . . . . . . . . . . . . . . . . . . . . . . . . .        42
  3.6 Conformal ﬁeld theory and bosonization . . . . . . . . . . . . . . . . . . .         43
      3.6.1 Conformal invariance at a critical point . . . . . . . . . . . . . . . .       43
      3.6.2 The Gaussian model . . . . . . . . . . . . . . . . . . . . . . . . . .         50

4 The Luttinger Liquid                                                                     56
  4.1 The conjecture . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .     56
  4.2 Luttinger model with nonlinear dispersion – the emergence of higher har-
      monics . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .   58
  4.3 Backward and Umklapp scattering . . . . . . . . . . . . . . . . . . . . . .          59
  4.4 Lattice models: Hubbard & Co. . . . . . . . . . . . . . . . . . . . . . . . .        64


                                             iii
       4.4.1 Models . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .    64
       4.4.2 Bethe Ansatz . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .      65
       4.4.3 Low-energy properties of one-dimensional lattice models . . . . . .           69
   4.5 Electron-phonon interaction and impurity scattering . . . . . . . . . . . . .       82
   4.6 Transport in Luttinger liquids . . . . . . . . . . . . . . . . . . . . . . . . .    86
       4.6.1 Electron-electron scattering . . . . . . . . . . . . . . . . . . . . . .      86
       4.6.2 Electron-impurity scattering . . . . . . . . . . . . . . . . . . . . . .      88
       4.6.3 Electron-phonon scattering . . . . . . . . . . . . . . . . . . . . . . .      94
   4.7 The notion of a Landau-Luttinger liquid . . . . . . . . . . . . . . . . . . .       95

5 Alternatives to the Luttinger liquid: spin gaps, the Mott transition, and
  phase separation                                                                       98
  5.1 Spin gaps . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 98
  5.2 The Mott transition . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 100
  5.3 Phase separation . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 107

6 Extensions of the Luttinger Liquid                                                 109
  6.1 Multi-component models . . . . . . . . . . . . . . . . . . . . . . . . . . . . 110
  6.2 Crossover to higher dimensions . . . . . . . . . . . . . . . . . . . . . . . . 114
  6.3 Edge states in the quantum Hall eﬀect . . . . . . . . . . . . . . . . . . . . 128

7 The normal state of quasi-one-dimensional metals – a Luttinger liquid?134
  7.1 Organic conductors and superconductors . . . . . . . . . . . . . . . . . . . 134
  7.2 Inorganic charge density wave materials . . . . . . . . . . . . . . . . . . . . 138
  7.3 Semiconductor heterostructures . . . . . . . . . . . . . . . . . . . . . . . . 139

8 Summary                                                                                 141




                                            iv
Chapter 1

Introduction

1.1     Motivation
Strongly correlated fermions are an important problem in solid state physics. Over the
last one or two decades, experiments on many classes of materials have provided evidence
that strong correlations are a central ingredient for the understanding of their physical
properties. Among them are the heavy fermion compounds, the high-Tc superconductors,
a variety of intimately related organic metals, superconductors, and insulators, just to
name a few. Also in normal metals, the interactions between the electrons are rather
strong, although the correlations may be much weaker than in the systems mentioned
before. The eﬀective dimension of the electron gas plays an important role in correlating
interacting fermions, and the materials listed are essentially three-(3D), two-(2D), and
one-dimensional (1D), respectively. Correlations are also very important in semiconduc-
tor heterostructures and quantum wires, being two- or one-dimensional, including the
Quantum Hall regime.
    The theoretical description of strongly interacting electrons poses a formidable prob-
lem. Exact solutions of speciﬁc models usually are impossible, exception made for certain
one-dimensional models to be discussed later. Fortunately, such exact solutions are rarely
required (and more rarely even practical) when comparing with experiment. Most mea-
surements, in fact, only probe correlations on energy scales small compared to the Fermi
energy EF so that only the low-energy sector of a given model is of importance. More-
over, only at low energies can we hope to excite only a few degrees of freedom, for which
a meaningful comparison to theoretical predictions can be attempted.
    Correlated fermions in three dimensions are a well studied problem. Their theo-
retical description, by Fermi liquid theory, is approximate but well understood [1, 2].
It becomes an asymptotically exact solution for low energies and small wavevectors
(E → EF , |k| → kF , T → 0). The limitation to low energies is instrumental here
because, together with Fermi statistics, it implies that the phase space for excitations is
severely restricted. In one dimension, there is a variety of exactly solvable models, which
have been known for quite a time, but a deeper understanding of their mutual relation-
ships and their relevance for describing the generic low-energy physics, close to the 1D


                                            1
Fermi surface, has emerged only rather recently. These relations as well as the properties
of such one-dimensional Fermi liquids, or following Haldane “Luttinger liquids” [3], are
the main subjects of this review article. Here we shall use the terms “one-dimensional
Fermi liquids” and “Luttinger liquids” synonymously, although, as we show below, Fermi
liquid behaviour as it is established in 3D is not possible in 1D.
     Fermi liquid theory is based on (but not exhausted by) a picture of quasi-particles
evolving out of the particles (holes) of a Fermi gas upon adiabatically switching on in-
teractions [1, 2]. They are in one-to-one correspondence with the bare particles and,
speciﬁcally, carry the same quantum numbers and obey Fermi-Dirac statistics. The free
Fermi gas thus is the solvable model on which Fermi liquid theory is built. The electron-
electron interaction has three main eﬀects: (i) it renormalizes the kinematic parameters of
the quasi-particles such as the eﬀective mass, and the thermodynamic properties (speciﬁc
heat, susceptibility), described by the Landau parameters Fna,s ; (ii) it gives them a ﬁnite
lifetime diverging, however, as τ ∼ (E −EF )−2 as the Fermi surface is approached, so that
the quasi-particles are robust against small displacements away from EF ; (iii) it introduces
new collective modes. The existence of quasi-particles formally shows up through a ﬁnite
jump zkF of the momentum distribution function n(k) at the Fermi surface, corresponding
to a ﬁnite residue of the quasi-particle pole in the electron’s Green function.
     One-dimensional Fermi liquids are very special in that they retain a Fermi surface
(if deﬁned as the set of points where the momentum distribution or its derivatives have
singularities) enclosing the same k-space volume as that of free fermions, in agreement
with Luttinger’s theorem [4]. However, there are no fermionic quasi-particles, and their
elementary excitations are rather bosonic collective charge and spin ﬂuctuations dispers-
ing with diﬀerent velocities. An incoming electron decays into such charge and spin
excitations which then spatially separate with time (charge-spin separation). The corre-
lations between these excitations are anomalous and show up as interaction-dependent
nonuniversal power-laws in many physical quantities where those of ordinary metals are
characterized by universal (interaction independent) powers.
     To be more speciﬁc, a list of salient properties of such 1D Fermi liquids includes: (i)
a continuous momentum distribution function n(k), varying with as | k − kF |α with an
interaction-dependent exponent α, and a pseudogap in the single-particle density of states
∝| ω |α , consequences of the non-existence of fermionic quasi-particles (the quasi-particle
residue vanishes as zk ∼ |k − kF |α as k → kF ); (ii) similar power-law behaviour in all
correlation functions, speciﬁcally in those for superconducting and spin or charge den-
sity wave ﬂuctuations, with universal scaling relations between the diﬀerent nonuniversal
exponents, which depend only on one eﬀective coupling constant per degree of freedom;
(iii) ﬁnite spin and charge response at small wavevectors, and a ﬁnite Drude weight in
the conductivity; (iv) charge-spin separation; (v) persistent currents quantized in units of
2kF . All these properties can be described in terms of only two eﬀective parameters per
degree of freedom which take over in 1D the role of the Landau parameters familiar from
Fermi liquid theory.
     The reasons for these peculiar properties are found in the very special Fermi surface
topology of 1D fermions producing both singular particle-hole response and severe conser-

                                             2
vation laws. In a 1D chain, one has simply two Fermi “points” ±kF , and the Fermi surface
of an array of chains consists of two parallel sheets (in the absence of interchain hopping).
In both cases, one has perfect nesting, namely one complete Fermi sheet can be trans-
lated onto the other by a single wavevector ±2kF . This produces a singular particle-hole
response at 2kF , the well-known Peierls instability [5]. This type of response is assumed
ﬁnite in Fermi liquid theory but, in 1D, is divergent for repulsive forward scattering (or
attractive backscattering, the case considered by Peierls), leading to a breakdown of the
Fermi liquid description. In addition, we have, as in 3D, the BCS singularity for attrac-
tive interactions [6]. On the other hand, the disjoint Fermi surface gives a well-deﬁned
dispersion, i.e. particle-like character, to the low-energy particle-hole excitations. They
now can be taken as the building blocks upon which to construct a description of the 1D
low-energy physics.
    These properties are generic for one-dimensional Fermi liquids but particularly promi-
nent in a 1D model of interacting fermions proposed by Luttinger [7] and Tomonaga [8]
and solved exactly by Mattis and Lieb [9]. All correlation functions of the Luttinger
model can be computed exactly, so that one has direct access to all physical properties
of interest. The notion of a “Luttinger liquid” was coined by Haldane to describe these
universal low-energy properties of gapless 1D quantum systems, and to emphasize that an
asymptotic (ω → 0, q → 0) description can be based on the Luttinger model in much the
same way as the Fermi liquid theory in 3D is based on the free Fermi gas. The basic ideas
and procedures had been discussed earlier by Efetov and Larkin [10] but passed largely
unnoticed. The name “Tomonaga – Luttinger liquid” might be more appropriate to give
credit to Tomonaga’s important early contribution but has not become widely popular
today.
    Despite this apparently very diﬀerent set of physical properties, there are also sim-
ilarities in the structures of Fermi and Luttinger liquids. Some concepts make these
similarities particularly apparent: conformal ﬁeld theory, where we essentially exploit the
fact that both Fermi and Luttinger liquids (the former in 1D, of course) are critical, in
the language of the theory of phase transitions, and possess the same central charge; a
description of both theories based on Ward identities (i.e. symmetries and conservation
laws), and the notion of a “Landau-Luttinger liquid”, where one formulates a Fermi liquid
picture for the pseudo-particles appearing in the exact Bethe-Ansatz solution of models
like the 1D Hubbard model. Other methods, often more suitable for the practical calcu-
lations required by a solid state physicist, like bosonization, more strongly emphasize the
diﬀerences between Fermi and Luttinger liquids.
    In two dimensions, the applicability of Fermi liquid theory, speciﬁcally to the high-Tc
problem, is quite controversial. In fact, much of the recent interest in Luttinger liquids
is due to Anderson’s observation that the normal state properties of the 2D high-Tc su-
perconductors are strikingly diﬀerent from all known metals and cannot be reconciled
with Fermi-liquid theory; they are more similar to properties of 1D models [11]. An-
derson proposed that the essential physics be contained in the 2D Hubbard model and
suggested a picture of a “tomographic Luttinger liquid” for the ground state and the
low-energy excitations of this model, building on Haldane’s earlier work in 1D, to give

                                             3
a more systematic basis to these conjectured non-Fermi liquid properties of the high-Tc
superconductors. Arguments have been advanced, however, also in favour of Fermi-liquid
physics [12]. In addition a theory somewhat intermediate between Fermi and Luttinger
liquids, a “marginal Fermi liquid” has been proposed [13], where the quasi-particle residue
zk vanishes logarithmically as k → kF . (We parenthetically note that there is no simple
solvable model, like the Fermi gas, or the Luttinger model, onto which one could build the
marginal Fermi liquid phenomenology [13]. Very recent work seems to indicate, however,
that certain impurity models do produce marginal Fermi liquid behaviour [14].)
    While the relevance of Anderson’s ideas is still quite controversial and no unambigu-
ous formal justiﬁcation has been published to date, they have refocussed attention on
1D models as paradigms for the breakdown of Fermi-liquid theory: there are few other
instances where this has been established ﬁrmly. The main progress of the last years, to
be reviewed here, is related to the realization that, in 1D, a variety of models allows es-
sentially exact calculations of the physical properties of “exotic” non-Fermi-liquid metals.
Emphasis has been directed in two main directions. (i) The relation of models deﬁned on a
lattice, such as the 1D Hubbard model, to continuum theories of the Tomonaga-Luttinger
type. There had been a widespread opinion, that the lattice models would be appropriate
to model the limit of strong electron-electron interactions, while the ﬁeld theories would
be better suited for weak-coupling situations. It has now become clear that this is not so,
and that the continuum theories rather are the asymptotic low-energy limits of the lattice
models even at arbitrarily strong coupling. Moreover, this mapping has provided us with
several algorithms to extract the eﬀective parameters of the continuum models from the
(either Bethe Ansatz or numerical) solution of the lattice models. It therefore provides
an asymptotically exact solution to the 1D many-body problem. We now can compute
essentially all correlation functions for lattice models, an impossible task if one wanted to
use the lattice solution directly. (ii) The calculation of physical properties from the now
known correlation function allows to work out the distinctive diﬀerence of such Luttinger
liquids from the predictions of Fermi liquid theory in higher dimensions, so as to get tools
for the diagnosis of non-Fermi liquid behaviour.
    With the general excitement in the community over the spectacular physics of the high-
Tc superconductors, it has been somewhat forgotten that there are many families of organic
and inorganic quasi-1D metals [15, 16] which do deviate strikingly from Fermi-liquid
behaviour (at least from ordinary metals) in their normal state, and undergo a variety of
low-temperature phase transitions into, e. g., charge or spin density wave (CDW/SDW)
insulating phases or even become superconducting. The normal state properties of these
materials are often highly anisotropic and justify application of 1D theory. We therefore
possess a laboratory playground where we can confront theoretical evaluations of the
distinctive properties of such “Luttinger liquids” with experimental reality – in a situation
where the theoretical basis (namely one-dimensionality) is quite ﬁrmly established from
experiment.
    There is thus at least a threefold motivation to study models of 1D interacting elec-
trons: (i) The search for a coherent description of the quasi-1D metals whose “exotic”
properties have been studied over nearly two decades and which continue to be the focus

                                             4
of intense experimental eﬀorts. (ii) 1D models as a paradigm for “metallic” systems which
are not Fermi liquids. The detailed calculations possible here will hopefully sharpen our
understanding of critical requirements for the breakdown of Fermi-liquid theory in gen-
eral, and how such scenarios translate into experimental reality. There are only a few
established examples of non-Fermi liquid metals in higher dimension such as the multi-
channel Kondo problem, but even these reduce, due to the spherical symmetry commonly
assumed, to eﬀective 1D problems [17]. (iii) The possibility of ﬁnding exact solutions to
nontrivial many-body problems.


1.2     Purpose and structure of this review
This article will present a practical introduction to Luttinger liquids. It attempts to
combine a review of the progress of the last couple of years with a self-contained and
pedagogical presentation of the Luttinger model, its solution, and its properties (i.e.
correlation functions) and especially emphasize bosonization as a simple practical means
both to solve the model and to calculate correlation functions. Based on this, we carry on
to the notion of a Luttinger liquid and a discussion of the various methods employed to
map a complicated 1D many-body problem onto the relatively simple Luttinger model.
For all models to be discussed, the emphasis will be on their properties, i.e. correlation
functions, which ultimately can be compared with experiment. I also hope to demonstrate
that the Luttinger liquid often is a useful device if none of the exact nonperturbative
methods to compute correlation exponents works: incorporating all essential features of
the 1D Fermi liquid, it is presumably the best possible starting point for a renormalization
group analysis of the problem at hand.
    On the other hand, we shall be quite schematic concerning the methods used to achieve
an exact solution of the (lattice) models we are interested in, such as the Bethe Ansatz
or numerical diagonalization techniques. We shall be more concerned with the various
methods which have been invented to extract eﬀective Luttinger parameters given a cer-
tain type of solution of the starting models, to compare their virtues and drawbacks
and emphasize their complementarity. Moreover, we do not attempt to present a com-
plete overview of the numerous 1D models used to describe strongly correlated electrons.
Rather, we shall concentrate on a few of them, most often the paradigmatic Hubbard
model. The methods discussed often can be applied without signiﬁcant changes to other
models the reader might be more interested in.
    The ﬁeld of 1D Fermi liquids is not new. Stimulated by and stimulating the research on
quasi-1D organic conductors in the seventies and early eighties, a number of useful review
articles has been available for some time. The meanwhile classical reviews of Sólyom [18]
and Emery [19] contain much material on the use of renormalization group (with respect
to a 1D Fermi gas) to treat the singularities generated perturbatively by the 1D inter-
actions. There is also material on the solution of the Tomonaga-Luttinger model either
by bosonization (in a somewhat approximate but for many purposes suﬃcient form) and
through the use of Ward identities. We are extremely brief on papers duely covered there.


                                             5
Our presentation here will be limited to abelian bosonization. Nonabelian bosonization,
retaining manifestly the SU(2)-invariance in the spin sector, is reviewed by Aﬄeck [20].
Firsov, Prigodin, and Seidel [21] and Bourbonnais and Caron [22] more strongly emphasize
phase transitions in real materials made of coupled 1D chains, and especially the paper by
Bourbonnais and Caron gives a very modern presentation combining functional integral
representations with renormalization group. A classical review on the earlier work on
organic conductors is by Jérôme and Schulz [15] and the more recent developments have
been summarized by Jérôme [23] and Williams et al. [24]. A pedagogical overview of both
experimental and theoretical aspects can be found in the Proceedings of the 1986 NATO-
ASI in Magog (Canada) [25] while the latest progress on organic materials is collected in
the Proceedings of the biannual Synthetic Metals conferences [16]. Some subjects do not
receive due coverage in this article: concerning the Bethe Ansatz, there are reviews by
Sutherland [26], Korepin et al. [27], and Izyumov and Skryabin [28], and there is also a
vast literature on conformal ﬁeld theory [29]. Other problems of high current interest, and
intimately related to our subject, could not be included for restrictions in space and time:
spin chains, which can be related by a variety of methods to 1D interacting fermions;
all developments starting from the Calogero-Sutherland model; one-dimensional bosons;
persistent currents in mesoscopic rings, where interesting contributions originate from the
study of 1D fermions despite the 3D spherical Fermi surface in the real materials, and
many more. We hope that others take up the challenge to review these active areas.
    This article is structured as follows. Chapter 2 will complement this brief introduction
in that it discusses the breakdown of the Fermi liquid on a more technical level and
identiﬁes the relevant features of one-dimensionality. Speciﬁcally we show (i) how the
Peierls divergence produces an instability of the 1D Fermi gas in the presence of repulsive
interactions, (ii) how the breakdown of a quasi-particle picture can be seen in a second-
order perturbation calculation, and (iii) where Landau’s derivation of a transport equation
crashes in 1D.
    Chapter 3 will present a detailed discussion of the Luttinger model from various angles.
In Section 3.1, we argue that a universal low-energy description of 1D Fermi liquids
can be based on this model. We deﬁne the Hamiltonian and discuss its symmetries
and conservation laws which are essential for all solutions. In Section 3.2.1, we give a
solution using a boson representation of the Hamiltonian, before constructing an explicit
operator identity between fermions and these bosons in Section 3.2.2. This representation
is fruitfully employed in Section 3.3 for a calculation of the Luttinger model correlation
functions. The manifestation of charge-spin separation in dynamical correlations is the
subject of Section 3.4. An alternative method of solution based on the equations of motion
of the Green functions, and on Ward identities, is presented in Section 3.5. Another
alternative for constructing a boson representation of the fermions, conformal ﬁeld theory,
is introduced in Section 3.6 and shown to be fully equivalent to the operator approach of
the earlier sections.
    The Luttinger model is based on very strong restrictions on the dispersion and inter-
action of the particles. In Chapter 4 we shall pass beyond these restrictions and show
that the Luttinger physics still is conserved in a low-energy subspace of more realistic

                                             6
models. This is conjectured in Section 4.1, and then case studies are presented to its
support. With nonlinear band dispersion (Section 4.2), the fermion operators acquire
higher harmonics in kF . Large-momentum transfer scattering in (Section 4.3) lifts unre-
alistic degeneracies of Luttinger model correlation functions by logarithmic corrections.
The correlations of various lattice models are evaluated in Section 4.4. Electron-phonon
systems or dirty 1D metals can also have Luttinger liquid correlations, and we touch upon
these problems in Section 4.5. Section 4.6 shows that rich transport phenomena occur as
one goes away from the simple Luttinger model. Finally, in Section 4.7, we show that the
low-energy physics of the 1D Hubbard model is determined by low-energy excitations in
the charge-momentum- and spin-rapidity-distribution functions, and that in each sector,
one can therefore formulate a Fermi-liquid theory for its excitations.
    Not all 1D systems are Luttinger liquids. In some cases, there are gaps in either the
charge or spin excitation spectra, and phase separation can occur (at least in models).
Chapter 5 discusses these cases. We expand especially on the Mott transition in Section
5.2 which has been studied in considerable detail during the past years.
    In Chapter 6, we go beyond the framework of the Luttinger liquid outlined before.
We discuss multi-band models in Section 6.1. An important issue has been the crossover
from the 1D Luttinger liquid to higher-dimensional behaviour. We elaborate on this
problem in Section 6.2. Finally, we describe the modelling of edge excitations supporting
the transport in the quantum Hall eﬀect in terms of a chiral Luttinger liquid in Section
6.3. While the general features are similar to the standard Luttinger liquid, the edge
excitations have irrational charges and constitute a new universality class, described by a
conformal ﬁeld theory with central charge c 6= 1.
    This review closes with a summary of experiments which provide (often controver-
sial) evidence for Luttinger liquid correlations in several classes of materials. We discuss
organic conductors and superconductors, inorganic charge density wave systems, and
semiconductors in the quantum Hall regime.
    The general approach chosen here is to give some space to the discussion of the basic
methods used in this ﬁeld in the last decade and to some selected examples. This nec-
essarily requires selection, often biased by the author’s prejudices, and many important
papers are discussed only brieﬂy. It is hoped that the general discussion will give tools,
and that the overview on the current status give orientation to the reader to locate and
appreciate the original articles relevant to him. Although I have tried to incorporate a
maximum of the published literature available to me, space restrictions did not allow to
do so systematically. I apologize to all those whose contributions have not received due
coverage.




                                             7
Chapter 2

Fermi liquid theory and its failure in
one dimension

2.1      The Fermi liquid
Macroscopic properties of ordinary (3D) metals can be described remarkably well by the
model of a Fermi gas although the interactions are not weak. Why is this possible? The
answer is provided by Landau’s theory of the Fermi liquid [1, 2].
    The key observation is that macroscopic properties involve only excitations of the
system on energy scales (say temperatures) small compared to the Fermi energy. The state
of the system can be speciﬁed in terms of its ground state, i.e. its Fermi surface, and its
low-lying elementary excitations – a rariﬁed gas of “quasi-particles”. These quasi-particles
evolve continuously out of the states of a free Fermi gas when interactions are switched
on adiabatically, and are in one-to-one correspondence with the bare particles (adiabatic
continuity). They possess the same quantum numbers as the original particles, but their
dynamical properties are renormalized by the interactions. This scenario emerges because
the phase space for scattering of particles is severly restricted by Fermi statistics: at low
temperatures, most particles are frozen inside the Fermi sea, and only a fraction T /TF ≪ 1
participate in the scattering processes. Apart those originating from the requirement of
stability there are, however, no restrictions on the magnitude of the eﬀective interactions
between the quasi-particles, as measured by the Landau parameters. The restriction to
low-lying excitations implying low densities of excitations, and Fermi statistics are enough
to ensure Fermi liquid properties.
    The ground state of a gas of free particles is fully described by its momentum distribu-
tion function n0 (k). For the interacting system, it can be speciﬁed by the quasi-particle
distribution function which is the same as that of the bare particles in the free system.
Excitations are then determined by the deviations they produce in the momentum dis-
tribution with respect to the ground state, δn(k) = n(k) − n0 (k). So long as there are
few excitations, δn(k) is small. The change in energy δE associated with quasi-particle




                                             8
excitations can then be expanded in powers of δn(k)
                                                1X
                                                       δn(k)f (k, k′ )δn(k′ ) + . . . ,
                     X
              δE =       [ε0 (k) − µ] δn(k) +                                             (2.1)
                     k                          2 k,k′

where f (k, k′ ) is the quasi-particle interaction and µ is the chemical potential. Although
the single-particle term is of ﬁrst order in δn(k) and the interaction term of second order,
they are in fact of equal importance and the second term cannot be neglected: the notion
of a quasi-particle making sense only in the neighbourhood of the Fermi surface, ε0 (k) − µ
is small there and of the same sign as δn(k).
    On a more formal level, the Green function of an electron is
                                                    1
                              G(k, ω) =                        ,                          (2.2)
                                          ε0 (k) − ω − Σ(k, ω)
where ε0 (k) is the bare dispersion and Σ(k, ω) is the self-energy containing all the many-
body eﬀects. The poles of the Green functions give the single-particle excitation energies,
and the imaginary part of the self-energy provides the damping of these excitations.
Σ(k, ω) is, for ﬁxed k, a smooth function of ω and continuous in k. This guarantees
solutions to the equation
                                 ε0 (k) − ω − Σ(k, ω) = 0 ,                            (2.3)
determining the single particle excitation energies. One hopes that there is only a single
solution to this equation – but this need not be so. In fact, having a single solution – the
quasi-particle pole with ﬁnite residue [4]
                                                         !−1
                                      ∂ReΣ(k, ω)
                             zk = 1 −                              ≤1                     (2.4)
                                         ∂ω               ω=ε(k)

– implies a normal Fermi liquid. We shall see below that the the breakdown of Fermi liquid
theory in 1D is signalled by the appearance of multiple solutions or vanishing of zk . The
quasi-particle residue zkF gives the magnitude of the jump of the momentum distribution
function of the bare particles at the Fermi surface [4]. Expanding the self-energy to second
order, the Green function close to the Fermi surface becomes
                                                        zk
      G(k, ω) = Ginc (k, ω) +                                                      .    (2.5)
                                ω − v(|k| − kF ) + i u sign(|k| − kF )(|k| − kF )2
There is no damping of the quasi-particles at the Fermi surface. They will exist oﬀ the
Fermi surface only to the extent that their damping is suﬃciently small (their lifetime
long enough) to make them behave like an eigenstate over a reasonably long time scale.
Damping of a quasi-particle with energy ω is provided by complex conﬁgurations of quasi-
particle–quasi-hole excitations. They also produce incoherent background ImGinc (ω) in
the spectral function which, interfering with the coherent part, gives ImG(ω) ∝ ω 2 for
ω → 0 at ﬁnite k. Eq. (2.5) is to be compared to the 1D Green functions derived
in Chapter 3.3, and to that of the marginal Fermi liquid whose quasi-particle residue
vanishes as [13]
                        zk ∼ −1/ ln | ε(k) | for ε(k) → µ = 0 .                    (2.6)

                                                 9
    The quasi-particle is the central concept in the theory of the Fermi liquid. From
the quasi-particle picture, Landau derived, in his ﬁrst paper, a Boltzmann-like transport
equation for the Fermi liquid [1]. To this end, one assumes that spatially inhomogeneous
excitations in the system take place on a macroscopic scale only, so that the wavevector k
remains a good quantum number at least within a volume of macroscopic size. One can
then deﬁne a local distribution function δn(k, r). The time evolution of this distribution
is then given by
      ∂δn(k, r)
                                                 f (k, k′ )vk · ∇δn(k′ , r) = I[n] ,
                                             X
                + vk · ∇δn(k, r) + δ(εk − µ)                                           (2.7)
         ∂t                                  k ′



where I[n], the collision term, is a functional of n(k, r) and the velocity vk = ∇k ε(k).
Since δn and δ(εk − µ) appear, it is clear that this equation applies only close to the
Fermi surface. Notice that the assumption of variation of n(k, r) over macroscopic length
scales implies coarse graining any underlying microscopic theory over length scales at
least of the order of the thermal de Broglie length ξ ∼ vF /πT . ξ measures the length
over which the quasi-particles loose their phase coherence. Moreover, due to the collision
term, (2.7) contains dissipation, produced by the elimination of degrees of freedom in the
coarse graining process.
    Subsequently however, Landau was able to derive the same equation from the general
formalism of many-body theory without making reference to the quasi-particle picture [1],
and one could conceive generalizations of the Fermi liquid theory based on this equation.
For the one-dimensional Fermi liquid, however, the analogon of the Landau-Boltzmann
transport equation has not yet been derived, and the usual derivation fails in 1D. In the
remainder of this article, we shall base our notion of a Fermi liquid on the quasi-particle
picture.


2.2      Breakdown of Fermi liquid theory in one dimen-
         sion
Adiabatic continuity is, a priori, a hypothesis which needs veriﬁcation: while it works
for repulsive interactions in 3D, it cannot be justiﬁed for attractive interactions where a
transition to superconductivity takes place – but neither can it be justiﬁed for repulsive
interactions in 1D, the case of highest interest in the present article. Here, we discuss
where Fermi liquid theory breaks down in 1D. The ﬁrst discussion is rather qualitative and
handwaving. A second one computes the perturbation corrections in the Green function
of a 1D Fermi gas due to some interactions and therefore probes quasi-particles. The
third part ﬁnally indicates where the derivation of Landau’s quasi-particle interactions
and transport equation breaks down and suggests that also the latter will have a new
shape in 1D.
    On the microscopic level, the central problem in the theory of 1D interacting electrons
is the Peierls instability [5], Figure 2.1: 1D electrons spontaneously open a gap at the
Fermi surface when they are coupled adiabatically to phonons with wave vector 2kF . The

                                              10
mechanism operates, however, also for electron-electron interactions. The particle-hole
susceptibility in Figure 2.1 diverges as ln[max(vF q, ω)] if momentum 2kF +q and frequency
ω are transferred through the bubble. Its origin is the nesting property of the 1D Fermi
surface: one piece of the Fermi surface can be matched identically onto the other by a
“translation” with Q = ±2kF . (In higher dimensions, in the generic case, a given 2kF only
matches two points – a Fermi surface part of measure zero.) Summing up a particle-hole
ladder, i.e. doing a mean-ﬁeld theory, one would predict a (charge or spin) density wave
instability at some ﬁnite temperature for repulsive interactions – implying that there can
be no Fermi liquid in 1D. The ﬁnite transition temperature is, of course, unphysical and an
artefact of mean-ﬁeld theory. It is removed by realizing that, since the Peierls channel is as
divergent as the Cooper pairing channel, both types of instabilities interfere and one has
to solve at least a “parquet” of diagrams [30]. The Peierls–Cooper interference conveys a
marked non-mean-ﬁeld character to this problem: mean-ﬁeld theories are constructed by
selecting one important series of diagrams. Here two of them interfere and compete! The
1D Fermi gas is inherently unstable towards any ﬁnite interaction, suggesting that it is
not a good point of departure for analyzing interacting electrons in 1D. (Notwithstanding
this statement, much progress in our understanding of 1D fermions is due perturbing the
1D Fermi gas by electron-electron interaction [18].) There is thus urgent need for new
low-energy phenomenology, similar in spirit to the Fermi liquid picture, but adapted to
the speciﬁc problems of 1D electrons.
    The breakdown of Fermi liquid theory in 1D is also visible in a second order pertur-
bation calculation, as we will demonstrate now. We consider a simpliﬁed problem of 1D
electrons with a density-density interaction parameterized by a coupling constant g. We
calculate the self-energy Σrs (q, ω) in Eq. (2.2) in second order perturbation theory. The
relevant diagrams are shown in Figure 2.2. Anticipating on the next Chapters, we limit
ourselves to (forward) scattering processes transferring only small momentum q ≪ kF ,
and discuss the relevant processes separately in order to avoid obscuring interferences.
All arguments are robust, however.
    We start with the process where all scattering partners are on the same side r = ± of
the Fermi surface, to be called g4 hereafter [the Hamiltonian is written out in Eq. (3.4)].
So long as g4 is independent of momentum transfer, Hartree and Fock terms will cancel
each other for scattering partners having the same spin. If they have opposite spin (g4⊥ ),
(b) and (d) are absent, and (a) only renormalizes the chemical potential. The self-energy
(c) can be calculated and injected into (2.2). The pole of the Green function should give
the energy for quasi-particle excitations, but here we obtain two solutions
                                                  !
                                       g4⊥
                            ω = vF ± | √ | (rk − kF ) !!!                               (2.8)
                                        8π
This violates the single-pole assumption at the origin of the Fermi liquid. Anticipating
Chapter 3 the meaning of the two poles is clear: charge-spin separation. The two poles
are not converged into a single pole by higher order terms, which generate more and more
poles around the two found in Eq. (2.8) and ﬁnally merge into a branch cut, giving this
model the speciﬁc spectral features discussed in detail in Section 3.4.

                                             11
    We now turn to forward scattering where both partners are on opposite sides of the
Fermi surface [labelled g2 hereafter, cf. Eq. (3.3)]. We drop spin indices since one has
only the Hartree diagrams (a) (renormalizing again the chemical potential) and (c) both
for g2k and g2⊥ . Diagram (c) contains a counterpropagating electron-hole pair at ±kF .
This is precisely the Peierls bubble from Fig. 2.1 which gives a logarithmic dependence to
Σ(k, ω). The pole in the Green function (2.2) now has a residue zk ∼ −1/ ln |rk − kF | → 0
as k → kF . Any quasi-particle character of the excitation fades away as we approach the
Fermi surface! Again, higher order terms cannot restore the quasi-particle pole. They
produce higher powers of the logarithm which sum up to a power law. These ubiquitous
power laws have been mentioned in the Introduction and will be discussed in more detail
in Chapter 3.
    A complete and rigorous microscopic justiﬁcation of the Landau theory can be given
[2]. Here, we limit ourselves to a sketch of where these arguments break down in 1D. The
quasi-particle interaction f (k, k ′ ) deﬁned via Landau’s expansion of the total energy (2.1)
is related through

                      f (k, k ′ ) = 2πizk zk′ lim lim Γ(k, EF , k ′ , EF ; q, ω)         (2.9)
                                             ω→0 q→0


to the complete particle-hole interaction vertex Γ(k, E, k ′, E ′ ; q, ω). Notice that no mo-
mentum transfer is involved in the quasi-particle interaction. The complete particle-hole
interaction Γ is related to the irreducible one I by the Bethe-Salpeter equation which we
only display graphically in Figure 2.3. Singularities in Γ are required for eventually desta-
bilizing quasi-particles (Γ determines the two-particle Green function which is coupled,
via the interaction, into the single-particle Green function). So long as I is nonsingular,
singular Γ can only arise from the internal Green functions in the right diagram in Figure
2.3. Physically, they represent that part of the eﬀective interaction which is mediated
by propagating particles. There are, in fact, such singularities when the diﬀerence of
(four-)momenta on the internal lines tends to zero. Due to the particular limit involved
in Eq. (2.9), the quasi-particle interaction is not sensitive to these singularities and re-
mains regular. The singularities matter, however, in opposite (forward scattering) limit
ω = 0, q → 0 when momentum transfer is allowed. Then collective (zero sound) modes
can be excited. Their velocity, however, exceeds the Fermi velocity so that they do not
interfere with the quasi-particles.
    Now consider one dimension. As we have seen in Figure 2.1 above there is a logarithmic
singularity in the (Peierls) particle-hole susceptibility at q = 2kF . It is clear from Figure
2.3 that the Peierls bubble gives an additional divergence in the Bethe-Salpeter equation
when the momentum of the internal Green functions diﬀers by 2kF whereas the derivation
of Landau theory assumes this vertex to be ﬁnite at 2kF . Moreover, the Peierls divergence
is worse than that at q = 0 in that the internal momentum integrals sample the full
bandwidth; at small q, the pole structure of the singular part is such that one only
integrates over a slice of width q. This is why the singularity does not enter the quasi-
particle interaction. The two-particle Green function then carries the singularity in Γ into
the single-particle Green function where it will ruin the quasi-particle pole.

                                                 12
    The quasi-particle interaction f (k, k ′ ) in (2.9) does not involve momentum transfer
between the quasi-particles. In other words, the components of the interaction which
do transfer momentum are irrelevant in 3D. This is very diﬀerent from 1D where, on
dimensional grounds, these interactions are marginal and cannot be neglected compared
to those which do not transfer momentum. This ﬁnally generates charge-spin separation.
We shall give a more detailed argument in the next chapter, at the end of Section 3.1.3,
after we have introduced the relevant Hamiltonian. A reduction of the interactions to an
eﬀective quasi-particle interaction (2.9) cannot be operated in 1D.
    Any search for an extension or a replacement of Fermi liquid theory in 1D must neces-
sarily incorporate in a consistent manner the Peierls divergence and momentum transfer
in the interaction process. This is what the Luttinger liquid approach, to be discussed
in the next chapter, does. A valid though less satisfactory alternative, starting from a
1D Fermi gas, is oﬀered by either solving parquet equations or performing renormaliza-
tion group as “devices” to sum up consistently the oﬀending divergences discussed here
[18, 30].




                                           13
Chapter 3

The Luttinger model

3.1      Low-energy phenomenology in 1D – the Luttinger
         model
3.1.1     Ground state and elementary excitations of 1D fermions
We have seen in the previous chapters that both the Peierls singularity and charge-spin
separation, both related to the small phase space in 1D, spoil a Fermi liquid description
of 1D correlated fermions and require new approaches. On the other hand, the rewarding
feature of 1D physics is that the particle-hole excitations acquire well-deﬁned particle-
like dispersion in the long-wavelength limit q → 0, Figure 3.1. These collective density
ﬂuctuations obey approximately bosonic commutation relations and can indeed be used
to construct the new low-energy phenomenology called for.
    To describe the low-energy physics, we need to know the ground state and the ele-
mentary excitations. Consider a system with N0 electrons in a system of length L. In the
absence of external ﬁelds, the ground state of the free system is the Fermi sea |F Si with
kF = N0 π/2L. In general, the ground state may be diﬀerent, however. In a magnetic
ﬁeld, the number of up- and down-spins, is diﬀerent, kF ↑ 6= kF ↓, and in an electric ﬁeld,
                                                                  (+)       (−)
the number of right- and left-moving fermions is diﬀerent, kF 6= −kF , producing a net
magnetization and current, respectively. Varying the chemical potential changes all four
kF . With respect to the reference state given by kF , one can therefore introduce four
numbers Nr,s measuring the addition or removal of fermions, above or below the reference
kF , in the channel (r, s), where r labels the dispersion branch close to rkF and s the spin.
The total charge and spin as well as charge and spin currents with respect to the reference
state are obtained by linear combination.
    What are the elementary excitations? For the free system, one could add a fermion
in a k-state with |k| > kF and create a quasi-particle. However, we have seen in the
preceding chapter that these quasi-particles are not stable against turning on interactions.
Next consider particle-hole excitations c†k+q ck |F Si, Fig. 3.1 (left). Firstly, notice that the
electron and hole created travel at the same group velocity and therefore form an almost
bound state which is certainly extremely susceptible to interactions, particularly in 1D.


                                               14
Secondly, for small q where the dispersion is almost linear, there is a huge degeneracy
L|q|/2π of these excitations with energy ω(q). We can form “particles”, corresponding to
the linear dispersion branch ω(q) ∝ |q| for q → 0 in Fig. 3.1, by coherently superposing
particle-hole excitations with diﬀerent k, Eq. (3.5) below. These ﬂuctuations are also
present in the Fermi liquid but there, the low-energy spectral region (ω < vF kF , 0 <
q < 2kF ) is ﬁlled in. The presence of these ﬁnite-q low-energy states allows the decay of
these excitations into their constituent quasi-particles and therefore is responsible for a
kind of “chemical” equilibrium between quasi-particles and collective excitations. In 1D
this decay into quasi-particles is not possible and makes these charge- (spin-) ﬂuctuations
stable elementary excitations of the system. They have bosonic commutation properties.
    With respect to our reference state |F Si, there are thus two types of elementary exci-
tations: (i) the charge and spin and their corresponding current excitations which change
                          (r)
the Fermi wavevectors kF,s and thus the number of fermions in the system [3], and (ii)
the collective bosonic charge and spin-density ﬂuctuations. There are no stable quasi-
particles, and the addition of a fermion generates both types of elementary excitations,
cf. Eq. (3.41) below.
    These features are generic to 1D gapless quantum systems but are particularly promi-
nent in the exactly solvable Luttinger model. In the following, we describe and solve this
model before we turn, in the next chapter, to the reduction of microscopic lattice models
(e.g. Hubbard model) onto eﬀective Luttinger Hamiltonians.


3.1.2    Tomonaga-Luttinger Hamiltonian
The Tomonaga-Luttinger model describes 1D right- and left-moving fermions through the
Hamiltonian [3], [7] -[9], [31]-[35]

             H = H0 + H2 + H4 ,                                                                          (3.1)
                              vF (rk − kF ) : c†rks crks : ,
                      X
            H0 =                                                                                         (3.2)
                      r,k,s
                      1 Xh                                 i
            H2 =               g2k (p)δs,s′ + g2⊥ (p)δs,−s′ ρ+,s (p)ρ−,s′ (−p) ,                         (3.3)
                      L p,s,s′
                       1 X h                                  i
            H4 =                  g4k (p)δs,s′ + g4⊥ (p)δs,−s′ : ρr,s (p)ρr,s′ (−p) :                .   (3.4)
                      2L r,p,s,s′

crks describes fermions with momentum k and spin s on the two branches (r = ±) of the
dispersion varying linearly [εr (k) = vF (rk − kF )] about the two Fermi points ±kF .
                                                      X †                                           
                               : c†r,k+p,scr,k,s :=         cr,k+p,scr,k,s − δq,0 hc†r,k,scr,k,si0
                          X
             ρr,s (p) =                                                                                  (3.5)
                          k                           k

is the density ﬂuctuation operator (describing the “particles” introduced above), and
: . . . : denotes normal ordering, deﬁned by the second equality. The Tomonaga and
Luttinger models are distinguished by diﬀerent cutoﬀ prescriptions on the dispersion. In
the Tomonaga model [8] there is a ﬁnite bandwidth cutoﬀ k0 , i.e. the allowed k-space
states for branch r are rkF − k0 < k < rkF + k0. This simulates the ﬁnite bandwidth of all

                                                       15
real physical systems but, unfortunately, only allows an asymptotically exact solution. In
the Luttinger model [7], on the contrary, the dispersion extents to inﬁnity: −∞ < k < ∞
for both branches. In order to obtain physically meaningful results, all the negative energy
states have to be occupied. The presence of these unphysical states is not expected to
aﬀect the low-energy physics of the model (|ω| ≪ EF , |q| ≪ kF ). (A thorough discussion
of various cutoﬀ procedures is given by Sólyom [18] and Apostol [36].) The normal ordering
convention in Eqs. (3.2) and (3.5) is necessary to avoid reference to the inﬁnite quantity
P †
   k hcrks crks i, the total particle number, which is ill-deﬁned. The coupling constants g2
and g4 measure the strength of forward scattering (momentum transfer |q| ≪ kF ) between
particles on diﬀerent or on the same branch of the dispersion, respectively, Figure 3.2.
They may depend on the relative orientation of the spin of the scattering particles. The
interaction terms with p = 0 give the change in Hartree-Fock energy of the system upon
addition of particles, and those with ﬁnite p describe the scattering of the elementary
excitations.
     An exact solution of the Luttinger model is possible [3, 9, 31, 34] if a cutoﬀ Λ is
imposed on the momentum transfer of the interactions [3, 31]. The coupling “constants”
gi (p) therefore depend on the momentum transfer (below, we shall exhibit explicitly this
momentum dependence only where necessary).


3.1.3     Symmetries and conservation laws
The possibility for an exact solution of the Luttinger model can be traced back to severe
conservation laws. The Hamiltonian not only conserves the total charge and spin of the
system
                             [Nρ , H] = 0 ,       [Nσ , H] = 0                      (3.6)
but is does so separately on each branch r

                [Nr,ρ , H] = 0 ,     [Nr,σ , H] = 0 ,      or [Nr,s , H] = 0 .         (3.7)

Clearly, this implies conservation of the charge and spin currents

                   [Jρ , H] = 0 ,     [Jσ , H] = 0 ,      or [Js , H] = 0 .            (3.8)

Consequently, the Hamiltonian is invariant under the gauge transformations

                                    Ψrs (x) → exp(iθr )Ψrs (x)                         (3.9)

for each branch separately. Expressed diﬀerently, the Luttinger model possesses, in addi-
tion to the usual gauge symmetry Ψrs (x) → exp(iθ)Ψrs (x), a chiral symmetry

                                   Ψrs (x) → exp(irθ)Ψrs (x) .                       (3.10)

The physical origin of these conservation laws is the restriction of the interaction Hamil-
tonian H2 + H4 to small momentum transfer (forward) scattering: processes scattering
particles across the Fermi surface are excluded from the model.

                                               16
   For speciﬁc values of the interaction constants

                              g2,k = g2,⊥ and g4,k = g4,⊥ ,                           (3.11)

the Hamiltonian is invariant under a spin-rotation
                                            X
                                Ψrs (x) →        gss′ Ψrs′ (x) ,                      (3.12)
                                            s′

where gss′ = (exp[iΩ·σ])ss′ is a SU(2)-matrix. As will be seen below, correlation functions
are spin-rotation invariant also when only the left equation in (3.11) is fulﬁlled.
    The linear dispersion and the normal ordering involved in the density operators (3.5)
makes the model charge-conjugation symmetric [Ψrs (x) → Ψ†rs (x)]. While a more com-
plete model need not be charge conjugation symmetric, linearizing the dispersion amounts
to a constant-density-of-states approximation – often employed also in higher-dimensional
systems. Finally, when g2,s,s′ = g4,s,s′ the Luttinger model can be considered as the small
momentum transfer limit of a physical Hamiltonian involving only density-density inter-
actions.
    Conservation of total charge and spin applies to most models commonly studied. Their
conservation separately on each branch is, however, a speciﬁc property of the Luttinger
model and not shared by more realistic 1D models. There, it holds in a low-energy
subspace if interaction terms not commuting with the charge and spin currents are irrel-
evant. If they are relevant, the low-energy physics is characterized by diﬀerent (possibly
reduced) symmetries and cannot be described by an eﬀective Luttinger model. Two such
interaction processes are depicted in Figure 3.3. g1⊥ describes exchange scattering across
the Fermi surface and spoils spin current conservation but respects charge current con-
servation. g3⊥ is Umklapp scattering of two particles in the same direction across the
Fermi surface and destroys charge current conservation while conserving the spin current.
However, momentum conservation usually inactivates g3⊥ , except for commensurate band
ﬁllings. Other interaction processes violating both charge and spin current conservation
are possible, too.
    Charge conjugation and spin rotation occur as separate symmetries because of the
interactions. The free Hamiltonian has a higher symmetry which, however, is broken
by the interaction terms. The g2 -interaction does not commute with the kinetic energy
[H2 , H0 ] 6= 0. It therefore can modify the ground state by exciting particle-hole pairs out
of the Fermi sea. On the other hand, g4 commutes [H4 , H0 ] = 0. With this term alone
the Fermi sea remains the ground state. Its inﬂuence is limited to removing degeneracies
in the excitations, as can a magnetic ﬁeld or a hopping matrix element between chains.
    The corresponding interactions are present also in higher dimensions. Still, it seems
that they play no role there. The reason is that these interactions are marginal or scale
invariant in 1D, in a renormalization group sense, while they are irrelevant in D > 1
and drop out of the problem. Marginality means that the coupling constant does not
change under a change in the length (or energy) scale while relevance or irrelevance
imply an increase resp. decrease of the coupling constant as the length (energy) scale is
increased (decreased). The marginality of g2 and g4 can be seen by simple power counting.

                                             17
Taking the length scale to have canonical dimension [L] = 1, the Hamiltonian has [H] =
−1, the fermion operator has [Ψr (x)] = −1/2 and the density operator [ρr (x)] = −1.
Consequently [g2 ] = [g4 ] = 0 i.e. g2 and g4 do not change with scale. The dimension of
Ψr (x) can be changed by the presence of marginal operators of g2 -type but not by those of
g4 -type. The dimension of ρr (x) is not changed by marginal interactions. Notice that the
coupling constants gi transfer momentum in the scattering process, and their marginality
implies that this momentum transfer cannot be neglected on any length (energy) scale.
In contrast, the momentum transfer of interactions in 3D can be neglected because the
interaction is irrelevant (the explicit prefactor L−3 in Hint gives it a dimension −2).
     To see the consequences of this marginality, and in particular of g4 , inject a particle
into the second empty plane wave state above the Fermi surface |ϕ1 i = c†kF +4π/L,s |F Si.
Where can it be transferred by H4 which conserves the energy? The only allowed process
relaxes it into the ﬁrst empty state above the Fermi surface and excites the last particle
from the Fermi sea to the same empty state: |ϕ2 i = H4 |ϕ1 i = c†kF +2π/L,−s ckF ,−s c†kF +2π/L,s
|F Si. Now, within this two-state subsystem {|ϕ1i, |ϕ2 i}, the Hamiltonian reduces to the
matrix                                                    !
                                        4vF π/L 2g4⊥ /L
                               H=                             .                           (3.13)
                                        2g4⊥ /L 4vF π/L
The diagonal terms come from the kinetic energy, and the 1/L-factor comes in from
the quantization of the k-vectors, and the oﬀ-diagonal interaction terms are proportional
to 1/L because of the explicit normalization factor in the Hamiltonian H4 . Interaction
and kinetic energy both scale with 1/L and are of equal importance! Carrying through
the same argument in 3D, the kinetic terms will continue to scale with 1/L while the
interaction terms scale with 1/L3 and therefore can safely be neglected at ﬁnite momentum
transfer [37]. The new eigenvalues are (4π/L)(vF ± g4⊥ /2π) suggesting that the particles
have split into two objects propagating at two diﬀerent renormalized velocities vρ,σ =
vF ± g4⊥ /2π – charge-spin separation.
    The argument continues to hold as one injects the particles at higher momenta 2nπ/L
where H4 couples it to n − 1 other states of lower energy. It also carries over to the g2 -
interaction. Due to the non-conservation of energy, however, an inﬁnite number of states
are coupled to the particle at any momentum. Momentum transfer scattering, therefore,
can never be neglected in 1D, and a reduction to a quasi-particle interaction (2.9) cannot
be justiﬁed in any circumstances. The marginality of forward scattering with ﬁnite mo-
mentum transfer in 1D is at the origin both of the anomalous correlation exponents and
charge-spin separation which we shall discuss in more detail in the subsequent sections.
It is the important diﬀerence to higher-dimensional systems.


3.2      Boson solution of the Luttinger model
A variety of solutions for the Luttinger model have been produced in the past. Histori-
cally, the ﬁrst solution involved a boson representation of the Hamiltonian [9] and will be
reviewed ﬁrst. This solution was “completed” by the construction of a boson representa-


                                               18
tion for the fermion operators [32, 33] which has been made rigorous by Haldane [3] and
Heidenreich et al. [31]. It emphasizes the diﬀerences between Fermi liquids in one and in
higher dimensions. Methods developed in Fermi liquid theory, more strongly emphasizing
similarities between 1D and 3D Fermi liquids, have also been used to solve the Luttinger
model [34, 35] and are reviewed in Section 3.5.


3.2.1     Diagonalization of Hamiltonian
The Tomonaga-Luttinger model (3.1), (although using Luttinger’s version with inﬁnite
bands and a momentum transfer cutoﬀ in the interactions throughout, we shall often
attach Tomonaga’s name to the model, too) describes excitations with respect to a ground
state described by the Fermi wave vector kF = (π/2)(N0/L) where N0 is the number of
physical electrons in a chain of length L. Due to the unphysical negative energy states,
N0 6= rks hc†rks crks i0 ; the left-hand side of this equation is ﬁnite, the right-hand side is
       P

inﬁnite. The inﬁnitely extended dispersion introduces many more subtleties into the model
which are crucial to obtain a correct solution. There are three important steps in achieving
a complete solution of this model: (i) the realization that due to the inﬁnite dispersion,
the ρr,s (p) obey exact boson commutation relations [9]; (ii) a representation of the free
Hamiltonian (3.2) as a bilinear in these boson operators [9]; (iii) the
                                                                      √ explicit   construction
of a boson representation for the fermion operators Ψrs (x) = (1/ L) k crks exp(ikx).
                                                                           P

    “Normally” (the precise meaning of this will become apparent below) density operators
commute [ρs (p1 ), ρs (p2 )] = 0 because their Fourier transforms ρs (x) = Ψ†s (x)Ψs (x) are
local objects. This is no longer true for Luttinger’s density operators because of the
fermion doubling
                                                                       X
                          Ψs (x) → Ψr,s (x) ;                  cks =         Θ(rk)crks .                         (3.14)
                                                                       r=±

Θ(x) is the step function. There is now a nonlocal relation between the physical fermions
Ψs (x) and the right- and left-moving Ψr,s (x)

                   1 X L/2                                    π    πy
                            Z                                                                       
      Ψ†s (x) =              dy K(y) Ψ†r,s (x + y) with K(y) = cot                                           ,   (3.15)
                  2πi r −L/2                                  L    L

and the density operators no longer commute.
   The commutator of the density operators is
                                                   X †                                          
        [ρr,s (p), ρr′ ,s′ (−p′ )] = δr,r′ δs,s′       cr,k+p,scr,k+p′,s − c†r,k+p−p′,s cr,k,s           .       (3.16)
                                                   k

In a ﬁnite band containing both ±kF (ck,s without the subscript r), it is permissible to
change the summation variable k → k+p′ in the second term which makes the commutator
vanish. For the Tomonaga model (ﬁnite bands around ±kF ), for p 6= p′ one has an
operator acting on the states near the band edges rkF ± k0 , and the approximate bosonic
commutators of the Tomonaga model are obtained by neglecting these band edge terms.
For p = p′ one measures the diﬀerence in the number of occupied states at k and k + p, i.e.

                                                          19
p – making the commutator a ﬁnite number. For inﬁnite bands (Luttinger model), one
manipulates the (ill-deﬁned) diﬀerence of two inﬁnite quantities, and one must introduce
normal ordered operators, Eq. (3.5), into the right hand side of Eq. (3.16). The problem
of the band edge terms is then rigorously absent since there is no band edge left, and for
p = p′ the argument for the Tomonaga model carries over:

          [ρr,s (p), ρr′ ,s′ (−p′ )] = δr,r′ δs,s′        : c†r,k+p,scr,k+p′,s − c†r,k+p−p′,s cr,k,s :
                                                     X

                                                     k
                                                          X
                                    + δr,r′ δs,s′ δp,p′        [hnr,k+p,si0 − hnrks i0 ]
                                                           k
                                                            rpL
                                    = −δr,r′ δs,s′ δp,p′        .                                        (3.17)
                                                             2π
One can safely change the summation variable in the ﬁrst line of (3.17) because the
operators are normal-ordered; the two terms add up to zero, leaving the contribution of
the second line. In the Tomonaga model with ﬁnite bands for right- and left-movers, the
boson algebra obtains approximately (for wave vectors far from the band edges) because
one works with truncated density operators. The algebra (3.17) is known as the U(1)
Kac-Moody algebra in ﬁeld theory, and the nonvanishing of the commutator (3.17) due
to the inﬁnite number of negative energy states (Luttinger model) or the cutoﬀ procedure
(Tomonaga model) is called an “anomaly”.
    Acting on the ground state of the free Hamiltonian H0 , the ρr,s (p) behave either as
creation or annihilation operators, depending on sign(p)

                           ρ+,s (−p)|0i = ρ−,s (p)|0i = 0 for p > 0 .                                    (3.18)

To complete the algebra, it is necessary to construct a ladder operator Urs which changes
the fermion number without aﬀecting the bosonic excitations. This operator is necessary
again because of the inﬁnite dispersion: since there are no upper and lower limits to the
number of particles, the number operator cannot be expressed in terms of raising and
lowering operators. Haldane and Heidenreich et al. have given such a construction in
terms of the bosons ρr,s (p) and the fermions Ψrs (x) [3, 31], cf. below.
   There are several ways to see that the free fermion Hamiltonian H0 , Eq. (3.2), is
equivalent to an operator bilinear in the bosons ρrs (p). The simplest one [9] is to examine
the commutator
                                [H0 , ρr,s (p)] = vF r p ρr,s (p)                      (3.19)
which is obviously compatible with
                                  πvF X
                          H0 =                : ρr,s (p)ρr,s (−p) : + const.                             (3.20)
                                   L r,p6=0,s

The equivalence of the Hamiltonians (3.2) and (3.20) is known as Kronig’s identity [38],
and is valid at ﬁxed particle number. If particles are added to the system , the “+const.”
becomes important, however, because one must add their kinetic energy to the Hamilto-
nian. We put them into the lowest available states above the Fermi sea (other states can


                                                     20
be reached by acting with the boson operators). The complete Hamiltonian then takes
the form
                          πvs X
                  H0 =                : ρr,s (p)ρr,s (−p) :                               (3.21)
                           L r,p6=0,s
                           π Xh                                           i
                        +         vN (N+,s + N−,s )2 + vJ (N+,s − N−,s )2       ,
                          2L s
               (−1)Js = −(−1)N
                             s ,              (vs = vN = vJ = vF ) ,

where the Nr,s ≡ ρr,s (p = 0), Eq. (3.5), are taken relative to their (inﬁnite) ground state
value and therefore measure excitations with respect to a given ground state charge. The
symmetric combination Ns = r Nr,s measures charge and the antisymmetric combination
                                P

Js = r rNr,s measures current excitations, both carrying spin s. Total charge and spin,
      P

as well as charge and spin currents, are obtained by the appropriate sums over s. These
quantities specify the number and the left-right asymmetry of the fermions added to the
reference state (Ns = N0 /2, Js = 0). The equality of the three velocities in (3.21) to
the bare one only holds for the free model and is violated by interactions (the Hartree-
Fock energy of the added particles appears as the q = 0 components of the interaction
Hamiltonian). Including the charge and current excitations, (3.2) and (3.21) possess the
same spectrum, by construction. That the multiplicities of the levels also are equal can
be proved by calculating the grand partition function both in the fermion (3.2) and in the
boson (3.21) representation. Thus the fermionic and bosonic Hilbert spaces are identical.
     Why are such two diﬀerent representations of the same Hamiltonian possible? (i)
Reconsider the elementary particle–hole excitations in Figure 3.1. They acquire a well-
deﬁned particle-like character in 1D as q → 0. In the Luttinger model the low-q branch
of their dispersion is strictly linear in q. Decay of these excitations in the constituent
particles and holes is forbidden on account of 1D kinematics – it would involve states
in the void low-frequency part of the spectrum. There should thus be a representation
of the Hamiltonian, which describes excitations, in terms of these particles alternative
to the original fermionic one. Moreover, the absence of dispersion implies that these
excitations do not interact: one excitation with momentum q + q ′ has the same energy
as two excitations with momenta q and q ′ . Certainly, these collective modes also exist
in higher dimensions, but so does the electron-hole continuum which permits their decay
into quasi-particles and quasi-holes. (ii) An intimately related observation is that the
particle and the hole created in such an excitation, travel at the same group velocity and
therefore form an almost bound state which surely is extremely susceptible to dramatic
modiﬁcation by interactions where, in any case, momentum transfer cannot be neglected.
(iii) All states with even (odd) fermion charge N − N0 have excitation energies that are
even (odd) multiples of πvF /L. In other words, the spectrum eﬀectively becomes that of
a harmonic oscillator. This fact again suggests that an equivalent boson representation
of H0 should be possible. (iv) The Kac-Moody algebra (3.17) can be obtained either by
representing ρrs (p) as a fermion bilinear (3.5) or as the gradient of true bosonic ﬁeld Φr,s (x)
[Eq. (3.40) below]. Since the algebra is unique, the two representations must be equivalent.
While for the noninteracting problem, the two representations are true alternatives, the

                                               21
success of bosonization is related to the fact that the bosonic one becomes more “natural”
once interactions are introduced.
    Now the Luttinger Hamiltonian can be diagonalized by a Bogoliubov transformation
[3, 9, 31]. First transform to charge and spin variables
                       1                               1
             ρr (p) = √ [ρr,↑ (p) + ρr,↓ (p)] , Nr,ρ = √ [Nr,↑ + Nr,↓ ] ,
                        2                                2
                       1                                1
             σr (p) = √ [ρr,↑ (p) − ρr,↓ (p)] , Nr,σ = √ [Nr,↑ − Nr,↓ ] .                           (3.22)
                        2                                2
We only include the z-component of the spin density operator working within abelian
bosonization. At this point, the SU(2)-spin transformation properties of the fermions
(3.12) has been broken down to U(1) [just like the gauge transformation (3.9) for the
charges], and likewise for the symmetry of the Hamiltonian, even if (3.11) is satisﬁed.
One can keep the spin densities transforming explicitly according to SU(2)
                                          X1
                               Sr (x) =              Ψ†rs (x)σss′ Ψrs′ (x)                          (3.23)
                                          s,s′
                                                 2

and represent the Hamiltonian in terms of the U(1)-ρr - and SU(2)-Sr -ﬁelds. In this way,
one can keep SU(2)-invariance manifest at every stage of the calculation. The price to be
paid is, however, a signiﬁcantly more complicated boson respresentation which will not
be reviewed here [20, 39].
   The interactions transform as
                              1                               1           
                      giρ =     gik + gi⊥            , giσ =       gik − gi⊥   .                    (3.24)
                              2                                 2
The Hamiltonian then becomes (ν = ρ, σ henceforth)
              πvF X
       H0 =               : νr (p)νr (−p) :                                                         (3.25)
               L νrp6=0
               π h                                       i
            +     vN ν (N+ν + N−ν )2 + vJν (N+ν − N−ν )2                     (vN ν = vJν = vF ) ,
              2L
              2X
       H2   =       g2ν (p)ν+ (p)ν− (−p) ,                                                          (3.26)
              L νp
              1X
       H4   =       g4ν (p) : νr (p)νr (−p) : .                                                     (3.27)
              L νrp

We diagonalize by the canonical transformation

                  H̃ = eiSν He−iSν , ν̃r (p) = eiSν νr (p)e−iSν
                       2πi X ξν (p)
                  Sν =              [ν+ (p)ν− (−p) − ν− (p)ν+ (−p)]                   .             (3.28)
                        L p>0 p

The νr ’s explicitly transform as

                      ν̃r (p) = vr (p) cosh[ξν (p)] + ν−r (p) sinh[ξν (p)] ,                        (3.29)

                                                     22
and H̃ is diagonal under the condition
                                           v
                                           u πvF + g4ν (p) − g2ν (p)
                                           u
                                  2ξν (p)
                         K (p) ≡ e
                           ν              =t                                    .       (3.30)
                                             πvF + g4ν (p) + g2ν (p)

For repulsive interactions, Kν < 1 while for attraction Kν > 1. The diagonal form is then
                      π X
            H̃    =             vν (p) : ν̃r (p)ν̃r (−p) :                              (3.31)
                      L rνp6=0
                       π h                                        i
                  +         vN ν (N+ν + N−ν )2 + vJν (N+ν − N−ν )2 ,
                      2L
                 with vN ν vJν = vν2 i.e. vN ν = vν /Kν and vJν = vν Kν .               (3.32)

(The Nrν -operators are not changed by the canonical transformation.) The renormalized
charge and spin ﬂuctuation velocity is
                                   v
                                   u"                 #2     "         #2
                                   u        g4ν (p)          g2ν (p)
                           v (p) = t v
                               ν        F +                −                ,           (3.33)
                                              π                π

and therefore
                       vN ν = vF + g4ν + g2ν ,     vJν = vF + g4ν − g2ν ,               (3.34)
and the limit p → 0 is implied whenever p is not exhibited explicitly. Due to the momen-
tum transfer cutoﬀ Λ, we have asymptotically
                   (                                         (
                       Kν for p ≪ Λ                              vν for p ≪ Λ
        Kν (p) →                                 vν (p) →                           .   (3.35)
                        1 for p ≫ Λ                              vF for p ≫ Λ

    Eqs. (3.31) and (3.32) are the central constitutive relations for the Luttinger model
and the Luttinger liquid hypothesis discussed in the next chapter will postulate that these
relations continue to hold in a low-energy subspace of all solvable gapless 1D models. The
quantity Kν (p → 0), Eq. (3.30), is the essential renormalized coupling constant for each
degree of freedom, and physically plays the role of a stiﬀness constant. Kν governs the
power-law decay of most correlation functions. The two parameters vν and Kν completely
describe the low-energy physics of each degree of freedom ν of the model. That there are
just two such parameters is not surprising: the Hamiltonian has only two parameters g2ν
and g4ν , and we just get back what we have put in. Important are the following facts:
(i) the three diﬀerent velocities in the problem are all renormalized by the interactions,
Eq. (3.32), and describe diﬀerent physical processes. vν , the renormalized Fermi (or
“sound”) velocity governs the bosonic excitations; vN ν is related to the fermionic charge
excitations, i.e., for ν = ρ measures the shift in chemical potential upon varying the
Fermi wave vector δµ = vN ρ δkF and, for ν = σ the relation of the magnetic ﬁeld to
the magnetization M = vN σ (kF ↑ − kF ↓). vJν ﬁnally measures the energy necessary to
create persistent charge or spin currents on the periodic chain. (ii) All three velocities are
properties of the spectrum of the model. Spectra can, however, be calculated either exactly
by Bethe Ansatz (e.g. Hubbard model) or to high accuracy with numerical methods, and

                                              23
the velocities can then be determined. (iii) The three velocities determine the renormalized
coupling constant Kν which in turn determines all correlation functions of the Luttinger
model. It is now obvious how Eq. (3.32) turns the Luttinger model into a very useful
device for accessing the correlation functions of all 1D gapless models.
    One prominent property of the Luttinger model – charge-spin separation – is manifest
here: charge and spin ﬂuctuations propagate with diﬀerent velocities and will therefore
separate in time. In realistic models, charge-spin separation will be dynamically generated
close to their Fermi surface. In the Luttinger model describing just this subspace, it has
become a manifest property of the model.
    Collective charge density and spin density ﬂuctuations propagating with diﬀerent ve-
locities do also occur in higher dimensional models, and in particular in the Fermi liquid.
This is not special to 1D. Dramatic consequences in 1D arise, however, from the lack
of robustness of hypothetical quasi-particles with respect to these elementary excitations
separating in time. Quasi-particles do not exist in 1D systems with charge-spin separa-
tion. This may again be traced back to the lack of a continuum of low-energy excitations
for 0 ≤ q ≤ 2kF , (Figure 3.1): in 1D there is no way how these collective modes can decay
into the hypothetical constituent quasi-particles (holes) which therefore never reappear
once interactions have been introduced. The absence of quasi-particles is most directly
seen in the single-particle spectral function which cannot be written in a form similar to
Eq. (2.5). Detailed results can be found in Section 3.4.
    Labelling the charge-localization (Mott-Hubbard) transitions generated by strong Cou-
lomb interactions as “charge-spin separation” is somewhat misleading. It happens in
higher dimensions, too. At issue are the excitations out of this state, and whether there
are quasi-particles at low energies. Of course, there may be borderline cases, where the
quasi-particle residue in (2.5) is small but ﬁnite, and most of the spectral weight resides
in the collective modes.
    Charge-spin separation is also visible in the many-particle correlation functions. This
is trivial, and also happens in higher dimension, for the small-q parts of density and
spin density correlation functions. The novel feature of the correlation functions in 1D
is the appearance of two separate singularities close to 2kF (and, partly, higher multiples
thereof) where a single one is expected in the absence of charge-spin separation. This will
also be discussed in Section 3.4. Before, we need to ﬁnd a practical representation of the
fermion operator in terms of the bosons diagonalizing the Hamiltonian in order to be able
to calculate correlation functions.


3.2.2     Bosonization
A completely satisfactory boson solution of the Luttinger model also requires an explicit
representation of the fermion operators Ψrs (x) in terms of the bosons ρrs (p). Then any
correlation function can be given an equivalent boson representation and, the diagonal
Hamiltonian being a simple boson bilinear, the calculation of any of these correlation
functions becomes almost trivial, reducing to Gaussian averages.
   Pioneering work in this direction was performed by Luther and Peschel [32] and Mattis

                                            24
[33]. They proposed a bosonization formula which allowed an asymptotic calculation of
correlation functions but was certainly not an operator identity transforming between
fermions and bosons. The cutoﬀ procedures and the interpretation of these cutoﬀs were
ambiguous [36]. Field theorists proposed similar constructions at the same time [40].
    A precise formulation of such an operator identity was given independently by Haldane
[3] and Heidenreich et al. [31], and involves the construction of the (unitary) ladder
operator Ur,s . This operator increases by unity the number of fermions with spin s on
branch r and must commute with the boson operators with ﬁnite momentum. It is
suﬃcient for that purpose to consider states |Nr,s i where all states below a certain wave
vector are ﬁlled and above empty:

                    Ur,s |Nr,s Nr̄,s̄ i = |Nr,s + 1 Nr̄,s̄ i , [ρr,s (p 6= 0), Ur′ ,s′ ] = 0                     (3.36)

in evident notation. A natural guess is to put the new fermion into the ﬁrst free level
above the reference state, occupied up to | kF + 2πNr,s /L |,
                                                              "                         #!
                            1 X †                     (2Nr,s + 1)π
                 Ur,s    = √      crks δ rk − kF +                                                               (3.37)
                             L k                           L
                                                     "                    # !
                            1 Z L
                                                             (2Nr,s + 1)π
                         = √      dx Ψ†r,s (x) exp ir kF +                 x                     .
                             L 0                                  L
Its commutator with the bosons does, however, not vanish
                                                                            "                   # !
                         δr,r′ δs,s′                                           (2Nr,s + 1)π
                                       Z L
                                                    ipx
   [ρr,s (p), Ur′ ,s′ ] = √                  dx e         Ψr,s (x) exp ir kF +              x            .       (3.38)
                               L        0                                           L
The idea now is to introduce, into Eq. (3.37), a bosonic ﬁeld φr,s (x) whose commutators
with ρr,s (p) compensate the unwanted commutator from Ψr,s . One then has
                                   1
                                            Z L
                                                                  †
                 Ur,s      =      √               dxeirkF x e−iφr,s (x) Ψ†r,s (x) e−iφr,s (x)                    (3.39)
                                    L        0
                         with                                                                       
                                    πrx              2πi X e−α|p|/2−ipx
             φr,s (x)      =      −     Nr,s + lim                     Θ(rp)ρr,s (−p)                          (3.40)
                                     L         α→0    L p6=0  |p|

which is the desired operator. This expression can be inverted for Ψr,s (x), now given in
terms of bosons and the ladder operator, and compactiﬁed into
                 eir(kF −π/L)x †
                                                                                                             !
                                      −i
   Ψrs (x) = lim √            Urs exp √ [rΦρ (x) − Θρ (x) + s {rΦσ (x) − Θσ (x)}]                                 .
             α→0       2πα             2
                                                                                                                 (3.41)
The two phase ﬁelds are
                          iπ X e−α|p|/2−ipx                                   πx
          Φν (x) = −                        [ν+ (p) + ν− (p)] − (N+,ν + N−ν )    ,                               (3.42)
                          L p6=0    p                                         L

and
                             iπ X e−α|p|/2−ipx                                   πx
                Θν (x) =                       [ν+ (p) − ν− (p)] + (N+,ν − N−ν )                                 (3.43)
                             L p6=0    p                                         L

                                                               25
and are constructed from the φr,s and φ†r,s plus commutator terms. The charge density
operator is related to Φρ by
                                                       √
                               √                         2 ∂Φρ (x)
                        ρ(x) = 2 [ρ+ (x) + ρ− (x)] = −             ,             (3.44)
                                                       π     ∂x
                  √
where the factor 2 comes from (3.22), and there is an analogous expression for the spin
density. Θν (x) is related to the momentum canonically conjugate to Φν (x)
                          1 X −α|p|/2−ipx                                    π
               Πν (x) =          e        [ν+ (p) − ν− (p)] + (N+,ν − N−,ν )                   (3.45)
                          L p6=0                                             L
by                                              Z x
                                   Θν (x) = π         dz Πν (z)                                (3.46)
                                                 −∞
and the commutation relations are
                           [Φν (x), Πν ′ (x′ )] = iδν,ν ′ δ(x − x′ )                           (3.47)
                                               π
                      [Φν (x), Θν ′ (x′ )] = i δν,ν ′ sign(x′ − x) .                           (3.48)
                                               2
We can rewrite the Hamiltonian in terms of these phase ﬁelds as
                                                                           !2 
                      1 XZ                                       ∂Φν (x)      
                  H=       dx vJν π 2 Π2ν (x) + vN ν                               ,           (3.49)
                     2π ν                                          ∂x        

making obvious the equivalence to the Gaussian model of statistical mechanics. Under
the Bogoliubov transformation (3.28), the phase ﬁelds transform as
                                 q                                      q
                       Φν → Φν Kν           and          Θ ν → Θ ν / Kν                        (3.50)
if we neglect the momentum dependence of the interactions g(p) so that the Kν can be
taken outside the summations in (3.42) and (3.43). These expressions can now be em-
ployed for calculating arbitrary correlation functions. Examples are given in the following.
    There is also a more physical way of arriving at the general boson structure of the
fermion operators [41, 42]. Deﬁne a boson ﬁeld Φr,s (x) by ∂Φr,s (x)/∂x = −πρr,s (x) where
ρ describes density fluctuations. Introducing a particle at site x creates a kink of amplitude
π in the ﬁeld Φr,s , i.e. the phases of all other particles have to shift to accommodate the
new particle. This ﬁeld can be considered as a dynamical implementation of the Fermi
surface phase shifts appearing in Anderson’s arguments in favour of a Luttinger liquid
in 2D [11]. Since displacement operators are exponentials of momentum operators, one
                                Rx
could guess Ψr,s (x) ∼ exp[iπ −∞     dzΠr,s (z)] where Πr,s (z) is the momentum canonically
conjugate to Φr,s (x). This operator commutes, however, with itself. The required change
of sign at x = x′ is achieved by multiplying with exp[±iΦr,s (x)] which yields
                             1                                x
                                                                   Z                  
             Ψr,s (x) ≈ lim     exp irkF x − irΦr,s (x) + iπ    dzΠr,s (z)                 .   (3.51)
                        α→0 2πα                              −∞

This is essentially the Luther–Peschel–Mattis formula [32, 33] which contains all the im-
portant bosonic terms for the calculation of physical properties but does not have the
status of an operator identity in the full Hilbert space of the Luttinger model.

                                                26
3.2.2.1   Spinless fermions
At various stages of this article, we will need spinless fermions, either because of their
physical relevance as elementary charge excitations (holons) in the Hubbard and related
models, or just for simpliﬁcation. Here, we compile the most important formulae from
the preceding paragraphs for spinless fermions.
    The Hamiltonian is obtained by dropping the spin label and summations in (3.2) –
(3.4), i.e.
                                πvF X                     πvF  2     
                  H =                 : ρr (p)ρr (−p) : +      N + J2                                   (3.52)
                                 L rp                     2L
                                                                                                !
                        1X                       g4 (p) X
                      +     g2 (p)ρ+ (p)ρ− (p) +          : ρr (p)ρr (−p) :                             (3.53)
                        L p                        2    r

with N, J = N+ ± N− . The Hamiltonian is diagonalized as
                         X πv(p)                                  π
                  H̃ =                   : ρ̃r (p)ρ̃r (−p) : +      (vN N 2 + vJ J 2 ) + const.         (3.54)
                            r     L                              2L

with the velocities
         v
         u"                 #2     "          #2
         u         g4 (p)          g2 (p)                         g4 (0) + g2 (0)             g4 (0) − g2 (0)
v(p) =   t
              vF +               −                 , vN = vF +                    , vJ = vF +                 ,
                    2π              2π                                  2π                          2π
                                                                                                        (3.55)
and the stiﬀness “constant”
                                              v
                                              u 2πvF + g4 (p) − g2 (p)
                                              u
                                       K(p) = t                                 .                       (3.56)
                                                     2πvF + g4 (p) + g2 (p)

Finally, the bosonization identity for spinless fermions is

                                       eir(kF −π/L)x †
                     Ψr (x) = lim         √         Ur exp (−i [rΦ(x) − Θ(x)])              .           (3.57)
                                   α→0       2πα
The ﬁelds Φ(x) and Θ(x) are given by the expressions (3.42) and (3.43) for the charges,
and the operators ρr (p) now refer to spinless fermions. With these ﬁelds, the Hamiltonian
the has the following phase representation
                                                                               !2 
                                1                                       ∂Φ(x)
                                         Z                                        
                            H=               dx vJ π 2 Π2 (x) + vN                      .               (3.58)
                               2π                                       ∂x         


3.3       Physical Properties of the Luttinger Model – Ther-
          modynamics and Correlation Functions
The machinery set up in the preceding section is extremely useful in calculating correlation
functions. A remarkable feature of the Luttinger model is that all correlation functions can
be calculated exactly. With the boson representation of an operator, all the expectation

                                                          27
values reduce to Gaussian averages, as we shall show on some examples here. The linear
response of an operator B in a system described by a Hamiltonian H0 , coupled to an
                                                              R
external ﬁeld a(x, t) by the operators A(x), i.e. H = H0 + dx a(x, t) A(x) is related,
through the Kubo formulae, to correlation functions of the system in the absence of the
external ﬁeld (in the interaction picture and assuming translational invariance)
                                                Z ∞
                            (a=0)
          hB(x, t)i = hB            (x, t)i +         χBA (x − x′ , t − t′ )a(x′ , t′ )dx′ dt′ ,
                                                −∞
          χBA (x, t) = −iΘ(t)h[B(x, t), A(0, 0)]ia=0 .                                             (3.59)

χ is called susceptibility, response function, retarded correlation function, etc. There
are many closely related functions and below, we shall denote all of them as RBA or, if
symmetric, simply as RA , with some exception for cases of special relevance. Within linear
response theory, the Luttinger model can make predictions for all possible measurements.


3.3.1     Thermodynamics and transport
The Luttinger model has a speciﬁc heat linear in temperature
                                                                        !
                                                γ    1       vF   vF
                         C(T ) = γT ,              =            +           .                      (3.60)
                                                γ0   2       vρ   vσ
The linearity is both characteristic of the underlying fermions (linear speciﬁc heat in
any dimension) as well as of the bosonic excitations (phonons in 1D also have a linear
speciﬁc heat). γ0 is the coeﬃcient of free electrons which can be calculated from both
representations as
                                      π 2 kB
                                           2
                                                      2πkB2
                                 γ0 =        N(EF ) =        ,                      (3.61)
                                         3             3vF
the density of states of the free Luttinger model being a constant N(E) = 2/πvF including
spin and both branches. The spin susceptibility and compressibility are
                          1   1 ∂ 2 E0 (σ)             1   1 ∂ 2 E0 (n)
                            =              ,             =              ,                          (3.62)
                          χ   L ∂σ 2                   κ   L ∂n2
where E0 is the ground state energy as a function of the particle (spin) density n (σ).
Throughout this article, we denote the average particle density (band ﬁlling factor) by
n and the density ﬂuctuations by ρ(x). The susceptibilities are renormalized by the
interactions
                          2Kσ      2             2Kρ       2
                     χ=       =         and κ =        =         .               (3.63)
                          πvσ    πvN σ            πvρ     πvN ρ
They are related to the renormalized velocities for the charge (spin) excitations deﬁned
in Eq. (3.34). This is expected, of course, because vN ν measures the change in energy
upon changing the number of electrons in the system, cf. (3.31). As we shall see below,
spin-rotation invariance requires Kσ = 1.
    The electrical conductivity is determined from the current-current correlations through
the Kubo formula
                                           i D
                                                          
                                   σ(ω) =        + RjR (ω)                            (3.64)
                                          ω π

                                                  28
where the ﬁrst term is the diamagnetic part and the (second) paramagnetic term is given
in terms of the retarded current-current correlation function
                                   i
                                       Z L        Z ∞
                     RjR (ω) = −             dx         dth[j(x, t), j(0, 0)]ieiωt .          (3.65)
                                   L    0          0

The Drude weight D in fact is a susceptibility and is related to the derivative of the
ground state energy with respect to an applied ﬂux Φ [43]

                                        π ∂ 2 E0 (Φ)
                              D=                     = 2vJρ                                   (3.66)
                                       2L ∂Φ2 Φ=0

A ﬂux creates a “persistent” current in a Luttinger ring, and the appearance of vJρ here
should not surprise from (3.31) again. 2vJρ = 2vρ Kρ plays the role of the plasma frequency
in 1D [44].
    One has to be careful in the deﬁnition of the current operators. Naively, one has
       √                         √
j(x) = 2vF [ρ+ (x) − ρ− (x)] = 2vF Πρ (x). A more careful evaluation via the continuity
equation ∂t ρ(xt) + ∂x j(xt) = 0 gives, however,
                          √
                            2∂            √                √
                 j(xt) =        Φρ (xt) = 2vρ Kρ Πρ (xt) = 2vJρ Πρ (xt) .             (3.67)
                          π ∂t
The diﬀerence is due to the fact that, in the Luttinger model, g2 may be diﬀerent from
g4 and the density does not necessarily commute with the interaction Hamiltonian, as it
does in a well-deﬁned lattice model. Notice, however, that vρ Kρ = vJρ ; if the Luttinger
model is derived from a well-deﬁned lattice model with density-density interactions only,
g2ν = g4ν is required and, using Eq. (3.34), one obtains vJρ = vF , i.e. the current
operators are not renormalized by interactions. This applies to galilean invariant models
in general where, in the limit q → 0, the current becomes proportional to momentum
which is conserved by the interactions [45]. Consequently, as can be shown by two partial
integrations on Eq. (3.65) producing
                                             Z ∞
              σ(ω) = − lim Re (iω)−3               dteiωt h[ [H, j(qt)] , [H, j(q, 0)] ]i ,   (3.68)
                        q→0                  0

one has RJR (ω) ≡ 0 [45], so that the conductivity reduces to a pure Drude peak

                               σ(ω) = 2vJρ δ(ω) = 2vF δ(ω)                                    (3.69)

with an interaction-independent strength. This relation has been derived by a number of
people [44, 46, 47, 48].
    There are a few most remarkable facts about these unspectacular formulae. (i) The
ﬁniteness of the susceptibilities characterizes the system as a “normal metal”. It is highly
nontrivial in view of the ubiquitous divergences we shall encounter in the following sec-
tions. The physical origin lies in the strong conservation laws of the 1D phase space in the
absence of backscattering [46]. (ii) These quantities can be calculated both in a fermion
representation where one considers the charge excitations Nν and uses (3.62), and from
the q → 0 limit of bosonic correlation functions which we shall compute in Section 3.5.

                                                       29
The result is the same. The reason will be given below [47]. (iii) The boson representation
gives the susceptibilities in absolute magnitude for lattice models provided parameters are
identiﬁed correctly [47]. One can invert the procedure and use these relations to identify
the parameters of a low-energy boson theory for lattice models from (3.62) [10, 48, 49].
(iv) They can be obtained from the energy alone which can be calculated either from an
exact solution or accurately with numerical diagonalization where correlation functions
are not readily available [48, 49].


3.3.2     Single- and two-particle correlation functions
The thermodynamic properties do not diﬀer from the Fermi liquid. There, compressibility
and susceptibility are renormalized by interactions, too, and the renormalization is given
by the Landau parameters F0s and F0a . We neither see the anomalous power-laws not the
eﬀects of charge-spin separation highlighted earlier. To this end, we carry on to the space-
and/or time-dependent correlation functions
                                              h                   i 
                                                          †
                         RO (x, t) = −iΘ(t)    O(x, t), O (0, 0)                       (3.70)
                                                                   ±


of various operators O of interest. [. . .]± denotes commutator or anticommutator for
bosons and fermions, respectively. Other, e.g. time-ordered, correlation functions are
obtained in a similar way.
   We give a rather explicit calculation for the single-electron Green function
                                                                               
        Grs (xt) = −iΘ(t)h{Ψrs (xt), Ψ†rs (00)}i ≡ −iΘ(t) G̃(xt) + G̃(−x − t)          (3.71)

where Ψr,s (x) has been deﬁned in Eq. (3.41), to sketch how such a calculation works in
practice, and to give some formulae useful for the work with boson operators. In (3.71), we
have incorporated that G is diagonal in r and s. Using the bosonization identity (3.41)
                                       †
in (3.71), we ﬁrst commute the Urs       -operator from Ψr,s (x) at the left of the expression
through the exponentials until it arrives at the right, where Ψ†rs (0) has a Urs . Being
                     †
unitary, we have Urs   Urs = 1. What are the terms we pick up during the commutations?
Urs commutes with ρrs (p 6= 0) by construction, so that the only nonvanishing terms come
from the operators Nrs measuring the charge excitations in the phase ﬁelds Φν and Θν .
These terms, however, involve prefactors 1/L so that their contribution vanishes in the
limit L → ∞. If we are interested in this thermodynamic limit, we can neglect both the
Urs - and Nrs -operators altogether. We see that the Luther-Peschel-Mattis formula (3.51)
(neglecting the Ur,s - and Nr,s -operators) gives the exact asymptotic behaviour of the Green
function! (This statement is not completely true for the many-particle functions: Urs
anticommutes with Ur′ s′ if at least one index is diﬀerent. When one considers operators O
pairing Ψr,s (x) with diﬀerent indices, as we do in almost all two-particle functions below,
the Urs will produce phase factors. The exponent of the power-law is unaﬀected by these
phase factors but logarithmic or prefactor corrections crucially depend on them [50].)
    After diagonalizing the Hamiltonian, the Green function becomes (dropping the indices


                                              30
r and s)

             eirkF x
                              *                                            !                                       !+
                            i h                   i     i h                   i
G̃(xt) = lim         exp − √ r Φ̃ρ (xt) − Θ̃ρ (xt) exp √ r Φ̃ρ (00) − Θ̃ρ (00)                                               ×
         α→0 2πα             2                           2                                                               ρ
                 *                                            !                                 !+
                            i h                   i     i h                   i
         ×           exp − √ r Φ̃σ (xt) − Θ̃σ (xt) exp √ r Φ̃σ (00) − Θ̃σ (00)                            .            (3.72)
                             2                           2                                           σ

However, we keep the momentum dependence of the interactions and do not use (3.50); we
denote the transformed ﬁelds by Φ̃ν and Θ̃ν . Moreover, since the ρ-phase ﬁelds commute
with the σ-ﬁelds, we have separated the exponentials into products involving only ρ and
σ separately. h. . .iν denotes the expectation value with the ν-part of the Hamiltonian.
Next we use the important relation

                                  eA eB = eA+B e[A,B]/2            valid if [A, B] ∈ C
                                                                                     C                            (3.73)

to merge all ν-phase ﬁelds into one exponential. The commutators contribute exp[Cν (xt)]
with
                π X e−α|p| e−ipx
                                                "                      #                                 !
                                                               1
    Cν (xt) = −                                     Kν (p) +        i sin [vν (p)pt] + 2r cos [vν (p)t]            .
                L p6=0   p                                   Kν (p)
                                                                                                                  (3.74)
                                   A+B
The expectation value he                 i ≡ exp[Dν (xt)] is evaluated using
                                                             1
                                                                          
                                               hexp Ai = exp hA2 i                                                (3.75)
                                                             2
valid for a linear form in boson operators whose exponential is averaged with a harmonic
oscillator (Gaussian) Hamiltonian. We ﬁnd
                                                 ′
                  π 2 X e−α(|p|+|p |)/2
       Dν (xt) =                        ×                                                                         (3.76)
                 4L2 p,p′6=0 pp′
                                                                                  
                                                          q                    1                             
                        hνR (p)νR (p′ )i                                        e−iP (x−Rvν (P )t) − 1
                  X                         Y
             ×                                       r   Kν (P ) + R q
                  R=±                      P =p,p′                     Kν (P )

with
                                                                                   (                                   )!
             ′           L|p|       Θ(rp)                                  1
hνr (p)νr (p )i = δp,−p′                          + Θ(−rp) 1 +                             .
                         2πexp [vν (p)p/2kT ] − 1               exp [vν (p)p/2kT ] − 1
                                                                                    (3.77)
For T = 0, to be treated ﬁrst, the Bose-Einstein distribution vanishes for p 6= 0, and we
can rearrange eCν eDν so that
                                         1h ν                             i
                 Cν (xt) + Dν (xt) = −     V+ (xt) + V−ν (xt) − 2rV0ν (xt) ,                                      (3.78)
                                         2
                                       1     dp −αp ±1 h
                                         Z ∞                                   i
                            V±ν (xt) =         e Kν (p) 1 − cos(px)e−ivν (p)pt                     ,              (3.79)
                                       2 0 p
                              ν        i Z ∞ dp −αp
                            V0 (xt) =          e    sin(px)e−ivν (p)pt .                                          (3.80)
                                       2 0 p

                                                              31
All correlation functions can be expressed in terms of V± and V0 .
    Now remember that in the Luttinger model a momentum transfer cutoﬀ must be
imposed on the interactions, and the asymptotic values of Kν and vν are given by (3.35).
Taking e.g. V+ , we split the integral in two terms by adding and subtracting [. . .] on the
right-hand side [51, 52]. Taking together (Kν − 1)[. . .], the important contributions will
come from p ≪ 1/Λ, and we can replace vν (p) → vν there. The contribution of this term
to V+ then becomes

                         Λν+ + ivν t + ix             Λν+ + ivν t − ix
                                                !                                    !
               Kν − 1                       Kν − 1
                      ln                  +        ln                                          (3.81)
                 4             Λν+            4             Λν+

where the cutoﬀ Λν+ is given by

                 Λν+
                       !
                                  1            dp h
                                         Z ∞                                     i
              ln           =−                       Kν (p) − 1 − (Kν − 1) e−Λ0 p         .     (3.82)
                 Λ0             Kν − 1   0     p

Λ0 is arbitrary but ﬁnite. Since (3.81) would be obtained by taking an exponential cutoﬀ
on Kν (p) − 1, (3.82) amounts to ﬁnding an equivalent exponential cutoﬀ to the cutoﬀ
of arbitrary form contained in Kν (p). In the following, we assume that there is a single
cutoﬀ Λ in the problem independent of the indices ± and ν. In the second term from V+ ,
the only interaction-dependent quantity is vν (p). Here it is simplest to use the fact that
(3.81) can be obtained with an exponential cutoﬀ Λ, add and subtract exp(−Λp) and use
vν resp. vF for the integrals weighted at small or large momentum. V0 is treated in the
same way. The ﬁnal result is then [18, 51, 52, 53] (approximate expressions have been
given by many others)
                                                                                              !γν
             1 irkF x     Λ + i(vF t − rx) Y            1                        Λ2
 G̃(x, t) =    e      lim                        q                                                  .
            2π        α→0 α + i(vF t − rx)
                                           ν=ρ,σ  Λ + i(vν t − rx)        (Λ + ivν t)2 + x2
                                                                                               (3.83)
The exponent is
                                     1      1
                                                          
                                γν =   Kν +    −2 ≥0 .                                         (3.84)
                                     8      Kν
Eq. (3.83) gives the universal behaviour of the Green function, which is independent
of detailed cutoﬀ forms. Nonuniversal contributions which have been eliminated by the
trick of adding, subtracting and recombining terms above, can also be evaluated [54].
The spinless fermion result can be obtained by putting formally Kρ = Kσ = K and
vρ = vσ = v [32, 55].
    For t = 0, the Green function decays as

                        Grs (x) ∼ x−1−α ,
                                                               X
                                                         α=2       γν ≥ 0 .                    (3.85)
                                                               ν

The exponent α appears in all single-particle properties. α/2 is the “anomalous dimen-
sion” of the fermion operators. [It has become customary to use α both for the exponent
of the Green function and for the inﬁnitesimal in the bosonization identity (3.41); the


                                                    32
context usually identiﬁes clearly which α is referred to, and confusion seems unlikely.]
From Grs , one can derive the momentum distribution function [53, 56, 57]
                            1
                   n(k) ∼     − C1 sign(k − kF ) | k − kF |α −C2 (k − kF )             (3.86)
                            2
which does not have a jump at kF but rather a continuous power-law variation. An
exact calculation of the prefactors is also possible [53]. In (3.86) the breakdown of Fermi
liquid theory and the absence of quasi-particles are evident. Fermi liquids have a jump
discontinuity of amplitude zkF ≤ 1 at kF where zk is the wave-function renormalization
constant, Eq. (2.4). However, the velocities do not enter and charge-spin separation does
not manifest itself, and only the absence of quasi-particles due to the Peierls-type coupling
of the two Fermi points is probed. The single-particle density of states N(ω) varies as a
power-law
                                        N(ω) ∼| ω |α                                   (3.87)
with the same exponent α. Again, exact but lengthy expressions are available [53].
    The density-density correlation function consists out of several pieces, corresponding
to the wave vectors q ≈ 0 (ρ), q ≈ ±2kF (CDW), and q ≈ ±4kF (4kF -CDW), and, in
principle, higher multiples
                                                        √
                         X              √ X               2 ∂Φρ (x)
              Oρ(x) =         ρr,s (x) = 2   ρr (x) = −                              (3.88)
                          r,s              r            π     ∂x
                               Ψ†+,s (x)Ψ−,s (x)
                         X
         OCDW (x) =
                           s
                       1 X           †
                                            n           √                    o
                     =         U+,s U−,s exp −2ikF x + 2i [Φρ (x) + sΦσ (x)]          (3.89)
                      2πα s
                       1      n            √        o      √
                    ≈    exp −2ikF x + 2iΦρ (x) cos[ 2Φσ (x)] .
                      πα
                      X †
           O4kF (x) =    Ψ+,s (x)Ψ†+,−s (x)Ψ−,−s (x)Ψ−,s (x)
                           s
                            2       n            √          o
                     =          exp   −4ik F x +   8iΦρ (x)   .                       (3.90)
                         (2πα)2
In the Luttinger model, the Urs -ladder operators give only contributions vanishing in the
thermodynamic limit L → ∞ and have been dropped after (3.89) [see however the remark
after Eq. (3.71)]. Notice also that O4kF involves four fermions in the Luttinger model but,
as will be explained below, is part of the (two-particle) density operator in lattice models.
Moreover, the wavelength λ = 2π/4kF = (N0 /L)−1 equals the inverse particle density.
Establishment of 4kF -CDW long-range order therefore corresponds to the formation of
a Wigner crystal, and we shall be interested in this possibility as well as its short-range
ordered variant below. The expectation values are evaluated exactly as in the case of the
Green function above, so that we only give the asymptotic decay laws
                        Kρ
                Rρ (x) =       ,                                                      (3.91)
                       (πx)2
            RCDW (x) ∼ cos(2kF x) x−2+αCDW               , αCDW = 2 − Kρ − Kσ ,       (3.92)
                                           −2+α4kF
              R4kF (x) ∼ cos(4kF x) x                   , α4kF = 2 − 4Kρ ,            (3.93)

                                                   33
We see that the 4kF -correlations decay very fast at weak-coupling but become competitive
with the 2kF ones when Kρ decreases [58]. For Kσ = 1, 4kF correlations dominate over
2kF for Kρ ≤ 1/3.
    The other correlation functions follow similar power-laws. Long wavelength spin ﬂuc-
tuations follow (3.91) with Kρ → Kσ . For later use, we also give the operators for the
x, y, z-components of the SDW correlations

                                   Ψ†+,s (x)Ψ−,−s (x)
                              X
             OSDW,x(x) =
                               s
                           1    h            √     i   h√       i
                          =  exp −2ikF x + 2iΦρ (x) cos 2Θσ (x)                          (3.94)
                          παX
             OSDW,y (x) = −i   sΨ†+,s (x)Ψ−,−s (x)
                                   s
                           1      h            √   i   h√       i
                        =    exp −2ikF x + 2iΦρ (x) sin 2Θσ (x)                          (3.95)
                          πα
                             sΨ†+,s (x)Ψ−,s (x)
                          X
             OSDW,z (x) =
                               s
                               i    h         √        i   h√       i
                          =      exp −2ikF x + 2iΦρ (x) sin 2Φσ (x)                 .    (3.96)
                              πα
The correlation functions decay as

        RSDW (x) ∼ cos(2kF x)x−2+αSDW ,                                                  (3.97)
           αSDWx =      αSDWy = 2 − Kρ − Kσ−1           ,   αSDWz = 2 − Kρ − Kσ .        (3.98)

Singlet (SS) and triplet (TS) superconducting correlations do not oscillate and decay with
exponents

               αSS = 2 − Kρ−1 − Kσ ,                                                     (3.99)
              αT S0 =    2 − Kρ−1 − Kσ      ,        αT S±1 = 2 − Kρ−1 − Kσ−1   .       (3.100)

Each correlation function has its proper special combination of the two parameters Kν in
the power-law exponent which therefore parameterize completely the scaling laws between
the exponents. Remember also that Kν relates the three velocities for each degree of
freedom, i.e. the spectrum of low-lying eigenvalues (3.32). Diﬀerent is only the correlation
function of the long-wavelength charge or spin ﬂuctuations. The operator ν(x)ν(0) is
marginal with a scaling dimension −2 and does not acquire an anomalous dimension.
Also its correlation function does not depend on a cutoﬀ (in the other expressions, it has
simply been suppressed), as has been discussed in Section 3.3.1.
    The three components of the spin density and triplet superconductivity operators
have very diﬀerent representations in terms of the phase ﬁelds Φσ (x) and Θσ (x), and
their correlation functions diﬀer (at least formally) even in the exponents. This is so
because our abelian bosonization scheme treats σz on a special footing and breaks the
spin-rotation symmetry SU(2) down to U(1). In the absence of external magnetic ﬁelds
or spin-anisotropic interactions, the correlation functions must be spin-rotation invariant.
We see that this requires Kσ = 1. We shall assume this to be the case throughout this

                                                34
article except when stated to the contrary. Again, nonabelian bosonization would allow
to keep the spin-rotation invariance manifest at every stage of the calculation.
    The Green function’s α is invariant under Kρ → 1/Kρ and therefore does not depend in
an important way on the sign of the interaction. It is positive and, had one only g2 , would
be symmetric in attraction and repulsion. It is only g4 which slightly changes the modulus
of α when gi → −gi . α = 0 is possible only when the ﬂuctuations on all branches are free
– the system may still be interacting, though, if g4 6= 0. On the other hand, the many-
particle correlations do depend on the sign of the interactions: Kρ < 1 for repulsion,
and Kρ > 1 for attraction. Consequently, for repulsive interactions, the 2kF density
wave correlations decay more slowly than for free fermions (∼ x−2 ), while for attractive
coupling, the superconducting correlations decay slowest. At ﬁrst sight surprising will be
the fact that the correlation functions of density and spin density (as well as those for
singlet and triplet superconductivity) are strictly degenerate in the spin-rotation invariant
Luttinger model. This is quite counterintuitive, and nature is certainly richer than such
simple-minded results. On the other hand, the Luttinger liquid hypothesis requires that
this degeneracy of exponents carries over to more realistic models. The resolution of this
puzzle will be postponed to Chapter 4.
    If one is interested in ﬁnite temperatures, there are several possibilities. (i) One can use
the conformal invariance of the Luttinger model to map the T = 0 correlation functions
onto those at T 6= 0. This will be demonstrated in the next section, Eq. (3.158). (ii) One
can introduce Matsubara frequencies and calculate the boson propagators ∼ Dν (xτ ) at
imaginary times. (iii) One can simply use the Bose-Einstein distribution nBE (p) at ﬁnite
temperature in (3.77). This will decorate the integrals appearing in (3.79) and partly
those in (3.80) with factors coth(βvν p/2). The integrals can still be evaluated in terms
of logarithms of Gamma functions which, for small temperatures essentially add terms
ln{π[x ± ivν t]/ sinh(π[x ± ivν t]/vν β)} to (3.81). If x ≫ vν β, the hyperbolic sine will grow
exponentially, and correlation functions like (3.92) will therefore decay exponentially on
a scale set by the thermal coherence length ξT = πvF /T . If ξT ≫ 1/Λ, the power-laws
discussed before will still show up in the window in between.
    Transforming to k-space, one has to distinguish between the instantaneous and static
correlation functions. Given a correlation function in x-space

                     Ri (x) ∼ cos(nkF x)x−2+αi ,         R(t) ∼ t−2+α ,                 (3.101)

the instantaneous and static correlations behave as

       Ri (k, t = 0) ∼ (k − nkF )1−αi ,        Ri (k, ω = 0) ∼ (k − nkF )−αi ,          (3.102)

respectively, with equivalent formulae for the ω-dependent local and q = 0-functions. For
free fermions, the static correlations have a logarithmic divergence which is changed into
a power law divergence by even weak interactions. On the other hand, the instantaneous
correlations are nonsingular usually (though possibly enhanced), and singularities can
only be brought up by rather strong interactions. Divergences of this kind have been
observed both in computer simulations and in X-ray scattering on quasi-1D materials,
and will be discussed below.

                                              35
   We have not discussed charge-spin separation in detail yet. While it is contained in
the full expression for the Green function (3.83), it does not inﬂuence the long-distance
or time properties of the correlation functions. It is clear that this subtle feature of
1D interacting fermions can only be probed in dynamic, q- and ω-resolved correlation
functions.


3.4     Dynamical correlations: the spectral properties
        of Luttinger liquids
Fermi liquid theory breaks down in 1D for two reasons: (i) the anomalous dimensions
of the fermion operators, giving rise to the nonuniversal power laws discussed in the
preceding section, and (ii) charge-spin separation. Either of them is suﬃcient to kill all
quasi-particles in the neighbourhood of the Fermi surface, and both together will certainly
cooperate. However, all correlation functions of the previous section are aﬀected only by
the anomalous dimensions. Much eﬀort has been devoted to the study of these functions
over the last decade.
    On the other hand, for a long time much less has been known about the dynamical
(x − and t− resp. q − and ω−dependent) correlations. Also, how to measure charge-spin
separation? Since this phenomenon is characterized by diﬀerent propagation velocities
for charge and spin ﬂuctuations, fully dynamical correlation functions are needed to put
it into evidence. The single-particle spectral function ρrs (q, ω) is deﬁned as
                                          1
                            ρrs (q, ω) = − ImGrs (rk + q, µ + ω)                     (3.103)
                                          π
where Grs is the retarded Green function (3.71), (3.83). There is no principal diﬃculty
in computing this quantity. All we need to do is Fourier transform. This can be done
quite easily for spinless fermions or for the one-branch Luttinger liquid (g2 = 0) but is
laborious for the full model for s = 1/2-fermions we are most interested in.
    With spinless fermions we can single out the inﬂuence of the anomalous fermion di-
mensions. This is the generic structure [32, 53, 54, 59, 60]: At q = 0 (i.e. k = kF ),
ρ(0, ω) ∼| ω |α−1 , i.e. a power-law divergence (or cusp-singularity for α > 1) instead
of the δ-function in Fermi liquid theory. Clearly, as the 1D correlations increase from
zero, spectral weight is pushed away from the Fermi surface by the virtual particle-hole
excitations generated by g2 . Let us increase q. In a Fermi liquid, the δ-function would
disperse with q and broaden but essentially conserve its shape. In the Luttinger liquid,
ρ(q, ω) strongly deforms: There is a power law singularity ρ(q, ω) ∼ Θ(ω − vq)(ω − vq)γ0 −1
at positive frequencies (for q > 0) and a weaker singularity ∼ Θ(−ω − vq)(−ω − vq)γ0
at negative frequencies. In the positive frequency contribution – particle creation above
the Fermi surface – spectral weight of an incoming particle is boosted to higher energies
by the particle-hole excitations on both branches. The negative frequency contribution
describes the destruction of particles above the Fermi surface present in the ground state
as a result of particle-hole excitations. As q increases, the negative frequency part is
exponentially suppressed and all the spectral weight is transferred to positive frequencies.

                                            36
     For the “one-branch” Luttinger liquid (g2 = 0, charge-spin separation only), one has
ﬁnite spectral weight only at positive frequencies (for q > 0) between vσ q and vρ q with
inverse-square-root divergences at the edges [53, 59, 61]. At kF , the spectral function
reduces to δ(ω) and the momentum distribution is a step function with a jump of unity at
kF , in agreement with Luttinger’s theorem [4]. Although this seems to imply a Fermi liquid
it is clear that the physical picture is quite diﬀerent and that the notion of a quasi-particle
does not make sense because the δ-function does not survive the slightest displacement
from the Fermi surface. The incident electron decays into multiple particle–hole-like
charge and spin ﬂuctuations which all live on the same branch as the incoming fermion.
It is immediately apparent that n(k) and, more generally, any quantity depending on k
or ω alone will fail to detect charge-spin separation. It can be seen only in quantities
depending on both q and ω.
     We now turn to the spectral properties of the s = 1/2-Luttinger liquid [53, 54, 59, 60,
62]. We limit ourselves to the spin-rotation invariant case (γσ = 0). Fig. 3.6 displays the
dispersion of ρ(q, ω) for small q and α = 0.125. It is apparent that the spectral function
carries features both from the spinless fermions (synonymous with “anomalous fermion
dimensions”) and the one-branch problem (“charge-spin separation”). At very small q,
on the scale of the Figure, ρ looks pretty much like the spinless fermions’ function. As
q increases, the negative frequency weight (very small anyway) is transferred to positive
frequency but, most importantly, the generic two-peak structure of the spectral function
becomes apparent. The exponent of the singularity at vσ q is 2γρ − 1/2 while it is γρ − 1/2
at the vρ q-singularity and γρ at −vρ q. Since γρ = 1/16 here, the correction to the one-
branch case is quite insigniﬁcant here and the charge-spin separation aspect is clearly
dominant at ﬁnite q. The weight above/below ±vρ q originating from the anomalous
dimensions is barely visible. As α increases, the various power-law divergences weaken and
ﬁnally transform into cusp-singularities. At the same time, the spectral function becomes
much less structured, and spectral weight is shifted by the electronic correlations both to
above/below ±vρ q, more reminiscent of the spinless fermion problem. As the correlations
increase, the features originating from charge-spin separation are more and more obscured
by transfers of spectral weight over signiﬁcant energy scales. The important scale here is
the energy of the charge ﬂuctuations ±vρ q.
     The spectral function in Figure 3.6 obeys to the sum rule
                               Z ∞
                                     dωρrs (q, ω) = 1 for all q .                      (3.104)
                                −∞

The single-particle density of states N(ω) has already been discussed above. A local sum
rule is not satisﬁed by N(ω) unless g4k = 0 [51] as is the case for local interactions; in
general (long-range interactions), one has [53, 62, 63]
                    Z ∞
                                                      1 Z ∞ dk
                          dω [Nrs (ω) − N0 (ω)] = −            g4k (k) ,               (3.105)
                      0                             4πvF −∞ 2π
N0 (ω) = 1/2πvF being the noninteracting density of states. It is satisﬁed, however, by
the Tomonaga model with a ﬁnite bandwidth cutoﬀ [63]. Here, as usual, 0∞ dωN(ω) = n,
                                                                        R



                                               37
the particle density which is not changed by the interactions. The failure of the local
sum rule in the Luttinger model is certainly due to the introduction of the unphysical
negative-energy states which are sampled in the frequency integral.
     The many-particle spectral functions display similar features. Fig. 3.7 displays the
charge [S(q, ω)] and spin [χ(q, ω)] structure factors at 2kF and the charge factor at 4kF
[S4 (q, ω)] [53, 64]. Again there are power-law singularities at ω = ±vσ q and ±vρ q but
the functions now are symmetric because the CDW and SDW operators mix left- and
right-moving particles. At weak coupling, there are cusps, and only as Kρ < 1/2 do
they turn into divergences. Further interesting is the fact that the 2kF CDW and SDW
ﬂuctuations are sensitive to charge-spin separation but the 4kF -CDW is not. This is easy
to understand from the boson representation of these operators (3.89) – (3.96): the 2kF -
operators necessarily involve the Φσ or Θσ -ﬁelds in addition to Φρ . The only divergent
4kF -operator, however, only depends on the charge ﬁeld Φρ . 4kF -operators involving the
spin degrees of freedom are never divergent.


3.5      Alternative methods
3.5.1     Green function methods
There are alternative routes for solving the Tomonaga-Luttinger model, based on dia-
grammatic methods or equations of motion for the Green function. They provide an
interpretation of the novel physics of the Luttinger liquid from the standpoint of con-
ventional many-body theory, and therefore stress the formal similarities of Fermi and
Luttinger liquids while the bosonization approach more strongly emphasizes their diﬀer-
ences. Moreover, the connection between symmetries, conservation laws and the low-
energy structure of 1D Fermi liquids may become more apparent in this approach which
we outline now. It has been pioneered by Dzyaloshinskĭi and Larkin for a spinless variant
of the model, Eq. (3.52) [34] and followed and extended by others [18, 35, 46, 65].
    The power of the 1D conservation laws can be gauged from the fact that our ar-
guments for the breakdown of Fermi liquid theory in 1D in Section 2.1 were based on
divergences encountered in a perturbation treatment of the self-energy corrections to the
1D Green functions. As a consequence of Ward identities, vertex and self-energy correc-
tion cancel exactly in some quantities (such as density-density correlation functions) and
to such a large extent in others that meaningful answers are obtained and all results of
the bosonization approach reproduced.
    What are Ward identities? They are speciﬁc relations between the vertex operators
and (single or n-particle) Green functions of a theory, translating its conservation laws i.e.
its symmetries, into a Green function formalism which describes the dynamics of the ex-
citations. Vertex operators couple the charges and currents of a system to external ﬁelds.
They involve the corresponding density operator (e.g. ρ(p), jρ (p)) plus two (more gen-
erally 2n) fermions. The equation of motion for the vertex operator in general produces
Green functions involving even more particles. If the charge is conserved, however, ρ(p)
obeys the continuity equation. Combining it with the equation of motion of the simple

                                             38
vertex described, yields just the diﬀerence of the two single-particle propagators involved,
instead of complicated objects involving intermediate excitations. The principle is easy:
use the continuity equation associated with the conserved charge to reduce the equations
of motion for the object under consideration, then Fourier transform the resulting expres-
sion to recover an algebraic relation. This is particularly transparent for density-density
response which we study now before carrying on to the single-particle Green function.
    In Section 3.1.3, we had studied the conservation of charge and spin separately on
each branch of the dispersion. This generates the following continuity equations for the
charge and spin densities and currents from the Heisenberg equations of motion
                              ∂ν(p, t)
                            i            = [ν(p, t), H] = −vJν p jν (p, t)                 (3.106)
                                  ∂t
                              ∂ ν̃(p, t)
                            i            = [ν̃(p, t), H] = −vN ν p j̃ν (p, t)              (3.107)
                                  ∂t
with the total charge (ν = ρ) and spin (ν = σ) densities and currents
                                      X                           X
                            ν(p) =        νr (p) and jν (p) =              rνr (p) .       (3.108)
                                      r                            r

In the Green function approach, it is the physical charge and spin densities which enter
the various operators. For this reason, we deﬁne in this section, and only in this section

                                          νr (p) = ρr↑ (p) ± ρr↓ (p)                       (3.109)

at variance with the remainder of this paper. This will avoid a confusing proliferation of
        √
factors 2 due to the diﬀerent deﬁnition in (3.22). The “axial” charge and spin densities
and currents (named after similar constructions appearing in ﬁeld theory) are
                                      X                            X
                            ν̃(p) =       rνr (p) and j̃ν (p) =             νr (p)         (3.110)
                                      r                                r

and are identical to the usual currents and charges, Eq. (3.108), respectively. vJν and vN ν
are the velocities for charge and current excitations [3] deﬁned earlier (3.32).
   Notice in passing that both equations can be put together to produce the equations
of motion of a harmonic oscillator [46]
                                 ∂ 2 ν(p, t)
                                       2
                                             + vJν vN ν p2 ν(p, t) = 0 ,                   (3.111)
                                     ∂t
indicating that the charge (spin) density ﬂuctuations are the elementary excitations of the
                                                                √
systems which propagate with an eﬀective (sound) velocity vJν vN ν . The conservation
laws thus completely determine the dynamics of our system.
    For illustration, we investigate the density-density correlation function
                                                                  i
                   Z ∞
    Rρρ (q, ω) =         dteiωt Rρρ (q, t) ,        Rρρ (q, t) = − hT ρ(q, t)ρ(−q, 0)i .   (3.112)
                   −∞                                             L
T is the time ordering operator. Applying i∂t to this equation and using (3.106), we have
                  ∂Rρ (q, t)  i                            1
              i              = vJρ qhT jρ (q, t)ρ(−q, 0)i + δ(t)h[ρ(q), ρ(−q)]i            (3.113)
                    ∂t        L                            L

                                                     39
where the last term originates from taking the time derivatives of the step functions
implied by time ordering but vanishes on account of the commutator algebra Eq. (3.17).
A ﬁrst Ward identity is obtained from the Fourier transform

                                  ωRρρ (q, ω) − vJρ qRjρ ρ (q, ω) = 0 .                                           (3.114)

 Similar Ward identities can be derived for Rjρ ρ (q, ω) (with the diﬀerence that [jρ (q), ρ(q)]
6 0) and for the axial charges and currents (3.110). The second derivative of the density-
 =
 density correlation function is then

                            ∂ 2 Rρρ (q, t)             2              2vJρ q 2
                       −                   = v  v
                                              Jρ N ρ q   Rρρ (q, t) +          δ(t) ,                             (3.115)
                                 ∂t2                                    π
which is Fourier transformed into
                                           2 vJρ q 2             √
                       Rρρ (q, ω) =           2    2  2
                                                        with vρ = vJρ vN ρ .                                      (3.116)
                                           π ω − vρ q

Eq. (3.113) is an example of a very simple – yet manifestly powerful – Ward identity.
Metzner and Di Castro [46] give many more.
   Now consider the single-particle Green function

                                   Grs (k, t) = −ihT crs (k, t)c†rs (k, 0)i                                       (3.117)

which obeys the equation of motion [35]
                                    X Z dΩ h
                                                                        ν
(ω − rvF k)Grs (k, ω) = 1 + i                     g2ν (1 − 2δν,σ δs,↓ )F−rrs (k, ω; k + q, ω + Ω; q, Ω)
                                     ν,q    2π
                                                    ν
                             +g4ν (1 − 2δν,σ δs,↓ )Frrs (k, ω; k + q, ω + Ω; q, Ω)] .                             (3.118)

To get (3.118), take i∂t Grs (k, t) using the Heisenberg equation of motion and Fourier
transform; deriving the T -operator gives the 1, taking the commutator with H0 gives
rvF kGrs , and the commutators with H2 and H4 and using (3.22) to go from the ρrs to
the νr , gives the vertex functions

                    Frν′ rs (k1 , t1 ; k2 , t2 ; qt) = −hT νr′ (qt)crs (k2 , t2 )c†rs (k1 , t1 )i                 (3.119)

Continuing now without using (3.106) would lead to a hopeless hierarchy of equations.
However, (3.119) obeys a remarkable Ward identity

qFrν′ rs (k, ω; k + q, ω + Ω; q, Ω) = rπ(1 −2δν,σ δs,↓ )Rνr′ νr (q, Ω) [Grs (k, ω) − Grs (k + q, ω + Ω)]
                                                                                                 (3.120)
which helps to simplify the problem. The one-branch density-density correlation function
                                                                    
                        i
                            Z                                        rq ω+r(v2Nν +vJ ν2)q/2        for r = r ′
                                                                        π       ω −(vν q)
     Rνr′ νr (q, ω) = −         dteiωt hT νr′ (qt)νr (−q0)i =           1 (vJ ν −vNν )q 2 /2
                        L                                           
                                                                        π ω 2 −(vν q)2
                                                                                                    for r = −r ′
                                                                                                             (3.121)


                                                        40
can itself be derived from (3.113) and related Ward identities. One can now eliminate
the vertex function from (3.118) and close the equation of motion for the Green function.
The resulting integral equation is then solved by Fourier transforming back to a real space
diﬀerential equation and taking into account boundary and analyticity conditions. The
result agrees with the expression (3.83) up to details of cutoﬀ procedures. Notice that
the Ward identity for Frν′ rs (3.120) involves the chiral (charge and spin) density operators
νr . It therefore is the consequence of two separate Ward identities, one for the density
   r νr which is present also in the many-body problem in higher dimensions, and a new
P

one involving the axial density r rνr which is new and related to the disconnected 1D
                                   P

Fermi “surface” and the absence of backscattering in the Luttinger model.
     In these two examples, we have rederived results via Ward identities which are also
quite easy to derive from bosonization. There are others where the derivation via Ward
identities are easier than with bosonization. An example is the intra- or inter-branch
polarization bubble Πρrr′ (q, ω) which is related to the density correlation function (3.121)
by Dyson’s equation

                   Rρr ρr′ (q, ω) = Πρrr′ (q, ω) +         Πρrt (q, ω)gtt′ ρ Rρt′ ρr′ (q, ω) ,
                                                     X
                                                                                                 (3.122)
                                                     tt′

represented graphically in Figure 3.4. grr′ρ denotes g2ρ or g4ρ . The polarization Πρrr′ is
given by the irreducible vertex Λρrr′s and the exact single-particle Green functions Gr′ s
                   X Z dkdΩ
 Πρrr′ (qω) = −i                Λρrr′ s (k, Ω; k + q, ω + Ω; q, ω)Gr′s (k, Ω)Gr′ s (k + q, Ω + ω) (3.123)
                   s    (2π)2

as shown in Fig. 3.5. Λ is obtained from F by amputating the external fermion legs, i.e.
dividing by the product of the two Green functions involved in (3.120) and taking only
the interaction-irreducible part of F . Π must be a wildly divergent function because the
Green functions have divergences and the vertex corrections certainly have divergences,
too! This is not true, however, and with the Ward identity (3.120), converted into one
for Λ, one obtains the simple, ﬁnite results

         Πρr,−r (q, ω) = 0 ,                                                                     (3.124)
                            −i     X Z dkdΩ
          Πρrr (q, ω) =                       [Grs (k, Ω) − Grs (k + q, Ω + ω)]
                         ω − rvF q s   (2π)2
                         r    q
                       =            ≡ Πρ(0)
                                       rr (q, ω) .                                               (3.125)
                         π ω − vF q
This result is remarkable: all vertex and self-energy corrections have cancelled out as
a consequence of the Ward identities, and the polarization is identical to Πρ(0) of free
fermions. Eq. (3.122) then reduces to a standard RPA summation, showing that RPA
is exact for the density-density correlation functions. Moreover, the charge and spin
susceptibilities limq→0 limω→0 Rνν (q, ω) are ﬁnite, in agreement with (3.62). The Luttinger
liquids therefore are “normal” metals. This is entirely due to the conservation laws and
Ward identities which enforce the cancellation of all divergences which would occur in a
diagrammatic development.

                                                     41
    Of course, one can also compute all the many-particle Green functions, and construct
the same picture as in the preceding sections using the standard many-body formalism.
We reemphasize that in the exact solutions we had found, both the Ward identities related
to the charges (currents) and to the axial charges (currents) were essential. It is the latter
one that gives the one-dimensional Fermi liquids their special properties.
    Similar results can also be obtained by more diagram-based techniques [18, 34, 65]. In
this case, the Ward identities are expressed by the theorem that closed fermion loops with
more than two fermion lines vanish (equivalent in the vanishing of the transverse current
in quantum electrodynamics). The limitation to forward scattering only in the Luttinger
model implies that a closed fermion line has all of its parts on a deﬁnite branch r.
    Moreover, one can use the Ward identities to construct a ﬁeld-theoretical renormaliza-
tion group formulation of the Luttinger model with respect to the free Fermi gas [46, 66].
This veriﬁes that all couplings are dimensionless, and that consequently, the beta-function
                                                   !
                                             ∂g
                                    β(g) = Λ           ≡0                             (3.126)
                                             ∂Λ
at the Luttinger liquid ﬁxed point. The density operators do not acquire anomalous
dimensions, and the coupling constants are renormalization group invariants. It also
veriﬁes the correctness of the earlier scaling Ansatz [18].

3.5.2     Other bosonic schemes
In Section 3.2.2, we have solved the Luttinger model via a boson representation of the
Hamiltonian and of the fermion operators. Other bosonic approaches, based on functional
integrals and a Hubbard-Stratonovich decoupling have been developed in the past [61, 67].
They are closer to the methods used in quantum ﬁeld theory than Haldane’s operator
approach. They also provide an exact solution of the model, and reproduce all the results
obtained by the two methods presented above. Which one to use is rather a matter of
taste and background than of the speciﬁc nature of the problem at hand.
    A bosonic scheme widely used for strongly correlated fermions are “slave bosons” and
one may naturally wonder if there is any relation to the bosonization discussed above.
Slave bosons are usually applied to problems where double occupancy of lattice sites is
dynamically forbidden because of strong electronic repulsion. One tries to circumvent the
diﬃcult treatment of inequality constraints (such as hni i ≤ 1) by introducing additional
particles into an enlarged Hilbert space whereby the inequality constraint translates into
an equality constraint which can be solved by Lagrange multipliers. Properties are then
obtained by projecting back onto the physical Hilbert space. From these remarks, it is
quite clear that slave bosons and the Tomonaga-Luttinger bosons are two distinct entities.
While the latter are the elementary excitations of the 1D Fermi liquid, the former are, in
the ﬁrst place, a bookkeeping device to obtain good approximations to fermionic proper-
ties. Still, slave bosons have been used successfully, together with standard bosonization,
to obtain low-energy properties of, e.g., the U = ∞ Hubbard model [68]. A deeper knowl-
edge of diﬀerences and similarities of both types of bosons is, however, just beginning to
emerge [69].

                                             42
3.6      Conformal field theory and bosonization
In the language of the theory of phase transitions, one-dimensional Fermi liquids are
critical at T = 0. An arbitrary system, close to a second order phase transition, exhibits
strong precursor ﬂuctuations of the ordered phase, whose typical size is measured by the
correlation length ξ ∼ |(T −Tc )/Tc |−ν which diverges as the critical point Tc is approached.
Thermodynamic properties (speciﬁc heat, magnetization, etc.) exhibit similar divergences
whose sole origin is the divergence in ξ. Therefore, their critical exponents can be related
by scaling relations to ν and the dimension of space. These scaling relations only depend
on the symmetry of the theory (universality). At the critical point, correlation functions
decay as power-laws of distance and time with some critical exponents which generally
can be calculated from the model under consideration [70]. The power-law correlations of
one-dimensional Fermi liquids found in Section 3.3, show explicitly that we have a T = 0
quantum critical point.


3.6.1     Conformal invariance at a critical point
Conformal ﬁeld theory is a powerful means of characterizing universality classes of critical
systems in 2D statistical mechanics or 1D quantum ﬁeld theories [time playing the role
of a second dimension, these theories in fact are (1+1)D] in terms of a single dimension-
less number, the central charge c of the underlying Virasoro algebra [29]. The critical
exponents are the scaling dimensions of the various operators in a conformally invariant
theory and, generically, are fully determined by c. A notable exception are theories with
central charge c = 1 such as the Gaussian model, of particular relevance to the problems
considered here, where the exponents (scaling dimensions) depend on a single eﬀective
coupling constant of the model. Both the central charge and the scaling dimensions can
be computed from the ﬁnite-size scaling properties of the ground state energy and the
low-lying excitations [29, 71]. This is important because these quantities can be computed
accurately either by Bethe Ansatz (for models solvable by the technique) or, in any case,
by numerical diagonalization.
    What are the symmetries of systems at a critical point? It is certainly translationally
and rotationally invariant. Quantum ﬁeld theories, in addition are Lorentz invariant but
in (1+1)D, Lorentz invariance reduces to rotations in the x = (x, t)-plane. As we have
seen above, a system at criticality, in addition is characterized by scale invariance,

                                         x → λx .                                     (3.127)

It turns out that the combined rotational and scale invariance implies that the system
is invariant under a wider symmetry group, the global conformal group. On a classical
level, conformal transformations are general coordinate transformations which leave the
angles between two vectors invariant. In dimension D > 2, the global conformal group is
ﬁnite-dimensional, and so is the associated Lie algebra of its generators. There is a ﬁnite
number of constraints, and these allow for an evaluation of the two-point and three-point
correlation functions, but not for the higher ones.

                                             43
   The situation is diﬀerent in two dimensions, where all correlation functions can be
determined. Consider a general coordinate transformation

                                   x → x′ = x + ξ(x) .                                                 (3.128)

For this transformation to be conformal, ξ must satisfy certain constraints which can
be expressed in a diﬀerential equation (Killing-Cartan equation). In general dimension
D, this leaves for ξ(x) a polynomial of second degree in x (with tensor coeﬃcients). In
two dimensions, however, the Killing-Cartan equation reduces to the Cauchy-Riemann
equation, and therefore all analytic functions are allowed for conformal transformations.
This group of transformations, called local conformal group, is much wider than the global
conformal group encountered before. It is then natural to switch to complex variables
z, z̄ = x1 ± ix2 , so that we have

                  z → z + ξ z (z) = f (z) ,             z̄ → z̄ + ξ¯z̄ (z̄) = f(z̄)
                                                                              ¯     .                  (3.129)

To determine the algebra corresponding to the local conformal group, we need the com-
mutation relations of the generators of the transformations. Since ξ z (z) and f (z) are
analytic, they can be expanded in a Laurent series
                                                  ∞
                                      ξ z (z) =          ξn z n+1
                                                  X
                                                                                                       (3.130)
                                                  n=−∞

                            ¯
[and a similar equation for ξ(z̄)], and we ﬁnd the generators of the local conformal trans-
formations

               ℓn (z) = −z n+1 ∂z ,          ℓ̄n (z̄) = −z̄ n+1 ∂z̄ ,               n ∈ ZZ .           (3.131)

These generators obey the local conformal algebra

    [ℓm , ℓn ] = (m − n)ℓm+n ,        [ℓ̄m , ℓ̄n ] = (m − n)ℓ̄m+n ,                [ℓm , ℓ̄n ] = 0 .   (3.132)

This inﬁnite dimensional algebra is called the classical Virasoro algebra. (The global
conformal algebra is generated by {ℓ−1 , ℓ0 , ℓ1 }.) Since the two algebras are independent,
one may take z and z̄ as independent, corresponding to the natural variables for left- and
right-moving objects; the physical theory then lives on z̄ = z ⋆ .
    We now go to the quantum (or statistical mechanics) case. How do ﬁelds and corre-
lation functions of a quantum ﬁeld theory transform under conformal transformations?
In general, an inﬁnitesimal symmetry variation in a ﬁeld φ is generated by δξ φ = ξ[Q, φ]
where Q is the conserved charge associated with the symmetry. Local coordinate trans-
formations are generated by the charges constructed from the stress-energy tensor Tij .
Rotational invariance constrains Tij to be symmetric, and scale invariance requires its
trace to vanish; then conformal invariance does not impose additional constraints showing
that it is implied by rotational and dilatational invariance. Translating these conditions
into the complex variables z and z̄, one can show that only the diagonal components

                          T (z) ≡ Tzz (z)         and     T̄ (z̄) ≡ T̄z̄ z̄ (z̄)                       (3.133)

                                                  44
do not vanish. In the radial quantization scheme, the conserved charge then becomes
                              1 I h                          ¯
                                                                   i
                        Q=          dzT (z)ξ(z) + dz̄ T̄ (z̄)ξ(z̄)   ,          (3.134)
                             2πi
which generates a ﬁeld variation
                      1
                           Z
                                                                   ¯
                            n                              h                       io
     δξ,ξ̄ φ(w, w̄) =        dz [T (z)ξ(z), φ(w, w̄)] + dz̄ T̄ (z̄)ξ(z̄), φ(w, w̄)    . (3.135)
                     2πi
In general, it is diﬃcult at this point to proceed further without having explicit expressions
at hand. There is, however, a distinctive class of ﬁelds, to be called primary ﬁelds, for
which
         δξ,ξ̄ φ(w, w̄) = h∂z ξ z (z) + ξ z (z)∂z + h̄∂z̄ ξ¯z̄ (z̄) + ξ¯z̄ (z̄)∂z̄ φ(w, w̄)
                                                                                 
                                                                                              (3.136)
which can be recognized as the inﬁnitesimal version of
                                                !h           !h̄
                                           ∂f         ∂ f¯                  ¯ w̄)) .
                          φ(w, w̄) →                               φ(f (w), f(                (3.137)
                                           ∂w         ∂ w̄
All other ﬁelds are called secondary ﬁelds. h and h̄ are two real numbers, the conformal
weights of the ﬁeld φ. The combinations ∆ = h+ h̄ and s = h− h̄ are the scaling dimension
and spin of the ﬁeld φ, respectively [if one works in a basis of eigenstates of L0 and L̄0 , the
combinations L0 + L̄0 and i(L0 − L̄0 ) are generators of dilations and rotations, respectively].
Eq. (3.137) is the transformation law of a complex tensor of rank h, h̄. Normally, such
a tensor transforms with integer powers of ∂f /∂z and ∂ f¯/∂ z̄ which are the number of
z and z̄ indices; here, however, one could conceive also noninteger exponents. They are
called anomalous dimensions. As a consequence, the scaling dimension of the ﬁeld φ also
can become anomalous. We have seen examples in the Luttinger model in the preceding
section.
    One reason for the special status of primary ﬁelds is that one can derive (in fact in any
dimension) some of their correlation functions from the transformation property (3.136).
The two-point function G(2) = hφ1 (z1 , z̄1 )φ2 (z2 , z̄2 )i must be invariant under a conformal
transformation (3.129)
                        δξ,ξ̄ G(2) (zi , z̄i ) = h(δξ,ξ̄ φ1 )φ2 i + hφ1 δξ,ξ̄ φ2 i = 0 .      (3.138)
Using the transformation law (3.136), one can derive a diﬀerential equation for G(2) which
can be solved to yield
                                                    C12
                                 G(2) (zi , z̄i ) = 2h 2h̄ ,                       (3.139)
                                                   z12 z̄12
where zij = zi − zj and C12 ∝ δ∆1 ,∆2 is a constant. The three-point function G(3) can
be determined in a similar manner, but the four-point function, at the present stage of
development, can only be determined up to a function of the cross-ratio z12 z34 /z13 z24 .
    Not all ﬁelds are primary ﬁelds. For the primary ﬁelds to transform according to
(3.136), the operator product expansion (OPE) of the stress-energy tensor with φ for
short distances must go as
                                        h                 1
                T (z)φ(w, w̄) =             2
                                              φ(w, w̄) +     ∂w φ(w, w̄) + . . . ,            (3.140)
                                    (z − w)              z−w

                                                      45
where radial ordering is implied, and there is an equivalent equation for the anti-holomorphic
(left-moving) piece of the stress-energy tensor. (In the following, we always imply the ex-
istence of such equivalent equations for the anti-holomorphic dependences.) A secondary
ﬁeld has a higher than double-pole singularity in its OPE with T (z). The most prominent
representative is T (z) itself
                                   c/2          2              1
                 T (z)T (w) =           4
                                          +         2
                                                      T (w) +     ∂T (z) .           (3.141)
                                (z − w)     (z − w)           z−w
The coeﬃcient c (= c̄ ≥ 0) is called the central charge. It cannot be determined by
the requirement of conformal invariance alone, and will depend on the theory studied.
Diﬀerent values of c will imply diﬀerent universality classes.
    The nonvanishing of c represents an anomaly which often occurs in problems with
local symmetries. It means that a classical symmetry cannot be implemented quantum-
mechanically due to renormalization eﬀects. Therefore not all ﬁelds but only the primary
ﬁelds transform according to (3.136). As will be seen below, T (z) determines the change in
action under a local coordinate transformation. In a path-integral formalism, the anomaly
in T then implies that the complete measure cannot be made conformally invariant. The
anomaly is also called Schwinger term. As examples, for a free boson φ(z), T (z) =:
[∂z φ(z)]2 : /2 and c = 1; free real (Majorana) fermions ψ(z), relevant for the 2D Ising
model, have T (z) =: ψ(z)∂z ψ(z) : /2 and c = 1/2; ﬁnally, free complex (Dirac) fermions
Ψ(z), relevant for the Luttinger model, have T (z) = i : [∂z Ψ† (z)]Ψ(z) − Ψ† (z)∂z Ψ(z) : /2
and c = 1 like the bosons.
    This anomaly has important consequences for the algebra of the generators of the local
conformal transformations on the quantum level. Just as above on the classical level, one
can derive the algebra of the generators from a Laurent expansion of the stress-energy
tensor                                    ∞
                                                    Ln z −n−2 .
                                            X
                                  T (z) =                                            (3.142)
                                            n=−∞

Using (3.141), we obtain the Virasoro algebra with central extension c
                                                  c 3
                    [Ln , Lm ] = (n − m)Ln+m +       (n − n)δn+m,0 ,
                                                 12
                                                  c̄
                    [L̄n , L̄m ] = (n − m)L̄n+m + (n3 − n)δn+m,0 ,                   (3.143)
                   h          i                  12
                     Ln , L̄m = 0 .

The classical Virasoro algebra is recovered for c = 0. Every conformal quantum ﬁeld
theory deﬁnes a representation of (3.143) with some central charge c, c̄. The Ln are the
generators of transformations of quantum ﬁelds associated with the monomial of degree
n + 1 in z. For ξ z (z) = −ξn z n+1 , we have

                                δφ(z, z̄) = −ξn [Ln , φ(z, z̄)] .                    (3.144)

Unitarity constrains the generators to satisfy

                                          L†m = L−m                                  (3.145)

                                               46
and regularity of the stress-energy tensor at the origin implies

                 Lm |0i = 0 ,     m ≥ −1         and       L†m |0i = 0 ,     m ≤ −1   (3.146)

in their action on the vacuum |0i.
    There are two more important properties of the stress-energy tensor. Under a local
conformal transformation to z ′ = f (z), it transforms as
                                                      !2
                                     ′      dz ′                 c
                      T (z) → T (z) =                 T (z ′ ) + {z ′ , z} ,          (3.147)
                                             dz                 12
                                  3 ′        2 ′ 2
                                 ∂z z     3(∂z z )
                     {z ′ , z} =        −               .                             (3.148)
                                 ∂z z ′   2(∂z z ′ )2

The ﬁrst term in (3.147) translates the fact that T (z) is a ﬁeld of conformal weight (2, 0)
in agreement with (3.141) above, while the second term contains the conformal anomaly.
(3.148) is known as the Schwarzian derivative.
    We now turn to the representations of the Virasoro algebra, i.e. the states of our
Hilbert space. In general, the representations of symmetry groups are constructed from
highest weight vectors (states). Such a highest weight state |hi is created by the action
of a holomorphic primary ﬁeld φ on the vacuum, at the origin

               |hi = φ(0)|0i ,     L0 |hi = h|hi ,            Ln |hi = 0 ,    n>0 .   (3.149)

|hi is thus eigenstate of L0 . The Ln , n > 0 are the lowering operators annihilating |hi.
The corresponding raising operators are L−n , n > 0 and, acting on |hi, generate the
descendant states

                     L−n1 . . . L−nk |0i =
                                         6 0 ,             1 ≤ n1 ≤ . . . ≤ nk .      (3.150)

They form a basis for the representation vector space. The eigenvalue of L0 on the state
(3.150) is h + n1 + . . . + nk . The highest weight state |hi has the lowest eigenvalue among
all the states that can be created out of it by acting with the raising operators. It is the
ground state in a given sector of the theory. The descendants are the excited states. The
Ln (n > 0) act as an inﬁnite number of harmonic oscillator annihilation operators, and
the L†n = L−n then are the creation operators. The level of the state (3.150) is ki=1 nk ,
                                                                                      P

and the level associated with an operator L−n is n. The number of basis vectors on a
given level N is P (N), the number of partitions of N. The conformal weight of all the
descendant states on level N is h + N. The vector space generated from |hi is called
Verma module.
    All states (and ﬁelds) in a conformal ﬁeld theory can be grouped into conformal families
(towers). They consist of a highest weight state |hi and all the descendant states generated
by the application of the raising operators L−n . The diﬀerent highest weight states are
obtained from the action of the diﬀerent primary ﬁelds φn (z) [or, more generally, φn (z, z̄)]
on the vacuum according to (3.149). The conformal families oﬀer a very convenient way
to classify the excitations in the system and the spectrum of the scaling dimensions.

                                                 47
    All correlation functions involving secondary ﬁelds can be calculated from those con-
taining primary ﬁelds only, by acting on them with a diﬀerential operator obtained from
the transformation property (3.144). From global conformal invariance, we also know the
two-point correlation functions of the primary ﬁelds, Eq. (3.139), and can construct the
three-point function according to the same scheme. What about the n-point function for
primary ﬁelds? It may happen that on a given level of the theory, say k, the states are not
linearly independent but that there is a combination of states that vanishes (the family
is then said to be degenerate at level k). The equation describing this degeneracy can
then be transformed into a diﬀerential equation to be satisﬁed for an arbitrary correlation
function of primary ﬁelds, if at least one of them is degenerate. In this way, it is possible
to obtain, for conformal ﬁeld theories with degenerate families, all correlation functions.
    Unitary representations of the Virasoro algebra only exist for certain values of c and
h

              c≥1     ,   h≥0                                                         (3.151)
                                                                                  2
                                6                 [(m + 1)p − mq] − 1
                or c = 1 −           , hp,q (m) =                                     (3.152)
                          m(m + 1)                     4m(m + 1)
           with m = 3, 4, . . . , 1 ≤ p ≤ m − 1 , 1 ≤ q ≤ p ,

and at least the discrete series (3.152) does indeed have degenerate families. The models
belonging to this discrete series have quantized critical exponents [72] contained in (3.152).
The most famous among them is the 2D Ising model with c = 1/2.
   Up to now, we have implicitly assumed that our ﬁelds are deﬁned in the inﬁnite z-
plane. What happens when we consider ﬁnite systems? From Eq. (3.146), we deduce
that                                      ∞
                                                   Lm
                                         X                
                              hT (z)i =         0 m+2 0 = 0                            (3.153)
                                        m=−∞      z
in the inﬁnite complex z plane. Now use the exponential transformation
                                         2πi                        L
                                                
                           z = exp           u       ,        u=       log z          (3.154)
                                          L                        2πi
to map the inﬁnite z-plane onto a strip (u) of width L with periodic boundary conditions.
Observe that under this transformation, the mode expansion (3.142) simply becomes a
Fourier transformation, and the Virasoro generators Ln become the Fourier coeﬃcients of
the stress-energy tensor. We obtain
                                                                             !2
                                                    c                   dz
                                                                   
                          Tstrip (u) = Tplane (z) − {u, z}                            (3.155)
                                                   12                   du

and with (3.153) therefore
                                                     c 2π 2
                                                             
                                     hTstrip (u)i =           .                        (3.156)
                                                    24 L
The stress-energy tensor measures the cost of energy [change in the action δS = (−1/2π) ×
  Tij ∂i ξj d2 r] of a change in metric. One can now calculate the change in energy associated
R



                                                     48
with another (nonconformal) transformation, a horizontal dilatation of the u-strip [u′1 =
(1 + ε)u1, u′2 = u2 ] which changes the length of the system, and integrate to ﬁnd
                                                                     cπ
                                                  E(L) − E(∞) =         ,                              (3.157)
                                                                     6L
where E(L) is the energy per unit length [71]. This formula is extremely important
because it allows us to determine the value of the central charge from calculations on
ﬁnite systems! Moreover, it suggests an interpretation of the anomaly (3.148) as a Casimir
eﬀect, i.e. a shift in the energy due to the ﬁnite geometry of the system. The mathematical
reason is that the local conformal transformations (with the exception of the global ones)
are (i) usually not deﬁned in all points of the complex plane and (ii) are not one-to-one
mappings of the complex plane on itself.
    The exponential transformation (3.154) is also important to obtain the scaling dimen-
sions of primary ﬁelds from ﬁnite-size calculations [73]. The two-point correlation function
of a primary operator φ(z, z̄) with conformal weights h, h̄ transforms under a conformal
transformation (3.154) into

                                                                (π/L)2∆
        hφ(u, ū)φ(u′ , ū′)i =                                                                    .   (3.158)
                                         (sinh[π(u − u′ )/L])2h (sinh[π(ū − ū′ )/L])2h̄

[Notice in passing: correlation functions at ﬁnite temperature 1/β must satisfy periodic
boundary conditions in the Matsubara time τ = it. (3.158) then gives directly the ﬁnite
temperature expressions for the correlation functions of the preceding section if we put
L = 2vβ, as suggested in Section 3.3.] Writing u = u1 + iu2 and going on the physical
surface ū = u⋆ , this can be expanded as
                                                      ∞
                                                  2∆ X
                                             2π
                                         
                  ′   ′
      hφ(u, ū)φ(u , ū )i =                                  aN aN̄ exp[−2π(∆ + N + N̄)(u1 − u′1 )/L]
                                             L      N,N̄ =0

                               × exp[2πi(s + N − N̄)(u2 − u′2 )/L] .                                   (3.159)

Here, ∆ and s are scaling dimension and spin of the operator, respectively. The correlation
function can also be calculated using operators φ̂(u2 ) which act on the states |n, ki of a
Hilbert space
                                                                          ′
          hφ(u)φ(u′)i =                 h0|φ̂(u2 )|n, kie−(En −E0 )(u1 −u1 ) hn, k|φ̂(u′2 )|0i ,
                                X
                                                                                                       (3.160)
                                    n

where the matrix elements depend on u2 as exp(iku2 ) with momentum k. Comparing
(3.159) with (3.160), we ﬁnd that energies and momenta scale as
                                                       (L)
                          En(L) (N, N̄ ) = E0                 + 2πv(∆ + N + N̄ )/L ,                   (3.161)
                              (L)                      (∞)
                          k         (N, N̄ ) = k              + 2π(s + N − N̄ )/L .                    (3.162)

Here, the energies are taken on the system of length L, and v is the velocity of the
excitations. In (3.162), we have allowed for a ﬁnite momentum k (∞) of the highest weight
state in the conformal tower built by the primary ﬁeld φ, extrapolated to the inﬁnite

                                                              49
system. Eqs. (3.161), (3.162) show that on a ﬁnite strip, each primary operator generates
the whole spectrum of scaling dimensions and momenta of the conformal tower, i.e. also
those of the descendant operators at level (N, N̄).
    There are thus two ways to obtain the scaling dimensions and correlation functions
of a conformal ﬁeld theory; (i) one can construct the stress-energy tensor; from its trans-
formation properties (3.147) or its OPE with itself (3.141), one can deduce c, and from
its OPE with other ﬁelds one obtains their scaling dimensions (3.140). (ii) one can study
the ﬁnite size scaling behaviour of the ground state and a set of excited states, and ob-
tain the central charge from Eq. (3.157). Going back now from z, z̄ = z ⋆ to (x, t) and
extrapolating L → ∞, the correlation functions of a primary (h, h̄) ﬁeld φ(xt) are then
given from (3.139)
                                                 (∞)     (∞)
                                              eik x eik̄ x
                          hφ(xt)φ(00)i =                                            (3.163)
                                          (x + ivt)2h (x − ivt)2h̄
and those of the descendant ﬁelds have the same structure with the corresponding (h +
N, h̄ + N̄).

3.6.2    The Gaussian model
The ﬁrst problem beyond the discrete classiﬁcation scheme (3.152) – also the most impor-
tant in the context of the present article – is given by theories with central charge c = 1
and realized by free bosons, precisely the spinless Luttinger model, or the Gaussian model
of statistical mechanics. Here, we give a conformal ﬁeld theory analysis. The action for
free bosons is given by
                             1
                               Z
                      S=         dz dz̄(∂z Φ)(∂z̄ Φ) ,     Φ ≡ Φ(z, z̄) ,           (3.164)
                            2π
and the equivalence to the Luttinger model is clear when represented in terms of phase
ﬁelds (3.49) or (3.58). The model is critical and manifestly conformally invariant, and
remains so even upon introducing a dimensionless coupling constant g as a prefactor in S,
for all values of g [cf. below after Eq. (3.187)]. The solution of the equations of motion
can be given in terms of left- and right-moving (holomorphic and anti-holomorphic) ﬁelds
Φ(z, z̄) = [φ(z) + φ̄(z̄)]/2 where z, z̄ = x ± iy. Their correlation functions are
        hφ(z)φ(w)i = − log(z − w) ,          hφ̄(z̄)φ̄(w̄)i = − log(z̄ − w̄) .       (3.165)
The ﬁelds φ(z) are not conformal ﬁelds, but their derivatives are. To show this, we
need the stress-energy tensor which can be identiﬁed from the change in the action δS =
(−1/2π) Tij ∂i ξj d2 r under a conformal transformation r → r + ξ of the ﬁelds φ as (after
         R

going to the complex z-plane)
                                         "           !             !       #
                 1               1           d        d   1
        T (z) = − : [∂φ(z)]2 :≡ − lim ∂φ z +   ∂φ z −   − 2                      ,   (3.166)
                 2               2 d→0       2        2  d
where the identity deﬁnes the normal-ordering convention. From the OPE of φ with the
stress-energy tensor, we ﬁnd
                                     ∂φ(w)       1
                     T (z)∂φ(w) =           2
                                              +     ∂ 2 φ(w) + . . . ,               (3.167)
                                    (z − w)     z−w

                                             50
which, comparing with Eq. (3.140), indeed identiﬁes ∂φ as a primary ﬁeld with conformal
weights (1, 0). It is now possible to write down a mode expansion (Laurent series) for the
ﬁeld ∂φ(z)
                                     ∞
                                          Jn                 dz n
                                    X                     I
                 J(z) ≡ i∂φ(z) =          n+1
                                               ,     Jn =       z J(z) .          (3.168)
                                   n=−∞ z                   2πi
Again, on a cylinder, i.e. periodic boundary conditions for a (1+1)D ﬁeld theory, the Jn
simply are the Fourier components of the current J(z). Their algebra from (3.168) is

                                    [Jn , Jm ] = nδn+m,0 ,                         (3.169)

the U(1)-Kac-Moody algebra. We immediately note that the algebra of the Jn , (i) up to
the factor n which can be absorbed into a redeﬁnition of Jn , is a bosonic one, and (ii)
is identical to the algebra satisﬁed by the Luttinger density operators ρrs , Eq. (3.17).
Physically, this identiﬁes the Jn as (chiral) density ﬂuctuation modes or currents, which
is the same because we look at a single branch only. The modes with n < 0 are creation
operators, and those with n > 0 are annihilation operators

                             Jn |0i = 0        for       n>0 .                     (3.170)

The correlation function of the currents J(z) = i∂φ(z) is
                                                         1
                                  hJ(z)J(w)i =                                     (3.171)
                                                     (z − w)2

from (3.139) and the conformal weights (1, 0). Of course, for free bosons, these results
can also be obtained directly by simply calculating a Gaussian integral.
   Eq. (3.169) is a special case of a more general expression

                           [Jna , Jm
                                   b
                                     ] = if abc Jn+m
                                                 c
                                                     + knδ ab δn+m,0               (3.172)

satisﬁed by the current generators Jna of a more general Lie group, e.g. SU(2) as appears
in nonabelian bosonization schemes [20]. f abc are its structure constants, and the integer
k is the level of the Kac-Moody algebra. The central charge of the associated Virasoro
algebra is related to the level k by c = 3k/(k + 2). We do not go into further details
here, although we shall encounter an example of a U(1)-Kac-Moody algebra with c 6= 1
in Section 6.3 when we discuss the chiral Luttinger liquids formed by the edge excitations
in the fractional quantum Hall eﬀect.
    One can also consider “vertex operators” : exp[iαφ(z)] : which, from their OPE with
T (z), are identiﬁed as primary ﬁelds with weights (α2 /2, 0). This determines the decay
of their correlation functions, which, like all Gaussian model correlations, can also be
evaluated explicitly
                                                2                    1
                   h: eiαφ(z) :: e−iαφ(w) :i = eα hφ(z)φ(w)i =               .     (3.173)
                                                                 (z − w)α2

The ﬁrst equality is (3.75) and the second equality has been obtained with (3.165).

                                              51
   Up to now, we have been silent on a parameter of the theory – the compactiﬁcation
radius R. This is a parameter of the theory, and one can either ﬁx it from certain
constraints on the vertex operators, or give it from the outset and then determine the
operators which are well-behaved. Single-valuedness of the vertex operators implies that
the ﬁelds φ(z) must be compactiﬁed with a compactiﬁcation radius R (obey periodic
boundary conditions on a circle with radius R)

                                 φ + 2πR = φ ,               R = n/α .                         (3.174)

In general, the vertex operators : exp[iαφ(z)] : have weird commutation relations. We can
require, however, the object
                                   Ψ†α (z) =: exp[iαφ(x)] :                        (3.175)
to obey fermionic anticommutation relations with Ψ(z) and with its antiholomorphic
counterparts Ψ̄† (z̄), Ψ̄(z̄), and to commute with the currents [40]

                    {Ψ(z), Ψ† (z ′ )} = δ(z − z ′ )      ,    {Ψ(z), Ψ(z ′ )} = 0 ,
                    {Ψ(z), Ψ̄† (z̄ ′ )} = {Ψ(z), Ψ̄(z̄ ′ )} = 0 ,                              (3.176)
                      [J(z), Ψ(z ′ )] = −δ(z − z ′ )Ψ(z) .

This imposes α = 1 for free fermions. : exp[iφ(z)] : then creates a (1, 0) state from the
vacuum. One can also prove that the current Jf (z) =: Ψ† (z)Ψ(z) : written as a fermion
bilinear is identical to the bosonic current Jb (z) = i∂φ(z) where the ﬁeld φ is precisely
the one appearing in the exponential in (3.175), making the identity of the fermion and
boson representations complete.
    The Kac-Moody generators Jm are extremely useful in classifying the excitations in
our model. The Hamiltonian is related to the stress-energy tensor through [x is the spatial
coordinate of the image of z on the cylinder]
                                                                                      2
          1                                              1                1 2π
              Z h                i                                            
    H=          T (x) + T̄ (x) dx ,            T (x) =     : J(x)J(x) : +                  .   (3.177)
         2π                                              2                24 L
The constant shows that our model has a central charge c = 1. Putting together the mode
expansions (3.142), (3.168) and the exponential transform (3.154), and realizing that the
transformation to the cylinder generates an anomaly similar to (3.147) in : J(z)J(z) :, we
ﬁnd the generators of the Virasoro algebra
                                                       ∞
        2π       1                                 π X                       cπ
                        Z ∞
                                     2π
           Lm =               dx ei L mx T (x) =          : Jn Jm−n : −δm,0     .              (3.178)
        L       2π       0                         L n=−∞                   12L

The Lm satisfy the Virasoro algebra (3.143) with central charge c = 1 among them, and

                                          [Ln , Jm ] = −mJn+m                                  (3.179)

with the generators of the Kac-Moody algebra. To every Kac-Moody algebra, there is an
associated Virasoro algebra, and the present construction of the Virasoro generators from


                                                   52
the Kac-Moody ones is due to Sugawara. Specializing (3.179) to n = 0 yields (taking only
one chiral component)
                                               2π
                                   [H, Jm ] = − mJm .                              (3.180)
                                                L
showing that the Jm act as raising (m < 0) and lowering (m > 0) operators of a harmonic
spectrum. The spectrum is harmonic because of the linearized dispersion and the equal
k-spacing. Moreover, Eq. (3.170) implies that the state |0i is annihilated by the Virasoro
generators (3.178) with n > 0, and therefore qualiﬁes as a highest-weight state.
    The Jm can be used to algebraically generate this spectrum and its conformal tower
(family) of descendant states from a reference state |0i. We suppose this state completely
ﬁlled up to some energy, call it Fermi energy, EF = 0. By applying the Jm with m < 0, we
make a particle-hole excitation with energy −m by raising a particle from below the Fermi
energy into an unoccupied state above, −m levels higher. The energy level structure of
the Hamiltonian carries over to the descendants created from the reference state |0i

                    J−n1 . . . J−nk |0i =
                                        6 0 ,        1 ≤ n1 ≤ . . . ≤ nk ,          (3.181)

as in Eq. (3.150) for the Virasoro generators. The level of the state (3.181) is ki=1 ni ,
                                                                                   P

(ni > 0), and the level associated with a single generator J−m is m (> 0). The energy
of the state equals its level in units of 2π/L. Of course, such a description is redundant:
a state at level N can be generated in P (N) ways; P (N) is the number of partitions of
N. At level N, we have an N-particle–N-hole excitation. The Kac-Moody algebra can
therefore be used to classify the particle-hole excitations from a reference state.
    There are states which the currents cannot create from our Fermi sea |0i: those with
additional particles, i.e. a total charge Q with respect to |0i, and speciﬁcally the lowest-
energy states |Qi where the Q particles occupy the ﬁrst Q states above the Fermi level.
We anticipate that there is an inﬁnity of such states, and each of them will be the highest
weight state in the sector with total charge Q of the theory. From our discussion, it is
clear that the vertex operators (with α = 1 for a free theory)

                                   Ψ† (z) =: exp[iφ(z)] :                           (3.182)

creates a chiral fermion. The chiral state |Qi then is created out of |0i by

                                |Qi =: exp[iQφ(z)] : |0i .                          (3.183)

The energy of a state |Qi is
                                                       πQ2
                                E(Q) − E(0) = vF           .                        (3.184)
                                                        L
Acting on |Qi, the Kac-Moody generators J−m will again create the full spectrum of
particle-hole excitations in the sector |Qi.
   There are more general operators than (3.182). One can build them by combining
ﬁelds of both chiralities, writing e.g.
                                         h                         i
                     Ψ†mn (z, z̄) =: exp i αmn φ(z) + ᾱmn φ̄(z̄)        :   .      (3.185)

                                                53
                             2      2
Its scaling dimension is (αmn   + ᾱmn  )/2, and α and ᾱ are related to the compactiﬁcation
radius R by
                            1 m nR                         1 m nR
                                                                     
                    αmn =        +           ,     ᾱmn =         −        .            (3.186)
                            2 R       2                    2 R        2
Its physical meaning is quite clear. Increasing m means increasing the charge for both
chiralities Ψ†m0 |Q, Q̄i = |Q + m, Q̄ + mi. Increasing n transfers charge from one chirality
to the other, i.e. creates a ﬁnite persistent current Ψ†0n |Q, Q̄i = |Q + n, Q̄ − ni [this is an
example of a primary operator with k (∞) 6= 0 in (3.162)]. Ψ†mn creates charge or current
excitations, or combinations thereof. As for Ψα (z), the particles making up these charge
and current excitations are fermions only at the particular compactiﬁcation radius R = 1.
Else, they are more general objects.
    The Luttinger or Gaussian model has operators with continuously varying exponents.
Responsible for this are dimension (1, 1) marginal operators which take the model along
a whole critical line. The simplest of these operators is
                                         g−1
                                                    Z
                                S′ =                    dz dz̄(∂z Φ)(∂z̄ Φ) ,                     (3.187)
                                          2π
which is proportional to the free action (3.164) and whose only eﬀect is to introduce
the coupling constant g as a prefactor into S. The eﬀect of this interaction can simply
                                                 √
be absorbed by redeﬁning the ﬁelds φ → φ/ g. With this redeﬁnition, the eﬀective
          √
α → α/ g in the vertex operators changes accordingly, and consequently both their
compactiﬁcation radius and their conformal weight. When the compactiﬁcation radius
R 6= 1, Ψ†α no longer describes a fermion but a more complicated object. In the Luttinger
model, the g2 -interaction is such a marginal operator, coupling currents of both chiralities.
From Eq. (3.173) it is obvious then that S ′ generates continuously varying exponents in
the correlation functions, and varying g sweeps the model over a whole critical line.
     By transforming the phase-ﬁeld representation of the spinless Luttinger model 3.58
into an imaginary time (τ = it) action, one obtains the Gaussian model with an eﬀective
coupling constant g = K. Importantly, the coupling constant g depends essentially on
g2 . Finite g4 only renormalizes the eﬀective g2 but, alone, is not able to give g 6= 1. This
is quite easy to understand because it only changes the Fermi velocity of the Luttinger
model and is therefore absorbed when going to the second spatial coordinate y = vτ .
     More interesting is the case when the interactions are not of current-current type, or
when the theory is formulated on a lattice so that the identiﬁcation of the conformal
operators is far from obvious. Mironov and Zabrodin have given a simple application of
the methods discussed above to interacting spinless fermions (or bosons) [74]
                                         g
         Z L                                 Z L
    H=         dx ∂x ψ † (x) ∂x ψ(x) +             dx dy ψ † (x) ψ † (y) V (x − y) ψ( y) φ(x) .   (3.188)
           0                             2    0

V (x) is a repulsive pair interaction of rather general form. The density of particles is
n = N/L and kF = πn. The model can be solved by Bethe Ansatz for V (x) = δ(x) but
most of the results are expected to carry over for reasonable longer-range potentials.
    From the ﬁnite-size scaling formula for the ground state energy (3.157), one ﬁnds
c = 1 which puts it in the Gaussian (Luttinger liquid) universality class. Now we want

                                                         54
to ﬁnd the correlation function of some local operator O(x). To this end, one must
compute up to order 1/L the energy of the lowest excited state |ϕi whose matrix element
h0|O(x)|ϕi = 6 0 for L → ∞. Then, one can use Eq. (3.163) if its scaling dimension
and spin is known from (3.161) and (3.162). As an example, one can make particle-
hole excitations [ρ(x)] with momentum 2mπ/L (m small). From their excitation energies
linear in m, one can deduce the renormalized sound velocity v and ∆ = ±s = 1. Of
course, this is in agreement with our earlier discussion where we found that the currents
of the Gaussian model are (1, 0) or (0, 1) ﬁelds. Next, make an excitation at constant
                         (∞)
particle number with k0n = 2nkF where the particle-hole spectrum goes to zero. In a
free system, this would correspond to applying the operator Ψ†0n to the Fermi sea. The
Bethe Ansatz gives the energy change δE0n = (2π/L)(2kF n2 /v) and, using (3.161), the
scaling dimension ∆0n = 2kF n2 /v. Comparing with (3.186), one ﬁnds a compactiﬁcation
radius R2 = 2kF /v. One can also add pairs of particles or a single particle, where a
selection rule enforces half-integer n. The energy shift is given by (3.161) with a scaling
dimension (3.186) with m = 1, n = 1/2 and the R found above. The Green function
and the CDW correlation functions (corresponding to the low-energy excitation at 2kF
discussed before) are then
                         2   2                                  2
 G(x) ∼ cos(kF x)x−1/2R −R /2 ,     RCDW (x) ∼ cos(2kF x)x−2R ,        R2 = 2kF /v = K .
                                                                                     (3.189)
The exponents satisfy the scaling relations of the spinless Luttinger model, and the corre-
lation exponent K has been identiﬁed in the last equality. (The factor 4 diﬀerence in R2
to Mironov and Zabrodin [74] must be due to a diﬀerent prefactor [2/π] of the Gaussian
action.)
    The close correspondence of conformal ﬁeld theory and the operator approach to
bosonization should be apparent now, at least for the case c = 1 of the Luttinger and
Gaussian models. Density ﬂuctuations (currents), charge and current excitations, and
fermion raising and lowering operators all appear either in an operator approach based
on a Hilbert space, or in an algebraic formalism based on the U(1)-Kac-Moody algebra,
which is satisﬁed by the currents as a consequence of the U(1)-gauge symmetry (3.9) cor-
responding to the conservation of left- and right-moving particles separately. The main
problem in the operator approach is the explicit identiﬁcation of the coupling constant of
the Luttinger model which then determines all correlation functions. In conformal ﬁeld
theory, we must determine the scaling dimensions of the various primary operators. As
will be discussed in the next chapter, in both cases the spectrum of low-lying eigenvalues
is suﬃcient for that purpose, showing once more the full equivalence between bosonization
and conformal ﬁeld theory. Which one to use is a matter of taste.
    The preceding analysis of the interacting spinless fermions foreshadows the application
of conformal ﬁeld theory to rather general models of interacting electrons. We shall discuss
this topic in the next chapter, where some other methods for extracting the low-energy
physics will also be presented.




                                            55
Chapter 4

The Luttinger Liquid

4.1      The conjecture
The Luttinger model can be solved exactly at any interaction strength, except for too
strong attraction where the model becomes unstable towards phase separation (forma-
tion of electron droplets; Section 5.3). However, it contains drastic approximations with
respect to a realistic many-body problem: (i) its dispersion is strictly linear, and (ii) the
electron-electron interaction is limited to forward scattering only. The possibility of an
exact solution is precisely related to these two approximations.
    One may therefore wonder if these approximations are essential in the sense that the
Luttinger physics is lost in any diﬀerent model or if, on the contrary, this physics is robust.
In this case, only parameters (Kν , vν ) would be renormalized close to the Fermi surface,
but the structure of the low-energy theory would be identical to the Luttinger model.
Of course, further away from the Fermi surface, new phenomena such as boson-boson
interactions or lifetime eﬀects could occur but it would be guaranteed that they fade
away as (k − kF , ω, T ) → 0. This is what happens in the Fermi liquid. The Luttinger
model would then represent the generic behaviour of gapless 1D quantum systems, and
one could build upon it the universal low-energy phenomenology for all 1D metals (the
Luttinger liquid) called for by the breakdown of the Fermi liquid in 1D (Chapter 2).
    Haldane, in the early 1980’s, conjectured that this was indeed possible and supported
this conjecture with a series of case studies of models solvable by Bethe Ansatz [49, 75].
He also demonstrated that certain features mapped away when passing to the Luttinger
model, such as curvature in the dispersion, only introduce nonsingular, perturbative in-
teractions among the bosons [3] which disappear as one goes to the long-wavelength or
low-frequency limit. Haldane’s conjecture has meanwhile been veriﬁed in an impressive
number of instances some of which will be discussed below and, to my knowledge, no
counterexample has been discovered yet.
    What is the content of this “Luttinger liquid conjecture”? Given any 1D model of cor-
related quantum particles (in 1D not even necessarily fermions) and let there be a branch
of gapless excitations: then the Luttinger model is the stable low-energy ﬁxed point of the
original model (or at least its gapless degrees of freedom). In other words, the asymptotic


                                              56
low-energy properties of the degree of freedom associated with this branch are described by
an eﬀective (renormalized) Luttinger model, in particular with one renormalized Fermi
velocity vν and one renormalized eﬀective coupling (stiﬀness) constant Kν , up to per-
turbative boson–boson interactions. All properties found for the Luttinger model: (i)
absence of fermionic quasi-particles in the vicinity of the Fermi surface, (ii) anomalous
dimensions of the fermion operators producing nonuniversal power-law correlations, (iii)
charge-spin separation, (iv) the universal relations among the nonuniversal exponents of
the correlation functions, among the velocities for sound, charge, and current excitations
and between velocities and the eﬀective renormalized coupling constants, carry over to the
low-energy sector of the model under consideration. The nontrivial task remaining then is
to determine the two central quantities of the Luttinger liquid, the renormalized velocity
vν and the renormalized eﬀective coupling constant Kν , from the original model. Once
this is achieved, one has an asymptotically exact solution of the 1D many-body problem.
This is what most of this chapter will be about.
    A word of caution is required for systems with several degrees of freedom. If all
degrees of freedom remain gapless, the low-energy ﬁxed point will be a Luttinger liquid
in the sense described. If some degrees of freedom become gapped while others do not,
the physics within the gapless degrees of freedom can be described as a Luttinger liquid
while all quantities involving gapped degrees of freedom will deviate qualitatively from
the Luttinger liquid. In Chapter 5, we will give examples for this kind of situation.
    When mapping a more realistic model of interacting electrons in 1D onto the Luttinger
model, complications arise from two sources: (i) the dispersion of these models is not lin-
ear; (ii) the interactions generally do not only contain the forward scattering processes
included in, and solved by the Luttinger model but also the large momentum transfer
backward (spin exchange) and Umklapp scattering (for commensurate band ﬁlling) de-
picted in Fig. 3.3. Moreover if the interactions are not weak, states far from the Fermi
surface are coupled to the Fermi surface states; curvature and interaction could then con-
spire to invalidate the Luttinger liquid picture. That none of this in fact happens, was
demonstrated by Haldane [3, 49].
    There are two basic ways of proceeding. One can start from a Luttinger model and
extend it by various interactions and other features, and then study the stability and
renormalization of the Luttinger model solution. The alternative is to start directly from
a realistic model of 1D correlated fermions, possibly on a lattice, and search for either
Luttinger liquid-correlations or the speciﬁc Luttinger liquid properties of the spectrum of
charge, current and sound excitations, Eq. (3.32). The organization of the chapter will
follow roughly this order.




                                            57
4.2      Luttinger model with nonlinear dispersion – the
         emergence of higher harmonics
Haldane extended the Luttinger Hamiltonian, Eqs. (3.1)–(3.4), by terms modelling non-
linear dispersion

             εr (k) = vF (rk − kF )
                                          1                 λ
                    → vF (rk − kF ) +       (rk − kF )2 +         (rk − kF )3 .           (4.1)
                                         2m               12m2 vF
The third order term is necessary to ensure stability, and λ > 3/4 is required then.
(4.1) can be bosonized, and one obtains quadratic terms of the usual structure (3.21),
with parameters renormalized by m and λ, but also cubic and quartic boson terms. The
quadratic form can be diagonalized as usual and the remaining terms are written as (for
spinless fermions for simplicity [3])
                           X 1 Z L             1 3            λ
                    δH =              dx :       Φ̃r (x) +     2v
                                                                   Φ̃4r (x) : ,            (4.2)
                            r   2π    0       6m           48m   F
                                                  √
where the ﬁelds Φr (x) = [rΦρ (x) − Θρ (x)]/ 2 are given in terms of the phase ﬁelds of
Eqs. (3.42) and (3.43) and the tilde implies that the Bogoliubov transformed ﬁelds (3.50)
enter. δH describes boson-boson interactions. Their appearance is quite clear physically
because, for a curved dispersion, two ﬂuctuations with wave vector q and q ′ will have an
energy diﬀerent from a single one with q + q ′ : ﬂuctuations interact. Fortunately, δH is
harmless: one can either (i) argue, using renormalization group, that these higher order
boson terms are irrelevant and therefore do not inﬂuence the ﬁxed point physics described
by the quadratic ones, or (ii) as did Haldane, perform a systematic 1/m-expansion to
ﬁnd that the model still obeys the constitutive Luttinger liquid relations (3.32) between
velocities and coupling constant, and that the relation of K to the correlation function
exponents, Eqs. (3.85) – (3.100), also remains unchanged. Only the values of K and the
velocities change.
    There is, however, another important eﬀect caused by the nonlinear dispersion: the
appearance, in the physical fermion operators Ψ(x), of higher harmonics in the chiral
fermion operators Ψr (x) which generates components with 3kF , 5kF , . . . in the fermion
ﬁelds and with 4kF , 6kF , . . . in the pair ﬁelds. Consequently, the single-particle Green
function acquires components at 3kF , 5kF . . ., and e.g. the density-density correlations
get oscillations at 4kF , 6kF . . . in addition to the usual ones at small q and at 2kF . These
components are not present in the Luttinger model but may appear in any more general
model with nonlinear dispersion ε(k). They are necessary for constructing local density
and fermion operators.
    This becomes apparent when one attempts to construct a representation for excitations
on all length scales from the long-wavelength ones which dominate the low-energy physics
[41]. Recall from our bosonization procedure in Section 3.2.2 that the ﬁeld Φ(x) had a
kink of amplitude π at the location of each particle. The location of the lth particle then

                                              58
is given by Φ(x) = lπ. When going from the smeared, long-wavelength density operators
ρr (x) to a physical local operator ρ(x), it is suﬃcient to multiply by a delta function
   l δ[Φ(x) − lπ] to locate the individual particles. The local density then is written as
P

                                            ∞
                                            X
                    ρ(x) = [n + Ξ(x)]              exp [2im {Φ(x) + kF x}]           ,       (4.3)
                                          m=−∞

where n = N/L is the average density, and the ﬁeld Ξ(x) describes the long-wavelength
ﬂuctuations. The fermion ﬁeld essentially is the square-root
                   q                             ∞
                                                 X
          Ψ(x) ∼    n + Ξ(x) exp [iΘ(x)]                exp [(2m + 1)i {Φ(x) + kF x}]    ,   (4.4)
                                               m=−∞

but the sum must contain only odd terms to ensure the anticommutation property. Θ(x)
and Φ(x) have been introduced in (3.42) and (3.43), and Ξ(x) commutes with Θ(x)
as [Θ(x), Ξ(x′ )] = iδ(x − x′ ). Moreover, describing charge density ﬂuctuations, Ξ(x) is
related to Φ(x) by ∂x Φ(x) = −π[n + Ξ(x)]. An equation equivalent to (4.4) for spin-
1/2 fermions can be constructed easily. The correlation exponents associated with these
higher harmonics are then deduced with the methods of Section 3.3 [3].
    In the Luttinger model with its linear dispersion, only the components with m = 0, ±1
are present in (4.3) and those with m = −1, 0 in (4.4). This is related to the fact that
in the Luttinger model, the mean current is [from the continuity equation (3.106) for
q → 0] j = vj J/L, and is strictly conserved because J is a good quantum number [3].
With δH [Eq. (4.2)] containing the nonlinearity, the current operator as determined from
the continuity equation contains higher-order boson terms, and a simple relation to the
quantum number J only obtains close to the Fermi surface. In order to allow for a
fermionic representation of this complex current operator, the physical fermions must
contain the higher harmonics in the chiral fermions.


4.3     Backward and Umklapp scattering
We now turn to the problem of non-Luttinger interactions. The Luttinger model includes
only the forward scattering interactions g2 and g4 , Eqs. (3.3) and (3.4). This is certainly
very restrictive since any realistic model, say with an interaction
                                  1 X
                        Hint =                  V (q)c†k+q,sc†k′ −q,s′ ck′,s′ ck,s           (4.5)
                                  L k,k′,q,s,s′

will also contain components of V (q) with q large, speciﬁcally q ≈ 2kF . The restriction to
forward scattering is, however, absolutely essential in guaranteeing the exact solvability
of the Luttinger model.
    In any realistic theory, these oﬀending interactions will be there. The most important
processes are depicted in Figure 3.3. The contributions to the Hamiltonian are
                         XZ L
           H1⊥ = g1⊥              dx : Ψ†+,s (x)Ψ−,s (x)Ψ†−,−s (x)Ψ+,−s (x) :                (4.6)
                          s   0


                                                   59
                    2g1⊥
                           Z        √
                 =       2
                             dx cos[ 8Φσ (x)] ,                                         (4.7)
                   (2πα)
                   g3⊥ X L
                           Z
           H3⊥   =            dx : Ψ†+,s (x)Ψ†+,−s (x)Ψ−,−s (x)Ψ−,s (x) + H.c. :        (4.8)
                    2 s 0
                    2g3⊥ Z          √
                 =           dx cos[  8Φρ (x)] .                                        (4.9)
                   (2πα)2
The ﬁrst term represents exchange scattering of two counterpropagating particles with
opposite spin across the Fermi surface (momentum transfer ≈ 2kF ) and violates spin-
current conservation. [SU(2)-invariant backscattering would imply the presence of a g1k -
term in the Hamiltonian which, after bosonization, can however be absorbed into g2ν →
g2ν − g1k /2.] The second term is Umklapp scattering of two particles moving in the same
direction. The product of four fermion ﬁelds in Eq. (4.8) contains a factor exp(4ikF x)
which, generally, oscillates rapidly and suppresses contributions from this term. For
half-ﬁlled bands, however, 4kF equals a reciprocal lattice vector ±2π/a, and Umklapp
scattering becomes important. Charge-spin separation is respected here. This is not
generic. However all purely electronic processes coupling charge and spin, i.e. arising
from four fermion operators, are less relevant than (4.6) and (4.8) [50].
    For the Luttinger liquid phenomenology to survive one must demonstrate that, al-
though these interactions certainly renormalize velocities and stiﬀness constant, they do
not destroy the universal relations among them nor those between K and the correlation
function exponents. To map the low-energy physics onto a Luttinger model, one then has
to (i) check that there are (how many?) branches with gapless excitations; (ii) for each
branch determine the relevant renormalized velocity and coupling constant; (iii) insert
these into the Luttinger liquid expressions for the quantities of interest. If this works, it
is proven that the originally oﬀending interactions are irrelevant at the Luttinger liquid
ﬁxed point and that their only eﬀect was a quantitative renormalization of the Luttinger
liquid parameters.
    This is the spirit of all approaches to a Luttinger liquid description of interacting
1D electrons. It is most explicit in the renormalization group method if one accepts the
limitation to weak coupling, and we shall treat H1⊥ in this way. While more power-
ful mappings of lattice models onto the Tomonaga-Luttinger model are available now,
in conjunction with renormalization group, such “direct” extensions of the Tomonaga-
Luttinger model give a clear and simple idea of how the renormalized eﬀective parameters
in the Luttinger liquid are generated. Moreover, many problems beyond the 1D electron-
electron-interaction models, such as coupling to phonons or scattering by impurities, only
become tractable with this approach. Also renormalization group allows to determine
corrections to the simple power-law decay (3.92) – (3.100) of correlation functions of the
Luttinger model which are absolutely essential to obtain a correct picture of the physics
of more complicated models. Finally, much of the early understanding of what is now
called “Luttinger liquid” was based on continuum models [18, 19], by that time most often
running under the label “g-ology”, and renormalization group was the most important
tool for their understanding.
    We derive renormalization group equations for H1⊥ following a method described by

                                             60
Chui and Lee [76]. There are other ways to formulate the renormalization group; they have
been reviewed in detail elsewhere [18, 19, 22]. First diagonalize the Luttinger part of Hσ
(shorthand for all terms containing σ-operators). Then compute the partition function
Zσ = hexp −βHσ i in the Matsubara formalism of imaginary times τ = it. Zσ can be
expanded in H1⊥ and the expectation value be evaluated with respect to the diagonal
part
                            !2n Z                                               !
                                    2n 2
                                                                       | ri − rj |2 
                                             !
         X  1        g1⊥            Y dr                   X
   Zσ =        2
                                                 exp 2Kσ     qi qj ln                .   (4.10)
        n (n!)      (2π)2           i   α2                i>j               α2

The 2D vector r = (x, vσ τ ) and qi = 1 for i = 1 . . . n and −1 else. Zσ is now identiﬁed
as the partition function of a classical 2D Coulomb gas with charges qi , at a ﬁctitious
temperature βCG = 4Kσ and a fugacity g1⊥ /(2π)2 . For this problem Kosterlitz and
Thouless [77] derived a set of renormalization group equations which translate into
                                         2
                   dKσ    1    g1⊥                     dg1⊥
                                    
                       = − Kσ2                    ,         = g1⊥ (2 − 2Kσ ) .            (4.11)
                    dℓ    2    πvσ                      dℓ
They describe the ﬂow of the eﬀective coupling constants g1⊥ and Kσ , shown in Figure
4.1, when short-distance degrees of freedom (between α and αeℓ ) are integrated out. Here
α is reinterpreted as a short-distance cutoﬀ parameter which may be of the order of a
lattice constant. The coupling constants must be rescaled so as to maintain the Fermi
surface physics and the asymptotic correlations invariant. There are two diﬀerent types
of ﬂow. (i) Assume Kσ suﬃciently large so that |g1⊥ | decreases with increasing ℓ (lower
right part of Fig. 4.1). If this remains so even for ℓ → ∞, the renormalization group
                                          ⋆
trajectory will ﬂow into a ﬁxed point g1⊥     = 0 and Kσ → Kσ⋆ . g1⊥ has dropped out of
the problem, i.e. at long distances the model behaves eﬀectively as a Luttinger model
with a renormalized Kσ⋆ . The ﬁxed point is spin-rotation invariant if it turns out that
Kσ⋆ = 1. Then the ﬂow is precisely along the separatrix. This is one example of a
Luttinger liquid. [Even then, during intermediate stages of the calculation, one may have
Kσ (ℓ) 6= 1; this apparent breaking and ﬁnal restoration of SU(2)-invariance is typical of
abelian bosonization.] (ii) If the bare Kσ is not large enough compared to | g1⊥ |, Kσ will
ﬂow towards 0 but more importantly | g1⊥ | will increase. Derived from a perturbation
expansion, the renormalization group manifestly looses its sense. It is clear that the
system ﬂows away from the Luttinger liquid ﬁxed line, and the diverging | g1⊥ | signals
an instability of the model towards a diﬀerent ground state whose accurate description
must, however, be based on diﬀerent methods. This regime will be the subject of Section
5.1.
    So long as the system is not half-ﬁlled, the charge exponent Kρ is not renormalized.
At half-ﬁlling, the situation in the charge degrees of freedom is isomorphic to the spin
part discussed here. It is suﬃcient to change g1⊥ → g3⊥ , Kσ → Kρ and carry over the
Equations (4.11). Also more complicated models where charge-spin coupling is impor-
tant can be treated in this way [50]. The application to phonons and impurities will be
discussed below.


                                                  61
    The essential weakness of the renormalization group approach is its limitation to weak
coupling, being derived from perturbation expansions. This limitation has been overcome
by several methods which will be discussed in the subsequent sections.
    Before, however, we discuss in more details the correlation functions of such a Luttinger
liquid where all non-Luttinger interactions have become irrelevant. A ﬁrst idea about the
correlations is obtained by inserting the ﬁxed point value Kν⋆ into the correlation functions
of Section 3.3. This is the standard procedure in the renormalization group treatment of
critical points [70]. In particular, we would then ﬁnd a degeneracy of exponents between
SDW and CDW, and SS and TS, no matter what the precise ﬁxed point values Kν⋆ .
Anticipating that the non-half-ﬁlled repulsive Hubbard model can be described, at least
for small U, by (3.1)+(4.6), it is clear that this cannot be the whole story.
    Let us consider the 2kF -SDWz correlation function for deﬁniteness. The SDWz -
operator is
       †
                   X     †                  −i     h          √          i     h√          i
     OSDW    (x) =    sΨ −,s (x)Ψ +,s (x) =    exp  2ik F x −   2iΦρ (x)   sin    2iΦσ (x)    .
           z
                    s                       πα
                                                                                             (4.12)
Now consider the time-ordered correlation function (again in imaginary-time formalism)
                               D                            E
                                                †
         − RSDWz (r) =             Tτ OSDWz (r)OSDW z
                                                      (0)
                                                                         "Z                         #!
                              1                  †
                                                                            β→∞
                            =    Tr Tτ OSDWz (r)OSDW   (0) exp                           dτ H(τ )        , (4.13)
                              Zσ                     z
                                                                            0

where H = HLutt + H1⊥ and the trace (Tr) is performed over σ and ρ. The charge part
is trivial and gives the Luttinger result |r|−Kρ . In the spin part, use Wick’s theorem to
expand the exponential in H1⊥ . This will generate nonvanishing contributions at all even
orders which are essentially those contained in the partition function Zσ multiplied by
OO †. In addition to these terms there will, however, be important new terms in odd
orders of H1⊥ not present in the partition sum [78, 79]. They arise from contracting the
σ-part of the SDWz -operators with H1⊥
                      q                  q                    q                    
                 sin    2Kσ Φσ (r) sin            2Kσ Φσ (0) cos       8Kσ Φσ (r1 )
                       1   q                                                              
                    = − exp 2Kσ [Φσ (r) + Φσ (0) − 2Φσ (r1 )] + H.c.                           .           (4.14)
                       8
These expectation values do not vanish because the prefactor of the Φσ -ﬁeld in the cor-
relation function is half of that in the perturbation operator or, in other words, because
the Ψ†−,s Ψ+,s -components of the SDWz -operator also occur as factors in H1⊥ . In the
Coulomb gas language, this is equivalent to saying that one considers the screening of two
test charges q/2 by charges −q. The terms up to second order can be reexponentiated in
the spirit of a cumulant expansion. Now it is important to integrate up the correlation
function along the whole renormalization group trajectory [78, 79]. The spin-part of the
correlation function then becomes
                                                                                   #2              
                                               g1⊥ (ℓ′ ) ′ 1            g1⊥ (ℓ′ )
                                                                 Z ℓ"
                             |r|                                                           |r|
                                            Z ℓ
   (σ)
  RSDWz (r; α) = exp −Kσ ln     +                      dℓ +                             ln dℓ′  .        (4.15)
                                       α     0  πvσ          2     0     πvσ                α

                                                     62
If scaling goes to weak coupling, the integrals can be extended to inﬁnity and the usual
expressions involving the ﬁxed-point exponent Kσ⋆ follow. Notice, however, that an ulti-
mate cutoﬀ is provided by the observation scale |r| (if not by temperature or system size)
so that the integration cannot go beyond ℓ⋆ = ln |r|/α. The correlation function then
decays as
                                     !−Kρ −Kσ⋆ s
                                 |r|               |r|
                   RSDWz (r) =                  ln      ,     Kσ⋆ = 1 ,             (4.16)
                                  α                 α
where we have reintroduced the contribution from the charge density ﬂuctuations. In
doing the integrals, we have used explicitly the fact that we scale along critical line
(the separatrix in Fig. 4.1) so that the logarithmic corrections only obtain in the spin-
rotation invariant case. In this case, one recovers expressions identical to (4.16) for the
x- and y-components of the SDW correlation function although, involving Θσ -ﬁelds, the
intermediate expressions are quite diﬀerent. The charge density wave and superconducting
correlations decay as
                                                    −1                                −1
RCDW (r) ∼ |r|−Kρ−1 ln−3/2 |r| ,   RSS (r) ∼ |r|−Kρ −1 ln−3/2 |r| ,  RT S (r) ∼ |r|−Kρ −1 ln1/2 |r| .
                                                                                        (4.17)
There is no logarithmic correction to the 4kF -CDW function because it does not involve
spin ﬂuctuations. It is remarkable that at this level, the degeneracy of the CDW and SDW
correlation functions and between SS and TS is lifted: they have the same exponents,
correctly given by the Luttinger model but the correlations are logarithmically stronger
for SDW and TS. For repulsive interactions, magnetic correlations must dominate! If
we have attractive backscattering g1⊥ → −g1⊥ with Kσ left unchanged, CDW and SS
will be logarithmically enhanced over SDW and TS [just exchange the log-exponents in
(4.16) and (4.17)]. Finally, if spin-rotation invariance is broken and there is an easy plane
anisotropy, g1⊥ scales to zero faster. In this case, the integration along the trajectory
only gives prefactor corrections to the power-law correlations [79]. These results can
be transposed straightforwardly to commensurate systems when Umklapp scattering is
irrelevant [50].
    The phase diagram in the g1⊥ −Kρ -plane obtained in the absence of Umklapp scattering
is displayed in Figure 4.2. At g1⊥ > 0, the dominant divergences are SDW for Kρ < 1 and
TS for Kρ > 1. Subdominant ﬂuctuations are indicated in parenthesis, and the preceding
discussion shows that CDW and SS have the same exponents as SDW and TS but are
disfavoured by their logarithmic corrections. We have assumed the system to be spin-
rotation invariant, and consequently, the ﬁxed-point Kσ⋆ = 1. For g1⊥ < 0, a spin gap
opens through a Kosterlitz-Thouless transition, and formally Kσ⋆ = 0. Here, CDW and
SS have the strongest divergences for Kρ < 1 and Kρ > 1, respectively. They also diverge
in the regimes 1 ≤ Kρ ≤ 2 and 1/2 ≤ Kρ ≤ 1, respectively, though with a weaker power
than the dominant ﬂuctuations.
    Logarithmic corrections to the free energy of statistical models whose fermionic de-
scription contains a marginally irrelevant Umklapp operator and which are related to the
singularities found here in the correlation functions, had been discovered earlier by Black
and Emery [80].

                                              63
4.4      Lattice models: Hubbard & Co.
A variety of nontrivial lattice models can be solved exactly in 1D, for which no exact
solution exists in higher dimension. A non-exhaustive list contains the Heisenberg model
[81], the Hubbard model [82, 83] and various long-range, supersymmetric or degenerate
extensions, the supersymmetric t − J-model [84]-[86], and others. Solvable continuum
models include, apart the Tomonaga-Luttinger model discussed above and the Luther-
Emery model reviewed in Section 5.1, the massive and massless Thirring model [87] and
the interacting Bose gas [88]. Exact solutions are due to a large extent to very strong
conservation laws arising from the restricted phase space for 1D fermions.
    We brieﬂy discuss some important lattice models. A central role is played by the
Hubbard model, and our treatment of Luttinger liquid correlations in lattice models will
be centered on this model. We therefore also present a short summary of important
Bethe-Ansatz results for this model to make this section more self-contained.


4.4.1     Models
The Hubbard model [82] is described by the Hamiltonian
                                            UX
                             c†i,s cj,s +
                      X                                                         X
        HHub = −t                                 (ni,s − 1/2)(ni,−s − 1/2) − µ     ni,s ,    (4.18)
                    <i,j>s                  2 i,s                               i,s


where ci,s describes fermions with spin s in Wannier orbitals at site i, ni,s = c†i,s ci,s , U is the
repulsion of two electrons on the same site and µ the chemical potential. One can also ﬁx
the band ﬁlling to n = Nelectrons /Nsites . < i, j > restricts the sum to nearest neighbours.
This model is the simplest approximation for strongly correlated electrons in a crystal
lattice. The model is exactly solvable, cf. Section 4.4.2. For a long time, it was believed
that the Hubbard model describes the strong-coupling limit of the 1D Fermi liquid while
the Tomonaga-Luttinger model rather would represent the weak-coupling case. To show
that this is not the case, and that both are closely related, is a major purpose of Section
4.4.
    Various more realistic extensions can be considered. In some cases, it is necessary
to add longer-range interactions between the electrons. The extended Hubbard model
[50, 89]                                              X
                                HEHM = HHub + V          ni ni+1                              (4.19)
                                                                 i
includes interactions between neighbouring sites, but one may obviously go to longer
interaction range [such as 1/r [90] or a Yukawa form exp(−r)/r]. In contrast to the
Hubbard model, this Hamiltonian is no longer exactly solvable. Also “oﬀ-diagonal” terms,
i.e. interactions coupling charge densities on site to those on bonds, can be added [91]-[96]
                                            X †                     
                   H = HHub + X                   ci=1,s ci,s + H.c. (ni,−s + ni+1,−s ) .     (4.20)
                                            i,s

An important feature here is the breaking of charge-conjugation symmetry generated
by X. This term goes beyond the zero-diﬀerential-overlap approximation. A critical

                                                         64
discussion of the approximations involved in going from a realistic correlation problem
to the Hubbard model in a 1D context has been given by Painelli and Girlando [92] and
Campbell et al. [94].
    At U > 0 and half-ﬁlled band, the Hubbard model has an insulating ground state
whose spin ﬂuctuations are described by an eﬀective Heisenberg model [81] with an (an-
tiferromagnetic) exchange integral J = 4t2 /U. For a nearly half-ﬁlled Hubbard model,
it is more convenient to think in terms of a few holes doped into such an antiferromag-
netic Heisenberg system. For large U, double occupancy of lattice sites is dynamically
forbidden, and the energy scales for charge ﬂuctuations (∼ t) and for spin ﬂuctuations
(∼ J ≪ t) are well separated. One can then simplify the problem by projecting out the
states in the Hilbert space involving double occupancies. In a restricted Hilbert space
containing only singly-occupied and empty sites, one ﬁnds in second order in t/U the
following Hamiltonian (t − J-model, [84]-[86])
                                                                       X              1
             Xh                                               i                                       
 Ht−J = −t        (1 − ni,−s )c†i,s ci+1,s (1 − ni+1,−s ) + H.c. + J        Si · Si+1 − ni ni+1           .
              i                                                        i               4
                                                                                    (4.21)
                                                                                  †
The fermions ci,s now behave as spinless fermions, and Si =                       are spin
                                                                            s,s′ ci,s (σ)s,s′ ci,s′
                                                                           P

operators. This model can be solved in two limits. For J = 0, it reduces to the U = ∞-
Hubbard model which describes free spinless fermions, and for J/t = 2, it possesses an
additional supersymmetry and can be solved by Bethe Ansatz [84]-[86]. The t − J-model
approximates the strong-coupling limit of the Hubbard model only for J ≪ t. Models
with other interactions or more bands can, however, be approximated in a low-energy
subspace by a t − J-model with sizable J [97]. Both the t − J and the Hubbard model
can be extended to include additional degeneracies [98]. Another interesting extension
consists in introducing longer-range hopping [99] or spin exchange. We shall not say much
on these variants here.
    Most of the methods discussed below for extracting the Luttinger liquid parameters
from one of these models will work, with minor modiﬁcations, also for the others with sim-
ilar structure. When a model is not solvable by Bethe-Ansatz, numerical diagonalization
can provide similar information. We therefore limit our discussion as much as possible to
the quite generic case of the Hubbard model and only brieﬂy discuss changes occurring
when passing to other systems. In the following section, we list some important elements
of the Bethe-Ansatz which are helpful for understanding the mapping onto the Luttinger
liquid.


4.4.2     Bethe Ansatz
The 1D Hubbard model has been solved exactly via Bethe Ansatz by Lieb and Wu [83]
(for pedagogical reviews on the Bethe Ansatz, see Sutherland [26], Korepin et al. [27],
Izyumov and Skryabin [28] or Nozières [100]), and the ground state energy and some
thermodynamic quantities can be obtained [101]–[103]. Also the excitation spectrum of
some collective modes has been computed quite early [104, 105]. The basic physical
picture emerging from these initial studies is as follows. For U > 0, the system is metallic

                                                65
whenever the band is not half-ﬁlled (Nelectrons 6= Nsites = L/a with lattice constant a):
the chemical potential for adding a particle to N-   √ and N − 1-particle systems are equal.
Exactly at half-ﬁlling, one ﬁnds a diﬀerence (∼ U exp(−1/U) for U → 0 and ∼ U for
U → ∞ [83, 104]) between these two quantities indicating that the system has turned
into a Mott insulator for any U > 0. Finite U > 0 obviously prohibits double occupancy
of sites, all sites are now (singly) occupied and no low-energy charge excitations possible.
The lower Hubbard band is completely ﬁlled, and the upper Hubbard band is empty in
the ground state. The spins are coupled through an eﬀective antiferromagnetic exchange
integral J = 4t2 /U, and their dynamics reduces to a Heisenberg model.
    At half-ﬁlling, the U < 0-sector is related to the U > 0 one by a particle-hole trans-
formation ci,s → (−1)i c†i,s for a single spin direction only, say s =↑, exchanging the role
of charge and spin degrees of freedom, and the charge gap discussed above turns into a
spin gap: occupying sites with two electrons with antiparallel spins is favoured. These
pairs are mobile and the charge excitations massless. There are no singular features in
the Bethe Ansatz for U < 0 as a function of band-ﬁlling implying that the picture applies
to the whole U < 0-sector [103].
    These results can be obtained qualitatively, and for U/t ≪ 1 also quantitatively, with
the renormalization group methods described in the preceding section. The coupling
constants are gi⊥ = Ua, i = 1, . . . , 4 (g3⊥ only occurs for half-ﬁlled bands), and the Fermi
velocity is vF = 2ta sin(kF a).
    Bethe’s Ansatz provides a solution for all interaction strengths and band-ﬁllings [83].
We sketch the principal ideas, following Nozières [100]. The Bethe Ansatz relies on the
following facts. (i) Due to energy and momentum conservation, in 1D a two-particle
collision classically and quantum-mechanically conserves both momenta individually. The
particles then only can be exchanged or phase-shifted, and the two-particle wave-function
asymptotically (|x1 − x2 | → ∞) obeys

                         Ψ(x1 , x2 ) = aei(k1 x1 +k2 x2 ) + bei(k1 x2 +k2 x1 ) .           (4.22)

The Bethe Ansatz postulates this behaviour for all distances between the particles. (ii)
A three-particle collision does not conserve individual momenta except if the scattering
matrix factorizes. This factorization implies another conservation law. For N particles,
one then has N conservation laws, expressed by {ki′ } = {ki}. (iii) The Hilbert space of
the Hamiltonian separates in N! quadrants each characterized by a permutation P of the
N particles, ordered in one quadrant as 1 ≤ x1 ≤ x2 ≤ . . . xN ≤ L. The N-particle
wave-function there becomes

                                                          A[P ]eikPi xi .
                                                      X
                              Ψ(x1 , . . . , xN ) =                                        (4.23)
                                                      P

Fermi or Bose statistics determines its continuation into the other sectors. (iv) The
amplitude A[P ] is determined by the conditions of continuity of Ψ as xi → xi+1 and
periodic boundary conditions Ψ(x1 , . . . , xN ) = Ψ(x2 , . . . , xN , x1 + L). The problem is the
computation of A[P ]. (v) Introducing spin, suppose we have N electrons, M of which
have spin ↓, on a lattice with L sites xi . One must then ensure that the factorization

                                                   66
of the S-matrix is not perturbed by the spin indices (Yang-Baxter conditions). There
is then a second permutation Q for the spin labels, and the wave function where the
M down-spins occupy the sites x1 . . . xM and the N − M up-spins the sites xM +1 . . . xN
is denoted by Ψ(x1 , . . . , xM , xM +1 , . . . , xN ). The Bethe Ansatz postulates that in each
quadrant characterized by Q, i.e. 1 ≤ xQ1 ≤ xQ2 ≤ . . . xQN ≤ L, the wave function is
given by [83]
                                                                                                     
                                                          X                            N
                                                                                       X
             Ψ(x1 , . . . , xM , xM +1 , . . . , xN ) =        A[Q, P ] exp i                kP j xQj  .       (4.24)
                                                           P                           j=1

The N numbers ki are determined from the coupled Lieb-Wu equations (u = U/4t)
                                     M
                                                                        !
                                     X   sin kj − Λβ
            2πIj    = Lkj − 2     arctan                                       ,                                 (4.25)
                              β=1              u
                              N                                         M
                                                               !
                                   Λα − sin kj                                                Λα − Λβ
                              X                                         X                              
            2πJα    = 2     arctan                                 −2         arctan                         ,   (4.26)
                        j=1            u                                β=1                     2u
                          (                                              (
                              integer                                         even
               Ij =                                if M =                                     ,                  (4.27)
                              half − odd − integer                            odd
                          (                                                        (
                              integer                                                  odd
               Jα =                                if N − M =                                     .
                              half − odd − integer                                     even
The total energy and momentum of the system are then
                                            N
                                            X                               N
                                                                            X
                                  E = −2t         cos ki ,         P =             ki .                          (4.28)
                                            i=1                             i=1

     Eqs. (4.24) – (4.28) give the exact energy and wavefunction of the 1D Hubbard
model. The quantum numbers ki are the momenta of the particles characterizing the
orbital degrees of freedom. Unlike for free particles, they are not equally spaced but
shifted by the presence of the other particles. The Λα are called rapidities and describe
the spin state. On the other hand, the integers or half-odd-integers Ii and Jα are equally
spaced. The ground state is obtained by occupying the levels with minimal |Ii| and
|Jα |. Therefore the distribution of qi = 2πIi /L and pα = 2πJα /L is given by a Fermi
distribution Θ(kF ↑ + kF ↓ − qi ) and Θ(kF ↓ − pα ), respectively. In the absence of a magnetic
ﬁeld, the ground state has kF ↑ + kF ↓ = 2kF and kF ↓ = kF , so that the qi have a doubled
Fermi wavevector while the pα have the normal kF .
     This splitting of the Fermi surface into two can be clariﬁed further by studying the
elementary excitations. Two of them are obtained by making a hole either in the Ii - or in
the Jα -distribution. In the ﬁrst case, one obtains a charged, spinless holon, in the second
case a neutral spin-1/2 spinon. Both holon and spinon live in the lower Hubbard band.
There are other solitonic excitations involving doubly occupied sites which therefore build
up the upper Hubbard band [106]. In general, holons and spinons are not independent,
and the Lieb-Wu equations (4.25), (4.26) imply that they interact. Introducing a real hole
will aﬀect both channels. Moreover, the representation of physical electrons and holes in
terms of holons and spinons is not known to date.

                                                          67
   The interaction of holons and spinons complicates the calculation of their dispersion.
Simple results are obtained only for weak or strong U. Then, the holons obey
                                (
                                    4t cos(qa/2) − 2t cos(kF a) for u ≪ 1
                   ε(h) (q) =                                                               .     (4.29)
                                    2t cos(qa)                  for u ≫ 1
                                (h)            (h)
Their Fermi surface is at kF = 2kF , εF = −µ. The spinon have dispersion
                                    (
                       (s)              2t[cos(qa) − cos(kF a)] for u ≪ 1
                      ε (q) =                                                           .         (4.30)
                                        (π/2)Jef f cos(qa/n)    for u ≫ 1

The eﬀective exchange integral is

                                              4t2
                                                                          !
                                                     sin(2πn)
                                      Jef f =     n−                          .                   (4.31)
                                              U         2π
                                                   (s)
The dispersion is only deﬁned for q ≤ kF = kF , and the energy becomes zero at kF . The
ﬁrst feature translates the reduced Brillouin zone of the compressed Heisenberg chain,
and the second one implies that spinon-antispinon pairs can be created spontaneously.
    The wavefunction (4.24) is not of much practical value due to its enormous complex-
ity: in fact, there are about N!2 expansion coeﬃcients A[Q, P ]! In the calculation of
the wavefunction, there is no gain with respect to brute-force exact diagonalization. A
calculation of correlation functions, and especially of their asymptotic behaviour, based
on the Bethe Ansatz is therefore elusive.
    Important simpliﬁcations occur in the limit U → ∞ [107]. The members on the left-
hand sides of Eqs. (4.25) and (4.26) are of order O(U 0 ). For the equalities to hold, the
Λ on the right-hand sides must be proportional to u: Λα = 2uλα making the sin kj -terms
negligible. This simpliﬁes the Lieb-Wu equations to
                                             M
                                             X
                    2πIj = Lkj + 2                 arctan (2λβ )      ,                           (4.32)
                                             β=1
                                                              M
                                                              X
                    2πJα = 2N arctan (2λα ) − 2                     arctan (λα − λβ )       .     (4.33)
                                                              β=1

The equations for kj and λα now decouple and can be solved successively. Concomitant
with this decoupling is a decoupling of the wave function (for the quadrant Q)
                                                                      h           i
              Ψ(x1 , . . . , xM , xM +1 , . . . , xN ) = (−1)Q det eiki xQj Φ(y1 , . . . , yM )   (4.34)

into a charge and a spin part. det[...] is a Slater determinant involving only the particle
positions irrespective of their spin, i.e. describing free spinless fermions. Φ(y1 , . . . , yM ) is
the Bethe Ansatz wave function of a Heisenberg chain [81] of the N spins, characterized
through the positions of the M down-spins, on a compressed lattice of just N sites. This
decoupling of the wave function means a complete charge-spin separation over all energy
scales in the U → ∞-Hubbard model and is correct to O(1/u).


                                                         68
    The wave function (4.34) can be evaluated numerically for much bigger systems than
(4.24) and, combined with either ﬁnite-size scaling or further analytical work, allows to
discuss the asymptotic low-energy properties and the critical exponents of correlation
functions. Applications will be discussed in the following section. We also note that there
is a systematic large-U expansion for the distribution functions of the momenta k and
rapidities Λ [108].


4.4.3     Low-energy properties of one-dimensional lattice models
In the ﬁrst part of this section, we shall discuss various successful methods to derive the
correlation exponents of interacting electrons in 1D lattices, taking the Hubbard model
as an example. At the end, we brieﬂy summarize the physical picture and then outline
the changes occurring when going to the variants introduced in Section 4.4.1.
    Early studies of correlation functions heavily relied on numerical simulation of Hub-
bard and extended Hubbard models. Hirsch and Scalapino used quantum Monte Carlo
techniques to directly study the density and spin density correlation functions at various
band-ﬁllings and interaction strengths on lattices of 20 – 40 sites at temperatures down
to about t/15 [109]. Of course, both the ﬁnite temperatures and the accuracy of the
simulations did not allow a determination of the correlation exponents and thus of Kρ ,
but one main point of concern was the doubling of the wave vector of divergence in the
charge density response from 2kF to 4kF as interactions are increased and/or V is turned
on. This could be rephrased in terms of the present language as under what conditions
Kρ +1 < (>) 4Kρ i.e. Kρ < (>) 1/3 which marks the value where 2kF - and 4kF -responses
are equally divergent. Quite generally, it was found that increasing U decreases the 2kF -
CDW-correlations but somewhat increases the 4kF -CDW as U → ∞. The decrease at
2kF was less, however, if charge density ﬂuctuations were measured on the bonds between
lattice sites (bond order wave, BOW) rather than on the lattice sites themselves. The
2kF -SDW correlations were enhanced by U. This is quite easy to understand physically:
U generates antiferromagnetic spin exchange but suppresses on-site charge ﬂuctuations
while intersite ﬂuctuations remain unaﬀected, at least at lowest order in U. On the other
hand, for U → ∞, the electrons behave as spinless fermions with a Peierls divergence
              (s=0)     (s=1/2)
vector of 2kF       = 4kF       . Adding a nearest-neighbour repulsion V strongly favours
the 4kF -CDW, especially on-site and in quarter-ﬁlled bands, also enhances the SDW and
further suppresses the 2kF -CDW: the energies due to both U and V are minimized when
the particles occupy every second site, i.e. forming a 4kF -CDW.
    The suppression of the 2kF -CDW by U and V is interesting in view of the general
expression for the density correlations in a Luttinger liquid, Eqs. (3.92) and (3.102) which
imply that both exponents of divergence at 2kF and 4kF increase with decreasing Kρ and
thus with increasing U and V . The suppression of the 2kF -CDW then must be due to the
inﬂuence of U on its prefactor which must decrease as U increases. Hirsch and Scalapino
demonstrate this by showing that, at low enough temperature and various U, both SDW
and CDW diverge with the same exponent but that the scale where the asymptotic be-
haviour is observed, is vastly diﬀerent and, in fact, very low for the CDWs [109]. A related

                                            69
suppression of 2kF -CDW correlations due to the prefactor (with a concomitant enhance-
ment of SDW and BOW) can also demonstrated for a half-ﬁlled band in renormalization
group [78].
    More extended results on the inﬂuence of band-ﬁlling and interaction range on the
competition of 2kF - and 4kF -CDWs have been produced by Mazumdar, Dixit, and Bloch
[110]. They also propose a qualitative but systematic picture predicting the appearance
of 2kF - or 4kF -CDWs, in terms of the contribution to the ground state wave function of
certain extreme symmetry broken conﬁgurations and the barriers to resonance between
them. Speciﬁcally, for the quarter-ﬁlled band, ﬁnite V is necessary to promote a 4kF -
CDW but an eventual second-neighbour repulsion V2 must be small: V2 < V /2. For
1/2 < n < 2/3, however, a new kind of defect-CDW with periodicity π/a is found
possible and competes with the 4kF one, depending on the precise values of the interaction
constants. Long-range interactions are necessary to stabilize a 4kF -CDW for n > 2/3,
and the generic CDW will be at 2kF . The competition between 2kF - and 4kF -CDWs
will reappear below in terms of the Luttinger parameter Kρ being smaller or larger than
1/3. For the special case of n = 1/2, electron-phonon coupling has also been included
recently [111]. Also, a more systematic theory for a Luttinger liquid ﬂoating on top of a
commensurate CDW, e.g. with qCDW = π/a, will be given at the end of this section [112].
    Subsequent work rather turned attention to single-particle properties and to the ques-
tion of (non)-Fermi-liquid behaviour in the 1D Hubbard model. Several quantum Monte
Carlo studies indicated a ﬁnite jump in the momentum distribution function n(k) at kF ,
to be compared with the Luttinger prediction (3.86) [113]-[116]. Notice, however, that
Equation (3.86) applies to an inﬁnite system. Finite size eﬀects give n(k) a ﬁnite jump
at kF whose scaling is governed by the exponent α [57, 115]

                    ∆n(kF ) = n(kF − π/L) − n(kF + π/L) ∼ L−α ,                     (4.35)

subsequently identiﬁed in improved simulations [117]. The absence of any signiﬁcant
rounding expected from the power-law behaviour in n(k), up to about 200 lattice sites
indicates, however, that the asymptotic Luttinger regime in the 1D Hubbard model is
conﬁned to a tiny momentum slice around the Fermi surface, whose smallness, in fact,
remains surprising. (With reference to the diﬀerent scales in diﬀerent quantities, identi-
ﬁed by Hirsch and Scalapino [109] and discussed above, this does not necessarily imply
that Luttinger liquid correlations in all other quantities are conﬁned to such small mo-
mentum/energy scales.)
    Sorella et al. also studied the divergences of the density and spin density correlation
functions of the 1D Hubbard model and could identify the diﬀerent exponents from ﬁnite-
size scaling [117]. In particular, they were able to verify the scaling relations between
αCDW , αSDW , and α4kF , Eqs. (3.92) – (3.98), implied by their dependence upon Kρ alone
(Kσ = 1 for SU(2)-invariance), and they found an upper limit α = 1/8 as U → ∞,
implying Kρ ≥ 1/2.
    These exponents can be determined exactly from the U → ∞ Bethe wave function



                                            70
[107]. We study the momentum distribution function
                                                 1X †
                          n(k) = hc†ks cks i =        hc cls ieik(j−l)a .                 (4.36)
                                                 L j,l js

At this stage, the real-space representation of the Bethe wave function can be used. In
order to transfer an electron from site l to j, we have to take out of the Slater determinant
one spinless fermion at l and reinsert it at j. At the same time, the spin conﬁguration is
changed: we must take out of the Heisenberg chain the spin at l′ , corresponding to the
electron at l (l 6= l′ because of the compressed lattice), and insert it again at j ′ correspond-
ing to the new electron site j which can also be viewed as permuting neighbouring spins
successively between l′ and j ′ . Then, one has to sum over all conﬁgurations of the spin-
less fermions, as implied by the average h...i in (4.36) taken over the wavefunction (4.34).
The permutation of two neighbouring spins is mediated by the operator 2Si · Si+1 + 1/2
so that the evaluation of the spin contribution to n(k) requires calculation a correlation
function of j − l of these operators for each conﬁguration of spinless fermions. The charge
contribution, on the other hand, is just the product of two Slater determinants.
    Ogata and Shiba solved these functions numerically and obtained a function n(k)
characterized by a jump at kF and, surprisingly at that time, another weak singularity at
3kF , shown in Fig. 4.3. Both of these facts were somewhat surprising because the spinless
fermions’ n(k) jumps at 2kF which thus appeared a natural candidate for Fermi surface
of the U → ∞-Hubbard model. However, the electrons involved in n(k) both contain a
charge and a spin component, and the spins feed back into the charges by the kernel on the
right-hand side of (4.32). The (re-)appearance of kF and 3kF is due to oscillations with
wavevector ±2kF in the spin contribution to n(k). A careful ﬁnite-size-scaling analysis
showed that the apparent jump at kF would fade away as L → ∞ and that the variation of
n(k) with system size was compatible with the Luttinger liquid power law (3.86) with an
exponent α ≈ 0.14. The 3kF -singularity was shown to be due an excitation of kF -fermions
to 3kF accompanied by creation of electron-hole pairs with -2kF , and is also required by
the picture of Section 4.2. They also studied the spin-spin correlation function at q = 2kF .
From the singularity observed as a function of q they inferred a decay in real space as
RSDW (x) ∼ cos(2kF x)x−1.44 while their results for the Heisenberg model were consistent
with the known form ∼ cos(πx) ln1/2 (x)/x [79, 118].
    An analytical evaluation of these quantities is also possible [119]-[121]. Parola and
Sorella started from an evaluation of the spin-spin correlation function [119]
                                            r+1
                                                   r
                                            X
                             < Sr · S0 >=         PSF (j)SH (j − 1) ,                     (4.37)
                                            j=2

                                                                                       r
where SH (j) is the (known) spin correlation function of the Heisenberg model and PSF    (j)
is the probability of ﬁnding j (spinless) particles between 0 and r with one at 0 and one at
r. The evaluation of this latter quantity is diﬃcult but at least asymptotically possible,
and one ﬁnds
                                                       ln1/2 r
                              < Sr · S0 >≈ cos(2kF r) 3/2 ,                           (4.38)
                                                        r

                                                  71
which is consistent with the Luttinger liquid function (3.98) provided Kρ = 1/2. This
implies an exponent α = 1/8 for the momentum distribution function n(k) of the U = ∞-
Hubbard model at kF , in quite good agreement with the numerical data of Ogata and
Shiba. Parola and Sorella could recalculate analytically the momentum distribution,
following the procedure by Ogata and Shiba and, ﬁxing two open parameters so as to
reproduce the behaviour at kF , were able to identify the exponent at 3kF as α3kF = 9/8
[120], a value also found by others [65, 122].
    Anderson and Ren compute the correlation exponents of the Hubbard model in the
U → ∞-limit in a more physical way [122]. They observe that the Ogata-Shiba wave
function implies charge-spin separation only for those excitations which take place solely
in one channel. If we consider correlation functions of excitations aﬀecting both channels,
phase shifts will arise in the distribution of the momenta {ki} due to changes in the
rapidity-distribution. This is due to the kernel on the right-hand side of Eq. (4.32), and
to the parity eﬀects in the distributions of the quantum numbers Ii and Jα in the Lieb-
Wu equations, cf. (4.27). As an example, the Green function for the holon at +2kF is
G(h) (x, t) ∼ e2ikF x /(x − vρ t) and involves only charge degrees of freedom: if one adds an
Ii to the system, the rapidities do not change. Removing a spinon at −kF , i.e. a Jα , there
is a phase shift of δ±2kF = π/2 of all holon momenta in the same direction. The spinon
                                                                √
Green function, which for the Heisenberg model is eikF x / x − vσ t, will therefore also
contain a contribution from the phase shift of the holons which reduces the overlap with
                                                                                         2
the “unshifted” ground state wave function. This introduces a factor (x ± vρ t)−(δ/2π) for
the phase shifts on each side of the momentum distribution. The 2kF -spin-spin correlation
function consists of a right-moving particle (spinon) and a left-moving hole (antispinon).
Each of them shifts the ki -distribution in the same direction, so that the total phase shift
is δ±2kF = π on each side. Putting everything together, we have
                                                  cos(2kF x)
           hS(xt) · S(00)i =
                                (x − vσ t) (x + vσ t)1/2 (x − vρ t)1/4 (x + vρ t)1/4
                                          1/2

                            =   x−3/2 cos(2kF x) for t = 0 .                           (4.39)
The 4kF -CDW only involves a right-moving holon and a left-moving antiholon, and there-
fore is decoupled from the spins
                                  †                cos(4kF x)
                       hO4kF (xt)O4k   (00)i =                      .            (4.40)
                                     F
                                               (x − vρ t)(x + vρ t)
Other interesting examples are provided by the kF - and 3kF -pieces of the single-particle
Green function. Here, one has to take out (add) both a holon and a spinon. One can
take out the holon at 2kF and the spinon at −kF . The removal of the spinon shifts the
holon momenta by π/2 in the positive direction, and this phase shift cancels a quarter of
the 2π-shift caused by the holon removal at 2kF : δ2kF = 3π/2 while δ−2kF = π/2. This
process determines the kF -component. One can, however, also take out the spinon at
+kF , and then the ensuing phase shift adds to that of the holon removal δ2kF = 5π/2.
This determines the 3kF -Green function. We have
                                              exp[i(2kF ± kF )x]
                GkF (3kF ) (xt) =                                                 . (4.41)
                                  (x − vσ t)1/2 (x − vρ t)(1∓1/4)2 (x + vρ t)1/16

                                             72
All these correlation functions agree with the Luttinger liquid expressions taken at Kρ =
1/2.
     The removal or addition of spinons and holons can also be interpreted in terms of
the charge and current excitations of a Luttinger liquid in the charge and spin channels.
One can consider the 3kF -component of the Green function as being due to an additional
current excitation with momentum 2kF with respect to the kF -piece. Anderson and Ren
also prove that the correlation exponents of the Green function, which can be derived from
the kernels of the Lieb-Wu equations (4.25) and (4.26) [75], are precisely the Fermi-surface
phase shifts due to the insertion of an additional particle [122].
     The applicability of these methods is, however, quite restricted: (i) there are many
models which cannot be solved exactly, and (ii) even if a Bethe Ansatz solution is available,
manageable simpliﬁcations generally only occur in special limits such as U → ∞ for the
Hubbard model. On the other hand, the notion of a Luttinger liquid is based on the
low-energy properties of a many-body problem, and a priori, a complete solution is not
required. Following Haldane [49] and Section 3.2.2, a Luttinger liquid can be identiﬁed
and its characteristic parameters determined by using only the low-energy spectrum of
the lattice Hamiltonian. These can be found reliably either from an exact solution or by
numerical diagonalization.
     One general method is due to Efetov and Larkin [10] and Haldane [3, 49] where it
was formulated for a spinless fermion system, and then extended by Schulz [42, 48] for
models of S = 1/2-electrons. Here, one formulates an eﬀective Luttinger Hamiltonian for
the low-energy physics and then identiﬁes its parameters Kν , vν from the properties of the
exact solution. Central to this approach is the use of the relations between the correlation
exponents Kν and the renormalized velocities [49] vN ν = vν /Kν , ; vJν = vν Kν , Eq. (3.32).
To identify the Luttinger liquid one must, in principle, determine the three velocities
vν , vN ν , and vJν per degree of freedom and check that they satisfy (3.32). Kν is then
obtained automatically. In practice, this programme is rarely carried out to this point
(with the notable exception of [75]). Rather, one assumes (3.32) to hold and determines
both vν and vN ν which are suﬃcient to yield the remaining parameters Kν . vN ρ = vρ /Kρ
is related to the compressibility κ by Eq. (3.62) κ−1 = L−1 ∂ 2 E/∂n2 = πvN ρ /2, and
the change of the ground state energy with particle density n can be readily determined
by Bethe Ansatz or numerical methods. A similar relation (3.62) for vN σ = vσ /Kσ to
the magnetic susceptibility can be explored in the spin sector. If the system is spin-
rotation invariant, Kσ = 1 and vσ is found. In the charge sector, vρ must be determined
independently from the low-energy spectrum of charge excitations. To identify which
type of excitations in the Bethe Ansatz is relevant, one can realize, as does Schulz [42],
from the boson representation (3.90) that the 4kF -CDW operator involves only charge
degrees of freedom and then argue that power-law decay of this correlation function must
originate from gapless excitations at that wavevector. These “particle-hole” excitations
have been known since a long time [105], and their velocity is

                                             ε(k0 , p0 )
                                   vρ = lim              .                            (4.42)
                                         p→0 p(k0 , p0 )



                                              73
Operationally, in the Bethe Ansatz wave function, take one particle with pseudo-momentum
k0 out of the ﬁlled (charge) pseudo-Fermi sea and put it into one of the empty states above
at pseudo-momentum p0 . Find the energy ε(k0 , p0 ) and (physical) momentum p(k0 , p0 )
associated with this excitation; then take the limit p → 0. This gives vρ , and Kρ is
then determined, too. Ultimately, the correlation exponent Kρ is fully determined by
thermodynamic properties [3, 10, 48, 49].
    This procedure does not suﬀer from the limitations of perturbative renormalization
group and allows an exact calculation of the Luttinger liquid parameters. Being related
to properties of the eigenvalue spectrum, it can easily be adapted to numerical exact
diagonalization studies. One concern might be ﬁnite size eﬀects because the numerical
solutions are conﬁned to small systems. They are, however, not critical here since the
energies of the low-lying states usually converge rather quickly to the inﬁnite system limit.
    One can also apply conformal ﬁeld theory methods to determine the correlation ex-
ponents of the Hubbard model. Conformal ﬁeld theory, as we have sketched it in Section
3.6, requires a Lorentz-invariant system [29]. This is the case for spinless fermions (or
models of the same universality class) with only one branch of gapless excitations, and
has consequently been applied to such problems with great success [74]. The Hubbard
model and all other models in the universality class of a spin-1/2 Luttinger liquid are not
Lorentz-invariant because the spin and charge velocities vσ 6= vρ play the roles of two dif-
ferent velocities of light. Each channel ν taken by itself is conformally invariant, however,
described by a Virasoro algebra with central charge cν = 1. The complete theory is then
described by a semidirect product of these Virasoro algebras, and the scaling dimensions
of operators now depend, instead of a single coupling constant, on an N × N-matrix of
coupling constants, the “dressed charge matrix”, for an N-component system [123].
    Frahm and Korepin have applied these methods to the 1D Hubbard model in order
to deduce the long-distance asymptotics of its correlation functions [124]. The idea is the
following: the elements of the dressed charge matrix
                                         !                              !
                               Zcc Zcs            ξcc (k0 ) ξcs (Λ0 )
                        Z≡                   =                                       (4.43)
                               Zsc Zss            ξsc (k0 ) ξss (Λ0 )
(and, of course, the velocities of the gapless excitations vν ) can be evaluated from the
Bethe Ansatz. Its entries ξ obey equations derived from and similar to the Lieb-Wu
equations (4.25), (4.26), with the limit L → ∞ taken. k0 and Λ0 are the cutoﬀs in the
distribution functions of the momenta and rapidities. The entries of the dressed charge
matrix are related to thermodynamic quantities of the model in much the same way as
the eﬀective coupling constant of spinless fermions is. For example, Frahm and Korepin
ﬁnd [124]
                                      2
                                     ξcc (k0 ) = πvρ n2 κ                           (4.44)
where κ is the compressibility and n the charge density. Comparing (4.44) to (3.62),
             2
we see that ξcc (k0 ) is essentially Kρ , up to a factor n2 . This formula has been derived
independently by Kawakami and Yang [125], who use earlier Bethe Ansatz evaluations of
on the thermodynamic properties in order to get ξcc as a function of the system parameters.
These authors, however, neglect the oﬀ-diagonal elements of the dressed charge matrix.

                                             74
    In analogy to Section 3.6, conformal invariance then determines the scaling dimensions
of (primary and descendant) operators. The role of the coupling constant g of the Gaussian
model is now played by the matrix Z. ∆Nc(s) and Dc(s) , later grouped into vectors ∆N
and D, count the charges (c) and spins (s) added by the ﬁeld φ to the Bethe Ansatz
distribution and are (up to linear combination) the changes in the charge and current
excitations of the Luttinger model [126]. The ground state has ∆N = D = 0. Allowed
values of D depend on ∆N. For example, for a fermion operator c†±kF ,↑ , ∆N = (1, 0),
D = (±1/2, ∓1/2), for c†±kF ,↓ , ∆N = (1, 1), D = (0, ±1/2), and for the density operator
                                     ±                                             P ±
ρ, one has ∆N = 0. Numbers Nc(s)        characterize descendent ﬁelds φ at level Nc(s)   .
                       ±
Primary ﬁelds have Nc,s = 0, and ﬁnite values describe secondary ﬁelds. The correlation
functions of the primary and descendent ﬁelds φ∆± with scaling dimensions ∆± are given
by conformal ﬁeld theory as
                                    exp[−2iDc PF,↑ x] exp[−2i(Dc + Ds )PF,↓ x]
   hφ∆± (x, t)φ∆± (0, 0)i =                +              −              +              −          (4.45)
                              (x − ivρ t)2∆c (x + ivρ t)2∆c (x − ivσ t)2∆s (x + ivσ t)2∆s
which is a direct generalization of (3.163) to a two-component system.
    As in Section 3.6, the central charge and the scaling dimensions can be obtained from
the ﬁnite size corrections to the energy of the ground state and the energies and momenta
of low-lying excited states of the system. For c = 1 in both the charge and spin channel,
(3.157) generalizes to
                                            π                 1
                                                                       
                         E0 (L) − Lε0 = − (vρ + vσ ) + O            ,                 (4.46)
                                           6L                 L
where the symbol O(1/L) stands for terms decaying faster than 1/L. E0 is the ground
state energy at size L, and ε0 is the energy density in the inﬁnite system. Eq. (4.46) must
be veriﬁed by the solution. Eqs. (3.161) and (3.162) for energy and momentum of the
low-lying excitations are given by
                          2π h                                      1
                                                            i                     
      E(∆N, D) − E0 =         vρ (∆+     −           +   −
                                    c + ∆c ) + vσ (∆s + ∆s ) + O         ,         (4.47)
                          L                                         L
                          2π  +                      
      P (∆N, D) − P0 =         ∆c − ∆− c + ∆ +
                                             s −  ∆ −
                                                    s + 2Dc PF ↑ + 2(Dc + Ds )PF ↓ .
                          L
On the other hand, these quantities can be computed from the Bethe Ansatz (or numer-
ically) as
                       2π               1
                                    
       E(∆N, D) − E0 =                    ∆NT · (Z −1 )T · (diag[vρ , vσ ]) · Z −1 · ∆N+           (4.48)
                       L                4
                                                                                          1
                                                                                   o          
         T                           T
    + D · Z · (diag[vρ , vσ ]) · Z       · D + vρ (Nc+ + Nc− ) + vσ (Ns+ + Ns− )       +O          ,
                                                                                          L
                 2π n                                   o
P (∆N, D) − P0 =      ∆NT · D + Nc+ − Nc− + Ns+ − Ns− + 2Dc PF,↑ + 2(Dc + Ds )PF,↓ .
                 L
Comparing Eqs. (4.48) to (4.47) one deduces the scaling dimensions
                                         Zss ∆Nc − Zcs ∆Ns 2
                                                                             
         2∆±
           c (∆N, D) =            Zcc Dc + Zsc Ds ±          + 2Nc± ,
                                              2 det Z
                                         Zcc ∆Ns − Zsc ∆Nc 2
                                                         
           ±
         2∆s (∆N, D) = Zcs Dc + Zss Ds ±                     + 2Ns± .                              (4.49)
                                              2 det Z

                                                    75
    In order to obtain the correlation functions of the Hubbard model, on would have
to expand the physical operators O in terms of the conformal ﬁelds. This is usually
not possible. On the other hand, the quantum numbers of the intermediate states can be
determined from the representation of the operators O in terms of the electron creation and
annihilation operators. We have given examples above. Then, the complete asymptotic
behaviour of the correlation functions can be given in terms of the scaling dimensions and
thus in terms of the dressed charge matrix Z whose entries depend on U and the bandﬁlling
n. As an example, the ﬁrst few terms of the complete density-density correlation function
are given by Frahm and Korepin [124] and, in the absence of a magnetic ﬁeld, reduce to
Eqs. (3.91)–(3.93) when the appropriate Kρ is inserted there. In this way, the conformal
ﬁelds contributing to the density-density correlations are not explicitly identiﬁed. The
knowledge of their scaling dimensions is suﬃcient to determine their contribution to the
correlation function. Penc and Solyom have ﬁnally deduced explicit Tomonaga-Luttinger
coupling constants gi from the dressed charge matrix and the scaling dimensions of the
Hubbard model [126].
    While the asymptotic correlation exponents agree with the approach by Schulz [42,
48] and Kawakami and Yang [125], there are some subtle diﬀerences. In general, in
the absence of magnetic ﬁelds, Z is not diagonal as naively expected for charge-spin
separation. However, one of the matrix elements Zcs = 0 and Zsc = Zcc /2 which gives
critical exponents identical to those for a charge-spin separating system as assumed by
Schulz. One can include an external magnetic ﬁeld [127]. Then, there is no longer a simple
relation between the elements of Z, the exponents now diﬀer from those derived under
the assumption of charge-spin separation, and charge and spin are strongly coupled. On
the other hand, the dressed charge matrix is probably not a good quantity to “measure”
charge-spin separation, because it does not change in any essential way in the limit U → ∞
where we know [107] that the product form of the Bethe wavefunction implies complete
charge-spin separation.
    The dependence of Kρ on U and n is shown in Fig. 4.4, and that of the velocities vν in
Fig. 4.5 [48]. For small U, the variation of Kρ with U is consistent with the perturbative
result Kρ ≈ 1 − U/πvF , and the slope varies with bandﬁlling due to the n-dependence of
the Fermi velocity vF = 2t sin(πn/2). At larger U, Kρ deviates from a straight line and
Kρ → 1/2 for U → ∞ for all n. Kρ = 1/2 is also the limit for n → 0 for any U > 0 which
is quite obvious due to the n-dependence of vF . Also Kρ → 1/2 for n → 1, (U > 0), cf.
below. The velocities vν → vF for U → 0 as expected, and as U → ∞, vρ = 2t sin(πn)
and vσ = (2πt2 /U)[1 − sin(2πn)/(2πn)]. While vρ ∝ n for all U and small n, vσ ∝ n2 for
U > 0 and ∝ n for U = 0.
    These parameters can then be inserted into the results obtained in Section 3.3 to obtain
the correlation functions of the Hubbard model as a function of U and n. In particular,
for U → ∞, one obtains α → 1/8, αCDW,SDW → 1/2 and α4kF → 0. The properties of
the charge degrees of freedom in this limit can be straightforwardly understood in terms
of spinless fermions, in agreement with the factorization of the Bethe wave function. E.g.
the 4kF -part of the density-density correlations is simply the 2kF -CDW of free spinless
fermions with a doubled Fermi wavevector. The large-U limit of vρ is simply the Fermi

                                            76
velocity of free spinless fermions with a hopping integral t. Also close to half-ﬁlling even
at ﬁnite U, a spinless fermion picture applies: here one best thinks in terms of a few
holes doped into the insulating half-ﬁlled band, and the repulsion U is accounted for
by treating them as spinless fermions. When there are very few of them, their mutual
interaction will be negligible. This explains the value Kρ = 1/2 found for all U as n → 1.
The spinless fermion picture also implies that the prefactor of the 2kF -part of the density-
density correlation function must vanish as U → ∞. More care has to be taken for spin
or single-particle correlations. The ground state of the Hubbard model can be viewed as
containing a number of holons appropriate to the doping level but no spinons. In this
way, it becomes clear that the characteristic wave vector for the SDW oscillations 2kF
shifts with doping due to the introduction of holes although in a local picture, there are no
conﬁgurations of parallel neighbouring spins [42]. The motion of holons disrupts the spin
correlations and therefore leads to a more rapid decay of the spin-spin correlations than in
the half-ﬁlled band or a Heisenberg antiferromagnet. Introducing a hole (or an electron)
creates, however, a holon at ±2kF and a spinon at ±kF , and therefore the single-particle
Green function oscillates with wavevectors kF , 3kF , etc.
    The low-energy spectral function of the Hubbard model, obtained by inserting α =
1/8 for the limit U → ∞ into the Luttinger model, is shown in Fig. 3.6. It is clearly
dominated by the spectral weight between vσ and vρ , and the weight above/below ±vρ
is quite negligible. Comparison to functions of models with either charge-spin separation
or anomalous dimensions only, suggests that charge-spin separation is the dominant non-
Fermi-liquid feature in the 1D Hubbard model [53, 59, 60]. Even for inﬁnite repulsion,
the anomalous correlations are quite weak. Physically, this implies that the power-laws
in the correlations are most sensitive to the range of the interaction, taken ﬁnite in the
Luttinger but zero in the Hubbard model, while the inﬂuence of short-range interactions
is strong on charge-spin separation. This allows to rationalize the small momentum range,
where Luttinger liquid behaviour is seen in n(k) in Figure 4.3. Unfortunately, no signature
of charge-spin separation has been detected in a Monte-Carlo simulation of the spectral
function directly of the Hubbard model [128]. This could be due to ﬁnite system size
and/or temperature, but certainly needs further study.
    Correlation functions of the t − J-model behave in a similar manner and also identify
it as a Luttinger liquid [129, 130]. Speciﬁcally, at the supersymmetric point J/t = 2,
where the model is solvable by Bethe Ansatz, conformal ﬁeld theory allows to derive the
dependence of Kρ on band-ﬁlling [129], in a similar manner as for the Hubbard model.
It obeys to the same limits as for the U > 0 Hubbard model 1 ≥ Kρ ≥ 1/2 but tends
towards the free value for the nearly empty band, while in this limit the Hubbard model
behaves as if U → ∞. On going away from the supersymmetric point, the model is
no longer solvable, and one has to turn to numerical diagonalization on small clusters
to obtain the correlation exponents [130]. Again, one uses Eq. (3.62) to obtain vρ /Kρ
and separately studies the spectrum of the charge excitations. While Kρ continues to
obey to the lower bound Kρ ≥ 1/2 (the equality holding for empty bands at J < 2t,
half-ﬁlled bands at J < 3.5t and at J = 0 for any ﬁlling), Kρ > 1 now occurs for
larger values of J. Eqs. (3.99) and (3.100) imply a region of dominant superconducting

                                             77
ﬂuctuations. According to the general scaling arguments above, logarithmic corrections
would favour the triplet type if the spins are massless, while opening of a spin gap would
make singlet superconductivity dominate. Evidence for a spin gap has been produced
by using variational wavefunctions, a procedure to be discussed below [131]. Imada and
Hatsugai also measured spin correlation functions in their Monte Carlo simulations [116].
While for small J/t, their results are quite close to those of the Hubbard model found by
Hirsch and Scalapino [109], the spin correlations become commensurate, i.e. peaked at
q = π/a rather than at 2kF as J increases. In this regime, the holes in the t − J-model
probably act as mobile defects in a short-range-ordered antiferromagnetic background.
Finally, in the large-J region (> 2 . . . 3.5t depending on n), phase separation occurs: here
the attraction due to the interaction terms in Eq. (4.21) is optimized at the expense of
the kinetic energy. The point J = 2t, n = 0 is possibly singular and Kρ there may depend
on the order of the limits.
    The phase diagram and the Luttinger liquid correlations of the t − J-model have also
been established from variational wave functions [131, 132, 133]. This result is particularly
noteworthy because these functions can be generalized into higher dimensions where exact
solutions generally are not possible and numerical studies are severely limited by ﬁnite
size eﬀects (Section 6.2). Recall that, on a technical level, a major problem in treating the
t − J-model with analytical methods, is the implementation of the constraint of excluded
double occupancy. This constraint is implemented, however, in a variational wave function
due to Gutzwiller [134]

                                                                                        c†k↑ c†k↓ |0i ,
                           Y                                                  Y
               |ΨG i =          (1 − ni↑ ni↓ )|F Si with |F Si =                                                   (4.50)
                           i                                              |k|<kF

where |F Si is the ﬁlled Fermi sea and |0i the vacuum. This wave function yields rather
good energies but the correlation hole between two particles it contains is too short. The
momentum distribution has a sharp jump at kF but the spin correlations (at n = 1) are
pretty close to the exact ones for a Heisenberg chain [135]. To ﬁnd a way to increase the
range of correlations, notice the following. |ΨG i provides an exact solution to spin chains
with an exchange integral falling oﬀ as J ∝ r −2 [136]. In the course of this solution, it
has been shown that |ΨG i can be rewritten as
                                                                                            π
                                                                                                          
                       iqi rj         ipi rj            −                           2
               X                                   Y                    Y
     |ΨG i =       det(e        ) det(e        )       S (rj )|F Mi ∝         sin             (ri − rj )       ,   (4.51)
                                                   j                    i<j                 L

where |F Mi denotes the fully (up)- spin-polarized ferromagnetic chain and j labels the
sites of the overturned spins. The size of the correlation hole can now be increased simply
by increasing the power of the sines (Jastrow factor):
                                                                   ν
                                                    π
                                          Y             
                                |ψν i =         sin (ri − rj )           |ψG i ,                                   (4.52)
                                        all i<j    L

where the notation under the product sign emphaised that in this product, the positions
enter irrespective of the particles’ spin direction. (|Ψν i is also related to the quantum
Hall eﬀect as will be seen in Section 6.3). This can be seen quite explicitly from |ψν |2 =

                                                            78
 i<j exp(−Vij ) with Vij  ∝ −ν ln |zi − zj | and zi = exp(2πiri /L), which represents the
Q

partition function of hard core objects with a logarithmic interaction [133]. It therefore
can serve as a natural starting point for a variational treatment of the t − J-model.
Correlation functions show power-law behaviour compatible with the Luttinger liquid
form, Section 3.3, whose exponents now depend on the optimal value of ν which is obtained
from variational Monte Carlo simulations. One can establish an explicit relation
                                                 1
                                        Kρ =                                            (4.53)
                                               2ν + 1
to the Luttinger exponent Kρ , and the numerical data are in good agreement. (4.53) can
be derived either by ﬁnding a solvable model whose ground state is given by |ψν i. Kρ can
then be extracted from the spectrum of low-lying states exactly as for the Hubbard model
above [137]. Another possibility is to computed explicitly the momentum distribution
and then identify the exponent to Eq. (3.85) [138]. Finally, by applying increasing powers
of the Hamiltonian to |Ψν i, one can obtain increasingly accurate approximations to the
exact ground state (provided that it is not orthogonal to the trial state |Ψν i), and this
method has allowed to uncover evidence for the formation of a spin gap in a region of very
low carrier density and large J/t close to the phase separation instability. In this limit, the
system is a singlet superconductor. The resulting phase diagram is given in Figure 4.6,
where “attractive Luttinger” stands for dominant TS and “repulsive Luttinger” implies
dominant SDW correlations in a Luttinger liquid. The t − J-model can be generalized to
include a J ∝ r −2 exchange, and its solutions are quite close to the Gutzwiller-Jastrow
form discussed above.
    One can also formulate Hubbard- and t − J-type models with long-range hopping
which, in the limit of half-ﬁlled band, reduce to the Haldane-Shastry spin chain [99].
These models are exactly solvable but the solution in general is not Jastrow form. Away
from half-ﬁlling, they have Luttinger liquid low-energy physics. One important element
of these models is chirality, i.e. the hopping term must be constructed in such a way that
the electronic dispersion contains only a single linear branch, corresponding to right-(or
left-) moving particles alone. In this situation, the only allowed eﬀective interaction of the
electrons is of g4 -type, Eq. (3.4), while g1 = g2 = g3 = 0. This still allows for charge-spin
separation because g4⊥ 6= 0 but the renormalized eﬀective coupling constant Kρ = 1,
the value for free fermions. This is an interesting situation because all q- or ω-dependent
correlation functions will be indistinguishable from a Fermi liquid, still there are no quasi-
particle excitations. From the discussion in Sec. 3.3 one would conclude, e.g., that the
momentum distribution of such a model is a step function n(k) = Θ(kF − k) but the
spectral function ρ(q, ω) is purely incoherent with spectral weight between vσ q and vρ q
and square-root singularities at these frequencies.
    At half-ﬁlling, the model exhibits a metal-insulator transition for U ≥ 2πt, as borne out
by a jump in the chemical potential at n = 1. How is this possible if Umklapp processes
are forbidden? As U → 2πt from below, the charge velocity diverges, corresponding to
a divergence of g4 ! At the same time, the compressibility goes to zero and the Drude
weight of the conductivity also diverges. This is due to the dispersion exhibiting a jump

                                              79
discontinuity at the Brillouin zone boundary [99]. This is pretty opposite to the standard
scenario, where relevant Umklapp processes generate the Mott-Hubbard transition, the
charge velocity vanishes, and the Drude weight has a ﬁnite jump (Sec. 5.2). Here, the
compressibility diverges and the Drude weight vanishes. The properties of the model in the
charge sector therefore are peculiar and strongly aﬀected by the pathological dispersion.
The spin ﬂuctuations, on the other hand, are more normal with a strong peak in χ(T ) at
T ∼ J = 4t2 /U, and the instantaneous spin-spin correlation function has a logarithmic
divergence at q = π, corresponding to 1/r-decay in space, as for the half-ﬁlled Hubbard
model.
    A further example for application of these methods, especially Eq. (3.62), is provided
by the extended Hubbard model, Eq. (4.19). At half-ﬁlling, this model has been studied
by many methods both analytical and numerical [50, 139]. This model possesses a rich
phase diagram but, due to the importance of Umklapp scattering here, the system is
insulating when the interactions are repulsive [50, 139]. Correlation functions and the
identiﬁcation of the phases as Luttinger liquids (eventually only in a single channel) have
been studied using renormalization group [50]. The physics away from half-ﬁlling is also
interesting. For U → ∞, we recover spinless fermions, and the model can be mapped
onto an anisotropic Heisenberg chain which again can be solved by Bethe Ansatz, so
that the correlation exponents can be deduced [140, 141]. For ﬁnite U, Mila, Zotos, and
Penc [142, 143] used numerical diagonalization combined with Eq. (3.62) to evaluate the
phase diagram and correlation functions of the quarter-ﬁlled band. The phase diagram
together with lines of constant Kρ in the positive U, V -region is given in Figure 4.7. On
a technical level, this study is noteworthy because it is one of the few instances where
the three velocities vN ρ , vρ , and vJρ have been determined explicitly and their consistency
with the Luttinger liquid relations has been veriﬁed. For vJρ , one can use the relation of
the Drude weight of the conductivity (precisely 2vJρ ) to the dependence of the ground
state energy on an external ﬂux [43]
                                          π ∂ 2 E0 (φ)
                                 vJρ =                     .                           (4.54)
                                         2L ∂φ2 φ=0

At weak coupling, the system is a Luttinger liquid, and its correlations are described by
a parameter Kρ , indicated in Fig. 4.7 as dashed lines. This parameter can now become
smaller than 1/2, the U → ∞-limit of the Hubbard model. Due to the relevance of
Umklapp scattering terms which have a scaling dimension of 2 − 8Kρ , there is a lower
limit Kρ = 1/4 in the metallic phase. Beyond, the system goes insulating, and Kρ
discontinuously jumps to zero. The dominant correlations at weak-coupling are SDW
but 2kF -CDWs are only logarithmically weaker. For Kρ < 1/3, however, the divergence
of the 4kF -CDW correlations becomes stronger than the SDW one, indicating gradual
charge localization on alternating sites. In the insulating phase, this charge modulation
is long-range ordered, and the system can be viewed as a Wigner crystal. Fourth-order
processes in t still give an antiferromagnetic exchange interaction between occupied sites,
and a 2kF -SDW consequently is superposed on the 4kF -CDW. As one goes to larger V
(unphysical if one thinks in terms of electron-electron interaction alone but conceivable if

                                             80
on-site phonons are included), the eﬀective correlations get weaker, and Kρ can become
even larger than unity. If the system is still a Luttinger liquid in this range, it would be
dominated by triplet superconducting correlations before giving way to phase separation.
(The caveat is important, since a conclusive study of the properties of the spectrum of
the Hamiltonian on which the derivation of the Luttinger parameters is based, was not
possible [142, 143], and Mila et al. conjecture about a two-ﬂuid picture where a Luttinger
liquid would coexist with a liquid of local singlet pairs.) A more complete diagram,
including attractive interactions is also available [143]. Here, one can ﬁnd 2kF -CDWs, SS
when a spin gap opens, another TS when there is no spin gap, and a phase separation
regime when all interactions are attractive, as in the half-ﬁlled band (commensurability
is unimportant at this point). Most of these results agree with a similar study by Sano
and Ono [144] who, however, ﬁnd evidence for a spin gap in the large-V –small-U region,
and who therefore would favour an SS phase preceding phase separation. Moreover, these
authors extend these results to a third-ﬁlled band (n = 2/3) where similar results obtain
except for strong repulsion. Here, no evidence for a transition to an insulating phase is
found. While the general absence of such a transition is somewhat surprising, the Umklapp
operators which could mediate such a transition are less relevant than at quarter-ﬁlling,
and the transition may have escaped detection because is expected to occur at stronger
coupling. Notice that for a third-ﬁlled band, 2kF = 4kF = π/3a (mod 2π/a), and that the
Umklapp operator couples charges and spins (Section 5.2). One thus predicts the opening
of a charge gap to be accompanied by opening of a spin gap. The competition of SDW
and TS at positive U and negative V , a situation that might be generated in two-band
models, has been studied in detail by Kuroki et al. who, however, ﬁnd somewhat poor
agreement with renormalization group predictions even at weak coupling [145].
    At general bandﬁlling n, the mapping onto a Heisenberg chain produces a ﬁnite mag-
netic ﬁeld [140, 141]. Still, one can derive Luttinger parameters, and Kρ now can become
as small as 1/8 [49], allowing α to increase up to about 1.5. This conﬁrms the earlier
statement that the correlation exponents are strongly sensitive to the interaction range.
A ﬁnite range is required to produce really strong correlations from strong interactions.
This is exempliﬁed most dramatically by considering a long-range Coulomb potential
V (r) ≈ 1/r [90]. In a continuum system, the charge ﬂuctuations no longer have a linear
                                                √
spectrum at low q but rather go as ωρ (q) ≈ q 2 ln q, so that formally vρ = 0. The spin
ﬂuctuations behave normal. The logarithmic low-energy spectrum also gives a peculiar
dependence to the correlation functions involving density operators. The density-density
correlations decay as
                                         √
                                  exp(−c ln x)                           √
     hρ(x)ρ(0)i = A1 cos(2kF x)                 + A2 cos(4kF x) exp(−4c ln x) ,       (4.55)
                                        x
i.e. slower than any power of x in its 4kF -component. Comparing to (3.92) and (3.93), one
formally would have Kρ = 0. The Green function behaves as G(x) ≈ exp(ikF x−c ln−3/2 x)
and decays faster than any power of x (formally α → ∞). The system is at the edge of
Wigner crystallization. It retains some marginal Luttinger liquid character because the
quantum version of the Mermin-Wagner theorem [146, 147] forbids a real phase transition

                                            81
into a long-range ordered 1D crystal.
    On the lattice, a systematic investigation of the eﬀects of band-ﬁlling on the structure
of the ground state and thus the dominant CDW instability can be performed in the strong
coupling limit under quite general conditions of convexity for a long-range density-density
interaction [89, 148]. In particular, from the minimization of the electronic interaction
energy (i.e. in the atomic limit) one ﬁnds a series of generalized Wigner lattices as the
band-ﬁlling n is varied. For n = 1/m, one has every m-th site singly occupied with m − 1
empty sites in between. For n = 2/(2m + 1), the singly occupied sites are separated
alternatingly by m and m − 1 empty sites. Other conﬁgurations can be constructed with
a simple algorithm [89, 148]. As one dopes the system away from these rational band-
ﬁllings, one introduces solitons with fractional charge q = ±ρe into the ground states.
These particles are mobile if the hopping integral t is ﬁnite, and they will experience an
eﬀective interaction. They will form again a Luttinger liquid, and their eﬀective velocities
vν and correlation exponent Kν can be calculated as a function of the ﬁlling factor (the
analysis is practical only for inﬁnite interactions) [112].


4.5      Electron-phonon interaction and impurity scat-
         tering
How stable is the Luttinger liquid with respect to electron-phonon coupling?
    There are several models describing diﬀerent aspects of this interaction. Coupling of
electrons to acoustic phonons is modelled by the Hamiltonian

                                                                                    Pi2
                                                                                                          !
                                                                                       K
                                              c†i+1,s ci,s + H.c.                       + [ui+1 − ui ]2
            X                                                               X
 HSSH = −          (t0 − αSSH [ui+1 − ui ])                             +                                     .
             i,s                                                            i       2M   2
                                                                                   (4.56)
The electron-phonon coupling arises from the ﬁrst-order modulation of the hopping in-
tegral by the relative displacements ui+1 − ui of two neighbouring sites. K is the spring
constant, Pi the momentum operator, and M the ion mass. Electron-electron interactions
can be added if required. This model has been proposed to describe the essential physics
of conducting polymers, and polyacetylene in particular, by Su, Schrieﬀer, and Heeger
(SSH) and most often has been studied close to half-ﬁlling [149, 150].
    Electrons may also be coupled to intramolecular vibrations (optical phonons) which
modulate the energy levels εi of the lattice sites

                                                           Pi2
                                                                                !
                       X †                                    f
                                                               + Q2i + g
                                                     X                   X
        HHol = −t0            ci+1,s ci,s + H.c. +                         Qi ni .                        (4.57)
                        i,s                          i    2Mr   2        i


This model is due to Holstein [151] and has played a central role in the polaron problem
[152]. Here, the phonons are dispersionless, the spring constant is called f , and g is the ﬁrst
order coupling of a molecular energy level to a vibrational coordinate Q with an associated
reduced mass Mr . Another model somewhat intermediate between the SSH and Holstein
models, where the electrons couple to the librational motion of rings in a polymer chain,

                                                     82
has been introduced and discussed recently [153]. It combines dispersionless phonons
with coupling to the hopping integral t. Phonon dispersion and diﬀerent structures of the
coupling terms lead to important diﬀerences in the physics of these models. Being not
central to the subject of this article, we shall not detail them here but rather emphasize
the common features of phonon-coupled Luttinger liquids.
    Mean-ﬁeld theory, the crudest form of an adiabatic approximation, does not lead to
Luttinger liquid behaviour [5]. Rather, a gap opens and CDW long-range order obtains.
Compatibility with the Mermin-Wagner theorem [146, 147] for incommensurate systems
is reestablished by the Goldstone mode, the sliding of the CDW, but this only gives a
gapless charge density excitation. The spins remain gapped, and the generic physics of
such models is discussed further in Section 5.1. For genuine Luttinger liquid behaviour,
one must therefore go beyond phonon mean-ﬁeld theory and/or include electron-electron
interaction. Due to the importance of electron-phonon backscattering in 1D [5], we give
a brief discussion using renormalization group, directly extending Section 4.3 to include
electron-phonon interaction.
    The generic electron-phonon coupling Hamiltonian has the boson representation [154]

              H = H1e−p + H2e−p ,                                                                                     (4.58)
                   γ1 Z    n     h√         i      h√  i           o
           H1e−p =      dx exp 2iΦρ (x) cos 2Φσ (x) ϕ2kF (x) + H.c.  ,                                                (4.59)
                   πα Z
                   γ2
           H2e−p = √     dx [ρ+ (x) + ρ− (x)] ϕ0 (x) .                                                                (4.60)
                     L
  e−p
H1,2  describe electron-phonon backward and forward scattering.√      ϕ2kF (x) is the 2kF -
component of the displacement ﬁeld Qi or ui+1 − ui , scaled by M , and ϕ0 (x) the q ≈ 0-
component. ϕ0 (x) is a real ﬁeld, but ϕ2kF (x) is complex because the scattering processes
with ±2kF 6= π/a are physically diﬀerent. The coupling constants are
                    (SSH)                                      (SSH)              (Hol)      (Hol)
                   γ1       = 4iαSSH sin(kF a) ,          γ2           = 0 ; γ1           = γ2       =g .             (4.61)

The vanishing of γ2 for acoustic phonons only holds at q = 0 and is a consequence of
the linear dispersion in the centre of the Brillouin zone. The inﬂuence of the ﬁnite-q
contribution is of order (vs /vρ )2 where vs is the sound velocity of the phonons, and can
be neglected in most realistic situations [155]. This may perhaps not be permitted close
to a Mott transition where vρ ≪ vF and may become comparable to vs [156].
    Electron-phonon forward scattering in a Luttinger model can be diagonalized exactly
[155]. Equivalent results are obtained by including it into the renormalization group.
First, we integrate out the phonons to generate eﬀective, retarded electron-electron inter-
actions (in imaginary time formalism)
                                   !2 Z
                        |γ1 |                  Z                                      √                                  
H1eff (τ − τ ′ )    = 2                     dx dx′ D0 (x − x, τ − τ ′ ) exp                2i [Φρ (x, τ ) − Φρ (x′ , τ ′ )]
                        2πα
                                       √                                     
                                            2 [Φσ (x, τ ) + rΦσ (x′ , τ ′ )] + H.c. ,
                            X
                        ×        cos                                                                                  (4.62)
                             r
                                        Z       Z
               H2eff (τ − τ ′ ) = γ22        dx dx′            ρr (x, τ )D0 (x − x′ , τ − τ ′ )ρr′ (x′ , τ ′ )
                                                       X
                                                                                                                      (4.63)
                                                       r,r ′


                                                               83
with the bare phonon propagator
                                           1
                           D0 (x, τ ) =        δ(x) exp (−ωph |τ |)     .           (4.64)
                                          2ωph

When deriving scaling equations for the eﬀective coupling constants, α is interpreted as
a cutoﬀ which is also extended to the τ -direction (Section 4.3). In order not to loose the
short-time contributions which are important at high phonon frequencies ωph , one must
integrate the eﬀective retarded interactions between τ − τ ′ = 0 and α/vF , giving eﬀective
instantaneous interactions, plus (4.62) and (4.63) with a cutoﬀ α/vF in τ [157]. The
instantaneous interactions are added to the electronic terms, and the retarded pieces are
included into the renormalization group. Following Section 4.3, we obtain the following
set of scaling equations [154, 157]

                         dKρ−1      1 vρ  (ph)     (ph)
                                                         
                                  =       Y1 − Y2          D(ℓ) ,
                          dℓ        2 vσ
                         dKσ−1      1 2       (ph)
                                                        
                                  =    Yσ + Y1 D(ℓ) ,
                          dℓ        2
                          dYσ                               (ph)
                                  = Yσ (2 − 2Kσ ) − Y1             D(ℓ) ,           (4.65)
                           dℓ
                           (ph)
                        dY1               (ph)
                                  = Y1           (3 − Kρ − Kσ − Yσ )    ,
                          dℓ
                           (ph)
                        dY2               (ph)
                                  = Y2            ,
                          dℓ
                           dvν         1      
                                                 (ph) (ph)
                                                           
                                  =      vν Kν Y1 − Y2       D(ℓ) .
                            dℓ         2
The abbreviations are
                                       |γ1 |2
                                                                            !
                  g1⊥        (ph)                   α0 ωph       α(ℓ)ωph
             Yσ =     ,    Y1 =              2
                                               , D=        exp −                .   (4.66)
                  πvσ                 πvσ ωph        vσ            vσ
 (ph)     (ph)
Y2     = Y1     for dispersionless modes, and zero (for the present purposes) for acoustic
modes.
    A few important points are immediately apparent. (i) The phonon frequency ωph ,
through D(ℓ), is the decisive quantity controlling the interplay of repulsive electron-
electron and attractive electron-phonon interactions. At a scale ℓph = ln(EF /ωph ), all
retardation eﬀects are scaled out, and the model behaves (and eventually continues to
renormalize) as eﬀectively instantaneous. The inﬂuence of electron-phonon interaction
is the stronger the lower ωph . (ii) The charge degrees of freedom remain gapless for any
nonvanishing phonon frequency. While Kρ rather strongly decreases for acoustic phonons,
its sense of renormalization for dispersionless modes depends on the relative importance
of forward and backward scattering. The intial Kρ (ℓ = 0) contains a contribution from
the short-time part of D0 , as discussed above. (iii) A gap may open in the spin ﬂuc-
tuations, and in fact does so for low enough phonon frequency and / or high enough
electron-phonon coupling. The system then is no longer a Luttinger liquid and its physics

                                                      84
will be discussed in more detail in Section 5.1. Here SS or CDW correlations dominate,
depending on Kρ [157, 158]. (iv) In the opposite limit of high phonon frequency and/or
weak coupling, there is a Luttinger liquid regime. Depending on the renormalized Kρ ,
we have SDW or TS correlations. The properties at low energies, below ωph , are then
given by the Luttinger liquid correlations (Section 3.3) with the ﬁxed-point values Kρ⋆
and vν⋆ . The scaling equations respecting spin-rotation invariance, Kσ⋆ = 1 is guaranteed
for gapless spin ﬂuctuations. At energies above ωph , there will be deviations from the
Luttinger liquid properties. An example, the Holstein contribution to the optical conduc-
tivity, involving phonon emission, will be discussed in the next section [159]. Corrections
to the spectral functions of a model with forward scattering only [155, 156], have also been
evaluated [160]. (v) The velocities vν of the charge and spin ﬂuctuations are renormalized
by electron-phonon interaction. Consequently, this interaction has a pronounced inﬂuence
on the thermodynamic properties such as speciﬁc heat, compressibility and susceptibility
[159]. It is analogous to the enhancement of the eﬀective mass, or the density of states at
the Fermi level, familiar from higher-dimensional systems. In contrast to higher dimen-
sions, the electron-phonon interaction couples charge and spin ﬂuctuations and therefore
strongly renormalizes the magnetic properties of the Luttinger liquid.
    Renormalization group is also very useful to study the inﬂuence of impurity scattering
on the low-energy properties of Luttinger liquids [161, 162]. The forward (q ≈ 0) and
backward (q ≈ 2kF ) electron-impurity scattering components can be represented by two
Gaussian ﬁelds η(x) and ξ(x) with white noise correlations Pξ = exp[−Dξ−1 |ξ(x)|2dx]
                                                                                 R

and a similar expression for Pη [163]. Dη(ξ) = vF /τη(ξ) and τ is the scattering time. The
interaction Hamiltonian is
                                                       √ Z
                        XZ
                                      †                  2           ∂Φρ (x)
               Hf =          dx η(x)Ψrs (x)Ψrs (x) = −       dx η(x)                  (4.67)
                        rs                             π               ∂x
                       XZ          h                                              i
              Hb =              dx ξ(x)Ψ†+s (x)Ψ−s (x) + ξ ⋆ (x)Ψ†−s (x)Ψ+s (x)
                        s
                        1
                            Z     n       √                   √                o
                   =            dx ξ(x)ei[ 2Φρ (x)+2kF x] cos[ 2Φσ (x)] + H.c.   .    (4.68)
                       πα
This Hamiltonian is of the same structure as the electron-phonon interaction (4.59) and
(4.60) except that η(x) and ξ(x) are static ﬁelds while ϕ0 (x) and ϕ2kF (x) posses dynamics.
The renormalization group treatment therefore is parallel to the phonon problem up to
two diﬀerences: (i) the “phonon frequency” ωph = 0 here to reﬂect the static nature of the
impurity ﬁelds; (ii) for the same reason, forward scattering can be completely eliminated
by simply shifting                                  √
                                                      2Kρ Z x
                        Φρ (x) → Φ̃ρ (x) = Φρ (x) −           dz η(z)                 (4.69)
                                                      vρ
and completing the square. More importantly, if one uses the replica trick to treat
backscattering, the resulting action only contains differences of Φρ -ﬁelds so that they
are not aﬀected by the shift (4.69). Also unaﬀected by this shift are the Πρ (x)- and
Θρ -ﬁelds because they are generated from Φρ by time derivatives. This immediately im-
plies that both the conductivity and the pairing ﬂuctuations (SS and TS) are unaﬀected

                                                85
by electron-impurity forward scattering. The charge and spin density wave correlation
functions, on the other hand will decay exponentially with distance
                                             K
                                      −Dη ( v ρ )2 |x|
                  RCDW,SDW (x, t) = e         ρ          RCDW,SDW (x, t) |η≡0   .    (4.70)

Decay with time is not aﬀected.
   Also the inﬂuence of electron-impurity backscattering ξ(x) is dramatic. The renor-
malization group equations (4.65) can be taken over directly [161] with the phonon D
           (ph)          (ph)
dropped, Y2 = 0, and Y1       is replaced by a new
                                                         !K ρ
                                     2Dξ α          vσ
                                  D=                            .                    (4.71)
                                      πvσ2          vρ

The scaling dimension of the impurity backscattering operator D is 3 − Kρ − Kσ⋆ and
determines its (ir)relevance in the limit D, Yσ → 0 where mutual renormalization eﬀects
can be neglected [162]. D goes relevant except for Kρ > 2 for a SU(2)-invariant system
(Kσ⋆ = 1) and for Kρ > 3 for a spin-gapped system (Kσ⋆ = 0): disorder is always relevant
except deep in the superconducting region, and more so for a triplet superconductor
than for a singlet one. The fact that even weak disorder becomes relevant for weak
superconducting correlations (1 < Kρ < 2) shows that Anderson’s theorem [164] fails
in 1D. A Luttinger liquid only occurs when the coupling constants of the pure system
were such that it is strongly TS (Kρ⋆ ≥ 2 required), and TS correlations then continue
to dominate. Disorder can also be irrelevant when a spin gap opens (Yσ → −∞) with
SS correlations strongest, but very large Kρ⋆ ≥ 3 is called for here. In all other cases,
both D and −Yσ ﬂow to inﬁnity. Disorder is relevant, and localization occurs. Moreover,
one always has a spin gap, and the physics then is best described as a CDW (Kρ⋆ = 0)
pinned by impurities [165] (charge density glass). For strong enough repulsion between
the electrons, one would however expect localization in the presence of antiferromagnetic
correlations. Such a random antiferromagnet is, in fact, conjectured by Giamarchi and
Schulz [161] and their failure to ﬁnd it identiﬁed as an artefact of the development leading
to the renormalization group equations. The main features of the RG equations can also
be rationalized by realizing that the impurity backscattering operator linearly couples
to the CDW-operator (3.89) while the other types of ﬂuctuations (SDW, SS, TS) are
only inﬂuenced in higher order. It is therefore clear, that the charge density glass phase
descending from CDWs strongly extends in the phase diagram.
    The inﬂuence of impurities and electron-phonon scattering on transport is a subject
of the following section.


4.6     Transport in Luttinger liquids
4.6.1     Electron-electron scattering
In the presence of band curvature and in lattice models, the Hamiltonian does not com-
mute with the current which no longer is proportional to the momentum, and nonvanishing

                                               86
conductivity at ﬁnite frequencies is possible. There are several processes contributing. The
most obvious ones are Umklapp processes whereby n electrons are transferred from one
side of the Fermi surface to the other, carrying with them momentum of the order ±2nkF .
These processes are possible at low energy only in commensurate systems where the Fermi
wave vector has a rational relation to a reciprocal lattice vector G: kF = (m/n)G. Away
from these commensurate band-ﬁllings they involve states separated from the Fermi level
by a ﬁnite energy gap ∆m/n and will therefore contribute to the conductivity only at
frequencies or temperatures above ∆m/n [44, 45]. These issues will be discussed further
in Section 5.2. Another contribution comes from band curvature. In the presence of
interactions, band curvature will also renormalize the current operator [3, 45].
    Band curvature in an incommensurate system adds a term (4.2) to the Luttinger
Hamiltonian (3.1). The current operator is given by Eq. (3.67), and its commutator with
the Hamiltonian for small q reduces to
                                                    λ
                                lim [H, j(q)] =           + ...                        (4.72)
                                q→0               48m2 vF
Then, using Eq. (3.68), one obtains at T = 0
                                                  !2
                                  1       λ            Kρ − Kρ−1 3
                      σ(ω > 0) =                                ω + ...                (4.73)
                                 8π     12m2 vF           4vρ3

i.e. a universal (interaction-independent) ω 3 -law [45]. This result is essentially perturba-
tive in the band-curvature. Both for Kρ → 1 (noninteracting electrons) and λ/m2 → 0
[free electrons with k 2 /2m-dispersion, i.e. Galilei invariance (λ → 0)], or Lorentz in-
variance (m → ∞)] the ﬁnite frequency contribution disappears, as it must according to
Chapter 3. A direct calculation of the temperature dependence of the dc-conductivity is
not possible, but Giamarchi and Millis [45] give arguments for a divergence faster than
any power of 1/T as T → 0.
    In these calculations, there is no mechanism for dissipation. Ogata and Anderson
argue that special boundary conditions must be used in order to allow for dissipative
eﬀects [166]. Further neglecting vertex corrections, they ﬁnd that the dc-resistivity and
conductivity vary as
                                             1
                                   ρ(T ) =        ∼ T 1−2α                              (4.74)
                                           σ(T )
where α is the single-particle exponent. For α ≪ 1 as we have in the 1D Hubbard model
the resistivity varies nearly linearly with temperature. This behaviour should be closer
to real systems than the Hamiltonian-based calculations outlined before. The frequency
dependence then is determined by a relaxation rate linear in ω:

                                                ω 2α
                                  σ(ω) ∼                 .                             (4.75)
                                           iω + ω tan πα
That the optical conductivity in real materials could essentially probe the density of states
and thus depend on powers of α had also been conjectured earlier [167].


                                             87
    Finally, some information can also be obtained by other methods. Carmelo and Horsch
[168] calculate the weight of the δ(ω)-peak in the conductivity of the 1D Hubbard model
directly from the Bethe-Ansatz wave function and provide an interpretation from the
Landau-Luttinger-liquid point-of-view (Section 4.7).
    Obviously, while electron-electron scattering is one conduction-limiting mechanism,
experiments often probe other inﬂuences: scattering oﬀ impurities and phonons. Much
work has been done on the impurity problem, less on electron-phonon scattering, and we
start with the former.


4.6.2     Electron-impurity scattering
We shall proceed in two steps: (i) a single (or double) impurity and (ii) a system containing
a ﬁnite concentration of impurities.
   If we consider a single impurity in a Luttinger liquid, it is convenient to compute the
conductance G rather than the conductivity σ of the system. The conductance is deﬁned
on a sample of ﬁnite dimensions by G = 1/R in terms of the resistance, and related
macroscopically to the conductivity σ = 1/ρ by G = σA/L where A is the cross section
(= 1 in our 1D problems) and L the length of the system. Microscopically, G can be
computed via a Kubo formula [169]
                                  1    L
                                     Z         Z
                      G = lim            dx dτ eiωτ hTτ J(xτ )J(00)i .                 (4.76)
                           ω→0 h̄Lω 0

For reference, one can evaluate this expression for the impurity-free Luttinger liquid and
ﬁnds
                                                  e2
                                       G = nKρ        ,                                (4.77)
                                                  h
where h = 2πh̄ and n is the number of channels (n = 2 for spin-1/2 electrons). This
result has been found earlier by Apel and Rice [170]. Notice that in contrast to σ, G is
renormalized by the electron-electron interactions. At ﬁrst sight, this is not surprising
since the ﬁnite length breaks the translational invariance of the system which is the basis of
the independence of σ of electronic interactions. On the other hand, G can also be deﬁned
for L → ∞ and then gives a results diﬀerent from the Drude weight in the conductivity.
It thus appears that the limit L → ∞ and the process of turning on the electron-electron
interaction do not commute.
    We now include a single or double impurity, mainly following Kane and Fisher [169].
Equivalent results have been obtained by Furusaki and Nagaosa [171]. For simplicity, we
restrict ourselves to spinless fermions (n = 1, Kρ → K). There are two complementary
starting points: a weak impurity where perturbation theory in the impurity potential
works, and a strong impurity which can be viewed as two weakly connected semi-inﬁnite
Luttinger liquids. In the ﬁrst case, the Hamiltonian for an impurity at x = 0 is
                                         Z
                                δH =         dx V (x) Ψ† (x)Ψ(x)                       (4.78)

with V (x) strongly peaked around x = 0. The action for its dominant contribution,
backscattering of m electrons across the Fermi surface, i.e. transferring momentum

                                                   88
±2mkF , is
                                              ∞
                                                 vm
                                                            Z
                                                                dτ ei2mΦ(x=0,τ ) .
                                              X
                                   δS ≈                                                                    (4.79)
                                             m=−∞ 2

vm is the Fourier transform of V (x) at 2mkF . Here, we have included the higher harmonics
from Ψ(x) which occur in the Luttinger liquid (Section 4.2). The weak link, on the other
hand, can be modelled by a hopping Hamiltonian
                                          h                                          i
                            δH ≈ −t Ψ†l (x = 0)Ψr (x = 0) + H.c.                          .                (4.80)

Now one traces over the degrees of freedom away from the impurity (x 6= 0) to obtain
an eﬀective action for x = 0 only. This can then be used to compute the conductance
through the impurity. To this end, one derives renormalization group equations for vm or
tm
                                                             m2
                                                                !
                  dvm          2
                                               dtm
                       = 1 − m K vm ,               = 1−          tm .            (4.81)
                   dℓ                            dℓ          K
For repulsive interactions K < 1, the most relevant backscattering term v1 increases
under scaling, i.e. an initially weak impurity behaves eﬀectively as a strong one. This
qualitative conclusion is supported by the strong-coupling limit where t1 (and all higher
tm ) is irrelevant, i.e. the two Luttinger liquids are eﬀectively isolated. The impurity
thus produces total reﬂection for repulsive interactions. On the other hand, for attractive
interactions, K > 1, all vm are irrelevant and at least t1 is relevant, i.e. the impurity allows
for total transmission. At the ﬁxed point, in the former case the resulting conductance is
G = 0, in the latter one has the ideal Luttinger liquid conductance G = Ke2 /h.
    When temperature T , frequency ω, or voltage V are ﬁnite, they provide an eﬀective
cutoﬀ to the renormalization group ﬂow and produce power-law corrections to the ﬁxed
point conductances. One ﬁnds [with Ω = max(ω, T, V ) and n = 1 for spinless fermions]
                                       ∞
                                e2
                                         "                                               #
                                                          2
                                          amΩ | vm |2 Ω2(m K−1)
                                      X
                         G(Ω) =    K−                                                         .            (4.82)
                                h     m=1

The expansion coeﬃcients amΩ are nonuniversal but their ratios are universal. Power-laws
similar to the second terms on the right-hand side may be derived for transport through
a weak link [169, 171].
    Including spin degrees of freedom, the physics becomes much richer. The Hamiltonian
for scattering oﬀ an impurity now becomes
                              XZ
                 δH =                   dx V (x) Ψ†s (x)Ψs (x)
                               s
                               X                  Z              √                 √            
                  δS =                  vmρ ,mσ       dτ cos          2mρ Φρ cos          2mσ Φσ           (4.83)
                              mρ ,mσ

and for a weak link connecting two semi-inﬁnite spin-1/2 Luttinger liquids
                   Xh                                   i
       δH = −t            Ψ†rs (0)Ψls (0) + H.c.
                     s
                 X                 Z            √                    √            
       δS =              tmρ ,mσ       dτ cos        2mρ Θρ cos             2mσ Θσ       , mρ = mσ mod 2 . (4.84)
                mρ ,mσ


                                                            89
Notice how the impurity couples charge and spin degrees of freedom. In addition to the
(charge) conductance G ≡ Gρ , Eq. (4.76), a spin conductance Gσ = 2Kσ e2 /h can be
deﬁned. Then several phases are possible in principle, depending on the interactions Kν :
(i) the impurity can be irrelevant for charge and spin so that one recovers the perfect
conductor Gν = 2Kν e2 /h; (ii) the impurity can be relevant in one channel only, i.e. one
has a charge conductor and spin insulator (Gρ = 2Kρ e2 /h and Gσ = 0) or vice versa; (iii)
the impurity is relevant and one has a perfect insulator Gν = 0. Treating the impurity
potential or the weak link by renormalization group, one ﬁnds that the most relevant
term is 2kF -backscattering of an electron on the impurity. In the limit of small impurity
potential, the renormalization equation for vmρ ,mσ is

                        dvmρ ,mσ           Kρ       Kσ
                                                        
                                 = 1 − m2ρ    − m2σ    vmρ ,mσ .                      (4.85)
                          dℓ               2        2
In the spin-symmetric case (Kσ = 1), the lowest term with mρ = mσ = 1 is relevant
[case (iii)] for repulsive interactions (Kρ < 1), marginal for free electrons (Kρ = 1) and
irrelevant [case (i)] for attractive interactions (Kρ > 1), as in the spinless case. Also
corrections to the ﬁxed point conductances can be evaluated, and one ﬁnds expressions
very similar to Eq. (4.82) from the spinless case. Case (ii) obtains when, for some reason,
a potential component with mρ > 1 much larger than v1,1 and has to be incorporated ﬁrst.
Its principal eﬀect is to ﬁx the phase of Φρ at the impurity to a preferred value. With
respect to this phase-quenched situation, v1,1 is irrelevant if Kρ < 2 and Kσ > 2 in general,
and if Kσ > 1/2 for symmetric potentials. All indices ρ ↔ σ if a potential component with
mσ > 1 is large, and the criterion of symmetry of the scattering potential is replaced by
spin symmetry of the barrier. There are also several ﬁxed points at intermediate couplings
where explicit calculations are possible [169].
    For ﬁnite impurity strength, consistency requires to include the irrelevant electronic
interactions into the renormalization group scheme. This applies to g1⊥ in the spin-
1/2 case. Matveev et al. [172] treat a Fermi gas plus perturbative interactions. g1⊥
renormalizes Kσ which enters the conductance exponent. Translated into a conductance,
one obtains logarithmic corrections to the power-laws characterizing the (electronic) ﬁxed-
point properties. Matveev et al. also claim that the temperature dependence of the
conductance changes to nonmonotonic for g1 more repulsive than a critical strength.
Electron-electron backscattering can be quenched by applying a magnetic ﬁeld. This
gives an interesting crossover behaviour to the conductance. At energy scales larger than
2µB B (µB is the Bohr magneton), backscattering is present and the system behaves as a
Luttinger liquid. Below 2µB B, the external ﬁeld blocks the backscattering contribution,
and the scaling behaviour of spinless electrons applies. One then has to match both sets
of equations at ℓB = ln(2µB B). Matveev et al. also argue that backscattering can be
restored by applying a ﬁnite bias V , and predict a cusp-singularity in the diﬀerential
conductance at V = 2µB B/e.
    The analysis can be generalized to a situation with two impurities creating an is-
land between two semi-inﬁnite Luttinger liquids [169, 173]. By ﬁne-tuning a parameter,
e.g. the energy of the (noninteracting and spinless) electrons incident on the barrier, one

                                             90
ﬁnds resonances with perfect transmission at certain energies although they have a ﬁnite
width even at T = 0. As one turns on repulsive interactions, interesting changes take
place. One still needs to tune the energy of the incident electrons in order to make the
2kF -backscattering matrix element v1 vanish. (i) Then, however, the resonances become
inﬁnitely sharp as T → 0 – the interactions suppress all oﬀ-resonance conductance. (ii)
The conductance exactly at resonance depends on the strength of the electron-electron
repulsion and, eventually, on the impurity strength at higher multiples of 2kF . In partic-
ular, for 1 > K > 1/2 (and also for 1/2 > K > 1/4 provided that v2 is small enough), one
recovers the full Luttinger liquid conductance Ke2 /h at resonance with zero conductance
oﬀ resonance. Only for K < 1/4, or K < 1/2 and v2 large enough, is zero conductance
obtained. Of course, for attractive interactions, the barriers become irrelevant, there are
no resonances and one recovers the full Luttinger liquid conductance without ﬁne-tuning.
     Including spin, there are important diﬀerences, as can be seen easily in the limit of
very strong barriers [169]. The charge on the island now is discrete; if it is odd, there
will be a spin degeneracy as for a local magnetic moment. This is reminiscent of the
Kondo eﬀect, where a magnetic impurity (s = 1/2 in the simplest case) is embedded in a
Fermi sea of electrons. Resonant transmission through the island is again possible upon
ﬁne-tuning one (or several) parameters.
     Generically, there are two types of resonances which can be achieved tuning one pa-
rameter only. The Kondo resonance is the generalization of the spinless fermion resonance
discussed above. Suppose that we have tuned the 2kF -backscattering term (4.83) to zero.
Transmission will then depend on whether the next-to-leading terms (mρ or mσ = 2) are
relevant or not. For Kσ = 1, v1,2 is harmless, and v2,1 blows up only if Kρ < 1/2. This im-
plies that, for 1 > Kρ > 1/2, both spin and charge are perfectly transmitted on resonance
(although a single barrier would be totally reﬂecting), but for Kρ < 1/2, charge is totally
reﬂected while spin is transmitted on resonance. Oﬀ resonance, there is no conductance,
as for spinless fermions. Of course, for attractive interactions (Kρ > 1) the barriers are
irrelevant altogether. Allowing for Kσ 6= 1, one can also ﬁnd a phase which transmits
charge and reﬂects spin.
     Another resonance is possible when both v1,1 and v2,1 become relevant, i.e. Kρ < 1/2.
For a symmetric potential and v1,1 only, one obtains charge and spin insulating barriers.
For v2,1 only, the barriers are charge insulating and spin conducting. As a function of
v1,1 /v2,1 , one will have a charge resonance with ﬁnite conductance in between two charge
insulating phases. In a case with broken spin-rotation invariance, this intermediate ﬁxed
point is accessible perturbatively, and its properties can be computed in some detail [169].
Its main interest lies in its ﬁnite charge conductance, because the generic Kondo resonance
in this regime has Gρ = 0 and is thus diﬃcult to observe.
     More relevant experimentally is the shape of the resonance (an I − V -characteristic,
for example) as a control parameter δ (e.g. the gate voltage on the island) is tuned
through the resonance. Perfect resonance is achieved when the renormalized potential
v ⋆ = 0. Oﬀ resonance, the conductance will be determined by the growth of v as it ﬂows
away from the ﬁxed point v ⋆ = 0. According to Eq. (4.85), v1,1 grows with an exponent
λ = 1 − Kρ /2 − Kσ /2 (resp. 1 − K for spinless fermions). Close to the critical point, there

                                             91
will be a vanishing frequency scale Ω ∼ δ 1/λ . Here, one then expects the conductance
depend in a universal way on the ratio Ω/T

                                    G(T, δ) ∼ G̃(cδ/T λ )                             (4.86)

where G̃ is a universal scaling function. For small argument, one can expand G̃ to second
order about the ﬁxed-point value G⋆ . For large arguments, i.e. far from the critical point,
one can match onto the conductance at ﬁnite temperature in the single-strong-impurity
limit. In this way, one ﬁnds
                                      G̃(X) ∼ X −2/Kρ                                 (4.87)
(drop the index ρ for fermions without spin). Only for a noninteracting system is the line
shape Lorentzian. If interactions are present (Kρ 6= 1), the tails of the resonance line will
be suppressed (repulsion) or enhanced (attraction). For spinless fermions, these scaling
arguments can be backed up by an exact nonperturbative calculation for a special value
of the coupling constant K = 1/2. Moreover, for another value K = 1/3, relevant for
the Luttinger liquid description of the fractional quantum Hall eﬀect at ν = 1/3 (where
ν is the Landau level ﬁlling factor) [174] (Section 6.3), quantum Monte Carlo simulations
give excellent agreement with the scaling prediction (4.87) and, in addition, provide the
complete scaling function G̃(X) for all X [175].
    A particularly detailed discussion of the line shapes is given by Furusaki and Nagaosa
either for the tail region of a strong resonance or in the limit of strong barriers (weak
link) [173]. They showed that, only for strong electron-electron interaction (no matter
what its sign), both width and height of the peak vary monotonically with temperature.
Nonmonotonic behaviour in one of these quantities is observed for weaker interactions
1/2 < K < 2: for repulsive interactions, the peak height passes through a minimum
between its high-temperature value and the low-T ﬁxed point conductance Ke2 /h, while
for moderate attraction, the peak width passes through a minimum. The crossover in
both cases is determined by the ratio of temperature to the island quantization energy
δǫ ∼ vF /R.
    These results apply to short-range i.e. well-screened interactions. This is presumably
relevant for quasi-1D organic metals but a doubtful hypothesis for semiconductor quantum
wires where the electron density both in the wire and in its environment is low. Then, the
long-range nature of the Coulomb interactions has to be taken into account [90]. There
are two essential modiﬁcations [176]: (i) the conductance of even the pure Luttinger liquid
is length (L) dependent as
                                                3e2 ν
                                    G(L) = q             ,                             (4.88)
                                             h R⊥ /L
                                                                             q
where R⊥ is the transverse extension of the quantum wire, and ν = (2/3) (1 + g1 )π/4ζ
(with g1 the 2kF -component of the Coulomb potential, ζ = e2 /κvF , and κ a dielectric
constant simulating the environment). The length-dependence of G apparently indicates a
vanishing of the Drude weight in the conductivity of the inﬁnite system. This is interpreted
as being due to the vanishing compressibility of this system with long-range interactions,


                                             92
Eqs. (3.62) and (3.66) with Kρ → 0 [Section 4.4, after Eq. (4.55)]. (ii) The conductance
through an impurity vanishes faster than any power of T or V (replace T → eV below)
                                                h               i
                                G(T ) ∼ exp −ν ln3/2 (T0 /T )       .                 (4.89)

This is very much reminiscent of threshold behaviour.
    Essentially in disagreement with this work, an earlier calculation [177] ﬁnds a power-
law variation of the resistivity with temperature by treating the scattering with a fi-
nite density of impurities in Born approximation. Using the same method, Ogata and
Fukuyama later studied the crossover taking place as a function of system size and tem-
perature, between regimes of quantized conductance implying inﬁnite dc-conductivity,
and ﬁnite conductivity [178]. They show that, for small L, one better thinks in terms
of a conductance G = 2Kρ e2 /h (including spin) while beyond a given system size (de-
termined by temperature and the elastic mean free path), the conductance crosses over
to a 1/L-behaviour which implies ﬁnite dc-conductivity. While details of their prediction
may depend on computational procedures, the existence of such a crossover seems quite
plausible both for short and long range interactions.
    We now pass on to the problem of many randomly positioned impurities. Here, the
interference of the scattered electrons becomes important and can lead to localization
[179]. In a noninteracting 1D electron gas in the presence of disorder, all states will be
localized [180]. This need no longer be so if electron-electron interaction is turned on, and
we have given a general discussion of their mutual renormalization in Section 4.5. Here
we sketch their inﬂuence on transport.
    One important feature is already apparent when comparing the renormalization group
ﬂow of a single impurity [(4.85) with mρ = mσ = 1] and of many impurities (Section 4.5)
in a Luttinger liquid. For the noninteracting system, the single impurity is marginal, i.e.
does not change its conductance, while a ﬁnite concentration of impurities is strongly
relevant and leads to localization (the interacting system follows the same logic). The
diﬀerence is due to quantum interference, i.e. an electron multiply scattered oﬀ impurities
interferes with its time reversed shadow. This leads to an eﬀective backward scattering
of the electron and enhanced localization. The process is absent for a single impurity.
    The renormalization group equations allow to determine, in some cases, the localiza-
tion length Lloc and temperature Tloc = vF /Lloc beyond/below which localization takes
place. For small disorder D → 0, and close to the critical surface where the disorder is
marginal, one ﬁnds respectively
                                                                            !
                          −1/(3−Kρ −Kσ⋆ )                     Kρ − 2
               Lloc ∼ D                     ,   Lloc ∼ exp                      .     (4.90)
                                                           D − (Kρ − 2)Yσ

       spin-gap phases, these equations change [put Kσ⋆ = 0 and replace exp(. . .) by
In the q
exp{1/ 9D − (Kρ − 3)2 } in (4.90)].
   To determine the temperature-dependent conductivity σ(T ), we observe that thermal
ﬂuctuations will break coherence at a length scale ξT = vF /T , and renormalization will
stop there. The conductivity can then be calculated in Born approximation. In the

                                                    93
delocalized phase, one obtains σ ∼ T −1−γ with γ = Kρ⋆ −2 in the TS region and γ = Kρ⋆ −3
in the SS region, and Kρ⋆ is the renormalization group ﬁxed point value. In the localized
region, Tloc sets a crossover scale: for T > Tloc , conductivity ﬁrst increases with decreasing
temperature, and only for T < Tloc the quantum interference leading to localization and a
decreasing σ(T ) sets in. Above (below) Tloc (Lloc ), quantum interference is unimportant
and one has a diﬀusive regime (absent for noninteracting 1D electrons). Furusaki and
Nagaosa have reﬁned this picture by pointing out that there is another temperature scale
Tdis = vF /kB R > Tloc where R is the mean impurity distance [171]. For Tdis > T > Tloc ,
there is no localization (quantum interference) and the impurities behave as isolated.
Electron-electron interactions are present however, and the conductivity of the system is
governed by the scattering oﬀ individual impurities as considered in the beginning of this
Section. Tdis necessarily exceeds Tloc because localization can take place only on length
scales beyond the mean impurity distance.


4.6.3     Electron-phonon scattering
One may ﬁnally inquire about the inﬂuence of electron-phonon scattering on the conduc-
tivity of a Luttinger liquid. The renormalization group equations for the electron-phonon
problem (4.65) are strongly controlled by ωph /E(ℓ). For ℓ > ln(EF /ωph ), they reduce to
a purely electronic problem with renormalized starting parameters. For an incommen-
surate system where there are no non-Luttinger interactions left in the charge channel,
once all retardation eﬀects have been renormalized away one expects to ﬁnd a Drude
peak with a renormalized weight 2vρ⋆ Kρ⋆ where vρ and Kρ are obtained from (4.65). These
parameters generically decrease under renormalization so that the conductivity is lowered
by electron-phonon scattering. An exception occurs only in the high-phonon-frequency
regime of models with signiﬁcant forward scattering which do have dominant supercon-
ducting ﬂuctuations [157]. At temperatures above the phonon frequency, the renormal-
ization stop is determined by T , and one can take over the conductivity results from the
impurity scattering problem.
    Interesting eﬀects occur in the optical conductivity σ(ω). In the presence of phonons,
a new absorption process (Holstein absorption) is allowed: upon absorbing a photon (ω
ﬁnite, q ≈ 0), one creates a particle-hole pair [ωp−h = ω − ωph (q)] and a phonon [ωph (q)]
whose essential task is to take up the momentum imparted by the particle-hole pair. Such
a process is possible, of course, only for ω > ωph , and the additional optical conductivity
generated, has been computed in second order for a 2kF -phonon as [159]

                       σhol (ω) ∼ Θ(ω − ω2kF ) | ω − ω2kF |1−αCDW     ,                 (4.91)

where αCDW is the CDW correlation function exponent (3.92). In higher orders, one
has to take account of the lattice softening induced by the electron-phonon coupling,
and there will be Holstein conductivity for all ω > 0 varying again as a power-law for
small ω. Small momentum scattering, on the other hand, in ineﬃcient in generating
additional conductivity in the absence of band curvature. Physically, this is so because
the particle and the hole generated travel with the same group velocity and therefore

                                              94
will recombine with probability one. In the presence of band-curvature, there is a ﬁnite
forward contribution to the Holstein conductivity.


4.7      The notion of a Landau-Luttinger liquid
We have seen in Section 4.4.2 that the Bethe Ansatz solution of the Hubbard model (4.24)
is generated from the distributions of two quantum numbers {Ii } and {Jα } via the Lieb-
Wu equations (4.25) and (4.26). In the ground state, {Ii } and {Jα } occupy consecutive
integer or half-odd-integer values once and only once, so that the distribution functions
become
                     Mc0 (q) = Θ(2kF − |q|) , N↓0 (p) = Θ(kF ↓ − |p|)              (4.92)
in the limit L → ∞. The single occupancy of q- and p-states suggests that (pseudo)-
particles associated with these quantum numbers behave as fermions. Carmelo and col-
laborators have used this fact to construct a formalism which allows an interpretation
of the Bethe-Ansatz solution in terms of a generalized Fermi liquid of charge- and spin-
pseudo-particles, and proposed the name “Landau-Luttinger liquid” to integrable quan-
tum systems exhibiting this structure [168], [181]-[184]. The low-energy physics is fully
controlled by departures of the distribution functions from their ground state forms (4.92).
    Consider a Hubbard model oﬀ half-ﬁlling in a magnetic ﬁeld. The SO(4)-symmetry
is therefore broken down to U(1) × U(1). In this case, all low-energy excitations of the
Hubbard model are given by real roots {ki}, {Λα } of the Lieb-Wu equations (4.25) and
(4.26), and are functionals of the distributions Mc (q) and N↓ (p). Quantities like the energy
E or the momentum P of a state, Eq. (4.28), or magnetization and particle number, are
therefore functionals of Mc (q) and N↓ (p), too. All low-energy states only have small
deviations δc (q), δ↓ (p) from their ground state distributions

                  Mc (q) = Mc0 (q) + δc (q) ,                N↓ (p) = N↓0 (p) + δ↓ (p) .    (4.93)

The smallness of δc (q) and δ↓ (p) allows an expansion of the energy in powers of these
deviations E = E0 + E1 + E2 + . . .. Here, E0 is the ground state energy, and
                                (Z                                                  )
                         L       π                         kF ↑Z
                 E1   =            dq δc (q) εc (q) +            dp δ↓ (p) ε↓ (p)       ,   (4.94)
                        2π −π                             −kF ↑

                                                          fcc (q, q ′ )
                               (Z
                          L         π    Z π
                                                 ′
                 E2   =      2
                                      dq      dq   δc (q)               δc (q ′ )
                        (2π)       π       −π                  2
                                                        fss (p, p′)
                          Z kF ↑     Z kF ↑
                        +         dp        dp′ δ↓ (p)                δ↓ (p′ )
                           −kF ↑      −kF ↑                  2
                               Z π        Z kF ↑                              )
                           +         dq            dpδc (q)fcs (q, p)δ↓ (p)                 (4.95)
                                −π         −kF ↑


in precise analogy to the Fermi liquid [Eq. (2.1)]! The quantities εc (q) and εs (p) are
the renormalized pseudo-particle energies, and the functions fcc , fss , and fcs describe the
pseudo-particle interactions. The momentum, particle number, and magnetization are

                                                        95
linear in the deviations and therefore independent of the pseudo-particle interactions. Also
the low-lying excitations involve only a single pseudo-particle, and the interaction term
is of order 1/L with respect to the kinetic energy and unimportant. On the other hand,
the asymptotic decay of correlation functions is controlled by ﬁnite densities of pseudo-
particles with low energy, and therefore determined by the pseudo-particle interactions
f . These interactions can be related to both the elements of the dressed charge matrix Z
(4.43) and to the scattering phase shifts at the Fermi surface [122]. The inﬂuence of the
interaction U and the external ﬁelds H and µ on the low-energy properties essentially is
through the pseudo-particle interactions f .
    Though extremely similar in structure to the Fermi liquid, these Landau-Luttinger liq-
uids diﬀer in some important ways. Unlike the Fermi liquid, the pseudo-particles describe
collective charge and spin modes of the physical system (Section 4.4.2), and a construc-
tion of the physical electrons in terms of these pseudo-particles has not been achieved
yet. Single-particle excitations constructed out of one holon and one spinon do not map
onto free electrons as U → 0. Finally, the pseudo-particle excitations here refer to exact
eigenstates of the Hubbard Hamiltonian whereas the Fermi liquid quasi-particles are made
from a superposition of such eigenstates and therefore decay with time.
    Similarities and diﬀerences to the Fermi liquid can be gauged quite accurately from a
study of two-particle excitations [168, 183]. The dynamical charge- or spin-susceptibility
(ν = ρ, σ) has the spectral decomposition
                                                                 2ωj0
                    χ(ν) (k, ω) = −       |hj |ν(k)| 0i|2
                                      X
                                                             2
                                                                              ,      (4.96)
                                      j                     ωj0 − (ω + i0)2

where |ji is an eigenstate with energy ωj0 relative to the ground state |0i. Carmelo and
Horsch observe that even in a Fermi liquid, in the limit k → 0, only matrix elements
involving single-pair excitations connect to the ground state [168, 183]. In this limit,
the pair excitations become real one-electron–one-hole excitations, and the corresponding
matrix element with the ground state reduces to unity. This fact can be taken as a
two-particle criterion for Fermi liquids. Unlike the quasi-particle residue, these matrix
elements (there are four of them, taking ρ and σ between states with holon or spinon
excitations and the ground state) do not vanish in the generalized Landau-Luttinger
liquids, and are determined by the pseudo-particle interactions f . The matrix formed by
these elements regularly tends towards the unit matrix as U → 0, indicating that the
long-wavelength two-particle properties of the Landau-Luttinger liquid smoothly evolve
out of those of the free Fermi gas as the interactions are turned on. Adiabatic continuity
therefore holds in the long-wavelength two-particle excitations. From a study of the
charge and spin currents, one can determine both the charge and spin Drude weights of
the conductivities, but also the charge and spin of the pseudo-particles themselves. All
except the spinon charge (zero) depend on U and the external ﬁelds and are not ﬁxed to
canonical values.
    From the Fermi liquid character of the pseudo-particle excitations, we expect that
we can ﬁnd a framework similar to Chapter 3 for their low-energy description, and this
is indeed the case [184]. In particular, one can formulate operator descriptions of these

                                                96
pseudo-particles, separately in the charge and spin sectors, which obey to a fermionic al-
gebra. The low-energy structure can also be analyzed with conformal ﬁeld theory, where
one ﬁnds the typical tower structure of charge, current and sound excitations both for
charges and spin. The particle-hole excitations are described by a U(1)-Kac-Moody alge-
bra with central charge c = 1, and the Virasoro generators can be constructed explicitly
from the currents. Of course, one can then construct an eﬀective boson description of the
fermionic pseudo-particles.
    However, one always has to remember that the pseudo-particles are not perturbatively
related to physical particles, and their quantum numbers are not the quantum numbers
of real excitations. While they clarify the structure of the theory to a considerable ex-
tent, they still do not allow for a straightforward computation of the physical correlation
functions.
    The single-particle properties of Luttinger liquids are distinctively diﬀerent from Fermi
liquids. Their two-particle properties are distinct at larger wavevectors, but in the centre
of the Brillouin zone, they are very similar. In this sense, they can be considered as almost
Fermi liquids. The notion of a Landau-Luttinger liquid is one formal way of making these
connections explicit.




                                             97
Chapter 5

Alternatives to the Luttinger liquid:
spin gaps, the Mott transition, and
phase separation

The Luttinger liquid is one possible low-energy state of 1D fermions, realized when there
is no gap in the excitation spectrum. There are several other possibilities: states with a
gap in the spin excitations or/and in the charge excitations (the Mott insulator) or phase
separation. (A more detailed review of the Mott transition in 1D has been written by
Schulz [185].) In many models, there is a duality between the spin and charge degrees of
freedom, and consequently the methods to describe them are closely related.


5.1     Spin gaps
Spin gaps occur in spin-rotationally invariant models when the electron-electron backscat-
tering is eﬀectively attractive. We have seen an example for renormalization group scaling
in this situation in Section 4.3, Eqs. (4.11), when g1 < 0. Scaling was towards strong cou-
pling indicating that the Luttinger liquid ﬁxed point was unstable but naturally, renor-
malization group alone cannot tell us much about the physics in this situation. The
generic model for this problem is given by the Hamiltonian (3.1) plus (4.6) with g1⊥ < 0,
and an easy solution was provided by Luther and Emery [186]. For explicit spin-rotation
invariance, we add a process g1k to the Hamiltonian, whose eﬀect is to renormalize the
g2ν → g2ν − g1k /2. After the canonical transformation (3.28), Hσ , Eq. (3.31) is diagonal
with a renormalized velocity vσ (3.33), and using (3.50), H1⊥ becomes
                                 2g1⊥ Z        q                
                        H1⊥ =           dx cos  8Kσ Φσ (x)           .                (5.1)
                                (2πα)2
The essential observation now is that for Kσ = 1/2, i.e. g1k − 2g2σ = −6πvF /5, a sizable
attractive interaction for a spin-rotation invariant model (g2σ = 0), (5.1) can be written
as a bilinear in spinless fermions (3.57)
                               g1⊥
                                     Z      h                             i
                       H1⊥ =             dx Ψ†+ (x)Ψ− (x)e2ikF x + H.c.               (5.2)
                               2πα

                                                98
in an external potential (g1⊥ /πα) cos(2kF x). The kinetic energy (2πvσ /L)     rp σr (p) σr (−p)
                                                                            P

can also be written in fermion representation, and the total Hamiltonian
                                                g1⊥ X  †                  
                   H ′ = vσ      rkc†r,k cr,k +
                            X
                                                       c+,k c−,k−2kF + H.c.               (5.3)
                             r,k                2πα k

can be diagonalized by a Bogoliubov transformation. In (5.3), k ≈ rkF . From the sine-
Gordon form of the boson representation (5.1), it is apparent that the Ψ†r (x) create solitons
rather than electrons. The eigenvalue spectrum is
                                  q                                  g1⊥
                Er,± (k) = vσ kF ± (k − rkF )2 + ∆2σ ,        ∆σ =           ,           (5.4)
                                                                     2πα
where ∆σ is the spin gap at the Fermi level.
   When Kσ 6= 1/2, the problem can no longer be solved exactly. Renormalization group
arguments, however, support the existence of a spin gap
                                                        !
                                        vF     πvF
                                   ∆σ ∼    exp                                            (5.5)
                                        α       g1
for all negative values of g1k = g1⊥ and, with a diﬀerent functional dependence, for all
g1⊥ < 0, g1k < |g1⊥ | [76]. This conclusion is reached by scaling the model onto the
Luther-Emery line Kσ (ℓLE ) = 1/2 and relating the gap to the Luther-Emery gap ∆LE by
the length of the scaling trajectory ∆σ = ∆LE exp(−ℓLE ). The gap may also be obtained
from a homogeneity requirement of the partition function [187] or by using the exact
solution of the sine-Gordon model [140].
    The Hamiltonian (3.49) plus (5.1) is recognized as the quantum-sine-Gordon model
which is equivalent to the massive Thirring model [40, 188]. Both models are related to
the spin-1/2 Heisenberg chain [140, 141], and it is not surprising that they can be solved
by Bethe Ansatz resp. the quantum-inverse-scattering method [27, 28, 87, 189, 190].
Haldane constructed a renormalized Bethe Ansatz solution and could determine some
correlation functions of these models [191].
    This gap has dramatic consequences for the physical properties. It implies long-range
order in the Φσ -ﬁeld. This is best seen by going back to the boson representation of
H⊥ which has the form of a quantum-sine-Gordon Hamiltonian. For g1⊥ negative and
                                                                  √               √
scaling to strong coupling, the energy will be minimized by hcos( 8Φσ i = 1, i.e. 8Φσ =
0 mod 2π. The Θσ -ﬁeld gets disordered, and correlation functions containing exponentials
of Θσ will decay exponentially with a correlation length ξσ = vσ /∆σ . This cuts oﬀ the
divergences in the SDW and TS correlation functions, while SS and CDW continue to
diverge. Their exponents can be obtained by setting formally Kσ = 0 in (3.92) and (3.99).
(Due to the breaking of the SU(2) spin-symmetry to U(1) by our abelian bosonization
scheme, the cutting oﬀ of the divergence is obvious only for the Sz = ±1-components of
TS and the x- and y-component of SDW. The representation of the TS0 and SDWz (3.96)
rather suggests a cancellation of two individually divergent terms with ordered Φσ -ﬁelds,
which is also found in a renormalization group calculation of the correlation functions
[78]. The conclusion of non-diverging TS and SDW correlations in all components is ﬁrm,
however, and required by spin-rotation invariance.)

                                             99
    The negative-U Hubbard model falls into this universality class, and the spin gap can
also be calculated from the Bethe Ansatz [103]. A physical mechanism for the generation
of attractive interactions is electron-phonon interaction, and a renormalization group
treatment of this problem has been presented in Section 4.5 [154]. In an incommensurate
system where repulsively interacting electrons are coupled to phonons of ﬁnite frequency,
both the electron-phonon coupling and the phonon frequency determine if the system
scales towards a Luttinger liquid ﬁxed point or into a strong-coupling region with a spin
gap. The ﬁrst alternative has been discussed in Section 4.5. If the phonon frequency
ωph is small and the coupling constant γ1 big enough, the system will pass beyond the
                               ⋆
Luttinger liquid ﬁxed point g1⊥   = 0, Kσ⋆ = 1 before all retardation eﬀects are scaled out,
and ﬂow into the spin gap region. The scaling out of the retardation eﬀects then provides
another factor ωph /EF on the right-hand side of (5.5), and g1 → g1 (ℓ = ln[EF /ωph ]) in the
exponent in (5.5). Usually, CDW correlations are dominant, except for a Holstein-type
electron-phonon coupling at suﬃciently high phonon frequency, where superconductivity
is found [157]. Here, the electron-phonon system is in the universality class of the Luther-
Emery model. If the phonon frequency is low enough, it may be more appropriate to
start out from the Peierls mean-ﬁeld limit [5], and correct it by quantum ﬂuctuations and
interactions [154]. In any case, the formation of a 3D CDW is preceded by the opening
of a 1D spin gap on the chains.
    Examples for opening of spin gaps when the spin-SU(2) is broken, are given by Gia-
marchi and Schulz [192].


5.2      The Mott transition
In half-ﬁlled bands, a Mott metal-insulator transition may occur as a results of com-
mensurability, manifest in Umklapp scattering (4.8) becoming relevant. The problem is
completely analogous to the spin-gap situation discussed above. In the special case of the
Hubbard model at n = 1, there is a duality transformation relating positive to negative
U
                           ci↑ → (−1)i c†i↑ ,     ci↓ → ci↓ ,                        (5.6)
i.e. a particle-hole transformation on one spin species only. In the boson representation,
U → −U simply leads to an exchange of the roles of charge and spin ﬂuctuations. All
results of the preceding section then carry over, and the spin gap becomes the Mott-
Hubbard charge gap, separating the upper and lower Hubbard (sub)bands.
    This picture can be extended to include the eﬀects of doping (in the spin-gap problem,
this corresponds to the introduction of a magnetic ﬁeld which, however, is required to be
unrealistically strong to have visible eﬀects). We take the doping level δ = 1 − n and,
due to charge conjugation symmetry at n = 1, do not distinguish electron from hole
doping. Due to the commensurability pinning, it is expected that kF does not respond
immediately to doping, and that one will rather create charged defects in a commensurate
SDW background. Therefore the gap structure is expected to persist for some ﬁnite doping
range, but the chemical potential will move above (below) the gap to accommodate the

                                            100
additional charge carriers.
    A more reﬁned formulation of the model is necessary, however, to obtain a detailed
picture of the Mott transition [44]. We consider the Hamiltonian of the charge degrees of
(3.1) plus (4.8) and apply the canonical transformation (3.28). Unlike Section 3.2.1, we do
not require the non-diagonal terms (2g2ρ /L) p ρ+ (p)ρ− (p) to vanish but just transform
                                               P

so that Kρ = 1/2. In general then, a ﬁnite g2 -type interaction, not diagonal in the bosons,
will remain. The Hamiltonian then becomes [141]

 H = H0 + H1 ,                                                                                     (5.7)
                                                                  g3⊥
         Xh                                                      i      Z      h               i
H0 =          (vk + µ) : c†+,k c+,k : − (vk − µ) : c†−,k c−,k : +           dx c†+,k c−,k + H.c.      ,
          k                                                       2πα
                                                                        !
       πvρ sinh(2θ) X                     X
H1   =                2ρ+ (p)ρ− (−p) − f1   : ρr (p)ρr (−p) :                 ,
             L      p                     r
  v = vρ (cosh(2θ) + f1 sinh(2θ))        ,        exp(−2θ) = 2Kρ .

The fermions crk are spinless, and the boson operators ρr (p) refer to these spinless
fermions. H0 is of the Luther-Emery form and can be diagonalized. For the half-ﬁlled
system, the interactions simply renormalize the gap as in the preceding section. The f1
term has been introduced by Schulz [193] and does not aﬀect the gap. f1 is arbitrary and
can be ﬁxed as convenient.
    At half-ﬁlling, the chemical potential is in the centre of the gap, and the lower (upper)
band is completely ﬁlled (empty). Doping will shift it into the upper (δ < 0) or lower
(δ > 0) subband generating a ﬁnite occupation of negative or positive carriers there. For
very low energies (≪ ∆ρ ), the physics is determined by the partially occupied band only.
The band structure can then be linearized again around the new Fermi level kc = π|δ|,
and one keeps only interaction processes at the new Fermi surface. f1 can now be ﬁxed
so as to cancel all g4 -type terms arising, and the new subband Hamiltonian is [44]
                                                                             (a)    (a)
                                            
                  vc k a†+,k a+,k − a†−,k a−,k + 2πvρ sinh(2θ)f (kc )
              X                                                         X
     H =                                                                    ρ+ (p)ρ− (−p) ,
              k                                                         p
                               2
              ∂E         v kc
     vc =        =q                   ,                                                            (5.8)
              ∂k   (vkc )2 + (∆ρ /2)2
                 1                                       vc2
     f1 = q                 ,                f (kc ) =       .
           1 + (2vkc /∆ρ )2                              v2

The fermions ark now refer to the partially occupied subband, and the ρr(a) (p) are con-
structed from these fermions. This spinless Hamiltonian can now be diagonalized as in
Section 3.2.2.1, and the exponent K governing the decay of correlation functions is given
by                                  "                   #
                                  1      4vρ kc
                             K=       1−        sinh(2θ) .                          (5.9)
                                  2       ∆ρ
Notice the following: (i) As one goes towards the half-ﬁlled band δ → 0, the Fermi velocity
in the partially occupied band vanishes (vc ∼ kc /∆ρ → 0) which could be interpreted as

                                                 101
a diverging eﬀective mass m ∼ 1/δ [194] as vc = kc /m in the vicinity of the Fermi
surface. However, caution is required with this argument, because when only a few holes
are left, the Fermi sea and velocity become ill-deﬁned. The vanishing of vc indicates that
one has reached the bottom of the upper subband, and there one recovers the parabolic
dispersion of free particles with a ﬁnite eﬀective mass. (ii) The interactions between the
spinless fermions vanish ∝ δ 2 on account of the f (kc )-factor, i.e. one is always in the
weak-coupling limit close to the half-ﬁlled band. This ultimately justiﬁes the separation
of the Hamiltonian as in Eqs. (5.7). (iii) K → 1/2 as δ → 0, which is consistent with
the behaviour of the Hubbard model, Section 4.4. We do however not make use of any
speciﬁc feature of this model, so that these results are valid for any Luttinger liquid close
to half-ﬁlling [44]. (iv) Densely packed, strongly coupled spin-1/2 fermions map onto
dilute, weakly coupled spinless fermions (holons, solitons). This kind of mapping can be
fruitfully applied to many other problems [196]. (v) Of particular interest is the Drude
weight D of the conductivity which, as was pointed out by Kohn [43], can be taken as
an order parameter for the metal-insulator transition. The spinless fermion current is
proportional to the one of the spin-carrying fermions, and the Drude weight is therefore
D ∝ vc K, vanishing linearly as δ → 0 with a slope ∼ 1/∆ρ . (vi) From the mapping
onto the 2D commensurate-incommensurate transition, it follows that the Mott-Hubbard
transition is in the universality class of the Pokrovsky-Talapov transition [193, 194, 195].
This is the case quite generally for the doping behaviour of models which, exactly at
commensurability, display a Kosterlitz-Thouless transition as a function of the coupling
constant, Eq. (4.11), and therefore applies universally to the metal-insulator transition at
even commensurability ratios in 1D.
    At higher energies, the other (completely occupied) band contributes to the proper-
ties. To treat this case, Gulácsi and Bedell have proposed a bosonization scheme which
decomposes the physical fermion into four new particles, a right- and left-moving fermion
for each band [194]. The Hamiltonian then takes the form of a Luttinger model for the
partially occupied band and of a sine-Gordon model for the gapped band. One can then
calculate various correlation functions and, concerning e.g. the momentum distribution
function n(k), ﬁnds a sum of a Luttinger function (3.86), weighted by the doping level
δ, and a term linear in k characteristic for gapped systems [57], rather independent of
doping.
    A mapping of strongly coupled spinning fermions onto weakly interacting spinless
holons can also be operated in the Bethe-Ansatz formalism for the Hubbard model [197].
The Bethe-Ansatz equations can be reformulated in terms of the charge excitations only
and, for small doping, can be mapped onto weakly coupled holons. The Bethe Ansatz
allows the introduction of a magnetic ﬂux through the Hubbard ring, and the Drude weight
can then be obtained from the second derivative of the ground state energy, Eq. (4.54).
Also, the total optical spectral weight
                                                                         !
                                               π         π        ∂E0
                           Z ∞
                 πNtot ≡         Re[σ(ω)]dω =    hT i =    E0 − U                     (5.10)
                           0                  2L        2L        ∂U

can be computed quite easily, so that the optical properties can be discussed in some

                                            102
detail.
    At half-ﬁlling, on a ring of circumference L, the Drude weight varies exponentially
D(L) ∼ exp[−L/ξ(U)] as L → ∞, deﬁning a coherence length ξ(U). ξ(U) ∼ 1/∆ρ for
U → 0 but vanishes only logarithmically ξ ∼ 1/ ln(U) for U → ∞. ξ also determines the
exponential decay of the Green function at n = 1, and comparing to the sine-Gordon form
of the Hubbard Hamiltonian, is identiﬁed as the typical length of the solitons introduced
upon doping. The divergence of ξ as U → 0 suggests that U = 0, n = 1 is a quantum
critical point, and power-counting gives D the scaling dimension zero. Consequently, the
singular part of D should be a dimensionless scaling function

                              D sing (n, L, U) = Y± (ξδ, ξ/L) ,                        (5.11)

where the index ± refers to U > (<)0. Y± can be determined both analytically and
numerically in various limits. One remarkable result is that D has a universal jump of
2/π as U goes from 0+ to 0− at n = 1 and L = ∞ – the system is insulating at positive U
and metallic at U < 0. Moreover, at small doping, Y+ (ξδ, 0) ∼ ξδ as ξδ → 0. The Drude
weight grows linearly with doping, as we have already seen above. It saturates for ξδ ∼ 1.
On the other hand, the sum rule (5.10) is rather independent of δ, L and U in the critical
region. At δ = 0, all the spectral weight is in the upper Hubbard band. As one dopes
the system, spectral weight is simply transferred from the upper to the lower Hubbard
band where it goes into the Drude peak, a result which also holds in higher dimensions
[198]. When ξδ ∼ 1, most of the spectral weight resides in the Drude peak, and the gap
structure has been destroyed.
    The charge velocity vanishes as δ → 0 (the Bethe Ansatz explicitly gives a ﬁnite
eﬀective mass to the holons). Close to the metal insulator transition, the charge entropy
then is much higher than the spin entropy and will dominate the thermopower. This can
then be evaluated from the spinless fermions [199], and one ﬁnds a hole-like thermopower
for n < 1 and an electron-like sign for n > 1 with coeﬃcients varying as 1/δ 2 [42, 197].
On the other hand, the Fermi surface is given by the number of electrons in agreement
with Luttinger’s theorem [4].
    Kolomeisky used renormalization group to provide a general framework of the Mott
transition in a 1D metal of spinless fermions in an external potential with periodicity
kF a = (p/q)π (p, q integers) [200, 201]. There is forward and backward single-particle
scattering from this potential, and the electron-electron interaction is of spinless Luttinger
form (hslf). Forward scattering, though, can be eliminated by the same argument as in
(4.69) so long as one is interested only in the conductance which can be used as an order
parameter for the transition. The backscattering terms are then mapped onto a model
for the commensurate – incommensurate transition on 2D surfaces, which occurs at a
critical Kc = 2/q 2 [202]. This mapping again identiﬁes the universality classes of the
Mott transition. Unlike the Hubbard model, a ﬁnite critical interaction strength Kc < 1
is necessary for the transition to occur. We can approach it two diﬀerent ways: (i) one can
decrease K → Kc at ﬁxed band-ﬁlling kF a = (p/q)π (corresponding to a soliton density
ns = qkF /π − pa = 0 in the 2D problem) (Kosterlitz-Thouless universality class [77]);


                                             103
(ii) one can vary the bandﬁlling kF a → (p/q)π (ns → 0) at ﬁxed K < Kc (Pokrovsky-
Talapov university class [195]). In both cases, there is a universal jump of K and thus of
the conductance at the transition. The insulating phase of course has G ≡ 0, and in the
metallic phase
                                            2
                        e2       |ns |2(q K−2)
                                                  !
                    G =      K+                  , (K > Kc ) ,                       (5.12)
                        h              q2
                        e2 2
                                            !
                                   const.
                    G =        −               , (K = Kc ) ,                         (5.13)
                        h q 2 q 2 ln |ns |
                        e2 1
                    G →       , (K < Kc , ns → 0) .                                  (5.14)
                        h q2
Eq. (5.12) gives the conductance in case (i) above the transition, and here as well as in
(5.13), we have indicated the corrections predicted for slightly doping (ns ≪ kF a) away
from the ideal commensurability. Of course, K ≥ Kc includes the renormalization by
the irrelevant scattering processes from the lattice (in total analogy to the logarithmic
corrections found in Section 4.3). These are responsible for the nonanalytic correction
terms.
    The universal jumps of the conductance can also be rationalized quite easily in a
language closer to the main development of this article. One would describe commen-
surability eﬀects in the presence of electron-electron interaction by introducing suitable
                       (q)   R
Umklapp operators H3 ∼ dx cos[2qΦ(x)], transferring q electrons across the Fermi sur-
face, generalizing Section 4.3. Their scaling dimension will depend on q as 2 − q 2 K and
therefore imply a critical value of Kc (q) = 2/q 2 for each q. The universal jump of the
conductance is then immediately obtained by inserting Kc (q) into (4.77). Little work
has been done on the problem in the presence of spin. At q-even commensurabilities,
the above analysis is extended straightforwardly: the 2qkF -transfer Umklapp operators
           (S=0,q)   R        √
become H3          ∼ dx cos[ 2qΦρ (x)], where in the superscript we have indicated the
fact that the q particles transfer a total spin S = 0. These operators are more relevant
than those transferring ﬁnite spin and have scaling dimensions 2 − q 2 Kρ /2. The critical
Kρ scales as Kρ,c = 4/q 2 . The half-ﬁlled Hubbard model and the half- and quarter-ﬁlled
extended Hubbard models [50, 139, 142] obey to this relation. An example of an Umklapp
operator transferring ﬁnite spin is given by
                           2g3k Z        h√         i     h√         i
                    H3k =         dx cos    8Φρ (x)   cos    8Φσ (x)                 (5.15)
                          (2πα)2
which couples charge and spin. It is important in the half-ﬁlled extended Hubbard model
where the CDW-SDW transition is continuous at weak coupling but becomes ﬁrst order
beyond a tricritical point at about U = 2V ≈ 4 . . . 5t. At the origin is H3k with a scaling
dimension (2 − 2Kρ − 2Kσ ) [50, 139]. For q-odd commensurabilities, half-odd-integer spin
is necessarily transferred in Umklapp scattering. The Umklapp operators therefore must
                                                                          √
be of the form (5.15) although Φρ and Φσ have prefactors diﬀerent from 8. Here, charges
and spins are strongly coupled, and the Mott transition is accompanied by the opening
of a spin gap. The physics of such an odd-q Mott insulator has not been explored yet.

                                            104
     Transport in commensurate systems is very interesting because Umklapp processes
provide an important relaxation mechanism for charge carriers. The problem here is that
the conductivity does not have a regular perturbation expansion in the Umklapp operators
g3 , Eq. (4.8). A way out is provided by the memory function formalism [203]. Assuming
that the system is a normal metal with a ﬁnite dc-conductivity (a strong assumption
which needs justiﬁcation), one can rewrite Eq. (3.64) as
                                         2ivρ Kρ  1
                               σ(ω) =                  ,                            (5.16)
                                            π ω + M(ω)
and a perturbative calculation of the memory function M(ω) is well-deﬁned. It involves
the commutator [H, j] introduced before which, for the case of Umklapp processes in a
half-ﬁlled band, Eq. (4.8), reads
                                   8g3⊥              hq                 i
                   [j(xt), H] =          ivρ K ρ sin   8K ρ Φρ (xt) + δx    ,       (5.17)
                                  (2πα)2
where δ = 4kF − 2π/a measures an eventual doping level with respect to the half-ﬁlled
band.
    If g3⊥ ≪ 1, one obtains σ(ω) ∼ 1/ω for Kρ > 1 and σ(ω) ∼ ω 3−4Kρ for Kρ < 1 if
ω ≫ T . In the opposite case T ≫ ω, one has σ(0, T ) ∼ T 3−4Kρ . Of course, these results
are valid only at suﬃciently high T and ω because at smaller scales, there will be a charge
gap and one expects an activated conductivity. In case that g3⊥ is ﬁnite, one can extend
these results by performing a renormalization group calculation such as the one in Section
4.3 which will be stopped by the ﬁnite temperature at a scale ℓT = ln(EF /T ). Then,
additional temperature dependence in the conductivity will be generated by inserting the
renormalized values of g3⊥ (ℓT ) and Kρ (ℓT ) into the memory functions.
    Surprising results obtain at lower frequencies where one expects the inﬂuence of the
charge gap. Here, one can use the Luther and Emery solution [186] to diagonalize the
charge part of the Hamiltonian in terms of new spinless fermions, and then express the
current in the new fermions [44]. The dc-conductivity comes out inﬁnite at any ﬁnite
temperature. The explanation is quite obvious: the only scattering mechanism for our
charge carriers were the Umklapp processes which, however, have been diagonalized ex-
actly by the Luther-Emery transformation. Thermally excited carriers have no dissipation
mechanism left.
    Away from half-ﬁlling, there are two regimes. If T, ω ≫ vρ δ, the energy scales are too
high for the Umklapp processes to be quenched by doping, and one basically recovers the
half-ﬁlled band results. If T falls below vρ δ, the latter quantity will act as a cutoﬀ to
renormalization and freeze out the Umklapp scattering. One will then have a crossover
to presumably exponential increase with 1/T of the conductivity characteristic for the
incommensurate system. On the other hand, at zero temperature, as one approaches the
half-ﬁlled band, the weight of the Drude δ(ω)-part vanishes linearly with doping and with
a slope that depends on the charge gap [44], for the Hubbard model in agreement with
the Bethe Ansatz results [197].
    Similar results for σ(ω) can be obtained by using Eq. (3.68). On the other hand,
the predictions for σ(T ) agree with the memory function approach [204] only in certain

                                              105
cases [45]. Giamarchi and Millis suggest that the use of memory functions is particularly
dangerous in cases of inﬁnite dc-conductivity where the underlying conservation laws
may not be incorporated correctly into this method [45]. In fact, it seems that there is an
obvious contradiction between the assumed ﬁnite dc-conductivity of the memory function
method and the inﬁnite conductivity in the Luttinger liquid.
    The q ≈ 0-component of the two-particle charge-charge spectral function [ImRρ (q, ω)
with Rρ from Eq. (3.91)] can be studied in detail close to the Mott transition because
the charge operator here has a simple representation in terms of the spinless fermions
ρ(xt) = Ψ†+ (xt)Ψ+ (xt) + Ψ†− (xt)Ψ− (xt) [205]. At ﬁnite doping δ, one ﬁnds a two-peak
structure: a low-energy peak with linear dispersion arises from the long-wavelength den-
sity ﬂuctuations within the partially occupied subband. It looses weight ∝ δ → 0 as the
Mott transition is approached. This peak is modelled accurately by the eﬀective Luttinger
liquid description of Chapter 4. However, a second peak at higher energies (∼ ∆ρ ) is quite
pronounced over a signiﬁcant doping range. It represents density ﬂuctuations between the
upper and lower Hubbard subbands. In the Mott insulating phase (δ = 0), it is the only
signal present. The region in q and ω in which a simple Luttinger liquid description is
valid, therefore is very small close to the Mott transition and may contain excitations
carrying very little spectral weight [205].
    Shankar has considered the eﬀect of impurities in commensurate models [47]. For a
half-ﬁlled spinless fermion system with nearest-neighbour repulsion V i ni ni+1 , which has
                                                                        P

a Mott transition into a CDW state at V = 2t, he ﬁnds that the Mott gap is destroyed
by even a small amount of disorder. This is supported by numerical density matrix
renormalization group [206]. On the other hand, this work points towards persisting
diﬀerences between impurities in systems with and without a Mott gap: if one dopes the
system with an additional charge, it is strongly localized when the interactions are strong
enough to open a charge gap while localization is quite weak in the absence of the gap,
for identical disorder conﬁgurations. This situation corresponds to a Mott transition as
a function of band-ﬁlling at ﬁxed interaction strength, and Kolomeisky has argued that
the elementary excitations remain solitons, as in the pure Mott system, which, however,
become localized in the presence of arbitrarily small disorder [207]. In contrast, for a
half-ﬁlled (S=1/2) Hubbard model, Shankar predicts the Mott-Hubbard charge gap ∆ρ
to survive so long as the variations of the random potential are bounded to |ξ(x)| ≪ ∆ρ in
agreement with general arguments [207] and real-space renormalization group [208]. The
diﬀerence may again be due to the impurities coupling linearly to the CDW ﬂuctuations
which build up the order parameter in the spinless model but which are suppressed in the
half-ﬁlled Hubbard model.
    In a diﬀerent line of work, Horsch and Stephan [209] consider the conductivity of a
single hole doped into a half-ﬁlled t − J- and large-U Hubbard model. They ﬁnd that,
in addition to the Drude peak, there is conductivity at ﬁnite frequencies varying as ω −1/2
and ω 3/2 , respectively. These analytical results are supported by numerical diagonalization
studies on rings as big as 19 sites. Currently, it is not understood why σ(ω > 0) in both
models diﬀers qualitatively and also diﬀers from the Luttinger liquid prediction ω 3 . On
the other hand, one could speculate that a crossover to the ω 3 behaviour could occur as a

                                            106
ﬁnite concentration of holes is doped into the Mott insulator and a Fermi surface forms.
    The Ogata-Shiba wavefunction Eq. (4.34) [107] also allows to ﬁnd the spectral prop-
erties of one hole doped into a half-ﬁlled U = ∞-Hubbard model, the prototypical Mott-
Hubbard insulator. This problem had been examined long time ago by Brinkman and
Rice [210] who assumed Néel order for the spin conﬁguration. They had found a complete
localization of the hole becoming totally incoherent. Expressed in terms of the spectral
function
                                        1                    1
                          A(k, ω) = − ImG(k, ω) = √ 2                .                 (5.18)
                                        π               2 ω −4
There is no quasi-particle pole, and A is independent of k. This result, however, is mainly
due to the assumed static antiferromagnetic Néel order. In the U → ∞-Hubbard model,
the magnetic ground state is far from Néel, and taking the real Heisenberg ground state,
Sorella and Parola get quite diﬀerent spectral functions [120]. Generically, a three-peak
structure is found which can be understood qualitatively   q as a convolution of a holon and
                                       (h)
spinon Green function [∼ 1/{ω − ε (k)} resp. ∼ 1/ ω − ε(s) (k) [122], where ε(h,s)(k)
has been deﬁned in Eqs. (4.29) and (4.30)]. At special wavevectors, two singularities may
coalesce giving the peaks observed. Unfortunately, qualitatively diﬀerent results were
published slightly later by the same authors [121] where only a two-peak behaviour is
found. While the latter is in agreement with the spectral function of a Luttinger model
with charge-spin separation only and no anomalous dimension (α = 0 – there is no
partner for the holes to g2 -interact) [59, 61], the reason for the discrepancy between both
results is not clear. The dynamics of a single hole in the 1D t − J-model has also been
studied by Horsch and coworkers [211] both by numerical diagonalization, and analytically
within the subspace generated by applying the hopping operator to the state obtained
by annihilating a fermion with (k, s) in the 1D Néel state. The two methods agree in
their essential features. The inclusion of quantum ﬂuctuations in the spin background
changes the results in several essential ways with respect to the dispersionless, incoherent
Brinkman-Rice continuum. (i) It generates interesting dispersion in the spectra. While
the lowest eigenstate disperses on a scale J, the ﬁrst moment of the spectral function
R∞
 −∞ dωωA(k, ω) disperses on a scale t. (ii) To the extent one can gauge from the ﬁnite
lattice data, there seem to be three peaks, and the above dispersion behaviour suggests
that spectral weight is mainly transferred, as a function of k between peaks which have
diﬀerent dispersion. This is not unlike the three-peak structure initially found by Parola
and Sorella for the Hubbard model [120] but diﬀerent from later work by the same authors
[121]. (iii) The lower edge of the spectrum disperses little and remains sharp close to
ω ≈ −2t, but the high-energy edge of the Brinkman-Rice continuum gets washed out into
a tail of states. Comparing the work of the diﬀerent groups it appears that the dynamics
of a single hole doped into a Mott insulator is not fully clariﬁed.


5.3      Phase separation
For strongly attractive interactions g2ρ + g4ρ = −πvF , Kρ becomes inﬁnite, indicating
an instability of the Luttinger liquid [9]. The physical interpretation of this transition

                                            107
becomes obvious by going back to Eqs. (3.32) and (3.62) which shows that a divergence
in Kρ implies
                              ∂n
                          κ=      →∞ ,         vN ρ → 0 .                       (5.19)
                              ∂µ
Both facts indicate that a particle can be added to the system without cost in energy; the
electron clump into droplets i.e. one has phase separation. This transition takes place e.g.
in the extended Hubbard model with nearest neighbour attraction [50, 139, 142, 143, 145]
or in the t − J-model with suﬃciently large J [130, 131, 133].




                                            108
Chapter 6

Extensions of the Luttinger Liquid

This chapter discusses three extensions of the Luttinger liquid picture. The ﬁrst two
extensions are intimately related: models with two or more bands, and models with
several coupled chains. In the third part, we outline the important extension to chiral
Luttinger liquids arising in the fractional quantum Hall eﬀect, where a Luttinger liquid
with central charge c 6= 1 is found.
    There are very strong similarities between models with several bands and models with
several chains. The former in fact often model the bandstructure of materials with several
chains per unit cell. Coupling N chains by a hopping matrix element produces N bands.
They also can originate from applying a strong magnetic ﬁeld to a chain. We somehow
artiﬁcially separate this topic into two parts on multi-component and multi-chain models
mainly because the physical questions asked in both parts are rather diﬀerent.
    To see the similarities more closely, consider ﬁrst a two-band model

                                                ǫα (k)c†ksαcksα + Hint .
                                        X
                               H=                                                              (6.1)
                                        k,s,α


α is the band index, and ǫα (k) is the dispersion. The Fermi momenta kF α and velocities
vF α may be diﬀerent in general, and the vF α may be positive (electron) or negative (hole
bands at the centre of the Brillouin zone) as shown in Fig. 6.1. Hint is the interaction
Hamiltonian which contains all the processes gi discussed before, both within every band α
and between the diﬀerent bands. For electrons in a magnetic ﬁeld Hkẑ, the single-particle
Hamiltonian is
                                           X †                        
                        ǫ(k)c†ks cks + h          ck↑ ck↑ − c†k↓ ck↓
                   X
            H0 =                                                           ,   h = gµB H/2 .   (6.2)
                   ks                       k

With s → α, this reduces to a spinless variant of (6.1) with ǫα (k) = ǫ(k) ± h. Coupling
two chains i = 1, 2 with a single-particle tunneling matrix element t⊥ gives
                                                         X †                     
                                   ǫ(k)c†ksi cksi − t⊥
                             X
                    H0 =                                        cks1cks2 + H.c.       .        (6.3)
                             ksi                           ks

Here the bonding and antibonding bands disperse with ǫ0,π (k) = ǫ(k) ∓ 2t⊥ and are
labeled by their transverse momenta 0 and π. The spinless version of (6.3) also describes

                                                     109
electrons in a transverse magnetic ﬁeld Hkx̂, and the dispersions ǫ0,π (k) can then also be
obtained by rotating the ﬁeld around the y-axis align it with ẑ. Under this rotation, the
interactions transform nontrivially. The transformation does not aﬀect the “isocharge”.
In the “isospin” channel, the g1 -processes (and consequently also g2σ ) transform as [213]
                 Z                               XZ
  H1 = −g1k          dx : σ+ (x)σ− (x) : +g1⊥             dx Ψ†+,s (x)Ψ†−,−s (x)Ψ+,−s (x)Ψ−,s (x)
                                                   s
                 Z
                                      g1k + g1⊥ Z
       → −g1⊥ dx : σ+ (x)σ− (x) : +                 dx Ψ†+,s (x)Ψ†−,−s (x)Ψ+,−s (x)Ψ−,s (x)
                                            2
           g1k − g1⊥ Z
         −             dx Ψ†+,s (x)Ψ†−,s (x)Ψ−,−s (x)Ψ+,−s (x) .                         (6.4)
               2
The last process does not conserve the total spin of the scattering partners. In a single-
band model, it can arise from spin-orbit scattering, and work on this topic is relevant
here [192]. The coupling constant is commonly denoted by gf and describes interband
backscattering and does not conserve the number of particles on a given branch of a
band. More interactions of this kind can arise in systems where the starting model has
internal degrees of freedom. Of course, in all these multicomponent problems, the stan-
dard ﬂuctuation operators from Section (3.3) can be extended to include inter-component
ﬂuctuations, giving a ﬂavour of the richness of the physics that can be described.


6.1     Multi-component models
We ﬁrst describe a multi-component Tomonaga-Luttinger model, and then some of the
instabilities occurring in more complicated models when scaling does not go towards a
Tomonaga-Luttinger ﬁxed point in all channels.
    The Hamiltonian for Tomonaga-Luttinger model with N components (colours, labelled
by λ, including spin and chirality index) is [126]
                                      N
                                      X                 N
                                                        X
                              H =           Hλ +                 Hλλ′ ,
                                      λ=1              λ,λ′ =1

                                                (k − kF λ )c†kλ ckλ ,
                                        X
                             Hλ = vλ                                                                (6.5)
                                            k
                                       1 X
                           Hλλ′ =          gλλ′ (p)ρλ (p)ρλ′ (−p) .
                                      2L p

We assume that the Fermi velocities and momenta are pairwise (vλ , −vλ ), (kF λ , −kF λ),
corresponding to a symmetric dispersion, and that the coupling constants satisfy gλλ′ =
gλ′ λ . The standard Tomonaga-Luttinger model (3.1) is obtained for N = 4 and the two
pairs of Fermi velocities and momenta equal. The density operators commute as
                                                       pL
                          [ρλ (p), ρλ′ (−p)] = −          δλ,λ′ δp,p′ sign vλ .                     (6.6)
                                                       2π
One can now repeat the arguments of Section 3.2.1 to show that (i) the single-particle
Hamiltonian Hλ can be written as a boson bilinear, and (ii) that the equivalence to the

                                                  110
boson description is complete only upon including charge (Nλ ) excitations with respect
to the vacuum. The Hamiltonian then becomes
                      2π X                                 πX
             H =                  Aλλ′ (p)ρλ (p)ρλ′ (−p) +       Aλλ′ (p = 0)Nλ Nλ′ , (6.7)
                      L λ,λ′ ,p>0                          L λλ′
                                             gλλ′ (p)
          Aλλ′ (p) = |vλ |δλλ′ +                      .                                                                       (6.8)
                                               2π
This Hamiltonian being a bilinear form in the bosons, it can be diagonalized by an N-
component generalization of a Bogoliubov transformation [126]
              2π X                                           πX        X       (j)
         H =           |vj |ρj (p signvj ) ρj (−p signvj ) +     |vj |     Nλ αλλ′ Nλ′ ,                                      (6.9)
              L j,p>0                                        L j       λλ′
              X               π  X                 (j)
          P =    kF λ Nλ +           sign(vj )Nλ αλλ′ Nλ′ +                                                                  (6.10)
               λ              L jλλ′
                         2π X
                     +           sign(vj ) ρj (p signvj ) ρj (−p signvj ) .
                         L j,p>0

P is the momentum operator. The index j denotes the new operators and parameters.
                                                     (j)
The renormalized sound velocities vj and the matrix αλλ′ are obtained as the solution of
the eigenvalue problem

              A · B|w (j) i = vj |w (j)i ,                                                                                   (6.11)
                                                                                            (j)    (j) (j)
                           A = (Aλλ′ ) ,                 B = (δλλ′ signvλ ) ,              αλλ′ = wλ wλ′           .

Correlation functions
                                        Gλ1 ...λm (x′1 , . . . , x′m ; x1 , . . . , xm ) =
                          (−i)m hT Ψλ1 (x′1 ) . . . Ψλm (x′m )Ψ†λm (xm ) . . . Ψ†λ1 (x1 )i                                   (6.12)
can then be evaluated either by generalization of the bosonization formula (3.41) to N
components, or by combining the Ward identities associated with (6.5) with equation-
of-motion methods. [In (6.12), x stands for the space-time point (x, t) and T is the
time-ordering operator.] One ﬁnds
                                                                              Y fλl λ ′ (xl − x′ l′ )fλl λ ′ (x′ l − xl′ )
   Gλ1 ...λm (x′1 , . . . , x′m ; x1 , . . . , xm ) =       Gλl (x′l , xl )
                                                        Y
                                                                                        l                    l
                                                                                                                 ′     ′
                                                                                                                             ,
                                                        l                          f
                                                                              l′ <l λl λl′
                                                                                           (xl − xl ′ )fλl λl′ (x l − x l′ )
                                                                                                                           (6.13)
                            (0)
    Gλ (x′ , x) = Gλ (x′ , x) fλλ (x − x′ ) ,
                                                                                                                       (j)
                                                             δλλ′ Y                       −αλλ′
                                                 i                            i
                                                                                                            
                            −2α′
    fλλ′ (x, t) = Λ                    x − vλ t + sign(vλ t)        x − vj t + sign(vj t)                                    .
                                                 Λ                j           Λ

Here G(0) (x) is the noninteracting Green function, Λ is the momentum transfer cutoﬀ
                                      P (j)
familiar from Section 3.1.2, and α′ = j αλλ′ with the sum going only over those j where
vj vλ < 0. Asymptotically, this gives
                                                               P
                           G({x}, {∆Nλ }) ∼ e−ix                       ∆Nλ kF λ
                                                                                      (x − vj t)−2∆j
                                                                                  Y
                                                                   λ                                                         (6.14)
                                                                                  j


                                                               111
with                                     X           (j)
                                  ∆j =         Nλ αλλ′ Nλ′ .                        (6.15)
                                         λλ′

∆Nλ is the number of fermions of colour λ propagating from 0 to x, weighted by signvλ ,
i.e. the charge excitation introduced by the operator whose correlations are to be com-
puted. This is in agreement with the conformal ﬁeld theory prediction, if the ∆j are
interpreted as scaling dimensions. That this is indeed justiﬁed is seen by evaluating ener-
gies and momenta in a state with a deﬁnite number of charge and particle-hole excitations
(Nλ , nj = Lq/2π respectively)

                                   2π X
               E(Nλ , nj ) − E0 =        |vj | (∆j + nj ) + . . . ,                 (6.16)
                                   L j
                                   X             2π X
                     P (Nλ, nj ) =    Nλ kF λ +         (∆j + nj ) signvj ,         (6.17)
                                    λ            L j

i.e. one obtains the typical tower structure of conformal ﬁeld theories. Comparing with
Eqs. (3.161), (3.162), ∆j is identiﬁed as the scaling dimension of a primary operator, and
we thus have generalized these expressions to an N-component system [126].
    One example where these expressions can be fruitfully applied, is the Hubbard model
in a magnetic ﬁeld which scales towards an N = 4-Tomonaga-Luttinger model. Of course,
one could take the perturbative renormalization approach [214]. More accurate results,
valid at any coupling, are obtained, however, from the the Bethe-Ansatz solution in a ﬁnite
magnetic ﬁeld. There are two practical possibilities: either use conformal ﬁeld theory
directly to obtain the correlation exponents [127] or perform a mapping on the N-color
Tomonaga-Luttinger model by identifying the low-energy spectral properties between both
models [126]. We brieﬂy comment on the second method.
    The similarity to the ∆N and D in the conformal ﬁeld theory treatment of the
Hubbard model in Section 4.4.3 should be apparent, as well as the similarity between
Eqs. (6.14) and (4.45). The requirement that the correlation exponents of the Tomonaga-
Luttinger model and the Hubbard model be equal, implies for the scaling dimensions

                                      ∆j = ∆±
                                            c(s) ,                                  (6.18)

where the latter quantity is evaluated in the Hubbard model and related by (4.49) to the
elements of the dressed charge matrix. Also the A-matrix, and therefore the coupling
constants gλλ′ of the Tomonaga-Luttinger model, can be found. This basically involves
constructing an expansion of the scaling dimensions (6.15) in terms of the excitations in
the Bethe Ansatz wavefunction of the Hubbard model. Of course, the coupling constants
gi are found linear in U at small U. As U → ∞, they saturate, as implied by the saturation
in Kρ . More interesting is the ﬁnding that, at ﬁxed U, the gi have a nonanalytic variation
with h as h → 0, translating into a nonanalytic h-dependence of Kρ [127], and meaning
that a magnetic ﬁeld h can never be regarded as a small perturbation.
    Models involving interactions other than forward scattering alone often do not scale
towards the N-colour Luttinger liquid ﬁxed point (6.5) and most often have been studied

                                               112
for two bands (A, B) with or without spin degrees of freedom. The most important in-
teraction not contained in single-band models is interband backscattering, the last term
in (6.4) with coupling constant gf . In Eq. (6.4), the spin index labels the two bands
s = A, B. (There are more interband backscattering terms; momentum conservation
suppresses all of them but gf when the two Fermi momenta are not nearly equal.) For
spinning fermions, we can have gf k 6= gf ⊥ . For half-ﬁlled bands (here kF,A + kF,B or
2kF,A(B) = 2π/a), one must further add the corresponding Umklapp scattering process
g3 . It is also useful to think in terms of charge ﬂuctuation interactions (scattering pro-
cesses changing the number of particles in a band like gf does) and exchange interactions
(interband processes conserving the charge but changing the spin in a band).
     These models have been studied most often with the same methods used for the single-
band problems: renormalization group starting from a bosonic or fermionic description
and eventually strong-coupling ﬁeld theory. We neglect from our subsequent discussion all
non-Luttinger intraband interactions whose eﬀects have been discussed in the preceding
chapters. The 2-colour Luttinger liquid (6.5) is a hyperplane of critical ﬁxed points
g3 = gf = 0 [215]. It is stable for 2g2AB < −|g2AA +g2BB |, and then is attractive for [gf = 0
and (2g2AB +g2AA +g2BB ) < c|g3 |] or [g3 = 0 and (2g2AB −g2AA −g2BB ) < −c|gf |], where c is
a constant related to the diﬀerence in the Fermi velocities. In the symmetric case (vF,A =
vF,B , g2AA = g2BB ) the two bands decouple, and one can compute correlation functions by
the standard methods presented earlier [192]. In the absence of intraband backscattering,
the renormalization group equations have the Kosterlitz-Thouless structure (4.11), and
there are both massive and massless phases. If g2AB − g2AA < 0 and |g2AB − g2AA | < |gf |,
scaling will go to weak coupling, and there will be a massless two-component Luttinger
liquid with dominant CDW correlations. The combination g2AB + g2AA controls if they
are of inter- or intraband type (corresponding to SDWz and CDW of a s=1/2-single-
band model, respectively). If one of the preceding inequalities is violated, scaling will
go to strong coupling and, depending on g2AB + g2AA , one will have either intraband
superconducting pairing, or one of two new types of interband CDWs (corresponding to
SDWx,y in a spin-1/2 single-band model). Their structure can be seen more clearly if
one imagines the two bands arising from two spinless fermion chains coupled by t⊥ [213].
There, they correspond to (i) a CDW with a charge density modulation on the bonds of
the chains and (ii) to a conﬁguration where currents circulate around the plaquettes of
the ladder in an alternating pattern. This can be viewed as an orbital antiferromagnet
and is directly related to the staggered ﬂux phases discussed some time ago in the high-Tc
-problem [216].
     In the asymmetric model, the bands do not decouple. At weak coupling, this is quite
apparent from the renormalization group equations. At strong coupling, the Hamiltonian
can be decoupled into two sine-Gordon models involving phase ﬁelds which are linear
combinations of those describing the bands, with one condition on the coupling constants
[215], and the excitation spectra and correlation exponents can be determined. One
consequence of the coupling between the bands is that the correlation exponents for the
diﬀerent intraband and the interband ﬂuctuations may all be diﬀerent. For example,
when g3 = 0, gf may become relevant and open a gap in one of the sine-Gordon models,

                                             113
the other remaining massless. Depending on the precise value of the interactions, either
an intraband SS or an interband CDW have divergent ﬂuctuations. It is interesting then
that the conditions for divergent SS can be realized from purely repulsive interactions,
something impossible in the single-band case [215].
    Up to now, we have discussed only the physics of the charge ﬂuctuations. The in-
terband exchange processes are interesting, too, and require an extension of the previous
models by spin degrees of freedom [212, 217]. Due to the proliferation of the coupling
constants, a general discussion of such a model is a formidable task, and will not be at-
tempted here. An interesting limit is vA ≪ vB , i.e. a band of light electrons (B) coupled
to heavy electrons (A). On a technical level, a small velocity vA in (6.1) is generated by
hybridizing a dispersionless A-band with the B-electrons [take the two-chain Hamiltonian
(6.3) and put tk = 0 for one spin direction only]. For vA ≪ vB , the charge ﬂuctuations
between the bands may scale out of the problem. In that case, exchange between the
bands is the only remaining coupling, and the physics then becomes very similar to the
single-impurity Kondo problem [212, 217]. In particular, for positive exchange coupling
constants, scaling goes to weak coupling, in analogy to the ferromagnetic Kondo impurity.
For negative exchange constants, on the other hand, scaling is to strong coupling as in the
antiferromagnetic Kondo problem. The carriers in the two bands will bind into interband
singlets, and an interband spin gap will open. The dominant response functions are then
interband CDW and SS, depending on the remaining marginal intraband couplings. In
this way, one can model a 1D Kondo lattice.
    Pursuing the analogy of this two-band model to the Kondo problem and identifying the
heavy carriers with spins, complete Kondo screening can occur because there are always
suﬃcient light electrons to screen out the spins (kF A < kF B in Fig. 6.1) [218]. Caron
and Bourbonnais have studied directly a 1D Kondo lattice with ns impurity spins and
2nc carriers [219]. They verify by second order renormalization group Nozières’ criterion
[218], stating that complete Kondo screening only occurs when there are suﬃcient carriers
2nc ≥ ns . If this criterion is violated, the spins become RKKY-coupled by the electrons
and form a 2kF -SDW, at least for weak exchange integrals. For stronger exchange, a
Kondo regime may be reestablished.
    Finally, we add for completeness that Emery has solved the 1D version [196] of the
two-band model which was proposed in 2D for the CuO-high-Tc superconductors [220].
Here, the band splitting is produced by a term in the Hamiltonian (ǫ/2) n,s (−1)n c†ns cns
                                                                             P

modelling the energy diﬀerence between the copper and oxygen orbitals. In contrast to the
models discussed above, the two bands do not overlap in energy, and the physics taking
place upon doping is qualitatively similar to that arising from a half-ﬁlled one-band model
with a charge gap, which was discussed in Section 5.2.


6.2     Crossover to higher dimensions
On a macroscopic level, 1D systems are well known for their opposition to long-range
order. At ﬁnite temperature, the entropy associated with the defects in an ordered phase


                                           114
more than outweighs the cost in energy for their creation [221], and thermal ﬂuctuations
thus destroy ordered phases. At T = 0, the inﬂuence of quantum ﬂuctuations is more
subtle. From the equivalence of 1D quantum systems to 2D classical statistical mechanics,
the Mermin-Wagner theorem [146] suggests that phases where a continuous symmetry
would be broken, could not possess long-range order even at zero temperature. That
quantum ﬂuctuations indeed destroy long-range order associated with continuous broken
symmetries was demonstrated by Takada [147]. Finite temperature phase transitions
therefore must be a consequence of 3D coupling between the chains. Two mechanisms
can couple electrons on diﬀerent chains: ﬁnite-range Coulomb interactions and interchain
tunneling.
   The electron dynamics must also be aﬀected by 3D tunneling. Assume that we have
a Luttinger model on-chain dispersion vF (rk − kF1D ) and a hopping matrix element t⊥
between neighbouring chains. The 3D dispersion of the electrons then becomes

                ε3D                1D
                 r (k) = vF (rk − kF ) − 2t⊥ cos(k⊥b b) − 2t⊥ cos(k⊥c c) ,            (6.19)

where b and c are the transverse lattice constants (the longitudinal one is denoted a). We
ﬁnd for the Fermi surface
                             h                                      i 
                           r kF1D + 2tvF⊥ cos(k⊥b b) + 2tvF⊥ cos(k⊥c c) 
                  k3D
                   F,r =                                                   .         (6.20)
                                               k⊥

If t⊥ is of the order of tk ∼ vF /a, the Fermi surface will be closed and we better start
from an anisotropic 3D system. For smaller t⊥ , however, the Fermi surface consists of two
warped sheets, Fig. 6.2, and retains some 1D character. The issue now is the transverse
coherence of the electronic motion. Naively, we expect that at high temperatures T > t⊥ ,
where there is “thermal blurring” of the Fermi surface of the order T , the electrons are
unable to sense the warping and behave essentially 1D. At T < t⊥ , the warping and
thus the 3D aspects of the Fermi surface can be probed, and transverse coherence would
emerge. We shall see below that the actual picture is signiﬁcantly more complicated.
    The reasons for these complications reside in the electron-electron interaction which
may possibly conﬁne electrons on their chains. In 1D, here are two dramatic diﬀerences
from the free particle picture implictly assumed in the preceding arguments: the vanish-
ing quasi-particle residue at the Fermi energy, and charge-spin separation. t⊥ transfers
particles or at least quasi-particles. Its eﬃciency may therefore be severly reduced if there
are only collective excitations. While z(k = t⊥ /vF ) 6= 0 in general, we still expect that
a reduced quasi-particle residue z(t⊥ ) ≪ 1 will delay the establishment of 3D coherence
in the single-electron dynamics [21, 22, 222]. Charge-spin separation could also conﬁne
particles on their chains because a holon and spinon must tunnel together – yet in general
they are separated [223].
    The theory we have outlined in the preceding paragraphs relies heavily on the 1D
nature of our models. The key point were the 1D conservation laws of charge and spin
currents, i.e. of charge and spin on each branch of the dispersion separately, Eq. (3.7)
which no longer hold at t⊥ 6= 0. Is the theory of the preceding chapters therefore limited

                                             115
to strictly one dimension, or can it be extended beyond? What is its relevance for highly
anisotropic quasi-1D problems? Can it provide a framework to describe the physics of
real quasi-1D materials such as the organic (super-)conductors?
    To answer this questions, we consider an array of coupled chains to mimic a 2D or 3D
situation. The Hamiltonian then becomes
                                (t)             (g)
            H = Hk + H⊥ + H⊥                           ,                                                 (6.21)
                           Hnk ,
                      X
           Hk =                                                                                          (6.22)
                       n
                                            Z
           (t)
                                                dxΨ†m,r,s (x)Ψn,r,s (x) + H.c.
                               X
          H⊥      = −t⊥                                                                                  (6.23)
                            <m,n>,r,s

                                                    [cos(k⊥b b) + cos(k⊥c c)] c†k,k⊥ ,r,s ck,k⊥ ,r,s ,
                                   X
                  = −2t⊥
                             k≈rkF ,k⊥ ,r,s

            (g)     2 X (⊥)
          H⊥      =       g (k, k⊥ )ρ+ (k, k⊥ )ρ− (−k, −k⊥ ) +                                           (6.24)
                    L k,k⊥ 2
                      1 X (⊥)
                  +            g (k, k⊥ )ρr (k, k⊥ )ρr (−k, −k⊥ ) +
                      L k,k⊥ ,r 4
                                                Z
                                      (⊥)
                                                    dxΨ†m,+,s (x)Ψ†n,−,s′ (x)Ψn,+,s′ (x)Ψm,−,s (x) .
                           X
                  +                g1,m,n                                                                (6.25)
                      <m,n>,s,s′

Here, Hnk is the one-chain Luttinger Hamiltonian (3.1) for chain n where the density
operators acquire an additional chain (n) or transverse momentum (k⊥ ) label. t⊥ is the
transverse hopping integral, m, n in the sums denotes the chains, and r and s are the
branch and spin index, respectively. We have allowed for diﬀerent lattice constants in all
                    (⊥)      (⊥)
three directions. g2 and g4 are the interchain forward scattering constants of g2 - and
                                                                                        (⊥)
g4 -type, respectively, which, in the case of a Coulomb interaction, must be equal. g1
measures the strength of the interchain backscattering. If this term is included into the
Hamiltonian, consistency would require that one include also the intrachain backscattering
Hamiltonian (4.6) into Hnk , in order to treat both interactions on an equal footing.
     We ﬁrst discuss the interchain Coulomb interaction (t⊥ = 0). Quite generally, trans-
verse Coulomb coupling screens the eﬀective on-chain interactions or, if negative initially,
makes them more negative [224, 225, 226] – a tendency reminiscent of Little’s old sugges-
tion in favour of quasi-1D materials as candidates for high-temperature superconductivity
[227]. However, a more detailed investigation leads to rather diﬀerent conclusions. Inter-
                            (⊥) (⊥)
chain forward scattering (g2 , g4 ) respects the conservation of total charge and spin on
                                                                     (⊥)
each branch of the dispersion on each chain separately. Moreover, g2 is a marginal oper-
ator and only couples the charge ﬂuctuations; therefore it will inﬂuence the dimensions of
operators, and the exponents of those correlation functions which are sensitive to charge
ﬂuctuations. The Hamiltonian can be diagonalized exactly, and one obtains renormalized
values of Kρ (k⊥ ) depending now on the perpendicular wavevector k⊥ [224, 225, 226]. Ex-
ponents of on-chain correlation functions then contain integrals over k⊥ involving Kρ (k⊥ )
or functions thereof while the spin parts can be taken over unchanged from the single-
chain problem. Physically, the system remains a Luttinger liquid but, concerning the
competition between SS and CDWs, SS is favoured at the expense of CDWs, not unlike

                                                            116
Little’s suggestion [227]. The situation is completely diﬀerent if interchain backscattering
   (⊥)
(g1 ) is allowed. Firstly, as on a single chain, it violates the separate conservation of to-
tal spin on each dispersion branch. But, unlike the intrachain backscattering, (6.25) also
violates separate charge conservation. This indicates that, if this interaction process can
become relevant, gaps may open in the charge and spin ﬂuctuations with the concomitant
possibility of long-range CDW order. This is indeed what happens, at least in the regime
of attractive on-chain backscattering, but also for repulsive backscattering if the complete
intra- and inter-chain potential has δ-function shape [224, 225, 226]. Depending on the
          (⊥)
sign of g1 , long-range CDW order can be stabilized with a wavevector Q< = (2kF , 0, 0)
                                                         (⊥)
(i.e. a CDW in phase on neighbouring chains) for g1 < 0, and Q> = (2kF , π/b, π/c)
                                                                   (⊥)
(i.e. the CDWs on neighbouring chains are out of phase) for g1 > 0. Physically, these
results are quite easy to understand for dominant on-chain-CDW ﬂuctuations because
the system can gain Coulomb energy from the charge modulations on the neighbouring
chains with Q< resp. Q> .
     Up to this point, we have allowed general coupling contants gi both for the intra- and
interchain interactions. Of course, the physical Coulomb potential is V (q) = 4πe2 /q2 ,
and ﬁnite forward scattering constants only arise as a consquence of screening (g1 can
be considered as constant but may depend on details of the wavefunctions of particular
materials). The problem of screening of the divergence of the Coulomb potential can be
solved on an array of chains [52, 228]: the interaction of two electrons on a given chain
can be screened by the electrons on the others.
     The Hamiltonian
                      e2 X                                ρn (z)ρn′ (z ′ )
                               Z
               HC =                dzdz ′ q                                                 (6.26)
                      2 n,n′               a2 [(nx − n′x )2 + (ny − n′y )2 ] + (z − z ′ )

[where e is the electron charge, ρn (z) the total charge density operator (3.44) at position
z on chain n, and a the transverse lattice constant] can be mapped onto the form (3.25)
with the couplings
                                                      4πe2
                           g2ρ (q) = g4ρ (q) = 2               2
                                                                   .                  (6.27)
                                               a (εk qz2 + ε⊥ q⊥ )
(In principle, there is an inﬁnite sum over transverse reciprocal lattice vectors, but the
matrix elements then will depend again on details of wavefunctions and are not universal
[52]). εk,⊥ are background dielectric constants. The giσ remain unaﬀected. One now can
diagonalize the Hamiltonian for each q⊥ leading to q⊥ -dependent velocities and coupling
constants. The energy of the charge excitations is
                       v
                                               2 2
                                             ωpl qz              8e2 vF   4πe2 n
                       u
                                                            2
                       u
               ω (q) = tv 2 q 2 +
                 ρ         F z                          , ω pl =        =        .          (6.28)
                                       εk qz2 + ε⊥ q⊥ 2            a2       m
For any ﬁnite q⊥ , ωρ (qz ) ∝ |qz | in the limit qz → 0, allowing to deﬁne a renormalized
charge velocity vρ (q⊥ ). For |q| → 0, one obtains the plasma frequency of the anisotropic
system (εk = ε⊥ = ε for simplicity)
                                              ωpl
                                    ωρ (Θ) = √ | cos Θ| .                           (6.29)
                                                ε

                                                   117
Θ is the angle between q and the z-axis. A renormalized coupling constant Kρ (q⊥ ) can
be deﬁned from the diagonalization of the Hamiltonian. Its usefulness for determining
the asymptotic decay of correlation functions is, however, not as immediate as for the
single-chain problem. In fact, when calculating the correlation functions, one obtains q⊥ -
dependent expressions for their decay exponents which have to be integrated over q⊥ at
the end. It is not allowed to use an integrated d2 q⊥ Kρ (q⊥ ) in the standard Luttinger
                                                    R

expressions. As a consequence, the simple scaling relations between the exponents of the
various correlation functions (single-particle Green function, SDW, CDW, SS, . . . ) break
down! Each function has its own, independent exponent.
    The screening eﬀect strongly depends on the density of carriers and on the anisotropy
of the lattice. Denser chain packing means better screened interaction. In the limit of
vanishing packing density, one crosses over to the single-chain case [90] with a vanishing
plasma frequency, a correction ∝ ln |qz | to the Fermi velocity, and a formally vanishing
Kρ -exponent, as discussed at the end of Section 4.4.3.
    Interchain single-particle tunneling t⊥ can lead to further new physics. t⊥ can generate
transverse coherence in the electron dynamics, i.e. a crossover from essentially 1D to
eﬀectively 3D behaviour. It is not clear at this time, if the eﬀectively higher-dimensional
behaviour is necessarily of Fermi-liquid type or not. Interchain tunneling also can generate
transverse pair tunneling (either of particle-particle or particle-hole type) which propagate
the dominant on-chain correlations in the transverse directions, and eventually a ﬁnite-
temperature phase transition into a symmetry-broken ground state occurs. In both cases,
the 1D Luttinger liquid is unstable.
                                                      (g)
    We now consider the Hamiltonian (6.21) with H⊥ ≡ 0 (6.24). The essential qualitative
physics can be seen from a scaling argument due to Schulz [42] and Wen [229]. Consider
the free energy of a system with small t⊥ at ﬁnite temperature and investigate the relevance
of diﬀerent terms generated by an expansion in t⊥ . The free energy of the strictly 1D
system is F (0) ∝ T 2 . In second order in t⊥ , we obtain a correction
                                             Z
                              δF (2) ≈ t2⊥       dxdτ G2rs (x, τ ) ,                  (6.30)

where Grs (x, τ ) is the single-chain Green function at imaginary time τ . This function
behaves as

       Grs (x1 − x2 , τ1 − τ2 ) ≈ | 1 − 2 |−1−α ,                                    (6.31)
                                       s
                                    vF            x1 − x2
                                                         
             with | 1 − 2 | ≡            cosh 2πT           − cos [2πT (τ1 − τ2 )] .
                                  2πT               vF
α is the single-particle exponent from Section (3.3). The correction to the free energy
then scales as
                                    δF (2) ∝ t2⊥ T 2α .                               (6.32)
                     √                √
If α < 1 (i.e. 3 − 8 < Kρ < 3 + 8), a case encountered in many models (Section
4.4), this terms will become more important than F (0) at suﬃciently low temperature no
matter how small t⊥ , indicating that t⊥ then is a relevant perturbation. If t⊥ is the most
relevant perturbation, we expect the system to show a single-particle 1D–3D crossover at

                                                 118
some temperature TX1 . Only if α > 1 interchain single-particle tunneling will be irrelevant.
But then, look at the next order in the expansion of the free energy, corresponding to
interchain pair tunneling
                                          "                    #(Kρ −1/Kρ )/2
                          Z
                                          | 1 − 3 || 2 − 4 |
     δF   (4)
                ≈   t4⊥       d1 d2 d3 d4                                       [| 1 − 4 || 2 − 3 |]−2−2α
                                          | 1 − 2 || 3 − 4 |
                                                  
                ≈ t4⊥ max T 4α , T 2Kρ , T 2/Kρ         .                                               (6.33)

The ﬁrst term corresponds to two uncorrelated single-particle events and is the square o
δF (2) . The second term is generated from coherent tunneling of a particle-hole pair and is
more important than F (0) whenever Kρ < 1, i.e. for repulsive interactions. Coherent pair
tunneling generates the third term which dominates the zero-order term for attractive
interactions. The particle-particle and particle-hole pair terms are more important than
                                                      √
the single-particle terms for 1/Kρ resp. Kρ < (2/ 3 − 1) i.e. rather strong interactions.
If this happens, one expects to ﬁnd a two-particle 1D–3D crossover at a temperature
TX2 > TX1 , and the system very likely will undergo a symmetry-breaking phase transition
to a ground state corresponding to the most dominant intrachain ﬂuctuation. For spinless
                                                                                          √
fermions, single-particle tunneling is relevant for α < 1/2 i.e. K resp. 1/K < 2 + 3,
but two-particle tunneling is stronger than single-particle tunneling already for K resp.
             √
1/K > 1 + 2 [230].
    This renormalization group argument is good for inﬁnitesimal transverse coupling
only. It will certainly fail for bigger t⊥ : one expects the warping of the Fermi surface and
deviations from perfect nesting to cut oﬀ the Peierls divergence. Below the temperature
where this cutoﬀ happens, superconductivity in general will be the only possible instability
remaining. A description of the system for ﬁnite t⊥ is, however, a diﬃcult task. We only
brieﬂy review the major achievements and refer the reader to more extended treatments
[21, 22, 222] for further details.
    Early work starts from the exact solution of the 1D models and adds t⊥ as a perturba-
tion [222, 224, 231]. In this way, one generates an eﬀective transfer of a pair of particles.
There are no real interchain single-particle transitions, and the pair motion takes place
through virtual events. The perturbation theory only becomes well deﬁned if there is
either a gap in the charge or spin ﬂuctuations, or if the Luttinger model interactions are
suﬃciently strong [basically, the integral in Eq. (6.30) must converge]. This is a good
assumption for attractive backscattering where we have a spin gap, but not for the generic
repulsive Luttinger liquid. Doing then mean-ﬁeld theory in t⊥ with spin gap, one ﬁnds a
transition to a SS or CDW phase at a ﬁnite critical temperature [224]. When only one
type of ﬂuctuation is divergent on a single chain, tunneling will stabilize it into an ordered
phase. When both are divergent, tunneling will favour SS.
    The question of a single-particle crossover from 1D to 3D behaviour was addressed by
Prigodin and Firsov [222]. When the 1D interactions are weak, the system will behave
as a 1D Luttinger liquid at higher energies. Naively, one would expect a crossover to
3D behaviour at an energy of the order of the transverse bandwidth t⊥ . t⊥ is, however,
renormalized by the 1D intrachain correlations, and the 1D–3D crossover will only take

                                                       119
place at a temperature TX1 ≈ t′⊥ /π determined by the renormalized t′⊥ which can be signiﬁ-
cantly lower than t⊥ . t′⊥ is determined self-consistently from the requirement t′⊥ = t⊥ z(t′⊥ )
where z(t′⊥ ) is the quasi-particle residue at the energy scale t′⊥ . The renormalization of
interchain tunneling t⊥ → t′⊥ indicates a tendency of the electrons towards conﬁnement
on the chains induced by their on-chain correlations. Below the crossover temperature,
the interference between the Peierls and Cooper channels is destroyed. The transition
temperatures to a symmetry-broken ground state and the competition of various types of
order then can be determined from standard summation of ladder diagrams. In the 1D
high-energy regime, the perturbative treatment does not allow for generation of interchain
pair tunneling. This, again, could only take place in the case of strong interactions or
presence of a spin or charge gap, a problem that also is present in later work by Bra-
zovskiĭ and Yakovenko [231]. Interestingly, however, in such a gapped regime, Prigodin
and Firsov obtain a maximum of the superconducting Tc as a function of t⊥ for t⊥ ∼ ∆,
where ∆ is the 1D spin or charge gap [222]. Tc at maximum is signiﬁcantly higher than
in the 3D limit t⊥ → tk . The reasons for this become apparent upon realizing that the
maximal Tc just occurs at the point where the Peierls state breaks down: here one has an
optimal combination of 1D eﬀects (phonon softening at 2kF and high density of states at
EF ) with the 3D tunneling necessary to establish superconductivity.
    Bourbonnais and Caron proposed a renormalization group scheme both for the on-
chain interactions gi and the interchain tunneling t⊥ with respect to the free Fermi gas
which generates interchain pair tunneling from single particle tunneling even at weak
coupling [22, 232]. The basic mechanism is shown in Fig. 6.3, where we display an
expansion of the vertex corrections in terms of the gi and t⊥ . In particular, the last
diagram corresponds to the coherent hopping of a pair to neighbouring chains. This
scheme produces all kinds of pair tunneling processes because the general diagrammatic
structure of Fig. 6.3 applies to all combinations of propagation directions and spins. The
renormalization group transformations under a scaling of the bandwidth cutoﬀ from E0
to E0 (ℓ) generate terms of the type
                                 1 X                 †
                       Hpair =                Vµ (ℓ)Oµ,i (q, ωn )Oµ,j (q, ωn ) ,          (6.34)
                                 4 µ,i,j,q,ωn

where ﬁnite pair tunneling matrix elements Vµ arise from t⊥ through

     dVµ (k⊥ )                                                  d ln X̄µ (ℓ) [Vµ (k⊥ , ℓ)]2
               = fµ (ℓ) [cos(k⊥b b) + cos(k⊥c c)] + Vµ (k⊥ , ℓ)             −              (6.35)
       dℓ                                                            dℓ          2πvF
                                   !2
                              t′⊥
           fµ = ±2πvF                 gµ2 (ℓ) .                                            (6.36)
                            E0 (ℓ)
Here, the index µ = CDW,SDW,SS,TS denotes the diﬀerent kinds of ﬂuctuations, the
operators Oµ,i describe these ﬂuctuations on chain i as in Eqs. (3.89) or (3.94)–(3.96),
and the gµ denote eﬀective combinations of the coupling constants gi relevant for the
respective operators. In (6.36), the plus-sign applies for µ =CDW,SDW and the minus-
sign for µ =SS,TS. X̄µ (ℓ) is an auxiliary pair correlation function for ﬂuctuations of type
µ. The last term is an RPA-like interchain ladder contribution, the second term is the

                                                 120
pair vertex correction whose strong-coupling limit basically has been treated in the earlier
work, and the ﬁrst term generates ﬁnite Vµ from the initial value Vµ = 0.
    The ﬂuctuation µ has a tendency to long-range order at that wavevector k⊥ for which
Vµ (k⊥ ) is negative and extremal. One now integrates the renormalization group equa-
tions (approximately) and ﬁnds the eﬀective pair-tunneling amplitudes in all situations of
interest, both for weak and strong coupling, and on high and low energy scales. Interest-
ingly, the solutions allow for a regime where, for weak on-chain interactions, scaling of Vµ
goes to strong coupling at energies above TX1 . This corresponds to the growth of critical
ﬂuctuations of type µ gaining 3D coherence. There can thus be a two-particle 1D – 3D
crossover temperature TX2 > TX1 where interchain pair tunneling becomes coherent despite
essentially 1D single-particle dynamics. This complements, at weak coupling, earlier work
in the strong-coupling or gapped regime [231]. Moreover, since the interchain interactions
strongly depend on temperature, they can change from repulsive at high temperature to
attractive at low temperature. In this case, one will ﬁnd antiferromagnetic ﬂuctuations
coexisting with singlet superconductivity. At lower temperatures T < TX1 , in the absence
of perfect nesting, a transition to superconductivity occurs. Here, interchain Cooper pairs
form, and the superconducting gap has a line of zeros on the Fermi surface. By combining
the quasi-1D renormalization group with approaches like RPA and parquet summation,
a variety of useful results on critical temperatures and response functions in the presence
of interchain tunneling can be computed in all relevant regimes [22].
    By 1991, it was believed that this series of work provided quite detailed a picture for
the crossover from one into three dimensions both concerning the electron dynamics and
the establishment of long-range order of some symmetry-broken phase. Then, Anderson
pointed out that both our simple renormalization group argument at the beginning of
this section as well as the series of detailed calculations reviewed thereafter, are irrelevant
because they neglect charge-spin separation [223]. This is supposed to be a particularly
serious ﬂaw because charge-spin separation is a consequence of the restricted phase space
in 1D and a nonperturbative eﬀect. According to Anderson, there is a well-deﬁned order
in which to turn on interactions and t⊥ : interactions ﬁrst, and then t⊥ . In this way,
electrons on the chains would ﬁrst separate into holons and spinons and inactivate t⊥ ,
because it requires both of them, i.e. an electron, to tunnel. Consequently, the electrons
would be conﬁned to a 1D chain. Only pair tunneling of holons and spinons would be
allowed, and therefore, in the language of the preceding paragraphs, one would necessarily
have a two-particle 1D–3D crossover. A single-particle crossover, presumably to a Fermi-
liquid state, would be forbidden. In addition, anomalous fermion dimensions could, of
course, strengthen the intrachain conﬁnement [233]. Anderson also pointed out that two
chains are enough to study conﬁnement which introduces considerable simpliﬁcation in
the actual calculations.
    Anderson’s suggestion has spun oﬀ a ﬂurry of activity on two-chain Hubbard and
Luttinger models. Many of these do not follow Anderson’s prescription and diagonalize the
bandstructure ﬁrst and then turn on the interactions. Moreover, charge-spin separation is
often neglected, again. In this way, one arrives at the eﬀective two-band models discussed
before.

                                             121
    Charge-spin separation is present in a one-branch Luttinger liquid where the only
allowed interaction is g4⊥ 6= g4k . The question “conﬁnement or not?” can be studied
here on a minimal model. Fabrizio and Parola have produced an exact solution of such a
two-chain one-branch Luttinger liquid following precisely Anderson’s prescription in that
they ﬁrst produce charge-spin separation and then turn on t⊥ [234, 235]. The Hamiltonian
is (6.23) with (3.2) and (3.4) for each chain. Keeping only the right-moving particles and
dropping the corresponding index r = + on the operators,
              2π X
        H =     vρ  [ρ1 (p)ρ1 (−p) + ρ2 (p)ρ2 (−p)]                                       (6.37)
              L p>0
              2π X                                       Xh †                i
            +   vσ  [σ1 (p)σ1 (−p) + σ2 (p)σ2 (−p)] − t⊥     cks1 cks2 + H.c.         .
              L p>0                                      k,s

The index 1,2 labels the chains. The on-chain part of the Hamiltonian has already been
diagonalized and exhibits charge-spin separation vρ 6= vσ . We now can use the bosoniza-
tion identity (3.41) for the interchain part H⊥ in order to get its representation in terms
of the on-chain phase ﬁelds Φν and Θν , Eqs. (3.42) and (3.43). Introducing symmetric
and antisymmetric combinations of the charge and spin density operators ν1,2 (p) of the
diﬀerent chains, the resulting boson Hamiltonian can be refermionized simply by inverting
the bosonization identity (3.41). Then going through a series of unitary transformations,
one ﬁnally obtains a Hamiltonian bilinear in fermions with four dispersion branches
                                                           rh
                                                            (vρ −vσ )q 2
                                                                      i
                  ǫ1 (q) = vρ q   ǫ3 (q) = (vρ +v
                                                2
                                                  σ )q
                                                       +         2
                                                                         + 4t2⊥
                                                         rh                               (6.38)
                                                            (vρ −vσ )q 2
                                                                      i
                  ǫ2 (q) = vσ q   ǫ4 (q) = (vρ +v
                                                2
                                                  σ )q
                                                       −         2
                                                                         + 4t2⊥   .

A particle-hole transformation having been performed in the course of the calculation,
these expressions are only deﬁned for q > 0.
   Two excitation branches 1,2 retain the original Luttinger dispersion: they originate
from the chain-symmetric linear combinations of the density operators which remains
unaﬀected by t⊥ . The antisymmetric combinations are shifted by t⊥ . At q = 0, they
are split from the Fermi level by ±2t⊥ and for q → ∞, they approach the two Luttinger
branches: ǫ3,4 → vν q. The ground state of the system is thus obtained by occupying the
                         √
branch 4 up to Q = 2t⊥ / vρ vσ , i.e. up to ǫ4 (Q) = 0, the chemical potential. Information
on the conﬁnement of the carriers on individual chains can be obtained from several
quantities. The ground state energy change due to t⊥ is determined by the occupation of
the branch 4
                                        1 4t2⊥
                                                           !
                             ∆E                         vσ
                                  =−               log         .                      (6.39)
                              L        2π vρ − vσ       vρ
                                                                                             (t)
Being of order t2⊥ , it indicates that there is a ﬁnite ground state expectation value of H⊥
(e.g. ∆E ∝ t2⊥ is obtained for free particles where t⊥ shifts the bands). The occupation
number diﬀerence between the bonding and anti-bonding bands (labelled by their k⊥ -
values 0 and π) is                                              !
                             hN0 − Nπ i    4t⊥     1         vσ
                                         =              log        ,                    (6.40)
                                  L         2π vρ − vσ       vρ

                                              122
also indicating a shift between the bonding and anti-bonding bands ∝ t⊥ . The diﬀerence
in occupation numbers corresponds to a shift of the Fermi wavevector between the bonding
and antibonding bands of 2∆kF with
                                               t⊥       vρ
                                                             
                                   ∆kF =            log           .                            (6.41)
                                            vρ − vσ     vσ
All three quantities show that interchain tunneling does shift the bonding with respect to
the antibonding band, and that there is no conﬁnement of electrons on individual chains
despite charge-spin separation. On the other hand, the nature of the spectrum indicates
that charge-spin separation is a phenomenon robust against interchain coupling so that it
could conceivably survive under certain circumstances in more than one dimension, and
with it some Luttinger liquid physics.
    This is made more clear in the single- and many-particle dynamics. The Green func-
tion for particles with transverse momentum 0 or π can be calculated from a cumulant
expansion and becomes

    hΨ0,π (x, t)Ψ†0,π (0, 0)i ∼ ei(kF ±∆kF )x (x − vρ t)−3/8 (x − vσ t)−3/8 (x − vr t)−1/4 ,   (6.42)

where vr = 2vρ vσ /(vρ + vσ ) and the +(−)-signs go with k⊥ = 0, π, respectively. The
corresponding spectral function still is purely incoherent – there is no quasi-particle-like
feature – but now, it exhibits a three-peak structure at wavevectors small with respect
to t⊥ /(vρ − vσ ), compared to two peaks for the isolated chains. In the new excitation
dispersing with vr , charge and spin strongly interact through t⊥ . At large wavevectors,
on the contrary, t⊥ seems to be ineﬃcient, and the spectral function reduces to that of two
uncoupled chains [53, 59, 61]. The long-wavelength charge and spin density correlation
functions are also changed. The on-chain spectral function for the charge ﬂuctuations
contains a pole contribution from the Luttinger branch which has the form of isolated
chains. In addition, there are incoherent pieces close to vρ q ± 2t⊥ indicating branch cuts
in the correlation function, which originate from the coupling between charge and spin
ﬂuctuations generated by t⊥ as well as the nonlinear dispersion of ǫ3,4 (q). As q is increased,
spectral weight is transferred from the incoherent features into the central pole.
    For the special problem of the two-chain–one-branch Luttinger liquid, the same results
are found by proceeding in the opposite sense: ﬁrst diagonalize the band structure and
then turn on the interactions [236]. Here, one bosonizes the bonding and antibonding
fermions, but now the antiparallel-spin interactions lead to a Hamiltonian which is highly
nonlinear in the boson operators [of the structure of the backscattering Hamiltonian H1⊥
in Eq. (4.6) but with right- or left-moving ﬁelds only], so that an exact solution no longer
is feasible. Still, the Hamiltonian separates into four pieces corresponding to the four
excitations found in Eq. (6.38). These spectra can be determined from thermodynamics
and using special symmetries of the model, and agree with (6.38). The Green function
then obtains as Eq. (6.42).
    Although obtained from an exceedingly simple Hamiltonian, these results are ex-
tremely important. They tell us (i) that even in the case where the interchain tunneling
is turned on after the establishment of charge-spin separation on the chains, there is

                                                 123
no conﬁnement of electrons by this special kind of 1D interactions, and their interchain
dynamics can become coherent; (ii) the results do not depend on the order of turning
on charge-spin separation and interactions. Since charge-spin separation was the only
important feature left out in the work reviewed at the beginning of this section, we get
additional conﬁdence in the relevance of its conclusions.
    One can now include the g2 -forward scattering into a two-chain model. This couples
right-and left-moving electrons and gives rise to the anomalous dimensions on a single
chain parameterized by Kρ . On a more qualitative level, one can study conﬁnement by
looking at the stability of the 1D momentum distribution function n(k), Eq. (3.86), with
respect to t⊥ . Turning on t⊥ at the end, one ﬁnds [237]
                               h                    i
                      t⊥ cos k⊥ C + D(kk − kF )2α−1              for    α<1
             δn(k) =            h                i                                    (6.43)
                      t⊥ cos k⊥ C + D(kk − kF )                  for    α≥1 .

There is a singular correction to the momentum distribution in the neighbourhood of kF
for small α while it vanishes for large α. This essentially reproduces the conclusions of
our scaling argument on the level δF (2) from the beginning of this section, Eq. (6.32). Of
course, in the large-α limit, we will ﬁnd relevant pair-tunneling processes which are not
covered by this argument.
    A more detailed analysis is possible if one accepts ﬁrst diagonalizing the band struc-
ture – but from the behaviour of the two-chain–one-branch model above, we expect this
procedure to be safe. In a renormalization group analysis of Luttinger models (g2 , g4 6= 0)
coupled by t⊥ , new relevant interactions are generated by the RG [236]. Speciﬁcally, an
interaction term
                          λ X
                  Hλ =             [ρ+,0 (p) − ρ+,π (p)] [ρ−,0 (p) − ρ−,π (−p)]       (6.44)
                         4L |p|≪kF

is generated and goes relevant, and its coupling constant λ increasing towards large nega-
tive values under renormalization – independent of the sign of the on-chain g2 ! It is driven
by interband forward scattering with antiparallel spins involving opposite branches (i.e.
of interband-g2 -type but formally of structure similar to the usual backscattering Hamil-
tonian) which does not conserve the total spin on each of the four excitation branches.
In Eq. (6.44), ρr,k⊥ (p) denotes the right- or left-moving (r = +, −) density ﬂuctuations
obtained from the bonding or antibonding (k⊥ = 0, π) fermions with parallel momentum
p. Due to the shift between the bands brought about by t⊥ , the diﬀerences in [. . .] do
not equal the on-chain densities. One can now bosonize the strong-coupling ﬁxed point
and ﬁnd that a spin gap opens in the system. At this level, it is not completely clear
if this favours SS or CDW correlations, but in a 3D array of pairs of chains, the Peierls
divergence will be cut oﬀ by t⊥ and superconductivity comes up [236]. Here, the Cooper
pairs can be formed predominantly either on or between the chains, depending on the sign
of g2 . For repulsive interactions, one would ﬁnd pairing between the chains, in qualitative
agreement with Bourbonnais and Caron [22].
    One can go one step further and consider the Hubbard model on two-chains – ﬁnally,
this is the problem we are most interested in! This requires the inclusion of all kind

                                              124
of backscattering processes, and one has to treat a problem with ﬁfteen independent
coupling constants (excluding commensurate situations where additional Umklapps come
up) [235, 238]. The phase diagram is given in Fig. 6.4. There is a trivial Luttinger
liquid (LL1) at large t⊥ where the upper band is empty and only the bonding band is
ﬁlled. When the two bands only slightly overlap, there is another Luttinger liquid (LL2)
whose existence is related to a big diﬀerence between the bonding and antibonding Fermi
velocities. However, there is a ﬁnite value of teff ⊥ and no conﬁnement. Decreasing t⊥ ,
one enters strong-coupling phases. The phase III at large U and small t⊥ does have
conﬁnement (teff ⊥ = 0) and strong pair hopping between the chains. It is interesting
that an interband pair susceptibility, pairing particles of the bonding with those of the
antibonding band, has the most divergent ﬂuctuations, but on-chain SDWs diverge, too.
At smaller U, one enters another phase I where the dominant pairing ﬂuctuations involve
pairs from the bonding or from the antibonding bands. An interchain SDW diverges, too,
though less strongly. Intercalated between those phases may be a third phase II with
conventional on-chain Cooper pairing.
    The correlations on two Hubbard chains can also be studied with numerical calcula-
tions [239]. A density-matrix renormalization group study ﬁnds a spin gap at half-ﬁlling
with exponentially decaying spin-spin correlations. The correlation length is a few lat-
tice constants. Singlet pairing correlations also decay exponentially, and their correlation
length is even shorter which may indicate a liquid of disordered singlets. If one dopes the
systems with holes, the spin gap is quite robust and persists down to at least n ∼ 3/4 i.e.
a doping level of 25%. On the other hand, the doping greatly favours the pairing corre-
lations (both on and between the chains i.e. in a d-wave like pattern) which change from
exponential to power-law and therefore will be dominant at long distance. However, they
decay as 1/r 2 , like free fermions which is deﬁnitely weaker than the divergences predicted
from renormalization group. In addition, no sign of the subdominant SDW divergences
predicted by renormalization group is reported from the numerical calculations. Another
Quantum Monte Carlo study where the reduced density matrix of the superconducting
correlations was computed, does ﬁnd evidence for enhanced superconducting correlations
with respect to the uncorrelated system at n = 3/4 [240]. There is some structure in this
enhancement when t⊥ is varied at ﬁxed U which has been associated with the diﬀerent
phases LL2, SC1, and SC2 in Fig. 6.4. When t⊥ becomes so large that only the bonding
band is occupied (LL1), no enhancement can be detected. On the other hand, a ﬁnite size
analysis of the correlations assuming the Luttinger liquid power laws (3.92) and (3.99)
suggests that the exponent Kρ < 1 which would imply dominant density wave and only
leave space for subdominant SS correlations [240]. This conclusion does not agree with
the renormalization group work [235, 238].
    Much information has also been gathered on arrays of coupled t − J-chains following
a suggestion that they could be used as a model for certain cuprate compounds [241].
Two or more chains described by the standard t − J-Hamiltonian (4.21) are coupled by
transverse hopping (t⊥ ) and and exchange (J⊥ ) integrals. In an undoped system of two
(or an even number of) coupled Heisenberg chains [242], if J⊥ ≫ J, of course singlet
pairs will form across the rungs of the ladder, and the excitations will have a spin gap.

                                            125
This singlet-triplet gap survives not only down to the isotropic point J⊥ = Jk but there
is evidence that it does so for any ﬁnite J⊥ [242]. On the other hand, for an odd number
of chains, no such dimer state is possible, and it turns out that its excitations are gapless
like in the single-chain model. Introducing holes into two chains will lower but not destroy
the spin gap [243, 244]. One can now combine this fact with a bosonization analysis to
inquire what type of correlations will govern the physics of this two-chain system. In a
spin-singlet state, the eﬀective exponents for the charge degrees of freedom become
                               s
                        1             J                   J⊥
                           =     1+      hSij · Si+1j i ±    hSi1 · Si2 i ,              (6.45)
                       Kρ±            πt                  πt
where ± stands for the chain-symmetric (antisymmetric) combination of the phase ﬁelds
Φν and Θν used to bosonize the single chain, Sij is the spin operator at site i of chain
j = 1, 2, and the expectation values do not depend on the site index i [243]. In general,
one has Kρ+ > 1 corresponding to attractive interactions in the bonding channel which are
generated by the preferred singlet (hSi1 ·Si2 i < 0) correlations across the rung of the ladder.
This analysis cannot determine if Kρ− > or < 1, which would correspond to modiﬁed d-
wave SS correlations or a special CDW phase where an alternating ﬂux Φ = 2kF is enclosed
in a plaquette [243]. Such an “orbital antiferromagnet” had been discovered earlier in
a study of a two-chain model of spinless fermions with nearest-neighbour interaction
[213]. Numerical calculations seem to prefer the d-wave SS correlations [244]. The orbital
antiferromagnet is a two-chain version of the ﬂux states discussed for the 2D high-Tc
superconductors; these ﬂux phases have been discussed also for anisotropic 2D systems as
we consider them here [245]. They model systems with both open and closed orbitals in the
neighbourhood of the Fermi surface, and in the anisotropic limit, instabilities reminiscent
of the 1D systems are found.
    There is also a detailed picture of the excitations created upon hole-doping a t − J-
ladder [244]. The lowest excitation at half-ﬁlling is a spin-triplet above the gap. Doped
holes (with concentration δ) will pair so that the spins can take advantage of the singlet
binding across the rungs. One obvious magnetic excitation is the triplet, again, which
can propagate in the ladder with an exchange integral J/2 while the hole pair moves with
1/(J⊥ − 4/J⊥ ). The number of such possible triplets goes as (1 − δ). But there is another
possibility: one can form quasi-particles, singly occupied rungs, carrying charge and spin-
1/2, as a bound holon-spinon pair. These quasi-particles will move with a hopping element
t/2 and their number scales with δ. They have triplet spin correlations. In a wide range
of J⊥ , the creation of such quasi-particles is energetically favourable, and the spin gap
is then reduced from the singlet-triplet gap of the half-ﬁlled model. Consequently, the
dynamics and thermodynamics of the spin excitations is dominated by diﬀerent energy
scales as the doping level is varied: increasing doping will bring up a new low-energy scale
associated with the quasi-particle excitations [244]. The quasi-particles also show up in
the single-particle spectral function although there are sizable incoherent contributions.
There is a coherent peak dispersing towards the Fermi energy as k → kF , until the spin
gap is reached. In this limit, the particle peak at ω > 0 has acquired a strong shadow
component at ω < 0, as in a superconductor [244]. On the other hand, this strong

                                              126
shadow component is the direct continuation of the spectral weight at ω < 0 found for
the Luttinger liquid in Section 3.3, Fig. 3.6, to a situation where a fully developed spin
gap exists.
    A generalization of this picture for four coupled t − J-chains is now available [246].
Also, the interplay of superconductivity and phase separation has been studied in the
regime of large J/t [247]. Here, a strong possibility for phase separation between the
chains is found, and this is precisely the range where strong signals of superconductivity
are detected. Notice, however, that these J values are out of the range which can be
derived from large-U Hubbard models, although more general models do allow them [97].
    Very recently, the partition and Green functions have been derived for Luttinger liquids
on an arbitrary number of chains coupled by interchain hopping, including charge-spin
separation [248]. This analysis essentially conﬁrms the earlier results [22] where this
feature had been neglected. Provided the interactions are not so strong that a two-
particle crossover would occur before the single-particle crossover, this work provides us
with Green functions containing explicitly a quasi-particle residue indicative of a Fermi
liquid ground state in this case, plus correction terms containing the remnants of the 1D
Luttinger liquid. Others give explicit spectral functions for the case of selfconsistently
screened Coulomb interactions [52, 228] including interchain hopping [249] although some
approximations made may overestimate the anomalous 1D component of the spectra.
    An important virtue of the variational wavefunctions used for mapping out the Lut-
tinger liquid correlations of the 1D t−J-model in Section 4.4 is the possibility to generalize
them to 2D [250]. The Luttinger liquid state with nontrivial Kρ is stabilized by gains
in kinetic energy with respect to the Gutzwiller wave function describing a Fermi liquid.
It possess the anomalous dimensions of a Luttinger liquid but no charge-spin separation.
Moreover, as in the 1D case, one can apply the power method to obtain increasingly
accurate approximations to the true ground state which conserve the typical power laws
[251]. There have been claims of charge-spin separation in the 2D t − J-model based on
high-temperature expansion [252] but this interpretation of the data has been opposed by
others [253].
    An approach rather diﬀerent from the work above has been taken by Castellani et
al. who consider fermions with short-range interactions in continuous dimensions 1 ≤ D ≤
2 [254]. Here, the Fermi surface is closed and isotropic in the D-dimensional reciprocal
space while the approaches coupling 1D Luttinger liquids with t⊥ ≪ tk all imply open
warped Fermi surfaces which conserve a strong 1D character. They ﬁnd that while the
1D conservation laws for total charge and spin on a branch of the dispersion, Eqs. (3.106)
and (3.107), are no longer satisﬁed exactly, similar laws for charge and spin associated
with directions radially outward from the D-dimensional Fermi surface are still obeyed
asymptotically. This allows the formulation of corresponding asymptotic Ward identities
which strongly constrain the low-energy physics close to the Fermi surface. In particular,
a Fermi liquid ﬁxed point is found for all dimensions D > 1. However, for dimensions
D ≤ 2, there are dramatic corrections to quasi-particle behaviour away from the ﬁxed
point. They are strongly reminiscent of the behaviour of 1D Luttinger liquids but now
in radial direction. Such a “tomographic Luttinger liquid” behaviour at ﬁnite energy

                                             127
could completely mask the Fermi liquid ﬁxed point physics, and provide a realization of
Anderson’s suggestion [11]. Singular interactions, as proposed by Anderson, could then
conceivably stabilize such physics also at the ﬁxed point.
   We ﬁnally mention that there is a variety of work in 2D producing evidence for non-
Fermi-liquid and possibly Luttinger liquid low-energy physics using peculiar, often long-
range, interaction Hamiltonians [255]. Others attempt to describe the Fermi liquid with
methods borrowed from the 1D systems reviewed here, such as bosonization and renor-
malization group [256]. In some sense, one goes the way opposite to the one we took in
Section 3.5 where we applied standard techniques of Fermi liquid theory in 1D. Further
development of these methods will hopefully sharpen our understanding of scenarios for a
possible breakdown of Fermi liquid theory in higher dimensions, and for similarities and
diﬀerences to the 1D case reviewed here.


6.3     Edge states in the quantum Hall effect
When a 2D electron gas which can be created in the inversion layer of a metal-oxide-
semiconductor or a semiconductor heterostructure, is exposed to a strong magnetic ﬁeld, it
is observed that the Hall conductance is quantized in units of the elementary conductance
σxy = νe2 /h [257]. The initial observation was that ν is integer [258] but subsequently
fractional ν were discovered, too [259]. In both cases, the quantization is due to the
existence of a mobility gap at the Fermi level in the bulk of the sample, although its
microscopic origin is diﬀerent: in the integer eﬀect, disorder leads to localized states
while in the fractional eﬀect, correlations condense the particles into a new collective
state whose excitations are gapped. Due to the mobility gap in the bulk, transport must
take place on the edge of the sample – a 1D manifold.
     The basic model for the integer eﬀect was put forward by Halperin [260] and developed
further by Büttiker [261] and others [262]. In Fig. 6.5 an annulus with inner radius r1 and
outer radius r2 is considered and the disorder is supposed to be conﬁned to the bulk of
the annulus. The edges are shifted upward in energy because of the boundary condition
of vanishing wavefunction at the sample boundaries. Although all bulk states at EF are
localized (if there are any), at the ﬁelds where σxy shows a plateau, low-energy excitations
are possible at the edges. The excitations living on the edges are ordinary electrons.
They form a 1D chiral Fermi liquid – Fermi liquid now understood in the sense of the
higher-dimensional systems. In the Luttinger model (3.1), there is only one of the two
dispersion branches: due to the orbital coupling, all electrons move in the same direction,
i.e. have a deﬁnite chirality. This leaves g4 as the only possible interaction. However, due
to Zeeman coupling, the electrons are fully spin-polarized, and g4⊥ , in principle able to
generate charge-spin separation, is quenched. Remains g4k which only renormalizes the
Fermi velocity and does not destroy the quasi-particle pole in the Green function.
     Gapless edge excitations also exist in the fractional quantum Hall eﬀect, and Wen has
clariﬁed their nature and dynamics in considerable detail [174]. We attempt to follow
his proceeding here, because his way from very general principles (essentially only gauge


                                            128
invariance, locality of the theory, and incompressibility of the ground state) to a detailed
operator description of the low-energy properties is in some sense opposite to the bulk
of our earlier presentation, and highly instructive. Related work has been performed by
Stone [263].
    We ﬁrst ﬁx the general form of the action of the edge excitations from the requirement
of gauge invariance. Assume that a system displays the quantum Hall eﬀect with σxy =
νe2 /h in an magnetic vector potential Āµ . We do not know the detailed Hamiltonian,
but due to the gap in the quasi-particle excitations, we know that the electrons can be
integrated out safely, resulting in an eﬀective Lagrangian

                        νe2                   1             1
      Leff [δAµ ] =         δAµ ∂λ δAκ ǫµλκ + 2 (δF01 )2 − 2 (δF12 )2 + . . . ,        (6.46)
                        4π                   4g1           4g2
             δAµ      = Aµ − Āµ ,        δFµλ = ∂µ δAλ + ∂λ δAµ ,       µ = 0, 1, 2 .

δFµλ is the strength of the magnetic ﬁeld. The ﬁrst term on the right-hand side is
called Chern-Simons term, and its coeﬃcient is given by the Hall conductance. The
detailed properties of Leff are unimportant in what follows. On a compactiﬁed space,
say a torus, the action Sbulk = d3 x Leff [δAµ ] is invariant under gauge transformations
                                 R

Aµ → Aµ + ∂µ f (x). This is not so on a bounded space where

                                                             νe2
                                                                   Z
                  Sbulk [Aµ + ∂µ f (x)] = Sbulk [Aµ ] +                dx0 dσf (x)δFσ0 (x) .          (6.47)
                                                             4π
The variable σ parameterizes the boundary, and x0 = t. Gauge invariance is violated
by a boundary term generated by the Chern-Simons term. A gauge invariant action can
now be obtained by adding a boundary action Sedge , from which the properties of the
boundary excitations can be constructed. Sedge alone must not be gauge invariant and
must transform as (6.47) but with a minus-sign in front of the Chern-Simons contribution,
and is given by
         1
             Z
                                           αβ
 Sedge =         dt dσ dt′ dσ ′ δAα (t, σ)R(j) (t − t′ , σ − σ ′ )δAβ (t′ , σ ′ ) ,   (α, β = 0, σ) , (6.48)
         2
        αβ
where R(j)  is the time-ordered current-current correlation function (containing, in the
notation of Chapter 3, Rρρ , Rjj and Rρj ). It has the properties

             αβ         νe2 αβ                  αβ           αβ            αβ
                                                                              h           i⋆
       − kα R(j) =         ǫ kα ,              R(j) (kα ) = R(j) (−kα ) = R(j) (−kα )          ,      (6.49)
                        4π
where kα = (ω, k) is a reciprocal space vector. We recognize the ﬁrst equation as a Ward
identity, up to the diﬀerent right-hand side identical to (3.113). The second equation im-
plements the required symmetries (even for the symmetric and odd for the nonsymmetric)
and the reality of the correlation functions.
   One can imagine knowing the Hamiltonian for the edge excitations and their coupling
to the gauge ﬁeld Aα . By integrating out the edge excitations, one would then obtain
the action (6.48). We proceed inversely and try to get information on the dynamics of
the excitations from the eﬀective action. Assume that all edge excitations are gapped,

                                                       129
and that the theory is local. Then R(j) is smooth near ω = 0 and k = 0. But a smooth
function cannot satisfy (6.49). There must thus be gapless excitations (labelled by i).
If their dispersion is linear ω(k) = vi k, and if R(j) has pole structure for the gapless
excitations (the gapped ones can only contribute polynomials), its singular part must be
of the form
                αβ sing                    δij ηi S αβ (ω, k)
               R(j),ij  (ω, k) =                              ,                              (6.50)
                                            2π(ω − vi k)
                     S 00 = k      ,       S 0σ = S σ0 = (ω + vi k)/2 ,      S 11 = vi ω .

ηi = sign(vi )qi2 , where qi is the charge of the excitations. There must be an operator jiα (k)
which generates a state with energy ω(k) = vi k from the vacuum. One can then deduce
ﬁrst the vacuum expectation values of the commutators of ji± (k) = [ji0 (k) ± jiσ (k)/vi ]/2
from the correlation functions, and then, under some very general further assumptions,
the algebra of the operators themselves

                [ji+ (k), jj+ (k ′ )] = |ηi |kδi,j δk,−k′ ,        [H, ji+ (k)] = ckji+ .    (6.51)

For sign(vi )sign(k) < 0, the operator ji+ (k) acts as an annihilation operator. For sign(vi )sign(k) >
0, it generates the harmonic spectrum of H. The operator ji− (k) acts as a null operator.
    We recognize the algebra of the ji+ (k) (6.51) as a U(1)-Kac-Moody algebra. Unlike
Eq. (3.169), however, the prefactor of the right-hand side is |ηi | rather than unity. This
suggests that our edge excitations on each branch i are described by a U(1)-Kac-Moody
algebra with a central charge c = |ηi | = qi2 . Following our discussion in Section 3.6, we
then can construct both an eﬀective action as a bilinear in boson currents ji± and in terms
of chiral fermions Ψi coupled to a gauge ﬁeld, and the latter reads
                             XZ
                 Sedge = i             dtdσΨ†i [(∂t + iqi δA0 ) + vi (∂σ + iqi δAσ )] Ψi     (6.52)
                              i

with charges qi satisfying the sum rule

                                                      sign(vi )qi2 = νe2 .
                                   X              X
                                           ηi =                                              (6.53)
                                       i          i

For the integer eﬀect (ν integer), the charges are integer i.e. the fermions describe real
electrons, but for the fractional quantum Hall eﬀect, they are irrational in general. If
                                         √
there is a single branch, we have qi = νe. The fermions rather refer to solitons than real
electrons. So long as all edge excitations move in the same direction, there is no possibility
to open a mass gap. Only when velocities have diﬀerent signs (an issue we touch upon
below) can a gap be opened, as a consequence of backward and Umklapp scattering. In
the same way, it should be apparent from the discussion of impurity scattering in Section
4.6 that the edge excitations travelling in the same direction, are not sensitive to scattering
by impurities.
    For practical calculations, of course, the boson representation is more convenient, and
the Hamiltonian corresponding to the boson action is
                                     X X πvi
                                H=            2 i
                                                 ρ (k)ρi (−k) .                          (6.54)
                                       i  k qi


                                                       130
There may be also interactions between diﬀerent excitations, i.e.
                                                 XX
                  H → H + δH ,            δH =             gij ρi (k)ρj (−k) .      (6.55)
                                                 ij    k

This has the structure of the Luttinger Hamiltonian (3.1) with g2 and g4 processes, depend-
ing on the sign of the velocities of the branches, or of its multicomponent generalization
(6.5). In general, the properties will be diﬀerent, however, because c 6= 1. (6.55) can be
diagonalized by a Bogoliubov transformation, leading to new operators ρ̃i , renormalized
velocities ṽi , and to renormalized charges q̃i = j Uij qj where (U)ij is the transforma-
                                                   P

tion matrix. It is these renormalized charges and velocities which are experimentally
measurable in edge magnetoplasmon excitations. Fractional charges can also be found
in the integer eﬀect when several branches of excitations are present. Wen showed that
the renormalized fractional charges can be measured experimentally as the strength of
the peaks in the absorption spectrum of a rotating electric ﬁeld. Also the width of the
resonances is related through the charges to the edge resistance.
    Up to now, we have only considered particle-hole excitations out of the Fermi sea on
the edges, i.e. we have restricted to the charge-zero sector of the theory. We now consider
the charge excitations on the edges, to give a more systematic basis to the notion of
irrational charges, and to construct a relation between the physical fermions Ψ and the
bosons living on the edges. We assume a single excitation branch for the moment with
     √
q = ν. There is thus a deﬁnite chirality. The fermions act as charge-raising operators
                                                       Z
                          [Ψ, Q] = eΨ ,        Q=          dσj 0 (σ) .              (6.56)

The Hilbert space is therefore composed of sectors with charge Q, and within these sectors,
j + creates particle-hole excitations. Within each sector Q, it generates the Fock space
of the harmonic oscillators deﬁned by the U(1)-Kac-Moody algebra (6.51). One can now
introduce a bosonic ﬁeld ϕ(x) via the current and charge
                               √
                     α           ν αβ                      √
                    j (t, σ) =     ǫ ∂β ϕ(t, σ) ,     Q = νNsign v .                 (6.57)
                               2π
The charge-raising operators of a chiral boson theory are in general, Eq. (3.175)

                                   Ψ(x) =: eiγϕ(x) :       .                        (6.58)

From the requirement that they anticommute, we derive γ 2 = 2n + 1, an odd integer.
                                                                                        √
Moreover, Ψ must carry a unit charge. From [Q, Ψ] we ﬁnd that the charge of Ψ is γ ν
which must equal unity. This imposes a restriction on the ﬁlling fractions ν which can be
described by a single branch of excitations ν = 1/(2n + 1). All other ﬁlling fractions must
possess more than one edge excitation – a conclusion also veriﬁed in numerical calculations
[264]. But even in the single-branch situation, a physical electron carrying unit charge,
                                                                        √
added to the edge, is fragmented into solitonic excitations of charge ν. However, the
                                                        √
charges of excited states are integers, not multiples of ν.
   In principle, one can now calculate all the correlation functions on the edge. Due to
the fractional charges, or equivalently to the central charge being diﬀerent from unity,

                                           131
anomalous powers arise even in the one-branch situation, contrary to the standard Lut-
tinger liquid of Chapter 3. This can be seen quite easily from (6.58) where the fractional
charge ν = K plays the same role as the stiﬀness constant played in Chapter 3. The map-
ping is provided by comparing to Eq. (3.67). As an example, the single-particle Green
function is                                              1/ν
                                                      i
                                                 
                                       †
                             hΨ(t, σ)Ψ (0, 0)i ∼               .                       (6.59)
                                                   t+σ
Rewriting this in the form of a standard Luttinger liquid, one concludes that the chiral
single-particle exponent is
                                             1
                                    αchiral = − 1 = 2n                                 (6.60)
                                             ν
for a ﬁlling fraction ν = 1/(2n + 1). The scaling relation between α and K in a chiral
Luttinger liquid is diﬀerent from the non-chiral system. The remarkable fact here is that
the exponents become universal and are fully determined by the ﬁlling of the Landau
levels. This means that one can precisely predict the exponents of the correlation functions
probed by speciﬁc experiments. Moreover, ν being a topological invariant, the exponents
are expected to be robust against perturbations. Wen has proposed the label “chiral
Luttinger liquid” for the low-energy physics of the quantum Hall edge states.
    An interesting generalization, which could also be relevant for situations with several
edges with opposite velocities, is provided by considering the edge states on a cylinder
threaded by the magnetic ﬂux. There are now two edges with excitations moving in
opposite directions, and the Luttinger liquid is no longer chiral. Of course, it can be built
on the chiral Luttinger liquid of a disk, and the structure of the theory is quite similar
to the previous one. There are two important diﬀerences, however: (i) charge excitations
can be transferred between the edges, which complicates somewhat the quantization rules
relating γ in (6.58) to the ﬁlling fraction ν; (ii) if the edges are not too far from each
other, tunneling both of electrons and of Laughlin quasi-particles, the fractionally charged
objects introduced earlier, may take place between them. Electron tunneling can be
described by the operator
                                                       "       #
                                                        ϕ(x)
                                             Z
                               Htunnel = g       dx cos √          ,                   (6.61)
                                                          ν

which is isomorphic in form to our the backscattering operator (4.6). The scaling dimen-
sion of this operator is 2 − 1/ν, and the operator is irrelevant for ν < 1/2 while it is
relevant for ν > 1/2. This would imply that in the integer eﬀect (ν = 1), a gap could
open on the edges when they are brought close enough together. On the other hand, for
the fractional eﬀect ν = 1/(2n + 1) ≤ 1/3, the electron tunneling operator is irrelevant.
Tunneling of Laughlin quasi-particles is possible because the two edges are connected by
the quantum Hall ﬂuid (and not vacuum), and described by an operator (6.61) where,
                        √                   √
however, the factor 1/ ν is replaced by ν [262]. This operator is always relevant. An
important problem, however, is that of a local constriction on a Quantum Hall cylinder:
here the inter-edge tunneling only takes place at x = 0, and the dimension of this operator
is then 1 − ν. It is marginal in the integer eﬀect and relevant for all fractional single-edge

                                                 132
situations. The problem can also be formulated in terms of scattering oﬀ impurities in a
non-chiral Luttinger liquid [169], and out conclusion agrees with the analysis of Section
4.6.
    The dynamical excitations on the edges have a very rich structure which reﬂects the
topological order in the quantum Hall eﬀect. Wen [174, 262] and others [263] have devel-
oped here a chiral Luttinger liquid theory as a framework for a detailed description of their
properties. It is similar to the Luttinger liquid discussed in the preceding chapters but
diﬀers (at least) in one important way: the charges of the edge excitations are fractional
(or irrational), and the universality classes of the chiral and standard Luttinger liquids
are diﬀerent: the central charge describing the edge excitations is diﬀerent from unity.




                                            133
Chapter 7

The normal state of
quasi-one-dimensional metals – a
Luttinger liquid?

A wide variety of materials with low-dimensional structural and electronic properties is
available now, and experimentalists have used them to search for Luttinger liquid corre-
lations. In the main body of this chapter, we shall concentrate on the quasi-1D organic
conductors such as T T F − T CNQ and superconductors like (T MT SF )2 X or the re-
lated (nonsuperconducting) series (T MT T F )2 X. We summarize evidence that electronic
correlations are important in these materials, that in their normal state, they are suf-
ﬁciently anisotropic so that 1D models of interacting electrons are indeed relevant for
their description, and that experiments can be interpreted consistently within the theo-
retical framework set up in this article. At the end, we brieﬂy touch upon semiconductor
heterostructures, a new and rapidly growing branch in the ﬁeld of correlated 1D electrons.


7.1     Organic conductors and superconductors
Tetrathiafulvalene-tetracyanoquinodimethane (T T F − T CNQ) crystalizes in a herring-
bone pattern of two segregated stacks of T T F and T CNQ molecules, respectively. A
charge transfer from the TTF to the TCNQ molecules of 0.57 electron/molecule produces
partially ﬁlled electron- and hole-like bands, i.e. the material behaves as a two-chain
conductor.
    Between 54K and 38K, T T F − T CNQ undergoes a series of phase transitions into a
CDW state, accompanied by a periodic lattice modulation due to electron-phonon cou-
pling. Although the traditional picture due to Peierls would consider electron-phonon
interaction as the driving force of such a CDW transition [5, 265], the actual situation is
more complicated, probably radically diﬀerent.
    In fact, there is ample evidence for important repulsive interactions on both chains. In
X-ray experiments, diﬀuse X-ray scattering is not only detected at 2kF but surprisingly
also at 4kF , even up to very high temperature [266, 267]. While 2kF -ﬂuctuations are


                                            134
expected as precursors of the Peierls transition [265], the existence of 4kF ﬂuctuations
can only be explained assuming sizable Coulomb correlations [58], as can be seen from
comparing the exponents of the 2kF - and 4kF -CDW correlation functions (3.92) and
                                                                            (ph)
(3.93). Notice from Eqs. (4.65) that coupling to lattice phonons (Y2             = 0) reduces
Kρ . When electronic correlations are dominant, phonons can enhance them further, and
they certainly outweigh the logarithmic “advantage” of the SDWs against the 2kF -CDWs.
The Pauli susceptibility is signiﬁcantly enhanced over the free electron value [268, 269]
and the ﬁnite frequency optical conductivity is much larger than the dc-conductivity [167].
Further evidence for Coulomb correlations stems from the analysis of systematic variations
of physical properties through entire families [270] of closely related compounds such as
(NMP )x (P hen)1−x (T CNQ) [110, 271] or the 1 : 2 − T CNQ salts [272].
    There is thus an alternative, well supported view that the CDWs in T T F − T CNQ
are, in fact the consequence of electronic correlations rather than of electron-phonon inter-
action; the latter then would just probe the electronic ﬂuctuations without feeding back
on them in any signiﬁcant manner, and couple the preformed charge density modulation
into the lattice and make it visible to X-rays. This is diﬀerent from other CDW systems
to be discussed in Section 7.2 below.
    Closely related are the single-chain conductors (T MT SF )2 X and (T MT T F )2 X (“Bech-
gaard salts”), where T MT SF stands for the molecule tetramethyl-tetraselenafulvalene.
A sketch of this molecule and of the stacking pattern, immediately suggestive of one-
dimensionality, is shown in Figure 7.1. (T MT SF )2 P F6 undergoes a metal–insulator
transition into a SDW state at ambient pressure at TSDW = 12K. Evidence for SDWs is
provided by peculiar NMR relaxation behaviour [15] but most convincingly by observation
of the nonlinear conductivity associated with a sliding SDW [273]. Under 12 kbar pres-
sure, however, superconductivity can be stabilized at Tc = 0.9K [274]. Other members
of the family show superconductivity, too [275]. By substituting the four selenium atoms
by sulfur, one obtains (T MT T F )2 X. Generically, these sulfur-based systems undergo
a charge localization transition (“Wigner crystallization”) around 200K (seen e.g. as a
minimum in the resistivity) and reduce to an eﬀective spin chain below. Finally, around
20 K, one observes spin-Peierls transitions into a spin-singlet state, accompanied by a
lattice deformation [23]. However, by applying pressure, a behaviour more akin to the
SDW state of (T MT SF )2 P F6 can be obtained.
    The importance of Coulomb interactions in the (T MT SF )2 X and (T MT T F )2 X is
more readily apparent than in T T F − T CNQ. We discussed various Luttinger liquid
correlation functions in Chapter 4, and SDW correlations require repulsive interactions.
In the (T MT T F )2 X-series, the Coulomb repulsion is even stronger than in (T MT SF )2 X:
the charge localization transition around 200K can be interpreted as a transition into a
4kF -CDW [58, 89, 110]. Other properties indicate strong Coulomb interaction, too. The
Pauli susceptibility of the conduction electrons is enhanced considerably (×3 − 5) with
respect to a simple band picture [276]. Moreover, it is temperature dependent and, at low
temperature, close to what is expected for a 1D antiferromagnet [23]. Optical properties
are also unconventional. Apparently it is observed that σ(ω) in the infrared is higher
than the dc-conductivity which is not compatible with free electrons and suggests rather

                                            135
localized charges. In these infrared measurements one also observes totally symmetric
molecular vibrations [277, 278]. These vibrations are IR-forbidden for free electrons but
can be activated by local charge modulations such as a CDW [279]. In the (T MT SF )2 X
and (T MT T F )2 X such a CDW would be at 4kF and the observation of the activated
vibrations in the IR then suggests a considerable degree of charge localization. Strong
electronic repulsion generates antiferromagnetic spin ﬂuctuations which can be, and have
been, observed in NMR [280, 281]. There is also a detailed theory for the analysis of these
experiments which lends further support to a strongly correlated picture for the electrons
in the Bechgaard salts [282, 283].
    The basic building blocks of the materials discussed in the preceding section are large
planar molecules with π-orbitals directed out of the molecular plane. In general, the lat-
tice parameters, the lattice dynamics, and the elastic constants are anisotropic though
not strongly so, and are best viewed as three-dimensional [15]. The electronic properties,
however, are strongly anisotropic. Essentially, the overlap between wave functions on
neighbouring molecules, and matrix elements of a Hamiltonian between them, both de-
pend exponentially on the intermolecular separation: minor variations in the structure are
then dramatically ampliﬁed in the electron dynamics. The sensitive dependence on the
intermolecular distances is further ampliﬁed by the strong directionality of many of the
molecular orbitals involved. However, relatively short distances between Se or S atoms
in the (T MT SF )2 X and (T MT T F )2 X give nonnegligible interstack contacts and some
eﬀectively 2D character to the (T MT SF )2 X salts [284].
    The central question is therefore if the Fermi surface of these organic conductors is
closer to the parallel sheets characterizing 1D or to the cylinder obtained for layered
2D materials, i.e. open vs. closed orbits, and if, for given external parameters (T, P ),
the electrons hop coherently or not from one chain to its neighbour. There seems to
be general agreement [23] that the picture of two sheets, warped by the ﬁnite hopping
integrals perpendicular to the chains, is most appropriate. Values often used are tk ≡ ta =
150 . . . 200meV , t⊥ ≡ tb = 20 . . . 30meV , and tc < tb /10 for (T MT SF )2 X [23] although
next-nearest-neighbour transfer integrals also seem to play some role [284]. Apparently
T T F − T CNQ is signiﬁcantly more anisotropic and the Fermi surface has been suggested
to consist out of two parallel, diﬀuse sheets. Representative transfer integrals are tk =
110meV for the T CNQ chain, tk = 50meV for T T F [15], and t⊥ as low as 5meV [285].
    Transport measurements probe the anisotropy and coherence of the electron dynamics.
In optical absorption, a pronounced plasma edge in the 1eV -range is observed for electric
ﬁelds polarized parallel to the chain axis both in T T F − T CNQ and (T MT SF )2 X, indi-
cating band formation along the chains, and longitudinal bandwidths of the order of 1eV
have been derived within simple tight-binding models. In (T MT SF )2 P F6 , a transverse
plasma edge at about 0.1eV , implying coherent perpendicular transport, is observed only
at T = 25K [15]. In T T F − T CNQ, to the best of the author’s knowledge, the establish-
ment of a transverse plasma edge has never been observed. These measurements support
the picture of a very anisotropic band and rule out the possibility of a closed Fermi surface
in these materials.
    Depending on the magnitude of τk t⊥ /h̄, the transverse transport can be either coherent

                                            136
or diﬀusive. Here τk is the on-chain collision time after which the electron wave function
looses its coherence, i.e. a measure of cleanliness, and t⊥ < tk is assumed. The transverse
escape rate 1/τ⊥ ≈ 2πτk t2⊥ /h̄ can be measured by NMR [286]. The long-wavelength spin
ﬂuctuations on the chains are certainly diﬀusive and then described by a 1D random walk
                  √
which gives a 1/ ωe power spectrum to the NMR relaxation rate 1/T1 T and strong ﬁeld-
dependent deviations from the Korringa law through the electronic Larmor frequency
ωe . At low-ﬁelds, the spin dynamics becomes 3D and 1/T1 T is ﬁeld independent. A
crossover is observed for ωe τ⊥ ≈ 1 in T T F − T CNQ [286] and (T MT SF )2 X [287]. τk
can be estimated e.g. from conductivity. Putting things together, one concludes that, in
T T F − T CNQ, the perpendicular transport is always diﬀusive while in (T MT SF )2 P F6 ,
it is diﬀusive at higher temperature but transverse coherence is established at lower tem-
peratures. One also obtains the above values of t⊥ . This suggests that theories discussing
the establishment of transverse coherence in the single- and two-particle dynamics can be
critically tested here.
     The information available points towards a picture of strong Coulomb interaction and
pronounced one-dimensionality. What is the experimental evidence in favour of Lut-
tinger liquid behaviour in these “metals”? The instabilities observed at low temperatures
are certainly suggestive of 1D physics. Of course, they do not tell us much about the
normal-state properties; still the observation of high-temperature 4kF -CDW ﬂuctuations
in T T F − T CNQ [266, 267] places constraints on the eﬀective Luttinger parameters:
Kρ < 1/2 for their divergence, and Kρ < 1/3 for them being stronger than the 2kF -CDWs.
These low values of Kρ indicate that a simple Hubbard model is certainly inappropriate
for the description of this compound, and that longer range interactions cannot be ne-
glected. The optical spectrum of T T F − T CNQ is very unusual (Figure 7.2). There is
a pronounced pseudogap present already at 85 K, i.e. far above the Peierls temperature,
which deepens as the temperature is lowered into the CDW phase. It is tempting to
connect this with the pseudogap observed in the density of states [167], and in fact, σ(ω)
is not incompatible with the expression (4.75) derived by Ogata and Anderson [166], if
the large α-values implied by the 4kF -ﬂuctuations are inserted.
     In the (T MT SF )2 X-materials, NMR has uncovered anomalous correlations [280, 281]
(Figure 7.3). The spin-lattice relaxation rate T1−1 strongly deviates from the Korringa
law T1−1 ∝ T at lower temperatures. This is believed to result from the temperature
dependent SDW-correlations. In fact, T1−1 contains two contributions, from the long-
wavelength and the 2kF -spin-ﬂuctuations: T1−1 ∝ T + T 1−αSDW = T + T Kρ . Here, we have
a quantity which can give direct information on Kρ ! Below a certain temperature T0 , the
SDW contribution T Kρ dominates over the long-wavelength part T . From the latest work
[281], one deduces Kρ ∼ 0.15. This is a surprisingly big value, and again indicates eﬀective
strong and long-range interactions. One problem here, in contrast to T T F − T CNQ is
that the 4kF -ﬂuctuations predicted in this limit, are not observed in X-rays (but they are
neither in the (T MT T F )2 X-series where 4kF -localization is established quite ﬁrmly).
     Similar values of Kρ are suggested by the photoemission experiments shown in Figure
7.4. This experiment measures the occupied (ω < 0) part of the single-particle density of
states N(ω) (3.87). There is no spectral weight at the Fermi surface, and it rises smoothly

                                            137
as one goes to lower energies. The origin of the peak at −1eV is not clear – this scale
lies at the lower edge of the valence band, or even below. Close to the Fermi energy,
the smooth variation is compatible with the Luttinger liquid form |ω|α if one assumes an
exponent α > 1. The NMR-Kρ = 0.15 implies α ∼ 1.25, and this value describes the data
quite well.
    Summarizing, there are experimental indications in favour of Luttinger liquid correla-
tions in these quasi-1D organic conductors which, if taken serious, would place them in
the limit of strong, long-range eﬀective interactions. The experiments described probe,
however, only the anomalous operator-dimensions. There has been no successful attempt
to measure charge-spin separation. From Section 3.4, this would require angle-resolved
photoemission or inelastic neutron scattering. However, the relevance of a Luttinger liq-
uid description, even within a 1D framework, has been questioned [289]. In fact, the
(T MT SF )2 X-materials are slightly dimerized, and therefore the Fermi level lies in an ef-
fectively half-ﬁlled subband, where even weak interactions can lead to charge localization
and an associated charge gap, cf. Chapter 5. The unusual phenomena observed would, in
this view, either be extrinsic or mainly reﬂect the consequences of a Mott transition. At
the time of writing, the controversy over the appropriate model for describing the organic
conductors is pretty open.


7.2     Inorganic charge density wave materials
Many inorganic crystals, such as e. g. K0.3 MoO3 , (T aSe4 )2 I, NbSe3 etc. undergo, at tem-
peratures between 50K and 250K, a Peierls transition into a CDW ground state, giving
rise to fascinating nonlinear transport phenomena [290]. Apart NbSe3 which apparently
is quite 3D and where pieces of a Fermi surface persist even into the CDW state, the
materials, generically, are rather 1D and do not show indications of strong electronic
correlations.
    The driving mechanism for CDW formation is the electron-phonon interaction [5],
and accordingly, this interaction is supposed to be the dominant one in these materials.
Considerable success in describing their normal state properties has been achieved based
on the model of a ﬂuctuating Peierls insulator [291]. The basic idea here is that 1D
ﬂuctuations will lower the actually observed critical temperature TP below the 1D mean-
ﬁeld temperature TPM F by as much as a factor of 4 − 5. In the ﬂuctuation regime, there is
a pseudo-gap in the electronic density of states which develops into a real gap only at TP
and which accounts for the unusual thermodynamic and transport properties above TP .
There is no pseudo-gap left beyond TPM F .
    The ﬂuctuating Peierls insulator model is a single-particle picture, i.e. charge and
spin degrees of freedom behave symmetrically. This is observed in some materials, such
as (T aSe4)2 I, but not in others, e.g. K0.3 MoO3 , where the dc-conductivity is totally
unaﬀected by the conjectured pseudo-gap while the susceptibility shows temperature de-
pendence reminiscent of thermal activation. Moreover, the transition in conductivity
is extremely sharp – but gradual in susceptibility [292]. The Lee-Rice-Anderson picture


                                            138
seems to imply that above TPM F the system reduces to a normal metal. The corresponding
temperature-independent Pauli susceptibility above TPM F has, however, not been observed
in any of the 1D CDW materials.
    Photoemission experiments question the validity of the picture of a ﬂuctuating Peierls
insulator. As in the organic conductors, the single-particle density of states shows no
signiﬁcant weight at the Fermi energy in the blue bronze K0.3 MoO3 , and appreciable
spectral weight is only found a sizable fraction of an eV below [293]. Angle-resolved
studies on related materials either show a fading away of the signal as the Fermi surface is
approached [294], or weight dispersing some ﬁnite energy below EF [295]. Clearly, there
have been speculations about 1D correlations at the origin of the mysterious behaviour.
    Experimental evidence points against simple Luttinger liquid behaviour in these CDW
materials. On the other hand, our renormalization group analysis (4.65) in Section 4.5
shows that, in such a 1D scenario, a spin gap ∆σ must open as a precursor of CDW
formation while the charge ﬂuctuations remain massless in strictly 1D. Such a system is in
the Luther-Emery universality class [186]. The Pauli susceptibility rising with increasing
temperature, found in all CDW materials, can be interpreted as evidence for such a spin
gap. The conductivity of the blue bronze K0.3 MoO3 also provides evidence for massless
charge ﬂuctuations [292]. One can compute, at least the diagonal part of the single-particle
density of states for this model and ﬁnds [53]

                           N(ω) ≈ Θ(|ω| − ∆σ )(|ω| − ∆σ )2γρ ,                         (7.1)

where γρ has been deﬁned in (3.84). Such a behaviour is consistent with the photoemission
properties of the blue bronzes. We note, however, that (i) optical experiments [296] are
in excellent agreement with the ﬂuctuating-Peierls-insulator model when one goes beyond
the Lee-Rice-Anderson treatment and includes the thermally excited motion of the lattice
[297], and their precise relation to the photoemission experiments is not understood to
date; (ii) there is no evidence for charge-spin separation in CDW-materials other than
K0.3 MoO3 which therefore are not in the Luther-Emery universality class.
    Similar unusual photoemission behaviour: absence of spectral weight at the Fermi
surface and a smooth rise below, has also been reported for another inorganic 1D material,
BaV S3 [298].


7.3     Semiconductor heterostructures
Semiconductor heterostructures may open a wide new ﬁeld for the study of 1D interacting
electrons, in regimes usually inaccessible to organic crystals. There are two principal
directions: (i) quantum wires and (ii) quantum Hall eﬀect edge states.
    Traditionally, a 2D electron gas is induced at interfaces in such structures by applying
a gate voltage across the structure. Very recent progress has allowed the fabrication of
narrow channels in the heterostructures where the electrons can be conﬁned [299] into a
quantum wire. The electronic system can be made truly one-dimensional by appropriate
design of the structure. Periodic conductance oscillations are observed as a function of the

                                            139
carrier density, and it has been speculated that they could be either due to the formation
of a charge density wave or of a Wigner crystal [299]. Wigner crystal formation, i.e. the
formation of 4kF -CDWs has been discussed in Chapter 4 [89, 90, 112, 148]. Furthermore,
the 1D channel can be constricted, and we can verify the predictions for transport through
an impurity, discussed in Section 4.6.
    Such a constriction can also be built on samples showing the quantum Hall eﬀect.
From Section 6.3, we know that the edge states are described as chiral Luttinger liquids.
For the ν = 1/3 quantum Hall state where we have a single edge, the Luttinger stiﬀness
constant is K = ν = 1/3. The exponents of all correlation functions are fully determined
by the ﬁlling-factor ν of the Landau levels! Eq. (4.82) shows that the corrections to the
Luttinger liquid conductance diverge as T → 0. An equation equivalent for the opposite
case, tunneling across the constriction, predicts the tunneling conductance across the
constriction to vary as G(T ) ∼ T 4 [169]. Such an experiment has been performed [300],
and the result shown in Figure 7.5 is in accurate agreement with the theoretical prediction.
For comparison, a temperature independent conductance is expected for a Fermi liquid
(K = 1), and is indeed found in the integer ν = 1-state [300]. The scaling with applied
point-contact voltage is similar. Again, for the ν = 1/3-state, a strong variation with
voltage is found while the variation for ν = 1 is much weaker [300]. It would be very
interesting to see if such constrictions can also be used to separate charge and spin of the
electrons on the two sides, as suggested in Section 4.6.




                                            140
Chapter 8

Summary

We have gone a long way from the simplest 1D model Hamiltonian, the Luttinger model,
to exotic correlations in complicated materials, often uncovered only under extreme con-
ditions. It is certainly useful to brieﬂy summarize the essential steps and achievements.
    Fermi liquid theory based on a quasi-particle picture as in higher dimensions, does not
work in 1D because of two new features with respect to 3D: a logarithmic divergence in
the particle-hole bubble, due to the perfect nesting of the 1D Fermi surface, and because
of charge-spin separation in 1D. Both eﬀects are connected to the fact that momentum
transfer cannot be neglected in the scattering processes in 1D.
    Quasi-particles are unstable in 1D, and the elementary excitations are bosonic col-
lective charge and spin ﬂuctuations. The Luttinger model incorporates these essential
features and can therefore be taken as a basis for the description of gapless 1D quantum
systems. This model has been solved by several methods: bosonization, equation of mo-
tion and Green’s function techniques, conformal ﬁeld theory. All of them are related to
the symmetries and conservation laws of the 1D Fermi surface, but incorporate them in a
diﬀerent manner. While the use of Ward identities in the Green’s function method empha-
sizes strong similarities to the Fermi liquid, bosonization rather displays the diﬀerences.
In particular, we used bosonization to compute correlation functions. They decay as non-
universal power-laws, and the scaling relations between their exponents are parameterized
by a single eﬀective coupling constant Kν per degree of freedom. In addition, there is a
renormalized velocity of each collective mode. It renormalizes the thermodynamic and
transport properties, but its most spectacular consequence, charge-spin separation, is only
visible in dynamical correlations at large wave-vector, such as the single-particle spectral
function close to kF or the charge and spin structure factors at 2kF .
    The eﬀective coupling constant is deﬁned from the velocities associated with three
diﬀerent low-energy excitations: particle-hole excitations, charge (±kF -symmetric addi-
tion of particles) and current (kF ↔ −kF -transfer of particle) excitations, and thus from
the eigenvalue spectrum alone. This structure persists in a low-energy subspace of more
complicated models containing nonlinear dispersion, (irrelevant) large-momentum trans-
fer scattering, coupling to external degrees of freedom, etc., and carries to the notion of
a “Luttinger liquid”. It implies that the low-energy properties of these models are de-
scribed by a renormalized Luttinger model, provided their excitations are gapless. The

                                            141
Luttinger liquid is the universality class of these gapless 1D quantum systems. By a
controlled mapping of 1D models ranging from the Hubbard model to electron-phonon
systems, an asymptotically exact solution of the 1D many-body problem is achieved. We
have discussed several procedures, some applicable only where an exact solution by Bethe
Ansatz is possible, others generally applicable and therefore also suited for non-soluble
models. We often used renormalization group which is not as powerful as methods based
on an exact eigenvalue spectrum because it is based on perturbative developments and
thus limited to weak coupling. While failing quantitatively at stronger coupling, most
of its predictions are qualitatively valid beyond the weak-coupling range. In particular,
it allows to derive logarithmic corrections to correlation functions which lift the unphys-
ical degeneracies implied by their exponents. Moreover, it is ﬂexible enough to allow
a treatment of problems beyond the reach of both exact and numerical solutions such
as electron-phonon coupling and scattering oﬀ impurities. It is therefore essential for
a determination of transport properties, to which we devoted much space. Of course,
Luttinger liquid behaviour is also found in multi-band and multi-component models, and
most methods generalize straightforwardly to these problems.
    Not all 1D fermion systems are Luttinger liquids. When backward or Umklapp scat-
tering operators become relevant, as they do for attractive interactions or commensurate
band-ﬁllings, respectively, a gap opens in the spin or in the charge channel. Passing back
and forth between strong- and eﬀective weak-coupling models, a detailed picture of their
properties can be constructed. We have done this in particular for the Mott transition in
commensurate, repulsively interacting systems, and emphasized phase diagrams, critical
interaction strengths, and the scaling behaviour of transport properties and correlations.
    The solution of the Luttinger, Hubbard and other models relies in an essential way on
the strong conservation laws provided by the small phase space of 1D. An important prob-
lem therefore is the stability of the Luttinger liquid with respect to transverse coupling.
Coupling by interchain Coulomb interaction often gives only quantitative modiﬁcations of
the 1D behaviour, except for backscattering which can stabilize charge density wave cor-
relations into a long-range ordered phase. Interchain tunneling on the other hand can lead
to transverse coherence either in the single- or in the two-particle dynamics, depending on
the on-chain correlations, and stabilize a variety of phases. If a single-particle crossover
occurs ﬁrst, as the temperature is lowered, the Peierls-Cooper interference in destroyed,
and a low-temperature phase transition may take place in one channel alone. Despite
intense research, the normal-state properties above such a transition, are not fully clear
to date. There seems to be agreement that charge-spin separation is an essential feature
in this situation, but there is disagreement on the extent to which it conﬁnes the electron
dynamics onto a single chain. A two-particle crossover may occur before the single-particle
one, and the on-chain correlations are then propagated by transverse particle-particle or
particle-hole pair hopping, leading again to low-temperature phase transitions. Here, the
normal state is of 1D Luttinger type. An important problem is the Hubbard model on two
or more coupled chains, and at least the two-chain variant provides evidence for possible
superconducting correlations at repulsive interactions.
    Many experiments have provided evidence for Luttinger liquid correlations in low-

                                            142
dimensional materials, although there is often some controversy about their precise inter-
pretation. Quasi-1D organic conductors and superconductors, for example, show (T T F −
T CNQ) diﬀuse X-ray scattering at 2kF and 4kF and strongly depressed low-frequency
optical conductivity, and others ((T MT SF )2 X) power-law deviations from the Korringa
law in NMR, and vanishing spectral weight at the Fermi surface in photoemission. These
experiments point towards really strong, and in particular long-range, interactions. In-
strumental to this conclusion are bounds on the Luttinger coupling constants Kν derived
from mapping various lattice models onto the Luttinger model. Suggesting single-particle
exponents α in excess of unity, in fact, there are no known lattice models which naturally
would provide values so big. This certainly is a major problem for future research and for
the modelling of these materials.
    Similarly surprising is the absence of spectral weight at EF in inorganic charge density
wave systems although these are believed to be dominated by electron-phonon coupling.
From our discussion of phonon-coupled Luttinger liquids, we have suggested that they fall
into the Luther-Emery universality class, and that spin gap formation is quite generally a
precursor of charge density wave formation. Studies of spectral functions for these models
are certainly called for.
    Finally, edge state transport in the fractional quantum Hall eﬀect is an exciting new
area of low-dimensional physics. We have discussed how these gapless edges can be
modelled as chiral Luttinger liquids. While they are similar to those discussed before,
having a central charge c 6= 1, they fall into a diﬀerent universality class. They also have
power-law correlations, but their charges in general are irrational. Still, much of what has
been said about correlation functions and transport for the normal Luttinger liquid carries
over to the chiral variant. The remarkable feature here is that, at least for the single-edge
situations, the renormalized coupling constant K is fully determined by the Landau level
ﬁlling fraction K = ν, and therefore all correlation exponents (i) are known in advance,
and (ii) can be tuned accurately by varying ν. A recent experiment on tunneling through
a barrier on the edges at ν = 1/3 is in agreement with the chiral Luttinger prediction and
apparently provides a ﬁrst evidence for the relevance of this picture.


Acknowledgements
I should like to thank the following colleagues for stimulating interaction, helpful sug-
gestions, criticism, and essential support, often over many years: Jim Allen, Natan An-
drei, Claude Bourbonnais, Sergei Brazovskiĭ, Helmut Büttner, David Campbell, Laurent
Caron, Michele Fabrizio, Florian Gebhard (especially for many constructive comments on
the present article), Thierry Giamarchi, Daniel Malterre, Thierry Martin, Eugene Mele,
Philippe Nozières, Jürgen Parisi, Jean-Paul Pouget, Dierk Rainer, Mario Rasetti and the
Institute for Scientiﬁc Interchange in Torino, Heinz Schulz, Markus Schwoerer, André-
Marie Tremblay, Joe Wheatley. The responsibility for ﬂaws in this article is, however,
entirely mine. My research is supported by Deutsche Forschungsgemeinschaft through
SFB 279–B4.


                                            143
Bibliography

 [1] L. D. Landau, Sov. Phys. JETP 3, 920 (1957); 5, 101 (1957); 8, 70 (1959).

 [2] P. Nozières, Interacting Fermi Systems, W. A. Benjamin Inc, New York (1964).

 [3] F. D. M. Haldane, J. Phys. C 14, 2585 (1981).

 [4] J. M. Luttinger, Phys. Rev. 119, 1153 (1960).

 [5] R. Peierls, Quantum Theory of Solids, Oxford University Press, London (1955).

 [6] J. Bardeen, L. N. Copper, and J. R. Schrieﬀer, Phys. Rev. 108, 1175 (1957).

 [7] J. M. Luttinger, J. Math. Phys. 4, 1154 (1963).

 [8] S. Tomonaga, Prog. Theor. Phys. 5, 544 (1950).

 [9] D. C. Mattis and E. H. Lieb, J. Math. Phys. 6, 304 (1963).

[10] K. B. Efetov and A. I. Larkin, Sov. Phys. JETP 42, 390 (1976).

[11] P. W. Anderson and Y. R. Ren, Proceedings of the Los Alamos Conference on High-
     Tc -Superconductivity, Addison Wesley Publ. Comp., 1990, p. 3; P. W. Anderson,
     Phys. Rev. Lett. 64, 1839 and 65, 2306 (1990).

[12] J. R. Engelbrecht and M. Randeria, Phys. Rev. Lett. 65, 1032 (1990); D. Coﬀey
     and K. S. Bedell, ibid. 71, 1043 (1993).

[13] C. M. Varma, P. B. Littlewood, S. Schmitt-Rink, E. Abrahams, and A. E. Rucken-
     stein, Phys. Rev. Lett. 63, 1996 (1989); N. Mitani and S. Kurihara, Physica C 192,
     230 (1992).

[14] I. Perakis, C. M. Varma, and A. E. Ruckenstein, Phys. Rev. Lett. 70, 3467 (1993);
     G.-M. Zhang and L. Yu, ibid. 72, 2474 (1994); C. Sire, C. M. Varma, A. E. Rucken-
     stein, and T. Giamarchi, ibid. p. 2478. See also G. M. Eliashberg, JETP Lett. 46,
     S81 (1988); B. R. Alascio and C. R. Proetto, Sol. St. Comm. 75, 217 (1990).

[15] D. Jérôme and H. J. Schulz, Adv. Phys. 31, 299 (1982).

[16] Proceedings of recent conferences on Synthetic Metals, e. g. Synth. Met. 27 (1988)
     – 29 (1989); 41 – 43 (1991); 55 – 57 (1993); 69 – 71 (1995).

                                         144
[17] P. Nozières and A. Blandin, J. Phys. (Paris) 41, 193 (1980); N. Andrei and C.
     Destri, Phys. Rev. Lett. 52, 364 (1984); A. W. W. Ludwig and I. Aﬄeck, Phys.
     Rev. Lett. 67, 3160 (1991).

[18] J. Sólyom, Adv. Phys. 28, 201 (1979).

[19] V. J. Emery, in Highly Conducting One-Dimensional Solids, ed. by J. T. Devreese,
     R. E. Evrard, and V. E. van Doren, Plenum Press, New York (1979).

[20] I. Aﬄeck, in: Fields, Strings, and Critical Phenomena, ed. by E. Brézin and J.
     Zinn-Justin, Elsevier Science Publishers B. V., Amsterdam, 1989.

[21] Yu. A. Firsov, V. N. Prigodin, and Chr. Seidel, Phys. Rep. 126, 245 (1985).

[22] C. Bourbonnais and L. G. Caron, Int. J. Mod. Phys. B 5, 1033 (1991).

[23] D. Jérôme, Science 252, 1509 (1991).

[24] J. M. Williams, A. J. Schultz, U. Geiser, K. D. Carlson, A. M. Kini, H. H. Wang,
     W.-K. Kwok, M.-H. Whangbo, and J. E. Schirber, Science 252, 1501 (1991).

[25] Low-Dimensional Conductors and Superconductors, ed. by D. Jérôme and L. G.
     Caron, Plenum Press, New York, 1987.

[26] B. Sutherland, in Exactly Solvable Problems in Condensed Matter and Relativistic
     Field Theory, Lecture Notes in Physics 242, 1 (1985).

[27] V. E. Korepin, N. M. Bogoliubov, and A. G. Izergin, Quantum Inverse Scattering
     Method and Correlation Functions, Cambridge University Press, Cambridge, 1993.

[28] Yu. A. Izyumov and Yu. N. Skryabin, Statistical Mechanics of Magnetically Ordered
     Systems, Consultants Bureau, New York, 1988, chapter 5.

[29] A. A. Belavin, A. M. Polyakov, and A. B. Zamolodchikov, Nucl. Phys. B 241, 333
     (1984); Fields, Strings, and Critical Phenomena, ed. by E. Brézin and J. Zinn-
     Justin, Elsevier Science Publishers B. V., Amsterdam, 1989; C. Itzykson and J.-M.
     Drouﬀe, Statistical Field Theory, Cambridge Universtity Press, Cambridge, 1989,
     vol. 2; Y. Grandati, Ann. Phys. Fr. 17, 159 (1992); A. W. W. Ludwig, Trieste
     Lectures 1992.

[30] Yu. A. Bychkov, L. P. Gorkov, and I. E. Dzyaloshinskiĭ, Sov. Phys. JETP 23, 489
     (1966).

[31] R. Heidenreich, R. Seiler, and A. Uhlenbrock, J. Stat. Phys. 22, 27 (1980).

[32] A. Luther and I. Peschel, Phys. Rev. B 9, 2911 (1974).

[33] D. C. Mattis, J. Math. Phys. 15, 609 (1974).


                                          145
[34] I. E. Dzyaloshinskiĭ and A. I. Larkin, Sov. Phys. JETP 38, 202 (1974).

[35] H. U. Everts and H. Schulz, Sol. State Comm. 15, 1413 (1974).

[36] M. Apostol, J. Phys. C 16, 5937 (1983).

[37] This argument was suggested by Michele Fabrizio.

[38] R. de L. Kronig, Physica 2, 968 (1935).

[39] E. Witten, Commun. Math. Phys. 92, 455 (1984).

[40] S. Mandelstam, Phys. Rev. D 11, 3026 (1975).

[41] F. D. M. Haldane, Phys. Rev. Lett. 47, 1840 (1981).

[42] H. J. Schulz, Int. J. Mod. Phys. B 5, 57 (1991).

[43] W. Kohn, Phys. Rev. 133, A171 (1964); X. Zotos, P. Prelovsek, and I. Sega, Phys.
     Rev. B 42, 8445 (1990); B. S. Shastry and B. Sutherland, Phys. Rev. Lett. 65, 243
     (1990).

[44] T. Giamarchi, Phys. Rev. B 44, 2905 (1991).

[45] T. Giamarchi and A. J. Millis, Phys. Rev. B 46, 9325 (1992).

[46] W. Metzner and C. Di Castro, Phys. Rev. B 47, 16107 (1993).

[47] R. Shankar, Int. J. Mod. Phys. B 4, 2371 (1990).

[48] H. J. Schulz, Phys. Rev. Lett. 64, 2831 (1990).

[49] F. D. M. Haldane, Phys. Rev. Lett. 45, 1358 (1980).

[50] J. Voit, Phys. Rev. B 45, 4027 (1992).

[51] Y. Suzumura, Prog. Theor. Phys. 63, 5 (1980).

[52] H. J. Schulz, J. Phys. C 16, 6769 (1983).

[53] J. Voit, J. Phys. CM 5, 8305 (1993).

[54] K. Schönhammer and V. Meden, Phys. Rev. B 47, 16205 (1993) and (E) 48, 11521
     (1993).

[55] A. Theumann, J. Math. Phys. 8, 2460 (1967).

[56] H. Gutfreund and M. Schick, Phys. Rev. 168, 418 (1968).

[57] M. Brech, J. Voit, and H. Büttner, Europhys. Lett. 12, 289 (1990).

[58] V. J. Emery, Phys. Rev. Lett. 37, 107 (1976).

                                            146
[59] J. Voit, Phys. Rev. B 47, 6740 (1993).

[60] V. Meden and K. Schönhammer, Phys. Rev. B 46, 15753 (1992).

[61] H. C. Fogedby, J. Phys. C 9, 3757 (1976).

[62] J. Voit, in the Proceedings of the NATO Advanced Research Workshop on The
     Physics and Mathematical Physics of the Hubbard Model, San Sebastian, October
     3–8, 1993, edited by D. Baeriswyl, D. K. Campbell, J. M. P. Carmelo, F. Guinea,
     and E. Louis; Plenum Press, New York (1995).

[63] K. Schönhammer and V. Meden, Phys. Rev. B 48, 11390 (1993).

[64] J. Voit, Synth. Met. 70, 1015 (1995).

[65] K. Penc and J. Sólyom, Phys. Rev. B 44, 12690 (1991).

[66] C. Di Castro and W. Metzner, Phys. Rev. Lett. 67, 3852 (1991);

[67] D. K. K. Lee and Y. Chen, J. Phys. A 21, 4155 (1988).

[68] D. Schmeltzer, Phys. Rev. B 43, 8650 (1991).

[69] C. Mudry and E. Fradkin, Phys. Rev. B 50, 11409 (1994).

[70] S.-K. Ma, Modern Theory of Critical Phenomena, Benjamin/Cummings Publ.
     Comp., Reading, MA, 1976.

[71] H. W. J. Blöte, J. L. Cardy, and M. P. Nightingale, Phys. Rev. Lett. 56, 742 (1986);
     I. Aﬄeck, ibid. p. 746.

[72] D. Friedan, Z. Qiu, and S. Shenker, Phys. Rev. Lett. 52, 1575 (1984).

[73] J. Cardy, J. Phys. A 17, L385 (1984) and Nucl. Phys. B 270, [FS16], 186 (1986).

[74] A. D. Mironov and A. V. Zabrodin, Phys. Rev. Lett. 66, 534 (1991).

[75] F. D. M. Haldane, Phys. Lett. 81A, 153 (1981).

[76] S.-T. Chui and P. A. Lee, Phys. Rev. Lett. 35, 325 (1975).

[77] J. M. Kosterlitz and D. J. Thouless, J. Phys. C 6, 1181 (1973); J. M. Kosterlitz, J.
     Phys. C 7, 1046 (1974).

[78] J. Voit, J. Phys. C 21, L1141 (1988).

[79] T. Giamarchi and H. J. Schulz, Phys. Rev. B 39, 4620 (1989).

[80] J. L. Black and V. J. Emery, Phys. Rev. B 23, 429 (1981).

[81] H. A. Bethe, Z. Phys. 71, 205 (1931).

                                          147
 [82] J. Hubbard, Proc. Roy. Soc. A 240, 539 (1957); 243, 336 (1958); 276, 238 (163).

 [83] E. H. Lieb and F. Y. Wu, Phys. Rev. Lett. 20, 1445 (1968).

 [84] P. A. Bares and G. Blatter, Phys. Rev. Lett. 64, 2567 (1990).

 [85] B. Sutherland, Phys. Rev. B 12, 3795 (1975).

 [86] P. Schlottmann, Phys. Rev. B 36, 5177 (1987).

 [87] H. Bergknoﬀ and H. B. Thacker, Phys. Rev. D 19, 3666 (1979).

 [88] E. Lieb and W. Liniger, Phys. Rev. 130, 1616 (1963).

 [89] J. Hubbard, Phys. Rev. B 17, 494 (1978).

 [90] H. J. Schulz, Phys. Rev. Lett. 71, 1864 (1993).

 [91] S. Kivelson, W.-P. Su, J. R. Schrieﬀer, and A. J. Heeger, Phys. Rev. Lett. 58, 1899
      (1987).

 [92] A. Painelli and A. Girlando, in Ref. [93].

 [93] Interacting Electrons in Reduced Dimensions, ed. by D. Baeriswyl and D. K. Camp-
      bell, Plenum Press, New York (1989).

 [94] D. K. Campbell, J. T. Gammel, and E. Y. Loh Jr. Phys. Rev. B 42, 475 (1990).

 [95] F. Buzatu, Phys. Rev. B 49, 10176 (1994).

 [96] J. E. Hirsch, Physica C 158, 326 (1989).

 [97] F. C. Zhang and T. M. Rice, Phys. Rev. B 37, 3759 (1988); A. Fortunelli and A.
      Painelli, Sol. State Comm. 89 771 (1994).

 [98] K.-J.-B. Lee and P. Schlottmann, Phys. Rev. Lett. 63, 2299 (1989); P. Schlottmann,
      Phys. Rev. B 43, 3101 (1991).

 [99] F. Gebhard and A. E. Ruckenstein, Phys. Rev. Lett. 68, 244 (1992); F. Gebhard,
      A. Girndt, and A. E. Ruckenstein, Phys. Rev. B 49, 10926 (1994).

[100] P. Nozières, Lecture Notes, Collège de France, Paris, 1991/92.

[101] H. Shiba, Phys. Rev. B 6, 930 (1972).

[102] M. Takahashi, Prog. Theor. Phys. 47, 69 (1972).

[103] T. B. Bahder and F. Woynarovich, Phys. Rev. B 33, 2114 (1986); K. Lee and P.
      Schlottmann, Phys. Rev. B 38, 11566 (1988).

[104] A. A. Ovchinnikov, Sov. Phys. JETP 30, 1160 (1970).

                                           148
[105] C. F. Coll III, Phys. Rev. B 9, 2150 (1974).

[106] F. D. M. Haldane and Yuhai Tu, unpublished.

[107] M. Ogata and H. Shiba, Phys. Rev. B 41, 2326 (1990).

[108] J. Carmelo and D. Baeriswyl, Phys. Rev. B 37, 7541 (1988).

[109] J. E. Hirsch and D. J. Scalapino, Phys. Rev. B 27, 7169 (1983) and 29, 5554 (1984).

[110] S. Mazumdar and A. N. Bloch, Phys. Rev. Lett. 50, 207, (1983); S. Mazumdar, S.
      N. Dixit, and A. N. Bloch, Phys. Rev. B 30, 4842 (1984); S. Mazumdar and S. N.
      Dixit, ibid. 34, 3683 (1986).

[111] K. C. Ung, S. Mazumdar, and D. Toussaint, Phys. Rev. Lett. 73, 2603 (1994).

[112] G. Goméz-Santos, Phys. Rev. Lett. 70, 3780 (1993).

[113] S. Sorella and M. Parinello, in Ref. [93].

[114] S. Sorella, E. Tosatti, S. Baroni, R. Car, and M. Parinello, Int. J. Mod. Phys. B 1,
      993 (1988).

[115] C. Bourbonnais, H. Nélisse, A. Reid, and A.-M. S. Tremblay, Phys. Rev. B 40, 2297
      (1989).

[116] M. Imada and Y. Hatsugai, J. Phys. Soc. Jpn. 58, 3752 (1989).

[117] S. Sorella, A. Parola, M. Parinello, and E. Tosatti, Europhys. Lett. 12, 721 (1990).

[118] T. A. Kaplan, P. Horsch, and J. Borysowicz, Phys. Rev. B 35, 1877 (1987); R. R.
      P. Singh, M. E. Fisher, and R. Shankar, Phys. Rev. B 39, 2562 (1989).

[119] A. Parola and S. Sorella, Phys. Rev. Lett. 64, 1831 (1990).

[120] S. Sorella and A. Parola, J. Phys. CM 4, 3589 (1992).

[121] A. Parola and S. Sorella, Phys. Rev. B 45, 13156 (1992).

[122] Y. Ren and P. W. Anderson, Phys. Rev. B 48, 16662 (1993).

[123] A. G. Izergin, V. E. Korepin, and N. Yu. Reshetikhin, J. Phys. A 22, 2615 (1989);
      F. Woynarovich, ibid., p. 4243; H. Frahm and N.-C. Yu, ibid. 23, 2115 (1990).

[124] H. Frahm and V. E. Korepin, Phys. Rev. B 42, 10553 (1990).

[125] N. Kawakami and S.-K. Yang, Phys. Lett. A 148, 359 (1990).

[126] K. Penc and J. Sólyom, Phys. Rev. B 47, 6273 (1993).

[127] H. Frahm and V. E. Korepin, Phys. Rev. B 43, 5653 (1991).

                                            149
[128] R. Preuss, A. Muramatsu, W. von der Linden, P. Dieterich, F. F. Assaad, and W.
      Hanke, Phys. Rev. Lett. 73, 732 (1994).

[129] N. Kawakami and S.-K. Yang, Phys. Rev. Lett. 65, 2309, (1990) and J. Phys. CM
      3, 5983 (1991).

[130] M. Ogata, M. Luchini, S. Sorella, and F. F. Assaad, Phys. Rev. Lett. 66, 2388
      (1991).

[131] C. S. Hellberg and E. J. Mele, Phys. Rev. B 48, 646 (1993).

[132] C. S. Hellberg and E. J. Mele, Phys. Rev. B 44, 1360 (1991).

[133] C. S. Hellberg and E. J. Mele, Phys. Rev. Lett. 67, 2080 (1991).

[134] M. C. Gutzwiller, Phys. Rev. Lett. 10, 159 (1963).

[135] F. Gebhard and D. Vollhardt, Phys. Rev. Lett. 59, 1472 (1987).

[136] B. Sutherland, Phys. Rev. A 4, 2019 (1971) and 5, 1372 (1972); F. D. M. Haldane,
      Phys. Rev. Lett. 60, 635 (1988); B. S. Shastry, ibid., p. 639.

[137] N. Kawakami and P. Horsch, Phys. Rev. Lett. 68, 3110 (1992).

[138] C. S. Hellberg and E. J. Mele, Phys. Rev. Lett. 68, 3111 (1992).

[139] B. Fourcade and G. Spronken, Phys. Rev. B 29, 5089 and 5096, (1984); J. E. Hirsch,
      Phys. Rev. Lett. 53, 2327 (1984); H. Q. Lin and J. E. Hirsch, Phys. Rev. 33, 8155
      (1986); J. W. Cannon and E. Fradkin, Phys. Rev. B 41, 9435 (1990); J. W. Cannon,
      R. T. Scalettar, and E. Fradkin, Phys. Rev. B 44, 5995 (1991).

[140] A. Luther, Phys. Rev. B 14, 2153 (1976).

[141] A. Luther, Phys. Rev. B 15, 403 (1977).

[142] F. Mila and X. Zotos, Europhys. Lett. 24, 133 (1993).

[143] K. Penc and F. Mila, Phys. Rev. B 49, 9670 (1994).

[144] K. Sano and Y. Ono, J. Phys. Soc. Jpn. 63, 1250 (1994).

[145] K. Kuroki, K. Kusakabe, and H. Aoki, Phys. Rev. B 50, 575 (1994).

[146] N. D. Mermin and H. Wagner, Phys. Rev. Lett. 17, 1133 (1966); P. C. Hohenberg,
      Phys. Rev. 158, 383 (1967).

[147] S. Takada, Prog. Theor. Phys. 54, 1039 (1975).

[148] P. Bak and R. Bruinsma, Phys. Rev. Lett. 49, 249 (1982); G. V. Uimin and V. L.
      Pokrovsky, J. Phys. (Paris) Lett. 44, L865 (1983); L. A. Bol’shov, V. L. Pokrovsky,
      and G. V. Uimin, J. Stat. Phys. 38, 191 (1985).

                                          150
[149] W.-P. Su, J. R. Schrieﬀer, and A. J. Heeger, Phys. Rev. Lett. 42, 1698 (1979) and
      Phys. Rev. B 22, 2099 (1980).

[150] A. J. Heeger, S. Kivelson, J. R. Schrieﬀer, and W.-P. Su, Rev. Mod. Phys. 60, 781
      (1988).

[151] T. Holstein, Ann. Phys. 8, 325 and 343 (1959).

[152] D. Feinberg, S. Chiuchi, and F. de Pasquale, Int. J. Mod. Phys. B 4, 1317 (1990).

[153] J. M. Ginder and A. J. Epstein, Phys. Rev. B 41, 10674 (1990); D. Baranowski, H.
      Büttner, and J. Voit, ibid. 45, 10990 (1992) and 47, 15472 (1993).

[154] J. Voit and H. J. Schulz, Phys. Rev. B 34, 7429 (1986), 36, 968 (1985), and 37,
      10068 (1988); L. G. Caron and C. Bourbonnais, Phys. Rev. B 29, 4230 (1984); C.
      Bourbonnais and L. G. Caron, J. Phys. (Paris) 50, 2751 (1989).

[155] S. Engelsberg and B. B. Varga, Phys. Rev. 136, A1583 (1964); J. Voit and H.
      J. Schulz, Molec. Cryst. Liq. Cryst. 119, 449 (1985). An error in the treament of
      acoustic phonons in this paper has been corrected by Y. Chen, D. K. K. Lee, and
      M. U. Luchini, Phys. Rev. B 38, 8497 (1988).

[156] D. Loss and T. Martin, Phys. Rev. B 50, 12160 (1994).

[157] J. Voit, Phys. Rev. Lett. 64, 323 (1990).

[158] G. T. Zimanyi, S. A. Kivelson, and A. Luther, Phys. Rev. Lett. 60, 2089 (1988).

[159] J. Voit, Synth. Met. 27, A41 (1988).

[160] V. Meden, K. Schönhammer, and O. Gunnarsson, Phys. Rev. B 50, 11179 (1994).

[161] T. Giamarchi and H. J. Schulz, Europhys. Lett. 3, 1287 (1987), and Phys. Rev. B
      37, 325 (1988).

[162] S.-T. Chui and J. W. Bray, Phys. Rev. B 16, 1329 (1977); W. Apel, J. Phys. C 15,
      1973 (1982); Y. Suzumura and H. Fukuyama, J. Phys. Soc. Jpn. 52, 2870 (1983)
      and 53, 3918 (1984).

[163] A. A. Abrikosov and J. A. Ryzhkin, Adv. Phys. 27, 147 (1978).

[164] P. W. Anderson, J. Phys. Chem. Sol. 11, 26 (1959).

[165] H. Fukuyama and P. A. Lee, Phys. Rev. B 17, 535 (1978).

[166] M. Ogata and P. W. Anderson, Phys. Rev. Lett. 70, 3087, (1993).

[167] H. Basista, D. A. Bonn, T. Timusk, J. Voit, D. Jérôme, and K. Bechgaard, Phys.
      Rev. B 42, 4088 (1990).


                                             151
[168] J. M. P. Carmelo and P. Horsch, Phys. Rev. Lett. 68, 871 (1992).

[169] C. L. Kane and M. P. A. Fisher, Phys. Rev. Lett. 68, 1220 (1992), Phys. Rev. B
      46, 7268 and 15233 (1992).

[170] W. Apel and T. M. Rice, Phys. Rev. B 26, 7063 (1982).

[171] A. Furusaki and N. Nagaosa, Phys. Rev. B 47, 4631 (1993).

[172] K. A. Matveev, D. Yue, and L. I. Glazman, Phys. Rev. Lett. 71, 3351 (1993).

[173] A. Furusaki and N. Nagaosa, Phys. Rev. B 47, 3827 (1993).

[174] X. G. Wen, Phys. Rev. Lett. 64, 2206 (1990), Phys. Rev. B 41, 12838 (1990) and
      43, 11025 (1991).

[175] K. Moon, H. Yi, C. L. Kane, S. M. Girvin, and M. P. A. Fisher, Phys. Rev. Lett.
      71, 4381 (1993).

[176] M. Fabrizio, A. O. Gogolin, and S. Scheidl, Phys. Rev. Lett. 72, 2235 (1994).

[177] H. Fukuyama, H. Kohno, and R. Shirasaki, J. Phys. Soc. Jpn. 62, 1109 (1993).

[178] M. Ogata and H. Fukuyama, Phys. Rev. Lett. 73, 468 (1994).

[179] P. A. Lee and T. V. Ramakrishnan, Rev. Mod. Phys. 57, 287 (1985).

[180] N. F. Mott and W. D. Twose, Adv. Phys. 10, 107 (1961).

[181] J. Carmelo and A. A. Ovchinnikov, J. Phys. CM 3, 757 (1991).

[182] J. Carmelo, P. Horsch, P. A. Bares, and A. A. Ovchinnikov, Phys. Rev. B 44, 9967
      (1991).

[183] J. M. P. Carmelo, P. Horsch, and A. A. Ovchinnikov, Phys. Rev. B 45, 7899 and
      46, 14728 (1992).

[184] J. M. P. Carmelo, A. H. Castro Neto, and D. K. Campbell, Phys. Rev. Lett. 73,
      926 and Phys. Rev. B 50, 3667 and 3683 (1994).

[185] H. J. Schulz, in Strongly Correlated Electronic Materials: The Los Alamos Sympo-
      sium 1993, ed. by K. S. Bedell et al., Addison-Wesley, Reading, 1994, p. 187.

[186] A. Luther and V. J. Emery, Phys. Rev. Lett. 33, 589 (1974); P. A. Lee, Phys. Rev.
      Lett. 34, 1247 (1973).

[187] V. J. Emery, A. Luther, and I. Peschel, Phys. Rev. B 13, 1272 (1976).

[188] S. Coleman, Phys. Rev. D 11, 2088 (1975).

[189] M. Fowler and X. Zotos, Phys. Rev. B 24, 2634 (1981).

                                          152
[190] E. K. Sklyanin, L. A. Takhtadzhyan, and L. D. Faddeev, Theor. Mat. Phys. 40, 688
      (1979).

[191] F. D. M. Haldane, J. Phys. A 15, 507 (1982).

[192] T. Giamarchi and H. J. Schulz, Phys. Rev. B 33, 2066 (1986) and J. Phys. (Paris)
      49, 819 (1988).

[193] H. J. Schulz, Phys. Rev. B 22, 5274 (1980).

[194] M. Gulácsi and K. S. Bedell, Phys. Rev. Lett. 72, 2765 (1994).

[195] V. L. Pokrovsky and A. L. Talapov, Phys. Rev. Lett. 42, 65 (1979).

[196] V. J. Emery, Phys. Rev. Lett. 65, 1076 (1990).

[197] C. A. Staﬀord and A. J. Millis, Phys. Rev. B 48, 1409, (1993).

[198] H. Eskes and A. Oleś, Phys. Rev. Lett. 73, 1279 (1994).

[199] P. M. Chaikin, R. L. Greene, S. Etemad, and E. Engler, Phys. Rev. B 13, 1627
      (1976).

[200] E. B. Kolomeisky, Phys. Rev. B 47, 6193 (1993).

[201] J. P. Straley and E. B. Kolomeisky, Phys. Rev. B 48, 1378 (1993).

[202] B. Horovitz, T. Bohr, J. M. Kosterlitz, and H. J. Schulz, Phys. Rev. 28, 6596 (1983).

[203] W. Götze and P. Wölﬂe, Phys. Rev. B 6, 1226 (1972).

[204] T. Giamarchi, Phys. Rev. B 46, 342 (1992).

[205] M. Mori, H. Fukuyama, and M. Imada, J. Phys. Soc. Jpn. 63, 1639 (1994).

[206] H. Pang, S. Liang, and J. F. Annett, Phys. Rev. Lett. 71, 4377 (1993).

[207] E. B. Kolomeisky, Phys. Rev. B 48, 4998 (1993).

[208] M. Ma, Phys. Rev. B 26, 5097 (1982).

[209] P. Horsch and W. Stephan, Phys. Rev. B 48, 10 595, (1993).

[210] W. F. Brinkman and T. M. Rice, Phys. Rev. B 2, 1324 (1970).

[211] K. J. von Szczepanski, P. Horsch, W. Stephan, and M. Ziegler, Phys. Rev. B 41,
      2017 (1990); M. Ziegler and P. Horsch, in Dynamics of Magnetic Fluctuations in
      High-Temperature Superconductors, ed. by G. Reiter and P. Horsch, Plenum Press,
      New York, 1991, p.329.

[212] K. Penc and J. Sólyom, Phys. Rev. B 41, 704 (1990).

                                           153
[213] A. A. Nersesyan, Phys. Lett. A 153, 49 (1991).

[214] G. Montambaux, M. Héritier, and P. Lederer, Phys. Rev. B 33, 7777 (1986).

[215] K. A. Muttalib and V. J. Emery, Phys. Rev. Lett. 57, 1370 (1986).

[216] I. Aﬄeck and J. B. Marston, Phys. Rev. B 37, 3774 (1988); A. B. Harris, T. C.
      Lubensky, and E. J. Mele, Phys. Rev. B 40, 2631 (1989).

[217] C. M. Varma and A. Zawadowski, Phys. Rev. B 32, 7399 (1985).

[218] P. Nozières, Ann. Phys. Fr. 10, 19 (1985).

[219] L. G. Caron and C. Bourbonnais, Europhys. Lett. 11, 473 (1990).

[220] V. J. Emery, Phys. Rev. Lett. 58, 2794 (1987); C. M. Varma, S. Schmitt-Rink, and
      E. Abrahams, Sol. State Comm. 62, 681 (1987).

[221] L. D. Landau and E. M. Lifshitz, Statistical Physics, Pergamon Press, London
      (1959), p. 482.

[222] V. N. Prigodin and Yu. A. Firsov, Sov. Phys. JETP 49, 369 and 813 (1979).

[223] P. W. Anderson, Phys. Rev. Lett. 67, 3844 (1991).

[224] R. A. Klemm and H. Gutfreund, Phys. Rev. B 14, 1086 (1976).

[225] P. A. Lee, T. M. Rice, and R. A. Klemm, Phys. Rev. B 15, 2984, (1977).

[226] L. P. Gor’kov and I. E. Dzyaloshinskiĭ, Sov. Phys. JETP 40, 198 (1975).

[227] W. A. Little, Phys. Rev. 134, A1416 (1964).

[228] S. Baris̆ić, J. Phys. (Paris) 44, 185 (1983); S. Botrić and S. Baris̆ić, ibid. 45, 185
      (1984).

[229] X. G. Wen, Phys. Rev. B 42, 6623 (1990).

[230] F. V. Kusmartsev, A. Luther, and A. Nersesyan, JETP Lett. 55, 724 (1992); V.
      Yakovenko, ibid. 56, 510 (1992).

[231] S. Brazovskiĭ and V. Yakovenko, J. Phys. (Paris) Lett. 46, L-111 (1985); Sov. Phys.
      JETP 62, 1340 (1985); J. Phys. (Paris) 47, 175 (1986).

[232] C. Bourbonnais and L. G. Caron, Europhys. Lett. 5, 209 (1988).

[233] D. G. Clarke, S. P. Strong, and P. W. Anderson, Phys. Rev. Lett. 72, 3218 (1994).

[234] M. Fabrizio and A. Parola, Phys. Rev. Lett. 70, 226 (1993).

[235] M. Fabrizio, Phys. Rev. B 48, 15838 (1993).

                                             154
[236] A. M. Finkel’stein and A. I. Larkin, Phys. Rev. B 47, 10461 (1993).

[237] C. Castellani, D. di Castro, and W. Metzner, Phys. Rev. Lett. 69, 1703 (1992).

[238] M. Fabrizio, A. Parola, and E. Tosatti, Phys. Rev. B 46, 3159 (1992).

[239] R. M. Noack, S. R. White, and D. J. Scalapino, Phys. Rev. Lett. 73, 882 (1994).

[240] Y. Asai, Phys. Rev. B 50, 6519 (1994).

[241] T. M. Rice, S. Gopalan, and M. Sigrist, Europhys. Lett. 23, 445 (1993).

[242] S. P. Strong and A. J. Millis, Phys. Rev. Lett. 69, 2419 (1992); T. Barnes, E.
      Dagotto, J. Riera, and E. S. Swanson, Phys. Rev. B 47, 3196 (1993); S. Gopalan,
      T. M. Rice, and M. Sigrist, Phys. Rev. B 49, 8901 (1994).

[243] D. V. Khveshchenko, Phys. Rev. B 50, 386 (1994).

[244] H. Tsunetsugu, M. Troyer, and T. M. Rice, Phys. Rev. B 49, 16078 (1994).

[245] J. Voit and E. J. Mele, Synth. Met. 43, 3911 (1991).

[246] D. Poilblanc, H. Tsunetsugu, and T. M. Rice, Phys. Rev. B 50, 6511 (1994).

[247] J. A. Riera, Phys. Rev. B 49, 3629 (1994).

[248] D. Boies, C. Bourbonnais, and A.-M. S. Tremblay, Phys. Rev. Lett. 74, 968 (1995).

[249] P. Kopietz, V. Meden, and K. Schönhammer, Phys. Rev. Lett. 74, 2997 (1995).

[250] R. Valentí and C. Gros, Phys. Rev. Lett. 68, 2402 (1992) and (E) 69, 996 (1992);
      C. Gros and R. Valentí, Mod. Phys. Lett. B 7, 119 (1993).

[251] Y. C. Chen and T. K. Lee, Z. Phys. B 95, 5 (1994).

[252] W. O. Putikka, R. L. Glenister, R. R. P. Singh, and H. Tsunetsugu, Phys. Rev.
      Lett. 73, 170 (1994).

[253] Y. C. Chen, A. Moreo, F. Ortolani, E. Dagotto, and T. K. Lee, Phys. Rev. B 50,
      655 (1994); C. Gros and R. Valentí, ibid., p. 11313; T. Tohyama, P. Horsch, and S.
      Maekawa, Phys. Rev. Lett. 74, 980 (1995).

[254] C. Castellani, C. Di Castro, and W. Metzner, Phys. Rev. Lett. 72, 316 (1994).

[255] T. Holstein, R. E. Norton, and P. Pincus, Phys. Rev. B 8, 2649 (1973); M. Yu.
      Reizer, Phys. Rev. B 39, 1602 (1989) and 40 11571 (1989); F. Guinea and G.
      Zimanyi, Phys. Rev. B 47, 501 (1993); P. A. Bares and X.-G. Wen, Phys. Rev. B
      48, 8636 (1993); D. V. Khveshchenko, R. Hlubina, and T. M. Rice, Phys. Rev. B
      48, 10766 (1993); R. Hlubina, Phys. Rev. B 50, 8252 (1994).



                                          155
[256] A. Luther, Phys. Rev. B. 19, 320 (1979); R. Shankar, Physica A 177, 530 (1991)
      and Rev. Mod. Phys. 66, 129 (1994); A. Houghton and J. B. Marston, Phys. Rev.
      B 48, 7790 (1993); A. Houghton, H.-J. Kwon, and J. B. Marston, Phys. Rev. B 50,
      1351 (1994); A. H. Castro Neto and E. Fradkin, Phys. Rev. Lett. 72, 1393 (1994)
      and Phys. Rev. B 49, 10877 (1994).

[257] The Quantum Hall Effect, ed. by R. E. Prange and S. M. Girvin, Springer Verlag,
      New York, 1987.

[258] K. von Klitzing, G. Dorda, and M. Pepper, Phys. Rev. Lett. 45, 494 (1980).

[259] D. C. Tsui, H. L. Sörmer, and A. Gossard, Phys. Rev. Lett. 48, 1559 (1982).

[260] B. I. Halperin, Phys. Rev. B 25, 2185 (1982).

[261] M. Büttiker, Phys. Rev. B 38, 9375 (1988).

[262] For a review, see X.-G. Wen, Int. J. Mod. Phys. B 6, 1711 (1992).

[263] M. Stone, Ann. Phys. (NY) 207, 38 (1991) and Int. J. Mod. Phys. B 5, 509 (1991).

[264] M. D. Johnson and A. H. MacDonald, Phys. Rev. Lett. 67, 2060 (1991).

[265] D. Jérôme and H. J. Schulz, in Extended Linear Chain Compounds, Vol. 2, edited
      by J. S. Miller, Plenum Press, New York (1982).

[266] J. P. Pouget, S. K. Khanna, F. Denoyer, R. Comès, A. F. Garito, and A. J. Heeger,
      Phys. Rev. Lett. 37, 437 (1976).

[267] S. Kagoshima, T. Ishiguro, and H. Anzai, J. Phys. Soc. Japan 41, 2061 (1976).

[268] S. Klotz, J. S. Schilling, M. Weger, and K. Bechgaard, Phys. Rev. B 38, 5878 (1988).

[269] T. Takahashi, D. Jérôme, F. Masin, J. M. Fabre, and L. Giral, J. Phys. C 17, 3777
      (1984).

[270] J. B. Torrance, in Ref. [25].

[271] J. P. Pouget, R. Comès, A. J. Epstein, and J. S. Miller, Molec. Cryst. Liq. Cryst.
      85, 1593 (1982).

[272] J. Skov Pedersen and K. Carneiro, Rep. Prog. Phys. 50, 995 (1987).

[273] S. Tomić, J. R. Cooper, and K. Bechgaard, Phys. Rev. Lett. 62, 462 (1989).

[274] D. Jérôme, A. Mazaud, M. Ribault, and K. Bechgaard, J. Phys. Lett. (Paris) 41,
      L95 (1980).

[275] S. S. P. Parkin, M. Ribault, D. Jérôme, and K. Bechgaard, J. Phys. C 14, 5305
      (1981).

                                           156
[276] L. Forró, J. R. Cooper, B. Rothaemel, J. S. Schilling, M. Weger, and K. Bechgaard,
      Solid State Comm. 60, 11 (1986).

[277] R. Bozio, M. Meneghetti, D. Pedron, and C. Pecile, Synth. Met. 27, B129 (1988).

[278] R. Bozio, M. Meneghetti, and C. Pecile, J. Chem. Phys. 76, 5785 (1982).

[279] M. J. Rice, Phys. Rev. Lett. 37, 36 (1976).

[280] C. Bourbonnais, F. Creuzet, D. Jérome, K. Bechgaard, and A. Moradpour, J. Phys
      (Paris) Lett. 45, L-755 (1984).

[281] P. Wzietek, F. Creuzet, C. Bourbonnais, D. Jérôme, and A. Moradpour, J. Phys.
      (Paris) I 3, 171 (1993).

[282] C. Bourbonnais, in Ref. [25].

[283] C. Bourbonnais, J. Phys. (Paris) I 3, 143 (1993).

[284] L. Ducasse, M. Abderraba, J. Hoarau, M. Pesquer, B. Gallois, and J. Gaultier, J.
      Phys. C 19, 3805 (1986).

[285] G. Soda, D. Jérôme, M. Weger, J. M. Fabre, and L. Giral, Solid State Comm. 18,
      1417 (1976).

[286] G. Soda, D. Jérôme, M. Weger, J. Alizon, J. Gallice, H. Robert, J. M. Fabre, and
      L. Giral, J. Phys. (Paris) 38, 931 (1977).

[287] P. C. Stein, A. Moradpour, and D. Jérôme, J. Phys. Lett. (Paris) 46, 241 (1985).

[288] B. Dardel, D. Malterre, M. Grioni, P. Weibel, Y. Baer, J. Voit, and D. Jérôme,
      Europhys. Lett. 24, 687 (1993).

[289] F. Mila and K. Penc, Synth. Met. 70, 997 (1995).

[290] Electronic Properties of Inorganic Quasi-One-Dimensional Compounds, vol. 1 and
      2, edited by P. Monceau, D. Reidel Publ. Comp., Dordrecht (1985).

[291] P. A. Lee, T. M. Rice, and P. W. Anderson, Phys. Rev. Lett. 31, 462 (1973).

[292] C. Schlenker and J. Dumas, in Crystal Chemistry and Properties of Materials with
      Quasi-One-Dimensional Structures, ed. by J. Rouxel, D. Reidel Publ. Comp., Dor-
      drecht, 1986, p. 135.

[293] B. Dardel, D. Malterre, M. Grioni, P. Weibel, Y. Baer, and F. Lévy, Phys. Rev. Lett.
      67, 3144 (1991); J.-Y. Veuillen, R. C. Cinti, and E. Al Khoury Nemeh, Europhys.
      Lett. 3, 355 (1987).

[294] Y. Hwu, P. Alméras, M. Marsi, H. Berger, F. Lévy, M. Grioni, D. Malterre, and G.
      Margaritondo, Phys. Rev. B 46, 13624 (1992)

                                           157
[295] K. E. Smith, K. Breuer, M. Greenblatt, and W. McCarrol, Phys. Rev. Lett. 70,
      3772 (1993).

[296] L. Degiorgi, G. Grüner, K. Kim, R. H. McKenzie, and P. Wachter, Phys. Rev. B
      49, 14754 (1994).

[297] K. Kim, R. H. McKenzie, and J. W. Wilkins, Phys. Rev. Lett. 71, 4015 (1993).

[298] N. Nakamura, A. Sekiyama, H. Namatame, A. Fujimori, H. Yoshihara, T. Ohtani,
      A. Misu, and M. Takano, Phys. Rev. B 49, 16191 (1994).

[299] U. Meirav, M. A. Kastner, M. Heiblum, and S. J. Wind, Phys. Rev. B 40, 5871
      (1989).

[300] F. P. Milliken, C. P. Umbach, and R. A. Webb, unpublished; also reported by B.
      Gross Levi, Physics Today 47, 21 (1994).




                                        158
List of Figures
Figure 2.1: The Peierls instability: the presence of an interaction component with wave
vector q ≈ 2kF in a 1D electron gas (left) hybridizes the two Fermi points ±kF and,
in a mean-ﬁeld description, opens a gap at the Fermi level (middle). Responsible is the
logarithmic 2kF divergence in the particle-hole bubble (right).

Figure 2.2: Diagrams contributing to the self-energy to second order.

Figure 2.3: The Bethe-Salpeter equation. Γ is the complete particle-hole interaction, I
the irreducible one. Solid lines are Green’s functions.

Figure 3.1: Particle-hole excitations in 1D (left). The spectrum (right) has no low-
frequency excitations with 0 ≤| q |≤ 2kF unlike in higher dimensions where these states
are ﬁlled in.

Figure 3.2: The Luttinger model. Dispersion (left) and forward scattering processes
(right). Solid lines denote electrons propagating with kF and dashed lines those propa-
gating with −kF .

Figure 3.3: Backward (g1⊥ ) and Umklapp (g3⊥ ) scattering not included in the Luttinger
model. Scattering particles have antiparallel spin here.

Figure 3.4: Dyson equation for the density correlation function Rρρ .

Figure 3.5: Dyson equation for the polarization. λρ represents the bare vertex.

Figure 3.6: Luttinger model spectral function ρ+ (q, ω) for q ≥ 0 and α = 0.125. The
ω < 0-part has been multiplied by 10 for clarity.

Figure 3.7: Dynamical charge and spin structure factors of the Luttinger model. S(q, ω)
and S4 (q, ω) are the 2kF - and 4kF -CDW structure factors, and χ(q, ω) is the magnetic
structure factor close to 2kF .

Figure 4.1: Linearized renormalization group ﬂow of g1⊥ and Kσ for the backscattering
                       ⋆
Hamiltonian. The line g1⊥ = 0, Kσ⋆ ≥ 1 is the Luttinger liquid ﬁxed line.

Figure 4.2: Phase diagram of the one-dimensional Fermi liquid oﬀ half-ﬁlling. The
system is a Luttinger liquid at g1⊥ ≥ 0 where Kσ⋆ = 1. Fluctuations indicated in paren-
thesis have the same exponents as the dominant ones but are logarithmically weaker.
At g1⊥ < 0, there is a spin gap, and formally Kσ⋆ = 0. Here, ﬂuctuations appearing in
parenthesis diverge with a smaller power-law exponent than the dominant ones.



                                          159
Figure 4.3: Momentum distribution n(k) of the quarter-ﬁlled Hubbard model in the limit
U/t → ∞ as calculated from the Bethe Ansatz equations (4.32) and (4.33). (Anti)periodic
boundary conditions were used for 4n + 2-(4n-)site lattices, respectively. From ref. [107],
Fig. 3.

Figure 4.4 The correlation exponent Kρ of the Hubbard model as a function of band-
ﬁlling n for diﬀerent values of U (U/t = 1, 2, 4, 8, 16 from top to bottom). From ref. [42],
Fig. 3.

Figure 4.5: The charge and spin velocities vρ (full line) and vσ (dash-dotted lines) of the
Hubbard model as a function of bandﬁlling for diﬀerent U/t. U/t = 1, 2, 4, 8, 16 from top
to bottom for vσ and from bottom to top for vρ in the left part of the Figure. From ref.
[42], Fig. 1. uρ,σ are denoted vρ,σ in our text.

Figure 4.6: Phase diagram of the t−J-model determined from variational wavefunctions.
“Repulsive Luttinger” stands for a Luttinger liquid with dominant SDW correlations, and
“attractive Luttinger” for one with dominant TS. The spin-gap phase has dominant SS.
The dashed line corresponds to Kρ = 1. From ref. [131], Fig. 1.

Figure 4.7: Phase diagram of the extended Hubbard model at quarter-ﬁlling. I is an in-
sulating 4kF -CDW state, M the metallic, repulsive Luttinger liquid and SC an attractive
Luttinger liquid with superconducting correlations. The dashed lines are lines of constant
Kρ . From [142], Fig. 1.

Figure 6.1: Dispersion relations of two hybridized bands and their linearized approxi-
mations. In (a) two particle-like bands hybridize. In (b) a particle-like band hybridizes
with a hole-like band leading to diﬀerent signs of the Fermi velocities on the same side of
the dispersion. From Ref. [212], Figs. 1+2. (a) contains (a) from both Fig. 1 and Fig. 2;
same applies to (b).

Figure 6.2: Cut at ky = 0 through the Brillouin zone of a system of weakly coupled
chains. The shaded area indicates occupied electron states. From Ref. [15], Fig. 1.7.
Their kF0 is denoted by kF1D in our text.

Figure 6.3: Generation of transverse hopping corrections to the propagation of correlated
particle-particle or particle-hole pairs. The thick (thin) lines refer to 3D (1D) propagators
in the high-energy shell eliminated by the renormalization group transformation. Time
arrows and spin indices can be put depending on the (CDW, SDW, SS, TS)-operator un-
der consideration, and the full square then denotes its eﬀective combination of coupling
constants. From Ref. [22], Fig. 9.

Figure 6.4: Phase diagram for the quarter-ﬁlled two-chain Hubbard model from renor-
malization group. The diﬀerent phases are explained in the text. From Ref. [235], Fig. 9.

                                            160
ρ in the inset is denoted by n in our text.

Figure 6.5: Electronic structure for the integer quantum Hall eﬀect on an annulus of
radii r1 and r2 . The shaded areas indicate localized states. From Ref. [260], Fig. 3.

Figure 7.1: Structure of the molecule tetramethyl-tetraselenafulvalene and schematic
stacking pattern of the (T MT SF )2 X-crystals.

Figure 7.2: Real part of the optical conductivity of T T F − T CNQ at 85 K along the
chain axis for two diﬀerent samples (trial 1 and 2). Notice the suppression of conductivity
with respect to a Drude model at low frequency. From Ref. [167], Fig. 6.

Figure 7.3: 77 Se-NMR spin-lattice relaxation rate T1−1 as a function of temperature in
(T MT SF )2 ClO4 . The diﬀerent symbols denote diﬀerent ﬁelds. Shown in the inset is
the theoretical proﬁle for T1−1 for two values of the exponent αSDW . TX1 is the single-
particle crossover temperature, and E0 marks the temperature where the 2kF -SDW be-
comes stronger than the q ≈ 0-ﬂuctuations. From Ref. [280], Fig. 1 (main ﬁgure) and
5(a) (inset). η is αSDW in our text and TX is TX1 .

Figure 7.4: HeII photoemission spectrum of (T MT SF )2 P F6 at T = 50K. The HeI-
spectrum in the insert has a better statistics and clearly shows that there is no spectral
weight near the Fermi surface. From Ref. [288], Figure 1.

Figure 7.5: Tunneling conductance through a constriction in a ν = 1/3 quantum Hall
state as a function of temperature. Diﬀerent curves refer to diﬀerent voltages on the point
contact forming the constriction. The Luttinger liquid prediction is G(T ) ∼ T 4 . From
the preprint of Ref. [300] and Physics Today (p.23).




                                              161
               E(k)                  E(k)




                                                          ~kf
      V(2kf)
                           k                          k
-kf                   kf
                               -kf          kf
                                                 2∆       ~-kf
E(k)                      ω(q)


           ω
       q
               k


                                       q

                   -2kF          2kF
|g1⊥|




        K σ-1
           TMTSF
CH3   Se           Se   CH3




CH3   Se           Se   CH3



                              TMTSF
Σ=         +         +         +         +…
     (a)       (b)       (c)       (d)
                          ε(k)




                                                       g2
          -kf                      kf              k

123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
                                                       g4
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
123456789012345678901234567890121234567890123456
                Ι                 Γ
Γ   =   Ι   +       +…=   Ι   +
                Ι                 Ι
g1⊥   g3⊥
123456789012345678
123456789012345678
123456789012345678
123456789012345678
123456789012345678
123456789012345678
123456789012345678
123456789012345678
                     =            +
123456789012345678
123456789012345678

                         ρ
      Rρρ                Π

                                           + ...
                             ρ         ρ
                         Π       gρ   Π
                G
    =
ρ           ρ   G       ρ
Π       Λ           λ
1000

                                                         α = 0.125

ρ


 500




                       ×10                                                           .005
                                                                              .004

       0                                                               .003
       -.010
                                                                .002
               -.005
                             .000                        .001    q
                                    ω   .005
                                                  .000
                                               .010
       S(q,ω)
       χ(q,ω)
                   (ω -vσq)Kρ-½
                                    |ω -vρq|Kρ




                                           ω

-vρq   -vσq      vσq              vρq


                S4(q,ω)
                                   (ω -vρq)2Kρ-1




                                           ω

-vρq                              vρq
