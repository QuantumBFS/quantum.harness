---
source: "https://www.cond-mat.de/events/correl19/manuscripts/zhang.pdf"
type: "web"
canonical_id: "zhang_2019_auxiliary-field-quantum-monte-carlo"
title: "Auxiliary-Field Quantum Monte Carlo at Zero- and Finite-Temperature"
authors: "Shiwei Zhang"
year: "2019"
venue: "Many-Body Methods for Real Materials (Modeling and Simulation Vol. 9), Forschungszentrum Julich"
full_text: yes
note: "Lecture notes Ch. 6; ISBN 978-3-95806-400-3"
---

## **6 Auxiliary-Field Quantum Monte Carlo** **at Zero- and Finite-Temperature**
### Shiwei Zhang Center for Computational Quantum Physics Flatiron Institute, New York, NY10010, USA Department of Physics, College of William & Mary Williamsburg, VA23185, USA **Contents**

**1** **Introduction** **2**

**2** **Formalism** **3**

2.1 Hubbard-Stratonovich transformation . . . . . . . . . . . . . . . . . . . . . . 4

2.2 Ground-state projection . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 6

2.3 Finite-temperature, grand-canonical ensemble calculations . . . . . . . . . . . 9

**3** **Constraining the paths in AFQMC** **11**

3.1 An exact boundary condition . . . . . . . . . . . . . . . . . . . . . . . . . . . 11

3.2 Implementing the boundary condition and importance sampling . . . . . . . . 12

3.3 The phaseless formalism for complex auxiliary-fields . . . . . . . . . . . . . . 15

**4** **Overview of applications, further reading, and outlook** **19**

**A A few basics of Monte Carlo techniques** **22**

**B** **Properties of non-orthogonal Slater determinants** **24**

E. Pavarini, E. Koch, and S. Zhang (eds.)
Many-Body Methods for Real Materials
Modeling and Simulation Vol. 9
Forschungszentrum J¨ulich, 2019, ISBN 978-3-95806-400-3
[http://www.cond-mat.de/events/correl19](http://www.cond-mat.de/events/correl19)


-----

6.2 Shiwei Zhan g
### **1 Introduction**

Auxiliary-field quantum Monte Carlo (AFQMC) is increasingly becoming a general and pow
erful tool for studying interacting many-fermion systems, in different sub-areas including the

study of correlated electron models, cold Fermi gas, electronic structure of solids, and quantum

chemistry. My lecture will give an introduction to the advances, both in the zero-temperature

or ground-state form and in the non-zero-temperature ( *T >* 0 K) form, which have allowed

AFQMC to become a systematic and scalable tool. The ground-state portion of the lecture will

draw (or even copy!) from Refs. [1] and [2]; the *T >* 0 K portion is based on Refs. [3] and [4].

As we have seen repeatedly echoed through this school, the accurate treatment of interacting

quantum systems is one of the grand challenges in modern science. Explicit solution of the

many-body Schr¨odinger equation leads to rapidly growing computational cost as a function of

system size (see, e.g., [5]). To circumvent the problem, most computational quantum mechani
cal studies of large, realistic systems rely on simpler independent-particle approaches based on

density-functional theory (DFT) (see, e.g., [6, 7]), using an approximate energy functional to

include many-body effects. These replace the electron-electron interaction by an effective po
tential, thereby reducing the problem to a set of one-electron equations. Methods based on DFT

and through its Car-Parrinello molecular dynamics implementation [8] have been extremely ef
fective in complex molecules and solids [6]. Such approaches are the standard in electronic

structure, widely applied in condensed matter, quantum chemistry, and materials science.

Despite the tremendous successes of DFT, the treatment of electronic correlation is approxi
mate. For strongly correlated systems (e.g., high-temperature superconductors, heavy-fermion

metals, magnetic materials, optical lattices), where correlation effects from particle interac
tion crucially modify materials properties, the approximation can lead to qualitatively incorrect

results. Even in moderately correlated systems when the method is qualitatively correct, the

results are sometimes not sufficiently accurate. For example, in ferroelectric materials the usu
ally acceptable 1% errors in DFT predictions of the equilibrium lattice constant can lead to

almost full suppression of the ferroelectric order. Additional challenges are present to go be
yond ground state and account for thermal as well as quantum fluctuations.

The development of alternatives to independent-particle theories is therefore of paramount fun
damental and practical significance. To accurately capture the quantum many-body effects,

the size of the Hilbert space involved often grows exponentially. Simulation methods utilizing

Monte Carlo (MC) sampling [9–14] are, in principle, both non-perturbative and well-equipped

to handle details and complexities in the external environment. They are a unique combination

of accuracy, general applicability, favorable scaling (low-power) of computational cost with

physical system size, and scalability on parallel computing platforms [15].

For fermion systems, however, a so-called sign problem [16–18] arises in varying forms in

these MC simulation methods. The Pauli exclusion principle requires that the states be anti
symmetric under interchange of two particles. As a consequence, negative signs appear, which

cause cancellations among contributions of the MC samples of the wave function or density

matrix. In some formalisms, as we discuss below, a phase appears which leads to a continuous


-----

AF Q MC 6.3

degeneracy and more severe cancellations. As the temperature is lowered or the system size

is increased, such cancellation becomes more and more complete. The net signal thus decays

*exponentially* versus noise. The algebraic scaling is then lost, and the method breaks down.

In AFQMC, we cast the MC random walks in a space of over-complete Slater determinants,

which significantly reduces the severity of the sign problem. In this space we study the prop
erties of the paths and derive exact boundary conditions for the sign of their contributions in

the ground-state wave function or *T >* 0 K density matrix. This then allows us to formulate

approximate constraints on the random walk paths which are less sensitive to the details of the

constraint. We then develop internal checks and constraint release methods to systematically

improve the approach. These methods have come under the name of constrained path Monte

Carlo (CPMC) [19] for systems where there is a sign problem (for example, Hubbard-like mod
els where the auxiliary-fields are real due to the short-ranged interactions). For electronic sys
tems where there is a phase problem (as the Coulomb interaction leads to complex auxiliary

fields), the methods have been referred to as phaseless or phase-free AFQMC [14,20,21]. We

will refer to the methods as AFQMC following more recent literature in *ab initio* electronic

structure. When it is necessary to emphasize the constrained-path (CP) approximation, to dis
tinguish from unconstrained zero-temperature (free-projection) or *T >* 0 K (sometimes referred

to as determinantal MC) calculations, we will refer to them as CP-AFQMC.
### **2 Formalism**

The Hamiltonian for any many-fermion system with two-body interactions (e.g., the electronic

Hamiltonian under the Born-Oppenheimer approximation) can be written as


*M*
� *V* ext ( **r** *m* ) +

*m* =1


*M*
� *V* int ( **r** *m* *−* **r** *n* ) *,* (1)

*m<n*


ˆ
*H* = ˆ *H* 1 + ˆ *H* 2 = *−* [ℏ] [2]

2 *m*


*M*
� *∇* [2] *m* [+]

*m* =1


where **r** *m* is the real-space coordinate of the *m* -th fermion. The one-body part of the Hamiltonian, *H* [ˆ] 1, consists of the kinetic energy of the electrons and the effect of the ionic (and any other

external) potentials. (We have represented the external potential as local, although this does not

have to be the case. For example, in plane-wave calculations we will use a norm-conserving

pseudopotential, which will lead to a non-local function *V* ext .) The two-body part of the Hamiltonian, *H* [ˆ] 2, contains the electron-electron interaction terms. The total number of fermions, *M*,

will be fixed in the ground-state calculations; for *T >* 0 K, a chemical potential term will be

included and the number of fermions will fluctuate. For simplicity, we have suppressed the

spin-index; when the spins need to be explicitly distinguished, *M* *σ* will denote the number of

electrons with spin *σ* ( *σ* = *↑* or *↓* ). We assume that the interaction is spin-independent, so the
total *S* *z*, defined by ( *M* *↑* *−* *M* *↓* ), is fixed in the ground-state calculation, although it will be
straightforward to generalize our discussions to treat other cases, for example, when there is

spin-orbit coupling (SOC) [22].


-----

6.4 Shiwei Zhan g

With any chosen one-particle basis, the Hamiltonian can be written in second quantization in

the general form


*N*
� *V* *ijkl* *c* *[†]* *i* *[c]* *[†]* *j* *[c]* *k* *[c]* *l* *[,]* (2)

*i,j,k,l*


ˆ
*H* = ˆ *H* 1 + ˆ *H* 2 =


*N*
� *T* *ij* *c* *[†]* *i* *[c]* *j* [+ 1] 2

*i,j*


where the one-particle basis, *{|χ* *i* *⟩}* with *i* = 1 *,* 2 *, . . ., N*, can be lattice sites (Hubbard model),

plane-waves (as in solid state calculations) [23], or Gaussians (as in quantum chemistry) [20,
24], etc. The operators *c* *[†]* *i* [and] *[ c]* *[i]* [ are creation and annihilation operators on] *[ |][χ]* *[i]* *[⟩]* [, satisfying]
standard fermion commutation relations. The one-body matrix elements, *T* *ij*, contain the effect
of both the kinetic energy and external potential. For the *T >* 0 K calculations we will discuss,

a term *µ* ˆ *n* containing the chemical potential *µ* and density operator is included [12,25,26]. The

two-body matrix elements, *V* *ijkl*, are from the interaction. The matrix elements are expressed in
terms of the basis functions, for example,

*V* *ijkl* = *d* **r** 1 *d* **r** 2 *χ* *[∗]* *i* [(] **[r]** [1] [)] *[χ]* *[∗]* *j* [(] **[r]** [2] [)] *[V]* [int] [(] **[r]** [1] *[−]* **[r]** [2] [)] *[χ]* *[k]* [(] **[r]** [2] [)] *[χ]* *[l]* [(] **[r]** [1] [)] *[ .]* (3)
�

In quantum chemistry calculations, these are readily evaluated with standard Gaussian basis

sets. In solid state calculations with plane-waves, the kinetic and electron-electron interaction

terms have simple analytic expressions, while the electron-ion potential leads to terms which

are provided by the pseudopotential generation. We will assume that all matrix elements in

Eq. (2) have been evaluated and are known as we begin our many-body calculations.
###### **2.1 Hubbard-Stratonovich transformation**

The two-body part in the Hamiltonian in Eq. (2), *H* [ˆ] 2, can be written in the following form


ˆ
*H* 2 = [1]

2


*N* *γ*

ˆ

� *λ* *γ* *v* *γ* [2] *[,]* (4)

*γ* =1


where *λ* *γ* is a constant, ˆ *v* *γ* is a one-body operator similar to *H* [ˆ] 1, and *N* *γ* is an integer. There are
various ways to achieve the decomposition in Eq. (4) for a general two-body term [27]. Below

we outline the two most commonly applied cases in electronic structure: ( **a** ) *with plane-wave*

*basis* and ( **b** ) for a more dense matrix *V* *ijkl* resulting from a *general basis set* such as Gaussians.
In a *plane-wave basis*, the two-body part is the Fourier transform of 1 */|* **r** *m* *−* **r** *n* *|* [23]


ˆ
*H* 2 *→* [1]

2 *Ω*


�

*i,j,k,l*


4 *π*
*|* **G** **i** *−* **G** **k** *|* [2] *[ c]* *i* *[†]* *[c]* *[†]* *j* *[c]* *l* *[c]* *k* *[δ]* **[G]** **i** *[−]* **[G]** **k** *[,]* **[G]** **l** *[−]* **[G]** **j** *[δ]* *[σ]* *i* *[,σ]* *k* *[δ]* *[σ]* *j* *[,σ]* *l* *[,]* (5)


where *{* **G** **i** *}* are planewave wave-vectors, *Ω* is the volume of the supercell, and *σ* denotes spin.
Let us use **Q** *≡* **G** **i** *−* **G** **k**, and define a density operator in momentum space

*ρ* ˆ( **Q** ) *≡* � *c* *[†]* **G** + **Q** *,σ* *[c]* **G** *,σ* *[,]* (6)

**G** *,σ*


-----

AF Q MC 6.5

where the sum is over all **G** vectors which allow both **G** and **G** + **Q** to fall within the pre
defined kinetic energy cutoff, *E* cut, in the planewave basis. The two-body term in Eq. (5) can

then be manipulated into the form


ˆ
*H* 2 *→*
�

**Q** = *̸* **0**


*π* � *ρ* ˆ *[†]* ( **Q** ) ˆ *ρ* ( **Q** ) + ˆ *ρ* ( **Q** ) ˆ *ρ* *[†]* ( **Q** )� *,* (7)
*ΩQ* [2]


where the sum is over all **Q** ’s except **Q** = 0, since in Eq. (5) the **G** **i** = **G** **k** term is excluded due

*−*
to charge neutrality, and we have invoked *ρ* *[†]* ( **Q** ) = *ρ* ( **Q** ). By making linear combinations of
�( *ρ* *[†]* ( **Q** ) + *ρ* ( **Q** )� and �( *ρ* *[†]* ( **Q** ) *−* *ρ* ( **Q** )� terms, we can then readily write the right-hand side in
Eq. (7) in the desired square form of Eq. (4) [23].

With a *general basis* (e.g., Gaussians basis as standard in chemistry), the most straightforward
way to decompose *H* [ˆ] 2 is through a direct diagonalization [20, 28, 2]. However, this is computationally costly. A modified Cholesky decomposition leads to *O* ( *N* ) fields [24, 21]. This

approach, which has been commonly used in AFQMC for molecular systems with Gaussian

basis sets and for downfolded Hamiltonians [29], realizes the following


*V* *ijkl* = *V* ( *i,l* ) *,* ( *j,k* ) = *V* *µν* = *[.]*


*N* *γ*
� *L* *[γ]* *µ* *[L]* *ν* *[γ]* *[,]* (8)

*γ* =1


where *µ* = ( *i, l* ) and *ν* = ( *j, k* ) are composite indices introduced for convenience. The process

is carried out recursively using a modified Cholesky algorithm [30,31]. Recently an alternative

with density-fitting has also been used [32]. The 4-index matrix elements can be represented
to a pre-defined accuracy tolerance *δ* (which for molecular calculations is typical of *δ* range
between 10 *[−]* [4] and 10 *[−]* [6] in atomic units [21]), such that


*L* *[γ]*
*ν* ( *j,k* ) *[c]* *j* *[†]* *[c]* *k*

��� *jk*


�


*L* *[γ]*
*µ* ( *i,l* ) *[c]* *i* *[†]* *[c]* *l*

�� *il*


ˆ
*H* 2 *→* [1]

2


*N* CD
�

*γ* =1


+ *O* ( *δ* ) *.* (9)


Hence the form in Eq. (4) is realized, with ˆ *v* *γ* = [�] *il* *[L]* *[γ]* *µ* ( *i,l* ) *[c]* *i* *[†]* *[c]* *[l]* [. The process decomposing the]

two-body interaction is illustrated in Fig. 1.


*j*

### *i*
# *V*

*l*


*j*

*k*

### *i*


*l*



*k*


**Fig. 1:** *Schematic illustration of the decoupling of the two-body interaction, either via Cholesky*
*decomposition, the planewave factorization, or density fitting. The number of auxiliary index γ*
*(magenta wiggly line) controls the number of auxiliary fields.*


-----

6.6 Shiwei Zhan g

We can then apply the Hubbard-Stratonovich (HS) transformation to each term in Eq. (4)


*∞*

2 *[x]* [2]

*e* *[−]* *[∆τ]* 2 *λ* ˆ *v* [2] = *dx* *[e]* *[−]* [1] *√*

� *−∞* *√* 2 *π* *[e]* *[x]*


*−∆τλ* ˆ *v* *,* (10)


where *x* is an auxiliary-field variable. The key idea is that the quadratic form (in ˆ *v* ) on the left

is replaced by a linear one on the right. If we denote the collection of auxiliary fields by **x** and
combine one-body terms from *H* [ˆ] 1 and *H* [ˆ] 2, we obtain the following compact representation of

the outcome of the HS transformation

*e* *[−][∆τ]* [ ˆ] *[H]* = *d* **x** *p* ( **x** ) *B* [ˆ] ( **x** ) *,* (11)
�

where *p* ( **x** ) is a probability density function (PDF), for example, a multi-dimensional Gaussian.
The propagator *B* [ˆ] ( **x** ) in Eq. (11) has a special form, namely, a product of operators of the type

ˆ
*B* = exp *c* *[†]* *i* *[U]* *[ij]* *[c]* *j* *,* (12)
�� �

*ij*

with *U* *ij* depending on the auxiliary field. The matrix representation of *B* [ˆ] ( **x** ) will be denoted
by *B* ( **x** ). See Appendix B for more details.

Note that the constant in front of ˆ *v* in the exponent on the right-hand side of Eq. (10) can be
real or imaginary. So the matrix elements of *B* ( **x** ) can become complex, for example when *λ*

in Eq. (10) is positive, which occurs in both of the forms discussed above. Sometimes we

will refer to this situation as having complex auxiliary fields, but it should be understood that
this is interchangeable with *B* [ˆ] ( **x** ) being complex, and the relevant point is whether the Slater

determinant develops complex matrix elements which evolve stochastically.

In essence, the HS transformation replaces the two-body interaction by one-body interactions

with a set of random external auxiliary fields. In other words, it converts an interacting system

into many *non-interacting* systems living in fluctuating external auxiliary-fields. The sum over

all configurations of auxiliary fields recovers the interaction.

Different forms of the HS transformation can affect the performance of the AFQMC method.

For example, it is useful to subtract a mean-field “background” from the two-body term prior to

the decomposition [33,34,20]. The idea is that using the HS to decompose any constant shifts

in the two-body interaction will necessarily result in more statistical noise. In fact, it has been

shown [35, 21] that the mean-field background subtraction can not only impact the statistical

accuracy, but also lead to different quality of approximations under the CP methods that we

discuss in the next section.
###### **2.2 Ground-state projection**

Most ground-state quantum MC (QMC) methods are based on iterative projection

*|Ψ* 0 *⟩∝* lim (13)
*τ* *→∞* *[e]* *[−][τ]* [ ˆ] *[H]* *[|][Ψ]* *[T]* *[⟩]* [;]


-----

AF Q MC 6.7

that is, the ground state *|Ψ* 0 *⟩* of a many-body Hamiltonian *H* [ˆ] can be projected from any known
trial state *|Ψ* *T* *⟩* that satisfies *⟨Ψ* *T* *|Ψ* 0 *⟩̸* = 0. This can be achieved by numerical iteration

*|Ψ* [(] *[n]* [+1)] *⟩* = *e* *[−][∆τ]* [ ˆ] *[H]* *|Ψ* [(] *[n]* [)] *⟩,* (14)

where *|Ψ* [(0)] *⟩* = *|Ψ* *T* *⟩* . The ground-state expectation *⟨O* [ˆ] *⟩* of a physical observable *O* [ˆ] is given by

*⟨* *Ψ* [(] *[n]* [)] *|* *O* [ˆ] *|* *Ψ* [(] *[n]* [)] *⟩*
*⟨O* [ˆ] *⟩* = lim (15)
*n→∞* *⟨Ψ* [(] *[n]* [)] *|Ψ* [(] *[n]* [)] *⟩* *[.]*

For example, the ground-state energy can be obtained by letting *O* [ˆ] = *H* [ˆ] . A so-called mixed
estimator exists, however, which is exact for the energy (or any other *O* [ˆ] that commutes with *H* [ˆ] )

and can lead to considerable simplifications in practice

*⟨* *Ψ* *T* *|* *H* [ˆ] *|* *Ψ* [(] *[n]* [)] *⟩*
*E* 0 = lim (16)
*n→∞* *⟨Ψ* *T* *|Ψ* [(] *[n]* [)] *⟩* *[.]*

QMC methods carry out the iteration in Eq. (14) by Monte Carlo (MC) sampling. At the sim
plest conceptual level, one can understand the difference between different classes of QMC

methods as what space is used to represent the wave function or density matrix and to carry

out the integration. The AFQMC methods work in second quantized representation and in a

non-orthogonal space of Slater determinants. Ground-state AFQMC represents the many-body

wave function stochastically in the form


where *|φ⟩* is a Slater determinant


*|Ψ* [(] *[n]* [)] *⟩* = � *α* *φ* *|φ⟩* *,* (17)

*φ*

*|φ⟩≡* *ϕ* ˆ *[†]* 1 *[ϕ]* [ˆ] *[†]* 2 *[· · ·]* [ ˆ] *[ϕ]* *[†]* *M* *[|]* [0] *[⟩]* *[.]* (18)


The Slater determinants evolve with *n* via rotations of the orbitals, as do their coefficients,

which are represented by the weights in the MC sampling. The *T >* 0 AFQMC formalism, as

we will see later, is closely related and works in the same space.
From Thouless’ theorem, the operation of *e* *[−][τ]* [ ˆ] *[H]* [1] on a Slater determinant simply yields another
determinant. Thus for an independent-particle Hamiltonian, where *H* [ˆ] 2 is replaced by a one
body operator, the ground-state projection would therefore turn into the propagation of a single
Slater determinant. In DFT, for example, under the local density approximation (LDA), *H* [ˆ] 2 is
replaced by *H* [ˆ] LDA = *H* [ˆ] 1 + *V* [ˆ] *xc*, where *V* [ˆ] *xc* contains the density operator in real-space, with matrix

elements given by the exchange-correlation functional which is computed with the local density

from the current Slater determinant in the self-consistent process. An iterative procedure can

be carried out, following Eq. (14), to project the solution using the approximate Hamiltonians,

as an imaginary-time evolution of a single Slater determinant [36]. This is illustrated by the

blue line in Fig. 2. Note that this procedure is formally very similar to time-dependent DFT

(TDDFT), except for the distinction of imaginary versus real time.


-----

6.8 Shiwei Zhan g

With Eq. (11), we can now turn the many-body projection into a linear combination of iterative

projections, mimicking the evolution of an ensemble of the corresponding non-interacting systems subjected to fluctuating external (auxiliary) fields. For simplicity, we will take *|Ψ* [(0)] *⟩* (i.e.,
*|Ψ* *T* *⟩* ) as a single Slater determinant. Using the mixed estimator in Eq. (16), we can visualize
the calculation of the energy as carrying out the projection of the ket *|Ψ* [(] *[n]* [)] *⟩* by an open-ended

random walk. Aside from technical steps such as importance sampling, population control,

numerical stabilization, etc. to make this process practical and more efficient [19,2], we could
think of the calculation at the conceptual level as: (i) start a population of walkers *{|φ* [0)] *k* *[⟩}]* [ with]
*k* = 1 *, . . ., N* *w* labeling the walkers, (ii) sample an **x** from *p* ( **x** ) for each walker, (iii) propagate
it by *B* ( **x** ), (iv) sweep through the population to advance to *n* =1, and repeat steps (ii) and (iii) to

iterate *n* . The ideas are illustrated in Fig. 2. [Note that, if we use a linear combination of Slater
determinants of the form of Eq. (17) for *|Ψ* [(0)] *⟩*, we can sample the determinants to initialize the

population in (i).] In Appendix A we include a brief review of MC and random walks.

We now expand on the formalism a bit more to make a more explicit connection with the *T >* 0

formalism that we will discuss in Sec. 2.3. There we will look more deeply into the origin

of the sign problem. By making the formal connection, the discussion on the sign problem at

finite- *T* can be straightforwardly connected to the ground-state situation here. For computing
### n ∆ τ

![](.figures/zhang_2019_auxiliary-field-quantum-monte-carlo/zhang_2019_auxiliary-field-quantum-monte-carlo.pdf-7-0.png)

**Fig. 2:** *Illustration of the iterative imaginary-time projection to the ground state. The overlap*
*of the Slater determinants with a test wave function (e.g., the exact ground state |Ψ* 0 *⟩) is plotted*
*vs. imaginary time n∆τ* *. The thick blue line indicates a projection using e* *[−][∆τ]* [ ˆ] *[H]* [LDA] [(] *[φ]* [(] *[n]* [)] [)] *which*
*converges to the LDA ground state (or a local minimum). The wiggly magenta lines indicate*
*an AFQMC projection which captures the many-body effect beyond LDA as a stochastic linear*
*superposition. The propagator is obtained by expanding the two-body part of the* ˆ ˆ *H* [ˆ] *, namely*
*H* 2 *−V* *xc* *, by a Hubbard-Stratonovich transformation as discussed in Sec. 2.1. The dotted redline*
*indicates a path which can lead to a sign problem (Sec. 3.1).*


-----

AF Q MC 6.9

the ground-state expectation *⟨O* [ˆ] *⟩* in Eq. (15), the denominator is

2 *n*

*⟨ψ* [(0)] *|e* *[−][n∆τ]* [ ˆ] *[H]* *e* *[−][n∆τ]* [ ˆ] *[H]* *|ψ* [(0)] *⟩* = *ψ* [(0)] [��] � *d* **x** [(] *[l]* [)] *p* ( **x** [(] *[l]* [)] ) *B* [ˆ] ( **x** [(] *[l]* [)] )�� *ψ* (0) �
��

*l* =1

= *d* **x** [(] *[l]* [)] *p* ( **x** [(] *[l]* [)] ) det [ *Ψ* [(0)] ] *[†]* [ �] *B* ( **x** [(] *[l]* [)] ) *Ψ* [(0)] [�] *.* (19)
�� �

*l* *l*

In the early forms of ground-state AFQMC calculations [13, 37] (which in the presence of a

sign problem are transient estimates that have exponential scaling), a value of *n* is first chosen

and fixed throughout the calculation. If we use *X* to denote the collection of the auxiliary-fields
*X* = *{* **x** [(1)] *,* **x** [(2)] *, . . .,* **x** [(2] *[n]* [)] *}* and *D* ( *X* ) to represent the integrand in Eq. (19), we can write an
estimator of the expectation value of Eq. (15) as


*⟨* *O* [ˆ] *⟩* � � *D* ( *X* ) � � *s* ( *X* ) *dX*
��� *D* ( *X* )�� *s* ( *X* ) *dX* *,* (20)


*⟨* *O* [ˆ] *⟩* *D* ( *X* ) *dX*
=
� *D* ( *X* ) *dX*


�


*⟨O* [ˆ] *⟩* =


�


where
*s* ( *X* ) *≡* *D* ( *X* ) */* �� *D* ( *X* )�� (21)

measures the “sign” of *D* ( *X* ), and *⟨s⟩* = *⟨s* ( *X* ) *⟩* *|D|* gives an indication of the severity of the
sign problem, as further discussed in Sec. 3.1 under the *T >* 0 formalism. The non-interacting
expectation for a given *X* is *⟨O* [ˆ] *⟩≡⟨O* [ˆ] *⟩* *φ* *L* *φ* *R* as defined in Eq. (55) in Appendix B, where

*⟨φ* *L* *|* = *⟨ψ* [(0)] *|* *B* [ˆ] ( **x** [(2] *[n]* [)] ) *B* [ˆ] ( **x** [(2] *[n][−]* [1)] ) *· · ·* *B* [ˆ] ( **x** [(] *[n]* [+1)] )

ˆ
*|φ* *R* *⟩* = *B* ( **x** [(] *[n]* [)] ) ˆ *B* ( **x** [(] *[n][−]* [1)] ) *· · ·* ˆ *B* ( **x** [(1)] ) *|ψ* [(0)] *⟩,*

which are both Slater determinants. In Appendix B, basic properties of Slater determinants and

the computation of expectation values are reviewed.
*D* ( *X* ) as well as *⟨φ* *L* *|* and *|φ* *R* *⟩* are completely determined by the path *X* in auxiliary-field
space. The ex p ectation in Eq. (20) is therefore in the form of Eq. (49), with *f* ( *X* ) = *|D* ( *X* ) *|*
and *g* ( *X* ) = *⟨O* [ˆ] *⟩* . The important point is that, for each *X*, *|D* ( *X* ) *|* is a number and *g* ( *X* ) can
be evaluated using Eqs. (56) and (57). Often the Metropolis Monte Carlo algorithm [38] is
used to sample auxiliary-fields *X* from *|D* ( *X* ) *|* . Any *⟨O* [ˆ] *⟩* can then be computed following the

procedure described by Eq. (48) in Appendix A.
###### **2.3 Finite-temperature, grand-canonical ensemble calculations**

At a temperature *T >* 0 K, the expectation value of any physical observable

*⟨O* [ˆ] *⟩≡* [Tr] [(] [ ˆ] *[O e]* *[−][β]* [ ˆ] *[H]* [)] *,* (22)

Tr( *e* *[−][β]* [ ˆ] *[H]* )

which is a weighted average in terms of the partition function *Z* in the denominator

*Z ≡* Tr( *e* *[−][β]* [ ˆ] *[H]* ) = Tr[ *e* ~~�~~ *[−][∆τ]* [ ˆ] *[H]* *· · · e* �� *[−][∆τ]* [ ˆ] *[H]* *e* *[−][∆τ]* [ ˆ] *[H]* � ] *,* (23)
*L*


-----

6.10 Shiwei Zhan g

where *β* = 1 */kT* is the inverse temperature, *∆τ* = *β/L* is the time-step, and *L* is the number

of “time slices.” Substituting Eq. (11) into Eq. (23) gives

*Z* = � *dXP* ( *X* ) Tr[ *B* ( **x** *L* ) *· · · B* ( **x** 2 ) *B* ( **x** 1 )] *,* (24)

�

*X*

where *X ≡{* **x** 1 *,* **x** 2 *, . . .,* **x** *L* *}* denotes a complete *path* in auxiliary-field space, and *P* ( *X* ) =
� *Ll* =1 *[p]* [(] **[x]** *[l]* [)][. Note that, similar to the] *[ T]* [ = 0][ K case, a Trotter error can be present in Eq. (11),]
which is controllable (by, e.g., extrapolating results with different values of *∆τ* ). The trace over

fermion degrees of freedom can be performed analytically [12,39], which yields

*Z* = *dXP* ( *X* ) det[ *I* + *B* ( **x** *L* ) *· · · B* ( **x** 2 ) *B* ( **x** 1 )] *,* (25)
�

where *I* is the *N × N* unit matrix. Note that the trace in Eq. (24), which is over numbers of

particles and initial states, is now replaced by the fermion determinant

*D* ( *X* ) *≡* *P* ( *X* ) det[ *I* + *B* ( **x** *L* ) *· · · B* ( **x** 2 ) *B* ( **x** 1 )] *,* (26)

which can be readily computed for each path *X* . The sum over all paths is evaluated by standard

Monte Carlo techniques. Relating *L* to 2 *n* in the ground-state discussions around Eq. (20), we

can now connect these two classes of methods. Below we will rely on the finite- *T* form in

understanding the origin of the sign problem. This will serve as a common framework for

thinking about the sign problem, and then subsequently the phase problem, by analyzing the

nature and behavior of the paths in *X* space.
The symptom of the sign problem is that *D* ( *X* ) is not always positive. In practice, the MC
samples of *X* are drawn from the probability distribution defined by *|D* ( *X* ) *|* . As *β* increases,
*D* ( *X* ) approaches an antisymmetric function and its average sign,

*⟨s⟩* = � *D* ( *X* ) */* � *|D* ( *X* ) *|,* (27)

*X* *X*

vanishes exponentially, as illustrated in Fig. 3. In the limit of *T →* 0 or *β →∞*, the distribution

becomes fully antisymmetric. (In ground-state calculations discussed in Sec. 2.2, the situation

depicted in Fig. 3 corresponds to the equilibration phase at shorter projection times *τ* . When

the ground state is reached after equilibration, there will be no “green” part left.)

|Col1|det[]|
|---|---|
||det[]|
|||



**Fig. 3:** *Schematic illustration of the sign problem. The horizontal axis denotes an abstraction of*
*the many-dimensional auxiliary-field paths X. The sign problem occurs because the contribut-*
*ing part (shaded area) is exponentially small compared to what is sampled, namely |D* ( *X* ) *|.*
*The origin of the symptoms shown here is explained in Sec. 3.1.*


-----

AF Q MC 6.11
### **3 Constraining the paths in AFQMC**

The sign/phase problem is a generic feature, and is only absent in special cases where the singleparticle propagator *B* [ˆ] ( **x** ) satisfies particular symmetries (see, for example, Ref. [40]). In these
cases, *D* ( *x* ) is real and non-negative, and *s* ( *X* ) remains strictly 1. The symmetries are affected

by the choice of the basis and the form of the decomposition, so it is possible to “engineer

away” the sign problem in some cases. However, these are still limited to very special classes
of Hamiltonians. In general, a sign problem arises if *B* [ˆ] ( **x** ) is real, and a phase problem arises if

ˆ
*B* ( **x** ) is complex.
For real *B* [ˆ] ( **x** ) (e.g. Hubbard-type of short-range repulsive interactions with the spin decom
position), the sign problem occurs because of the fundamental symmetry between the fermion
ground-state *|Ψ* 0 *⟩* and its negative *−|Ψ* 0 *⟩* [18, 41]. In *T* = 0 K calculations, for any ensemble
of Slater determinants *{|φ⟩}* which gives a MC representation of the ground-state wave function, as in Eq. (17), this symmetry implies that there exists another ensemble *{−|φ⟩}* which is

also a correct representation. In other words, the Slater determinant space can be divided into
two degenerate halves (+ and *−* ) whose bounding surface *N* is defined by *⟨Ψ* 0 *|φ⟩* = 0. This

dividing surface is unknown. (In the cases with special symmetry mentioned above, the two

sides separated by the surface are both positive.) In the illustration in Fig. 2, the surface is the

*−*
horizontal axis; the “ ” ensemble is given by the mirror images of the paths shown, i.e., by

reflecting them with respect to the horizontal axis.
###### **3.1 An exact boundary condition**

To gain further insight on the origin of the sign problem, we conduct a thought experiment in

which we generate all the complete paths *X* by *L* successive steps, from **x** 1 to **x** *L* [25]. We

use the *T >* 0 K formalism, whose understanding will provide a straightforward connection

to the ground-state method. We consider the contribution in *Z* of an individual *partial path*
*{* **x** 1 *,* **x** 2 *, · · ·,* **x** *l* *}* at step *l*

*P* *l* ( *{* **x** 1 *,* **x** 2 *, · · ·,* **x** *l* *}* ) *≡* Tr[ *BB · · · B* � �� � *B* ( **x** *l* ) *· · · B* ( **x** 2 ) *B* ( **x** 1 )] *,* (28)
*L−l*

where *B ≡* *e* *[−][∆τH]*, which in general is not a single-particle propagator. In particular, we

consider the case when *P* *l* = 0. This means that, after the remaining *L −* *l* steps are finished,

the collective contribution from *all* complete paths that result from the partial path will be
precisely zero. In other words, complete paths whose first *l* elements are *{* **x** 1 *,* **x** 2 *, · · ·,* **x** *l* *}* do
not contribute in *Z* ; the sum over all possible configurations of *{* **x** *l* +1 *,* **x** *l* +2 *, · · ·,* **x** *L* *}* simply
reproduces the *B* ’s in (28), leading to zero by definition.

Thus, in our thought experiment any partial path that reaches the axis in Fig. 4 immediately

turns into noise, regardless of what it does at future *l* ’s. A complete path which is in contact
with the axis at any point belongs to the “antisymmetric” part of *D* ( *X* ) in Fig. 3, whose contri
butions cancel. The “noise” paths, which become an increasingly larger portion of all paths as

*β* increases, are the origin of the sign problem.


-----

6.12 Shiwei Zhan g

Since *P* 0 is positive and *P* *l* changes continuously with *l* at the limit *∆τ →* 0, a complete

path contributes **iff** it stays entirely *above* the axis in Fig. 4. Thus, in our thought experiment,

imposition of the boundary condition (BC)

*P* 1 ( *{* **x** 1 *}* ) *>* 0 *,* *P* 2 ( *{* **x** 1 *,* **x** 2 *}* ) *>* 0 *,* *· · ·,* *P* *L* ( *{* **x** 1 *,* **x** 2 *, · · ·,* **x** *L* *}* ) *>* 0 (29)

will ensure all contributing complete paths to be selected while eliminating all noise paths. *The*

*axis acts as an infinitely absorbing boundary.* A partial path is terminated and discarded as soon

as it reaches the boundary. By discarding a path, we eliminate all of its future paths, including

the ones that would eventually make positive contributions. The BC makes the distribution of

complete paths vanish at the axis, which accomplishes complete cancellation of the negative
and the corresponding positive contributions in the antisymmetric part of *D* ( *X* ). Calculation of

*Z* from our thought experiment remains exact.
###### **3.2 Implementing the boundary condition and importance sampling**

**3.2.1** **Implementation of the boundary condition (BC) at finite** ***∆τ***

In actual simulations *∆τ* is finite and paths are defined only at a discrete set of imaginary times.

The BC on the underlying continuous paths is the same, namely that the probability distribution

must vanish at the axis in Fig. 4.

In Fig. 5, we illustrate how the BC is imposed under the discrete representation. The “contact”

point is likely to be between time slices and not well defined, i.e., *P* *l* may be zero at a non
integer value of *l* . To the lowest order, we can terminate a partial path when its *P* *l* first turns

negative. That is, we still impose Eq. (29) in our thought experiment to generate paths. In

Fig. 5, this means terminating the path at *l* = *n* (point B) and thereby discarding all its future

paths (represented by the dashed lines ‘BS...’ and ‘BT...’).

We actually use a higher order approximation, by terminating at either *l* = *n −* 1 or *l* = *n*, i.e.,

either point B or point A. The probability for terminating at A is chosen such that it approaches
1 smoothly as *P* *n−* 1 *→* 0, for example, *p* A = 1 */* [1 + *P* *n−* 1 */|P* *n* *|* ]. If A is chosen, all future

*Z*




|Col1|lP|
|---|---|
||P l|
|l|L 0|


![](.figures/zhang_2019_auxiliary-field-quantum-monte-carlo/zhang_2019_auxiliary-field-quantum-monte-carlo.pdf-11-0.png)

**Fig. 4:** *Schematic illustration the boundary condition to control the sign problem. P* *l* *(Eq. (28))*
*is shown as a function of the length of the partial path, l, for several paths. When P* *l* *becomes* 0 *,*
*ensuing paths (dashed lines) collectively contribute zero. Only complete paths with P* *l* *>* 0 *for*
*all l (solid line) contribute in Z.*


-----

AF Q MC 6.13

paths from A are discarded (represented by ‘AR...’ and ‘AB...’); otherwise we terminate at B as

above. This is in the spirit of the so-called mirror correction (see, e.g., Ref. [42,19]).

It is important to note that, in both approaches, the finite- *∆τ* error in imposing the BC vanishes
as *∆τ →* 0. The first method, terminating at B, makes a fluctuating error of *O* ( *∆τ* ) in the

location of the absorbing boundary. The method we actually use ensures that the location of the

boundary is correct to the next order, and is a second order algorithm.

**3.2.2** **Approximating the boundary condition**

In practice *B* is not known. We replace it by a known trial propagator *B* *T* . The BC now yields

approximate results, which become exact if *B* *T* is exact. If *B* *T* is in the form of a single-particle

propagator, we can evaluate Eq. (28) and combine it with Eq. (29) to obtain the approximate

BC: *For each l*,

*L−l*

*P* *l* *[T]* [(] *[{]* **[x]** [1] *[,]* **[ x]** [2] *[,][ · · ·][,]* **[ x]** *[l]* *[}]* [) = det[] *[I]* [ + (] � *B* *T* ) *B* ( **x** *l* ) *· · · B* ( **x** 1 )] *>* 0 *.* (30)

*m* =1

Different forms of *B* are possible, and of course it is valuable and important to think about

improving *B* . Recently self-consistent constraints formulated in ground-state AFQMC [43]

have been generalized to the *T >* 0 method [4].

**3.2.3** **Importance sampling algorithm—automatic imposition of the constraint** ***and***
**“nudge” in the random walks**

*(1) Automatic imposition of the constraint.* To implement the constraint in a path-integral frame
work of Eq. (20) at *T* = 0 K and Eq. (25) at *T >* 0 K would have severe difficulties with

ergodicity. We wish to generate MC samples of *X* which satisfy the conditions in (30). The

most natural way to accomplish this is to incorporate the boundary conditions on the path as

an additional acceptance condition [44]. However, the BC is *non-local* ; it also breaks trans
lational invariance in imaginary time, since the condition selects an *l* = 1 to start. Updating

the auxiliary-fields at a particular time *l* can cause violation of the constraint in the future (at

*Z*

|Col1|P l R A S n|
|---|---|
|l|L C n-1 0 B T|



**Fig. 5:** *Imposition of the boundary condition at finite ∆τ* *. Paths are discrete. The point of con-*
*tact, C (see Fig. 4), must be approximated, either by B (low order algorithm) or by interpolation*
*between B and A (higher order).*


-----

6.14 Shiwei Zhan g

larger *l* ) or in the past (when sweeping the path backwards in *l* ). Without a scheme to pro
pose paths that incorporates information on future contributions, it is difficult to find complete

paths which satisfy all the constraints, especially as *β* increases. Global updating is difficult,

because the number of green paths is exponentially small compared to the total number of pos
sible paths, as illustrated in Fig. 4. The formulation of the open-ended, branching random walk

approach [19, 25] in imaginary-time solves this problem. An additional advantage is that it is

straightforward to project to longer imaginary-time in order to approach the ground state for

*T* = 0 K. Moreover, when we carry out constraint release [35], the formalism will rely on the

open-ended random walk.

*(2) Nudging the random walk* . The goal of the branching random walk algorithm is to generate

MC samples of *X* which *both* satisfy the conditions in (30) *and* are distributed according to
*D* ( *X* ). The basic idea is to carry out the thought experiment stochastically. We construct

an algorithm which builds directly into the sampling process both the constraints and some

knowledge of the projected contribution. In terms of the *trial* projected partial contributions
*P* *l* *[T]* *≡P* *l* *[T]* [(] *[{]* **[x]** [1] *[,]* **[ x]** [2] *[,][ · · ·][,]* **[ x]** *[l]* *[}]* [)][ in the] *[ T >]* [ 0][ K method, the fermion determinant] *[ D]* [(] *[X]* [)][ can be]

written as


*D* *X* *[P]* *L* *[T]*
( ) =
*P* *L* *[T]* *−* 1


*P* *L* *[T]* *−* 1 *· · ·* *[P]* 2 *[T]*
*P* *L* *[T]* *−* 2 *P* 1 *[T]*


*PP* 10 *[T][T]* *P* 0 *[T]* *[.]* (31)


As illustrated in Fig. 6, we construct the path *X* by a random walk of *L* steps, corresponding

to stochastic representations of the *L* ratios in Eq. (31). At the *l* -th step, we sample **x** *l* from
the conditional probability density function defined by ( *P* *l* *[T]* *[/][P]* *l* *[T]* *−* 1 [)][. This allows us to select] **[ x]** *[l]*
according to the best estimate of its projected contribution in *Z* . In other words, we sample

from a probability distribution function of the contributing paths only (solid lines in Fig. 4),

instead of *all* possible paths. Note that the probability distribution for **x** *l* vanishes smoothly as
*P* *l* *[T]* [approaches zero, naturally imposing the BC in Eq. (30) as anticipated in part (1) of this]
section. Ref. [4] contains a more detailed outline of the procedure.

*(3) Connecting the importance sampling algorithms between T* = 0 *and T >* 0 *K methods.*

In the above we have used the *T >* 0 K framework to describe the basic idea of importance
sampling. At each step, the importance-sampling transformation uses *P* *l* *[T]* *[/][P]* *l* *[T]* *−* 1 [to modify the]
probability distribution from which **x** *l* is sampled. The ground-state version, conceptually, uses
*⟨Ψ* *T* *|φ* [(] *[n]* [)] *⟩/⟨Ψ* *T* *|φ* [(] *[n][−]* [1)] *⟩* . In Sec. 3.3, we show how this is actually realized when the auxiliary
fields are continuous (complex), by the use of a force bias. To connect back to the *T >* 0 K

form, all we need is to invoke the formal equivalence

*⟨* *Ψ* *T* *|φ* *[′]* ( **x** ) *⟩* *m* = 1 *[B]* *[T]* [)] *[ B]* [(] **[x]** [)] *[B]* [(] **[x]** *[l][−]* [1] [)] *[ · · ·][ B]* [(] **[x]** [1] [)]]

*⇐⇒* [det] [[] *[I]* [ + ] [(][�] *[L][−][l]* *.* (32)
*⟨Ψ* *T* *|φ⟩* det[ *I* + ( [�] *[L]* *m* *[−]* =1 *[l]* [+1] *B* *T* ) *B* ( **x** *l−* 1 ) *· · · B* ( **x** 1 )]

On the right of Eq. (32), the finite- *T* path segment *{* **x** 1 *, · · ·,* **x** *l−* 1 *}* has been generated already,
and the step in question is *l*, where we wish to generate **x** *l*, denoted by **x** .


-----

AF Q MC 6.15
###### **3.3 The phaseless formalism for complex auxiliary-fields**

When the many-body Hamiltonian leads to a decomposition with *λ >* 0 in Eq. (4), the resulting

HS transformation will have complex auxiliary-fields. This is the case for the electron-electron

repulsion. (As mentioned earlier, when we refer loosely to having complex auxiliary-fields,

what we really mean is that the propagator resulting from the two-body Hamiltonian is com
plex. Incidentally, it is always possible to have real auxiliary-fields, for example by making a

negative shift to the positive potential, but that simply leads to many fluctuating fields to recover

a constant background, and a much more severe sign problem [14,35].) In this situation a phase

problem arises, as illustrated in Fig. 7. The random walks now extend into a complex plane,

and the boundary condition discussed in Sec. 3.1 must be generalized. This generalization is not

straightforward, since the orbitals (or one-particle propagators) contain random phases which

are entangled with the phases in the coefficients in front of the determinants. We next describe

the formalism to deal with the problem [14], using the *T* = 0 K framework. See Eq. (32) in the

previous section for how to “translate” this to *T >* 0 K.

With a continuous auxiliary-field, importance sampling is achieved with a force bias [14, 45].

To sketch a derivation we write the full many-body propagator as


1
�� *√* 2 *π*


*N* *γ*
*e* *[−]* **[x]** [2] *[/]* [2] *B* ( **x** ) *d* **x** *,* (33)
�


where for formal convenience we will assume that we can combine products of one-body prop
agators, as in Eq. (12), into a joint form by summing the one-body operators in the exponent, or

vice versa, possibly incurring additional Trotter errors which will be dealt with separately. For
### step
##### *0* *1* *2* *L--1* *L*

![](.figures/zhang_2019_auxiliary-field-quantum-monte-carlo/zhang_2019_auxiliary-field-quantum-monte-carlo.pdf-14-1.png)

**Fig. 6:** *Illustration of the sampling procedure in the algorithm. Circles represent auxiliary-*
*fields* **x** *l* *. A row shows the field configuration at the corresponding step number shown on the*
*right. Within each row, the imaginary-time index l increases as we move to the left, i.e., the*
*first circle is* **x** 1 *and the last* **x** *L* *. Red circles indicate fields which are not “activated” yet, i.e.,*
*B* *T* *is still in place of B. Green circles indicate fields that have been sampled, with the arrow*
*indicating the one being sampled in the current step.*


-----

6.16 Shiwei Zhan g

compactness we will also omit the normalization factor, (1 */√* 2 *π* ) *[N]* *[γ]*, of the Gaussian probabil
ity density function from here on.

We introduce a shift in the integral in Eq. (33), which leads to an alternative propagator

*e* *[−]* **[x]** [2] *[/]* [2] *e* **[x]** *[·]* **[x]** [¯] *[−]* **[x]** [¯] [2] *[/]* [2] *B* ( **x** *−* **x** ¯) *d* **x** *.* (34)
�

The new propagator is exact for any choice of the shift ¯ **x**, which can be complex in general.

We recall that the random walk is supposed to sample the coefficient *α* *φ* in Eq. (17)

*|Ψ* 0 *⟩* = *[.]* � *w* *φ* *|φ⟩* *.* (35)

*{φ}*

The sum in Eq. (35) is over the population of walkers after equilibration and is over the Monte
Carlo samples, typically much smaller than the sum in Eq. (17). The weight of each walker *|φ⟩*,
*w* *φ*, can be thought of as 1 (all walkers with equal weight); it is allowed to fluctuate only for
efficiency considerations.

Using the idea of importance sampling, we seek to replace Eq. (35) by the following to sample

Eq. (17):

*|φ⟩*

*|Ψ* 0 *⟩* = � *w* *φ* *⟨Ψ* *T* *|φ⟩* *[,]* (36)

*φ*

where any overall phase of the walker *|φ⟩* is cancelled in the numerator and denominator on the

right-hand side [14]. This implies a modification to the propagator in Eq. (34):

*⟨Ψ* *T* *|φ* *[′]* ( **x** ) *⟩e* *[−]* **[x]** [2] *[/]* [2] *e* **[x][x]** [¯] *[−]* **[x]** [¯] [2] *[/]* [2] *B* ( **x** *−* **x** ¯) 1 (37)
� *⟨Ψ* *T* *|φ⟩* *[d]* **[x]** *[,]*

¯
where *|φ* *[′]* ( **x** ) *⟩* = *B* ( **x** *−* **x** ) *|φ⟩* and the trial wave function *|Ψ* *T* *⟩* represents the best guess to *|Ψ* 0 *⟩* .

Now the weight of the waker under importance sampling becomes

*⟨* *Ψ* *T* *|φ* *[′]* ( **x** ) *⟩*
*w* *φ* *′* ( **x** ) = *w* *φ* *e* **[x]** *[·]* **[x]** [¯] *[−]* **[x]** [¯] [2] *[/]* [2] *.* (38)

*⟨Ψ* *T* *|φ⟩*

We can minimize the fluctuation of the factor on the right-hand side with respect to **x**, by
evaluating the ratio *⟨Ψ* *T* *|φ* *[′]* ( **x** ) *⟩/⟨Ψ* *T* *|φ⟩* in Eqs. (37) and (38), or correspondingly, the ratio on
the right-hand side of Eq. (32) for *T >* 0 K. Expanding the propagators in *∆τ*, and rearranging

terms [1,21], we obtain the optimal choice for the force bias

**x** ¯ = ¯ **v** *≡−* *[⟨]* *[Ψ]* *[T]* *[|]* **[v]** [ˆ] *[|][φ][⟩]* *∼O* ( *√∆τ* ) (39)

*⟨Ψ* *T* *|φ⟩*

for ground state and a similar expectation value ¯ **v** evaluated at time-step *l* for *T >* 0. The

weight factor in Eq. (38) can then be manipulated into a more compact form

*w* *φ* *′* ( **x** ) = *w* *φ* exp� *−* *∆τE* *L* ( *φ* )� *,* (40)

where *E* *L* is the local energy of the Slater determinant

*E* *L* ( *φ* ) *≡* *[⟨]* *[Ψ]* *[T]* *[|]* *[H]* [ ˆ] *[|][φ][⟩]* (41)

*⟨Ψ* *T* *|φ⟩* *[.]*


-----

AF Q MC 6.17




**1**

**0.5**

**0**

**−0.5**


![](.figures/zhang_2019_auxiliary-field-quantum-monte-carlo/zhang_2019_auxiliary-field-quantum-monte-carlo.pdf-16-0.png)

**−1**

**−1** **−0.5** **0** **0.5** **1**
**Re<** Ψ T |φ>

|Im|m|Col3|Col4|Col5|Col6|Col7|Col8|Col9|
|---|---|---|---|---|---|---|---|---|
|Re|||||||||
||||||||||



**Fig. 7:** *Schematic illustration of the phase problem and the constraint to control it, using the*
*ground-state formalism. The left panel shows, as a function of projection time β ≡* *n∆τ* *,*
*trajectories of 5 walkers characterized by the real (Re) and imaginary (Im) parts of their overlap*
*with the ground-state wave function. The right panel shows the walker distribution integrated*
*over imaginary time, i.e., the different frames in the left panel stacked together along β. The*
*phase problem occurs because the initial phase “coherence” of the random walkers rapidly*
*deteriorates with β, as they become uniformly distributed in the Re-Im-plane. The idea of the*
*phase constraint [14] is to apply a gauge transformation such that confining the random walk*
*in the single magenta plane (left) is a good approximation.*

We now have the full propagator of Eq. (37)

¯
*e* *[−]* **[x]** [2] *[/]* [2] *B* ( **x** *−* **v** ) exp� *−* *∆τE* *L* ( *φ* )� *d* **x** *.* (42)
�

Projection with Eq. (42) will in principle lead to the ground-state wave function in the form of

Eq. (36). The weight of the walker is determined by *E* *L*, which is independent of any phase

factor of the determinant. We will refer to this as the local energy form of AFQMC. As an

alternative, referred to as the hybrid form, we could evaluate the weight of each walker directly

according to Eq. (38) after the propagation. (In this form ¯ **x** can in principle be anything, but of

course poor choices will lead to larger fluctuations in the weights.)
In the limit of an exact *|Ψ* *T* *⟩*, *E* *L* is a *real* constant, and the weight of each walker remains real.

The mixed estimate for the energy from Eq. (16) is phaseless


*E* 0 [c] [=]


� *φ* *[w]* *[φ]* *[E]* *[L]* [(] *[φ]* [)]

*.* (43)

� *φ* *[w]* *[φ]*


With a general *|Ψ* *T* *⟩* which is not exact, a natural approximation is to replace *E* *L* in Eq. (42) by

its real part, Re *E* *L* . The same replacement is then necessary in Eq. (43).

In early tests in the electron gas and in simple solids, we found that the phase of *E* *L* could be

carried for very long imaginary-times (and then resetting) without causing any noticeable effect

on the phase problem. Keeping the phase also did not appear to affect the total energy computed

from the mixed estimator. For computing observables in the ground state, back-propagation

(BP) [19, 45] is needed. It was found that restoring the phases of *E* *L* in the BP paths helped


-----

6.18 Shiwei Zhan g

improve the computed observables and correlations [46]. More tests for *T >* 0 are necessary

but it is likely that keeping the phase will be preferable (especially because the paths are much

shorter than in ground-state calculations). At *T >* 0, it was also found that restoring time
translation symmetry after the compete path has been sampled improves the results [4].

This formalism is all that is needed to handle the sign problem in the case of a *real* ˆ **v** . For any

**v** ˆ the shift ¯ **x** diverges as a walker approaches the origin in the complex plane shown in the right
panel of Fig. 7, i.e., as *⟨Ψ* *T* *|φ* *[′]* *⟩→* 0. The effect of the divergence is to move the walker away
from the origin. With a *real* ˆ **v**, *∆θ* = 0 and the random walkers move only on the real axis. If
they are initialized to have positive overlaps with *|Ψ* *T* *⟩*, ¯ **x** will ensure that the overlaps remain

positive throughout the random walk. Thus in this case our formalism above reduces to the CP

methods ground state [42,19] and finite- *T* [25].

For a general case with a complex ˆ **v**, however, the phaseless formalism alone is not sufficient to
remove the phase problem. To illustrate this we consider the phase of *⟨Ψ* *T* *|φ* *[′]* ( **x** *−* **x** ¯) *⟩/⟨Ψ* *T* *|φ⟩*,

or the equivalent form for *T >* 0 K given by Eq. (32). This phase, which we shall denote by
*∆θ*, is in general non-zero: *∆θ ∼O* ( *−* **x** Im(¯ **x** )). The walkers will thus undergo a random walk
in the complex plane defined by *⟨Ψ* *T* *|φ* *[′]* *⟩* . At large *β* they will therefore populate the complex

plane symmetrically, independent of their initial positions. This is illustrated in the right panel
of Fig. 7, which shows *⟨Ψ* *T* *|φ⟩* for three-dimensional jellium with two electrons at *r* *s* = 10 for a
total projection time of *β* = 250. The distribution of the walkers is seen to be symmetric about
the phase angle, and any signal that the walkers are all real initially (and *⟨Ψ* *T* *|φ* [(0)] *⟩* = 1) is lost

in the statistical noise.

In other words, for a complex ˆ **v**, the random walk is “rotationally invariant” in the complex

plane, and the divergence of ¯ **x** is not enough to prevent the build-up of a finite density at the

origin. Near the origin the local energy *E* *L* diverges, which causes diverging fluctuations in

the weights of walkers. To address this we make an additional approximation. We project

the random walk to “one-dimension” and multiply the weight of each walker in each step by
cos( *∆θ* )

*w* *φ* *′* = *w* *φ* *′* max *{* 0 *,* cos( *∆θ* ) *}* (44)

in addition to Eq. (40) (or Eq. (38) if the hybrid form is used). This is only a good approximation

in the presence of the similarity transformation that we have already preformed in what we have

been calling importance sampling. There is a subtle but fundamental distinction between the

formalism we have introduced and “traditional” importance sampling. In the latter, only the

sampling efficiency is affected, not the expectation, because the transformation involves only

real and non-negative functions. Here, in contrast, the functions, as given in Eq. (32), are

*complex* and determine a gauge choice for our random walks. The proper choice of the force
bias ensures that the leading order in the overall phase of *|φ⟩* in the propagator in Eq. (37) is

eliminated.

Several alternatives to Eq. (44) were tested [14, 47, 34]. One that seemed to work as well was
exp� *−* (Im(¯ **x** )) [2] */* 2�, which is the same as cos( *∆θ* ) in the limit of small values of *∆θ* . Another
was to impose Re *⟨Ψ* *T* *|φ* *[′]* *⟩* *>* 0, which gave similar results, but with somewhat larger variance.


-----

AF Q MC 6.19
### **4 Overview of applications, further reading, and outlook**

Due to space limitations, we will not include any examples of applications here. The AFQMC

method has been applied to lattice models, ultracold atoms, solids, and molecular systems.

In lattice models, most of the applications involve “only” a sign problem, because of the short
range nature of the interaction, although in multi-band models there can be tradeoffs between

decompositions which lead to a sign or a phase problem [48]. A large body of results exist, including recent benchmark results [49]. Systems of *O* (1000) electrons have been treated

quite routinely. The AFQMC method has demonstrated excellent capabilities and accuracy,

illustrating its potential as a general many-body computational paradigm. A key recent devel
opment [43] is to use the density or density matrix computed from AFQMC as a feedback into a

mean-field calculation. The trial wave function or density matrix obtained from the mean-field

is then fed back into the AFQMC as a constraint, and a self-consistent constraining condition

is achieved. This has lead to further improvement in the accuracy and robustness of the calcu
lation [43,50]. This development is also seeing more applications in molecules and solids.

A related area involves ultracold atoms, where many valuable calculations have been performed

with AFQMC. In addition to the physics advances these calculations have lead to, this has

proved a fertile test ground for methodological developments, including better sampling meth
ods [51,52], computation of excitations and dynamical correlations [53], the use of BCS [or an
tisymmetrized geminal power (AGP)] trial wave functions [54,55] and projection/path-integral

in Hartree-Fock-Bogoliubov (HFB) space [56], treatment of spin-orbit coupling (SOC) [22],

Bose systems and Fermi-Bose mixtures [45, 57], and achieving linear scaling in lattice or ba
sis size at *T >* 0 K [58]. Many of these developments have direct applications in correlated

systems of molecules and solids.

For molecular systems, a recent review article [21] describes in more detail the application of

AFQMC in quantum chemistry. The formulation of AFQMC with Gaussian basis sets [20,24]

has been extremely valuable. Direct comparisons can be made with high-level QC results,

which have provided valuable benchmark information and have been crucial in developing the

method. Many calculations have been performed using AFQMC as a “post-DFT” or “post-HF”

approach for molecules and solids by simply feeding in the solution from standard DFT or HF.

Several other systematic benchmarks have appeared, for example on the G1 set [59], on a set

of 44 3 *d* transition-metal containing diatomics [60], on singlet-triplet gaps in organic biradicals

[61], etc. Major recent methodological advances include the computation of observables [46],

geometry optimization [62], and speedups using GPUs [32], low-rank tensor decomposition

[63], embedding [64] and localization/downfolding [65], and correlated sampling [66], etc.

For solids, calculations have been done using planewaves and pseudopotentials including recent

implementation of multiple-projector ones [67], with downfolding [29], with Gaussian-type

orbitals [68], etc. A benchmark study [69] was recently carried out involving a large set of

modern many-body methods. AFQMC was found to be comparable in accuracy to CCSD(T),

the gold standard in chemistry [70,71], near equilibrium geometry. For bond breaking, AFQMC

was able to maintain systematic accuracy. The AFQMC method can also be used to study


-----

6.20 Shiwei Zhan g

excited states. Excited states distinguished by different symmetry from the ground state can

be computed in a manner similar to the ground state. For other excited states, prevention of

collapse into the ground state and control of the fermion sign/phase problem are accomplished

by a constraint using an excited state trial wave function [72]. An additional orthogonalization

constraint is formulated to use virtual orbitals in solids for band structure calculations [73].

The AFQMC method is a computational framework for many-body calculations which com
bines a field-theoretic description with stochastic sampling. AFQMC has shown strong promise

with its scalability (with system size and with parallel computing platforms), capability (total

energy computation and beyond), and accuracy. The method is just coming into form, and rapid

advances in algorithmic development and in applications are on-going. The literature is grow
ing and I only listed a portion of it above. In addition, there is a pedagogical code for lattice

models written in Matlab [74] that will be very useful for getting into the method.

We have discussed both ground-state and *T >* 0 auxiliary-field-based methods for correlated

electron systems. We have outlined the formalism in a rather general way which allows for

a systematic understanding of the origin of the sign/phase problem as well as the underlying

theory for a scalable method capable of handling large molecules and bulk systems.

Often in the study of correlated models in condensed matter or cold atoms in optical lattices, the

comment “But there is a sign problem” is made, to imply “so QMC calculations cannot be used

here.” I hope that these lectures and the large number of results in the literature with AFQMC

will change this mindset. Calculations indeed can be done in systems where a sign problem is

present—often with some of the most accurate results that are presently possible.

The AFQMC method has low-polynomial (cubic) scaling with system size, similar to DFT

calculations. The structure of the open-ended random walk makes it ideally suited for modern

high-performance computing platforms, with exceptional capacity for parallel scaling [15]. The

rapid growth of high-performance computing resources will thus provide a strong boost to the

application of AFQMC in the study of molecules and solids. The connection with independent
electron calculations, as we have highlighted, makes it straightforward to build AFQMC on top

of DFT or HF codes, and take advantage of the many existing technical machineries developed

over the past few decades in materials modeling. It also gives AFQMC much versatility as

a general many-body method, offering, for example, straightforward treatment of heavier el
ements and spin-orbit coupling, computation of dynamical correlations, and the capability to

embed AFQMC naturally and seamlessly in a calculation at the independent-particle level.

The development of AFQMC is entering an exciting new phase. We expect the method and the

concept discussed here to see many applications, and to significantly enhance the capability of

quantum simulations in interacting fermion systems. A large number of possible directions can

be pursued, including many opportunities for algorithmic improvements and speedups. These

will be spurred forward and stimulated by growth in applications, which we hope will in turn

allow more rapid realization of a general many-body computational framework for correlated

quantum materials.


-----

AF Q MC 6.21
###### **Acknowledgments**

I am indebted to numerous colleagues and outstanding students and postdocs. Length restriction

does not allow the full list here, but I would be remiss without thanking Y. He, H. Krakauer,

F. Ma, M. Motta, W. Purwanto, M. Qin, J. Shee, H. Shi, and E. Vitali for their contributions.

My group has been a part of the Simons Foundation’s Many-Electron collaboration, from which

we have benefitted greatly. Support from the Department of Energy (DOE) and the National

Science Foundation (NSF) is also gratefully acknowledged. Computing was done on the Oak

Ridge Leadership Computing Facilities via an INCITE award, and on the HPC facilities at

William & Mary. The Flatiron Institute is a division of the Simons Foundation.


-----

6.22 Shiwei Zhan g
### **Appendices** **A A few basics of Monte Carlo techniques**

We list a few key elements from standard Monte Carlo (MC) techniques which are important to

our discussions on QMC. For an introduction on MC methods, see, e.g., Ref. [38].

MC methods are often used to compute many-dimensional integrals of the form


*Ω* � 0 *Ω* *[f]* 0 [(] *[f]* **[x]** [(][)] **[x]** *[g]* [(][)] **[x]** *[d]* **[x]** [)] *[d]* **[x]** *,* (45)


*G* =


�


where **x** is a vector in a many-dimensional space and *Ω* 0 is a domain in this space. We will
assume that *f* ( **x** ) *≥* 0 on *Ω* 0 and that it is normalizable, i.e., the denominator is finite. A
familiar example of the integral in Eq. (45) comes from classical statistical physics, where *f* ( **x** )

is the Boltzmann distribution.

To compute *G* by MC, we *sample* **x** from a probability density function (PDF) proportional to
*f* ( **x** ): *f* [¯] ( **x** ) *≡* *f* ( **x** ) */* � *Ω* 0 *[f]* [(] **[x]** [)] *[d]* **[x]** [. This means to generate a sequence] *[ {]* **[x]** [1] *[,]* **[ x]** [2] *[, . . .,]* **[ x]** *[i]* *[, . . .][ }]* [ so]

that the probability that any **x** *i* is in the sub-domain ( **x** *,* **x** + *d* **x** ) is

Prob *{* **x** *i* *∈* ( **x** *,* **x** + *d* **x** ) *}* = *f* [¯] ( **x** ) *d* **x** *.* (46)

There are different techniques to sample a many-dimensional function *f* ( **x** ). The most general
and perhaps most commonly used technique to sample *f* ( **x** ) (i.e., the PDF *f* [¯] ( **x** )) is the Metropo
lis algorithm, which creates a Markov chain random walk [38] in **x** -space whose equilibrium

distribution is the desired function. We will also use a branching random walk, in which case

there can be a weight *w* *i* associated with each sampled **x** *i* . (In Metropolis, *w* *i* = 1.) The MC

samples provide a formal representation of *f*

*f* ( **x** ) *∝* � *w* *i* *δ* ( **x** *−* **x** *i* ) *.* (47)

*i*

Given *M* independent samples from *f* ( **x** ), the integral in Eq. (45) is estimated by


*M*

*w* *i* (48)

�

*i* =1


*G* *M* =


*M*
� *w* *i* *g* ( **x** *i* ) */*

*i* =1


The error in the estimate decays algebraically with the number of samples: *|G* *M* *−G| ∝* 1 */√M* .

Using the results above, we can compute


*Ω* � 0 *Ω* *[f]* 0 [(] *[f]* **[x]** [(][)] **[x]** *[g]* [(][)] **[x]** *[h]* [)][(] *[h]* **[x]** [(][)] **[x]** *[d]* **[x]** [)] *[d]* **[x]** *,* (49)


*G* *[′]* =


�


if the function *h* ( **x** ) is such that both the numerator and denominator exist. Formally

*M*
*G* *[′]* *M* [=] � *i* � = 1 *Mi* =1 *[w]* *[i]* *[g]* *[w]* [(] *[i]* **[x]** *[h]* *[i]* [(] [)] **[x]** *[h]* *[i]* [(] [)] **[x]** *[i]* [)] *,* (50)


-----

AF Q MC 6.23

although, as we will see, difficulties arise when *h* ( **x** ) can change sign and is rapidly oscillating.

Integral equations are another main area of applications of MC methods. For example [38], the

integral equation

*Ψ* *[′]* ( **x** ) = *K* ( **x** *,* **y** ) *w* ( **y** ) *Ψ* ( **y** ) *d* **y** *,* (51)
� *Ω* 0

can be viewed in terms of a *random walk* if it has the following properties: *Ψ* ( **y** ) and *Ψ* *[′]* ( **x** )
can be viewed as PDF’s (in the sense of *f* in Eq. (45)), *w* ( **y** ) *≥* 0, and *K* ( **x** *,* **y** ) is a PDF for **x**
conditional on **y** . Then, given an ensemble *{* **y** *i* *}* sampling *Ψ* ( **y** ), the following two steps will
allow us to generate an ensemble that samples *Ψ* *[′]* ( **x** ). First an absorption/branching process is
applied to each **y** *i* according to *w* ( **y** *i* ). For example, we can make int( *w* ( **y** *i* ) + *ξ* ) copies of **y** *i*,
where *ξ* is a uniform random number on (0 *,* 1). Second we randomly walk each new **y** *j* to an
**x** *j* by sampling the PDF *K* ( **x** *j* *,* **y** *j* ). The resulting *{* **x** *j* *}* are MC samples of *Ψ* *[′]* ( **x** ). An example
of this is the one-dimensional integral equation


*∞*
*Ψ* ( *x* ) =
� *−∞*


1
*√πe* *[−]* [(] *[x][−][y]* [)] [2] *[ √]*


2 *e* *[−][y]* [2] *[/]* [2] *Ψ* ( *y* ) *dy,* (52)


which has a solution *Ψ* ( *x* ) = *e* *[−][x]* [2] *[/]* [2] . The random walks, starting from an arbitrary distribution,
will iteratively converge to a distribution sampling *Ψ* ( *x* ).


-----

6.24 Shiwei Zhan g
### **B Properties of non-orthogonal Slater determinants**

In Eq. (18), the operator ˆ *ϕ* *[†]* *m* *[≡]* [�] *i* *[c]* *i* *[†]* *[ϕ]* *[i,m]* [, with] *[ m]* [ taking an integer value among][ 1] *[,]* [ 2] *[, . . ., M]* [,]

creates an electron in a single-particle orbital *ϕ* *m* : ˆ *ϕ* *[†]* *m* *[|]* [0] *[⟩]* [=][ �] *i* *[ϕ]* *[i,m]* *[|][χ]* *[i]* *[⟩]* [. The content of the]

orbital can thus be conveniently expressed as an *N* -dimensional vector *{ϕ* 1 *,m* *, ϕ* 2 *,m* *, . . ., ϕ* *N,m* *}* .
The Slater determinant *|φ⟩* in Eq. (18) can then be expressed as an *N × M* matrix





 *.*




*Φ ≡*











*ϕ* 1 *,* 1 *ϕ* 1 *,* 2 *· · ·* *ϕ* 1 *,M*

*ϕ* 2 *,* 1 *ϕ* 2 *,* 2 *· · ·* *ϕ* 2 *,M*

... ... ...

*ϕ* *N,* 1 *ϕ* *N,* 2 *· · ·* *ϕ* *N,M*


Each column of this matrix represents a single-particle orbital that is completely specified by its

*N* -dimensional vector. For convenience, we will think of the different columns as all properly

orthonormalized, which is straightforward to achieve by, for example, modified Gram-Schmidt

(see e.g., [2,21]). For example the occupied manifold in a DFT solution forms a “wave function”

which is a Slater determinant.
A key property of Slater determinants is the *Thouless Theorem* : any one-particle operator *B* [ˆ]

of the form in Eq. (12), when acting on a Slater determinant, simply leads to another Slater

determinant [75], i.e.,

ˆ
*B|φ⟩* = ˆ *φ* *[′ †]* 1 *[φ]* [ˆ] *[′ †]* 2 *[· · ·]* [ ˆ] *[φ]* *[′ †]* *M* *[|]* [0] *[⟩≡|][φ]* *[′]* *[⟩]* (53)

with *φ* [ˆ] *[′ †]* *m* [=][ �] *j* *[c]* *[†]* *j* *[Φ]* *[′]* *jm* [and] *[ Φ]* *[′]* *[ ≡]* *[e]* *[U]* *[Φ]* [, where] *[ U]* [ is a square matrix whose elements are given by]

*U* *ij* and *B ≡* exp( *U* ) is therefore an *N ×* *N* square matrix as well. In other words, the operation
of *B* [ˆ] on *|φ⟩* simply involves multiplying an *N × N* matrix to the *N × M* matrix representing

the Slater determinant.

In standard quantum chemistry (QC) methods, the many-body ground-state wave function is

also represented by a sum of Slater determinants. However, there is a key difference between it

and the AFQMC representation. In QC methods, the different Slater determinants are orthogo
nal, because they are obtained by excitations based on a fixed set of orbitals (for instance, the

occupied and virtual orbitals from a reference calculation such as Hartree-Fock). In AFQMC,

the Slater determinants are non-orthogonal because they are generated by “rotating” (only) the

occupied orbitals through the operations in Eq. (53).

Several properties of non-orthogonal Slater determinants are worth mentioning. The overlap

between two of them is given by

*⟨φ|φ* *[′]* *⟩* = det( *Φ* *[†]* *Φ* *[′]* ) *.* (54)

We can define the expectation of an operator *O* [ˆ] with respect to a pair of non-orthogonal Slater

determinants

*⟨O* [ˆ] *⟩* *φφ* *′* *≡* *[⟨][φ]* *⟨φ* *[|]* *[O]* [ ˆ] *|φ* *[|][φ]* *[′]* *⟩* *[′]* *[⟩]* *[,]* (55)


-----

AF Q MC 6.25

for instance single-particle Green function *G* *ij* *≡⟨c* *i* *c* *[†]* *j* *[⟩]* *φφ* *′*

*G* *ij* *≡* *[⟨][φ][|][c]* *[i]* *[c]* *j* *[†]* *[|][φ]* *[′]* *[⟩]* = *δ* *ij* *−* [ *Φ* *[′]* ( *Φ* *[†]* *Φ* *[′]* ) *[−]* [1] *Φ* *[†]* ] *ij* *.* (56)
*⟨φ|φ* *[′]* *⟩*

Given the Green function matrix *G*, the general expectation defined in Eq. (55) can be computed

for most operators of interest. For example, we can calculate the expectation of a general twobody operator, *O* [ˆ] = [�] *ijkl* *[O]* *[ijkl]* *[ c]* *i* *[†]* *[c]* *[†]* *j* *[c]* *k* *[c]* *l* [, under the definition of Eq. (55)]

*⟨O* [ˆ] *⟩* *φφ* *′* = � *O* *ijkl* � *G* *[′]* *jk* *[G]* *il* *[′]* *[−]* *[G]* *[′]* *ik* *[G]* *[′]* *jl* � *,* (57)

*ijkl*

where the matrix *G* *[′]* is defined as *G* *[′]* *≡* *I −* *G* .

There are several generalizations of the formalism we have discussed which extend the capa
bility and/or accuracy of the AFQMC framework. These can be thought of as generalizing one

or both of the Slater determinants in Eqs. (54), (55), and (56). From the viewpoint of AFQMC,

the“bra” in these equations represents the trial wave function, and the “ket” represents the ran
dom walker:

*•* The first generalization is to replace *⟨φ|* by a projected Bardeen-Cooper-Schrieffer (BCS)

wave function, that is, to use a projected BCS as a trial wave function, which can be ad
vantageous for systems with pairing order. The corresponding overlap, Green functions,

and two-body mixed expectations have been worked out [54].

*•* The second is to have both *⟨φ|* and *|φ* *[′]* *⟩* in generalized HF (GHF) form, which is necessary

to treat systems with SOC. The required modification to the formalism outlined above is

given by [22].

*•* The third generalization is to have both sides in Hartree-Fock-Bogoliubov (HFB) form,

for example, to treat Hamiltonians with pairing fields. This will also be useful when

using AFQMC as an impurity solver in which the embedding induces pairing order. The

corresponding AFQMC formalism has been described [56].


-----

6.26 Shiwei Zhan g
### **References**

[1] S. Zhang, in W. Andreoni and S. Yip (eds.): *Handbook of Materials Modeling*

(Springer, Cham, 2018)

[2] S. Zhang, in E. Pavarini, E. Koch, and U. Schollw¨ock (eds.): *Emergent Phenomena in*

*Correlated Matter*, Modeling and Simulation, Vol. 3 (Forschungszentrum J¨ulich, 2013)

[3] S. Zhang, Comput. Phys. Commun. **127**, 150 (2000)

[4] Y.Y. He, M. Qin, H. Shi, Z.Y. Lu, and S. Zhang, Phys. Rev. B **99**, 045108 (2019)

[5] A. Szabo and N. Ostlund: *Modern quantum chemistry* (McGraw-Hill, New York, 1989)

[6] W. Kohn, Rev. Mod. Phys. **71**, 1253 (1999) and references therein

[7] R.M. Martin: *Electronic Structure: Basic theory and practical methods*

(Cambridge University Press, 2004)

[8] R. Car and M. Parrinello, Phys. Rev. Lett. **55**, 2471 (1985)

[9] M.H. Kalos, D. Levesque, and L. Verlet, Phys. Rev. A **9**, 2178 (1974)

[10] W.M.C. Foulkes, L. Mitas, R.J. Needs, and G. Rajagopal, Rev. Mod. Phys. **73**, 33 (2001)

and references therein

[11] D.M. Ceperley, Rev. Mod. Phys. **67**, 279 (1995) and references therein

[12] R. Blankenbecler, D.J. Scalapino, and R.L. Sugar, Phys. Rev. D **24**, 2278 (1981)

[13] G. Sugiyama and S.E. Koonin, Ann. Phys. (NY) **168**, 1 (1986)

[14] S. Zhang and H. Krakauer, Phys. Rev. Lett. **90**, 136401 (2003)

[15] K.P. Esler, J. Kim, D.M. Ceperley, W. Purwanto, E.J. Walter, H. Krakauer, S. Zhang,

P.R.C. Kent, R.G. Hennig, C. Umrigar, M. Bajdich, J. Kolorenc, L. Mitas, and

A. Srinivasan, J. Phys.: Conf. Series **125**, 012057 (2008)

[16] K.E. Schmidt and M.H. Kalos, in K. Binder (ed.): *Applications of the Monte Carlo Method*

*in Statistical Physics* (Springer, Heidelberg, 1984)

[17] E.Y. Loh Jr., J.E. Gubernatis, R.T. Scalettar, S.R. White, D.J. Scalapino, and R. Sugar,

Phys. Rev. B **41**, 9301 (1990)

[18] S. Zhang, in M.P. Nightingale and C.J. Umrigar (eds.): *Quantum Monte Carlo Methods in*

*Physics and Chemistry* (Kluwer Academic Publishers, 1999)

[19] S. Zhang, J. Carlson, and J.E. Gubernatis, Phys. Rev. B **55**, 7464 (1997)


-----

AF Q MC 6.27

[20] W.A. Al-Saidi, S. Zhang, and H. Krakauer, J. Chem. Phys. **124**, 224101 (2006)

[21] M. Motta and S. Zhang, Wiley Interdiscip. Rev. Comput. Mol. Sci. **8**, e1364 (2018)

[22] P. Rosenberg, H. Shi, and S. Zhang, J. Phys. Chem. Solids **128**, 161 (2019)

[23] M. Suewattana, W. Purwanto, S. Zhang, H. Krakauer, and E.J. Walter,

Phys. Rev. B **75**, 245123 (2007)

[24] W. Purwanto, H. Krakauer, Y. Virgus, and S. Zhang, J. Chem. Phys. **135**, 164105 (2011)

[25] S. Zhang, Phys. Rev. Lett. **83**, 2777 (1999)

[26] Y. Liu, M. Cho, and B. Rubenstein, J. Chem. Theory and Comput. **14**, 4722 (2018)

[27] J.W. Negele and H. Orland: *Quantum Many-Particle Systems*

(Perseus Books, Reading, MA, 1998)

[28] W.A. Al-Saidi, H. Krakauer, and S. Zhang, J. Chem. Phys. **126**, 194105 (2007)

[29] F. Ma, W. Purwanto, S. Zhang, and H. Krakauer, Phys. Rev. Lett. **114**, 226401 (2015)

[30] H. Koch, A.S. de Mer´as, and T.B. Pedersen, J. Chem. Phys. **118**, 9481 (2003)

[31] F. Aquilante, L. De Vico, N. Ferre, G. Ghigo, P. A Malmqvist, P. Neogrady, T. Pedersen, [˚]

M. Pitonak, M. Reiher, B. Roos, L. Serrano-Andres, M. Urban, V. Veryazov, and R. Lindh,

J. Comp. Chem. **31**, 224 (2010)

[32] J. Shee, E.J. Arthur, S. Zhang, D.R. Reichman, and R.A. Friesner,

J. Chem. Theory Comput. **14**, 4109 (2018)

[33] R. Baer, M. Head-Gordon, and D. Neuhauser, J. Chem. Phys. **109**, 6219 (1998)

[34] W. Purwanto and S. Zhang, Phys. Rev. A **72**, 053610 (2005)

[35] H. Shi and S. Zhang, Phys. Rev. B **88**, 125132 (2013)

[36] S. Zhang and D.M. Ceperley, Phys. Rev. Lett. **100**, 236404 (2008)

[37] S. Sorella, S. Baroni, R. Car, and M. Parrinello, Europhys. Lett. **8**, 663 (1989)

[38] M.H. Kalos and P.A. Whitlock: *Monte Carlo methods*, Vol I (Wiley, 1986)

[39] J.E. Hirsch, Phys. Rev. B **31**, 4403 (1985)

[40] Z.C. Wei, C. Wu, Y. Li, S. Zhang, and T. Xiang, Phys. Rev. Lett. **116**, 250601 (2016)

[41] S. Zhang and M.H. Kalos, Phys. Rev. Lett. **67**, 3074 (1991)

[42] S. Zhang, J. Carlson, and J.E. Gubernatis, Phys. Rev. Lett. **74**, 3652 (1995)


-----

6.28 Shiwei Zhan g

[43] M. Qin, H. Shi, and S. Zhang, Phys. Rev. B **94**, 235119 (2016)

[44] S.B. Fahy and D.R. Hamann, Phys. Rev. Lett. **65**, 3437 (1990)

[45] W. Purwanto and S. Zhang, Phys. Rev. E **70**, 056702 (2004)

[46] M. Motta and S. Zhang, J. Chem. Theory Comput. **13**, 5367 (2017)

[47] S. Zhang, H. Krakauer, W.A. Al-Saidi, and M. Suewattana,

Comput. Phys. Commun. **169**, 394 (2005)

[48] H. Hao, B.M. Rubenstein, and H. Shi, Phys. Rev. B **99**, 235142 (2019)

[49] J.P.F. LeBlanc, A.E. Antipov, F. Becca, I.W. Bulik, G.K.L. Chan, C.M. Chung, Y. Deng,

M. Ferrero, T.M. Henderson, C.A. Jim´enez-Hoyos, E. Kozik, X.W. Liu, A.J. Millis,

N.V. Prokof’ev, M. Qin, G.E. Scuseria, H. Shi, B.V. Svistunov, L.F. Tocchio, I.S. Tupitsyn,

S.R. White, S. Zhang, B.X. Zheng, Z. Zhu, and E. Gull, Phys. Rev. X **5**, 041041 (2015)

[50] B.X. Zheng, C.M. Chung, P. Corboz, G. Ehlers, M.P. Qin, R.M. Noack, H. Shi, S.R. White,

S. Zhang, and G.K.L. Chan, Science **358**, 1155 (2017)

[51] H. Shi, S. Chiesa, and S. Zhang, Phys. Rev. A **92**, 033603 (2015)

[52] H. Shi and S. Zhang, Phys. Rev. E **93**, 033303 (2016)

[53] E. Vitali, H. Shi, M. Qin, and S. Zhang, Phys. Rev. B **94**, 085140 (2016)

[54] J. Carlson, S. Gandolfi, K.E. Schmidt, and S. Zhang, Phys. Rev. A **84**, 061602 (2011)

[55] E. Vitali, P. Rosenberg, and S. Zhang, arXiv:1905.05012

[56] H. Shi and S. Zhang, Phys. Rev. B **95**, 045144 (2017)

[57] B.M. Rubenstein, S. Zhang, and D.R. Reichman, Phys. Rev. A **86**, 053606 (2012)

[58] Y.Y. He, H. Shi, and S. Zhang, arXiv e-prints arXiv:1906.02247 (2019)

[59] E.J. Landinez Borda, J. Gomez, and M.A. Morales, J. Chem. Phys. **150**, 074105 (2019)

[60] J. Shee, B. Rudshteyn, E.J. Arthur, S. Zhang, D.R. Reichman, and R.A. Friesner,

J. Chem. Theory Comput. **15**, 2346 (2019)

[61] J. Shee, E.J. Arthur, S. Zhang, D.R. Reichman, and R.A. Friesner, arXiv:1905.13316

[62] M. Motta and S. Zhang, J. Chem. Phys. **148**, 181101 (2018)

[63] M. Motta, J. Shee, S. Zhang, and G. Kin-Lic Chan, arXiv:1810.01549

[64] Y. Virgus, W. Purwanto, H. Krakauer, and S. Zhang, Phys. Rev. Lett. **113**, 175502 (2014)


-----

AF Q MC 6.29

[65] B. Eskridge, H. Krakauer, and S. Zhang, J. Chem. Theory Comput. **15**, 3949 (2019)

[66] J. Shee, S. Zhang, D.R. Reichman, and R.A. Friesner,

J. Chem. Theory Comput. **13**, 2667 (2017)

[67] F. Ma, S. Zhang, and H. Krakauer, Phys. Rev. B **95**, 165103 (2017)

[68] S. Zhang, F.D. Malone, and M.A. Morales, J. Chem. Phys. **149**, 164102 (2018)

[69] M. Motta, D.M. Ceperley, G.K.L. Chan, J.A. Gomez, E. Gull, S. Guo, C.A. Jim´enez
Hoyos, T.N. Lan, J. Li, F. Ma, A.J. Millis, N.V. Prokof’ev, U. Ray, G.E. Scuseria,

S. Sorella, E.M. Stoudenmire, Q. Sun, I.S. Tupitsyn, S.R. White, D. Zgid, and S. Zhang,

Phys. Rev. X **7**, 031059 (2017)

[70] R.J. Bartlett and M. Musiał, Rev. Mod. Phys. **79**, 291 (2007)

[71] T.D. Crawford and H.F. Schaefer III, Rev. Comput. Chem. **14**, 33 (2000)

[72] W. Purwanto, S. Zhang, and H. Krakauer, J. Chem. Phys. **130**, 094107 (2009)

[73] F. Ma, S. Zhang, and H. Krakauer, New J. Phys. **15**, 093017 (2013)

[74] H. Nguyen, H. Shi, J. Xu, and S. Zhang, Comput. Phys. Commun. **185**, 3344 (2014)

[75] D.R. Hamann and S.B. Fahy, Phys. Rev. B **41**, 11352 (1990)


-----
