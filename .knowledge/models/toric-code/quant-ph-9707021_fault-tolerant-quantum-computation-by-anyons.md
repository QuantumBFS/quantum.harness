---
source: "https://arxiv.org/abs/quant-ph/9707021"
type: "arxiv"
canonical_id: "quant-ph/9707021"
title: "Fault tolerant quantum computation by anyons"
authors: "A. Kitaev"
year: "1997"
venue: "Annals of Physics"
arxiv_id: "quant-ph/9707021"
doi: "10.1016/S0003-4916(02)00018-0"
full_text: yes
---

# Fault tolerant quantum computation by anyons

**Authors:** A. Kitaev

**Citation:** Annals of Physics, vol. 303, pp. 2-30, 1997

**arXiv:** [quant-ph/9707021](https://arxiv.org/abs/quant-ph/9707021)

**DOI:** [10.1016/S0003-4916(02)00018-0](https://doi.org/10.1016/S0003-4916(02)00018-0)

## Abstract

A two-dimensional quantum system with anyonic excitations can be considered as a quantum 
computer. Unitary transformations can be performed by moving the excitations around 
each other. Measurements can be performed by joining excitations in pairs and observing the 
result of fusion. Such computation is fault-tolerant by its physical nature.

## Full Text

Fault-tolerant quantum computation by anyons
                                                                                  A. Yu. Kitaev
                                                              L.D.Landau Institute for Theoretical Physics,
                                                                        117940, Kosygina St. 2
                                                                      e-mail: kitaev @ itp.ac.ru
arXiv:quant-ph/9707021v1 9 Jul 1997




                                                                                November 26, 2024


                                                                                        Abstract
                                                A two-dimensional quantum system with anyonic excitations can be considered as a
                                             quantum computer. Unitary transformations can be performed by moving the excitations
                                             around each other. Measurements can be performed by joining excitations in pairs and
                                             observing the result of fusion. Such computation is fault-tolerant by its physical nature.

                                          A quantum computer can provide fast solution for certain computational problems (e.g.
                                      factoring and discrete logarithm [1]) which require exponential time on an ordinary computer.
                                      Physical realization of a quantum computer is a big challenge for scientists. One important
                                      problem is decoherence and systematic errors in unitary transformations which occur in real
                                      quantum systems. From the purely theoretical point of view, this problem has been solved
                                      due to Shor’s discovery of fault-tolerant quantum computation [2], with subsequent improve-
                                      ments [3, 4, 5, 6]. An arbitrary quantum circuit can be simulated using imperfect gates, provided
                                      these gates are close to the ideal ones up to a constant precision δ. Unfortunately, the threshold
                                      value of δ is rather small1 ; it is very difficult to achieve this precision.
                                          Needless to say, classical computation can be also performed fault-tolerantly. However, it
                                      is rarely done in practice because classical gates are reliable enough. Why is it possible? Let
                                      us try to understand the easiest thing — why classical information can be stored reliably on a
                                      magnetic media. Magnetism arise from spins of individual atoms. Each spin is quite sensitive
                                      to thermal fluctuations. But the spins interact with each other and tend to be oriented in the
                                      same direction. If some spin flips to the opposite direction, the interaction forces it to flip back
                                      to the direction of other spins. This process is quite similar to the standard error correction
                                      procedure for the repetition code. We may say that errors are being corrected at the physical
                                      level. Can we propose something similar in the quantum case? Yes, but it is not so simple.
                                      First of all, we need a quantum code with local stabilizer operators.
                                          I start with a class of stabilizer quantum codes associated with lattices on the torus and
                                      other 2-D surfaces [6, 8]. Qubits live on the edges of the lattice whereas the stabilizer operators
                                      correspond to the vertices and the faces. These operators can be put together to make up a
                                        1
                                            Actually, the threshold is not known. Estimates vary from 1/300 [7] to 10−6 [4].

                                                                                             1
Hamiltonian with local interaction. (This is a kind of penalty function; violating each stabilizer
condition costs energy). The ground state of this Hamiltonian coincides with the protected
space of the code. It is 4g -fold degenerate, where g is the genus of the surface. The degeneracy
is persistent to local perturbation. Under small enough perturbation, the splitting of the ground
state is estimated as exp(−aL), where L is the smallest dimension of the lattice. This model
may be considered as a quantum memory, where stability is attained at the physical level rather
than by an explicit error correction procedure.
    Excitations in this model are anyons, meaning that the global wavefunction acquires some
phase factor when one excitation moves around the other. One can operate on the ground
state space by creating an excitation pair, moving one of the excitations around the torus, and
annihilating it with the other one. Unfortunately, such operations do not form a complete basis.
It seems this problem can be removed in a more general model (or models) where the Hilbert
space of a qubit have dimensionality > 2. This model is related to Hopf algebras.
    In the new model, we don’t need torus to have degeneracy. An n-particle excited state
on the plane is already degenerate, unless the particles (excitations) come close to each other.
These particles are nonabelian anyons, i.e. the degenerate state undergoes a nontrivial unitary
transformation when one particle moves around the other. Such motion (“braiding”) can be
considered as fault-tolerant quantum computation. A measurement of the final state can be
performed by joining the particles in pairs and observing the result of fusion.
    Anyons have been studied extensively in the field-theoretic context [9, 10, 11, 12, 13]. So,
I hardly discover any new about their algebraic properties. However, my approach differs in
several respects:

    • The model Hamiltonians are different.

    • We allow a generic (but weak enough) perturbation which removes any symmetry of the
      Hamiltonian.2

    • The language of ribbon and local operators (see Sec. 5.2) provides unified description of
      anyonic excitations and long range entanglement in the ground state.

    An attempt to use one-dimensional anyons for quantum computation was made by G. Castag-
noli and M. Rasetti [14], but the question of fault-tolerance was not considered.


1        Toric codes and the corresponding Hamiltonians
Consider a k × k square lattice on the torus (see fig. 1). Let us attach a spin, or qubit, to
each edge of the lattice. (Thus, there are n = 2k 2 qubits). For each vertex s and each face p,
consider operators of the following form
                                  Y                           Y
                         As =          σjx        Bp =               σjz                    (1)
                                       j∈star(s)                     j∈boundary(p)


These operators commute with each other because star(s) and boundary(p) have either 0 or 2
common edges. The operators As and Bp are Hermitian and have eigenvalues 1 and −1.
    2
        Some local symmetry still can be established by adding unphysical degrees of freedom, see Sec. 3.



                                                         2
                                                           p

                                                  s



                                  Figure 1: Square lattice on the torus

    Let N be the Hilbert space of all n = 2k 2 qubits. Define a protected subspace L ⊆ N as
follows3                n                                                o
                  L = |ξi ∈ N : As |ξi = |ξi, Bp |ξi = |ξi for all s, p                 (2)

This construction gives us a definition of a quantum code TOR(k), called a toric code [6, 8].
The operators As , Bp are the stabilizer operators of this code.
                                    Q subspace L, weQ
    To find the dimensionality of the                  can observe that there are two relations
                                                                                            2
between the stabilizer operators,       A
                                       s s   = 1 and     p Bp = 1. So, there are m = 2k −
2 independent stabilizer operators. It follows from the general theory of additive quantum
codes [15, 16] that dim L = 2n−m = 4.
    However, there is a more instructive way of computing dim L. Let us find the algebra L(L)
of all linear operators on the space L — this will give us full information about this space.
Let F ⊆ L(N ) be the algebra of operators generated by As , Bp . Clearly, L(L) ∼= G/I, where
G ⊇ F is the algebra of all operators which commute with As , Bp , and I ⊂ G is the ideal
generated by As −1, Bp −1. The algebra G is generated by operators of the form
                                      Y                     Y
                               Z =       σjz         X =       σjx
                                           j∈c                       j∈c′


where c is a loop (closed path) on the lattice, whereas c′ is a cut, i.e. a loop on the dual lattice
(see fig. 2). If a loop (or a cut) is contractible then the operator Z is a product of Bp , hence
Z ≡ 1 (mod I). Thus, only non-contractible loops or cuts are interesting. It follows that the
algebra L(L) is generated by 4 operators Z1 , Z2 , X1 , X2 corresponding to the loops cz1 , cz2
and the cuts cx1 , cx2 (see fig. 2). The operators Z1 , Z2 , X1 , X2 have the same commutation
relations as σ1z , σ2z , σ1x , σ2x . We see that each quantum state |ξi ∈ L corresponds to a state of
2 qubits. Hence, the protected subspace L is 4-dimensional.
    In a more abstract language, the algebra F corresponds to 2-boundaries and 0-coboundaries
(with coefficients from Z2 ), G corresponds to 1-cycles and 1-cocycles, and L(L) corresponds to
1-homologies and 1-cohomologies.
    There is also an explicit description of the protected subspace which may be not so useful
but is easier to grasp. Let us choose basis vectors in the Hilbert space N by assigning a label
zj = 0, 1 to each edge j. 4 The constraints Bp |ξi = |ξi say that the sum of the labels at the
boundary of a face should be zero ( mod 2). More exactly, only such basis vectors contribute to
   3
     We will show that this subspace is really protected from certain errors. Vectors of this subspaces are
supposed to represent “quantum information”, like codewords of a classical code represent classical information.
   4
     0 means “spin up”, 1 means “spin down”. The Pauli operators σz , σx have the standard form in this basis.


                                                       3
                                                                     c




                                                                         c’


                                     cx2
                                     cz1
                                           cz2 cx1

                          Figure 2: Loops on the lattice and the dual lattice

a vector from the protected subspace. Such a basis vector is characterized by two topological
numbers: the sums of zj along the loops cz1 and cz2 . The constraints Ap |ξi = |ξi say that all
basis vectors with the same topological numbers enter |ξi with equal coefficients. Thus, for
each of the 4 possible combinations of the topological numbers v1 , v2 , there is one vector from
the protected subspace,
                            2
                                   X                      X                X
           |ξv1 ,v2 i = 2−(k −1)/2   |z1 , . . . , zn i :    zj = v1 ,          zj = v2        (3)
                                      z1 ,...,zn                     j∈cz1             j∈cz2


Of course, one can also create linear combinations of these vectors.
    Now we are to show that the code TOR(k) detects k − 1 errors5 (hence, it corrects k−1
                                                                                              
                                                                                              2
errors). Consider a multiple error
                                                       Y          Y
           E = σ(α1 , . . . , αn ; β1 , . . . , βn ) =   (σjx )αj  (σjz )βj (αj , βj = 0, 1)
                                                         j           j


This error can not be detected by syndrome measurement (i.e. by measuring the eigenvalues of
all As , Bj ) if and only if E ∈ G. However, if E ∈ F then E|ξi = |ξi for every |ξi ∈ L. Such an
error is not an error at all — it does not affect the protected subspace. The bad case is when
E ∈ G but E 6∈ F . Hence, the support of E should contain a non-contractible loop or cut. It
is only possible if | Supp(E)| ≥ k. (Here Supp(E) is the set of j for which αj 6= 0 or βj 6= 0).
    One may say that the toric codes have quite poor parameters. Well, they are not “good”
codes in the sense of [17]. However, the code TOR(k) corrects almost any multiple error of size
O(k 2). (The constant factor in O(. . .) is related to the percolation problem). So, these codes
work if the error rate is constant but smaller than some threshold value. The nicest property
of the codes TOR(k) is that they are local check codes. Namely,

   1. Each stabilizer operators involves bounded number of qubits (at most 4).

   2. Each qubit is involved in a bounded number of stabilizer operators (at most 4).
   5
     In the theory of quantum codes, the word “error” is used in a somewhat confusing manner. Here it means
a single qubit error. In most other cases, like in the formula below, it means a multiple error, i.e. an arbitrary
operator E ∈ L(N ).


                                                        4
   3. There is no limit for the number of errors that can be corrected.

Also, at a constant error rate, the unrecoverable error probability goes to zero as exp(−ak).
   It has been already mentioned that error detection involves syndrome measurement. To
correct the error, one needs to find its characteristic vector (α1 , . . . , αn ; β1 , . . . , βn ) out of the
syndrome. This is the usual error correction scheme. A new suggestion is to perform error
correction at the physical level. Consider the Hamiltonian
                                             X          X
                                   H0 = −        As −       Bp                                             (4)
                                                      s             p


Diagonalizing this Hamiltonian is an easy job because the operators As , Bp commute. In
particular, the ground state coincides with the protected subspace of the code TOR(k); it is
4-fold degenerate. All excited states are separated by an energy gap ∆E ≥ 2, because the
difference between the eigenvalues of As or Bp equals 2. This Hamiltonian is more or less
realistic because in involves only local interactions. We can expect that “errors”, i.e. noise-
induced excitations will be removed automatically by some relaxation processes. Of course,
this requires cooling, i.e. some coupling to a thermal bath with low temperature (in addition
to the Hamiltonian (4)).
    Now let us see whether this model is stable to perturbation. (If not, there is no practical
use of it). For example, consider a perturbation of the form

                               V = −~h
                                         X          X
                                             ~σj −     Jjp (~σj , ~σp )
                                                 j            j<p


It is important that the perturbation is local, i.e. each term of it contains a small number of
σ (at most 2). Let us estimate the energy splitting between two orthogonal ground states of
the original Hamiltonian, |ξi ∈ L and |ηi ∈ L. We can use the usual perturbation theory
because the energy spectrum has a gap. In the m-th order of the perturbation theory, the
splitting is proportional to hξ|V m |ηi or hξ|V m |ξi − hη|V m |ηi. However, both quantities are
zero unless V m contains a product of σjz or σjx along a non-contractible loop or cut. Hence, the
splitting appears only in the ⌈k/2⌉-th or higher orders. As far as all things (like the number
of the relevant terms in V m ) scale correctly to the thermodynamic limit, the splitting vanishes
as exp(−ak). A simple physical interpretation of this result is given in the next section. (Of
course, the perturbation should be small enough, or else a phase transition may occur).
     Note that our construction is not restricted to square lattices. We can consider an arbitrary
irregular lattice, like in fig. 6. Moreover, such a lattice can be drawn on an arbitrary 2-D
surface. On a compact orientable surface of genus g, the ground state is 4g -fold degenerate. In
this case, the splitting of the ground state is estimated as exp(−aL), where L is the smallest
dimension of the lattice. We see that the ground state degeneracy depends on the surface
topology, so we deal with topological quantum order. On the other hand, there is a finite
energy gap between the ground state and excited states, so all spatial correlation functions
decay exponentially. This looks like a paradox — how do parts of a macroscopic system know
about the topology if all correlations are already lost at small scales? The answer is that there
is long-range entanglement 6 which can not be expressed by simple correlation functions like
hσja σlb i. This entanglement reveals itself in the excitation properties we are going to discuss.
   6
       Entanglement is a special, purely quantum form of correlation.


                                                          5
                                                       z
                                                               t
                                                x
                                                                   z
                                                           x
                                                     t’



                                      Figure 3: Strings and particles

2     Abelian anyons
Let us classify low-energy excitations of the Hamiltonian (4). An eigenvector of this Hamiltonian
is an eigenvector of all the operators As , Bp . An elementary excitation, or particle occurs      Q if only
     Q the constraints As |ξi = |ξi, Bp ξi = |ξi is violated. Because of the relations s As = 1
one of
and p Bp = 1, it is impossible to create a single particle. However, it is possible to create a
two-particle state of the form |ψ z (t)i = S z (t)|ξi or |ψ x (t′ )i = S x (t′ )|ξi, where |ξi is an arbitrary
ground state, and                      Y                                  Y
                            S z (t) =     σjz               S x (t′ ) =         σjx                        (5)
                                          j∈t                              j∈t′

(see fig. 3). In the first case, two particles are created at the endpoints of the “string” (non-
closed path) t. Such particles live on the vertices of the lattice. We will call them z-type
particles, or “electric charges”. Correspondingly, x-type particles, or “magnetic vortices” live
on the faces. The operators S z (t), S x (t′ ) are called string operators. Their characteristic
property is as follows: they commute with every As and Bp , except for few ones (namely, 2)
corresponding to the endpoints of the string. Note that the state |ψ z (t)i = S z (t)|ξi depends
only on the homotopy class of the path t while the operator S z (t) depends on t itself.
     Any configuration of an even number of z-type particles and an even number of x-type
particles is allowed. We can connect them by strings in an arbitrary way. Each particle
configuration defines a 4g -dimensional subspace in the global Hilbert space N . This subspace
is independent of the strings but a particular vector S a1 (t1 ) · · · S am (tm )|ξi depends on t1 , . . . , tm .
If we draw these strings in a topologically different way, we get another vector in the same 4g -
dimensional subspace. Thus, the strings are unphysical but we can not get rid of them in our
formalism.
     Let us see what happens if these particles move around the torus (or other surface). Moving
a z-type particle along the path cz1 or cz2 (see fig. 2) is equivalent to applying the operator Z1
or Z2 . Thus, we can operate on the ground state space by creating a particle pair, moving one
of the particles around the torus, and annihilating it with the other one. Thus we can realize
some quantum gates. Unfortunately, too simple ones — we can only apply the operators σz
and σx to each of the 2 (or 2g) qubits encoded in the ground state.
     Now we can give the promised physical interpretation of the ground state splitting. In the
presence of perturbation, the two-particle state |ψ z (t)i is not an eigenstate any more. More
exactly, both particles will propagate rather than stay at the same positions. The propagation
process is described by the Schrödinger equation with some effective mass mz . (x-type particles
have another mass mx ). In the non-perturbed model, mz = mx = ∞. There are no real particles

                                                       6
                                                               c


                                            z   t          z

                                                q
                                        x           x




                   Figure 4: An x-type particle moving around a z-type particle

in the ground state, but they can be created and annihilate virtually. A virtual particle can
tunnel around the torus before annihilating with the other one. Such processes contribute terms
bz1 Z1 , bz2 Z2 , bx1 X1 , bx2 X2 to the ground√state effective Hamiltonian. Here bαi ∼ exp(−aα Li ) is
the tunneling amplitude whereas aα ∼ 2m∆E is the imaginary wave vector of the tunneling
particle.
    Next question: what happens if we move particles around each other? (For this, we don’t
need a torus; we can work on the plane). For example, let us move an x-type particle around
a z-type particle (see fig. 4). Then

          |Ψinitial i = S z (t) |ψ x (q)i ,     |Ψfinal i = S x (c) S z (t) |ψ x (q)i = −|Ψinitial i

because S x (c) and S z (t) anti-commute, and S x (c)|ψ x (q)i = |ψ x (q)i. We see that the global
wave function (= the state of the entire system) acquires the phase factor −1. It is quite
unlike usual particles, bosons and fermions, which do not change their phase in such a process.
Particles with this unusual property are called abelian anyons. More generally, abelian anyons
are particles which realize nontrivial one-dimensional representations of (colored) braid groups.
In our case, the phase change can be also interpreted as an Aharonov-Bohm effect. It does not
occur if both particles are of the same type.
     Note that abelian anyons exist in real solid state systems, namely, they are intrinsicly re-
lated to the fractional quantum Hall effect [18]. However, these anyons have different braiding
properties. In the fractional quantum Hall system with filling factor p/q, there is only one
basic type of anyonic particles with (real) electric charge 1/q. (Other particles are thought to
be composed from these ones). When one particle moves around the other, the wave function
acquires a phase factor exp(2πi/q).
     Clearly, the existence of anyons and the ground state degeneracy have the same nature. They
both are manifestations of a topological quantum order, a hidden long-range order that can not
be described by any local order parameter. (The existence of a local order parameter contradicts
the nature of a quantum code — if the ground state is accessible to local measurements then
it is not protected from local errors). It seems that the anyons are more fundamental and can
be used as a universal probe for this hidden order. Indeed, the ground state degeneracy on the
torus follows from the existence of anyons [19]. Here is the original Einarsson’s proof applied
to our two types of particles.
     We derived the ground state degeneracy from the commutation relations between the op-
erators Z1 , Z2 , X1 , X2 . These operators can be realized by moving particles along the loops

                                                     7
                  Figure 5: A fly-over crossing geometry for a 2-D electron layer

cz1 , cz2 , cx1 , cx2 . These loops only exist on the torus, not on the plane. Consider, however,
the process in which an x-type particle and a z-type particle go around the torus and then
trace their paths backward. This corresponds to the operator W = X1−1 Z1−1 X1 Z1 which can be
realized on the plane. Indeed, we can deform particles’ trajectories so that one particle stays
at rest while the other going around it. Due to the anyonic nature of the particles, W = −1.
We see that X1 and Z1 anti-commute.
     The above argument is also applicable to the fractional quantum Hall anyons [19]. The
ground state on the torus is q-fold degenerate, up to the precision ∼ exp(−L/l0 ), where l0
is the magnetic length. This result does not rely on the magnetic translational symmetry or
any other symmetry. Rather, it relies on the existence of the energy gap in the spectrum
(otherwise the degeneracy would be unstable to perturbation). Note that holes (=punctures)
in the torus do not remove the degeneracy unless they break the nontrivial loops cx1 , cx2 , cz1 ,
cz2 . The fly-over crossing geometry (see fig. 5) is topologically equivalent to a torus with 2
holes, but it is almost flat. In principle, such structure can be manufactured 7 , cooled down
and placed into a perpendicular magnetic field. This will be a sort of quantum memory — it
will store a quantum state forever, provided all anyonic excitation are frozen out or localized.
Unfortunately, I do not know any way this quantum information can get in or out. Too few
things can be done by moving abelian anyons. All other imaginable ways of accessing the
ground state are uncontrollable.


3       Materialized symmetry: is that a miracle?
Anyons have been studied extensively in the gauge field theory context [9, 10, 11, 13]. However,
we start with quite different assumptions about the Hamiltonian. A gauge theory implies a
gauge symmetry which can not be removed by external perturbation. To the contrary, our model
is stable to arbitrary local perturbations. It is useful to give a field-theoretic interpretation
of this model. The edge labels zj (measurable by σjz ) correspond to a Z2 vector potential,
whereas σjx corresponds to the electric field. The operators As are local gauge transformations
whereas Bp is the magnetic field on the face p. The constraints As |ξi = |ξi mean that the
state |ξi is gauge-invariant. Violating the gauge invariance is energetically unfavorable but not
forbidden. The Hamiltonian (which includes H0 and some perturbation V ) need not obey the
gauge symmetry. The constraints Bp |ξi = |ξi mean that the gauge field corresponds to a flat
connection. These constraints are not strict either.
    7
     It is not easy. How will the two layers (the two crossing “roads”, one above the other) join in a single
crystal layout?


                                                     8
    Despite the absence of symmetry in the Hamiltonian H = H0 + V , our system exhibits two
conservation laws: electric charge and magnetic charge (i.e. the number of vortices) are both
conserved modulo 2. In the usual electrodynamics, conservation of electric charge is related to
the local (=gauge) U(1) symmetry. In our case, it should be a local Z2 symmetry for electric
charges and another Z2 symmetry for magnetic vortices. So, our system exhibits a dynamically
created Z2 × Z2 symmetry which appears only at large distances where individual excitations
are well-defined.
    Probably, the reader is not satisfied with this interpretation. Really, it creates a new puzzle
rather than solve an old one. What is this mysterious symmetry? How do symmetry operators
look like at the microscopic level? The answer sounds as nonsense but it is true. This symmetry
(as well as any other local symmetry) can be found in any Hamiltonian if we introduce some
unphysical degrees of freedom. So, the symmetry is not actually being created. Rather, an
artificial symmetry becomes a real one.
    The new degrees of freedom are spin variables  vs , wp = 0, 1 for each vertex s and each face
p. The vertex spins will stay in the state 2−1/2 |0i + |1i whereas the face spins will stay in
the state |0i. So, all the extra spins together stay in a unique quantum state |ζi. Obviously,
σsx |ζi = |ζi and σpz |ζi = |ζi, for every vertex s and every face p. From the mathematical point
of view, we have simply defined an embedding of the space N into a larger Hilbert space T of
all the spins, |ψi 7→ |ψi ⊗ |ζi. So we may write N ⊆ T . We will call N the physical space (or
subspace), T the extended space. Physical states (i.e. vectors |ψi ∈ N ) are characterized by
the equations
                                 σsx |ψi = |ψi , σpz |ψi = |ψi
for every vertex s and face p.
    Now let us apply a certain unitary transformation U on the extended space T . This trans-
formation is just a change of the spin variables, namely
                                          X                               X
          vs 7→ vs ,      zj 7→ zj +              vs ,   wp 7→ wp +               zj      (6)
                                       s=endpoint(j)                       j∈boundary(p)


(all sums are taken modulo 2). The physical subspace becomes N ′ = UN . Vectors |ψi ∈ N ′
are invariant under the following symmetry operators

                    Ps = Uσsx U † = σsx As             Qp = Uσpz U † = σpz Bp                  (7)

The transformed Hamiltonian H ′ = UHU † commutes with these operators. It is defined up to
the equivalence Ps ≡ 1, Qp ≡ 1. In particular,
                                                 X        X
                        H0′ = U H0 U † = H0′ ≡ −    σsx −     σpz                      (8)
                                                          s         p


   In the field theory language, the vertex variables vs (or the operators σsz ) are a Higgs field.
The operators Ps are local gauge transformations. Thus, an arbitrary Hamiltonian can be
written in a gauge-invariant form if we introduce additional Higgs fields. Of course, it is a
very simple observation. The real problem is to understand how the artificial gauge symmetry
“materialize”, i.e. give rise to a physical conservation law.



                                                 9
    Electric charge at a vertex s isQgiven by the operator σsx . The total electric charge on a
compact surface is zero8 because s σsx ≡ 1. This is not a physically meaningful statement
as it is. It is only meaningful if there are discrete charged particles. Then the charge is also
conserved locally, in every scattering or fusion process. It is difficult to formulate this property
in a mathematical language, but, hopefully, it is possible. (The problem is that particles are
generally smeared and can propagate. Physically, particles are well-defined if they are stable and
have finite energy gap). Alternatively, one can use various local and nonlocal order parameters
to distinguish between phases with an unbroken symmetry, broken symmetry or confinement.
    The artificial gauge symmetry materialize for the Hamiltonian (8) but this is not the case
for every Hamiltonian. Let us try to describe possible symmetry breaking mechanisms in terms
of local order parameters. If the gauge symmetry is broken then there is a nonvanishing vacuum
average of the Higgs field, φ(s) = hσsz i =
                                          6 0. Electric charge is not conserved any more. In other
words, there is a Bose condensate of charged particles. Although the second Z2 symmetry is
formally unbroken, free magnetic vortices do not exist. More exactly, magnetic vortices are
confined. (The duality between symmetry breaking and confinement is well known [25]). It is
also possible that the second symmetry is broken, then electric charges are confined. From the
physical point of view, these two possibilities are equivalent: there is no conservation law in
the system.9
    An interesting question is whether magnetic vortices can be confined without the gauge
symmetry being broken. Apparently, the answer is “no”. The consequence is significant: electric
charges and magnetic vortices can not exist without each other. It seems that materialized
symmetry needs better understanding; as presented here, it looks more like a miracle.


4       The model based on a group algebra
From now on, we are constructing and studying nonabelian anyons which will allow universal
quantum computation.
   Let G be a finite (generally, nonabelian) group. Denote by H = C[G] the corresponding
group algebra, i.e. the space of formal linear combinations of group elements with complex
                                                                                      n
coefficients. We can consider H as a Hilbert space with a standard orthonormal basis |gi :
       o
g ∈ G . The dimensionality of this space is N = |G|. We will work with “spins” (or “qubits”)
taking values in this space.10 Remark : This model can be generalized. One can take for H
any finite-dimensional Hopf algebra equipped with a Hermitian scalar product with certain
properties. However, I do not want to make things too complicated.
   To describe the model, we need to define 4 types of linear operators, Lg+ , Lg− , T+h , T−h acting
on the space H. Within each type, they are indexed by group elements, g ∈ G or h ∈ G. They
act as follows
                      Lg+ |zi = |gzi                T+h |zi = δh,z |zi
                                                                                                  (9)
                      Lg− |zi = |zg −1 i            T−h |zi = δh−1, z |zi
    8
      Strictly speaking, the electric charge is not a numeric quantity; rather, it is an irreducible representation
of the group Z2 . “Zero” refers to the identity representation.
    9
      The two possibilities only differ if an already materialized symmetry breaks down at much large distances
(lower energies).
   10
      In the field theory language, the value of a spin can be interpreted as a G gauge field. However, we do not
perform symmetrization over gauge transformations.


                                                        10
                                                                                                  Lg+



                                                  p                                         Th-         Th+

                                              s
                                                                                                  Lg-

          Figure 6: Generic lattice and the orientation rules for the operators Lg± and T±h

(In the Hopf algebra context, the operators Lg+ , Lg− , T+h , T−h correspond to the left and right
multiplications and left and right comultiplication, respectively). These operators satisfy the
following commutation relations
                                                                                             −1
                          Lg+ T+h = T+gh Lg+                            Lg+ T−h = T−hg Lg+
                                            −1
                                                                                                              (10)
                          Lg− T+h = T+hg Lg−                            Lg− T−h = T−gh Lg−

    Now consider an arbitrary lattice on an arbitrary orientable 2-D surface, see fig. 6. (We
will mostly work with a plane or a sphere, not higher genus surfaces). Corresponding to each
edge is a spin which takes values in the space H. Arrows in fig. 6 mean that we choose some
orientation for each edge of the lattice. (Changing the direction of a particular arrow will be
equivalent to the basis change |zi 7→ |z −1 i for the corresponding qubit). Let j be an edge of the
lattice, s one of its endpoints. Define an operator Lg (j, s) = Lg± (j) as follows. If s is the origin
of the arrow j then Lg (j, s) is Lg− (j) (i.e. Lg− acting on the j-th spin), otherwise it is Lg+ (j).
This rule is represented by the diagram at the right side of fig. 6. Similarly, if p is the left (the
right) ajacent face of the edge j then T h (j, p) is T−h (resp. T+h ) acting on the j-th spin.
    Using these notations, we can define local gauge transformations and magnetic charge op-
erators corresponding to a vertex s and an adjacent face p (see fig. 6). Put

                                                                Lg (j, s)
                                                           Q
                              Ag (s, p) = Ag (s) =
                                                                   j∈star(s)

                                                                 k                                            (11)
                                                                            hm
                                                         P       Q
                                   Bh (s, p) =                          T        (jm , p)
                                                      h1 ···hk =h m=1

where j1 , . . . , jk are the boundary edges of p listed in the counterclockwise order, starting from,
and ending at, the vertex s. (The sum is taken over all combinations of h1 , . . . , hk ∈ G, such that
h1 · · · hk = h. Order is important here!). Although Ag (s, p) does not depend on p, we retain this
parameter to emphasize the duality between Ag (s, p) and Bh (s, p). 11 These operators generate
an algebra D = D(G), Drinfield’s quantum double [20] of the group algebra C[G]. It will play
a very important role below. Now we only need two symmetric combinations of Ag (s, p) and
Bh (s, p), namely                       X
                           A(s) = N −1      Ag (s, p)          B(p) = B1 (s, p)                    (12)
                                            g∈G
  11
       In the Hopf algebra setting, Ag (s, p) does depend on p.

                                                           11
where N = |G|. Both A(s) and B(p) are projection operators. (A(s) projects out the states
which are gauge invariant at s, whereas B(p) projects out the states with vanishing magnetic
charge at p). The operators A(s) and B(p) commute with each other.12 Also A(s) commutes
with A(s′ ), and B(p) commutes with B(p′ ) for different vertices and faces. In the case G = Z2 ,
these operators are almost the same as the operators (1), namely A(s) = 12 (As + 1), B(p) =
1
2
  (Bp + 1). 13
    At this point, we have only defined the global Hilbert space N (the tensor product of many
copies of H) and some operators on it. Now let us define the Hamiltonian.
                                    X                 X
                            H0 =        (1 − A(s)) +     (1 − B(p))                         (13)
                                           s                   p


It is quite similar to the Hamiltonian (4). As in that case, the space of ground states is given
by the formula
                         n                                                   o
                   L = |ξi ∈ N : A(s)|ξi = |ξi, B(p)|ξi = |ξi for all s, p                  (14)

The corresponding energy is 0; all excited states have energies ≥ 1.
    It is easy to work out an explicit representation of ground states similar to eq. (3). The
ground states correspond 1-to-1 to flat G-connections, defined up to conjugation, or super-
positions of those. So, the ground state on a sphere is not degenerate. However, particles
(excitations) have quite interesting properties even on the sphere or on the plane. (We treat
the plane as an infinitely large sphere). The reader probably wants to know the answer first,
and then follow formal calculations. So, I give a brief abstract description of these particles. It
is a mixture of general arguments and details which require verification.
    The particles live on vertices or faces, or both; in general, one particle occupies a vertex
and an adjacent face same time. A combination of a vertex and an adjacent face will be called
a site. Sites are represented by dotted lines in fig. 7. (The dashed lines are edges of the dual
lattice).
    Consider n particles on the sphere pinned to particular sites x1 , . . . , xn at large distances
from each other. The space L[n] = L(x1 , . . . , xn ) of n-particle states has dimensionality N 2(n−1) ,
including the ground state.14 Not all these states have the same energy. Even more splitting
occurs under perturbation, but some degeneracy still survive. Of course, we assume that the
perturbation is local, i.e. it can be represented by a sum of operators each of which acts only on
few spins. To find the residual degeneracy, we will study the action of such local operators on
the space L[n]. Local operators generate a subalgebra P[n] ⊆ L(L[n]). Elements of its center,
C[n], are conserved classical quantities; they can be measured once and never change. (More
exactly, they can not be changed by local operators). As these classical variables are locally
measurable, we interpret them as particle’s types. It turns out that the types correspond 1-to-1
to irreducible representations of the algebra D, the quantum double. Thus, each particle can
belong to one of these types. The space L[n] and the algebra P[n] split accordingly:
              M                               M                                                     
    L[n] =         Ld1 ,...,dn      P[n] =           Pd1 ,...,dn       Pd1 ,...,dn ⊆ L(Ld1 ,...,dn )   (15)
             d1 ,...,dn                          d1 ,...,dn
  12
     This is not obvious. Use the commutation relations (10) to verify this statement.
  13
     Here As and Bp are the notations from Sec. 1; we will not use them any more.
  14
     The absence of particle at a given site is regarded as a particle of special type.

                                                        12
where dm is the type of the m-th particle. The “classical” subalgebra C[n] is generated by the
projectors onto Ld1 ,...,dn .
    But this is not the whole story. The subspace Ld1 ,...,dn splits under local perturbations from
Pd1 ,...,dn . By a general mathematical argument,15 this algebra can be characterized as follows

                   Ld1 ,...,dn = Kd1 ,...,dn ⊗ Md1 ,...,dn             Pd1 ,...,dn = L(Kd1 ,...,dn )              (16)

The space Kd1 ,...,dn corresponds to local degrees of freedom. They can be defined independently
for each particle. So, Kd1 ,...,dn = Kd1 ⊗ · · · ⊗ Kdn , where Kdm is the space of “subtypes”
(internal states) of the m-th particle. Like the type, the subtype of a particle is accessible by
local measurements. However, it can be changed, while the type can not.
    The most interesting thing is the protected space Md1 ,...,dn . It is not accessible by local
measurements and is not sensitive to local perturbations, unless the particles come close to each
other. This is an ideal place to store quantum information and operate with it. Unfortunately,
the protected space does not have tensor product structure. However, it can be described as
follows. Associated with each particle type a is an irreducible representation Ud of the quantum
double D. Consider the product representation Ud1 ⊗ · · · ⊗ Udn and split it into components
corresponding to different irreducible representations. The protected space is the component
corresponding to the identity representation.
    If we swap two particles or move one around the other, the protected space undergoes some
unitary transformation. Thus, the particles realize some multi-dimensional representation of the
braid group. Such particles are called nonabelian anyons. Note that braiding does not affect the
local degrees of freedom. If two particles fuse, they can annihilate or become another particle.
The protected space becomes smaller but some classical information comes out, namely, the
type of the new particle. So, the we can do measurements on the protected space. Finally, if we
create a new pair of particles of definite types, it always comes in a particular quantum state.
So, we have a standard toolkit for quantum computation (new states, unitary transformations
and measurements), except that the Hilbert space does not have tensor product structure.
Universality of this toolkit is a separate problem, see Sec. 7.
    Our model gives rise to the same braiding and fusion rules as gauge field theory models [10,
11]. The existence of local degrees of freedom (subtypes) is a new feature. These degrees of
freedom appear because there is no explicit gauge symmetry in our model.


5      Algebraic structure
5.1      Particles and local operators
This subsection is also rather abstract but the claims we do are concrete. They will be proven
in Sec. 5.4.
    As mentioned above, the ground state of the Hamiltonian (13) is not degenerate (on the
sphere or on the plane regarded as an infinitely large sphere). Excited states are characterized
by their energies. The energy of an eigenstate |ψi is equal to the number of constraints (A(s) −
1)|ψi = 0 or (B(p) − 1)|ψi = 0 which are violated. Complete classification of excited states is
a difficult problem. Instead of that, we will try to classify elementary excitations, or particles.
 15
      Pd1 ,...,dn is a subalgebra of L(Ld1 ,...,dn ) with a trivial center, closed under Hermitian conjugation.



                                                          13
    Let us formulate the problem more precisely. Consider a few excited “spots” separated by
large distances. Each spot is a small region where some of the constrains are violated. The
energy of a spot can be decreased by local operators but, generally, the spot can not disappear.
Rather, it shrinks to some minimal excitation (which need not be unique). We will see (in
Sec. 5.4) that any excited spot can be transformed into an excitation which violates at most
2 constraints, A(s) − 1 ≡ 0 and B(p) − 1 ≡ 0, where s is an arbitrary vertex, and p is an
adjacent face. Such excitations are be called elementary excitations, or particles. Note that
definition of elementary excitations is a matter of choice. We could decide that an elementary
excitation violates 3 constraints. Even with our definition, the “space of elementary excitations”
is redundant.
    By the way, the space of elementary excitations is not well defined because such an excitation
does not exist alone. More exactly, the only one-particle state on the sphere is the ground state.
(This can be proven easily). The right thing is the space of two-particle excitations, L(a, b).
Here a = (s, p) and b = (s′ , p′ ) are the sites occupied by the particles. (Recall that a site is
a combination
    Q            Q a vertex and an adjacent face). The projector onto L(a, b) can be written
                 of
as r6=s,s′ A(r) l6=p,p′ B(l). Note that introducing a third particle (say, c) will not give more
freedom for any of the two. Indeed, b and c can fuse without any effect on a.
    Let us see how local operators act on the space L(a, b). In this context, a local operator is
an operator which acts only on spins near a (or near b). Besides that, it should preserve the
subspace L(a, b) ⊆ N and its orthogonal complement. (N is the space of all quantum states).
Example: the operators Ag (a) and Bh (a), where a = (s, p), commute with A(r), B(l) for all
r 6= s and l 6= p. Hence, they commute with the projector onto the subspace L(a, b). These
operators generate an algebra D(a) ⊂ L(N ). It will be shown in Sec. 5.4 that D(a) includes
all local operators acting on the space L(a, b), and the action of D(a) on L(a, b) is exact (i.e.
different operators act differently).
    Actually, the algebra D(a) = D does not depend on a, only the embedding D → L(N ) does.
This algebra is called the quantum double of the group G and denoted by D(G). Its structure
is determined by the following relations between the operators Ag = Ag (a) and Bh = Bh (a)

             Af Ag = Af g               Bh Bi = δh,i Bh                      Ag Bh = Bghg−1 Ag               (17)

The operators D(h,g) = Bh Ag form a linear basis of D. (In [10, 11] these operators were denoted
by h ). The following multiplication rules hold
     g


                             D(h1 ,g1 ) D(h2 ,g2 ) = δh1 , g1 h2 g1−1 D(h1 , g1 g2 )

This identity can be also written in a symbolic tensor form, with h and g being combined into
one index:
                                                     (h,g)
            Dm Dn = Ωkmn Dk                        Ω(h1 ,g1 ) (h2 ,g2 ) = δh1 , g1 h2 g1−1 δh,h1 δg, g1 g2   (18)

(summation over k is implied). Actually, D is not only an algebra, it is a quasi-triangular Hopf
algebra, see Secs. 5.2, 5.3.
   Note that D = D(a) is closed under Hermitian conjugation (in L(N )) which acts as follows

                 A†g = Ag−1               Bh† = Bh                    †
                                                                     D(h,g) = D(g−1 hg, g−1 )                (19)


                                                      14
Thus, D = D(a) is a finite-dimensional C ∗ -algebra. Hence it has the following structure
                                              M
                                      D =         L(Kd )                                  (20)
                                                      d

where d runs over all irreducible representations of D. We can interpret d as particle’s type.16
The absence of particle corresponds to a certain one-dimensional representation called the
identity representation. More exactly, the operators D(h,g) act on the ground state |ξi as follows

                            Dk |ξi = εk |ξi                where ε(h,g) = δh,1                            (21)

    The “space of subtypes”, Kd actually characterize the redundancy of our definition of el-
ementary excitations. However, this redundancy is necessary to have a nice theory of ribbon
operators (see Sec. 5.2).
    Irreducible representations of D can be described as follows [10]. Let u ∈ G be an arbitrary
element, C = {gug −1 : g ∈ G} its conjugacy class, E = {g ∈ G : gu = ug} its centralizer.
There is one irreducible representation d = (C, χ) for each conjugacy class C and each irre-
ducible representation χ of the group E (see below). It does not matter which element u ∈ C
is used to define E. The conjugacy class C can be interpreted as magnetic charge whereas χ
corresponds to electric charge. For example, consider the group S3 (the permutation group of
order 3). It has 3 conjugacy classes of order 1, 2 and 3, respectively. So, the algebra D(S3 ) has
irreducible representations of dimensionalities 1,1,2; 2,2,2; 3,3.
    The simplest case is when χ is the identity representation, i.e. the particle carries only
magnetic charge but no electric charge. Then the subtypes can be identified with the elements
of C, i.e. the corresponding space (denoted by BC ) has a basis {|vi : v ∈ C}. The local
operators act on this space as follows

                                       D(h,g) |vi = δh, gvg−1 |gvg −1i                                    (22)
                                                                (χ)
   Now consider the general case. Denote by Wf = Wf the irreducible action of f ∈ E on an
appropriate space Aχ . Choose arbitrary elements qv ∈ G such that qv uqv−1 = v for each v ∈ C.
Then any element g ∈ G can be uniquely represented in the form g = qv f , where v ∈ C and
f ∈ E. We can define a unique action of D on BC ⊗ Aχ , such that
                                
                    Bh |vi ⊗ |ηi = δh,v |vi ⊗ |ηi                                         (23)
                                
                  Aqv f |ui ⊗ |ηi = |vi ⊗ Wf |ηi          (v ∈ C, f ∈ E)
                               
More generally, D(h,g) |vi ⊗ |ηi = δh, gvg−1 |gvg −1i ⊗ Wf |ηi, where f = qv (qgvg−1 )−1 g. This
action is irreducible.

5.2     Ribbon operators
The next task is to construct a set of operators which can create an arbitrary two-particle state
from the ground state. I do not know how to deduce an expression for such operators; I will
  16
     Caution. The local operators should not be interpreted as symmetry transformations. The true symmetry
transformations, so-called topological operators, will be defined in Sec. 6. Mathematically, they are described
by the same algebra D, but their action on physical states is different.

                                                      15
                 a                                                                            b




                                     Figure 7: A ribbon on the lattice

just give an answer and explain why it is correct. In the abelian case (see Sec. 2) there were
two types of such operators which corresponded to paths on the lattice and the dual lattice,
respectively. In the nonabelian case, we have to consider both types of paths together. Thus,
the operators creating a particle pair are associated with a ribbon (see fig. 7). The ribbon
connects two sites at which the particles will appear (say, a = (s, p) and b = (s′ , p′ )). The
corresponding operators act on the edges which constitute one side of the ribbon (solid line),
as well as the edges intersected by the other side (dashed line).
    For a given ribbon t, there are N 2 ribbon operators F (h,g) (t) indexed by g, h ∈ G. They act
as follows17

                                     ✛     x1      ✛      x2       ✛      x3
                                     ✻             ✻               ✻

                      F (h,g) (t)    y1             y2              y3                        =


                                                                                                         (24)
                                     ✛     x1      ✛      x2       ✛      x3
                                     ✻             ✻               ✻

                =     δg, x1 x2 x3   hy1            x−1
                                                     1 hx1 y2       (x1 x2 )−1 h(x1 x2 ) y3



These operators commute with every projector A(r), B(l), except for r = s, s′ and l = p, p′ .
This is the first important property of ribbon operators.
   The operators F (h,g) (t) depend on the ribbon t. However, their action on the space L(a, b)
  17
    Horizontal and vertical arrows are the two types of edges. Each of the two diagrams (6 arrows with labels)
stand for a particular basis vector



                                                     16
depends only on the topological class of the ribbon This is also true for a multi-particle excitation
space L(x1 , . . . , xn ). More exactly, consider two ribbons, t and q, connecting the sites x1 = a
and x2 = b The actions of F (h,g) (t) and F (h,g) (q) on L(x1 , . . . , xn ) coincide provided none of the


                                  x3                q


                         a=x1                                                      x2=b
                                                     t
                                                                              x4



sites x3 , . . . , xn lie on or between the ribbons. This is the second important property of ribbon
                                                                                  M
operators. We will write F (h,g) (t) ≡ F (h,g) (q), or, more exactly, F (h,g) (t) ≡ F (h,g) (q), where
M = {x1 , . . . , xn }.
    Linear combination of the operators F (h,g) (t) are also called ribbon operators. They form
an algebra F (t) ∼     = F . The multiplication rules are as follows
                                                          (h ,g ) (h2 ,g2 )
              F m(t) F n(t) = Λmn k
                               k F (t)
                                                            1 1
                                                         Λ(h,g)               = δh1 h2 , h δg1 ,g δg2 ,g    (25)

(summation over m and n is implied).
    Any ribbon operator on a long ribbon t = t1 t2 (see figure below) can be represented in terms
of ribbon operators corresponding to its parts, t1 and t2

                                       t1                            t2


                                                        (h,g)
      F k(t1 t2 ) = Ωkmn F m(t1 ) F n(t2 )          Ω(h1 ,g1) (h2 ,g2 ) = δg, g1 g2 δh1 ,h δh2 , g1−1 hg1   (26)

(Note that F m(t1 ) and F n(t2 ) commute because the ribbons t1 and t2 do ton overlap). By
some miracle, the tensor Ω⋆⋆⋆ is the same as in eg. (18). From the mathematical point of view,
eq. (26) defines a linear mapping ∆(t1 , t2 ) : F (t1 , t2 ) → F (t1 ) ⊗ F (t2 ), or just ∆ : F → F .
Such a mapping is called a comultiplication.
    The comultiplication rules (26) allow to give another definition of ribbon operators which
is nicer than eq. (24). Note that a ribbon consists of triangles of two types (see fig. 7). Each
triangle corresponds to one edge. More exactly, a triangle with two dotted sides and one dashed
side corresponds to a combination of an edge and its endpoint, say, i and r. Similarly, a triangle
with a solid side corresponds to a combination of an edge and one of the adjacent faces, say, j
and l. Each triangle can be considered as a short ribbon. The corresponding ribbon operators
are
                                                                                −1
                  F (h,g) (i, r) = δg,1 Lh (i, r)           F (h,g) (j, l) = T g (j, l)
The ribbon operators on a long ribbon can be constructed from these ones.
   It has been already mentioned that the multiplication in D and the comultiplication in F
are defined by the same tensor Ω⋆⋆⋆ . Actually, D and F are Hopf algebras dual to each other.


                                                   17
(For general account on Hopf algebras, see [21, 22, 23]). The multiplication in F corresponds
to a comultiplication in D defined as follows

                                         ∆(Dk) = Λmn
                                                  k D m ⊗ Dn                                                 (27)

                                 h1 h2 =h D(h1 ,g) ⊗ D(h2 ,g) ). The unit element of F is 1F = εk F ,
                                                                                                   k
                               P
(More explicitly, ∆(D(h,g) ) =
where εk are given by eq. (21); the tensor ε⋆ also defines a counit of D (i.e. the mapping
ε : D → C : ε(Dk) = εk ). The unit of D and the counit of F are given by
                                                   e(h,g) = δg,1                                             (28)

The Hopf algebra structure also includes an antipode, i.e. a mapping S : D → D : S(Dk) =
                                                      ⋆
Sm                         m       m k
 k Dm, or S : F → F : S(F ) = Sk F . The tensor S⋆ is given by the equation

                                         (h ,g )
                                       S(h12 ,g12 ) = δg1−1 h1 g1 , h−1
                                                                     2
                                                                        δg1 , g2−1                           (29)

       Here is the complete list of Hopf algebra axioms.

                   Λlm
                    i  Λin   lj mn
                        k = Λk Λj                                  εi Λim
                                                                       k  = Λmj
                                                                             k  εj = δ m
                                                                                       k                     (30)

                    Ωilm Ωkin = Ωklj Ωjmn                          ei Ωkin = Ωkmj ej = δ km                  (31)


             q
         Λlm       l   m   ir js
          q Ωkn = Ωij Ωrs Λk Λn                        εq Ωqkn = εk εn                q e
                                                                                     Λlm q
                                                                                           = el em           (32)

                                     q         n      q   k
                                  p Ωkn δ m = δ l Λp Ωkn Sm = εp e
                             Skl Λlm               lm     n       q
                                                                                                             (33)


    Most of these identities correspond to physically obvious properties of ribbon operators.
Eq. (30) is a statement of the usual multiplication axioms in the algebra F , namely, (F lF m)F n =
F l(F mF n) and 1F m = F m1 = F m. The first equation in (31) (coassociativity of the comulti-
plication in F ) can be proven by expanding F k(t1 t2 t3 ) as Ωkin F i(t1 t2 ) F n(t3 ) or Ωklj F l(t1 ) F j (t2 t3 )
— the result must be the same.18 Eqs. (32) mean that the multiplication and comultiplication
are consistent with each other. To prove the first equation in (32), expand F l(t1 t2 ) F m(t1 t2 )
in two different ways. The second equation follows from the fact that εq F q (t1 t2 ) is the identity
operator.
    The antipode axiom (33) does not have explicit physical meaning. Mathematically, it is
a definition of the tensor S⋆⋆ : the element γ = Slk F k ⊗ Dl ∈ F ⊗ D is the inverse to the
canonical element δ = F i ⊗ Di. The antipode have the following properties which can be
derived from (30–33)

                       Sil Sjm Λlm
                                p  = Λji q
                                      q Sp                           Spq Ωqij = Ωpml Sm  l
                                                                                      j Si                   (34)
  18
      The coassociativity is necessary and sufficient for that. The sufficiency is rather obvious; the necessity
follows from the fact that the mapping F → F(t) is injective, i.e. the operators F k(t) with different k are
linearly independent.



                                                          18
                                     q1                                        q2




                                     t1                                      t2

                    a)                                                                                  b)
                         Figure 8: Two ribbons attached to the same site

   Finally, we can define a so-called skew antipode S̃⋆⋆ as follows
                                                                        m
                                          i Sn = Sj S̃n = δ n
                                        S̃m  i    m j
                                                                                                             (35)

In our case, S̃m    m
               i = Si , but this is not true for a generic Hopf algebra. The skew antipode have
the following properties similar to (33) and (34)
                                   q        k       q    n
                             l Λp Ωkn δ m = δ l Λp Ωkn S̃m = εp e
                           S̃n  lm               lm      k       q
                                                                                                             (36)

                      S̃il S̃jm Λlm
                                 p  = Λji  q
                                       q S̃p                     S̃pq Ωqij = Ωpml S̃m   l
                                                                                    j S̃i                    (37)
(Note the distinction between (33) and (36), however).
    The reader may be overwhelmed by a number of formal things, so let us summarize what we
know by now. We have defined two algebras, D and F , and their actions on the Hilbert space
N . In this context, we denote them by D(a) and F (t) because the actions depend on the site
a or on the ribbon t, respectively. Operators from D(a) affect one particle whereas operators
from F (t) affect two particles. The action of F (t) on the space of n-particle states L(x1 , . . . , xn )
depends only on the topological class of the ribbon t. This space have not been found yet, even
for n = 2. (It will be found after we learn more about local and ribbon operators). The algebra
F is a Hopf algebra. The comultiplication allows to make up a long ribbon from parts. There
is a formal duality between F and D. The comultiplication in F is dual to the multiplication
in D. The multiplication in F is dual to a comultiplication in D. (The meaning of the latter is
not clear yet).

5.3     Further properties of local and ribbon operators
Let us study commutation relations between ribbon operators. Consider two ribbons attached
to the same site, as shown in fig. 8 a or b. Then
                                                                               −1 hv, v −1 g)
                        F (h,g) (t1 ) F (v,u) (q1 ) =     F (v,u) (q1 ) F (v                    (t1 )
                                                                            (h, gu−1 vu)
                        F (h,g) (t2 ) F (v,u) (q2 ) =     F (v,u) (q2 ) F                  (t2 )
In a tensor form, these equations read as follows
                          F m(t1 ) F n(q1 ) =           Rik Ωn   m   j       l
                                                             ij Ωkl F (q1 ) F (t1 )
                                                                                                             (38)
                          F m(t2 ) F n(q2 ) =           F i(q2 ) F k(t2 ) Ωn   m
                                                                           ij Ωkl R̄
                                                                                     jl



                                                         19
                                                                              q’
                       q1                q2
                                                                       q2          q1


                        t1               t2                            t2            t1

                                a)                                            b)
                   Figure 9: Checking consistency of the commutation relations

where
                       R(h,g)(v,u) = δh,u δg,1                R̄(h,g)(v,u) = δh−1, u δg,1                   (39)
Note that
                             R̄ik Ωn   m
                                   ij Ωkl R
                                            jl
                                               = Rik Ωn   m
                                                      ij Ωkl R̄
                                                                jl
                                                                   = en em                                  (40)
   To prove19 (and to see the physical meaning of) this equation, consider the configuration
shown in fig. 9b. Clearly, F r(t2 t1 ) and F s(q ′ ) commute. On the other hand, F s(q ′ ) ≡ F s(q2 q1 ),
so F r (t2 t1 ) and F s(q2 q1 ) commute. It follows that R̄ik Ωn    m jl
                                                                ij Ωkl R   = enem. This identity
can be easily written in an invariant form, namely, R̄R = 1D⊗D , where R = Rjl Dj ⊗ Dl
and R̄ = R̄ik Di ⊗ Dk. It also implies that RR̄ = 1D⊗D because the algebra D ⊗ D is finite
dimensional. Thus, R̄ = R−1 .
   The tensor R⋆⋆ (or the element R ∈ D ⊗ D) is called the R-matrix. It satisfies the following
axioms
                   Λij
                    k R
                         km
                               = Ril Rjn Ωmln               RmkΛji       m
                                                                  k = Ωln R R
                                                                              li nj
                                                                                                  (41)
                                     Λji   i    j
                                      k = Ωlmr Ωpns R
                                                      lp
                                                         Λmn
                                                          k  R̄rs                                           (42)
where Ωilmr = ΩiluΩu              u    i
                           mr = ΩlmΩur . Eqs. (41) follow from (38). Conversely, these equations
ensure that the commutation relation are consistent. To prove the first equation in (41),
                                                                           ijm a
commute F m(t1 ) F i(q1 ) F j (q1 ) in two different ways. You will get Wab   F (q1 ) F b(t1 ), with
                                     ijm                   ijm a b
two different expressions for Wab        . Then calculate Wab e e using the axioms (30–32). The
second equation in (41) can be proven in a similar way.
    To prove eq. (42), consider the configuration shown in fig. 9a. Clearly, F i(q1 q2 ) ≡ F i(t1 t2 ),
so F j (t1 t2 ) F i(q1 q2 ) ≡ Λji   k                                                    j
                               k F (t1 t2 ). On the other hand, we can first expand F (t1 t2 ) and
  i
F (q1 q2 ) using the comultiplication rules, and then apply the commutation relations (38). The
result must be the same.
    Let t be a ribbon connecting sites a and b. The local and ribbon operators commute as
follows
                        a                              t                                b


   F m(t) Di(a) = Λjk m          l
                   i Ωkl Dj (a) F (t)                       Di(b) F m(t) = Ωm   kj l
                                                                            lk Λi F (t) Dj (b)              (43)
  19
     This proof is not rigorous, but an interested reader can easily fix it. Anyway, you can just substitute (39)
into (40) and check it directly.




                                                       20
These commutation relations can be also written in the form
                           Dj (a) F l(t) =     Λik  n  l   m
                                                j S̃k Ωnm F (t) Di(a)
                                                                                           (44)
                           F l(t) Dj (b)   =   Ωlmn S̃n  ki       m
                                                      k Λj Di(b) F (t)


where S̃⋆⋆ is the skew antipode (see eqs. (35,36)).
   Finally, we introduce some special elements C ∈ D and τ ∈ F . The first one has a clear
physical meaning: the corresponding operator C(a) = A(a) B(a) projects out states with no
particle at the site a. The element C can be represented in the form

                           C = ci Di            where c(h,g) = N −1 δh,1                   (45)

It has the following properties:

               CX = XC = ε(X) C            for any X ∈ D                 ε(C) = 1
or, in tensor notations,

                       Ωkij ci = Ωkji ci = εj ck                εk ck = 1                  (46)

   The element τ ∈ F is dual to C; it is defined as follows

                           τ = τiFi             where τ (h,g) = N −1 δ1,g                  (47)

Its properties are as follows

                      Λij       ji
                       k τ i = Λk τ i = e τ k
                                         j
                                                                ek τ k = 1                 (48)

Note that τ k ck = N −2 . Using these properties, we can we can derive an important consequence
from the commutation relations (43)

            τ s Ωsmp Spq F m(t) C(a) F q(t) = τ s Ωspm Spq F q (t) C(b) F m(t) = N −2      (49)

5.4    The space L(a, b)
Now we are in a position to find the space L(a, b) and to prove the assertions from Sec. 5.1.
The first assertion was that any excited spot can be transformed into one particle. It is simple
if we can transform two particles into one by ribbon operators. Let us choose an arbitrary site
b the excited spot to be compressed to. Let some constraint, A(s) − 1 ≡ 0 or B(p) − 1 ≡ 0,
be violated. Choose any site a containing the vertex s or the face p. Connect a and b by
a ribbon. By the assumption, we can clean up the site a while changing the state of b, but
without violating any more constraint. We can repeat this procedure again and again to clean
up the whole spot.
    So, we only need to show that two particles can be transformed into one. What does it mean
exactly? Physically, any transformation must be unitary, but it can involve also some external
system. (Otherwise, it is impossible to “decrease entropy”, i.e. to convert many states into
fewer). On the other hand, it is clear that unitarity is not relevant to this problem. However,
we should exclude degenerate transformations, such as multiplication by the zero operator. So,
it is better to reformulate the assertion as follows: any two-particle state (plus some other

                                                 21
excitations far away) can be obtained from one-particle states (plus the same excitations far
away). Let |ψi ∈ L(a, b, . . .) be such a two-particle state. We are going to use the formula (49).
Let
                 Gq = N 2 τ s Ωsmp Spq F m(t)               |η q i = C(a) F q (t) |ψi          (50)
Then |ψi = Gq |η q i. The states |η q i belong to L(b, . . .), i.e. do not contain excitation at a.
This is exactly what we need.
    The other two assertions were about the action of local operators on the space L(a, b), so
we need to find this space first. We can consider this space as a representation of the algebra
E ∼= E(t) generated by the operators Dj = Dj (a), F l = F l(t) and Dj′ = Dj (b). As a linear
space, E = D ⊗ F ⊗ D. (Thus, E has dimensionality N 6 ). Multiplication in E is defined by the
commutation relations (43). We will call E ∼= E(t) the algebra of extended ribbon operators. It
is just an algebra, not a Hopf algebra. More exactly, it is a finite-dimensional C ∗ -algebra. The
involution (=Hermitian conjugation) is given by the formulas (cf. (19))
                                                          −1 ,g)
    (D(h,g) )† = D(g−1 hg, g−1 )     (F (h,g) )† = F (h                ′
                                                                     (D(h,g) )† = D(g
                                                                                   ′
                                                                                      −1 hg, g −1 )   (51)

[Remark. Apparently, the algebra E will play the central role in a general theory of topolog-
ical quantum order. Indeed, we were lucky to define ribbon operators separately from local
operators. In the general case, ribbon operators should be mixed with local operators.]
    So, we are looking for a particular representation L of the algebra E. This representation
must contain a special vector |ξi (the ground state) such that

                            Dk |ξi = εk |ξi                 Dk′ |ξi = εk |ξi                          (52)

We start with constructing a representation Ľ spanned by the vectors |ψ ki = F k |ξi. (It will be
proven after that Ľ = L). We assume that the vectors |ψ ki are linearly independent. This need
not be the case in the representation L but we can postulate |ψ ki being linearly independent
in Ľ. Thus, L contains a factor-representation of Ľ.
    The representation Ľ is given by the formulas

    Dj |ψ ki = S̃n  k    m
                 j Ωnm |ψ i           F j |ψ ki = Λjk  m
                                                   m |ψ i              Dj′ |ψ ki = Ωkmj |ψ mi         (53)

It is easy to show that this representation is irreducible. Hence, L contains Ľ, i.e. the vectors
|ψ ki are linearly independent in L. The scalar products between the vectors |ψ ki can be found
from (53) and (51),
                                  hψ (v,u) |ψ (h,g) i = N −1 δv,h δu,g                        (54)
    To prove that Ľ = L, we use the equation (49) again. For an arbitrary two-particle state
|ψi ∈ L, define the vectors |η q i and operators Gq as in eq. (50). Then |ψi = Gq |η q i. One
could say that |η q i ∈ L(b) but, actually, the space L(b) is spanned by the sole vector |ξi. It
follows that |ψi ∈ Ľ — the assertion has been proven. Thus, the action of local and ribbon
operators on the space L = L(a, b) is given by eq. (53).
    It is easy to see that the action of D(a) on L(a, b) is exact (though it is reducible). Besides
that, D(a) is the commutant of D(b) in L(L(a, b)) and vise versa. (That is, D(a) consists of all
operators X ∈ L(L(a, b)) which commute with every Y ∈ D(b) ). Hence, D(a) includes all local
operators acting on the space L(a, b). Indeed, a local operator, which involves only spins near
the site a, must commute with any operator acting on distant spins. Of course, there are many

                                                 22
such operators, but their action on the two-particle space L(a, b) coincides with the action of
the operators from D(a). This is also true for a multi-particle excitation space L(x1 , . . . , xn ).
    The space L(x1 , . . . , xn ) can be described as follows. Let us connect the sites x1 , . . . , xn by
n − 1 ribbons t1 , . . . , tn−1 in an arbitrary way so that the ribbons form a tree. Then the vectors
|ψ k1 , . . . , kn−1 i = F k1 (t1 ) . . . F kn−1 (tn−1 ) |ξi form a basis of L(x1 , . . . , xn ). Choosing different
ribbons means choosing a different basis. In the next section we will give another description
of multi-particle excitation spaces.


6     Topological operators, braiding and fusion
Let us consider again the n-particle excitation space L = L(x1 , . . . , xn ). The algebra L(L)
includes the local operator algebras D(x1 ), . . . , D(x1 ). An operator Y ∈ L(L) which commute
with every X ∈ D(xj ) (j = 1, . . . , n) is called a topological operator. Physically, topological
operators correspond to nonlocal degrees of freedom. For n = 2, the algebra of topological
operators coincides with the center of D(x1 ) or D(x2 ). (The two centers coincide). Hence, the
only nonlocal degree of freedom is the type of either particle. (The two particles correspond to
dual representations of D; in other words, these are a particle and an anti-particle). So, there
is no hidden (i.e. quantum nonlocal) degree of freedom in this case. Such hidden degrees of
freedom appear for n ≥ 3.
    To describe the space L and operators acting on it, let us choose an arbitrary site x0
(distinct from x1 , . . . , xn ) and connect it with x1 , . . . , xn by non-intersecting ribbons t1 , . . . , tn ,
see fig. 10a. As stated above, the space L(x0 , x1 , . . . , xn ) is spanned by the vectors

                                  |ψ k1 , . . . , kn i = F k1 (t1 ) . . . F kn (tn ) |ξi                      (55)

The space in question, L = L(x1 , . . . , xn ) is contained in L(x0 , x1 , . . . , xn ). It consists of all
vectors |ψi ∈ L(x0 , x1 , . . . , xn ) which are invariant under the action of D(x0 ) on the latter
space.
    The advantage of this description is that we can easily find all operators on the space
L(x0 , x1 , . . . , xn ) which commute with D(x1 ) ⊗ . . . ⊗ D(xn ). These are simply operators which
                                                                                                              (r)
act on the ends of the ribbons t1 , . . . , tn attached to the site x0 . More exactly, an operator Dj
(r = 1, . . . , n) acts on the r-th ribbon as Dj′ = Dj (x0 ) (see eq.(53)), but does not affect the
other ribbons,
                                        
                         (1)         (n)
                      Dj1 ⊗ . . . ⊗ Djn |ψ k1 , . . . , kn i = Ωkm11 j1 . . . Ωkmnn jn |ψ m1 , . . . , mn i (56)

Thus we arrive to an interesting physical conclusion. Let us consider only one particle attached
to an end of a semi-infinite ribbon (an analog of Dirac’s string). Then the topological operators
act on the far end of the ribbon.
Example. Let us see how the topological operators act on magnetic vortices. As shown in
Sec. 5.1, a vortex type is characterized by a conjugacy class C of the group G. Individual
topological states of the particle are characterized by particular elements v ∈ C. In terms of
the notation (55), such a state can be represented as follows
                                                   X
                                |u, vi = |C|1/2           |ψ (u,x) i
                                                            x: x−1 ux=v


                                                           23
              x1    x2     x3     x4                 xs        xs+1       t’s+1              xs        xs+1

                                                   ts            t’s                        t’s         t’s+1

                                                                                                    q

                         x0                               x0                                      x0

                       a)                                 b)                                      c)
               Figure 10: Braiding and fusion in terms of ribbon transformations

                                                                                        ′
where u ∈ C characterize the local state of the particle. One can easily check that D(h,g) |u, vi =
δh, gvg−1 |u, hi. This is consistent with eq. (22). Note that the local degree of freedom, u, is not
affected.
      How can we physically apply topological operators to particles? We can just move the
particles around each other; this process is called braiding. Let us see what happens if we
interchange two particles, xs and xs+1 , counterclockwise, as shown in fig. 10b. The state
|ψ . . . , k, l, . . .i becomes a new state

               |ψ . . . , k, l, . . .inew = Rx |ψ . . . , k, l, . . .i = . . . F k(t′s ) F l(t′s+1 ) . . . |ξi

To represent this state in the old basis, we should represent the operator F k(t′s ) F l(t′s+1 ) in
terms of F m(ts ) and F n(ts+1 ). Obviously, F k(t′s ) = F k(ts+1 ); also F l(t′s+1 ) ≡ F l(ts ) as long as
there is no particle at xs+1 , i.e. the operator F k(ts+1 ) is not applied yet. Hence

                                     F k(t′s ) F l(t′s+1 ) ≡ F k(ts+1 ) F l(ts )

Now we can apply the second commutation relation from (38). (Actually, we should reverse
it). It follows that

                        F k(ts+1 ) F l(ts ) = Rji Ωlmi Ωknj F m(ts ) F n(ts+1 )
                                                                   
                                                         (s)  (s+1)
                       Rx |ψ . . . , k, l, . . .i = Rji Di ⊗ Dj       |ψ . . . , l, k, . . .i

(see eq. (56)). Consequently, the counterclockwise interchange operator has the form

                              Rx = Rji (Di′ ⊗ Dj′ ) σ = σ Rij (Di′ ⊗ Dj′ )                                       (57)

where σ is the permutation operator, and Di′ , Dj′ are understood as topological operators.
(Note that the operator σ permutes both topological and local degrees of freedom).
Example. Consider two magnetic vortices characterized by topological parameters v1 , v2 ∈ G.
The operator R x acts on the state |v1 , v2 i as follows

                                          Rx |v1 , v2 i = |v1 v2 v1−1 , v1 i                                     (58)

(The local parameters, u1 and u2 , are suppressed in this formula).

                                                            24
   Finally, let us see what happens if two particles, xs and xs+1 , fuse into one. The resulting
particle can be characterized by the action of topological operators on it. From this point of
view, we can just glue parts of the corresponding ribbons (see fig. 10c) instead of fusing the
particles themselves. Then
                                                         m ′     n ′
                     F k(ts ) F l(ts+1 ) ≡ Ωkmi Ωlnj Λij                   p
                                                      p F (ts ) F (ts+1 ) F (q)

                            |ψ ...,k,l,...i ≡ Ωkmi Ωlnj Λij m ′     n ′
                                                         p F (ts ) F (ts+1 ) |ψ
                                                                                ...,p,...
                                                                                          i
                       (s)  (s+1)
                  Λuv
                   r D u ⊗ Dv     ≡ Dr′
where Dr′ acts on the end of the ribbon q. Thus, fusion is described by the comultiplication in
the algebra D, see equation (27). (To avoid confusion, one should replace D⋆ with D⋆′ in that
equation). The topological operator ∆(Dk′ ) acts on a particle pair as the topological operator
Dk′ on the particle resulting from fusion.
Example. Consider a pair of opposite magnetic vortices |v, v −1 i. The operators ∆(Dk′ ) act
on this state as follows
                               ′
                            ∆(D(h,g) ) |v, v −1 i = δh,1 |gvg −1, gv −1g −1 i                     (59)
It terms of the representation classification (see Sec. 5.1), this action corresponds to the pair
(C, χ), where C = {1}, and χ is the adjoint representation of G. Thus, when opposite magnetic
vortices fuse, the resulting particle has no magnetic charge but may have some electric charge.


7      Universal computation by anyons
(This section should be considered as an abstract of results to be presented elsewhere).
    Universal quantum computation is possible in the model based on the permutation group
S5 . (Unsolvability of the group seems to be important). Vortex pairs |v, v −1 i, where v is a
transposition, are used as qubits. It is possible to perform the following operations.
    1. To produce pairs with zero charge. If a pair is created from the ground state, it has no
       charge automatically.
    2. To measure the electric charge of a vortex pair destructively. For this, we should simply
       fuse the the pair into one particle.
    3. To perform the following unitary transformation on two pairs
                          |u, u−1 i ⊗ |v, v −1 i 7→ |vuv −1, vu−1v −1 i ⊗ |v, v −1 i              (60)
       For this, we pull the first pair (as a whole) between the particles of the second pair.
    4. To measure the value of v and produce an unlimited number of pure states |v, v −1 i for
       any given transposition v (say, (1, 2) or (2, 3) ). [At first sight, it is impossible because we
       can only measure the conjugacy class of a v. However, we can agree on a given state to
       correspond to v = (1, 2). Then we use it as a reference to produce an unlimited number
       of copies.]
    The operations 3 and 4 are sufficient to perform universal classical computation. It is
relatively simple to run quantum algorithms based on measurements [24]. Simulating a universal
gate set is more subtle and requires composite qubits. That is, a usual qubit (with two distinct
states) is represented by several vortex pairs.

                                                    25
Concluding remarks
It has been shown that anyons can arise from a Hamiltonian with local interactions but without
any symmetry. These anyons can be used to perform universal quantum computation. There are
still many things to do and questions to answer. First of all, it is desirable to find other models
with anyons which allow universal quantum computation. (The group S5 is quite unrealistic for
physical implementation). Such models must be based on a more general algebraic structure
rather than the quantum double of a group algebra. A general theory of anyons and topological
quantum order is lacking. [In a sense, a general theory of anyons already exists [10]; it is based
on quasi-triangular quasi-Hopf algebras. However, this theory either merely postulates the
properties of anyons or connects them to certain field theories. This is quite unlike the theory of
local and ribbon operators which describes both the properties of excitations and the underlying
spin entanglement.] It is also desirable to formulate and prove some theorem about existence
and the number of local degrees of freedom. (It seems that the local degrees of freedom are a
sign that anyons arise from a system with no symmetry in the Hamiltonian). Finally, general
understanding of dynamically created, or “materialized” symmetry is lacking. There one may
find some insights for high energy physics. If we adopt a conjecture that the fundamental
Hamiltonian or Lagrangian is not symmetric, we can probably infer some consequences about
the particle spectrum.

Acknowledgements. I am grateful to J. Preskill, D. P. DiVincenzo and C. H. Bennett
for interesting discussions and questions which helped me to clarify some points in my con-
structions. This work was supported, in part, by the Russian Foundation for Fundamental
Research, grant No 96-01-01113. Part of this work was completed during the 1997 Elsag-Bailey
– I.S.I. Foundation research meeting on quantum computation.


References
 [1] P. Shor, Algorithms for quantum computation: discrete logarithms and factoring. In Pro-
     ceedings of the 35th Annual Symposium on Fundamentals of Computer Science. Los Alami-
     tos, CA: IEEE Press, pp. 124–134 (1994).

 [2] P. Shor, Fault-tolerant quantum computation. In Proceedings of the Symposium on the
     Foundations of Computer Science. Los Alamitos, CA: IEEE Press (1996); e-print quant-
     ph/9605011.

 [3] E. Knill and R. Laflamme, Concatenated quantum codes, e-print quant-ph/9608012 (1996)

 [4] E. Knill, R. Laflamme and W. Zurek, Accuracy threshold for quantum computation, e-
     print quant-ph/9610011 (1996).

 [5] D. Aharonov and M. Ben-Or, Fault tolerant quantum computation with constant error,
     e-print quant-ph/9611025 (1996).

 [6] A. Yu. Kitaev, Quantum computing: algorithms and error correction, Russian Math.
     Surveys, to be published (1997).



                                                26
 [7] C. Zalka, Threshold estimate for fault tolerant quantum computing, e-print quant-
     ph/9612028 (1996).
 [8] A. Yu. Kitaev, Quantum error correction with imperfect gates. In Proceedings of the Third
     International Conference on Quantum Communication and Measurement, September 25-
     30, 1996, to be published (1997).
 [9] F. Wilczek, Fractional statistics and anyon superconductivity, World Scientific, Singapore
     (1990).
[10] R. Dijkgraaf, V. Pasquier and P. Roche, Quasi-Hopf algebras, group cohomology and
     orbifold models, Nucl. Phys. B (Proc. Suppl.) 18B (1990).
[11] F. A. Bais P. van Driel and M. de Wild Propitius, Quantum symmetries in discrete gauge
     theories, Phys. Lett. B280, 63 (1992).
[12] F. A. Bais and M. de Wild Propitius, Discrete gauge theories, e-print hep-th/9511201
     (1995).
[13] H. K. Lo and J. Preskill, Non-abelian vortices and non-abelian statistics, Phys. Rev. D48,
     4821 (1993).
[14] G. Castagnoli and M. Rasetti, The notion of symmetry and computational feedback in the
     paradigm of steady, simultaneous quantum computation, Int. J. of Mod. Phys. 32, 2335
     (1993).
[15] D. Gottesman, Phys. Rev. A54, 1862 (1996).
[16] A. R. Calderbank, E. M. Rains, P. M. Shor and N. J. A. Sloane, Quantum error correction
     and orthogonal geometry, Phys. Rev. Lett. 78, 405 (1997).
[17] A. R. Calderbank and P. W. Shor, Good quantum error-correcting codes exist, e-print
     quant-ph/9512032 (1995)
[18] D.Arovas, J.R.Schrieffer, and F.Wilczek, Fractional statistics and the quantum Hall Effect,
     Phys. Rev. Lett. 53, 722–723 (1984).
[19] T.Einarsson, Fractional statistics on a torus, Phys. Rev. Lett. 64, 1995-1998 (1984).
[20] V. G. Drinfeld, Quantum groups. In Proc. Int. Cong. Math. (Berkley, 1986), pp. 798-820
     (1987).
[21] M. Sweedler, Hopf algebras, W. A. Benjamin, Inc., New York (1969).
[22] S. Majid, Quasi-triangular Hopf algebras and Yang-Baxter equation, Intern. J. of Modern
     Phys. A5, 1-91 (1990).
[23] C. Kassel, Quantum groups, Springer-Verlag, New York (1995).
[24] A. Yu. Kitaev, Quantum measurements and Abelian stabilizer problem, e-print quant-
     ph/9511026 (1995).
[25] G. t’Hooft, Nucl. Phys. B138, 1 (1978).


                                               27
