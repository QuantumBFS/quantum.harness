// Technology assessment — open-source quantum many-body computation software
// Generated 2026-06-20 from .knowledge/literature/software (sci-brain survey pipeline).
// Compile: typst compile 2026-06-20-many-body-software-review.typ

#set page(margin: 1.6cm)
#set text(size: 10pt)
#set par(justify: true, leading: 0.62em)
#set heading(numbering: "1.")

#let title = [Open-Source Software for Quantum Many-Body Computation]
#let authors = ["survey review draft"]

#show link: set text(fill: blue.darken(30%))

// ---- reusable helpers ---------------------------------------------------

#let section_box(title, body, fill: rgb("f7f8fc"), stroke: rgb("d9deeb")) = rect(
  width: 100%, inset: 10pt, radius: 6pt, fill: fill, stroke: stroke,
  [#strong[#title] #v(0.3em) #body],
)

#let stage(name, body, fill) = rect(
  width: 100%, inset: 7pt, radius: 5pt, fill: fill, stroke: rgb("c7cfe0"),
  align(center)[#text(weight: "semibold", size: 9pt)[#name] #v(0.2em) #text(size: 8pt)[#body]],
)

#let proscons(pros, cons) = grid(
  columns: (1fr, 1fr), gutter: 0.6em,
  rect(width: 100%, inset: 7pt, radius: 5pt, fill: rgb("eef6ef"), stroke: rgb("bcd9c4"))[
    #text(weight: "semibold", fill: green.darken(30%))[Strengths]
    #pros
  ],
  rect(width: 100%, inset: 7pt, radius: 5pt, fill: rgb("fbecec"), stroke: rgb("e3c6c6"))[
    #text(weight: "semibold", fill: red.darken(20%))[Limitations]
    #cons
  ],
)

// adaptive cross-approach matrix (custom columns for this field)
#let compare_table(rows) = table(
  columns: (16%, 26%, 16%, 26%, 16%),
  stroke: (x, y) => if y == 0 { 0.8pt + black } else { 0.4pt + rgb("d7dbe6") },
  inset: 6pt,
  table.header(
    [#strong[Approach]], [#strong[Representative codes]], [#strong[Reach]],
    [#strong[Key limitation]], [#strong[Best-fit use]],
  ),
  ..rows.flatten(),
)

#let problem_table(rows) = table(
  columns: (5%, 24%, 38%, 22%, 11%),
  stroke: (x, y) => if y == 0 { 0.8pt + black } else { 0.4pt + rgb("d7dbe6") },
  inset: 6pt,
  table.header(
    [#strong[No.]], [#strong[Problem]], [#strong[Why it matters]], [#strong[Who could solve it]], [#strong[Urgency]],
  ),
  ..rows.flatten(),
)

// ---- title --------------------------------------------------------------

#heading(numbering: none)[#title]

#align(center)[
  #text(size: 12pt, weight: "semibold")[State-of-the-Art Review]
  #v(0.25em)
  #text(fill: gray.darken(20%))[#authors]
  #v(0.25em)
  #text(fill: gray.darken(10%))[Generated 2026-06-20 from a 22-package knowledge base.]
]

#v(0.9em)

#section_box(
  [Scope],
  [This report assesses the landscape of #emph[popular open-source software] for computing
  ground-state and finite-temperature properties of quantum many-body lattice models. It is
  written for a researcher or team choosing a code, or onboarding to the field, and is organized
  #emph[by technical approach] (method family): one code is rarely "best" — the right tool is set
  by the model, dimensionality, and target observable. It covers 22 actively-maintained packages
  with a published release paper; it deliberately excludes density-functional / electronic-structure
  suites, closed-source codes, and one-off group scripts. State of the art and trade-offs are given
  #emph[inside each approach], not as global sections.],
)

= What and Why

The quantum many-body problem is the task of computing properties of interacting quantum systems —
spins, bosons, or fermions on a lattice — whose Hilbert space grows #emph[exponentially] with system
size. A modest 50-site spin-½ model already has $2^50 approx 10^15$ basis states, so brute-force
storage of the wavefunction is impossible beyond ~20 sites. Every practical method is therefore a
#emph[controlled compression] of that exponential object: a tensor-network ansatz, a stochastic
sample, a variational parametrization, or a self-consistent local approximation. Many-body computation
software packages each implement one such compression, plus the lattice/Hamiltonian bookkeeping,
symmetry handling, and convergence diagnostics needed to use it reliably.

This matters now because the field has shifted from private, per-group Fortran/C++ codes to a shared,
documented, #emph[citable] open-source ecosystem. Reproducibility pressure, the rise of
publication venues for research software (e.g. SciPost Physics Codebases), and a wave of
high-productivity numerical languages have lowered the barrier to entry: a graduate student today
runs DMRG @fishman_2020_itensor or neural-network states @vicentini_2021_netket in a notebook rather
than porting a legacy code. A recent survey of the DMRG-codes landscape documents both the breadth
of this ecosystem and its growing pains @sehlstedt_2025_software.

How it differs from the prior approach: instead of a single monolithic solver, the modern stack is a
set of #emph[method-specialized] libraries — DMRG/tensor networks for 1D and gapped 2D systems,
quantum Monte Carlo for sign-problem-free regimes, exact diagonalization for small frustrated
clusters, variational/neural states for 2D frustrated and continuous-time dynamics, and dynamical
mean-field theory for correlated electronic structure. The clear recent trend is toward
#emph[Julia + automatic differentiation] and #emph[Python + JAX], which wrap or replace older
compiled cores while keeping their performance.

#v(0.5em)
#figure(
  grid(
    columns: (22%, 4%, 70%),
    align: horizon,
    stage([Exponential\ Hilbert space], [$dim = d^N$, intractable], rgb("fbecec")),
    align(center + horizon)[#text(size: 14pt)[→]],
    grid(
      columns: (1fr, 1fr, 1fr, 1fr, 1fr), gutter: 4pt,
      stage([Tensor\ networks], [low entanglement], rgb("eef3ff")),
      stage([Exact\ diag.], [small clusters], rgb("eef3ff")),
      stage([Quantum\ Monte Carlo], [sign-free sampling], rgb("e9f7ee")),
      stage([Variational /\ neural states], [parametrized $psi$], rgb("e9f7ee")),
      stage([DMFT /\ impurity], [local self-energy], rgb("fdf2e9")),
    ),
  ),
  caption: [The shared problem (left) and the five method families that compress it (right). Each
  family is implemented by one or more of the surveyed packages; none dominates across all regimes.],
)

= Technical Approaches

The ecosystem clusters into five method families. A clear generational shift runs through all of
them: compiled C++/Fortran cores from 2011–2017 have been progressively wrapped or replaced by
Julia and Python+JAX packages from ~2020 onward, increasingly published through SciPost Physics
Codebases.

#figure(
  grid(
    columns: (30%, 4%, 30%, 4%, 30%),
    align: horizon,
    stage([2011–2017 · compiled cores],
      [ALPS, TRIQS, HΦ, mVMC, iQIST (C++/Fortran)], rgb("eef3ff")),
    align(center + horizon)[#text(size: 13pt)[→]],
    stage([2016–2019 · Python front-ends],
      [QuSpin, NetKet, quimb], rgb("eef6ef")),
    align(center + horizon)[#text(size: 13pt)[→]],
    stage([2020–2025 · Julia / JAX + autodiff],
      [ITensors.jl, NetKet 3, jVMC, PEPSKit, SmoQyDQMC, XDiag, TensorKit], rgb("fdf2e9")),
  ),
  caption: [Field landscape: from monolithic compiled solvers to composable autodiff-native libraries.],
)

== Tensor networks (DMRG / MPS and PEPS)

*What it is.* Tensor-network methods represent the wavefunction as a contraction of small tensors
whose bond dimension $chi$ caps the captured entanglement. In one dimension the matrix-product-state
(MPS) ansatz with the density-matrix renormalization group (DMRG) is essentially exact for gapped
systems; in two dimensions the projected-entangled-pair-state (PEPS) generalization trades the
clean 1D algorithms for harder contraction and optimization.

*State of the art.* For 1D and quasi-2D ground states and dynamics, ITensor (C++ and Julia) is the
general-purpose workhorse @fishman_2020_itensor, with TeNPy the leading Python alternative
@hauschild_2024_tensor and quimb adding large-scale, contraction-path-optimized tensor networks
@gray_2018_quimb. block2 pushes high-performance DMRG with a strong quantum-chemistry, finite-$T$,
and dynamics focus @zhai_2023_block. The Julia stack is now unified by TensorKit.jl, a symmetric-tensor
backend supporting Abelian, non-Abelian, and anyonic symmetries @devos_2025_tensorkit. In 2D, the
current reference is automatic-differentiation–based infinite-PEPS optimization (CTMRG environments
with reverse-mode AD), as implemented in the PEPSKit.jl line of work @naumann_2023_introduction. A
2025 survey maps the full DMRG-codes ecosystem and its maturity spread @sehlstedt_2025_software.

#proscons(
  list(
    [Near-exact, variational (true energy upper bound) for 1D/gapped systems, with controlled error via $chi$ @fishman_2020_itensor.],
    [No sign problem — works for frustrated and fermionic models inaccessible to QMC @hauschild_2024_tensor.],
    [Mature, well-documented 1D tooling with symmetry support across languages @devos_2025_tensorkit.],
  ),
  list(
    [Cost grows steeply with entanglement ($~chi^3$); 2D and critical systems need large $chi$ @sehlstedt_2025_software.],
    [PEPS optimization (gauge fixing, CTMRG convergence, AD stability) is far less turnkey than 1D DMRG @naumann_2023_introduction.],
    [Real-time dynamics is limited by entanglement growth @hauschild_2024_tensor.],
  ),
)

== Exact diagonalization

*What it is.* Exact diagonalization (ED) builds the Hamiltonian matrix in a symmetry-reduced basis
and extracts low-lying eigenpairs (Lanczos) or the full spectrum. It is the unbiased reference
method — no ansatz, no sign problem — but limited to small clusters by the exponential basis size.

*State of the art.* QuSpin is the most widely used package for ED and quantum dynamics of spin, boson,
and fermion lattices, with a Python interface and extensive symmetry support @weinberg_2016_quspin.
XDiag (C++ core with a Julia wrapper) pushes the size frontier through symmetry-adapted bases and
sublattice coding @wietek_2025_xdiag. HΦ adds full diagonalization and thermal-pure-quantum (TPQ)
sampling for finite-temperature properties of Hubbard, Heisenberg, and Kondo models
@kawamura_2017_quantum. QuTiP, though built for open-system dynamics, is a common choice for
small-system ED and Hamiltonian construction @johansson_2011_qutip.

#proscons(
  list(
    [Unbiased and exact — the gold-standard benchmark for other methods @weinberg_2016_quspin.],
    [No sign problem; handles arbitrary frustration, disorder, and long-range terms @wietek_2025_xdiag.],
    [Gives the full spectrum / dynamical correlators and finite-$T$ via TPQ @kawamura_2017_quantum.],
  ),
  list(
    [Exponential memory/time — practically capped near 40–50 spin-½ sites even with symmetries @wietek_2025_xdiag.],
    [Finite-size effects dominate; extrapolation to the thermodynamic limit is indirect @weinberg_2016_quspin.],
  ),
)

== Quantum Monte Carlo

*What it is.* Quantum Monte Carlo (QMC) maps the quantum partition function to a classical
statistical sum and samples it stochastically — worldline / stochastic-series-expansion for spins and
bosons, or determinant / auxiliary-field for fermions. It scales polynomially and reaches large
sizes, but is restricted to models without a fermion (or frustration) sign problem.

*State of the art.* ALPS is the historical meta-framework bundling loop/SSE/worm QMC alongside ED and
DMRG @bauer_2011_alps. ALF provides finite-temperature and projective auxiliary-field (determinant)
QMC for interacting fermions @bercx_2017_alf. SmoQyDQMC.jl is a modern Julia determinant-QMC code for
Hubbard and electron–phonon models, including anharmonic and acoustic phonons via hybrid Monte Carlo
@cohenstead_2023_smoqydqmc. DSQSS implements worldline / directed-loop QMC for spin and Bose-Hubbard
systems at finite temperature @motoyama_2020_dsqss.

#proscons(
  list(
    [Polynomial scaling — reaches thousands of sites, enabling thermodynamic-limit extrapolation @bercx_2017_alf.],
    [Numerically exact (statistical errors only) for sign-free models @motoyama_2020_dsqss.],
    [Natural finite-temperature access @cohenstead_2023_smoqydqmc.],
  ),
  list(
    [Fermion / frustration sign problem makes doped and frustrated models exponentially hard @bercx_2017_alf.],
    [Real-frequency dynamics needs ill-posed analytic continuation @bauer_2011_alps.],
    [Autocorrelation and equilibration can be costly near critical points @motoyama_2020_dsqss.],
  ),
)

== Variational Monte Carlo and neural quantum states

*What it is.* Variational Monte Carlo (VMC) optimizes a parametrized trial wavefunction by sampling.
Neural quantum states (NQS) replace the traditional Jastrow/pair-product form with a neural network,
giving a flexible ansatz whose parameters are trained by stochastic reconfiguration or gradient
descent. This family targets exactly the frustrated 2D and fermionic regimes where QMC fails and
tensor networks strain.

*State of the art.* NetKet (Python, JAX) is the dominant NQS toolbox for ground states and dynamics,
with composable network architectures and autodiff @vicentini_2021_netket. jVMC offers a
GPU-accelerated, AD-based VMC implementation in the same JAX ecosystem @schmitt_2021_jvmc. mVMC is the
established many-variable VMC code for interacting fermions, optimizing $10^4$+ parameters via
stochastic reconfiguration for Hubbard, Heisenberg, and Kondo models @misawa_2017_mvmc.

#proscons(
  list(
    [Flexible ansatz reaches 2D frustrated and fermionic systems beyond QMC and PEPS @vicentini_2021_netket.],
    [Variational upper bound; GPU/autodiff-native and scalable @schmitt_2021_jvmc.],
    [Mature fermionic VMC with many-parameter optimization @misawa_2017_mvmc.],
  ),
  list(
    [Optimization is non-convex; convergence and reliability diagnostics lag tensor networks @vicentini_2021_netket.],
    [Expressivity-vs-cost trade-off is poorly characterized; results can be hard to certify @schmitt_2021_jvmc.],
  ),
)

== Dynamical mean-field theory and impurity solvers

*What it is.* Dynamical mean-field theory (DMFT) maps a correlated lattice model onto a self-consistently
determined quantum impurity embedded in a bath, capturing local quantum fluctuations exactly. The
computational core is the impurity solver — most often continuous-time quantum Monte Carlo (CT-HYB).
DMFT is the workhorse for correlated electronic structure and realistic materials.

*State of the art.* TRIQS is the dominant toolbox for interacting quantum systems and DMFT, with a
C++/Python interface and DFT interfaces @parcollet_2015_triqs. w2dynamics provides a multi-orbital
CT-HYB solver with a full DMFT loop @wallerberger_2018_dynamics, and iQIST offers CT-HYB and
Hirsch–Fye impurity solvers @huang_2014_open. DCore integrates these into a turnkey DMFT package with
DFT front-ends (via Wannier90) @shinaoka_2020_dcore.

#proscons(
  list(
    [Handles multi-orbital, realistic materials by coupling to DFT @parcollet_2015_triqs.],
    [Captures local correlations (Mott transition, quasiparticles) at modest cost @wallerberger_2018_dynamics.],
    [Mature, modular ecosystem with integrated workflows @shinaoka_2020_dcore.],
  ),
  list(
    [Neglects non-local correlations unless extended (cluster/diagrammatic) at much higher cost @parcollet_2015_triqs.],
    [Impurity-solver QMC inherits sign problems and analytic-continuation issues @huang_2014_open.],
  ),
)

== At-a-glance comparison

#compare_table((
  ([Tensor networks],
    [ITensor @fishman_2020_itensor, TeNPy @hauschild_2024_tensor, PEPSKit @naumann_2023_introduction],
    [1D exact; 2D harder],
    [Entanglement / $chi$ cost; 2D not turnkey @sehlstedt_2025_software],
    [Gapped 1D & quasi-2D, frustrated spins]),
  ([Exact diagonalization],
    [QuSpin @weinberg_2016_quspin, XDiag @wietek_2025_xdiag, HΦ @kawamura_2017_quantum],
    [~40–50 sites],
    [Exponential size limit @wietek_2025_xdiag],
    [Small frustrated clusters; benchmarks]),
  ([Quantum Monte Carlo],
    [ALF @bercx_2017_alf, SmoQyDQMC @cohenstead_2023_smoqydqmc, DSQSS @motoyama_2020_dsqss],
    [1000s of sites],
    [Sign problem @bercx_2017_alf],
    [Sign-free spin/boson & half-filled fermions, finite $T$]),
  ([VMC / neural states],
    [NetKet @vicentini_2021_netket, jVMC @schmitt_2021_jvmc, mVMC @misawa_2017_mvmc],
    [Large 2D],
    [Non-convex; hard to certify @vicentini_2021_netket],
    [Frustrated 2D & fermionic where QMC fails]),
  ([DMFT / impurity],
    [TRIQS @parcollet_2015_triqs, w2dynamics @wallerberger_2018_dynamics, DCore @shinaoka_2020_dcore],
    [Bulk + materials],
    [Local approx.; solver sign problem @huang_2014_open],
    [Correlated electronic structure, materials]),
))

= Open Problems

#problem_table((
  ([1], [Fermion / frustration sign problem],
    [Doped Hubbard and frustrated magnets — the central open questions in correlated matter — stay exponentially hard for QMC, forcing reliance on less-controlled methods @bercx_2017_alf.],
    [QMC + tensor-network / NQS developers; algorithmic theory],
    [#text(fill: red.darken(10%))[Critical]]),
  ([2], [Robust, turnkey 2D tensor networks],
    [PEPS optimization (gauge fixing, CTMRG convergence, AD stability) remains research-grade, blocking routine 2D ground-state studies @naumann_2023_introduction @sehlstedt_2025_software.],
    [PEPSKit / TensorKit groups @devos_2025_tensorkit],
    [#text(fill: red.darken(10%))[Critical]]),
  ([3], [Certifying neural-quantum-state results],
    [NQS reach regimes others cannot, but lack the convergence guarantees and error bars that make tensor-network and QMC results trustworthy @vicentini_2021_netket @schmitt_2021_jvmc.],
    [NetKet / jVMC + ML-theory community],
    [#text(fill: orange.darken(20%))[High]]),
  ([4], [Interoperability and common formats],
    [Codes use incompatible Hamiltonian/lattice/symmetry representations, so cross-method validation — the backbone of trust — is manual and error-prone @sehlstedt_2025_software.],
    [Cross-package consortium; standards effort],
    [#text(fill: orange.darken(20%))[High]]),
  ([5], [GPU / HPC modernization of legacy cores],
    [JAX/Julia codes get GPU acceleration cheaply, but mature C++/Fortran solvers (ALPS, TRIQS, mVMC) need heavy porting to keep pace @bauer_2011_alps @misawa_2017_mvmc.],
    [Core maintainers + HPC engineers],
    [#text(fill: olive.darken(10%))[Medium]]),
  ([6], [Sustainability and citation hygiene],
    [Many packages are single-group projects with uneven maintenance; widely-used tools (MPSKit.jl, peps-torch, pomerol) lack a standalone release paper, complicating provenance @sehlstedt_2025_software.],
    [Funders, journals (SciPost Codebases), communities],
    [#text(fill: olive.darken(10%))[Medium]]),
))

#v(0.8em)

#section_box(
  [Bottom line],
  [There is no single best many-body code — the field is a portfolio of method-specialized libraries,
  and the right choice is dictated by dimensionality, sign structure, and target observable: tensor
  networks (ITensor/TeNPy) for 1D and gapped systems, ED (QuSpin/XDiag) for small frustrated clusters
  and benchmarks, QMC (ALF/SmoQyDQMC) for sign-free models at scale, neural/variational states
  (NetKet/jVMC) for frustrated 2D where QMC fails, and DMFT (TRIQS/DCore) for correlated materials.
  The strongest current momentum is in the Julia+autodiff and Python+JAX ecosystems
  @devos_2025_tensorkit @vicentini_2021_netket; the highest-value open targets are the sign problem
  and turnkey 2D tensor networks @bercx_2017_alf @naumann_2023_introduction.],
  fill: rgb("eef6ef"), stroke: rgb("bcd9c4"),
)

#v(0.6em)

#bibliography("ref.bib", title: "References", style: "ieee")
