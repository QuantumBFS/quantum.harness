---
source: "https://arxiv.org/abs/quant-ph/0511069"
type: "arxiv"
canonical_id: "quant-ph/0511069"
title: "Simulating Quantum Computation by Contracting Tensor Networks"
authors: "Markov, Igor L., Shi, Yaoyun"
year: "2008"
venue: "SIAM journal on computing (Print)"
arxiv_id: "quant-ph/0511069"
doi: "10.1137/050644756"
full_text: yes
---

# Simulating Quantum Computation by Contracting Tensor Networks

**Authors:** Markov, Igor L., Shi, Yaoyun

**Citation:** SIAM journal on computing (Print), vol. 38, pp. 963-981, 2008

**arXiv:** [quant-ph/0511069](https://arxiv.org/abs/quant-ph/0511069)

**DOI:** [10.1137/050644756](https://doi.org/10.1137/050644756)

## Abstract

The treewidth of a graph is a useful combinatorial measure of how close the graph is to a tree. We prove that a quantum circuit with $T$ gates whose underlying graph has a treewidth $d$ can be simulated deterministically in $T^{O(1)}\exp[O(d)]$ time, which, in particular, is polynomial in $T$ if $d=O(\log T)$. Among many implications, we show efficient simulations for log-depth circuits whose gates apply to nearby qubits only, a natural constraint satisfied by most physical implementations. We also show that one-way quantum computation of Raussendorf and Briegel (Phys. Rev. Lett., 86 (2001), pp. 5188-5191), a universal quantum computation scheme with promising physical implementations, can be efficiently simulated by a randomized algorithm if its quantum resource is derived from a small-treewidth graph with a constant maximum degree. (The requirement on the maximum degree was removed in [I. L. Markov and Y. Shi, preprint:quant-ph/0511069].)

## Full Text

### **Simulating quantum computation by contracting tensor networks**

Igor L. Markov [1] and Yaoyun Shi [2]

Department of Electrical Engineering and Computer Science
The University of Michigan
2260 Hayward Street
Ann Arbor, MI 48109-2121, USA
E-mail: imarkov shiyy @eecs.umich.edu
{ | }

### Abstract


The treewidth of a graph is a useful combinatorial measure of how close the graph is to a tree. We prove that
a quantum circuit with _T_ gates whose underlying graph has treewidth _d_ can be simulated deterministically in
_T_ _[O]_ [(][1][)] exp[ _O_ ( _d_ )] time, which, in particular, is polynomial in _T_ if _d_ = _O_ (log _T_ ). Among many implications,
we show efficient simulations for log-depth circuits whose gates apply to nearby qubits only, a natural
constraint satisfied by most physical implementations. We also show that _one-way quantum computation_ of
Raussendorf and Briegel ( _Physical Review Letters_, 86:5188–5191, 2001), a universal quantum computation
scheme with promising physical implementations, can be efficiently simulated by a randomized algorithm
if its quantum resource is derived from a small-treewidth graph.


**Keywords** : Quantum computation, computational complexity, treewidth, tensor network, classical simulation, one-way quantum computation.


1Supported in part by NSF 0208959, the DARPA QuIST program and the Air Force Research Laboratory.
2Supported in part by NSF 0323555, 0347078 and 0622033.


### **1 Introduction**

The recent interest in quantum circuits is motivated by several complementary considerations. Quantum
information processing is rapidly becoming a reality as it allows manipulating matter at unprecedented scale.
Such manipulations may create particular entangled states or implement specific quantum evolutions — they
find uses in atomic clocks, ultra-precise metrology, high-resolution lithography, optical communication, etc.
On the other hand, engineers traditionally simulate new designs before implementing them. Such simulation
may identify subtle design flaws and save both costs and effort. It typically uses well-understood host
hardware, e.g., one can simulate a quantum circuit on a commonly-used conventional computer.
More ambitiously, quantum circuits compete with conventional computing and communication. Quantummechanical effects may potentially lead to computational speed-ups, more secure or more efficient communication, better keeping of secrets, etc. To this end, one seeks new circuits and algorithms with revolutionary
behavior as in Shor’s work on number-factoring, or provable limits on possible behaviors. While proving
abstract limitations on the success of unknown algorithms appears more difficult, a common line of reasoning for such results is based on simulation. For example, if the behavior of a quantum circuit can be
faithfully simulated on a conventional computer, then the possible speed-up achieved by the quantum circuit
is limited by the cost of simulation. Thus, aside from sanity-checking new designs for quantum informationprocessing hardware, more efficient simulation can lead to sharper bounds on all possible algorithms.
Since the outcome of a quantum computation is probabilistic, we shall clarify our notion of simulation.
By a randomized simulation, we mean a classical randomized algorithm whose output distribution on an
input is identical to that of the simulated quantum computation. By a deterministic simulation, we mean a
classical deterministic algorithm which, on a given pair of input _x_ and output _y_ of the quantum computation,
outputs the probability that _y_ is observed at the end of the quantum computation on _x_ .
To simulate a quantum circuit, one may use a na¨ıve brute-force calculation of quantum amplitudes that
has exponential overhead. Achieving significantly smaller overhead in the generic case appears hopeless

- in fact, this observation lead Feynman to suggest that quantum computers may outperform conventional
ones in some tasks. Therefore, only certain restricted classes of quantum circuits were studied in existing
literature on simulation.
Classes of quantum circuits that admit efficient simulation are often distinguished by a restricted “gate
library”, but do not impose additional restrictions on how gates are interconnected or sequenced. A case in
point is the seminal Gottesman-Knill Theorem [13] and its recent improvement by Aaronson and Gottesman [1]. These results apply only to circuits with stabilizer gates — Controlled-NOT, Hadamard, Phase,
and single-qubit measurements in the so called Clifford group. Another example is given by _match gates_
defined and studied by Valiant [34], and extended by Terhal and DiVincenzo [32].
A different way to impose a restriction on a class of quantum circuits is to limit the amount of entanglement in intermediate states. Jozsa and Linden [17], as well as Vidal [37] demonstrate efficient classical
simulation of such circuits and conclude that achieving quantum speed-ups requires more than a bounded
amount of entanglement.
In this work we pursue a different approach to efficient simulation and allow the use of arbitrary gates.
More specifically, we assume a general quantum circuit model in which a gate is a general quantum operation
(so called _physically realizable operators_ ) on a constant number of qubits. This model, proposed and studied
by Aharonov, Kitaev and Nisan [2], generalizes the standard quantum circuit model, defined by Yao [41],
where each gate is unitary and measurements are applied at the end of the computation. We also assume
that (i) the computation starts with a fixed unentangled state in the computational basis, and (ii) at the end
each qubit is either measured or _traced-out_ .
Our simulation builds upon the framework of _tensor network contraction_ . Being a direct generalization of


2


matrices, tensors capture a wide range of linear phenomena including vectors, operators, multi-linear forms,
etc. They facilitate convenient and fundamental mathematical tools in many branches of physics such as
fluid and solid mechanics, and general relativity [15]. More recently, several methods have been developed
to simulate quantum evolution by contracting variants of tensor networks, under the names of _Matrix Prod-_
_uct States (MPS)_, _Projected Entangled Pairs States (PEPS)_, etc [37, 38, 35, 42, 35, 36, 25]. Under this
framework, a quantum circuit is regarded as a network of tensors. The simulation contracts edges one by
one and performs the convolution of the corresponding tensors, until there is only one vertex left. Having
degree 0, this vertex must be labeled by a single number, which gives the final measurement probability
sought by simulation. In contrast with other simulation techniques, we do not necessarily simulate individual gates in their original order — in fact, a given gate may even be simulated _partially_ at several stages of
the simulation.
While tensor network contraction has been used in previous work, little was known about optimal contraction orders. We prove that the minimal cost of contraction is determined by the _treewidth_ tw( _GC_ ) of the
circuit graph _GC_ . Moreover, existing constructions that approximate optimal _tree-decompositions_ (e.g. [29])
produce near-optimal contraction sequences. We shall define the concepts of treewidth and tree decompositions in Section 2. Intuitively, the smaller a graph’s treewidth is, the closer it is to a tree, and a tree
decomposition is a drawing of the graph to make it look like a tree as much as possible. Our result allows us to leverage the extensive graph-theoretical literature dealing with the properties and computation of
treewidth.


**Theorem 1.1.** _Let C be a quantum circuit with T gates and whose underlying circuit graph is GC. Then C_
_can be simulated deterministically in time T_ _[O]_ [(][1][)] exp[ _O_ (tw( _GC_ ))] _._


A rigorous restatement of the above theorem is Theorem 4.6. By this theorem, given a function computable in polynomial time by a quantum algorithm but not classically, any polynomial-size quantum circuit
computing the function must have super-logarithmic treewidth.
The following corollary is an immediate consequence.


**Corollary 1.2.** _Any polynomial-size quantum circuit of a logarithmic treewidth can be simulated determin-_
_istically in polynomial time._


Quantum formulas defined and studied by Yao [41] are quantum circuits whose underlying graphs are
trees. Roychowdhury and Vatan [31] showed that quantum formulas can be efficiently simulated deterministically. Since every quantum formula has treewidth 1, Corollary 1.2 gives an alternative efficient
simulation.
Our focus on the _topology_ of the quantum circuit allows us to accommodate arbitrary gates, as long as
their qubit-width (number of inputs) is limited by a constant. In particular, Corollary 1.2 implies efficient
simulation of some circuits that create the maximum amount of entanglement in a partition of the qubits,
e.g., a layer of two-qubit gates. Therefore, our results are not implied by previously published techniques.
We now articulate some implications of our main result to classes of quantum circuits, in terms of properties of their underlying graphs. The following two classes of graphs are well-studied, and their treewidths
are known. The class of _series parallel graphs_ arises in electric circuits, and such circuits have treewidth
≤ 2. Planar graphs _G_ with _n_ vertices are known to have treewidth tw( _G_ ) = _O_ (�| _V_ ( _G_ )|) [4].

**Corollary 1.3.** _Any polynomial size parallel serial quantum circuit can be simulated deterministically in_
_polynomial time._

**Corollary 1.4.** _A size T planar quantum circuit can be simulated deterministically in_ exp[ _O_ (√ _T_ )] _time._


3


Another corollary deals with a topological restriction representative of many physical realizations of
quantum circuits. Let _q_ 1 be an integer. A circuit is said to be _q_ -local-interacting if under a linear
≥
ordering of its qubits, each gate acts only on qubits that are at most _q_ distance apart. A circuit is said to
be local-interacting if it is _q_ -local interacting with a constant _q_ independent of the circuit size. Such _local-_
_interaction_ circuits generalize the restriction of qubit couplings to nearest-neighbor qubits (e.g., in a spinchain) commonly appearing in proposals for building quantum computers, where qubits may be stationary
and cannot be coupled arbitrarily. To this end, we observe that the treewidth of any local-interaction circuit
of logarithmic depth is at most logarithmic.


**Corollary 1.5.** _Let C be a quantum circuit of size T and depth D, and is q-local-interacting. Then C_
_can be simulated deterministically in T_ _[O]_ [(][1][)] exp[ _O_ ( _qD_ )] _time. In particular, if C is a polynomial-size local-_
_interacting circuit with a logarithmic depth, then it can be simulated deterministically in polynomial time._


Yet another important application of our approach is to the simulation of _one-way quantum computation_ .
In two influential papers [7, 26], Briegel and Raussendorf introduced the concept of _graph states_ - quantum
states derived from graphs, — and show that an arbitrary quantum circuit can be simulated by _adaptive_,
_single-qubit measurements_ on the _graph state_ derived from the grid graph. Note that the graph state for
a one-way quantum computation does not depend on the quantum circuit to be simulated (except that its
size should be large enough) and that for most physical implementations single-qubit measurements are
much easier to implement than multi-qubit operations. Hence it is conceivable that graph states would be
manufactured by a technologically more advanced party, then used by other parties with lesser quantumcomputational power in order to facilitate universal quantum computing. This makes one-way quantum
computation an attractive scheme for physical implementations of universal quantum computation. An
experimental demonstration of one-way quantum computation appeared in a recent Nature article [39].
A natural question about one-way computation is to characterize the class of graphs whose graph states
are universal for quantum computation. We call a family of quantum states φ = {| φ 1⟩, | φ 2⟩, ···, | φ _n_ ⟩, ···}
_universal for one-way quantum computation_ if (a) the number of qubits in φ _n_ is bounded by a fixed poly| ⟩
nomial in _n_ ; (b) any quantum circuit of size _n_ can be simulated by a one-way quantum computation on φ _n_ .
| ⟩
On the other hand, φ is said to be efficiently simulatable if any one-way quantum computation on φ _n_ can
| ⟩
be efficiently simulated classically for all sufficiently large _n_ . Note that the class of universal families and
that of efficiently simulatable families are disjoint if and only if efficient quantum computation is indeed
strictly more powerful than efficient classical computation. We show that it is necessary for graphs to have
high treewidth so that the corresponding graph states are not efficiently simulatable.


**Theorem 1.6.** _Let G be a simple undirected graph. Then a one-way quantum computation on the respective_
_graph state can be simulated by a randomized algorithm in time_ _V_ ( _G_ ) exp[ _O_ (tw( _G_ ))] _._
| | _[O]_ [(][1][)]

Our simulation can be made deterministic with a better upper bound on time complexity if the one-way
computation satisfies additional constraints, such as those in [26]. We shall elaborate on this improvement
in Section 6.
An important limitation of our techniques is that a circuit family with sufficiently fast-growing treewidth
may require super-polynomial resources for simulation. In particular, this seems to be the case with known
circuits for modular exponentiation. Therefore, there is little hope to efficiently simulate number-factoring
algorithms using tree decompositions. As an extreme example to illustrate the limitation of our technique,
we give a depth-4 circuit — including the final measurement as the 4th layer — that has large treewidth.


**Theorem 1.7.** _There exists a depth-4 quantum circuit on n qubits using only one- and two-qubit gates such_
_that its treewidth is_ Ω ( _n_ ) _._


4


Note that a circuit satisfying the assumption in the above theorem must have _O_ ( _n_ ) size. Our construction
is based on expander graphs, whose treewidth must be linear in the number of vertices (Lemma 5.2).
This finding is consistent with the obstacles to efficient simulation that are evident in the results of Terhal
and DiVincenzo [33], later extended by Fenner et al. [14]. In contrast, we are able to efficiently simulate
any depth-3 circuit _deterministically_ while the simulation in [33] is probabilistic.


**Theorem 1.8.** _Assuming that only one- and two-qubit gates are allowed, any polynomial-size depth-_ 3 _quan-_
_tum circuit can be simulated deterministically in polynomial time._


Our simulation algorithm is related to algorithms for other tasks in that its runtime depends on the
treewidth of a graph derived from the input. Bodlaender wrote an excellent survey [8] on this subject.
Particularly relevant are algorithms based on “vertex eliminations”, e.g., the _Bucket Elimination_ algorithm
for Bayesian Inference [11]. Another parallel can be made with the work by Broering and Lokam [10],
which solves Circuit-SAT in time exponential in the treewidth of the graph of the given circuit. However, to
our best knowledge, we are the first to relate the treewidth of a quantum circuit to its classical simulation.
Our results are applicable to the simulation of classical probabilistic circuits, which can be modeled by
matrices, similarly to quantum circuits. Such simulation has recently gained prominence in the literature
on the reliability of digital logic [18], and is particularly relevant to satellite-based and airborne electronics
which experience unpredictable particle strikes at higher rates.
The rest of the paper is organized as follows. After introducing notation, we describe how quantum
circuits and their simulation can be modeled by tensor networks. The runtime of such simulation depends
on the graph parameter that we call the _contraction complexity_ . We then relate the contraction complexity
to treewidth, and apply the simulation to restricted classes of graphs, and to one-way quantum computation. Finally, we discuss possible directions for future investigations with a brief survey on the subsequent
development since the announcement of our results.

### **2 Notation and definitions**

For integer _n_ ≥ 1, define [ _n_ ] [def] = {1, 2,..., _n_ }. An ordering π of an _n_ -element set is denoted by π (1), π (2), ...,
π ( _n_ ). Unless otherwise stated, graphs in this paper are undirected and may have multiple edges or loops.
Edges connecting the same pair of vertices are called parallel edges. If _G_ is a graph, its vertex set is denoted
by _V_ ( _G_ ) and its edge set by _E_ ( _G_ ). When it is clear in the context, we use _V_ = _V_ ( _G_ ) and _E_ = _E_ ( _G_ ). The
_degree_ of a vertex _v_, denoted by _d_ ( _v_ ), is the number of edges incident to it. In particular, a loop counts as 1
edge. The maximum degree of a vertex in _G_ is denoted by ∆ ( _G_ ).


**Treewidth of a graph.** Let _G_ be a graph. A _tree decomposition_ of _G_ [28] is a tree _T_, together with a
function that maps each vertex _w_ _V_ ( _T_ ) to a subset _Bw_ _V_ ( _G_ ). These subsets _Bw_ are called _bags_ (of
∈ ⊆
vertices). In addition, the following conditions must hold.

(T1) _v_ _V_ ( _T_ ) _[B][v]_ [=] _[ V]_ [(] _[G]_ [)][, i.e., each vertex must appear in at least one bag.]

[S] ∈

(T2) _u_, _v_ _E_ ( _G_ ), _w_ _V_ ( _T_ ), _u_, _v_ _Bw_, i.e., for each edge, at least one bag must contain both of its
∀{ } ∈ ∃ ∈ { } ⊆
end vertices.

(T3) _u_ _V_ ( _G_ ), the set of vertices _w_ _V_ ( _T_ ) with _u_ _Bw_ form a connected subtree, i.e., all bags containing
∀ ∈ ∈ ∈
a given vertex must be connected in _T_ .


5


![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-5-0.png)

g



![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-5-1.png)















c











Figure 1: A graph and its decomposition of width 2 with 6 bags.


The _width_ of a tree decomposition is defined by max _w_ ∈ _V_ ( _T_ ) | _Bw_ | − 1. The _treewidth_ of _G_ is the minimum
width over its tree decompositions. For example, all trees have treewidth 1 and single cycles of length at
least 3 have treewidth 2. Figure 1 shows an example of tree decomposition. Intuitively, a tree decomposition
_T_ is a way of drawing a graph to look like a tree, which may require viewing sets of vertices (bags) as single
vertices. The less a graph looks like a tree, the larger the bags become. The notion of tree decomposition has
been useful in capturing the complexity of constraint satisfaction problems, Bayesian networks and other
combinatorial phenomena represented by graphs. In further writing, we may refer to a vertex in _T_ by its
bag when the context is clear.
Treewidth can be defined in several seemingly unrelated ways, e.g., as the minimum _k_ for which a given
graph is a _partial k-tree_, as the _induced width_ (also called the _dimension_ ), or as the _elimination width_ [30, 5].
An _elimination ordering_ π of a graph _G_ is an ordering of _V_ ( _G_ ). The _induced width of a vertex v_ ∈ _V_ ( _G_ )
in the ordering is the number of its neighbors at the time it is being removed in the following process: start
with π (1), add an edge for each pair of its neighbors that were previously not adjacent, remove π (1), then
repeat this procedure with the next vertex in the ordering. The _width of_ π is the maximum induced width of
a vertex, and the _induced width of G_ is the minimum width of an elimination ordering. It is known that the
induced width of a graph is precisely its treewidth [5].
It follows straightforwardly from the definition of treewidth that if _G_ is obtained from _G_ [′] by removing a
degree 1 vertex, tw( _G_ ) = tw( _G_ [′] ), unless _G_ [′] has only 1 edge, in which case tw( _G_ ) = 0 and tw( _G_ [′] ) = 1. We
will also use the following well known and simple fact, a proof for which is provided in the Appendix.


**Proposition 2.1.** _Let G be a simple undirected graph, and w be a degree_ 2 _vertex. Then removing w and_
_connecting its two adjacent vertices does not change the treewidth._


**Quantum circuits.** We review some basic concepts of quantum mechanics and quantum computation. For
a more detailed treatment, we refer the readers to the book by Nielsen and Chuang [24].
The state space of one qubit is denoted by _H_ [def] = C [2] . We fix an orthonormal basis for _H_ and label the
basis vectors with 0 and 1 . The space of operators on a vector space _V_ is denoted by **L** ( _V_ ). The identity
| ⟩ | ⟩
operator on _V_ is denoted by _IV_, or by _I_ if _V_ is implicit from the context. A density operator, or a mixed
state, of _n_ qubits is a positive semi-definite operatordef ρ ∈ **L** ( _H_ [⊗] _[n]_ ) with trace ρ = 1. For a binary string

_x_ = _x_ 1 _x_ 2 _xn_ 0, 1, let ρ _x_ = _i_ =1 = _i_ =1 [|] _[x][i]_ [⟩][.]
In this paper, a quantum gate with ··· ∈{ } _[n]_ [N] _[n]_ _a_ input qubits and [|] _[x][i]_ [⟩⟨] _[x][i]_ [|][ be the density operator of the state] _b_ output qubits is a superoperator [ |] _[x]_ [⟩] [def] ⊗ _[n]_ _Q_ : **L** ( _H_ [⊗] _[a]_ ) →
**L** ( _H_ [⊗] _[b]_ ). There are certain constraints that _Q_ must satisfy in order to represent a physically realizable
quantum operation. We need not be concerned about those constraints as our simulation method does not
depend on them. In existing applications one typically has _a_ _b_ and often _a_ = _b_, though a density operator
≥
can also be regarded as a gate with _a_ = 0. The ordering of inputs and outputs is in general significant. If
_Q_ is a _traced out_ operator, then _b_ = 0, and _Q_ ( _x_ _y_ ) = _x_ _y_, for all _x_, _y_ 0, 1 . We denote by _Q_ [ _A_ ] the
| ⟩⟨ | ⟨ | ⟩ ∈{ } _[a]_
application of _Q_ to an ordered set _A_ of _a_ qubits.


6


The information in a quantum state is retrieved through the application of measurements. A POVM
(Positive Operator-Valued Measure) _M_ on _n_ qubits is a set _M_ = _M_ 1, _M_ 2,, _Mk_, where each _Mi_ is called
{ ··· }
a POVM element, and is a positive semi-definite operator in **L** ( _H_ [⊗] _[n]_ ) such that ∑ _[k]_ _i_ =1 _[M][i]_ [ =] _[ I]_ [. The single-qubit]
measurement in the computational basis is 0 0, 1 1 .
{| ⟩⟨ | | ⟩⟨ |}
We assume that the maximum number of qubits on which a quantum gate can act is bounded by a constant
(often two or three). A quantum circuit of size _T_ with _n_ input-qubits and _m_ output-qubits consists of the
following:

(1) A sequence of _n_ input-wires, each of which represents one input-qubit, i.e., a qubit which is not the
output qubit of any gate.

(2) A sequence of _T_ quantum gates _g_ 1, _g_ 2, ..., _gT_, each of which is applied to some subset of the wires.

(3) A sequence of _m_ output-wires, each of which represents an output-qubit, i.e., a qubit which is not the
input qubit of any gate.

Note that by the above definition, a quantum circuit _C_ defines a functiondef _C_ : **L** ( _H_ [⊗] _[n]_ ) → **L** ( _H_ [⊗] _[m]_ ). In most
applications, a circuit _C_ is applied to an input state ρ _x_ = ⊗ _i_ _[n]_ =1 [|] _[x][i]_ [⟩⟨] _[x][i]_ [|][, for some binary string] _[ x]_ [ =] _[ x]_ [1][ ···] _[x][n]_ [ ∈]
0, 1, and at the end of the computation, measurements in the computational basis are applied to a subset
{ } _[n]_
of the qubits. We shall restrict our discussions to such case, though our results can be extended to more
general cases.
The graph of a quantum circuit _C_, denoted by _GC_, is obtained from _C_ as follows. Regard each gate as a
vertex, and for each input/output wire add a new vertex to the open edge of the wire. [3] Each wire segment
can now be represented by an edge in the graph.

### **3 Tensors and tensor networks**


Tensors, commonly used in physics, are multi-dimensional matrices that generalize more traditional tools
from linear algebra, such as matrix products. Here we focus on features of tensors that are relevant to our
work.

**Definition 3.1.** A rank- _k_ tensor in an _m_ -dimension space _g_ = [ _gi_ 1, _i_ 2,..., _ik_ ] _i_ 1, _i_ 2,..., _ik_ is an _m_ _[k]_ -dimensional array
of complex numbers _gi_ 1, _i_ 2,..., _ik_, indexed by _k_ indices, _i_ 1, _i_ 2, ..., _ik_, each of which takes _m_ values. When the
indices are clear we omit them outside the bracket.

For example, a rank-0 tensor is simply a complex number, and a rank-1 tensor is a dimension- _m_ complex
vector. We focus on dimension-4 tensors, and set the range of each index to be Π [def] = {| _b_ 1⟩⟨ _b_ 2| : _b_ 1, _b_ 2 ∈
0, 1 . We fix the following tensor representation of a density operator and a superoperator.
{ }}

**Definition 3.2.** Let ρ be a density operator on _a_ qubits. The tensor of ρ is [ ρσ 1, σ 2,..., σ _a_ ] σ 1, σ 2,..., σ _a_ ∈ Π, where

def
ρσ 1,..., σ _a_ = _tr_ ( ρ                 - (⊗ _i_ _[a]_ =1 [σ] _[i]_ [)][†][)][.]

Let _Q_ be a superoperator acting on _a_ input qubits and _b_ output qubits. The tensor of _Q_ is


_Q_ σ 1, σ 2,···, σ _a_, τ 1, τ 2,···, τ _b_ ] σ 1,..., σ _a_, τ 1,..., τ _b_ ∈ Π,

where
def
_Q_ σ 1, σ 2,, σ _a_, τ 1, τ 2,, τ _b_ = _tr_ ( _Q_ ( _i_ =1 [σ] _[i]_ [)] [·] [(][⊗] _[b]_ _j_ =1 [τ] _[ j]_ [)][†][)][.]
··· ··· ⊗ _[a]_

3These vertices are going to represent input states, as well as measurements and trace-out operators at the end of the computation.


7


We shall use the same notation for a density operator (or a superoperator) and its tensor. We now define
the central object of the paper.


**Definition 3.3.** A _tensor network_ is a collection tensors, each index of which may be used by either one or
two tensors.


A rank- _k_ tensor _g_ can be graphically represented as a vertex labeled with _g_, and connected to _k_ open wires,
each of which is labeled with a distinct index. We may represent a tensor network by starting with such
graphical representations of its tensors, and then connecting wires corresponding to the same index. Note
that now each wire corresponds to a distinct index. Also, an index that appears in one tensor corresponds to
an open wire, and an index that appears in two tensors corresponds to an edge connecting two vertices. Parts
(a) and (b) in Figure 2 give an example of the graphical representation of a tensor and a tensor network. In
the tensor _gQ_, we call the σ _i_ wires, 1 _i_ _a_, input wires, and the τ _j_ wires, 1 _j_ _b_, the output wires.
≤ ≤ ≤ ≤



![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-7-2.png)



i1



![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-7-3.png)





i1









j1 [′]



i3 jk iℓ−1 jk [′] `[′]`



j1







(a) (b) (c) (d)


Figure 2: A rank-4 tensor is illustrated in (a), and a tensor network with four tensors is shown in (b).
Contraction of two tensors is illustrated in (c) and (d).


Suppose in a tensor network, there are ℓ parallel edges _i_ 1, _i_ 2, ..., _i_ ℓ between two vertices _g_ = [ _gi_ 1,..., _i_ ℓ, _j_ 1,..., _jk_ ]
and _h_ = [ _hi_ 1,..., _i_ ℓ, _j_ 1′ [,...,] _[j]_ _k_ [′] [′] []][. We may contract those edges by first removing them, then merging] _[ v][g]_ [ and] _[ v][h]_ [ into a]
new vertex _v_ _f_, whose tensor is _f_ = [ _f j_ 1,..., _jk_, _j_ 1 [′] [,...,] _[j]_ _k_ [′] [′] []][, and]


def
## f j 1,..., jk, j 1 [′] [,...,] [j] k [′] [′] = ∑ gi 1,..., i ℓ, j 1,..., jk hi 1,..., i ℓ, j 1 [′] [,...,] [j] k [′] [′] [.] (1)
_i_ 1, _i_ 2,..., _i_ ℓ                                             
Parts (c) and (d) in Figure 2 illustrate the above contraction. Note that a tensor network with _k_ open wires
can be contracted to a single tensor of rank _k_, and the result does not depend on the order of contractions.
The following example is instructive.


**Example 1.** Let ρ be an _a_ -qubit density operator and _Q_ be a superoperator with _a_ input qubits and _b_ output
qubits. Consider the tensor network that connects all wires of the tensor ρ to the input wires of the tensor _Q_ .
Then contracting this tensor network gives the tensor of the density operator _Q_ ( ρ ). Figure 3 illustrates this
example.


A quantum circuit _C_ can be naturally regarded as a tensor network _N_ ( _C_ ): each gate is regarded as the
corresponding tensor. The qubit lines are wires connecting the tensors, or open wires that correspond to the
input and output qubits. Figure 4 illustrates the concept.
Let _C_ be a quantum circuit with _n_ input qubits and _m_ output qubits. Suppose that _C_ is applied to the initial
state ρ _x_, for some _x_ 0, 1, and we are interested in knowing the probability of observing some particular
∈{ } _[n]_
outcome when some single-qubit measurements are applied to a subset of the qubits. The setting can be
described by a measurement scenario defined as follows.

**Definition 3.4.** Let _m_ ≥ 1 be an integer. A _measurement scenario_ on _m_ qubits is a function τ : [ _m_ ] → **L** (C [2] ),
such that τ ( _i_ ) is a single-qubit POVM measurement element.


8


Q(ρ)





=⇒


|ρ<br>Q|Col2|Col3|Col4|
|---|---|---|---|
|ρ<br>Q||||
|||||



Figure 3: Contracting the wires connecting the tensors for a density operator ρ and a gate _Q_ results in the
tensor for _Q_ ( ρ ).


Note that if a qubit _i_ is not to be measured, we can set τ ( _i_ ) = _I_ .
To compute the probability that τ is realized on _C_ ( ρ _x_ ), we build a tensor network _N_ ( _C_ ; _x_, τ ) from _N_ ( _C_ )
by attaching to each input open wire _i_ the tensor for _xi_ _xi_, and attaching to each open wire for the output
| ⟩⟨ |
qubit _i_ the tensor for τ ( _i_ ). When _x_ = 0 _[n]_, we abbreviate _N_ ( _C_ ; _x_, τ ) as _N_ ( _C_ ; τ ). Figure 4 illustrates the concept
of _N_ ( _C_ ) and _N_ ( _C_ ; τ ).

![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-8-3.png)


|0⟩⟨0|                                      - · · |0⟩⟨0|



![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-8-1.png)

=⇒ C



=⇒



trace( [�][m] i=1 [τ] [(][i][)][ C][(][|][0][⟩⟨][0][|][⊗][n][))]



![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-8-2.png)

τ (1) τ (2) τ (3) τ (4)

N(C) N(C; τ )


(a) (b)


Figure 4: In (a), a circuit _C_ can be naturally regarded as a tensor network _N_ ( _C_ ). Contracting _N_ ( _C_ ) gives
the tensor for the operator that _C_ realizes. Part (b) illustrates the tensor network _N_ ( _C_ ; τ ), contracting which
gives the rank-0 tensor whose value is precisely the probability that the measurement scenario τ is realized
on _C_ ( 0 0 ).
| ⟩⟨ | [⊗] _[n]_


**Proposition 3.5.** _Let C be a quantum circuit, x be a binary string, and_ τ _be a measurement scenario._
_Contracting the tensor network N_ ( _C_ ; _x_, τ ) _to a single vertex gives the rank-_ 0 _tensor which is the probability_
_that_ τ _is realized on C_ ( ρ _x_ ) _._

_Proof._ Let ρ _[t]_ [ def] = _gt_ _gt_ −1 ··· _g_ 1( ρ _x_ ), 1 ≤ _t_ ≤ _T_, and ρ [0] = ρ _x_ . By the definitions of tensors for density operators
and superoperators and tensor contraction, contracting wires connecting the tensor of a superoperator _Q_ and
the tensors for a density operator ρ gives the tensor of _Q_ ( ρ ). Thus sequentially contracting input wires of
_g_ 1,, _gt_ gives the tensor for ρ _[t]_, and contracting the remaining wires gives the tensor for τ ( ρ _[T]_ ), which is
···
the probability of realizing τ on ρ _[T]_ = _C_ ( ρ _x_ ).
⊓⊔

We remark that _N_ ( _C_ ; _x_, τ ) is not the only tensor network for which the above Proposition holds.
Although the ordering of the edges in the contraction process does not affect the final tensor, it may
significantly affect space and time requirements.


9


**Proposition 3.6.** _Given a tensor network N of a size T quantum circuit, and a contraction process specified_
_by an ordering of wires in N, let d be the maximum rank of all the tensors that appear in the process. Then_
_the contraction takes O_ ( _T_ exp[ _O_ ( _d_ )]) _time._


_Proof._ Note that the size of _N_ is Θ ( _T_ ). The algorithm stores the tensors of each vertex. When contracting
an edge, it computes the new tensor according to Equation 1, and updates the tensor accordingly. This takes
exp[ _O_ ( _d_ )] time. Hence the total runtime is _O_ ( _T_ exp[ _O_ ( _d_ )]).
⊓⊔

In the next Section we will investigate near-optimal orderings for simulation and ways to find them.
While traditional simulation of quantum circuits proceeds in the same order in which the gates are applied,
it appears that an optimal ordering may not have any physical meaning. Therefore, we formalize this optimization using abstract graph contractions.

### **4 Contraction complexity and treewidth**


Let _G_ be a graph with vertex set _V_ ( _G_ ) and edge set _E_ ( _G_ ). Recall that the contraction process discussed in
the previous Section removes parallel edges in one step because contracting one edge at a time can create
multiple loops. However, for future convenience we prefer the latter simulation and therefore allow loops to
remain not contracted, counting toward the degree of a vertex. Note that if a “parallel” contraction contracts
ℓ edges between two vertices _u_ and _v_ of degrees ℓ + _k_ and ℓ + _k_ [′], respectively, the corresponding “one-edgeat-a-time” contraction would create vertices of degrees _k_ + _k_ [′] + ℓ 1, _k_ + _k_ [′] + ℓ 2,, _k_ + _k_ [′], each of which

                 -                 - ···
is _d_ ( _u_ ) + _d_ ( _v_ ). Thus the one-edge-at-a-time contraction process can emulate the parallel contraction,
≤
while increasing the maximum vertex degree observed by no more than two-fold. We make the definition of
this new contraction process precise below.


**Definition 4.1.** The _contraction of an edge e_ removes _e_ and replaces its end vertices (or vertex) with a
single vertex. A _contraction ordering_ π is an ordering of all the edges of _G_, π (1), π (2), ..., π (| _E_ ( _G_ )|). The
complexity of π is the maximum degree of a merged vertex during the contraction process. The _contraction_
_complexity_ of _G_, denoted by cc( _G_ ), is the minimum complexity of a contraction ordering.


Since only the degrees of the merged vertices are considered in defining the contraction complexity, cc( _G_ )
could be strictly larger than ∆ ( _G_ ). For example, if _G_ is a path, cc( _G_ ) = 1 and ∆ ( _G_ ) = 2.
Note that sequentially contracting all π ( _i_ ), 1 ≤ _i_ ≤| _E_ ( _G_ )|, reduces _G_ to a single vertex (or an empty graph
of several vertices). Also, for any graph _G_, cc( _G_ ) _E_ ( _G_ ) 1, since any merged vertex would be incident
≤| |−
to no more than | _E_ ( _G_ )|− 1 number of edges. Furthermore, cc( _G_ ) ≥ ∆ ( _G_ ) - 1, since when an edge incident
to a vertex of degree ∆ ( _G_ ) is removed, the resulting merged vertex is incident to at least ∆ ( _G_ ) - 1 edges.
The nature of cc( _G_ ) becomes clearer once we consider the _line graph_ of _G_, denoted by _G_ [∗] . That is, the

vertex set of _G_ [∗] is _V_ ( _G_ [∗] ) [def] = _E_ ( _G_ ), and the edge set is

_E_ ( _G_ [∗] ) [def] = _e_ 1, _e_ 2 _E_ ( _G_ ) : _e_ 1 = _e_ 2, _v_ _V_ ( _G_ ) such that _e_ 1 and _e_ 2 are both incident to _v_ .
{{ } ⊆ ̸ ∃ ∈ }

**Proposition 4.2.** _For any graph G_ = ( _V_, _E_ ) _,_ cc( _G_ ) = tw( _G_ [∗] ) _. Furthermore, given a tree decomposition of_
_G_ [∗] _of width d, there is a deterministic algorithm that outputs a contraction ordering_ π _with_ cc( π ) ≤ _d in_
_polynomial time._


Computing the treewidth of an arbitrary graph is NP-hard [6], but we do not know if this remains true
for the special class of graphs _G_ [∗] . Nevertheless, this is not critical in our work since the constant-factor
approximation due to Robertson and Seymour [29] suffices for us to prove our key results.


10


**Theorem 4.3** (Robertson and Seymour [29]) **.** _There is a deterministic algorithm that given a graph G_
_outputs a tree decomposition of G of width O_ (tw( _G_ )) _in time_ _V_ ( _G_ ) exp[ _O_ (tw( _G_ ))] _._
| | _[O]_ [(][1][)]

_Proof of Proposition 4.2._ There is a one-to-one correspondence of the contraction of an edge in _G_ and the
elimination of a vertex in _G_ [∗], and the degree of the merged vertex resulting from contracting an edge _e_ in _G_
is the same as the degree of _e_ being eliminated in _G_ [∗] . Thus cc( _G_ ) = tw( _G_ [∗] ).
To prove the second part of the statement, denote the tree decomposition by _T_ . Repeat the following
until the tree decomposition becomes an empty graph. Choose a leaf ℓ in _T_ . If ℓ is the single vertex of _T_,
output vertices (of _G_ [∗] ) in _B_ ℓ in any order. Otherwise, let ℓ [′] be its parent. If _B_ ℓ _B_ ℓ′, remove ℓ and repeat
⊆
this process. Otherwise, let _e_ _B_ ℓ _B_ ℓ′. Output _e_, remove it from the tree decomposition and continue the
∈              process, until all vertices of the tree decomposition are removed. The number of steps in this process is
polynomial in the size of the tree decomposition.
Note that each output _e_ appears in only one bag in the tree decomposition. Therefore, all (current)
neighbors of _e_ must appear in the same bag. Hence its induced width is at most _d_ . By the one-to-one
correspondence of the vertex elimination in _G_ [∗] and the contraction process in _G_, cc( π ) ≤ _d_ . ⊓⊔

Before we complete the description of our simulation algorithm, we relate the treewidth of _G_ to that of
_G_ [∗] . This is useful for reasoning about quantum circuits _C_ when the graph _GC_ is easier to analyze than
its line graph _GC_ [∗] [. In such cases one hopes to bound the runtime of the simulation algorithm in terms of]
parameters of _G_ rather than _G_ [∗] . Fortunately, since _GC_ is of bounded degree, the treewidths of _GC_ and _GC_ [∗]
are asymptotically the same.


**Lemma 4.4.** _For any graph G of maximum degree_ ∆ ( _G_ ) _,_

(tw( _G_ )              - 1)/2 ≤ tw( _G_ [∗] ) ≤ ∆ ( _G_ )(tw( _G_ )+ 1)              - 1.

_Proof._ From a tree decomposition _T_ of _G_ of width _d_ we obtain a tree decomposition _T_ [∗] of _G_ [∗] of width
( _d_ + 1) · ∆ ( _G_ ) − 1 by replacing each vertex _v_ ∈ _V_ ( _G_ ) with all edges _e_ incident to _v_ . This guarantees that
every edge of _G_ [∗] is in some bag, i.e. (T1) is true. Item (T2) is true since if _e_ 1 and _e_ 2 are both incident to a
vertex _u_ in _G_, then any bag in _T_ containing _u_ contains both _e_ 1 and _e_ 2 in _T_ [∗] . To verify Item (T3), suppose
that _e_ connects _u_ and _v_ in _V_ ( _G_ ). Take two bags _a_ and _b_ that both contain _e_ . Then in _T_, both bags _a_ and _b_
must have either _u_ or _v_ . If they contain the same vertex, then _a_ and _b_ are connected, by (T3). Otherwise,
there must be a bag _c_ that contains both _u_ and _v_, by (T2). So _a_ and _b_ are connected through _c_ . Therefore we
have proved that tw( _G_ [∗] ) ≤ ∆ ( _G_ )(tw( _G_ )+ 1) - 1.
Now to prove tw( _G_ ) ≤ 2tw( _G_ [∗] )+ 1, we start with a tree decomposition _T_ [∗] of _G_ [∗] of width _d_, and replace
every _e_ by its two end vertices in _V_ ( _G_ ). The verification of (T1) through (T3) can be accomplished in a
similar way.
⊓⊔

Note that the above bounds are asymptotically tight, since for an _m_ -ary tree (of which each non-root
internal vertex has degree _m_ + 1), the treewidth is 1 and the contraction complexity is _m_ . We summarize the
above finding in the following theorem.


**Theorem 4.5.** _Let d_ 1 _be an integer. For any family of graphs Gn, n_ N _, such that_ ∆ ( _Gn_ ) _d, for all n,_
≥ ∈ ≤
_then_
(tw( _Gn_ )         - 1)/2 ≤ cc( _Gn_ ) = tw( _G_ [∗] _n_ [)][ ≤] _[d]_ [(][tw][(] _[G][n]_ [)+] [1][)] [−] [1][,] ∀ _n_ ∈ N.

We are now ready to put everything together to prove the following restatement of Theorem 1.1.


11


**Theorem 4.6.** _LetC be a quantum circuit of size T and with n input and m output qubits, x_ 0, 1 _be an in-_
∈{ } _[n]_
_put, and_ τ : [ _m_ ] → **L** (C [2] ) _be a measurement scenario. Denote by GC the underlying circuit graph of C. Then_
_the probability that_ τ _is realized on C_ ( ρ _x_ ) _can be computed deterministically in time T_ _[O]_ [(][1][)] exp[ _O_ (cc( _GC_ ))] =
_T_ [(][1][)] exp[ _O_ (tw( _GC_ ))] _._

_Proof._ The following algorithm computes the desired probability.

(1) Construct _N_ = _N_ ( _C_ ; _x_, τ ).

(2) Apply the Robertson-Seymour algorithm to compute a tree decomposition _T_ of _N_ [∗] of width _w_ =
_O_ (tw( _N_ [∗] )) (Theorem 4.3).

(3) Find a contraction ordering π from _T_ (Proposition 4.2) of width _w_ .

(4) Contract _N_ using π, and output the desired probability from the final (rank-0) tensor (Proposition 3.5).

The runtime bottlenecks are Steps (2) and (4), both taking time _T_ _[O]_ [(][1][)] exp( _O_ [tw( _N_ [∗] )]), which by Theorem 4.5 is _T_ _[O]_ [(][1][)] exp[ _O_ (cc( _GC_ ))] = _T_ _[O]_ [(][1][)] exp[ _O_ (tw( _GC_ ))]. In fact, Steps 2 and 4 can be combined, but we
separate them for the sake of clarity.
⊓⊔

### **5 Treewidth and quantum circuits**


In this section we prove the implications of Theorem 1.1 stated in the Introduction. A number of tight
bounds for the treewidth of specific families of graphs have been published, including those for planar and
series-parallel graphs. However, similar results for graphs derived from quantum circuits are lacking. To
this end, we strengthen Corollary 1.5 as follows.


**Proposition 5.1.** _Let C be a quantum circuit in which each gate has an equal number of input and output_
_qubits, and whose qubits are index by_ [ _n_ ] _, for an integer n_ 1 _. Suppose that the size of C is T, and r is_
≥
_the minimum integer so that for any i,_ 1 _i_ _n_ 1 _, no more than r gates act on some qubits j and j_ [′] _with_
≤ ≤                 _j_ _i_ < _j_ [′] _. Then C can be simulated deterministically in time T_ _[O]_ [(][1][)] exp[ _O_ ( _r_ )] _._
≤

Corollary 1.5 follows since _r_ = _O_ ( _qD_ ) under its assumption.

_Proof of Proposition 5.1._ Assume without loss of generality that tw( _GC_ ) 2. Let _G_ be the graph obtained
≥
from _GC_ by removing degree 1 vertices and contracting edges incident to degree 2 vertices. Then tw( _G_ ) =
tw( _GC_ ), by Proposition 2.1 and the observation stated before it. Then each vertex in _G_ corresponds to a
multi-qubit gate in _C_ .
We now construct a tree decomposition _T_ for _G_ that forms a path of _n_  - 1 vertices _B_ 1− _B_ 2−···− _Bn_ −1.
The bag _Bi_ of the _i_ _[th]_ vertex (1 _i_ _n_ 1) consists of multi-qubit gates (vertices) that act on some qubits _j_
≤ ≤             and _j_ [′] with _j_ ≤ _i_ < _j_ [′] . Hence | _Bi_ | ≤ _r_ by the assumption. If _u_ acts on qubits _i_ 1, _i_ 2, ···, _ik_, _i_ 1 < _i_ 2 < ··· < _ik_,
then _i_ connects two gates _u_ ∈ _Bi_, for all _i_, _i u_ 1 ≤ and _i_ ≤ _v_, the bag _ik_ . Thus (T1) and (T3) are true. If a wire segment corresponding to the qubit _Bi_ contains both _u_ and _v_ . Thus (T2) is true. Therefore _T_ is a tree
decomposition for _G_ with width _r_ 1. Hence tw( _GC_ ) = tw( _G_ ) = _O_ ( _r_ ), which by Theorem 1.1 implies that
               _C_ can be simulated in _T_ _[O]_ [(][1][)] exp[ _O_ ( _r_ )] time.
⊓⊔

We now turn to quantum circuits of bounded depth. To prove Theorem 1.7 we will make use of the following observation that relates expander graphs to contraction complexity. Let _d_ be a constant and { _Gn_ } _n_ ∈N
be a family of _d_ -regular graphs, and ε - 0 be a universal constant. Recall that _Gn_ is called a family of
{ }
expander graphs with expansion parameter ε if, for any subset _S_ _V_ ( _Gn_ ) with _S_ _V_ ( _Gn_ ) /2, there are no
⊆ | | ≤| |
less than ε | _S_ | edges connecting vertices in _S_ with vertices in _V_ ( _G_ ) - _S_ .


12


**Lemma 5.2.** _For an expander graph Gn with the expansion parameter_ ε _,_ cc( _Gn_ ) ≥ ε | _V_ ( _Gn_ )|/4 _._

_Proof._ Fix a contraction ordering of _Gn_ . Let _v_ be the first merged vertex so that _kv_, the number of vertices
in _V_ ( _Gn_ ) that were eventually merged to _v_, is at least _V_ ( _Gn_ ) /4. Then _kv_ _V_ ( _Gn_ ) /2, and _v_ must have
| | ≤| |
degree ε _V_ ( _Gn_ ) /4.
| | ⊓⊔

The following graph is shown to be an expander by Lubotzky, Phillips and Sarnak [19]. Let _p_  - 2 be a
prime, and _Gn_ be the graph with _V_ ( _Gp_ ) [def] = Z _p_ ∞, and every vertex _x_ is connected to _x_ + 1, _x_ 1 and _x_ [−][1]
∪{ }                   
( ∞ 1 are defined to be ∞ ). Note that _Gp_ is a 3-regular graph.
±

_Proof of Theorem 1.7._ By Lemma 5.2, cc( _Gp_ ) = Ω ( _p_ ). Since _Gp_ is a 3 regular graph, tw( _Gp_ ) =
Θ (cc( _Gp_ )) = Ω ( _p_ ), by Theorem 4.5. Let _G_ [′] _p_ [be the graph obtained from] _[ G][p]_ [by removing the vertex] [ ∞]
and the edge 0, _p_ 1 . This would only decrease tw( _Gp_ ) by at most constant. Hence tw( _G_ [′] _p_ [) =] [ Ω] [(] _[p]_ [)][.]
{       - }
Therefore to prove the theorem, it suffices to construct a quantum circuit _C_ on _p_ qubits so that _G_ [′] _p_ [is a minor]
of _GC_ [∗] [.]
Each qubit of _C_ corresponds to a distinct vertex in _V_ ( _G_ [′] _p_ [)][. Observe that edges in] _[ E]_ [(] _[G]_ [′] _p_ [)][ can be partitioned]
into three vertex-disjoint subsets: (1) _x_, _x_ [−][1] ; (2) _x_, _x_ + 1 for even _x_, 0 _x_ _p_ 3; (3) the remaining
{ } { } ≤ ≤                   edges. Each subset gives a layer of two-qubit gates in _C_ . In _GC_ [∗] [, contracting all the vertices that correspond]
to the same qubit gives a graph of which _G_ [′] _p_ [is a minor. Hence tw][(] _[C]_ [) =] [ Θ] [(][tw][(] _[G]_ _C_ [∗] [)) =] [ Ω] [(] _[p]_ [)][.] ⊓⊔

_Proof of Theorem 1.8._ By Theorem 4.5, it suffices to prove that cc( _GC_ ) = _O_ (1) for any depth-2 circuit.
Observe that for any such circuit, after contracting the input and output vertices (those are of degree 1,
hence contracting them will not increase the contraction complexity), every vertex in _GC_ has degree either
1 or 2. Hence the edges can be decomposed into disjoint paths and cycles, which can be contracted without
increasing the degree. Hence cc( _GC_ ) 2.
≤ ⊓⊔

### **6 Simulating one-way quantum computation**


This section revisits the notions of _graph states_ and _one-way quantum computation_ . We first simulate oneway computation with an algorithm whose complexity grows exponentially with the contraction complexity
of the underlying graph. We then reduce general one-way computation to the special case where the vertex
degree is bounded by a constant. Since for such graphs the contraction complexity is the same as the
treewidth (up to a constant), this reduction facilitates a more efficient simulation algorithm, as stated in
Theorem 1.6.
Let _G_ = ( _V_, _E_ ) be a simple undirected graph with | _V_ | = _n_ . For a subset _V_ [′] ⊆ _V_, denote by _e_ ( _V_ [′] ) the
number of edges in the subgraph induced by _V_ [′] . We associate a qubit with each vertex _v_ ∈ _V_, and refer to it
by qubit _v_ . For a subset _V_ [′] ⊆ _V_, we identify the notation | _V_ [′] ⟩ with the computational basis | _x_ ⟩, for _x_ ∈{0, 1} _[n]_

being the characteristic vector of _V_ [′] (i.e., the _i_ _[th]_ bit of _x_ is 1 if and only if the _i_ _[th]_ vertex under some fixed
ordering is in _V_ [′] ). The graph state | _G_ ⟩ is the following _n_ -qubit quantum state [7]

1
## | G ⟩ [def] = √2 [n] [ ∑] V [′] ⊆ V (−1) [e] [(] [V] [ ′][)] | V [′] ⟩.

Note that _G_ can be created from 0 _[n]_ by first applying Hadamard gates to all qubits, followed by the
| ⟩ | ⟩
Controlled-Phase gate Λ ( σ _[z]_ ) = ∑ _b_ 1, _b_ 2∈{0,1}(−1) _[b]_ [1][·] _[b]_ [2] | _b_ 1, _b_ 2⟩⟨ _b_ 1, _b_ 2| on each pair of qubits _u_ and _v_ with
{ _u_, _v_ } ∈ _E_ . Since all the Λ ( σ _[z]_ ) operators commute, the order of applying them does not affect the result.
A basic building block of our simulation algorithm is the following.


13


**Lemma 6.1.** _Let G_ = ( _V_, _E_ ) _be a graph with n vertices, and_ τ _be a measuring scenario (defined in Defini-_
_tion 8) on n qubits. Then the probability p that_ τ _is realized on_ | _G_ ⟩ _can be computed deterministically in_
_time O_ ( _V_ exp[ _O_ (cc( _G_ ))]) _._
| | _[O]_ [(][1][)]

_Proof._ Fix a circuit _CG_ that creates _G_ from 0 0 . Let _u_, _v_ _E_, and _g_ = _gu_ +, _u_ −, _v_ +, _v_ - be a tensor in
| ⟩ | ⟩⟨ | [⊗] _[n]_ { } ∈
_N_ ( _CG_ ; τ ) corresponding to Λ ( σ _[z]_ )[ _u_, _v_ ]. The wires representing the qubit _u_ (or _v_ ) before and after the gate
are labeled _u_ [+] (or _v_ [+] ) and _u_ [−] (or _v_ [−] ), respectively. We replace _g_ by two tensors _g_ _[u]_ = _g_ _[u]_ _u_ [+], _u_ [−], _t_ [+], _t_ [−] [and]
_g_ _[v]_ = _g_ _[v]_ _v_ [+], _v_ [−], _t_ [+], _t_ [−][, which share two labels] _[ t]_ [+][ and] _[ t]_ [−] [and are defined as follows. For a wire segment with a]
label _a_, denote by **L** _a_ the 4-dimensional space of linear operators associated with this wire segment. Set
_g_ _[u]_ to be the identity superoperator that maps **L** _u_ + **L** _t_ - **L** _t_ + **L** _u_ −, and _g_ _[v]_ to be the tensor for a Λ ( σ _[z]_ )
⊗ → ⊗
that maps **L** _t_ + **L** _v_ + **L** _t_ - **L** _v_ −. By their definitions, contracting _g_ _[u]_ and _g_ _[v]_ gives precisely _g_ . We call the
⊗ → ⊗
inserted wires labeled with _t_ [+] and _t_ [−] _transition wires_ . See Figure 5 for an illustration.

![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-13-0.png)

![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-13-1.png)

u [+] v [+] u [+] v [+]







u [−] v [−] u [−] v [−]


Figure 5: Replacing a tensor _g_ corresponding to σ _z_ [ _u_, _v_ ] by two tensors _g_ _[u]_ and _g_ _[v]_ .


Denote by _N_ [′] ( _CG_ ; τ ) the tensor network obtained from _N_ ( _CG_ ; τ ) by applying the above replacement procedure for each edge in _E_ . Let _G_ [′] be the underlying graph of _N_ [′] ( _CG_ ; τ ). Note that _G_ [′] has the maximum
degree 4 and the number of vertices is _O_ ( _E_ ). See Figure 6 for an illustration. Thus _p_ can be computed by
| |
contracting _N_ [′] ( _CG_ ; τ ) in time _O_ ( _V_ exp[ _O_ (cc( _G_ [′] ))]), according to Theorem 4.6.
| | _[O]_ [(][1][)]


G N(CG; τ ) N [′] (CG; τ )


(a)                          (b)                         (c)                       (d)


Figure 6: For a graph _G_ in (a), the tensor network _N_ ( _CG_ ; τ ) is shown in (b). Input vertices are at the top, and
output vertices are at the bottom. Each box is a tensor corresponding to a Λ ( σ _z_ ) applied to qubits adjacent
in _G_ . In (c), each Λ ( σ _z_ ) tensor is replaced by two tensors and two wires connecting them, as described in
Figure 5. Contracting all solid lines in (c) produces the graph in (d), which is precisely _G_ with each edge
doubled.


We now prove that cc( _G_ [′] ) = _O_ (cc( _G_ )). This can be seen by contracting all wire segments corresponding


14



![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-13-4.png)

![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-13-5.png)
to the same qubit in _G_ [′], while leaving the transition wires untouched. Since contracting the edge incident
to an input or output vertex results in a new vertex of degree 3, and contracting the rest of the wires for a
qubit _v_ results in a new vertex of degree 2 _d_ ( _v_ ), the maximum degree of a merged vertex in this process is
max{3, 2 ∆ ( _G_ )}. The one-to-one correspondence between the resulting vertex set and _V_ induces naturally a
one-to-one correspondence between the pairs of transition wires and _E_ . Thus a contraction ordering of _G_
gives a contraction ordering of _G_ [′] (of this stage) with at most twice of the contraction complexity. Therefore

cc( _G_ [′] ) ≤ max{3, 2 ∆ ( _G_ ), 2cc( _G_ )} = _O_ (cc( _G_ )+ 1).

Thus _p_ can be computed deterministically in time _O_ ( _V_ exp[ _O_ (cc( _G_ [′] ))]) = _O_ ( _V_ exp[ _O_ (cc( _G_ ))]).
| | _[O]_ [(][1][)] | | _[O]_ [(][1][)]
⊓⊔

A _one-way_ computation on a quantum state | φ ⟩ consists of a sequence of adaptive single-qubit measurements and single-qubit unitary operations applied to | φ ⟩. The description of each measurement or unitary
operation, including the index of the qubit that it acts on, can be computed by a deterministic and efficient
(polynomial time) algorithm from previous operations and their measurement outcomes. In our discussion
we treat this computation time as a constant. We call a one-way quantum computation _oblivious_ if before the
last measurement (which produces the outcome of the computation), different computational paths involve
the same number of measurements, take place with the same probability, and result in an identical state.
Note that the one-way computation of Raussendorf and Briegel [26] is oblivious.
We point out that allowing single-qubit unitary operations in the definition is for the convenience of
discussion only, since each single-qubit unitary can be combined with a future measurement on the same
qubit (should there be one). To see this fact, let us call two quantum states _LU-equivalent_ (where LU stands
for Local Unitary), if there exists a set of single-qubit unitary operations applying which maps one state to the
other. A one-way computation with unitary operators always has an almost identical one-way computation
without unitary operations: the measurements are in one-to-one correspondence with identical outcome
distributions, and the states after corresponding measurements are LU-equivalent. Therefore, when we are
only interested in the distribution of the measurement outcomes, we may assume without loss of generality
that a one-way computation does not involve any unitary operation.
We now derive a simulation algorithm whose complexity depends on the contraction complexity.


**Lemma 6.2.** _A one-way quantum computation on a graph G_ = ( _V_, _E_ ) _can be simulated by a randomized_
_algorithm in time O_ ( _V_ exp[ _O_ (cc( _G_ )]) _. If the one-way computation is oblivious, the simulation can be_
| | _[O]_ [(][1][)]
_made deterministic._


_Proof._ Let _T_ be the number of measurements during the one-way computation. Assume without loss of
generality that no single-qubit unitary operation is applied. The simulation consists of _T_ steps, one for each
single-qubit measurement. It maintains a data structure _r_ = ( τ, _p_ ), where τ is a measurement scenario, and _p_
is the probability that τ is realized on | _G_ ⟩. Denote by _rt_ = ( τ _t_, _pt_ ) the value of _r_ when _t_ measurements have
been simulated. Initially τ 0( _i_ ) = _I_ for all _i_, 1 ≤ _i_ ≤ _n_, and _p_ 0 = 1.
Suppose we have simulated the first _t_ 1 measurements, 1 _t_ _T_ 1.
                 - ≤ ≤                 
(1) Based on the one-way algorithm, compute from τ _t_ 1 the description of the _t_ _[th]_ measurement _Pt_ =

                    _Pt_ [0][,] _[P]_ _t_ [1] [that it acts on. Denote by] [ τ] _t_ [0] [the measurement scenario identical to] [ τ] _[t]_ [−][1][,]
{ [}][ and the qubit] _[ a][t]_
except that τ _t_ [0][(] _[a][t]_ [) =] _[ P]_ _t_ [0][.]

(2) Compute _pt_ [0][, the probability of realizing] [ τ] _t_ [0][. By Lemma 6.1, this takes] _[ O]_ [(][|] _[V]_ [|] _[O]_ [(][1][)][ exp][[] _[O]_ [(][cc][(] _[G]_ [))])][ time.]


15


(3) Flip a coin that produces 0 with probability _pt_ [0][/] _[p][t]_ [−][1][, resulting in an outcome] _[ b][t]_ [to be]

[∈{][0][,] [1][}][. Set] [ τ] _[t]_
identical to τ _t_ 1, except that τ ( _at_ ) = _pt_ _[b]_ . Set _[t]_ _pt_ = (1 _bt_ ) _pt_ [0] [+] _[b][t]_ [(] _[p][t]_ [−][1] _t_ [)][. Continue the simulation]

       -       - [−] _[p]_ [0]
until _t_ = _T_ .

By construction, the output distribution is identical to that of the one-way computation. The complexity
of the algorithm is _O_ ( _V_ exp[cc( _G_ )]).
| | _[O]_ [(][1][)]
If the one-way computation is oblivious, there is no need to adaptively simulate the first _T_ 1 mea                                    surements, as all of them lead to the same state with the same probability _pT_ 1. Let τ _T_ 1 ( τ _T_ ) be the

                             -                             measurement scenario corresponding to the first _T_ 1 ( _T_, respectively) measurements giving the outcome
                    0. We compute the probabilities _pT_ 1 and _pT_ that τ _T_ 1 and τ _T_ are realized. Then the probability that

             -              the one-way computation produces 0 is precisely _pT_ / _pT_ −1. The computation is deterministic and takes
_V_ exp[ _O_ (cc( _G_ ))] time by Lemma 6.1.
| | _[O]_ [(][1][)] ⊓⊔

The main difference between the above lemma and Theorem 1.6 is that the simulating complexity of
the former is exponential in cc( _G_ ), while that of the latter is exponential in tw( _G_ ). Since ∆ ( _G_ ) is not
bounded in general, the lemma does not directly imply the theorem. We shall reduce a one-way computation
on a graph state | _G_ ⟩ to a one-way computation on another graph state | _G_ [′] ⟩, such that ∆ ( _G_ [′] ) = _O_ (1) and
tw( _G_ [′] ) = _O_ (tw( _G_ )). Under this reduction, the exponent in the simulating complexity is on the order of
cc( _G_ [′] ) = _O_ (tw( _G_ [′] )) = _O_ (tw( _G_ )). Such a reduction was found in [21]. Let _G_ and _G_ [′] be two graphs. We call
_G_ [′] an _expansion_ of _G_ if _G_ can be obtained from _G_ [′] by contracting a set of edges that form a forest.

**Theorem 6.3** ([21]) **.** _Any undirected simple graph G_ = ( _V_, _E_ ) _has an expansion G_ [′] = ( _V_ [′], _E_ [′] ) _such that_
∆ ( _G_ [′] ) ≤ 3 _,_ | _V_ [′] | = _O_ (| _E_ | + | _V_ |) _, and_ tw( _G_ [′] ) ≤ tw( _G_ ) + 1 _. Furthermore, such a graph G_ [′] _can be computed_
_deterministically from G in_ ( _V_ ) _[O]_ [(][1][)] exp[ _O_ (tw( _G_ ))] _time._
| |

In our application we need to insert a vertex into an edge that will be contracted during the transformation
of the graph _G_ [′] in the above theorem to _G_ . This is to facilitate the application of the following fact about
graph states, a proof for which is given in the Appendix.

**Proposition 6.4** ([26]) **.** _Let G be a graph obtained from a simple undirected graph G_ [′] _by replacing a vertex_
_u_ ∈ _V_ ( _G_ [′] ) _with three vertices v, w, and v_ [′] _, such that w is adjacent to v and v_ [′] _only, and each vertex adjacent to_
_u in G_ [′] _becomes adjacent to either v or v_ [′] _, but not both. Then_ | _G_ [′] ⟩ _can be obtained from_ | _G_ ⟩ _by an oblivious_
_one-way computation that makes_ 2 _measurements._

The use of expansion is illustrated in Figure 7, and summarized in the following Corollary.


**Corollary 6.5.** _Let G_ = ( _V_, _E_ ) _be a simple undirected graph. There exists a graph G_ 1 = ( _V_ 1, _E_ 1) _such that_
_(a)_ ∆ ( _G_ 1) ≤ 3 _, (b)_ | _V_ 1| = _O_ (| _E_ | + | _V_ |) _, (c)_ tw( _G_ 1) ≤ tw( _G_ ) + 1 _, (d) G_ 1 _can be computed deterministically_
_from G in time_ _V_ exp[ _O_ (tw( _G_ ))] _, and, (e)_ _G_ _can be obtained by an oblivious one-way computation_
| | _[O]_ [(][1][)] | ⟩
_on_ | _G_ 1⟩ _,_

contracting which would transform _Proof._ Let _G_ [′] = ( _V_ [′], _E_ [′] ) be a graph satisfying the properties in Theorem 6.3. Let _G_ [′] to _G_ . For each _e_ _E_ 1 [′] [, insert a vertex at] _[ e]_ [ (that is, disconnect the end] _E_ 1 [′] [⊆] _[E]_ [′][ be the set of edges]
∈
vertices of _e_ and connect them to the new vertex).
We show that the resulting graph _G_ 1 satisfies the required properties. Note that by Proposition 2.1,
tw( _G_ [′] ) = tw( _G_ 1). Properties of _G_ [′] implies that Properties (a–e) hold. The composition of the oblivious
one-way computation in Proposition 6.4 applied to the inserted vertices transforms | _G_ 1⟩ to | _G_ ⟩, and is itself
oblivious.
⊓⊔

We are now able to prove this section’s main theorem, which restates Theorem 1.6 and extends it to the
case of oblivious one-way computation.


16


![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-16-0.png)

![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-16-1.png)

![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-16-2.png)

![](.figures/arxiv__quant-ph-0511069/quant-ph-0511069.pdf-16-3.png)

(a)                         (b)                            (c)                       (d)


Figure 7: To a graph with high-degree vertices in (a) we apply the construction from [21] to produce a
small-degree expansion in (b) that preserves treewidth. The graph in (c) is obtained from (b) by inserting a
vertex at each edge. The corresponding graph state can lead to the graph state of (a) through an oblivious
one-way computation. The graph in (d) illustrates that not every expansion of (a) preserves treewidth [21].


**Theorem 6.6.** _Let G_ = ( _V_, _E_ ) _be a simple undirected graph. Then a one-way computation on G can be sim-_
_ulated by a randomized algorithm in time_ _V_ exp[ _O_ (tw( _G_ ))] _. The simulation can be made deterministic_
| | _[O]_ [(][1][)]
_if the one-way computation is oblivious._

_Proof._ Let _G_ 1 = ( _V_ 1, _E_ 1) be a graph satisfying the properties stated in Corollary 6.5. Thus | _G_ ⟩ can be
obtained from | _G_ 1⟩ through an oblivious one-way computation. Therefore, the given one-way computation
_P_ on | _G_ ⟩ can be carried out by a one-way computation _P_ [′] on | _G_ 1⟩ which first produces | _G_ ⟩ then continues
executing _P_ . Note that _P_ [′] is oblivious if _P_ is. By Lemma 6.2, _P_ [′] can be simulated by a randomized, or
deterministic if _P_ is oblivious, algorithm in time _O_ (| _V_ 1| _[O]_ [(][1][)] exp[ _O_ (cc( _G_ 1))]). Note that cc( _G_ 1) = _O_ (tw( _G_ 1)),
by Lemma 4.5, since ∆ ( _G_ 1) ≤ 3. Thus cc( _G_ 1) = _O_ (tw( _G_ )), since tw( _G_ 1) ≤ tw( _G_ ) + 1. Since | _V_ 1| =
_O_ ( _V_ + _E_ ) = _O_ ( _V_ ), the simulation time complexity is _O_ ( _V_ exp[ _O_ (tw( _G_ ))]).
| | | | | | [2] | | _[O]_ [(][1][)] ⊓⊔

### **7 Discussion**


In this work we studied quantum circuits regardless of the types of gates they use, but with a focus on how
the gates are connected. We have shown that quantum circuits that look too similar to trees do not offer
significant advantage over classical computation. More generally, when solving a difficult classical problem
on a quantum computer, one encounters an _inherent_ trade-off between the treewidth and the size of quantum
circuits for solving it — the smaller the quantum circuit, the more topologically sophisticated it must be.
Investigating such trade-offs for specific problems of interest is an entirely open and very attractive avenue
for future research. Similar considerations may apply to classical circuits. We conjecture that there are
simple functions, such as modular exponentiation, whose circuit realizations require large treewidth.
Furthermore, our work raises an intriguing possibility that the treewidth of some quantum circuits may be
systematically reduced by restructuring the circuit, while preserving the final result of the entire computation. Perhaps, future research in this direction can clarify the limits to efficient quantum computation, while
the tools developed in this context will be useful for practical tasks.


17


The pre-print of this paper [20] has lead to several follow-up results. Jozsa [16] and Aharonov et al. [3]
gave alternative proofs for some of our theorems. Furthermore, Aharonov et al. [3], and Yoran and Short [40]
pointed out that Quantum Fourier Transform (QFT) over Z _n_ admits approximate circuit realizations that,
viewed as tensor networks, have small treewidth. Given the central role of QFT in known quantum algorithms, their results are somewhat unexpected and their implications are yet to be fully explored. For
example, what type of circuits would remain efficiently simulatable when interleaved with QFT circuits?
In general, as implied by Theorem 1.7 and 1.8, the treewidth of a circuit may increase dramatically under
composition. Yoran and Short [40] have shown that this drawback may be avoided in some cases. Extending
their result would deepen our understanding of quantum speed-ups.
The important question of characterizing quantum states that are universal (or efficiently simulatable) for
one-way quantum computation remains unsolved. In another follow-up thread, van den Nest et al. [23, 22]
defined additional width-based parameters of quantum states and demonstrated results for those parameters
similar to Theorem 1.6. It is unlikely that the set of quantum states with small width-based parameters
includes all efficiently simulatable states because a set of simulatable states of high widths was identified
recently by Bravyi and Raussendorf [9]. Nevertheless, it remains plausible that those width-based results
and their further extensions may be part of a classification theorem that gives a complete characterization of
efficiently simulatable states.
**Acknowledgments.** We thank George Viamontes and John Hayes for motivating this study and helpful
discussions. We are grateful to Guifr´e Vidal, Frank Verstraete, Ashwin Nayak, Tzu-Chieh Wei, and the
anonymous reviewers for many valuable comments, including pointing out relevant previous works. Y. S.
is grateful to Alexei Kitaev for introducing to him the general concept of tensor networks, and to Peng-Jun
Wan for useful comments. I. M. is grateful to Ike Chuang for useful discussions.

### **References**


[1] S. Aaronson and D. Gottesman. Improved simulation of stabilizer circuits. _Physical Review A_,
70:052328, 2004.


[2] D. Aharonov, A. Kitaev, and N. Nisan. Quantum circuits with mixed states. In _Proceedings of the 31th_
_Annual ACM Symposium on the Theory of Computation (STOC)_, pages 20–30, 1998.


[3] D. Aharonov, Z. Landau, and J. Makowsky. The quantum FFT can be classically simulated. Preprint:
quant-ph/0611156.


[4] J. Alber, H. L. Bodlaender, H. Fernau, T. Kloks, and R. Niedermeier. Fixed parameter algorithms for
dominating set and related problems on planar graphs. _Algorithmica_, 33(4):461–493, 2002.


[5] S. Arnborg. Efficient algorithms for combinatorial problems on graphs with bounded decomposability

   - a survey. _BIT_, 25(1):2–23, 1985.


[6] S. Arnborg, D. G. Corneil, and A. Proskurowski. Complexity of finding embeddings in a _k_ -tree. _SIAM_
_Journal on Algebraic and Discrete Methods_, 8(2):277–284, 1987.


[7] H.J. Briegel and R. Raussendorf. Persistent entanglement in arrays of interacting particles. _Physical_
_Review Letters_, 86, 910–913, 2001.


[8] H. L. Bodlaender. Treewidth: characterizations, applications, and computations. Technical Report
UU-CS-2006-041, Universiteit Utrecht.


18


[9] S. Bravyi and R. Raussendorf. On measurement-based quantum computation with the toric code states.
Preprint: quant-ph/0610102.


[10] E. Broering and S. Lokam. Width-based algorithms for SAT and Circuit-SAT (extended abstract).
In _Sixth International Conference on Theory and Applications of Satisfiability Testing (SAT 2003),_
_Springer-Verlag Lecture Notes in Computer Science (LNCS)_, volume 2919, pp. 162–171, 2004.


[11] R. Dechter. Bucket elimination: a unifying framework for reasoning. _Artificial Intelligence_, 113(12):41–85, 1999.


[12] L.-M. Duan and R. Raussendorf. Efficient quantum computation with probabilistic quantum gates.
_Physical Review Letters_, 95:080503, 2005.


[13] D. Gottesman. The Heisenberg representation of quantum computers. In S. P. Corney, R. Delbourgo,
and P. D. Jarvis, editors, _Group22: Proceedings of the XXII International Colloquium on Group The-_
_oretical Methods in Physics_, pages 32–43, Cambridge, MA, 1999. International Press. Long version:
quant-ph/9807006.


[14] S. F. F. Green, S. Homer, and Y. Zhang. Bounds on the power of constant-depth quantum circuits.
Preprint: quant-ph/0312209, 2004.


[15] A. W. Joshi. _Matrices and tensors in physics_ . Halsted Press [John Wiley & Sons], New York-LondonSydney, 1975.


[16] R. Jozsa. On the simulation of quantum circuits. Preprint: quant-ph/0603163.


[17] R. Jozsa and N. Linden. On the role of entanglement in quantum computational speed-up. _Proceedings_
_of the Royal Society of London, Series A_, 459: 2011-2032, 2003.


[18] S. Krishnaswamy, G. F. Viamontes, I. L. Markov and J. P. Hayes. Accurate reliability evaluation and
enhancement via probabilistic transfer matrices. _Proc. Design Automation and Test in Europe (DATE)_,
pp. 282-287, Munich, Germany, March 2005.


[19] A. Lubotzky, R. Phillips, and P. Sarnak. Ramanujan graphs. _Combinatorica_, 8(3):261–277, 1988.


[20] I. L. Markov and Y. Shi. Simulating quantum computation by contracting tensor networks. Pre-print:
quant-ph/0511069.


[21] I. L. Markov and Y. Shi. Constant degree graph expansions and treewidth. Manuscript.


[22] M. van den Nest, W. D¨ur, G Vidal,and H J. Briegel. Classical simulation versus universality in
measurement based quantum computation. _Physical Review A_, 75:012337, 2007.


[23] M. van den Nest, A. Miyake, W. D¨ur and H. J Briegel. Universal resources for measurement-based
quantum computation. _Physical Review Letters_, 97:150504, 2006.


[24] M. A. Nielsen and I. L. Chuang. _Quantum Computation and Quantum Information_ . Cambridge
University Press, Cambridge, England, 2000.


[25] D. Porras, F. Verstraete and J. I. Cirac. Renormalization algorithm for the calculation of spectra of
interacting quantum systems. Preprint: cond-mat/0504717.


19


[26] R. Raussendorf and H. J. Briegel. A one-way quantum computer. _Physical Review Letters_, 86, 5188–
5191, 2001.


[27] N. Robertson and P. D. Seymour. Graph minors. II. Algorithmic aspects of tree-width. _Journal of_
_Algorithms_, 7(3):309–322, 1986.


[28] N. Robertson and P. D. Seymour. Graph minors. III. Planar tree-width. _Journal of Combinatorial_
_Theory, Series B_, 36(1):49–64, 1984.


[29] N. Robertson and P. D. Seymour. Graph minors. X. Obstructions to tree-decomposition. _Journal of_
_Combinatorial Theory, Series B_, 52(2):153–190, 1991.


[30] D. J. Rose. Triangulated graphs and the elimination process. _Journal of Mathematical Analysis and_
_Applications_, 32:597–609, 1970.


[31] V. P. Roychowdhury and F. Vatan. Quantum formulas: a lower bound and simulation. _SIAM Journal_
_on Computing_, 31(2): 460–476, 2001.


[32] B. M. Terhal and D. P. DiVincenzo. Classical simulation of noninteracting-fermion quantum circuits.
_Physical Review A_, 65:32325–32334, 2002.


[33] B. M. Terhal and D. P. DiVincenzo. Adaptive quantum computation, constant depth quantum circuits
and Arthur-Merlin games. _Quantum Information and Computation_, 4(2):134–145, 2004.


[34] L. G. Valiant. Quantum circuits that can be simulated classically in polynomial time. _SIAM Journal_
_on Computing_, 31(4):1229–1254, Aug. 2002.


[35] F. Verstraete and J. I. Cirac. Renormalization algorithms for Quantum-Many Body Systems in two
and higher dimensions. Preprint: cond-mat/0407066.


[36] F. Verstraete, J. J. Garcia-Ripoll and J. I. Cirac. Matrix product density operators: simulation of
finite-temperature and dissipative systems. _Physical Review Letters_, 93:207204, 2004.


[37] G. Vidal. Efficient classical simulation of slightly entangled quantum computations. _Physical Review_
_Letters_, 91:147902, 2003.


[38] G. Vidal. Efficient simulation of one-dimensional quantum many-body systems. _Physical Review_
_Letters_, 93:040502, 2004.


[39] P. Walther, K.J. Resch, T. Rudolph, E. Schenck, H. Weinfurter, V. Vedral, M. Aspelmeyer, and
A. Zeilinger. Experimental one-way quantum computing. _Nature_, 434, 169–176, 2005.


[40] N. Yoran and A. Short. Efficient classical simulation of the approximate quantum Fourier transform.
_Physical Review A_, 76:042321, 2007.


[41] A. Yao. Quantum circuit complexity. _Proceedings of the 34th Annual Symposium on Foundations of_
_Computer Science_, 352–361, 1993.


[42] M. Zwolak and G. Vidal. Mixed-State dynamics in one-dimensional quantum lattice systems: a timedependent superoperator renormalization algorithm. _Physical Review Letters_, 93:207205, 2004.


20


### **A Proof of Proposition 2.1**

Recall that a minor of a graph _G_ is a graph obtained from a subgraph of _G_ by contracting edges. A basic
property of treewidth is that it does not increase under taking minors [27].


_Proof of Proposition 2.1._ Let _G_ [′] be the graph resulting from the contractions. Since _G_ [′] is a minor of _G_,
tw( _G_ [′] ) tw( _G_ ) ([27]). If tw( _G_ [′] ) = 1, then _G_ [′] is a non-empty forest (otherwise _G_ has a triangle minor,
≤
thus tw( _G_ ) 2). Thus _G_ is also a non-empty forest and tw( _G_ ) = 1 = tw( _G_ [′] ). Suppose tw( _G_ [′] ) 2. Let
≥ ≥
_T_ be a tree decomposition for _G_ [′] . We obtain a tree decomposition _T_ [′] for _G_ by inserting a bag containing
_u_, _w_, _v_, and connecting it to a bag that contains _u_, _v_ . One can verify directly that the three conditions
{ } { }
( _T_ 1 _T_ 3) that define tree decompositions hold for _T_ . Since the width of _T_ is no more than that of _T_, we
  - [′] [′]
have tw( _G_ ) tw( _G_ [′] ). Therefore, tw( _G_ ) = tw( _G_ [′] ).
≤ ⊓⊔

### **B Proof of Proposition 6.4**

_Proof of Proposition 6.4._ Denote by _G_ [¯] the subgraph of _G_ [′] induced by _V_ ( _G_ [′] ) _u_ . Let _A_ and _A_ [′] be vertices
−{ }
in _V_ ( _G_ [′] ) _u_ that are adjacent to _v_ and _v_ [′], respectively, in _G_ . Note that _A_ _A_ [′] =, thus _A_ _A_ [′] = _A_ _A_ [′] is
−{ } ∩ ⊘ ⊕ ∪
the neighborhood of _u_ in _G_ [′] . Also, _v_ _A_ [′] and _v_ [′] _A_ .
̸∈ ̸∈
Starting with _G_, we first measure σ _x_ on _w_ . If the outcome is +1, the resulting state is
| ⟩

| φ 1⟩ [def] = |00⟩ _v_ [′] _v_ | _G_ [¯] ⟩ + |11⟩ _v_ [′] _v_ σ _z_ [ _A_ ⊕ _A_ [′] ]| _G_ [¯] ⟩. (2)

Otherwise, the resulting state is
01 _v_ [′] _v_ σ _z_ [ _A_ ] _G_ [¯] + 10 _v_ [′] _v_ σ _z_ [ _A_ [′] ] _G_ [¯],
| ⟩ | ⟩ | ⟩ | ⟩

which can be brought to | φ 1⟩ by σ _x_ [ _v_ ] σ _z_ [ _A_ ]. We then measure σ _x_ [ _v_ [′] ] on | φ 1⟩. If the outcome is +1, then the
resulting state is precisely _G_ [′] . Otherwise it is
| ⟩

0 _v_ _G_ [¯] 1 σ _z_ [ _A_ _A_ [′] ] _G_ [¯],
| ⟩ | ⟩−| ⟩ ⊕ | ⟩

which can be brought to _G_ [′] by σ _z_ [ _v_ ]. The four outcomes of the two measurements have equal probability
| ⟩
(1/4). Thus the one-way computation is oblivious.
⊓⊔


21
