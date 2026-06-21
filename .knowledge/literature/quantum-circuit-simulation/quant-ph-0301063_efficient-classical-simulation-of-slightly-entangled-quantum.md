---
source: "https://arxiv.org/abs/quant-ph/0301063"
type: "arxiv"
canonical_id: "quant-ph/0301063"
title: "Efficient classical simulation of slightly entangled quantum computations."
authors: "Vidal, Guifre"
year: "2003"
venue: "Physical Review Letters"
arxiv_id: "quant-ph/0301063"
doi: "10.1103/PhysRevLett.91.147902"
full_text: yes
---

# Efficient classical simulation of slightly entangled quantum computations.

**Authors:** Vidal, Guifre

**Citation:** Physical Review Letters, vol. 91 14, pp. 
          147902
        , 2003

**arXiv:** [quant-ph/0301063](https://arxiv.org/abs/quant-ph/0301063)

**DOI:** [10.1103/PhysRevLett.91.147902](https://doi.org/10.1103/PhysRevLett.91.147902)

## Abstract

We present a classical protocol to efficiently simulate any pure-state quantum computation that involves only a restricted amount of entanglement. More generally, we show how to classically simulate pure-state quantum computations on n qubits by using computational resources that grow linearly in n and exponentially in the amount of entanglement in the quantum computer. Our results imply that a necessary condition for an exponential computational speedup (with respect to classical computations) is that the amount of entanglement increases with the size n of the computation, and provide an explicit lower bound on the required growth.

## Full Text

Efficient classical simulation of
slightly entangled quantum computations


Guifr´e Vidal [1]

1Institute for Quantum Information, California Institute of Technology, Pasadena, CA 91125, USA
(Dated: February 1, 2008)


We present a scheme to efficiently simulate, with a classical computer, the dynamics of multipartite
quantum systems on which the amount of entanglement (or of correlations in the case of mixed-state
dynamics) is conveniently restricted. The evolution of a pure state of n qubits can be simulated by
using computational resources that grow linearly in n and exponentially in the entanglement. We
show that a pure-state quantum computation can only yield an exponential speed-up with respect
to classical computations if the entanglement increases with the size n of the computation, and gives
a lower bound on the required growth.



PACS numbers: 03.67.-a, 03.65.Ud, 03.67.Hk


In quantum computation, the evolution of a multipartite quantum system is used to efficiently perform computational tasks that are believed to be intractable with
a classical computer. For instance, provided a series
of severe technological difficulties are overcome, Shor’s
quantum algorithm [1] can be used to decompose a large
number into its prime factors efficiently —that is, exponentially faster than with any known classical algorithm.
While it is not yet clear what physical resources are
responsible for such suspected quantum computational
speed-ups, a central observation, as discussed by Feynman [2], is that simulating quantum systems by classical
means appears to be hard. Suppose we want to simulate
the joint evolution of n interacting spin systems, each
one described by a two-dimensional Hilbert space H2.
Expressing the most general pure state |Ψ⟩∈H2⊗n of
the n spins already requires specifying about 2 [n] complex
numbers ci1···in,



1





- ci1···in |i1⟩⊗· · · ⊗|in⟩, (1)

in=0



Here we show how to efficiently simulate, with a classical computer, pure-state quantum dynamics of n entangled qubits, whenever only a restricted amount of entanglement is present in the system. It follows that entanglement is a necessary resource in (pure-state) quantum
computational speed-ups. More generally, we establish
an upper bound, in terms of the amount of entanglement, for the maximal speed-up a quantum computation
can achieve. An analogous upper bound, but in terms of
correlations (either classical or quantum), also applies to
quantum computations with mixed states.
For simplicity sake the analysis is focused on a computation in the quantum circuit model. Thus we consider
a discretized evolution of the n qubits, initially in state
|0⟩ [⊗][n], according to a sequence of poly(n) (i.e., a number polynomial in n) single-qubit and two-qubit gates.
We recall, however, that any evolution of n qubits according to single-qubit and two-qubit Hamiltonians can
be efficiently approximated, with arbitrary accuracy, by
the above circuit model, so that the present results also
apply to this more general setting [6].
Consider, as in Eq. (1), a pure state |Ψ⟩∈H2⊗n of an
n-qubit system. Let A denote a subset of the n qubits
and B the rest of them. The Schmidt decomposition SD
of |Ψ⟩ with respect to the partition A:B reads



|Ψ⟩ =




- - · ·

i1=0



1




where {|0⟩, |1⟩∈H2} denotes a single-spin orthonormal
basis; and computing its evolution in time is not any
simpler. This exponential overhead of classical computational resources –as compared to the quantum resources
needed to directly implement the physical evolution by
using n spin systems– strongly suggests that quantum
systems are indeed computationally more powerful than
classical ones.
On the other hand, some specific quantum evolutions
can be efficiently simulated by a classical computer –
and therefore cannot yield an exponential computational
speed-up. Examples include a system of fermions with
only quadratic interactions [3], or a set of two-level systems or qubits initially prepared in a computational-basis
state and acted upon by gates from the Clifford group [4].
Recently, Jozsa and Linden [5] have also shown how to
efficiently simulate any quantum evolution of an n-qubit
system when its state factors, at all times, into a product of states each one involving, at most, a constant (i.e.
independent of n) number of qubits.



where the vector |Φ [[] α [A][]][⟩] [(][|][Φ][[] α [B][]][⟩][) is an eigenvector with]
eigenvalue |λα| [2] - 0 of the reduced density matrix ρ [[][A][]]

(ρ [[][B][]] ), whereas the coefficient λα follows from the relation ⟨Φ [[] α [A][]][|][Ψ][⟩] [=][ λ] α [|][Φ][[] α [B][]][⟩][.] The Schmidt rank [χ] A is a
natural measure of the entanglement between the qubits
in A and those in B [7]. Accordingly, we quantify the
entanglement of state |Ψ⟩ by [χ],


χ ≡ max (3)
A [χ][A][,]


that is, by the maximal Schmidt rank over all possible bipartite splittings A:B of the n qubits. We shall say that
|Ψ⟩ is only slightly entangled if [χ] is “small”. In particular, here we are interested in sequences of states {|Ψn⟩} of



χA
|Ψ⟩ = - λα|Φ [[] α [A][]][⟩⊗|][Φ][[] α [B][]][⟩][,] (2)

α=1


an increasing number n of qubits (corresponding, say, to
quantum computations with increasingly large inputs).
In such a context we consider [χ] to be “small” if it grows
at most polynomially with n, [χ] n = poly(n) [8].


Definition.– A pure-state quantum evolution is
slightly entangled if, at all times t, the state |Ψ(t)⟩ of the
system is slightly entangled —that is, if [χ] (t) is small. A
sequence of evolutions with an increasingly large number
n of qubits is slightly entangled if [χ] n(t) is upper bounded
by poly(n).


The key ingredient of our simulation protocol is a local
decomposition of the state |Ψ⟩∈ H2⊗n in terms of n
tensors {Γ [[][l][]] } [n] l=1 [and][ n][−][1 vectors][ {][λ][[][l][]][}] l [n] =1 [−][1][, denoted]

|Ψ⟩ ←→ Γ [[1]] λ [[1]] Γ [[2]] λ [[2]]   - · · Γ [[][l][]]   - · · λ [[][n][−][1]] Γ [[][n][]] . (4)


Here, tensor Γ [[][l][]] is assigned to qubit l and has (at most)
three indices, Γ [[] αα [l][]][i][′][, where][ α, α][′][ = 1][,][ · · ·][, χ][ and][ i][ = 0][,][ 1,]
whereas λ [[][l][]] is a vector whose components λα [[][l][]][′][ store the]
Schmidt coefficients of the splitting [1 · · · l]:[(l+1) · · · n].
More explicitly, we have [9]

ci1i2···in =   - Γα [[1]] 1 [i][1][λ] α [[][l][]] 1 [Γ] α [[2]] 1 [i] α [2] 2 [λ] α [[2]] 2 [· · ·][ Γ][[] α [n] n []]   - [i][n] 1 [.] (5)

α1,···,αn−1


so that the 2 [n] coefficients ci1···in are expressed in terms of
about (2 [χ][2] + [χ] )n parameters, a number that grows only
linearly in n for a fixed value of [χ] . This decomposition
is local in that, as we shall see, when a two-qubit gate is
applied to qubits l and l+1, only Γ [[][l][]], λ [[][l][]] and Γ [[][l][+1]] need
be updated.
Decomposition (4) (but not [χ] ) depends on the particular way qubits have been ordered from 1 to n, and
essentially consists of a concatenation of n−1 SDs. We
first compute the SD of |Ψ⟩ according to the bipartite
splitting of the systems into qubit 1 and the n - 1 remaining qubits [from now on we omit the tensor product
symbol],

|Ψ⟩ =      - λ [[1]] α1 [|][Φ] α [[1]] 1 [⟩|][Φ][[2] α1 [···][n][]] ⟩ (6)

α1

=     - Γα [[1]] 1 [i][1] [λ] α [[1]] 1 [|][i][1][⟩|][Φ][[2] α1 [···][n][]] ⟩, (7)

i1,α1


where in the last line we have expanded each Schmidt
vector |Φ [[1]] α1 [⟩] [=][ �] i1 [Γ] α [[1]] 1 [i][1] [|][i] 1 [⟩] [in terms of the basis vectors]
{|0⟩, |1⟩} for qubit 1. We then proceed according to the
following three steps: (i) first we expand each Schmidt
vector |Φ [[2] α [···][n][]] ⟩ in a local basis for qubit 2,

|Φ [[2] α1 [···][n][]] ⟩ =       - |i2⟩|τα [[3] 1 [···] i2 [n][]][⟩][;] (8)

i2



(ii) then we write each (possibly unnormalized) vector |τα [[3] 1 [···] i2 [n][]][⟩] [in terms of the][ at most][ χ][ Schmidt vectors]

{|Φ [[3] α2 [···][n][]] ⟩} [χ] α2=1 [(i.e., the eigenvectors of][ ρ][[3][···][n][]][) and the]

corresponding Schmidt coefficients λ [[2]] α2 [,]



|τα [[3] 1 [···] i2 [n][]][⟩] [=] - Γα [[2]] 1 [i] α [2] 2 [λ] α [[2]] 2 [|][Φ][[3] α2 [···][n][]] ⟩; (9)

α2



2


(iii) finally we substitute Eq. (9) in Eq. (8) and the
latter in Eq. (7) to obtain


|Ψ⟩ =  - Γ [[1]] α1 [i][1] [λ] α [[1]] 1 [Γ] α [[2]] 1 [i] α [2] 2 [λ] α [[2]] 2 [|][i][1][i][2][⟩|][Φ][[3] α1 [···][n][]] ⟩. (10)

i1,α1,i2,α2


Iterating steps (i)-(iii) for the Schmidt vectors
|Φ [[3] α2 [···][n][]] ⟩, |Φ [[4] α3 [···][n][]] ⟩, · · ·, |Φ [[] α [n] n []] −1 [⟩][, one can express state][ |][Ψ][⟩]
in terms of tensors Γ [[][l][]] and λ [[][l][]], as in Eq. (4).
A useful feature of description (4) is that it readily
gives the SD of |Ψ⟩ according to the bipartite splitting

[1 · · · l] : [(l+1) · · · n],


|Ψ⟩ = λ [[] α [l][]] l [|][Φ] α [[1] l [···][l][]] ⟩|Φ [[(] αl [l][+1)][···][n][]] ⟩. (11)

   
αl


Indeed, it can be checked by induction over l that


|Φ [[1] αl [···][l][]] ⟩←→ Γ [[1]] λ [[1]]     - · · λ [[][l][−][1]] Γ [[] α [l][]] l [,] (12)


meaning that


|Φ [[1] αl [···][l][]] ⟩ =   - Γ [[1]] α1 [i][1][λ] α [[1]] 1 [· · ·][ Γ][[] α [l][]] l− [i][l] 1αl [|][i][1][ · · ·][ i][l][⟩][;] (13)

α1,···,αl−1


whereas by construction we already had that


|Φ [[(] αl [l][+1)][···][n][]] ⟩←→ Γ [[] α [l][+1]] l λ [[][l][+1]]    - · · λ [[][n][−][1]] Γ [[][n][]], (14)


which stands for

|Φ [[(] αl [l][+1)][···][n][]] ⟩ = - Γα [[][l][+1]] lαl+1 [i][l][+1] [· · ·][ λ][[] α [n] n [−] - [1]] 1 [Γ][[] α [n] n []] - [i][n] 1 [|][i][l][+1][ · · ·][ i][n][⟩][.][(15)]

αl+1,···,αn


The following lemmas explain how to update the description of state |Ψ⟩ when a single-qubit gate or a twoqubit gate (acting on consecutive qubits) is applied to
the system. Remarkably, the computational cost of the
updating is independent of the number n of qubits, and
only grows in [χ] as a polynomial of low degree.


Lemma 1.– Updating the description (4) of state |Ψ⟩
after a unitary operation U acts on qubit l does only
involve transforming Γ [[][l][]] . The incurred computational
cost is of Ø( [χ][2] ) basic operations.


Proof.– In the SD according to the splitting [1 · · · (l−
1)] : [l · · · n], a unitary operation U on qubit l does
not modify the Schmidt vectors for part [1 · · · (l − 1)]
and therefore Γ [[][j][]] and λ [[][j][]] (1 ≤ j ≤ l − 1) remain the
same. Similarly, by considering the SD for the splitting

[1 · · · l] : [(l+1) · · · n], we conclude that also Γ [[][j][]] and λ [[][j][−][1]]

(l+1 ≤ j ≤ n) remain unaffected. Instead, Γ [[][l][]] changes
according to


Γ [′][[] αβ [l][]][i] [=]   - Uj [i][Γ][[] αβ [l][]][j] ∀α, β = 1, · · ·, [χ] . (16)

j=0,1


Lemma 2.– Updating the description (4) of state |Ψ⟩
after a unitary operation V acts on qubits l and l + 1
does only involve transforming Γ [[][l][]], λ [[][l][]] and Γ [[][l][+1]] . This
can be achieved with Ø( [χ][3] ) basic operations.


Proof.– In order to ease the notation we regard |Ψ⟩
as belonging to only 4 subsystems,


H = J ⊗HC ⊗HD ⊗K. (17)


Here, J is spanned by the [χ] eigenvectors of the reduced
density matrix


ρ [[1][···][(][l][−][1)]] = |α⟩⟨α|, |α⟩≡ λ [[] α [l][−][1]] |Φα [[1][···][(][l][−][1)]] ⟩; (18)

   
α


and, similarly, K is spanned by the [χ] eigenvectors of the
reduced density matrix


ρ [[(][l][+2)][···][n][]] = |γ⟩⟨γ|, |γ⟩≡ λγ [[][l][+1]] |Φ [[(] γ [l][+2)][···][n][]] ⟩; (19)

   
γ


whereas HC and HD correspond, respectively, to qubits
l and l+1. In this notation we have



χ
|Ψ⟩ = 
α,β,γ=1



1

- Γαβ [[][C][]][i][λ][β] [Γ] βγ [[][D][]][j][|][αijγ][⟩][,] (20)

i,j=0



1




and, reasoning as in the proof of lemma 1, when applying unitary V to qubits C and D we need only update
Γ [[][C][]], λ, Γ [[][D][]] . We can expand |Ψ [′] ⟩≡ V |Ψ⟩ as



χ
|Ψ [′] ⟩ = 
α,γ=1



1

- Θ [ij] αγ [|][αijγ][⟩][,] (21)

i,j=0



1




3


We now state our main results. We consider a purestate quantum computation using n qubits, and consisting of poly(n) one- and two-qubit gates and a final local measurement. The simulation protocol works as follows. We use tensors Γ [[][l][]] and λ [[][l][]] to store the initial
state |0⟩ [⊗][n] and update its description as the gates are
applied [10]. Recall that in description (4) each qubit
has been associated a position from 1 to n. In order to
update |Ψ⟩ according to a two-qubit gate between nonconsecutive qubits C and D, we will first simulate Ø(n)
swap gates between adjacent qubits to bring C and D together. Computing the expectation value for any product
operator (e.g. a projection corresponding to a local measurement) from {Γ [[][l][]], λ [[][l][]] } is straightforward and can also
be done with n poly( [χ] ) operations.


Theorem 1.— If through a pure-state quantum computation [χ] n is upper bounded by poly(n), then the computation can be classically simulated with poly(n) memory space and computational time.


Theorem 2.— If [χ] n grows subexponentially in n,
then the quantum computation can be classically simulated with subexp(n) memory space and computational
time.


Thus, theorem 1 provides us with a sufficient condition for the efficient classical simulation of a quantum
computation, which by extension also applies to generic
pure-state, multi-particle unitary dynamics generated by
local interactions [6]. In turn theorem 2 provides us with
a more general condition under which a quantum computation cannot yield an exponential speed-up with respect
to classical computations. Both theorems follow straightforwardly from the previous lemmas and considerations.
The above results establish a clear connection between
the amount of entanglement in a multipartite system and
the computational cost of simulating the system with a
classical computer. This suggests a new approach to the
study of multipartite entanglement, based on the complexity of describing and simulating quantum systems.
We propose to quantify the entanglement of a pure state
|Ψ⟩ through measures that indicate how difficult it is to
express |Ψ⟩ in terms of local states or, relatedly, to account for a local change in the system. An example of
such entanglement measures is the function


Eχ ≡ log2 [χ], (28)


which, apart from serving the purposes, has a series
of other appealing properties: (i) Eχ only vanishes for
product (i.e., unentangled) vectors; (ii) Eχ is additive
under tensor products, Eχ(Ψ ⊗ Ψ [′] ) = Eχ(Ψ) + Eχ(Ψ [′] );
(iii) Eχ monotonically decreases under (both deterministic and stochastic) LOCC manipulations of the system.
We also note that Eχ(Ψ) is not a continuous function of
|Ψ⟩ with respect any reasonable distance [11].
We can rephrase the results of this paper in terms of
Eχ. Notice that the maximum value of Eχ in a system of n particles is linear in n. Theorem 1 states that
an efficient simulation of quantum dynamics is possible



where




- Vkl [ij] [Γ] αβ [[][C][]][k][λ][β][Γ] βγ [[][D][]][l][.] (22)

kl



Θ [ij] αγ [=] 
β



Θ [ij] αγ [=] 


Vkl [ij] [Γ] αβ [[][C][]][k][λ][β][Γ] βγ [[][D][]][l][.] (22)
kl



By diagonalizing ρ [′][[][D][K][]],


ρ [′][[][D][K][]] = trJ C |Ψ [′] ⟩⟨Ψ [′] | (23)



⟨α|α⟩Θ [ij] αγ [(Θ][ij] αγ [′]

[�] α,i




[ij] αγ [′][)][∗]







|jγ⟩⟨j [′] γ [′] |,




= 






 [�] α,i



j,j [′],γ,γ [′]



we obtain its eigenvectors {|Φ [′] β [[][D][K][]] ⟩}, which we can expand in terms of {|jγ⟩} to obtain Γ [′][[][D][]],


|Φ [′] β [[][D][K][]] ⟩ = Γβγ [′][[][D][]][j] |jγ⟩. (24)

    
j,γ


The eigenvectors of ρ [′][[][J][ C][]] and λ [′] follow then from


λ [′] β [|][Φ][′] β [[][J][ C][]] ⟩ = ⟨Φ [′] β [[][D][K][]] |Ψ [′] ⟩ (25)

= (Γβγ [′][[][D][]][j] ) [∗] Θ [ij] αγ [⟨][γ][|][γ][⟩|][αi][⟩][,] (26)

    
i,j,α,γ


and by expanding each |Φ [′] β [[][J][ C][]] ⟩,

|Φ [′] β [[][J][ C][]] ⟩ =       - Γ [′] αβ [[][C][]][i][|][αi][⟩][,] (27)

iα


we also obtain Γ [′][[][C][]] . All the above manipulations can
be performed by storing Ø( [χ][2] ) coefficients and require
Ø( [χ][3] ) basic operations.


whenever Eχ grows at most logarithmically in n. More
generally, we have shown how a state |Ψ⟩ can be given a
description in terms of local states by using a number of
parameters that grows linearly in the number of systems
and exponentially in the amount of entanglement Eχ,


local description n exp(Eχ)
(29)
of an n-qubit state [≈] parameters.


This expression implies an upper bound, in terms of the
entanglement, for the computational speed-up a quantum
evolution can achieve with respect to classical computations.
So far we have only considered pure-state dynamics.
But if the n qubits are in a mixed state ρ ∈B(H2⊗n),
we can regard density matrices as vectors in the space
of linear operators. By using product expansions and
the Schmidt decomposition in this space, one can readily
re-derive the above results, but with the former role of
entanglement played now by both quantum and classical correlations. Thus, an efficient simulation is possible if the total amount of correlations (as measured by
the analog of [χ] ) is sufficiently restricted. In particular,
this results do not rule out the possibility of obtaining
a computational speed-up through a quantum computation with very noisy mixed states [12].
Finally, [a simple modification of] the simulation protocol discussed in this paper may find practical applications
as a tool to study quantum systems [13]. The results
of [14] suggest that, at zero temperature, non-critical
spin-chains typically meet sufficient conditions for an efficient classical simulation. Perhaps, then, understanding
the structure of multipartite entanglement is the key to
achieve efficient simulation of certain multipartite quantum phenomena.


The author thanks Dave Bacon, Ignacio Cirac, Ann
Harvey and Richard Jozsa and Debbie Leung for valuable
advice. Support from the US National Science Foundation under Grant No. EIA-0086038 is acknowledged.


[1] P. Shor, in Proceedings of the 35th Annual Symposium
on Foundations of Computer Science, Santa Fe, NM, 20
to 22 November 1994, S. Goldwasser, Ed. (IEEE Computer Society, Los Alamitos, CA, 1994) p. 124.

[2] R. P. Feynman, Opt. News 11, 11 (1985): Found. Phys.
16 507 (1986); Int. J. Theor. Phys. 21, 467 (1982).

[3] L. Valiant, Proceedings of 33rd STOC, 114-123 (2001).
B. M. Terhal and D. P. DiVincenzo, Phys. Rev. A 65,
032325/1-10 (2002).

[4] D. Gottesman, Ph. D. Thesis, 1997 (Caltech, Pasadena).

[5] R. Jozsa and N. Linden, On the role of entanglement in
[quantum computational speed-up, quant-ph/0201143.](http://arXiv.org/abs/quant-ph/0201143)

[6] A straightforward generalization of the present results is
possible to the case of d-level subsystems with m-body



4


interactions, provided d and m do not grow with the total
number n of subsystems.

[7] The use of [χ] A as a measure of entanglement can be justified by considering a trade-off of non-local resources
that becomes possible when subsystems A and B are manipulated using local operations and classical communication LOCC. About log2 [χ] EPR pairs shared between
A and B (equivalently, log2 [χ] CNOT gates involving A
and B) are necessary and sufficient to prepare |Ψ⟩ with
the additional help of LOCC. Also, log2 [χ] is the maximal number of EPR pairs that, with finite probability,
can be extracted from |Ψ⟩ by LOCC. The Schmidt rank
χ can be shown not to increase (not even probabilistically) under LOCC, as required to any entanglement
measure, and is related to the more popular measure
entropy of entanglement E(Ψ) ≡− tr(ρA log2 ρA) [15]
through E(Ψ) ≤ log2 [χ] . Notice that using E(Ψ) to quantify the entanglement of |Ψ⟩ in the present context may
not be an appropriate choice, since E(Ψ) refers to asymptotic properties of |Ψ⟩, i.e. to properties of |Ψ⟩ [⊗][N] in the
limit N →∞, whereas here we are concerned with the
case N = 1.

[8] For a general n-qubit state, [χ] A is upper bounded by 2 [n/][2]

[value reached when A contains half of the n qubits and,
e.g., |Ψ⟩ is maximally entangled between A and B]. Thus,
states for which [χ] = poly(n) contain exceptionally little
entanglement.

[9] Expansion (5) very much resembles that of a product
vector |Ψprod⟩ = |Φ [[1]] ⟩⊗· · · ⊗|Φ [[][n][]] ⟩, in which case the
coefficients ci1···il···in = Γ [[1]][i][1]   - · · Γ [[][l][]][i][l]   - · · Γ [[][n][]][i][n] can be expressed in terms of tensors Γ [[][l][]], where Γ [[][l][]] completely
characterizes the pure state |Φ [[][l][]] ⟩ of qubit l. The extra
indices α’s in (5) account for the correlations between
qubits.

[10] A digital computer only allows for an approximate description of gates and states, since real coefficients are
truncated. See Ref. [5] for a discussion on how to obtain
efficient approximations by using rational numbers.

[11] Discontinuity of Eχ implies that a good approximation
|Ψ [˜] ⟩ to |Ψ⟩ may exists with a significantly lower value
of Eχ. Correspondingly, a more efficient simulation may
be obtained, at the expenses of a tolerable inaccuracy,
if we consider truncated Schmidt decompositions. That
is, for a given δ > 0 and any partition A:B of the n
qubits, we may consider keeping only a number [χ] λ of the
Schmidt terms in the SD of |Ψ⟩, where [χ] δ is determined
by requiring that α=1 [|][λ][α][|][2][ ≥] [1][−][δ][. Then, for a small][ λ][,]
the truncated SD corresponds to a state [�][χ][δ] |Ψ [˜] ⟩ very similar
to |Ψ⟩ (|⟨Ψ|Ψ [˜] ⟩| [2] ≥ 1 − δ), but [χ] λ may be much smaller
than [χ] . The function Eχδ = log2 [χ] δ can then be used to
measure the computational cost of simulating quantum
dynamics with degree δ of accuracy.

[12] E. Knill, R. Laflamme, Phys. Rev. Lett. 81 (1998) 56725675.

[13] G. Vidal, in preparation.

[14] G. Vidal, J. I. Latorre, E. Rico, A. Kitaev, Entanglement
[in quantum critical phenomena, quant-ph/0211074.](http://arXiv.org/abs/quant-ph/0211074)

[15] C. H. Bennett, H. J. Bernstein, S. Popescu, and B. Schumacher, Phys. Rev. A 53, 2046-2052 (1996).
