---
source: "https://arxiv.org/abs/cond-mat/0701105"
type: "arxiv"
canonical_id: "cond-mat/0701105"
title: "Numerical renormalization group method for quantum impurity systems"
authors: "R. Bulla, T. Costi, T. Pruschke"
year: "2007"
venue: "Reviews of Modern Physics"
arxiv_id: "cond-mat/0701105"
doi: "10.1103/RevModPhys.80.395"
full_text: yes
---

# Numerical renormalization group method for quantum impurity systems

**Authors:** R. Bulla, T. Costi, T. Pruschke

**Citation:** Reviews of Modern Physics, vol. 80, pp. 395-450, 2007

**arXiv:** [cond-mat/0701105](https://arxiv.org/abs/cond-mat/0701105)

**DOI:** [10.1103/RevModPhys.80.395](https://doi.org/10.1103/RevModPhys.80.395)

## Abstract

In the early 1970s, Wilson developed the concept of a fully nonperturbative renormalization group transformation. When applied to the Kondo problem, this numerical renormalization group (NRG) method gave for the first time the full crossover from the high-temperature phase of a free spin to the low-temperature phase of a completely screened spin. The NRG method was later generalized to a variety of quantum impurity problems. The purpose of this review is to give a brief introduction to the NRG method, including some guidelines for calculating physical quantities, and to survey the development of the NRG method and its various applications over the last 30 years. These applications include variants of the original Kondo problem such as the non-Fermi-liquid behavior in the two-channel Kondo model, dissipative quantum systems such as the spin-boson model, and lattice systems in the framework of the dynamical mean-field theory.

## Full Text

The numerical renormalization group method for quantum impurity systems
                                                                  Ralf Bulla∗
                                                                  Theoretische Physik III, Elektronische Korrelationen und Magnetismus, Institut für Physik, Universität Augsburg,
                                                                  86135 Augsburg, Germany

                                                                  Theo Costi†
                                                                  Institut für Festkörperforschung, Forschungszentrum Jülich, 52425 Jülich, Germany
arXiv:cond-mat/0701105v1 [cond-mat.str-el] 5 Jan 2007




                                                                  Thomas Pruschke‡
                                                                  Institut für Theoretische Physik, Universität Göttingen, 37077 Göttingen, Germany

                                                                  (Dated: November 26, 2024)

                                                                  In the beginning of the 1970’s, Wilson developed the concept of a fully non-perturbative renor-
                                                                  malization group transformation. Applied to the Kondo problem, this numerical renormalization
                                                                  group method (NRG) gave for the first time the full crossover from the high-temperature phase
                                                                  of a free spin to the low-temperature phase of a completely screened spin. The NRG has been
                                                                  later generalized to a variety of quantum impurity problems. The purpose of this review is to give
                                                                  a brief introduction to the NRG method including some guidelines of how to calculate physical
                                                                  quantities, and to survey the development of the NRG method and its various applications over
                                                                  the last 30 years. These applications include variants of the original Kondo problem such as the
                                                                  non-Fermi liquid behavior in the two-channel Kondo model, dissipative quantum systems such as
                                                                  the spin-boson model, and lattice systems in the framework of the dynamical mean field theory.



                                                        Contents                                                                        1. Multi-orbital Anderson model                  37
                                                                                                                                        2. NRG calculations – an overview                38
                                                          I. Introduction                                                 1             3. Selected results on low-energy properties     39
                                                                                                                                     E. Bosonic degrees of freedom and dissipation       41
                                                         II. Introduction to the Numerical Renormalization
                                                             Group Method                                                 4      V. Application to Lattice Models within DMFT            43
                                                             A. Structure of the Hamiltonian                              6         A. Hubbard model                                     44
                                                             B. Logarithmic discretization                                6            1. Mott metal-insulator transition                44
                                                             C. Mapping on a semi-infinite chain                          8            2. Ordering phenomena                             45
                                                             D. Iterative diagonalization                                 9            3. Multi-band Hubbard models                      46
                                                             E. Renormalization group flow                                11           4. Other generalizations of the Hubbard model     46
                                                                                                                                    B. Periodic Anderson and Kondo lattice models        47
                                                        III. Calculation of Physical Properties                           13        C. Lattice models with phonons                       48
                                                             A. Thermodynamic and static properties                       13
                                                                1. Entropy, specific heat and susceptibility              13    VI. Summary                                              49
                                                                2. Other local properties                                 15
                                                                3. Example: The Kondo model                               15         Acknowledgments                                     50
                                                                4. Improving the accuracy: The Z-averaging                16
                                                             B. Dynamic properties                                        16         References                                          50
                                                                1. Equilibrium dynamics and transport                     16
                                                                2. Self-energy and reduced density matrix approach        19
                                                                3. The x-ray problem and transient dynamics               20
                                                                                                                                I. INTRODUCTION
                                                        IV. Application to Impurity Models                          23
                                                            A. Kondo effect and related phenomena                   23             The last decades saw a steadily increasing interest in a
                                                               1. Screening and photoemission                       23          wide range of physical systems involving quantum impu-
                                                               2. Kondo effect in the bulk and underscreened models 24
                                                               3. Kondo effect in nanostructures                    26
                                                                                                                                rities. The expression ‘quantum impurity system’ is used
                                                            B. Two-channel Kondo physics                            28          in a very general sense here, namely a small system (the
                                                            C. Impurity quantum phase transitions                   31          impurity) with only a few degrees of freedom coupled to
                                                               1. Multi-impurity physics                            31          a large system (the environment or bath) with very many
                                                               2. Local criticality                                 33          degrees of freedom, and where both subsystems have to
                                                               3. Kondo effect in superconductors                   35
                                                                                                                                be treated quantum mechanically.
                                                            D. Orbital effects                                      37
                                                                                                                                   The use of the terminology ‘impurity’ is due to histori-
                                                                                                                                cal reasons. In the Kondo problem, the small system is a
                                                                                                                                magnetic impurity, such as an iron ion, interacting with
                                                        ∗ Electronic address: Ralf.Bulla@Physik.Uni-Augsburg.De                 the conduction electrons of a nonmagnetic metal such as
                                                        † Electronic address: t.costi@fz-juelich.de                             gold (Hewson, 1993). Other realizations are for example
                                                        ‡ Electronic address: pruschke@theorie.physik.uni-goettingen.de         artificial impurities such as quantum dots hosting only
                                                                                                                            2

a small number of electrons. Here, the environment is            intervals [Λ−(n+1) ωc , Λ−n ωc ] and [−Λ−n ωc , −Λ−(n+1) ωc ]
formed by the electrons in the leads. The term ‘quantum          (n = 0, 1, 2, . . .). We shall call Λ > 1 the NRG discretiza-
impurity systems’ can also be used for what are tradi-           tion parameter. After a sequence of transformations, the
tionally called ‘dissipative systems’. As an example, let        discretized model is mapped onto a semi-infinite chain
the impurity correspond to a spin degree of freedom and          with the impurity spin representing the first site of the
the environment be built up by a bosonic bath; this de-          chain. The Kondo model in the semi-infinite chain form
scribes the well-known spin-boson model experimentally           is diagonalized iteratively, starting from the impurity site
relevant, for example, for dissipative two-level systems         and successively adding degrees of freedom to the chain.
like tunneling centers in glasses (Leggett et al., 1987).        Due to the logarithmic discretization, the hopping pa-
   Any theoretical method for the investigation of quan-         rameters between neighboring sites fall off exponentially,
tum impurity systems has to face a number of serious             i.e. going along the chain corresponds to accessing de-
obstacles. First of all, because the environment typically       creasing energy scales in the calculation.
consists of a (quasi-)continuum of quantum-mechanical               In this way, Wilson achieved a non-perturbative de-
degrees of freedom, one has to consider a wide range of          scription of the full crossover from a free impurity spin at
energies – from a high-energy cut-off (which can be of           high temperatures to a screened spin at low temperatures
the order of several eV) down to arbitrarily small excita-       (Wilson, 1975a), thus solving the so-called Kondo prob-
tion energies. On the other hand, because the impurity           lem as discussed in detail in Hewson (1993). After this
degrees of freedom usually form an interacting quantum-          first application more than 30 years ago, the NRG has
mechanical system, their coupling to a continuum of ex-          been successfully generalized and applied to a much wider
citations with arbitrarily small energies can result in in-      range of quantum impurity problems. The first exten-
frared divergencies in perturbational treatments. A well-        sion was the investigation of the single-impurity Ander-
known example for this difficulty is the Kondo problem:          son model (Anderson, 1961), which extends the Kondo
Its physics is governed by an energy scale, the Kondo            model by including charge fluctuations at the impurity
temperature TK , which depends non-analytically on the           site. Krishna-murthy et al. (1980a,b) described all the
spin-exchange coupling J between the impurity and the            technical details, the analysis of fixed points, and the
conduction band of the host, ln TK ∝ 1/J (see Hewson             calculation of static quantities for this model.
(1993) for a detailed description of the limitations of the         In the following, the development of the NRG con-
perturbational approach for the Kondo model and the              centrated on the analysis of more complicated impurity
single-impurity Anderson model). One is thus faced with          models, involving either more environment or impurity
the task to perform non-perturbative calculations for an         degrees of freedom. For example, in the two-channel
interacting quantum-mechanical many-body system with             Kondo model the impurity spin couples to two conduc-
a continuum of excitations covering a broad spectrum of          tion bands. This model, which has a non-Fermi liquid
energies.                                                        fixed point with associated non-Fermi liquid properties,
   A very efficient way to treat systems with such a broad       has been first investigated with the NRG by Cragg et al.
and continuous spectrum of energies is the renormaliza-          (1980). The numerical calculations for such a two-
tion group approach. It allows, in general, to go in a cer-      channel model are, however, much more cumbersome
tain sequence of renormalization group steps from high           because the Hilbert space grows by a factor 16 in each
energies, such as the bandwidth, to low energies, such as        step of the iterative diagonalization, instead of the fac-
the Kondo temperature. General introductions of renor-           tor 4 in the single-channel case. Pang and Cox (1991)
malization group concepts have been given in Goldenfeld          and Affleck et al. (1992) later analyzed the stability of
(1992); Ma (1976); Salmhofer (1999) (see also the original       the non-Fermi liquid fixed point with respect to various
papers: Wilson and Kogut (1974) and Wilson (1975b)).             perturbations such as channel anisotropy.
Here we focus on a specific implementation of the renor-            The two-impurity Kondo model as paradigm for
malization group idea: Wilson’s numerical renormaliza-           the competition of local Kondo screening and non-
tion group method (Wilson, 1975a), referred to as ‘NRG’          local magnetic correlations was studied with NRG
in the remainder of the review. This approach is dif-            by Jones and Varma (1987); Jones et al. (1988);
ferent from most renormalization group methods as it is          Sakai and Shimizu (1992a,b); Sakai et al. (1990);
non-perturbative in all system parameters; however, the          Silva et al. (1996). Here, the focus was on the question,
price one has to pay is that the renormalization group           if the two regimes are connected by a quantum-phase
steps have to be performed numerically.                          transition or rather by a smooth crossover. Later on,
   The general strategy of the NRG is the following (more        such studies were extended to the two-channel situation,
details are given in Sec. II). As specific example, let          too (Ingersent et al., 1992).
us consider the Kondo model which describes a mag-                  Originally, the NRG was used to determine thermo-
netic impurity with spin S   ~ coupled to the electrons of       dynamic properties of quantum impurity systems. The
a conduction band, assumed to be non-interacting, via            calculation of dynamic quantities with the NRG started
an interaction of the form J S ~ · ~s, with ~s the spin of the   with the T = 0 absorption and photoemission spectra
electrons at the impurity site. The NRG starts with              of the x-ray Hamiltonian (Oliveira and Wilkins, 1981,
a logarithmic discretization of the conduction band in           1985), followed by the T = 0 single-particle spectral func-
                                                                                                                          3

tion for the orbitally non-degenerate and degenerate An-        leads can give rise to Kondo-like features in the trans-
derson model (Brito and Frota, 1990; Costi and Hewson,          port characteristics, has also led to a resurgence of in-
1990, 1992b; Frota and Oliveira, 1986; Sakai et al.,            terest in quantum impurity systems, both experimen-
1989). The resulting spectral functions are obtained on         tally and theoretically. An important feature of quan-
all energy scales, with a resolution proportional to the        tum dot systems is their flexibility and a number of
frequency as discussed in detail in Sec. III.B. Calculation     different set-ups have been realized so far, and inves-
of finite-temperature spectral functions A(ω, T ) are more      tigated theoretically by various methods including the
problematic since all excitations can, in principle, con-       NRG. Applications of the NRG in this field include the
tribute. Nevertheless, the NRG has been shown to give           standard Kondo effect (Borda et al., 2005; Costi, 2001;
accurate results for A(ω, T ), too, which also allows to cal-   Gerland et al., 2000; Izumida et al., 1998), coupled quan-
culate transport properties (Costi and Hewson, 1992b;           tum dots (Borda et al., 2003; Cornaglia and Grempel,
Costi et al., 1994a; Suzuki et al., 1996). A subsequent         2005b; Galpin et al., 2006b; Hofstetter and Schoeller,
development is the introduction of the concept of the           2002; Hofstetter and Zaránd, 2004), quantum dots in
reduced density matrix, which allows to calculate dy-           a superconductor (Choi et al., 2004a), and quantum
namic quantities in equilibrium in the presence of ex-          dots coupled to ferromagnetic leads (Choi et al., 2004b;
ternal fields (Hofstetter, 2000). The calculation of non-       Martinek et al., 2003).
equilibrium transient dynamics requires a multiple-shell           From this brief overview one can see that the range
NRG procedure (Costi, 1997a) and has been accom-                of applicability of the NRG has widened considerably
plished with the aid of a complete basis set and the re-        since Wilson’s original paper, covering physical phenom-
duced density matrix (Anders and Schiller, 2005). The           ena such as the Mott transition, quantum dot physics, lo-
first applications of this approach show very promis-           cal criticality, dissipative quantum systems, etc. Further
ing results, both for fermionic and bosonic systems             applications are still lying ahead and various optimiza-
(Anders et al., 2006; Anders and Schiller, 2005, 2006).         tions of the technique itself are still being developed – we
Another recent generalization of the NRG approach is to         shall come back to this point in the summary section.
quantum impurities coupled to a bosonic bath (bosonic              This paper is the first review of the NRG approach
NRG, see Bulla et al. (2005); for early related approaches      (since Wilson’s original paper on the Kondo problem)
see Evangelou and Hewson (1982)). The bosonic NRG               which attempts to cover both the technical details and
has already been successfully applied to the sub-Ohmic          all the various applications. In this way, the reader
spin-boson model which shows a line of quantum crit-            should get an overview over the field, learn about the
ical points separating localized and delocalized phases         current status of the individual applications, and (hope-
(Bulla et al., 2003).                                           fully) come up with ideas for further calculations. This
   Additional motivation to further improve the NRG             review can only be a start for a deeper understanding of
method came from the development of the dynam-                  the NRG. The following shorter reviews on selected top-
ical mean-field theory (DMFT) (Georges et al., 1996;            ics are also helpful: section 4 in Hewson (1993) contains
Metzner and Vollhardt, 1989) in which a lattice model           a pedagogical introduction to the NRG as applied to the
of correlated electrons, such as the Hubbard model, is          Kondo problem, Gonzalez-Buxton and Ingersent (1998)
mapped onto a single-impurity Anderson model with               discuss the soft-gap Anderson and Kondo models, Costi
the impurity coupled to a bath whose structure has to           (1999) gives a general overview of the key concepts, in-
be determined self-consistently. This requires the NRG          cluding the application to the anisotropic Kondo model,
to handle impurity models with an arbitrary density of          Bulla et al. (2005) present a detailed introduction to the
states of the conduction electrons and to calculate di-         bosonic NRG, and, finally, the two papers on the first
rectly the impurity self-energy (Bulla et al., 1998). The       calculations for the single-impurity Anderson model by
first applications of the NRG within the DMFT frame-            Krishna-murthy et al. (1980a,b) are still valuable read-
work concentrated on the Mott transition in the Hub-            ing for an overview of the method and the details of the
bard model and accurate results could be obtained for           analysis of fixed points.
both T = 0 (Bulla, 1999; Sakai and Kuramoto, 1994)                 The review is organized as follows: in Sec. II we start
and finite temperatures (Bulla et al., 2001). Within            with an introduction to the basic concepts of the NRG
DMFT, the NRG has been applied to the periodic An-              approach. The single-impurity Anderson model serves
derson model (Pruschke et al., 2000), the Kondo lat-            as an example here, but the strategy applies to quan-
tice model (Costi and Manini, 2002), multi-band Hub-            tum impurity systems quite generally. At the end of this
bard models (Pruschke and Bulla, 2005), the ferromag-           section, we discuss the flow of the many-particle eigenen-
netic Kondo lattice model with interactions in the band         ergies and the appearance of fixed points in this flow.
(Liebsch and Costi, 2006), and to lattice models with a         This analysis already gives important insights into the
coupling to local phonon modes such as the Holstein             physics of a given model, but the calculation of physical
model (Meyer et al., 2002) and the Hubbard-Holstein             quantities needs some extra care, as described in Sec. III.
model (Koller et al., 2004b).                                   This section is divided into Sec. III.A (thermodynamic
   The observation that the coupling between electronic         and static quantities, such as entropy, specific heat and
degrees of freedom in quantum dots and the surrounding          susceptibilities) and Sec. III.B (dynamic quantities, both
                                                                                                                         4

in equilibrium and non-equilibrium).                          the Hubbard model and other lattice models of correlated
   The following two sections deal with the various ap-       electrons this is achieved via the dynamical mean-field
plications of the NRG and we distinguish here between         theory, see Sec. V.
quantum impurity systems (Sec. IV) and lattice mod-              Before we start with the technical details of the NRG
els within DMFT (Sec. V). Section IV covers most of           approach, let us give a brief overview of the general strat-
the work using the NRG which has been published so            egy. For basically all NRG applications, one proceeds as
far. We shall present results for systems which show          follows:
the standard Kondo effect (Sec. IV.A, this also includes
                                                                a) Division of the energy support of the bath spectral
most of the NRG-results on quantum dots), the two-
                                                                   function into a set of logarithmic intervals.
channel Kondo problem (Sec. IV.B), models displaying
impurity quantum phase transitions (Sec. IV.C), quan-           b) Reduction of the continuous spectrum to a discrete
tum impurity systems with orbital degrees of freedom               set of states (logarithmic discretization).
(Sec. IV.D), and, finally, impurities coupled to bosonic
degrees of freedom (Sec. IV.E). The section on lattice           c) Mapping of the discretized model onto a semi-
models within DMFT (Sec. V) covers calculations for the             infinite chain.
Hubbard model (Sec. V.A), the periodic Anderson and             d) Iterative diagonalization of this chain.
Kondo lattice models (Sec. V.B), and lattice models with
coupling to phonons (Sec. V.C).                                  e) Further analysis of the many-particle energies, ma-
   In the summary we shall discuss open problems as well            trix elements, etc., calculated during the iterative
as possible directions for future developments of the NRG           diagonalization. This yields information on fixed
approach.                                                           points, static and dynamic properties of the quan-
   Let us finish the introduction with a few remarks on             tum impurity model.
the selection of the material presented and the references:   Parts a),b) and c) of this strategy are sketched in Fig. 1,
Due to the flexibility of the NRG, the review covers          where we consider a constant bath spectral function
a broad range of physical phenomena, in particular in         within the interval [−1, 1]. The NRG discretization pa-
Secs. IV and V. We shall, however, only give very brief       rameter Λ defines a set of discretization points, ±Λ−n ,
introductions to these phenomena and refer the reader         n = 0, 1, 2, . . ., and a corresponding set of intervals. The
to the references given in the individual subsections, in     continuous spectrum in each of these intervals (Fig. 1a)
particular reviews or seminal books. Furthermore, due to      is approximated by a single state (Fig. 1b). The result-
lack of space, we shall mostly not review the results from    ing discretized model is mapped onto a semi-infinite chain
other theoretical approaches which have been applied to       with the impurity (filled circle) corresponding to the first
quantum impurity systems, such as Bethe ansatz, quan-         site of this chain. Due to the logarithmic discretization,
tum Monte Carlo, resolvent perturbation theory, local-        the hopping matrix elements decrease exponentially with
moment approach, etc, unless these appear crucial for an      distance from the impurity, tn ∝ Λ−n/2 .
understanding of relevant NRG results. Comparisons be-           While the various steps leading to the semi-infinite
tween the results from NRG and these approaches are,          chain are fairly straightforward from a mathematical
in most cases, included in the papers cited here (see also    point of view, the philosophy behind this strategy is prob-
Hewson (1993)). This means that we shall focus, almost        ably not so obvious.
completely, on references which use the NRG.                     Quite generally, a numerical diagonalization of Hamil-
                                                              tonian matrices allows to take into account the various
                                                              impurity-related terms in the Hamiltonian, such as a lo-
II. INTRODUCTION TO THE NUMERICAL                             cal Coulomb repulsion, non-perturbatively. Apparently,
RENORMALIZATION GROUP METHOD                                  the actual implementation of such a numerical diagonal-
                                                              ization scheme requires some sort of discretization of the
   The NRG method can be applied to systems of the            original model, which has a continuum of bath states.
following form: a quantum mechanical impurity with            There are, however, many ways to discretize such a sys-
a small number of degrees of freedom (so that it can          tem, so let us try to explain why the logarithmic dis-
be diagonalized exactly) coupling to a bath of fermions       cretization is the most suitable one here. As it turns out,
or bosons, usually with continuous excitation spectrum.       quantum impurity models are very often characterized
There is no restriction on the structure of the impurity      by energy scales orders of magnitudes smaller than the
part of the Hamiltonian; it might contain, for example,       bare energy scales of the model Hamiltonian. If the ratio
a Coulomb repulsion of arbitrarily large strength. The        of these energy scales is, for example, of the order of 105 ,
bath, however, is required to consist of non-interacting      a linear discretization would require energy intervals of
fermions or bosons, otherwise the various mappings de-        size at most 10−6 to properly resolve the lowest scale in
scribed below cannot be performed.                            the system. Since for a finite system the splitting of ener-
   Whenever we discuss, in this review, models of a differ-   gies is roughly inversely proportional to the system size,
ent kind, such as the Hubbard model, these models will        one would need of the order of 106 sites, which renders
be mapped onto impurity models of the above type. For         an exact diagonalization impossible.
                                                                                                                                         5

                                        ∆(ω)                                  model with a star geometry as in Fig. 1b has been im-
   a)
                                                                              plemented for the spin-boson model (Bulla et al., 2005).
                                                                              For reasons which are not yet completely clear, such a
                                                                              ‘star-NRG’ is only partly successful. Let us just men-
                                                                              tion here that for a fermionic model such as the single-
         −1       −Λ
                      −1
                           −Λ −Λ ... Λ
                             −2   −3        −3   −2
                                                 Λ
                                                      −1
                                                      Λ          1        ω   impurity Anderson model, the iterative diagonalization
                                                                              of the model in the semi-infinite chain form is much more
                                                                              convenient since one site of the chain can be added in
                                                                              each step without violating particle-hole symmetry (for
                                                                              a detailed discussion of this point see Bulla et al. (2005)).
                                                                                 The quantum impurity model in the semi-infinite chain
                                                                              form is solved by iterative diagonalization, which means
                                                                              that in each step of the iterative scheme one site of the
                                        ∆(ω)                                  chain is added to the system and the Hamiltonian matri-
   b)                                                                         ces of the enlarged cluster are diagonalized numerically.
                                                                              As already pointed out, without taking further steps to
                                                                              reduce the size of the Hilbert space this procedure would
                                                                              have to end for chain sizes of ≈ 10. Here the renor-
                                                                          ω   malization group concept enters the procedure through
         −1                                                      1            the dependence of the hopping matrix elements on the
                                                                              chain length, tn ∝ Λ−n/2 . Adding one site to the chain
                                                                              corresponds
                                                                                        √ to decreasing the relevant energy scale by
                                                                              a factor Λ. Furthermore, because the coupling tn to
                                                                              the newly added site falls off exponentially, only states
   c)                                                                         of the shorter chain within a comparatively small energy
                 ε0                    ε1                  ε2        ε3       window will actually contribute to the states of the chain
                                                                              with the additional site. This observation allows to in-
           V               t0                    t1             t2            troduce a very simple truncation scheme: after each step
                                                                              only the lowest lying Ns many-particle states are retained
FIG. 1 Initial steps of the NRG illustrated for the single-                   and used to build up the Hamiltonian matrices of the next
impurity Anderson model in which an impurity (filled circle)                  iteration step, thus keeping the size of the Hilbert space
couples to a continuous conduction band via the hybridization                 fixed as one walks along the chain.
function ∆(ω); a) a logarithmic set of intervals is introduced
through the NRG discretization parameter Λ; b) the contin-                       All these technical steps will be discussed in detail in
uous spectrum within each of these intervals is approximated                  the following. Let us briefly remark on the general set-
by a single state; c) the resulting discretized model is mapped               up of this section. We would of course like to keep this
onto a semi-infinite chain where the impurity couples to the                  section as general as possible, because it should serve
first conduction electron site via the hybridization V ; the pa-              as an introduction to the NRG technique, whose appli-
rameters of the tight-binding model (see Eq. (26)) are εn and                 cation to a variety of problems is then the subject of
tn .                                                                          the remainder of this review. This quest for general-
                                                                              ity is, however, contrasted by the large variety of pos-
                                                                              sible impurity-bath interactions. Instead of presenting
   Apparently, the logarithmic discretization reduces this                    explicit formulae for all possible quantum impurity mod-
problem in that the low-energy resolution now depends                         els, we restrict ourselves to the single-impurity Ander-
exponentially on the number of sites in the discretized                       son model as a specific – and most important – example
model. Of course, the accuracy of such an approach has                        here. The original introductions to the technique for the
to be checked by suitable extrapolations of the discretiza-                   Kondo model (Wilson, 1975a) and the single-impurity
tion parameters, in particular a Λ → 1 extrapolation,                         Anderson model (Krishna-murthy et al., 1980a,b) were
which recovers the original continuum model. Very often                       restricted to a constant bath density of states (or bet-
it turns out that already for Λ of the order of 2 the re-                     ter, a constant hybridization function ∆(ω) as defined
sults are accurate to within a few percent and a Λ → 1                        below). Here, we consider a general frequency dependent
extrapolation indeed reproduces exact results, if these are                   ∆(ω) from the outset. This generalization is essential
available.                                                                    for various applications of the NRG (the soft-gap mod-
   However, this argument in favor of the logarithmic dis-                    els, see Sec. IV.C.2, and lattice models within DMFT,
cretization does neither explain the need for a mapping                       see Sec. V) where the physics is largely determined by
to a chain Hamiltonian as in Fig. 1c, nor how the problem                     the frequency dependence of ∆(ω). If the hybridization
of an exponentially growing Hilbert space with increas-                       function is non-zero for positive frequencies only, the ma-
ing chain length is resolved. As far as the first point is                    nipulations of the bath degrees of freedom equally hold
concerned, an iterative diagonalization for the discretized                   for a bosonic bath, see Bulla et al. (2005).
                                                                                                                           6

   In this section we cover the steps a), b), c) and d)        band operators fulfill the standard fermionic commuta-
of the list given above. Concerning the analysis of the        tion relations: a†εσ , aε′ σ′ + = δ(ε − ε′ )δσσ′ . It has been
data [step e) in the list], we discuss the flow of the many-   shown in Bulla et al. (1997b) that the two functions g(ε)
particle spectra and all related issues here. The calcula-     and h(ε) are related to the hybridization function ∆(ω)
tion of static and dynamic quantities will be described in     via
Sec. III.
                                                                                             dε(ω)
                                                                               ∆(ω) = π            h[ε(ω)]2 ,            (5)
                                                                                              dω
A. Structure of the Hamiltonian
                                                               where ε(ω) is the inverse function to g(ε), g[ε(ω)] = ω.
  The Hamiltonian of a general quantum impurity model          For a given ∆(ω) there are obviously many possibilities
consists of three parts, the impurity Himp , the bath          to divide the ω-dependence between ε(ω) and h(ε(ω)).
Hbath , and the impurity-bath interaction Himp−bath:           This feature will turn out to be useful later.
                                                                 For a constant ∆(ω) = ∆0 within the interval [−1, 1],
            H = Himp + Hbath + Himp−bath .              (1)    Eq. (5) can be fulfilled by choosing ε(ω) = ω (this corre-
                                                               sponds to g(ε) = ε) and h2 (ε) = ∆0 /π.
For the single-impurity Anderson model (SIAM)
(Anderson, 1961) with the Hamiltonian H = HSIAM ,
these three terms are given by:
                                                               B. Logarithmic discretization
                          εf fσ† fσ + U f↑† f↑ f↓† f↓ ,
                       X
             Himp =
                          σ
                                                                  The Hamiltonian in the integral representation Eq. (4)
                                                               is a convenient starting point for the logarithmic dis-
                               εk c†kσ ckσ ,
                        X
             Hbath =                                           cretization of the conduction band. As shown in Fig. 1a,
                          kσ                                   the parameter Λ > 1 defines a set of intervals with dis-
                                                  
                               Vk fσ† ckσ + c†kσ fσ .          cretization points
                        X
        Himp−bath =                                     (2)
                          kσ
                                                                             xn = ±Λ−n , n = 0, 1, 2, . . . .            (6)
                                               (†)
In this Hamiltonian, the fermionic operators ckσ corre-
spond to band states with spin σ and energy εk , and the       The width of the intervals is given by
 (†)
fσ to the impurity states with energy εf . The Coulomb
interaction between two electrons occupying the impu-                             dn = Λ−n (1 − Λ−1 ) .                  (7)
rity site is parametrized by U and both subsystems are
                                                               Within each interval we now introduce a complete set of
coupled via a k-dependent hybridization Vk .
                                                               orthonormal functions
   The influence of the bath on the impurity is completely
determined by the so-called hybridization function ∆(ω):                     1 ±iωn pε
                                                                              √ e         for xn+1 < ±ε < xn
                                                                   ±           dn
                                                                  ψnp (ε) =                                        (8)
                          X                                                  0            outside this interval .
                ∆(ω) = π      Vk2 δ(ω − εk ) .         (3)
                               k
                                                               The index p takes all integer values between −∞ and
Thus, if we are only interested in the impurity contri-        +∞, and the fundamental frequencies for each interval
butions to the physics of the SIAM, we can rewrite the         are given by ωn = 2π/dn . The next step is to expand the
Hamiltonian in a variety of ways, provided the manipula-       conduction electron operators aεσ in this basis, i.e.
tions involved do not change the form of ∆(ω). Without                        Xh                             i
loss of generality, we assume that the support of ∆(ω)                                   +             −
                                                                        aεσ =     anpσ ψnp (ε) + bnpσ ψnp (ε) ,      (9)
completely lies within the interval [−D, D], with D > 0                         np
chosen suitably. Henceforth, we will use D = 1 as energy
unit.                                                          which corresponds to a Fourier expansion in each of the
   One such possible reformulation is given by the follow-     intervals. The inverse transformation reads
ing Hamiltonian:                                                                     Z 1
                                                                                              +    ∗
                        XZ 1                                                anpσ =        dε ψnp (ε) aεσ ,
         H = Himp +             dε g(ε)a†εσ aεσ                                         −1
                                                                                       Z 1
                           σ       −1                                                           −     ∗
                                                                             bnpσ =          dε ψnp (ε) aεσ .           (10)
                 XZ 1                             
                                                                                        −1
             +            dε h(ε) fσ† aεσ + a†εσ fσ .   (4)
                 σ   −1                                                          (†)          (†)
                                                               The operators anpσ and bnpσ defined in this way fulfill
Here we introduced a one-dimensional energy representa-        the usual fermionic commutation relations. The Hamil-
tion for the conduction band with band cut-offs at ener-       tonian Eq. (4) is now expressed in terms of these discrete
gies ±1, a dispersion g(ε) and a hybridization h(ε). The       operators.
                                                                                                                                      7

  In particular, the transformed hybridization term (first                The first term on the right hand side of Eq. (17) is diag-
part only) is                                                             onal in the index p. The discrete set of energies ξn± can
 Z 1                                Z +,n                                 be expressed as (Bulla et al., 1997b)
                           X
              †         †                         +
     dε h(ε)fσ aεσ = fσ        anpσ       dε h(ε)ψnp (ε)                            R ±,n
                                                                                          dε∆(ε)ε
                                                                                                                   
   −1                                                                                                1
                                 np                                           ξn± = R ±,n           = Λ−n (1 + Λ−1 ) ,             (18)
                                      Z −,n                                              dε∆(ε)     2
                                                      −
                            + bnpσ            dε h(ε)ψnp (ε) , (11)
                                                                          where we added the result for a constant ∆(ε) in brack-
where we have defined                                                     ets. The coupling of the conduction band states with
  Z +,n      Z xn       Z −,n      Z −xn+1                                different p, p′ (the second term) recovers the continuum
                                                                          (no approximation has been made so far, Eq. (17) is still
        dε ≡       dε ,       dε ≡         dε .                   (12)
                     xn+1                        −xn
                                                                          exact). For the case of a linear dispersion, g(ε) = ε, the
                                                                          prefactors α±           ′
                                                                                           n (p, p ) are the same for both sides of the
For a constant h(ε) = h, the integrals in Eq. (11) filter                 discretization and take the following form
out the p = 0 component only
                                                                                              1 − Λ−1 Λ−n           2πi(p′ − p)
                                                                                                                               
             Z ±,n                                                            α±
                                                                               n (p, p ′
                                                                                         ) =                  exp                 . (19)
                                                                                                 2πi p′ − p          1 − Λ−1
                                p
                        ±
                   dε hψnp (ε) = dn hδp,0 .         (13)
                                                                          The actual discretization of the Hamiltonian is now
In other words, the impurity couples only to the p = 0                    achieved by dropping the terms with p 6= 0 in the expres-
components of the conduction band states. It will be-                     sion for the conduction band Eq. (17). This is, of course,
come clear soon, that this point was essential in Wilson’s                an approximation, the quality of which is not clear from
original line of arguments, so we would like to main-                     the outset. To motivate this step we can argue that (i)
tain this feature (h(ε) being constant in each interval                   the p 6= 0 states couple only indirectly to the impurity
of the logarithmic discretization) also for a general, non-               (via their coupling to the p = 0 states in Eq. (17)) and
constant ∆(ω). Note that this restriction for the func-                   (ii) the coupling between the p = 0 and p 6= 0 states has a
tion h(ε) does not lead to additional approximations for                  prefactor (1 − Λ−1 ) which vanishes in the limit Λ → 1. In
a non-constant ∆(ω) as one can shift all the remaining                    this sense one can view the couplings to the states with
ε-dependence to the dispersion g(ε), see Eq. (5).                         p 6= 0 as small parameters and consider the restriction to
   As discussed in Chen and Jayaprakash (1995a)                           p = 0 as zeroth order step in a perturbation expansion
in the context of the soft-gap model (see also                            with respect to the coefficients a±        ′
                                                                                                              n (p, p ) (Wilson, 1975a).
Chen and Jayaprakash (1995b)), one can even set                           As it turns out, the accuracy of the results obtained from
h(ε) = h for all ε. Here we follow the proposal of                        the p = 0 states only is surprisingly good even for values
Bulla et al. (1997b), that is we introduce a step function                of Λ as large as Λ = 2, so that in all NRG calculations
for h(ε)                                                                  the p 6= 0 states have never been considered so far.
                                                                             Finally, after dropping the p 6= 0 terms and relabel-
                  h(ε) = h±
                          n , xn+1 < ±ε < xn ,                    (14)
                                                                          ing the operators an0σ ≡ anσ , etc., we arrive at the dis-
with h±                                                                   cretized Hamiltonian as depicted by Fig. 1b
      n given by the average of the hybridization func-
tion ∆(ω) within the respective intervals,                                                       X
                                                                                                      ξn+ a†nσ anσ + ξn− b†nσ bnσ
                                                                                                                                  
                                                                                  H = Himp +
                        Z ±,n
                 2    1           1                                                               nσ
              h±
               n   =          dε ∆(ε) .            (15)                                 1 X †X +
                     dn           π                                                  + √     f    γn anσ + γn− bnσ
                                                                                                                   
                                                                                         π σ σ n
This leads to the following form of the hybridization term                                   "                    #
                                                                                        1 X X + †          − †
                                                                                                                 
   Z 1
                          1    X                                                    + √         γn anσ + γn bnσ fσ .              (20)
       dε h(ε)fσ† aεσ = √ fσ†         γn+ an0σ + γn− bn0σ ,                              π σ
                                                           
                                                                                               n
    −1                     π     n
                                                             (16)         Before we continue with the mapping of the Hamiltonian
         2   R ±,n
with γn± =         dε ∆(ε).                                               Eq. (20) onto a semi-infinite chain, Fig. 1c, let us make a
  Next, we turn to the conduction electron term, which                    few remarks on alternative discretizations of the contin-
transforms into                                                           uous bath spectral function.
   Z 1                                                                       The above procedure obviously applies for general
                                                                          asymmetric ∆(ω), also for different upper and lower cut-
                          X                                   
        dε g(ε)a†εσ aεσ =      ξn+ a†npσ anpσ + ξn− b†npσ bnpσ
     −1                        np
                                                                          offs, Du and Dl . A special case is Dl = 0, which occurs
         X                                                              for a bosonic bath, see Bulla et al. (2005); here the log-
   +              α+      ′ †              −      ′ †
                   n (p, p )anpσ anp′ σ − αn (p, p )bnpσ bnp′ σ       .   arithmic discretization is performed for positive frequen-
        n,p6=p′                                                                                         (†)
                                                                          cies only, and the operators bnσ in Eq. (20) are no longer
                                                                  (17)    present.
                                                                                                                                8

   In Sec. III we shall discuss that the discreteness of         (similarly for the hermitian conjugate term). Note that
the model Eq. (20) can be (in some cases) problematic            for a k-independent hybridization,
                                                                                                  p Vk = V in Eq. (2), the
for the calculation of physical quantities. As it is not         coupling in Eq. (25) reduces to ξ0 /π = V .
possible in the actual calculations to recover the contin-                           (†)
                                                                    The operators c0σ represent the first site of the con-
uum by taking the limit Λ → 1 (or by including the               duction electron part of the semi-infinite chain. These
p 6= 0 terms), it has been suggested to average over vari-       operators are of course not orthogonal to the operators
ous discretizations for fixed Λ (Frota and Oliveira, 1986;        (†)   (†)
                                                                 anσ , bnσ . Constructing a new set of mutually orthog-
Oliveira and Oliveira, 1994; Yoshida et al., 1990). The                            (†)       (†)        (†)    (†)
discretization points are then modified as                       onal operators cnσ from c0σ and anσ , bnσ by a stan-
                                                                 dard Gram-Schmidt procedure leads to the desired chain
                                                                 Hamiltonian, which takes the form
                     
                       1          : n=0
               xn =       −(n+Z)                      (21)
                       Λ          : n≥1,
                                                                                    r
                                                                                       ξ0 X h †               i
                                                                      H = Himp +             fσ c0σ + c†0σ fσ
                                                                                       π σ
where Z covers the interval [0, 1). This ‘Z-trick’ is, in-
                                                                        ∞ h
deed, successful as it removes certain artificial oscillations                                                          i
                                                                                εn c†nσ cnσ + tn c†nσ cn+1σ + c†n+1σ cnσ
                                                                        X
(see Sec. III.A.4), but it should be stressed here that the         +                                                       ,
continuum limit introduced by integrating over Z is not                 σn=0

the same as the true continuum limit Λ → 1.                                                                                 (26)
  Another shortcoming of the discretized model is that                                   (†)
                                                                 with the operators cnσ corresponding to the nth site of
the hybridization function ∆(ω) is systematically under-
                                                                 the conduction electron part of the chain. The parame-
estimated. It is therefore convenient to multiply ∆(ω)
                                                                 ters of the chain are the on-site energies εn and the hop-
with the correction factor                                                                                   (†)
                                                                 ping matrix elements tn . The operators cnσ in Eq. (26)
                           1      Λ+1                                                   (†) (†)
                   AΛ =      ln Λ     ,                  (22)    and the operators {anσ , bnσ } in Eq. (20) are related via
                           2      Λ−1                            an orthogonal transformation
                                                                               ∞                           ∞
which accelerates the convergence to the continuum limit.                      X                           X
                                                                      anσ =          umn cmσ , bnσ =            vmn cmσ ,
For a recent derivation of this correction factor see
                                                                               m=0                        m=0
Campo, Jr. and Oliveira (2005), where it was also shown                                      ∞
that by a suitable modification of the discretization pro-
                                                                                             X
                                                                                     cnσ =         [unm amσ + vnm bmσ ] .   (27)
cedure, the factor AΛ can be taken into account from the                                     m=0
outset.
                                                                 From the definition of c0σ in Eq. (23) we can read off the
                                                                 coefficients u0m and u0m
C. Mapping on a semi-infinite chain                                                    γ+         γ−
                                                                                 u0m = √m , v0m = √m .                      (28)
                                                                                        ξ0         ξ0
   According to Fig. 1b and c, the next step is to trans-        For the remaining coefficients unm , vnm , as well as for
form the discretized Hamiltonian Eq. (20) into a semi-           the parameters εn , tn , one can derive recursion relations
infinite chain form with the first site of the chain (filled     following the scheme described in detail in, for example,
circle in Fig. 1c) representing the impurity degrees of          Appendix A of Bulla et al. (2005). The starting point
freedom. In the chain Hamiltonian, the impurity directly         here is the equivalence of the free conduction electron
couples only to one conduction electron degree of freedom        parts
                 (†)
with operators c0σ , the form of which can be directly read                X
                                                                                ξn+ a†nσ anσ + ξn− b†nσ bnσ =
                                                                                                           
off from the second and third line in Eq. (20). With the
definition                                                                 nσ
                                                                     ∞ h                                       i
                                                                        εn c†nσ cnσ + tn c†nσ cn+1σ + c†n+1σ cnσ .
                                                                     X
                    1 X +                                                                                                  (29)
                         γn anσ + γn− bnσ ,
                                         
             c0σ = √                                     (23)
                    ξ0 n                                            σn=0

                                                                 The recursion relations are initialized by the equations
in which the normalization constant is given by
                                                                          1 1
                                                                             Z
                                                                   ε0 =          dε∆(ε)ε ,
             X                         Z 1                                ξ0 −1
                 (γn+ )2 + (γn− )2 =
                                  
      ξ0 =                                   dε∆(ε) ,    (24)             1 X +
                                                                   t20 =          (ξm − ε0 )2 (γm
                                                                                                + 2      −
                                                                                                           − ε0 )2 (γm
                                                                                                                     − 2
                                                                                                                         
             n                          −1                                                        ) + (ξm              ) ,
                                                                          ξ0 m
the hybridization term can be written as                                1 +
                                                                  u1m =   (ξ − ε0 )u0m ,
                                   r                                    t0 m
      1 †X +              −
                                    ξ0 †                               1 −
     √ fσ       γn anσ + γn bnσ =      f c0σ ,           (25)     v1m =   (ξ − ε0 )v0m .                                    (30)
       π    n
                                     π σ                                t0 m
                                                                                                                               9

For n ≥ 1, the recursion relations read                            Equation (26) is a specific one-dimensional representa-
             X                                                  tion of the single-impurity Anderson model Eq. (2) with
                   + 2       − 2
                                   
      εn =        ξm unm + ξm  vnm ,                            the special feature that the hopping matrix elements tn
               m
              X                                                fall off exponentially. As mentioned above, this represen-
      t2n         + 2 2
                                ) vnm − t2n−1 − ε2n ,
                              − 2 2                             tation is not exact since in the course of its derivation,
                                     
            =   (ξm ) unm + (ξm
               m                                                the p 6= 0 terms have been dropped. We should stress
           1  +                                               here that the dimensionality of the chain Hamiltonian is
 un+1,m =     (ξm − εn )unm − tn−1 un−1,m ,                     not related to that of the original model which describes,
          tn
           1  −                                               for example, an impurity in a three-dimensional host (ap-
 vn+1,m =     (ξm − εn )vnm − tn−1 vn−1,m .             (31)    parently, this only holds for a non-interacting conduction
          tn                                                    band). Nevertheless, the conduction electron sites of the
Note that for a particle-hole symmetric hybridization           chain do have a physical meaning in the original model
function, ∆(ω) = ∆(−ω), the on-site energies εn are zero        as they can be viewed as a sequence of shells centered
for all n.                                                      around the impurity. The first site of the conduction elec-
   For a general hybridization function, the recursion re-      tron chain corresponds to the shell with the maximum of
lations have to be solved numerically. Although these           its wavefunction closest to the impurity (Hewson, 1993;
relations are fairly easy to implement, it turns out that       Wilson, 1975a); this shell is coupled to a shell further
the iterative solution breaks down typically after about        away from the impurity and so on.
20-30 steps. The source of this instability is the wide
range of values for the parameters entering the recursion
                                                         ±      D. Iterative diagonalization
relations (for instance for the discretized energies ξm    ).
In most cases this problem can be overcome by using ar-
bitrary precision routines for the numerical calculations.        The transformations described so far are necessary to
Furthermore, it is helpful to enforce the normalization of      map the problem onto a form (the semi-infinite chain,
the vectors unm and vnm after each step.                        Eq. (26)) for which an iterative renormalization group
   Analytical solutions for the recursion relations have so     (RG) procedure can be defined. This is the point at
far been given only for few special cases. Wilson derived       which, finally, the RG character of the approach enters.
a formula for the tn for a constant density of states of the      The chain Hamiltonian Eq. (26) can be viewed as a
conduction electrons in the Kondo version of the impurity       series of Hamiltonians HN (N = 0, 1, 2, . . .) which ap-
model (Wilson, 1975a); this corresponds to a constant           proaches H in the limit N → ∞.
hybridization function ∆(ω) in the interval [−1, 1]. Here
we have εn = 0 for all n and the expression for the tn                          H = lim Λ−(N −1)/2 HN ,                      (34)
                                                                                          N →∞
reads
                                                                with
               1 + Λ−1 1 − Λ−n−1
                                    
      tn = √               √             Λ−n/2 .        (32)                                      r
           2 1 − Λ−2n−1 1 − Λ−2n−3                                                          ξ0 X  †                
                                                                  HN = Λ   (N −1)/2
                                                                                          Himp +   fσ c0σ + c†0σ fσ
                                                                                            π σ
(Similar expressions have been given for the soft-gap
model, see Bulla et al. (1997b).) In the limit of large           N              N −1                          
                                                                                                       †
                                                                  X              X
                                                                        †                 †
n this reduces to                                               +   εn cnσ cnσ +      tn cnσ cn+1σ + cn+1σ cnσ       .
                                                                  σn=0                  σn=0
                     1
                        1 + Λ−1 Λ−n/2 .
                                
               tn −→                               (33)                                                                      (35)
                     2
The fact that the tn fall off exponentially with the dis-       The factor Λ(N −1)/2 in Eq. (35) (and, consequently, the
tance from the impurity is essential for the following dis-     factor Λ−(N −1)/2 in Eq. (34)) has been chosen to can-
cussion, so let us briefly explain where this n-dependence      cel the N -dependence of tN −1 , the hopping matrix ele-
comes from. Consider the discretized model Eq. (20) with        ment between the last two sites of HN . Such a scaling
a finite number 1 + M/2 (M even) of conduction electron         is useful for the discussion of fixed points, as described
states for both positive and negative energies (the sum         below. For a different n-dependence of tn , as for the
over n then goes from 0 to M/2). This corresponds to            spin-boson model (Bulla et al., 2005), the scaling factor
2 + M degrees of freedom which result in 2 + M sites            has to be changed accordingly. (The n-dependence of εn
of the conduction electron part of the chain after the          is, in most cases, irrelevant for the overall scaling of the
mapping to the chain Hamiltonian. The lowest energies           many-particle spectra.)
                                                       ±
in the discretized model Eq. (20) are the energies ξM/2            Two successive Hamiltonians are related by
which, for a constant hybridization function, are given by                    √
                                                                                                   εN +1 c†N +1σ cN +1σ
                                                                                               X
 ±
ξM/2   = ± 12 Λ−M/2 (1 + Λ−1 ), see Eq. (18). This energy            HN +1 = ΛHN + ΛN/2
shows up in the chain Hamiltonian as the last hopping                                       
                                                                                                    σ
                                                                                                                        
matrix element tM , so we have tM ∼ ξM/2 equivalent to                                    tN c†N σ cN +1σ + c†N +1σ cN σ ,
                                                                                    X
                                                                              N/2
                                                                         +Λ                                                  (36)
Eq. (33).                                                                           σ
                                                                                                                                                               10

                                                                                                ε0                                     εN
and the starting point of the sequence of Hamiltonians is
given by                                                            HN :
                                                                                      V                 t0                    t N−1

                                   ε0 c†0σ c0σ
                                X
                  −1/2
          H0 = Λ         Himp +                                                                 ε0                                     εN
                                      σ
                  r                              
                      ξ0 X  †                                                        V                 t0                    t N−1
              +             fσ c0σ + c†0σ fσ         .       (37)
                      π σ
                                                                    |r,s         :                         |r                                       |s (N+1)
                                                                           N+1                                  N
This Hamiltonian corresponds to a two-site cluster
                                                                                                ε0                                     εN              ε N+1
formed by the impurity and the first conduction electron
site. Note that in the special case of the single-impurity          H N+1:
                                                                                       V                 t0                    t N−1           tN
Anderson model, one can also choose H−1 = Λ−1 Himp
as the starting point (with a proper renaming of param-             FIG. 2 In each step of the iterative diagonalization scheme
eters and operators) since the hybridization term has the                                                  (†)
                                                                    one site of the chain (with operators cN+1 and on-site energy
same structure as the hopping term between the conduc-              εN+1 ) is added to the Hamiltonian HN . A basis |r; siN+1 for
tion electron sites.                                                the resulting Hamiltonian, HN+1 , is formed by the eigenstates
   The recursion relation Eq. (36) can now be understood            of HN , |riN , and a basis of the added site, |s(N + 1)i.
in terms of a renormalization group transformation R:
                       HN +1 = R (HN ) .                     (38)   a)                     b)                       c)                  d)
                                                                                                1/2
                                                                             E N (r)            Λ     E N (r)            E N+1 (r)           after truncation
In a standard RG transformation, the Hamiltonians are
specified by a set of parameters K   ~ and the mapping R
transforms the Hamiltonian H(K)   ~ into another Hamilto-
nian of the same form, H(K ~ ′ ), with a new set of parame-
     ~ ′
ters K . Such a representation does not exist, in general,
for the HN which are obtained in the course of the iter-
ative diagonalization to be described below. Instead, we
characterize HN , and thereby also the RG flow, directly
by the many-particle energies EN (r)
                                                                    0
      HN |riN = EN (r)|riN , r = 1, . . . , Ns ,             (39)
with the eigenstates |riN and Ns the dimension of HN .
This is particularly useful in the crossover regime be-             FIG. 3 (a): Many-particle spectrum EN (r) of the Hamilto-
tween different fixed points, where a description in terms          nian HN with the ground-state energy set to zero. (b): The
of an effective Hamiltonian with certain renormalized pa-           relation between √successive Hamiltonians, Eq. (36), includes
rameters is not possible. Only in the vicinity of the fixed         a scaling factor Λ. (c) Many-particle spectrum EN+1 (r)
points (except for certain quantum critical points) one             of HN+1 , calculated by diagonalizing the Hamiltonian ma-
can go back to an effective Hamiltonian description, as             trix Eq. (41). (d) The same spectrum after truncation where
described below.                                                    only the Ns lowest-lying states are retained; the ground-state
   Our primary aim now is to set up an iterative scheme             energy has again been set to zero.
for the diagonalization of HN , in order to discuss the
flow of the many-particle energies EN (r). Let us assume
that, for a given N , the Hamiltonian HN has already                (see, for example, Eq. (36)) where the operator ŶN +1
been diagonalized, as in Eq. (39). We now construct a               only contains the degrees of freedom of the added site,
basis for HN +1 , as sketched in Fig. 2:                            while X̂N,N +1 mixes these with the ones contained in
              |r; siN +1 = |riN ⊗ |s(N + 1)i .               (40)   HN . Apparently, the structure of the operators X̂ and Ŷ ,
                                                                    as well as the equations for the calculation of their matrix
The states |r; siN +1 are product states consisting of the          elements, depend on the model under consideration.
eigenbasis of HN and a suitable basis |s(N + 1)i for the
added site (the new degree of freedom). From the basis                The following steps are illustrated in Fig. 3: In Fig. 3a
Eq. (40) we construct the Hamiltonian matrix for HN +1 :            we show the many-particle spectrum of HN , that is the
                                                                    sequence of many-particle energies EN (r). Note that,
    HN +1 (rs, r′ s′ ) = N +1 hr; s|HN +1 |r′ ; s′ iN +1 .   (41)   for convenience, the ground-state energy has been set to
                                                                    zero. Figure 3b
                                                                                  √ shows the overall scaling of the energies
For the calculation of these matrix elements it is useful           by the factor Λ, see the first term in Eq. (36).
to decompose HN +1 into three parts
                   √                                                   Diagonalization of the matrix Eq. (41) gives the new
         HN +1 = ΛHN + X̂N,N +1 + ŶN +1 ,           (42)           eigenenergies EN +1 (w) and eigenstates |wiN +1 which are
                                                                                                                         11

related to the basis |r; siN +1 via the unitary matrix U :    all, which of the symmetries of the Hamiltonian should
                        X                                     be used in the iterative diagonalization. In the original
            |wiN +1 =       U (w, rs)|r; siN +1 .     (43)    calculations of Wilson (1975a) and Krishna-murthy et al.
                        rs                                    (1980a,b) the following quantum numbers were used: to-
                                                              tal charge Q (particle number with respect to half-filling),
The set of eigenenergies EN +1 (w) of HN +1 is displayed      total spin S and z-component of the total spin Sz . It has
in Fig. 3c (the label w can now be replaced by r). Ap-
                                                              certainly been essential in the 1970’s to reduce the size
parently, the number of states increases by adding the        of the matrices and hence the computation time as much
new degree of freedom (when no symmetries are taken
                                                              as possible by invoking as many symmetries as possi-
into account, the factor is just the dimension of the basis   ble. This is no longer necessary to such an extent on
|s(N +1)i). The ground-state energy is negative, but will
                                                              the modern computer systems, i.e. one can, at least for
be set to zero in the following step.                         single-band models, drop the total spin S and classify the
   The increasing number of states is, of course, a prob-
                                                              subspaces with the quantum numbers (Q, Sz ) only. This
lem for the numerical diagonalization; the dimension of       simplifies the program considerably as one no longer has
HN +1 grows exponentially with N , even when we con-
                                                              to worry about reduced matrix elements and the corre-
sider symmetries of the model so that the full matrix         sponding Clebsch-Gordan coefficients, see, for example
takes a block-diagonal form with smaller submatrices.
                                                              Krishna-murthy et al. (1980a). As we use this represen-
This problem can be solved by a very simple truncation        tation in Sec. III.A, let us here explicitly state the form
scheme: after diagonalization of the various submatrices
                                                              of |r; siN +1 :
of HN +1 one only keeps the Ns eigenstates with the low-
est many-particle energies. In this way, the dimension          |Q, Sz , r; 1iN +1 = |Q + 1, Sz , riN ,
of the Hilbert space is fixed to Ns and the computation
                                                                |Q, Sz , r; 2iN +1 = c†N +1↑ Q, Sz − 21 , r N ,
time increases linearly with the length of the chain. Suit-                                                             (44)
able values for the parameter Ns depend on the model;           |Q, Sz , r; 3iN +1 = c†N +1↓ Q, Sz + 21 , r N ,
for the single-impurity Anderson model, Ns of the order         |Q, Sz , r; 4iN +1 = c†N +1↑ c†N +1↓ |Q − 1, Sz , riN .
of a few hundred is sufficient to get converged results for
the many-particle spectra, but the accurate calculation       Note that the quantum numbers (Q, Sz ) on both sides
of static and dynamic quantities usually requires larger      of these equations refer to different systems, on the left-
values of Ns . The truncation of the high energy states is    hand side they are for the system including the added
illustrated in Fig. 3d.                                       site, and on the right-hand side without the added site.
   Such an ad-hoc truncation scheme needs further ex-         We do not go into the details of how to set up the Hamil-
planations. First of all, there is no guarantee that this     tonian matrices Eq. (41), as this procedure is described
scheme will work in practical applications and its quality    in great detail in Appendix B in Krishna-murthy et al.
should be checked for each individual application. Impor-     (1980a)).
tant here is the observation that the neglect of the high-       For fermionic baths, the discretization parameter Λ
energy states does not spoil the low-energy spectrum in       and the number of states Ns kept in each iteration are
subsequent iterations – this can be easily seen numeri-       the only parameters which govern the quality of the re-
cally by varying Ns . The influence of the high-energy on     sults of the NRG procedure. As discussed in more detail
the low-energy states is small since the addition of a new    in Sec. IV.E, for the case of a bosonic bath the infinite
site to the chain can be viewed as a perturbation of rel-     dimensional basis |s(N + 1)i for the added bosonic site
ative strength Λ−1/2 < 1. This perturbation is small for      requires an additional parameter Nb , which determines
large values of Λ but for Λ → 1 it is obvious that one has    the dimension of |s(N + 1)i.
to keep more and more states to get reliable results. This
also means that the accuracy of the NRG results is get-
ting worse when Ns is kept fixed and Λ is reduced (vice       E. Renormalization group flow
versa, it is sometimes possible to improve the accuracy
by increasing Λ for fixed Ns ).                                  The result of the iterative diagonalization scheme are
   From this discussion we see that the success of the        the many-particle energies EN (r) with r = 1, . . . , Ns (ap-
truncation scheme is intimately connected to the special      parently, the number of states is less than Ns for the very
structure of the chain Hamiltonian (that is tn ∝ Λ−n/2 )      first steps before the truncation sets in). The index N
which in turn is due to the logarithmic discretization of     goes from 0 to a maximum number of iterations, Nmax ,
the original model. A direct transformation of the single-    which usually has to be chosen such that the system has
impurity Anderson model to a one-dimensional chain re-        approached its low-temperature fixed point.
sults in tn → const (Hewson, 1993), and the above trun-          As illustrated in Fig. 3, the set of many-particle ener-
cation scheme fails. A similar observation is made when       gies cover roughly the same energy range independent of
such a truncation is applied to the one-dimensional Hub-      N , due to the scaling factor Λ(N −1)/2 in Eq. (35). The
bard model, see the brief discussion in Sec. V.               energy of the first excited state of HN is of the order
   Let us now be a bit more specific on how to construct      of Λ(N −1)/2 tN −1 , a constant according to Eq. (33). The
the basis |r; siN +1 . For this we have to decide, first of   energy of the highest excited state kept after truncation
                                                                                                                             12

           4.0                                                      three different fixed points of the RG transformation for
                     Q=0, S=1/2                                     early iteration numbers N < 10, for intermediate values
                     Q=1, S=0                                       of N and for N > 60 (strictly speaking, because we look
           3.0       Q=1, S=1
                                                                    at N odd only, these are fixed points of R2 , not of R).
                                                                    The physics of these fixed points cannot be extracted by
                                                                    just looking at the pattern of the many-particle energies.
   EN(r)




           2.0                                                      This needs some further analysis, in particular the di-
                                                                    rect diagonalization of fixed point Hamiltonians (which
                                                                    usually have a simple structure) and the comparison of
           1.0                                                      their spectrum with the numerical data. An excellent
                                                                    account of this procedure for the symmetric and asym-
                                                                    metric single-impurity Anderson model has been given
           0.0                                                      by Krishna-murthy et al. (1980a,b), and there is no need
                 0      20        40           60           80      to repeat this discussion here. The analysis shows that
                                  N
                                                                    for N ≈ 3 − 9, the system is very close to the free-orbital
FIG. 4 Flow of the lowest-lying many-particle energies of the       fixed point, with the fixed point Hamiltonian given by
single-impurity Anderson model for parameters εf = −0.5 ·           Eq. (26) for U = 0 and V = 0. This fixed point is unsta-
10−3 , U = 10−3 , V = 0.004, and Λ = 2.5. The states are            ble and for N ≈ 11 − 17, we observe a rapid crossover to
labeled by the quantum numbers total charge Q and total             the local-moment fixed point. This fixed point is char-
spin S. See the text for a discussion of the fixed points visible   acterized by a free spin decoupled from the conduction
in this plot.                                                       band. The local-moment fixed point is unstable as well
                                                                    and after a characteristic crossover (see the discussion
                                                                    below) the system approaches the stable strong-coupling
depends on Ns – for typical parameters this energy is
                                                                    fixed point of a screened spin. Note that the terminology
approximately 5-10 times larger as the lowest energy.
                                                                    ‘strong-coupling’ has been introduced originally because
   Multiplied with the scaling factor Λ−(N −1)/2 , see
                                                                    the fixed point Hamiltonian can be obtained from the
Eq. (34), the energies EN (r) are an approximation to
                                                                    limit V → ∞, so ‘coupling’ here refers to the hybridiza-
the many-particle spectrum of the chain Hamiltonian
                                                                    tion, not the Coulomb parameter U .
Eq. (26) within an energy window decreasing exponen-
tially with increasing N . Note, that the energies for                 The NRG does not only allow to match the structure
higher lying excitations obtained for early iterations are          of the numerically calculated fixed points with those of
not altered in later iteration steps due to the truncation          certain fixed point Hamiltonians. One can in addition
procedure. Nevertheless one can view the resulting set              identify the deviations from the fixed points (and thereby
of many-particle energies and states from all NRG iter-             part of the crossover) with appropriate perturbations of
ations N as approximation to the spectrum of the full               the fixed point Hamiltonians. Again, we refer the reader
Hamiltonian and use them to calculate physical proper-              to Krishna-murthy et al. (1980a,b) for a detailed descrip-
ties in the whole energy range, see Sec. III.                       tion of this analysis. The first step is to identify the
   Here we want to focus directly on the many-particle              leading perturbations around the fixed points. The lead-
energies EN (r) and show how one can extract informa-               ing operators can be determined by expressing them in
tion about the physics of a given model by analyzing their          terms of the operators which diagonalize the fixed point
flow, that is the dependence of EN (r) on N .                       Hamiltonian; this tells us directly how these operators
   As a typical example for such an analysis, we show               transform under the RG mapping R2 . One then proceeds
in Fig. 4 the flow of the many-particle energies for the            with the usual classification into relevant, marginal, and
symmetric single-impurity Anderson model, with param-               irrelevant perturbations. The final results of this analysis
eters εf = −0.5 · 10−3 , U = 10−3 , V = 0.004, and                  perfectly agree with the flow diagram of Fig. 4: There is a
Λ = 2.5 (the same parameters as used in Fig. 5 in                   relevant perturbation which drives the system away from
Krishna-murthy et al. (1980a); note that we show here               the free-orbital fixed point, but for the local-moment
a slightly different selection of the lowest-lying states).         fixed point there is only a marginally relevant perturba-
The energies are plotted for odd N only, that is an odd             tion, therefore the system only moves very slowly away
total number of sites (which is N + 2). This is neces-              from this fixed point. Note that this marginal perturba-
sary, because the many-particle spectra show the usual              tion – which is the exchange interaction between the local
even-odd oscillations of a fermionic finite-size system (the        moment and the spin of the first conduction electron site
patterns for even N look different but contain, of course,          – gives rise to the logarithms observed in various physi-
the same physics). The data points are connected by                 cal quantities. Finally, there are only irrelevant operators
lines to visualize the flow. As in Krishna-murthy et al.            which govern the flow to the strong-coupling fixed point.
(1980a), the many-particle energies are labeled by total            These are responsible for the Fermi-liquid properties at
charge Q and total spin S.                                          very low temperatures (Hewson, 1993).
   What is the information one can extract from such a                 Having identified the leading operators for each fixed
flow diagram? First of all we note the appearance of                point, it is possible to calculate physical properties
                                                                                                                           13

close to the fixed points perturbatively. We do not            HN instead of the full Hamiltonian (26).
want to go into the calculational details here, see               Provided we can keep enough states in the truncation
Krishna-murthy et al. (1980a) and also Sec. 4 in Hewson        scheme introduced in Sec. II to ensure convergence of the
(1993). Recently, Hewson et al. (2004) and Hewson              partition function on the scale kB T , it is thus permissible
(2005) developed an alternative approach based on the          to use the truncated Hamiltonian on the level N obtained
renormalized perturbation theory. This approach is             from the iterative diagonalization to calculate physical
much easier to implement, has been used to describe the        properties for the impurity on the temperature or energy
physics close to the strong-coupling fixed point and is,       scale Λ−(N −1)/2 /β̄.
in principle, applicable also on all energy scales and for
non-equilibrium (Hewson et al., 2005).
   Flow diagrams as in Fig. 4 also give information about      A. Thermodynamic and static properties
the relevant energy scales for the crossover between the
fixed points. For example, an estimate of the Kondo tem-       1. Entropy, specific heat and susceptibility
perature TK (the temperature scale which characterizes
the flow to the strong-coupling fixed point) is given by          The simplest physical quantities related to the impu-
TK ≈ ωc Λ−N̄/2 , with N̄ ≈ 55 for the parameters in Fig. 4.    rity degrees of freedom are the impurity contribution to
   The discussion of flow-diagrams as in Fig. 4 concludes      the entropy, Simp , specific heat, Cimp , and magnetic sus-
our introduction to the basics of the NRG approach. An         ceptibility, χimp .
important part is still missing, of course, that is the cal-      The entropy and specific heat are the first derivative
culation of physical quantities from the flow of the many-     of the free energy F = −kB T ln Z and internal energy
particle energies (and from certain additional matrix el-      U = hHi with respect to temperature, i.e.
ements). This is the topic of the following section.                                                 ∂F
   In Sec. IV we will come back to the discussion of flow                                    S=−        ,
                                                                                                     ∂T
diagrams and the structure of fixed points when study-
ing various other quantum impurity systems, in particu-        and
lar the two-channel Kondo model which displays a non-                                               ∂U
Fermi liquid fixed point, see Sec. IV.B, and the soft-gap                                     C=       .
                                                                                                    ∂T
Anderson model which has a quantum critical point sep-
arating the strong-coupling and local-moment phase, see        From a numerical point of view, performing differentia-
Sec. IV.C.2.                                                   tions is something to avoid if possible. For the numerical
                                                               implementation of the NRG another complication arises.
                                                               To avoid an exponential increase of energies, it is neces-
III. CALCULATION OF PHYSICAL PROPERTIES                        sary to subtract the ground state energy at each NRG-
                                                               level N , i.e. one would have to keep track of these sub-
   In the previous section II we discussed the information     tractions. Apparently, a much more convenient approach
that can be gained from the the low-lying energy levels        is to evaluate the derivative analytically, yielding
during the RG flow. Apparently, a lot can already be
learned on this level about the physical properties of the                         S/kB = βhHi + ln Z ,
system. However, an obvious aim of any method is also
                                                               for the entropy and
to calculate thermodynamic quantities like specific heat,
susceptibilities or even dynamical properties.                                 C/kB = β 2 hH 2 i − hHi2 ,
                                                                                                      
   Let us start by reminding the reader that the co-
efficients tn appearing in the transformed Hamiltonian         for the specific heat.
Eq. (26) decay like Λ−n/2 for large n. This aspect can be         The prescription to calculate the impurity contribu-
used in the following way (Krishna-murthy et al., 1980a;       tion to the magnetic susceptibility requires some more
Oliveira and Oliveira, 1994; Wilson, 1975a): Diagonaliz-       thought. The standard definition for the magnetic sus-
ing the Hamiltonian (35) for a given chain length N yields     ceptibility is (we set gµB = 1)
                        (N )
a set of eigenvalues ηl      ∝ ±Λl . Obviously, eigenval-                             Zβ
                 (N )
ues Λ−(N −1)/2 ηl     ≫ kB T, ω will not contribute signif-                 χ(T ) =          hSz [τ ]Sz idτ − βhSz i2 ,   (46)
icantly to the calculation of physical properties anyway.
                                                    (N )                                 0
On the other hand, for those l where Λ−(N −1)/2 ηl       ≪
kB T, ω one can safely approximate ηl
                                         (N )
                                              ≈ 0, which       with
means that for the calculation of impurity properties                                    1  −βH τ H
                                                                                                e Sz e−τ H Sz .
                                                                                                             
these contributions will drop out. With β = (kB T )−1 ,                 hSz [τ ]Sz i =     Tr e
                                                                                         Z
                    βΛ−(N −1)/2 =: β̄                  (45)    However, the evaluation of the latter expectation value
                                                               is equivalent to the calculation of a dynamical correla-
and β̄ chosen properly, it will thus be sufficient to use      tion function. This is in general a much more complex
                                                                                                                                               14

task and will be discussed in detail in the next section.                            obtained from the bare conduction Hamiltonian
Here, we employ a different approach, which in turn is
                                                                                                   N
also closer related to the experimental definition of this                                  (N )
                                                                                                   X h
                                                                                           Hcb =      ǫn c†nσ cnσ +                           (55)
quantity.
                                                                                                   σn=0
   In general, experiments address the susceptibility of                                                                            i
the whole system. Since the total spin commutes with                                                      tn c†nσ cn+1σ + c†n+1σ cnσ    .
the Hamiltonian, the expression (46) simplifies to
                          2                                                           Similarly, for kB TN = Λ−(N −1)/2 /β̄ the specific heat
                                  i − hStot,z i2 ,
                                                
            χtot (T ) = β hStot,z
                                                                                     and magnetic susceptibility are obtained as
in this case. From this, one subtracts the susceptibility                                                              (N )      (N )
of a reference system, i.e. without impurity, leading to                                           Cimp (TN )/kB ≈ Ctot − Ccb ,               (56)
Wilson’s definition (Wilson, 1975a) of the impurity con-
tribution to the susceptibility                                                      and
                                                                                                                     (N )     (N )
                                                          (0)                                         χimp (TN ) ≈ χtot − χcb        .        (57)
                  χimp (T ) = χtot (T ) − χtot (T ) .                         (47)

Since Stot,z is a quantum number used to classify the                                Since the Hamiltonian (55) is a non-interacting sys-
                                                                                                             (N )
states in the calculation, the expectation values in (47)                            tem, these quantities Scb etc. can be expressed via the
can be evaluated straightforwardly.                                                  eigenenergies ηlσ of (55) in standard fashion.
  Similarly, the impurity contributions to the entropy                                  For T → 0 the behavior of Simp (T ) and χimp (T ) given
and specific heat can be calculated as                                               by Eqs. (56) and (57) can be obtained analytically from
                                                                                     the fixed point spectra. We refer the reader interested in
                                                          (0)                        this derivation to Wilson (1975a) and concentrate here
                  Simp (T ) = Stot (T ) − Stot (T ) ,                         (48)
                                                                                     on the actual numerical calculations.
and                                                                                     Another aspect is that the fixed points and the flow
                                                          (0)
                                                                                     to them are different for N even and odd. This in turn
                 Cimp (T ) = Ctot (T ) − Ctot (T ) ,                          (49)   means, that one in principle has to calculate thermody-
         (0)                     (0)
                                                                                     namic properties either for N even or odd only and thus
where Stot (T ) and Ctot (T ) are again entropy and specific                         loose half of the temperature values. One can, however,
heat of a suitable reference system.                                                 use all information by properly averaging odd and even
  Let us discuss the details of the actual calculation for                           steps:
the entropy as specific example. Following the introduc-
tory remarks, we can – for a given temperature kB T –                                   • For a given N , calculate the quantities O(N −1) ,
restrict the Hilbert space to the NRG iteration L fulfill-                                O(N ) and O(N +1) .
ing (45). If we denote the corresponding Hamiltonian by
                                                                                        • Approximate O(TN ) as
H (N ) , we can introduce the quantity
                                                                                                      1 h (N )
               S (N ) /kB := βhH (N ) i(L) + ln Z (N ) ,                      (50)         O(TN ) ≈      O     + O(N −1) +
                                                                                                      2
where, using the notation of Sec. II (see, for example,
Eq. (40)),                                                                                                O(N +1) − O(N −1)              i
                                                                                                                            (TN − TN −1 ) .
                                                                                                           TN +1 − TN −1
                       1     XX
 h. . .i(N ) :=                                e−βEL (Q,Sz ,r) ×                            The first term in the square bracket is the observ-
                  Z (N )     Q,Sz      r                                                    able calulated at step N . The second and third
                                               N hQ, Sz , r| . . . |Q, Sz , riN ,           term are a linear interpolation of the values at N −1
                                                                              (51)          and N + 1 to iteration N .
and
                                 XX                                                     • Continue with N + 1.
                     (N )                           −βEN (Q,Sz ,r)
                 Z          :=                  e                      .      (52)
                                                                                     As a positive side effect, this averaging also improves the
                                 Q,Sz      r
                                                                                     accuracy of the thermodynamic quantities calculated.
The impurity contribution to the entropy for a tempera-                                At this point some remarks about potential numeri-
ture kB TN := Λ−(N −1)/2 /β̄ can then be obtained as                                 cal problems one can encounter should be made. The
                                                                                     arguments given in the introduction to this section rely
                                                                (N )                 on the assumption, that one can keep states with high
          Simp (TN )/kB ≈ S (N ) /kB − Scb /kB .                              (53)
                                                                                     enough energy to ensure (i) the accuracy of the states
Here we introduced the “free entropy”                                                at medium and low energies and (ii) the convergence of
                                                                                     the partition function and expectation values. Depend-
                (N )                       (N )                    (N )
               Scb /kB := βhHcb i(N ) + ln Zcb ,                              (54)   ing on the actual quantity to be calculated, the latter
                                                                                                                                      15

point can in principle lead to problems. As an exam-                    3. Example: The Kondo model
ple, consider hHi and hH 2 i. While for a given energy
cut-off Ecut the contribution β̄Ecut e−β̄Ecut to hHi can                   As example for the method let us present results for
already be small enough to use the sum up to Ecut as                    the Kondo model Eq. (128). Depending on the number of
approximation to hHi, this must not be necessarily true                 bands coupling to the local spin, one observes a conven-
for hH 2 i. Thus,the resulting values for the specific heat,          tional Kondo effect with the formation of a local Fermi
β̄ hH 2 i − hHi2 , can be rather poor although entropy                  liquid or a non-Fermi liquid fixed point with anomalous
and susceptibility come out much more accurate.                         temperature dependencies of specific heat and suscep-
                                                                        tibility as well as a residual entropy S(0) = 21 ln 2 at
                                                                        T = 0 (Cragg et al., 1980; Nozières and Blandin, 1980)
2. Other local properties                                               (this will be discussed in more detail in Secs. IV.A and
                                                                        IV.B). In Fig. 5 we show the entropy Simp (T ), suscepti-
   While entropy, specific heat and impurity suscepti-
bility can be obtained directly from the spectra of the                    2.5
Hamiltonian, other local quantities require the calcula-                                                                 S/ln(2)
tion of the corresponding local matrix elements. As an                       2                                           4TKχimp
example, we want to discuss here the local occupancy
nσ = hfσ† fσ i and double occupancy D = hf↑† f↑ f↓† f↓ i for               1.5                                           TKγimp
the single-impurity Anderson model Eq. (2). Both quan-                                                                   RW
tities are of interest in actual applications. Expectation                   1
values of other local operators can be calculated in a sim-
ilar manner.
   As before, on a given temperature scale kB TN =                         0.5
Λ−(N −1)/2 /β̄, we approximate the expectation values by
                                                                             0
                 1                                                             -6        -4       -2        0        2            4
                                                                             10       10       10         10      10          10
                       XX
                                        −βEN (Q,Sz ,r)
 nσ (TL ) ≈                         e                    ×       (58)
               Z (N ) Q,S       r
                                                                                                       T/TK
                            z

                                                  †
                                    N hQ, Sz , r|fσ fσ |Q, Sz , riN ,
                                                                        FIG. 5 Entropy Simp (T ), susceptibility χimp (T ), Sommerfeld
for the occupancy and a corresponding expression for the                coefficient γimp = Cimp (T )/T , and Wilson ratio RW for the
double occupancy. The matrix elements                                   single-channel Kondo model. The Kondo temperature is de-
                                                                        fined by the Wilson relation χimp (0) = 0.413
                                                                                                                 4TK
                                                                                                                      .
 nσ (Q, Sz , r, r′ ; N ) := N hQ, Sz , r|fσ† fσ |Q, Sz , r′ iN , (59)
                                                                        bility χimp (T ), Sommerfeld coefficient γimp = Cimp (T )/T
at a given step N can be calculated from those of                       and Wilson ratio RW := 4π 2 χimp (T )/(3γimp(T )) as func-
the previous step N − 1 with the help of the basis                      tion of T /TK for the single-channel Kondo model. As
transformation (43) for the step N . The same scheme                    Kondo coupling we choose J = 0.05D, where D is the
works for the matrix elements of the double occupancy                   half-bandwidth of the conduction band, for which we as-
D(Q, Sz , w, w′ ; −1) and the matrix elements of general                sume a density of states ρcb (ǫ) = NFΘ(D − |ǫ|). The
local operators – like fσ† needed in the calculation of the             value of TK is obtained from Wilson’s definition (Wilson,
single-particle Green function (see Sec. III.B).                        1975a) 4TK χimp (0) = 0.413. The calculations are per-
   All we are left to specify are the initial values for                formed with a discretization parameter Λ = 4, keeping
nσ (Q, Sz , w, w′ ; −1) and D(Q, Sz , w, w′ ; −1) on the level          400 states at each NRG step. Although this value of Λ
of the impurity. For the Anderson model Eq. (2) they                    seems to be fairly large, experience tells that for static
are explicitly given as                                                 properties such large values of Λ are still permissible, con-
                                                                        siderably reducing the number of states one has to keep
                     nσ (0, 0, 0, 0; −1) = 0 ,                          in the truncation procedure.
                     nσ (1, σ, 0, 0; −1) = 1 ,                             One nicely sees in Fig. 5 the quenching of the local mo-
                     nσ (2, 0, 0, 0; −1) = 2 ,                          ment by the Kondo effect for temperatures of the order
                                                                        of TK . Also the high-temperature values for the entropy
                      D(0, 0, 0, 0; −1) = 0 ,
                                                                        Simp (T → ∞) = ln 2 and the Wilson ratio RW = 2
                     D(1, σ, 0, 0; −1) = 0 ,                            (Wilson, 1975a) are obtained with high precision.
                      D(2, 0, 0, 0; −1) = 1 .                    (60)      If one adds a second screening channel to the Kondo
                                                                        model, one arrives at the so-called two-channel Kondo
With these prerequisites we are now in the position to do               model. The rather interesting physics of this model will
actual calculations for the thermodynamic properties of                 be discussed in detail in Sec. IV.B. Here we merely want
quantum impurity models using NRG.                                      to demonstrate that NRG calculations for this model are
                                                                                                                                     16


   1.4                                                           from the continuum limit Λ → 1 of interest, and, (ii),
                                                                 introduces oscillations into the thermodynamic expecta-
   1.2                                                           tion values. A way out of this dilemma, proposed by
                                                                 Oliveira and Oliveira (1994), is as follows:
     1
                                                                    • Instead of the discretization Eq. (6) choose
   0.8
                                               S/ln(2)
                                                                              xn = Λ−n+Z , n ≥ 1 , Z ∈ [0, 1) .                   (61)
   0.6                                         TKχimp
                                               TKγimp                  The mapping to a semi-infinite chain is done as
   0.4                                                                 before (see Sec. II.C) with the replacement Λ−n →
                                               RW/(8/3)
   0.2                                                                 Λ−n+Z for n ≥ 1.

     0 -6                                                           • For fixed Z ∈ [0, 1) perform a NRG calculation for
     10       10
                 -4
                       10
                          -2
                                  10
                                    0
                                          10
                                             2
                                                        10
                                                          4
                                                                      a fixed set of temperatures TL = Λ−(L−1)/2 /β̄ as
                               T/TK                                   before.
                                                                    • Average over several calculations for different Z.
FIG. 6 Entropy Simp (T ), susceptibility χimp (T ), Sommerfeld        This averaging is meant to reintroduce the contin-
coefficient γimp = Cimp (T )/T , and Wilson ratio RW for the          uum limit to some extent (Oliveira and Oliveira,
two-channel Kondo model. The value for the Kondo temper-              1994) and also can be shown to remove oscillations
ature is the same as in Fig. 5.                                       introduced by the use of a large Λ ≫ 1.
                                                                 Already for two different values of Z this procedure re-
possible, too; however, the additional bath degrees of           moves spurious oscillations in thermodynamic quanti-
freedom, which lead to Hilbert spaces larger by a fac-           ties and reproduces the exact result with good accu-
tor of four, make calculations more cumbersome and for           racy for Λ as large as Λ = 10. This technique can be
some quantities also less accurate. In Fig. 6 we show            incorporated straightforwardly into the NRG code (for
as before the impurity contributions to the entropy, sus-        applications, see Campo, Jr. and Oliveira (2003, 2004);
ceptibility and Sommerfeld coefficient as well as the Wil-       Costa et al. (1997); Paula et al. (1999); Ramos et al.
son ratio as function of T /TK . The impurity parameters         (2003); Silva et al. (1996)).
are the same as in Fig. 5; for the NRG we again choose
Λ = 4 but keep 8100 states per iteration. The value
of TK is that of the corresponding single-channel model.         B. Dynamic properties
As emphasized before, entropy and susceptibility come
                                                                 1. Equilibrium dynamics and transport
out quite accurately, in particular the residual entropy
S(0) = 12 ln 2 is obtained as well as the logarithmic in-
                                                                   We consider now the application of the NRG to the cal-
crease of χimp (T ) ∝ ln (T /TK ) for T < TK (Affleck et al.,
                                                                 culation of dynamic and transport properties of quantum
1992; Cragg et al., 1980; Pang and Cox, 1991). The spe-
                                                                 impurity models (Costi and Hewson, 1992b; Costi et al.,
cific heat, however, is less accurate, but also shows the
                                                                 1994a; Frota and Oliveira, 1986; Sakai et al., 1989). For
logarithmic increase as expected, although with strong
                                                                 definiteness we shall consider the Anderson impurity
oscillations superimposed. Fitting both quantities with
                                                                 model and illustrate the procedure for the impurity spec-
a logarithmic form, one can recover the correct Wilson
                                                                 tral density Aσ (ω, T ) = − π1 ImGσ (ω, T ), with
ration RW = 8/3 for T → 0. Note, however, that the
latter value is approached only logarithmically.                                      Z +∞
                                                                                                                  ′
                                                                      Gσ (ω, T ) =               d(t − t′ )eiω(t−t ) Gσ (t − t′ ) , (62)
                                                                                        −∞

4. Improving the accuracy: The Z-averaging                           Gσ (t − t′ ) = −iθ(t − t′ )h[fσ (t), fσ† (t′ )]+ i̺ ,        (63)

  For more complex quantum impurity models, like the             with ̺ the density matrix of the system. Suppose, for the
two-channel Kondo model (discussed briefly in the pre-           moment, that we have all the many-body eigenstates, |ri,
vious section and in more detail in Sec. IV.B), or multi-        and eigenvalues, Er , of the Anderson impurity Hamilto-
orbital models, the Hilbert space per NRG step increases         nian, H, exactly. Then the density matrix, ̺(T ), and
more strongly than for single-channel models. Conse-             partition function, Z(T ), of the full system at tempera-
quently, the fraction of states kept in the truncation pro-      ture kB T = 1/β can be written
cedure has to be reduced. As has been pointed out by                                   1 X −βEr
Oliveira and Oliveira (1994), this leads to an exponential                     ̺(T ) =         e |rihr|,                          (64)
                                                                                      Z(T ) r
decrease of accuracy, which can however be compensated
by an increase of the discretization parameter Λ. How-
                                                                                      X
                                                                              Z(T ) =    e−βEr ,                                  (65)
ever, the use of a large Λ, (i), takes one further away                                      r
                                                                                                                                                         17

and the impurity spectral density, Aσ , can be written in
the Lehmann representation as                                                                   B = 100 TK                     pert. RG
                                                                                   0.06                                        pert. RG broadened
                1 X                                                                                                            NRG
 Aσ (ω, T ) =          |Mr,r′ |2 (e−Er /kB T + e−Er′ /kB T )
              Z(T ) ′
                            r,r




                                                                            NF T (ω)
                   ×δ(ω − (Er′ − Er )).                          (66)              0.04


with Mr,r′ = hr|fσ |r′ i the relevant many-body matrix
elements.                                                                          0.02
   Consider first the T = 0 case (T > 0 is described
below), then
                                                                                       0
                          1 X                                                              -4       -2       0    2       4           6             8
     Aσ (ω, T = 0) =              |Mr,0 |2 δ(ω + (Er − E0 ))                                                     ω/Β
                      Z(0) r
         1 X                                                            FIG. 7 The spin-resolved Kondo resonance at high magnetic
     +           |M0,r′ |2 δ(ω − (Er′ − E0 ),            (67)           fields calculated with NRG and perturbative RG. The large
       Z(0) ′
               r                                                        Gaussian broadening used at ω = gµB B = 100TK reduces the
                                                                        height of the sharp peak and overestimates its width, as is
with E0 = 0 the ground state energy. In order to eval-
                                                                        evident on applying the NRG broadening procedure to the
uate this from the information which we actually obtain                 analytic perturbative RG result (Rosch et al., 2003).
from an iterative diagonalization of H, we consider the
impurity spectral densities corresponding to the sequence
of Hamiltonians HN , N = 0, 1, . . ., whose characteristic              natural choice for the width ηN of P is ωN , the character-
scale is ωN = 12 (1 + Λ−1 )Λ−(N −1)/2 ,                                 istic scale for the energy level structure of HN . Two com-
                                    1 X                                 monly used choices for P are the Gaussian, PG , and the
       AN
        σ (ω, T = 0) =
                                             N 2
                                           |Mr,0 | δ(ω + ErN )          Logarithmic Gaussian, PLG , distributions (Bulla et al.,
                                  ZN (0) r
                                                                        2001; Costi et al., 1994a; Sakai et al., 1989):
             1 X      N 2            N
       +            |M0,r ′ | δ(ω − Er ′ ).                      (68)                                                     »        N)
                                                                                                                                          –2
           ZN (0) ′                                                                                              1   −
                                                                                                                              (ω±Er
                     r
                                                                                        PG (ω ± ErN )
                                                                                                                                ηN
                                                                                                             =   √ e                           ,        (72)
                                                                                                               ηN π
Here, ErN and |riN          are the eigenvalues and eigenstates                                                       2
                                                                                                                              »         N)
                                                                                                                                               –2
                                                                                                                                  ln(ω/Er
of HN , i.e.                                                                                                    e−b /4 −
                                                                                       PLG (ω ± ErN )
                                                                                                                                      b
                                                                                                             =     √ e                              ,   (73)
                                                                                                               bErN π
                         HN |riN = ErN |riN ,                    (69)
and,                                                                     For the Gaussian, a width ηN = 0.3ωN − 0.8ωN is typi-
                                                                        cally used (Costi et al., 1994a), whereas, for the logarith-
                          N                 ′
                         Mr,r ′ = N hr|fσ |r iN ,                (70)   mic Gaussian, a typical width parameter b = 0.3 − 0.7
                                                                        is used (Bulla et al., 2001; Sakai et al., 1989). Note that
are the relevant many-body matrix elements, whose cal-                  the logarithmic Gaussian gives little weight to excitations
culation will be outlined below. Since the spectrum of                  below ωN and more weight to the higher energy excita-
HN is truncated, the range of excitations it describes                  tions. Due to the logarithmic discretization, this might
is limited to 0 ≤ ω ≤ K(Λ)ωN , where K(Λ) depends                       appear to be the better choice. In practice, the difference
on both Λ and the actual number of states retained at                   to using a Gaussian is small.
each iteration and is typically 5 − 10 for Λ = 1.5 − 2.0                   In general, spectra for even and odd N differ by a
for Ns = 500 − 1000 retained states. Moreover, excita-                  few % at most as a result of finite-size effects (see also
tions and eigenstates below the characteristic scale ωN of              the discussion of the reduced density matrix approach
HN will only be approximations to the excitations and                   in Sec. III.B.2), so generally either even N or odd N
eigenstates of the infinite system described by H. These                spectra are calculated (as for thermodynamics). It is
excitations and eigenstates are refined in subsequent it-               also possible to combine information from shell N and
erations. Hence, for each N = 1, 2, . . . we can evaluate               N + 2 by an appropriate weighting (Bulla et al., 2001).
the spectral density from AN σ at a frequency ω chosen to               We note also, that since the broadening is proportional to
lie in the window ωN ≤ ω ≤ K(Λ)ωN ,                                     energy, a peak of intrinsic width Γ at frequency Ω0 will
               Aσ (ω, T = 0) ≈ AN                                       be well resolved by the above procedure provided that
                                σ (ω, T = 0).                    (71)
                                                                        Ω0 ≪ Γ, which is the case for the Kondo resonance and
A typical choice, for Λ = 1.5 − 2.0, is ω = 2ωN .                       other low energy resonances. In the opposite case, the
  The above procedure still only yields discrete spectra.               low (logarithmic) resolution at higher frequencies may
For comparison with experiment, smooth spectra are re-                  be insufficient to resolve the intrinsic widths and heights
quired, so we replace the delta functions δ(ω ± ErN ) ap-               of such peaks, although their weights are correctly cap-
pearing in (68) by smooth distributions P (ω ± ErN ). A                 tured. In cases where the width of such high energy
                                                                                                                              18

peaks is due to single-particle effects, e.g. the resonant
level in the empty orbital regime of the Anderson model,
one can use the representation of the spectral density
in terms of the correlation self-energy, as described in
the next section, with the single-particle broadening be-
ing put in explicitly so that essentially the correct peak
widths and heights is obtained. In other cases, when
the width of such peaks is due to correlations, one in-
evitably has some over-broadening. An extreme example
is the spin-resolved Kondo resonance at high magnetic
fields, B ≫ TK , which is sharply peaked at ω = B and
is highly asymmetrical, as shown in Fig. 7. The extent
of the problem is quantified here by comparison with an-
alytic perturbative results with and without the NRG
broadening procedure.
   A procedure for obtaining smooth spectra, which re-          FIG. 8 T = 0 spectral densities for single-particle (solid line),
solves finite frequency peaks without broadening the dis-       magnetic (dashed line) and charge (dot-dashed line) excita-
crete spectra, involves an averaging over many different        tions of the spin degenerate symmetric Anderson model versus
discretizations of the band (the Z-averaging discussed in       energy ω/D for U = 0.6D, D = 1.0 and ∆/π = M = 0.03D
                                                                (Sakai et al., 1989).
the previous section on thermodynamics). We refer the
reader to Yoshida et al. (1990) for details.
   In calculating the impurity spectral density, one re-
                                     N                          be suppressed by Boltzmann factors. This motivates the
quires also the matrix elements Mr,r   ′ at each iteration.
                                                                following approximation: at ω = 2ωn > kB T one can
These are obtained recursively by using the unitary trans-
                                                                calculate Aσ (ω, T ) as in the T = 0 case
formation Eq. (43) yielding
           N
                   X X                                                  Aσ (ωn , T ) ≈ Anσ (ωn , T )
        Mr,r ′ =           UN (r, psN )UN (r′ , p′ s′N )
                                                                             1 X           n 2 −Ern /kB T      n
                  p,sN p′ ,s′N                                          =              |Mr,r ′ | (e       + e−Er′ /kB T )
                                                                          Zn (T ) ′
                             N −1                                                  r,r
                  ×δsN ,s′N Mp,p′ .                     (74)
                                                                        ×δ(ωn − (Ern′ − Ern )).                             (75)
                                    N
Hence, the matrix elements Mr,r       ′ can be evaluated re-

cursively from a knowledge of the eigenstates of all fi-        In the other limit, ω = 2ωn ≤ T , there is no com-
nite size Hamiltonians up to HN starting from the initial       pletely satisfactory procedure. One approach assumes
matrix elements −1 hr|fσ |r′ i−1 of the isolated impurity       that the main contribution to the spectral density for
Himp = εf σ fσ† fσ + U f↑ f↑ f↓† f↓ . Similar considerations
               P                                                ω = 2ωn ≤ T comes from the energy window containing
apply to other local dynamical quantities such as dy-           thermal excitations O(kB T ) (Costi and Hewson, 1992b;
namical spin and charge susceptibilities. Figure 8 shows        Costi et al., 1994a). In this case, the relevant shell, M ,
T = 0 spectral densities for single-particle, magnetic and      is determined by temperature via ωM ≈ β̄kB T , as in the
charge excitations calculated using the above procedure.        evaluation of thermodynamic properties in the previous
These NRG calculations have been shown to satisfy exact         section, so that, for ω = 2ωn ≤ kB T , we use
Fermi liquid relations, such as the Friedel sum rule for the           Aσ (ωn , T ) ≈ AMσ (ωn , T )
single-particle spectral density and the Shiba relation for
                                                                            1      X
                                                                                          M 2 −ErM /kB T      M
the magnetic excitation spectrum, to within a few per-                 =               |Mr,r ′ | (e      + e−Er′ /kB T )
cent irrespective of the interaction strength U/π∆ in the                ZM (T ) ′
                                                                                   r,r
Anderson model or the value of the exchange J in the
                                                                       ×δ(ωn − (ErM′ − ErM )).                              (76)
Kondo model, see Costi et al. (1994a) and Costi (1998)
for a discussion.                                               In practice, this procedure gives a smooth crossover as
   The case of finite temperature dynamics is more com-         ω is lowered below kB T for temperatures comparable to
plicated. Contributions to the spectral density at fre-         the Kondo scale and higher, but becomes less reliable at
quency ω ∼ ωN now arise from excitations between arbi-          ω < kB T ≪ TK .
trary excited states, i.e. ω = Er − E0 = Er′ − Ep′ =               Once the finite-T spectral density is known, one can
Er′′ − Ep′′ = . . . with E0 = 0 < Ep′ < Ep′′ < . . .            also calculate transport properties, since the transport
see Fig. 9. Consequently, the finite-T spectral density         time, τtr , for electrons scattering from a small concentra-
at ω ∼ ωN will have contributions from all energy shells        tion, ni , of magnetic impurities is given in terms of the
n = 1, . . . , N . These need to be summed up, as in the cal-   spectral density by
culation of transient quantities described in Sec. III.B.3.
It is clear, however, that in the case of equilibrium spec-                          1        2ni
                                                                                            =     ∆Aσ (ω, T ),              (77)
tral densities, the contributions from shells n < N will                        τtr (ω, T )   NF
                                                                                                                                                               19

     a)       Er
                N                                              N                                                    1.2
                                            b)             Er
                                                                                                                                       R(T) Kondo Model
     Κω N                                                                                                           1.0                G(T) Kondo Model




                                                                                             R(T)/R(0), G(T)/G(0)
                                                                                                                                       R(T) Anderson Model
                                                                                                                                                          2
                                                                            ...                                     0.8                R(T)/R(0)=1−c(T/TK)
                                                                           ω                                                           Hamann
                                                                   ω
     ωN                                                   ω
                                                                                                                    0.6
                    ω

      0
                                                                                                                    0.4

                                                                                                                    0.2
FIG. 9 Excitations of HN contributing to the spectral func-
tion at frequency ω for, (a), T = 0, and, (b), T > 0.                                                               0.0 −3 −2 −1 0    1 2 3  4  5
                                                                                                                      10 10 10 10 10 10 10 10 10
                                                                                                                                   T/TK
where NF is the conduction electron density of states
and ∆ is the hybridization strength. For example, the                                    FIG. 10 Scaled resistivity and conductance of the S = 1/2
resistivity R(T ) due to Kondo impurities in a clean metal                               Kondo model. Adapted from Costi (2000). For compar-
is given by                                                                              ison the resistivity of the symmetric Anderson model for
                                                                                         U/π∆ = 4 is also shown (Costi and Hewson, 1993) and is
                                            1                                            seen to be identical to that for the Kondo model, up to
            R(T ) =                                                  ,          (78)
                        e2
                             R
                                 dω         ∂f
                                          − ∂ω       τtr (ω, T )                         non-universal corrections arising from charge fluctuations at
                                                                                         higher temperatures (for U/π∆ = 4 these corrections occur
                                                                                         for T > 10TK ).
and the conductance through a quantum dot (or the re-
sistivity of Kondo impurities in a dirty metal) modeled
by an Anderson impurity model is given by                                                where S is the impurity spin and TKH is a Kondo scale
                                                                                       defined by
                   XZ           ∂f
      G(T )/G(0) =      dω −          Aσ (ω, T ) . (79)                                                                   R(T = TKH ) = R(0)/2.               (83)
                    σ
                                ∂ω
                                                                                         Micklitz et al. (2006a) found numerically that TKH ≈
Figure 10 compares the scaled resistivity R(T )/R(0) for                                 0.91TK. We see from Fig. 10 that the NRG result for the
the Kondo and Anderson models with the scaled conduc-                                    resistivity of the Kondo model agrees with the Hamann
tance G(T )/G(0) for the Kondo model. The conductance                                    result for T ≥ TK . The T 2 Fermi liquid behavior at
and resistivity are seen to be almost identical universal                                low-temperature T ≪ TK is also recovered. In contrast,
functions of T /TK. At finite magnetic field, the two quan-                              the Hamann result violates Fermi liquid behavior and
tities deviate from each other in the region T ≈ B (Costi,                               cannot be trusted for T < TK . A numerical determi-
2000). The NRG results can be compared to analytic re-                                   nation of the coefficient c in Eq. (80) requires obtaining
sults at low and high temperature. The resistivity of                                    τtr (ω, T ) accurately up to second order in both ω and T
the Anderson model in the low-temperature Fermi liquid                                   (Costi et al., 1994a). Typical errors for c can be as large
regime is given by the result of Nozières (1974),                                       as 10-30% so there is room for further improvement of
                                                              2                        the finite T dynamics in the Fermi liquid regime T ≪ TK .
                                                          T                              For a discussion of other transport properties of Kondo
  R(T )/R(0) = G(T )/G(0) = 1 − c                                      , T ≪ TK ,
                                                          TK                             systems, such as thermopower and thermal conductiv-
                                                   (80)                                  ity, the reader is referred to Costi and Hewson (1993);
where c = π 4 /16 = 6.088 and TK is the low-temperature                                  Costi et al. (1994a); Zlatić et al. (1993).
Kondo scale defined from the static spin susceptibility
via
                                                                                         2. Self-energy and reduced density matrix approach
               χ(T = 0) = (gµB )2 /4kB TK .                                       (81)
                                                                                            We now describe two improvements to the calculation
At high temperatures, T > TK , Hamann used the                                           of dynamical quantities. The first of these, a direct cal-
Nagaoka-Suhl approximation (Hewson, 1993) to obtain                                      culation of the correlation part of the self-energy of the
for the resistivity of the Kondo model                                                   Anderson impurity model (Bulla et al., 1998), is partic-
                                                                                         ularly important for applications to DMFT, where the
                   1               ln(T /TKH )                                           impurity self-energy plays a central role. The second,
 R(T )/R(0) =        (1 −                                  ),
                   2      (ln(T /TKH )2 + π 2 S(S + 1))1/2                               the introduction of the reduced density matrix into the
                                                          (82)                           calculation of dynamics, is important, for example, in
                                                                                                                                     20

correcting large finite-size errors in spin-resolved spectra
of the Anderson and Kondo models when a magnetic field                           20                                      NRG
                                                                                         20                           DM-NRG
perturbs the ground state (Hofstetter, 2000).
                                                                                         10
   The correlation part of the self-energy for the Anderson                      15
impurity model, Σσ , is defined via                                                       0
                                                                                         -0.003   0       0.003




                                                                         A↑(ω)
                                  1
          Gσ (ω, T ) =                          ,             (84)               10
                       ω − εf + i∆ − Σσ (ω, T )
and can be expressed, via the equation of motion for Gσ                          5
(Bulla et al., 1998), as the ratio of a two-particle and a
one-particle Green function
                                                                                 0
                          †                                                       -0.1            -0.05           0     0.05   0.1
     Σσ (ω, T ) = U hhfσ f−σ f−σ ; fσ† ii/hhfσ ; fσ† ii .     (85)
                                                                                                                  ω
Evaluating the spectral densities of the two Green func-
tions in (85) as in the previous section, and calculating            FIG. 11 Comparison of the spectral function for the Ander-
                                                                     son impurity model calculated in a magnetic field with and
from these, via a Kramers-Kronig transformation, the
                                                                     without the reduced density matrix: ∆ = 0.01, U = 0.1, εf =
corresponding real parts of the Green functions one ob-              −0.05, B = 0.001 from Hofstetter (2000).
tains the self-energy. Using this in (84) one is able to
obtain the impurity spectral density with improved reso-
lution of high-energy peaks, since in this procedure, the            The reduced density matrices ̺n,red are calculated iter-
single-particle broadening ∆ is included exactly. In par-            atively backwards starting from the density matrix of
ticular, this scheme recovers the limit U → 0 exactly.               HNmax . One situation where the reduced density matrix
It is also found to improve the spectral sum rule with               is important is in obtaining correctly the spin-resolved
typical errors as low as 0.1% or less.                               spectral density of the Anderson model in a magnetic
   The evaluation of spectral densities described in the             field (Hofstetter, 2000). A magnetic field comparable
previous section is subject to systematic errors due to              to TK changes the magnetization and therefore the oc-
neglect of high-energy states in constructing HN . These             cupation of up/down states by O(1) so large shifts in
are the same as for thermodynamic properties, and they               spectral weight occur at high energies in the impurity
can be controlled by increasing Λ and the number of re-              spectral density which are only captured correctly by us-
tained states Ns . Another source of error, specific to              ing the reduced density matrix, see Fig. 11. Results for
the method used to calculate dynamics, is that while we              dynamical susceptibilities in a magnetic field using the
chose the frequency ω in evaluating spectra from HN                  reduced density matrix have been discussed by Hewson
carefully so that ω > ωN , nevertheless the eigenstates in           (2006). The reduced density matrix also eliminates to
the range 0 ≤ ErN ≤ ωN , which for small N are only                  a large extent the difference between the spectra calcu-
crude approximations to the eigenstates of H, are also               lated for even/odd N and allows a correct description of
used in the evaluation. They enter the calculation di-               the asymptotics of the Kondo resonance in high magnetic
rectly, as can be seen from Fig. 9, and, also, via the               fields (Rosch et al., 2003).
density matrices (e.g. at T = 0 via ̺N = |0iN N h0|)
which are used to arrive at (68) and (75-76). As a result,
the spectral density is subject to errors for small N , i.e.         3. The x-ray problem and transient dynamics
for high energies, due to the use of low-lying states which
are not converged (Hofstetter, 2000). With increasing N ,
                                                                        We consider here the calculation of the response of a
i.e. lower energies, this error will decrease. An improve-
                                                                     system to a sudden local perturbation, such as the ex-
ment, due to Hofstetter (2000), is to use in place of ̺N
                                                                     citation of an electron from a core-level to the conduc-
the reduced density matrix, ̺N,red , of HN , obtained from
                                                                     tion band of a metal in the x-ray problem, or, the time-
the density matrix of the largest finite size Hamiltonian
                                                                     dependent response of a spin in the spin-boson model fol-
diagonalized, HNmax , i.e.,
                                                                     lowing an initial-state preparation. The NRG approach
              ̺N,red = T rsN +1 ,...,sN         [̺Nmax ]      (86)   to the x-ray problem (Oliveira and Wilkins, 1981) was
                                          max
                                                                     the first application of the method to dynamical quanti-
where sN +1 , . . . , sNmax are the extra degrees of freedom         ties. In common with previous treatments of the x-ray
contained in HNmax but absent in HN . As ̺N,red is not               problem, for a review see (Mahan, 1975), the approach
diagonal in the eigenbasis of HN , the resulting spectral            developed by Oliveira and Wilkins (1981) calculates the
function takes on a more complicated form                            absorption spectrum within linear response theory, and,
                       X                                             therefore, belongs logically to Sec. III.B.1. We include
     ANσ (ω, 0) =
                                   N
                           Cr′ ,r Mr,r           N      N
                                       ′ δ(ω − (Er ′ − Er )) (87)
                                                                     it here for two reasons, (i), because the response of the
                     r ′ ,r
                     X                         X N,red               electrons to the appearance of the core-hole potential is a
          Cr′ ,r =            ρN,red N
                               p,r Mr ′ ,p +
                                                        N
                                                ρr′ ,p Mp,r . (88)   problem of transient dynamics, and, (ii), because it uses
                       p                        p                    the idea of formulating the calculation of the absorption
                                                                                                                                   21

spectrum in terms of initial and final state Hamiltoni-
ans (Nozières and De Dominicis, 1969), which is also in-
herent to the recent NRG approach to transient dynam-
ics beyond linear response theory (Anders and Schiller,
2005; Costi, 1997a).
   A simple model for describing the x-ray absorption
spectra in metals, is given by the following spinless
Hamiltonian

              εk c†k ck + Ed d† d +   Udc c†k ck′ dd† ,
          X                         X
     H=                                                 (89)
            k                       k,k′


where d† creates a core-electron with energy Ed and the
attractive screening interaction, Udc , acts only when the
core-level is empty (dd† = 1). The core-level lifetime is             FIG. 12 Absorption spectrum normalized by the Noziéres-
assumed infinite, and the interaction with the x-ray field            De Domenicis result (Eq. (91)) for several screening potentials
                                                                      of the form Udc (k, k′ ) = G0 +G1 (k+k′ ) (Oliveira and Wilkins,
is taken to be of the form
                                                                      1981).
                Hx = w(c†0 de−iωt + H.c.),                     (90)
                                                                      form Ad (ω) = δ(ω − Ed ) in the absence of screening, is
            P
where c0 = k ck . The x-ray absorption spectrum, µ(ω),
is obtained using linear response theory from the imagi-              replaced by an incoherent spectrum of the form
nary part of the optical conductivity, χcd = hhc†0 d; d† c0 ii.
                                                                                 Ad (ω) ∼ θ(E˜d − ω)(E˜d − ω)−(1−ε) ,            (95)
At zero temperature, one finds for the absorption spec-
trum a power law singularity of the form                              in the presence of screening (Doniach and Šunjić, 1970).
                                           −α                            Oliveira and Wilkins (1981) applied the NRG to the
                   µ(ω) ∼ (ω − ET )              ,             (91)
                                                                      initial-state and final-state Hamiltonians (92-93) and cal-
where, ET is the absorption threshold, and, α, is an expo-            culated the zero temperature linear response absorption
nent which depends on the strength of the core-hole po-               spectrum,
tential. The exponent α has two contributions α = α′ −ε,
                                                                                                     |hmF |c†0 d|mI,GS i|2
                                                                                                  X
an excitonic part, α′ , due to Mahan (1967) and an or-                              µ(ω) = 2πw2
                                                                                                  mF
thogonality part, ε, which follows from Anderson’s or-
thogonality catastrophe theorem (Anderson, 1967). An                               ×δ(ω − (EmF − EmI,GS )),                      (96)
exact solution of the ’x-ray problem’ has been obtained
by Nozières and De Dominicis (1969) by using the de-                 with HI,F |mI,F i = EmI,F |mI,F i and |mI,GS i the ground
composition of (89) into single-particle initial-state, HI ,          state of HI . In evaluating µ(ω), truncated Hamiltoni-
                                                                              N
and final-state, HF , Hamiltonians, corresponding to the              ans, HI,F  , were used and the spectrum was evaluated
situations before (dd† = 0) and after (dd† = 1) a core-               at an appropriate frequency ω = ωN as in Sec. III.B.1
electron is excited to the conduction band:                           but with a box broadening function on a logarithmic
                                                                      scale. They were able to recover the exact thresh-
                        εk c†k ck + Ed ,                              old exponent of Nozières and De Dominicis (1969) (see
                     X
             HI =                                      (92)
                      k                                               Lı́bero and Oliveira (1990a) for similar calculations of
                                                                      the photoemission spectra). They also extended the cal-
                          εk c†k ck +          Udc c†k ck′ .
                     X                  X
            HF =                                               (93)   culation of absorption spectra to core-hole potentials of
                      k                 k,k′
                                                                      finite range Udc → Udc (k, k ′ ), finding (see Fig. 12) that
For the spinless model, (89), Nozières and De Dominicis              the threshold exponent remains universal, i.e. it depends
(1969) found the exponents                                            only on the phase shift δ at the Fermi level, but that
                                                                      the asymptotic scale for the onset of power-law behavior
                  α′ = 2δ/π, ε = (δ/π)2 ,                      (94)   depends on both the range (Oliveira and Wilkins, 1981)
                                                                      and the strength of the core-hole potential (Cox et al.,
where the phase-shift δ = arctan(−πNF Udc ) is that for               1985). It also depends on any energy dependence in the
conduction electrons scattering from the additional po-               density of states (Chen et al., 1995). These results reflect
tential created by the core-hole, and, NF is the conduc-              the fact that the crossover scale to the low energy fixed
tion electron density of states at the Fermi level. In ad-            point, determining universal properties, depends on de-
dition to the absorption spectrum, the core-level pho-                tails of the density of states and the core-hole potential.
toemission spectrum, Ad (ω) = −Im[hhd; d† ii]/π, is also
of interest. In the core-level photoemission spectrum,                  X-ray singularities also play an important role in
only the orthogonality effect is operative and the core-              the dynamics of auxiliary particles in the slave-boson
electron spectral function, which has the quasiparticle               approach to the infinite U Anderson impurity model
                                                                                                                               22

(Coleman, 1984; Müller-Hartmann, 1984). A NRG cal-               with
culation of the T = 0 photoemission spectra for slave-                                     Z +∞
bosons, Ab (ω), and pseudo-fermions, Af σ (ω), showed                            P (t) =           P (ω) cos(ωt)dω.          (105)
that these diverge with the exponents given above for                                       0
the photoemission and absorption spectra respectively,            We see that even at T = 0, no ground state enters the
generalized to include spin, (Costi et al., 1996, 1994b):         delta functions in (104), in contrast to the linear-response
                                                                  expression (96) for µ(ω) in the x-ray problem. This im-
                Af σ (ω) ∼ (ω − ET )−αf ,                  (97)   plies that in evaluating P (ω) at a frequency ω ∼ ωN , con-
                 Ab (ω) ∼ (ω − ET )−αb ,                   (98)   tributions will arise from all energy shells n = 1, 2, . . . , N
                             δσ X δσ 2                            as discussed previously for finite-T dynamics. In the
                      αf = 2 −       ( ) ,                 (99)   present situation, however, the contributions from higher
                             π     σ
                                      π
                                                                  energy shells (i.e. n < N ) are not suppressed by Boltz-
                               X δσ
                      αb = 1 −    ( )2 ,                  (100)   mann factors, so it is not clear a priori that using a single
                                σ
                                    π                             shell approximation will give meaningful results. Such
                                                                  an approximation shows that the short-time dynamics of
with the phase shift δσ = πnf σ and nf σ the occupancy            the spin-boson model can be recovered and that in or-
per spin of the local level. Here, also, the scale for the        der to obtain the long-time dynamics one has to sum up
onset of power-law behavior is determined by the relevant         contributions from all shells (Costi, 1997a). Adding up
low energy crossover scale, e.g., the Kondo scale in the          such contributions using the retained states of succes-
                                                                                          N    N +1
Kondo regime.                                                     sive Hamiltonians HI,F    , HI,F  , . . . is problematical due
   We turn now to a problem which is formally similar to          to the overlap of the spectra at low energies. An elegant
the x-ray problem, namely the dynamics of a spin subject          solution of this problem, allowing multiple-shell NRG cal-
to an initial state preparation, as in the case, for exam-        culations to be carried out, has recently been found by
ple, of the dynamics of the spin in the spin-boson model          Anders and Schiller (2005). Their idea, was to recognize
Eq. (139). Further discussion of the effects of screening         that the set of states discarded, |rim,disc , at each NRG
on the spectra of impurity models is given in Sec. IV.A.1.        iteration m, supplemented with the degrees of freedom
In the spin-boson model one is interested in the dynam-           |e; mi = |sm+1 i ⊗ . . . ⊗ |sNmax i, for m = 1, . . . , Nmax ,
ics of a spin, σz , described by P (t) = hσz (t)i̺I , following   with Nmax the largest Hamiltonian diagonalized, forms a
an initial-state preparation of the system described by           complete basis set
an initial density matrix ̺I (Leggett et al., 1987). For
                                                                               N max
example, the spin σz in (139) could be prepared in state                       X       X
                                                                                                |r, e; mihr, e; m| = 1 .     (106)
| ↑i at t < 0 by an infinite bias ε = ∞ with the environ-
                                                                               m=1 r∈{disc}
ment fully relaxed about this state, and the bias could
subsequently be switched off at t = 0 allowing the spin to        Using this identity, their result for P (t) in the basis of
evolve. The time evolution of the spin for t > 0 is then          final states is
described by
                                                                                          N trun
                                                                                                               m
                                                                                                            i(Em −Em′ )t/~
                                                                                          X X
                   1                                                            P (t) =                 e       F    F
    hσz (t)i̺I =       T r[̺I e−iHF t/~ σz eiHF t/~ ] ,   (101)                           m=1 mF ,m′F
                 T r̺I
                                                                                ×hmF |σz |m′F i̺m,red
                                                                                                mF ,m′ ,                     (107)
where ̺I = T r[e−βHI ] and the initial and final state                                                      F

Hamiltonians are given by                                         where ̺m,red
                                                                          rF ,sF are the matrix elements of the reduced den-
                                                                  sity matrix ̺I for HIm introduced in the previous sec-
                    HI = HSB (ε = ∞) ,                    (102)                         Ptrun
                                                                  tion and the sum         mF ,m′F implies that at least one
                    HF = HSB (ε = 0) ,                    (103)                          ′
                                                                  of the states mF , mF is in the discarded sector for it-
where HSB is the spin-boson Hamiltonian (139).                    eration m. Rotating ̺m,red  rF ,sF to the initial state ba-
   This approach has been investigated within NRG by              sis gives overlap matrix elements hmI |mF i, hmI |m′F i
Costi (1997a) using, for the Ohmic case, in place of HSB ,        as in (104) above. Within this approach the time-
the equivalent anisotropic Kondo model. Despite the for-          dependent transient dynamics of a number of models
mal similarity with the x-ray problem, the exact formula-         has been investigated, including the Anderson and reso-
tion indicates the difficulties that have to be overcome in       nant level models (Anders and Schiller, 2005), the Kondo
calculating transient dynamical quantities beyond linear          model (Anders and Schiller, 2006) and the sub-ohmic
response. Consider the spectral function                          spin-boson model (Anders et al., 2006).
                                                                     The use of a complete basis set (106) has poten-
               1       X                                          tial to improve also the finite-T calculation of spec-
    P (ω) =                       e−βEmI hmI |mF ihm′F |mI i      tral densities, particularly in the problematical range
               ZI
                    mI ,mF ,m′F
                                                                  ω < T (Weichselbaum and von Delft, 2006). A fur-
           × hmF |σz |m′F iδ(ω − (EmF − Em′F )),          (104)   ther improvement in using a complete basis set is that
                                                                                                                                   23
                                      R∞
the sum rule for spectral densities −∞ dωAσ (ω, T ) = 1                   and the level hybridizes with the conduction band via a
is, by construction, fulfilled exactly (Peters et al., 2006;              term
Weichselbaum and von Delft, 2006).                                                                 X †
                                                                                         Hmix = V      (ck b + H.c.).       (110)
                                                                                                      k

IV. APPLICATION TO IMPURITY MODELS                                        Note that Hdb just represents a screening of the core-
                                                                          hole by electrons in the resonant level. Excitation of
   In this section we review the application of the NRG                   an electron from the core-level by an x-ray can pro-
to a range of quantum impurity models. Section IV.A                       ceed either directly or via the resonant level, leading
reviews work on models with conduction electron screen-                   to a Fano anti-resonance in the x-ray absorption at fi-
ing (Sec. IV.A.1), underscreened and fully screened                       nite energy (in addition to the usual edge singularity at
Kondo models (Sec. IV.A.2), and models exhibiting the                     ω = ET ). This Fano anti-resonance, present also with-
Kondo effect in nanostructured devices (Sec. IV.A.3).                     out the core-hole potential, is found to be significantly
Section IV.B deals with the prototypical overscreened                     narrowed and shifted in the presence of the core-hole
Kondo model, the two-channel Kondo model, which                           potential (Oliveira and Wilkins, 1985). It would be of
is often encountered as an effective model describing                     interest to investigate also the core-level photoemission
the quantum criticial point of more complex quan-                         spectrum of this model using the NRG, as both this, and
tum impurity models, e.g. certain double quantum dot                      the absorption spectrum, are accessible in experiments.
systems (Zaránd et al., 2006) or two-impurity systems                    Brito and Frota (1990) have carried out such a calcula-
(Jones and Varma, 1987). Impurity quantum phase tran-                     tion for an appropriately generalized spinfull version of
sitions are reviewed in Sec. IV.C in the contexts of multi-               the above model, i.e., the Anderson model (2) in the
impurity systems (IV.C.1), soft-gap systems (IV.C.2) and                  presence of both an interaction,
in the context of magnetic impurities in superconductors                                                X †
(IV.C.3). Sec. IV.D reviews work on multi-orbital sys-                                    Hdc = Udc dd†     ckσ ck′ σ ,       (111)
tems, including the effects of crystal-field splittings in                                                kk′ σ
Anderson impurity models. Finally, models with bosonic                    between the core-hole and the conduction electrons, and,
degrees of freedom are reviewed in Sec. IV.E. Note                        an interaction,
also, that a number of models of nanostructured devices,
for example, the single-electron box, quantum dots with
                                                                                                        X
                                                                                          Hdf = Udf dd†    fσ† fσ ,          (112)
phonons, or multi-orbital quantum dots, are to be found                                                      σ
in Sec. IV.B-IV.E.
                                                                          between the core-hole and the valence level. Signatures
                                                                          of the valence states could be identified in the XPS spec-
                                                                          tra and their dependence on Udc was investigated in the
A. Kondo effect and related phenomena
                                                                          mixed valence and empty orbital regimes. A reduction
                                                                          of the hybridization between the valence level and the
1. Screening and photoemission
                                                                          conduction band, arising from orthogonality effects, was
                                                                          found with increasing Udc . The corresponding calcula-
   Screening effects are important whenever an electron                   tion in the Kondo regime is still lacking. The x-ray ab-
is excited from a localized core- or valence-state into the               sorption spectrum of the same model has been investi-
conduction band or removed completely, leaving behind a                   gated in (Helmes et al., 2005) in the context of excitons
hole which attracts the conduction electrons. Such effects                in Kondo correlated quantum dots and the expected ab-
can have a drastic influence on the photoemission and                     sorption exponent from the Nozières – De Domenicis the-
absorption spectra of impurity systems. In this section                   ory was recovered.
we consider a number of extensions to the basic screening                    In the models discussed so far, the core-level was as-
model (89) introduced in Sec. III.B.3,                                    sumed to have infinite lifetime. Consequently, the screen-
                                                                          ing interaction gave rise to true singularities in the core-
               εk c†k ck + Ed d† d +          Udc c†k ck′ dd† .
         X                             X
    H=                                                            (108)   level absorption and photoemission spectra. These sin-
           k                           k,k′                               gularities are cut off as soon as the core-level lifetime
                                                                          is finite. Another situation where the singularities due
We consider first the generalization of (108) to a sim-                   to screening are cut off, but where screening effects may
plified model of an atom adsorbed on a metallic surface                   nevertheless be important, is in the valence band photoe-
(Oliveira and Wilkins, 1985). In addition to a core-level,                mission spectra of heavy fermions within a local impurity
as in (108), the atom has a resonant level (created by b† )               approach, which we now address.
whose position, EbI or EbF , depends on the occupancy                        It is often assumed that the effects of conduction elec-
of the core-level according to the term                                   tron screening on the f electron photoemission spectra of
                                                                          heavy fermions can be taken into account by renormaliz-
       Hdb = EbI b† bd† d + EbF b† b(1 − d† d),                   (109)   ing the bare parameters of an effective Anderson impurity
                                                                                                                            24

model. However, this is not a priori clear as the screening     band, which can be understood as an orthogonality ef-
interaction in these systems can be an appreciable frac-        fect. Nevertheless, we conclude from these NRG calcula-
tion of the local Coulomb repulsion. One of the merits of       tions that in the Kondo regime, and with realistic values
the NRG, which allows such questions to be investigated,        of Udf (Uf c ), the valence band photoemission spectra of
is that it can deal with all local Coulomb interactions on      both the above screening models can be well accounted
an equal footing and in a non-perturbative manner, and          for by an Anderson model with renormalized parameters.
some examples of this have already been given above.               The two-channel screening model above, has also
For the particle-hole symmetric Anderson model, (2), it         been studied for finite U (Perakis and Varma, 1994;
was shown in Costi and Hewson (1991, 1992a) that the            Perakis et al., 1993). At particle-hole symmetry, increas-
effect of a screening term of the form                          ing Udc reduces both U and the effective hybridization,
                                                                resulting, for sufficiently large Udc , in an effective attrac-
                                fσ† fσ c†kσ′ ck′ σ′ ,
                           X
              Hf c = U f c                            (113)     tive local Coulomb interaction and a charge Kondo ef-
                         kk′ σσ′                                fect. For still larger Udc , a Kosterlitz-Thouless transition
                                                                to a non-Fermi liquid state occurs (Perakis and Varma,
on the valence band photoemission spectrum could be             1994; Perakis et al., 1993) with a collapse of the Kondo
well accounted for by a renormalization of the bare pa-         resonance in the valence band photoemission spectrum
rameters of the Anderson model, both the local level po-        (Costi, 1997b).
sition, ε = −U/2, and the hybridization. An excitonic
like enhancement of the hybridization was found with in-
creasing Uf c . Similar effects are reflected in the STM con-   2. Kondo effect in the bulk and underscreened models
ductance of a magnetic adatom modeled by the screened
Anderson model (Cornaglia and Balseiro, 2003). Calcu-              Real magnetic impurities in metals have both or-
lations for the infinite U Anderson impurity model, for         bital and spin degrees of freedom and the resulting low-
thermodynamics (Alascio et al., 1986; Zhuravlev et al.,         energy effective impurity models can be very complicated
2005), and, dynamics (Takayama and Sakai, 1993), are            (Hewson, 1993). The NRG has been applied so far to
consistent with the above findings.                             models with at most three orbitals, see Sec. IV.D. In
   The above model for screening in heavy fermions as-          cases where the ground state is an orbital singlet, e.g. for
sumes that the largest contribution to screening of f holes     dilute Mn ions in metals, Nozières and Blandin (1980)
arises from conduction electrons in states that hybridize       have given a useful classification of the resulting effec-
with the f states. These hybridizing states are usually         tive single-impurity Kondo models in terms of the size of
the p levels from neighboring ligand ions, so the screen-       the impurity spin S and the number of conduction chan-
ing from these (denoted Uf c above) should be expected          nels, n, which couple to the spin via the Kondo exchange.
to be smaller than the onsite screening, Udf , from the d       These multi-channel Kondo models are described by
electrons of the rare-earth ion. By symmetry, the latter
                                                                                  εk c†kσα ckσα + J
                                                                              X                     X
do not hybridize with the f states. Neglecting Uf c and                  H=                           S · sα ,        (115)
representing the d electrons by a spinless s wave band,                       kσα                    α
we may represent the screening of f holes by d electrons
by adding to the Anderson model (2) the term                    where α = 1, . . . , n is the channel index, and the ex-
                                                                change constant, J, is antiferromagnetic. For n = 2S,
                  εk d†k dk + Udf    (nf − 1)d†k dk′ ,
             X                    X
     Hscr =                                             (114)   complete screening of the impurity spin takes place lead-
             k                     kk′                          ing to a local Fermi liquid at low temperatures. The
                                                                overscreened case, n > 2S, exhibits non-Fermi liquid be-
                    †
              P
where nf =       σ fσ fσ . The resulting model is a two-        havior and is reviewed in Sec. IV.B. In this section, we
channel Anderson model, in which one channel screens,           deal with some recent developments on the fully screened
but, does not hybridize, and, the other channel hy-             S = 1/2 Kondo model, relevant to bulk Kondo impuri-
bridizes, but, does not screen. Assuming localized d            ties, and also describe work on the the single-channel
electrons gives the model studied by Brito and Frota            underscreened case, n = 1 < 2S.
(1990) and discussed above.         For the full model,            One of the signatures of the Kondo effect is the appear-
Takayama and Sakai (1993, 1997) calculated the valence          ance in the impurity spectral density of the Kondo reso-
band photoemission spectrum and, surprisingly, found            nance at the Fermi level. Point contact spectroscopy on
that the effect of Udc in the Kondo regime could be ab-         Cu wires containing magnetic impurities, using the me-
sorbed into a renormalization of the Anderson model pa-         chanically controllable brake junction technique, show a
rameters. This result was for infinite U , but it should re-    zero bias anomaly, which is attributed to the Kondo res-
main valid in the Kondo regime for any finite U provided        onance (Yanson et al., 1995). In addition, these exper-
Udc remains smaller or comparable to U . In contrast to         iments show that the Kondo resonance splits in a mag-
the model described above, where the screening occurs           netic field. NRG calculations for the S = 1/2 Kondo
in the hybridizing channel, the effect of the screening in-     model in a magnetic field do indeed show that the Kondo
teraction in the present model is to reduce the effective       resonance splits in a magnetic field, B, provided the Zee-
hybridization of the valence electrons to the conduction        man splitting gi µB B exceeds the Kondo scale TK (Costi,
                                                                                                                                                                                                           25

2000). Here gi , µB are the impurity g-factor and Bohr                                    1
magneton and TK is the Kondo scale defined from the
                                                                                                                                                                                      σelastic
half-width at half-maximum of the T = 0 Kondo reso-                                                                                                                                   σinelastic
nance. The latter is obtained from the imaginary part of                                                                                                                              σtotal
the many-body T -matrix, Tkk′ σ , for spin σ, defined by
                                                                                                   Nagaoka−Suhl approx.




                                                                         σ / σ0
    Gkk′ σ (ω) = δkk′ G0kk′ σ + G0kkσ Tkk′ σ G0k′ k′ σ ,   (116)
                                                                                       0.5             −1                                      −2
                                                                                                  10                                  ~ln (ω/TK)
where Gkk′ σ (ω) = hhckσ ; c†k′ σ ii is the full conduction elec-                                      −2
                                                                                                  10
tron Green function and G0kk′ is the corresponding unper-
                                                                                                                                      2
                                                                                                                 ~(ω/TK)
                                                                                                       −3
turbed Green function. From the equations of motion for                                           10        −2           0                2         4     6
                                                                                                           10    10 10 10 10
Gkk′ one finds for the orbitally isotropic Kondo model                                                              ω/TK

                       J           J                                                      0 −2
         Tkk′ σ (ω) = σ hSz i + ( )2 hhOσ ; Oσ† ii,        (117)                          10                                   10
                                                                                                                                         −1
                                                                                                                                                                  10
                                                                                                                                                                        0
                                                                                                                                                                                               10
                                                                                                                                                                                                   1
                       2           2
                      X
                         ~                                                                                                                              ω/TK
                Oσ =     S · ~τσσ ckσ′ ,
                                 ′                         (118)
                          k
                                                                    FIG. 13 Elastic, inelastic and total scattering rates for the
with ~τ the Pauli matrices. From the T -matrix one can              S = 1/2 fully screened Kondo model at T = 0 (from
also extract the transport time and thereby the magne-              Zaránd et al. (2004)). The Kondo scale TK is that from the
toresistivity. The latter is found to agree well with ex-           half-width at half-maximum of the Kondo resonance and is
perimental data on diluted Ce impurities in LaAl2 (Costi,           approximately twice that from the T = 0 susceptibility de-
2000).                                                              fined in (81).
   A recent development has been the realization by
Zaránd et al. (2004) that one can use the NRG to extract                              0.25
from the many-body T -matrix both elastic and inelastic                                                                                                                              d=1
                                                                                                                                                                                     d=2
scattering rates and cross sections. The total scattering                               0.2
                                                                                                                                                                                     large B
cross section, σtot (ω), is related to the imaginary part of                                                                                                                         Nagaoka-Suhl
                                                                       1 / τφ πν/2nS



the T -matrix by the optical theorem
                                                                                       0.15
                                 2
              σtot (ω = εk ) = − Im[Tkkσ (ω)],             (119)
                                                                                                                     1 / τφ πν/2nS
                                                                                                                                     0.2
                                vk                                                      0.1                                                                             d=1

with vk the velocity of electrons with wavevector k. Con-                                                                            0.1
                                                                                       0.05
sequently, by using the expression for the elastic scatter-                                                                                                             T / TK
ing cross section                                                                                                                     0
                                                                                                                                           0                      0.5                     1
                                                                                         0
                                                                                              0        1         2                   3              4         5         6        7         8           9
                     2π X                                                                                                                               T / TK
   σel (ω = εk ) =        δ(εk′ − εk )|Tkk′ σ (ω)|2 ,      (120)
                     vk ′
                         k
                                                                    FIG. 14 Universal dephasing rate for the S = 1/2 fully
Zaránd et al. (2004) were able to calculate the inelastic          screened Kondo model calculated via NRG for Kondo impu-
scattering cross section σinel = σtot − σel and the inelastic       rities in d = 1, 2 dimensional conductors (from Micklitz et al.
                          −1                                        (2006a)). The solid line in the inset is the analytic T 2 result
scattering time, τinel ∼ σinel . In order to shed some light
                                                                    from Fermi liquid theory valid for T ≪ TK , where TK is the
on the expression for σinel , consider the Anderson
                                              P       model         scale defined in (81).
for a flat band with density of states NF = k′ δ(εk′ −εk )
and resonant level width ∆ = πNF V 2 . We have, Tkk′ =
V 2 Gd , with Gd = (ω − εd + i∆ − Σ(ω))−1 and Σ the cor-
relation part of the self-energy. The inelastic scattering            A quantity closely related to the inelastic scattering
                                                                                      −1
cross section for ω = εk reduces to (Zaránd et al., 2004)          time, τinel ∼ σinel  , is the dephasing time, τφ , for elec-
                                                                    trons scattering from magnetic impurities and measured
              2               V 2 Σ′′ (ω)                           in weak-localization experiments on diffusive conductors
  σinel = −                                          , (121)        (Bäuerle et al., 2005; Mohanty et al., 1997; Pierre et al.,
              vk (ω − εd − Σ′ (ω))2 + (∆ − Σ′′ (ω))2
                                                                    2003; Schopfer et al., 2003). The two quantities are, how-
which shows that the inelastic scattering rate vanishes             ever, not identical. An exact expression for the dephasing
for electrons at the Fermi level due to the Fermi liquid            rate of electrons scattering from a dilute concentration
properties of the self-energy. Zaránd et al. (2004) eval-          of Kondo impurities in a weakly disordered metal has
uated σinel for the S = 1/2 Kondo model via the NRG                 recently been derived (Micklitz et al., 2006a). Fig. 14
using the T-matrix in (117) at T = 0 and for both zero              shows the dephasing rate as a universal function of T /TK
and finite magnetic fields. The maximum in the inelastic            for the S = 1/2 Kondo model, obtained by using the
scattering rate occurs close to the ω ≈ TK (see Fig. 13).           NRG for finite temperature dynamics. The maximum
                                                                                                                               26

dephasing rate occurs at T ≈ TK and decreases at first         Alzoubi and Birge (2006). Calculations for the tem-
linearly with temperature below TK and eventually as           perature dependence of the resistivity and dephasing
T 2 in the Fermi liquid region T ≪ TK . The magnetic           rates of the spin S > 1/2 underscreened Kondo mod-
field dependence of the dephasing time, τφ (B, T ), has also   els and their relevance to Fe impurities in Ag can be
been calculated and the expression for the dephasing rate      found in (Mallet et al., 2006). It is also interesting to
has been generalized to arbitrary dynamical scatterers         note, that calculations for ferromagnetic Kondo models
(Micklitz et al., 2006b). Recent experiments on Fe impu-       (Koller et al., 2005b) show that all cross sections vanish
rities in Ag wires show better than expected agreement         at the Fermi level with the inelastic part contributing
with the theoretical predictions for the dephasing rate        nearly all the scattering in this limit and with the elastic
of the S = 1/2 Kondo model (Alzoubi and Birge, 2006;           part being negligibly small.
Mallet et al., 2006). Fe impurities in Ag will have both          Finally we mention recent work on calculating spa-
an orbital moment and a spin S = 2 in the absence of           tial correlations such as spin-density correlations, C(x) =
crystal field and spin-orbit interactions. Inclusion of the     ~ sx i, around Kondo impurities, where s~x is the electron
                                                               hS·~
latter, may, however, result in an effective S = 1/2 single-   spin density at distance x from the impurity (for earlier
channel Kondo model at the low temperatures T ≈ 1K             work involving perturbative aspects combined with NRG
of the experiments, thereby helping to explain the good        see (Chen et al., 1987, 1992)). Borda (2006) works with
agreement with the S = 1/2 theory. At the very lowest          Wannier states centered at both the impurity and at x,
temperatures, T < 0.1TK , a slower decay of the dephas-        thereby reducing the problem to a two-impurity type cal-
ing rate has been reported in these experiments, as com-       culation (Sec. IV.C.1). At T = 0 and in one dimension,
pared to that expected from a fully screened model. One        the decay of C(x) is found to change from 1/x to 1/x2
possible explanation for this is that a small fraction of      around x = ξK = ~vF /TK , where the coherence length,
Fe impurities is only partially screened. Underscreened        ξK , describes the size of the Kondo screening cloud. At fi-
Kondo models, to which we now turn, are known to give a        nite temperature, the expected exponential decay of C(x)
much slower decay of the dephasing rate below the Kondo        for x > ξT = ~vF /kB T is recovered.
scale, see below and Vavilov and Glazman (2003).
   Cragg and Lloyd (1979) investigated the single-
channel S = 1 underscreened Kondo model and showed             3. Kondo effect in nanostructures
that its low-energy fixed point corresponds to the spec-
trum of the ferromagnetic S ′ = 1/2 Kondo model. The             Recent experimental work has demonstrated the
deviations from the fixed point at iteration N are of the      importance of the Kondo effect in determining the
       ˜ )S~′ · ~s0 with J(N
form J(N                   ˜ ) being O(−A/(N + C(J)))          low-temperature transport properties of nanoscale size
with A being a constant and C(J) depending on J, i.e.          devices such as quantum dots (Cronenwett et al., 1998;
the deviations are marginally irrelevant. These calcu-         Goldhaber-Gordon et al., 1998; van der Wiel et al.,
lations were extended by Koller et al. (2005b) to mod-         2000). An example of such a device, a quantum dot, is
els with S = 1, . . . , 5/2. They also determined C(J)         shown in Fig. 15. More complicated devices, such as
explicitly for the different cases. Using the relation of      capacitively coupled double-dots or dots contained in one
N to energy ω ∼ Λ−N/2 , the effective coupling can be          or two arms of an Aharanov-Bohm interferometer can be
             ˜
written as J(ω)    ∼ 1/ ln(ω/T0 ) with T0 an appropriate       built up from this basic unit. A quantum dot consists of
Kondo scale (Koller et al., 2005b). Consequently, there        a confined region of electrons coupled to leads via tunnel
are logarithmic corrections to thermodynamic quantities        barriers. It may be viewed as an artificial multi-electron
at low temperature, instead of the power-law corrections       atom, in which the different levels (filled, partially filled
characteristic of fully screened Kondo models. Non-            or empty) couple to electron reservoirs via one or more
analytic corrections are also found in dynamical quan-         channels. A quantum dot can be described, in general,
tities (Koller et al., 2005b; Mehta et al., 2005), so un-      by the following multi-level Anderson impurity model
derscreened Kondo models have been termed “singular
Fermi-liquids” (Mehta et al., 2005). For, example, the               H = Hdot + Hc + Htun ,                 (123)
spectral density, ρt (ω), obtained from the T-matrix (117)                                         2
                                                                            εiσ d†iσ diσ + EC N̂ − N − JH S
                                                                                                          ~2 ,
                                                                          X
takes a finite value at the Fermi level, but the approach          Hdot =
                                                                               iσ
to this value is non-analytic (Koller et al., 2005b):
                                                                                    εkσ c†kασ ckασ ,
                                                                              X
                                          2
                                                                     Hc =
             ρt (ω) = ρt (0) − b/ ln(ω/T0 ) ,         (122)                   kασ
                                                                                                              
                                                                                     tαi d†iσ ckασ + c†kασ di,σ ,
                                                                              X
Similarly, the T = 0 inelastic cross section, also calcu-          Htun =
lated by Koller et al. (2005b), decays as 1/ ln(ω/T0 )2 , at                  kαiσ
low energies, and consequently, the dephasing rate de-
cays as τφ−1 (T ) ∼ 1/ ln(T /T0 )2 . As mentioned above,       where ǫiσ , i = 1, 2, . . ., are the dot level energies for spin σ
                                                               electrons, N = hN̂ i = iσ hd†iσ diσ i, is the dot occupancy,
                                                                                            P
a small fraction of underscreened Fe impurities may ex-
                                                                                                  ~ = 1
                                                                                                         P       †
plain the excess dephasing observed at the lowest tem-         EC is the charging energy, S            2    iµν diµ ~
                                                                                                                    σµν diν is the
peratures in the experiments of Mallet et al. (2006) and       total spin of the dot and JH > 0 is the Hund’s exchange
                                                                                                                            27

                 VL           VG          VR                       even combination of left and right electron states, akσ ,
                                                                   below, couples to the local level, as can be seen by using
                                                                   the canonical transformation
                                                                                                         q
                                                                           akσ = (tL ckLσ + tR ckRσ )/ t2L + t2R ,      (124)
                                                                                                           q
    2DEG                    DOT                      2DEG                   bkσ = (−tR ckLσ + tL ckRσ )/ t2L + t2R , (125)

                                                                   with tα = tαi δi,1 .          We note that treating the
                                                                   Coulomb interaction classically implies that, for an in-
                                                                   teger number of electrons on the dot, transport is
                                                                   blocked for large U, since transferring electrons through
                  VL          VG           VR
                                                                   the dot requires overcoming the large Coulomb repul-
FIG. 15 Schematic top view of a lateral quantum dot, consist-      sion. Glazman and Raikh (1988) and Ng and Lee (1988)
ing of a confined region of typical size 10-100nm defined in the   pointed out, however, that in the situation where the to-
two-dimensional electron gas (2DEG) of a GaAs/AlGaAs het-          tal spin on the dot is finite, as happens for an odd number
erostructure. The dot is connected to left and right electron      of electrons (i.e. for N = 1 in the effective single-level
reservoirs. Gate voltages VL,R control the tunnel barriers into    model), one should expect, on the basis of (2), an en-
and out of the dot, while VG controls the dot level positions.     hancement of the conductance to its maximum possible
                                                                   value of G = 2e2 /h via the Kondo effect in the limit of
                                                                   zero temperature. A device, representing a tunable An-
coupling. In the above, α = L, R labels left/right lead            derson impurity model, was realized (Cronenwett et al.,
degrees of freedom and k labels the wavevector of a single         1998; Goldhaber-Gordon et al., 1998) and the predicted
transverse channel propagating through the constriction            enhancement of the low-temperature conductance for
between the 2DEG and the quantum dot. Electrons tun-               dots with an odd number of electrons was measured and
nel into and out of the dot with amplitudes tαi and give           compared (Goldhaber-Gordon et al., 1998) to quantita-
rise to a single-particle broadening Γi of the levels.             tive NRG calculations (Costi et al., 1994b) such as those
   The model above is essentially the same model as the            shown in Fig. 10 for the conductance in the Kondo regime
multi-orbital model of Sec. IV.D, used to describe bulk            (see also Izumida et al. (2001a)). Tuning the quantum
Kondo systems. The novel situation in quantum dots is              dot to the mixed valence and empty orbital regimes, has
that parameters such as the tunnel couplings and level             enabled also comparisons with theory in those regimes
positions can be controlled by gate voltages. This allows          (Costi, 2003; Schoeller and König, 2000).
such models to be experimentally investigated in all phys-            The frequency dependence of the linear conduc-
ically interesting regimes, such as spin and charge fluctu-        tance, G′ (ω), of a single-level quantum dot de-
ation regimes, and in principle also to be tuned through           scribed by (2) has been considered by several au-
quantum phase transitions. In addition, different real-            thors (Campo, Jr. and Oliveira, 2003; Izumida et al.,
izations of quantum dots (nanotubes, vertical dots) may            1997; Sindel et al., 2005). Sindel et al. (2005) calculated
have level degeneracies or near level degeneracies, allow-         G′ (ω), in the Kondo regime at T = 0, and extracted also
ing the effects of Hund’s exchange to be investigated.             the current noise
Finally, the devices described by (123) can be driven                             Z +∞
out of equilibrium by a finite transport voltage, allowing                C(ω) =         dteiωt [hI(0)I(t)i − hIi2 ] ,    (126)
the study of non-equilibrium effects in relatively “sim-                           −∞
ple” quantum many-body systems. This would be one
motivation to further develop the NRG to steady-state              by making use of the fluctuation-dissipation theorem
non-equilibrium situations.
                                                                                               2~ω
                                                                                  C(ω) =                G′ (ω).          (127)
                                                                                           e~ω/kB T − 1
a. Single-level quantum dots    In the low-temperature                The conductance and spin-resolved conductances of
limit, only one or two partially filled levels close to the        single-level quantum dots in a magnetic field have also
Fermi level of the leads will be important for transport.          been calculated and a strong spin-filtering effect has been
The remaining levels will be either filled or empty, and, at       observed in the mixed valence regime (Costi, 2001). For
the low temperatures of interest for quantum transport,            spin-filtering effects in quantum dots with ferromagnetic
they may be neglected. The simplest model, therefore,              leads see Martinek et al. (2003); Simon et al. (2006).
to describe low-temperature transport through a quan-                 One of the hallmarks of the S = 1/2 single-channel
tum dot, is the single-level Anderson impurity model (2)           Kondo effect is the flow of the exchange coupling to
with level position ε1 = εf = −eVG controlled by gate              strong coupling (Wilson, 1975a). This can be interpreted
voltage and Coulomb repulsion U given by the charging              as resulting in a phase shift of the conduction electrons at
energy EC = U/2. Only one conduction channel, the                  the Fermi level, at T = 0, of δσ = π/2 (Nozières, 1974).
                                                                                                                            28

A direct measurement of this phase shift is possible if one
embeds a quantum dot in one arm of an Aharanov-Bohm
interferometer. Assuming a single-level Anderson model
for the quantum dot and a multi-terminal open geometry,
Gerland et al. (2000) carried out NRG calculations for
the interference term, GAB , whose measurement can be
used to extract δσ . A similar set-up has been investigated
by Hofstetter et al. (2001) for the flux dependence G(φ)
of the conductance at T = 0 and by Kang et al. (2005)
for the complex transmission. Izumida et al. (1997) cal-
culated G(φ) for two single-level quantum dots embedded
in the arms of an Aharanov-Bohm interferometer. This
model, reduces, in general, to a two-channel two-orbital
Anderson model, which we discuss next.


b. Two-level quantum dots     A quantum dot with two ac-        FIG. 16 The singlet-triplet crossover in the linear conduc-
tive levels for transport introduces some new physics due       tance of the two-channel two-orbital Anderson model includ-
to the competition between the level spacing δ = ε2 − ε1 ,      ing a Hund’s exchange JH , intra- and inter-orbital Coulomb
the charging energy EC and the Hund’s exchange JH . In          energy, U , levels εd ± δ/2 and temperature T . Top/bottom
particular, a Kondo effect with an even number of elec-         panels shows G(T ) on the triplet/singlet side of the crossover
trons on the dot can be realized. This can occur when the       and (µ − εd )/U = 0.5, 1.5, 2.5 correspond to N = 1.0, 2.0, 3.0
dot is occupied with two electrons and δ < 2JH so that          electrons on the dot. Adapted from Sakai and Izumida
the ground state of the dot has S = 1. Such a two-level         (2003).
dot will, in general, couple to two channels so a S = 1
Kondo effect will result, leading to a singlet ground state
and an enhanced conductance G(T ) at low temperatures.          in the differential conductance similar to predictions for
In the opposite case δ > 2JH the dot will have S = 0, the       the spectral density (Hofstetter and Schoeller, 2002).
Kondo effect is absent and the conductance will be low.           The above is only a brief account of the simplest nanos-
This behavior is believed to have been measured in the          tructured devices studied using the NRG. Further appli-
experiments of Sasaki et al. (2000) on vertical quantum         cations include numerous studies of double-dot systems,
dots, where a magnetic field was used to decrease the en-       including realizing an SU(4) Kondo state (Borda et al.,
ergy splitting, ∆T S = δ − 2JH , between the triplet and        2003) and quantum critical points of two-impurity
singlet states, thereby leading to the above mentioned          Kondo models (Garst et al., 2004; Zaránd et al., 2006;
crossover behavior in the conductance at N = 2. The-            Zhu and Varma, 2006) (see Sec. IV.C.1), static and
oretical calculations by Izumida et al. (2001b), shown in       dynamics of double-dots (Galpin et al., 2006a,b), dou-
Fig. 16, are consistent with the experimental results.          ble dots with only one dot coupled to the leads
   The singlet-triplet crossover behavior in a two-level        (Cornaglia and Grempel, 2005b), applications to quan-
quantum dot can become a quantum phase transition for           tum tunneling in molecular magnets (Romeike et al.,
the special case where only one conduction channel cou-         2006a,b), a novel Kondo effect in a ν = 1 integer
ples to the leads, e.g. when all lead couplings are equal       quantum Hall system (Choi et al., 2003b) and the con-
(Hofstetter and Schoeller, 2002; Pustilnik and Glazman,         ductance of ultrasmall tunnel junctions (Frota, 2004;
2001). In this case, for large Hund’s exchange, an ef-          Frota and Flensberg, 1992).
fective single-channel S = 1 underscreened Kondo model
results which has a doubly degenerate many-body ground
state. For small Hund’s exchange, a model with S = 0 re-        B. Two-channel Kondo physics
sults having a non-degenerate many-body ground state.
A sharp transition separates these two different ground            Nozières and Blandin (1980) have proposed a variation
states. As discussed above, however, two channels will,         of the Kondo model in which the localized spin couples
in general, couple to the dot and this will result in perfect   to two conduction bands. The Hamiltonian of this two-
screening of the S = 1 so that the ground state is always       channel Kondo model is given by
a singlet. Nevertheless, proximity to the singlet-triplet
                                                                                    εk c†kσα ckσα + J
                                                                              X                         X
transition can still be seen as signatures in various quan-             H=                                  S · sα ,     (128)
tities, such as a non-monotonic dependence of the con-                        kσα                       α
ductance as a function of magnetic field on the triplet
side of the crossover (Hofstetter and Zaránd, 2004). Ex-       with α = 1, 2 the channel index and S (sα ) the spin
periments on lateral quantum dots at the singlet-triplet        operators of the impurity (the conduction band electrons
crossover point (van der Wiel et al., 2002) show behavior       at the impurity site with channel index α).
                                                                                                                            29

   An important feature of this model is the overscreen-        coupling J or large values of the discretization parame-
ing of the impurity spin: in the strong-coupling limit, the     ter (up to Λ = 9.0). Nevertheless, these calculations give
spins of both conduction bands try to screen the impu-          the correct fixed point spectrum of the (isotropic) two-
rity spin, so that again a net spin 1/2 object is formed.       channel Kondo model with the characteristic structure of
In other words, the strong-coupling fixed point at J = ∞        excitations at energies 1/8, 1/2, 5/8, 1, etc., at least for
(which gives rise to the Fermi-liquid fixed point in the        the lowest-lying excited states. Figure 17 shows a typical
single-channel case) is unstable and an intermediate-           flow diagram for parameters J = −0.05D, where 2D is
coupling fixed point is realized. This new fixed point          the bandwidth of the featureless conduction band density
shows a variety of non-Fermi liquid properties such as          of states, Λ = 4, and Ns = 4900, for both even (dashed
                                                                curves) and odd NRG iterations (full curves) (for similar
   • a divergence of the specific heat ratio C/T = γ ∝          plots, see Fig. 1 in Cragg et al. (1980) and Figs. 1 and
     ln T and of the spin susceptibility χ ∝ ln T for T →       2 in Pang and Cox (1991)). After some initial even-odd
     0;                                                         oscillations, the flow reaches the non-Fermi liquid fixed
   • an anomalous Wilson ratio R = χ/γ = 8/3, in                point which does not show any even-odd effect. Note that
     contrast to the result for the standard Kondo model        this feature is by no means related to the non-Fermi liq-
     R = 8/4 = 2;                                               uid properties of the model; it just reflects the fact that
                                                                in each iteration, two sites are added to the chain so that
   • a zero-point entropy of 12 ln 2, indicating that ‘half’-   (for particle-hole symmetry) the number of electrons in
     fermionic excitations (Majorana fermions) play a           the ground state is always even.
     crucial role for the structure of the fixed point.
                                                                   Comparison with conformal field theory calculations
We have discussed these features already in the section on      (Affleck et al., 1992) gave an excellent agreement with
the calculation of thermodynamic and static quantities,         the NRG for both the excitation spectrum and the cor-
see Fig. 6. An extensive review of the two-channel Kondo        responding degeneracies. Such a comparison, however,
model, its physical properties and its relevance for non-       requires the extrapolation of the NRG fixed point spec-
Fermi liquid behavior in real materials has been given          tra for Λ → 1 (see Fig. 9 in Affleck et al. (1992); the
in Cox and Zawadowski (1998). This paper also reviews           analysis is not quite satisfactory for Λ < 2 and it would
the earlier NRG-calculations for this model.                    be interesting to repeat these calculations using larger
   Historically, the two-channel Kondo model has been           values of Ns ). This work, and the previous paper by
the first application of the NRG to a quantum impurity          Pang and Cox (1991), also focussed on the stability of
model in which the physics is not governed by the Fermi         the non-Fermi liquid fixed point against various pertur-
liquid fixed point of the standard Kondo model. In this         bations. As it turns out, the non-Fermi liquid fixed point
sense, the early work of Cragg et al. (1980) on the two-        is stable against anisotropy in the exchange interaction
channel Kondo model opened the way for a variety of in-         (Jz 6= J⊥ ) but unstable against both the presence of a
vestigations of more complex impurity models, displaying        magnetic field and the lifting of the exchange symmetry
both Fermi liquid and non-Fermi liquid fixed points. Due        between the two channels (Ja 6= Jb ). In the latter case,
to the importance of this and following work, we want to        a temperature scale T ∗ ∝ (Ja − Jb )2 for the crossover
focus this section purely on two-channel Kondo physics          between the non-Fermi liquid fixed point at intermediate
and shift the discussion of other multi-band models to          temperatures and the stable Fermi liquid fixed point at
the section on orbital effects (Sec. IV.D).                     T → 0 has been found. These instabilities have been later
   As discussed already in Sec. II, the truncation of states
within the iterative diagonalization scheme severely lim-
its the applicability of the NRG to multi-band models. In                   2.5
the calculations of Cragg et al. (1980), the iterations were
observed to break down only after a few (approximately                       2
twelve) steps. The source of this problem is mainly the
small number of states (Ns ≈ 400) used in√this work,                        1.5
which would correspond to keeping Ns ≈ 400 = 20
                                                                    EN(r)




states in a one-channel calculation. Specific symmetries
                                                                              1
of the two-channel Kondo model, such as the total ax-
ial charge, have been used to reduce the matrix sizes in
the diagonalization (Pang and Cox, 1991), but later cal-                    0.5
culations showed that by simply increasing the number
of states, the iterations can be stabilized sufficiently. In-                0
                                                                              0   10    20      30      40     50      60
dependent of the value of Ns , it is important to avoid any                                     N
symmetry breaking due to the truncation of states.
   In order to approach the non-Fermi liquid fixed point        FIG. 17 Flow diagram of the lowest lying many-particle levels
within only a few iterations, Cragg et al. (1980) and           for the isotropic two-channel Kondo model (even iterations
Pang and Cox (1991) used large values of the exchange           dashed curves, odd iterations full curves).
                                                                                                                       30

investigated in more detail in Yotsuhashi and Maebashi           The two-channel Anderson model investigated in
(2002), via the calculation of the impurity entropy and       Anders (2005) is connected to the two-channel Kondo
the crossover temperature.                                    model via a Schrieffer-Wolff transformation (note that
   Further investigations concerning the stability of         this only holds when the impurity degrees of freedom
the non-Fermi liquid fixed point have been per-               in the Anderson model are written in terms of Hub-
formed in Pang (1994) (flavor exchange coupling) and          bard operators which include the channel index). This
Kusunose and Kuramoto (1999); Kusunose et al. (1996)          connection is clearly visible in thermodynamic proper-
(effect of repulsion among conductions electrons and po-      ties, such as the zero-point entropy of 12 ln 2. Again,
tential scattering).                                          the single-particle dynamics (spectral function and self-
   A ‘pedestrian’ approach for the understanding of           energy) do not have a counterpart in the two-channel
the two-channel Kondo model was introduced by                 Kondo model. Concerning the results for the dynamic
Coleman et al. (1995). The authors of this work argued        susceptibility χ(ω) presented in Anders (2005), a com-
that the two conduction bands in the two-channel Kondo        parison to the corresponding results of the two-channel
model can be replaced by a single conduction band, with       Kondo model has not yet been done.
a coupling between impurity spin S to both spin σ and            There is an ongoing discussion about the observability
isospin τ of the conduction band. The isospin τ takes         of two-channel Kondo physics in experiments for a vari-
into account the charge degrees of freedom of the con-        ety of systems. Let us stress here that the instability of
duction band and the compactified ‘σ-τ ’ model takes the      the non-Fermi liquid fixed point itself does not exclude its
form                                                          observation. As for any system with a quantum critical
                                                              point, the corresponding anomalous properties dominate
                 εk c†kσ ckσ + J (S · σ + S · τ ) .
             X
        H=                                          (129)     a significant fraction of the finite-temperature phase di-
             kσ                                               agram (determined by the critical exponent) so that a
This model can be related to an Anderson-type model           precise tuning of the Hamiltonian parameters is not re-
(the ‘O(3)-symmetric’ Anderson model) via a Schrieffer-       quired. Nevertheless, two-channel Kondo physics is now
Wolff transformation (Coleman and Schofield, 1995).           mainly discussed within systems in which alternative de-
   It has been later verified with the NRG approach           grees of freedom (such as orbital quantum numbers) take
(Bulla and Hewson, 1997) that these compactified mod-         the role of spin or channel in the Hamiltonian Eq. (128);
els indeed show many of the anomalous non-Fermi liq-          one example is the quadrupolar Kondo model which is
uid properties of the two-channel Kondo model, although       discussed in detail in Cox and Zawadowski (1998).
these models do not allow for an overscreening of the            Here we want to briefly discuss NRG calculations
impurity spin. Furthermore, the structure of the non-         for two-channel Kondo physics in quantum dot systems
Fermi liquid fixed point has been studied in detail. It       (Anders et al., 2004, 2005; Lebanon et al., 2003a,b).
turns out that the many-particle spectrum of this fixed       Within a model of a quantum box coupled to the leads via
point is composed of single Majorana fermion excitations      a single-mode point contact (see Fig. 1 in Lebanon et al.
(Bulla et al., 1997a). This information can then be ex-       (2003b)), the physics at the degeneracy points of the
tended to the fixed point structure of the two-channel        Coulomb blockade staircase can be directly connected
Kondo model which can be described by two towers of ex-       to that of the two-channel Kondo model. Here the two
citations which are both composed of Majorana fermions,       charge configurations in the box play the role of the im-
see Sec. VIII in Bulla et al. (1997a).                        purity spin and the physical spin of the conduction elec-
   Naturally, we expect that the non-Fermi liquid prop-       trons corresponds to the channel index. For such a sys-
erties of the two-channel Kondo model are also visible in     tem, the NRG allows the non-perturbative calculation
its dynamic properties, but, unfortunately, detailed and      of the charge inside the box and the capacitance in the
comprehensive NRG calculations for the dynamics have          whole parameter regime. The results show, for example,
not been performed so far. Apart from a brief sketch of       that the shape of the charge steps is governed by the
the results for the T -matrix and the magnetic suscepti-      non-Fermi liquid fixed point of the two-channel Kondo
bility in Sakai et al. (1993a), the published data are only   model.
for models equivalent to the two-channel Kondo model             To conclude this section let us mention that there are
in certain limits.                                            models involving a more complicated orbital structure
   It has been argued in Bradley et al. (1999) that the       of the impurity – including, for example, excited crys-
dynamical spin-susceptibility χ(ω) of the compactified        talline electric field levels – which reduce to the two-
models introduced above is exactly equivalent to that         channel Kondo model in certain limits or which dis-
of the two-channel Kondo model, and that this equiva-         play non-Fermi liquid fixed points of the two-channel
lence holds for the full frequency range. The NRG-results     Kondo type. NRG-studies of such models can be found
show, for example, a ln(ω)-divergence of χ′ (ω) for ω → 0,    in Hattori (2005); Koga and Cox (1999); Koga and Shiba
in agreement with the results of Sakai et al. (1993a). On     (1995, 1996); Sakai et al. (1997). Overscreening can also
the other hand, there is no counterpart of the single-        be realized in single-channel models when the conduction
particle dynamics calculated by Bradley et al. (1999) in      electron spin exeeds the impurity spin, for a discussion of
the two-channel Kondo model.                                  this issue see for example Kim et al. (1997). We note also
                                                                                                                                   31

a recent study (Kolf and Kroha, 2006) showing an expo-              Here, s(Rl ) is the conduction electron spin density at
nential dependence of the Kondo scale on −1/JNF and                 the impurity site Rl and JK > 0 is the antiferromagnetic
−JNF , for small and large coupling cases respectively,             Kondo exchange. The first two terms in Eq. (130) are suf-
which may explain the absence of a broad distribution               ficient to generate an indirect RKKY interaction IRKKY
of Kondo scales in nanoconstrictions with two-channel               between the impurity spins. In some contexts a direct ex-
Kondo impurities.                                                   change interaction among the impurity spins of strength
                                                                    ID can arise (Jones and Varma, 1987)), so the last term
                                                                    has been added. The net effective exchange interaction
                                                                    between the spins is given by Ieff = ID + IRKKY and
C. Impurity quantum phase transitions
                                                                    can be either ferromagnetic Ieff < 0 or antiferromagnetic
                                                                    Ieff > 0. The properties of the model then depend solely
   In this section, we focus on models which, as a func-            on the ratio Ieff /TK , where TK is the single-ion Kondo
tion of one or more couplings in the model, give rise               scale, and the details of the dispersion relation εk . The
to a phase transition in the ground state. Typically,               model in Eq. (130) also arises in the Schrieffer-Wolff limit
this is due to a competition between the Kondo effect               (Schrieffer and Wolff, 1966) of the two-impurity Ander-
on the one hand, which tends to favor a strong-coupling             son model, which in the notation introduced in Eq. (2)
ground state with a screened or partially screened local            reads
moment, and some competing mechanism, which leads
to a ground state with a free or almost free local mo-                                                 2 X
                                                                                       εk c†kσ ckσ +                    †
                                                                                 X                     X
ment. In general, such phase transitions are termed ‘im-                  H =                                      εlσ flσ flσ
purity quantum phase transitions’ (for recent reviews, see                        kσ                   l=1     σ
Bulla and Vojta (2003); Vojta (2006)), as they are only                                2
                                                                                              †       †
                                                                                       X
observable in the impurity contribution to physical prop-                        +U          fl↑ fl↑ fl↓ fl↓
erties and not connected to possible phase transitions in                              l=1
the bulk to which the impurity couples.                                               2
                                                                                   1 X X  iRl ·k †            
   As impurity quantum phase transitions are usually                             +√         Vk e flσ ckσ + h.c.
                                                                                   N l=1 kσ
associated with a vanishing low-energy scale, the NRG
method is ideally suited to their investigation, allowing                        +ID S(R1 ) · S(R2 ) .                           (131)
their detection and characterization with very high ac-
curacy. This is most evident for continuous transitions             The motivation to study such two-impurity models origi-
where the critical exponents connected to the quantum               nally arose in the context of heavy fermions. In these sys-
critical point can only be calculated when a large range of         tems, the competition between the local Kondo exchange
energy or temperature scales is accessible. In this section         and the intersite RKKY interaction is expected to lead
we give an overview on NRG-results for multi-impurity               to a phase transition between non-magnetic and mag-
models (Sec. IV.C.1), models with locally critical behav-           netically ordered ground states as a function of Ieff /TK
ior (Sec. IV.C.2), and models with magnetic impurities              (Doniach, 1977). The nature of this quantum phase tran-
in superconductors (Sec. IV.C.3). Note that impurity                sition remains an open question in heavy fermion physics
quantum phase transitions are also observed in models               (v. Löhneysen et al., 2006). It is therefore of some in-
which are discussed in other sections of this review: the           terest to investigate the possibility of a transition in the
non-Fermi liquid fixed point of the two-channel Kondo               two-impurity problem as this might shed light on the
model Sec. IV.B can be viewed as a quantum critical                 physics of heavy fermions.
point when the control parameter ‘channel anisotropy’                  Jones et al. (1988) have established that such a phase
is tuned through zero; locally critical behavior is also            transition can occur under certain conditions, see be-
connected to models with coupling to a bosonic bath as              low, in the particle-hole symmetric two-impurity Kondo
discussed in Sec. IV.E.                                             model. This can be seen by considering the strong-
                                                                    coupling limits Ieff → ±∞ (Affleck et al., 1995). For
                                                                    Ieff → −∞ the two spins combine to form a spin S = 1
                                                                    interacting antiferromagnetically with two conduction
1. Multi-impurity physics                                           channels (characterized by even/odd parity) with, in gen-
                                                                    eral, energy dependent coupling strengths Je (k), Jo (k)
  An early extension of the NRG to more complex                     replaced in (Jones et al., 1988) by constants (see be-
systems was the study of the two-impurity S =                       low). The resulting two-stage Kondo effect progressively
1/2 Kondo model (Jones and Varma, 1987; Jones et al.,               screens the S = 1 spin down to a singlet and leads to a
1988), whose Hamiltonian is given by                                Fermi-liquid ground state characterized by phase shifts
                                                                    δe,o for electrons in the even/odd parity channels. The
                                    2                               assumed particle-hole symmetry and the nature of the
                 εk c†kσ ckσ + JK
           X                        X
     H=                                   S(Rl ) · s(Rl )   (130)   strong-coupling ground state ensures that these phase
            kσ                      l=1                             shifts will be exactly π/2 (Millis et al., 1990). In the
           +ID S(R1 ) · S(R2 ).                                     other limit, Ieff → ∞, the spins form an intersite sin-
                                                                                                                         32

glet S = 0 and the Kondo effect is absent so that the           mal even (e) and odd (o) parity states for the conduc-
phase shifts are exactly zero. Since the fixed points at        tion electrons. This results in more complicated interac-
Ieff = ±∞ are both stable and characterized by different        tion terms; in particular, one will obtain two exchange
(constant) phase-shifts, it follows that there can be an        couplings Je/o (k), with Je (k) 6= Jo (k) in general, which
unstable fixed point at some critical intermediate value        will depend on momentum or energy (Jones and Varma,
of the intersite exchange, Ic , at which the phase shifts       1987). The precise form of Je/o (k) will depend on the
change discontinuously. This phase transition has also          details of the band-structure of the conduction electrons.
been found in the particle-hole symmetric two-impurity          For free electrons in D = 3 it can be approximated as
Anderson model (Paula et al., 1999; Sakai and Shimizu,          (Jones and Varma, 1987; Sakai et al., 1990)
1992a). Jones et al. (1988) estimates Ic /TK ≈ 2.2.                                                      
The associated critical point has been characterized us-                                           sin kR
                                                                               Je/o (k) ≈ JK 1 ±             ,
ing conformal field theory (Affleck and Ludwig, 1992;                                                kR
Affleck et al., 1995) and bosonization (Gan, 1995), and
the physics is found to be similar to that of the two-          where R = |R1 − R2 |. Jones and Varma (1987) used
channel Kondo model. In particular, the staggered sus-          constant couplings Je/o (k) ≈ Je/o (kF ) to obtain for the
ceptibility, χs (T ), diverges logarithmically at low tem-      interaction part of the Hamiltonian (130)
perature and the residual entropy has the same√value as                           Xh                                    i
in the two-channel Kondo model S(T = 0) = ln 2 (Gan,               Hint = S(e) ·       Je c†eα σαβ ceβ + Jo c†oα σαβ coβ +
1995). In contrast C(T )/T = γ is predicted to remain fi-                         αβ
nite exactly at the critical point, in contrast to the behav-                      Xh p                        i
                                                                            S(o) ·   i Je Jo c†eα σαβ coβ + h.c +
ior in the two-channel Kondo model. Close to the critical
                                                                                  αβ
point, conformal field theory predicts γ ∼ (Ieff − Ic )−2 ,
in agreement with numerical results (Jones, 1990). The                      ID S(R1 ) · S(R)2 ,                       (132)
level structure of the fixed point at quantum criticality
agrees well with NRG calculations and is rather com-            where S(e/o) := S(R1 ) ± S(R2 ). The conduction elec-
                                                                tron Hamiltonian now consists of two decoupled linear
plex, exhibiting a hidden SO(7) symmetry (Affleck et al.,
1995).                                                          chains with even and odd parity symmetry. By neglect-
                                                                ing the energy dependence of the couplings an particle-
   For generic situations, the natural energy dependence        hole symmetric model results. This is the form used by
of Je/o obtained from transforming the Kondo model              Jones et al. (1988) to investigate the phase transition dis-
(130) or Anderson model (131) as described below in             cussed above. The results of retaining the full energy
Eq. (132), as well as a charge transfer term of the form        dependence of the couplings, using for example the for-
  P     †
t σ (f1σ  f2σ + h.c.) in the two-impurity Anderson model,       mulation of Sec. II, will be described below. We note
breaks particle-hole symmetry and destroys the criti-           here that from the NRG point of view the two-impurity
cal point (Affleck et al., 1995; Sakai et al., 1990). A         models (131) and (130) present a challenging task be-
similar charge transfer term involving conduction elec-         cause, as in the case of the two-channel Kondo model
trons has the same effect in the two-impurity Kondo             (128), the “impurity” now couples to two semi-infinite
model (Zaránd et al., 2006; Zhu and Varma, 2006). Po-          chains. Consequently, the Hilbert space grows by a fac-
tential scattering, if it does not induce charge transfer,      tor 16 in each NRG step. While this is still manage-
breaks particle-hole symmetry but may not affect the            able with modern computer resources, it is apparent that
critical point, for a discussion see Affleck et al. (1995);     larger clusters or more complex situations quickly become
Zaránd et al. (2006); Zhu and Varma (2006). Thus, in           too expensive to be treated with NRG with sufficient ac-
general the quantum phase transition discussed above            curacy, although the flow of the many-body eigenstates
will be absent in the two-impurity models (130) and             can still be used to identify fixed points and thus qual-
(131), although signatures of it might still be ob-             itatively describe the physics of more complicated sys-
servable as crossover behavior in various properties.           tems, like the two-channel two-impurity Kondo model
We note briefly here the case of Ising coupled spins            (Ingersent et al., 1992) and the three-impurity Kondo
ISz (R1 )Sz (R2 ). In this case, the ground state for large I   model (Ingersent et al., 2005). In high-symmetry situ-
will be doubly degenerate as compared to that for small         ations even a calculation of thermodynamical quantities
I where the Kondo effect screens the individual spins to        has been performed recently for three-impurity models
singlets, so a quantum phase transition separating these        (Žitko and Bonča, 2006a). However, for a reliable calcu-
two different ground states arises and is found to be of        lation of dynamics or in situations with less symmetries
the Kosteritz-Thouless type (Garst et al., 2004).               in the system – e.g. in an external magnetic field – ad-
   In order to formulate Eq. (130) or (131) as a linear         ditional tools like the ones described in section III.A.4
chain problem for treatment with the NRG, one needs             allowing one to work with large Λ ≫ 1 and so maintain
an orthonormal basis set. The local conduction electron         low truncation errors should be useful.
states on the impurity sites in Eq. (130) are not orthog-          The generic two-impurity Anderson model (131), in-
onal. Following Jones and Varma (1987), the Kondo ex-           cluding a charge transfer term, has been studied by Sakai
change part of Eq. (130) is rewritten in terms of orthonor-     and coworkers (Sakai and Shimizu, 1992a,b; Sakai et al.,
                                                                                                                        33

1990) using the NRG. Single particle and magnetic exci-         the RKKY exchange IRKKY = IFM is ferromagnetic,
tation spectra were calculated and in the case of particle-     with |IRKKY |/TK ≫ 1 and a two-stage screening scenario
hole symmetry, Sakai et al. (1993a) showed that on pass-        arises: First, the system locks into an S = 1 state at high
ing through the transition, a peak in the impurity single-      temperatures due to the RKKY interaction. In the in-
particle spectra sharpened at Ieff = Ic into a cusp             termediate temperature regime this triplet is screened to
and turned into a dip for Ieff > Ic . In the generic            a doublet via the even channel, which then is further
case, the regime with Kondo screening, |Ieff | ≪ TK ,           screened to a singlet by the odd channel. Finally, for
and the non-local singlet regime, Ieff ≫ TK , are con-          kF R = π, the RKKY exchange IRKKY = IAFM is anti-
nected via a smooth crossover (Campo, Jr. and Oliveira,         ferromagnetic with IRKKY /TK ≫ 1 and a non-local sin-
2004; Sakai and Shimizu, 1992a,b; Sakai et al., 1990;           glet is formed eventually. Similar results for entropy and
Silva et al., 1996).                                            specific heat of the two-impurity Kondo model, exhibit-
   Results from thermodynamic calculations are shown            ing a smooth change of physical properties with changing
in Fig. 18 for the squared effective magnetic moment            IRKKY , can be found in Campo, Jr. and Oliveira (2004).
taken from Silva et al. (1996) for the two-impurity Kondo          We note, here, that while two-impurity models with
model with ID = 0. In these calculations Ieff = IRKKY           energy independent coupling constants are crude ap-
and the energy dependence of Je/o (k) is crucial to gen-        proximations in the context of bulk Kondo impuri-
erate the intrinsic RKKY exchange interaction IRKKY .           ties and heavy fermions, these can, however, be re-
Using the result for free electrons in three dimensions         alized in quantum dots. Correspondingly, they have
(Sakai et al., 1990), an approximate formula for the en-        been proposed to describe various extensions of sin-
ergy dependence of the coupling constants is (Silva et al.,     gle quantum dots and studied in this context with
1996)                                                           NRG by several groups (Boese et al., 2002; Borda et al.,
                                                              2003; Hofstetter and Schoeller, 2002; Vojta et al., 2002a;
                           sin [kF R (1 + ǫ)]                   Zaránd et al., 2006; Žitko and Bonča, 2006b) over the
       Je/o (ǫ) = JK 1 ±                             (133)
                              kF R (1 + ǫ)                      past years.       Since modern nanostructure technol-
                                                                ogy permits a rather broad tailoring of such meso-
with ǫ ∈ [−1, 1], kF the Fermi momentum of the conduc-          scopic objects, the models discussed typically in-
tion states. For the derivation of Eq. (133) a linearized       troduce additional interactions as compared to the
dispersion relation ǫk ≈ kDF (k − kF ) was assumed and          conventional two-impurity Anderson model (131) like
D = 1 used as energy scale.                                     capacitive couplings (Boese et al., 2002; Borda et al.,
   Dependent on the value of kF R, different regimes can        2003; Hofstetter and Schoeller, 2002) or direct hopping
then be identified (see, for example, Fig. 18): For kF R →      (Dias da Silva et al., 2006; Žitko and Bonča, 2006b).
                                                                Consequently, these extended models show a much
                                                                larger variety in intermediate- and low-temperature
                                                                fixed points than the bare model (131), ranging
                                                                from conventional Kondo effect over a two-stage
                                                                Kondo effect (Jayaprakash et al., 1981; Vojta et al.,
                                                                2002a), two-channel physics as intermediate fixed-
                                                                point (Žitko and Bonča, 2006a,b) to quantum-phase
                                                                transitions (Vojta et al., 2002a; Zaránd et al., 2006;
                                                                Zhu and Varma, 2006; Žitko and Bonča, 2006b).


                                                                2. Local criticality

                                                                   The term ‘local criticality’ has been first used in the
                                                                context of phase transitions in certain heavy fermion
                                                                systems, such as CeCu6−x Aux (Si et al., 2001, 1999;
                                                                v. Löhneysen et al., 2006). It has been argued that the
FIG. 18 Effective local moment µ2 (T ) := T · χimp (T ) for     quantum critical point separating the magnetically or-
the two-impurity Kondo model (131) for the three regimes        dered and the paramagnetic phases at T = 0 is charac-
described in the text. Figure taken from Silva et al. (1996).   terized by critical excitations which are local. This ob-
The arrows indicate the Kondo scale TK = 1.4 × 10−4 , and       servation raised a considerable interest in models which
the RKKY interactions for ferromagnetic (IFM = −8 × 10−3 ))     show such locally critical behavior: these are either lat-
and atiferromagnetic cases (IAFM = 3 × 10−3 ).                  tice models studied within certain extensions of DMFT
                                                                (see also Sec. V.B) or impurity models as discussed in this
∞ we have IRKKY = 0, single-impurity physics domi-              section. Such impurity models might not be directly con-
nates and no non-local magnetic exchange is generated,          nected to the locally critical behavior in heavy fermion
as expected (Jones and Varma, 1987). For kF R = π/2,            systems, nevertheless, the insights gained in studying im-
                                                                                                                            34

purity models might be helpful in constructing theories       fixed points is particularly complex in the asymmetric
for lattice systems (for a general discussion of the rela-    case, see, for example, the schematic flow diagrams of
tion between quantum impurity physics and the physics         Fig. 16 in Gonzalez-Buxton and Ingersent (1998).
of lattice systems, see Bulla (2006)).                           The impurity spectral function of the symmetric soft-
   Let us focus here on the soft-gap Anderson model,          gap Anderson model was first investigated in Bulla et al.
originally proposed by Withoff and Fradkin (1990). The        (1997b): the spectral function shows a divergence A(ω) ∝
Hamiltonian is the same as the one for the standard           |ω|−r for both the SC and quantum critical phases
single-impurity Anderson model Eq. (2), but the hy-           whereas it goes as A(ω) ∝ |ω|r in the LM phase (for
bridization function is assumed to have a power-law form      the behavior in the asymmetric case, see the discussion
                                                              in Sec. IV.C.3).
            ∆(ω) = ∆0 |ω|r    with r > −1 ,          (134)       In the symmetric SC phase, the product F (ω) =
                                                              c|ω|r A(ω) (where the prefactor cancels the divergence in
either valid over the whole frequency range or restricted
                                                              the spectral function) contains a generalized Kondo res-
to some low-frequency region. The competing mech-
                                                              onance at the Fermi level with a pinning of F (ω = 0)
anisms leading to a quantum phase transition in this
                                                              (for a properly chosen constant c) and a width that goes
model are local moment formation (favored by increas-
                                                              to zero upon approaching the quantum critical point.
ing U ) and screening of the local moments. For values of
                                                              This feature, together with the scaling properties and the
the exponent r > 0, corresponding to a soft-gap in ∆(ω),
                                                              low-energy asymptotics has been discussed in detail in
there are less degrees of freedom available to screen the
                                                              Bulla et al. (2000), based on both the results from NRG
moment and a quantum phase transition occurs at some
                                                              and from the local moment approach (also described ear-
finite value of ∆0 .
                                                              lier in Logan and Glossop (2000)).
   This quantum phase transition and the physical prop-
                                                                 Dynamical properties at the quantum critical point
erties in the whole parameter regime have been studied
                                                              are particularly interesting: Ingersent and Si (2002) have
in detail with a variety of techniques (for an overview,
                                                              shown that the dynamical susceptibility at the criti-
see Bulla and Vojta (2003); Vojta (2006) and the intro-
                                                              cal point exhibits ω/T -scaling with a fractional expo-
ductory parts in Lee et al. (2005)). The NRG method
                                                              nent, similar to the locally critical behavior in the heavy
has been particularly helpful to clarify the physics of the
                                                              fermion systems mentioned above. This result also im-
soft-gap Anderson model (and the related Kondo version
                                                              plies that the critical fixed point is interacting, in contrast
of the model) as we shall briefly discuss in the following.
                                                              to the stable fixed points (SC and LM) which both can be
The technical details necessary to apply the NRG to the
                                                              composed of non-interacting single-particle excitations.
soft-gap Anderson model have already been introduced
                                                                 The interacting fixed point of the symmetric soft-gap
in Sec. II, see also Bulla et al. (1997b).
                                                              model has been further analyzed in Lee et al. (2005).
   Thermodynamic and static properties of the var-
                                                              The general idea of this work can be best explained with
ious phases of the soft-gap Anderson and Kondo
                                                              Fig. 19 which shows the dependence of the many-particle
models have been presented in Chen and Jayaprakash
                                                              spectra for the various fixed points on the exponent r.
(1995a), Ingersent (1996), Bulla et al. (1997b), and
Gonzalez-Buxton and Ingersent (1998).          The most                 4.0     QCP
comprehensive review of these results is given in                               LM
Gonzalez-Buxton and Ingersent (1998). This paper cov-                           SC

ers the discussion of thermodynamic properties and the                  3.0
analysis of the various fixed points also for the under-
                                                                   EN




screened spin-1 Kondo model and the (overscreened) two-
                                                                  N/2




                                                                        2.0
channel Kondo model (both with a soft-gap in the con-
                                                                  Λ




duction electron density of states).
   The key role of particle-hole symmetry has been iden-                1.0
tified in Ingersent (1996) and investigated in more detail
in Gonzalez-Buxton and Ingersent (1998). As shown, for
                                                                        0.0
example, in Fig. 5 in this work, the line of quantum                      0.0    0.1      0.2       0.3      0.4      0.5
                                                                                                r
critical points separating the local moment (LM) and
strong-coupling (SC) phases is restricted to 0 < r < 1/2      FIG. 19 Dependence of the many-particle spectra for the
in the particle-hole symmetric case (for r > 1/2, only        three fixed points of the particle-hole symmetric soft-gap An-
the LM phase exists). This is different in the asym-          derson model on the exponent r: SC (dot-dashed lines), LM
metric case where transition line extends up to r → ∞.        (dashed lines), and the (symmetric) quantum critical point
Particle-hole symmetry also influences the physical prop-     (solid lines). (Figure adapted from Lee et al. (2005)).
erties of the various fixed points. The symmetric SC
fixed point, for example, shows a residual magnetic mo-          For the limits r → 0 and r → 1/2, the many-particle
ment of χimp = r/(8kB T ) and a residual entropy of           spectra of the quantum critical point approach those of
Simp = 2rkB ln 2, whereas both values are zero in the         the LM and SC fixed points, respectively. The devia-
asymmetric SC fixed point. The appearance of unstable         tions and splittings of the spectra at the quantum critical
                                                                                                                        35

point close to these limits can then be understood from      the conduction electrons. We therefore expect a quantum
a proper perturbational analysis using suitable marginal     phase transition from a screened phase to a local moment
operators. Information on these operators can be ex-         phase upon increasing the value of the superconducting
tracted from epsilon-expansion techniques, as shown in       gap, ∆, similar to the phase transitions in the soft-gap
Lee et al. (2005).                                           (and hard-gap) impurity models discussed in Sec. IV.C.2.
   The case of negative exponents in the hybridization       In fact, a relation between impurity models in supercon-
function, ∆(ω) ∝ |ω|r with −1 < r < 0, where the soft-       ductors and those in metallic hosts with a soft or hard
gap turns into a divergence at the Fermi level, has been     gap can be established as discussed below.
analyzed in Vojta and Bulla (2002a) in the context of the      The first applications of the NRG to magnetic im-
Kondo model with both ferromagnetic and antiferromag-        purities in superconductors focused on the s-wave case
netic values of J. The behavior of this class of models      (Sakai et al., 1993b; Satori et al., 1992), with the stan-
turns out to be rather complex, see the schematic flow       dard Kondo Hamiltonian Eq. (115) supplemented by the
diagrams of Fig. 1 in this work. A remarkable feature        BCS pairing interaction
here is the appearance of a stable intermediate coupling                        X † †                  
fixed point with universal properties corresponding to a                    −∆       ck↑ c−k↓ + c−k↓ ck↑ .
fractional ground-state spin.                                                    k
   The case of a hard gap in the hybridization function,
                                                             Several strategies have been developed to transform the
that is ∆(ω) = 0 within a certain gap region around the
                                                             Hamiltonian including the BCS-term onto a semi-infinite
Fermi level, can be viewed as the r → ∞-limit of the
                                                             chain which can then be diagonalized iteratively in the
soft-gap case, provided the powerlaw is restricted to the
                                                             usual way. Satori et al. (1992) performed a sequence
gap region |ω| ≤ Eg /2, with Eg the width of the gap.
                                                             of transformations, including a Bogoliubov and a par-
   From a technical point of view, two different strate-
                                                             ticular particle-hole transformation, to map the original
gies have been developed to apply the NRG to the hard-
                                                             model onto a Hamiltonian which conserves particle num-
gap case. Takegahara et al. (1992) and Takegahara et al.
                                                             ber (this is somewhat easier for the numerical implemen-
(1993) considered the case of a small but finite value of
                                   ¯ for |ω| ≤ Eg /2, and    tation though not absolutely necessary). The approach
∆(ω) in the gap region, ∆(ω) = ∆
                                                ¯ → 0. In    in Sakai et al. (1993b) leads to the same Hamiltonian, the
based their conclusions on the extrapolation ∆
                                                             difference here is that the Bogoliubov transformation is
this approach, the standard NRG for non-constant hy-
                                                             performed before the logarithmic discretization. In both
bridization functions as described in Sec. II can be ap-
                                                             cases, the semi-infinite chain contains a staggered poten-
plied.
                                          ¯ is set to zero   tial of the form
   If, on the other hand, the value of ∆
                                                                              ∞
from the outset, the NRG approach has to be modified.                                                     
                                                                                  (−1)n c†n↑ cn↑ + c†n↓ cn↓ .
                                                                              X
As discussed in Chen and Jayaprakash (1998), the loga-                   −∆
rithmic discretization of a ∆(ω) with a hard gap results                      n=0

in a discretized model which maps onto a chain with a        This term does not fall off exponentially as the other
finite number of sites, M , with Eg of the order of Λ−M .    terms in the chain-Hamiltonian so that the NRG-
The iterative diagonalization then has to be terminated      iterations should be terminated a few steps after the
at site M . Thermodynamic properties at temperatures         characteristic scale ωN of the chain Hamiltonian HN has
T < Eg can nevertheless be computed using the Hamil-         reached the superconducting gap ∆. This procedure still
tonian of the final iteration (see Chen and Jayaprakash      allows to access the properties of the localized excited
(1998) where also a variety of correlations functions have   state within the energy gap whose position and weight
been calculated for both the Kondo and the Anderson          can now be determined in the full parameter space (in
model with a hard gap).                                      contrast to previous investigations, see the references
   Certain features of the soft-gap case with finite r       in Satori et al. (1992)). Figure 20 shows position and
are also visible in the fully gapped case. As expected       weight of the localized excited state as a function of TK /∆
from the discussion above, there is no transition in the     (TK is determined from the corresponding Kondo model
particle-hole symmetric case, but a transition exists as     with ∆ = 0). The position changes its sign when TK
soon as one is moving away from particle-hole sym-           is of the order of ∆ (the precise value depends on the
metry (Chen and Jayaprakash, 1998; Ingersent, 1996;          model), corresponding to a change of the ground state
Takegahara et al., 1992). This transition turns out to       from doublet for small TK /∆ to singlet for large TK /∆.
be of first order.                                           This quantum phase transition can be characterized as a
                                                             level crossing transition (see Fig. 5 in Satori et al. (1992))
                                                             and is not connected to quantum critical behavior.
3. Kondo effect in superconductors                              These studies of impurities in s-wave superconductors
                                                             have been later extended to more complex impurity mod-
  Let us now consider magnetic impurities in supercon-       els. Yoshioka and Ohashi (1998) investigated the case of
ducting hosts. In this case, the screening of the mag-       an anisotropic interaction between impurity and conduc-
netic moments competes with Cooper pair formation of         tion electron spin, with basically the same NRG approach
                                                                                                                           36

                                                                   lar sequence of transformations as in the s-wave case is
                                                                   applied to impurity models in p- or d-wave superconduc-
                                                                   tors.
                                                                      Matsumoto and Koga (2001, 2002) considered the
                                                                   Kondo model with a coupling of the impurity spin to
                                                                   superconductors with px + ipy and dx2 −y2 + idxy symme-
                                                                   try (with extensions to spin-polarized superconducting
                                                                   states investigated in Koga and Matsumoto (2002a) and
                                                                   to S = 1 impurities in Koga and Matsumoto (2002b)).
                                                                   The quasiparticle density of states in these cases also
                                                                   shows a full gap, as for s-wave superconductors, but the
                                                                   sequence of transformations now results in a model with
                                                                   a coupling of the impurity to two angular momenta of
                                                                   the conduction electrons. NRG calculations for this two-
                                                                   channel model give a ground state which is always a spin
FIG. 20 Position Eb and weight (intensity) of the localized
                                                                   doublet for arbitrary values of TK /∆, in contrast to the
excited state as a function of TK /∆ for the Kondo model in an
s-wave superconductor. At TK /∆ ≈ 0.2, the position changes        s-wave case, and no level crossing is observed. This is
its sign and the weight jumps by a factor of 2, see also Fig. 2A   supported by calculations of the impurity susceptibility
in Sakai et al. (1993b).                                           which show that the effective magnetic moment is always
                                                                   finite, although strongly reduced with increasing TK /∆
                                                                   (Matsumoto and Koga, 2002). The authors of this work
                                                                   argued that the orbital dynamics of the Cooper pairs is
as in Sakai et al. (1993b). The phase diagram of this
                                                                   responsible for the ground state spin.
model turns out to be much more complex than the one
for the isotropic case. For example, two localized excited            This interpretation has been questioned in
states with different energies appear in certain regions of        Fritz and Vojta (2005), where is was shown that,
the parameter space.                                               indeed, the local quasiparticle density of states of the
                                                                   superconductor is the only necessary ingredient in
   Yoshioka and Ohashi (2000) considered the Anderson              a number of cases, in particular for unconventional
version of the impurity model with coupling to an s-               superconductors. Applied to the model studied in
wave superconductor. From a technical point of view,               Matsumoto and Koga (2001), this means that the
this case is different to the corresponding Kondo model            results of the NRG calculations for the effective two-
since the sequence of transformations used in, for exam-           channel model can also be understood from a single-band
ple, Sakai et al. (1993b) now produce an extra impurity            calculation where screening is absent for a hard-gap
term of the form δ(f↑† f↓† + h.c.), so that the whole Hamil-       density of states and particle-hole symmetry.
tonian does no longer conserve charge (note that the pa-              The results of Fritz and Vojta (2005) also have impor-
rameter δ is zero for the particle-hole symmetric case).           tant consequences for the study of impurities in uncon-
The results for the Kondo regime of this model are, as             ventional superconductors with dx2 −y2 symmetry. In this
expected, the same as those obtained previously, but the           case, the mappings which have been used for the models
approach of Yoshioka and Ohashi (2000) also allows to              discussed above result in an impurity model with cou-
study other parameter ranges of the model, such as the             pling to infinitely many bands to which the NRG clearly
mixed valent regime.                                               cannot be applied. For certain geometries, however, it
   It is important to note here that the final Hamiltonian         is sufficient to consider only the quasiparticle density of
used in Satori et al. (1992) and Sakai et al. (1993b) for          states which, for a point-like impurity, shows a soft-gap
the NRG iteration is the same as the one for an impurity           with exponent r = 1.
in a non-superconducting host with a gapped density of                This simplification has already been used earlier in
states (which corresponds to the quasiparticle density of          Vojta and Bulla (2002b) (at that time it has been ar-
states of the superconductor). In addition, the sequence           gued to be a reasonable approximation). The results
of transformations also generates a potential scattering           of this work are therefore both valid for the soft-gap
term. In the light of the results for the hard-gap impu-           Kondo model and for impurities in d-wave superconduc-
rity models (Sec. IV.C.2) this potential scattering term           tors. Vojta and Bulla (2002b) have motivated their in-
is essential to observe the quantum phase transition from          vestigations with experimental results for non-magnetic
a screened to an unscreened phase.                                 impurities in cuprate superconductors which have been
   The question now arises, whether the quasiparticle              seen to generate magnetic moments. As discussed in
density of states can be used as the sole bath charac-             this work, an effective model for this problem then takes
teristic (possibly supplemented by a potential scattering          the form of a Kondo model in a d-wave superconductor.
term) in more general situations, such as impurities in            Connections to experimental results can indeed be made
unconventional superconductors. Before we address this             within this framework. For example, the T -matrix T (ω)
issue, let us have a look at what happens when a simi-             displays a very narrow peak at finite frequencies with the
                                                                                                                         37

peak energy corresponding to the energy scale which van-       rity and they usually give rise to finite spin and orbital
ishes at the quantum phase transition from a screened to       magnetic moments. Thus, a realistic description of such
an unscreened moment. A very similar peak has been             impurities in solids, requires taking both spin and or-
observed in STM-experiments.                                   bital magnetic moments into account. The same is true
   This work has been later extended in Vojta et al.           for the compounds of transition metal, rare-earth and ac-
(2002b), where the effects of local and global magnetic        tinide elements, where the interplay of orbital and spin
fields have been investigated. For the case of a local field   degrees of freedom gives rise to very rich phase diagrams
hloc , the quantum phase transition for zero field persists    (Imada et al., 1998). Among the methods to theoreti-
for hloc 6= 0, but for a global field, the quantum phase       cally study the properties of these materials, the dynam-
transition turns into a sharp crossover since the global       ical mean-field theory (see Sec. V) has become a stan-
field induces a finite spectral weight at the Fermi level.     dard approach. Since in this approach one ends up with
   The investigations described so far are mainly applica-     an effective quantum impurity problem which retains the
ble to impurities in the bulk or on the surface of a super-    full local orbital and spin structure of the original lattice
conducting host. A different geometry is realized in quan-     system, the development of a reliable method to solve
tum dot systems (see Sec. IV.A.3). For superconducting         quantum impurity models with orbital and spin degrees
leads, such a setup introduces a new control parameter to      of freedom is of crucial importance.
the problem, that is the phase difference, Φ = ΦL − ΦR ,          In this section we, therefore, discuss the application of
between the phases of the two superconducting leads.           the NRG to situations where orbital and spin degrees of
The resulting Josephson current, in particular the tran-       freedom are both present. Some orbital effects in quan-
sition from 0- to π-junction behavior, has been studied        tum dots have been discussed in Sec. IV.A.3 and will
in detail in Choi et al. (2004a) and Oguri et al. (2004).      be discussed further below. The appropriate model is
   Choi et al. (2004a) investigated various static and dy-     again a suitable extension of the single-impurity Ander-
namic properties for this geometry with identical s-wave       son model (2) and is given by
superconductors as the two leads. For zero phase differ-                                  ′†
                                                                          X X
ence, Φ = 0, the local pairing correlation shows a sign           H =                 ǫmm
                                                                                       kσ ckmσ ckm′ σ
change at TK /∆ ≈ 0.42. Physically, this is connected to                   k mm′ σ
the same quantum phase transition as described above                          X             U X f f
since for Φ = 0 and identical leads the model can be                      +       εmσ nfmσ +      n n
                                                                            mσ
                                                                                             2 mσ mσ mσ̄
mapped onto the same model as discussed in Satori et al.
(1992). For finite phase difference (or for non-identical                   2U ′ − J X X f
                                                                          +                    nimσ nfim′ σ′
leads) the system remains a two-channel problem and                             4
                                                                                     m6=m′ σσ′
the NRG analysis is more complicated. Nevertheless, de-
                                                                                         ~f ′
                                                                                    ~f · S
                                                                              X
tailed information on ground state properties such as the                 −J        S m    m
single-particle excitation spectrum have been obtained in                     m6=m′
Choi et al. (2004a) and interpreted as a phase-dependent                   J X X † †
formation of Andreev bound states.                                        −           fmσ fmσ̄ fm′ σ̄ fm′ σ
                                                                           2
                                                                              m6=m′ σ
   In Oguri et al. (2004), the Hamiltonian of an An-
derson impurity coupling to two superconducting leads                        1 X X  mm′ †                    
                                                                          +√             Vkσ ckmσ fm′ σ + h.c. ,
has been considerably simplified by studying the limit                       N k mm′ σ
|∆L | ≫ |∆R | in which the model can be mapped exactly
                                                                                                                      (135)
onto a single-channel one with an extra superconducting
gap on the impurity. Results for this limit show that the      where m labels the orbital degrees of freedom, and nfmσ =
phase difference changes both the energy and the wave                         ~m
                                                                †               f
                                                                                  = 21
                                                                                       P †
                                                               fmσ fmσ , with S          fmα~σαβ fmβ . In addition to the
function of the bound state. In particular, the phase dif-                               αβ
ference appears to work against the screening of the local     intra-orbital Coulomb term U also occurring in (2), the
moment.                                                        following interaction terms are present now: An inter-
                                                               orbital Coulomb repulsion U ′ and an exchange term J.
                                                               The exchange term we have split in accordance with stan-
D. Orbital effects                                             dard notation (Imada et al., 1998) into a Heisenberg-like
                                                               spin-exchange term (Hund’s coupling) and an orbital ex-
1. Multi-orbital Anderson model                                change term. To account for the proper combination of
                                                               operators in the general exchange contribution, an addi-
  The physics of the Kondo effect requires the existence       tional part proportional to J appears in the inter-orbital
of local magnetic moments, as realized, for example, in        Coulomb term. For free atoms, rotational invariance usu-
systems with open d or f shells, such as transition metal      ally imposes U ′ = U − 2J as constraint for the different
or rare-earth impurities in non-magnetic host metals. For      Coulomb parameters (Imada et al., 1998). Further mod-
such systems, the local Coulomb correlations and Hund’s        ifications to the model (135) can be made, to take into
exchange determine the electronic structure of the impu-       account, for example, spin-orbit and crystal-field effects.
                                                                                                                            38

   The mapping of (135) onto a linear-chain model, see            1990). Since the SU (N ) model has a large degeneracy
Eq. (26) of Sec. II, clearly leads to m semi-infinite con-        of the individual levels, it allows for a considerable re-
duction chains coupled to the local Hamiltonian, which            duction of the sizes of the individual Hilbert spaces in
in turn means that at each step of the iterative diagonal-        the diagonalization. This enabled the authors to use
ization, the Hilbert space increases by a factor 4m . For         the NRG to calculate physical properties including dy-
large m, this exponential increase in the number of states        namical quantities and to study, for example, the de-
makes the NRG truncation scheme useless, because the              velopment of the Kondo temperature or the behavior of
number of states one can keep is way too small to al-             the Abrikosov-Suhl resonance as function of degeneracy
low for a reasonable accuracy. Thus, calculations for the         (Sakai et al., 1989; Shimizu et al., 1990). Similar inves-
model (135) involving a full d shell (m = 5), or even a full      tigations for the model (135) with fixed orbital degen-
f shell (m = 7), and taking into account all interactions         eracy m = 2 in the presence of a magnetic field were
seem to be impossible.                                            presented in the work by Zhuravlev et al. (2004), a com-
   In practice, however, one is typically not interested in       parison with STM experiments for Cr(001) surface states
rotationally invariant situations, as described by (135),         by (Kolesnychenko et al., 2005), and a detailed study
but in situations where the impurity is embedded in the           of the dependence of the low-energy properties of the
crystalline environment of a solid. The reduced point-            multi-orbital Anderson model for m = 2 with J > 0
group symmetry due to the crystalline electric field, then        by Pruschke and Bulla (2005). Furthermore, from the
leads to a splitting of the orbital degeneracy. The en-           fixed-point level structure, interesting information about
ergy associated with this crystal-field splitting can be          quantities like “residual interactions” in the heavy Fermi
much larger than the temperatures one is interested in            liquid state can be extracted (Hattori et al., 2005). In
experiments, for example in 3d transition metals. Fur-            particular for an f 2 ground state – as possibly realized
thermore, the local Coulomb interaction can lead to a             in uranium compounds – a subtle enhancement of in-
localization of electrons in the lower crystal-field multi-       terorbital interactions can be observed (Hattori et al.,
plets, as happens, for example, in the case of manganese          2005), which can lead to superconducting correlations in
in a cubic environment (Imada et al., 1998). In this case,        a triplet channel when used as effective interaction in a
these states form a localized spin according to Hund’s            model for heavy-fermion superconductivity.
rules. For manganese, for example, this results in a high-           While these studies deal with the conventional
spin state (S = 3/2) of the threefold degenerate t2g or-          Kondo effect in multi-orbital models, it was noted
bitals, which couples ferromagnetically to the twofold de-        (Cox and Zawadowski, 1998) that for higher rare-earth
generate eg electrons. Thus, the actual number of rele-           and actinide elements the orbital structure in connec-
vant orbitals, and thus the number of semi-infinite chains        tion with spin-orbit coupling and crystal-field effects can
coupling to the local Hamiltonian, may be considerably            result in an orbital multiplet structure that leads to
reduced. Similar effects can be observed in the higher            the two-channel Kondo effect (see Sec. IV.B). Multi-
rare-earth elements, for example in gadolinium.                   orbital models of that type were studied by Sakai et al.
   In case the local point-group symmetry is reduced suf-         (1996), Shimizu et al. (1998), Shimizu et al. (1999a,b),
ficiently, one may, in fact, be left with a localized spin S      Koga (2000) and Hattori and Miyake (2005), covering a
coupled to a single spin-degenerate, correlated orbital hy-       wide range of aspects possibly realized in actinide heavy-
bridizing with conduction states. This Kondo-Anderson             fermion systems. The authors could identify parame-
model is given by (2) supplemented with the ferromag-             ter regimes where non-Fermi liquid properties related to
netic exchange term −JH S   ~ · ~sd , with ~sd the spin-density   the two-channel Kondo effect can be observed and could,
of the correlated level in the Anderson model. Such               in addition, identify relevant symmetry breakings like
a Kondo-Anderson model was studied by Sakai et al.                crystal-field splittings or external fields that eventually
(1996) and Peters and Pruschke (2006) and shown to ex-            lead to conventional Kondo physics below a tempera-
hibit different types of screening, ranging from conven-          ture scale connected to the energy scale of the symmetry
tional Kondo screening to two-stage screening and local           breaking.
singlet formation or two-channel Kondo effect.                       As mentioned in the introductory remarks of this sec-
                                                                  tion, the crystal-field splitting is usually much larger than
                                                                  the relevant low-energy scales. However, this does not
2. NRG calculations – an overview                                 need to be true in general. Besides uranium-based com-
                                                                  pounds (Kusunose, 2005), a possible example where the
  A first serious attempt to study effects of true orbital        crystal-field splitting can actually be of the order of the
degeneracy with NRG can be found in Sakai et al. (1989).          Kondo scale is Ce1−x Lax Ni9 Ge4 (Scheidt et al., 2005).
However, the authors did not study the full Hamiltonian           For higher temperatures, the ground state seems to be
(135), but a SU (N ) version of it, using values of N rang-       a quadruplet, i.e. it can be described by a multi-orbital
ing from two (i.e. the standard single-impurity Anderson          Anderson model with m = 2. The states building this
model (2)) to five, representative for rare-earth ions like       quadruplet are obtained from spin-orbit coupled f states,
samarium or thulium in solids under the influence of a            which results in different g-factors for its members. Inter-
crystalline field (Allub and Aligia, 1995; Shimizu et al.,        estingly, these different g-factors in connection with the
                                                                                                                                          39

small crystal-field splitting can lead to a behavior, where    ory, the authors could deduce the residual entropy as
specific heat and susceptibility seem to have different low-                                 "√       #
energy scales (Scheidt et al., 2005). However, this dis-                                 1      5+1
crepancy can be resolved by observing that the difference                    S(T = 0) = ln √            ,
                                                                                         2      5−1
in g-factors leads to a “protracted” screening behavior for
the specific heat in NRG calculations, while the system as     and also corresponding fractional values for the local
a whole has only one, but strongly reduced Kondo tem-          spectral function ρf (0) at the Fermi energy, which leads
perature. In addition, NRG results for the low-energy          to non-unitary values in the conductance, and a non-
spin dynamics show an anomalous energy dependence,             integer power law for ρf (ω) − ρf (0). Away from half
which again is related to the difference in the g-factors      filling a quantum phase transition between Kondo screen-
entering the local susceptibility (Anders and Pruschke,        ing and local singlet formation as function of filling oc-
2006).                                                         curs (De Leo and Fabrizio, 2005). Multi-orbital models
   Conventionally, the Hund’s exchange J appearing in          also arise in the context of quantum dots as described in
(135) is positive, i.e. mediating a ferromagnetic inter-       Sec. IV.A.3 and Sec. IV.C.1.
action leading to Hund’s first rule. However, there
may be circumstances, for example a coupling to vibra-
tional modes, Jahn-Teller distortions or crystal-field in-     3. Selected results on low-energy properties
duced anisotropies (De Leo and Fabrizio, 2004), which
can lead to an effective J < 0, i.e. antiferromagnetic           In the following we shall present some selected results
exchange. In this case we encounter a situation simi-          for the properties of the multi-orbital Anderson model
lar to the multi-impurity problem (see section IV.C.1),        (135) with orbital degeneracy m = 2.
where the exchange was generated by the RKKY effect.
Under special conditions, an antiferromagnetic exchange
then could lead to a quantum phase transition between          a. Effect of Hund’s coupling  As a first example we want
Kondo screening and non-local singlet formation. Con-          to discuss the influence of Hund’s exchange J on the low-
sequently, one may expect a similar transition for the         energy properties of the model Eq. (135). We consider
multi-orbital model, too, when one varies J from the           only J ≥ 0, i.e. the usual atomic ferromagnetic exchange,
ferromagnetic to the antiferromagnetic regime. Such a          and in addition use the constraint U ′ = U − 2J. For the
model was studied by Fabrizio et al. (2003) and, with an       conduction electrons we assume a band with a flat density
additional single-ion anisotropy, by De Leo and Fabrizio                  (0)
                                                               of states ρc (ǫ) = NF Θ(D −|ǫ|) and use ∆0 = πV 2 NF as
(2004) for two orbitals, i.e. m = 2. The model indeed          energy scale. Results for thermodynamic quantities are
shows the anticipated quantum phase transition, which          shown in Fig. 21. The calculations are for U/∆0 = 16π
in this case is driven by the competition between the
local antiferromagnetic exchange coupling and the hy-
bridization to the band states. Furthermore, one can                                    m=1
                                                                                        m=2, J=0
study the development of the spectral function across this
transition (De Leo and Fabrizio, 2004). One finds that                                  m=2, J=U/100
the impurity spectral function on the Kondo screened                          2/3       m=2, J=U/10
side of this transition shows a narrow Kondo peak on
                                                                     T⋅χ(T)




top of a broader resonance. As has also been observed
                                                                              1/3
by Pruschke and Bulla (2005) and Peters and Pruschke                          1/4
(2006) this broad resonance is related to the exchange
splitting J. The narrow peak transforms into a pseudo-                         0
gap on the unscreened side of the transition.
   De Leo and Fabrizio (2005) have demonstrated that                      ln(6)
                                                                   S(T)




NRG calculations are possible even for m = 3, using                       ln(3)
the symmetries of the model to reduce the size of the                     ln(2)
Hilbert space blocks. They studied a realistic model for
a doped C60 molecule, taking into account the orbitally                         0 -25        -20        -15      -10        -5        0
                                                                               10       10         10          10      10        10
threefold degenerate t2u lowest unoccupied molecular or-                                                      T/∆0
bitals. Again, coupling to vibrational modes can lead
to Hund’s coupling with negative sign. In this regime,         FIG. 21 Effective local moment T · χ(T ) (upper panel) and
one observes non-Fermi liquid behavior for half-filling        entropy (lower panel) for a two-orbital impurity Anderson
n = 3, associated with a three-channel, S = 1 over-            model. Model parameters are U/∆0 = 16π at particle-hole
screened Kondo model. Interestingly, the critical sus-         symmetry. For comparison the results for one orbital are in-
ceptibilities associated with this non-Fermi liquid appear     cluded (triangles).
to be a pairing in the spin and orbital singlet channel
(De Leo and Fabrizio, 2005). Using conformal field the-        and particle-hole symmetry. NRG parameters are Λ = 5
                                                                                                                                                                40

and 2500 retained states per iteration. The triangles are                     600                                                             100
                                                                                         γ(T)                                       χ1
results from a calculation with m = 1 for the same pa-                                                                              χ2        90
                                                                              500                                                   χ1+2 χ2   80
rameters. For J = 0 (circles) we find the behavior ex-




                                                                     in k B/∆0
                                                                                                                                              70




                                                                                                                                                χα(T) in 1/∆0
pected for a SU (4) symmetry, i.e. an energy scale, TKm ,                     400




                                                                    2
                                                                                                                                              60
that is related to the Kondo scale at m = 1, TKm=1 , by
                                                                              300                                                             50
TKm = (TK1 )1/m . However, even a small Hund coupling                                                                                         40
J = U/100 leads to a dramatic reduction of TK , which




                                                                    γ(T)
                                                                              200                                                             30
increases with increasing J. Let us note here, that for                                                                                       20
                                                                              100
J > 0 the effect of the orbital exchange term in (135) is                                                                                     10
negligible, i.e. the results are indistinguishable if one does                   0 -2                                                         0
                                                                                                     -1       0                 1
the calculation with and without this contribution. Very                         10             10          10             10
often, the orbital exchange term is neglected in theoreti-                                                T in [K]
cal studies of transition metal compounds (Imada et al.,         FIG. 22 Comparison between γ(T ) = C(T )/T versus T and
1998), an approximation which is supported by the above          the susceptibility contributions of the two doublets versus T
result.                                                          for EΓ(1) /∆0 = −8.5, δCEF /∆0 = 0.015 and g22 /g12 = 2. The
                                                                          7
                                                                 contribution of the lower doublet, χ1 is much larger than the
                                                                 one of the upper doublet, χ2 . NRG parameters are Λ = 4 and
                                                                 1500 states kept in each step.
b. Crystal-field effects  Recently, experiments showing
unusual specific heat, magnetic susceptibility and re-
sistivity data for Ce1−x Lax Ni9 Ge4 have drawn a lot of
attention, because this material has the “largest ever           (Scheidt et al., 2005)
recorded value of the electronic specific heat at low
                                                                                         ǫkασ c†kασ ckασ +
                                                                                    X                             X
temperature” (Killer et al., 2004) of γ(T ) = ∆C/T ≈                    H =                                            Eασ |ασihασ|                 (136)
5JK−2 mol−1 . While the γ coefficient continues to rise                             kα                            ασ
at the lowest experimentally accessible temperature, the
                                                                                                                            
                                                                                              Vασ |ασih0|ckασ + c†kασ |0ihασ| ,
                                                                                        X
                                                                                    +
magnetic susceptibility tends to saturate at low temper-
                                                                                        kασ
atures.
   One possible scenario (Anders and Pruschke, 2006;                                                                 (α)
Scheidt et al., 2005) to account for the behavior of             where |ασi represents the state Γ7 with spin σ and en-
Ce1−x Lax Ni9 Ge4 is a competition of Kondo and crystal-         ergy Eασ on the Ce 4f shell, and ckασ annihilates a cor-
field effects which leads to a crossover regime connecting       responding conduction electron state with energy ǫkασ .
incoherent spin scattering at high temperatures and a            Note that locally only fluctuations between an empty and
conventional strong-coupling Fermi liquid regime at tem-         a singly occupied Ce 4f shell are allowed.
peratures much lower than the experimentally accessi-              While the entropy and specific heat for the model (136)
ble 30mK. The Hund’s rule ground state of Ce3+ with              can be calculated in the usual way, the Ce contribution to
j = 5/2 is split in a tetragonal symmetry (Killer et al.,        the susceptibility requires some more thought, because
                                                                                                (α)
2004) in three Kramers doublets. If the crystalline elec-        the spin-orbit coupled states Γ7 have different g-factors,
tric field (CEF) parameters are close to those of cubic          which we label by gα . Thus, the total susceptibility is
                                          (1)     (2)
symmetry, the two low-lying doublets Γ7 and Γ7 , orig-           given by (Scheidt et al., 2005)
inating from the splitting of the lowest Γ8 quartet, are
                                                                                                                       (α)
                                                                                                             X
well separated from the higher lying Γ6 doublet. Ignor-                                   χimp = µ2B              gα2 χimp .                        (137)
ing this Γ6 doublet, we can discuss two extreme limits.                                                       α
In a cubic environment, the CEF splitting vanishes and
the low-temperature physics is determined by an SU (4)           While the g-factors are, in principle, determined by the
Anderson model. In a strongly tetragonally distorted             CEF states of the multiplets, we view them as adjustable
crystal, on the other hand, the crystal-field splitting of       parameters and fix them together with EΓ(α) by compar-
                                                                                                            7
the quartets is expected to be large. In this case, the          ing with experiment (Scheidt et al., 2005).
low-temperature properties are determined by an SU (2)             The comparison between the temperature dependence
Anderson model. If, however, the material parame-                of γ(T ) and χ(T ) is shown in Fig. 22 assuming a ratio
ters lie in the crossover regime where the effective low-        of g22 /g12 = 2 for a good fit to the experimental data
temperature scale T ∗ is of the order of the crystal-field       (Scheidt et al., 2005). The ground state doublet dom-
splitting δCEF = EΓ(2) − EΓ(1) , then the excited doublet        inates the magnetic response at low temperature and
                      7       7
will have significant weight in the ground state so that         tends to saturate at temperatures higher than the γ-
the total magnetic response differs from a simple SU (4)         coefficient, consistent with the experiments (Killer et al.,
Anderson model.                                                  2004). We find this behavior only for CEF-splittings
   Such a situation can be captured by a SU (4) Ander-           δCEF ≈ T ∗ (δCEF ) while for much larger or much smaller
son model with infinite U whose Hamiltonian is given by          values χ(T ) and γ(T ) saturate simultaneously.
                                                                                                                             41

E. Bosonic degrees of freedom and dissipation                   be partly explained by an effective single-impurity An-
                                                                derson model in which the coupling to the phonons is
   In the models discussed so far, the bath consists of non-    included in an effective interaction Ueff . An explicit form
interacting fermionic degrees of freedom while the impu-        of this interaction can only be given in the limit ω0 → ∞:
rity is either represented by a fermion or a spin. This         Ueff = U − 2λ2 /ω0 . Interestingly, Hewson et al. (2004)
section deals with quantum impurity systems involving           have shown that an effective quasiparticle interaction can
bosonic degrees of freedom. We distinguish between mod-         be defined for any value of ω0 . This can be accomplished
els in which only a small number of bosonic degrees of          with the renormalized perturbation theory by fitting the
freedom couples to the impurity and models where the            lowest lying energy levels obtained in the NRG calcula-
impurity couples to a bosonic bath (corresponding to an         tions to those from a renormalized Anderson model.
infinite number of bosonic degrees of freedom).                    These investigations represent a starting point for var-
   As we will see below, the first case can be dealt with       ious applications of the NRG to coupled electron-phonon
in the usual scheme, provided the subsystem consisting          system. For the investigation of transport properties
of impurity and bosons can be treated as a large impu-          of single molecule devices, for which the coupling to
rity which is then coupled to the fermions. The second          local phonons is a natural ingredient, similar models
class, however, requires a different set-up for the NRG-        as Eq. (138) have been investigated in Cornaglia et al.
procedure.                                                      (2004) and Cornaglia and Grempel (2005a). Not only
   Let us first consider the so-called Anderson-Holstein        the coupling to the electron density as in Eq. (138), but
model (Hewson and Meyer, 2002) in which the impurity            also the change of the hybridization between molecule
is linearly coupled to a single bosonic degree of freedom       and leads due to the phonons has been shown to be im-
(typically a phonon mode):                                      portant for the conductance properties (Cornaglia et al.,
                                                                2005).
                              X                                    Different physical phenomena can be expected in
    H = HSIAM + λ(b† + b)          fσ† fσ + ω0 b† b ,   (138)   multi-orbital systems when the impurity degrees of free-
                               σ                                dom couple to Jahn-Teller phonons. Such a model has
                                                                been investigated in Hotta (2006) and it was argued that
with HSIAM the Hamiltonian of the single-impurity An-
                                                                within this model a new mechanism of Kondo phenomena
derson model as in Eq. (2). The coupling to the bosonic
                                                                with non-magnetic origin can be established.
operators (b† and b) does not influence the mapping of
                                                                   Two different strategies have been developed to study
the conduction electron part of the Hamiltonian to a
                                                                impurity models with a coupling to a bosonic bath, i.e. a
semi-infinite chain. This means that the bosons enter
                                                                bosonic environment with a continuous spectral density
the iterative diagonalization only in the very first step
                                                                J(ω). Let us discuss these strategies in the context of
in which the coupled impurity-boson subsystem has to
                                                                the spin-boson model
be diagonalized. The fact that only a limited number
of bosonic states nb can be taken into account in this                   ∆         ǫ                     σz X
                                                                                             ωi a†i ai +        λi (ai + a†i ) .
                                                                                         X
diagonalization imposes some restrictions on the param-          H =−        σx + σz +
                                                                          2        2       i
                                                                                                         2   i
eters λ (the electron-phonon coupling strength) and ω0
(the frequency of the phonon mode). As discussed in                                                                       (139)
Hewson and Meyer (2002), it should be sufficient to in-         This model naturally arises in the description of quantum
clude a number of nb ≈ 4λ2 /ω02 bosonic states for the          dissipative systems (Leggett et al., 1987). The dynamics
initial diagonalization. With an upper limit of nb ≈ 1000       of the two-state system, represented by the Pauli ma-
this means that the limit ω0 → 0 (with fixed λ) cannot          trices σx,z , is governed by the competition between the
be treated within this setup.                                   tunneling term ∆ and the friction term λi (ai + a†i ). The
   Apart from this minor restriction, Hewson and Meyer          ai constitute a bath of harmonic oscillators responsible
(2002) showed that the NRG (which is non-perturbative           for the damping, characterized by the bath spectral func-
in both λ and U ) works very well for such type of im-          tion
purity models. In particular, both electron and phonon                                     X
spectral functions as well as dynamic charge and spin                            J (ω) = π    λ2i δ (ω − ωi ) .           (140)
                                                                                             i
susceptibilities can be calculated with a high accuracy.
   As discussed in detail in Jeon et al. (2003) and             A standard parametrization of this spectral density is
Choi et al. (2003a), the calculation of the phonon
spectral function needs some extra care and the au-                J(ω) = 2π α ωc1−s ω s , 0 < ω < ωc ,      s > −1 .     (141)
thors introduced an improved method (as compared to
Hewson and Meyer (2002)). The proper calculation of             The case s = 1, known as Ohmic dissipation, allows a
the phonon spectral function is important to discuss the        mapping of the spin-boson model onto the anisotropic
softening of the phonon mode, see also the discussion in        Kondo model (for the definition of the Hamiltonian and
Sec. V.C in the context of lattice models with coupling         the relation of its parameters to those of the spin-boson
to phonons.                                                     model, see Costi and Kieffer (1996)). The first strat-
   The low-energy features of the model Eq. (138) can           egy is then to apply the NRG to the anisotropic Kondo
                                                                                                                            42

model and to treat the fermionic conduction band in the         discussed in Castro Neto et al. (2003) and Novais et al.
usual way. Though restricted to the Ohmic case, such            (2005). The bosonic baths in these models can be
calculations have been shown to give very accurate re-          mapped onto two independent fermionic baths, and a
sults for dynamic and thermodynamic quantities of the           generalization of the anisotropic Kondo model is ob-
corresponding spin-boson and related models, as briefly         tained. These models are of interest to study the effect
discussed in the following.                                     of quantum frustration of decoherence.
   The focus of Costi and Kieffer (1996) has been the              The second strategy to investigate impurity models
equilibrium dynamics of the spin-boson model, in partic-        with a coupling to a bosonic bath does not rely on a
ular the spin-spin correlation function, χ(ω) = hhσz ; σz ii,   mapping to a fermionic impurity model. This approach
at temperature T = 0. An interesting finding of this            – which has been termed “bosonic” NRG – was intro-
study, is that the spin relaxation function, χ′′ (ω)/ω, ex-     duced in Bulla et al. (2003) in the context of the spin-
hibits a crossover from inelastic to quasielastic behavior      boson model (for full details see (Bulla et al., 2005)). Let
as α exceeds the value 1/3 signalling the onset to inco-        us just mention briefly the main differences to the stan-
herent dynamics which occurs at α ≥ 1/2 (Leggett et al.,        dard (fermionic) NRG: the logarithmic discretization is
1987). The accuracy of this approach has been shown via         now directly performed for the bosonic bath (for the spin-
the comparison to exactly solvable limiting cases, such         boson model, the bath spectral function J(ω) Eq. (140) is
as the Toulouse point α = 0.5, and via the generalized          discretized); the subsequent mapping onto a semi-infinite
Shiba relation. The issue of scaling and universality,          chain is technically very similar to the fermionic case but
concepts which are quite naturally connected to renor-          the resulting tight-binding chain is built up of bosonic
malization group treatments of the Kondo problem, have          sites. This gives rise to additional difficulties in setting up
been discussed in the context of the spin-boson model in        the iterative diagonalization scheme because only a finite
Costi (1998). Universal scaling functions have been cal-        number of bosonic states Nb can be taken into account
culated for thermodynamic quantities (the specific heat),       when adding one site to the chain. Furthermore, the set
the static susceptibility and the spin-relaxation function.     of Nb states should in general be optimized to give the
Scaling as a function of temperature or frequency has           best description of the lowest lying many-particle states,
been observed in the limit ∆ → 0 for fixed coupling             see the discussion in Bulla et al. (2005).
strength α, this means that the scaling functions turn             The first applications of the bosonic NRG focused on
out to depend on the value of α. This is illustrated,           the spin-boson model Eq. (139), in particular the sub-
for example, in Fig. 2 in Costi (1998) which shows the          Ohmic case with exponents 0 < s < 1 in the parametriza-
temperature dependence of the specific heat for differ-         tion of the bath spectral function J(ω) Eq. (141). The
ent α. In particular, a signature distinguishing weakly         sub-Ohmic case does not allow for the mapping to a
dissipative from strongly dissipative systems is found in       fermionic impurity model, in contrast to the Ohmic case.
γ(T ) = C(T )/T , which is found to exhibit a peak for          Furthermore, the bosonic NRG turns out to have cer-
α < 1/3 but is monotonic in temperature for α ≥ 1/3.            tain advantages over other approaches usually applied to
This, together with the above mentioned behavior in the         the spin-boson model (Leggett et al., 1987) as it is non-
spin-relaxation function, is reminiscent of measurements        perturbative in both α and ∆. As an example of the
on Ce1−x Lax Al3 (Goremychkin et al., 2002), but the ap-        success of the bosonic NRG we show in Fig. 23 the T = 0
plicability of an anisotropic Kondo model here is contro-       phase diagram of the spin-boson model with bias ǫ = 0
versial (Pietri et al., 2001). Specific heats have also been    in the α-s plane for different values of the tunneling am-
calculated for more complicated tunneling models, such          plitude ∆.
as the ionic tunneling model with a spinless fermionic             The most remarkable feature of the phase diagram is
bath (Ferreira and Libero, 2000), which shows similar be-       the line of quantum critical points for 0 < s < 1 which
havior to the Ohmic spin boson model for α ≤ 1/4, and to        terminates for s → 1− in the Kosterlitz-Thouless transi-
an extension of this including an assisted tunneling term       tion of the Ohmic case. The critical exponents along this
(Ramos and Lı́bero, 2006). The spectral density of the          line have been discussed in detail in Vojta et al. (2005)
former has also been investigated (Lı́bero and Oliveira,        where it was shown that the exponents fulfill certain hy-
1990b).                                                         perscaling relations.
   The mapping of a bosonic bath to a fermionic one                There are still quite a number of open issues and pos-
has been also exploited for various other problems.             sible applications in the context of the sub-Ohmic spin-
Costi and McKenzie (2003) have used the NRG to cal-             boson model which can be investigated with the bosonic
culate the entropy of entanglement for the spin-boson           NRG, see for example Tong and Vojta (2006). In addi-
model, a quantity which measures the entanglement be-           tion, the NRG can be generalized to more complex im-
tween the spin and the environment. Interestingly, the          purity models with a coupling to a bosonic bath. Two
entanglement appears to be highest for α → 1− , where           recent examples are the investigations of the Bose-Fermi
the system undergoes a quantum phase transition from            Kondo model (Glossop and Ingersent, 2005) and of mod-
a delocalized to a localized phase.                             els which are connected to electron and exciton transfer
   The case of two bosonic baths which couple to differ-        phenomena (Tornow et al., 2006a,b).
ent components of the impurity spin operator, has been             Technically the most challenging of these extensions
                                                                                                                      43

     1.5                                                      Schollwöck, 2005), which today is a standard technique
                       -1
                                                              to study one-dimensional interacting quantum models.
                  ∆=10
                  ∆=10
                       -3                                        There exists, however, an approximation for correlated
     1.0          ∆=10
                       -5                                     lattice models, where the interacting lattice problem is
                                                              mapped onto an effective quantum impurity model, for
   α




                                                              which the NRG can be applied. Underlying this ap-
                     localized                                proach is the dynamical mean-field theory (DMFT). The
     0.5
                                                              DMFT has its origin in the investigation of correlated
                                                              lattice models in the limit of infinite spatial dimension-
                                          delocalized         ality (Metzner and Vollhardt, 1989). A proper scaling
     0.0                                                      of the hopping matrix element t in models such as the
       0.0                  0.5            1.0
                                  s                           Hubbard model (142) leads to a vanishing of all non-
                                                              local self-energy sceleton diagrams. The resulting purely
FIG. 23 Phase diagram of the spin-boson model for T =
0 calculated with the bosonic NRG for various values of ∆.
                                                              local self-energy Σ(z) can be identified with the self-
A line of quantum critical points separates the delocalized   energy of an effective single-impurity Anderson model.
from the localized phase. (Figure adapted from Bulla et al.   In this sense we speak of a mapping of a lattice model
(2003)).                                                      onto an effective quantum impurity model, typically the
                                                              single-impurity Anderson model as introduced in Eq. (2),
                                                              supplemented by a self-consistency condition, which de-
is the study of impurity models which couple to both          termines the bath degrees of freedom of the effective
fermionic and bosonic baths. The first successful treat-      quantum-impurity. Since the technical details of the
ment of such a model, the Bose-Fermi Kondo model with         DMFT are not the subject of this review, we refer the
Ising-type coupling between spin and bosonic bath, has        reader to the review by Georges et al. (1996).
been discussed in Glossop and Ingersent (2005, 2006a).           To investigate lattice models in the DMFT we there-
Here the two baths are mapped on two semi-infinite            fore need a technique (analytical or numerical) to cal-
chains, one for the bosonic and one for the fermionic         culate the full frequency dependence of the self-energy
degrees of freedom. Due to the competition between dis-       for a single-impurity Anderson model defined by ar-
sipation and screening, quantum phase transitions occur       bitrary input parameters (εf , U , T , and a manifestly
which turn out to be in the same universality classes as      energy-dependent hybridization function ∆(ω)). There
the transitions in the spin-boson model. This can be un-      are many methods besides the NRG available to cal-
derstood through a mapping between the (Ising-)Bose-          culate dynamic quantities for quantum impurity models
Fermi Kondo model and the spin-boson model where the          and we shall not give an overview here (for reviews see,
bath spectral function has both an Ohmic and a sub-           for example, Sec. VI in Georges et al. (1996), Sec. III in
Ohmic component (the Ohmic part represents the cou-           Maier et al. (2005), and Bulla (2006)), but rather concen-
pling to the fermionic bath, while the sub-Ohmic part         trate on the application of the NRG method to the Hub-
is the same as the one in the original model, see also        bard model (see Sec. V.A), the periodic Anderson and
Li et al. (2005)). On the other hand, the (Ising-)Bose-       Kondo lattice models (see Sec. V.B), and lattice mod-
Fermi Kondo model with an Ohmic bosonic bath can              els with coupling to phonons (see Sec. V.C) within the
also be mapped onto the anisotropic Kondo model, see          DMFT approach.
for example Borda et al. (2005).                                 Before we discuss the results obtained for those mod-
                                                              els, let us comment on pecularities of the NRG when ap-
                                                              plied to DMFT calculations. The DMFT self-consistency
V. APPLICATION TO LATTICE MODELS WITHIN                       specifies at each iteration an input hybridization function
DMFT                                                          ∆(ω), the form of which depends on the model under in-
                                                              vestigation, its parameters and also on the history of the
  The application of the NRG is restricted to quan-           previous DMFT-iterations. The frequency dependence of
tum impurity systems with the impurity degree of free-        ∆(ω) has to be taken into account within the logarith-
dom coupled to a non-interacting bath. Therefore, the         mic discretization scheme, exactly as described in Sec. II
NRG cannot be directly applied to lattice models of           and already employed in the NRG investigations of the
interacting particles, such as the Hubbard model (see         soft-gap Anderson model, see Sec. IV.C.2.
Eq. (142) in Sec. V.A). Early attempts to extend Wil-            Concerning the output, the quantity of interest is usu-
son’s concepts to such models failed (Bray and Chui,          ally the self-energy ΣAM of the effective single-impurity
1979; Chui and Bray, 1978; Lee, 1979). The reason             Anderson model, although in some cases, as for the Bethe
for this failure was later found to be connected with         lattice, the knowledge of the single-particle Green func-
boundary conditions between “system” and “environ-            tion is sufficient for the DMFT iteration (Georges et al.,
ment” (Noack and Manmana, 2005; White and Noack,              1996). It has proven advantageous to calculate, within
1992), and led to a novel scheme nowadays known as            DMFT, the self-energy ΣAM via the ratio of a two-
density-matrix renormalization group (Hallberg, 2006;         particle and a one-particle Green function, see Eq. (85).
                                                                                                                                             44

As discussed in Bulla et al. (1998) (see also Sec. III.B.2)             transition, when the quasiparticle peak has disappeared,
the calculation of the self-energy via Eq. (85) significantly           an insulating solution with a preformed gap is realized.
improves the quality of the results. This approach has
been used in most NRG calculations within DMFT.
                                                                                    1.2    a)                                 U/W=1.0
                                                                                                                              U/W=1.42
                                                                                                                              U/W=1.61
                                                                                    0.8




                                                                             A(ω)
A. Hubbard model

                                                                                    0.4
   The simplest model for correlated fermions on a lattice
is the single-band Hubbard model with the Hamiltonian
                                                                                     0
                                                                                      -2         -1          0            1              2
                  (c†iσ cjσ +c†jσ ciσ )+U                                                                   ω/W
                                            X †
                                             ci↑ ci↑ c†i↓ ci↓ . (142)
           X
 H = −t                                                                           0.05
          <ij>σ                              i
                                                                                           b)                           Uc1
                                                                                  0.04
Consequently the first applications of the NRG within                                                                   Uc2
DMFT focused on this model; in particular on the Mott-                            0.03




                                                                            T/W
transition, which the Hubbard model displays in the half-                         0.02
filled paramagnetic case. These investigations and fur-
ther generalizations are described in the following sub-                          0.01
sections.
                                                                                  0.00
                                                                                           1.0        1.2         1.4             1.6
                                                                                                            U/W
1. Mott metal-insulator transition                                      FIG. 24 (a) Spectral functions for the half-filled Hubbard
                                                                        model at T = 0 for various values of U (similar data as in
   Although the qualitative features of the Mott transi-                Fig. 2 in Bulla (1999); (b) phase diagram for the Mott tran-
tion have been correctly described very early in the devel-             sition. For a comparison with other methods see the corre-
opment of the DMFT (see the review by Georges et al.                    sponding Fig. 9 in Bulla et al. (2001).
(1996)), the NRG helped to clarify a number of conflict-
ing statements in the literature (see the discussion in                   We should remind the reader at that point that the
Bulla (1999) and Bulla et al. (2001)). The NRG method                   NRG results for dynamic quantities have a certain fixed
appears to be ideally suited to investigate the Mott tran-              resolution on a logarithmic scale (c.f. the discussion in
sition because (i) the transition occurs at interaction                 Sec. III.B). This means that structures close to ω = 0
strengths of the order of the bandwidth which requires                  are much better resolved than structures at, for exam-
the use of a non-perturbative method, and (ii) at T = 0                 ple, the band edges of the Hubbard bands. In contrast,
the Mott transition is characterized by a vanishing en-                 the dynamical density-matrix renormalization group re-
ergy scale, T ∗ → 0, when approached from the metallic                  cently applied to the DMFT for the Hubbard model
side. Thus, a method is needed that is able to resolve                  works with a fixed resolution on a linear scale, see for
arbitrarily small energies close to the Fermi level.                    example Karski et al. (2005). The structures close to the
   The first investigation of the Mott transition with the              inner band edges of the Hubbard bands seen in these cal-
NRG has been performed by Sakai and Kuramoto (1994)                     culations (see Fig. 2 in Karski et al. (2005)) cannot be
(see also Shimizu and Sakai (1995)). These calculations                 resolved in present implementations of the NRG method.
did not use an expression of the self-energy as in Eq. (85),              Figure 24b shows the T -U phase diagram for the Mott
but nevertheless a Mott transition and a hysteresis region              transition, again only considering paramagnetic phases.
have been observed, with critical values very close to the              As already observed earlier (Georges et al., 1996), there
ones reported later in Bulla (1999).                                    are two transition lines, because the insulator-to-metal
   A detailed discussion of the NRG calculations for the                transition occurs at a lower critical value (Uc,1 (T )) as the
Hubbard model is given in Bulla (1999) for T = 0 and                    metal-to-insulator transition (Uc,2 (T )). Within this hys-
in Bulla et al. (2001) for finite temperatures. The main                teresis region, both metallic and insulating solutions can
results are summarized in Fig. 24: Spectral functions cal-              be stabilized within the DMFT self-consistency. With
culated with NRG for the half-filled Hubbard model in                   increasing temperature, the hysteresis region shrinks
the paramagnetic regime for different values of U and                   to zero at a critical Tc , above which there is only a
T = 0 are shown in Fig. 24a. Upon increasing U from                     crossover from metallic-like to insulating-like solutions;
the metallic side, the typical three-peak structure forms,              this crossover region is indicated by the dashed lines in
with upper and lower Hubbard peaks at ω ≈ ±U/2 and                      Fig. 24b. The NRG values for Uc,1/2 (T ) have later been
a central quasiparticle peak at ω = 0. The width of                     verified by a number of other, non-perturbative tech-
this quasiparticle peak goes to zero when approaching                   niques (see for example Tong et al. (2001) or Potthoff
the transition from below, U ր Uc,2 ≈ 1.47W , with W                    (2003)).
the bandwidth of the noninteracting model. Right at the                   As discussed above, most of the NRG calculations
                                                                                                                               45

within DMFT have been performed using Eq. (85) for              large U , ferromagnetic solutions can be stabilized. For
the calculation of the self-energy. This quantity itself        intermediate U and finite doping, magnetic ordering ap-
shows interesting properties (see, for example, Fig. 3 in
Bulla (1999) and Fig. 5 in Bulla et al. (2001)), and al-                      1000000000000000000000000
                                                                               111111111111111111111111
                                                                               000000000000000000000000
                                                                               0000000000000000000000000000000000000000000
                                                                               1111111111111111111111111111111111111111111
                                                                               000000000000000000000000
                                                                               111111111111111111111111
                                                                               0000000000000000000000000000000000000000000
                                                                               1111111111111111111111111111111111111111111
                                                                                                    FM
                                                                              000000000000000000000000
                                                                              111111111111111111111111
                                                                              0000000000000000000000000000000000000000000
                                                                              1111111111111111111111111111111111111111111
                                                                              000000000000000000000000
                                                                              111111111111111111111111
                                                                              111111111111111111111111
                                                                              000000000000000000000000
                                                                              111111111111111111111111
                                                                              000000000000000000000000
lows to calculate the U -dependence of the quasiparticle                      111111111111111111111111
                                                                              000000000000000000000000
                                                                                    AFM
                                                                              111111111111111111111111
                                                                              000000000000000000000000
                                                                              111111111111111111111111
                                                                              000000000000000000000000
                                                                              000000000000000000000000
                                                                              111111111111111111111111
                                                                              111111111111111111111111
                                                                              000000000000000000000000
weight, see Fig. 1 in Bulla (1999).                                          0,8000000000000000000000000
                                                                                111111111111111111111111
                                                                              111111111111111111111111
                                                                              000000000000000000000000
                                                                              111111111111111111111111
                                                                              000000000000000000000000
                                                                                000000000000000000000000
                                                                                111111111111111111111111
                                                                              111111111111111111111111
                                                                              000000000000000000000000
                                                                                111111111111111111111111
                                                                                000000000000000000000000
    The Mott transition can also be induced by moving                           111111111111111111111111
                                                                                000000000000000000000000
                                                                                000000000000000000000000
                                                                                111111111111111111111111
away from half-filling, provided the value of U is larger                    0,6000000000000000000000000
                                                                                111111111111111111111111
                                                                                   AFM(PS)
                                                                                111111111111111111111111
                                                                                000000000000000000000000




                                                                   U/(1+U)
than the Uc for the half-filled case. Unfortunately, no                         111111111111111111111111
                                                                                000000000000000000000000
                                                                                000000000000000000000000
                                                                                111111111111111111111111
                                                                                000000000000000000000000
                                                                                111111111111111111111111
                                                                                000000000000000000000000
                                                                                111111111111111111111111
systematic NRG calculations have been published for this                     0,4000000000000000000000000
                                                                                111111111111111111111111
                                                                                111111111111111111111111
                                                                                000000000000000000000000
                                                                                111111111111111111111111
                                                                                000000000000000000000000   PM
filling-induced Mott transition, despite the fact that the                      111111111111111111111111
                                                                                000000000000000000000000
                                                                                000000000000000000000000
                                                                                111111111111111111111111
NRG can be easily extended to the Hubbard model away                            000000000000000000000000
                                                                                111111111111111111111111
                                                                             0,2000000000000000000000000
                                                                                111111111111111111111111
from particle-hole symmetry. Only a few results for the
phase diagram (Ōno et al., 2001) and spectral functions
(Freericks et al., 2003; Krug von Nidda et al., 2003) are                     0
                                                                                  0%         10%           20%           30%
available in the literature.                                                                         δ
    A nice feature of the DMFT is that it also allows for the
                                                                FIG. 25 Ground state magnetic phase diagram for the Hub-
calculation of physical quantities other than the single-
                                                                bard model on a hypercubic lattice. The phases show anti-
particle Green function, in particular susceptibilities and     ferromagnetic (AFM) order, which for smaller U and doping
also transport properties, both static and dynamic. This        δ > 0 also shows phase separation (PS), and ferromagnetic
aspect of the DMFT has been intensively used already            order at large U . To display the whole interval [0, ∞), the
in the early applications (see for example the reviews          vertical axis was rescaled as U/(1 + U ) (see also Fig. 10 in
by Pruschke et al. (1995) and Georges et al. (1996)), em-       Zitzler et al. (2002)).
ploying different methods to solve the effective quantum-
impurity problem. However, apart from discussions of            pears to exist but its type could not be determined yet.
the A1g Raman response (Freericks et al., 2001, 2003)              In contrast to this work, the NRG calculations in
and calculations of the resistivity (Georges et al., 2004;      Zitzler et al. (2004) concentrated on the antiferromag-
Limelette et al., 2003) and the local dynamic susceptibil-      netic phase at half-filling in a Hubbard model with frus-
ity (Krug von Nidda et al., 2003), no detailed studies of       tration. As expected, the antiferromagnetic region in the
such quantities for the paramagnetic phase of the Hub-          T -U phase diagram is suppressed upon increasing frus-
bard model have been performed yet with the NRG.                tration. However, the resulting phase diagram turns out
                                                                to be significantly different from the one proposed for
                                                                the frustrated Hubbard model in Georges et al. (1996),
2. Ordering phenomena                                           where it was claimed that the main effect of frustration is
                                                                to suppress TN such that the first-order Mott transition is
    The Mott transition from a paramagnetic metal to a          visible above the antiferromagnetic region. This contro-
paramagnetic insulator is merely one of the many fea-           versial issue certainly calls for more detailed calculations
tures in the rich phase diagram of the Hubbard model            (with NRG and other methods); after all, the similarity
and its generalizations. In addition, various types of or-      of the phase diagram for the Hubbard model in DMFT
dering phenomena occur, such as charge, orbital (in case        and the experimental one for the transition metal oxide
of multi-orbital models), and magnetic ordering, and –          V2 O3 has been claimed to be one of the early success of
possibly – superconductivity. The NRG has been used             DMFT (Georges et al., 1996).
in particular to study magnetic ordering phenomena in a            The optical conductivity in the antiferromagnetic
wide range of parameters.                                       phase of the Hubbard model at half-filling and
    For the investigation of symmetry broken phases             zero temperature has been studied in detail in
within DMFT, the self-consistency equations have to be          Pruschke and Zitzler (2003). For small values of U , the
adapted appropriately (Georges et al., 1996). The ef-           antiferromagnetic phase shows signatures of a Slater in-
fective impurity models still have the structure of the         sulator, while for large U a Mott-Heisenberg picture ap-
single-impurity Anderson model so that the application          plies. There is a smooth crossover between these two
of the NRG is straightforward, see the discussion in            limiting cases upon variation of U , in contrast to the
Zitzler et al. (2002). This work also contains a detailed       Mott transition in the paramagnetic phase. The evi-
study of the magnetic phases of the Hubbard model at            dence from the optical data has been supported by a de-
T = 0 both at and away from half-filling. Right at half-        tailed discussion of the local dynamical magnetic suscep-
filling and for a particle-hole symmetric band-structure,       tibility, giving additional insight into the subtle changes
the groundstate is always antiferromagnetically ordered.        in the physics of charge- and spin-degrees of freedom
Upon doping, the situation is more complicated as shown         across the Mott metal-insulator transition (Pruschke,
in Fig. 25: For small values of U , phase separation within     2005; Pruschke and Zitzler, 2003).
the antiferromagnetic phase is observed, while for very            When the Hubbard model Eq. (142) is supplemented
                                                                                                                        46

by a nearest-neighbor Coulomb repulsion V , a transition       4. Other generalizations of the Hubbard model
to a charge ordered state is observed upon increasing V .
This transition has been studied in Pietig et al. (1999)           Let us conclude this section with a brief overview of
for the quarter-filled case. NRG calculations, together        applications of the NRG to various other generalizations
with results from non-crossing approximation and exact         of the Hubbard model.
diagonalization show a phase diagram with a reentrant              The influence of correlations in a conduction band
charge ordering transition, a feature which has also been      (modeled by a Hubbard model within DMFT) on the
observed in a variety of transition metal oxides. The          physics of the single-impurity Anderson model has been
NRG results in this work are restricted to T = 0, where        investigated in Hofstetter et al. (2000). The DMFT ap-
the transition is of first order. It would be very interest-   proach allows to map this model on an effective impu-
ing to extend the NRG calculations to a wider range of         rity model with two coupled correlated sites, the first
parameters, in particular to finite temperatures to study      one corresponding to the original impurity and the sec-
the change of the character of the transition which is         ond one coming from the DMFT treatment of the Hub-
continuous at higher T .                                       bard model. This two-site cluster couples to a free effec-
                                                               tive conduction band. As discussed in Hofstetter et al.
                                                               (2000), correlations in the conduction band have a sig-
3. Multi-band Hubbard models                                   nificant influence on the low-energy scale and also lead
                                                               to a suppression of the Kondo resonance.
   The application of the NRG to the investigation of              Within the so-called Anderson-Hubbard model, disor-
multi-band Hubbard models within DMFT is still in a            der effects can be incorporated via a random distribution
very early stage. This is because (i) the computational        of the local energies εi . This model has been studied in
effort grows considerably with the number of orbitals and      Byczuk et al. (2004) within DMFT for binary alloy dis-
(ii) the DMFT requires a very high accuracy for the cal-       order. The application of the NRG here is standard –
culated dynamic properties. Furthermore, self-consistent       two independent single-impurity Anderson models have
solutions of the DMFT equations have to be obtained.           to be considered at each iteration step. Nevertheless, the
   The first (and so far the only) DMFT results for a two-     physics of this model is already quite interesting, in par-
band Hubbard model using the NRG have been presented           ticular the occurrence of a Mott transition at non-integer
in Pruschke and Bulla (2005). In this work, two different      filling. The DMFT treatment in Byczuk et al. (2004)
strategies have been used to handle the complexity of          does not allow for true Anderson localization (as far as
the problem. The first one is to explicitly include the        disorder is concerned, the DMFT is equivalent to the co-
orbital quantum numbers in the iterative construction of       herent potential approximation and the main effect of the
the basis states. As for the impurity models discussed in      binary disorder is to split the bands). This deficiency has
Sec. IV.D, this additional quantum number significantly        been cured in Byczuk et al. (2005) where a generalization
reduces the typical matrix size. However, this approach        of the DMFT approach has been used, based on the geo-
fails as soon as the Hamiltonian contains terms which          metrically averaged (typical) local density of states. This
break the orbital symmetry.                                    allows to study both Mott insulating and Anderson in-
   The second strategy is an asymmetric truncation             sulating phases, see Fig. 1 in this paper. The calculation
scheme: Instead of adding both orbital degrees of free-        has been performed using a continuous probability distri-
dom simultaneously, the Hilbert space is truncated after       bution, approximated by up to 30 different values of εi ,
adding each orbital individually, which also leads to a        so that in each DMFT step a corresponding number of
significant reduction of the typical matrix size. This ap-     independent single-impurity Anderson models have to be
proach works quite well in a wide range of parameters,         considered. All the NRG calculations for the Anderson-
but it appears to violate the orbital symmetry, if present.    Hubbard model have been so far restricted to T = 0 and
However, in the presence of a crystal-field splitting of the   to phases without long-range order.
orbitals, such a strategy might be usable.                         Recently, the NRG has been used within an extension
   The focus in Pruschke and Bulla (2005) was on the role      of the standard DMFT. The ‘DMFT+Σk ’ approach as in-
of the Hund exchange coupling J on the Mott transition         troduced in Sadovskii et al. (2005) and Kuchinskii et al.
in the two-band Hubbard model. It was found that both          (2005) adds to the local self-energy a k-dependent part
the position in parameter space and the nature of the          Σk . Applied to the one-band Hubbard model, the effec-
Mott transition depend on the value of J and the precise       tive single-impurity Anderson model is still of the same
form of the coupling. For example, the replacement of a        type as the one appearing in standard DMFT, the only
rotationally invariant Hund exchange by an Ising-like ex-      difference is in the structure of the self-consistency equa-
change leads to a significant change in the physics of the     tions.
Mott transition. Note that such features can be partly             For details of the NRG calculations and the dis-
understood already on the level of the corresponding ef-       cussion of the physics of the Falikov-Kimball model
fective impurity models, which underlines the importance       (Anders and Czycholl, 2005) and the ionic Hubbard
to thoroughly investigate the properties of the impurity       model (Jabben et al., 2005) we refer the reader to the re-
models appearing in the DMFT.                                  spective references. Both papers show the usefulness of
                                                                                                                                                           47

                                                                                      1
the NRG approach to a wide range of correlated lattice
                                                                                           1




                                                                                                                     effective medium
models within DMFT, in particular for the calculation of
dynamic quantities at low temperatures.                                             0.8



B. Periodic Anderson and Kondo lattice models                                       0.6    0                                            0




                                                                            Af(ω)
                                                                                               -0.1   0    0.1                                  0

   A variety of Lanthanide- and Actinide-based com-                                 0.4                                                         PAM
pounds can be characterized as heavy fermion systems                                                                                            SIAM
with a strongly enhanced effective mass of the quasiparti-
                                                                                    0.2
cles. These compounds contain well localized 4f or 5f or-
bitals coupling via a hybridization to a conduction band
consisting of s, p or d orbitals. The appropriate micro-                             0
                                                                                      -2              -1         0                          1          2
scopic model for these materials is the periodic Anderson                                                        ω
model (PAM)
                                                                       FIG. 26 Comparison of dynamic properties for the particle-
                   X †             X †         †                       hole symmetric periodic Anderson model (solid lines) and
           H = εf      fiσ fiσ + U    fi↑ fi↑ fi↓ fi↓                  the corresponding single-impurity Anderson model (dashed
                       iσ                     i                        lines). Main panel: f electron spectral function; left inset:
              εk c†kσ ckσ +              †
                                            cjσ + c†jσ fiσ .
         X                    X                           
     +                              Vij fiσ                    (143)   enlarged view of the region around the Fermi energy; right in-
         kσ                   ijσ                                      set: (effective) hybridization function. (Figure adapted from
                                                                       Pruschke et al. (2000)).
When charge fluctuations of the f orbitals are negligi-
ble, the low energy physics of the PAM can equally be
described by the Kondo lattice model                                      The right inset to Fig. 26 shows the hybridization func-
                                                                       tion of the effective impurity model after self-consistency
                      ~i · ~si +   εk c†kσ ckσ .
                  X              X
            H=J       S                          (144)                 has been reached (full line) in comparison to the same
                        i                kσ
                                                                       quantity entering the isolated impurity (dashed line). At
The large effective mass in these models arises from a                 first sight, the only difference seems to be the gap at the
strongly reduced lattice coherence scale T0 ; this is one              Fermi level. However, for the particle-hole symmetric
of the reasons why the NRG is very well suited for the                 case, one can show that ∆(ω) has a pole at the Fermi
investigation of heavy fermion behavior when the PAM                   level. At first sight, this pole appears to be a problem
or the Kondo lattice model are treated within DMFT.                    for the NRG as the logarithmic discretization explicitly
The main difference for the NRG treatment (as com-                     excludes the point ω = 0, i.e. such a pole cannot be incor-
pared to the Hubbard model) lies in the DMFT self-                     porated in the mapping to the semi-infinite chain. The
consistency. This means that the structure of the ef-                  way out is to take the pole into account via an extra site
fective impurity model is changed only via the effective               which couples directly to the impurity, thus removing the
hybridization ∆(ω) (which may lead to complications as                 pole from the hybridization function.
discussed later).                                                         Due to the appearance of the hybridization gap, the
   The PAM with on-site hybridization Vij = V δij and                  particle-hole symmetric PAM seems rather suitable to
particle-hole symmetry on a hypercubic lattice has been                describe so-called Kondo insulators, but not the metallic
discussed in Shimizu and Sakai (1995), Pruschke et al.                 heavy fermion behavior. There are various ways to drive
(2000), and Shimizu et al. (2000). In this case, a hy-                 the PAM into the metallic regime, two of which we will
bridization gap at the Fermi level appears in the spectral             discuss in the following. One possibility is to use asym-
functions for both conduction and f electrons. This effect             metric parameters for the f electrons (εf 6= −U/2) and
for the f spectral function is shown in Fig. 26 by the full            to keep the conduction band symmetric so that nc ≈ 1.
lines in the main panel and left inset. Apparently, the                More interesting (and also physically more relevant) is
Kondo resonance of the corresponding single-impurity                   the opposite case, namely keeping εf = −U/2 and shift-
Anderson model (dashed curves in the main panel and                    ing the conduction band center-of-mass away from the
left inset in Fig. 26), for which the hybridization func-              Fermi level, so that nc is reduced from 1. This situation
tion is given by the bare density of states of the lattice,            has been discussed in the context of Nozières exhaus-
is split in the periodic model. The energy scale of the                tion principle (Nozières, 1998) which states that, upon
gap in the PAM (proportional to the lattice coherence                  decreasing nc , there will not be enough conduction elec-
scale T0 ) depends exponentially on the model parame-                  trons available to screen the impurity spins. Collective
ters, similar as for the width of the Kondo resonance in               screening then becomes effective only at a strongly re-
the impurity model (proportional to the Kondo temper-                  duced lattice coherence scale. We do not want to go into
ature TK ). Further analysis shows that the lattice coher-             the details here and refer the reader to the discussion
ence scale T0 is enhanced over the impurity scale TK (for              in Sec. 5.4 of Vidhyadhiraja and Logan (2004), which is
details see Pruschke et al. (2000)).                                   based on results for the PAM obtained with the local-
                                                                                                                       48

moment approach.                                               of these studies has been the variation of the spectra
   There is one particular feature found in the DMFT cal-      with conduction band filling nc . For this case it was
culations which at first sight seems to support Nozières      found that the spectra exhibit two energy scales, one
idea, namely that, as shown in Fig. 6b in Pruschke et al.      being the Kondo temperature TK of the corresponding
(2000), the effective hybridization function is strongly re-   single-impurity Kondo model, the other one being the
duced in a region close to the Fermi level. Since this         Fermi liquid coherence scale T0 which, for low carrier
quantity can be interpreted as being proportional to the       densities, nc ≪ 1, is strongly reduced as compared to
conduction band density of states effectively seen by the      TK , similar to the observations made in Pruschke et al.
f -states, it seems that indeed there are less conduction      (2000) for the PAM. A comparison of the temperature
electrons available to screen the moments of the f elec-       dependence of the photoemission spectra with experi-
trons. Figure 6a in Pruschke et al. (2000) shows the           mental data on YbInCu4 showed good agreement. A
corresponding f -spectral function, which consequently         ferromagnetic version of the Kondo lattice model with
now displays metallic (heavy fermion) behavior. The            Coulomb interactions in the conduction band was stud-
corresponding lattice coherence scale is now reduced as        ied by Liebsch and Costi (2006) in the context of the or-
compared to TK , see Fig. 8 in Pruschke et al. (2000)          bitally selective Mott phase of the two-band Hubbard
where the dependence of both T0 and TK on nc is plot-          model with inequivalent bands. The physics of this
ted. However, in contrast to Nozières original claim, i.e.    model is quite different to the usual Kondo lattice model.
T0 ∝ (TK )2 , a behavior T0 ∝ TK is found, with a prefactor    In particular, one finds, as in Biermann et al. (2005),
decreasing exponentially with decreasing nc . Again, the       non-Fermi liquid or bad metallic behavior, depending
ability of the NRG to accurately identify exponentially        on whether the ferromagnetic exchange is isotropic or
small energy scales proves to be of great value here.          anisotropic, respectively.
   Another route to metallic behavior in the PAM is to            All these results have been obtained for the paramag-
incorporate a dispersion of the f electrons of the form        netic phases of the PAM or Kondo lattice model. Of
                   X  †             †
                                                              course, the presence of localized moments implies the
                tf        fiσ fjσ + fjσ fiσ .         (145)    possibility for magnetic ordering, which is frequently ob-
                 <ij>,σ                                        served in heavy fermion compounds, partly in close vicin-
The effect of such a dispersion term – in particular the       ity to superconducting phases. These issues have not
closing of the gap upon increasing tf – has been studied       been addressed yet with the NRG, but, as has been
in detail in Shimizu et al. (2000) for both the particle-      demonstrated for the Hubbard model, are of course acces-
hole symmetric and asymmetric cases. The authors of            sible with this method and are surely a promising project
this work also study the relation between charge and spin      for future NRG calculations for the PAM or Kondo lat-
gaps in the dynamical susceptibilities and the hybridiza-      tice model within the DMFT.
tion gap in the spectral function.                                Magnetic quantum phase transitions in the Kondo lat-
   A metallic ground state of the particle-hole symmetric      tice model have been the focus of calculations within the
PAM can also be realized when the hybridization be-            extended DMFT (Si et al., 2001), for which the effective
tween f electrons and c electrons is only between nearest      impurity model includes a coupling to both fermionic and
neighbors:                                                     bosonic baths. The NRG has been generalized to such
                                                              types of impurity models, see Sec. IV.E, and recent ap-
               V : i, j nearest neighbors                      plications of the NRG within the extended DMFT are
      Vij =                                         (146)
                0 : otherwise               .                  discussed in Glossop and Ingersent (2006b); Zhu et al.
                                                               (2006).
For T = 0, the PAM with nearest-neighbor hybridiza-
tion shows a notable difference to the models discussed
above: the low-energy scale T0 does no longer depend           C. Lattice models with phonons
exponentially on U but vanishes at a finite critical Uc
(Held and Bulla, 2000). This behavior is reminiscent of          Let us consider the Hubbard model Eq. (142) and sup-
the physics of the Mott-transition in the Hubbard model.       plement it by a local coupling of the electron density
The difference, however, is that in the PAM defined by         to the displacement of Einstein phonons with frequency
(143) and (146) the Mott-transition occurs only in the         ω0 . This results in the Hubbard-Holstein model with the
subsystem of the f electrons – a gap opens in the f            Hamiltonian
electron spectral function while the c electron part still                X †            X †             X †
has finite spectral weight at the Fermi level (see Fig. 3        H = ε       ciσ ciσ − t     ciσ cjσ + U  ci↑ ci↑ c†i↓ ci↓
in Held and Bulla (2000)) so that the overall system re-                  iσ           <ij>σ              i
mains metallic.                                                           X †     
                                                                            bi + bi c†iσ ciσ + ω0
                                                                                                  X †
                                                                       +g                          bi bi .          (147)
   The calculations described so far have all been re-
                                                                               iσ                     i
stricted to T = 0. Finite temperature calculations for
single-particle and magnetic excitation spectra have been      The limit U → 0 of this Hamiltonian gives the Holstein
presented in Costi and Manini (2002) for the Kondo lat-        model, still a highly non-trivial model as discussed in the
tice model. As in Pruschke et al. (2000), one focus            following.
                                                                                                                               49

   Within DMFT, the model Eq. (147) maps onto the             can possibly be accomplished by considering additional
Anderson-Holstein (impurity) model, to which the NRG          orbital degrees of freedom.
method has been first applied by Hewson and Meyer
(2002), see Sec. IV.E. The self-consistency equations are             0.9
the same for both Hubbard-Holstein and the pure Hub-                  0.8
bard model, the only difference lies in the calculation of                    bipolaronic
                                                                      0.7
the self-energy for the effective impurity model which now
contains an additional contribution from the coupling to              0.6
the phonons. This contribution can also be calculated as              0.5
a ratio of two correlation functions.




                                                                  g
                                                                      0.4
   From a technical point of view, there is no difference
in the NRG-treatment of the Hubbard-Holstein model                    0.3
                                                                                            metallic
with either finite or zero value of U . Historically, the             0.2                                        Mott
first applications of the NRG have been for the U = 0-                                                         insulator
                                                                      0.1
case (the Holstein model, see Meyer et al. (2002) and
Meyer and Hewson (2003)) and have already revealed a                   0
                                                                        0     1     2       3    4     5   6      7        8
number of interesting results. As compared to other                                              U
methods applied to the Holstein-model, the advantage
of the NRG combined with the DMFT is that it is non-          FIG. 27 Phase diagram of the half-filled Hubbard-Holstein
perturbative in both g and U and that it allows to study      model for T = 0 (figure adapted from Koller et al. (2004a)).
the case of a macroscopic electron density (in contrast to    The thick solid lines denote the phase boundaries while the
the few electron case).                                       dashed line corresponds to Ueff = U −2g 2 /ω0 = 0. The dashed
                                                              and dot-dashed lines are polaronic lines, see Koller et al.
   For the half-filled case, the investigations of
                                                              (2004a).
Meyer et al. (2002) showed some unexpected properties
for the transition from a metal to a bipolaronic insula-
                                                                 Recently, the Hubbard-Holstein model has been stud-
tor at a critical coupling gc . In contrast to the Mott
                                                              ied for the quarter-filled case and large values of U
transition in the Hubbard model, no hysteresis and no
                                                              (Koller et al., 2005a). In this situation, a strongly renor-
preformed gap is observed here (at least for small values
                                                              malized band of polaronic quasiparticle excitations oc-
of ω0 ) which indicates that the physics of the transition
                                                              curs within the lower Hubbard band of the electronic
to the bipolaronic insulator might be completely different
                                                              spectral function.
(whether it is connected to locally critical behavior is an
                                                                 All the investigations of lattice models with electron-
interesting subject for future research).
                                                              phonon coupling described in this section have been re-
   For large values of ω0 , the physics of the transi-        stricted to T = 0 and to phases without long-range or-
tion is getting closer to that of the Hubbard model           der. Generalizations to finite temperatures and ordered
(Meyer and Hewson, 2003). This is because in the ω0 →         phases (such as superconducting and charge ordered
∞-limit the Holstein model can be mapped onto the at-         phases) appear to be possible within the DMFT/NRG
tractive Hubbard model which has the same behavior as         approach and will certainly give interesting results and
the repulsive Hubbard model when charge and spin de-          new insights. Other possible generalizations are different
grees of freedom are interchanged.                            types of lattice models, such as the periodic Anderson
   The phase diagram of the Hubbard-Holstein model at         model and multi-orbital models, and models with a dif-
half-filling, T = 0, and neglecting any long-range or-        ferent type of coupling between electrons and phonons.
dered phases has been discussed in detail in Koller et al.
(2004b), Jeon et al. (2004), and Koller et al. (2004a).
The main features are summarized in Fig. 27 which shows       VI. SUMMARY
the position of the phase boundaries between metallic,
Mott-insulating, and bipolaronic insulating phases. The         Let us first summarize here the main purpose of this
nature of these various transitions, together with the be-    review:
havior of dynamic quantities has been discussed in detail
                                                                (i) To give a general introduction to the basic concepts
in Koller et al. (2004a). Let us point out here the behav-
                                                                    of the numerical renormalization group approach
ior of the phonon spectral function which shows a consid-
                                                                    (Sec. II) and to the general strategy for the cal-
erable phonon softening upon approaching the transition
                                                                    culation of physical quantities within this method
to the bipolaronic insulator. Such a softening is absent in
                                                                    (Sec. III).
the approach to the Mott insulator, for the simple reason
that close to the Mott transition, where charge fluctua-       (ii) To cover the whole range of applications over the
tions are strongly suppressed, the phonons are effectively          last 25 years, following the seminal work of Wilson
decoupled from the electrons. One of the interesting top-           (1975a) on the Kondo problem and the work of
ics for future research are models which do show such a             Krishna-murthy et al. (1980a) on the Anderson im-
phonon softening even close to the Mott transition; this            purity model (Secs. IV and V).
                                                                                                                       50

Apparently, the range of applicability of the NRG               From a conceptual point of view it will be very inter-
widened considerably, in particular over the last ten        esting to view the NRG in a broader context. One step in
years. This can be easily seen in the list of references     this direction has been made in Verstraete et al. (2005).
in which more than 50% of the entries are from the years     The authors of this work interpret the NRG iteration in
starting with 2000. In physical terms, the NRG is now        terms of matrix product states, and establish a connec-
being used to study very different phenomena of con-         tion to the widely used density matrix renormalization
densed matter physics: Typical correlation phenomena         group method.
such as the Mott transition and heavy-fermion behavior,         Concerning the future prospects of the numerical
the physics of a two-state system in a dissipative envi-     renormalization group, let us conclude with a remark
ronment, Kondo correlations in artificial atoms such as      from Wilson’s original paper (Wilson (1975a), page 777),
quantum dots, to name but a few. Of course, we ex-           about the prospects of the renormalization group in gen-
pect that there are still very many problems to which        eral:
the NRG will be applied in the future, and we hope that
this review will be helpful as a starting point for such               ... However, most of the unsolved prob-
investigations.                                                    lems in physics and theoretical chemistry are
   Some of the concepts discussed in Secs. II and III are          of the kind the renormalization group is in-
fairly recent developments: For example the generaliza-            tended to solve (other kinds of problems do
tion of the NRG to quantum impurities coupled to a                 not remain unsolved for long). It is likely that
bosonic environment (see also Sec. IV.E) and the calcu-            there will be a vast extension of the renor-
lation of time-dependent quantities (transient dynamics,           malization group over the next decade as the
see Sec. III.B.3). As only a few applications of these new         methods become more clever and powerful;
concepts have been considered so far, one line of future           there are very few areas in either elementary
research of the NRG is their generalization to a broader           particle physics, solid state physics, or the-
class of impurity models.                                          oretical chemistry that are permanently im-
   We already discussed some open issues and ideas                 mune to this infection.
for further investigations in the various subsections of
Secs. IV and V. Let us mention here a few suggestions
for further generalizations and applications of the NRG:     Acknowledgments
   • Application of the bosonic NRG to generalizations
                                                                It is a pleasure to acknowledge many useful discus-
     of the spin-boson models such as coupled spins in
                                                             sions on the topic of this review with present and for-
     a dissipative environment.
                                                             mer colleagues, including F.B. Anders, J. Bonča, L.
   • Magnetic, orbital and charge ordering in lattice        Borda, S. Florens, J. Freericks, A.C. Hewson, W. Hof-
     models within DMFT.                                     stetter, K. Ingersent, S. Kehrein, J. Kroha, D. Logan,
                                                             N. Manini, A. Rosch, C. Varma, M. Vojta, D. Voll-
   • Application of multiple-shell techniques (Sec. III.B)   hardt, J. von Delft, P. Wölfle, G. Zaránd, A. Zawad-
     to further improvement of the dynamics, particu-        owski, and V. Zlatić. This work was supported in
     larly at the lowest temperatures.                       part by the DFG through the collaborative research
   What are the main open issues of the NRG approach?        centers SFB 484 and SFB 602. We acknowledge su-
As discussed in Sec. IV.D, multi-site and multi-orbital      percomputer support by the Leibniz Computer Center,
models pose severe technical problems for the NRG, be-       the Max-Planck Computer Center Garching under grant
cause the Hilbert space increases dramatically with the      h0301, the Gesellschaft für wissenschaftliche Datenver-
number of orbitals. This limits, in particular, the ac-      arbeitung Göttingen (GWDG), the Norddeutscher Ver-
curacy in the calculation of dynamical quantities which      bund für Hoch- und Höchstleistungsrechnen (HLRN) un-
in turn restricts the applicability of the NRG to multi-     der project nip00015 and the John von Neumann Insti-
band models within DMFT (see Sec. V.A) or its exten-         tute for Computing (Jülich).
sions. Concerning dynamical quantities, another short-
coming of the present implementations of the NRG is the
rather poor resolution at high frequencies, for example      References
features such as the band edges of upper and lower Hub-
bard bands in the Hubbard model or the sharply peaked        Affleck, I., and A. W. W. Ludwig, 1992, Phys. Rev. Lett. 68,
and highly asymmetrical spin-resolved Kondo resonance          1046.
                                                             Affleck, I., A. W. W. Ludwig, and B. A. Jones, 1995, Phys.
at high magnetic fields, as shown in Fig. 7.                   Rev. B 52, 9528.
   A gradual improvement of the accuracy can, of course,     Affleck, I., A. W. W. Ludwig, H.-B. Pang, and D. L. Cox,
be achieved by simply increasing the computational ef-         1992, Phys. Rev. B 45, 7918.
fort, but for a real breakthrough (concerning multi-band     Alascio, B., R. Allub, and C. A. Balseiro, 1986, Phys. Rev. B
models and the high-energy resolution) we probably need        34, 4786.
completely new ideas and concepts.                           Allub, R., and A. A. Aligia, 1995, Phys. Rev. B 52, 7987.
                                                                                                                            51

Alzoubi, G. M., and N. O. Birge, 2006, Phys. Rev. Lett. 97,        I. Affleck, 2003, Phys. Rev. Lett. 91, 096401.
   226803.                                                       Chen, K., and C. Jayaprakash, 1995a, J. Phys.: Condens.
Anders, F. B., 2005, Phys. Rev. B 71, 121101.                      Matter 7, L491.
Anders, F. B., R. Bulla, and M. Vojta, 2006, cond-               Chen, K., and C. Jayaprakash, 1995b, Phys. Rev. B 52,
   mat/0607443 .                                                   14436.
Anders, F. B., and G. Czycholl, 2005, Phys. Rev. B 71,           Chen, K., and C. Jayaprakash, 1998, Phys. Rev. B 57, 5225.
   125101.                                                       Chen, K., C. Jayaprakash, and H. R. Krishnamurthy, 1987,
Anders, F. B., E. Lebanon, and A. Schiller, 2004, Phys. Rev.       Phys. Rev. Lett. 58, 929.
   B 70, 201306.                                                 Chen, K., C. Jayaprakash, and H. R. Krishnamurthy, 1992,
Anders, F. B., E. Lebanon, and A. Schiller, 2005, Physica B        Phys. Rev. B 45, 5368.
   359-361, 1381.                                                Chen, K., C. Jayaprakash, and H. R. Krishnamurthy, 1995,
Anders, F. B., and T. Pruschke, 2006, Phys. Rev. Lett. 96,         Phys. Rev. Lett. 58, 929.
   086404.                                                       Choi, H.-Y., T.-H. Park, and G. S. Jeon, 2003a, Int. J. of
Anders, F. B., and A. Schiller, 2005, Phys. Rev. Lett. 95,         Mod. Phys. B 17, 3381.
   196801.                                                       Choi, M.-S., N. Y. Hwang, and S.-R. E. Yang, 2003b, Phys.
Anders, F. B., and A. Schiller, 2006, cond-mat/0604517 .           Rev. B 67, 245323.
Anderson, P. W., 1961, Phys. Rev. 124, 41.                       Choi, M.-S., M. Lee, K. Kang, and W. Belzig, 2004a, Phys.
Anderson, P. W., 1967, Phys. Rev. Lett. 18, 1049.                  Rev. B 70, 020502.
Bäuerle, C., F. Mallet, F. Schopfer, D. Mailly, G. Eska, and    Choi, M.-S., D. Sánchez, and R. López, 2004b, Phys. Rev.
   L. Saminadayar, 2005, Phys. Rev. Lett. 95, 266805.              Lett. 92, 056601.
Biermann, S., L. de’Medici, and A. Georges, 2005, Phys. Rev.     Chui, S.-T., and J. W. Bray, 1978, Phys. Rev. B 18, 2426.
   Lett. 95, 206401.                                             Coleman, P., 1984, Phys. Rev. B 29, 3035.
Boese, D., W. Hofstetter, and H. Schoeller, 2002, Phys. Rev.     Coleman, P., L. B. Ioffe, and A. M. Tsvelik, 1995, Phys. Rev.
   B 66, 125315.                                                   B 52, 6611.
Borda, L., 2006, cond-mat/0611208 .                              Coleman, P., and A. J. Schofield, 1995, Phys. Rev. Lett. 75,
Borda, L., G. Zaránd, W. Hofstetter, B. I. Halperin, and          2184.
   J. von Delft, 2003, Phys. Rev. Lett. 90, 026602.              Cornaglia, P. S., and C. A. Balseiro, 2003, Phys. Rev. B 67,
Borda, L., G. Zaránd, and P. Simon, 2005, Phys. Rev. B 72,        205420.
   155311.                                                       Cornaglia, P. S., and D. R. Grempel, 2005a, Phys. Rev. B 71,
Bradley, S. C., R. Bulla, A. C. Hewson, and G.-M. Zhang,           245326.
   1999, Eur. Phys. J. B 11, 535.                                Cornaglia, P. S., and D. R. Grempel, 2005b, Phys. Rev. B 71,
Bray, J. W., and S. T. Chui, 1979, Phys. Rev. B 19, 4876.          075305.
Brito, J. J. S., and H. O. Frota, 1990, Phys. Rev. B 42, 6378.   Cornaglia, P. S., D. R. Grempel, and H. Ness, 2005, Phys.
Bulla, R., 1999, Phys. Rev. Lett. 83, 136.                         Rev. B 71, 075320.
Bulla, R., 2006, Phil. Mag. 86, 1877.                            Cornaglia, P. S., H. Ness, and D. R. Grempel, 2004, Phys.
Bulla, R., T. A. Costi, and D. Vollhardt, 2001, Phys. Rev. B       Rev. Lett. 93, 147201.
   64, 045103.                                                   Costa, S. C., C. A. Paula, V. L. Lı́bero, and L. N. Oliveira,
Bulla, R., M. T. Glossop, D. E. Logan, and T. Pruschke, 2000,      1997, Phys. Rev. B 55, 30.
   J. Phys.: Condens. Matter 12, 4899.                           Costi, T. A., 1997a, Phys. Rev. B 55, 3003.
Bulla, R., and A. C. Hewson, 1997, Z. Phys. B 104, 333.          Costi, T. A., 1997b, Phys. Rev. B 55, 6670.
Bulla, R., A. C. Hewson, and T. Pruschke, 1998, J. Phys.:        Costi, T. A., 1998, Phys. Rev. Lett. 80, 1038.
   Condens. Matter 10, 8365.                                     Costi, T. A., 1999, in Density-Matrix Renormalization - A
Bulla, R., A. C. Hewson, and G.-M. Zhang, 1997a, Phys. Rev.        New Numerical Method in Physics, edited by I. Peschel,
   B 56, 11721.                                                    X. Wang, M. Kaulke, and K. Hallberg (Springer), p. 3.
Bulla, R., H.-J. Lee, N.-H. Tong, and M. Vojta, 2005, Phys.      Costi, T. A., 2000, Phys. Rev. Lett. 85, 1504.
   Rev. B 71, 045122.                                            Costi, T. A., 2001, Phys. Rev. B 64, 241310.
Bulla, R., T. Pruschke, and A. C. Hewson, 1997b, J. Phys.:       Costi, T. A., 2003, in Concepts in Electron Correlations,
   Condens. Matter 9, 10463.                                       edited by A. C. Hewson and V. Zlatić (Kluwer Academic
Bulla, R., N.-H. Tong, and M. Vojta, 2003, Phys. Rev. Lett.        Publishers, Dordrecht), p. 247.
   91, 170601.                                                   Costi, T. A., and A. C. Hewson, 1990, Physica B 163, 179.
Bulla, R., and M. Vojta, 2003, in Concepts in Electron Cor-      Costi, T. A., and A. C. Hewson, 1991, Physica C 185-189,
   relations, edited by A. C. Hewson and V. Zlatić (Kluwer        2649.
   Academic Publishers, Dordrecht), p. 209.                      Costi, T. A., and A. C. Hewson, 1992a, J. Magn. and Magn.
Byczuk, K., W. Hofstetter, and D. Vollhardt, 2004, Phys.           Materials 108, 129.
   Rev. B 69, 045112.                                            Costi, T. A., and A. C. Hewson, 1992b, Phil. Mag. B 65,
Byczuk, K., W. Hofstetter, and D. Vollhardt, 2005, Phys.           1165.
   Rev. Lett. 94, 056404.                                        Costi, T. A., and A. C. Hewson, 1993, J. Phys.: Condens.
Campo, Jr., V. L., and L. N. Oliveira, 2003, Phys. Rev. B 68,      Matter 5, L361.
   035337.                                                       Costi, T. A., A. C. Hewson, and V. Zlatić, 1994a, J. Phys.:
Campo, Jr., V. L., and L. N. Oliveira, 2004, Phys. Rev. B 70,      Condens. Matter 6, 2519.
   153401.                                                       Costi, T. A., and C. Kieffer, 1996, Phys. Rev. Lett. 76, 1683.
Campo, Jr., V. L., and L. N. Oliveira, 2005, Phys. Rev. B 72,    Costi, T. A., J. Kroha, and P. Wölfle, 1996, Phys. Rev. B 53,
   104432.                                                         1850.
Castro Neto, A. H., E. Novais, L. Borda, G. Zaránd, and         Costi, T. A., and N. Manini, 2002, J. Low. Temp. Phys. 126,
                                                                                                                              52

  835.                                                               A. P. Murani, and C. A. Scott, 2002, Phys. Rev. Lett. 89,
Costi, T. A., and R. H. McKenzie, 2003, Phys. Rev. A 68,             147201.
  034301.                                                          Hallberg, K. A., 2006, Adv. Phys. 55, 477.
Costi, T. A., P. Schmitteckert, J. Kroha, and P. Wölfle, 1994b,   Hattori, K., 2005, J. Phys. Soc. Jpn. 74, 3135.
  Phys. Rev. Lett. 73, 1275.                                       Hattori, K., and K. Miyake, 2005, J. Phys. Soc. Jpn. 74, 2193.
Cox, D. L., H. O. Frota, L. N. Oliveira, and J. W. Wilkins,        Hattori, K., S. Yotsuhashi, and K. Miyake, 2005, J. Phys.
  1985, Phys. Rev. B 32, 555.                                        Soc. Jpn. 74, 839.
Cox, D. L., and A. Zawadowski, 1998, Adv. Phys. 47, 599.           Held, K., and R. Bulla, 2000, Eur. Phys. J. B 17, 7.
Cragg, D. M., and P. Lloyd, 1979, J. Phys. C: Solid St. Phys.      Helmes, R. W., M. Sindel, L. Borda, and J. von Delft, 2005,
  12, L215.                                                          Phys. Rev. B 72, 125301.
Cragg, D. M., P. Lloyd, and P. Nozières, 1980, J. Phys. C:        Hewson, A. C., 1993, The Kondo Problem to Heavy Fermions
  Solid St. Phys. 13, 803.                                           (Cambridge University Press, Cambridge).
Cronenwett, S. M., T. H. Oosterkamp, and L. P. Kouwen-             Hewson, A. C., 2005, J. Phys. Soc. Jpn. 74, 8.
  hoven, 1998, Science 281, 540.                                   Hewson, A. C., 2006, J. Phys.: Condens. Matter 18, 1815.
De Leo, L., and M. Fabrizio, 2004, Phys. Rev. B 69, 245114.        Hewson, A. C., J. Bauer, and A. Oguri, 2005, J. Phys.: Con-
De Leo, L., and M. Fabrizio, 2005, Phys. Rev. Lett. 94,              dens. Matter 17, 5413.
  236401.                                                          Hewson, A. C., and D. Meyer, 2002, J. Phys.: Condens. Mat-
Dias da Silva, L. G. G. V., N. P. Sandler, K. Ingersent, and         ter 14, 427.
  S. E. Ulloa, 2006, Phys. Rev. Lett. 97, 096603.                  Hewson, A. C., A. Oguri, and D. Meyer, 2004, Eur. Phys. J.
Doniach, S., 1977, Physica B 91, 231.                                B 40, 177.
Doniach, S., and M. Šunjić, 1970, J. Phys. C: Solid St. Phys.    Hofstetter, W., 2000, Phys. Rev. Lett. 85, 1508.
  3, 285.                                                          Hofstetter, W., R. Bulla, and D. Vollhardt, 2000, Phys. Rev.
Evangelou, S. N., and A. C. Hewson, 1982, J. Phys. C: Solid          Lett. 84, 4417.
  St. Phys. 15, 7073.                                              Hofstetter, W., J. König, and H. Schoeller, 2001, Phys. Rev.
Fabrizio, M., A. F. Ho, L. De Leo, and G. E. Santoro, 2003,          Lett. 87, 156803.
  Phys. Rev. Lett. 91, 246402.                                     Hofstetter, W., and H. Schoeller, 2002, Phys. Rev. Lett. 88,
Ferreira, J. V. B., and V. L. Libero, 2000, Phys. Rev. B. 61,        016803.
  10615.                                                           Hofstetter, W., and G. Zaránd, 2004, Phys. Rev. B 69,
Freericks, J. K., T. P. Devereaux, and R. Bulla, 2001, Phys.         235301.
  Rev. B 64, 233114.                                               Hotta, T., 2006, Phys. Rev. Lett. 96, 197201.
Freericks, J. K., T. P. Devereaux, R. Bulla, and T. Pruschke,      Imada, M., A. Fujimori, and Y. Tokura, 1998, Rev. Mod.
  2003, Phys. Rev. B 67, 155102.                                     Phys. 70, 1039.
Fritz, L., and M. Vojta, 2005, Phys. Rev. B 72, 212510.            Ingersent, K., 1996, Phys. Rev. B 54, 11936.
Frota, H. O., 2004, cond-mat/0401005 .                             Ingersent, K., B. A. Jones, and J. W. Wilkins, 1992, Phys.
Frota, H. O., and K. Flensberg, 1992, Phys. Rev. B 46, 15207.        Rev. Lett. 69, 2594.
Frota, H. O., and L. N. Oliveira, 1986, Phys. Rev. B 33, 7871.     Ingersent, K., A. W. W. Ludwig, and I. Affleck, 2005, Phys.
Galpin, M. R., D. E. Logan, and H. R. Krishnamurthy, 2006a,          Rev. Lett. 95, 257204.
  J. Phys.: Condens. Matter 18, 6571.                              Ingersent, K., and Q. M. Si, 2002, Phys. Rev. Lett. 89,
Galpin, M. R., D. E. Logan, and H. R. Krishnamurthy, 2006b,          076403.
  J. Phys.: Condens. Matter 18, 6545.                              Izumida, W., O. Sakai, and Y. Shimizu, 1997, J. Phys. Soc.
Gan, J., 1995, Phys. Rev. B 51, 8287.                                Jpn. 66, 717.
Garst, M., S. Kehrein, T. Pruschke, A. Rosch, and M. Vojta,        Izumida, W., O. Sakai, and Y. Shimizu, 1998, J. Phys. Soc.
  2004, Phys. Rev. B 69, 214413.                                     Jpn. 67, 2444.
Georges, A., S. Florens, and T. A. Costi, 2004, Journal de         Izumida, W., O. Sakai, and S. Suzuki, 2001a, J. Phys. Soc.
  Physique IV 114, 165.                                              Jpn. 70, 1045.
Georges, A., G. Kotliar, W. Krauth, and M. J. Rozenberg,           Izumida, W., O. Sakai, and S. Tarucha, 2001b, Phys. Rev.
  1996, Rev. Mod. Phys. 68, 13.                                      Lett. 87, 216803.
Gerland, U., J. von Delft, T. A. Costi, and Y. Oreg, 2000,         Jabben, T., N. Grewe, and F. Anders, 2005, Eur. Phys. J. B
  Phys. Rev. Lett. 84, 3710.                                         44, 47.
Glazman, L. I., and M. E. Raikh, 1988, JETP Lett. 47, 452.         Jayaprakash, C., H. R. Krishna-murthy, and J. W. Wilkins,
Glossop, M. T., and K. Ingersent, 2005, Phys. Rev. Lett. 95,         1981, Phys. Rev. Lett. 47, 737.
  067202.                                                          Jeon, G. S., T.-H. Park, and H.-Y. Choi, 2003, Phys. Rev. B
Glossop, M. T., and K. Ingersent, 2006a, cond-mat/0609589            68, 045106.
  .                                                                Jeon, G. S., T.-H. Park, J. H. Han, H. C. Lee, and H.-Y. Choi,
Glossop, M. T., and K. Ingersent, 2006b, cond-mat/0607566            2004, Phys. Rev. B 70, 125114.
  .                                                                Jones, B., 1990, in Field Theories in Condensed Matter
Goldenfeld, N., 1992, Lectures on Phase Transitions and the          Physics, edited by Z. Tesanović (Adison-Wesley, Redwood
  Renormalization Group (Perseus Books).                             City), p. 87.
Goldhaber-Gordon, D., J. Gores, M. A. Kastner, . H. Shtrik-        Jones, B. A., and C. M. Varma, 1987, Phys. Rev. Lett. 58,
  man, D. Mahalu, and U. Meirav, 1998, Phys. Rev. Lett.              843.
  81, 5225.                                                        Jones, B. A., C. M. Varma, and J. W. Wilkins, 1988, Phys.
Gonzalez-Buxton, C., and K. Ingersent, 1998, Phys. Rev. B            Rev. Lett. 61, 125.
  57, 14254.                                                       Kang, K., M.-S. Choi, and S. Lee, 2005, Phys. Rev. Lett. 71,
Goremychkin, E. A., R. Osborn, B. D. Rainford, . T. A. Costi,        045330.
                                                                                                                              53

Karski, M., C. Raas, and G. S. Uhrig, 2005, Phys. Rev. B 72,      Mahan, G. D., 1975, 29, 75.
   113110.                                                        Maier, T., M. Jarrell, T. Pruschke, and M. H. Hettler, 2005,
Killer, U., E.-W. Scheidt, G. Eickerling, H. Michor, J. Sereni,      Rev. Mod. Phys. 77, 1027.
   T. Pruschke, and S. Kehrein, 2004, Phys. Rev. Lett. 93,        Mallet, F., J. Ericsson, D. Mailly, S. Ünlübayir, D. Reuter,
   216404.                                                           A. Melnikov, A. D. Wieck, T. Micklitz, A. Rosch, T. A.
Kim, T.-S., L. N. Oliveira, and D. L. Cox, 1997, Phys. Rev.          Costi, L. Saminadayar, and C. Bäuerle, 2006, Phys. Rev.
   B 55, 12460.                                                      Lett. 97, 226804.
Koga, M., 2000, Phys. Rev. B 61, 395.                             Martinek, J., M. Sindel, L. Borda, J. Barnaś, J. König,
Koga, M., and D. L. Cox, 1999, Phys. Rev. Lett. 82, 2575.            G. Schön, and J. von Delft, 2003, Phys. Rev. Lett. 91,
Koga, M., and M. Matsumoto, 2002a, J. Phys. Soc. Jpn. 71,            247202.
   943.                                                           Matsumoto, M., and M. Koga, 2001, J. Phys. Soc. Jpn. 70,
Koga, M., and M. Matsumoto, 2002b, Phys. Rev. B 65,                  2860.
   094434.                                                        Matsumoto, M., and M. Koga, 2002, Phys. Rev. B 65, 024508.
Koga, M., and H. Shiba, 1995, J. Phys. Soc. Jpn. 64, 4345.        Mehta, P., N. Andrei, P. Coleman, L. Borda, and G. Zaránd,
Koga, M., and H. Shiba, 1996, J. Phys. Soc. Jpn. 65, 3007.           2005, Phys. Rev. B 72, 014430.
Kolesnychenko, O. Y., G. M. M. Heijnen, A. K. Zhuravlev,          Metzner, W., and D. Vollhardt, 1989, Phys. Rev. Lett. 62,
   R. de Kort, M. I. Katsnelson, A. I. Lichtenstein, and H. van      324.
   Kempen, 2005, Phys. Rev. B 72, 085456.                         Meyer, D., and A. C. Hewson, 2003, Acta. Phys. Pol. B 34,
Kolf, C., and J. Kroha, 2006, cond-mat/0610631 .                     769.
Koller, W., A. C. Hewson, and D. M. Edwards, 2005a, Phys.         Meyer, D., A. C. Hewson, and R. Bulla, 2002, Phys. Rev.
   Rev. Lett. 95, 256401.                                            Lett. 89, 196401.
Koller, W., A. C. Hewson, and D. Meyer, 2005b, Phys. Rev.         Micklitz, T., A. Altland, T. A. Costi, and A. Rosch, 2006a,
   B 72, 045117.                                                     Phys. Rev. Lett. 96, 226601.
Koller, W., D. Meyer, and A. C. Hewson, 2004a, Phys. Rev.         Micklitz, T., T. A. Costi, and A. Rosch, 2006b, cond-
   B 70, 155103.                                                     mat/0610304 .
Koller, W., D. Meyer, Y. Ōno, and A. C. Hewson, 2004b,           Millis, A. J., B. G. Kotliar, and B. Jones, 1990, in Field The-
   Europhys. Lett. 66, 559.                                          ories in Condensed Matter Physics, edited by Z. Tesanović
Krishna-murthy, H. R., J. W. Wilkins, and K. G. Wilson,              (Adison-Wesley, Redwood City), p. 159.
   1980a, Phys. Rev. B 21, 1003.                                  Mohanty, P., E. M. Jariwala, and R. A. Webb, 1997, Phys.
Krishna-murthy, H. R., J. W. Wilkins, and K. G. Wilson,              Rev. Lett. 78, 3366.
   1980b, Phys. Rev. B 21, 1044.                                  Müller-Hartmann, E., 1984, Z. Phys. B 57, 281.
Krug von Nidda, H.-A., R. Bulla, N. Büttgen, M. Heinrich,        Ng, T. K., and P. A. Lee, 1988, Phys. Rev. Lett. 61, 1768.
   and A. Loidl, 2003, Eur. Phys. J. B 34, 399.                   Noack, R. M., and S. R. Manmana, 2005, AIP Conf. Proc.
Kuchinskii, E. Z., I. A. Nekrasov, and M. V. Sadovskii, 2005,        789, 93.
   JETP Letters 82, 198.                                          Novais, E., A. H. Castro Neto, L. Borda, I. Affleck, and
Kusunose, H., 2005, J. Phys. Soc. Jpn. 74, 2157.                     G. Zaránd, 2005, Phys. Rev. B 72, 014417.
Kusunose, H., and Y. Kuramoto, 1999, J. Phys. Soc. Jpn. 68,       Nozières, P., 1974, J. of Low Temp. Phys. 17, 31.
   3960.                                                          Nozières, P., 1998, Eur. Phys. J. B 6, 447.
Kusunose, H., K. Miyake, Y. Shimizu, and O. Sakai, 1996,          Nozières, P., and A. Blandin, 1980, J. Physique 41, 193.
   Phys. Rev. Lett. 76, 271.                                      Nozières, P., and C. T. De Dominicis, 1969, Phys. Rev. 179,
Lebanon, E., A. Schiller, and F. B. Anders, 2003a, Phys. Rev.        1097.
   B 68, 041311.                                                  Oguri, A., Y. Tanaka, and A. C. Hewson, 2004, J. Phys. Soc.
Lebanon, E., A. Schiller, and F. B. Anders, 2003b, Phys. Rev.        Jpn. 73, 2494.
   B 68, 155301.                                                  Oliveira, L. N., and J. W. Wilkins, 1981, Phys. Rev. B 24,
Lee, H.-J., R. Bulla, and M. Vojta, 2005, J. Phys.: Condens.         4863.
   Matter 17, 6935.                                               Oliveira, L. N., and J. W. Wilkins, 1985, Phys. Rev. B 32,
Lee, P. A., 1979, Phys. Rev. Lett. 42, 1492.                         696.
Leggett, A. J., S. Chakravarty, A. T. Dorsey, M. P. A. Fisher,    Oliveira, W. C., and L. N. Oliveira, 1994, Phys. Rev. B 49,
   A. Garg, and W. Zwerger, 1987, Rev. Mod. Phys. 59, 1.             11986.
Li, M.-R., K. Le Hur, and W. Hofstetter, 2005, Phys. Rev.         Ōno, Y., R. Bulla, A. C. Hewson, and M. Potthoff, 2001, Eur.
   Lett. 95, 086406.                                                 Phys. J. B 22, 283.
Lı́bero, V. L., and L. N. Oliveira, 1990a, Phys. Rev. B 42,       Pang, H.-B., 1994, Phys. Rev. Lett. 73, 2736.
   3167.                                                          Pang, H.-B., and D. L. Cox, 1991, Phys. Rev. B 44, 9454.
Lı́bero, V. L., and L. N. Oliveira, 1990b, Phys. Rev. Lett. 65,   Paula, C. A., M. F. Silva, and L. N. Oliveira, 1999, Phys.
   2042.                                                             Rev. B 59, 85.
Liebsch, A., and T. A. Costi, 2006, Eur. Phys. J. B 51, 523.      Perakis, I. E., and C. M. Varma, 1994, Phys. Rev. B 49, 9041.
Limelette, P., P. Wzietek, S. Florens, A. Georges, T. A. Costi,   Perakis, I. E., C. M. Varma, and A. E. Ruckenstein, 1993,
   C. Pasquier, D. Jérome, C. Mézière, and P. Batail, 2003,       Phys. Rev. Lett. 70, 3467.
   Phys. Rev. Lett. 91, 016401.                                   Peters, R., and T. Pruschke, 2006, New J. Phys. 8, 127.
Logan, D. E., and M. T. Glossop, 2000, J. Phys.: Condens.         Peters, R., T. Pruschke, and F. B. Anders, 2006, Phys. Rev.
   Matter 12, 985.                                                   B 74, 245114.
Ma, S.-K., 1976, Modern Theory of Critical Phenomena              Pierre, F., A. B. Gougam, A. Anthore, H. Pothier, . D. Esteve,
   (Addison-Wesley).                                                 and N. O. Birge, 2003, Phys. Rev. B 68, 085413.
Mahan, G. D., 1967, Phys. Rev. 163, 612.                          Pietig, R., R. Bulla, and S. Blawid, 1999, Phys. Rev. Lett.
                                                                                                                             54

  82, 4046.                                                      Shimizu, Y., O. Sakai, and A. C. Hewson, 2000, J. Phys. Soc.
Pietri, R., K. Ingersent, and B. Andraka, 2001, Phys. Rev.          Jpn. 69, 1777.
  Lett. 86, 1090.                                                Shimizu, Y., O. Sakai, and T. Kasuya, 1990, Physica B 163,
Potthoff, M., 2003, Eur. Phys. J. B 36, 335.                        401.
Pruschke, T., 2005, Prog. Theor. Phys. Suppl. 160, 274.          Shimizu, Y., O. Sakai, and S. Suzuki, 1998, J. Phys. Soc. Jpn.
Pruschke, T., and R. Bulla, 2005, Eur. Phys. J. B 44, 217.          67, 2395.
Pruschke, T., R. Bulla, and M. Jarrell, 2000, Phys. Rev. B       Shimizu, Y., O. Sakai, and S. Suzuki, 1999b, Physica B 261,
  61, 12799.                                                        366.
Pruschke, T., M. Jarrell, and J. K. Freericks, 1995, Adv. in     Si, Q., S. Rabello, K. Ingersent, and J. L. Smith, 2001, Nature
  Phys. 44, 187.                                                    413, 804.
Pruschke, T., and R. Zitzler, 2003, J. Phys.: Condens. Matter    Si, Q. M., J. L. Smith, and K. Ingersent, 1999, Int. Journ.
  15, 7867.                                                         Mod. Phys. B 13, 2331.
Pustilnik, M., and L. I. Glazman, 2001, Phys. Rev. B 64,         Silva, J. B., W. L. C. Lima, W. C. Oliveira, J. L. N. Mello,
  045328.                                                           L. N. Oliveira, and J. W. Wilkins, 1996, Phys. Rev. Lett.
Ramos, L. R., and V. L. Lı́bero, 2006, Phys. Rev. B 73,             76, 275.
  073101.                                                        Simon, P., P. S. Cornaglia, D. Feinberg, and C. A. Balseiro,
Ramos, L. R., W. C. Oliveira, and V. L. Lı́bero, 2003, Phys.        2006, cond-mat/0607794 .
  Rev. B 67, 085104.                                             Sindel, M., W. Hofstetter, J. von Delft, and M. Kindermann,
Romeike, C., M. R. Wegewijs, W. Hofstetter, and                     2005, Phys. Rev. Lett. 94, 196602.
  H. Schoeller, 2006a, Phys. Rev. Lett. 96, 206601.              Suzuki, S., O. Sakai, and Y. Shimizu, 1996, J. Phys. Soc. Jpn.
Romeike, C., M. R. Wegewijs, W. Hofstetter, and                     65, 4034.
  H. Schoeller, 2006b, Phys. Rev. Lett. 96, 196601.              Takayama, R., and O. Sakai, 1993, Physica B 188, 915.
Rosch, A., T. A. Costi, J. Paaske, and P. Wölfle, 2003, Phys.   Takayama, R., and O. Sakai, 1997, J. Phys. Soc. Jpn. 66,
  Rev. B 68, 014430.                                                1512.
Sadovskii, M. V., I. A. Nekrasov, E. Z. Kuchinskii, T. Pr-       Takegahara, K., Y. Shimizu, N. Goto, and O. Sakai, 1993,
  uschke, and V. I. Anisimov, 2005, Phys. Rev. B 72, 155105.        Physica B 186-188, 381.
Sakai, O., and W. Izumida, 2003, Physica B-Condensed Mat-        Takegahara, K., Y. Shimizu, and O. Sakai, 1992, J. Phys. Soc.
  ter 328, 125.                                                     Jpn. 61, 3443.
Sakai, O., and Y. Kuramoto, 1994, Solid State Commun. 89,        Tong, N.-H., S.-Q. Shen, and F.-C. Pu, 2001, Phys. Rev. B
  307.                                                              64, 235109.
Sakai, O., and Y. Shimizu, 1992a, J. Phys. Soc. Jpn 61, 2333.    Tong, N.-H., and M. Vojta, 2006, Phys. Rev. Lett. 97, 016802.
Sakai, O., and Y. Shimizu, 1992b, J. Phys. Soc. Jpn 61, 2348.    Tornow, S., N.-H. Tong, and R. Bulla, 2006a, J. Phys.: Con-
Sakai, O., Y. Shimizu, and N. Kaneko, 1993a, Physica B 186-         dens. Matter 18, 5985.
  188, 323.                                                      Tornow, S., N.-H. Tong, and R. Bulla, 2006b, Europhys. Lett.
Sakai, O., Y. Shimizu, and T. Kasuya, 1989, J. Phys. Soc.           73, 913.
  Jpn. 58, 3666.                                                 v. Löhneysen, H., A. Rosch, and P. W. M. Vojta, 2006, cond-
Sakai, O., Y. Shimizu, and T. Kasuya, 1990, Solid State Com-        mat/0606317 .
  mun. 75, 81.                                                   Vavilov, M. G., and L. I. Glazman, 2003, Phys. Rev. B 67,
Sakai, O., Y. Shimizu, H. Shiba, and K. Satori, 1993b, J.           115310.
  Phys. Soc. Jpn. 62, 3181.                                      Verstraete, F., A. Weichselbaum, U. Schollwöck, J. I. Cirac,
Sakai, O., S. Suzuki, and Y. Shimizu, 1997, Solid State Com-        and J. von Delft, 2005, cond-mat/0504305 .
  mun. 101, 791.                                                 Vidhyadhiraja, N. S., and D. E. Logan, 2004, Eur. Phys. J. B
Sakai, O., S. Suzuki, Y. Shimizu, H. Kusunose, and                  39, 313.
  K. Miyake, 1996, Solid State Commun. 99, 461.                  Vojta, M., 2006, Phil. Mag. 86, 1807.
Salmhofer, M., 1999, Renormalization (Springer Verlag            Vojta, M., and R. Bulla, 2002a, Eur. Phys. J. B 28, 283.
  Berlin-Heidelberg-New York).                                   Vojta, M., and R. Bulla, 2002b, Phys. Rev. B 65, 014511.
Sasaki, S., S. De Francheschi, J. M. Elzermann, W. G. van der    Vojta, M., R. Bulla, and W. Hofstetter, 2002a, Phys. Rev. B
  Wiel, M. Eto, S. Tarucha, and L. P. Kouwenhoven, 2000,            65, 140405.
  Nature 405, 764.                                               Vojta, M., N.-H. Tong, and R. Bulla, 2005, Phys. Rev. Lett.
Satori, K., H. Shiba, O. Sakai, and Y. Shimizu, 1992, J. Phys.      94, 070604.
  Soc. Jpn. 61, 3239.                                            Vojta, M., R. Zitzler, R. Bulla, and T. Pruschke, 2002b, Phys.
Scheidt, E.-W., F. Mayr, U. Killer, W. Scherer, H. Michor,          Rev. B 66, 134527.
  E. Bauer, S. Kehrein, T. Pruschke, and F. Anders, 2005,        Weichselbaum, A., and J. von Delft, 2006, cond-mat/0607497
  cond-mat/0506163 .                                                .
Schoeller, H., and J. König, 2000, Phys. Rev. Lett. 84, 3686.   White, S. R., and R. M. Noack, 1992, Phys. Rev. Lett. 68,
Schollwöck, U., 2005, Rev. Mod. Phys. 77, 259.                     3487.
Schopfer, F., C. Bäuerle, W. Rabaud, and L. Saminadayar,        van der Wiel, W. G., S. De Franceschi, J. M. Elzerman,
  2003, Phys. Rev. Lett. 90, 056801.                                S. Tarucha, and L. P. Kouwenhoven, 2002, Phys. Rev. Lett.
Schrieffer, R., and P. A. Wolff, 1966, Phys. Rev. 149, 491.         88, 126803.
Shimizu, Y., A. C. Hewson, and O. Sakai, 1999a, J. Phys.         van der Wiel, W. G., S. De Franceschi, T. Fujisawa, J. M. Elz-
  Soc. Jpn. 68, 2994.                                               erman, S. Tarucha, and L. P. Kouwenhoven, 2000, Science
Shimizu, Y., and O. Sakai, 1995, in Computational Physics as        289, 2105.
  a New Frontier in Condensed Matter Research (The Phys-         Wilson, K. G., 1975a, Rev. Mod. Phys. 47, 773.
  ical Society of Japan), p. 42.                                 Wilson, K. G., 1975b, Adv. in Math. 16, 170.
                                                                                                                           55

Wilson, K. G., and J. Kogut, 1974, Phys. Rep. 12, 75.           Zhu, J.-X., S. Kirchner, R. Bulla, and Q. Si, 2006, cond-
Withoff, D., and E. Fradkin, 1990, Phys. Rev. Lett. 64, 1835.       mat/0607567 .
Yanson, I. K., V. V. Fisun, R. Hesper, A. V. K. =, J. M.        Zhu, L., and C. M. Varma, 2006, cond-mat/0607426 .
  Krans, J. A. Mydosh, and J. M. van Ruitenbeek, 1995,          Zhuravlev, A. K., V. Y. Irkhin, and M. I. Katsnelson, 2005,
  Phys. Rev. Lett. 74, 302.                                         cond-mat/0512512 .
Yoshida, M., M. A. Whitaker, and L. N. Oliveira, 1990, Phys.    Zhuravlev, A. K., V. Y. Irkhin, M. I. Katsnelson, and A. I.
  Rev. B 41, 9403.                                                  Lichtenstein, 2004, Phys. Rev. Lett. 93, 236403.
Yoshioka, T., and Y. Ohashi, 1998, J. Phys. Soc. Jpn. 67,       Žitko, R., and J. Bonča, 2006a, cond-mat/0604287 .
  1332.                                                         Žitko, R., and J. Bonča, 2006b, Phys. Rev. B 74, 045312.
Yoshioka, T., and Y. Ohashi, 2000, J. Phys. Soc. Jpn. 69,       Zitzler, R., T. Pruschke, and R. Bulla, 2002, Eur. Phys. J. B
  1812.                                                             27, 473.
Yotsuhashi, S., and H. Maebashi, 2002, J. Phys. Soc. Jpn. 71,   Zitzler, R., N.-H. Tong, T. Pruschke, and R. Bulla, 2004,
  1705.                                                             Phys. Rev. Lett. 93, 016406.
Zaránd, G., L. Borda, J. von Delft, and N. Andrei, 2004,       Zlatić, V., T. A. Costi, A. C. Hewson, and B. R. Coles, 1993,
  Phys. Rev. Lett. 93, 107204.                                      Phys. Rev. B 48, 16152.
Zaránd, G., C.-H. Chung, P. Simon, and M. Vojta, 2006,
  Phys.Rev.Lett. 97, 166802.
