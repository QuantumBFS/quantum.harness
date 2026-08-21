# Two-Paper Design for Exactly Degenerate Quantum Chaos and Geometric ETH

**Date:** 2026-08-17  
**Status:** Approved design  
**Primary task:** `task_05`  
**Manuscript base:** audited v12 cross-mechanism delivery  
**Decision:** replace the proposed single overloaded long paper by two back-to-back papers with different scientific objects, claims, and evidence obligations.

## 1. Rationale for the split

The current three-page article compresses a large body of calculations into one figure and roughly one thousand words of text. It reports the Moore--Read, lattice-supersymmetric, and X-cube comparison, but it cannot explain how those calculations relate to the earlier Laughlin, continuum-LLL, checkerboard-FCI, response-cumulant, spectral-silence, and holonomy results. Adding the ETH, BPS, super-JT, SYK, and black-hole literature to the same manuscript would not solve this problem. It would obscure the concrete result under a second, much broader theoretical question.

The two papers therefore answer different questions.

| Paper | Primary question | Evidence obligation | Main audience |
|---|---|---|---|
| I. *Exactly Degenerate Quantum Chaos* | How can quantum chaos be detected when the relevant eigenspace is exactly degenerate and ordinary level statistics are silent? | Exact models, common projector-response formalism, numerical scaling, covariance-complete correlations, and analytic negative controls | Condensed matter, quantum chaos, topological phases, numerical many-body physics |
| II. *The Geometric ETH* | What ETH-style statistical statement can be made about a degenerate quantum-state bundle, and what does it imply for protected/BPS sectors and black-hole microstates? | A gauge-covariant ansatz, a controlled limiting variable, an original theorem or parameter-free prediction, and source-verified gravitational applications | Quantum gravity, many-body chaos, ETH, supersymmetry, mathematical physics |

Paper I establishes the phenomenon, the observable, and mechanism dependence. Paper II proposes the general theory and must derive consequences not contained in Paper I. The second paper may cite the first paper's results as evidence; it may not reproduce the first paper under a broader title.

## 2. Shared scientific language

Both papers use one notation and one logical decomposition. Let $P(\boldsymbol\lambda)$ be a rank-$D$ spectral projector at energy $E_0$, separated from $Q=1-P$ by an open gap. An exactness-preserving tangent obeys

$$P(\partial_aH)P=(\partial_aE_0)P.$$

The traceless intrafiber splitting channel and the off-fiber geometric channel are

$$S_a=P(\partial_aH)P-\frac{\operatorname{Tr}[P(\partial_aH)P]}{D}P,\qquad V_a=Q(\partial_aH)P.$$

Exact degeneracy requires $S_a=0$, but places no general requirement on $V_a$. The complement response, matrix-valued quantum geometric tensor, metric, and non-Abelian curvature are

$$X_a=-[Q(H-E_0)Q]^{-1}V_a,\qquad \mathcal Q_{ab}=X_a^\dagger X_b,$$

$$g_{ab}=\frac{\mathcal Q_{ab}+\mathcal Q_{ba}}{2},\qquad F_{ab}=i(\mathcal Q_{ab}-\mathcal Q_{ba}).$$

This yields the protection--mixing separation principle:

> The algebraic mechanism that protects the eigenvalue and nullity is distinct from the response algebra that moves the protected fiber through Hilbert space.

The response algebra and its commutant are

$$\mathcal A_X=\operatorname{alg}\{X_a^\dagger X_b\},\qquad \mathcal A_X'=\{Y:[Y,X_a^\dagger X_b]=0\ \text{for all }a,b\}.$$

A fixed projector has $X_a=0$. A moving projector can still have scalar curvature and no connected fluctuations. Irreducible high-rank response, increasing effective channel number, and the absence of a large commutant are necessary candidates for geometric chaos. They are not assumed to be sufficient without a statistical test.

Both papers distinguish five statements that must not be conflated:

1. exact degeneracy;
2. nontrivial projector motion;
3. nonzero quantum metric or Berry curvature;
4. finite-size random-matrix correlations in a geometric observable;
5. asymptotic Geometric ETH, defined through a controlled limiting law.

## 3. Paper I design

### 3.1 Working title

**Exactly Degenerate Quantum Chaos: Non-Abelian Quantum Geometry as a Probe**

The alternative title *Quantum Chaos in Exactly Degenerate Systems: Non-Abelian Quantum Geometry as a Probe* is grammatically more explicit but less distinctive. The shorter title is retained unless journal feedback identifies ambiguity.

### 3.2 Scientific claim

Paper I will establish that exact spectral degeneracy and geometric chaos are logically independent. The protected eigenvalue can remain exactly flat while the projector response develops local random-matrix correlations, long-range structured memory, or an exactly scalar curvature, depending on the protection mechanism and tangent algebra. The paper will not claim conventional thermalization, a Lyapunov exponent, a universal thermodynamic Geometric ETH law, or complete covariance closure in models where that test is not available.

The strongest supported cross-mechanism statement is:

> Exact degeneracy removes ordinary spectral diagnostics but leaves a gauge-covariant projector response whose statistics distinguish frozen, scalar, structured, and locally random geometries. The observed class is finite-size and mechanism dependent.

### 3.3 Article format

- REVTeX 4.2, `aps,prb,reprint,superscriptaddress,longbibliography,floatfix`.
- Target main-text length: 14--18 reprint pages, including 7 principal figures and 2--3 compact tables.
- A separate Supplemental Material file will contain solver details, full derivations, complete parameter tables, provenance hashes, negative numerical controls, and extended finite-size panels.
- The v12 three-page article and supplement remain immutable historical deliverables.
- New source directory: `overleaf_sync/exactly_degenerate_quantum_chaos_prb/`.
- New task artifacts use the suffix `v13`; no v1--v12 source or output is overwritten.

### 3.4 Main-text structure

#### I. Introduction: the blind spot of exact degeneracy

The introduction begins from the operational failure of level statistics in an exactly degenerate manifold. It explains why lifting the degeneracy changes the protected object and why a projector-valued observable survives. The BPS Berry-curvature paper is used as motivation, not as a substitute for the condensed-matter question. The introduction ends with the protection--mixing separation and a concise statement of what is calculated.

#### II. Protected fibers and off-fiber response

This section derives the $P/Q$ block decomposition, distinguishes $S_a$ from $V_a$, derives $X_a$, and fixes the sign convention. It defines the QGT, metric, curvature, gauge transformations, and gauge-invariant trace words. It proves that a change confined to $PHP$ can randomize intramultiplet levels while leaving $P$, $g$, and $F$ invariant.

#### III. Statistical tests of geometric chaos

This section defines curvature eigenvalue statistics, connected form factors, number variance, covariance-deformed Jacobi references, and the four-channel tensor

$$T_{abcd}=D^{-1}\operatorname{Tr}(X_a^\dagger X_bX_c^\dagger X_d).$$

It defines the three-pairing complex Wick tensor $W_{abcd}$, the residual $K_{abcd}=T_{abcd}-W_{abcd}$, panel or realization units, pseudocovariance, and claim boundaries. Local level repulsion is explicitly treated as weaker evidence than covariance-complete higher-moment closure.

#### IV. Exact-degeneracy mechanisms and model families

The model section is organized by protection algebra rather than chronology. It introduces the two-body Laughlin parent, the three-body Moore--Read parent, random-supercharge and lattice-supercharge cohomology, and the X-cube stabilizer code. The checkerboard FCI is identified as a lattice geometry/chaos replication rather than a separate strict zero-mode mechanism. A table records the origin of degeneracy, rank sequence, gap condition, physical tangents, expected splitting channels, and role of every model.

#### V. Spectral silence and geometric correlations in Laughlin manifolds

This section presents the exact flat-band energy form factor, the finite-Jacobi curvature form factor, the structured-tangent control, the independent $PHP$ intervention, and the local-to-long-range hierarchy. It then presents the fixed-two-quasihole Wick sequence and the continuum-LLL parent comparison. The text separates exact theorems, held-out numerical observations, finite-size fits, and rejected asymptotic laws.

#### VI. Geometry and topology at fixed Chern class

This section decomposes curvature into trace and traceless components, explains why the Chern number fixes only the integrated $U(1)$ sector, and presents Wilson holonomy changes at fixed spectrum, gap, and first Chern number. It does not identify Wilson randomization with conventional time evolution.

#### VII. Three-body clustering and cohomological response

The Moore--Read calculation is presented as a change in constraint order and non-Abelian zero-mode structure. The random-supercharge SYK and lattice-SUSY calculations are presented through their exact/coexact Hodge split. Every inference is labelled by its actual unit: independent disorder realization, fixed-base tangent panel, or analytic control. The failure of a registered lattice-SUSY direction is not described as proof of Gaussianity.

#### VIII. Stabilizer counterexamples

The X-cube coefficient reweighting proves $g=F=0$ for a parameter-dependent Hamiltonian with fixed projector. The local isospectral orbit proves that nonzero projector motion and $F=-P/2$ can coexist with zero connected curvature variance. These calculations establish that neither exact degeneracy, projector motion, nor nonzero curvature is sufficient for chaos.

#### IX. Protection mechanism, tangent algebra, and accessible channels

This section assembles the mechanism-resolved classification. It reports accessible response rank, covariance effective dimension, known commutants or branch decompositions, local spectral correlations, and higher-order residual status. A candidate effective-channel scaling variable may be discussed only as a prospective theory unless it is tested without refitting.

#### X. Discussion and limitations

The discussion states what has and has not been established, identifies the missing matched covariance cells, and explains why model completeness is neither possible nor scientifically necessary. The conclusion is limited to exact spectral silence, informative projector geometry, mechanism dependence, and the protection--mixing separation.

### 3.5 Figure contract for Paper I

1. **Protection and mixing under exact degeneracy.** A new schematic/data hybrid showing the $S_a$ and $V_a$ blocks, the response construction, and the four regimes: frozen, scalar, structured, and chaotic geometry.
2. **Spectral silence versus geometric correlations.** Reuse and, if necessary, relabel the audited v2 energy/curvature form-factor figure.
3. **Local-to-global hierarchy in the Laughlin manifold.** Combine local spacing, curvature SFF, number variance, and covariance-deformed deviations without overlaying incompatible uncertainty units.
4. **Independent spectral and geometric chaos channels.** Reuse the fixed-projector and moving-projector interventions and make the $PHP$ versus $Q(\partial H)P$ distinction explicit in the caption.
5. **Higher-order response and parent dependence.** Present the many-body Wick sequence and continuum-LLL comparison, with the rejected no-refit law visible.
6. **Topology does not determine internal holonomy.** Present fixed $C_1$, Wilson eigenphases, and traceless holonomy statistics.
7. **Mechanism-resolved exact-degeneracy evidence.** Expand the v12 cross-mechanism figure so Moore--Read, random-supercharge SYK, lattice SUSY, and X-cube occupy separate, readable panels with their actual inference status.

The Supplemental Material may carry the Jacobi atom crossover, full finite-size regressions, additional operator classes, kernel/gap audits, complete covariance oracle, and resource tables. No figure is included merely to increase the count; each main-text figure must support a distinct logical step.

### 3.6 Evidence matrix and hard claim gates

The manuscript generator will build a machine-readable evidence matrix. Each model receives separate values for exact-fiber audit, internal bandwidth, external gap, projector motion, local spectral statistic, complete covariance statistic, independent ensemble status, size sequence, production status, and claim boundary. A missing cell remains visibly missing. The generator must reject prose macros that imply a stronger status than the source JSON.

The current gaps are retained:

- Laughlin: v12-matched complete three-pairing covariance remains absent.
- Random-supercharge SYK: complete nonseparable covariance closure remains absent.
- Moore--Read: $N=8$ and independent-Hamiltonian inference remain absent.
- Lattice SUSY: connected-family scaling and production status remain absent.
- X-cube: stochastic physical deformation ensemble is not applicable to the present analytic control.

## 4. Paper II design

### 4.1 Working title

**The Geometric ETH: Statistical Closure on Degenerate Quantum State Bundles**

The title *The Geometric ETH* is retained as the memorable short name. The subtitle states the mathematical object and prevents the paper from reading as an unsupported universal claim.

### 4.2 Scientific claim and entry gate

Paper II is not authorized to claim a new ETH solely because Paper I finds random-matrix-like curvature. Before a results manuscript is written, the theory program must produce all of the following:

1. a basis-independent Geometric-ETH ansatz for a sequence of degenerate bundles;
2. a precise sampling ensemble and symmetry-class statement;
3. complete covariance and pseudocovariance treatment;
4. an asymptotic variable derived from response structure rather than selected after observing a fit;
5. one original theorem, controlled random-channel calculation, or parameter-free prediction;
6. one quantitative consistency test using data not used to choose the prediction.

If these gates are not met, the appropriate product is a perspective or theory note, not a research article titled *The Geometric ETH*.

### 4.3 Theory architecture

#### I. Ordinary ETH and protected sectors

The paper states the standard ETH matrix-element ansatz only to identify which ingredients fail under exact degeneracy. It distinguishes thermalization, spectral chaos, eigenvector randomness, and protected subspace geometry.

#### II. Quantum-state bundles over coupling or moduli space

This section defines the bundle, connection, curvature, QGT, trace/traceless decomposition, Chern characters, and Wilson transport. It explains why raw connection entries are gauge dependent and why the statistical theory must be written in terms of covariant tensors or closed contractions.

#### III. Geometric-ETH ansatz

The ansatz is formulated for $X_{a,N}:P_N\mathcal H_N\to Q_N\mathcal H_N$ on a sequence with $D_N\to\infty$. Deterministic symmetry/topology components are separated from fluctuations. The whitened finite-dimensional distributions, connected cumulants, and strong/weak/deformed branches are defined. The Gaussian branch requires Wick closure; a non-Gaussian universal fixed tensor must be stated separately rather than called Gaussian ETH.

#### IV. Response algebra and the effective number of channels

This section studies $\mathcal A_X$, its commutant, accessible response rank, and covariance effective dimension

$$N_{\mathrm{eff}}=\frac{(\operatorname{Tr}C)^2}{\operatorname{Tr}C^2}.$$

The target derivation is a controlled channel model in which covariance-whitened fourth cumulants scale with $N_{\mathrm{eff}}$. Any proposed exponent must follow from the model before comparison with Paper I data.

#### V. Protection classes

The theory is applied to common kernels $C^\dagger C$, nilpotent cohomology $\{Q,Q^\dagger\}$, commuting stabilizers, chiral/index kernels, symmetry multiplets, and integrable spectral algebras. The section identifies which algebraic features constrain $\mathcal A_X$ and which merely fix $D$.

#### VI. BPS sectors, SYK, super-JT, and black-hole microstates

The gravitational literature is organized by a single question: what protects the spectrum, and what determines the geometry of the protected states over moduli space? Work by the named authors and related ETH/black-hole papers will be included only after exact title, authorship, primary-source claim, and BibTeX verification. The smooth/horizonless versus black-hole-like comparison is expressed through curvature structure, response rank, connected cumulants, and moduli-space topology rather than rhetorical analogy.

#### VII. Topology and statistical geometry

This section separates the trace curvature constrained by Chern data from the traceless sector carrying internal mixing. It asks when topology constrains only global integrals and when it imposes local Ward identities or curvature sum rules. Exponentially large Chern numbers in supersymmetric models are treated as topology data, not by themselves as evidence of chaos.

#### VIII. Predictions and falsification

The paper ends with concrete consequences: fixed Chern class need not fix $SU(D)$ holonomy; a large response commutant obstructs strong Geometric ETH; fixed-projector and scalar-curvature families are exact negative cases; and the correct scaling variable may be $N_{\mathrm{eff}}$ rather than $D$. Every prediction must name a model, observable, ensemble unit, and failure branch.

### 4.4 Figure contract for Paper II

1. **From energy-shell ETH to bundle ETH.** A mathematical schematic mapping $O_{mn}$ to $X_a$, the energy shell to a protected fiber, and energy differences to tangent labels.
2. **Protection--mixing classification.** The response-algebra phase diagram with frozen, scalar, reducible, and irreducible sectors.
3. **Covariance hierarchy and closure.** Ordinary covariance, pseudocovariance, three Wick pairings, connected residual, and strong/deformed branches.
4. **Topology versus internal statistics.** $U(1)$ Chern data and $SU(D)$ curvature/holonomy on the same bundle.
5. **Protected sectors across many-body and gravitational models.** A source-backed comparison of FQH parents, stabilizer codes, SUSY cohomology, smooth BPS sectors, SYK/super-JT, and black-hole-like microstates.
6. **Falsifiable predictions.** A compact plot or table using the derived scaling variable and held-out data, included only after the theory gate passes.

## 5. Cross-paper reuse rules

- Paper I owns all detailed numerical model descriptions, parameter tables, solver methods, finite-size plots, and model-specific conclusions.
- Paper II may reproduce definitions and one compact evidence summary with an explicit citation to Paper I; it does not reproduce Paper I's seven-figure narrative.
- Shared equations use identical notation but are rewritten for the purpose of each paper. Text is not copied verbatim between manuscripts.
- Paper I does not use the phrase “asymptotic Geometric ETH established.” Paper II treats Paper I as finite-size evidence and exact counterexamples.
- A result generated after Paper I freezes may enter Paper II only if it tests a Paper-II prediction and is identified as a separate calculation.
- Bibliographies are independent. Paper I emphasizes primary condensed-matter and quantum-chaos sources; Paper II emphasizes ETH, supersymmetry, BPS geometry, super-JT, SYK, and black-hole microstates.

## 6. Writing and presentation rules

Both papers follow APS/PRB notation and the project's physics-paper style. The prose begins from the physical problem, model, assumptions, calculation, and result. It does not contain headings such as “Our Contributions,” promotional adjectives, generic significance claims, or a catalogue of future applications. Claims are separated into derived results, numerical observations, interpretations consistent with the data, and conjectures.

The long form must not be produced by expanding every sentence of the short paper. Each section must introduce information needed later, and every paragraph must carry a physical statement, derivation, numerical condition, or limitation. Technical terminology is retained where it is standard; vague words such as “robust,” “novel,” “comprehensive,” and “promising” are removed unless quantified. The final prose will undergo a separate human-style audit for repetitive transitions, symmetrical list construction, empty summary sentences, and excessive “not X but Y” phrasing.

Figures use vector PDF as the canonical format and a 300-dpi PNG preview for visual inspection. Captions state the model, parameters, ensemble unit, uncertainty construction, and claim supported by each panel. Tables are generated from audited JSON or a source-verified literature file; empirical numbers are never typed manually into prose.

## 7. Reproducibility and delivery

Each paper receives an independent source directory, generated-data directory, figure manifest, citation audit, LaTeX verifier, PDF archive, and delivery JSON. Paper I can depend on immutable v1--v12 task artifacts but must record their hashes. Paper II can depend on Paper I's published or frozen evidence manifest but cannot import Paper I's prose.

The delivery verifier for each paper will check:

- title, authors, affiliations, and target document class;
- source JSON hashes and generated macro provenance;
- absence of manually typed empirical values where generated macros exist;
- resolved citations and cross-references;
- absence of undefined references, overfull boxes, and stuck floats;
- required figures and caption content;
- explicit claim-boundary sentences;
- page rendering at original resolution;
- byte-identical archived PDF;
- clean rerun without rewriting unchanged canonical audit files.

## 8. Execution order

1. Freeze this design and commit it independently.
2. Implement Paper I first because its evidence base is already audited.
3. During Paper I writing, build the common evidence matrix and identify exactly which missing covariance cells require new calculations.
4. Freeze Paper I's main scientific claims before Paper II imports any evidence.
5. Perform a primary-source literature audit for the ETH/BPS/black-hole section of Paper II.
6. Derive and test the Paper-II response-algebra/effective-channel result.
7. Write Paper II only after its independent theory gate passes.

This order permits back-to-back preparation while preventing the conceptual paper from outrunning the available theory.
