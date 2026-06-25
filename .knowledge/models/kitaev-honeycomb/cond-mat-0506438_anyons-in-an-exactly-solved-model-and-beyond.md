---
source: "https://arxiv.org/abs/cond-mat/0506438"
type: "arxiv"
canonical_id: "cond-mat/0506438"
title: "Anyons in an exactly solved model and beyond"
authors: "A. Kitaev"
year: "2005"
venue: "Annals of Physics"
arxiv_id: "cond-mat/0506438"
doi: "10.1016/j.aop.2005.10.005"
full_text: yes
---

# Anyons in an exactly solved model and beyond

**Authors:** A. Kitaev

**Citation:** Annals of Physics, vol. 321, pp. 2-111, 2005

**arXiv:** [cond-mat/0506438](https://arxiv.org/abs/cond-mat/0506438)

**DOI:** [10.1016/j.aop.2005.10.005](https://doi.org/10.1016/j.aop.2005.10.005)

## Abstract

A spin-1/2 system on a honeycomb lattice is studied. The interactions between nearest neighbors are of XX, YY or ZZ type, depending on the direction of the link; different types of interactions may differ in strength. The model is solved exactly by a reduction to free fermions in a static Z2 source gauge field. A phase diagram in the parameter space is obtained. One of the phases has an energy gap and carries excitations that are Abelian anyons. The other phase is gapless, but acquires a gap in the presence of magnetic field. In the latter case excitations are non-Abelian anyons whose braiding rules coincide with those of conformal blocks for the Ising model. We also consider a general theory of free fermions with a gapped spectrum, which is characterized by a spectral Chern number ν. The Abelian and non-Abelian phases of the original model correspond to ν = 0 and ν = ±1, respectively. The anyonic properties of excitation depend on ν mod 16, whereas ν itself governs edge thermal transport. The paper also provides mathematical background on anyons as well as an elementary theory of Chern number for quasidiagonal matrices.

## Full Text

Anyons in an exactly solved model and beyond
arXiv:cond-mat/0506438v3 [cond-mat.mes-hall] 1 Jan 2008




                                                                                                  Alexei Kitaev
                                                                         California Institute of Technology, Pasadena, CA 91125, U.S.A.
                                                                                            e-mail: kitaev@iqi.caltech.edu

                                                                                                 January 1, 2008

                                                                                                       Abstract
                                                                   A spin 1/2 system on a honeycomb lattice is studied. The interactions between nearest
                                                               neighbors are of XX, YY or ZZ type, depending on the direction of the link; different types
                                                               of interactions may differ in strength. The model is solved exactly by a reduction to free
                                                               fermions in a static Z2 gauge field. A phase diagram in the parameter space is obtained.
                                                               One of the phases has an energy gap and carries excitations that are Abelian anyons.
                                                               The other phase is gapless, but acquires a gap in the presence of magnetic field. In the
                                                               latter case excitations are non-Abelian anyons whose braiding rules coincide with those of
                                                               conformal blocks for the Ising model. We also consider a general theory of free fermions
                                                               with a gapped spectrum, which is characterized by a spectral Chern number ν. The
                                                               Abelian and non-Abelian phases of the original model correspond to ν = 0 and ν = ±1,
                                                               respectively. The anyonic properties of excitation depend on ν mod 16, whereas ν itself
                                                               governs edge thermal transport. The paper also provides mathematical background on
                                                               anyons as well as an elementary theory of Chern number for quasidiagonal matrices.


                                                          Contents
                                                          Introduction                                                                                        3

                                                          1 The model                                                                                        10

                                                          2 Representing spins by Majorana operators                                                         11
                                                            2.1 A general spin-fermion transformation . . . . . . . . . . . . . . . . . . . . . . .          11
                                                            2.2 Application to the concrete model . . . . . . . . . . . . . . . . . . . . . . . . . .        12
                                                            2.3 Path and loop operators . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .        14

                                                          3 Quadratic Hamiltonians                                                                           14

                                                          4 The spectrum of fermions and the phase diagram                                                   16

                                                          5 Properties of the gapped phases                                                            19
                                                            5.1 Perturbation theory study . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 19
                                                            5.2 Abelian anyons . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 21

                                                                                                           1
6 Phase B acquires a gap in the presence of magnetic field                                         23
  6.1 The conic singularity and the time-reversal symmetry . . . . . . . . . . . . . . .           23
  6.2 Derivation of an effective Hamiltonian . . . . . . . . . . . . . . . . . . . . . . .         24
  6.3 The spectrum and the Chern number . . . . . . . . . . . . . . . . . . . . . . . .            25

7 Edge modes and thermal transport                                                                 26

8 Non-Abelian anyons                                                                               28
  8.1 Bulk-edge correspondence . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .         29
  8.2 Unpaired Majorana modes . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .          31
  8.3 Fusion and braiding rules . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .      32
  8.4 Associativity relations . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .      34
  8.5 Algebraic consistency . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .      37
  8.6 Final details . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .    40

9 The sixteen-fold way                                                                             42

10 Odds and ends                                                                                   43

A Numerical results on the stability of the vortex-free phase                                      45

B Edge modes in phases Bν                                                                          47

C Quasidiagonal matrices                                                                           49
  C.1 The flow of a unitary matrix . . . . . . . . . . . . . . . . . . . . . . . . . . . . .       51
  C.2 General setting . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .      53
  C.3 Chern number . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .       54
  C.4 Majorana numbers . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .         57

D Some remarks on the chiral central charge                                              59
  D.1 The edge energy current and a bulk 2-current . . . . . . . . . . . . . . . . . . . 60
  D.2 Modular transformations beyond CFT . . . . . . . . . . . . . . . . . . . . . . . 63

E Algebraic theory of anyons                                                                       65
  E.1 Fusion theory . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . .      67
  E.2 Particle-antiparticle duality . . . . . . . . . . . . . . . . . . . . . . . . . . . . .      74
  E.3 Braiding and topological spin . . . . . . . . . . . . . . . . . . . . . . . . . . . .        80
  E.4 Verlinde algebra and topological S-matrix . . . . . . . . . . . . . . . . . . . . .          84
  E.5 Braiding nondegeneracy = modularity . . . . . . . . . . . . . . . . . . . . . . .            86
  E.6 Gauge freedom and Ocneanu rigidity . . . . . . . . . . . . . . . . . . . . . . . .           89
  E.7 Categorical formalism (aside) . . . . . . . . . . . . . . . . . . . . . . . . . . . .        94

F Weak symmetry breaking                                                                          104

Acknowledgments                                                                                   107

References                                                                                        107


                                                 2
Comments to the contents: What is this paper about?
Certainly, the main result of the paper is an exact solution of a particular two-dimensional
quantum model. However, I was sitting on that result for too long, trying to perfect it, derive
some properties of the model, and put them into a more general framework. Thus many
ramifications have come along. Some of them stem from the desire to avoid the use of conformal
field theory, which is more relevant to edge excitations rather than the bulk physics. This
program has been partially successful, but some rudiments of conformal field theory (namely,
the topological spin θa = e2πi(ha −ha ) and the chiral central charge c− = c − c) are still used.
    The paper is self-contained and provides an introduction into the subject. For most read-
ers, a good strategy is to follow the exposition through the beginning of Sec. 8, Nonabelian
anyons and take a glance at the rest of that section, where things become more technical. But
the mathematically inclined reader may be interested in those details, as well as some of the
appendices. I have tried to make the paper modular so that some parts of it can be understood
without detailed reading of the other. This has caused some redundancy though.
    Appendix E, Algebraic theory of anyons is an elementary introduction into unitary modular
categories, which generalizes the discussion in Sec. 8.
    Appendix C, Quasidiagonal matrices is also mostly expository but some of the arguments
may be new. It begins with a simplified treatment of “operator flow” and “noncommutative
Chern number” (the latter has been used to prove the quantization of Hall conductivity in
disordered systems [1]), but the main goal is to explain “unpaired Majorana modes”, a certain
parity phenomenon related to the Chern number.
    Appendix D on the chiral central charge and Appendix F on weak symmetry breaking contain
some raw ideas that might eventually develop into interesting theories.


Introduction
Overview of the subject. Anyons are particles with unusual statistics (neither Bose nor
Fermi), which can only occur in two dimensions. Quantum statistics may be understood as a
special kind of interaction: when two particles interchange along some specified trajectories, the
overall quantum state is multiplied by eiϕ . In three dimensions, there is only one topologically
distinct way to swap two particles. Two swaps are equivalent to the identity transformation,
hence eiϕ = ±1. On the contrary, in two dimensions the double swap corresponds to one
particle making a full turn around the other; this process is topologically nontrivial. Therefore
the exchange phase ϕ can, in principle, have any value — hence the name “anyon”. (However,
a stability consideration requires that ϕ be a rational multiple of 2π.) Of course, the real
question is whether such particles exist in nature or can be built somehow, but we will follow
the historic path, approaching the problem from the mathematical end.
    The study of anyons was initiated by Wilczek [2, 3] in early 1980’s. He proposed a simple
but rather abstract model, which was based on (2 + 1)-dimensional electrodynamics. This
theory has integer electric charges and vortices carrying magnetic flux (which is a real number
defined up to an integer). Considered separately, both kinds of particles are bosons. But when
a charge q goes around a vortex v, it picks up the phase 2πqv, known as the Aharonov-Bohm
phase. Thus, charges and vortices have nontrivial mutual statistics and therefore must be called


                                                3
anyons when considered together. Moreover, composite objects (q, v) consisting of a charge and
a vortex are anyons by themselves because they have nontrivial exchange phase ϕ(q,v) = 2πqv.
    A general way to describe quantum statistics is to consider particle worldlines in the (2 + 1)-
dimensional space-time. Such worldlines form a braid, therefore the statistics is characterized
by a representation of the braid group. In the preceding discussion we assumed that braiding
is characterized just by phase factors, i.e., that the representation is one-dimensional. The
corresponding anyons are called Abelian. But one can also consider multidimensional represen-
tations of the braid group; in this case the anyons are called non-Abelian. Actually, it may not
be so important how the braid group acts, but the very existence of a multidimensional space
associated with several particles is a key feature. Vectors in this space are quantum states that
have almost the same energy (see discussion of topological quantum computation below).
    Historically, the theory of non-Abelian anyons emerged from conformal theory (CFT). How-
ever, only topological and algebraic structure in CFT is relevant to anyons. Different pieces of
this structure were discovered in a colossal work of many people, culminating in the paper by
Moore and Seiberg [4]. Witten’s work on quantum Chern-Simons theory [5] was also very influ-
ential. A more abstract approach (based on local field theory) was developed by Fredenhagen,
Rehren, and Schroer [6] and by Frohlich and Gabbiani [7].
    The most amazing thing about anyons is that they actually exist as excitations in some
condensed matter systems. Such systems also have highly nontrivial ground states that are
described as possessing topological order. The best studied example (both theoretically and
experimentally) is the Laughlin state [8] in the fractional quantum Hall system at the filling
factor ν = 1/3. It carries Abelian anyons with exchange phase ϕ = π/3 and electric charge
±1/3. It is the fractional value of the charge that was predicted in original Laughlin’s paper and
confirmed by several methods, in particular by a shot noise measurement [9, 10]. The statistical
phase is a subtler property which is deduced theoretically [11, 12]; a nontrivial experimental
test has been performed recently using quasiparticle tunneling [13].
    A different kind of state is observed at the filling factor ν = 5/2, though it is more fragile and
less studied experimentally. There is much evidence suggesting that this system is described by
a beautiful theory proposed by Moore and Read [14, 15]. The Moore-Read state admits non-
Abelian anyons with charge ±1/4. If 2n such particles are present, the associated Hilbert space
has dimension 2n−1 . (The non-Abelian anyons studied in this paper have similar properties,
though there is no electric charge.)
    The notion of anyons assumes that the underlying state has an energy gap (at least for
topologically nontrivial quasiparticles). Otherwise excitations are not localizable and braiding
may not be defined. Note that if all excitations are gapped, then all equal-time correlators
decay exponentially with distance [16].
    An example of anyons in a spin-1/2 system originates from the theory of resonating valence
bond (RVB). The idea of RVB was put forward by Anderson [17] and used later as a model
of the undoped insulating phase in high-Tc cuprate superconductors [18]. Without electrically
charged holes, the problem seems to be described adequately by a Heisenberg-like Hamiltonian,
but its solution has proved very difficult. Several variants of an RVB state have been proposed,
both gapless and gapped. Here we discuss a particular gapped RVB phase, namely the one
which is realized on the triangular lattice [19], but which apparently exists on the square lattice
as well. This phase admits quasiparticles of four types: trivial excitations (such as spin waves),
spinons (spin-1/2 fermions, which are conserved modulo 2), Z2 -vortices (spinless bosons, also

                                                  4
                                a)                             b)

                 Figure 1: A classical vortex (a) distorted by fluctuations (b).

called visons), and spinon-vison composites [20]. The mutual statistics of spinons and visons is
characterized by the Aharonov-Bohm factor −1, therefore the composite particles are bosons.
Note that the relevance of this theory to cuprate superconductors is under debate. Senthil and
Fisher proposed an interesting way to detect visons in these materials [21], but the experiment
gave a negative result [22]. However, some kind of RVB state is likely to realize in a different
material, Cs2 CuCl4 . This conclusion is drawn from neutron-scattering experiments that have
shown the presence of spin-1/2 excitations [23].
    Anyonic particles are best viewed as a kind of topological defects that reveal non-trivial
properties of the ground state. Thus anyons carry some topological quantum numbers which
make them stable: a single particle cannot be annihilated locally but only through the fusion
with an antiparticle. An intuitive way to picture an anyon is to imagine a vortex in a medium
with a local order parameter (see Fig. 1a). Now suppose that quantum fluctuations are so
strong that the order parameter is completely washed out and only the topology remains (see
Fig. 1b). Of course, that is only a rough illustration. It resembles the Kosterlitz-Thouless phase
with power-law correlation decay, while in anyonic systems correlations decay exponentially due
to the energy gap.
    A real example can be constructed with spins on the edges of a square lattice. Basis states
of the spins are described by the variables sj = ±1, which may be regarded as a Z2 gauge field
(i.e., “vector potential”), whereas the “magnetic field intensity” on plaquette p is given by
                                                   Y
                                        wp =              sj .                                 (1)
                                              j∈boundary(p)


We say that there is a vortex on plaquette p if wp = −1. Now we may define the vortex-free
state:                          X
                      |Ψi = c        |si,       where s = (s1 , . . . , sN )           (2)
                               s: wp (s)=1
                                  for all p

(c is a normalization factor). The state with a single vortex on a given plaquetteQis defined
similarly. It is clear that the vortex can be detected by measuring the observable j∈l σjz for
any enclosing path l, though no local order parameter exists.
    The state (2) can be represented as the ground state of the following Hamiltonian with



                                                 5
four-body interaction [24]:
               X                X                                 Y                          Y
    H = −Je         As − Jm                Bp ,   where   As =             σjx ,   Bp =             σjz .   (3)
              vertices        plaquettes                         star(s)                  boundary(p)

Its elementary excitations are Z2 -charges with energy 2Je and vortices with energy 2Jm . Certain
essential features of this model are stable to small local perturbations (such as external magnetic
field or Heisenberg interaction between neighboring spins). Note that the robust characteristic
of excitations is not the energy or the property of being elementary, but rather superselection
sector. It is defined as a class of states that can be transformed one to another by local operators.
This particular model has the vacuum sector 1, the charge sector e, the vortex sector m, and
a charge-vortex composite ε. Particles of type e and m are bosons with nontrivial mutual
statistics, whereas ε is a fermion. Thus, the model represents a universality class of topological
order — actually, the same class as RVB.
    Anyonic superselection sectors may or may not be linked to conventional quantum num-
bers, like spin or electric charge. Most studies have been focused on the case where anyons
carry fractional electric charge or half-integer spin. Such anyons are potentially easier to find
experimentally because they contribute to collective effects (in particular, electric current) or
have characteristic selection rules for spin-dependent scattering. Chargeless and spinless quasi-
particles are generally harder to identify. But anyons, by virtue of their topological stability,
must have some observable signatures. For example, anyons can be trapped by impurities and
stay there for sufficiently long time, modifying the spectrum of local modes (magnons, excitons,
etc.). However, effective methods to observe anyons are yet to be found.
    Thus, the hunt for anyons and topological order is a difficult endeavor. Why do we care?
First, because these are conceptually important phenomena, breaking some paradigms. In
particular, consider these principles (which work well and provide important guidance in many
cases):

  1. Conservation laws come from symmetries (by Noether’s theorem or its quantum ana-
     logue);

  2. Symmetries are initially present in the Hamiltonian (or Lagrangian), but may be sponta-
     neously broken.
Let us limit our discussion to the case of gauge symmetries and local conservation laws, which
are described by fusion rules between superselection sectors. A profound understanding of the
first principle and its underlying assumptions is due to Doplicher and Roberts [25, 26]. They
proved that any consistent system of fusion rules for bosons is equivalent to the multiplication
rules for irreducible representations of some compact group. Fermions also fit into this frame-
work. However, anyonic fusion rules are not generally described by a group! As far as the
second principle is concerned, topological order does not require any preexisting symmetry but
leads to new conservation laws. Thus, the formation of topological order is exactly the opposite
of symmetry breaking!

Topological quantum computation. A more practical reason to look for anyons is their
potential use in quantum computing. In Ref. [24] I suggested that topologically ordered states
can serve as a physical analogue of error-correcting quantum codes. Thus, anyonic systems

                                                   6
provide a realization of quantum memory that is protected from decoherence. Some quantum
gates can be implemented by braiding; this implementation is exact and does not require
explicit error correction. Freedman, Larsen, and Wang [27] proved that for certain types of
non-Abelian anyons braiding enables one to perform universal quantum computation. This
scheme is usually referred to as topological quantum computation (TQC).
    Let us outline some basic principles of TQC. First, topologically ordered systems have
degenerate ground states under certain circumstances. In particular, the existence of Abelian
anyons implies the ground state degeneracy on the torus [28]. Indeed, consider a process in
which a particle-antiparticle pair is created, one of the particles winds around the torus, and
the pair is annihilated. Such a process corresponds to an operator acting on the ground state.
If A and B are such operators corresponding to two basic loops on the torus, then ABA−1 B −1
describes a process in which none of the particles effectively crosses the torus, but one of them
winds around the other. If the Aharonov-Bohm phase is nontrivial, then A and B do not
commute. Therefore they act on a multidimensional space.
    Actually, the degeneracy is not absolute but very precise. It is lifted due to virtual particle
tunneling across the torus, but this process is exponentially suppressed. Therefore the distance
between ground energy levels is proportional to exp(−L/ξ), where L the linear size of the torus
and ξ is some characteristic length, which is related to the gap in the excitation spectrum.
    In non-Abelian systems, degeneracy occurs even in the planar geometry when several anyons
are localized in some places far apart from each other (it is this space of quantum states the
braid group acts on). The underlying elementary property may be described as follows: two
given non-Abelian particles can fuse in several ways (like multi-dimensional representations
of a non-Abelian group). For example, the non-Abelian phase studied in this paper has the
following fusion rules:
                        ε × ε = 1,        ε × σ = σ,         σ × σ = 1 + ε,
where 1 is the vacuum sector, and ε and σ are some other superselection sectors. The last
rule is especially interesting: it means that two σ-particles may either annihilate or fuse into
an ε-particle. But when the σ-particles stay apart, 1 and ε correspond to two quantum states,
|ψ1σσ i and |ψεσσ i. These states are persistent. For example, if we create |ψεσσ i by splitting an ε
into two σ’s, wait some time, and fuse the σ-particles back, we will still get an ε-particle.
    Here is a subtler property: the fusion states |ψ1σσ i and |ψεσσ i are practically indistinguish-
able and have almost the same energy. In fact, a natural process that “distinguishes” them by
multiplying by different factors is tunneling of a virtual ε-particle between the fixed σ-particles
(which is possible since σ × ε = σ). However, ε-particles are gapped, therefore this process
is exponentially suppressed. Of course, this explanation depends on many details, but it is a
general principle that different fusion states can only be distinguished by transporting a quasi-
particle. Such processes are unlikely even in the presence of thermal bath and external noise,
as long as the temperature and the noise frequency are much smaller than the gap.
    In the above example, the two-particle fusion states |ψ1σσ i and |ψεσσ i cannot form coherent
superpositions because they belong to different superselection sectors (1 and ε, resp.). In order
to implement a qubit, one needs four σ-particles. A logical |0i is represented by the quantum
state |ξ1 i that is obtained by creating the pairs (1, 2) and (3, 4) from the vacuum (see Fig. 2). A
logical |1i is encoded by the complementary state |ξε i: we first create a pair of ε-particles, and
then split each of them into a σσ-pair. Note that both states belong to the vacuum sector and

                                                 7
     σ             σ          σ             σ             σ 1           2 σ       σ 1        2 σ
      1           2            1           2                                            ε   ε
                                       ε
                                       ε
      3           4            3           4
     σ            σ           σ            σ              σ 3           4 σ       σ 3           4 σ
          |ξ1 i                    |ξε i                        |η1 i                   |ηε i
                       Figure 2: Four ways to initialize an anyonic qubit.

therefore can form superpositions. Also shown in Fig. 2 are two alternative ways to initialize
the qubit, |η1 i and |ηε i. The detailed analysis presented in Secs. 8.4 and 8.5 implies that
                                1                           1             
                       |η1 i = √ |ξ1i + |ξε i ,       |ηε i = √ |ξ1 i − |ξε i .
                                 2                             2
Therefore we can performthe following gedanken experiment. We create the state |ξ1 i and then
measure the qubit in the |η1 i, |ηε i}-basis by fusing the pairs (1, 3) and (2, 4). With probability
1/2 both pairs annihilate, and with probability 1/2 we get two ε-particles. One can also think
of a simple robustness test for quantum states: if there is no decoherence, then both |ξ1 i and
|η1 i are persistent.
     As already mentioned, braiding is described by operators that are exact (up to virtual
quasiparticle tunneling). Indeed, the operators of counterclockwise exchange between two par-
ticles (R-matrices) are related to the fusion rules by so-called hexagon equations and pentagon
equation. We will see on concrete exapmles that these equations have only a finite number of
solutions and therefore do not admit small deformations. In general, it is a nontrivial theorem
known as Ocneanu rigidity [29, 30], see Sec. E.6.
     Thus, we have all essential elements of a quantum computer implemented in a robust fashion:
an initial state is made by creating pairs and/or by splitting particles, unitary gates are realized
by braiding, and measurements are performed by fusion. This “purely topological” scheme is
universal for sufficiently complicated phases such as the k = 3 parafermion state [31], lattice
models based on some finite groups (e.g. S5 [24], A5 [32, 33] and S3 [34]), and double Chern-
Simons models [35, 36, 37]. Unfortunately, the model studied in this paper is not universal
in this sense. One can, however, combine a topologically protected quantum memory with a
nontopological realization of gates (using explicit error correction). Note that some weak form
of topological protection is possible even in one-dimensional Josephson junction arrays [38],
which is due to the build-in U(1)-symmetry. Several other schemes of Josephson junction-
based topological quantum memory have been proposed recently [39, 40, 41].
     Unlike many other quantum computation proposals, TQC should not have serious scalability
issues. What is usually considered an initial step, i.e., implementing a single gate, may actually
be close to the solution of the whole problem. It is an extremely challenging task, though. It
demands the ability to control individual quasiparticles, which is beyond the reach of present
technology. One should however keep in mind that the ultimate goal is to build a practical
quantum computer, which will contain at least a few hundred logical qubits and involve error-
correcting coding: either in software (with considerable overhead) or by topological protection
or maybe by some other means. At any rate, that is a task for the technology of the future.


                                                  8
But for the meantime, finding and studying topological phases seems to be a very reasonable
goal, also attractive from the fundamental science perspective.

Comparison with earlier work and a summary of the results. In this paper we study
a particular exactly solvable spin model on a two-dimensional lattice. It only involves two-body
interactions and therefore is simpler than Hamiltonian (3) considered in [24], but the solution
is less trivial. It is not clear how to realize this model in solid state, but an optical lattice
implementation has been proposed [42].
    The model has two phases (denoted by A and B) which occur at different values of param-
eters. The exact solution is obtained by a reduction to free real fermions. Thus quasiparticles
in the system may be characterized as fermions and Z2 -vortices. Vortices and fermions interact
by the Aharonov-Bohm factor equal to −1. In phase A the fermions have an energy gap, and
the vortices are bosons that fall into two distinct superselection sectors. (Interestingly enough,
the two types of vortices have identical physical properties and are related to each other by a
lattice translation.) The overall particle classification, fusion rules, and statistics are the same
as in the model (2) or RVB. In phase B the fermions are gapless and there is only one type of
vortices with undefined statistics. Adding a magnetic field to the Hamiltonian opens a gap in
the fermionic spectrum, and the vortices become non-Abelian anyons. The difference between
the vortex statistics in phase A and phase B with the magnetic field may be attributed to
different topology of fermionic pairing.
    Topological properties of Fermi-systems were first studied in the theory of integer quantum
Hall effect [43, 44]. Let us outline the main result. To begin with, the Hall conductivity of
noninteracting electrons in a periodic potential (e.g., in the Hofstadter model with m/n flux
quanta per plaquette) is expressed in terms of a single-electron Hamiltonian in the Fourier basis.
Such a Hamiltonian is an n × n matrix that depends on the momentum q. For each value of q
one can define a subspace L(q) ⊆ Cn that is associated with negative-energy states, i.e., ones
that are occupied by electrons. Thus, a vector bundle over the momentum space is defined.
The quantized Hall conductivity is proportional to the Chern number of this bundle. Bellissard
at al [1] have generalized this theory to disordered systems by using a powerful mathematical
theory called noncommutative geometry [45].
    Even more interesting topological phenomena occur when the number of particles is not
conserved (due to the presence of terms like a†j a†k , as in the mean-field description of supercon-
ductors). In this case the single-electron Hamiltonian is replaced by a more general object, the
Bogolyubov-Nambu matrix. It also has an associated Chern number ν, which is twice the num-
ber defined above when the previous definition is applicable. But in general ν is an arbitrary
integer. The first physical example of this kind, the 3 He-A film, was studied by Volovik [46].
Volovik and Yakovenko [47] showed that the Chern number in this system determines the statis-
tics of solitons. More recently, Read and Green [48] considered BCS pairing of spinless particles
with angular momentum l = −1. They identified a “strong pairing phase” with zero Chern
number and a “weak pairing phase” with ν = 1. The latter is closely related to the Moore-Read
state and has non-Abelian vortices and chiral edge modes.
    In the present paper, these results are generalized to an arbitrary Fermi-system described
by a quadratic Hamiltonian on a two-dimensional lattice. We show that Z2 -vortices are Abelian
particles when the Chern number ν is even and non-Abelian anyons when ν is odd. The non-
Abelian statistics is due to unpaired Majorana modes associated with vortices. Our method


                                                 9
relies on a quasidiagonal matrix formalism (see Appendix C), which is similar to, but more
elementary than, noncommutative geometry. It can also be applied to disordered systems.
    Furthermore, we find that there are actually 16 (8 Abelian and 8 non-Abelian) types of
vortex-fermion statistics, which correspond to different values of ν mod 16. Only three of them
(for ν = 0, ±1) are realized in the original spin model. We give a complete algebraic description
of all 16 cases, see tables on pages 30, 41, and 42.


1    The model
We study a spin-1/2 system in which spins are located at the vertices of a honeycomb lattice,
see Fig. 3a. This lattice consists of two equivalent simple sublattices, referred to as “even” and

                 x               y           x               y       x                y        x               y       x               y       x               y

             z                           z                       z                         z                       z                       z                       z
                     y       x                   y       x               y        x                y       x               y       x               y       x

                         z                           z                        z                        z                       z                       z
                 x               y           x               y       x                y        x               y       x               y       x               y
                                                                                                                                                                                 x        y   z
             z                           z                       z                         z                       z                       z                       z
                     y       x                   y       x               y        x                y       x               y       x               y       x



                                                                                      a)                                                                                             b)
                                 Figure 3: Three types of links in the honeycomb lattice.

“odd” (they are shown by empty and full circles in the figure). A unit cell of the lattice contains
one vertex of each kind. Links are divided into three types, depending on their direction (see
Fig. 3b); we call them “x-links”, “y-links”, and “z-links”. The Hamiltonian is as follows:
                                 X                 X y y         X
                      H = −Jx         σjx σkx − Jy    σj σk − Jz     σjz σkz ,                  (4)
                                                                             x-links                                           y-links                                 z-links

where Jx , Jy , Jz are model parameters.
   Let us introduce a special notation for the individual terms in the Hamiltonian:
                                    x x
                                    σj σk , if (j, k) is an x-link;
                             Kjk =    σjx σky , if (j, k) is an y-link;                                                                                                                           (5)
                                    x z
                                      σj σk , if (j, k) is an z-link.
Remarkably, all operators Kjk commute with the following operators Wp , which are associated
to lattice plaquettes (i.e., hexagons):
                                     z
                     y                                   x
                                     3
                         2                       4
                         1
                                     p
                                                 5
                                                                                          Wp = σ1x σ2y σ3z σ4x σ5y σ6z = K12 K23 K34 K45 K56 K61 .                                                (6)
                 x                   6                       y

                                     z


                                                                                                                           10
Here p is a label of the plaquette. Note that different operators Wp commute with each other.
   Thus Hamiltonian (4) has the set of “integrals of motion” Wp , which greatly simplifies the
problem. In order to find eigenstates of the Hamiltonian, we first divide the total Hilbert space
L into sectors — eigenspaces of Wp , which are also invariant subspaces of H. This can be
written as follows:                         M
                                     L=           Lw1 ,...,wm ,                               (7)
                                            w1 ,...,wm

where m is the number of plaquettes. Each operator Wp has eigenvalues +1 and −1, therefore
each sector corresponds to a choice of wp = ±1 for each plaquette p. Then we need to solve for
the eigenvalues of the Hamiltonian restricted to a particular sector Lw1 ,...wm .
    The honeycomb lattice has 1/2 plaquette per vertex, therefore m ≈ n/2, where n is the
number of vertices. It follows that the dimension of each sector is ∼ 2n /2m ∼ 2n/2 (we will
in fact see that all these dimensions are equal). Thus splitting into sectors does not solve the
problem yet. Fortunately, it turns out that the degrees of freedom within each sector can be
described as real (Majorana) fermions, and the restricted Hamiltonian is simply a quadratic
form in Majorana operators. This makes an exact solution possible.


2     Representing spins by Majorana operators
2.1    A general spin-fermion transformation
Let us remind the reader some general formalism pertaining to Fermi systems. A system
with n fermionic modes is usually described by the annihilation and creation operators ak , a†k
(k = 1, . . . , n). Instead, one can use their linear combinations,

                                                                 ak − a†k
                              c2k−1 = ak + a†k ,         c2k =            ,
                                                                    i
which are called Majorana operators. The operators cj (j = 1, . . . , 2n) are Hermitian and obey
the following relations:
                            c2j = 1,      cj cl = −cl cj if j 6= l.                          (8)
Note that all operators cj can be treated on equal basis.
   We now describe a representation of a spin by two fermionic modes, i.e., by four Majorana
operators. Let us denote these operators by bx , by , bz , and c (instead of c1 , c2 , c3 , c4 ). The
Majorana operators act on the 4-dimensional Fock space M,    f whereas the Hilbert space of a
                                                            f
spin is identified with a two-dimensional subspace M ⊂ M defined by this condition:

                 |ξi ∈ M if and only if D|ξi = |ξi,              where D = bx by bz c.           (9)

We call M and M f the physical subspace and the extended space, respectively; the operator D
may be thought of as a gauge transformation for the group Z2 .
   The Pauli operator σ x , σ y , σ z can be represented by some operators σ
                                                                           ex, σey , σez acting on
                                                                              x     y
the extended space. Such a representation must satisfy two conditions: (1) σ e ,σe ,σ  ez preserve



                                                   11
the subspace M; (2) when restricted to M, the operators σ          ex , σ
                                                                        ey , σ
                                                                             ez obey the same algebraic
relations as σ x , σ y , σ z . We will use the following particular representation:
                              z
                              b

                        x     c        y            ex = ibx c,
                                                    σ                   ey = iby c,
                                                                        σ                    ez = ibz c.
                                                                                             σ                         (10)
                       b           b


(We have associated the Majorana operators with four dots for a reason that will be clear later.)
                                     eα (α = x, y, z) commutes with D (so that M is preserved),
This representation is correct since σ
 σ α )† = σ
(e        eα , (e
                σ α )2 = 1, and
                                     ex σ
                                     σ  ey σ
                                           ez = ibx by bz c = iD.
The last equation is consistent with the formula σ x σ y σ z = i because D acts as the identity
operator on the subspace M.
   A multi-spin system is described by four Majorana operators per spin. The corresponding
          eαj , Djα and the physical subspace L ⊂ Le are defined as follows:
operators σ

                                           eαj = ibαj cj ,
                                           σ                         Dj = bxj byj bzj cj ;
                                                                                                                       (11)
                                  |ξi ∈ L if and only if Dj |ξi = |ξi for all j.

Any spin Hamiltonian H{σjα } can be replaced by the fermionic Hamiltonian H{b     e αj , cj } =
H{eσ αj } the action of which is restricted to the physical subspace. (The resulting Hamilto-
nian He is rather special; in particular, it commutes with the operators Dj .)

Remark 2.1. The substitution σjα 7→ σ
                                    ejα = ibαj cj is gauge-equivalent to a more familiar one
(see [49] and references therein):

            σjα 7→ Dj σ
                      ejα ,                i.e., σjx 7→ −ibyj bzj ,         σjy 7→ −ibzj bxj ,    σjz 7→ −ibxj byj .   (12)

Thus one can represent a spin by only 3 Majorana operators without imposing gauge constraints.
However, this is not sufficient for our purposes.

2.2     Application to the concrete model
Let us apply the general procedure to the the spin Hamiltonian (4). Each term Kjk = σjα σkα
becomes K e jk = (ibα cj )(ibα ck ) = −i (ibα bα ) cj ck . The operator in parentheses, ûjk = ibα bα , is
                     j        k             j k                                                  j k
Hermitian; we associated it with the link (j, k). (The index α takes values x, y or z depending
on the direction of the link, i.e., α = αjk .) Thus we get:
                      X                           
              e=   i                                  2Jαjk ûjk if j and k are connected,
              H            Âjk cj ck ,  Âjk =
                   4                                       0     otherwise,
                       j,k                                                                          (13)
                                                                 α      α
                                                      ûjk = ibj jk bk jk .

Note that each pair of connected sites is counted twice, and ûkj = −ûjk . The structure of this
Hamiltonian is shown in Fig. 4.


                                                              12
                                                              Majorana operators

                                        cj
                                        z
                                       bj
                                             ujk
                                        z
                                       bk
                                                                    spins
                                        ck




                     Figure 4: Graphic representation of Hamiltonian (13).

     Remarkably, the operators ûjk commute with the Hamiltonian and with each other. There-
fore the Hilbert space Le splits into common eigenspaces of ûjk , which are indexed by the
                                                                                   L e
corresponding eigenvalues ujk = ±1. Similarly to (7) we may write Le =                u Lu , where u
stands for the collection of all ujk . The restriction of Hamiltonian (13) to the subspace Leu is
obtained by “removing hats”,P     i.e., replacing operators by numbers. This procedure results in
the Hamiltonian H eu = i
                         4    j,k jk cj ck , which corresponds to free fermions. The ground state of
                                 A
He u can be found exactly; let us denote it by |Ψ   e u i.
     Note, however, that the subspace Leu is not gauge-invariant: applying the gauge operator
Dj changes the values of ujk on the links connecting the vertex j with three adjacent vertices k.
Therefore the state |Ψe u i does not belong to the physical subspace. To obtain a physical space
we must symmetrize over all gauge transformations. Specifically, we construct the following
state:
                                             Y  1 + Dj 
                                  |Ψw i =                   e u i ∈ L.
                                                           |Ψ                                   (14)
                                              j
                                                     2

Here w denotes the equivalence class of u under the gauge transformations. For the planar
lattice (but not on the torus) w is characterized by numbers wp = ±1 defined as products
of ujk around hexagons. To avoid ambiguity (due to the relation ukj = −ujk ), we choose a
particular direction for each link:
                         Y                                                     
             wp =                 ujk   j ∈ even sublattice, k ∈ odd sublattice .    (15)
                   (j,k)∈boundary(p)

                                   Q
The corresponding operator Wfp = ûjk commutes with the gauge transformations as well as
the Hamiltonian. The restriction of this operator to the physical subspace coincides with the
integral of motion Wp defined earlier (see (6)).
Notation change: From now on, we will not make distinction between operators acting in
                                                                         fp versus Wp . The tilde
the extended space and their restrictions to the physical subspace e.g., W
mark will be used for other purposes.




                                                   13
2.3    Path and loop operators
One may think of the variables ukj as a Z2 gauge field. The number wp is interpreted as the
magnetic flux through the plaquette p. If wp = −1, we say that the plaquette carries a vortex.
   The product of ûjk along an arbitrary path corresponds to the transfer of a fermion between
the initial and the final point. However, this product is not gauge-invariant. One can define an
invariant fermionic path operator in terms of spins or in terms of fermions:
                                                                   n
                                                                                !
                                                                   Y
                    W (j0 , . . . , jn ) = Kjn jn−1 . . . Kj1 j0 =   −iûjs js−1 cn c0 ,    (16)
                                                             s=1

where Kjk is given by (5). If the path is closed, i.e., jn = j0 , the factors cn and c0 cancel each
other. In this case the path operator is called the Wilson loop; it generalizes the notion of
magnetic flux.
   On the honeycomb lattice all loops have even length, and formula (16) agrees with the sign
convention based on the partition into the even and odd sublattice. However, the spin model
can be generalized to any trivalent graph, in which case the loop length is arbitrary. For an odd
loop l the operator W (l) has eigenvalues wl = ±i. This is not just an artifact of the definition:
odd loops are special in that they cause spontaneous breaking of the time-reversal symmetry.
   The time-reversal operator is a conjugate-linear unitary operator T such that

                     T σjα T −1 = −σjα ,      T bj T −1 = bj ,     T cj T −1 = cj .           (17)

(The first equation is a physical requirement; the other two represent the action of T in the
extended space.) Therefore T commutes with the Hamiltonian (4) and the Wilson loop. Mul-
tiplying the equation Wl |Ψi = wl |Ψi by T , we get Wl T |Ψi = wl∗ T |Ψi. Thus the time-reversal
operator changes wl to wl∗ . For a bipartite graph wl∗ = wl for all loops, therefore fixing the
variables wl does not break the time-reversal symmetry. On the contrary, for a similar model
on a non-bipartite graph (e.g., a lattice containing triangles) the operator T does not preserve
the field configuration, which is defined by the values of wl on all loops. But T is a symmetry
operator, therefore all Hamiltonian eigenstates are (at least) two-fold degenerate.


3     Quadratic Hamiltonians
In the previous section we transformed the spin model (4) to a quadratic fermionic Hamiltonian
of the general form
                                             iX
                                    H(A) =         Ajk cj ck ,                            (18)
                                             4 j,k
where A is a real skew-symmetric matrix of size n = 2m. Let us briefly state some general
properties of such Hamiltonians and fix the terminology.
   First, we comment on the normalization factor 1/4 in Eq. (18). It is chosen so that
                                                             
                             [−iH(A), −iH(B)] = −iH [A, B] .                           (19)

Thus the Lie algebra of quadratic operators −iH(A) (acting on the 2m -dimensional Fock space)
is identified with so(2m). Operators of the form e−iH(A) constitute the Lie group Spin(2m).

                                                14
The center of this group consists of phase factors ±1 (e.g., eπc1 c2 = −1). The quotient group
Spin(2m)/{+1, −1} = SO(2m) describes the action of e−iH(A) on Majorana operators by con-
jugation:                                  X
                       e−iH(A) ck eiH(A) =    Qjk cj ,  where Q = eA                       (20)
                                                            j

(Q is a real orthogonal matrix with determinant 1).
   Note that the sum in Eq. (20) corresponds to the multiplication of the row vector (c1 , . . . , c2m )
by the matrix Q. On the other hand, when we consider a linear combination of Majorana op-
erators,                                       X
                                       F (x) =     xj cj ,                                         (21)
                                                                    j

we prefer to view x as a column vector. If the coefficients xj are real, we call F (x) (or x itself)
a Majorana mode.
   To find the ground state of the Hamiltonian (18), one needs to reduce it to a canonical form
                                              m                    m
                                  i X ′ ′′      X
                     Hcanonical =    εk bk bk =   εk (a†k ak − 12 ),                          εk ⩾ 0,      (22)
                                  2
                                            k=1                   k=1

where b′k , b′′k are normal modes, and a†k = 12 (b′k −ib′′k ), ak = 21 (b′k + ib′′k ) are the corresponding cre-
ation and annihilation operators. The ground state of Hcanonical is characterized by the condition
ak |Ψi = 0 for all k. The reduction to the canonical form is achieved by the transformation
                 (b′1 , b′′1 , . . . , b′m , b′′m ) = (c1 , c2 , . . . , c2m−1 , c2m ) Q,    Q ∈ O(2m),    (23)
such that                                                                              
                                          0 ε1
                                        −ε1 0                                        
                                                                                     
                                              ..                                      T
                                   A = Q         .                                   Q .                 (24)
                                                                                     
                                                                         0        εm 
                                                                         −εm        0
The numbers ±εk constitute the spectrum of the Hermitian matrix iA, whereas odd (even)
columns of Q are equal to the real (resp., imaginary) part of the eigenvectors. The ground
state of the Majorana system has energy
                                                           m
                                                1X          1
                                            E=−       εk = − Tr |iA|,                                      (25)
                                                2 k=1       4
where the function | · | acts on the eigenvalues, the eigenvectors being fixed. (In fact, any
function of a real variable can be applied to Hermitian matrices.)
    Note that different quadratic Hamiltonians may give rise to the same ground state. The
latter actually depends on
                                                                  
                                                 0 1
                                              −1 0                
                                                                  
                                                       ..          T
                        B = −i sgn(iA) = Q                .       Q ,                   (26)
                                                                  
                                                             0 1
                                                             −1 0

                                                                 15
(We assume that A is not degenerate.) The matrix B is real skew-symmetric and satisfies
B 2 = −1. It determines the ground state through the condition
                 X                                            1
                     Pjk cj |Ψi = 0 for all k,   where Pjk = (δjk − iBjk ).       (27)
                  j
                                                              2

Loosely speaking, B corresponds to a pairing1 between Majorana modes. The operators b′ =
F (x′ ) and b′′ = F (x′′ ) are paired if x′′ = ±Bx′ .
    The matrix P in Eq. (27) is called the spectral projector. It projects the 2m-dimensional
complex space C2m onto the m-dimensional subspace L spanned by the eigenvectors of iA
corresponding to negative eigenvalues. For any vector z ∈ L the corresponding operator F (z)
annihilates theP  ground state, so we may call L the space of annihilation operators. Note that if
    ′
z, z ∈ L then j zj zj′ = 0. The choice of an m-dimensional subspace L ⊆ C2m satisfying this
condition is equivalent to the choice of matrix B.
    The ground state of a quadratic Hamiltonian can also be characterized by correlation func-
tions. The second-order correlator is hΨ|cj ck |Ψi = 2Pkj ; higher-order correlators can be found
using Wick’s formula.


4       The spectrum of fermions and the phase diagram
We now study the system of Majorana fermions on the honeycomb lattice. It is described
by the quadratic Hamiltonian Hu = H(A), where Ajk = 2Jαjk ujk , ujk = ±1. Although the
Hamiltonian is parametrized by ujk , the corresponding gauge-invariant state (or the state of
the spin system) actually depends on the variables wp , see (15).
    First, we remark that the global ground state energy does not depend on the signs of the
exchange constants Jx , Jy , Jz since changing the signs can be compensated by changing the
corresponding variables ujk . We further notice that the ground state energy for Hu does not
depend on these signs even if u is fixed. Suppose, for instance, that we replace Jz by −Jz .
Such a change is equivalent to altering ujk for all z-links. But the gauge-invariant quantities
wp remain constant, so we may apply a gauge transformation that returns ujk to their original
values. The net effect is that the Majorana operators at some sites are transformed as cj 7→ −cj .
Specifically, the transformation acts on the set of sites Ωz that lie in the shaded area in the
picture below. In terms of spins, this action is induced by the unitary operator


                                                                           Y
                                                     Ωz             Rz =          σjz                  (28)
                                                                           j∈Ωz



So, for the purpose of finding the ground state energy and the excitation spectrum, the signs
of exchange constants do not matter (but other physical quantities may depend on them).
    1
    Note the nonstandard use of terminology: in our sense, electron half-modes in an insulator are paired as
well as in a superconductor. The only difference is that the insulating pairing commutes with the number
of electrons while the superconducting one doesn’t. This distinction is irrelevant to our model because the
Hamiltonian doesn’t preserve any integral charge, and the number of fermions is only conserved modulo 2.

                                                    16
    The most interesting choice of ujk is the one that minimizes the ground state energy. It turns
out that the energy minimum is achieved by the vortex-free field configuration, i.e., wp = 1
for all plaquettes p. This statement follows from a beautiful theorem proved by Lieb [50].
(Not knowing about Lieb’s result, I did some numerical study suggesting the same answer, see
Appendix A.) Thus we may assume that ujk = 1 for all links (j, k), where j belongs to the
even sublattice, and k belongs to the odd sublattice. This field configuration (denoted by ustd jk )
possesses a translational symmetry, therefore the fermionic spectrum can be found analytically
using the Fourier transform.
    The general procedure is as follows. Let us represent the site index j as (s, λ), where s refers
to a unit cell, and λ to a position type inside the cell (we choose theP unit cell as shown in the
figure accompanying Eq. (32)). The Hamiltonian becomes H = (i/4) s,λ,t,µ Asλ,tµ csλ ctµ , where
Asλ,tµ actually depends on λ, µ, and t − s. Then we pass to the momentum representation:
                          1X e                                    eλµ (q) =
                                                                                   X
                 H=         iAλµ (q)a−q,λ aq,µ ,                  A                    ei(q,rt ) A0λ,tµ ,   (29)
                          2                                                        t
                            q,λ,µ
                                                      1    X
                                          aq,λ = √              e−i(q,rs ) csλ ,                            (30)
                                                      2N    s

where N is the total number of the unit cells. (Here and on, operators in the momentum
representation are marked with tilde.) Note that a†q,λ = a−q,λ and ap,µ a†q,λ + a†q,λ ap,µ = δpq δµλ .
                                                                e
The spectrum ε(q) is given by the eigenvalues of the matrix iA(q).     One may call it a “double
spectrum” because of its redundancy: ε(−q) = −ε(−q). The “single spectrum” can be obtained
by taking only positive eigenvalues (if none of the eigenvalues is zero).
   We now apply this procedure to the concrete Hamiltonian
                                              iX
                           Hvortex-free =        Ajk cj ck ,              Ajk = 2Jαjk ustd
                                                                                       jk .                 (31)
                                              4
                                                j,k

We choose a basis (n1 , n2 ) of the translation group and obtain the following result:
                     unit cell                                       
                                           e              0    if (q)
                                          iA(q) =                       ,          ε(q) = ±|f (q)|,
                n2               n1                    −if (q)∗ 0
                                                                                                           (32)
                                                 f (q) = 2 Jx ei(q,n1 ) + Jy ei(q,n2 ) + Jz ,


                 √                    √
where n1 = ( 12 , 23 ), n2 = (− 12 , 23 ) in the standard xy-coordinates.
     An important property of the spectrum is whether it is gapless, i.e., whether ε(q) is zero
for some q. The equation Jx ei(q,n1 ) + Jy ei(q,n2 ) + Jz = 0 has solutions if and only if |Jx |, |Jy |,
|Jz | satisfy the triangle inequalities:

                     |Jx | ⩽ |Jy | + |Jz |,      |Jy | ⩽ |Jx | + |Jz |,      |Jz | ⩽ |Jx | + |Jy |.         (33)

If the inequalities are strict (“<” instead of “⩽”), there are exactly 2 solutions: q = ±q∗ .
The region defined by inequalities (33) is marked by B in Fig. 5; this phase is gapless. The

                                                           17
                                                      Jz=1,       Jx= Jy=0

                           gapless

                                                        Az                                gapped



                                                        B

                                           Ax                      Ay
                           Jx=1,                                                  Jy=1,
                    Jy= Jz=0                                                      Jx= Jz=0

Figure 5: Phase diagram of the model. The triangle is the section of the positive octant
(Jx , Jy , Jz ⩾ 0) by the plane Jx + Jy + Jz = 1. The diagrams for the other octants are similar.

gapped phases, Ax , Ay , and Az , are algebraically distinct, though related to each other by
rotational symmetry. They differ in the way lattice translations act on anyonic states (see
Section 5.2). Therefore a continuous transition from one gapped phase to another is impossible,
even if we introduce new terms in the Hamiltonian. On the other hand, the 8 copies of each
phase (corresponding to different sign combinations of Jx , Jy , Jz ) have the same translational
properties. It is unknown whether the 8 copies of the gapless phase are algebraically different.
    We now consider the zeros of the spectrum that exist in the gapless phase. The momentum q
is defined modulo the reciprocal lattice, i.e., it belongs to a torus. We represent the momentum
space by the parallelogram spanned by (q1 , q2 ) — the basis dual to (n1 , n2 ). In the symmetric
case (Jx = Jy = Jz ) the zeros of the spectrum are given by


                             q* − q*                         q∗ ≡ 13 q1 + 32 q2    (mod q1 , q2 )
                                                                                                    (34)
                  q2                       q
                                               1        −q∗ ≡ 23 q1 + 31 q2        (mod q1 , q2 )

If |Jx | and |Jy | decrease while |Jz | remains constant, q∗ and −q∗ move toward each other (within
the parallelogram) until they fuse and disappear. This happens when |Jx | + |Jy | = |Jz |. The
points q∗ and −q∗ can also effectively fuse at opposite sides of the parallelogram. (Note that
the equation q∗ = −q∗ has three nonzero solutions on the torus).
     At the points ±q∗ the spectrum has conic singularities (assuming that q∗ 6= −q∗ ):
                             ε(q)
                    δ qy
                                                                 p
                                                         ε(q) ≈ ± gαβ δqα δqβ ,
                                    δ qx
                                                                                                    (35)
                                                   where δq = q − q∗ or δq = q + q∗ .




                                                             18
5     Properties of the gapped phases
In a gapped phase, spin correlations decay exponentially with distance, therefore spatially
separated quasiparticles cannot interact directly. That is, a small displacement or another
local action on one particle does not influence the other. However, the particles can interact
topologically if they move around each other. This phenomenon is described by braiding rules.
(We refer to braids that are formed by particle worldlines in the 3-dimensional space-time.) In
our case the particles are vortices and fermions. When a fermion moves around a vortex, the
overall quantum state is multiplied by −1. As mentioned in the introduction, such particles
(with braiding characterized simply by phase factors) are called Abelian anyons.
    The description of anyons begins with identifying superselection sectors, i.e., excitation types
defined up to local operations. (An “excitation” is assumed to be localized in space, but it may
have uncertain energy or be composed of several unbound particles.) The trivial superselection
sector is that of the vacuum; it also contains all excitations that can be obtained from the
vacuum by the action of local operators.
    At first sight, each gapped phase in our model has three superselection sectors: a fermion,
a vortex and the vacuum. However, we will see that there are actually two types of vortices
that live on different subsets of plaquettes. They have the same energy and other physical
characteristics, yet they belong to different superselection sectors: to transform one type of
vortex into the other one has to create or annihilate a fermion.
    To understand the particle types and other algebraic properties of the gapped phases, we
will map our model to an already known one [24]. Let us focus on the phase Az , which occurs
when |Jx | + |Jy | < |Jz |. Since we are only interested in discrete characteristics of the phase, we
may set |Jx |, |Jy | ≪ |Jz | and apply the perturbation theory.

5.1    Perturbation theory study
The Hamiltonian is H = H0 + V , where H0 is the main part and V is the perturbation:
                        X                         X                 X y y
              H0 = −Jz      σjz σkz ,   V = −Jx        σjx σkx − Jy   σj σk
                           z-links                      x-links          y-links

Let us assume that Jz > 0 (the opposite case is studied analogously).
    We first set Jx = Jy = 0 and find the ground state. It is highly degenerate: each two spins
connected by a z-link are aligned (↑↑ or ↓↓), but their common direction is not fixed. We
regard each such pair as an effective spin. The transition from physical spins to effective spins
is shown in Fig. 6a,b. The ground state energy is E0 = −NJz , where N is the number of unit
cells, i.e., half the number of spins.
    Our goal is to find an effective Hamiltonian that would act in the space of effective spins
Leff . One way to solve the problem is to choose a basis in Leff and compute the matrix elements
                        (1)                    (2)
                                                         X′ ha|V |jihj|V |bi
                   ha|Heff |bi = ha|V |bi, ha|Heff |bi =                     , etc.
                                                         j
                                                                E 0 − Ej


However, we will use the more general Green function formalism.
   Let Υ : Leff → L be the embedding that maps the effective Hilbert space onto the ground
subspace of H0 . The map Υ simply doubles each spin: Υ|mi = |mmi, where m = ↑ or

                                                 19
                                    s                            s             m2               s
                       x        y                          z

                   z       p            z              y   p y                         p
                                x
                                                  n2             n1
                       y                                   z

                                                                                           m1


                           a)                              b)                         c)

Figure 6: Reduction of the model. Strong links in the original model (a) become effective spins
(b), which are associated with the links of a new lattice (c).

m = ↓. The eigenvalues of the “effective Hamiltonian” (if one exists) are supposed to be the
energy levels of H that originate from ground states of H0 . These levels can be unambiguously
defined as poles of the Green function G(E) = Υ† (E − H)−1Υ, which is an operator acting
on Leff and depending
                 −1 on the parameter E. The Green function is conventionally expressed as
 E − E0 − Σ(E) , where Σ(E) is called self-energy, so the energy levels in question are the
values of E for which the operator E − E0 − Σ(E) is degenerate. Neglecting the the dependence
of Σ(E) on E (for E ≈ E0 ), we define the effective Hamiltonian as Heff = E0 + Σ(E0 ).
                                                                                       ′
    The self-energy is computed by the standard method. Let G′0 (E) = (E − H0 )−1 be the
unperturbed Green function for exited states of H0 . The ′ sign indicates that the operator
              ′
 (E − H0 )−1 acts on excited states in the natural way but vanishes on ground states. Then
                                                                         
                   Σ(E) = Υ† V + V G′0 (E)V + V G′0 (E)V G′0 (E)V + · · · Υ,              (36)

                                                                               (0)
We set E = E0 and compute Heff = E0 + Σ in the zeroth order (Heff = E0 ), first order, second
order, and on, until we find a nonconstant term.2 The calculation follows.
           (1)
  1. Heff = Υ† V Υ = 0.

          (2)
                                X J2        X Jy2           Jx2 + Jy2
                  †   ′                 x
  2.    Heff = Υ V G0 V Υ = −             −            = −N           . Indeed, consider the action
                               x-links
                                       4Jz y-links 4Jz         4Jz
        of the second V in the expression Υ† V G′0 V Υ. Each term σjx σkx or σjy σky flips two spins,
        increasing the energy by 4Jz . The other V must flip them back.
           (3)
  3. Heff = Υ† V G′0 V G′0 V Υ = 0.

         (4)    †   ′    ′    ′
                                              Jx2 Jy2 X
  4.    Heff = Υ V G0 V G0 V G0 V Υ = const −           Qp ,           where Qp = (Wp )eff is the effective
                                              16Jz3 p
                                                             1
        spin representation of the operator (6). The factor 16 is obtained by summing 24 terms,
  2
      Higher order terms may be less significant than the dependence of Σ(E) on E in the first nonconstant term.

                                                           20
      each of which corresponds to flipping 4 spin pairs in a particular order:
                                    1      1      −1      1
                                       =8·    +8·    +8·     .
                                    16     64     64     128

   The above arguments can easily be adapted to the case Jz < 0. Now we have Υ : |↑i 7→
|↑↓i, |↓i 7→ |↓↑i. The result turns out to be the same, with Jz replaced by |Jz |.
   Thus the effective Hamiltonian has the form
                             Jx2 Jy2 X                   y        y         z      z
                 Heff = −              Qp ,        Qp = σleft(p) σright(p) σup(p) σdown(p)   (37)
                            16|Jz |3 p

(the geometric arrangement of the spins corresponds to Fig. 6b).

5.2    Abelian anyons
Hamiltonian (37) already lends itself to direct analysis. However, let us first reduce it to the
more familiar form (3). We construct a new lattice Λ′ so that the effective spins lie on its links
(see Fig. 6c). This is a sublattice of index 2 in the original lattice Λ (here “lattice” means
“translational group”). The basis vectors of Λ′ are m1 = n1 − n2 and m2 = n1 + n2 . The
plaquettes of the effective spin lattice become plaquettes and vertices of the new lattice, so the
Hamiltonian can be written as follows:
                                                                 !
                                              X          X
                             Heff = −Jeff         Qs +         Qp ,
                                               vertices          plaquettes


where Jeff = Jx2 Jy2 /(16|Jz |3 ).
   Now we apply the unitary transformation
                                       Y                             Y
                                   U =                Xj                   Yk                (38)
                                       horizontal links       vertical links

for suitably chosen spin rotations X and Y so that the Hamiltonian becomes
                                                                    !
                                                X           X
                        ′
                      Heff = UHeff U † = −Jeff       As +        Bp ,                        (39)
                                                          vertices        plaquettes


where As and Bp are defined in Eq. (3). (Caution: transformation (38) breaks the translational
symmetry of the original model.)
   The last Hamiltonian has been studied in detail [24]. Its key properties are that all the
terms As , Bp commute, and that the ground state minimizes each term separately. Thus the
ground state satisfies these conditions:

                               As |Ψi = +|Ψi,              Bp |Ψi = +|Ψi.                    (40)

Excited states can be obtained by replacing the + sign to a − sign for a few vertices and plaque-
ttes. Those vertices and plaquettes are the locations of anyons. We call them “electric charges”

                                                    21
and “magnetic vortices”, or e-particles and m-particles, respectively. When an e-particle moves
around a m-particle, the overall state of the system is multiplied by −1. This property is stable
with respect to small local perturbations of the Hamiltonian. (A local operator is a sum of
terms each of which acts on a small number of neighboring spins.) It is also a robust property
that the number of particles of each type is conserved modulo 2.
    The model has 4 superselection sectors: 1 (the vacuum), e, m, and ε = e × m. The
latter expression denotes a composite object consisting of an “electric charge” and a “magnetic
vortex”. These are the fusion rules:
                                    e × e = m × m = ε × ε = 1,
                                                                                             (41)
                              e × m = ε,        e × ε = m,       m × ε = e.

(In general, fusion rules must be supplemented by associativity relations, or 6j-symbols, but
they are trivial in our case.)
   Let us discuss the braiding rules. One special case has been mentioned: moving an e-particle
around an m-particle yields −1. This fact can be represented pictorially:


                                    = −1 ,           or                = −            .      (42)
                          m     e
                                                             m     e          m   e

The fist diagram shows the “top view” of the process. The diagrams in the second equation
correspond to the “front view”: the “up” direction is time.
    It is easy to show that e-particles are bosons with respect to themselves (though they clearly
do not behave like bosons with respect to m-particles); m-particles are also bosons. However
ε-particles are fermions. To see this, consider two processes. In the first process two εε-pairs
are created, two of the four ε-objects are exchanged by a 180◦ counterclockwise rotation, then
the pairs are annihilated. (Each ε-object is represented by e and m, so there are 8 elementary
particles involved.) In the second process the two pairs are annihilated immediately. It does
not matter how exactly we create and annihilate the pairs, but we should do it the same way
in both cases. For example, we may use this definition:
                                    m e   m e
                     creation =                 ,     annihilation =                  .      (43)
                                                                         m e m e

Now we compare the two processes. Each one effects the multiplication of the ground state by
a number, but the two numbers differ by −1:



                                                    = −                       .              (44)



Indeed, in the left diagram the dashed line is linked with the solid line. This corresponds to an
e-particle going around an m particle, which yields the minus sign.

                                                     22
                                           m       m        m

                                       e       e        e       e

                                   m       m       m        m       m

                                       e       e        e       e
                                           m       m        m

Figure 7: Weak breaking of the translational symmetry: e-vortices and m-vortices live on
alternating rows of hexagons.

    Braiding an ε-particle with an e- or m-particle also gives −1. This completes the description
of braiding rules.
    It remains to interpret these properties in terms of vortices and fermions in the original
model. Tracing sites and plaquettes of the reduced model (3) back to the original model, we
conclude that e-particles and m-particles are vortices that live on alternating rows of hexagons,
see Fig. 7. Note that the two types of vortices have the same energy and other physical
properties, yet they cannot be transformed one to another without creating or absorbing a
fermion. A general view on this kind of phenomenon is given in Appendix F.
    The fermions in the original model belong to the superselection sector ε, although they
are not composed of e and m. In the perturbation-theoretic limit, the energy of a fermion is
about 2|Jz | whereas an em-pair has energy 4Jeff ≪ |Jz |. The fermions are stable due to the
conservation of Wp (and also due to the conservation of energy). However, they will decay into
e and m if we let the spins interact with a zero-temperature bath, i.e., another system that can
absorb the energy released in the decay.


6     Phase B acquires a gap in the presence of magnetic
      field
6.1    The conic singularity and the time-reversal symmetry
Phase B (cf. Fig. 5) carries gapped vortices and gapless fermions. Note that vortices in this
phase do not have well-defined statistics, i.e., the effect of transporting one vortex around the
other depends on details of the process. Indeed, a pair of vortices separated by distance L is
strongly coupled to fermionic modes near the singularity of the spectrum, |q − q∗ | ∼ L−1 . This
coupling results in effective interaction between the vortices that is proportional to ε(q) ∼ L−1
and oscillates with characteristic wavevector 2q∗ . When one vortex moves around the other,
the quantum state picks up a nonuniversal phase ϕ ∼ L−1 t, where t is the duration of the
process. Since the vortex velocity v = L/t must be small to ensure adiabaticity (or, at least,
to prevent the emission of fermionic pairs), the nonuniversal phase ϕ is always large.
    The conic singularity in the spectrum is, in fact, a robust feature that is related to time-
reversal symmetry. As discussed in the end of Section 2, this symmetry is not broken by fixing
the gauge sector (i.e., the variables wp ) since the honeycomb lattice is bipartite. Let us show


                                                   23
that a small perturbation commuting with the time-reversal operator T can not open a spectral
gap.
    We may perform the perturbation theory expansion relative to the gauge sector of the
ground state (i.e., any term that changes the field configuration is taken into account in the
second and higher orders). This procedure yields an effective Hamiltonian which acts in the
fixed gauge sector and therefore can be represented in terms of cj and ûjk . The operator T
                                              α    α
defined by (17) changes the sign of ûjk = ibj jk bk jk , but this change can be compensated by a
gauge transformation. Thus we get a physically equivalent operator T ′ such that
                                                         
               ′      ′ −1               ′     ′ −1          cj if j ∈ even sublattice,
             T ûjk (T ) = ûjk ,      T cj (T ) =
                                                            −cj if j ∈ odd sublattice.
A T ′ -invariant perturbation to the fermionic Hamiltonian (31) (corresponding to a fixed gauge)
can not contain terms like icj ck , where j and k belong to the same sublattice. Thus the
perturbed matrix A(q)e    in Eq. (32) still has zeros on the diagonal, though the exact form of
the function f (q) may be different. However, a zero of a complex-valued function in two real
variables is a topological feature, therefore it survives the perturbation.

6.2    Derivation of an effective Hamiltonian
What if the perturbation does not respect the time-reversal symmetry? We will now show that
the simplest perturbation of this kind,
                                      X                           
                               V =−       hx σjx + hy σjy + hz σjz ,                   (45)
                                         j

does open a spectral gap. (Physically, the vector h = (hx , hy , hz ) is an external magnetic field
acting on all spins.) For simplicity we will assume that Jx = Jy = Jz = J.
    Let us use the perturbation theory to construct an effective Hamiltonian Heff acting on the
                                              (1)                                         (2)
vortex-free sector. One can easily see that Heff = 0. Although the second-order term Heff does
not vanish, it preserves the time-reversal symmetry. Therefore we must consider the third-order
term, which can be written as follows:
                                  (3)
                                Heff = Π0 V G′0 (E0 )V G′0 (E0 )V Π0 ,
where Π0 is the projector onto the vortex-free sector, and G′0 is the unperturbed Green function
with the vortex-free sector excluded. In principle,R the Green function can be computed for
                                                        ∞
each gauge sector using the formula G0 (E) = −i 0 ei(E−H0 +iδ)t dt (where δ is an infinitely
small number). For fixed values of the field variables ujk the unperturbed Hamiltonian may be
represented in the form (18) and exponentiated implicitly by exponentiating the corresponding
matrix A; the final result may be written as a normal-ordered expansion up to the second order.
However, it is a rather difficult calculation, so we will use a qualitative argument instead.
   Let us assume that all intermediate states involved in the calculation have energy ∆E ∼ |J|
above the ground state. (Actually, ∆E ≈ 0.27|J| for the lowest energy state with two adjacent
vortices, see Appendix A.) Then G′0 (E0 ) can be replaced by −(1 − Π0 )/|J|. The effective
Hamiltonian becomes
                                     (3)      hx hy hz X x y z
                                   Heff ∼ −               σ σ σ ,                             (46)
                                                J 2 j,k,l j k l

                                                 24
where the summation takes place over spin triples arranged as follows:

                         j l k                                                          k       j
             a)                      (and symmetry-equivalent),         or      b)                   .   (47)
                                                                                            l


Configuration (a) corresponds to the term σjx σky σlz = −iDl ûjl ûkl cj ck (where Dl may be omitted
as we work in the physical subspace), or simply −icj ck in the standard gauge. Configuration
(b) corresponds to a four-fermion term and therefore does not directly influence the spectrum.
Thus we arrive at this effective Hamiltonian:

                                                                    iX
                                                           Heff =         Ajk cj ck ,
                                                                    4 j,k

                                                           A = 2J (          ) + 2κ (           ),       (48)
                                                                hx hy hz
                                                           κ∼            .
                                                                  J2

Here (       ) is just another notation for ustd , i.e., the matrix whose entry ( )jk is equal to
1 if there is a solid arrow from k to j in the figure, −1 if an arrow goes from j to k, and 0
otherwise. (        ) is defined similarly.

6.3    The spectrum and the Chern number
The fermionic spectrum ε(q) of the Hamiltonian (48) is given by the eigenvalues of a modified
         e
matrix iA(q)  (cf. Eq. (32)):
                                           
                             ∆(q) if (q)                      p
                 e
               iA(q) =               ∗        ,      ε(q) = ± |f (q)|2 + ∆(q)2 ,            (49)
                            −if (q) −∆(q)
                                                                                              
where f (q) = 2J ei(q,n1 ) +ei(q,n2 ) +1 and ∆(q) = 4κ sin(q, n1 )+sin(q, −n2 )+sin(q, n2 −n1 ) .
Actually, the exact form of the function ∆(q) does not matter; the important parameter is
                                                   √        hx hy hz
                        ∆ = ∆(q∗ ) = −∆(−q∗ ) = 6 3 κ ∼              ,                                   (50)
                                                               J2
which determines the energy gap. The conic singularities are resolved as follows:
                           ε(q)
                  δ qy
                                                              p
                                                      ε(q) ≈ ± 3J 2 |δq|2 + ∆2 ,
                                  δ qx
                                                                                                         (51)
                                                  where δq = q − q∗ or δq = q + q∗ .


Remark 6.1. The magnetic field also gives nontrivial dispersion to vortices. Indeed, the
operators Wp are no longer conserved, therefore a vortex can hop to an adjacent hexagon.
Thus the vortex energy depends on the momentum. This effect is linear in h, but it is not so
important as the change in the fermionic spectrum.

                                                      25
   Let us also find the fermionic spectral projector, which determines the ground state. The
global spectral projector P is defined by Eq. (27); we now consider its Fourier component:
                    1                    1                                                  
                                e
             Pe(q) = 1 − sgn(iA(q)       = 1 + mx (q)σ x + my (q)σ y + mz (q)σ z ,               (52)
                    2                        2
                                                                             
                    
                     √           1
                                                      −δqy , −δq   x , −  √∆
                                                                                 if q ≈ q∗ ,
                     (δqx )2 +(δqy )2 +∆2 /(3J 2 )                         3J
             m(q) ≈                                                                            (53)
                    
                    
                     √           1
                                                      −δqy , δqx ,  √  ∆
                                                                                 if q ≈ −q∗ .
                            2        2   2      2
                             (δqx ) +(δqy ) +∆ /(3J )                  3J

The function m maps the torus to the unit sphere. If ∆ > 0, then this map has degree 1.
Indeed, the neighborhood of q∗ is mapped onto the lower hemisphere, the neighborhood of −q∗
is mapped onto the upper hemisphere; in both cases the orientation is preserved. (The rest of
the torus is mapped onto the equator.) For negative ∆ the map has degree −1.
    An important topological quantity characterizing a two-dimensional system of noninteract-
ing (or weakly interacting) fermions with an energy gap is the spectral Chern number. It plays
a central role in the theory of the integer quantum Hall effect [43, 44, 1]. In our model there
is no analogue of Hall conductivity (because the number of fermions is not conserved), but the
Chern number determines the edge mode chirality and anyonic properties of vortices (cf. [48]).
    The spectral Chern number is defined as follows. For each value of the momentum q we
                    e
consider the space L(q)   of annihilation operators, i.e., fermionic modes with negative energy;
this is the subspace the matrix Pe(q) projects onto. Thus we obtain a complex vector bundle
over the momentum space. (In our case L(q)   e    is a one-dimensional subspace of C2 , so the
bundle is one-dimensional.) The first Chern number of this bundle is denoted by ν and can be
expressed as follows (cf. [44]):
                    Z                                Z       e e               
               1                               1             ∂P ∂P    ∂ Pe ∂ Pe
          ν =           Tr Pe dPe ∧ dPe =                   e
                                                         Tr P        −              dqx dqy .    (54)
              2πi                              2πi            ∂qx ∂qy ∂qy ∂qx

   The Chern number is always an integer. If the spectral projector Pe(q) is given by Eqs. (52),
(53), then                 Z                  
                         1     ∂m ∂m
                 ν =                ×      , m dqx dqy = sgn ∆ = ±1.                        (55)
                        4π     ∂qx    ∂qy
We will use the notation Bν (where ν = ±1) to designate phase B in the magnetic field. In the
Abelian phases Ax , Ay , Az the Chern number is zero.


7     Edge modes and thermal transport
Remarkably, any system with nonzero Chern number possesses gapless edge modes. Such modes
were first discovered in the integer quantum Hall effect [51]; they are chiral, i.e., propagate only
in one direction (see Fig. 8). In fact, left-moving and right-moving modes may coexist, but the
following relation holds [52]:
                           def                                               
                    νedge =      # of left-movers − # of right-movers            = ν.            (56)

                                                        26
                                a)                               b)

             Figure 8: Chiral edge modes: left-moving (a) and right-moving (b).

In the absence of special symmetry, counterpropagating modes usually cancel each other, so
the surviving modes have the same chirality. A calculation of the edge spectrum in phases Bν
(for some specific boundary conditions) and a simple proof of Eq. (56) are given in Appendix B.
More rigorous and general results, which even apply to disordered systems, can be found in
Refs. [53, 54].
     It is important to note that the analogy to the quantum Hall effect is not exact. In our
model (like in two-dimensional superfluid and superconducting systems [55, 48]) edge modes
are described by real fermions, as contrasted to complex fermions in the quantum Hall effect.
Therefore each quantum Hall mode is equivalent to two modes in our system.
     Chiral edge modes can carry energy, leading to potentially measurable thermal transport.
(The temperature T is assumed to be much smaller than the energy gap in the bulk, so that
the effect of bulk excitations is negligible.) For quantum Hall systems, this phenomenon was
discussed in Refs. [56, 57]. The energy current along the edge in the left (counterclockwise)
direction is given by the following formula:
                                                 π
                                            I = c− T 2 ,                                      (57)
                                                 12
where c− is some real number. (The factor π/12 is introduced to make a connection to conformal
field theory, see below.) It is remarkable that c− does not depend on particular conditions at the
edge, but rather on the bulk state. Indeed, the energy current is conserved, therefore it remains
constant even if some conditions change along the edge. The effect is invariant with respect
to time rescaling. Since the energy current has dimension (time)−2 , it must be proportional to
T 2 . But the value of the dimensionless proportionality coefficient cannot be found using such
simple arguments.
     There are two standard ways to calculate the coefficient c− . They both rely on certain
assumptions but can be applied to our model, yielding this result:
                                                    ν
                                              c− = .                                          (58)
                                                    2
The first argument [58] (adapted to real fermions) assumes translational invariance and the
absence of interaction. Each edge mode is described by a free fermion with an energy spectrum
ε(q) such that ε(−q) = −ε(q) and ε(q) → ±∞ as q → ±∞. The signs in the last two expressions
agree if the mode propagates in the direction of positive q (for simplicity we may assume that
ε(q) > 0 when q is positive and ε(q) < 0 when q is negative). Thus the Hamiltonian has the
form
                                   1X                   X
                             H =        ε(q)a−q aq =         ε(q)a−q aq .
                                   2 q
                                                     q: ε(q)>0


                                               27
If ε(q) > 0, then aq is an annihilation operator and a−q = a†q is the corresponding creation
operator. The mode propagates with group velocity v(q) = dε/dq, and the occupation number
n(q) is given by the Fermi distribution. The energy flow due to each mode propagating in the
positive direction can be calculated as follows:
          Z                            Z                              Z ∞
                                  dq              ε(q)     dε dq    1     ε dε     π 2
    I1 =           n(q) ε(q) v(q)    =              ε(q)/T
                                                                 =           ε/T
                                                                                 =    T .
            ε(q)>0                2π    ε(q)>0 1 + e       dq 2π   2π 0 1 + e      24
                                                                                π
Each mode propagating in the opposite direction contributes −I1 , therefore I = 24 νT 2 .
   The second derivation [57] is based on the assumption that the edge modes can be described
by a conformal field theory (CFT). In this case,

                                          c− = c − c,                                       (59)

where c and c are the Virasoro central
                                      charges. Thus, c− is called the chiral central charge.
                                                                                           Left-
moving fermions have (c, c) = 12 , 0 whereas right-moving fermions have (c, c) = 0, 21 , which
implies Eq. (58). More generally, c and c are some rational numbers, and so is c− . The chiral
central charge parametrizes a two-dimensional gravitational anomaly [59] of the corresponding
CFT; it can also be identified with the coefficient in front of the gravitational Chern-Simons
action in a three-dimensional theory [5]. Volovik [60] suggested that for 3 He-A films, the role
of gravitational field is played by the order parameter interacting with fermions. However, it
is not obvious how to define a “gravitational field” for lattice models.
    It remains a bit mysterious how the chiral central charge is related to the ground state
and spin correlators in the bulk. This question is partially answered in Appendix D, but the
obtained expression for c− is not easy to use, nor can we demonstrate that c− is rational. Note
that there is a beautiful relation between the chiral central charge and algebraic properties of
anyons [7, 61], which does imply the rationality of c− . We discuss that relation in Appendix E
(see Eq. (172) on page 66), though it is unclear how to deduce it only considering the bulk. The
only known argument is to assume that edge modes are described by a CFT, then one can use
modular invariance [62]. In fact, the modular invariance alone would suffice. In Appendix D
we try to derive it from general principles, but again, encounter a problem.


8    Non-Abelian anyons
We continue the study of phase B in the magnetic field. Now that all bulk excitations are
gapped, their braiding rules must be well-defined. Of course, this is only true if the particles
are separated by distances that are much larger than the correlation length associated with the
spectrum (51). The correlation length may be defined as follows: ξ = | Im q|−1 , where q is a
complex solution to the equation ε(q) = 0. Thus
                                        √
                                          3J        J3
                                    ξ=         ∼           .                               (60)
                                          ∆       hx hy hz
   The braiding rules for vortices depend on the spectral Chern number ν. Although ν is
actually equal to +1 or −1 (depending on the direction of the magnetic field), one may formally
consider a model with an arbitrary gapped fermionic spectrum, in which case ν may take any

                                               28
                                τ
                        x




                               a)                              b)

            Figure 9: The space-time coordinates (a) and particle worldlines (b).

integer value. We will see that vortices behave as non-Abelian anyons for any odd value of ν,
but their exact statistics depends on ν mod 16.
    The properties of the anyons are summarized in Table 1 on page 30. The notation and
underlying concepts are explained below; see also Appendix E. Let us first show a quick
way of deriving those properties from conformal filed theory (CFT) in the most important
case, ν = ±1. (For a general reference on CFT, see [63].) Then we will give an alternative
derivation, which uses only rudimentary CFT and refers to the operational meaning of braiding
and fusion.

8.1    Bulk-edge correspondence
The properties listed in Table 1 form the same type of algebraic structure that was described by
Moore and Seiberg [4] in the CFT context. However, the actual connection to CFT is indirect:
anyons are related to edge modes, which in turn can be described by a field theory in 1 + 1
dimensions. More concretely, the space-time may be represented as a cylinder (see Fig. 9). It
is convenient to use the imaginary time formalism (t = −iτ , where τ ∈ R), so that we have a
two-dimensional Euclidean field theory on the side surface of the cylinder. The surface may be
parametrized by a complex variable z = τ + ix, where x is the spatial coordinate.
    The two-dimensional field theory describes the physics of the edge, which is generally richer
than that of the bulk. The theory possesses both local and nonlocal fields. The insertion of
a nonlocal field φ(τ + ix) corresponds to an anyonic particle emerging on the edge or sinking
into the bulk at point (τ, x). The correlation function of several nonlocal fields has nontrivial
monodromy which coincides with the anyonic braiding. Specifically, the counterclockwise ex-
change of anyons in the bulk is equivalent to moving the fields counterclockwise on surface (if
we look at the cylinder from outside). Moreover, the value of the correlator is not a number, but
rather an operator transforming the initial anyonic state (on the bottom of the cylinder) into
the final one (on the top of the cylinder). For non-Abelian anyons, the space of such operators
is multidimensional.
    The anyon-CFT correspondence has been successfully used in the study of quantum Hall
systems [14, 15, 31]. The correspondence is well-understood if all boundary fields are either
holomorphic or antiholomorphic, which is the case for our model. We have seen that the edge
carries a left-moving (holomorphic) fermion for ν = 1, or a right-moving (antiholomorphic)

                                               29
Superselection sectors: 1 (vacuum), ε (fermion), σ (vortex).
                                                           √
    Quantum dimension:          d1 = 1,   dε = 1      dσ = 2;
                                                                        
    Topological spin:           θ1 = 1,   θε = −1,    θσ = θ = exp π8 iν ;
                                                                                                                                                                                                           2
         Frobenius-Schur indicator:                                                       κ1 = 1,                        κε = 1,                           κσ = κ = (−1)(ν −1)/8 .
                                                                              def P
         Global dimension:                                                D2 =        2
                                                                                   u du = 4.


Fusion rules:                                             ε × ε = 1,                               ε × σ = σ,                                        σ × σ = 1 + ε.
Associativity relations:
         σ σ σ                                    σ σ σ                             σ σ σ                                    σ σ σ                                 σ σ σ                                       σ σ σ
                                κ                                           κ                                                                          κ                                     κ
             1                = √                             1           + √              ε       ,                             ε                   = √                       1           − √                         ε       ,
                                  2                                           2                                                                          2                                     2
                 σ                                        σ                            σ                                             σ                                     σ                                       σ


         ε       σ        ε                   ε       σ           ε                   σ        ε           σ             σ           ε       σ                             ε       ε       ε               ε       ε       ε

             σ                = −                         σ           ,                    σ                   = −                       σ       ,                                 1               =               1           ,
                 σ                                    σ                                        ε                                     ε                                             ε                               ε

ε σ σ                     ε σ σ                                   σ σ ε              σ σ ε                               σ       ε       ε             σ   ε   ε                               ε   ε       σ               ε       ε       σ

 σ           =                    1   ,                                   1     =              σ       ,                     σ                   =         1       ,                               1               =                   σ       ,
     ε                        ε                                           ε                ε                                     σ                         σ                                       σ                               σ

             σ        ε       σ               σ       ε           σ                   ε        σ           σ         ε       σ       σ                             σ           σ       ε               σ       σ       ε

                 σ
                                      =                   σ
                                                                      ,                   σ
                                                                                                               =                 ε
                                                                                                                                         ,                             ε
                                                                                                                                                                                           =                       σ
                                                                                                                                                                                                                           .
                      1                               1                                        1                             1                                                 1                               1

Braiding rules:

         Definition of Rzxy :                                                                                                                                            
         y       x                        y       x                                 R1εε = −1,                                                       R1σσ = κ exp − π8 iν ,
                      = Rzxy                          ;                                                                                                                 
                                                                                    Rσεσ = Rσσε = −iν ,                                              Rεσσ = κ exp 3π
                                                                                                                                                                   8
                                                                                                                                                                     iν   .
             z                                z


Topological S-matrix:
                                                          x                                                    1        1                √1
                                                                                                                                                       
                                                      x                                                         2        2                  2
        def 1                                                                                                 1        1                                                                          
     Sz xy =                                                      z ;               S1 =                       2        2
                                                                                                                                         − 12
                                                                                                                                           √           ,                          Sε σσ = exp − π4 iν .
             D
                                                      y                                                        √1    − √12                       0
                                                          y                                                      2



                     Table 1: Algebraic properties of anyons in non-Abelian phases (ν is odd).


                                                                                                               30
fermion for ν = −1. A vortex emerging on the surface corresponds to a twist field σ. The
correlation functions for such fields are given by holomorphic (resp. antiholomorphic) conformal
blocks for the Ising model.
     A partial bulk-edge correspondence can be established at a more elementary level. Let
ν = 1. A particularly important     parameter of the edge theory is the conformal weight of the
                          1
twist field, (hσ , hσ ) = 16 , 0 . The related bulk parameter is the topological spin of a vortex,
θσ ; it corresponds to the counterclockwise rotation by angle 2π. Since the rotations in the bulk
and on the surface must agree, the following equation holds for an arbitrary field a:

                                                θa = e2πi(ha −ha ) .                                   (61)

Thus θσ = eiπ/8 . Similarly, if ν = −1, then θσ = e−iπ/8 . In the general case, there are
|ν| = 2n + 1 species of the free fermion; the twist field also comes with some multiplicity.3
One may argue that the conformal weight of the twist field is proportional to the number of
fermionic species. Hence
                                         θσ = eiπν/8 .                                  (62)

8.2     Unpaired Majorana modes
We now begin a rather lengthy derivation of the properties listed in Table 1, dealing only with
anyons in the bulk. First, we give a crude description of vortices by Majorana operators and
find the fusion rules. The braiding rules and so-called associativity relations (also known as
crossing symmetry, or 6j-symbols) are determined up to several free parameters; we discuss
what combinations of these parameters have invariant meaning. Solving the so-called pen-
tagon and hexagon equations, we reduce the continuum of possibilities down to eight consistent
theories. The right theory is selected using Eq. (62).
    The starting point is this: if ν is odd, then each vortex carries an unpaired Majorana mode.
A sufficiently rigorous proof of this statement can be found in Appendix C. Here we give a
rough explanation based on the quantum Hall analogy.
    It is known that the quantized Hall conductivity for noninteracting electrons (in units of
e2 /h) is equal to the Chern number of the projector onto the occupied electron states [44].
The essential difference from our case is that electrons are ordinary fermions, not Majorana
fermions. However, we can concoct an analogue of an electron system from two copies of the
Majorana system, which may be pictured as two layers. The Hamiltonian is as follows:
                        iX                              X                           1
          Helectron =      Ajk (c′j c′k + c′′j c′′k ) =   iAjk a†j ak ,   where aj = (c′j + ic′′j ).   (63)
                        4                                                           2
                           j,k                         j,k


(We forget about the original spin model for the purpose of this construction.) Note that
the Hamiltonian possesses a global O(2) symmetry that consists of orthogonal linear transfor-
mations c′j 7→ αc′j + βc′′j , c′′j 7→ γc′j + δc′′j . The rotational subgroup U(1) ∼
                                                                                  = SO(2) ⊂ O(2)
corresponds to the conservation of electric charge, whereas reflections (i.e., transformations
with determinant −1) change the sign of the charge.
   3
    Specifically, there are 2n copies of the twist field, which are transformed according to the fundamental
representation of Spin(2n + 1).


                                                        31
    Assuming that the Fermi energy is zero, the projector onto the occupied electron states
coincides with the spectral projector for the Majorana system. Thus the Hall conductivity of
the electron system is ν.
    A vortex piercing both Majorana layers corresponds to half-integer magnetic flux. Such a
vortex carries excessive charge q = ν/2 + n, where n is an arbitrary integer. In particular, if
ν is odd, a state with q = 1/2 exist. By an O(2) reflection, it is related to a q = −1/2 state
with the same energy. The doublet of states with unit charge difference may be attributed to
a zero-energy electron mode that can be empty or occupied. This mode can be represented by
two Majorana modes. Since the layers are independent, we conclude that each layer contains
one zero-energy Majorana mode.
    It has been previously shown that zero-energy Majorana modes exist in some exotic one-
dimensional systems [64] as well as vortices in two-dimensional p-wave superconductors [48, 65].
A pair of Majorana modes at two vortices constitutes a full fermionic mode with a two-
dimensional Fock space. The quantum state of such a pair is virtually inaccessible to mea-
surements or perturbations as long as the vortices stay far apart from each other. A system
of 2n vortices possesses a protected space of dimensionality 2n (or 2n−1 , if we require that the
whole system have even fermionic parity).

8.3    Fusion and braiding rules
In our model a vortex carrying an unpaired Majorana mode is just one of the superselection
sectors, denoted by σ. The other sectors are 1 (the vacuum) and ε (a fermion). If two vortices
fuse, they either annihilate completely or leave a fermion behind: σ × σ = 1 + ε. The actual
fusion outcome depends on the initial quantum state. Hence the protected space of the vortex
pair has two basis vectors: |ψ1σσ i and |ψεσσ i. (The upper indices indicate the particle types
before the fusion whereas the subscript indicates the resulting particle.) The complete set of
fusion rules is as follows:

                       ε × ε = 1,        ε × σ = σ,        σ × σ = 1 + ε,                    (64)

plus trivial rules of the form 1 × x = x. Read backwards, these relations are understood as
splitting rules: for example, an ε-particle can split into two σ-particles. However, these rules
do not capture more subtle aspects of fusion and splitting, which will be discussed later.
    Braiding rules for Majorana half-vortices in a spin-triplet superconductor have been derived
by D. Ivanov [65]. Here we follow the main idea of Ivanov’s work. We should, however, keep in
mind one important difference between his setting and our model. A spin-triplet superconductor
has a locally measurable vector order parameter, which contributes to vortex-vortex interaction
and can interact with impurities. One vortex making a full turn around another may pick up
a nonuniversal phase, hence the non-Abelian statistics is defined up to arbitrary phase factors.
That is not the case for our model (or for spinless superconductors [48]), so additional arguments
are required to find the Abelian part of the vortex statistics.
    Once again, we use the fact that each vortex p carries an unpaired Majorana mode Cp ,
which is a linear combination of the operators cj on neighboring sites. The operators cj do
not commute with gauge transformations and therefore should be used with care. The gauge
can be fixed in a neighborhood of each vortex, so constructing the linear combination is not
a problem. However, the overall sign of Cp does not have invariant meaning. This ambiguity

                                               32
is avoided if we consider fermionic path operators (16), which are gauge-invariant. A suitable
linear combination of elementary paths constitutes a path that begins or ends at a vortex.
    Let us choose some reference path lp connecting each vortex p = 1, 2 . . . to a reference point
0. We will assume that the vortices lie on the horizontal axis whereas the reference point 0 is
located in the lower half-plane. Fixing the gauge along the paths, we may write
                                                    W (lp ) = Cp c0 .                                   (65)
    Let us exchange vortices 1 and 2 by moving them counterclockwise. The exchange process
is described by a unitary operator R acting on the physical Hilbert space. It also acts on
operators by conjugation: X 7→ RXR† . Clearly,

       1            2             2             1
                                                                   RW (l1 )R† = W (l1′ ) = W (l2 ),
           l1       l2   7−→          l1’           l2’ ;                                               (66)
                                                                   RW (l2 )R† = W (l2′ ) = −W (l1 ).
                0                           0
(We have used the fact that W (l2′ ) = −W (l1 ). Indeed, the paths l2′ and l1 differ by a loop
enclosing a vortex; transporting a fermion around the vortex gives rise to the minus sign.)
Hence
                       RC1 R† = C2 ,                        π        
                                                 R = θ exp  −   C 1 2 ,
                                                                   C                      (67)
                       RC2 R† = −C1 ,                         4
where θ is a phase factor. (We will see that θ is actually the topological spin of a vortex; for
now it is just an unknown parameter).
    At first sight, it is not clear whether the number θ has an invariant meaning. Indeed, the
operator that moves a vortex along a given path may be defined up to an arbitrary phase.
However, the ambiguity can be avoided by a careful definition of the particle exchange process.
The following argument is completely general; it is not based on adiabaticity or translational
invariance.
    Let us consider a vortex path operator Wσ (l) that is composed of elementary steps, i.e.,
displacements of the vortex from hexagon to hexagon.4 Each elementary displacement is defined
up to a phase, but the path operator satisfies these equations:
                           Wσ (l) = Wσ (l)† ,               Wσ (l1 l2 ) = Wσ (l2 )Wσ (l1 ).             (68)
Here l denotes the reverse path, whereas l1 l2 is the composite path (the vortex goes along l1
and then along l2 ). Remarkably, two vortices can be exchanged in such a way that the arbitrary
phases cancel each other, see Fig. 10. The vortices move along the indicated lines; each line
segment is passed by a vortex in both directions.
   As mentioned above, the vortex pair has two states corresponding to the possible fusion
outcomes, |ψ1σσ i and |ψεσσ i. They should be identified with the eigenvectors of C1 C2 , but we do
not know which is which. We can only write:
                         C1 C2 |ψ1σσ i = iα|ψ1σσ i,              C1 C2 |ψεσσ i = −iα|ψεσσ i,            (69)
   4
    The displacement may be realized as the action of σ α on one of the two spins at the boundary
                                                                                          P       between
                                                                                                         the
hexagons (which changes the field configuration) followed by an operator of the form exp     Fkm ck cm (which
adjusts the fermionic subsystem).

                                                            33
                                                 2                                     2
                           −→                                    −→                              −→
         1         2                   1                                                   1                2   1

Figure 10: A realization of the particle exchange in which all local contributions cancel, revealing
the topological effect in a pure form.

where α = ±1 is unknown. Thus the braiding operator R acts as follows:

                        R|ψ1σσ i = R1σσ |ψ1σσ i,                                       R1σσ = θ e−iαπ/4 ,
                                                                  where                                             (70)
                        R|ψεσσ i = Rεσσ |ψεσσ i,                                       Rεσσ = θ eiαπ/4 .

Remark 8.1. One may wonder why formula (67) contains the minus sign in front of C1 , but
not in front of C2 . This is, in fact, a consequence of the convention that the reference point 0
lies in the lower half-plane. If we move it to the upper half-plane, the signs will change, α will
turn into −α, and the signs in front of α in Eq. (70) will change too. The numbers R1σσ , Rεσσ
and θ are invariant though.

8.4       Associativity relations
The fusion rules only indicate what fusion and splitting events are possible. Nontrivial relations
arise if we consider a sequence of such events.

8.4.1 Relations based on the anticommutativity of fermionic operators. Let us
consider the splitting of a σ-particle into ε, σ, and ε. This can be done in two different ways,
depending on the order the two ε-particles are created. Let us suppose that the σ-particle is
located at point 2 in the middle; the ε-particles will appear at points 1 and 3 on the left and
on the right, respectively. The particles (or their future locations) are connected by the paths
l12 and l23 .
    The σ-particle is described by the associated Majorana mode C2 . The ε-particles can be
created from the vacuum by operators a†1 and a†3 . However, these operators are not physical
by themselves. To actually split the first ε-particle off the σ-particle, one needs to apply a
fermionic path operator W (l12 ), which equals a†1 C2 in a suitable gauge. The second ε-particle
is created by the operator W (l23 ) = a†3 C2 . Since W (l12 )W (l23 ) = −W (l23 )W (l12 ), we obtain
the following associativity relation between the two splitting processes:
                                             ε           σ   ε         ε   σ   ε

                                                     σ           = −       σ       .                                (71)
                                                     σ                     σ


   Similarly, we can consider the splitting of one ε-particle into three. For this, we use two
conventions:5 (i) moving an ε-particle from place j to place k is described by the operator a†k aj ;
  5
      Although these conventions are somewhat arbitrary, the result is invariant (see subsection 8.4.2).


                                                                 34
(ii) creating a fermionic pair from the vacuum is described by a†j a†k , where j is located left of
k. Thus we get:
                                             ε   ε   ε        ε   ε   ε

                                                 1       =        1                                        (72)
                                                 ε                ε

because (a†1 a†2 )(a†3 a2 ) = (a†2 a†3 )(a†1 a2 ). (In these graphs the “up” direction is time. The interme-
diate state of the middle particle is shown in all cases, but lines corresponding to label 1, i.e.,
the vacuum superselection sector, are suppressed.)

8.4.2 Some generalities. The analysis of other splitting processes (e.g., σ → σσσ) is more
complicated. Ideally, we would use the vortex path operator, but its exact form is unknown.
Therefore we have to rely on more abstract arguments. Before we proceed, let us clarify some
points pertaining to anyons in general.

   1. Speaking about anyons, we are interested in particle types (i.e., superselection sectors)
      and topology of the particle worldlines (braids, trees, etc.). An actual particle is also
      characterized by position and local degrees of freedom; for example, an ε-particle may be
      “elementary” or consist of two adjacent vortices. We generally ignore such details though.

   2. In the study of splitting and fusion, we consider particles located on the horizontal axis.
      In this case, we only care about the order of the particles on the line, but not about their
      positions. All configurations with the same particle types and order can be identified with
      each other. Unlike in the two-dimensional case, cycling through several configurations has
      trivial effect on the quantum state.6

   3. “Quantum state of a particle” is a rather subtle notion. It may be understood as a
      projector that enforces certain spin correlations in some neighborhood of the supposed
      particle location. (The neighborhood radius must be much larger than the correlation
      length). Such an object has no “overall phase”. Superpositions of states from different
      superselection sectors cannot be constructed either.

   4. In spite of that, the state |ψ1σσ i has a well-defined phase if we consider it relative to the
      vacuum. A similar argument holds for an arbitrary state |ψzxy i, which describes particles x
      and y with total “anyonic charge” z. For a general anyonic system, the xy-pair may have
      several distinct states that belongs to the same superselection sector z; in other words,
      there may be several ways to split z into x and y. Such states form a finite-dimensional
      Hilbert space Vzxy , which is called fusion space.7 In our model, all such spaces have
      dimension one or zero. For example, |ψ1σσ i is a unit vector in the one-dimensional space
      V1σσ .
   6
     This claim can be justified as follows. To move a particle z from one place to another, we apply a path
operator Wz (r, r′ ), which acts on the spins in some neighborhood of the interval [r, r′ ]. These operators are
defined in such a way that it does not matter whether the particle is moved at once or in several steps (cf.
Eq. (68)). When several particles are present, we do not let them pass through each other, which imposes a
certain restriction on the sequence of operators applied. All such sequences are actually equivalent since the
path operators for nonoverlapping intervals commute.                                                     ∗
   7                                                                                            z
     Technically, it should be called “splitting space”, whereas the fusion space is its dual, Vxy = Vzxy .


                                                         35
    For a more rigorous definition of the space Vzxy , consider the splitting of z into x and y by an
operator L that acts on the spins in some fixed finite region Ω. (We call such operators local.)
Let us also fix a quantum state |Ψz i that has a z-particle at a given place and no other particles
in Ω or within the correlation length from Ω. Finally, we consider the set of local operators
L for which the state L|Ψz i has an x-particle and an y-particle at the required places. By
definition, these are all possible states of the xy-pair that can be obtained from z. On the
other hand, such states are in one-to-one correspondence with equivalence classes of operators
L: we say that L and L′ are equivalent if L|Ψz i = L′ |Ψz i. For local operators, the equivalence
relation does not depend on the choice of |Ψz i. Thus we arrive at the following definition:
        Vzxy is the set of equivalence classes of local operators that split z into x and y.
   Each vertex in a splitting graph (as in Eqs. (71), (72) above) designates an equivalence class
                                                             ε σ
of local operators. For example,                                     = |ψσεσ i ∈ Vσεσ . One may choose an arbitrary basis in
                                                                 σ
the space Vzxy . In our case, this amounts to fixing the phase of the vectors |ψ1σσ i, |ψεσσ i, |ψσεσ i,
|ψσσε i, and |ψ1εε i. Different bases are related by a transformation of the form

                                                      |ψzxy i′ = uxy  xy
                                                                  z |ψz i,                                  |uxy
                                                                                                              z | = 1,                                             (73)

which generally affects relations like (71) and (72). However, these particular relations are
invariant since they have the same set of basis vectors on both sides: |ψσεσ i, |ψσσε i in Eq. (71)
and |ψ1εε i in Eq. (72).

8.4.3     More relations. Let us write some other possible associativity relations in a general
form:
                                  ε σ σ                          ε σ σ                          σ σ ε                          σ σ ε

                                      σ               = β1               1           ,                  1               = β2               σ           ,           (74)
                                          ε                              ε                              ε                              ε

                                  σ       ε       ε              σ       ε       ε              ε       ε       σ              ε       ε       σ

                                      σ               = γ1               1           ,              1                   = γ2               σ           ,           (75)
                                          σ                          σ                                  σ                              σ

                              σ       ε           σ          σ       ε           σ              σ           ε       σ          σ           ε           σ

                                  σ                   = δ                    σ       ,              σ
                                                                                                                        = τ                        σ
                                                                                                                                                           ,       (76)
                                      ε                              ε                                      1                              1

                          ε       σ           σ              ε       σ           σ              σ           σ       ε              σ           σ           ε

                              σ
                                                      = µ1                   ε
                                                                                     ,              ε
                                                                                                                        = µ2                           σ
                                                                                                                                                               .   (77)
                                  1                                  1                                      1                                  1

The numbers β1 , β2 , γ1 , γ2 , δ, τ , µ1 , µ2 are equal to 1 in magnitude. These and similar
coefficients are called structural parameters.
     Using the transformation (73), we can eliminate some of the parameters, e.g., β1 , β2 , and
γ1 . Indeed, they are transformed as follows:
                              uεσ
                               σ uε
                                   σσ
                                                                                          uσσ
                                                                                            1                                                  (uσε
                                                                                                                                                 σ )
                                                                                                                                                     2
                  β1′ =               β1 ,                                   β2′ =              β2 ,                       γ1′ =                       γ1 .        (78)
                               uσσ
                                 1                                                       uσ uσσ
                                                                                          σε
                                                                                              ε                                                 uεε
                                                                                                                                                  1

                                                                                         36
We require that β1′ = β2′ = γ1′ = 1 and solve for uxyz . Note that the solution is unique up to
trivial variations not affecting the structural parameters, namely

                                                uxy          −1 xy
                                                 z 7→ ζx ζy ζz uz .                                  (79)

    Finally, let us consider the splitting of one σ-particle into three σ-particles. The space Vσσσσ
is two-dimensional. A basis in this space can be chosen in two ways:
                                                                                        
              σ σ σ             σ σ σ                          σ σ σ              σ σ σ 
                                                                                        
      |ξ1 i = 1 , |ξε i = ε                     or       |η1 i =     1 ,    |ηε i =     ε    . (80)
    
                                       
                                                     
                                                                                          
                                                                                           
                  σ                    σ                                    σ                σ


Of course, one basis can be expressed in terms of the other:

      |ξ1 i = a11 |η1 i + aε1 |ηε i,       |ξε i = a1ε |η1 i + aεε |ηε i,   where axy = hηx |ξy i.   (81)

The coefficients axy and the other structural parameters will be found later. At this point, we
can only tell that the matrix (axy ) is unitary.
    To illustrate the physical meaning of the structural parameters, let us return to the gedanken
experiment considered in the introduction. Suppose we create two pairs of σ-particles from the
vacuum. Then we take one particle from each pair and fuse them. With probability |a11 |2 they
will annihilate, and with probability |aε1 |2 they will fuse into an ε-particle. (We will see that
|a11 |2 = |aε1 |2 = 1/2.)

8.5     Algebraic consistency
All the previous arguments were based on the result that vortices carry unpaired Majorana
modes. Not surprisingly, this property alone is not sufficient to fully characterize the fusion
and braiding of anyons. We now invoke some additional principles. The first one is consistency:
successive fusion and braiding events must commute with each other in certain cases. A more
careful statement of this requirement amounts to the formulation of an algebraic theory of
anyons.
    Anyons may be described in the framework of topological quantum field theory (TQFT),
which originates from Witten’s paper on quantum Chern-Simons fields [5] and the work of
Moore and Seiberg on conformal field theory [4]. Important mathematical studies in this area
were done by Reshetikhin and Turaev [66] and Walker [67]. For our purposes, it suffices to use
a construction called unitary modular category (UMC), which constitutes the algebraic core
of TQFT [68]. This construction will be outlined in Appendix E. Actually, the full theory
is not necessary to understand the calculations below. On the contrary, one may use these
calculations to motivate some of the UMC axioms.
    One of the axioms is known as the pentagon equation, see Fig. 17a on page 69. It deals with
the five ways to split a particle u into x, y, z, w, or five representation of the space Vuxyzw . The
arrows in the figure may be regarded as equality signs, therefore the diagram must commute.
For example, consider the splitting process σ → εσσσ via intermediate states q = 1 and p = σ.



                                                          37
The upper path across the diagram looks like this:
                   ε       σ       σ   σ                    ε       σ       σ    σ           ε           σ       σ       σ            ε       σ       σ       σ            ε   σ       σ       σ

                       σ                                                     1                                                                            1                                ε
                           1
                                           = a11                σ                    + aε1           σ               ε        = a11                               − aε1                            ,
                                                                                                                                                      σ                                σ

                               σ                                        σ                                    σ                                    σ                                σ


whereas the lower path is as follows:
   ε       σ       σ       σ               ε   σ        σ       σ                      ε   σ         σ           σ                        ε       σ       σ       σ                    ε       σ       σ       σ

       σ                                            ε                                            ε                                                            1                                            ε
           1
                                   = µ1         1
                                                                            = µ1 γ2                                      = µ1 γ2 a1ε                                  + µ1 γ2 aεε                                  .
                                                                                                     σ                                                    σ                                            σ

               σ                                    σ                                            σ                                                    σ                                            σ


Thus µ1 γ2 a1ε = a11 , µ1 γ2 aεε = −aε1 . One can also start with the splitting graph that has
intermediate state ε instead of 1; this gives another pair of relations between the structural
parameters.
    Overall, there are 23 spaces Vuxyzw with nontrivial upper indices. Thus we obtain 23 pen-
tagon equations, 5 of which are satisfied automatically. The remaining 18 equations imply the
following relations between the structural parameters:
                                                             
                         
                          µ 1 γ 2 a1ε = a11 ,                
                                                               µ2 γ1 aε1 = a11 ,
                                                             
                           µ1 γ2 aεε = −aε1 ,                     β2 a11 = aε1 ,
                Vσεσσσ :                             Vσσσσε :                             (82)
                         
                             β1 a11 = a1ε ,                  
                                                               µ2 γ1 aεε = −a1ε ,
                                                             
                              β1 aε1 = −aεε ;                     β2 a1ε = −aεε ;
                                                                                                                                  
                                      
                                         τ β1 aε1 = a11 ,                                                                         
                                                                                                                                    τ µ2 a11 = γ2 a1ε ,
                                                                                                                                  
                                          τ µ1 a11 = γ1 aε1 ,                                                                        δµ2 aε1 = γ2 aεε ,
                             Vσσεσσ :                                                                                     Vσσσεσ :                                                                             (83)
                                      
                                          δβ1 aεε = a1ε ,                                                                         
                                                                                                                                    τ β2 a1ε = a11 ,
                                                                                                                                  
                                          δµ1 a1ε = γ1 aεε ;                                                                         δβ2 aεε = aε1 ;
                                                                                                                                  
                                
                                     a211 + τ a1ε aε1 = 1,                                                                        
                                                                                                                                       a211 + δa1ε aε1 = 0,
                                                                                                                                  
                                  aε1 a11 + τ aεε aε1 = 0,                                                                           aε1 a11 + δaεε aε1 = β2 ,
                       V1σσσσ :                                                                                           Vεσσσσ :                                                                             (84)
                                
                                 a11 a1ε + τ a1ε aεε = 0,                                                                         
                                                                                                                                    a11 a1ε + δa1ε aεε = β1 ,
                                                                                                                                  
                                      aε1 a1ε + τ a2εε = 1;                                                                              aε1 a1ε + δa2εε = 0;

                                  V1σεεσ : τ 2 = γ1 γ2 ,                                                                     V1εεσσ , Vεεεσσ : µ1 β1 γ2 = 1,
                                  Vεσεεσ : δ 2 = γ1 γ2 ,                                                                     V1σσεε , Vεσσεε : µ2 β2 γ1 = 1,                                                   (85)
       V1εσεσ , Vεεσεσ , V1σεσε , Vεσεσε : δ = −τ,                                                                           V1εσσε , Vεεσσε : µ1 µ2 = β1 β2 .
   Equations (82–85) have only two solutions satisfying the convention that β1 = β2 = γ1 = 1:

                                               β1 = β2 = γ1 = γ2 = µ1 = µ2 = τ = 1,    δ = −1,
                                                                                                                                                                                                           (86)
                                                 a11 a1ε       κ 1 1
                                                           = √             ,    where κ = ±1.
                                                 aε1 aεε        2 1 −1

                                                                                                         38
Remark 8.2. The number of independent equations can be reduced by using a symmetry
between upper and lower indices: Vzxy ∼   = Vȳz̄x , where z̄ denotes the antiparticle for z (in our
case, ε̄ = ε, σ̄ = σ). However this symmetry generally involves nontrivial phase factors, so we
find the brute-force calculation a safer approach.
   Let us now examine consistency between fusion and braiding. Braiding is fully characterized
by the action of the counterclockwise rotation on fusion spaces: R bxy : V xy → V yx . Since in
                                                                    z      z       z
our case the spaces Vzxy and Vzyx are one-dimensional, the linear map R bxy is given by a single
                                                                         z
matrix element:8

                                  bxy |ψ xy i = Rxy |ψ yx i,
                                  R                                                                                  bxy |ψ xy i.
                                                                                                 where Rzxy = hψzyx |R                                                             (87)
                                   z    z        z    z                                                               z    z

                                                            y       x

In graphic notation,                   bxy |ψ xy i =
                                       R                                , therefore Eq. (87) reads:
                                        z    z
                                                                z


                                                                                 y       x                  y       x

                                                                                             = Rzxy                     .                                                          (88)
                                                                                     z                          z


    Nontrivial relations arise if we consider the action of braiding operators on the fusion space
of three particles. These relations can be expressed by two commutative diagrams called the
hexagon equations, see Fig. 20 on page 81. The arrows in those diagrams may be understood
as equalities of vectors in the space Vuyzx . Let us consider the following example of the first
equation (the first line below corresponds to the upper path across the hexagon, the second to
the lower path):
     σ σ σ                    σ σ σ                         σ σ σ                                  σ σ σ                                σ σ σ                                 σ σ σ

                                               κR1σσ                                 κR1σσ                                  κ(R1σσ )2                        κR1σσ Rεσσ
                  = R1σσ                 =        √                         +         √                         =             √                      +            √                    ;
         1                        1                    2                1                    2          ε                         2             1
                                                                                                                                                                      2            ε

             σ                    σ                             σ                                   σ                                       σ                                  σ


σ σ σ                    σ σ σ                σ σ σ                         σ σ σ                           σ σ σ                                   σ σ σ                       σ σ σ

                   κ                    κ                    κ                                    κRσσε                           1 + Rσσε                        1 − Rσσε
                 = √                  + √                  = √                               +     √            ε
                                                                                                                             =                                +                                .
 1                   2        1
                                          2        ε           2             1
                                                                                                       2                                2                1                2                ε

     σ                    σ                    σ                                 σ                                  σ                                σ                                 σ
                                              √                                                      √
Thus we get: 1 + Rσσε = κ 2(R1σσ )2 , 1 − Rσσε = κ 2R1σσ Rεσσ .
  The full set of equations arising from the first hexagon is as follows:
                                     √
                        1 + Rσσε = κ √2(R1σσ )2 ,
               Vσσσσ :   1 − Rσσε = κ √ 2R1σσ Rεσσ ,         Vεεεε : (Rεεε )2 = 1;                                                                                                 (89)
                       
                         1 + Rσσε = −κ 2(Rεσσ )2 ,

     8                                                                   bxy . This should not cause confusion
    In Appendix E, we take the liberty to omit the hat from the notation Rz
because we do not consider matrix elements there.

                                                                                             39
                   V1εσσ , V1σεσ : Rσσε Rεσσ = R1σσ ,                V1σσε : (Rσεσ )2 = R1εε ,
                   Vεεσσ , Vεσεσ : Rσσε R1σσ = −Rεσσ ,               Vεσσε : −(Rσεσ )2 = 1,               (90)
                   Vσσεε , Vσεσε : R1εε = −1,                         Vσεεσ : −(Rσσε )2 = 1.
The second hexagon is obtained from the first by replacing Rzxy with (R−1 )xy          yx −1
                                                                                 z = (Rz ) . For
example, the equation Rσσε Rεσσ = R1σσ becomes (Rσεσ )−1 (Rεσσ )−1 = (R1σσ )−1 .
   Eliminating redundancies, we get this system of equations:

                                                                κ(1 + Rσσε )
      R1εε = −1,       Rσσε = Rσεσ = ±i,        (R1σσ )2 =          √        ,     Rεσσ = −Rσσε R1σσ ,    (91)
                                                                      2
where κ = ±1. The system has eight solutions, which all fit Eq. (70). Specifically, the solutions
have the form

           R1εε = −1,        Rσσε = Rσεσ = −iα,              R1σσ = θ e−iαπ/4 ,       Rεσσ = θ eiαπ/4 ,   (92)

where the following combinations of θ, α, and κ are possible:

               θ     e−7iπ/8 e−5iπ/8 e−3iπ/8 e−iπ/8 eiπ/8 e3iπ/8 e5iπ/8 e7iπ/8
               α       +1      −1      +1     −1     +1    −1     +1     −1 .                             (93)
               κ       +1      −1      −1     +1     +1    −1     −1     +1

   Thus the properties of anyons are defined by the value of θ, which satisfies θ8 = −1.

8.6     Final details
To choose the the right solution and to complete the description of non-Abelian anyons, we use
Eq. (62) in conjunction with some general results from Appendix E.              √
   The matrix element a11 = hη1 |ξ1 i (cf. Eqs. (80), (81), (86)) is equal to κ/ 2. But according
to Eq. (187) on page 74, a11 = κσ /dσ , where dσ is the quantum dimension of the σ-particle,
and κσ is the Frobenius-Schur indicator. Therefore
                                          √
                                   dσ = 2,            κσ = κ.                                (94)

   The topological spin of the σ-particle can be computed using Eq. (211) on page 82:
                                                       
                                  θσ = d−1    σσ
                                         σ R1 + Rε
                                                    σσ
                                                         = θ.                                             (95)

This result also follows from Eq. (215). Matching it with the expression of θσ in terms of the
Chern number, we represent all eight cases in (93) by these formulas:
                                                                                  2
                        θ = eiπν/8 ,     α = (−1)(ν−1)/2 ,            κ = (−1)(ν −1)/8 .                  (96)

   Thus we have obtained almost all properties in Table 1. The remaining structure, namely
the topological S-matrix, can be found using general rules (see Appendix E).




                                                        40
Superselection sectors: 1 (vacuum), ε (fermion), e, m (vortices).

   Quantum dimension:                          d1 = 1,                       dε = 1                    de = dm = 1;
                                                                                                                              
   Topological spin:                           θ1 = 1,                       θε = −1,                  θe = θm = θ = exp π8 iν ;
                                                                                                                                
   Frobenius-Schur indicator:                  κ1 = 1,                       κε = 1,                   κe = κm = κ = exp π4 iν .

Fusion rules:

  ε × ε = 1,     ε × e = m,                ε × m = e,                             e × e = m × m = 1,                                 e × m = ε.

Case 1: ν ≡ 0, 8 (mod 16);                 θ = ±1, κ = 1.

     Associativity relations: all associativity relations are trivial.

     Braiding rules:
                                                                                eε                        εe
                                                                               Rm  = 1,                  Rm  = −1,
                                 R1εε = −1,
                                                                               Reεm = 1,                 Remε = −1,
                         R1ee = R1mm = θ,
                                                                               Rεem = θ,                 Rεme = −θ,


Case 2: ν ≡ ±4 (mod 16);                  θ = ±i, κ = −1.

     Nontrivial associativity relations:
                          e e e                 e e e                              m m m                     m m m

                              1          = −        1           ,                      1               = −       1           ,
                                 e                  e                                  m                         m


                      ε       e      ε          ε   e       ε                      ε           m ε           ε   m ε

                          m              = −            m           ,                      e           = −           e           ,
                              e                     e                                          m                 m

                     e       ε       e         e    ε       e                      m ε             m         m       ε       m

                         m               = −            m       ,                      e               = −               e       .
                             ε                      ε                                      ε                         ε


     Braiding rules:

                          R1εε = −1,                                          eε
                                                                             Rm     εe
                                                                                 = Rm  = Reεm = Remε = θ,
                    R1ee = R1mm = θ,                                               Rεem = Rεme = 1.


                    Table 2: Properties of anyons for ν ≡ 0 (mod 4).



                                                                        41
    Superselection sectors: 1 (vacuum), ε (fermion), a, ā (vortices).

     Quantum dimension:                              d1 = 1,               dε = 1                     da = dā = 1;
                                                                                                                              
     Topological spin:                               θ1 = 1,               θε = −1,                   θa = θā = θ = exp π8 iν = ±1±i
                                                                                                                                  √ ;
                                                                                                                                   2
     Frobenius-Schur indicator:                      κ1 = 1,               κε = 1.

    Fusion rules:

        a × ε = ā,        ā × ε = a,                    ε × ε = 1,                  a × a = ā × ā = ε,                            a × ā = 1.

    Nontrivial associativity relations:

                               a a a                     a a a                    a a a                      a a a
                                   ε           = −             ε       ,              ε               = −            ε       ,
                                       a                   a                              a                      a


                           ε       a       ε          ε    a       ε              ε       a       ε          ε   a           ε

                               a               = −             a       ,                  a           = −            a           ,
                                   a                       a                              a                      a

                          a        ε       a         a     ε       a              a           ε   a          a       ε       a

                               a               = −             a       ,              a                = −               a       .
                                   ε                       ε                                  ε                      ε

    Braiding rules:

                        R1εε = −1,                                 Rāaε = Rāεa = Raāε = Raεā = θ−2 ,
                  Rεaa = Rεāā = θ,                                        R1aā = R1āa = θ−1 .


                               Table 3: Properties of anyons for ν ≡ 2 (mod 4).

9      The sixteen-fold way
Let us again consider the theory with Z2 -vortices and free fermions whose spectrum is gapped
and characterized by the Chern number ν. The properties of anyons in this model depend on
ν mod 16. In the previous section we studied the case of odd ν; now we assume that ν is even.
    For even ν, the vortices do not carry unpaired Majorana modes (see Appendix C), therefore
a vortex cannot absorb a fermion while remaining in the same superselection sector. Thus,
there are actually two types of vortices, which are transformed one to another by adding a
fermion. Two vortices of the same type may either annihilate or fuse into a fermion. In the
first case the vortices are denoted by e and m; they obey the fusion rules (41). In the second
case, we denote the vortices by a and ā; the fusion rules are as follows:

          a × ε = ā,      ā × ε = a,                ε × ε = 1,                  a × a = ā × ā = ε,                               a × ā = 1.    (97)

                                                                           42
Both sets of rules are Abelian, i.e., they do not contain “+” on the right-hand side.
    The associativity relations can be found along the same lines as in the non-Abelian case.
First, the fermions must obey the trivial relation (72). The argument used in the derivation of
Eq. (71) remains valid, but we obtain two relations instead of one. Note that they are not in-
variant individually; for example, the sign in both relations may be changed to “+”. Finally, we
solve the pentagon equation. The fusion rules with e and m admit two nonequivalent solutions,
one of which is trivial; see Table 2. Both solutions are invariant under the transformation

                  |ψεme i 7→ −|ψεme i,     eε
                                         |ψm          eε
                                              i 7→ −|ψm  i,   |ψeεm i 7→ −|ψeεm i           (98)

(where |ψzxy is the basis vector in the corresponding fusion space), as well as trivial transfor-
mations
                                      |ψzxy i 7→ ζx ζy ζz−1|ψzxy i.                         (99)
In the case of a and ā, there is only one solution, which doesn’t admit any nontrivial symmetry;
see Table 3.
    The braiding rules are found by solving the hexagon equations in conjunction with the
requirement that R1εε = −1 and that transporting a fermion around a vortex is described by
the multiplication by −1. Then we compute the topological spin of the vortex and identify each
solution with a particular value of ν mod 16. The results are summarized in Tables 2 and 3.
(We have eliminated redundant solutions that can be obtained by the transformation (98)).
    Let us mention a couple of interesting properties of these Abelian theories. For ν ≡ 8
(mod 16), all three nontrivial particles (e, m, and ε) are fermions. For ν ≡ ±4 (mod 16), the
particles e and m are semions with trivial mutual braiding. (In comparison, the well-known
Kalmeyer-Laughlin state [69] has one semionic species.)


10     Odds and ends
What follows are some open questions, as well as thoughts of how the present results can be
extended.

  1. Duan, Demler, and Lukin [42] proposed an optical lattice implementation of the Hamil-
     tonian (4). It would be interesting to find a solid state realization as well. For example,
     the anisotropic exchange could be simulated by interaction of both lattice spins with a
     spin-1 atom coupled to a crystal field.
  2. The weak translational symmetry breaking in the Abelian phase has some interesting
     consequences. A particularly unusual phenomenon takes place when the lattice has a
     dislocation. A particle winding around the dislocation changes its type: e ↔ m. Since
     m = e × ε, the fermionic parity appears not to be conserved. To restore the conservation
     law, we must assume that the dislocation carries an unpaired Majorana mode. Therefore,
     Abelian phases can also be used for the implementation of quantum memory.
  3. Chiral phases (ν 6= 0) require that the time-reversal symmetry be broken. In the present
     model, this is achieved by applying a magnetic field. However, a spontaneous breaking of
     time-reversal symmetry occurs in the presence of odd cycles in the lattice. For example,
     one can replace each vertex of the honeycomb lattice by a triangle. In this case, a gapped
     ν = ±1 phase is realized without external magnetic field [70].
                                               43
4. The representation of a spin by four Majorana fermions might be useful for other models,
   even though it does not lead to an exact solution. In particular, one can consider a
   variational mean-field state in which cj are decoupled from bαj . It is unclear whether
   this type of states occur in Heisenberg antiferromagnets. On the triangular lattice, such
   a state has larger energy than the 120◦ Neel-type state. It would be interesting if the
   former could be stabilized by additional interactions and quantum fluctuations.

5. Topological phases with free fermions coupled to an effective Z2 gauge field have been
   classified by ν mod 16. However, this analysis does not include multilayer systems. One
   can argue that if the interaction between the layers is weak enough, topological particles
   cannot tunnel between the layers. Thus, each layer is described by one of the 16 theories
   studied above. In mathematical terms, we have the direct product of several unitary mod-
   ular categories (UMCs). Strongly interacting layers are roughly described by n fermionic
   species interacting with (Z2 )n -vortices, but a complete classification of such phases is yet
   to be found.

6. In addition to the particle classification, the chiral central charge c− = ν/2 is an important
   robust characteristic, though its topological meaning is not so clear. It appears that in
   multilayer systems the total value of ν is shared between the layers, i.e., increasing ν by
   16 in one layer while decreasing it in another does make a different topological phase.
   More generally, a topological phase is characterized by a UMC and a real number c−
   satisfying the relation (172). To prove or disprove this statement, a mathematical notion
   of equivalence between topological phases is necessary. It may be based on local (or
   quasilocal) isomorphisms between operator algebras.

7. A related question is whether the space-time boundary of an arbitrary topological phase
   can be described by a two-dimensional conformal field theory (CFT) and when two such
   theories have the same topological content. Two CFTs may be considered topologically
   equivalent if there is a consistent theory for a one-dimensional boundary between them.
   Conjecturally, this is the case if and only if both CFTs have the same chiral central charge
   c− = c − c and correspond to the same UMC.

8. Another topic to study is Bose-condensation of vortices, which occurs when a vortex
   energy becomes negative due to some parameter change. The condensation of e-particles
   in the ν = 0 phase is equivalent to the confinement of m- and ε-particles. Thus, the
   topological order is destroyed. In the ν = 16 system, this process produces a phase
   without anyons or fermions, but with the chiral central charge c− = 8. Under special
   circumstances, the boundary of this phase is described by the E8 CFT at level 1, though a
   generic (nonconformal) perturbation drives it into a state with 8 chiral bosons propagating
   with different velocities.

9. The condensation of εε-pairs in two adjacent ν = 1 layers leads to the binding of single-
   layer vortices into σσ pairs, which are equivalent to a or ā in the ν = 2 phase. Thus
   the direct product of two ν = 1 theories is related to the ν = 2 theory. It would be
   interesting to have a general mathematical characterization of such relations. The notion
   of lax tensor functor (see Remark E.26 on page 101) can be useful in this regard.


                                             44
Appendix A:                                             Numerical results on the stability of the
                                                        vortex-free phase
The goal of this study is to compare the energy of the vortex-free phase with that of other
phases. The case Jx = Jy = Jz = 1 has been investigated most carefully. The energy of
the vortex-free phase equals E0 ≈ −1.5746 per unit cell (i.e., per two sites, or one hexagon).
The actual computation was done for tori with periodic or antiperiodic boundary conditions
in each direction. The vortex-free phase and other periodic phases with small period are
computationally very simple, so dealing with large tori is not a problem. However, the energy
calculation for an arbitrary vortex configuration requires finding the singular values of an N ×N
matrix, where N is the number of unit cells. With our setup (MATLAB on a PC)√we could
handle matrices of size N ⩽ 2500, which corresponds to systems of linear size L = N ⩽ 50.
Although these numbers are pretty large, finite-size effects are still appreciable due to the
gapless nature of the spectrum (see Section 4).
                                0.1                                                                                   0.1



                               0.05                                                                                  0.05
            Relative energy




                                                                                                  Relative energy

                                 0                                                                                     0



                              −0.05                                                                                 −0.05

                                                                         periodic b.c.
                                                                         antiperiodic b.c.
                               −0.1                                                                                  −0.1
                                   0   3   6   9 12 15 18 21 24 27 30 33 36 39 42 45 48                                  0   3   6   9 12 15 18 21 24 27 30 33 36 39 42 45 48
                                                              L                                                                                     L

                                a) tori with basis (Ln1 , Ln2 )                                   b) tori with basis (Ln1 , Ln2 + n1 )
                                                Figure 11: Finite size effects in the vortex-free phase.

    Let us first discuss the finite-size effects in the vortex-free phase. From now on, we consider
the relative energy, i.e., we subtract NE0 from actual results. The plot in Fig. 11a shows the
relative energy as a function of size for symmetric L × L tori. The oscillatory behavior with
period 3 is due the fact that ε(q) vanishes at q = q∗ (see (34)). One may argue that each period
r of the torus contributes ∼ |r|−1 cos(2(q∗ , r)) to the total energy (there are infinitely many
such terms since the periods form a lattice). Interestingly enough, these contributions almost
cancel each other for periodic boundary conditions on the torus with basis (Ln1 , Ln2 + n1 ),
where n1 and n2 are the basis vectors of the lattice (see figure in Eq. (32)). The corresponding
plot is shown in Fig. 11b.
    The energy of an isolated vortex is Evortex ≈ 0.1536 above the ground state.9 The calculation
was done for tori with basis (Ln1 , Ln2 + n1 ) for L = 9, . . . , 32. (We actually put 4 vortices
on the torus of twice this size because the number of vortices must be even). Then the results
were extrapolated to L = ∞ by fitting the curve E(L) = Evortex + a1 L−1 + a2 L−2 to the data,
separately for L = 3k, L = 3k + 1, and L = 3k + 2 (see Fig. 12).
   9
    No rigorous precision analysis was attempted, but the error in this and the other figures is expected not to
exceed 1–2 units of the least significant digit.



                                                                                             45
                                                     0.154

                                                     0.153




                                 Energy per vortex
                                                     0.152

                                                     0.151

                                                      0.15

                                                     0.149    L=3k
                                                              L=3k+1
                                                              L=3k+2
                                                     0.148
                                                          0       0.02   0.04        0.06   0.08   0.1
                                                                                 1/L


Figure 12: Extrapolation to infinite size: 4 equally spaced vortices on the torus with basis
(2Ln1 , 2(Ln2 + n1 )).


                                                                                                                
             Evortex ≈ 0.1536,                        ∆E                        ≈ −0.04,           ∆E                  ≈ −0.07.

                                  Energy                                                                             Energy
                          Vortex                                                                             Vortex
                Phase             per and                                                     Phase                  per and
                          density                                                                            density
                                  per vortex                                                                         per vortex
                             1                                0.067                                            2          0.042
         1                                                                           8
                             1                                0.067                                            4          0.085

                             1                                0.052                                            3          0.059
         2                                                                           9
                             2                                0.104                                            4          0.078

                             1                                0.041                                            1          0.042
         3                                                                           10
                             3                                0.124                                            4          0.167

                             2                                0.054                                            3          0.074
         4                                                                           11
                             3                                0.081                                            4          0.099

                             1                                0.026                                            1          0.025
         5                                                                           12
                             3                                0.078                                            4          0.101

                             2                                0.060                                            2          0.046
         6                                                                           13
                             3                                0.090                                            4          0.092

                             1                                0.034                                            3          0.072
         7                                                                           14
                             4                                0.136                                            4          0.096

Table 4: Numerical results for Jx = Jy = Jz = 1. Vortices are shown in gray; for periodic
phases the unit cell is indicated by a parallelogram.


                                                                                46
    The energy of a vortex pair is smaller than 2Evortex if the vortices are close to each other:
by ≈ 0.04 for nearest neighbors and by ≈ 0.07 for next-nearest neighbors. (We didn’t try
to compensate the finite size effects, so the precision is poor). These numbers suggest that
inter-vortex interaction is rather strong and could, in principle, result in some configurations
having negative energy. However, our further calculations give evidence for the contrary.
    We have checked all periodic phases with unit cell containing 1, 2, 3 or 4 hexagons, see
Table 4. (As mentioned above, this computation requires much less computer resources than
the study of separate vortices or vortex pairs). In all these cases the energy is positive and
increases as more vortices are added. The smallest energy per vortex is achieved by phases 1
and 5 — 0.067 and 0.078, respectively.
    All 14 phases have positive energies (relative to the vortex-free phase) for all nonzero values
of Jx , Jy , Jz .


Appendix B:               Edge modes in phases Bν
It is understood that the edge spectrum depends strongly on particular conditions at the edge.
The calculations below are only meant to illustrate the universal feature of the spectrum —
the existence of a chiral gapless mode.
    Let us suppose that the honeycomb lattice fills the lower half-plane and is cut as follows:
                              bz        bz        bz      bz                0
                                                                            1
                                                                            2

                                                                            3
                                                                            4

                                                                            5


Row 0 consists of the Majorana operators bzj , which would be decoupled from the rest of
the system if not for the magnetic field. Performing the Fourier transform in the horizontal
direction, we compute effective couplings between the rows as functions of qx :
                                                   
                0    iγ    0
             −iγ α        is −β                                     r = 2J,
                                                   
              0 −is −α ir             β            
                                                                    s = −4J cos q2x ,
                   −β −ir α          is −β         
  iA(qx ) = 
                                                    
                                                ..  ,    where       α = 4κ sin qx ,   (100)
                          β −is −α ir            .                             qx
                                                                     β = 4κ sin 2 ,
                                               .. 
                               −β −ir α          .                  γ = −2hz .
                                      ..   .. ..
                                         .   .    .
   Let us first find edge modes ignoring the operators bzj , i.e., the first row and column in the
above matrix. If κ = 0, then for 2π/3 < qx < 4π/3 the matrix has a null vector with elements
                                          j
ψ(2j) = 0 and ψ(2j + 1) = −2 cos q2x , which corresponds to a zero-energy state localized
near the edge. If κ is not zero but still small, we get this spectrum:
                          ε(qx ) ≈ 12κ sin qx ,        qx ∈ [2π/3, 4π/3].                    (101)

                                                  47
         ε( qx )                                                   ε( qx )




                   2π /3   π     4π /3         2π   qx                                π                  2π   qx




                            a)                                                        b)

Figure 13: Schematic form of the edge spectrum in the simplest case (a) and with the operators
bzj taken into account (b). The shaded area represents the bulk spectrum.


It is shown in Fig. 13a, assuming that κ > 0, i.e., ν = +1. The point where the energy curve
crosses zero, qx = π, corresponds to a left-moving gapless mode.
    Now we take the operators bzj into account. If κ = 0, then a zero mode exists for qx ∈
[−2π/3, 2π/3], whereas for qx ∈ [2π/3, 4π/3] there are two modes with energies
                                              q
                                   ε(qx ) ≈ ±γ 1 − 4 cos2 q2x .                        (102)

The spectrum for κ > 0 is shown schematically in Fig. 13b. In this case a left-moving gapless
mode occurs at qx = 0.
    In conclusion, let us give a simple (but not completely rigorous) proof of Eq. (56). The idea
is due to Laughlin [71]: we put the system on a cylinder and run magnetic flux through it. For
simplicity, we consider a cylinder of the smallest radius, which is equal to the lattice period
divided by 2π. Thus the Hamiltonian is given by the matrix iA(qx ); the variable qx plays the
role of the magnetic flux.
    Let qx vary from 0 to 2π. When the energy of an edge state10 |ψi crosses zero, the spectral
projector P (qx ) changes by |ψihψ|. For an arbitrary operator Q the quantity Tr(QP (qx ))
changes by hψ|Q|ψi. Let
                                                 
                                                   1 near the edge,
                   Qjk = g(j)δjk ,        g(j) =                                            (103)
                                                   0 far away from the edge

(the exact form of the function g is not important). Then hψ|Q|ψi ≈ 1. Since Tr(QP (qx )) is
a periodic function of qx , the abrupt changes must be compensated by a continuous variation,
which we call “adiabatic”. Thus
              Z                                                        
                                                                     dP
       νedge = I(qx ) dqx ,        where I(qx ) = − Tr(QṖ ), Ṗ =                 .   (104)
                                                                     dqx adiabatic
 10
      We are using the first quantization formalism, therefore “states” are just superpositions of lattice points.



                                                         48
   The adiabatic evolution of the spectral projector may be represented by the Heisenberg
equation with a suitable Hamiltonian:

                                   Ṗ = i[H, P ],         where H = i[P, Ṗ ].                          (105)

Indeed, P 2 = P , hence P Ṗ + Ṗ P = Ṗ and P Ṗ P = 0, implying that −[[P, Ṗ ], P ] = Ṗ . Therefore
                                                                                     
        I(qx ) = −i Tr QHP − QP H = −i Tr HP Q − HQP = −i Tr H[P, Q] .                            (106)

(These transformations are valid because each trace is represented by a finite sum.) The last
expression in Eq. (106) may be calculated using the spectral projector for the bulk. Indeed, if
the function g were constant, the commutator [P, Q] would vanish; thus the main contribution
comes from the region where g changes from 1 to 0.
    In the final part of the proof, we take into account the periodicity of the bulk spectral
projector, representing the site index j as (s, λ). As is usual, lattice cells are indexed by s;
it is an integer that increases in the positive y-direction. We may assume that the function g
depends only on s and satisfies lims→∞ g(s) = 1, lims→−∞ g(s) = 0. Then
                                                         X                  
                [P, Q] tµ,sλ = g(s) − g(t) Ptµ,sλ ,            g(t + r) − g(t) = r.
                                                                          t

Using these auxiliary identities, we pass to the momentum representation:
                  X                              X                  X                 
 Tr H[P, Q] =          Hsλ,tµ Ptµ,sλ g(s) − g(t) =     H0λ,−rµ P0µ,rλ   g(t + r) − g(t)
                     s,λ,t,µ                                      r,λ,µ           t

                     X                               Z                 Z              
                                                            e ∂ Pe dqy          e ∂ Pe ∂ Pe dqy
                 =           H0λ,−rµ P0µ,rλ r = −i       Tr H          =   Tr P ,
                     r,λ,µ
                                                              ∂qy 2π              ∂qx ∂qy 2π

Substituting the result into (106) and (104), we get
                               Z                     Z                 
                                                −i            e ∂ Pe ∂ Pe
                  νedge =          I(qx ) dqx =          Tr P ,             dqx dqy = ν.
                                                2π              ∂qx ∂qy

Appendix C:                     Quasidiagonal matrices
The goal of this appendix is to provide a formal argument for the existence of unpaired Majorana
modes on vortices for odd values of the Chern number ν. However, the developed formalism
may be interesting on its own right. It suggests a rather efficient approach to problems like
quantization of Hall conductivity in disordered systems without the use of excessively heavy
tools. Some of results (in particular, the ones concerning the flow of a matrix and the Chern
number) are actually poor man’s variants of known mathematical theorems.11 A powerful
theory, called noncommutative geometry [45] was used by Bellissard at al [1] to prove rigorously
that the Hall conductivity is quantized provided the electron are localized (see [72, 73] for
  11
    Note for experts: we are effectively trying to build a K-theory on a manifold by considering functions that
are not continuous, but rather constant on cells that are dual to simplices. This seems to be an awkward
approach, but its possible advantage is the relation to a second-quantized case, see Appendix D.

                                                         49
                 η                                   η                                    η
                a)                                  b)                                    c)

Figure 14: Cutting a Majorana chain: Mη (B) = 1 in cases (a) and (c) whereas Mη (B) = −1
in case (b). The dashed lines in (c) show a possible way to reconnect the broken pairs.

another proof). We will use similar ideas, but focus mainly on providing the intuition rather
than mathematical rigor.
   A physical example of a quasidiagonal matrix is an electron hopping matrix T = (tjk ) on
a d-dimensional lattice. It is a Hermitian matrix with the property that tjk is bounded in
magnitude and vanishes if the distance |j − k| between the sites j and k is greater that some
constant L. Furthermore, if T has a spectral gap, i.e., if the eigenvalues
                                                                          are bounded away from
                                                        1
zero, then the corresponding spectral projector P = 2 1 − sgn T is also quasidiagonal. More
specifically, the matrix elements Pjk decay exponentially with distance.12
   In general, a quasidiagonal matrix is a lattice-indexed matrix A = (Ajk ) with sufficiently
rapidly decaying off-diagonal elements. Technically, one requires that

                                    |Ajk | ⩽ c|j − k|−α ,         α > d,

where c and α are some constants, and d is the dimension of the space. Note that “lattice”
is simply a way to impose coarse Rd geometry at large distances. We may think about the
problem in these terms: matrices are operators acting in some Hilbert space, and lattice points
are basis vectors. But the choice of the basis need not be fixed. One may safely replace the
basis vector corresponding to a given lattice point by a linear combination of nearby points.
One may also use some kind of coarse-graining, replacing the basis by a decomposition into
orthogonal subspaces corresponding to groups of points, or regions in Rd .
    Let us outline the main results. We first consider quasidiagonal unitary matrices in one
dimension and define an integral topological characteristic called flow. Then we study projection
matrices in two dimensions. The Chern number ν(P ) of a quasidiagonal projection matrix P is
expressed directly in terms of the matrix elements Pjk , see Eqs. (124) and (122). This definition
does not rely on translational invariance, but in the translationally invariant case we reproduce
Eq. (54).
    After those preliminaries, we switch to questions related to Majorana fermions (all necessary
background is given in Section 3). From the mathematical point of view, we study quasidiagonal
real skew-symmetric matrices B satisfying the condition B 2 = −1. In one dimension, such a
matrix is assigned a cutting obstruction Mη (B) = ±1 with respect to an arbitrary cut η dividing
the chain into two parts. Let us explain the physical meaning of this number. The matrix B
defines a pairing of Majorana modes (in the exact sense stated right after Eq. (27), but we
will use a cartoon description for illustration). If we cut the chain, the resulting pieces may
carry unpaired boundary modes [64]. This happens when an odd number of pairs is broken, as
  12
    Indeed, the function f (x) = sgn x can be approximated by a sequence of polynomials pn (x) of degree n → ∞
which converges exponentially on the spectrum
                                                of T . Therefore kP − pn (T )k < abn for some b < 1 . On the
other hand, the matrix elements pn (T ) jk vanish if |j − k| > nL.

                                                     50
                                             3
                                        2
                                    1
                                                 r             0    1   2    3



                                a)                                      b)

Figure 15: A map from two to one dimension: annular regions around the vortex (a) are
collapsed into points on a ray (b).

in Fig. 14b; otherwise one can modify the matrix near the cut so that to avoid broken pairs,
see Fig. 14c. More formally, let us consider quasidiagonal real skew-symmetric matrices B ′
that agree with B at infinity but have no nonzero elements across the cut. We prove that if
Mη (B) = −1, then no such B ′ exists that satisfies the equation (B ′ )2 = −1. Note that while
Mη (B) depends on the cut, the relative Majorana number of two matrices on the same chain,
M(A, B) = Mη (A)Mη (B) is invariant.
     The concept of Majorana number is also applicable in two dimensions. Let B 2 = −1,
and let us construct another matrix B ′ by inserting a Z2 -vortex at the origin. More exactly,
   ′
Bjk   = ±Bjk , where the minus sign occurs when the link (j, k) crosses some fixed ray r (an
analogue of the Dirac string). Note that the condition (B ′ )2 = −1 is only true asymptotically
(i.e., far away from the origin); it may or may not be possible to satisfy this equation by altering
the matrix elements near the vortex. In fact, the presence of an unpaired Majorana mode at
the vortex is defined as locally unrepairable failure of the equation (B ′ )2 = −1. Such a mode is
detected by an absolute Majorana number M(B ′ ). For its construction, let us regard B and
B ′ as one-dimensional by keeping track of the radial direction only: we divide the plane into
concentric rings and map all sites in each ring to a single location on a ray (see Fig. 15). To
simplify the calculation, we cut out the interior of a sufficiently large circle η; let |η| be the
number of sites removed. The presence or absence of an unpaired mode in this case is given
by Mη (B ′ ), which is defined using some annular neighborhood of η. Extrapolating to |η| = 0,
we get M(B ′ ) = (−1)|η| Mη (B ′ ) = M(B, B ′ ). The last number only depends on the matrix
elements of B in some neighborhood of the intersection point between η and r. Finally, we
show that M(B, B ′ ) = (−1)ν(P ) , where ν(P ) is the Chern number associated with the projector
P = 12 (1 − iB). Thus, vortices carry unpaired Majorana modes if and only if ν(P ) is odd.

C.1     The flow of a unitary matrix
C.1.1 Definition. Let us consider an arbitrary (possibly infinite) unitary matrix U = (Ujk ).
We refer to the values of j and k as “sites” and define a “current” flowing from k to j:

                                            fjk = |Ujk |2 − |Ukj |2 .                               (107)
                      P  ∗
                                    P          ∗
Since U is unitary,   j Ujl Ujk =       j Ulj Ukj = δlk , therefore the current is conserved at each site:
                                                     X
                                                         fjk = 0.                                   (108)
                                                     j


                                                         51
Suppose that the sites are positioned on a line (more specifically, enumerated by integers),
and that the off-diagonal matrix elements of U decay fast enough. We will see later that the
condition
                            |Ujk | ⩽ c|j − k|−α , where α > 1,                         (109)
is sufficient for our purposes. For now, let us simply assume that Ujk vanishes if |j −k| is greater
than some constant L. Then it is obvious that the total current through a “cross section” η,
                                                  XX
                                       F (U) =           fjk ,                                 (110)
                                                   j⩾η k<η

does not depend on the choice of η. The number F (U) is called the flow of U. For example,
the matrix with entries Ujk = δj, k+s has flow s.

C.1.2 Integrality of the flow. A nontrivial property is that the flow is quantized, i.e.,
has an integer value. To prove this statement, let us introduce the projector onto the sites M
through N:                              (
                               [M,N ]     1 if M ⩽ j = k ⩽ N,
                             Πjk      =                                                   (111)
                                          0 otherwise.
The projector onto an infinite interval is defined similarly. Let Π = Π[0,∞) ; then
                                                                                 
            F (U) = Tr U † ΠU(1 − Π) − Tr U † (1 − Π)UΠ = Tr U † ΠU − Π .                     (112)
(Caution: In the last expression, the orderPof operations is important: we first compute the
matrix Λ = U † ΠU − Π, and then its trace, j Λjj . It is not possible to use the cyclic property
of the trace, Tr AB = Tr BA, since it is only valid if one of the matrices has a finite number of
nonzero elements or, more generally, if the sum involved in the calculation of the trace converges
absolutely.)
    Note that the matrices Π and U † ΠU are orthogonal projectors. If they were finite, their
traces would be integers, and the difference would also be an integer. In the infinite case, one
may refer to the general notion of the relative index of two projectors [73, 74]. However, we
will proceed in a more pedestrian fashion and simply truncate the matrices.
    Let Λ = U † ΠU − Π. It is clear that the matrix element Λjk vanishes if |j| or |k| is greater
than L, so Λ is not changed by the truncation to the interval [−L, L]. Hence
                                                                     def
           F (U) = Tr(U † ΠU)trunc − Tr Πtrunc ,        where Atrunc = Π[−L,L] AΠ[−L,L] .     (113)
If A is an orthogonal projector and commutes with Π[−L,L] , then Atrunc is also an orthogonal
projector. Obviously, Π and Λ commute with Π[−L,L] , and so does the matrix U † ΠU = Π + Λ.
Thus both Πtrunc and (U † ΠU)trunc are orthogonal projectors. It follows that F (U) is an integer.
    In equation (112), the projector Π may be replaced by another operator with the same
asymptotics at infinity. (In other words, we can “blur” the boundary between the left and the
right half-line.) Indeed, the expression Tr(U † AU − A) vanishes if the cyclic property of the
trace is true, i.e., if the elements of A decay at infinity fast enough. Adding such a matrix A
to Π will not change the result. Thus
                                                                   (
                                                                   δjk for j, k → +∞,
   F (U) = Tr U † QU − Q = Tr U † [Q, U] ,         where Qjk =                              (114)
                                                                     0   for j, k → −∞.

                                                   52
(Here we also assume that the matrix Q is quasidiagonal, i.e, |Qjk | is bounded by a rapidly
decaying function of |j − k|, cf. (109).)

C.1.3 Translationally-invariant case. The flow can be easily calculated if U possesses a
translational symmetry. Let us group the sites by unit cells and index them as (s, λ), where s
is the number of the cell, and λ refers to a position type inside the cell. We assume that Usλ,tµ
depends only on t − s, λ and µ. In this case, we can express F (U) in terms of the trace per
unit cell (denoted by tr) and a position operator X:
                                            
                      F (U) = tr U † [X, U] ,      where Xsλ,tµ = s δst δλµ .              (115)
(For a proof, replace the factor s in the definition of X by the function g(s) such that g(s) = s
for |s| ⩽ N and g(s) = N sgn s for |s| > N, where N is large; then use Eq. (114)).
    In the momentum representation, the operator U becomes U        eµλ (q) = P ei(q,t) U0λ,tµ . We
                                                                                t
may also use these simple rules:
                                          e               Z π
                                        dA                    dq     e
                            [X, A] → i      ,     tr A →          Tr A.                        (116)
                                        dq                 −π 2π
Thus                                 
                          i
                              Z π
                                           d e
                                             U          1
                                                          Z q=π
                                                                              
                 F (U) =           Tr Ue †
                                                dq = −                   e
                                                                d ln det U(q)   .             (117)
                         2π     −π         dq          2πi q=−π

C.2     General setting
The result about the flow quantization can be extended to matrices satisfying condition (109),
which guarantees that the sum in Eq. (110) converges absolutely.
    Another generalization is coarse-graining, which means to allow multiple states per site. The
sites are now described by orthogonal subspaces of the total Hilbert space. This generalization
is useful if want to treat a two-dimensional system as one-dimensional.
    Finally, we may try
                      P to apply theP notion∗ of flow to finite systems. Let us assume that the
unitarity condition, j Ujl∗ Ujk = j Ulj Ukj      = δlk , is approximate and holds only if j and k
belong to some interval. In this case, one needs to restrict the sum (110) to the same interval,
and the result will not be an exact integer. But one can actually give an upper bound for the
deviation from the closest integer.
    Setting the last generalization aside, let us put the integrality theorem into a rigorous form.
(The reader may safely skip this formalism and proceed to the next subsection.)
                                                                                   L
Theorem C.1. Let U be a unitary operator acting in the Hilbert space H = ∞            j=−∞ Hj and
represented by a matrix whose entries Ujk are linear maps from Hk to Hj . Suppose that the
off-diagonal entries are Hilbert-Schmidt operators satisfying the condition
                                      kUjk kHS ⩽ c|j − k|−α                                   (118)
where c and α > 1 are some constants, and k · kHS is the Hilbert-Schmidt norm. Then the sum
in the expression for the flow,
                                   XX          †             †        
                           F (U) =       Tr(Ujk  Ujk ) − Tr(Ukj Ukj )                  (119)
                                    j⩾0 k<0

converges absolutely and has an integer value.

                                                 53
                              L                   L
Proof sketch. Let H− = j<0 Hj and H+ = j⩾0 Hj . An operator A is said to be quasi-
trace-class relative to the decomposition H = H− ⊕H+ if the matrix elements A++ and A−− are
trace class, whereas A+− and A−+ are Hilbert-Schmidt. By definition, Tr A = Tr A++ +Tr A−− .
An operator B is said to be quasi-bounded if B++ , B−− are bounded and B+− , B−+ are
Hilbert-Schmidt. Both types of operators form Banach spaces with respect to suitable norms;
quasi-trace-class operators form an ideal in the algebra of quasi-bounded operators.
    One can show that the operator Λ = U † ΠU − Π is quasi-trace-class. Also, the operators
P (L) = Π[−L,L] U † ΠUΠ[−L,L] are almost projectors, in the sense that limL→∞ (P (L)2 −P (L)) = 0
with respect to the quasi-trace norm. Hence P (L) can be approximated by a projector, which
has an integer trace.
    We omit the details and proceed to higher dimensions. Generally, our style will not be very
rigorous, but one can hopefully elaborate the results using the following definition.
Definition C.2. Let a positive integer d (the dimension) and a real number α > d be fixed.
A matrix (Ajk : j, k ∈ Zd ) with operator entries is called quasidiagonal if all its off-diagonal
entries are Hilbert-Schmidt, and there are some constants c and c′ such that
                       kAjj k ⩽ c,             kAjk kHS ⩽ c′ |j − k|−α       for j 6= k.               (120)
   Note that if A is unitary, then kAjj k ⩽ 1 automatically. Quasidiagonal matrices form a
Banach algebra with the norm
                               kAkqd = sup kAjj k + γ sup |j − k|α kAjk kHS ,                          (121)
                                          j                j6=k

where γ is a sufficiently large constant.

C.3     Chern number
C.3.1 General definition of ν(P ). Let P be an orthogonal projector represented by a
quasidiagonal matrix in two dimensions. (For simplicity, we assume that the matrix elements
Pjk are scalars, though they may be operators as well.) For each triple (j, k, l) we define a
“2-current”:13                                                   
                            hjkl = 12πi Pjk Pkl Plj − Pjl Plk Pkj .                     (122)
It is clear that hjkl is antisymmetric in all three indices. Since P is Hermitian, hjkl is a real
number. Moreover, since P 2 = P ,
                                             def
                                                 X
                                     (∂h)kl =       hjkl = 0.                              (123)
                                                       j

    Let us partition the plane into three sectors and define a quantity ν(P ), which will be shown
to generalize the notion of the Chern number:

                       B       A                                     def
                                                                           XXX
                                              ν(P ) = h(A, B, C) =                       hjkl .        (124)
                           C                                               j∈A k∈B l∈C


 13
P Another name of this object is “simplicial 2-chain”.            More exactly, the 2-chain is the formal sum
 j<k<l hjkl ∆jkl , where ∆jkl is a combinatorial simplex.


                                                      54
This sum converges absolutely. On the other hand, its value does not change if one reassigns any
site from one sector to another (due to Eq. (123)). Therefore ν(P ) is a topological invariant: it
is constant, provided that A, B, C are arranged in the counterclockwise order. We will see that
ν(P ) is actually an integer, and its value agrees with Eq. (54) in the translationally invariant
case.

C.3.2 Some properties and the translationally invariant case. Let us rewrite Eq. (124)
in an operator form using the relation A + B + C = 1, where the symbols A, B, C designate
the projectors on the corresponding sectors:
                                              
 ν(P ) = 12πi Tr(AP BP CP ) − Tr(AP CP BP )
                                                                                       
    = 4πi Tr AP BP CP + BP CP AP + CP AP BP − AP CP BP − CP BP AP − BP AP CP
                                                         def
       = 4πi Tr P AP BP − P BP AP = 4πi Tr P AP, P BP = ν(P, A, B).                 (125)
Note that the value of ν(P, A, B) will not change if we add arbitrary finite matrices to A and
B. Moreover, the commutator [P AP, P BP ] is nonzero only in the region where the supports
of A, B, and C = 1 − A − B touch each other, hence we can make arbitrary changes away
from the triple contact point. Thus the operators A, B, C do not have to be projectors or
even commute with each other; it is only important that they are supported by regions with
the particular topological configuration (possibly with some overlap along the boundaries and
triple overlap at the center).
    This freedom in the choice of A and B is very useful. As one application, we show that ν(P )
is additive. Let P1 and P2 be projectors onto orthogonal subspaces (i.e., P1 P2 = P2 P1 = 0) and
let P3 = 1 − P1 − P2 . We may replace A, B, and C = 1 − A − B with
                             3
                             X                      3
                                                    X                         3
                                                                              X
                      ′                         ′                        ′
                    A =            Pk APk ,   B =         Pk BPk ,     C =          Pk CPk ,
                             k=1                    k=1                       k=1

which differ from A, B, and C only at the boundaries of the corresponding regions. Then
                   (P1 + P2 )A′ (P1 + P2 )B ′ (P1 + P2 ) = P1 AP1 BP1 + P2 AP2 BP2 ,
                                                        
                ν P1 + P2 , A, B = ν P1 + P2 , A′ , B ′ = ν(P1 , A, B) + ν(P2 , A, B).
Thus
                          ν(P1 + P2 ) = ν(P1 ) + ν(P2 ),         ν(1 − P ) = −ν(P ).                     (126)
   Now, we calculate ν(P, A, B) for a different topological topological configuration. Let Π(x) =
Π(1) + Π(4) and Π(y) = Π(2) + Π(1) be the projectors onto the right and the upper half-plane,
respectively (see the picture below). Then
        y         ν(P, Π(x) , Π(y) )
    2   1
            x      = ν(P, Π(1) , Π(2) ) + ν(P, Π(1) , Π(1) ) + ν(P, Π(4) , Π(2) ) + ν(P, Π(4) , Π(1) )   (127)
    3   4
                   = ν(P ) + 0 + 0 + ν(P ) = 2ν(P ).
It follows that
                                                                     
                    (x)    (y)             (x)       (y)          (x) (y)
  ν(P ) = 2πi Tr P Π P, P Π P = 2πi Tr P [Π , P ], [Π , P ] + P [Π , Π ]P ,                              (128)

                                                      55
where the last term vanishes because Π(x) and Π(y) commute. Of course, Π(x) , Π(y) may be
replaced by any topologically equivalent pair of operators, i.e., we may deform or blur the
boundaries of the corresponding half-planes.
   In the translationally invariant case, the right-hand side of Eq. (128) can be calculated by
widening the fuzzy boundaries so that they turn into linear functions. Thus
                                                              
                               ν(P ) = 2πi tr P [X, P ], [Y, P ] ,                        (129)

where X and Y are the operators of x- and y-coordinate (resp.), and tr is the trace per unit
cell. Passing to the momentum representation and using a two-dimensional analogue of the
correspondence (116), we recover Eq. (54).

C.3.3 The integrality of ν(P ). We have seen ν(P ) has topological nature; let us show
that it is an integer. Let
                                                                             
  Q(x) = P Π(x) P, Q(y) = P Π(y) P, U (x) = exp 2πiQ(y) , U (y) = exp −2πiQ(x) . (130)

The operator U (x) coincides with the identity matrix away from the x-axis, and U (y) is equal
to the identity away from the y-axis. We may proceed in two different ways.
First proof. Let us regard the two-dimensional lattice as one-dimensional by identifying all
sites in each vertical row. Then U (x) satisfies the hypothesis of Theorem C.1, hence it has an
integer flow. But the flow can be expressed using Eq. (114) with Q = Q(x) . Thus
                                                  Z 2π                         
         (x)         −2πiQ(y) (x) 2πiQ(y)   (x)              d −iϕQ(y) (x) iϕQ(y) 
    F (U ) = Tr e            Q e          −Q      =     Tr       e      Q e         dϕ
                                                      0     dϕ                            (131)
                       (x) (y) 
             = 2πi Tr Q , Q        = ν(P ).

Note an analogy with the Laughlin argument: the integration over ϕ corresponds to the adia-
batic insertion of a magnetic flux quantum.
Second proof (sketch). Let us employ the notion of Fredholm determinant. It is a general-
ization of the determinant to infinite matrices that are close to the identity, specifically of the
form 1 + K, where K has a well-defined trace:14
                                                                                
                 def                                      1      2   1        2
     det(1 + K) = exp Tr ln(1 + K) = 1 + Tr K + − Tr K + (Tr K) + . . . .                     (132)
                                                           2          2
The exact meaning of this definition is as follows: we first obtain a formal expression as a power
series in K and then evaluate each term. (If K is a matrix of size n, then all terms of degree
higher than n vanish.) We claim that
                                                           
                                    (x) (y)     (x) −1   (y) −1
                             det U U         U         U        = 1.                          (133)
                                      
Indeed, the identity det ABA−1 B −1 = 1 is true at the formal power series level, assuming
that the cyclic property of the trace holds for any product of A − 1, A−1 − 1, B − 1, B −1 − 1
 14
      It is important that any matrix product that occurs in the problem has a trace satisfying the cyclic property.

                                                         56
containing at least one factor with A and at least one factor with B. On the other hand, one
can show that
                       (y)    (x)     (y)      (x)
                                                                             
              det eiϕy Q eiϕx Q e−iϕy Q e−iϕx Q       = exp ϕx ϕy Tr Q(x) , Q(y) .     (134)



C.4     Majorana numbers
In this section we study real skew-symmetric matrices satisfying the equation B 2 = −1. Re-
call that such a matrix defines the ground state |Ψi of a Majorana system with a quadratic
Hamiltonian (cf. Eqs. (26) and (27)). First, we consider finite or general infinite matrices (i.e.,
work in dimension zero), then proceed to quasidiagonal matrices in dimension one, and finally
to dimension two.

C.4.1 Dimension zero: fermionic parity and the Pfaffian. A few more words about
the Majorana system, then we will turn to matrices. Let us group the sites (or the corresponding
Majorana operators) into pairs (2k − 1, 2k) to form “full” fermionic modes with the occupation
number operators a†k ak = 12 (1 + ic2k−1 c2k ). Note that the operator −ic2k−1 c2k has eigenvalue 1 if
the mode is empty
             Q    and −1 if it is occupied. Thus the total fermionic parity is characterized by
the operator k (−ic2k−1 c2k ). The fermionic parity of the ground state is equal to the Pfaffian
of the matrix B:       Y
                         (−ic2k−1 c2k )|Ψi = (Pf B)|Ψi,           Pf B = ±1.                    (135)
                          k
   Let us recall some standard definitions. The Pfaffian of a skew-symmetric matrix is ex-
pressed as a sum over all partitions of the set {1, . . . , 2N} into pairs, or over all elements of the
permutation group S2N :
                                 1    X
                    Pf A = N               sgn(τ ) Aτ (1),τ (2) · · · Aτ (2N −1),τ (2N ) .       (136)
                              2 N! τ ∈S
                                              2N

For example,
                                                          
                                       0    a12  a13 a14
       0   a12                         −a12   0   a23 a24 
   Pf                  = a12 ,      Pf 
                                       −a13 −a23
                                                            = a12 a34 + a14 a23 − a13 a24 .
      −a12 0                                        0  a34 
                                        −a14 −a24 −a34 0
The Pfaffian satisfies the equations
                       (Pf A)2 = det A,            Pf(W AW T ) = Pf(A) det(W ).                  (137)
   We will also need a generalization of the Pfaffian to infinite matrices, which is called Fredholm
Pfaffian [75]. Let A and B be real skew-symmetric, B invertible, and A − B have a well-defined
trace. Then
                                                     
            def
                p                     1
  Pf(A, B) = det(1 + K) = exp           Tr ln(1 + K)
                                      2
                                                                                              (138)
                    1            1           1
             = 1 + Tr K + − Tr K 2 + (Tr K)2 + . . . ,               where K = AB −1 − 1.
                    2            4           8

                                                     57
This definition is understood as that of the Fredholm determinant: we first obtain a formal
expression as a power series in K and then evaluate each term. (For finite matrices of size 2N
we get Pf(A, B) = (Pf A)(Pf B)−1 ; note that the terms of degree higher than N vanish). The
Fredholm Pfaffian has the following properties:
                      Pf(B, B) = 1,         Pf(A, B) Pf(B, C) = Pf(A, C),                    (139)
        Pf(A, B)2 = det(AB −1 ),       Pf(W AW T , V BV T ) = Pf(A, B) det(V −1 W );         (140)
                           if A2 = B 2 = −1,       then Pf(A, B) = ±1.                       (141)
C.4.2 Dimension one: cutting obstruction and the relative Majorana number.
Now, consider a matrix that describes the ground state of Majorana fermions on an infinite
chain. From a formal point of view, it suffices to say that B = (Bjk : j, k ∈ Z) is quasidiagonal,
real skew-symmetric, and that B 2 = −1. Suppose that we cut the chain between sites η − 1
and η. Is it possible to find a new matrix B ′ that contains no cross elements (i.e., has the form
  ′      ′
B−−  ⊕ B++   ), satisfies the condition (B ′ )2 = −1, and coincides with B far away from the cut?
The following quantity represents an obstruction for the construction of such a matrix:
                                              
             Mη (B) = Pf V (η)BV (η), B = ±1,               where V (η) = 1 − 2Π[η,∞) .      (142)
                                                                                
Recall that Π[η,∞) denotes the projector onto sites η and higher; V (η)BV (η) jk = ±Bjk , where
the minus sign occurs when j and k lie on different sides of the cut.
    We claim that the conditions on B ′ cannot be met if Mη (B) = −1. Indeed,
                                                                          
                         Mγ (B) Mη (B)−1 = Pf V (γ)BV (γ), V (η)BV (η)
                                                                                            (143)
                                                        −1               γ−η
                                             = det V (η) V (γ) = (−1) .
The same is true for B ′ , hence the relative Majorana number,
                                             def
                                   M(B, B ′) = Mγ (B) Mγ (B ′ )                              (144)
does not depend on γ. However, Mγ (B ′ ) = Mγ (B) if |γ − η| is large enough (since B and B ′
agree far away from the cut), while Mη (B ′ ) = 1 (because B ′ = B−−′      ′
                                                                       ⊕ B++   ) and Mη (B) = −1
(by assumption). We have arrived at a contradiction.
    From the physical point of view, the impossibility to construct a suitable matrix B ′ indicates
the presence of unpaired Majorana modes on both sides of the cut. This situation may be
                          ′        ′
described by matrices B−−   and B++    having one zero eigenvalue.
    The cutting obstruction and the relative Majorana number can also be expressed as Fred-
holm determinants. To this end, consider the quasidiagonal matrix
                                               1  (x)           
                                                                           def
        W = V (0) exp(πX),        where X =       Π B + BΠ(x) , Π(x) = Π[0,∞) .               (145)
                                               2
Clearly, X is real skew-symmetric and commutes with B. Hence W is orthogonal, and W BW T =
V (0)BV (0). On the other hand, X is equal to B at +∞ and vanishes at −∞, therefore W is
equal to 1 at ±∞. One can actually show that W − 1 has a well-defined trace. It follows that
                                                         
                             M0 (B) = Pf W BW T , B = det W.                                  (146)
Similarly, one can define X ′ , W ′ as functions of B ′ . Thus
                                                                ′
                         M(B, B ′ ) = det W −1 W ′ = det e−πX eπX .                          (147)

                                                   58
C.4.3 Applications to two dimensions. Eq. (147) may be used as a more general defini-
tion of the relative Majorana number, which works even if Mη (B) and Mη (B ′ ) do not exist. For
example, let B be a quasidiagonal matrix in two dimensions and B ′ = (1 − 2Π(y) )B(1 − 2Π(y) ).
                    ′
In other words, Bjk   = ±Bjk , where the minus sign occurs when j and k lie on different sides
of the x-axis. If we regard the system as one-dimensional (collapsing it in the y direction),
the Majorana number M(B, B ′ ) is well-defined and can be expressed in terms of the projector
P = 21 (1 − iB). The calculation follows.
    First, we obtain an expression for the operator X:
                                                                 
                            X = i P Π(x) P − (1 − P )Π(x) (1 − P ) .
                                                
Then we use the relation 1 − 2Π(y) = exp ±iπΠ(y) :
                                        (y)      (y)
                                                                          
            M(B, B ′ ) = det e−πX e−iπΠ eπX eiπΠ        = exp iπ 2 Tr X, Π(y) .

Finally, we compute the trace of the commutator:
                                                                                    
         (y)            2           2      (y)                  (y)                     (y)
Tr X, Π        = Tr P + (1 − P ) X, Π             = Tr P X, Π P + (1 − P ) X, Π (1 − P )
                     h                   i      h                                             i
               = i Tr P Π(x) P, P Π(y) P − i Tr (1 − P )Π(x) (1 − P ), (1 − P )Π(y) (1 − P )
                  1                   1
             =      ν(P ) − ν(1 − P ) = ν(P ),
                 2π                    π
because ν(1 − P ) = −ν(P ). Thus

                                      M(B, B ′ ) = (−1)ν(P ) .                                (148)

    Equation (148) can be applied to the geometry shown in Fig. 15. In this case, B and B ′
correspond to two different Z2 -field configurations: the first is regarded as vortex-free and the
second has a vortex at the origin. The specific assumptions are as follows: (i) B and B ′ are
real skew-symmetric quasidiagonal matrices in two dimensions; (ii) B and B ′ coincide, except
       ′
that Bjk = −Bjk for those links which cross the ray r; (iii) B 2 = −1 (therefore (B ′ )2 = −1 far
away from the vortex). Note that Mη (B) and Mη (B ′ ) may be defined for a sufficiently large
loop η enclosing the vortex. Let |η| be the number of sites inside the loop. Then the absolute
                           def                              def
Majorana numbers M(B) = (−1)|η| Mη (B) and M(B ′ ) = (−1)|η| Mη (B ′ ) do not depend on η
and indicate the presence of unpaired Majorana modes in B and B ′ , respectively. However, an
unpaired mode cannot exist in B since B 2 = −1; therefore M(B, B ′ ) = M(B ′ ). We conclude
that
                                       M(B ′ ) = (−1)ν(P ) .                                 (149)


Appendix D:               Some remarks on the chiral central charge
This appendix is an attempt to understand the physical and mathematical meaning of the
chiral central charge beyond the CFT framework. Recall that chiral central charge is just the
coefficient c− in the edge energy current formula (57). This definition will be refined in Sec. D.1.

                                                59
It turns out that the edge energy current is a property of the bulk ground state. The edge current
is related to a bulk 2-current. Although the theory is in its embryonic stage, it looks like a
second-quantized version of the Chern number for quasidiagonal matrices (cf. Sec. C.3).
    In Sec. D.2 we discuss modular transformations of the partition function on a space-time
torus. In particular, the phase factor e−2πic− /24 appears in the description of the Dehn twist
along a time circle. However, other modular transformations are difficult to define because
space and time are not physically equivalent.

D.1       The edge energy current and a bulk 2-current
D.1.1 Energy current in the Hamiltonian formalism. Let us represent the Hamilto-
nian as a sum of local terms:        X
                                H=      Hj ,                              (150)
                                                 j

where Hj is a Hermitian operator acting only on spins in some neighborhood of the point j.
Note that the decomposition into local terms is not unique. We also assume that the ground
state |Ψi is separated from excited states by an energy gap; thus equal-time spin correlators
decay exponentially with distance [16]. We may slightly extend the notion of locality so that
Hj acts on all spins but                                   
                                    [Hj , σkα ] ⩽ u |j − k| ,                           (151)
where u is some function with fast decay at infinity (faster than any power). Then the equal-
time correlators also decay faster than any power, provided the spectrum is gapped.
   Microscopic energy current can be defined for any system with Hamiltonian (150) at finite
temperature. It is convenient to fix the temperature at T = 1 and vary the Hamiltonian instead.
The thermal average of an operator X is defined in the standard way:

                    hXi = Tr(ρX),       where ρ = Z −1 e−H ,     Z = Tr e−H .               (152)

   According to the Heisenberg equation,
                  dHj                X
                      = −i[Hj , H] =   fˆjk ,        where fˆjk = −i[Hj , Hk ].             (153)
                   dt                k


Thus the operator fˆjk characterizes the energy current from k to j. We denote its thermal
average by fjk :
                                                           def
                   fjk = f (Hj , Hk ),     where f (A, B) = −i[A, B] .               (154)
(Note that this definition depends on the decomposition of the Hamiltonian into local terms.)
Of course, the energy current is conserved:
                                           def
                                               X
                                    (∂f )k =     fjk = 0.                               (155)
                                                 j


Indeed,                                                            
                (∂f )k = f (H, Hk ) = Tr −iρ[H, Hk ] = Tr −i[ρ, H]Hk = 0,
since ρ and H commute.
                                               60
   Let us try to apply the general formula (154) to a specific geometry. Let H (∞) be the Hamil-
tonian of an infinite two-dimensional system with a ground state |Ψi and gapped excitations.
To simulate an edge, we introduce another Hamiltonian,

            y
                                                   (
                              X                                  0           if y(j) → +∞,
                   x     H=         Hj ,    Hj =           (∞)                                 (156)
                                j
                                                       βj Hj ,       βj → ∞ if y(j) → −∞,


where y(j) is the y-coordinate of the point j. Thus the lower part of the system is “bulk
material” characterized by the state |ΨihΨ|, whereas the upper part is “empty space” (actually,
a set of noninteracting spins in the maximally mixed state). By definition, the chiral central
charge is 12/π times the total energy current in the negative x-direction.

D.1.2 Representing the ground state by local constraints. At this point, we have
encountered a technical difficulty: the energy current does not necessarily vanish in the bulk.
The problem can be avoided if we describe the ground state by a set of local constraints. (A
local constraint is a local operator that annihilates the ground state.) Hamiltonians that are
explicitly written as sums of local constraints, e.g., the Rokhsar-Kivelson model [76, 19], have
provided a lot of insight into properties of quantum many-body systems.
                                                          P
Proposition D.1. Any gapped local Hamiltonian H = j Hj whose ground state |Ψi has zero
energy can be represented as a sum of Hermitian local operators H  e j such that H
                                                                                 e j |Ψi = 0.

Proof sketch. Without loss of generality we may assume that hΨ|Hj |Ψi = 0. (If not, change
Hj by a constant.) Let all excited states have energy greater or equal to ∆. Choose a smooth
function w(ε)
         b    such that

                w(−ε)
                b       b ∗,
                      = w(ε)               w(0)
                                           b    = 1,             w(ε)
                                                                 b = 0 for |ε| ⩾ ∆.
                                 R         dε
Its Fourier transform, w(t) = w(ε)  b e−εt 2π  decays faster than any power of t though more
              −γ|t|
slowly than e       (because w
                             b is smooth but not analytic). We set
                                       Z ∞
                                  e
                                  Hj =      eiHt Hj e−iHt w(t) dt.                      (157)
                                           −∞
                        P e               e
It is easy to check that j H  j = H and Hj |Ψi = 0. A locality condition of the form (151) can be
established using the bound of Lieb and Robinson [77] on correlation propagation (cf. [16]).
                                                                                          P
     For our purposes, we can actually use an arbitrary gapped Hamiltonian X = j Xj made
up of local constraints for the given state |Ψi. It turns out that the chiral central charge depends
only on the ground state. Indeed, one can interpolate between different sets of local constraints
for the same state. Consider the situation where the constrains are Xj in close proximity of
the edge, gradually changing to Xj′ deeper in the bulk. No energy current is associated with
the transition between X and X ′ .
     As an aside, we conjecture that there is a set of local constraints Yj such that the Hamiltonian
       P
Y = j Yj† Yj is gapped. Thus excitations can be efficiently detected locally, by coupling each

                                                 61
                                           P                               
Yj to an external indicator: Hdetector =        Yj ⊗ |1ih0| j + Yj† ⊗ |0ih1| j . A stronger version
                                                j
                                                                                     P
of this conjecture asserts that the original Hamiltonian H can be represented as j Yj† Yj , where
Yj are local constraints. This is true for the quadratic fermionic Hamiltonian (18), which needs
to be offset by its smallest eigenvalue (25) so that the ground  P stateenergy becomes zero. It
is easy to see that the matrix |iA| is symmetric and that j,k |iA| jk cj ck is equal to Tr |iA|
times the identity operator. Hence
             1 X                          X                               1            
      H =          iAjk + |iA| jk cj ck =         Djk cj ck ,    where D =       iA + |iA| ⩾ 0
             4 j,k                            j,k
                                                                             4
                                                                √
(meaning that D is positive semidefinite). The matrix D is quasidiagonal, provided A is
quasidiagonal and has a spectral gap around zero. Thus we can represent the Hamiltonian in
the desired form:
                            X                                    X√ 
                                  †
                      H=        Ym Ym ,        where Ym =              D    ck .               (158)
                                                                               mk
                              m                                       k

D.1.3 Bulk 2-current. In the disk geometry (i.e., when interaction is strong near the
origin and vanishes at infinity), the chiral central charge is 12/π times the energy current in
the counterclockwise direction. Let us divide the disk into three sectors, A, B, and C in the
counterclockwise Porder (see
                         P picture in Eq. (124), or in Eq. (160) below). In this setting, the
energy current is k∈B l∈A fkl .
    Let us try to represent the chiral central charge c− in a form that would explicitly depend
on the bulk Hamiltonian rather than the edge. To this end, we construct a 2-current h such
that                                                          X
                                                          def
                            f = ∂h,        where (∂h)kl =        hjkl .                    (159)
                                                                          j

(A 2-current is an antisymmetric function of three lattice sites that decays fast enough as the
distance between any two sites increases.) Then in the three-sector geometry we have:
                                                  !
                    XX            XX X                     XXX
                          fkl =               hjkl = −                 hjkl .
                     k∈B l∈A          k∈B l∈A       j                j∈A k∈B l∈C

Thus,

                          B       A                          12 X X X
                                            c− = −                    hjkl .                  (160)
                              C                              π j∈A
                                                                  k∈B l∈C

The last sum is dominated by a neighborhood of the triple contact point between A, B, and C.
    Unfortunately, there is no canonical expression for hjkl . Instead, we can define a canonical
object g which is a 2-current on the lattice and a 1-form on the space of local Hamiltonians. It
satisfies the condition
                                             ∂g = df.                                       (161)
A suitable 2-current h is obtained by integrating g over an arbitrary path H(β) : β ∈ [0, ∞)
in the space of spin Hamiltonians. Here we assume that H(β) is a sum of local terms Hj (β),
the corresponding thermal state has short-range correlators, H(0) = 0, and H(β) ≈ βH (∞) as
β → ∞. Thus we implicitly accept the following conjecture.

                                                        62
Conjecture D.2. The ground state of a gapped local Hamiltonian on a two-dimensional lattice
can be transformed into the maximally mixed state without a phase transition.
(In this formulation, β changes from ∞ to 0.) Note that usual symmetry-related phase tran-
sitions are not a problem because H(β) is not required to be symmetric. Rather, we should
worry about a transition from a topological phase to a non-topological one. However, in two
dimensions the long-range topological order in the ground state is destroyed at any finite tem-
perature. Indeed, all topological excitations are point-like and not confined, therefore they
have a finite density at any non-zero temperature. This argument does not apply to three-
dimensional systems, where string-like excitations are possible.
    Let us give an explicit formula for g. For any two operators A and B, we define the
Matsubara time-ordered average, as well as its “truncated” version:15
                                             
       A(τ )B(0) = Z −1 Tr e−(1−τ )H Ae−τ H B ,    where Z = Tr e−H , 0 ⩽ τ ⩽ 1;          (162)
           A(τ )B(0) = A(τ )B(0) − hAihBi.                                                                (163)
Next, we define a function of three operators:
                                           Z 1
                           µ(A, B, C) = i      A(τ ) [B, C](0) dτ.                                        (164)
                                                     0

Finally, we assume that the Hamiltonian H and the operators A, B, C depend on some pa-
rameters, so that we can differentiate them. Now we can define g:
          g(A, B, C) = µ(dA, B, C) + µ(dB, C, A) + µ(dC, A, B),              gjkl = g(Hj , Hk , Hl ).     (165)
      Let us verify Eq. (161). Note that µ(X, Y, H) = −i [X, Y ] because X(τ ) [Y, H](0) =
 d
dτ
      X(τ )Y (0) and [Y, H] = 0. We proceed as follows:
            ∂g(B, C) = g(H, B, C) = µ(dH, B, C) + µ(dB, C, H) + µ(dC, H, B)
                                                           
                     = −iZ −1 Tr de−H [B, C] − ihdHih[B, C]i − ih[dB, C]i + ih[dC, B]i
                                            
                     = d −iZ −1 Tr e−H [B, C]   = df (B, C).

D.2          Modular transformations beyond CFT
The modular invariance [62] is usually formulated in the CFT framework. In this section, we
demonstrate some modular properties of the partition function of edge excitations, not assuming
conformal, rotational, or any other symmetry. First, let us generalize the transformation of the
vacuum character16 under the Dehn twist:
                                      χ1 (w + 1) = e−2πic− /24 χ1 (w),                                    (166)
     15
      This notation is reminiscent of the formula A(τ ) = eτ H Ae−τ H , but the latter may be problematic to use
because eτ H ≈ exp(τ βH (∞) ) diverges as β → ∞. Thus the expression A(τ )B(0) should be viewed as a whole.
   16
      Some care should be taken to make a proper connection between the physics of edge modes and the the
CFT formalism. If all edge modes have the same chirality, characters correspond to representations of some
chiral algebra (as is usual in CFT). In general, the vacuum character χ1 is defined as a sum over all fields with
trivial monodromy whereas χa includes all fields that occur in the two-dimensional theory when an anyon of
type a emerges on the surface (see Fig. 9b on page 29).

                                                         63
where w is the modulus of the torus and the subscript 1 refers to the vacuum sector.
    In fact, the derivation of Eq. (166) does not require much more than the knowledge of the
energy-momentum tensor, or just its τ x-component, which is exactly the energy current I.
(We use imaginary time, τ = it.) In the thermodinamic limit,        the coordinate transformation17
                                                                 R dξ
(x, τ ) → (x, τ + ξ(x)) induces the action change δS = iI dx dx dτ . If the imaginary time
                                                                                       π
is cyclic, then twisting it by a full circle results in the action change δS = i 12      c− and the
                                               −S       −2πic− /24
multiplication of the partition function by e      = e             . We now describe a particular
setting in which this result is applicable.
    Let us consider the partition function Z = Tr e−H/T of a spin system on a disk. As is usual,
we think of the evolution over the time period 1/T , making the edge into a torus and the disk
itself into the three-dimensional manifold M = D 2 × S 1 . Let us suppose that the temperature
T is much smaller than the energy gap in the bulk, so that Z is mostly determined by edge
excitations. In fact, the partition function depends on full detail of the edge Hamiltonian as
well as some conditions in the bulk. For example, we may place an anyon of type a somewhere
in the disk, which slightly changes the edge excitation spectrum. In other words, we insert a
particle worldline ℓ into the manifold M, or act by the time-like Wilson loop operator Wa (ℓ).
Thus a partition function Za is defined. If all edge modes propagate with the same velocity v
and can be described by a CFT, then Za = χa (−1/w), where w = iLT /v. In the limit w → ∞,
                                              X
                          Za = χa (−1/w) =        Sab χb (w) ≈ Sa1 χ1 (w),                    (167)
                                                       b

because all characters χb (w) for b 6= 1 are exponentially smaller than the vacuum character
χ1 (w).
    The following argument does not depend on CFT. As already mentioned, twisting the torus
by ξ along a time circle leads to the the action change by iIξ/T , or the multiplication of the
partition function by e−iIξ/T . (The sign in the exponent depends on the direction of the twist;
we choose it to be consistent with the CFT formula.) For the full twist, ξ = 1/T , we get this
equation:
                                        Za′ ≈ e−2πic− /24 Za .                            (168)
Note that the finite-size quantization of edge modes might affect the energy current. We
therefore assume that the disk circumference L is much larger than the edge correlation length
ledge ∼ v/T , where v is the maximum group velocity of any excitation in the system.18 Small
corrections proportional to exp(−L/ledge ) are expected. Thus, Eq. (168) and its estimated
precision are in perfect agreement with the CFT formulas (166) and (167).
    With some more work, one can also derive an analogue of this CFT result:

                                      χb (w + 1) = e−2πic− /24 θb χb (w),                                   (169)
  17
      For lattice models, one should consider the transformation (j, τ ) → (j, τ + ξj ). It should be possible to
give an exact quantum-mechanical interpretation of such a reparametrization by coupling the discrete derivative
ηjk = ξj − ξk to the energy current operator fˆjk = −i[Hj , Hk ], where Hj , Hk are local terms in the Hamiltonian.
Such coupling is unambiguously defined only in the first order in ηjk , but that does not affect the thermodynamic
limit.
   18
      A rigorous and completely general upper bound for the group velocity was obtained by Lieb and Robin-
son [77]. It is consistent with the rough estimate v . rJ, where J is the inter-spin interaction strength and r
is its range.


                                                        64
where θb is the topological spin of b. In the non-conformal setting, the role of the characters
χb (w) is played by linear combinations of the partition functions:
                                              X
                                        Zeb =     sbā Za ,                               (170)
                                                 a

where sab are the entries of a topological S-matrix defined in terms of anyonic braiding, see
Eq. (223) on page 84. (We distinguish it form the modular matrix S, though they actually
coincide when the latter is defined.) A calculation based on the insertion of a space-like Wilson
         e shows that
loop Wb (ℓ)
                                      Zeb′ ≈ e−2πic− /24 θb Zeb .                           (171)
This equation is indeed similar to (169) with one important difference: unlike χa (w) and
χa (−1/w), the numbers Zea and Za are not obtained by evaluating the same function. An-
other problem is that the Dehn twist can only be performed along a time circle. It is therefore
not clear whether the full modular invariance can be established without conformal symmetry,
or at least a 90◦ -rotation symmetry of the space-time manifold.


Appendix E:               Algebraic theory of anyons
This appendix is an attempt to present an existing but difficult and somewhat obscure the-
ory in an accessible form, especially for the reader without extensive field theory knowledge.
(But we do assume some mathematical background and the willingness to follow abstract ar-
guments.) The presently available resources may be divided into three categories: the original
field-theoretic papers where the relevant mathematical structure was discovered [4, 5], local
field theory theory papers [6, 7] (see Haag’s book [78] for a general reference on this subject),
and purely mathematical expositions [68, 79, 80]. Unfortunately, all these texts have different
focus and/or are difficult to read. A nice elementary introduction can be found in Preskill’s
lecture notes on quantum computation [81], but more detail is needed for our purposes.
    The theory described below is applicable to two-dimensional many-body systems with short-
range interactions and an energy gap. Using some intuition about local excitations in such
systems, we characterize the properties of anyons by a set of axioms and derive some corollaries.
This approach is somewhat similar to what has been done rigorously in local field theory.
However, we avoid many difficulties by keeping the discussion at the physical level until all
essential properties are cast into a finite algebraic form, at which point we enter the realm of
mathematics.
    More specifically, we claim that finite-energy excitations are classified by superselection sec-
tors: each sector consists of states that can be transformed one to another by local operations.
(We do not care about rigorous definition here.) It is assumed that the full classification can
be established by considering a small neighborhood of an arbitrary point (of size compared to
the correlation length). Another assumption is that local excitations can be moved from one
place to another by applying an operator along an arbitrary path. Note that the quasiparticle
transport need not be adiabatic, nor we require translational symmetry. Topological proper-
ties, such as braiding rules, have invariant meaning independent of possible disorder, cf. Fig. 10



                                                65
                                                a             a          b        a       b
                                        a
                              a             =                                 =
                        a
                                                a                    c                c
                                   a)                                        b)
                                    Figure 16: Some “obvious” identities.

on page 34. Using some additional arguments, we will arrive at a theory that may be called
unitary braided fusion category (UBFC) (= unitary ribbon category) in abstract language.19
    With this approach, we get a weaker set of axioms compared to an analogous algebraic
structure in conformal field theory. Therefore some “obvious” properties require a proof. (A
similar situation occurs in local field theory, but our exposition is different in some details and
hopefully simpler.) For nonrelativistic quantum-mechanical models, the space and time are
not equivalent even if we use the imaginary time formalism. Thus the notion of an antiparticle
being a particle propagating back in time must be applied with caution. The identity in Fig. 16a
illustrates a standard use of this notion. (Shown in the figure are space-time diagrams; time
goes up.) On the left-hand side of the identity a particle a annihilates with its antiparticle ā that
was created as part of an āa pair. If space and time were related by a rotational symmetry, then
the zigzag on the particle worldline could simply be removed. In our formalism, this equation is
satisfied by a suitable choice of normalization factors for the creation and annihilation operators
of particle-antiparticle pairs. However, the relation in Fig. 16b is a nontrivial theorem; it follows
from the positivity of Hermitian inner product, see Section E.2. (In the categorical language,
this result reads: “Any unitary fusion category admits a pivotal structure”.)
    Having formulated fusion and braiding axioms, we will touch upon another question: What
UBFCs can be realized by a Hamiltonian with given symmetry properties? The simplest case
is where there is no built-in symmetry or associated conservation laws. That is, we assume that
the system consists of spins (or other bosonic degrees of freedom) and the Hamiltonian is in
generic position. (Fermions are excluded because their number is always conserved modulo 2.)
Thus, any effective conservation law for quasiparticles must have topological nature. In Sec. E.5
we formulate this condition as a certain nondegeneracy property of the braiding rules. Theories
satisfying this axiom are called unitary modular categories (UMC).20
    Unfortunately, UMC does not capture one important robust characteristic of the physical
system, namely the chiral central charge c− . However, there is a beautiful relation [7, 61] that
fixes c− mod 8:                                                       qP
                            X
                         −1      2       2πic− /8                            2
                      D         da θa = e         ,    where D =          a da ,                (172)
                               a

  19
      Note for experts (the general reader shouldn’t worry about this): a fusion category is a k-linear semisim-
ple rigid tensor category with finite-dimensional morphism spaces and finitely many simple objects such that
End(1) = k, see [30]. We take k = C. A unitary fusion category is automatically pivotal, spherical, and
nondegenerate. In the presence of braiding, these properties imply the existence of a ribbon twist.
   20
      The term “modular” refers to the possibility to define a Hilbert space associated with a torus, on which the
modular group acts. More generally, one can construct a so-called modular functor and a topological quantum
field theory [67, 68, 79] (but we do not cover these topics).


                                                       66
da is the quantum dimension of the superselection sector a (see Sec. E.2) and θa is the topological
spin (see Sec. E.3). The left-hand side of Eq. (172) is denoted by Θ; its algebraic meaning will
be explained in Sec. E.5. Roughly, Θ = S −1 T ST ST , where S is a so-called topological S-matrix
and T is the diagonal matrix with entries θa . We will see that Θ is a root of unity, hence
Eq. (172) implies that c− is rational.
    The standard proof of Eq. (172) is based on the assumption that the system admits con-
formally invariant edge modes under suitable boundary conditions. Then one can employ the
modular invariance of the partition function on a space-time torus, which is established in the
CFT framework [62]. It is not known whether the conformality hypothesis is true in general.
One may, however, hope to find a proof that would not depend on conformal symmetry. In
Sec. D.2 we made partial progress toward this goal. Specifically, we showed that the matrix
T = e−2πic− /24 T corresponds to the Dehn twist along a time circle. While S can also be re-
garded as a modular transformation in a suitable mathematical theory, it is not clear whether
that theory is applicable in the same context as the expression for T .
    In the remaining part of the appendix we do not discuss the chiral central charge. Our
primary goal is to define a unitary braided fusion category (UBFC) and its special case, unitary
modular category (UMC). The definition is rather long, so we break it into several parts. Each
part contains some physical motivation, formal axioms in terms of basic data and equations,
as well as some corollaries. Note that our formulation of the axioms does not involve the
mathematical notion of category, so we call the corresponding objects “theories” (e.g., “fusion
theory” instead of “fusion category”). Only later do we introduce the powerful but heavy
language of categories and functors (also known as “abstract nonsense”). It is surely overkill
for most of the problems considered in this paper, but the concept of tensor functor may
actually be useful in the study of phase transitions in anyonic systems, e.g., Bose-condensation
of spinless particle and weak symmetry breaking. (The last topic is considered in Appendix F.)

E.1     Fusion theory
In this section we consider anyons on a line (though the physical system is two-dimensional).
The motivation for the definitions has been provided in Sec. 8.4 (esp. in 8.4.2). Each particle is
characterized by a superselection sector label (describing its “anyonic charge”). The position
and local degrees of freedom may be ignored, but the order of particles is important. The main
element of the the fusion theory is the space Vcab — the state space of particles a and b restricted
to have total anyonic charge c. More exactly, vectors in this space correspond to different ways
of splitting c into a and b, or equivalence classes of local operators that effect the splitting.

E.1.1 Splitting and fusion operators. While Vcab may be called “splitting space”, the
corresponding fusion space is denoted by Vabc . If ψ ∈ Vcab is a splitting operator, then ψ † ∈ Vabc
is a fusion operator:
                                       a       b                          c
                                                                                  y
                          splitting:               ,        fusion:                   ,       (173)
                                           c                          a       b

where ψ and ψ † label the corresponding vertices. One may also use Dirac’s notation, i.e., write
|ψi instead of ψ and hψ| instead of ψ † . By definition, the Hermitian inner product corresponds


                                                       67
to the operator multiplication. Specifically, if ξ, η ∈ Vcab , then

                                     c                        c
                                         y
                               a         b    = hη|ξi             ,           i.e.,                     η † ξ = hη|ξi idc .                (174)
                                         
                                     c                        c

    Similarly, one can define splitting and fusion of multiple particles. The most general process
is one transforming particles b1 , . . . , bm into a1 , . . . , ak . It can be performed in two steps: first,
fusing all the particles into one, and then splitting it as required. Therefore
                                                 M
                                  Vba11...b
                                        ...ak
                                           m
                                              =      Vca1 ...ak ⊗ Vbc1 ...bm .                        (175)
                                                                      c

For example, the identity operator acting on particles a and b can be decomposed as follows:

                                                          a       b                         a           b

                                                                           XX                       j
                                                                      =                         c           ,                              (176)
                                                                                                    j
                                                                             c      j

                                                          a       b                         a           b


where j stands for both ψj and ψj† — basis vectors in Vcab and Vabc , respectively.
   The description of splitting and fusion will be complete when we understand relations be-
tween different spaces Vca1 ...ak . That is the topic of the following subsection.

E.1.2 Basic data and equations. The basic data include a set of superselection sectors,
fusion rules, and associativity relations. The latter satisfy so-called pentagon and triangle
equations. An additional condition (requiring the nondegeneracy of certain operators) will be
formulated in Sec. E.2.

Superselection sectors (also called “particle types”, or “labels”): They form a finite set M.

Fusion rules: For any combination of a, b, c ∈ M there is a fixed finite-dimensional Hilbert
space Vcab . The numbers Nab
                           c
                             = dim Vabc = dim Vcab are called fusion multiplicities. The choice
of a special element 1 ∈ M (the vacuum sector ) is also considered part of the fusion rules.

Associativity relations: For each a, b, c, d ∈ M there is a canonical unitary isomorphism
between two Hilbert spaces:

             a       b   c               a    b       c
                             Fuabc                                                  M                                M
                 e           −−→                  f                       Fuabc :               Veab ⊗ Vuec →              Vuaf ⊗ Vfbc .   (177)
                                                                                        e                              f
                     u                        u

Note that both spaces in question are simply different representation of the same physical space
Vuabc — that of the particles a, b, and c restricted to have total anyonic charge u. Therefore one
may regard the isomorphism Fuabc as equality. This view is formally justified by the pentagon

                                                                            68
                                                 x y z w

                                                                                                                                           F
                                                  p        t
                        F pzw
                          u                                                   F xyt
                                                                                u                                                       (inner)
x y z w                                                                                            x y z w
                                                      u
 p                                                                                                            t
  q                                                                                                       s                 F (outer)             F (outer)
               F xyz
                 q                                                                     F yzw
      u                                                                                  s            u
                       x y z w                                          x y z w
                                                                                                                                           F
                            r                     F xrw
                                                    u
                                                                              r
                        q                                                         s                                                     (inner)

                            u                                                 u
                                                      a)                                                                                   b)

Figure 17: The pentagon equation (a) and a “quadrilateral identity” (b). (The latter is satisfied
automatically.)

equation and MacLane’s coherence theorem, which will be formulated
                                                                 P e u later.  P Atu a fcruder,
combinatorial level associativity may be expressed as follows: e Nab    Nec = f Naf    Nbc .
    From the physical perspective, splitting off (or fusing with) the vacuum sector is trivial. In
any splitting diagram all lines labeled by 1 may be simply erased. To guarantee the consistency
of this procedure, we require that the spaces Vaa1 and Va1a are not only one-dimensional, but
canonically isomorphic to C. In other words, these spaces are endowed with fixed unit vectors
|αa i ∈ Vaa1 and |βa i ∈ Va1a . The canonical isomorphisms are given by the formulas

                        αa : C → Vaa1 :                        z 7→ z|αa i,                    βa : C → Va1a :             z 7→ z|βa i,             (178)

where z ∈ C. These isomorphisms must satisfy so-called triangle equations (see below).

Pentagon equation: The graphic representation of this axiom is shown in Fig. 17a. Its
exact meaning is this: for any x, y, z, w, u ∈ M the following diagram commutes:
                                                                 L       xy   pt   zw
                                                                   p,t Vp ⊗ Vu ⊗ Vt
                                           Fupzwgggggg
                                                      g3                                            WWWWW xyt
                                                                                                         WWFWuWW
                                          g g gg                                                                WWWWW
          L                          ggggg                                                                         L W+
                    xy   pz   qw                                                                                            xs   yt   zw
              p,q Vp ⊗ Vq ⊗ Vu                                                                                        s,t Vu ⊗ Vs ⊗ Vt              (179)
                                @@                                                                                             >
                                  @@                                                                                        ~~~
                                    @@ F xyz                                                                               ~
                                      @@ q                                                                        Fsyzw ~~
                                        @@                                                                              ~~
                                          @@                                                                          ~~
                                            @@                                                                     ~~~
                                 L         xr   yz   qw                       Fuxrw            L     xs   yz   rw
                                                                                                                  ~
                                     q,r Vq ⊗ Vr ⊗ Vu                                          r,s Vu ⊗ Vr ⊗ Vs
                                                                                           /


Arrow labels are abbreviated:
                      P xyz      for example, the arrow on the left (labeled by Fqxyz ) actually
designates the map q Fq ⊗ idVuqw , where idVuqw is the unit operator on Vuqw .
    According to MacLane’s coherence theorem [82], any sequence of F -moves between two
given trees results in the same isomorphism between the corresponding spaces: the equality of
all such isomorphisms follows from the pentagon equation. (Actually, the theorem is a bit more
general and also includes α- and β-moves, but we ignore them for the moment.) This result

                                                                                      69
                                                             1612                                                                  X X
                                1414
                                                                                           x 1 x 2 . . . . . x n−1      xj =                   µuv ,
                                                                                                                                   u∈Lj v∈Rj
                                                        1621
                                                                                                                     where µuv are fixed pos-
                                                                                                                     itive numbers associated
 1 234
                                                                                                                     with pairs of leaves (we
                                                      3214
                                                                                                                     have used µuv = 1).

                2 134                                                                             4312
                                         3124                                     4 21 3
                                                                                                                                    j−th interval

                                                                     4 123
                                                                                                                              Lj         Rj

                                                                                                    4321
1 261



                        2 161
                                                                    4141




                                                 a)                                                                                 b)

Figure 18: The graph of F -moves between binary planar trees with n = 5 leaves (a) and the
procedure used to assign coordinates x1 , . . . , xn−1 to each tree (b).

may be regarded as a combinatorial statement. Indeed, let us consider the graph Γn whose
vertices are binary planar trees with n leaves and whose edges correspond to F -moves. (The
graph Γ5 is shown in Fig. 18a.) Then the theorem says that any cycle in the graph can be filled
with pentagons and quadrilaterals. The latter correspond to the obvious fact that independent
F -moves commute; such moves can be nested as in Fig. 17b or occur in disjoint branches.
MacLane actually shows that any two directed paths between the same pair of vertices can be
transformed one to the other using the pentagon and quadrilateral equations; the proof is by
induction on a suitable parameter.
    Let us also mention a beautiful geometric proof of the coherence theorem: the graph Γn
together with the set of 2-cells (i.e., the pentagons and quadrilaterals) can be realized by the
vertices, edges, and 2-faces of some convex polytope Kn of dimension n − 2. This polytope
appeared in the work of Stasheff [83] and now bears his name; it is also called associahedron.
More exactly, this term refers to a certain combinatorial type of a polytope while its exact
shape may vary. The faces of Kn in all dimensions are associated with general (not necessarily
binary) planar trees. In particular, the edges correspond to trees with one degree-3 vertex, the
quadrilaterals correspond to trees with two degree-3 vertices, and the pentagons correspond to
trees with one degree-4 vertex. Described in Fig. 18b is a concrete geometric realization of Kn
(cf. Ref. [84]). It is fairly easy to show that the convex hull of the points (x1 , . . . , xn−1 ) ∈ Rn−1
obtained this way is characterized by one equation and n(n−1) 2
                                                                   − 1 inequalities:
        n−1
        X                              l−1
                                       X                                                                                           X
                                                                                                                        def
               xj = η1n ,                    xj ⩾ ηkl        (1 ⩽ k < l ⩽ n),                        where ηkl =                         µuv .      (180)
         j=1                           j=k                                                                                    k⩽u<v⩽l




                                                                             70
                    x        w                                                x        w                                                x        w




               αx                 βw                                βx                        βu                               αu                    αw
                        u                                                         u                                                         u



   x       1 w                     x 1 w                1       x w                           1 x w                x       w 1                       x w 1
                    F x1w
                      u                                                       F 1xw
                                                                                u                                                       F xw1
                                                                                                                                          u
       x                                    w               x                                          u               u                                      w

           u                            u                       u                                  u                       u                              u
                        a)                                                        b)                                                        c)

               Figure 19: The fundamental triangle equation (a) and its corollaries (b and c).

Triangle equations: The three equations in Fig. 19 guarantee that adding or removing
trivial lines commutes with F -moves. Let us write the first equation in a more conventional
form:
                       u ?       V xw                                                                       
                        ??
                             ??                                                            Fux1w |αx i ⊗ |ψi = |ψi ⊗ |βw i
            αx              ??βw     commutes,                         i.e.                                                                            (181)
                             ??
                                   ???                                                     for any |ψi ∈ Vuxw .
                   F x1w            
                       u
   V x1 ⊗ V xw
           x        u
                               / V xw ⊗ V 1w
                                                u   w


Lemma E.1.                   α1 = β1 .
Proof. Let x = u and w = 1. Then first and the third triangle equations coincide, except that
the right arrow is β1 in Fig. 19a and α1 in Fig. 19c. But the right arrow is the composition of
the other two, therefore it is the same in both cases.
Lemma E.2 (cf. [80], Lemma XI.2.2). The first triangle equation (together with the pentagon
and quadrilaterals) implies the second and the third.
The statement of the lemma refers to formal tree calculus. Moves between trees are bidirectional
(therefore we may represent them by lines rather then arrows). The quadrilaterals express the
commutativity of disjoint F -, α-, and β-moves.
Proof. Let us prove the equation in Fig. 19b.

                                                                                                           β                        β
    First, we join an additional trivial branch to
the trunk of each tree and show that the result-
                                                                                                               F
ing equation is equivalent to the original one. In
the diagram on the right, the old and the new                                                                              β
equation constitute the top and the bottom of a                                                        β                                     β
triangular prism, respectively. The sides of the
prism are commutative quadrilateral, therefore                                                             β                        β

the top triangle commutes if and only if the bot-
tom one does.                                                                                                      F



                                                                         71
    We now consider the bottom of the prism,                              1                                2
                                                                                          F
which may be identified with triangle 4-7-5 in
the new diagram. In this part of the argument
                                                                              α                                α           F
it is not important that the leftmost branch of
each tree is trivial, so we represent it by a solid
                                                                                                       F                       β
line. The outline of the diagram corresponds                          F
to the pentagon equation. Triangles 3-1-6 and                                         3                                4           5
4-2-5 are instances of the equation in Fig. 19a,                                β                                  β
which is true by hypothesis. The quadrilater-                                                                              F
als 1-2-4-3 and 6-3-4-7 also commute. Thus the
required triangle 4-7-5 commutes as well.                                              F
                                                                          6                                7
   The equation in Fig. 19c is proved analogously.

E.1.3 Examples. Several concrete theories have been presented in the main text, see tables
on pages 30, 41, 42. Let us now describe some general constructions leading to infinite series
of examples.

   1. Let the label set M be a finite group and the fusion rules correspond to the group
      multiplication. That is, the space Vzx,y is one-dimensional (with a basis vector ψzx,y )
      if z = xy, otherwise Vzx,y = 0. The associativity relations are trivial. Note that if the
      group M is non-Abelian, this fusion theory does not admit braiding.

   2. The associativity constraints in the above example can be deformed as follows:

                                               x        y   z                     x   y        z
                                       x,y,z
                                      Fxyz         xy           = f (x, y, z)             yz       ,                               (182)
                                                    xyz                               xyz


      where the vertices of the trees correspond to basis vectors and f (x, y, z) are some phase
      factors. In this case the pentagon equation reads:

                         f (xy, z, w) f (x, y, zw) = f (x, y, z) f (x, yz, w) f (y, z, w).                                         (183)

      This is a cocycle equation, i.e., f is a 3-cocycle on M with values in U(1). One can show
      that the triangle equations do not put any additional restriction on f but rather define
      α and β:

        αx = ζ f (x, 1, 1)−1ψxx,1 ,     βw = ζ f (1, 1, w)ψw1,w ,                     (ζ is an arbitrary phase). (184)
                        x,y           x,y
      The basis change ψxy  → u(x, y)ψxy  will result in a new cocycle g such that

                       f (x, y, z)−1 g(x, y, z) = u(x, y) u(x, yz)−1 u(xy, z) u(y, z)−1.                                           (185)

      The right-hand side of this equation is the coboundary of the 2-cochain u, i.e., g and f
      belong to the same cohomology class fe. Thus, the associativity relations are classified by
      H 3 (M, U(1)).

                                                                72
     For a concrete example, let M = Z2 = {1, a}. It is known that H 3 (Z2 , U(1)) = Z2 , i.e.,
     Eq. (183) has one trivial and one nontrivial solution. The nontrivial solution is given by
     f (a, a, a) = −1, the other seven values being equal to 1. This particular fusion theory
     admits two braidings: the counterclockwise exchange of two a-particles is characterized
     by either +i or −i. Such particles are called semions. Recall that Case 2 in the table on
     page 41 represents two independent species of semions.
  3. Let M be the set of irreducible representations of a finite group G and let Vcab =
     HomC[G] (c, a ⊗ b). In other words, elements of Vcab are intertwiners between c and a ⊗ b,
     i.e., linear maps that commute with the group action. The associativity relations are
     given by 6j-symbols. This theory admits trivial braiding.
  4. Examples 3 and 1 (with M = G) can be combined in what is called representation theory
     of Drinfeld’s quantum double [85, 80]. Models with anyons described by this theory
     were proposed in [86] (gauge-symmetric Lagrangian) and in [24] (lattice Hamiltonian not
     constrained by an external symmetry). This construction can be deformed by an arbitrary
     cohomology class fe ∈ H 3 (G, U(1)), see Refs. [87, 88].
  5. A very interesting set of fusion theories is based on a Temperley-Lieb category, see e.g.
     Chapter XII in book [68]. These theories are also known as “representations of quantum
     SU(2)”.

E.1.4 Calculations with planar graphs. The rules we have described allow us to work
not only with trees but with arbitrary oriented planar graphs. In particular, loops can be
removed using Eq. (174). If we encounter a subgraph like shown in Eq. (174) but with different
labels at the top and at the bottom (say, c′ and c′′ ), then its value is zero. Let us illustrate
that by a concrete example, using the fusion theory from Table 1 on page 30 for κ = +1:
      σ   σ           ε           σ   σ       ε               σ   σ           ε                  σ   σ       ε

                                                                                                                                  σ   σ       ε

                  σ                       σ                               σ           σ                  σ           σ
                                                  σ      1                                  1                               1
              ε           σ   =           ε           = √                         1
                                                                                          −√                     ε       = −√                 σ   .
                                                          2                                  2                                2
          σ                                   σ                               σ                              σ
                                                                                                                                          1
                  1                       1                               1                              1
                                                              |   {z                  }
                                                                      0

   In general, we consider planar graphs that satisfy the following conditions.
  1. Vertices are associated with fusion/splitting spaces Vlu1 ,...,l
                                                               1 ,...,us
                                                                     r
                                                                         ; the indices are represented
     by prongs. There may also be external labels (terminals) at the bottom and the top of
     the graph. Bottom terminals and upper indices are called sources, lower indices and top
     terminals are called targets.
  2. Each edge connects a source to an identically labeled target. (In pictures we use a single
     label for the whole edge.)
  3. The edges are transversal to the horizontal direction and oriented upwards. (We do not
     show the orientation in drawing because it is obvious.)

                                                                          73
    To each vertex we also assign an element of the corresponding space Vl1u,...,l     1 ,...,us
                                                                                             r
                                                                                                 . Using asso-
ciativity relations and Eqs. (174), (176), we can compute the value of the graph, X ∈ Vba11,...,b        ,...,ak
                                                                                                              m
                                                                                                                 ,
where a1 , . . . , ak and b1 , . . . , bm are the external labels. Note that we may freely add or remove
edges labeled with 1, thanks to the triangle equations.
    A general calculation strategy is based on the idea that X can be represented by a set of
maps Xc : Vcb1 ,...,bm → Vca1 ,...,ak for each label c; this representation is closely related to the
decomposition of identity (176). Thus we apply Eq. (176) first, and then start shrinking and
removing loops as illustrated above. For example:
                                σ           σ           σ           σ           σ           σ           σ           σ

                σ                                                                                                                   σ       σ       σ       σ
                        σ           ε                       ε
                                                                                    ε           σ           ε           σ
                    ε                       σ                       σ
                            =   σ               + σ                         =               σ
                                                                                                    −               σ
                                                                                                                            =           1       −       ε       .
                                        1                       ε                       1                       ε
                σ       σ                                                                                                           σ       σ       σ       σ
                                σ           σ           σ           σ           σ           σ           σ           σ


   We will see that for theories with particle-antiparticle duality, condition 3 can be dispensed
with. The formalism will be revised so that edges can bend, changing their direction from
upward to downward and back, and vertices can rotate by 360◦ as in Fig. 16b.

E.2      Particle-antiparticle duality
In this section we complement the fusion theory by the following condition.
Duality axiom. For each label a there is some label ā and vectors |ξi ∈ V1aā , |ηi ∈ V1āa
such that
                               αa ⊗ η Faaāa ξ ⊗ βa 6= 0.
Note that the matrix element in question corresponds to a physical process in which the ā-
particle from an aā-pair annihilates with a different copy of a:

                                                y
                                                a           y                                                                  a
                                                    1

                                            a       a           a           =   αa ⊗ η Faaāa ξ ⊗ βa                                .                               (186)
                                                        1
                                                                   a                                                           a


(The dotted lines and the associated labels, i.e., 1, αa , βa may be ignored.)
    Let hαa ⊗ η|Faaāa |ξ ⊗ βa i = u, assuming that |ξi and |ηi are unit vectors. We will see that
the spaces V1aā and V1āa are one-dimensional, therefore |u| is uniquely defined. The number
da = |u|−1, called quantum dimension, plays an important role in the theory. In particular,
da = 1 for Abelian particles (i.e., such that a × ā = 1), otherwise da > 1. If ā = a, then we may
set |ξi = |ηi so that u itself has an invariant meaning. Specifically,
                                                                        a                               a
                                                                                              κa
                                                                            a               =               ,                                                       (187)
                                                                                              da
                                                                                    a                   a


                                                                                        74
where κa is a uniquely defined phase, which is actually equal to ±1 (see below). This number
is called Frobenius-Schur indicator ; in the present context it was introduced by Fredenhagen,
Rehren, and Schroer [89].

E.2.1 Physical motivation for the duality axiom. The existence of antiparticles follows
from a locality principle mentioned at the beginning of this appendix: a quasiparticle can be
moved from one place to another by applying an operator that acts on spins along a path
connecting the given points. (We are still considering anyons on a line, therefore the path is
unique.) The action on different spins can be performed at once or in any particular order. For
example, to move a particle from point 3 to point 1 on its left, it may be natural to move it
first to some middle point 2, and then to the final destination. But it is also possible to act on
the interval [1, 2] before [2, 3]. The intermediate state must be a particle-antiparticle pair.
    For a slightly more rigorous argument, let X be an operator that moves a particle of type a
from 3 to 1, acting on spins along the interval. We can represent it as follows:

                                                                        X
                  Yk                    Zk                         X=         Y k Zk ,         (188)
            1                   2                  3                      k


where Yk and Zk act on disjoint sets of spins in some regions around [1, 2] and [2, 3], respectively.
Let Πx[s] (s = 1, 2, 3) be the projector onto states having particle x at point s; such operators
can be realized locally (to act in the gray circles in the above picture) if we only allow states
that are not excited away from the given three points. Finally, we define new versions of X,
Yk , and Zk :                                                               X
                             X ′ = Πa[1] Π1[2] Π1[3] X Π1[1] Π1[2] Πa[3] =     Zk′ Yk′ ,
                                                                             k                 (189)
                           ′      1    1          a                ′       a      1      1
                         Zk = Π[2] Π[3] Zk Π[3] ,               Yk = Π[1] Yk Π[1] Π[2] .
The operator X ′ still moves a from 2 to 3, but Yk′ and Zk′ overlap geometrically and therefore
no longer commute. It is clear that each operator Yk′ creates an a-particle at point 1 and some
particle at point 2, whereas Zk′ removes the second particle as well as the original particle at
point 3. Thus each product Zk′ Yk′ effects the process shown in Eq. (186), up to an overall factor.
This factor is nonzero for at least one value of k.

E.2.2    Some properties and normalization conventions.
                                                                             1     1
Lemma E.3. For each label a the corresponding label ā is unique. Moreover, Nab = Nba = δbā .
                        1   def
Proof. Recall that Nab    = dim Vab1 = dim V1ab . We first show that this number is equal to one
if b = ā and zero otherwise. Let ξ, η be as in the duality axiom, and let u be the corresponding
matrix element. For an arbitrary element ψ ∈ V1ab we have:

                       y                  b
                                                       (
                                         some
                                                           γidā for some γ ∈ C if b = ā
                   a   a    b       =   operator
                                                   =
                                                                      0         if b 6= ā.
                                           a




                                                           75
Therefore

                                                                        y                                             (
                                                                                                                           u−1 γ ξ if b = ā
                   ψ             =             u−1 a            a           a           b            =
                        by duality axiom                                                    due to the above                 0     otherwise.
                                                           

                   1
    To prove that Nba = δbā , we do a similar calculation with ψ ′ ∈ V1ba , putting (ψ ′ )† on the left
of ξ.
                          ¯ = a.
Corollary E.4. 1̄ = 1 and ā
    Let us now set new normalization conventions. In the definition of da we assumed that |ξi
and |ηi are √unit vectors, i.e., ξ †ξ = η † η = id1 . However, it is more convenient to multiply
ξ and η by da (and some suitable phase factors) so that the zigzag on the left-hand side
of equation (186) could be simply removed. The so normalized operators for the creation of
particle-antiparticle pairs will be represented as smooth “cups” with a triangle mark at the
bottom. The adjoint operators are “caps” obtained by flipping the pictures about a horizontal
line:21                                                                     †                                                          †
                                                           a            a                                                  a       a
                                                       =                            ,                             =                                                   (190)
                                       a       a                                                         a   a

In all four cases, the triangle points from a to ā as we follow the line. The four operators are
defined up to a single phase and satisfy the following relations:

                                                            a               a       = da =           a           a ,                                                  (191)


       a   a   a       = ida ,         a       a       a   = idā ,                              a   a       a    = ida ,                      a   a   a   = idā .   (192)

Eq. (191) and the first equality in (192) are true by definition. The second equality can be proved
analogously to Lemma E.3; the last two equalities are obtained by passing to adjoint operators.
Roughly, the normalization conditions may be described as follows: oppositely oriented triangles
cancel each other.
   So far the label a was fixed. Repeating the same procedure for ā, we get a new set of basis
vectors in V1aā , V1āa , Vaā
                             1      1
                                , Vāa , which must be related to the old ones:

                                           a       a                a       a                        a       a                 a       a
                                                       = κa                         ,                             = κā                    ,
                                                                                                                                                                      (193)
                                                       = κa∗                        ,                             = κā∗                   .
                                           a       a         a                  a                    a       a                 a       a

Combining these relations with Eqs. (191), (192), we get:

                                     |κa |2 = dā /da = |κā |−2 ,                                               κa (κā∗ )−1 = 1.
  21
    This notation is not standard, but it is convenient for calculations. In the notation used in [68, 79, 80],
cups and caps are not decorated but each particle has a fictitious degree of freedom: it is considered as either
a going up or ā going down. This prevents noninvariant phases from appearing in formulas.
                                                                                            76
Thus,
                                       dā = da ,                κā = κa∗ ,                        |κa | = 1.                                (194)
In general, the number κa depends on the arbitrary phases in the definition of cups and caps.
However, if a = ā, then κa is defined uniquely and coincides with the Frobenius-Schur indica-
tor.22 In this case, κa = ±1.
    Now we are in a position to relax the requirement that edges are transversal to the horizontal
direction.
Definition-Proposition E.5. A line is an alternating sequence of 2n cups and caps without
triangle marks. It may be open or closed. Such an object has a canonical normalization given
by n triangles pointing forward and n triangles pointing backward (relative to a chosen path
direction). All such decorations are equivalent.
       Let us also renormalize the inner product on splitting spaces:

                           r                                                  y
                                                                                       c
                     def            dc              1
              hhη|ξii =                  hη|ξi = √          a                              b c ,           where ξ, η ∈ Vcab .                (195)
                                   da db           da db dc 
                                                                                       c


(Triangles may be added in one of the two consistent ways; one may also flip the c-loop to the
left.) This renormalization does not violate the unitarity of associativity relations. The inner
product on fusion spaces is defined through the antilinear isomorphism Vcab → Vabc : ψ 7→ ψ † .
When computing either type of inner product, we stack two trees with branches touching each
other and connect the roots by a loop. Stacking the trees root to root might produce a different
result, but it turns out to be the same since we can actually rotate vertices by 360◦ , see below.
    Finally, we rewrite Eq. (176) in a form that is consistent with the new rules:

                a    b                                   a           b
                                             r
                                   XX             dc                 ab
                                                                         ;j                                 ab    ab
                          =                                  c                     ,               where hhψc,j |ψc,k ii = δjk                (196)
                                   c    j
                                                 da db           (       ab
                                                                             )y
                                                                          ;j


                a    b                                   a           b

               ab
(the elements ψc,j ∈ Vcab form a complete basis).

E.2.3       Raising and lowering of indices. Let us define the following linear maps:

                           a       b                a    b                                                       a       b         a b

 Aab    ab   b
  c : Vc → Vāc :                      7−→                   ,                     Bcab : Vcab → Vcab̄ :                     7−→             . (197)
                               c             a      c                                                                c              c    b

                                       c     b      ā     c̄      b̄
They are obviously invertible, hence Nab = Nāc = Nbc̄ = Nb̄ā = Nc̄a = Ncab̄ . Unfortunately, this
does not save us from the need to to distinguish between lower and upper indices because the
  22                                                                       ¯, which are regarded as different
    In category theory, κa is not a scalar but rather a morphism from a to ā
(albeit isomorphic) objects. Thus the arbitrariness goes away, but the Frobenius-Schur indicator has to be
defined in a more complicated fashion.

                                                                              77
                              Notation used in this paper                                                                                   Isotopy-invariant calculus
                                                                    a        a                               a       a            a
                              a       b                                              = κa                                                                        a               a   = κa a      a
  Vertices                                ,                                                                                                     ,
                                                                                                                                            b
                                  c                                                  = κ∗                                    c
                                                                                                                                                                 a               a   = κā a     a
                                                                a            a                               a       a
                                                    a                                                                                   a                                    a             a
  Lines                               a                     ,                                a               a                                               ,                         =
                                              a

  Cancellation rules          a       a       a        =                a        a           a           = ida                                               =                         =


                                                            Table 5: Notation summary.

simultaneous raising and lowering of indices on the two ends of a line results in the factor κa .
For example:

     a        x       b                                             x                            a       b

                     Aab        = κa                                  Aaux                                ,                        where η ∈ Vuāx ,                         ξ ∈ Vcab .    (198)
                                                                                                         
                  a                                             a
          u               c                                             u                            c

However, as the following theorem shows, we do not have to tie the types of indices to the
orientation of the corresponding vertex. This way, one obtains an isotopy-invariant calculus for
planar graphs, see Table 5. We will continue using the previous notation, though.
Theorem E.6. The maps Aab        ab
                            c , Bc are unitary with respect to the inner product hh·|·ii, and the
following diagram (in which the arrows may be traversed in both directions) commutes:

                                                                             Aab
                                                                              c gggg
                                                                                     Vcab WWWWWBcab
                                                                      ggg                                                        WWWWW
                                                                sggggg                                                                WW+ a
                                                                                                                                         Vcb̄
                                                  Vācb                                                                                   O
                                                        O
                                              Bābc̄                                                                                                Ab̄c̄a                                     (199)
                                                                                                                                                c̄a
                                                  Vābc̄ WWWWWW                                                                     V
                                                                                                                               ggggg b̄
                                                                                WWWWW                                    gggggc̄a
                                                                             Abc̄    W+                           c̄ s  g   B
                                                                              ā                             Vb̄ā     g
                                                                                                                                  b̄


Note that the commutativity of this diagram is equivalent the “pivotal identity” in Fig 16b.
The proof of the theorem is preceded by two lemmas.
Lemma E.7. The composition of any two adjacent arrows in Eq. (199) is unitary.
Proof. Due to symmetry, it suffices to consider just one particular case, e.g., the arrows con-
nected at the upper left corner. Let X = (Bābc̄ )−1 Aab
                                                      c : Vc
                                                            ab
                                                               → Vābc̄ . For arbitrary elements
      ab       bc̄
ξ ∈ Vc , η ∈ Vā we have:

                                                                a        b           c                                                      a         b      c
                                                                                                                             −1
                              Xξ =                                      
                                                                                         ,                               X        η =                                   ;
                                                                c                                                                                       a
                                                a                                                                                                                    c


                                                                                                             78
                                                                                                (X 1  )y
                                                           a
                                                                   y                                                 a            c
   p                                               a         b         c                                                  y                   p
    da db dc hhη|X|ξii =                                                            =                                                      =       da db dc hhX −1 η|ξii.
                                                                                                     a           b   c

                                           a
                                                   c                   X                                         
                                                                                                              c

Therefore X −1 = X † .
   Now consider the two paths from top to bottom of the hexagon (199):
                                                                                                      c                                            c

                                                                                          a b                                                              a b
 Ul , Ur : Vcab → Vb̄āc̄ ,                    Ul : ψ 7→                                                      ,                Ur : ψ 7→                                      . (200)
                                                                                          c                                                                      c
                                                                                b   a                                                                                 b   a

From the physical point of view, these operators (which are actually equal) correspond to the
CPT symmetry.
Lemma E.8.             Ul† = Ur−1 .
Proof. Let ξ ∈ Vcab and η ∈ Vb̄āc̄ . Then

                                                           Ul                                        (Ur 1  )y

  p                                                a b                                                    c       b   a                        p
   da db dc hhη|Ul |ξii =                                          c                    =                         y c
                                                                                                                                           =           da db dc hhUr−1 η|ξii.
                                    b          a       c 
                                                                                                                               a       b

                                    y     c                                                                                       c 




Proof of Theorem E.6. Let us consider the path around the diagram (199) in the counter-
clockwise direction, W = Ur−1 Ul . This operator is a composition of six arrows, therefore it is
unitary (due to Lemma E.7). On the other hand, Lemma E.8 implies that W = Ul† Ul is Her-
mitian and positive semidefinite. It follows that W is the identity operator, i.e., the diagram
commutes.
    Thus, Ul = Ur ; let us denote this operator simply by U. It is unitary by Lemma E.8. Any
arrow in the diagram is a composition of U (or U −1 ) and some number of arrow pairs. Therefore
all the arrows are unitary.

E.2.4     Quantum dimension and fusion rules. This is a key identity:
                                         X
                                             c
                                 da db =   Nab dc .                                                                                                                             (201)
                                                                                            c

To prove it, we use Eq. (196), the pivotal property, and Eq. (195):

                                                               a b                                                                                     (   ab
                                                                                                                                                                 )y
                                    r                                  ab                                                   r                               ;j
                           X             dc                                ;j
                                                                                                                      X             dc                                    X
                                                                                                                                                                                c
da db =        a   b   =                                       c                                  =                                        c       a b                =        Nab dc .
                              c,j
                                        da db                      (       ab
                                                                            ;j
                                                                               )y                   ab
                                                                                         rotating ψc,j
                                                                                                                      c,j
                                                                                                                                   da db                                  c
                                                                                                                                                           ab
                                                               a b                      counterclockwise
                                                                                                                                                           ;j




                                                                                         79
    Eq. (201) implies that the matrix N(a)b    = (Nab c
                                                        : b, c ∈ M) has eigenvector v = (dc : c ∈ M),
and the corresponding eigenvalue is da . Note that all the entries of v are positive. According
to the Perron-Frobenius theorem (about matrices with nonnegative entries), all eigenvalues of
Nb (a) satisfy the inequality
                                             |λj (a)| ⩽ da .                                     (202)
Thus, the quantum dimension da is the largest eigenvalue of the matrix N       b (a).
    The proof of Eq. (201) also motivates a definition of quantum trace. It is a number assigned
to any element X ∈ Vaa11...a
                          ...an
                             n
                                . Such an element acts as an operator in the space Vca1 ...an for each
c; we denote this action by Xc . The quantum trace is defined as follows:

                                                                                    a 1 a 2 . . . an
                                 def
                                               X
                            f
                            Tr X =                   dc Tr Xc =                         X              .       (203)
                                               c                                    a 1 a 2 . . . an




E.3     Braiding and topological spin
Braiding is an additional piece of algebraic structure characterizing anyons. It is defined by a
set of elements Rab ∈ Vabba that represent transposition of two particles:
                                   b a                                                            a b
                         Rab =             ,                  (Rab )−1 = (Rab )† =                         .   (204)
                                   a b                                                            b a

They must satisfy the Yang-Baxter equation, i.e., a line can be moved over or under a crossing
between two other lines:
                                                   c b a           c b a

                                                              =             .                                  (205)

                                                   a b c           a b c
More generally, a line can slide over or under an arbitrary vertex. It is sufficient to postulate this
property for three-prong vertices representing splitting and fusion and for lines tilted left and
right. Furthermore, splitting and fusion are related by the decomposition of the identity (196),
whereas changing the slope of the intersecting line is equivalent to replacing R with R−1 . Thus
the number of independent conditions is reduced to two:
                            y z    x           y z    x              y z        x           y z    x


                                       =                  ,                         =                  .       (206)

                            x r                x r                    x r                   x r

   The description of braiding in terms of basic data amounts to specifying the action of Rab
on splitting spaces:
                             b a

                                       = Rcab ψ,                    Rcab : Vcab → Vcba .                       (207)
                              c


                                                              80
                      y       z       x              y       z       x                                                                    y z           x            y       z       x

                                              F                                                                                                                F
                          p                                      q                                                                          p                                    q
                 R                                                       R                                                         R −1                                                  R −1
 y       z   x                                                                    y   z       x            y       z       x                                                                    y    z       x
                              u                              u                                                                                  u                            u



     p                                                                                    q                    p                                                                                         q

         u       F    y       z       x              y       z       x   F            u                            u                 F    y z           x            y       z       x   F           u


                                              R                                                                                                               R −1
                                  r                      r                                                                                          r                    r

                              u                              u                                                                                  u                            u
                                              a)                                                                                                              b)
                                                                 Figure 20: The hexagon equations.

Note that Rcab is a unitary map, therefore Nab
                                             c
                                                = Nbac
                                                       .
                                        ab
    To express Eq. (206) in terms of Rc , we join the two lines at the bottom of each graph and
perform equivalence transformations. These include F -moves as well as R-moves — absorbing
a line crossing by a vertex. Thus we obtain the diagrams in Fig. 20; the bottommost arrow in
each of them combines an R-move with the first or the second equation in question. We may
now forget about the topological meaning of braiding and only keep track of the linear maps
involved:
                       L yx          pz        Fuyxz         L yq       xz
                          p V p ⊗ V u
                                                           /
                                                              q Vu ⊗ Vq
                                                       ?                                                                                           ??
                                                                                                                                                      ?? L
                     L       xy                                                                                                                       ?? q idV yq ⊗Rxz
                          p Rp ⊗idV pz
                                                                                                                                                                     q
                                             u                                                                                                          ??    u
                                                                                                                                                         ??
                                                                                                                                                            ?
                     L         xy   pz
                                                                                                                                                       L         yq   zx
                           p Vp ⊗ Vu                                                                                                                          q Vu ⊗ Vq                             (208)
                                             ??
                                               ??                                                                                                          ?
                                                 ?? F xyz                                                                                        yzx 
                                                                                                                                                         
                                                   ?? u                                                                                         Fu
                                                     ??                                                                                               
                                                       ?                                                                                           
                                                L                                                    xr
                                                                                                                                   L
                                                                                      L
                                                                                          r (idVryz ⊗Ru ) · swap
                                                                                                                                                 
                                                        xr   yz                                                                            yz   rx
                                                    r Vu ⊗ Vr                                                                          r Vr ⊗ Vu
                                                                                                                               /


                                            L         yx   pz                                     Fuyxz                    L           yq   xz
                                                  p Vp ⊗ Vu                                                                        q Vu ⊗ Vq
                                                                                                                       /
                                        ?                                                                                                   ??
                   yx −1                                                                                                                   ?? L
             L
               p (Rp )   ⊗idV pz                                                                                                               ?? q idV yq ⊗(Rzx
                                                                                                                                                               q )
                                                                                                                                                                  −1
                             u                                                                                                                  ??    u
                                                                                                                                                 ??
                                                                                                                                                    ?
                 L       xy   pz
                                                                                                                                               L               yq   zx
                     p Vp ⊗ Vu                                                                                                                              q Vu ⊗ Vq                               (209)
                                          ??                                                                                                          ?
                                            ??                                                                                                     
                                              ?? F xyz                                                                                    Fuyzx 
                                                                                                                                                  
                                                ?? u                                                                                            
                                                  ??                                                                                          
                                                    ?                                                                                       
                                             L                                               rx −1 ) · swap
                                                                                                                           L
                                                                             L
                                                                                 r (idVryz ⊗(Ru )
                                                      xr   yz                                                                          yz   rx
                                                  r Vu ⊗ Vr                                                                        r Vr ⊗ Vu
                                                                                                                   /

These commutative diagrams are known as hexagon equations. They actually look nicer in the
tensor category formalism, see Eqs. (274) and (275).

                                                                                                      81
   Note that braiding with label 1 is trivial:
                 1       a           1       a           1       a

                                 =                   =                   ,            i.e., Raa1 αa = (Ra1a )−1 αa = βa .                                   (210)
                             a                   a                   a
                     a                   a                   a

(The proof is analogous to that of Lemma E.2.) Due to this property, we need not worry about
lines labeled by 1, e.g., ones that are implicitly attached to each cup and cap.
    To each label a we associate a complex number θa , called topological spin:

                                 def
                                                                                                                 X
                             θa = d−1                                        = d−1 f        −1
                                                                                                                             dc Tr Rcaa .
                                   a                                            a Tr Raa = da                                                               (211)
                                                         a a                                                         c

It may also be characterized by any of the following relations:
                                 a                   a           a                                        a              a        a

                                       = θa              =                    ,                               = θa∗          =              .               (212)
                                 a                   a           a                                        a              a        a

Note the following properties of the topological spin:
                                                         |θa | = 1,                             θā = θa .                                                  (213)
Indeed,
                                 a

          da θa θa∗ =                        = da ,                               da θā =                               =                      = da θa .
                                                                                                  a       a    a a             a a    a     a
                                 a

This is yet another expression for the topological spin:
                                                                         a    a             a     a
                                                                                  =   θa∗             .                                                     (214)


(To prove it, we need to put a left-oriented cap on both sides of the equation and rotate the
resultant figure-eight on the left-hand side by 90◦ .) In particular, if ā = a, then we have the
following representation for the invariant scalar R1aa :
                                                                             R1aa = θa∗ κa .                                                                (215)
Remark E.9. Eq. (215) provides a simple physical interpretation for the Frobenius-Schur
indicator κa . Suppose that the system is rotationally invariant, so that not only the topological
spin but also the usual spin sa has physical meaning. Of course, sa may take different values
subject to the constraint e2πisa = θa . Let us consider a pair of identical particles with trivial
total topological charge. What values does the total angular momentum of this composite
object take? This question may be answered as follows. Assuming that both particles are in
the same spin state sa and barring additional “isospin” degrees of freedom, the 180◦ rotation
is characterized by the phase factor eiπsa eiπsa R1aa = κa . Thus, the total angular momentum is
even if κa = 1 and odd if κa = −1.

                                                                                   82
   It is interesting that the effect of moving one particle around another is fully characterized
by the topological spin:
                                                     θc
                                        Rcba Rcab =      id ab .                            (216)
                                                    θa θb Vc

Proof. Consider the following element of the space Vabab :

                                        a   b                    a    b


                                                             =              = Rba Rab θa θb .                            (217)

                                        a       b                a    b


Acting by it as an operator on the space Vcab , we obtain the required identity.
Theorem E.10 (Vafa [90]). The topological spins are roots of unity. More specifically, θan = 1,
where the integer n 6= 0 depends only on the fusion multiplicities.
Proof. Let us use this fact from linear algebra: for any integer matrix Q XX      there is an integer
matrix Y (the adjugate) such that Y X = (det X)I. Therefore, if b θb = 1 for all a, then
                                                                              ab


θbdet X = 1 for all b.
     To find multiplicative relations between topological spins, we consider determinants of R-
and F -moves. Such determinants generally depend on the choice of basis in the source and the
target space. So, let us fix a basis in each space Vcab and replace the linear maps in the hexagon
equations (208) and (209) by their determinants. Dividing the first equation by the second, we
get:
                                  !                             !                                 !
          M                            M                                 M
    det      (Rpxy Rpyx ) ⊗ idVupz det     idVuyq ⊗ (Rqxz Rqzx ) = det       idVryz ⊗ (Ruxr Rurx ) .
         p                                               q                                          r


Note that the determinants here are actually invariant and can be expressed in terms of topo-
logical spins using Eq. (216):

                         Y  θp Nxy Npz Y  θq Nyq                                   Y  θu Nyz
                                      u     p     u N                        q                  r Nu
                                                      xz                                           xr

                                                                                   =                         ,
                         p
                               θx θy                     q
                                                             θx θz                     r
                                                                                           θx θr

             Y       p    p̄   p   p̄       p       p̄                    Nxyzv                   def
                                                                                                         X
                 θpNxy Nzv +Nxz Nyv +Nyz Nxv = θx θy θz θv                         ,       Nxyzv =            q
                                                                                                             Nxy  q̄
                                                                                                                 Nzv ,   (218)
             p                                                                                           q

where we have substituted v for ū.
   For our purposes, it is sufficient to consider the case where x = y = a and z = v = ā. Thus
we obtain a system of equations described by a square matrix:
             Y X
                                                                   b   b̄    b    b̄
                θb ab = 1,          where Xab = 4Naaāā δab − 2Naā Naā − Naa Nāā .    (219)
                 b




                                                                     83
It remains to show that X is nondegenerate. For this purpose, we may divide the a-th row of
X by Naaāā so that the matrix becomes 4I − Y ; the eigenvalues of Y are bounded by a suitable
multiplicative matrix norm:
                                                                           X
      Yab = (Naaāā )−1 2Naā
                           b    b̄
                               Naā    b
                                    + Naa   b̄
                                          Nāā  ,   eigenvaluej (Y ) ⩽ max    |Yab | = 3.
                                                                                              a
                                                                                                  b

Thus the matrix 4I − Y cannot have a zero eigenvalue.

E.4    Verlinde algebra and topological S-matrix
In this section we investigate some properties of fusion, based on the axioms stated above.
First, let as consider a fusion theory with particle-antiparticle duality, but without braiding.
The Verlinde algebra is an associative ∗-algebra spanned by elements ea : a ∈ M which satisfy
the following relations:               X
                                            c
                               ea eb =    Nab ec ,        e†a = eā .                      (220)
                                                  c

The basis element ea ∈ Ver may be represented by the matrix N       b (a) = (N c : b, c ∈ M); this
                                                                               ab
                                  b         b    †
representation is faithful. Since N (ā) = N (a) , the algebra operation † corresponds to taking
the adjoint matrix. Therefore Ver is actually a finite-dimensional C ∗ -algebra. Equation (201)
says that the linear map Ver → C : ea 7→ da is a homomorphism.
                                   c       c
    If braiding is defined, then Nab  = Nba  , therefore the Verlinde algebra is commutative. A
                                    ∗
finite-dimensional commutative C -algebra splits into several copies of C. Therefore we have
|M| distinct homomorphisms from Ver to C, which we refer to as fusion characters:
                                                                X
                                                                    c
                        λj : Ver → C,            λj (a)λj (b) =    Nab λj (c).              (221)
                                                                               c

The vector vj = (λj (c) : c ∈ M) is a common eigenvector of the matrices N   b (a), the eigen-
                                                     b (a) are normal, therefore eigenvectors
values being equal to λj (a). Note that the matrices N
corresponding to distinct eigenvalues must be orthogonal. Thus the following orthogonality
condition holds:              X
                                 λj (a)λk (a)∗ = 0      if j 6= k.                       (222)
                                        a

    We will now construct a map from the set of labels to the set of fusion characters. Specif-
ically, we are to show that some of the characters are given (up to a constant factor) by the
columns of the topological S-matrix S = (sab : a, b ∈ M), where

        def   1                     f
                                    Tr(Rb̄a Rab̄ )   1 X                       1 X c θc
    sab =       a   b   a   b   =                  =     dc Tr(Rcb̄a Rcab̄ ) =     Nab̄       dc .    (223)
              D                         D            D c                       D c      θa θb
                                        pP
The normalization factor 1/D with D =            2
                                              a da is chosen so that S is unitary under certain
conditions.
   Let us study properties of the numbers sab . First, we observe these symmetries:

                                sab = sba = sāb̄ = sb̄ā = s∗āb = s∗bā = s∗ab̄ = s∗b̄a .           (224)

                                                           84
Indeed, up to normalization we have:

                 b                                                                         a       a                ∗                        ∗
sab ∼        a       =       b
                                 a
                                     ∼ sba ,         sab ∼ a          b   a   b =                         b = θa θa a       b     a   b ∼ sāb .



Factors of the form sax /s1x often arise via this equation:

                                         x                  x

                                                      sax                                          dx
                                             a   =              ,                   s1x =             .                                  (225)
                                                      s1x                                          D
                                         x                  x

For example, let us repeat the calculation done in proof of Eq. (201), but now with an additional
line passing through the loops:

                                                                          x
                 x               x                                                                                      x
                                                                                  b
                                                       r                      a
                     b                           X           dc
                                                                                      ab
                                                                                      ;j
                                                                                                       X
                                                                                                               c
                         =           a   b   =                                c                    =          Nab           c .
                                                 c,j
                                                            da db               (     ab
                                                                                          )    y
                                                                                                          c
                     a                                                        a        ;j


                                                                                  b
                 x               x                                                                                      x
                                                                          x

                                                                    sax sbx          X
                                                                                        c scx
The first and the last expression are equal to                         2
                                                                            idx̄ and   Nab      idx̄ , respectively. Thus,
                                                                     s1x             c
                                                                                           s 1x

                                                     sax sbx   X
                                                                  c
                                                             =   Nab scx .                                                               (226)
                                                      s1x      c

Comparing this equation with Eq. (221), we conclude that
                                         sax
                                             = λj (a)                for some j = j(x).                                                  (227)
                                         s1x
In other words, for each x the map a 7→ sax /s1x is a fusion character.
    In the next section we will see that if braiding is sufficiently nontrivial, then the S-matrix
is unitary. In this case, the map from labels to fusion characters is one-to-one, and Eq. (226)
may be cast into a form known as Verlinde formula:23
                                              X sax sbx sc̄x
                                        c
                                      Nab  =                 .                               (228)
                                               x
                                                     s1x
  23
    Eqs. (226), (228) were first obtained by Pasquier for statistical models and conformal theories associated
with Dynkin diagrams [100]. A general derivation in the CFT framework is due to Verlinde [62].




                                                                    85
E.5     Braiding nondegeneracy = modularity
Let us recall the definition of a superselection sector: it is a class of states that can be trans-
formed one to another by local operators. From the physical perspective, the operators we
use must respect any unbroken symmetry present in the Hamiltonian, e.g., the U(1) symmetry
associated with the conservation of electric charge. Another example is the number of fermions
modulo 2, if that number is not conserved as an integer. (Here we speak about actual fermions
forming the system rather than effective Majorana modes obtained by a nonlocal transforma-
tion.) However, in the model studied in this paper the superselection sectors are stable with
respect to all local operators. More generally, we may consider an arbitrary system built of
spins or other bosonic degrees of freedom, and ask for properties that are stable to a generic
perturbation. In this case, the superselection sectors have purely topological nature: some sig-
nature of a nontrivial excitation x 6= 1 will be preserved even if we cut out a piece of material
containing the quasiparticle. It is quite reasonable to assume that the presence of such an
excitation can actually be detected by an Aharonov-Bohm measurement, i.e., by moving a test
particle a around x. Thus we arrive at the condition that the braiding is nondegenerate, which
must be true for any anyonic system not complicated by external symmetries.
Definition E.11. Braiding is said to be nondegenerate if for each label x 6= 1 there is some
label a such that the operator Rax Rxa is not identity.
Theorem E.12. L In a theory with nondegenerate braiding, the following operator Sz acting in
the space Lz = b Vbbz is unitary:
                                                        a       z
                          b       z
                                      def   1 X             b
                     Sz               =         da                   ,   where ψ ∈ Vbbz .    (229)
                                            D a             b
                              b
                                                     a

Note that the standard S-matrix corresponds to z = 1. The operator Sz† differs from Sz by the
orientation of crossings. (This is easy to show by considering a matrix element of Sz .) The
converse of Theorem E.12 is also true and can be proved easily: if the standard S-matrix is
unitary, then the braiding is nondegenerate.
Lemma E.13. The operator Rax Rxa is trivial for all labels a if and only if x is mapped to the
trivial fusion character j(x) = j(1), i.e., if sax /s1x = da for all a.
Proof. The triviality of Rax Rxa means that for all c, Rcax Rcxa = idxa         θc
                                                                     c , i.e., θx θa = 1 whenever
 c
Nxa 6= 0. We calculate sxā = s∗ax using Eq. (223):
                                             X           θc        X
                                                   c                  c
                                  D sxā =        Nxa         dc =   Nxa dc = dx da .
                                              c
                                                        θx θa      c

Thus, sax /s1x = da . Conversely, if the operator Rax Rxa is nontrivial, then
                                 X                         X
                                        c        θc              c
                    D Re sxā =       Nxa Re            dc <   Nxa dc = dx da ,
                                   c
                                               θx θ a        c

therefore sax /s1x 6= da .

                                                                86
    The proof of Theorem E.12 is based on the following equation, which is useful on its own
right:
                                                   x                              x

                                    1 X
                                         da                a   = δj(x),j(1) .                                (230)
                                    D2 a
                                                   x                              x

Indeed, the condition j(x) = j(1) means that the fusion character λj(x) : a 7→ sax /s1x is trivial,
i.e., sax /s1x = dP
                  a . On the other hand, if λj(x) is nontrivial, then it is orthogonal to the trivial
character, i.e., a da s∗ax = 0. The above equation combines both cases.
Proof of Theorem E.12. By Lemma E.13, the nondegeneracy condition implies that j(x) =
j(1) if and only if x = 1. Thus, the linear combination of loops in Eq. (230) is a projector onto
label 1. We apply it as follows:

                                                 x y                         x        y

                                   1 X                             1
                                            da         a       =      δx̄y                ;                  (231)
                                  D2   a
                                                                   dx
                                                 x y                         x        y


                                            x                  z                          x       z

                            1 X                                        X
                                                       b                                      b
                                                                                  δxb
               Sz† Sz ψ =           dx da         a                =         dx                       = ψ.
                            D 2 x,a                    b               x
                                                                                  dx          b
                                            x                                             x



    Theories with a unitary S-matrix are often called modular due to their relation to the
group of diffeomorphisms of the two-dimensional torus considered up to topological equiva-
lence (namely, isotopy). Let us discuss this subject at a speculative level. The first thing
to note is that a system of spins or electrons can in principle be put on a torus whether or
not the braiding is nondegenerate. However, as indicated earlier, degeneracy generally occurs
due to some external symmetry. If it is a gauge symmetry, then putting the system on the
torus involves some choice. For example, in the case of U(1) symmetry, one may run an ar-
bitrary magnetic flux through each basic circle of the torus. Those fluxes can be detected
by Aharonov-Bohm measurements, but they cannot be changed by intrinsic operations, which
include splitting, fusion, and moving particles around the torus. Mathematically, such oper-
ations form a so-called skein algebra, which may be defined in terms of graphs on the torus
up to equivalence transformations. (Recall that a planar graph without external lines can be
transformed to a number, therefore the skein algebra of the plane is simply C.) The skein
algebra is a finite-dimensional C ∗ -algebra; in general it is a direct sum of several blocks, each
block being isomorphic to the algebra of operators on some finite-dimensional Hilbert space.
Physically, different blocks correspond to different values of external parameters such as the
magnetic fluxes. Modular theories are special in that there is only one block. In other words,
the torus is characterized by a single finite-dimensional space.


                                                       87
    The Hilbert space of the torus is actually M = CM . A basis in this space may be associated
with effective anyonic charge that is detected by an Aharonov-Bohm measurement along some
circle. Different circles correspond to different bases. The S-matrix effects a transition between
two bases. Other important matrices are C = (δāb : a, b ∈ M) (which corresponds to a 180◦ -
degree rotation) and T = (θa δab : a, b ∈ M) (which corresponds to a Dehn twist). We will
justify this description by showing that S, C, and T obey the modular relations up to a phase
factor Θ:
                               (ST )3 = ΘC,       S 2 = C,    C 2 = I,                        (232)
where                                                                         X
                                                          Θ = D −1                 d2a θa .                                             (233)
                                                                               a

As a corollary, note that Θ is a root of unity. Indeed, S 4 = I, therefore Θ4|M | = (det T )12 is a
product of topological spins, which are roots of unity by Theorem E.10.
L Letbz us actually study relations between more general operators acting in the space Lz =
  b Vb (which corresponds to a punctured torus, with z being the anyonic charge of the punc-
ture). The operator Sz has been already defined, whereas

                            b       z                 b           z                           b        z               b        z
                                                              b
                                         def                                                               def
                       Cz                =      θb∗                   ,                Tz                  = θb                     .   (234)
                                                              b
                                b                     b                                            b                        b


Theorem E.14. The operators Sz , Cz , and Tz satisfy the following modular relations:

                      Sz† Tz Sz = Θ Tz† Sz† Tz† ,                             Sz = Sz† Cz ,                          Cz2 = θz∗ .        (235)

Proof. The calculation of Sz† Tz Sz parallels the proof of Theorem E.12, but the nondegeneracy
condition is not necessary. First, let us apply the S-matrix to the row vector with entries da θa :
                X                            1 X                  1 X
                                                       c θc                θc
                      da θa sax̄ =                 da Nax    dc =     dx dc dc = Θ dx θx∗ .
                  a
                                             D a,c        θx      D c      θx

The result may be written as follows:

                                                                          x                   x

                                                1 X
                                                    da θa                      a   = Θ                 .                                (236)
                                                D a
                                                                          x                   x

Then we replace the single line by two lines and simplify the result (cf. Eq. (217)):

                                                                          x    y
                                                 x y                                                             x      y
                         1 X
                                        da θa             a   = Θ                                 = Θ θx∗                   θy∗ .       (237)
                        D       a
                                                 x y                                                             x      y
                                                                          x    y


                                                                          88
Attaching a graph representing ψ ∈ Vȳȳz to the first and the last expression, we get Sz† Tz Sz ψ
and Θ Tz†Sz† Tz† ψ, respectively.
   Now we show that Sz = Sz† Cz . If ψ ∈ Vbbz , then

                            a       z                     a            z                        a       z

               1 X              b           1 X                    b
                                                                               1 X                  b
      Sz ψ =           da               =            da                    =           da θb∗               = Sz† Cz ψ.
               D   a            b           D   a                  b           D   a                b
                            a                             a                                     a


The formula Cz2 ψ = θz∗ ψ follows from (217).

E.6     Gauge freedom and Ocneanu rigidity
In the preceding sections, we defined a theory of anyons as a solution to a certain system of
algebraic equations for Fuabc , αa , βa , and Rcab . Specifically, these are the pentagon equation, the
triangle and hexagon equations as well as unitarity conditions. (The unitarity conditions are
algebraic in the real and imaginary part of the corresponding matrices.) The set of solutions
is some real algebraic variety. This description, however, does not take into account a gauge
degree of freedom. Indeed, two solutions are physically equivalent if they are related to each
other by a simultaneous basis change in the spaces Vcab . In the examples studied in this paper,
quotienting over such transformations makes the set of solutions discrete. In other words, the
algebraic structure is rigid, with the physical consequence that the properties of anyons are
stable to small perturbations of the Hamiltonian. Is it true in general? The affirmative answer
was obtained by Ocneanu, but he did not publish his proof. The only written proof I know
of is due to Etingof, Nikshych, and Ostrik [30], but it is more general and hence complex;
in particular, it does not depend on the unitarity or the pivotal property. Meanwhile, the
proof of Ocneanu rigidity for unitary theories is not very difficult and may be interesting to a
mathematical physicist.
    To prove that a solution to an equation system is rigid, one needs to study infinitesimal
deformations. Let us call a deformation of F , α, β, R permissible if it satisfies the equations
in the first order of Taylor expansion. The deformation is called trivial if it can be obtained
by a change of basis, also in the first order. (By restricting our attention to the first order, we
potentially make the space of permissible deformations larger and the space of trivial deforma-
tion smaller.) Our goal is to calculate the quotient, permissible modulo trivial, and show that
it vanishes. The analysis consists of several steps.
    First, we only consider F and the pentagon equation. The resulting deformation problem
resembles the definition of H 3 (G, R) for a group G. In fact, it is exactly that in example 2 on
page 72. Associated with an arbitrary fusion theory is a cochain complex defined by Crane and
Yetter [91] and independently by Davydov [92]. It is a sequence of real spaces and linear maps
                                                    δ1        δ2       δ3
                                            C1 −
                                               → C2 −
                                                    → C3 −
                                                         → ···                                                        (238)
                                                def
whose third cohomology space H 3 (C) = Ker δ 3 / Im δ 2 classifies the nontrivial deformations of
the theory. (The first and the second cohomology spaces have natural interpretation too.) We


                                                          89
will use the term “tangent cohomology”24 proposed by Davydov.
    It is well known that any finite group has trivial real cohomology in all dimensions n ⩾ 1.
Likewise, the tangent cohomology vanishes for an arbitrary unitary fusion theory (actually, any
fusion theory). The proof of this statement is based on the same idea as the corresponding
proof for groups. In the latter case, one uses averaging over the group, which is well-defined
because the group is finite. For a unitary fusion theory, one needs to take the quantum trace
(actually, a partial quantum trace) and average it over the label set with weight da /D 2 .
    The next step is to include α, β and to consider the triangle equations. This is just a
technical detail that involves trivial changes to the deformation theory [93]. (The argument is
quite general and applicable even if the label set is infinite, in which case the cohomology may
not vanish.) The rigidity of braiding follows from the vanishing of H 2 (C) in conjunction with
Vafa’s theorem (see Theorem E.10).

E.6.1 Gauge freedom in the description of anyons. An isomorphism between two
fusion theories, A and A′ is given by a bijection between the label sets (we simply assume that
they are equal) and a collection of unitary maps25 Γab       ′ ab      ab
                                                       c : (V )c → Vc ; these data are enough
to relate one system of associativity constraints to the other:
                    a       b   c        a   b       c
                                                                         X                     X              
 Fuabc , (F ′)abc
              u :       e           −→           f       ,       Fuabc        Γab   ec
                                                                               e ⊗ Γu        =        Γaf
                                                                                                       u  ⊗ Γ bc   ′ abc
                                                                                                              f (F )u . (239)
                                                                          e                       f
                            u                u

For example, let A′ be obtained from A by changing left and right, i.e., (V ′ )ab  c = V
                                                                                          ba
                                                                                              and
   ′ abc      cba −1                                       ab       ab −1
(F )u = (Fu ) . If theory A has braiding R, then Γc = (Rc ) is an isomorphism (for a
quick demonstration, apply the Yang-Baxter braid (205) to both trees above). However, we will
be mostly interested in the case where (V ′ )ab      ab          ab
                                               c = Vc so that Γc may be called “basis change”;
examples can be found in Sections 8.4 and 9.
    By analogy with Eq. (239), one can write similar equations for αa vs. αa′ and βa vs. βa′ .
However, the physical meaning of α and β is rather elusive, so it is not clear whether we obtain
the most general form of equivalence this way. A reasonable notion of isomorphism between two
theories, namely tensor functor arises naturally in the categorical formalism (see Sec. E.7.3).
To state it in concrete terms, we just need to supplement the basis change with an overall phase
factor γ so that
                              αa = Γa1     ′
                                      a γ αa ,          βa = Γ1a     ′
                                                              a γ βa .                      (240)
       Finally, the braiding rules are changed as follows:
                                                             Rcab Γab   ba  ′ ab
                                                                   c = Γc (R )c .                                       (241)
   Thus we have defined the family of theories A′ that are isomorphic to a given theory A.
However, their parametrization by Γab
                                   c and γ is redundant. In particular, F , α, β, R do not
change if we replace Γc and γ with Φab
                      ab
                                    c and ϕ such that
                                                              hc ab
                                             Φab
                                              c =                 Γ ,             ϕ = h1 γ,                             (242)
                                                             ha hb c
  24
      Etingof, Nikshych, and Ostrik call it “Yetter cohomology” in recognition of Yetter’s further work in this
area.
   25
      The direction of these maps is chosen to be consistent with the definition of a tensor functor (see Defini-
tion E.25).

                                                                         90
where hx are arbitrary phase factors. In the categorical language, the tensor functors defined
by (Γ, γ) and by (Φ, ϕ) are isomorphic.
   Thus we have entities of dimension 0, 1, and 2: theories of anyons, 1-isomorphisms (i.e., iso-
morphisms between theories), and 2-isomorphisms (i.e., isomorphisms between 1-isomorphisms).
Let us define three sets indexed by a complementary dimension:

   1. 2-automorphisms h of a given 1-isomorphism (Γ, γ);

   2. Equivalence classes of 1-automorphisms (Γ, γ) of a given theory A up to 2-isomorphisms;

   3. Equivalence classes of theories with given fusion multiplicities up to 1-isomorphisms.

The first set is an Abelian group, the second is a group (see Appendix F), the third does not
have any special structure.

E.6.2 Infinitesimal deformations and the vanishing of tangent cohomology. Let us
define infinitesimal analogues of sets 1, 2, 3; we will eventually prove that they are trivial. The
constructions involved are typical to cohomology theory, following a pattern that may already
be recognized by studying set 1. We are eventually interested in set 3, which classifies solutions
of the pentagon equation up to a basis change. In this subsection we ignore braiding and all
attributes of the vacuum sector (i.e., γ, α, β, and the triangle equations); these things will be
considered later.
    For a fixed fusion theory with associativity constraints Fuabc , let
                                                                                           
     ha ≈ 1 − iXa ,        Γab
                             c ≈ idVcab − iYc ,
                                               ab
                                                         (F ′ )abc
                                                               u   ≈ Fuabc idVuabc − iZuabc ,  (243)

where Xa is an infinitely small real number and Ycab , Zuabc are infinitely small Hermitian oper-
ators acting in Vcab and Vuabc , respectively.26 Now, let us substitute the expressions for h and Γ
into Eq. (242), assuming that Φab   c = idVcab . We get:

                                                ab def
                                    Ycab = δ 1 X c = (Xb − Xc + Xa )idVcab .                                      (244)

An infinitesimal analogue of set 1 is the space of deformations X = (Xa : a ∈ M) such that
δ 1 X = 0. One can deal with Eq. (239) and the pentagon equation in an analogous way.
     To present the results in a more convenient form, let us get rid of the lower index c. (In a
categorical formulation of the theory, it does not appear at all.) Note that the set of operators
Ycab for all c represents the action of a single element Yab ∈ Vabab , which may be constructed as
follows:
                                                 a           b
                   a b               r
                             X            dc             Y       ab      ab
                                                                          ;j                 ab    ab
                   Yab   =                           c
                                                                      y
                                                                               ,    where hhψc,j |ψc,k ii = δjk   (245)
                              c,j
                                         da db           (       ab
                                                                  ;j
                                                                     )
                   a b
                                                 a           b

  26
                                                 L
    To be rigorous, Zuabc acts in the space e Veab ⊗ Vuec , the representation of Vuabc corresponding to the ((ab)c)
label grouping. But that is not so important as we always identify different groupings (= trees) using F .




                                                                               91
                        ab
(cf. Eq. 196). For δ 1 X c this procedure yields:

                                                 a     b                               a             b                      a    b
                                                                     r                               ab

                                                            X               dc                          ;j
                          1
                          δ X ab =                   Xb −                                   Xc                      + Xa             .                           (246)
                                                                            da db
                                                              c,j
                                                                                                 (       ab
                                                                                                          ;j
                                                                                                               )y
                                                a      b                               a         b                          a    b

More generally, we can use the following definition.
                                                                                                                    L
Definition E.15. Let C n be the set of self-adjoint elements in                                                                      a1 ...an
                                                                                                                        a1 ,...,an Va1 ...an . The tangent
complex of the fusion theory is the sequence of R-linear maps
                                                                                                                    n+1
                                                                                                                    X
                         0               1           2         3
                     0 δ             1 δ         2 δ       3 δ                                           n
                   C −
                     →C −
                        →C −
                           →C −
                              → ··· ,                                                                δ =                   (−1)k fkn ,                           (247)
                                                                                                                     k=0

where the maps fkn : C n → C n+1 are defined as follows:

                           a1     a2            an+1                                                                            a1             an an+1
                                        .....                                                                                        .....
          
     f0n X a1 ...an+1 =           X 2 n+1 ,
                                       a :::a
                                                                                     n
                                                                                    fn+1
                                                                                          
                                                                                         X a1 ...an+1 =                         X    a1 :::a n           ,
                                        .....                                                                                        .....
                           a1     a2            an+1                                                                            a1           an an+1

                                                                      ak       ak+1                                                                              (248)
                                             s                 ....
                                                                           c    j
                                                                                           ...
                                      X
               
          fkn X a1 ...an+1 =
                                                     dc
                                                 dak dak+1
                                                               X k 1 k+2
                                                                    :::a       a       :::                          for k = 1, . . . , n.
                                      c,j                                  c       y
                                                               ....                        ...
                                                                                   j
                                                                       ak      ak+1

                                def                                                                                                                          P
(For n = 0 we use V∅∅ = V11 = C, hence C 0 = R. Correspondingly, f00 , f10 : 1 7→                                                                            a idVaa ,
therefore δ 0 = f00 − f10 = 0.)
    Note that C is indeed a cochain complex, i.e., δ n+1 δ n = 0, which follows from this easily
verifiable identity:
                       fkn+1 fm
                              n    n+1 n
                                = fm+1 fk     for 0 ⩽ k ⩽ m ⩽ n + 1.                      (249)
(It is part of structure that makes C into a cosimplicial space.)
    The reader may check that Eq. (239) becomes Z = δ 2 Y . Therefore the infinitesimal analogue
of set 2 is given by solutions to the equation δ 2 Y = 0 modulo elements of the form Y = δ 1 X.
Similarly, the pentagon equation may be written as δ 3 Z = 0, and the solutions should be
considered modulo δ 2 Y . Thus, low-dimensional cohomology of the tangent complex has the
following meaning:
   • H 0 (C) = R;

   • H 1 (C) classifies infinitesimal 2-automorphisms of the identity 1-automorphism;

                                                                      92
   • H 2 (C) classifies infinitesimal 1-automorphisms (i.e., basis changes that leave the associa-
     tivity constraints invariant) up to 2-isomorphisms;
   • H 3 (C) classifies infinitesimal deformations of the fusion theory up to 1-isomorphisms (i.e.,
     arbitrary basis changes).
Theorem E.16. H n (C) = 0 for all n > 0.
Proof. We will use a standard method of proving vanishing cohomology results, namely con-
tracting homotopy. Let
                                                                                                               c    a1        an 1
                                                                                                                         .....
                                                                     1 X
            χn : C n → C n−1 ,
                                                       
                                                   χn X a1 ...an−1 = 2
                                                                    D c
                                                                         dc                                    X    a1 :::a   n 1     .        (250)
                                                                                                                         .....
                                                                                                               c              an 1
                                                                                                                    a1

We will show that δχ + χδ = 1 or, more exactly,
                            χn+1 δ n + δ n−1 χn = idC n                                          for n > 0.                                    (251)
If this is true, then any X ∈ Ker δ n can be represented as δ n−1 χn X ∈ Im δ n−1 , hence H n (C) = 0.
    Equation (251) is an immediate corollary of this identity:
                                            (
                                               idC n    if k = 0,
                               χn+1 fkn =        n−1 n                                           (252)
                                               fk−1 χ if k, n > 0.
Let us rewrite it using graphic notation:
                                               c    a1            an
                                                         .....
                        1 X
         k=0:
                        D2 c
                             dc                     X    a1 :::a  n          = Xa1 ...an ,
                                                         .....
                                               c    a1            an
                                                              a a1                   an
                                                                                                               a1           c             an
                                       s                      c        j     ....                                                .....
                        1 X                                                                          1 X
         k=1:
                        D 2 a,c,j
                                  da
                                            dc
                                           da da1
                                                                  X        a2 :::a  n        =
                                                                                                     D2 c
                                                                                                          dc                X     a2 :::a n
                                                              c        y     ....                                                .....
                                                                       j                                                    c
                                                                                                               a1                         an
                                                              a a1                   an

(the case k > 1 is trivial). The equation for k = 0 is also obvious, whereas the one for k = 1
follows from this identity:
                                                                                        a1
                                                    a a1                                     a

                                  X a               c     j                X             a       j    c

                                                          y
                                                                  =                                       ,
                                                    c                                    a       y
                                       j   a              j                  j                   j
                                                                                                      c
                                                    a a1                                     a
                                                                                        a1

where we have used Lemma E.7. (Note that we did not use the pivotal property or the positivity
of the inner product; this sheds some light on why the result holds in a more general setting [30].)


                                                                  93
E.6.3 Technicalities related to the unit and braiding. Let us now take into account
additional structure that was neglected in the above analysis. We will get more variables
and more equations, but the old equations will not change. The new degrees of freedom are
characterized by infinitely small real numbers g, Aa , Ba and Hermitian operators Wcab which
are defined as follows:

                 γ ≈ 1 − ig,          αa′ ≈ (1 − iAa )αa ,    βa′ ≈ (1 − iBa )βa ,         (253)

                                   (R′ )ab   ab            ab
                                        c ≈ Rc (idVcab − iWc ).                            (254)
(Recall that γ is part of the definition of a 1-isomorphism.) It has been previously shown
that any infinitesimal deformation of the associativity constraints F can be compensated by
a suitable basis change Γ. Although α, β, and R may still remain deformed, the problem is
reduced to the case where F is fixed. Furthermore, any infinitesimal basis change not affecting
F has the form (242), hence α, β, or R are not altered either. The only parameter to tune is
γ ≈ 1 − ig.
    Let us first show that any permissible deformation of α and β is trivial, where “permissible”
means satisfying the triangle equations and “trivial” means satisfying Eq. (240). Taken to an
infinitesimal form, the first triangle equation (see Fig. 19a) and Eq. (240) read:

               Ax = Bw     for all x, w;          g + Aa = g + Ba = 0 for all a.           (255)

Clearly, the first condition implies the second if we put g = −A1 .
     Thus we may assume that the whole fusion theory, i.e., F , α, and β are fixed. It remains to
show that the braiding deformation W vanishes, provided it satisfies an infinitesimal version of
the hexagon equations. Instead of using the hexagon equations directly, we will rely on the fact
that braiding defines an isomorphism between the given fusion theory A and the theory A′ in
which left and right are changed. Thus (Rcab )−1 (R′ )ab
                                                      c is an automorphism of A. It follows that
δ 2 W = 0, hence
                                          ab
                            Wcab = δ 1 X c = (Xb − Xc + Xa )idVcab .
for some X ∈ C 1 . It is important that the right-hand side is a scalar times the identity, which
enables us to calculate the deformation of Rcba Rcab = θaθcθb easily:

                                θc′      θc                        
                                ′   ′
                                      ≈       1 − 2i(Xb − Xc + Xa ) .
                               θa θb    θa θb

But the topological spin is rigid due to Vafa’s theorem, hence Xb − Xc + Xa = 0.

E.7    Categorical formalism (aside)
Categories and functors are the language used by mathematicians to describe fusion, braiding,
and related concepts. I originally tried to write an exposition of the theory of anyons using
this formalism, but found it too awkward. I still think that functors are necessary for the
understanding of phase transitions and other advanced properties of anyonic systems, but most
things can be explained in more elementary terms. This section is a remainder of the abandoned
plan. Please be warned that these notes are very incomplete, e.g., there is no discussion of

                                                 94
duality and related concepts: rigid, pivotal, and spherical categories (not to mention that we
focus on semisimple categories — this restriction is natural for the intended applications).
    Let us outline the main elements of the theory. An abstraction called tensor category
generalizes the notion of fusion theory. While anyonic fusion has a compact description in terms
of basic data, a category is a huge collection of “objects” related by “morphisms”. However,
these relations form a regular structure that does not leave much freedom of choice. A rather
trivial example is the category Hilb, whose objects are all possible finite-dimensional Hilbert
spaces and the morphisms are all linear maps. A more interesting category Rep(G) is defined
as follows: the objects are finite-dimensional unitary representations of a compact group G and
the morphisms are intertwiners. We may also think of a fusion theory as a category: the objects
are finite sequences of particle labels, and the morphisms between (b1 , . . . , bm ) and (a1 , . . . , ak )
are fusion/splitting operators, i.e., elements of the space Vba11...b
                                                                  ...ak
                                                                     m
                                                                        . Another way to turn a fusion
theory into a category will be described later.
    By definition, a tensor category is equipped with an operation ✷ that is analogous to fusion.
The role of the vacuum sector is played by a special object 1. In the categories Hilb and Rep(G),
the operation ✷ is the usual tensor product and 1 is the set of complex numbers C regarded
as a one-dimensional space or the trivial representation of G.
    Yet another example: the matrix category Mat m,m . In this category,27 objects are m × m
matrices whose entries are finite-dimensional complex linear spaces, morphisms between matri-
ces are entrywise linear maps, and
                                                                    (
                                 M                                       C if j = k,
                   (A ✷ B)jl =        Ajk ⊗ Bkl ,        1jk =                                      (256)
                                   k
                                                                         0 if j 6= k.

(If the matrix entries are finite-dimensional Hilbert spaces, we use the notation Mat †m,m because
in this case each morphism has a Hermitian adjoint.) Note that (A ✷ B) ✷ C = A ✷ (B ✷ C)
and A ✷ 1 = A = 1 ✷ A; tensor categories with this property are called strict. In general,
the equalities are replaced by isomorphisms F , α, and β satisfying the pentagon and triangle
equations.
    A tensor functor is a map from one tensor category to another, a classic example being
the embedding Rep(G) → Hilb. Tensor functors have some physical applications, such as
transformations of particles by global symmetries (see Appendix F). They are also related
to the gauge freedom in the description of anyonic fusion, cf. Eqs. (239), (240), and (242).
However, our main goal is to understand the status of the isomorphisms F , α, β. To this end,
we will find an embedding of an arbitrary tensor category into a strict one by a tensor functor
that preserves distinction between morphisms (such functors are called faithful ). In particular,
any unitary fusion theory with label set M embeds into the matrix category Mat †M,M . The
embedding theorem implies
MacLane’s coherence theorem: All morphisms composed of F , α, β and having the same
source and target are equal.
Indeed, in the strict category the source and the target are the same object, and any composition
of F , α, and β is the identity morphism (i.e., equality). Thus all such compositions in the
  27
    The more scientific name for this creature is Cm -mod-Cm , the category of finite-dimensional bimodules over
the algebra Cm (the product of m copies of C).


                                                      95
original category are mapped to the same morphism. Since the functor preserves distinction
between morphisms, the original morphisms are also equal.

E.7.1 The basics of category theory. A category is a collection of objects and mor-
phisms. The set of morphisms from A to B in a category C is denoted by C(A, B).
    Morphisms are anything that can be composed: if f : A → B and g : B → C, then
gf : A → C. It is only required that (hg)f = h(gf ) and that every object A has an identity
morphism idA such that f idA = idB f = f for any f : A → B. (Example: objects are vertices of
a given graph, morphisms are paths of arbitrary length, identity morphisms are paths of length
0.)
    A morphism f : A → B is called an isomorphism if there is a morphism f −1 : B → A such
that f −1 f = idA and f f −1 = idB . Notation for isomorphic objects: A ∼
                                                                        = B.
    For applications in quantum mechanics, the basic example is the category Hilb of finite-
dimensional Hilbert spaces. Among its objects are the set of complex numbers C and the one-
dimensional space corresponding to the first level of a harmonic oscillator. These two spaces
are isomorphic but different. (The isomorphism maps the complex number 1 to a normalized
wavefunction ψ, but this map is not canonical because there is no reason to prefer ψ over −ψ.)
So, it does not generally make sense to ask whether two given objects are equal (unless they are
the same by definition). Morphisms between two given objects may be compared for equality
though. For two objects, X and Y , a reasonable question is whether X ∼    = Y . Of course, two
spaces are isomorphic if and only if they have the same dimension. But we also want to keep
track of isomorphisms, for they may not commute: a sequence of isomorphisms may result in
a nontrivial automorphism u : X → X, u 6= idX . (For Hilbert spaces, it is natural to consider
unitary isomorphisms.)
    The next example has motivation in superselection theory. Let us consider an infinite
spin system which is almost in the ground state, with excitations being allowed only in some
finite region. Quantum states of such a system are classified by superselection sectors. For
each sector a the state belongs to some finite-dimensional Hilbert space Xa , which depends on
specific constraints on the excitations. We are going to consider different sets of constraints
(called “objects”) and transformations from one object to another (called “morphisms”).
Definition E.17. Let M be some set. The category Vec †M is defined as follows.

   • An object X ∈ Vec †M is a collection of finite-dimensional Hilbert spaces (Xa : a ∈ M), of
     which only finitely many are nonzero.

   • A morphism f : X → Y is a collection of linear maps fa : Xa → Ya (for each a ∈ M).
     The identity morphism idX : X → X consists of the unit operators acting in Xa .

   • Additional structure: The set Vec †M (X, Y ) of morphisms from X to Y is a complex linear
     space. For any f : X → Y we define the adjoint morphism f † : Y → X such that
     (f † )a = (fa )† .

A unitary isomorphism is an isomorphism f such that f −1 = f † .
An simplified version of this construction is the category Vec M : we use complex linear spaces
instead of Hilbert spaces and do not consider adjoint morphisms.


                                              96
   For each a ∈ M we define the object [a] such that [a]a = C and [a]b = 0 for b 6= a. Objects
isomorphic to [a] are called simple. For any object Y ,
                                                        
                                      Ya = Vec †M [a], Y .                               (257)

From the physical perspective, simple objects correspond to quantum states (e.g., a particle
pinned to a point), whereas [a] is a reference state in the given superselection sector. For
a more formal example, consider the category Rep(G) whose objects are finite-dimensional
unitary representations of a compact group G and whose morphisms are intertwiners. Let M
be the set of irreps considered up to isomorphism, and let [a] be a particular irrep in the given
isomorphism class. Then we may identify the category A = Rep(G) with Vec †M this way:
   def         
Ya = A([a], Y .

Remark E.18. Our definition of Vec M and Vec †M resembles the construction of a vector space
using coordinates. An invariant characterization is also possible, though somewhat complicated.
When the label set M is unspecified, Vec M is called a semisimple C-linear category, and Vec †M
is called a unitary category.
   The concepts of functor and natural morphism are central in category theory. They are ex-
tremely general and therefore hard to grasp. We will try to illustrate them by simple examples,
which are still rather abstract. More meaningful (though less direct) examples can be found in
the next subsection.
Definition E.19. A functor F : A → B maps each object A of the category A to an object
F (A) of the category B and each morphism f : A → A′ to a morphism F (f ) : F (A) → F (A′ )
such that
                      F (f2 f1 ) = F (f2 ) F (f1 ), F (idA ) = idF (A) .
A morphism (or natural transformation) between two functors F , G : A → B is a collection h
of morphisms hA : F (A) → G(A) such that for any f : A → A′ this diagram commutes

                                               F (f )
                                      F (A)             / F (A′ )

                                      hA                        hA′                        (258)
                                              G(f )
                                                            
                                       G(A)             / G(A′ )


    We have already mentioned one example of a functor, namely the embedding F : Rep(G) →
Hilb. Acting on morphisms, it maps the set of intertwiners to the set of all linear maps between
two representation spaces. A natural morphism h : F → F may be constructed as follows: hA
is the action of some fixed group element on the representation space of A. Indeed, for this
particular choice of the functors F = G the commutative diagram (258) simply says that F (f )
is an intertwiner.
Example E.20. Let H be a finite-dimensional Hilbert space. We define a unitary functor
H : Hilb → Hilb by tensoring with H on the left (notation: H = [H ⊗]):
                                def                                   def
                          H(A) = H ⊗ A,                   H(f ) = idH ⊗ f.

                                                97
A linear map u : H → G between two spaces defines a natural morphism U = [u ⊗] between
the corresponding functors:
                                      def
                                   UA = u ⊗ idA .
   The functor H = [H ⊗] has some special properties, namely the map f 7→ H(f ) is linear
and H(f † ) = (H(f ))† . Such functors are called unitary.
Proposition E.21.
  1. Any unitary functor F : Hilb → Hilb is naturally isomorphic to the left-tensoring functor
     [H ⊗] for some space H, namely H = F (C). This isomorphism is unitary.

  2. Any natural morphism U : [G ⊗] → [H ⊗] has the form [u ⊗], where u = UC .
Proof. The idea is very simple: any space is a direct sum of one-dimensional spaces, any one-
dimensional space is isomorphic to C, therefore F and U are completely characterized by their
action on C. Let us go through the detail to see how the formalism works.
    1. Let A be an arbitrary finite-dimensional Hilbert space. Elements of A may be associated
with morphisms C → A. An orthonormal basis corresponds to a set of morphisms ψj : C → A
                                 P
such that ψk† ψj = δkj idC and j ψj ψj† = idA . Since F is a unitary functor,
                                                    X
                  F (ψk )† F (ψj ) = δkj idF (C) ,      F (ψj ) F (ψj )† = idF (A) .
                                                     j

The same is true for the functor H = [F (C) ⊗]. We define a morphism hA : F (A) → H(A) as
follows:                               X
                                 hA =     H(ψj ) hC F (ψj )† ,
                                            j

where hC : F (C) → H(C) = F (C) ⊗ C is an equality (indeed, X = X ⊗ C for any space X).
It is obvious that h†A hA = idF (A) and hA h†A = idH(A) , hence hA is a unitary isomorphism. To
show that h is natural, consider another object A′ with an orthonormal basis {ψj′ } and a linear
          P
map f = j,k cjk ψj′ ψk† , where cjk ∈ C. It is easy to check that
                                      X
                         hA′ F (f ) =    cjk H(ψj′ ) hC F (ψk )† = H(f ) hA .
                                      j,k

    2. Let G = [G ⊗] and H = [H ⊗]. For an arbitrary object A with an orthonormal basis
{ψj } we have UA G(ψj ) = H(ψj ) UC (due to the naturality of U). Hence
                                                !
                                 X            †
                                                     X
        UA = UA idG(A) = UA         G(ψj )G(ψj ) =       H(ψj ) UC G(ψj† ) = UC ⊗ idA .
                                  j                      j




    Adding another level of abstraction, we can reformulate Proposition E.21 as follows: The
category Fun † (Hilb, Hilb) of unitary functors from Hilb to Hilb is isomorphic to the category
Hilb. (One may replace Hilb by the category of finite-dimensional complex linear spaces, omit-
ting the unitarity condition.) By analogy, we obtain the following result.

                                                98
Proposition E.22. The category Fun † (Vec †M , Vec †N ) is isomorphic to the category Mat †N,M
whose objects are N × M matrices of finite-dimensional Hilbert spaces with a finite number of
nonzero entries in each column and whose morphisms are entrywise linear maps between such
matrices. (If M is finite, then Mat †N,M ∼     †
                                         = Vec N ×M .)

E.7.2 Fusion in categorical terms. Fusion theory may be formulated as additional struc-
ture on the category C = Vec †M . Let us assume that the the label set M contains a special
element 1 and that Vcab , Fuabc , αa , βa are defined and satisfy the pentagon and triangle equations
as well as unitarity conditions. If in addition M is finite and the duality axiom on page 74
holds, then the resulting construction is called unitary fusion category. (For a general definition
of fusion category see Ref. [30].)
    The use of categorical formalism has mathematical as well as physical motivation. Let A
and B be spatially confined excitations such that A is located on the left of B. Each excitation
may be described by an object in the category C. If we consider both excitations together, we
will obtain a new object, A ✷ B, which may be called “physical tensor product”. If A and B
do not have local degrees of freedom, i.e., A ∼      = [a], B ∼ = [b], then (A ✷ B)c ∼= Vcab . A nice
property of the physical tensor product is that (A ✷ B) ✷ C = A ✷ (B ✷ C) (provided A, B,
and C are arranged on the line in that particular order). Mathematically, the operation ✷ is
only associative up to a canonical isomorphism, but we will find some abstract representation
of objects in which the isomorphism becomes an equality.
    The tensor product of two objects, A, B ∈ C is defined by the equation
                                                   M
                                    (A ✷ B)c =         Vcab ⊗ Aa ⊗ Bb .                         (259)
                                                    a,b


This operation is neither commutative nor a priory associative. Different ways to multiply
several objects may be described by parenthesis structures, or trees. For example,

                   a       b   c
                                                                         M
                       e           :             [a] ✷ [b] ✷ [c]     =          Veab ⊗ Vuec .
                                                                u
                                                                            e
                           u

   The operation ✷ is a functor, meaning that for any morphisms f : A → A′ and g : B → B ′
there is a morphism f ✷ g : A ✷ B → A′ ✷ B ′ such that

                (f2 f1 ) ✷ (g2 g1 ) = (f2 ✷ g2 )(f1 ✷ g1 ), idA ✷ idB = idA✷B .            (260)
                                                                            P
(The tensor product of morphisms is defined in the obvious way: (f ✷g)c = a,b idVcab ⊗fa ⊗gb .)
   We may define a unitary isomorphism between (A ✷ B) ✷ C and A ✷ (B ✷ C):
                                                         X
  FA,B,C : (A ✷ B) ✷ C → A ✷ (B ✷ C),         FA,B,C u =      Fuabc ⊗ idAa ⊗ idBb ⊗ idCc , (261)
                                                                    a,b,c


where Fuabc is the associativity map (177). Similarly,

                               αA : A → A ✷ [1],              βA : A → [1] ✷ A                  (262)


                                                      99
(the definition is obvious). It is important that the isomorphisms FA,B,C , αA , βA are natural,
i.e., for any morphisms f : A → A′ , g : B → B ′ , and h : C → C ′ we have
                                                               
                         FA′ ,B′ ,C ′ (f ✷ g) ✷ h = f ✷ (g ✷ h) FA,B,C ,
                                                                                          (263)
                        αA′ f = (f ✷ id[1] ) αA ,   βA′ f = (id[1] ✷ f ) βA .

Proposition E.23. The functor property (260) and the naturality (263) imply all quadrilateral
identities of the tree calculus.
Indeed, there are two kinds of such identities. In the example shown in Fig. 17b, one of the
commuting moves occurs inside a subtree descending from the other. The inner move plays the
role of f in the naturality condition. If both moves occur in disjoint subtrees, one should use
the functor property.

E.7.3 Main definitions. Among things we are going to define, tensor category is just a
general formulation of properties of the operation ✷. Tensor functor is a new concept though.
For an elementary but important example, let the label types and fusion spaces be fixed but the
associativity constraints vary. Given two sets of associativity constraints, we may ask whether
they are equivalent up to a basis change, cf. Eqs. (239) and (240). This type of equivalence
is a special case of tensor functor. Note that two basis transformations may differ by trivial
factors, cf. Eq. (242); the corresponding tensor functors are said to be naturally isomorphic.
Definition E.24. A tensor category Cˆ is a category C endowed with a functor ✷ : C × C → C,
a special object 1 ∈ C, and natural isomorphisms

   FA,B,C : (A ✷ B) ✷ C → A ✷ (B ✷ C),                     αA : A → A ✷ 1,             βA : A → 1 ✷ A   (264)

such that the following diagrams (variants of the pentagon equation in Fig. 17a and the triangle
equation in Fig. 19a) commute:

                              FX✷Y,Z,W
  ((X ✷ Y ) ✷ Z) ✷ W                      / (X ✷ Y ) ✷ (Z ✷ W )
                                                            XXXXX F
                                                                 XXXX,Y,Z✷W
                                                                     XXXXX                              (265)
                                                                          XXXXX
                                                                               +
                FX,Y,Z ✷idW                                                      X ✷ (Y ✷ (Z ✷ W ))
                                                                  idX ✷FY,Z,Wffffff3
                                                                         ff
                                                                    fffff
                             FX,Y ✷Z,W                        fffff
  (X ✷ (Y ✷ Z)) ✷ W                       / X ✷ ((Y ✷ Z) ✷ W )


                                                       X ✷W
                                                          G
                                                       w      GG
                                           αX ✷idW www           GGidX ✷βW
                                                 ww
                                                   w                GG
                                                                      GG                                (266)
                                              {ww      FX,1,W           #
                                   (X ✷ 1) ✷ W                  / X ✷ (1 ✷ W )

The tensor category Cˆ is called strict if FA,B,C , αA , βA are equalities. It is called semisimple
if the base category C is Vec M . It is called unitary if C = Vec †M , the functor ✷ is unitary, and
the isomorphisms F , α, β are unitary.


                                                         100
    Semisimple tensor categories admit a compact description in terms of “basic data”, which
is just slightly more general than that of a fusion theory. Indeed, by analogy with Proposi-
tions E.21 and E.22 one can show that any functor of two arguments, ✷ : Vec M ×Vec M → Vec M
is given by a set of finite-dimensional spaces Vcab . However, the unit object is not necessarily
simple, an example being the category Mat M,M or Mat †M,M with the multiplication rule and the
unit (256). (Note that these tensor categories are strict.) In physical terms, the nonsimplicity
of the unit means that the vacuum is not unique; thus simple objects in Mat †M,M are boundaries
between vacua.
Definition E.25. Let Cˆ = (C, ✷, 1, F, α, β) and Cˆ′ = (C ′ , ✷′ , 1′ , F ′ , α′ , β ′) be tensor categories.
A tensor functor Ĝ : Cˆ → Cˆ′ is a functor G between the corresponding base categories, plus two
natural isomorphisms,28
                                 ΓA,B : G(A) ✷′ G(B) → G(A ✷ B),                                     γ : 1′ → G(1),                            (267)
such that the the following diagrams commute:
                  ΓX✷Y,Z                     ΓX,Y ✷′ idG(Z)                                                      
   G (X ✷ Y ) ✷ Z o       G(X ✷ Y ) ✷′ G(Z) o                                                        G(X) ✷′ G(Y ) ✷′ G(Z)
                          G(FX,Y,Z )                                                                                         ′
                                                                                                                            FG(X),G(Y ),G(Z)
                                                                                                                                               (268)
                 ΓX,Y ✷Z
                                            idG(X) ✷′ ΓY,Z                                                            
   G X ✷ (Y ✷ Z) o        G(X) ✷′ G(Y ✷ Z) o                G(X) ✷′ G(Y ) ✷′ G(Z)

                                α′                                                                   β′
                                 G(X)                                                                 G(X)
            G(X)                            / G(X) ✷′ 1′                                   G(X)                  / 1′ ✷′ G(X)

         G(αX )                                       idG(X) ✷′ γ                       G(βX )                                   γ✷′ idG(X)    (269)
                                ΓX,1                                                               Γ1,X                   
          G(X ✷ 1) o                        G(X) ✷′ G(1)                                G(1 ✷ X) o               G(1) ✷′ G(X)
The tensor functor Ĝ = (G, Γ, γ) is called unitary if all three of its components are unitary.
   This definition seems complicated, but basically it says the following: we may identify
G(A ✷ B) with G(A) ✷′ G(B) and G(1) with 1′ (by means of Γ and γ) so that
                                         ′                                             ′                           ′
                           G(FX,Y,Z ) = FG(X),G(Y ),G(Z) ,                   G(αX ) = αG(X) ,            G(βX ) = βG(X) .
Remark E.26. A lax tensor functor is defined likewise, but ΓA,B and γ are not required to be
isomorphisms. In physics, this construction describes a situation in which theory Cˆ is obtained
from Cˆ′ as a result of Bose-condensation, cf. note 9 on page 44.
Definition E.27. A morphism between two tensor functors, Ĝ = (G, Γ, γ) and Ĥ = (H, Φ, ϕ)
is a natural morphism h : G → H satisfying these additional commutation relations:
                                                 ΓX,Y
                                 G(X ✷ Y ) o                G(X) ✷′ G(Y )                               G(1) gN γ
                                                                                                                     NNN
                                                                                                                        NN
                                                                             ✷′ h                                          ′                   (270)
                                 hX✷Y                                   hX          Y                   h1
                                                                                                                       ppp1
                                                ΦX,Y                                                           pw p
                                                                                                                    ϕ
                                H(X ✷ Y ) o                 H(X) ✷′ H(Y )                               H(1)

  28
       The direction of arrows is a convention, which is slightly inconvenient for our purposes.

                                                                             101
The morphism h is called a (unitary) isomorphism if all the maps hX are (unitary) isomor-
phisms.
   Let us see how these definitions work for fusion theories. Let C and C ′ have label sets M and
M , respectively. We already know that an arbitrary functor G : C → C ′ is described by some
  ′

matrix (Gaa′ : a ∈ M, a′ ∈ M ′ ) of finite-dimensional Hilbert spaces. Then the supplementary
components of the tensor functor, Γ and γ are characterized by some unitary linear maps
                   M                              M
                          ′ a′ b′
           Γab
             c ′ :     (V  ) c ′  ⊗ G a
                                      a′ ⊗ G b
                                             b′ →    Vcab ⊗ Gcc′ ,      γ : C → G11′ .       (271)
                     a′ ,b′ ∈M ′                         c∈M

Note that since the original γ (the map form 1′ to G(1)) is an isomorphism, G1a′ = 0 if a′ 6= 1′ .
Eqs. (268) and (269) impose certain algebraic relations on Γab    c′ and γ. A unitary isomorphism
between two tensor functors is described by a set of unitary maps haa′ : Gaa′ → Haa′ satisfying
the equations that follow from Eq. (270).
    Returning to the example of basis transformations, let C = C ′ , ✷ = ✷′ , but possibly
F 6= F ′ , α′ 6= α, β ′ 6= β. Thus we fix the label types and fusion spaces while allowing different
associativity relations. Let us further assume that G is the identity functor, i.e., Gaa = C and
Gaa′ = 0 if a′ 6= a. In this case, Γab                                                  ab      ′ ab
                                    c is just a unitary operator acting in the space Vc = (V )c ,
and γ is a phase factor. Then Eqs. (268) and (269) become (239) and (240), respectively. In this
setting, an isomorphism between two tensor functors is described by unital complex numbers
ha satisfying Eq. (242).

E.7.4 The embedding theorem. Now, we will see the “abstract nonsense” in action.
While we manipulate with definitions, some combinatorial magic happens behind the scenes.
Basically, we turn pentagons into rectangles; this process may be viewed as a proof that the
2-skeleton of the Stasheff polytope is simply connected.
Theorem E.28. For any tensor category Cˆ = (C, ✷, 1, F, α, β) there exists a strict tensor cat-
egory Ĉ ′ = (C ′ , ✷′ , 1′ ) and a faithful tensor functor Ĝ = (G, Γ, γ) from Cˆ to Ĉ ′ (where “faithful”
means that the images of distinct morphisms are also distinct).
Proof (borrowed from Ref. [94]). Let C ′ be the category of functors from C to itself, ✷′ the
operation of composing two functors (usually denoted by ◦), and 1′ the identity functor. We
                                                         def
assume that functors act on the left, i.e., (X ◦ Y )(W ) = X(Y (W )). For any object X we set
                                def
G(X) = [X ✷], i.e., G(X)(W ) = X ✷ W . The isomorphism ΓX,Y between two functors may
also be defined in terms of its action on a test object W :
                                                                 def
                                                                  −1
ΓX,Y : [X ✷] ◦ [Y ✷] → [(X ✷ Y ) ✷],                 ΓX,Y (W ) = FX,Y,W : X ✷ (Y ✷ W ) → (X ✷ Y ) ✷ W.
Finally, we define
                                                               def
                             γ : idC → [1 ✷],         γ(W ) = βW : W → 1 ✷ W.
      Now we simply rewrite Eqs. (268) and (269), applying them to W :
                           FX✷Y,Z,W                       FX,Y,Z✷W
       ((X ✷ Y ) ✷ Z ✷ W             / (X ✷ Y ) ✷ (Z ✷ W )          / X ✷ (Y ✷ (Z ✷ W ))

                     FX,Y,Z ✷idW
                                  FX,Y ✷Z,W                           idX ✷FY,Z,W
        (X ✷ (Y ✷ Z)) ✷ W                      / X ✷ ((Y ✷ Z) ✷ W )                  / X ✷ (Y ✷ (Z ✷ W ))


                                                        102
        X ✷W                     X ✷W                                     X ✷W                         X ✷W
    αX ✷idW                               idX ✷βW                     βX ✷idW                                  βX✷W
                   FX,1,W                                                               F1,X,W          
     (X ✷ 1) ✷ W             / X ✷ (1 ✷ W )                           (1 ✷ X) ✷ W                   / 1 ✷ (X ✷ W )

These are the conditions we need to check. But the first and the second of them are identical to
Eqs. (264) and (265), respectively. The third condition is a different type of triangle equation,
which is shown in Fig. 19b. It follows from the standard one by Lemma E.2.
    To see that the functor G is faithful, we set W = 1 and observe that a morphism h : X → Y
is mapped to G(h)(1) = h ✷ id1 : X ✷ 1 → Y ✷ 1. Thus,
                                                   
                                      αY−1 G(h)(1) αX = h
(due to the naturality of α). It follows that distinct morphisms remain distinct.
  Note that if C = Vec †M , then C ′ = Mat †M,M . The functor G takes a simple object a to the
matrix whose [b, c] entry is Vcab .

E.7.5   Braiding. Let us be brief and just give some definitions.
Definition E.29. A braiding in a tensor category Cˆ = (C, ✷, 1, F, α, β) is a collection of iso-
morphisms
                                 RA,B : A ✷ B → B ✷ A                                     (272)
which are natural with respect to A and B, i.e., for any morphisms f : A → A′ , g : B → B ′
this square commutes:
                                                      f ✷g
                                            A✷B              / A′ ✷ B ′

                                          RA,B                        RA′ ,B′                                         (273)
                                                     g✷f         
                                       B✷A        / B ′ ✷ A′

It is also required that the following diagrams are commutative:
                                                     FY,X,Z
                                (Y ✷= X) ✷ Z                   / Y ✷ (X ✷ Z)
                                                                        DD
                                   zz                                     DD
                      RX,Y ✷idZ zzz                                         DDidY ✷RX,Z
                                z                                             DD
                              zz                                                DD
                            zz                                                    !
                   (X ✷ Y ) ✷ Z                                                     Y ✷ (Z ✷ X)                       (274)
                             DD                                                        =
                               DD                                                    zz
                                 DDFX,Y,Z                                  FY,Z,X zzz
                                   DD                                             z
                                     DD                                         zz
                                       !             RX,Y ✷Z                  zz
                                X ✷ (Y ✷ Z)                    / (Y ✷ Z) ✷ X


                                                     FY,X,Z
                                (Y ✷ X) ✷ Z                    / Y ✷ (X ✷ Z)
                                      =                                 DD
                      R−1
                                    zz                                    DD
                       Y,X ✷id Z zz
                                   z                                        DDidY ✷R−1
                                                                                    Z,X
                                z                                             DD
                             zzz                                                DD
                            z                                                     !
                   (X ✷ Y ) ✷ Z                                                     Y ✷ (Z ✷ X)                       (275)
                             DD                                                        =
                               DD                                                    zz
                                 DDFX,Y,Z                                  FY,Z,X zzz
                                   DD                                             z
                                     DD                                         zz
                                       !             R−1
                                                      Y ✷Z,X
                                                                              zz
                                X ✷ (Y ✷ Z)                    / (Y ✷ Z) ✷ X


                                                      103
Definition E.30. A braided tensor functor is a tensor functor that commutes with braiding.
More exactly, let Cˆ = (C, ✷, 1, F, α, β) and Cˆ′ = (C ′ , ✷′ , 1′ , F ′ , α′ , β ′) be tensor categories fur-
nished with braidings R and R′ , respectively. A tensor functor Ĝ = (G, Γ, γ) from Cˆ to Cˆ′ is
called braided if the following diagram commutes:
                                                   ΓA,B
                                     G(A ✷ B) o             G(A) ✷′ G(B)
                                  G(RA,B )                            R′G(A),G(B)                       (276)
                                                  ΓB,A           
                                     G(B ✷ A) o             G(B) ✷′ G(A)

Example E.31. Let Cˆ be an arbitrary braided tensor category and let Cˆ′ be defined as follows:

  C ′ = C,   A ✷′ B = B ✷ A,        1′ = 1,       ′
                                                 FX,Y,Z    −1
                                                        = FZ,Y,X ,        α′ = β,   β ′ = α,    ′
                                                                                               RA,B = RB,A .
                                                            −1
Then the identity functor G = idC supplemented with ΓA,B = RA,B and γ = id1 is a braided
                    ˆ    ˆ′
tensor functor from C to C . (We omit the proof.)


Appendix F:                 Weak symmetry breaking
A complete, yet to be discovered description of topological quantum order must include fusion
and braiding rules (characterized by a unitary braided fusion category (UBFC), see Appendix E)
as well as symmetries of the underlying microscopic Hamiltonian. The no-symmetry case was
considered in Sec. E.5. On the other hand, in our study of Abelian anyons in the honeycomb
lattice model (see Sec. 5.2) we observed a rather strange property: the translation by a lat-
tice vector interchanges two superselection sectors. This phenomenon may be called a “weak
breaking” of the translational symmetry.
    Let us now consider an arbitrary two-dimensional many-body system with a symmetry
group G. For simplicity, we assume that the system consists of spins (or other bosonic degrees of
freedom) rather than fermions. There are several ways in which the ground state can break the
symmetry that is present in the Hamiltonian. First, the symmetry may be spontaneously broken
in the usual sense, i.e., there may be a local order parameter. If such an order parameter does
not exist, we may look for finer signs of symmetry breaking, in particular, for nontrivial action
of G on superselection sectors. Such an action is described by a homomorphism ω1 : G → Γ1 ,
where Γ1 is some finite group defined below.
    But even if G does not permute the superselection sectors, there is still possibility for subtle
symmetry-breaking properties, some of which were studied by Wen [95, 96] under the rubric
of “projective symmetry groups” (PSG). While Wen’s approach is rather indirect, one may
instead investigate the action of symmetry transformations on superselection sectors. For a
simple example, let us consider the Hamiltonian (3) with Jm < 0 (note the analogy with Wen’s
model [96]). The ground state of this Hamiltonian may be obtained from the Jm > 0 state
by putting an m-particle on every plaquette (so that any missing m-particle would now be
regarded as an excitation). Therefore an e-particle picks up the phase factor −1 when it winds
around a plaquette. It follows that the translations by two basis lattice vectors commute up to
a minus sign when we consider their action on the nontrivial superselection sector e.

                                                      104
 Effective dimension
 in which the sym-          Mathematical description                     Examples
 metry is broken
           0            A local order parameter taking       Ferromagnet; Neel phase
                        values in the coset space G/H,
                        where H is a subgroup of G
           1            Nontrivial action of the symme-      Abelian phases Ax , Ay , Az in the
                        try group on superselection sec-     honeycomb lattice model
                        tors, which is characterized by a
                        homomorphism ω1 : G → Γ1
           2            The action of G on each super-       Hamiltonian (3) with Jm < 0;
                        selection sector a is described by   a number of models in [95, 96]
                        a central extension Ga ; the whole
                        set of extensions is characterized
                        by an element ω2 ∈ H 2 (BG, Γ2 )
           3
           4            Effective topological action for a Integer quantum Hall effect
                        G-gauge field; such actions are
                        classified by H 4 (BG, Z)
      Table 6: Four levels of symmetry breaking in a two-dimensional quantum system.

    Mathematically, the up-to-sign commutation means that the translational group G = Z × Z
is replaced by a central extension Ge → G with kernel Z2 . If general, central extensions
are classified by the cohomology group H 2 (G, U(1)). For each superselection sector a we get
an extension Ga . The whole collection of extensions is characterized by a cohomology class
ω2 ∈ H 2 (G, Γ2 ), where Γ2 is some finite Abelian group (see below).
    However, this is not the end of the story. Even without anyonic excitations (or if anyons
exist but do not complicate the group action in any way), the system may have nontrivial
properties such as the integer quantum Hall effect. The latter is described by a Chern-Simons
term in the effective action for the electromagnetic field. Dijkgraaf and Witten [97] showed
that a general topological action for a gauge field in 2 + 1 dimensions is characterized by an
element of the cohomology group H 4 (BG, Z), where BG is the classifying space of G. (The
group G is assumed to be compact.) An analogue of the Chern-Simons action exists even for
finite groups. In this case, BG = K(G, 1) (where K(G, n) is the Eilenberg-MacLane space)
and H 4 (BG, Z) ∼ = H 3 (G, U(1)) (where the first H refers to the topological cohomology and the
second to the group cohomology).
    The four-level classification of symmetry-breaking phenomena is summarized in Table 6. It
has the flavor of topological obstruction theory (see e.g. [98]). One may hypothesize that there
is a somehow relevant topological space Y such that π1 (Y ) = Γ1 , π2 (Y ) = Γ2 , π3 (Y ) = 0,
π4 (Y ) = Z, and all higher homotopy groups vanish. We now argue that the analogy with
obstruction theory has precise mathematical meaning in dimensions 1 and 2.
    Suppose that the symmetry remains unbroken in dimension 0, but can be removed (if so
is desired) by introducing a small perturbation to the Hamiltonian. That is obviously possible
if the system consists of spins, while the Z2 symmetry associated with fermions can never be

                                              105
removed. The properties that survive the perturbation are described by a unitary modular
category (UMC) A and a chiral central charge c− , but we ignore the latter.
    The action of the symmetry group G on superselection sectors can be described algebraically
as well as topologically. To begin with algebra, consider the 2-groupoid Γ = Aut(A). It has
a single object, the morphisms are invertible unitary braided tensor functors A → A, and the
2-morphisms are natural isomorphisms between such functors.29 If the functors are considered
up to isomorphisms, we obtain the group Γ1 that was mentioned above. The Abelian group Γ2
consists of all automorphisms of the identity functor. Note that Γ1 may act on Γ2 in a nontrivial
way. The 2-groupoid Γ is characterized by this action and a cohomology class h ∈ H 3 (Γ1 , Γ2 ).
    On the topological side, one can consider the classifying space X = BΓ, which is a topo-
logical space with a basepoint. I claim that X is connected, π1 (X) = Γ1 , π2 (X) = Γ2 , and
all higher homotopy groups vanish. Furthermore, the action of G on superselection sectors is
described by a continuous map f : BG → X defined up to a homotopy (some explanation is
given below). One may ask if f is homotopic to a constant map. The first obstruction to such
a homotopy is given by a homotopy class of maps ω1 : BG → K(Γ1 , 1); such classes are in
one-to-one correspondence with group homomorphisms G → Γ1 . If this obstruction vanishes,
one can define ω2 ∈ H 2 (BG, Γ2 ) = H 2 (G, Γ2 ). If ω2 = 0, then f is homotopic to identity, or
equivalently, the action of G on A is trivial.
    Note that X can be represented as a fibration with base K(Γ1 , 1) and fiber K(Γ2 , 2). Its
structure is characterized by the element h ∈ H 3 (Γ1 , Γ2 ). If h 6= 0, then the fibration does
not have a cross section. In this case, the homomorphism ω1 : G → Γ1 must satisfy a certain
constraint, namely the inverse image of h by ω1 must vanish. Thus, some seemingly possible
types of symmetry breaking in dimension 1 may be forbidden due to an obstruction in dimension
2.
    In conclusion, I conjecture a “physical” interpretation of the space X and the map f .
Specifically, X parametrizes quantum states in the universality class described by the unitary
modular category A. Each point of X is associated with a set of states that differ from each
other locally; thus all finite-energy excitations of a given gapped Hamiltonian are represented
by the same point. The original unperturbed system corresponds to some x0 ∈ X. To define
the map BG → X, let us assume that G is a compact Lie group which acts on each spin
independently according to a faithful representation G → U(m). The Hilbert space of the spin,
Cm may be embedded in a large space CM . Each embedding u has an associated state g(u) ∈ X.
The space E of embeddings is contractible in the limit M → ∞, therefore its quotient with
respect to the natural G-action may be regarded as a model of BG. Furthermore, since x0 is
symmetric, the map g : E → X factors through BG. Thus the map f : BG → X is defined.
Remark F.1. It is not clear how to define the “extended classifying space” Y that has non-
trivial homotopy in dimension 4. One may conjecture that Y = X ×K(Z, 4), but this definition
seems contrived. It may well be the case that the very idea to classify the Chern-Simons action
as symmetry breaking in dimension 4 is wrong. Indeed, the Chern-Simons action is not fully
described by homotopy theory because the fundamental homology class of the source (physical)
manifold is involved.
  29
    As explained to me by Ezra Getzler, higher groupoids may be nicely defined as Kan complexes [99]; this
approach also allows one to endow the morphism sets with topology. In the definition of Γ no topology is
assumed. It would be interesting to see what changes (if anything) when a natural topology is included.



                                                   106
Acknowledgments
During the years this work was in progress I received genuine interest and words of encourage-
ment from John Preskill, Michael Freedman, Mikhail Feigelman, Grigory Volovik, and many
other people. I thank Andreas Ludwig for having convinced me in the importance of the chiral
central charge in the study of topological order. A conversation with Dmitri Ivanov was essential
for understanding the difference between non-Abelian anyons and Majorana vortices in two-
dimensional p-wave superconductors. I also thank Matthew Fisher, Nicholas Read, and Xiao-
Gang Wen for helpful discussions. I am especially grateful to Jean Bellissard who read a prelim-
inary version of the manuscript and made some valuable comments; in particular, he directed
me to Ref. [50]. This work was supported in part by the National Science Foundation under
Grant No. EIA-0086038 and by the Army Research Office under grant No. W911NF-04-1-0236.


References
  [1] J. Bellissard, A. van Elst, H. Schulz-Baldes, “The noncommutative geometry of the quan-
      tum Hall effect,” J. Math. Phys. 35, 5373–5451, (1994), cond-mat/9411052.

  [2] F. Wilczek, “Magnetic flux, angular momentum, and statistics”, Phys. Rev. Lett. 48,
      1144–1146 (1982).

  [3] F. Wilczek, “Remarks on dyons”, Phys. Rev. Lett. 48, 1146–1149 (1982).

  [4] G. Moore, N. Seiberg, “Classical and quantum conformal field theory”, Commun. Math.
      Phys. 123 no. 2, 177–254 (1989).

  [5] E. Witten, “Quantum field theory and the Jones polynomial”, Commun. Math. Phys. 121
      no. 3, 351–399 (1989).

  [6] K. Fredenhagen, K. H. Rehren, B. Schroer, “Superselection sectors with braid group statis-
      tics and exchange algebras, I: General theory”, Commun. Math. Phys. 125 no. 2, 201–226
      (1989).

  [7] J. Fröhlich, F. Gabbiani, “Braid statistics in local quantum field theory”, Rev. Math. Phys.
      2 no. 3, 251–353 (1990).

  [8] R. B. Laughlin, “Anomalous quantum Hall effect — an incompressible quantum fluid with
      fractionally charged excitations,” Phys. Rev. Lett. 50, 1395–1398 (1983).

  [9] L. Saminadayar, D. C. Glattli, Y. Jin, B. Etienne, “Observation of the e/3 frac-
      tionally charged Laughlin quasiparticles”, Phys. Rev. Lett. 79, 2526–2529 (1997),
      cond-mat/9706307.

 [10] R. de-Picciotto, M. Reznikov, M. Heiblum, V. Umansky, G. Bunin, D. Mahalu, “Direct ob-
      servation of a fractional charge”, Nature 389, 162–164 (1997), cond-mat/9707289.

 [11] B. I. Halperin , “Statistics of quasiparticles and the hierarchy of fractional quantized Hall
      states”, Phys. Rev. Lett. 52, 1583–1586 (1984).

                                               107
[12] D. Arovas, J. R. Schrieffer, and F. Wilczek, “Fractional statistics and the quantum Hall
     effect”, Phys. Rev. Lett. 53, 722–723 (1984).

[13] F. E. Camino, W. Zhou, V. J. Goldman, “Direct observation of fractional statistics in two
     dimensions”, cond-mat/0502406.

[14] G. Moore, N. Read, “Nonabelions in the fractional quantum Hall effect,” Nucl. Phys. B
     360, 362–396 (1991).

[15] G. Moore, N. Read, “Fractional quantum Hall effect and nonabelian statistics”,
     hep-th/9202001.

[16] M. B. Hastings, “Lieb-Schultz-Mattis in higher dimensions”, Phys. Rev. B 69, 104431
     (2004), cond-mat/0305505.

[17] P. W. Anderson, “Resonating valence bond: A new kind of insulator?”, Mat. Res. Bull.
     8, 153–160 (1973).

[18] P. W. Anderson, “The resonating valence bond in La2 CuO4 and superconductivity”, Sci-
     ence 235, 1196–1198 (1987).

[19] R. Moessner, S. L. Sondhi, “Resonating valence bond phase in the triangular lattice quan-
     tum dimer model”, Phys. Rev. Lett. 86, 1881–1884 (2001), cond-mat/0007378.

[20] N. Read, B. Chakraborty, “Statistics of the excitations of the resonating-valence-bond
     state”, Phys. Rev. B 40, 7133–7140 (1989).

[21] T. Senthil, M. P. A. Fisher, “Fractionalization in the cuprates: Detecting the topological
     order”, Phys. Rev. Lett. 86, 292–295 (2001), cond-mat/0006481.

[22] D. A. Bonn, J. C. Wynn, B. W. Gardner, Yu-Ju Lin, Ruixing Liang, W. N. Hardy,
     J. R. Kirtley, K. A. Moler, “A limit on spin-charge separation in high-Tc superconductors
     from the absence of a vortex-memory effect”, Nature 414, 887–889 (2001).

[23] R. Coldea, D. A. Tennant, A. M. Tsvelik, Z. Tylczynski, “Experimental realization of
     a 2d fractional quantum spin liquid”, Phys. Rev. Lett. 86, 1335–1338 (2001),
     cond-mat/0007172.

[24] A. Yu. Kitaev, “Fault-tolerant quantum computation by anyons”, Annals of Physics 303
     no. 1, 2–30 (2003), quant-ph/9707021.

[25] S. Doplicher, J. E. Roberts, “Why there is a field algebra with a compact gauge group
     describing the superselection structure in particle physics”, Commun. Math. Phys. 131
     no. 1, 51–107 (1990).

[26] S. Doplicher, J. E. Roberts, “A new duality theory for compact groups” Invent. Math. 98
     no. 1, 157–218 (1989).

[27] M. H. Freedman, M. Larsen, Z. Wang, “A modular functor which is universal for quantum
     computation”, Commun. Math. Phys. 227 no. 3, 605–622 (2002), quant-ph/0001108.

                                             108
[28] T. Einarsson, “Fractional statistics on a torus”, Phys. Rev. Lett. 64, 1995-1998 (1990).

[29] A. Ocneanu, unpublished.

[30] P. Etingof, D. Nikshych, V. Ostrik, “On fusion categories”, math.QA/0203060.

[31] N. Read, E. Rezayi, “Beyond paired quantum Hall states: Parafermions and incom-
     pressible states in the first excited Landau level”, Phys. Rev. B, 59 8084–8092 (1999),
     cond-mat/9809384.

[32] R. W. Ogburn, J. Preskill, “Topological quantum computation”, Lecture Notes in Com-
     puter Science 1509, C. P. Williams (ed.) QCQC’98, pp. 341–356, Springer-Verlag (1999).

[33] J. Preskill, “Fault-tolerant quantum computation”, quant-ph/9712048.

[34] C. Mochon, “Anyon computers with smaller groups”, Phys. Rev. A 69, 032306 (2004),
     quant-ph/0306063.

[35] M. H. Freedman “A magnetic model with a possible Chern-Simons phase”, Commun.
     Math. Phys. 234 no. 1, 129–183 (2003), quant-ph/0110060.

[36] M. Freedman, C. Nayak, K. Shtengel, K. Walker, Z. Wang, “A Class of P, T -Invariant
     Topological Phases of Interacting Electrons”, cond-mat/0307511.

[37] M. Freedman, C. Nayak, K. Shtengel, “Non-Abelian topological phases in an extended
     Hubbard model”, cond-mat/0309120.

[38] B. Douçot, J. Vidal, “Pairing of Cooper Pairs in a Fully Frustrated Josephson Junction
     Chain”, Phys. Rev. Lett. 88, 227005 (2002)cond-mat/0202115.

[39] L. B. Ioffe, M. V. Feigel’man, “Possible realization of an ideal quantum computer in
     Josephson junction array”, Phys. Rev. B 66, 224503 (2002), cond-mat/0205186.

[40] B. Douçot, L. B. Ioffe, M. V. Feigel’man, “Topological order in the insulating Josephson
     junction array”, Phys. Rev. Lett. 90, 107003 (2003), cond-mat/0211146.

[41] B. Douçot, L. B. Ioffe, M. V. Feigel’man, “Discrete non-Abelian gauge theories in two-
     dimensional lattices and their realizations in Josephson-junction arrays”, Phys. Rev. B
     69, 214501 (2004), cond-mat/0302104.

[42] L.-M. Duan, E. Demler,       M. D. Lukin      Phys.   Rev.   Lett.   91,   090402   (2003),
     cond-mat/0210564.

[43] D. J. Thouless, M. Kohmoto, M. P. Nightingale, M. den Nijs, “Quantized Hall conductance
     in a two-dimensional periodic potential,” Phys. Rev. Lett. 49, 405–408 (1982).

[44] J. E. Avron, R. Seiler, B. Simon, “Homotopy and quantization in condensed matter
     physics,” Phys. Rev. Lett. 51, 51–53, (1983).

[45] A. Connes, “Noncommutative Geometry”, Academic Press (1994).


                                             109
[46] G. E. Volovik, “Analog of quantum Hall-effect in a superfluid 3 He film” Zh. Eksp. Teor.
     Fiz. 94 no. 9, 123–137 (1988) (in Russian) [English translation: Sov. Phys. JETP 67,
     1804 (1988)].

[47] G. E. Volovik, V. M. Yakovenko, “Fractional charge, spin and statistics of solitons in su-
     perfluid 3 He film”, J. Phys.: Condens. Matter 1, 5263–5274 (1989).

[48] N. Read, D. Green, “Paired states of fermions in two-dimensions with breaking of parity
     and time reversal symmetries, and the fractional quantum Hall effect,” Phys. Rev. B 61,
     10267 (2000), cond-mat/9906453.

[49] A. M. Tsvelik, “Quantum field theory in condensed matter physics”, Cambridge Univer-
     sity Press, 2nd edition (2003).

[50] E. H. Lieb, “Flux phase of the half-filled band”, Phys. Rev. Lett. 73, 2158–2161 (1994),
     cond-mat/9410025.

[51] B. I. Halperin “Quantized Hall conductance, current-carrying edge states, and the exis-
     tence of extended states in a two-dimensional disordered potential,” Phys. Rev. B 25,
     2185–2190 (1983).

[52] Y. Hatsugai, “Chern number and edge states in the integer quantum Hall effect,” Phys.
     Rev. Lett. 71, 3697–3700 (1993).

[53] H. Schulz-Baldes, J. Kellendonk, T. Richter, “Simultaneous quantization of edge and bulk
     Hall conductivity,” J. Phys. A: Math. Gen. 33 L27–L32 (2000), cond-mat/9912186.

[54] J. Kellendonk, T. Richter, H. Schulz-Baldes, “Edge current channels and Chern numbers
     in the integer quantum Hall effect,” Rev. Math. Phys. 14 no. 1, 87–119 (2002).

[55] G. E. Volovik, “Quantum Hall and chiral edge states in thin 3 He-A film”, Pis’ma v ZhETF
     55 no. 6, 363–367 (1992) [JETP Letters, 55 368–373 (1992)].

[56] C. L. Kane, M. P. A. Fisher, “Quantized thermal transport in the fractional quantum Hall
     effect”, Phys. Rev. B 55, 15832–15837 (1997), cond-mat/9603118.

[57] A. Cappelli, M. Huerta, G. R. Zemba, “Thermal transport in chiral conformal theories
     and hierarchical quantum Hall states”, Nucl. Phys. B 636 no. 3, 568–582 (2002),
     cond-mat/0111437.

[58] U. Sivan, Y. Imry, “Multichannel Landauer formula for thermoelectric transport with ap-
     plication to thermopower near the mobility edge”, Phys. Rev. B 33, 551–558 (1986).

[59] L. Alvarez-Gaume, E. Witten, “Gravitational anomalies”, Nucl. Phys. B 234 no. 2, 269–
     330 (1984).

[60] G. E. Volovik, “The gravitational topological Chern-Simons term in a film of superfluid
     3
       He-A”, Pis’ma v ZhETF 51 no. 2, 111–114 (1990) (in Russian) [English translation:
     JETP Letters 51, 125–128 (1990)].


                                             110
[61] K. H. Rehren, “Braid group statistics and their superselection rules” in The algebraic
     theory of superselection sectors, D. Kastler (ed.) Proceedings Palermo 1989, pp. 333–355,
     World Scientific Publishing (1990).

[62] E. Verlinde, “Fusion rules and modular transformations in 2D conformal field theory”,
     Nucl. Phys. B 300, 360–376 (1988).

[63] P. Di Francesco, P. Mathieu, D. Sénéchal, “Conformal field theory”, Springer (1996).

[64] A. Yu. Kitaev, “Unpaired Majorana fermions in quantum wires”, cond-mat/0010440.

[65] D. A. Ivanov, “Non-Abelian statistics of half-quantum vortices in p-wave superconduc-
     tors”, Phys. Rev. Lett. 86, 268–271 (2001), cond-mat/0005069.

[66] N. Reshetikhin, V. G. Turaev, “Invariants of 3-manifolds via link polynomials and quan-
     tum groups”, Inventiones Mathematicae 103 no. 3, 547–597 (1991).

[67] K. Walker, “On Witten’s 3-manifold invariants”, http://canyon23.net/math/ (1991).

[68] V. G. Turaev, “Quantum invariants of knots and 3-manifolds” (de Gruyter Studies in
     Mathematics 18), de Gruyter (1994).

[69] V. Kalmeyer, R. B. Laughlin, “Equivalence of the resonating-valence-bond and fractional
     quantum Hall states”, Phys. Rev. Lett. 59, 2095–2098 (1987).

[70] M. V. Feigel’man, A. Yu. Kitaev, unpublished.

[71] R. B. Laughlin, “Quantized Hall conductivity in two dimensions,” Phys. Rev. B 23, 5632–
     5633 (1981).

[72] J. E. Avron, R. Seiler, B. Simon, “Quantum Hall effect and the relative index of projec-
     tions,” Phys. Rev. Lett. 65, 2185–2189 (1990).

[73] J. E. Avron, R. Seiler, B. Simon, “Charge deficiency, charge transport and comparison of
     dimensions,” Commun. Math. Phys. 159 no. 2, 399–422 (1994), physics/9803014.

[74] J. E. Avron, R. Seiler, B. Simon, “The index of a pair of projections,” J. Func. Analysis
     120, 220–237 (1994).

[75] E. M. Rains, “Correlation     functions    for   symmetrized   increasing   subsequences”,
     math.CO/0006097.

[76] D. A. Rokhsar, S. A. Kivelson, “Superconductivity and the quantum hard-core dimer gas”,
     Phys. Rev. Lett. 61, 2376–2379 (1988).

[77] E. H. Lieb, D. W. Robinson, “ The finite group velocity of quantum spin systems”, Com-
     mun. Math. Phys. 28, 251–257 (1972).

[78] R. Haag, “Local quantum physics”, Springer Verlag, 2nd edition (1996).



                                               111
[79] B. Bakalov, A. Kirillov Jr., “Lectures on tensor categories and modular functors” (Uni-
     versity Lecture Series 21), American Mathematical Society (2001).

[80] C. Kassel, “Quantum groups” (Graduate Texts in Mathematics 155), Springer Verlag
     (1995).

[81] J. Preskill, “Topological quantum computation”, (Chapter 9 of Lecture notes on quantum
     computation), http://www.theory.caltech.edu/people/preskill/ph229/#lecture
     (2004).

[82] S. Mac Lane, “Categories for the working mathematician” (Graduate Texts in Mathemat-
     ics 5), Springer Verlag, 2nd edition (1998).

[83] J. D. Stasheff, “Homotopy associativity of H-spaces” (parts I and II), Trans. Amer. Math.
     Soc. 108, 275–292 and 293–312 (1963).

[84] J.-L. Loday, “Realization of the Stasheff polytope” Arch. Math. (Basel) 83 no. 3, 267–278
     (2004), math.AT/0212126.

[85] V. G. Drinfeld, “Quantum groups”, Proceedings of the International Congress of Mathe-
     maticians, Berkeley 1986, pages 798–820, Amer. Math. Soc. (1987).

[86] F. A. Bais, P. van Driel, M. de Wild Propitius, “Quantum symmetries with discrete gauge
     symmetries”, Phys. Lett. B 280, 63–70 (1992), hep-th/9203046.

[87] R. Dijkgraaf, V. Pasquier, P. Roche, “Quasi Hopf algebras, group cohomology and orbifold
     models”, Nucl. Phys. B (Proc. Suppl.) 18, 60–72 (1991).

[88] F. A. Bais, P. van Driel, M. de Wild Propitius, “Anyons in discrete gauge theories with
     Chern-Simons term”, Nucl. Phys. B 393, 547–570 (1993), hep-th/9203047.

[89] K. Fredenhagen, K. H. Rehren, B. Schroer, “Superselection sectors with braid group statis-
     tics and exchange algebras, II: Geometric aspects and conformal covariance”, Rev. Math.
     Phys. special issue 1, 113–157 (1992).

[90] C. Vafa, “Toward classification of conformal theories”, Phys. Lett. B 206, 421–426 (1988).

[91] L. Crane, D. N. Yetter, “Deformations of (bi)tensor categories”, Cahiers Topologie Géom.
     Différentielle Catég. 39 no. 3, 163–180 (1998), q-alg/9612011.

[92] A. A. Davydov, “Twisting of monoidal structures”, q-alg/9703001.

[93] D. N. Yetter, “ Functorial knot theory”, (Series on Knots and Everything, 26), World
     Scientific Publishing (2001).

[94] A. Rosenberg, “The existence of fiber functors”, Gelfand Mathematical Seminars 1996–
     1999, 145–154, Birkhäuser Boston (2000).

[95] X.-G. Wen, “Quantum orders and symmetric spin liquids”, Phys. Rev. B 65, 165113
     (2002), cond-mat/0107071.

                                             112
 [96] X.-G. Wen, “Quantum orders in an exact soluble model”, Phys. Rev. Lett. 90, 016803
      (2003), quant-ph/0205004.

 [97] R. Dijkgraaf, E. Witten, “Topological gauge theories and group cohomology”, Commun.
      Math. Phys. 129 no. 2, 393–429 (1990).

 [98] A. Hatcher, “Algebraic topology”, Cambridge University Press (2002).

 [99] J. P. May, “Simplicial objects in algebraic topology” (Chicago Lectures in Mathematics
      Series) University of Chicago Press, Reprint edition (1993).

[100] V. Pasquier, “Operator content of the ADE lattice models”, J. Phys. A 20, 5707–5717
      (1987).




                                            113
