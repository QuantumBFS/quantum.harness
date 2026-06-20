---
source: "https://arxiv.org/abs/cond-mat/9803107"
type: "arxiv"
canonical_id: "cond-mat/9803107"
title: "GREEN FUNCTION MONTE CARLO WITH STOCHASTIC RECONFIGURATION"
authors: "Sorella, S."
year: "1998"
venue: "Physical Review Letters"
arxiv_id: "cond-mat/9803107"
doi: "10.1103/PhysRevLett.80.4558"
full_text: yes
---

# GREEN FUNCTION MONTE CARLO WITH STOCHASTIC RECONFIGURATION

**Authors:** Sorella, S.

**Citation:** Physical Review Letters, vol. 80, pp. 4558-4561, 1998

**arXiv:** [cond-mat/9803107](https://arxiv.org/abs/cond-mat/9803107)

**DOI:** [10.1103/PhysRevLett.80.4558](https://doi.org/10.1103/PhysRevLett.80.4558)

## Abstract

A new method for the stabilization of the sign problem in the Green Function Monte Carlo technique is proposed. The method is devised for real lattice Hamiltonians and is based on an iterative ''stochastic reconfiguration'' scheme which introduces some bias but allows a stable simulation with constant sign. The systematic reduction of this bias is in principle possible. The method is applied to the frustrated J1-J2 Heisenberg model, and tested against exact diagonalization data. Evidence of a finite spin gap for J2/J1 >~ 0.4 is found in the thermodynamic limit.

## Full Text

## Green Function Monte Carlo with Stochastic Reconfiguration

Sandro Sorella


Istituto Nazionale di Fisica della Materia and International School for Advanced Studies Via


Beirut 4, 34013 Trieste, Italy


(November 26, 2024)

## Abstract


A new method for the stabilization of the sign problem in the Green Function


Monte Carlo technique is proposed. The method is devised for real lattice


Hamiltonians and is based on an iterative ”stochastic reconfiguration” scheme


which introduces some bias but allows a stable simulation with constant sign.


The systematic reduction of this bias is in principle possible. The method is


applied to the frustrated J1 − J2 Heisenberg model, and tested against exact


diagonalization data. Evidence of a finite spin gap for J2/J1 >∼ 0.4 is found


in the thermodynamic limit.


02.70.Lq,75.10.Jm,75.40.Mg


Typeset using REVTEX


1


As well known the Green Function Monte Carlo method (GFMC) allows to obtain the


exact ground state properties of a many body hamiltonian with a statistical method. One of


the most severe restriction is that only positive definite Green function GF can be sampled,


otherwise the method is facing the well known ”sign problem”. Approximate techniques like


the fixed node approximation (FN) have been developed to circumvent the sign problem


but at the very least they cannot be systematically improved to achieve the exact answer


within statistical errors. This property has severely limited the applications of GFMC to


fermions and frustrated boson models. In this letter I propose a new approach to stabilize


the sign problem, the GFMC with stochastic reconfiguration (GFMCSR), which will be


shortly described below, revisiting also the basic steps of the standard GFMC on a lattice.


[1,2]


In order to filter out the ground state of a given lattice hamiltonian H the standard


power method may be applied iteratively :


       
```
                                       ′ ′
```
ψn+1(x [′] ) = (Λδx,x − Hx,x)ψn(x) (1)

x

```
                                                                   ′
```

where x represents conventionally the index of a complete basis |x >, Hx,x being the


corresponding matrix elements of the hamiltonian which in the following are assumed real,


and Λ is a positive constant that allows the convergence of ψn to the ground state ψ0(x), for


large n. In numerical calculations of interesting lattice hamiltonians the dimension of the


basis grows exponentially with the size and the particle number, though the matrix itself

```
                                 ′
```

is very sparse and all its elements Hx,x, for given x, can be generally computed even for


large system size. In this case an exact application of (1) is impossible unless for few steps.


A way out is to use a stochastic approach, like GFMC,which is particularly simple on a


lattice.


In order to implement stochastically the iteration (1) the corresponding lattice GF

```
                               ′ ′ ′
```

Gx,x = Λδx,x − Hx,x (2)


may be decomposed in the following way:


2


```
                                ′ ′ ′
```

Gx,x = sx,xpx,xbx (3)

```
        ′
```

where px,x is a normalized stochastic matrix, bx ≥ 0 is a normalization constant and the

```
                                                                  ′ ′
```

matrix s takes into account the sign of the GF. The typical choice is to take px,x = |Gx,x|/bx

, bx = [�] x `[′]` [ |][G] x `[′]`,x [|][ and][ s] x `[′]`,x [= sgn][ G] x `[′]`,x [, which is identically one if there is no sign problem.]


In the GFMC method the so called ”walker“ is defined by a weight w and a configuration


x.. At a given iteration n the walker is assumed to sample statistically the state ψn(x) in


Eq.(1), in the sense that the probability Pn(w, x) to have the walker with weight w (not

                                  restricted to be positive) in a given configuration x satisfies: dwPn(w, x)w = ψn(x). Then


the matrix multiplication (1) can be implemented statistically, in the precise sense that

dwPn+1(w, x)w = ψn+1(x), by the following three steps:


1. scale the walker weight by bx: w [′] = bxw.


2. select randomly a new configuration x [′] according to the stochastic matrix px′, x.


3. finally multiply the weight of the walker by the sign factor sx′, x: w [′] → w [′] sx′, x


(MI)


In principle the previous Markov process determines, for large n, the ground state of H even


with a single walker. In practise it is convenient to use a large number M of walkers, which



I indicate by (wj, xj) j = 1, · · · M, shorthand in the following also by vector notations w, x.



< [�]
If there is sign problem the average walker sign < s >n= [�]



<

j [w][j][>][n]
< [�]

[|][w][j][|][>]



j

j [|][w][j][|][>][n][ decreases exponen-]



tially to zero as the Markov iteration MI is repeatedly applied and it is basically impossible


to reach a reasonably large value of n.


Recently a remarkable progress in GFMC on a lattice was the extension of the FN to this


case. The method is based on a definition of an effective GF G [f] x `[′]`,x [which is always positive]


definite but yields a good variational estimate of the energy. For later purposes we define


this effective GF in a slightly different way, by introducing a parameter γ: which allows to


sample also the negative elements of the GF :


3


−Hx′, x if Hx′, x ≤ 0

γHx′, x if Hx′, x > 0

Λ − Hx,x − (1 + γ)Vsf(x) if x = x [′]


̸



G [f] x `[′]`,x [=]


̸









̸



(4)


̸



where the diagonal sign-flip contribution is given by [3,4]:


        Vsf(x) = ′ (5)

Hx, x
Hx′, x>0,x `[′]` ̸=x


For γ = 0 the usual formulation [4] is recovered, whereas for γ > 0 [5] the crossing to the

```
                                                                  ′ ′
```

negative sign region is allowed so that the exact GF can be written as Gx,x = sx,xG [f] x `[′]`,x


Gx `′`,x
```
       ′
```
where sx,x is finite and non zero and is determined by the ratio G [f] with G and G [f] given
x `[′]`,x

by Eq.(2) and Eq.(4) respectively. The value of the constant γ necessary to cross the ”nodal


surface” was chosen to be 1/2 in all forthcoming applications.

```
                                                  ′
```

In the basic decomposition (3) the stochastic matrix px,x = G [f] x `[′]`,x [/b][x][ and the normaliza-]

tion coefficient bx = [�] x [′][ G] x [f] `[′]`,x [are instead determined only by][ G][f] [.]

```
                                  ′
```

By omitting the last step w [′] → wsx,x in the Markov iteration process MI, the state ψn


is indeed propagated trough the positive GF G [f] . The main property used in the following


is that at any Markov iteration n we can have a statistic knowledge of both the state


ψn(x) obtained with the exact GF and of ψn [f] [(][x][) obtained instead with the approximate but]

positive definite one G [f] . To this purpose the j [th] walker is defined by two weights wj [f] [and]


wj corresponding to the propagation of the walker by G [f] and G respectively. These weights


act on the same configuration xj. Hereafter the vector w represents therefore a shorthand


notation for the 2M components wj, wj [f] [for][ j][ = 1][, . . .M][.]


The walker vector w, x allows to determine statistically the state:



̸


    
   ψn(x) = d[w]

x



̸


  Pn(w, x) δx,xj wj/M (6)

j



̸


and analogously ψn [f] [(][x][) by replacing the weights][ w][j][ with the positive ones][ w] j [f] [in the previous]


equation. In this way the configurations generated by the described Markov process MI,


if weighted with the constants wj [f] [, are distributed for large][ n][, according to the variational]


4


state corresponding to G [f] . This is a reasonable variational wavefunction (WF), which will


be the initial approximation to which systematic corrections will be applied, as described


later on.


Apart for the previous technical definitions, we can explain in few words the basic idea


used for the stabilization of the sign problem, The iteration MI converges to the ground


state, but due to the sign problem, only few iterations can be performed with a reasonable


statistical accuracy. However, the representation of the state ψn(x) in terms of the walker


population xj, wj is not unique. In fact it is perfectly possible to represent the same state


ψn(x) either with a walker population with very small average sign or with a one with a very


large average sign. If such reconfigurations are possible each few kp steps, the average sign


may be stabilized to a large value during the iteration (1) and there will be no difficulty to


sample the ground state for n →∞, with no sign problem.


I will show that this reconfiguration is well defined and indeed possible. The set of M


walkers (w, x) are defined via their probability function Pn(w, x) which in turn defines the


state ψn(x) by Eq.(6). The task is to change Pn onto a new probability distribution Pn [′]


corresponding to a steadily high sign for the walker population. This without changing the


information content, the state ψn(x).


Let us define the new state ψn [′] [(][x][), as the one obtained by averaging over][ P][ ′] n [in Eq.(6),]

then the reconfiguration is exact if Pn [′] [is such that:]


ψn [′] [(][x][) =][ ψ][n][(][x][) for all][ x] (7)


In general it is difficult or impractical to realize all these conditions (7) as their number


equals the dimension of the Hilbert space. I consider therefore a set of operators O [k], k =


1, · · · p << M and require only p + 1 stochastic reconfiguration conditions:







Ox [k] `[′]`,x [ψ][n][(][x][)] (8)
x `[′]`,x




- 
Ox [k] `[′]`,x [ψ] n [′] [(][x][) =]
x `[′]`,x x `[′]`,x




           -            for k = 1, · · · p, beyond the normalization one x [ψ][′][(][x][) =] x [ψ] n [(][x][)]


The previous equations (8) mean that the so called ”mixed averages” of the operators


O [k] coincide before and after the reconfiguration. [6]


5


The main idea of this work is that these p + 1 conditions can be fulfilled exactly (for


chosen operators) by defining the reconfiguration in the following form:




j [|][p] xj [|][δ] x [′] i [, x][j]

 - δ(wi [′] [−]
j [|][p] xj [|]




j [w] j
i [)][ δ][(][w] i [f][ ′] −|wi [′][|][)]
βM [sgn][ p][x] `[′]`






 [P][n][(][w, x][)]


(9)




      
    Pn [′] [(][w][′][, x][′][) =] d[w]

x



�M


i = 1















where β =




- j [p][xj]



j

j [|][p][xj] [|][ is the average sign after the reconfiguration which is supposed to be much]



higher to stabilize the process. The new configurations x [′] i [are taken randomly among the]

old ones {xj}, according to the table pxj, defined below.. The positive weights wj [f] [represent]


a good starting point for the definition of a reconfiguration with large β. Though there is


some arbitrariness in the definition of the coefficients pxj, a simple and convenient choice is:


        pxj = wj [f] [(1 +] αk(Oj [k] [−] [O][¯] f [k][))]

k







where O [¯] f [k] [=]



j [w] j [f] [O] j [k]




j j are the averages over the positive weights wj [f] [of the mixed estimates]

j [w] j [f]




  Oj [k] [=] x `[′]` [ O] x [k] `[′]`,xj [corresponding to the operator][ O][k][ and the configuration][ x][j][.]



Then, in order to satisfy the WF conditions (8), by using the definition (9), it is sufficient


that the coefficients pxj satisfy the following Markovian conditions:







J
j [p][x][j] [O][k]








=
j [p][x][j]



j
j [w][j][O][k]




(10)
j [w][j]



which in turn determine the unknown variables αk, for k = 1, · · · p, for given w, x.


For hamiltonian not affected by the sign problem (G [f] = G αk = 0 and β = 1) this


reconfiguration was already used to control the walker population size without introducing


any source of systematic error. [7] The present more general reconfiguration (9) can be easily


and efficiently implemented in a similar way.


Obviously the reconfiguration conditions (8) are equivalent to the exact ones (7), when the


number p of linearly independent operators considered in (8) is equal to the large dimension


of the Hilbert space. An important applicative issue is whether GFMCSR converges, within


a reasonable accuracy, even with a small number p of meaningful operators O [k] .


6


We consider the frustrated J1 − J2 Heisenberg spin 1/2 model on a finite square lattice


with L sites and periodic boundary conditions (tilted by 45 degrees for the L = 32 size only).


The model hamiltonian is determined by an antiferromagnetic coupling J1 > 0 between


nearest neighbor spins and a frustrating coupling J2 > 0 between next neighbor ones. [8–10]


In all forthcoming examples the stochastic reconfigurations were applied frequently enough


to maintain the average sign before reconfiguration ∼ 0.8, condition that minimize the


statistical fluctuations. Moreover in each simulation it is important to work with a fairly


large number of walkers, since in the M →∞ limit, the GFMCSR results are practically


independent of the frequency of reconfigurations, as well as the overall constant energy shift


Λ.


The accuracy of GFMCSR for the ground state is displayed in Tab.I, and compared


with other methods. The variational WF (used also for GFMC importance sampling [6])


contains a Jastrow like factor



Exp( [η]

2





v(R − R [′] )SR [z] [S] R [z] `[′]` [)]
R,R `[′]`



to mimic the interaction between the spins SR [z] [=][ ±][1][/][2 at sites][ R, R][′][, where][ η][ is a variational]


parameter and the two-spin interaction v can be derived by using the method described in


[11], yielding an explicit Fourier transform for v:



vq/2 = 1 −







- [2][ −] [σ][(1][ −] [cos][ q][x][ cos][ q][y][) + cos][ q][x][ + cos][ q][y]

2 − σ(1 − cos qx cos qy) − cos qx − cos qy



with σ = 2J2/J1. This potential is not defined for J2/J1 = 1/2, and in such case I have chosen

                     to work with σ = 0.8. Restriction to any subspace of total spin projection Stot [z] [=] R [S] R [z]

allows to evaluate the spin gap by performing two simulations for Stot [z] [= 0 and][ S] tot [z] [= 1.]


Henceforth I will use the the same potential v in both subspaces, by optimizing η for the


Stot [z] [= 0 energy.]


As shown in the table the accuracy of the variational WF is rather poor, and is con

siderably improved by the FN, at least for small J2. This kind of accuracy is however not


enough to determine the rapid increase of the spin gap as J2/J1 approaches the value 1/2 of


7


the classical transition. Instead, as shown in Fig.(1) the GFMCSR allows to achieve a good


accuracy also on this delicate quantity by considering in the reconfigurations only the en
ergy and the spin structure factor Sq [z] [=][ �] R,R `[′]` [ e][iq][(][R][−][R] `[′]` [)][S] R [z] [S] R [z] `[′]` [ symmetrized over all directions]


and for all non equivalent wavevectors q. Remarkably also mixed averages of correlation


functions that are not included in such reconfiguration conditions (8) are also significantly


improved (see table).


The way GFMCSR reaches the large n limit (at fixed number of operators p) is displayed


in Fig.(2) where the initial n = 0 distribution was obtained by the FN for γ = 0. For fixed p


the algorithm is Markovian and reaches an equilibrium distribution for n →∞, independent


of the initial one (see example in Fig.2 where p was changed at the iteration indicated by the


arrow), this in turn will converge to the ground state distribution for large p. A comparison


with the standard ”release nodes” estimate is also shown in the picture. It is clear that


there is no hope to obtain meaningful results in this case by the direct sampling of the sign.


On the contrary this method looks very stable and, though approximate, a convergence to


a reasonable accuracy is obtained even with a very small number of operators, compared to


the dimension of the Hilbert space.


The data shown in the table and in the picture indicate that the accuracy of GFMCSR


may become rather size independent with a relatively small increase of the operator number


p. The error to work at finite small p is systematic. Thus there is a considerable cancellation


of this error for the determination of the spin gap displayed in Fig.(1).


The calculation was therefore extended to the large size system up to L = 100 where exact


diagonalization is not possible. The spin gap as a function of the system size is displayed


in Fig.(3). This figure is consistent with the opening of a finite spin gap for J2/J1 ≥∼ 0.4.


This gap is certainly not an artifact of the variational WF, which is obviously gapless, as


also confirmed numerically in the same figure. The present numerical results confirm that


the transition to a spin liquid state with a finite spin gap but no classical order parameter


should be close to J2/J1 = 0.4. [10]


This work was supported in part by INFM (PRA HTSC) and CINECA grant.


8


## REFERENCES


[1] N. Trivedi, D. Ceperley, Phys. Rev. B 41, 4552 (1990)


[2] K. Runge, Phys. Rev. B 44, 122252 (1992)


[3] H. van Bemmel et al. Phys. Rev. Lett. 72, 2442 (1994).


[4] D. ten Haaf et al. Phys. Rev. B 51, 13039 (1995).


[5] It is possible to prove that the method is variational also for γ > 0, with a simple


extension of the proof in [4].


[6] All the analysis remains unchanged if a guiding function ψG(x) is used for importance

```
                                                  ′
```

sampling. The matrix elements of all the operators Ox,x (including the GF) have to be

```
                         ′ ′
```

accordingly changed : Ox,x → ψG(x [′] )Ox,x/ψG(x).


[7] M. Calandra and S. Sorella, to appear in Phys. Rev. B .


[8] E. Dagotto, A. Moreo Phys. Rev. Lett. 63, 2148 (1989).


[9] T. Nakamura et al. J. Phys. Soc. Japan 61, 3494 (1992).


[10] J. Schulz et al. J. de Phys. 6, 675 (1996)..


[11] F. Franjic, S. Sorella, Prog. Theor. Phys. 97, 399 (1997)


9


FIGURES


FIG. 1. Estimate of the spin gap for several methods: variational (empty triangles), FN


(empty squares), GFMCSR p = 1 (empty dots), GFMCSR (full dots) as in the table for L = 16


(upper points) and L = 32 (lower ones). The exact results are connected by continuous lines.


10



![](.figures/arxiv__cond-mat-9803107/cond-mat-9803107.pdf-9-0.png)
![](.figures/arxiv__cond-mat-9803107/cond-mat-9803107.pdf-10-0.png)

FIG. 2. Energy per site vs. n for GFMCSR with p = 1 (upper curve to the left of the arrow)


and p = 9 (remaining curves). The triangles represent the standard method with sign problem,


i.e. with large error bars already for n > 15.


11


![](.figures/arxiv__cond-mat-9803107/cond-mat-9803107.pdf-11-0.png)

FIG. 3. Size scaling of the spin gap. The dashed lines are linear fit of the GFMCSR data


with p = 9, 14, 20 for L = 36, 64, 100 respectively. Lower curves are the variational estimates and


continuous lines are guides to the eye.


12


TABLES


J2/J1 L η % VMC % FN % SRe % SR


0.1 16 1.2 2.84 (2.2) 0.17 (0.1) -0.03 (0.0) 0.02 (0.0)


0.2 16 1.15 2.80 (2.5) 0.41 (0.4) 0.00 (0.2) 0.03 (0.0)


0.3 16 1.1 3.25 (2.5) 0.87 (0.7) 0.12 (0.8) 0.05 (0.1)


0.4 16 0.8 3.38 (2.4) 1.76 (3.2) 0.56 (4.5) 0.26 (0.2)


0.5 16 0.85 5.65 (10.9) 3.84 (8.9) 2.08 (8.9) 0.66 (1.1)


0.1 32 1 1.55 (2.5) 0.22 (0.3) 0.05 (0.1) 0.02 (0.0)


0.2 32 1 1.78 (2.5) 0.48 (0.6) 0.15 (0.6) 0.05 (0.1)


0.3 32 1 2.23 (2.1) 0.85 (0.91) 0.30 (1.4) 0.10 (0.0)


0.4 32 0.8 3.07 (4.0) 1.61 (3.1) 0.26 (5.6) 0.21 (0.1)


0.5 32 0.9 4.51 (10.0) 2.92 (7.2) 1.52 (7.7) 0.46 (0.9)


0.1 36 1.1 1.86 (2.8) 0.21 (0.2) 0.1 (0.12) 0.02 (0.1)


0.2 36 1.1 2.22 (2.8) 0.47 (0.5) 0.16 (0.5) 0.07 (0.1)


0.3 36 1 2.31 (2.8) 0.91 (1.4) 0.35 (2.0) 0.11 (0.1)


0.4 36 0.8 3.34 (5.5) 1.74 (4.5) 0.51 (6.8) 0.26 (0.3)


0.5 36 0.9 5.09 (14.4) 3.34 (11.1) 1.83 (11.8) 0.62 (2.1)


TABLE I. Percentage error of the energy (square antiferromagnetic order parameter ⃗m [2] as in


[7]) for the various methods: variational (VMC), fixed node (FN), p = 1 GFMCSR (SRe) with the


energy alone and p = 5, 8, 9 GFMCSR estimate (SR) with the energy and Sq [z] [for][ L][ = 16][,][ 32][,][ 36.]


The statistical errors are about one place in the last digit.


13
