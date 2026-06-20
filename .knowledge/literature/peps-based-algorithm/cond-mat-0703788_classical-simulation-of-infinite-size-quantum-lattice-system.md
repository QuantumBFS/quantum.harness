---
source: "https://arxiv.org/abs/cond-mat/0703788"
type: "arxiv"
canonical_id: "cond-mat/0703788"
title: "Classical simulation of infinite-size quantum lattice systems in two spatial dimensions."
authors: "Jordan, J., Orus, R., Vidal, G., Verstraete, F., Cirac, J. I."
year: "2008"
venue: "Physical Review Letters"
arxiv_id: "cond-mat/0703788"
doi: "10.1103/PhysRevLett.101.250602"
full_text: yes
---

# Classical simulation of infinite-size quantum lattice systems in two spatial dimensions.

**Authors:** Jordan, J., Orus, R., Vidal, G., Verstraete, F., Cirac, J. I.

**Citation:** Physical Review Letters, vol. 101 25, pp. 
          250602
        , 2008

**arXiv:** [cond-mat/0703788](https://arxiv.org/abs/cond-mat/0703788)

**DOI:** [10.1103/PhysRevLett.101.250602](https://doi.org/10.1103/PhysRevLett.101.250602)

## Abstract

We present an algorithm to simulate two-dimensional quantum lattice systems in the thermodynamic limit. Our approach builds on the projected entangled-pair state algorithm for finite lattice systems [F. Verstraete and J. I. Cirac, arxiv:cond-mat/0407066] and the infinite time-evolving block decimation algorithm for infinite one-dimensional lattice systems [G. Vidal, Phys. Rev. Lett. 98, 070201 (2007)10.1103/PhysRevLett.98.070201]. The present algorithm allows for the computation of the ground state and the simulation of time evolution in infinite two-dimensional systems that are invariant under translations. We demonstrate its performance by obtaining the ground state of the quantum Ising model and analyzing its second order quantum phase transition.

## Full Text

**Classical simulation of infinite-size quantum lattice systems in two spatial dimensions**



J. Jordan [1], R. Orús [1], G. Vidal [1], F. Verstraete [2], J. I. Cirac [3]

1 _School of Physical Sciences, The University of Queensland, QLD 4072, Australia_
2 _Fakult_ ¨a _t f_ ¨u _r Physik, Universit_ ¨a _t Wien, Boltzmanngasse 3, A-1090 Wien_
3 _Max-Planck-Institut f_ ¨u _r Quantenoptik, Hans Kopfermann-Str. 1, Garching, D-85748, Germany_



We present an algorithm to simulate two-dimensional quantum lattice systems in the thermodynamic limit.
Our approach builds on the _projected entangled-pair state_ algorithm for finite lattice systems [F. Verstraete
and J.I. Cirac, cond-mat/0407066] and the infinite _time-evolving block decimation_ algorithm for infinite onedimensional lattice systems [G. Vidal, Phys. Rev. Lett. 98, 070201 (2007)]. The present algorithm allows for
the computation of the ground state and the simulation of time evolution in infinite two-dimensional systems that
are invariant under translations. We demonstrate its performance by obtaining the ground state of the quantum
Ising model and analysing its second order quantum phase transition.



PACS numbers:


Strongly interacting quantum many-body systems are of
central importance in several areas of science and technology, including condensed matter and high-energy physics,
quantum chemistry, quantum computation and nanotechnology. From a theoretical perspective, the study of such systems
often poses a great computational challenge. Despite the existence of well-stablished numerical techniques, such as exact
diagonalization, quantum monte carlo [1], the density matrix
renormalization group [2] or series expansion [3] to mention
some, a large class of two-dimensional lattice models involving frustrated spins or fermions remain unsolved.
Fresh ideas from quantum information have recently led
to a series of new simulation algorithms based on an efficient representation of the lattice many-body wave-function
through a _tensor network_ . This is a network made of small
tensors interconnected according to a pattern that reproduces
the structure of entanglement in the system. Thus, a _matrix_
_product state_ (MPS) [4], a tensor network already implicit
in the density matrix renormalization group, is used in the
time-evolving block decimation (TEBD) algorithm to simulate time evolution in one-dimensional lattice systems [5],
whereas a _tensor product state_ [6] or _projected entangled-pair_
_state_ (PEPS) [7] is the basis to simulate two-dimensional lattice systems. In turn, the _multi-scale entanglement renormal-_
_ization ansatz_ accuratedly describes critical and topologically
ordered systems [8].
In this work we explain how to modify the PEPS algorithm
of Ref. [7] to simulate two-dimensional lattice systems in the
thermodynamic limit. By addressing an infinite system directly, the infinite PEPS (iPEPS) algorithm can analyse bulk
properties without dealing with boundary effects or finite-size
corrections. This is achieved by generalizing, to two dimensions, the basic ideas underlying the infinite TEBD (iTEBD)

[9]. Namely, we exploit translational invariance (i) to obtain
a very compact PEPS description with only two independent
tensors and (ii) to simulate time evolution by just updating
these two tensors. We describe the essential new ingredients
of the iPEPS algorithm, which is based on numerically solving a transfer matrix problem with an MPS. We then use it
to compute the ground state of the quantum Ising model with
transverse magnetic field, evaluate local observables, identify



the critical point of its second order quantum phase transition
and estimate the critical exponent β.
We point out that the algorithms of Ref. [6] have already
addressed the computation of the ground state of infinite twodimensional systems, by analysing an infinite transfer matrix
problem with a MPS. A major difference in our approach is
how this is handled. Instead of DMRG techniques (which
consider an increasingly large chain with a finite MPS), we
use the iTEBD algorithm [9], based on a power method that
uses an infinite MPS (iMPS) from the start. This seems to
significantly improve the results reported in Ref. [6].
**Finite PEPS algorithm.—** We start by recalling some basic facts of the PEPS algorithm for a finite system [7]. Consider a two-dimensional lattice L where each site, labeled by
a vector ⃗r, is represented by a Hilbert space V [[][⃗r][]][ ∼] = C [d] of
finite dimension d, so that the Hilbert space of the lattice is
VL = [�] ⃗r∈L [V][ [][⃗r][]][. For concreteness, we address the case of]
a square lattice, with N × N sites labelled by a pair of integers ⃗r = (x, y), x, y = 1, · · ·, N . [However, the key ingredients of the algorithm for infinite systems to be considered
here are still valid for any type of regular lattice.] The model
is further characterized by a Hamiltonian H = [�] ⃗r1,⃗r2 [h][[][⃗r][1][⃗r][2][]]

that decomposes as a sum of terms h [[][⃗r][1][⃗r][2][]] involving pairs of
nearest neighbor sites ⃗r1,⃗r2 ∈L. A pure state |Ψ⟩∈ VL of
the lattice is represented by a PEPS, namely a set of N × N
tensors {A [[][⃗r][]] }⃗r∈L, interconnected into a network P that follows the pattern of L (Figs. 1.i and 1.ii). Tensor A [[] sudlr [⃗r][]]
is made of complex numbers labelled by one _physical_ index
s and four _bond_ indices u, d, l and r. The physical index
runs over a basis {|s⟩}s=1,···,d of V [[][⃗r][]], whereas each bond
index takes D values and connects the tensor with the tensors in nearest neighbor sites. Thus, |Ψ⟩ is written in terms
of O(N [2] D [4] d) parameters, from which the d [N] complex amplitudes ⟨s(1,1)s(1,2) · · · s(N,N )|Ψ⟩ can be recovered by fixing
the physical index of each tensor A [[][⃗r][]] in P and by contracting
all the bond indices.
Given a PEPS for some state |Ψ0⟩∈ VL, the algorithm of
Ref. [7] allows to perform e.g. the following two tasks: (i)
computation of expected values ⟨Ψ0|O|Ψ0⟩ for a local operator O, such as the energy, a local order parameter or two-point
correlators, and (ii) update of the PEPS after a gate g [[][⃗r][1][⃗r][2][]] has


![](.figures/arxiv__cond-mat-0703788/cond-mat-0703788.pdf-1-0.png)

Figure 1: (color online) Diagramatic representations of (i) a PEPS
tensor Asudlr with one physical index s and four inner indices u,d, l
and r; (ii) local detail of the tensor network P for an iPEPS. Copies
of tensors A and B are connected through four types of links; (iii)
reduced tensor a of Eq. (2); and (iv) local detail of the tensor network
E .


been applied on two nearest sites ⃗r1,⃗r2 ∈L. The second task
can be used to simulate an evolution according to Hamiltonian
H, both in real time and in imaginary time,


e [−][Hτ] |Ψ0⟩
|Ψt⟩ = e [−][iHt] |Ψ0⟩, |Ψτ ⟩ = (1)
||e [−][Hτ] |Ψ0⟩|| [,]

in the sense of obtaining a new PEPS representation that approximates the states |Ψt⟩ and |Ψτ ⟩. This is achieved by
breaking the evolution operators e [−][iHt] and e [−][Hτ] into a sequence of local gates, using a Suzuki-Trotter expansion [10],
and by updating the PEPS after applying each of these gates.
In particular, one can approximate the ground state of Hamiltonian H through simulating an evolution in imaginary time
for large time τ, starting from a product state |Ψ0⟩ (for which
a PEPS can be trivially constructed).
Let E denote the network made by the N × N reduced tensors a [[][⃗r][]] (Figs. 1.iii and 1.vi),

   a [[] u¯ [⃗r] d []][¯][¯] lr¯ [≡] A [[] s udlr [⃗r][]] [(][A][[] s u [⃗r][]] `[′]` d `[′]` l `[′]` r `[′]` [)][∗][,] (2)

s

where ¯u represents the double bond index (u, u [′] ) and the
physical index s has been contracted, and let ⃗r1,⃗r2 ∈L denote two nearest neighbor sites. Then the _environment_ E [[][⃗r][1][,⃗r][2][]]

for these two sites is the network obtained by removing the
tensors a [[][⃗r][1][]] and a [[][⃗r][2][]] from E. By " _contracting a tensor net-_
_work_ " we mean " _summing over all the indices that connect_
_any two tensors of the network_ ". It turns out that both (i) the
computation of an expected value ⟨Ψ|O [[][⃗r][1][,⃗r][2][]] |Ψ⟩ and (ii) the
update of the PEPS after a gate g [[][⃗r][1][⃗r][2][]] can be achieved by contracting E [[][⃗r][1][,⃗r][2][]] . However, the cost of this contraction grows
exponentially with N . The core of the PEPS algorithm [7] is
an approximate, _efficient_ (quadratic in N ) scheme to contract
E [[][⃗r][1][,⃗r][2][]], based on MPS simulation techniques.
**Infinite PEPS algorithm.—** In order to consider the limit
of an infinite lattice, N →∞, where both |Ψ⟩ and H are in


2


Figure 2: The environment E [[][⃗r][1][,⃗r][2][]] for a link of type r is first approximated by an infinite strip F [[][⃗r][1][,⃗r][2][]] and then by a six-tensor network
G [[][⃗r][1][,⃗r][2][]] . These reductions can be performed according to either a
vertical/horizontal scheme (ii.a) or a diagonal scheme (ii.b). Tensors A, A [⋆], B and B [⋆] are not part of the environment.


variant under shifts by one lattice site, we need to understand
how to efficienlty contract an infinite environment E [[][⃗r][1][,⃗r][2][]] .
Translational invariance allows us to represent the state |Ψ⟩
in terms of only two tensors A and B that are repeated indefinitely in P (Fig. 1),


A [[(][x,x][+2][y][)]] = A, A [[(][x,x][+2][y][+1)]] = B, x, y ∈ Z, (3)


so that the iPEPS depends on just O(D [4] d) coefficients. Notice that E [[][⃗r][1][,⃗r][2][]] is also made of infinitely many copies of just
two reduced tensors a and b, defined in terms of A and B according to Eq. (2). Then its contraction is achieved in two
steps, as illustrated in Fig. (2): first we approximate E [[][⃗r][1][,⃗r][2][]]

with an infinite strip F [[][⃗r][1][,⃗r][2][]] ; then we approximate F [[][⃗r][1][,⃗r][2][]]

with a small set of tensors G [[][⃗r][1][,⃗r][2][]] = {G1, · · ·, G6}. This can
be achieved using a _vertical/horizontal_ scheme or a _diagonal_
scheme as illustrated in Figs. 2-3.
The first step considers a transfer matrix R consisting of an
infinite strip of reduced tensors a and b (Fig. 3). R can be
regarded as a linear operator acting on an infinite chain where
each site is described by a vector space of dimension D [2] . Let
|Φ⟩ denote the _dominant_ eigenvector of R—that is, the eigenvector of R, R|Φ⟩ = λ|Φ⟩, with the eigenvalue λ of largest
absolute value. Here we assume that the dominant eigenvector is unique [11]. By construction R is invariant under shifts
by two sites of the infinite chain – and so is |Φ⟩. We use
an iMPS, characterized by just two tensors {C, D} and with
Schmidt rank χ, to represent an approximation of |Φ⟩. We
obtain this iMPS by simulating (repeated) multiplication by
R on an initial state |Φ0⟩ with the iTEBD algorithm [9] and



![](.figures/arxiv__cond-mat-0703788/cond-mat-0703788.pdf-1-1.png)
3


Figure 4: Transverse magnetization mx and energy per site e as a
function of the transverse magnetic field h. The continuous line
shows series expansion results (to 26th and 16th order in perturbation theory) for h smaller and larger than hc ≈ 3.044 [14]. Increasing D leads to a lower energy per site e. For instance, at h = 3.1,
e(D = 2) ≈−1.6417 and e(D = 3) ≈−1.6423.



![](.figures/arxiv__cond-mat-0703788/cond-mat-0703788.pdf-2-1.png)

Figure 3: Transfer matrices R (i.a) and S (i.b) for the vertical/horizontal contraction scheme. Multiplication of an iMPS by R
using the iTEBD algorithm comes at a computational time that scales
as O(χ [3] D [6] +χ [2] D [8] d) (similar costs apply to multiplying by S). This
cost is lower in diagonal contraction scheme (ii.a) and (ii.b), namely
O(χ [3] D [4] + χ [2] D [6] d), but a slightly larger χ is required in order to
retain the same accuracy.


by using the fact that


R [p] |Φ0⟩
|Φ⟩ = lim (4)
p→∞ ||R [p] |Φ0⟩|| [.]


The iMPS for |Φ⟩ accounts for an infinite half plane of the
environment E [[][⃗r][1][,⃗r][2][]] . Similarly, we use another iMPS with
tensors {C [′], D [′] } to encode the left dominant eigenvector ⟨Φ [′] |
of R, ⟨Φ [′] |R = λ⟨Φ [′] |, which also accounts for an infinite half
plane. Then F [[][⃗r][1][,⃗r][2][]] is built from these two iMPS and a strip
of reduced tensors a and b.
In the second step, a transfer matrix S is defined in terms of
the tensors {a, b, C, D, C [′], D [′] } (Fig. 3). S can be regarded as
a linear operator acting on three sites with local vector space
dimensions χ, D [2] and χ. Again, its dominant eigenvector
|Ω⟩, encoded in a three-legged tensor X, is computed from an
initial state |Ω0⟩ using the fact that


S [q] |Ω0⟩
|Ω⟩ = lim (5)
q→∞ ||S [q] |Ω0⟩|| [.]


Let X [′] be the tensor for the left dominant eigenvector ⟨Ω [′] |
of S. Then G [[][⃗r][1][⃗r][2][]] is a (circular) MPS consisting of the six
tensors {C, D, C [′], D [′], X, X [′] }.
**Simulation of time evolution.—** We decompose the
Hamiltonian as H = Hr + Hd + Hl + Hu, where the operator
Hr = [�] (⃗r1,⃗r2)r [h][[][⃗r][1][⃗r][2][]][ collects all interactions along][ r][-links]

(and similarly for d-, l- and u-links), and consider a SuzukiTrotter expansion of the time-evolution operator e [−][iHt] of
Eq. (1) in terms of operators e [−][iH][r] [δt], e [−][iH][d][δt], e [−][iH][l][δt] and



![](.figures/arxiv__cond-mat-0703788/cond-mat-0703788.pdf-2-0.png)


- 
σz [[][⃗r][]][σ] z [[][⃗r] `[′]` []]   - λ
(⃗r,⃗r `[′]` ) ⃗r



e [−][iH][u][δt], where δt is some small time step. Each of these operators further decomposes into a product of identical two-site
unitary gates g ≡ e [−][ihδt] acting on all pairs of sites connected
by a link of the proper type. For instance, for links of type r
we have




  e [−][iH][r] [δt] =



g [[][⃗r⃗r] `[′]` []] . (6)

(⃗r,⃗r `[′]` )r



Without loss of generality, we need to address only the update of tensors A and B after applying e [−][iH][r] [δt] to |Ψ⟩. Let
us assume that the gate g is applied on just _one_ of the r-links.
In that case, in order to update the iPEPS we would (i) compute the environment for that specific r-link following Figs.
2-3, and (ii) determine the optimal new tensors A [′] and B [′] for
the link, using the optimization techniques of [7] (sweeping
over just the two sites involved). We notice, however, that the
above A [′] and B [′] already define an iPEPS for e [−][iH][r] [δ] |Ψ⟩ that is, with gates g acting on _all_ r-links. Indeed, this follows
from translation invariance and the fact that a _unitary_ gate g
on a given r-link does not affect the environment on any other
r-link. In other words, the update of tensors A and B on each
r-link is identical and need only be performed once.
The above argumentation fails for an evolution e [−][Hτ] in
imaginary time, since the gate g [′] ≡ e [−][hδτ] is no longer unitary. In this case, a gate applied on, say, an r-link modifies the
environment on the rest of r-links. Nevertheless, as in onedimensional systems [9], the same algorithm can still be used
to find the ground state of the system through imaginary-time
evolution, provided that a sufficiently small δτ (leading to almost unperturbed environments) is used at the last stages of
the simulation.
**Quantum phase transition.—** To demonstrate the performance of the iPEPS algorithm, we have simulated an evolution in imaginary time to obtain the ground state |Ψλ⟩ of the
quantum Ising model with transverse magnetic field,




  H(λ) ≡−



σx [[][⃗r][]][.] (7)
⃗r


![](.figures/arxiv__cond-mat-0703788/cond-mat-0703788.pdf-3-0.png)

Figure 5: (color online) Magnetization mz(λ) as a function of the
transverse magnetic field λ. Dashed lines are a guide tp the eye.
We have used the diagonal scheme for (D, χ) = (2, 20), (3, 25)
and (4, 35) [12] (the vertical/horizontal scheme leads to comparable
results with slightly smaller χ.) The inset shows a log plot of mz
versus |λ − λc|, including our estimate of λc and β. The continuous
line shows the linear fit.


Figure 6: (color online) Two-point correlator Szz(l) near the critical
point, λ = 3.05. For nearest neighbors, the correlator quickly converges as a function of D, whereas for long distances we expect to
see convergence for larger values of D.


[1] D.M. Ceperley and B.J. Alder, Phys. Rev. Lett. 45, 566 (1980).

[2] S. R. White, Phys. Rev. Lett. 69, 2863 (1992).

[3] J. Oitma, C. Hamer, W. Zheng, _Series expansion methods_
_for strongly interacting lattice models_, Cambridge University
Press, 2006.

[4] M. Fannes, B. Nachtergaele, R. Werner, Commun. Math. Phys.
144, 443 (1992). S. Ö stlund and S. Rommer, Phys. Rev. Lett.
75, 3537 (1995).

[5] G. Vidal, Phys. Rev. Lett. 91, 147902 (2003); _ibid._ 93, 040502
(2004).

[6] N. Maeshima, Y. Hieida, Y. Akutsu, T. Nishino, K. Okunishi,
Phys. Rev. E64 (2001) 016705. Y. Nishio, N. Maeshima, A.
Gendiar, T. Nishino, cond-mat/0401115.

[7] F. Verstraete, J. I. Cirac, cond-mat/0407066. V. Murg, F. Verstraete, J. I. Cirac, Phys. Rev. A 75, 033605 (2007)

[8] G. Vidal, Phys. Rev. Lett. 99, 220405 (2007); G. Vidal,
arXiv:quant-ph/0610099; M. Aguado and G. Vidal, Phys. Rev.
Lett. 100, 070404 (2008).



4


Then we have computed the energy per site e and the transverse and parallel magnetizations mx and mz (Figs. 4-5),


mx(λ) = ⟨Ψλ|σx|Ψλ⟩, mz(λ) = ⟨Ψλ|σz|Ψλ⟩, (8)


and the two point correlator Szz(l) (Fig. 6)


Szz(l) ≡⟨Ψλ|σz [[][⃗r][]][σ] z [[][⃗r][+][l][e][ˆ][x][]] |Ψλ⟩− (mz) [2] . (9)


Comparison with series expansion results of Ref. [14]
shows remarkable agreement for all local observables on both
sides of the critical point, which Monte Carlo calculations [13]


QMC Ref. [13] D=2 iPEPS D=3 iPEPS D=3 VDMA Ref. [6]

λc 3.044 3.10 3.06 3.2
β 0.327 0.346 0.332  

Table I: Critical point and exponent β as a function of D.

indicate to be at magnetic field λMC ≈ 3.044. We also obtain
accurate estimates of the critical magnetic field λc and critical
exponent β, which for D = 2 and D = 3 agree with Monte
Carlo results within 5.8% and 1.5% respectively.
In conclusion, we have presented an algorithm to simulate
infinite two-dimensional lattice systems. We have tested its
performance in the context of the quantum Ising model, where
our results can compete quantitatively with those obtained using long-established methods, such as quantum Monte Carlo

[1] or perturbative series expansions [3]. The iPEPS algorithm
can now be applied to address problems beyond the reach of
quantum Monte Carlo (since it has no _sign problem_ ) and series expansion methods (since it does not rely on an expansion
around an exactly solvable model). Thus we expect it to become a useful new tool in the study of strongly interacting
lattice models.
Support from the Australian Research Council (APA,
DP0878830 and FF0668731) is acknowledged.


[9] G. Vidal, Phys. Rev. Lett. 98, 070201 (2007). R. Orús, G. Vidal,
arXiv:0711.3960.

[10] M. Suzuki, Phys. Lett. A 146, 6 (1990) 319-323; J. Math Phys.
32, 2 (1991) 400-407. For third and forth order expansions see
also A. T. Sornborger and E. D. Stewart, quant-ph/9809009.

[11] We find that the dominant eigenvector is unique both at the disordered and ordered phases of the quantum Ising model. In the
ordered phase, spontaneous symmetry breaking seems to be directly responsible for this uniqueness.

[12] Given a value of the bond dimension D, we choose χ large
enough so that the results do no longer depend significantly on
χ.

[13] H. W. J. Blote and Y. Deng, Phys. Rev. E 66, 066110 (2002).

[14] H.-X. He, C. J. Hammer and J. Oitmaa, J. Phys. A: Math. Gen.
**23** (1990) 1775-1787. J. Oitmaa, C. J. Hamer and W. H. Zheng,
J. Phys. A: Math. Gen. **24** (1991) 2863-2867.



![](.figures/arxiv__cond-mat-0703788/cond-mat-0703788.pdf-3-1.png)
