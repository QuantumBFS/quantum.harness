---
source: "https://arxiv.org/abs/cond-mat/0010440"
type: "arxiv"
canonical_id: "cond-mat/0010440"
title: "Unpaired Majorana fermions in quantum wires"
authors: "A. Kitaev"
year: "2000"
venue: "Physics-Uspekhi"
arxiv_id: "cond-mat/0010440"
doi: "10.1070/1063-7869/44/10S/S29"
full_text: yes
---

# Unpaired Majorana fermions in quantum wires

**Authors:** A. Kitaev

**Citation:** Physics-Uspekhi, vol. 44, pp. 131-136, 2000

**arXiv:** [cond-mat/0010440](https://arxiv.org/abs/cond-mat/0010440)

**DOI:** [10.1070/1063-7869/44/10S/S29](https://doi.org/10.1070/1063-7869/44/10S/S29)

## Abstract

Certain one-dimensional Fermi systems have an energy gap in the bulk spectrum while boundary states are described by one Majorana operator per boundary point. A finite system of length L possesses two ground states with an energy difference proportional to exp(-L/l0) and different fermionic parities. Such systems can be used as qubits since they are intrinsically immune to decoherence. The property of a system to have boundary Majorana fermions is expressed as a condition on the bulk electron spectrum. The condition is satisfied in the presence of an arbitrary small energy gap induced by proximity of a three-dimensional p-wave superconductor, provided that the normal spectrum has an odd number of Fermi points in each half of the Brillouin zone (each spin component counts separately).

## Full Text

# Unpaired Majorana fermions in quantum wires

#### Alexei Yu. Kitaev [∗] Microsoft Research Microsoft, #113/2032, One Microsoft Way, Redmond, WA 98052, U.S.A. kitaev@microsoft.com 27 October 2000

Abstract


Certain one-dimensional Fermi systems have an energy gap in the
bulk spectrum while boundary states are described by one Majorana
operator per boundary point. A finite system of length L possesses two
ground states with an energy difference proportional to exp(−L/l0)
and different fermionic parities. Such systems can be used as qubits
since they are intrinsically immune to decoherence. The property of a
system to have boundary Majorana fermions is expressed as a condition on the bulk electron spectrum. The condition is satisfied in the
presence of an arbitrary small energy gap induced by proximity of a
3-dimensional p-wave superconductor, provided that the normal spectrum has an odd number of Fermi points in each half of the Brillouin
zone (each spin component counts separately).

### Introduction


Implementing a full scale quantum computer is a major challenge to modern physics and engineering. Theoretically, this goal should be achievable


∗On leave from L. D. Landau Institute for Theoretical Physics


1


due to the possibility of fault-tolerant quantum computation [1]. Unlimited quantum computation is possible if errors in the implementation of each
gate are below certain threshold [2, 3, 4, 5]. Unfortunately, for conventional
fault-tolerance schemes the threshold appears to be about 10 [−][4], which is
beyond the reach of current technologies. It has been also suggested that
fault-tolerance can be achieved at the physical level (instead of using quantum error-correcting codes). The first proposal of these kind [6] was based
on non-Abelian anyons in two-dimensional systems. The relation between
quantum computation, anyons and topological quantum field theories was
independently discussed in [7]. A mathematical result about universal quantum computation with certain type of anyons has been obtained recently [8],
but, generally, this approach is still undeveloped. In these paper we describe
another (theoretically, much simpler) way to construct decoherence-protected
degrees of freedom in one-dimensional systems (“quantum wires”). Although
it does not automatically provide fault-tolerance for quantum gates, it should
allow, when implemented, to build a reliable quantum memory.
The reason why quantum states are so fragile is that they are sensitive
to errors of two kinds. A classical error, represented by an operator σj [x][, flips]
the j-th qubit changing |0⟩ to |1⟩ and vice versa. A phase error σj [z] [changes]
the sign of all states with the j-th qubit equal to 1 (i. e. j-th spin down, if
the qubits are spins) relative to the states with the j-th qubit equal to 0.
It is generally easy to get rid of one type of errors, but not both. However,
the following method of eliminating the classical errors is worth considering.
Let each qubit be a site that can be either empty or occupied by an electron
(with spin up, say, the other spin direction being forbidden). Let us denote
the empty and the occupied states by |0⟩ and |1⟩, respectively. (Such sites are
not exactly qubits because electrons are fermions, but they can be also used
for quantum computation [9]). Now single classical errors become impossible
because the electric charge is conserved. Even in superconducting systems,
the fermionic parity (i. e. the electric charge (mod 2)) is conserved. Two
classical errors can still happen at two sites simultaneously, but this would
require that an electron jumps from one site to the other. Such jumps can be
avoided by placing the “fermionic sites” far apart from each other, provided
the medium between them has an energy gap in the excitation spectrum.
Obviously, this method does not protect from phase errors which are now
described by the operators a [†] j [a][j][. To the contrary, different electron configu-]
rations will have different energies and thus will pick up different phases over


2


time. Even without actual inelastic processes, this will produce the same
effect as decoherence. However, a simple mathematical observation suggests
that the situation could be improved. Each fermionic site is described by a
pair of annihilation and creation operators aj, a [†] j [. One can formally define]
Majorana operators

c2j−1 = aj + a [†] j [,] c2j = [a][j][ −] [a] j [†] (j = 1, . . ., N) (1)
i

which satisfy the relations

c [†] m [=][ c][m][,] clcm + cmcl = 2δlm (l, m = 1, . . ., 2N). (2)


If the operators c2j−1 and c2j belonged to different sites then the phase error
a [†] j [a][j] [=] 21 [(1 +][ ic][2][j][−][1][c][2][j][) would be unlikely to occur.] Indeed, it would require interaction between the two “Majorana sites” which could be possibly
avoided. Note that a single Majorana operator c2j−1 or cj can not appear
as a term in any reasonable Hamiltonian because it does not preserve the
fermionic parity. Thus an isolated Majorana site (usually called a Majorana
fermion) is immune to any kind of error!
Unfortunately, Majorana fermions are not readily available in solid state
systems. The goal of this paper is to construct Hamiltonians which would
give rise to Majorana fermions as effective low-energy degrees of freedom.
Surprisingly, this can be done even with non-interacting electrons. (Some
interaction is actually needed to create superconductivity, but it can be effectively described by terms like ∆ajak). The general idea is quite simple.
An arbitrary quadratic Hamiltonian can be written in the form



H = [i]

4




- Almclcm (A [∗] lm [=][ A][lm][ =][ −][A][ml][)][.] (3)

l,m



Its ground state can be described as “pairing” of Majorana operators: normal mode creation and annihilation operators ˜a [†] m [,][ ˜][a][m][, which are certain lin-]
ear combinations of cl, come in pairs. (In this sense, an insulator and a
superconductor represent different types of pairing). In some cases, most
Majorana operators are paired up with an energy gap while few ones (localized at the boundary or defects) remain “free”. For example, unpaired
Majorana fermions exist on vortices in chiral 2-dimensional p-wave superconductors [10, 11]. We will show that Majorana fermions can also occur at
the ends of quantum wires.


3


### 1 A toy model and the qualitative picture

We are going to describe a simple but rather unrealistic model which exhibits
unpaired Majorana fermions. It attempts to catch two important properties
which seem necessary for the phenomenon to occur. Firstly, the U(1) symmetry aj �→ e [iφ] aj, corresponding to the electric charge conservation, must
be broken down to a Z2 symmetry, aj �→−aj. Indeed, if a single Majorana
operator can be localized, symmetry transformation should not mix it with
other operators. So we should consider superconductive systems. The particular mechanism of superconductivity is not important; we may just think
that our quantum wire lies on the surface of 3-dimensional superconductor
(see fig. 1). The second property is less obvious and will be fully explained
in Sec. 2. Roughly speaking, the electron spectrum must strongly depend on
the spin. Here we will simply assume that only one spin component (say, ↑)
is present. [1]



✁ ✁

b [′] b [′′]

✁ ✁



b [′] b [′′]

✁

✁

θ ✁



θ



Figure 1: A piece of “quantum wire” on the surface of 3-dimensional superconductor.


Consider a chain consisting of L ≫ 1 sites. Each site can be either empty
or occupied by an electron (with a fixed spin direction). The Hamiltonian is



H1 = 
j



�−w(a [†] j [a][j][+1] [+][ a] j [†] +1 [a][j][)][ −] [µ][(][a][†] j [a][j] [−] [1] 2 [) + ∆][a][j][a][j][+1][ + ∆][∗][a] j [†] +1 [a][†] j �. (4)



Here w is a hopping amplitude, µ a chemical potential, and ∆= |∆|e [iθ] the
induced superconducting gap. It is convenient to hide the dependence on the
phase parameter θ into the definition of Majorana operators:



2

c2j−1 = e [i][ θ]



2 2
a [†] j [,] c2j = −ie [i][ θ]



2 2
aj + e [−][i][ θ]



2 2
aj + ie [−][i][ θ]



2
a [†] j (j = 1, . . ., L). (5)



1 It appears that only a triplet (p-wave) superconductivity in the 3-dimensional substrate can effectively induce the desired pairing between electrons with the same spin
direction — at least, this is true in the absence of spin-orbit interaction.


4


In terms of this operators, the Hamiltonian becomes



H1 = [i]

2





j



�−µc2j−1c2j + (w + |∆|)c2jc2j+1 + (−w + |∆|)c2j−1c2j+2�. (6)



Let us start with two special cases.

a) The trivial case:i |∆| = w = 0, µ < 0. Then H1 = −µ �j [(][a][†] j [a][j] [−] 2 [1][) =]

2 [(][−][µ][)][ �] j [c] 2j−1 [c] 2j [. The Majorana operators][ c] 2j−1 [, c] 2j [from the same]
site j are paired together to form a ground state with the occupation
number 0.


b) |∆| = w > 0, µ = 0. In this case

H1 = iw             - c2jc2j+1. (7)

j



Now the Majorana operators c2j, c2j+1 from different sites are paired
together (see fig. 2). One can define new annihilation and creation
operators ˜aj = 2 [1] [(][c][2][j][ +][ ic][2][j][+1][)][,][ ˜][a] j [†] [=][ 1] 2 [(][c][2][j][ −] [ic][2][j][+1][) which span the sites]



2 [1] [(][c][2][j][ +][ ic][2][j][+1][)][,][ ˜][a] j [†] [=][ 1] 2



operators ˜aj = 2 [(][c][2][j][ +][ ic][2][j][+1][)][,][ ˜][a] j [=][ 1] 2 [(][c][2][j][ −] [ic][2][j][+1][) which span the sites]

j and j + 1. The Hamiltonian becomes 2w �jL=1−1 [(˜][a] j [†][a][˜][j] [−] [1] 2 [). Ground]



j and j + 1. The Hamiltonian becomes 2w �j=1 [(˜][a] j [a][˜][j] [−] 2 [). Ground]

states satisfy the condition ˜aj|ψ⟩ = 0 for j = 1, . . ., L − 1. There are
two orthogonal states |ψ0⟩ and |ψ1⟩ with this property. Indeed, the
Majorana operators b [′] = c1 and b [′′] = c2L remain unpaired (i. e. do not
enter the Hamiltonian), so we can write




- ib [′] b [′′] |ψ0⟩ = |ψ0⟩, −ib [′] b [′′] |ψ1⟩ = −|ψ1⟩. (8)



c1 c2 c3

✎ ☞ ✎

s s s

✍ ✌ ✍



✎1

s

✍



☞



c3 c4

✎ ☞

s s

✍ ✌



✍



c2L−1 c2L

✎ ☞

s s

✍ ✌



✍



c1 c2 c3

✎ ☞ ✎

s s s

✍ ✌ ✍



✎1

s

✍



c2L−1 c2L

✎ ☞

s s

✍ ✌



✍



☞



c3 c4

✎ ☞

s s

✍ ✌



✍



☞



. . . ✎2L



☞L



☞



. . . ✎2L



☞L



a)



b)



Figure 2: Two types of pairing.


Note that the state |ψ0⟩ has an even fermionic parity (i. e. it is a superposition
of states with even number of electrons) while |ψ1⟩ has an odd parity. The
parity is measured by the operator


P = (−ic2j−1c2j). (9)

       
j


5


These two cases represent two phases, or universality classes which exist in
the model. A subtle point is that both phases have the same bulk properties.
In fact, one phase can be transformed to the other (and vice versa) by mere
permutation of Majorana operators,


cm �→ cm+1. (10)


Such a local transformation (operator algebra automorphism) is usually considered as “equivalence” in the study of lattice models. [2] Yet the boundary
properties of the two phases are clearly different: only the phase (b) has
unpaired Majorana fermions at the ends of the chain. This is due to the fact
that the operators c2j−1, c2j belong to one physical site while c2j, c2j+1 do not.
We may put it this way: one can not cut a physical site into two halves; if
one could, both types of boundary states would be possible in both phases.
Also note that the transformation (10) can not be performed in a continuous fashion, starting from the identity transformation. From the mathematical perspective, it means that one should have different definitions for
“weak” and “strong” equivalence of lattice models . We will not touch such
abstract matters here.
Now we want to study the model at arbitrary values of w, µ and ∆. Let
us begin with some generalities. Let N be the total number of fermionic
sites in the system, for now N = L. The Hamiltonian (6) has the general
form (3). Hence it can be reduced to a canonical form



N




Hcanonical = [i]

2



N

- ǫmb [′] m [b][′′] m [=]

m=1




- ǫ(˜a [†] m [a][˜][m][ −] 2 [1]

m=1



2 [)] (ǫm ≥ 0). (11)



Here b [′] m [, b][′′] m [are real linear combinations of][ c][2][j][−][1][, c][2][j] [with the same com-]
mutation relations whereas ˜am = 12 [(][b] m [′] [+][ ib] m [′′] [), ˜][a][†] m [=] 12 [(][b] m [′] [−] [ib] m [′′] [). More]

2 Nonlocal transformations can change the physical properties of the model even more
j−1 j−1
dramatically. The Jordan-Wigner transformation c2j−1 �→ σj [x] �k=1 [σ] k [z][,][ c][2][j][ �→] [σ] j [y] �k=1 [σ] k [z]
takes our model to a spin chain with xx and yy interactions and a z-directed magnetic
field. Unlike (10), the Jordan-Wigner transformation is well defined at the ends of the
chain. However, this mathematical procedure falls apart in the physical context, as far as
perturbations are involved. Indeed, the phase (b) has now an order parameter ⟨σ [x] ⟩̸= 0.
External fields will interact with the order parameter breaking the phase coherence between
|ψ0⟩ and |ψ1⟩.


6


specifically,


b [′] 1

 





















































b [′] 1
b [′′] 1
...
b [′] N
b [′′] N
















0 ǫ1
−ǫ1 0
...
0 ǫN
−ǫN 0



= W
















c1
c2
...
c2N −1
c2N



, WAW [T] =



,



(12)
where W is a 2N × 2N real orthogonal matrix (W [T] W = WW [T] = I) whose
rows are eigenvectors of A. The numbers ǫm ≥ 0 are one-particle excitation
energies. However, it is more convenient to deal with a “double spectrum”
{ǫm, −ǫm} since the matrix A has eigenvalues ±iǫm.
The bulk spectrum (energy vs. momentum) is given by


ǫ(q) = ±�(2w cos q + µ) [2] + 4|∆| [2] sin [2] q, −π ≤ q ≤ π. (13)


We may conjecture that the phases (a) and (b) extend to connected domains
in the parameter space where the spectrum has a gap. The signs of µ and w
seem not to be important, so we actually expect that the phase (a) occurs at
2|w| < |µ| while the phase (b) occupies the domain 2|w| > |µ|, ∆ = 0. (The
phase boundary is given by the equation 2|w| = |µ| while ∆= 0, 2|w| > |µ|
is a line of normal metal phase inside the domain (b)).
To verify the conjecture, we need to find boundary modes. They correspond to eigenvectors of A localized near the ends of the chain. Due to the
spectrum symmetry ǫ �→−ǫ, zero eigenvalues can occur in a general position.
If exist, such zero modes should have the form



b [′] = j [(][α] + [′] [x] + [j] [+][ α] - [′] [x] - [j] [)][ c] 2j−1 −µ ± 
  
x± =
b [′′] = �j [(][α] + [′′] [x] + [−][j] [+][ α] - [′′] [x] - [−][j][)][ c] 2j



b [′] = �j [(][α] + [′] [x] + [j] [+][ α] - [′] [x] - [j] [)][ c] 2j−1



µ [2] - 4w [2] + 4|∆| [2]



b [′′] = �j [(][α] + [′′] [x] + [−][j] [+][ α]  - [′′] [x]  - [−][j][)][ c] 2j 2(w + |∆|)

(14)
We will consider two cases corresponding to the expected existence domains
of the two phases.



a) If 2|w| < |µ|, we have |x+| > 1, |x−| < 1 or |x+| < 1, |x−| > 1.
Therefore, only one of the coefficients α+ [′] [, α]  - [′] [(or][ α] + [′′] [, α]  - [′′] [) can be non-]
zero, depending on whether the mode is to be localized at the left or at
the right end of the chain. This makes it impossible to satisfy boundary
conditions. So the supposed zero modes (14) do not exist.


7


b) If 2w > |µ|, ∆ = 0, we find that |x+|, |x−| < 1. Hence b [′] is localized
near j = 0 whereas b [′′] is localized near j = L. There are also boundary
conditions α+ [′] [+][ α]   - [′] [= 0,][ α] + [′′] [x] + [−][(][L][+1)] + α− [′′] [x]   - [−][(][L][+1)] = 0, but they can
be satisfied too. The zero modes b [′], b [′′] are actually the same as the
unpaired Majorana fermions discussed before. If −2w > |µ|, ∆ = 0
then b [′] and b [′′] change places. Thus the unpaired Majorana fermions
exist in the whole expected domain of the phase (b).


The above analysis is exact in the limit L →∞. If the chain length L
is finite, there is a weak interaction between b [′] and b [′′] . (For definiteness, we
will always assume that b [′] is at the left end of the chain whereas b [′′] is at the
right end). This interaction is described by an effective Hamiltonian

Heff = 2 [i] [t b][′][b][′′][,] t ∝ e [−][L/l][0], (15)


where l0 [−][1] is the smallest of ln |x+| and ln |x−| (note that both logarithms
have the same sign). Thus the energies of the ground states��� ��� ��� ��� |ψ0⟩ and |ψ1⟩
(see eq. (8)) differ by t. Note that it is not obvious any more which state
of the two is even and which is odd. In the case −2w > |µ|, the parity
is proportional to (−1) [L] . (This factor is the parity of the bulk part of the
chain).
The effective Hamiltonian (15) still holds if we include small electronelectron interaction (a four-fermion term) into (4). Indeed, the physical
meaning of t is an amplitude for a fermionic quasiparticle to tunnel across the
chain. In a long chain, this amplitude vanishes as e [−][L/l][0] if the bulk spectrum
has a gap.
Finally, we will discuss a role of the phase parameter θ (∆= e [iθ] |∆|).
According to eq. (5), the Majorana operators c2j−1, c2j are multiplied by
−1 when θ changes by 2π. The physical parameter ∆is the same at θ and
θ+2π, of course, but the ground states should undergo certain transformation
as θ changes to θ + 2π adiabatically. Note that the transformation cm �→
−cm also occurs if one conjugates cm by the parity operator P . Within the
effective Hamiltonian approach, P is the same as s(L)(−ib [′] b [′′] ) (s(L) = ±1).
Hence the adiabatic change of the superconducting phase by 2π results in
the unitary transformation


V = s(L)(−ib [′] b [′′] ) : V |ψ0⟩ = |ψ0⟩, V |ψ1⟩ = −|ψ1⟩. (16)


8


This is equivalent to transfer of an electron between the ends of the chain.
Some physical consequences of this result will be mentioned in Sec. 3.

### 2 A general condition for Majorana fermions


Let us consider a general translationally invariant one-dimensional Hamiltonian with short-range interactions. It has been mentioned that the necessary conditions for unpaired Majorana fermions are superconductivity and a
gap in the bulk excitation spectrum. The latter is equivalent to the quasiparticle tunneling amplitude vanishing as e [−][L/l][0] . Besides that, it is clear
that there should be some parity condition. Indeed, Majorana fermions at
the ends of parallel weakly interacting chains may pair up and cancel each
other (i. e the ground state will be non-degenerate). So, provided the energy gap, each one-dimensional Hamiltonian H is characterized by a “Majorana number” M = M(H) = ±1: the existence of unpaired Majorana
fermions is indicated as M = −1. The Majorana number should satisfy
M(H [′] ⊕ H [′′] ) = M(H [′] )M(H [′′] ), where ⊕ means taking two non-interacting
chains.
Remarkably, the Majorana number reveals itself even if the chain is closed
into a loop. This is handy as it eliminates the need to study boundary modes.
Let H(L) be the Hamiltonian of a closed chain of length L ≫ l0. (H itself is
a template which is used to generate H(L) for any L). We claim that


P (H(L1 + L2)) = M(H) P (H(L1)) P (H(L2)), (17)


where P (X) denotes the ground state parity of a Hamiltonian X (assuming
that the ground state is unique).



L1
❡❡❡❡❡❡

b [′] 1 b [′′] 1



L2
❡❡❡❡❡

b [′] 2 b [′′] 2



L1
❡❡❡❡❡❡

b [′] 1 b [′′] 1


b)



L2
❡❡❡❡❡

b [′] 2 b [′′] 2



a)



Figure 3: Reconnecting closed chains.


The following argument justifies eq. (17). An open chain of length L
can be described by an effective Hamiltonian which only includes boundary


9


modes. If M(H) = −1, there are Majorana operators b [′], b [′′] associated with
the ends of the chain. The parity operator P (see eq. (9)) can be replaced
by s(L)(−ib [′] b [′′] ), where s(L) = ±1. Thus the fermionic parity of |ψα⟩ is
s(L) (−1) [α], α = 0, 1. If we close the chain, the effective Hamiltonian is
Heff(L) = 2i [u b][′′][b][′][. (We have chosen to write][ b][′′][b][′][ in this order because][ b][′′]

precedes b [′] in the left-to-right order on the loop, where they are next to each
other). The parameter u represents direct interaction between the chain ends
(unlike t from eq. (15)), so u does not depend on L. The ground state of the
closed chain is |ψ1⟩ if u > 0 and |ψ0⟩ if u < 0. Hence


P (H(L)) = −s(L) sgn u.


Now let us take two chains, one of length L1, the other of length L2.
There are two ways to close them up, see fig. 3. Both cases can be described
by effective Hamiltonians:



2 [i] [u][ (][b] 1 [′′][b][′] 1 [+][b][′′] 2 [b][′] 2 [)][,] Heff(L1 +L2) = 2 [i]



Heff(L1)⊕Heff (L2) = [i]



2 [u][ (][b] 1 [′′][b][′] 2 [+][b][′′] 2 [b][′] 1 [)][.]



It follows that


P (H(L1)) P (H(L2)) = s(L1) s(L2), P (H(L1 + L2)) = − s(L1) s(L2).


So the equation (17) holds for M = −1. It also obviously holds for M = 1
because in this case there are no boundary modes to worry about.
Computing the Majorana number in general (especially for strongly correlated systems) may be a difficult task. However, the computation can be
carried through for any system of non-interacting electrons. Consider a periodic chain of L unit cells with n fermionic sites (i. e. 2n Majorana operators)
per cell, which totals to N = nL fermionic sites. We will index the Majorana
operators as clα, where l = 1, . . ., L, α = 1, . . ., 2n. The Hamiltonian is



H = [i]

4





l,m




- Bαβ(m − l) clαcmβ �Bαβ(j) [∗] = Bαβ(j) = −Bβα(−j)�.

α,β



(18)
We assume that the chain forms a loop, so m − l should be taken (mod L).
Eq. (18) is a special case of (3), so we will first find P (H) for the general
quadratic Hamiltonian (3), assuming that the matrix A is not degenerate.
The canonical form of this Hamiltonian (11) has an even ground state |0⟩.


10


The transformation (12) can be represented as conjugation by the paritypreserving unitary operator U = exp� 41 l,m [D] lm [c] l [c] m� if W has the form

          W = exp(D) for some real skew-symmetric matrix D, i. e. if det W = 1.
Otherwise, the transformation (12) changes the parity. Hence


P (H) = sgn det W = sgn Pf A. (19)


We remind the reader that the Pfaffian Pf is a function of a skewsymmetric matrix such that (Pf A) [2] = det A. It is defined as follows



1
Pf A =
2 [N] N!




- sgn(τ ) Aτ (1),τ (2) · · · Aτ (2N −1),τ (2N ). (20)

τ ∈S2N



(Here S2N is the set of permutations on 2N elements). For example,



0 a12 a13 a14
−a12 0 a23 a24
−a13 −a23 0 a34
−a14 −a24 −a34 0








 [=][ a][12][a][34][ +][ a][14][a][23][ −] [a][13][a][24][.]



Pf












In eq. (19) we have used this property of the Pfaffian:


Pf(WAW [T] ) = Pf(A) det(W ). (21)


Now we are to compute the Pfaffian of the matrix B from eq. (18). First,
we use the Fourier transform,



e [iqj] Bαβ(j), q = 2π [k]
j L



B˜αβ(q) =

  


L [(mod 2][π][)][, k][ = 0][, . . ., N][ −] [1][.][ (22)]



The matrix B [˜] (q) has these symmetries:


B˜ [†] (q) = −B˜(q) = ˜B [T] (−q). (23)


The spectrum ǫ(q) is a continuous real 2n-valued function on a circle (real
numbers (mod 2π)) given by the eigenvalues of iB [˜] (q). It has the symmetry
ǫ(−q) = −ǫ(q). The energy gap assumption implies that ǫ(q) never passes
0. It follows that there are n positive and n negative eigenvalues for any q.
Indeed, this is the case for q = 0 due to the ǫ �→−ǫ symmetry, hence it is
true for any q by continuity.


11


It follows from eqs. (22) and (21) that



Pf B [˜] (q)
q= [�] −q







q= [�] 


det B [˜] (q)
q= [�] −q











. (24)




Pf B =







q= [�] 


Remember that q is considered (mod 2π), so q = −q when q = 0 or q = π.
In the q ̸= −q case, each {q, −q} pair is counted once. Note that det B [˜] (q)
is a positive number since iB [˜] (q) has n positive and n negative eigenvalues.
Hence




- sgn(Pf B [˜] (q)) =

q=−q








 sgn(Pf B [˜] (0)) sgn(Pf B [˜] (π)) if L is even,


sgn(Pf B [˜] (0)) if L is odd.





sgn Pf B = 


q=−q  sgn(Pf B [˜] (0)) if L is odd.

(25)
Finally, we get



M(H) = sgn(Pf B [˜] (0)) sgn(Pf B [˜] (π)). (26)


This very general equation can be simplified if superconductivity is a
weak effect, i. e. |∆| ≪|ǫ(0)|, |ǫ(π)|. Indeed, the right hand side of (26)
makes perfect sense for a U(1)-symmetric Hamiltonian



H0 = [1]

2





l,m




- Cαβ(m − l) a [†] lα [a][mβ] �Cαβ(j) [∗] = Cβα(−j)�, (27)

α,β



where α, β = 1, . . .n refer to fermionic sites. The eigenvalues of C [˜] (q) (the
Fourier transform of C) form a “single spectrum” ǫ0(q). The “double spectrum” defined above is ǫ(q) = ±ǫ0(q). It is easy to show that Pf B [˜] (q) =
det C [˜] (q) for q = 0, π. Hence


M(H0) = (−1) [ν][(][π][)][−][ν][(0)], (28)


where ν(q) is the number of negative eigenvalues of C [˜] (q). Note that ν(π) −
ν(0) equals (mod 2) the number of Fermi points on the interval [0, π]. (A
Fermi point is a point where ǫ0(q) passes 0). In the most interesting case
ν(π) − ν(0) = 1 (mod 2), the Hamiltonian H0 has a gapless spectrum. So
eq. (28) is only relevant in the presence of superconductivity, i. e. a small
symmetry-breaking perturbation which opens an energy gap.


12


### 3 Speculations about physical realization

Physical realization of an M = −1 quantum wire is a difficult task because
electron spectra are usually degenerate with respect to spin, so ν(0) and
ν(π) are even. The degeneracy at q = 0 and q = π can be lifted only
if the time reversal symmetry is broken. Thus spin-orbit interaction does
not help. External magnetic field could help, but the Zeeman energy gµBH
is usually small compared to other spectrum parameters, so ν(0) and ν(π)
do not change. The situation may be different for charge and spin density
waves which add fine features to the electron spectrum. Charge density waves
(CDW) tend to occur at the wave vector q∗ = 2qF so that a gap opens at the
Fermi level. In the presence of magnetic field, qF is slightly different for the
↑ and ↓ spin components, so it is possible that q∗ matches only one of them.
The resulting spectrum is shown in fig. 4 in the q∗/(2π) units. This scenario
can be realized if |∆| [<] ∼ [E][CDW] [<] ∼ [gµ][B][H][.]
Another speculative possibility is to use midgap states at the edge of a
two-dimensional p-wave superconductor [12].





q


|Col1|ε0(q)|Col3|
|---|---|---|
||||
||spin up<br>spin down|spin up<br>spin down|



Figure 4: An electron spectrum in the presence of magnetic field and CDW.


A quantum wire bridge between two superconducting leads (see fig. 5a)
could be used as an experimental test for Majorana fermions. When the phase
parameter θ2 in the right piece of superconductor changes by 2π (relative to
θ1), a fermionic quasiparticle is effectively transported to the junction region.


13


At the same time, the Majorana fermions at the ends of the wire switch from
|ψ0⟩ to |ψ1⟩ or vice versa. If the quasiparticle stays localized, the junction
parameters change. They change back when θ2 changes by another 2π. Thus
the Josephson current is 4π-periodic as a function of θ = θ2 − θ1. In fact,
it is more accurate to say that the Josephson energy EJ is 2π-periodic but
2-valued, as shown in fig. 5b. The two levels may not quite cross at θ = π due
to a non-vanishing tunneling amplitude t ∝ e [−][L/l][0], where L is the distance
between the junction and the closest end of the wire.



✁ ✁
✁ ✁✁



✁ ✁
✁ ✁✁



✁✁

θ1 ✁



✁✁

θ2 ✁



|Col1|Col2|EJ(θ)|Col4|
|---|---|---|---|
|||EJ(θ)<br><br>|EJ(θ)<br><br>|
|-2π<br>-|π|t=0<br>t≠0|2π<br>π|


b)



θ



θ = θ2 − θ1


a)



Figure 5: A Josephson junction made of quantum wire.


Interesting phenomena can also take place in the simple layout shown
in fig. 1. Suppose that the superconducting island supporting the quantum
wire is connected to a larger piece of superconductor through an ordinary
Josephson junction. If the Coulomb energy is comparable to the Josephson
energy, spontaneous phase slips can occur. Each 2π phase slip is accompanied
by the operator V (see eq. 16). The phase slips occur by tunneling, so the
effective Hamiltonian is

Heff.1 = −λV − λ [∗] V [†] = [i] t = 4 Re λ, (29)

2 [s][(][L][)][ t b][′][b][′′][,]


where λ is the amplitude of the θ �→ θ + 2π process while λ [∗] corresponds
to the reverse process. Similarly, if the superconducting island supports two
quantum wires, the effective Hamiltonian becomes

Heff.2 = −λV1V2 − λ [∗] V1 [†][V][ †] 2 [= 1] 1 [b][′′] 1 [b][′] 2 [b][′′] 2 [.] (30)

2 [s][(][L][1][)][s][(][L][2][)][ t b][′]


Turning λ on and off can be possibly used for quantum gates implementation.


14


Acknowledgements. I am grateful to J. Preskill, M. Feigelman, P. Vigman
and V. Yakovenko for interesting discussions.

### References


[1] P. W. Shor, “Fault tolerant quantum computation”, Proceedings of the
37th Symposium on the Foundations of Computer Science (FOCS), 56–
[65 (1996); quant-ph/9605011.](http://arxiv.org/abs/quant-ph/9605011)


[2] D. Aharonov, M. Ben-Or, “Fault-Tolerant Quantum Computation with
Constant Error”, Proc. of the 29th Annual ACM Symposium on Theory
[of Computing (STOC) (1997); quant-ph/9611025.](http://arxiv.org/abs/quant-ph/9611025)


[3] D. Aharonov, M. Ben-Or, “Fault-Tolerant Quantum Computation with
[Constant Error Rate”, quant-ph/9906129.](http://arxiv.org/abs/quant-ph/9906129)


[4] E. Knill, R. Laflamme, W. H. Zurek, “Threshold Accuracy for Quantum
[Computation” quant-ph/9610011.](http://arxiv.org/abs/quant-ph/9610011)


[5] A. Yu. Kitaev, “Quantum Computations: Algorithms and Error Correction”, Russian Math. Surveys 52:6, 1191–1249 [Russian version: Uspekhi
Mat. Nauk 52:3, 53–112].


[6] A. Yu. Kitaev, “Fault-tolerant quantum computation by anyons”,
[quant-ph/9707021.](http://arxiv.org/abs/quant-ph/9707021)


[7] M. H. Freedman, “P/NP, and the quantum field computer”, Proc. Natl.
Acad. Sci. USA, 95, 98–101 (1998).


[8] M. Freedman, M. Larsen, Z. Wang, “A modular functor which is univer[sal for quantum computation”, quant-ph/0001108.](http://arxiv.org/abs/quant-ph/0001108)


[9] S. Bravyi, A. Kitaev, “Fermionic quantum computation”,
[quant-ph/0003137.](http://arxiv.org/abs/quant-ph/0003137)


[10] N. Read, D. Green, “Paired states of fermions in two dimensions with
breaking of parity and time-reversal symmetry”, Phys. Rev. B 61, 10267
[(2000); cond-mat/9906453.](http://arxiv.org/abs/cond-mat/9906453)


15


[11] D. A. Ivanov, “Non-abelian statistics of half-quantum vortices in p-wave
[superconductors, cond-mat/0005069.](http://arxiv.org/abs/cond-mat/0005069)


[12] K. Sengupta, I. Zutic, H. Kwon, V. M. Yakovenko, S. Das Sarma,
“Midgap edge states and pairing symmetry of quasi-one-dimensional
[organic superconductors”, cond-mat/0010206.](http://arxiv.org/abs/cond-mat/0010206)


16
