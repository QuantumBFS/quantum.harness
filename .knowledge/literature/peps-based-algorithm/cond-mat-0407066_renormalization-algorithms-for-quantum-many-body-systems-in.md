---
source: "https://arxiv.org/abs/cond-mat/0407066"
type: "arxiv"
canonical_id: "cond-mat/0407066"
title: "Renormalization algorithms for Quantum-Many Body Systems in two and higher dimensions"
authors: "Verstraete, F., Cirac, J. I."
year: "2004"
venue: "arXiv: Strongly Correlated Electrons"
arxiv_id: "cond-mat/0407066"
full_text: yes
---

# Renormalization algorithms for Quantum-Many Body Systems in two and higher dimensions

**Authors:** Verstraete, F., Cirac, J. I.

**Citation:** arXiv: Strongly Correlated Electrons, 2004

**arXiv:** [cond-mat/0407066](https://arxiv.org/abs/cond-mat/0407066)

## Abstract

We describe quantum many--body systems in terms of projected entangled--pair states, which naturally extend matrix product states to two and more dimensions. We present an algorithm to determine correlation functions in an efficient way. We use this result to build powerful numerical simulation techniques to describe the ground state, finite temperature, and evolution of spin systems in two and higher dimensions.

## Full Text

Renormalization algorithms for Quantum-Many Body Systems in two and higher
dimensions


F. Verstraete and J. I. Cirac
Max-Planck-Institut f¨ur Quantenoptik, Hans-Kopfermann-Str. 1, Garching, D-85748, Germany.
(Dated: October 22, 2018)


We describe quantum many–body systems in terms of projected entangled–pair states, which
naturally extend matrix product states to two and more dimensions. We present an algorithm to
determine correlation functions in an efficient way. We use this result to build powerful numerical
simulation techniques to describe the ground state, finite temperature, and evolution of spin systems
in two and higher dimensions.



PACS numbers: PACS


The theoretical investigation of strongly correlated systems is one the most challenging tasks in several fields of
Physics. Even though several analytical techniques and
numerical methods have been developed during the last
decades, there still exist a rich variety of systems which
remain untractable. Even some of the simplest systems,
which deal with spins in lattices with short range interactions, are very hard to simulate numerically. The development of powerful numerical techniques would allow us
to discover a rich variety of intriguing phenomena and to
confirm some of the predictions which have been made.
In the case of 1D systems, much analytical insight has
been gained by finding exact expressions for the ground
and/or excited eigenstates of some particular Hamiltonians, as it is the case for the 1D–AKLT states [1]. On
the other hand, a very powerful numerical simulation
method known as DMRG [2] has allowed us to determine physical properties of generic spin chains to an unprecedented accuracy. Recent work has also shown how
DMRG can be adapted to simulate the spin dynamics at
zero-temperature [3] or at finite temperature and in the
presence of dissipation [4, 5]. The success of the DMRG
method and its extensions relies on the existence of the
so-called matrix product states (MPS) [6], which generalize the 1D–AKLT states. The DMRG method can be
understood as a variational method within these MPS

[7, 8, 9], and part of its success relays on the fact that
correlation functions can be efficiently calculated.
In two or higher dimensions, however, almost no models have been solved exactly. A generalization of DMRG
to higher dimensions is hard to scale, as the MPS–ansatz
explicitly assumes a 1D configuration. The Monte Carlo
method [10], on the other hand, is very useful to describe certain systems, but for models with frustration
is, unlike DMRG, plagued by the so-called sign problem.
The physics of 2D spin systems is therefore not very well
understood as compared to 1D systems; this is very unfortunate as a good understanding would shed new light
on many open questions in condensed matter, such as
high-Tc superconductivity.
In this paper, we present a natural generalization of the
1D MPS to two and higher dimensions and build simu


where the matrices A [s] k have elements (A [s] k [)][l,r] =
⟨s|Qk|l, r⟩. Note that the indices l and r of each matrix
A [s] k [are related to the left and right bonds of the auxil-]
iary systems with their neighbors, whereas the index s
denotes the state of the physical system. The function
F1 is just the trace of the product of the matrices, i.e. it



lation techniques based on those states which effectively
extend DMRG to higher dimensions. We call those states
projected entangled–pair states (PEPS), since they can
be understood in terms of pairs of maximally entangled
states of some auxiliary systems, and that are projected
in some low–dimensional subspaces locally. This class
of states includes the generalizations of the 2D AKLTstates known as tensor product states [11] which have
been used for 2D problems (see also [12, 13, 14]) but is
much broader since every state can be represented as a
PEPS (as long as the dimension of the entangled pairs is
large enough). We also develop an efficient algorithm to
calculate correlation functions of these PEPS, and which
allows us to extend the 1D algorithms [2, 3, 4, 5] to higher
dimensions. This leads to many interesting applications,
such as scalable variational methods for finding ground
or thermal states of spin systems in higher dimensions as
well as to simulate their time-evolution. For the sake of
simplicity, we will present our results for a square lattice
in 2D, but they are easily generalized to higher dimensions and other geometries.
Let us start by recalling the representation introduced
in [9] of the state Ψ of N d–dimensional systems in terms
of MPS. For that, we substitute each physical system k by
two auxiliary systems ak and bk of dimension D (except
at the extremes of the chain). Systems bk and ak+1 are
in a maximally entangled state |φ⟩ = [�][D] n=1 [|][n, n][⟩][, which]
is represented in Fig. 1(a) by a solid line (bond) joining them. The state Ψ is obtained by applying a linear
operator Qk to each pair ak, bk that maps the auxiliary
systems onto the physical systems, i.e.


|Ψ⟩ = Q1 ⊗ Q2 ⊗ . . . QN |φ⟩ . . . |φ⟩



=



�d

F1(A [s] 1 [1] [, . . ., A] N [s][N] [)][|][s][1][, . . ., s][N] [⟩][,] (1)
s1,...,sN =1


#### (a)
#### (b) (c)

![](.figures/arxiv__cond-mat-0407066/cond-mat-0407066.pdf-1-2.png)

1 2 3 4 5



2


tangled state φ with one of its neighbor, as shown in the
figure. The state Ψ is obtained by applying to each site
one operator Qh,v that maps the auxiliary systems onto
the physical systems:







�d

F2({A [s] h,v [h,v] [}][)][|][s][1][,][1][, . . ., s][N] h [,N][v] [⟩][.][ (2)]
s1,1,...,sNh,Nv =1







|Ψ⟩ =









![](.figures/arxiv__cond-mat-0407066/cond-mat-0407066.pdf-1-1.png)

FIG. 1: Graphical representation of MPS in 1 dimension (a),
in 2 dimensions (b), and of PEPS (c). The bonds represent
pairs of maximally entangled D–dimensional auxiliary spins
and the circles denote projectors that map the inner auxiliary
spins to the physical ones.


contracts the indices l, r of the matrices A according to
the bonds.
As shown in [9], every state can be represented in the
form (1) as long as the dimension D can be chosen sufficiently large. Note, however, that the above picture of
the state is basically one dimensional, since each auxiliary system is entangled only to one nearest neighbor.
Thus, these states appear to be better suited to describe
1D systems, with short range interactions, since a small
local dimension D may give a good approximation to the
real state of the whole system. Note also that, as it is
clear from the above representation, any block of systems
is only entangled to the rest by at most two maximally
entangled state of the auxiliary particles and thus its entropy is bounded by 2 log2 D, independent of the block
size. This has been identified as the main reason why
DMRG does not describe well critical systems, where the
entropy grows with the logarithm of the block size [15].
States in the form (1) have also been used to represent
2D systems [16]. For simplicity let us thus consider a
2D square lattice of N := Nh × Nv systems. The idea
there is to numerate them in such a way that they can
be regarded as a long 1D system [Fig. 1(b)]. In general,
this method cannot be extended to larger systems since
nearest neighbor interactions in the original 2D system
(for example between 11 and 20) give rise to long interactions in the effective 1D description. Moreover, the
entropy of some blocks does not scale as the area of the
block, as it is expected for 2D configurations. For example, the block formed by systems from 6–15 has at most
a constant entropy of 2 log2 D.
For 2D systems we propose to use the description based
on Fig. 1(c). Each physical system of coordinates (h, v)
is represented by four auxiliary systems ah,v, bh,v, ch,v,
and dh,v of dimension D (except at the borders of the
lattices). Each of those systems is in a maximally en


Here, the A’s are four index tensors with elements
(A [s] h,v [)][u,d,l,r][ =][ ⟨][s][|][Q][h,v][|][u, d, l, r][⟩][. As in the 1D case, we]
associate each index of such tensors to each direction (up,
down, left, and right). Thus, the position with coordinates (h, v) is represented by a tensor (A [s] h,v [)][u,d,l,r][ whose]
index s is represents the physical system, and the other
four indices are associated with the bonds between the
auxiliary systems and the neighboring ones. The function F2 contracts all these indices u, d, l, r of all tensors
A according to those bonds. Note that we can generalize this construction to any lattice shape and dimension,
and that using the construction of [9] one can show that
any state can be written as a PEPS. In this way, we also
resolve the problem of the entropy of blocks mentioned
above, since now this entropy is proportional to the bonds
that connect such block with the rest, and therefore to
the area of the block. Note also that, in analogy to the
MPS [6], the PEPS are guaranteed to be ground states
of local Hamiltonians.
We show now how to determine expectation values of
operators in the state Ψ (2). We consider a general operator O = [�] h,c [O][h,c][ and define the four–indices tensor]



Here we have used the short–hand notation Eh,c :=
EOh,c, and the fact that the tensors in the first and last
rows have at most three indices [see Fig. 1c]. Thus, the
horizontal indices (l, r) of the tensors play the role of the
indices of each matrix, whereas the vertical ones (d) plays



(EOh,c )u,˜ ˜d,˜l,r˜ :=



�d

⟨s|Oh,c|s [′] ⟩(A [s] )u,d,l,r(A [s][′] ) [∗] u [′],d [′],l [′],r [′][(3)]
s,s [′] =1



where the indices are combined in pairs, i.e., ˜u =
(u, u [′] ), d [˜] = (d, d [′] ), [˜] l = (l, l [′] ), and ˜r = (r, r [′] ). One can
easily show that ⟨Ψ|O|Ψ⟩ = F2(EOh,c ). Thus, the evaluation of expectation values consists of contracting indices
of the tensors E. In order to show how to do this in practice, we notice that the tensors associated to the first and
last rows, once contracted, can be reexpressed in terms
of a MPS. In particular, we define [compare (1)]



|U1⟩ :=


⟨UNv | :=



�D [2]

F1(E1 [d], [1] 1 [. . . E] 1 [d],N [N] [)][|][d][1][ . . . d][N] [⟩][,][ (4a)]
d1...dN =1

�D [2]

F1(EN, [u][1] 1 [. . . E] N,N [u][N] [)][⟨][u][1][ . . . u][N] [|][.][(4b)]
u1...uN =1


the role of the indices corresponding to the physical systems in 1D. Analogously, the rows 2, 3, . . ., Nv − 1 can be
considered as matrix product operators (MPO) [5],



Uk :=



�D [2]

F(E1 [d], [1] 1 [,u][, . . ., E][1] 1 [d],N [N] [,u][N] )|d1 . . . dN ⟩⟨u1 . . . uN |.
d1,u1...=1



We have ⟨Ψ|O|Ψ⟩ = ⟨UN |UN −1 . . . U2|U1⟩.
The evaluation of expectation values poses a serious
problem since the number of indices proliferate after each
contraction. For example, the vector |U2⟩ := U2|U1⟩ can
be written as the MPS (4a) but with the substitution



3


can be adapted to develop very efficient algorithms to
determine the ground states of 2D Hamiltonians and the
time evolution of PEPS by extending DMRG and the
time evolution schemes to 2D.
Let us start with an algorithm to determine the ground
state of a Hamiltonian with short range interactions on
a square Nh × Nv lattice. The goal is to determine the
PEPS (2) with a given dimension D which minimizes the
energy. Following [9], the idea is to iteratively optimize
the tensors A [s] h,c [one by one while fixing all the other ones.]
The crucial observation is the fact that the exact energy
of |ψ⟩ (and also its normalization) is a quadratic function
of the components of the tensor A [s] h,¯ c¯ [to be optimized,]
which we write as a vector x; hence the energy can be
expressed in terms of an effective Hamiltonian:

E = [x][†][ ˆ][H][eff] [x] (6)

x [†][ ˆ] Nx

The denominator takes the normalization of the state
into account. This expression can readily be minimized
as it is equivalent to a generalized eigenvalue problem.
It turns out that H [ˆ] eff and N [ˆ] can be efficiently evaluated by the methods described above. In the case of N [ˆ],
the MPS |U1⟩ (4a) constructed from E11h,1 can be propagated up to the row ¯v − 1 with the technique outlined
before. Similarly, the last row ⟨UNv | (4b) can be propagated up to row ¯v + 1. The tensors E11hv¯ can now be
contracted with these two MPS from h = 1..h [¯] - 1, and
similarly from h = Nh..h [¯] + 1. The remaining tensor has
4 (double) indices from which one can readily determine
Nˆ . Hˆeff can be determined in an analogous way, but
here the procedure has to be repeated for every term in
the Hamiltonian (i.e. in the order of 2NhNv times in the
case of nearest neighbor interactions). Thus both N [ˆ] and
Hˆeff can be calculated efficiently. Therefore the optimal
A [s] h¯v¯ [can be determined, and one can proceed with the]
following projector, iterating the procedure until convergence.
In a practical implementation one can save much time
by storing appropriate tensors, implementing the algorithm in a parallel way, doing sparse tensor multiplications, and making use of quantum numbers and reflection symmetries. A more efficient variant can also be
constructed by an iterative procedure which resembles
the infinite-size DMRG-algorithm, where new rows are
inserted in the middle of the lattice.
Let us next move to describe how time-evolution can be
simulated on a PEPS. We will assume that the Hamiltonian only couples nearest neighbors, although more general settings can be considered. The simplest scheme
would work by optimally mapping a given PEPS to another PEPS after an infinitesimal time-step 11 − iHδt. It
can readily be checked that, up to first order of δt, the
action of this operator is to map a TPS with auxiliary
dimension D onto a new TPS with dimension of the auxiliary bonds nD; here n represents the minimal number



E1 [d],n [n] [→]



�D [2]

E1 [d],n [n] [⊗] [E] 2 [d],nn [′] [,d][n] . (5)
dn=1



This last tensor has more (right and left) indices than the
original one. Thus, every time we apply the MPO Uk to
a MPS |Uk−1⟩ the number of indices increases, and thus
the problem soon becomes intractable. Now we introduce
a numerical algorithm inspired by DMRG to numerically
determine F2(EOh,c ) and to overcome this problem.
Given an unnormalized MPS |ψA⟩ parameterized by
D × D matrices {A [s] k [}][, the goal is to find another MPS]
|ψB⟩, parameterized by Df × Df matrices {Bi [s][}][, where]
Df < D is a prescribed number. This has to be done
such that K := ∥|ψA⟩−|ψB⟩∥ [2] is minimal, i.e., such
that that |ψB⟩ gives the best approximation to |ψA⟩. We
have developed an algorithm that achieves this task in
an iterative way. The key insight is that K is quadratic
in all components of the matrices {Bk [s][}][, and hence if all]
these matrices are fixed except one of them (say Bj [s][)][ K]
is quadratic in the components of Bj [s][; the optimal choice]
for Bj [s] [thus amounts to solving a trivial system of linear]
equations. Having done that, one moves to the next site
j +1, fixes all other ones and repeats the same procedure.
After a few sweeps back and forth the optimal MPS is
found. Note that the error in the approximation is exactly known and if it becomes too large one can always
increase Df ; in all relevant situations we encountered the
error could be made very small even with moderate Df .
The same reasoning holds for MPS defined with periodic
instead of open boundary conditions. In this latter case
considered here, one can further simplify the system of
linear equations by performing a singular value decomposition of Bj [s] [and keeping only one of the unitary matrices]
at each step, analogously as one does in DMRG.
Thus, in order to evaluate an arbitrary expectation
value we first determine the MPS |U [˜] 2⟩ which is the closest to U2|U1⟩ but with a fixed dimensions Df of the corresponding matrices. Then, we determine |U [˜] 3⟩, which
is the closest to U3|U [˜] 2⟩, and continue in this vein until
we finally determine ⟨Ψ|O|Ψ⟩≃⟨UN |U [˜] N −1⟩. Interestingly enough, this method to calculate expectation values and to determine optimal approximations to MPS


4



of terms needed to express the couplings as tensor products of local operators plus 1 (e.g. n = 2 for the Ising
interaction and n = 4 for the Heisenberg interaction). In
analogy to the method introduced above for MPS, one
can approximate this new PEPS with another one having again bonds of auxiliary dimension D. The algorithm
to achieve this is a direct generalization of the method
introduced to reduce the D of MPS: again several sweeps
over all projectors have to be done, and the only difference is that at each step correlation functions of a PEPS
have to be calculated instead of correlations function of
a MPS. This can be done using the methods introduced
before. Of course there are again many possibilities to
boost the accuracy and to reduce the computational cost
of such an implementation, such as using the Trotter decomposition as in [3] and then using the sweeps to optimize the state. This algorithm can also be used to solve
finite temperature or dissipation problems by extending
the ideas of [4] and [5].
Let us now illustrate our methods with an example.
We consider a 2D lattice of spin 1/2-particles where nearest neighbors interact via the antiferromagnetic Heisenberg interaction with coupling constant J = 1. We use
the time–evolution algorithm for evolving the PEPS in
imaginary time; in this way we illustrate both the fact
that the new formalism allows us to find ground states as
well as to describe time-evolution. We implemented the
algorithm as follows: we start with a completely separable state |ψ0⟩ in which the spins are rotated by an angle
π/16 with respect to the previous one, and which can
trivially be written as a PEPS. Using the Trotter decomposition, we divide each time step into 4 parts in which
each spin is only interacting with one neighbor; as we
are considering the Heisenberg interaction, the dimension D between the 2 interacting spins gets multiplied
by a factor of 4. Let us parameterize this new PEPS
with the corresponding tensors Bh,v [s] [. After each of these]
substeps, we want to reduce the dimension again to the
original one giving rise to the PEPS Ch,v [s] [that optimally]
approximates the exact Bh,v [s] [. This is done in an iterative]
way, row by row, until convergence. Fixing all rows but
one, the problem of finding the optimal projectors in this
row is equivalent to the problem of approximating a MPS
with another one with lower dimension (the physical dimension of the MPS is the product of the bonds going up
and down), which can on itself done in an iterative way
as outlined above. Note that the computational cost of
the algorithm is polynomial in N and D.
We have first considered a 4 × 4 lattice on which the
imaginary time evolution can be determined exactly. In
Fig. 2, we plotted the exact evolution versus the one
where the evolution is approximated variationally within
the PEPS with bonds of dimension D = 2, 3 (D = 4 cannot be distinguished from the exact result). We used the
same Trotter approximation for the exact and variational
simulations with δt = −3i/100. It is remarkable that



2


1



![](.figures/arxiv__cond-mat-0407066/cond-mat-0407066.pdf-3-0.png)






# � 0



0







-1


-2





0 25 50
# �


FIG. 2: Imaginary time evolution with the Heisenberg and
a frustrated Heisenberg interaction on a 4 × 4 lattice, and
D = 2, Df = 16 (dotted) and D = 3, Df = 35 (dashed);
the D = 3 results are almost indistinguishable from the exact
ones (full line). The insert presents the evolution for D = 2
on a 10 × 10 lattice.


even for D = 3 we obtain a very good approximations,
both regarding time evolution and ground state energy.
The algorithm clearly converges to the ground state, and
the difference between the exact ground state energy and
the one obtained with our scalable algorithm rapidly decreases with D[17]; more specifically, 1 − Evar/Eexact is
given by .35, .02; .004; 0.0008 for D = 1, 2; 3; 4 (note that
the trivial situation D = 1 corresponds to the N´eel state).
We also repeated the same simulation but with a frustrated Heisenberg Hamiltonian, obtained by making 1
out of every 4 interactions on each spin ferromagnetic instead of antiferromagnetic. Again very good agreement
with the exact results is obtained; note that the energy
converges more slowly due to the fact that the energy gap
is smaller. The insert of Fig. (2) presents some simulation results for the imaginary time evolution for a square
10 × 10 lattice for both the Heisenberg antiferromagnet
and the frustrated case. The convergence is again very
fast, and increasing D from 2 to 3 (not shown in the
plot) allows us to find a better value for the energy of
the ground state. Note that we can easily handle larger
systems and, using the appropriate numerical techniques,
eventually increase the value of D.
In conclusion, we have introduced the class of PEPS
and showed how they arise naturally in the context of
constructing variational ground states for spin Hamiltonians on higher dimensional lattices. We presented an
efficient algorithm for calculating correlation functions,
which leads to scalable variational methods for finding
ground states and for describing their real or imaginary
time evolution. Interestingly, the methods described also


apply in the case of different geometries, of evolution in
the presence of dissipation, and for finding finite-T states.
It is also possible to identify quite generic classes of PEPS
for which 2-point correlation functions can be calculated
analytically [18]. We also note that the concept of PEPS
could be very useful for the description of 2-dimensional
transport problems, as the PEPS generalize the matrix
product states which proved to be very useful in the 1-D
case [19].
We thank M. A. Martin-Delgado for his insights on
DMRG and MPS. Work supported by the DFG (SFB
631), european projects (IST and RTN), and the Kompetenznetzwerk der Bayerischen Staatsregierung Quanteninformation.


[1] I. Affleck et al., Commun. Math. Phys. 115, 477 (1988).

[2] S.R. White, Phys. Rev. Lett. 69, 2863 (1992).

[3] G. Vidal, Phys. Rev. Lett. 91, 147902 (2003); A. Daley et
al., J.Stat.Mech.: Theor.Exp. P04005 (2004); S.R. White
[and A.E. Feiguin, cond-mat/0403310.](http://arxiv.org/abs/cond-mat/0403310)

[[4] M. Zwolak and G. Vidal, cond-mat/0406440.](http://arxiv.org/abs/cond-mat/0406440)

[5] F. Verstraete, J.J. Garcia-Ripoll and J. I. Cirac,
[cond-mat/0406426.](http://arxiv.org/abs/cond-mat/0406426)

[6] M. Fannes, B. Nachtergaele and R.F. Werner, Comm.



5


Math. Phys. 144, 443 (1992).

[7] S. Ostlund and S. Rommer, Phys. Rev. Lett. 75, 3537
(1995).

[8] J. Dukelsky et al., Europhys. Lett. 43, 457 (1997).

[9] F. Verstraete, D. Porras and J.I. Cirac,
[cond-mat/0404706.](http://arxiv.org/abs/cond-mat/0404706)

[10] D.M. Ceperley and B.J. Alder, Phys. Rev. Lett. 45, 566
(1980).

[11] Y. Hieida, K. Okunishi and Y. Akutsu, New J. Phys. 1,
7 (1999); K. Okunishi and T. Nishino, Prog. Teor. Phys.
103, 541 (2000); T. Nishino et al., Nucl. Phys. B 575,
[504 (2000); Y. Nishio et al., cond-mat/0401115.](http://arxiv.org/abs/cond-mat/0401115)

[12] H. Niggeman, A. Kl¨umper and J. Zittartz, Z. Phys. B
104, 103 (1997).

[13] M.A. Mart [´] in-Delgado, M. Roncaglia and G. Sierra, Phys.
Rev. B 64, 075117 (2001).

[[14] F. Verstraete and J.I. Cirac, quant-ph/0311130.](http://arxiv.org/abs/quant-ph/0311130)

[15] G. Vidal et al., Phys.Rev.Lett. 90, 227902 (2003).

[16] S. Liang and H. Pang, Phys. Rev. B 49, 9214 (1994);
S.R. White, Phys. Rev. Lett. 77, 3633 (1996); T. Xiang,
J. Lou, and Z. Su, Phys. Rev. B 64, 104414 (2001).

[17] The number of variational parameters scales as D [4],
whereas for 1D MPS it does as D [2] . Thus, modest values
of D already allow us to approximate the local 2-body
density operators (and hence the energy) to a good accuracy.

[18] In Preparation

[19] B. Derrida et al., J. Phys. A: Math. Gen. 26, 1493 (1993).
