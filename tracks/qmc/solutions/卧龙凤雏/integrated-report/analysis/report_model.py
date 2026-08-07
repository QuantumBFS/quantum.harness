"""Format-independent scientific content for the integrated report."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple, Union

from analysis.sources import LearningMitResult, ModelResult


@dataclass(frozen=True)
class Paragraph:
    text: str
    kind: str = "paragraph"


@dataclass(frozen=True)
class Equation:
    expression: str
    explanation: str
    number: str
    kind: str = "equation"


@dataclass(frozen=True)
class Figure:
    source: Path
    alt_text: str
    caption: str
    inference_limit: str
    kind: str = "figure"


@dataclass(frozen=True)
class Table:
    title: str
    columns: Tuple[str, ...]
    rows: Tuple[Tuple[str, ...], ...]
    note: str
    kind: str = "table"


@dataclass(frozen=True)
class Callout:
    title: str
    text: str
    tone: str
    kind: str = "callout"


@dataclass(frozen=True)
class CodeBlock:
    title: str
    code: str
    explanation: str
    kind: str = "code"


@dataclass(frozen=True)
class PageBreak:
    kind: str = "page_break"


Block = Union[Paragraph, Equation, Figure, Table, Callout, CodeBlock, PageBreak]


@dataclass(frozen=True)
class Section:
    title: str
    slug: str
    blocks: Tuple[Block, ...]


@dataclass(frozen=True)
class ReportDocument:
    title: str
    subtitle: str
    author: str
    abstract: str
    sections: Tuple[Section, ...]

    def section_for_slug(self, slug: str) -> Section:
        for section in self.sections:
            if section.slug == slug:
                return section
        raise KeyError(slug)

    def plain_text(self) -> str:
        parts = [self.title, self.subtitle, self.author, self.abstract]
        for section in self.sections:
            parts.append(section.title)
            for block in section.blocks:
                if isinstance(block, Paragraph):
                    parts.append(block.text)
                elif isinstance(block, Equation):
                    parts.extend((block.expression, block.explanation))
                elif isinstance(block, Figure):
                    parts.extend((block.alt_text, block.caption, block.inference_limit))
                elif isinstance(block, Table):
                    parts.extend((block.title, " ".join(block.columns), block.note))
                    parts.extend(" ".join(row) for row in block.rows)
                elif isinstance(block, Callout):
                    parts.extend((block.title, block.text))
                elif isinstance(block, CodeBlock):
                    parts.extend((block.title, block.code, block.explanation))
        return "\n".join(parts)


def build_report(
    models: Sequence[ModelResult], learning_mit: LearningMitResult
) -> ReportDocument:
    indexed = {model.slug: model for model in models}
    required = {"clean-ising", "nishimori-ising", "weak-self-dual"}
    if set(indexed) != required:
        raise ValueError("the integrated report requires exactly the three approved models")
    clean = indexed["clean-ising"]
    nishimori = indexed["nishimori-ising"]
    weak = indexed["weak-self-dual"]
    abstract = (
        "This report verifies central-charge extraction in three progressively more "
        "complex critical systems using frozen numerical evidence. A clean square-lattice "
        "Ising model supplies an exact benchmark, a quenched random-bond Ising model on "
        "the Nishimori line tests disorder averaging, and a Born-correlated weak self-dual "
        "Majorana network tests Gaussian trajectory methods. The measured values are "
        f"{clean.estimate:.6f}, {nishimori.estimate:.6f}, and {weak.estimate:.6f}; "
        "their declared intervals are consistent with the corresponding targets 0.5, "
        "0.464, and 0.447. The emphasis is not merely numerical agreement: every result "
        "is accompanied by an explanation of the estimator, finite-size ansatz, parameter "
        "choices, statistical uncertainty, systematic limitations, and independent "
        "scientific checks."
    )
    return ReportDocument(
        title="Three Routes to Central Charge",
        subtitle="Clean Ising, Nishimori Disorder, and Weak Self-Dual Majorana Dynamics",
        author="Team 卧龙凤雏 · Quantum Harness Challenge #122",
        abstract=abstract,
        sections=(
            _executive(clean, nishimori, weak),
            _foundation(),
            _architecture(),
            _clean_section(clean),
            _nishimori_section(nishimori),
            _weak_section(weak),
            _comparison(clean, nishimori, weak),
            _errors(clean, nishimori, weak),
            _implementation(),
            _open_research(learning_mit),
            _conclusions(clean, nishimori, weak),
            _appendices(clean, nishimori, weak),
        ),
    )


def _executive(clean: ModelResult, nishimori: ModelResult, weak: ModelResult) -> Section:
    rows = tuple(
        (
            model.name,
            f"{model.estimate:.6f}",
            f"{model.standard_error:.6f}",
            f"[{model.ci95[0]:.6f}, {model.ci95[1]:.6f}]",
            f"{model.target:.3f}",
            f"{model.runtime_s:.1f}",
            "PASS",
        )
        for model in (clean, nishimori, weak)
    )
    return Section(
        "Executive Summary",
        "executive-summary",
        (
            Paragraph(
                "Central charge is a compact measure of the long-distance degrees of "
                "freedom at a two-dimensional critical point. It enters the universal "
                "finite-size correction to a free energy or closely related information "
                "rate. That correction is small compared with the extensive bulk term, "
                "so a convincing numerical estimate requires more than a visually good "
                "fit. The calculation must control sampling noise, correlations, finite-"
                "width corrections, numerical stability, and the possibility that the "
                "implemented model differs subtly from the intended one."
            ),
            Paragraph(
                "The three studies form a deliberate ladder of difficulty. In the clean "
                "Ising model, a transfer-matrix calculation supplies a deterministic "
                "oracle and Wolff-cluster Monte Carlo supplies an independent stochastic "
                "route. The Nishimori model replaces uniform couplings with quenched "
                "random signs and therefore requires disorder averages, correlated "
                "finite-size vectors, and a Nishimori identity check. The weak self-dual "
                "network replaces equilibrium spin configurations with sequential "
                "Born-conditioned Gaussian fermion trajectories; its central-charge "
                "signal is extracted from a Shannon free-energy rate rather than the "
                "ordinary equilibrium free energy."
            ),
            Table(
                "Headline numerical results",
                ("Model", "Estimate", "SE", "95% CI", "Target", "Runtime (s)", "Gates"),
                rows,
                "The clean row reports the Monte Carlo estimate so that all three rows "
                "carry sampling intervals. Its independent transfer-matrix estimate is "
                f"{clean.exact_estimate:.6f}. Runtime values describe the recorded source "
                "workflows and are not directly comparable as hardware-independent costs.",
            ),
            Callout(
                "Interpretation",
                "All three estimates are statistically consistent with their declared "
                "benchmarks. This means the frozen data do not resolve a discrepancy at "
                "their quoted precision; it does not mean the numerical estimates are "
                "identically equal to the target values or free of broader systematic "
                "uncertainty.",
                "result",
            ),
            Paragraph(
                "The clean estimate is c = "
                f"{clean.estimate:.6f} with a 95% interval "
                f"[{clean.ci95[0]:.6f}, {clean.ci95[1]:.6f}], while the deterministic "
                f"route gives {clean.exact_estimate:.6f}. The Nishimori estimate is "
                f"c_eff = {nishimori.estimate:.6f} with interval "
                f"[{nishimori.ci95[0]:.6f}, {nishimori.ci95[1]:.6f}]. The weak self-dual "
                f"estimate is c_eff = {weak.estimate:.6f} with interval "
                f"[{weak.ci95[0]:.6f}, {weak.ci95[1]:.6f}]. Every required gate stored "
                "with these result sets passes."
            ),
            Figure(
                Path("generated/central-charge-intervals.png"),
                "Three central-charge estimates with confidence intervals and benchmark markers.",
                "Cross-model result summary. Points show the measured estimates and bars "
                "show 95% confidence intervals; distinct markers identify benchmark "
                "targets rather than treating them as additional measurements.",
                "Interval overlap with a target establishes consistency at the reported "
                "precision, not identity of microscopic models or equality of all "
                "systematic errors.",
            ),
        ),
    )


def _foundation() -> Section:
    return Section(
        "Conceptual Foundation",
        "conceptual-foundation",
        (
            Paragraph(
                "A continuous phase transition has fluctuations on every length scale. "
                "The correlation length diverges, local microscopic details become less "
                "important, and observables organize into scaling laws. In two spatial "
                "dimensions at equilibrium, the long-distance fixed point is often "
                "described by a conformal field theory. Conformal symmetry is much more "
                "restrictive than ordinary scale symmetry, and one of its defining "
                "numbers is the central charge c. Roughly speaking, c counts effective "
                "gapless degrees of freedom, although that phrase must be used carefully "
                "for non-unitary, disordered, or information-theoretic problems."
            ),
            Paragraph(
                "A finite cylinder turns central charge into a measurable correction. "
                "The leading free-energy density is nonuniversal: it depends on lattice "
                "spacing, local interactions, and normalization. The subleading Casimir "
                "term is universal because critical fluctuations wrap around the finite "
                "circumference. For a periodic cylinder of circumference L, the correction "
                "is proportional to c/L^2 in a free-energy density, or to c/L in a free "
                "energy per longitudinal step. The sign depends on the convention used "
                "for free energy, log partition function, or Shannon surprise. Each model "
                "chapter derives the convention actually fitted rather than moving signs "
                "by analogy."
            ),
            Equation(
                "f(L) = f_infinity - pi c/(6 L^2) + a/L^4 + ...",
                "Here f(L) is an intensive critical free-energy quantity, f_infinity is "
                "the nonuniversal bulk limit, and a absorbs the leading analytic or "
                "irrelevant-operator correction. The coefficient of 1/L^2 carries c. "
                "The L^-4 term is retained because the smallest simulated widths are not "
                "asymptotic. Omitting it may reduce nominal error bars while biasing the "
                "central term.",
                "1",
            ),
            Paragraph(
                "Finite-size scaling is an inference problem with an unfavorable signal "
                "structure. The bulk contribution is order one, while the universal term "
                "shrinks as L^-2. At larger L the theoretical approximation improves, but "
                "the difference used to identify c becomes smaller. At smaller L the "
                "signal is larger, but neglected corrections are more dangerous. A fit "
                "window therefore expresses a bias-variance compromise. It must be chosen "
                "or at least tested without selecting whichever window happens to produce "
                "the expected answer."
            ),
            Paragraph(
                "The notation c_eff is used when disorder, non-unitarity, replicas, or an "
                "information-theoretic ensemble changes what the Casimir coefficient "
                "represents. It remains the coefficient extracted from a universal "
                "finite-size term, but it need not equal a simple count of unitary CFT "
                "fields. This is why the clean Ising benchmark is labeled c=1/2 whereas "
                "the Nishimori and weak self-dual results are labeled effective central "
                "charges."
            ),
            Paragraph(
                "Quenched disorder means that random couplings are drawn and then held "
                "fixed while thermal degrees of freedom equilibrate. The physical free "
                "energy involves the disorder average of log Z, not the log of the "
                "disorder-averaged Z. These operations differ by Jensen's inequality. A "
                "numerical algorithm must therefore compute or estimate log-normalization "
                "increments for each disorder history before averaging. Treating every "
                "bond as if it were re-sampled during the thermal trace would instead "
                "describe annealed disorder and a different universality class."
            ),
            Equation(
                "F_quenched = - E_disorder[log Z],    F_annealed = -log E_disorder[Z]",
                "The distinction is conceptual and computational. The Nishimori workflow "
                "samples disorder realizations, evaluates thermal transfer operations for "
                "each realization, and averages accumulated logarithms. The equality of "
                "these expressions is not assumed.",
                "2",
            ),
            Paragraph(
                "Self-duality exchanges two complementary descriptions of the same "
                "critical point. In an Ising setting it exchanges high- and low-temperature "
                "objects; in the Majorana network it exchanges electric and magnetic "
                "vortex species after a one-Majorana translation. Weak self-duality does "
                "not mean that every individual random trajectory is symmetric. It means "
                "that the correctly sampled ensemble should show the corresponding "
                "exchange symmetry. A paired density difference is therefore a useful "
                "diagnostic of model implementation and sampling."
            ),
            Callout(
                "Why three models?",
                "The shared finite-size idea becomes more credible when it survives three "
                "different sources of complexity: ordinary thermal sampling, quenched "
                "disorder, and state-conditioned quantum measurement outcomes. The "
                "comparison is methodological, not a claim that the microscopic systems "
                "are interchangeable.",
                "principle",
            ),
        ),
    )


def _architecture() -> Section:
    return Section(
        "Shared Computational Architecture",
        "shared-architecture",
        (
            Paragraph(
                "All computationally intensive sampling and state evolution are written "
                "in Rust. Rust provides predictable memory use, explicit numerical data "
                "types, parallel iterators, and a compiler that catches many indexing and "
                "ownership errors before a long run starts. Python begins only after "
                "atomic artifacts have been written. It reads records, aggregates blocks, "
                "performs regressions and bootstrap resampling, and creates charts. This "
                "division keeps exploratory statistics convenient without putting the "
                "inner simulation loop behind an interpreter."
            ),
            Paragraph(
                "The pseudo-random generator is Xoshiro256++, supplied by the Rust "
                "rand_xoshiro implementation. A base seed is not reused directly for every "
                "width and replica. Instead, deterministic derivation assigns a distinct "
                "stream identity from the tuple of model, width, replica or trajectory, "
                "and measurement role. Reproducibility therefore means that the same "
                "configuration and stream key recreate the same bytes, while parallel "
                "scheduling does not decide which random numbers a stream receives."
            ),
            CodeBlock(
                "Deterministic stream derivation",
                "key = hash(base_seed, model_tag, width, replica, purpose)\n"
                "rng = Xoshiro256PlusPlus::seed_from_u64(key)\n"
                "for block in assigned_blocks:\n"
                "    estimate = simulate_block(rng, state)\n"
                "    write_atomic(stream_key, block, estimate)",
                "A stream key is part of the scientific record. Atomic replacement avoids "
                "a valid-looking partial JSON file after interruption, and stable keys "
                "allow completed streams to be reused byte for byte.",
            ),
            Paragraph(
                "Raw results are organized into blocks rather than only global averages. "
                "Blocking preserves information needed to diagnose correlation and to "
                "resample uncertainty. A single mean and variance cannot reveal whether "
                "early and late measurements disagree, whether one replica dominates, or "
                "whether widths share a common disorder realization. The precise block "
                "definition differs by model: Wolff sweeps for clean Ising, transfer rows "
                "for Nishimori disorder, and circuit layers within independent streams for "
                "the Majorana network."
            ),
            Paragraph(
                "Manifests record configuration values, software versions, seeds, command "
                "lines, runtimes, and cryptographic hashes. Loaders reject incompatible "
                "schema versions and mismatched configurations. This is scientific error "
                "handling rather than administrative bookkeeping. Combining a summary "
                "from one configuration with raw blocks from another can produce smooth "
                "plots and plausible numbers; schema and hash checks turn that silent "
                "failure into an explicit exception."
            ),
            Table(
                "Shared software responsibilities",
                ("Layer", "Responsibility", "Why it lives there"),
                (
                    ("Rust core", "State updates, transfer actions, sampling, atomic records", "Performance and explicit numerical invariants"),
                    ("Rust tests", "Small exact oracles, RNG replay, geometry and CLI contracts", "Catch physics and serialization errors near implementation"),
                    ("Python analysis", "Aggregation, fitting, bootstrap, diagnostics", "Transparent numerical experimentation and mature statistics"),
                    ("Python plotting", "Existing model figures and integrated comparisons", "Consistent publication graphics"),
                    ("Report generator", "Frozen-source validation and dual-format rendering", "Separates communication from simulation"),
                ),
                "The boundary is artifact based: Python consumes immutable outputs rather "
                "than reaching into a running Rust process.",
            ),
            Paragraph(
                "Tests are layered in the same order as the scientific argument. Unit "
                "tests establish local identities, such as a Born probability for a "
                "two-mode state. Integration tests compare complete short trajectories "
                "against dense exact evolution. Statistical gates then assess production "
                "data, and report tests verify that published values match frozen "
                "artifacts. A final visually inspected report is therefore the last link "
                "in a chain, not a substitute for testing the simulation."
            ),
        ),
    )


def _clean_section(model: ModelResult) -> Section:
    figures = _model_figures(model, _clean_captions())
    return Section(
        "Clean Ising Model",
        model.slug,
        (
            PageBreak(),
            Paragraph(
                "The clean benchmark is the ferromagnetic square-lattice Ising model with "
                "spins s_i in {-1,+1} and nearest-neighbor energy H = -sum s_i s_j. With "
                "the coupling absorbed into K, the exact critical point is "
                "K_c = 0.5 log(1+sqrt(2)). The continuum limit is the minimal Ising CFT "
                "with central charge c=1/2. Because both K_c and c are known, this model "
                "tests the complete measurement pipeline without asking the fit to "
                "discover an unknown universality class."
            ),
            Equation(
                "H = - sum_<ij> s_i s_j,    K_c = (1/2) log(1+sqrt(2))",
                "Periodic L by M tori are evaluated with M=8L. The elongated geometry "
                "approximates a cylinder while retaining periodic boundaries and limits "
                "contamination from the longitudinal circumference.",
                "3",
            ),
            Paragraph(
                "The deterministic route applies a transfer matrix without constructing "
                "the full dense matrix. A row configuration has 2^L states. Horizontal "
                "weights are diagonal, while vertical bonds factor into local two-state "
                "operations. This factorization reduces a naive O(4^L) multiplication to "
                "O(L 2^L). Power iteration obtains the dominant eigenvalue and hence the "
                "free energy per row. Tight eigenvalue and residual tolerances make this "
                "route effectively exact for the widths used in the fit."
            ),
            CodeBlock(
                "Matrix-free transfer action",
                "v = horizontal_weights * input\n"
                "for site in 0..L:\n"
                "    v = apply_two_state_vertical_factor(v, site, K)\n"
                "normalize v and accumulate log_norm\n"
                "repeat until eigenvalue and residual tolerances pass",
                "The algorithm stores vectors of length 2^L but never a 2^L by 2^L "
                "matrix. The transfer estimate provides a deterministic oracle for the "
                "Monte Carlo and fitting conventions.",
            ),
            Paragraph(
                "The stochastic route uses Wolff cluster updates. Near criticality, local "
                "single-spin updates suffer critical slowing down because correlated "
                "domains grow with system size. A Wolff update selects a seed spin and "
                "grows a like-spin cluster with the coupling-dependent bond probability, "
                "then flips the entire cluster. Large-scale modes move collectively, "
                "reducing autocorrelation relative to a local Metropolis chain. Stored "
                "blocks still matter because cluster updates do not make successive "
                "measurements exactly independent."
            ),
            Equation(
                "F(K_c) = -N log 2 + integral_0^Kc <H>_K dK",
                "At K=0 the partition function is exactly 2^N. The derivative of the "
                "dimensionless free energy with respect to K is the mean energy in the "
                "chosen sign convention. Simpson integration over a 129-point coupling "
                "grid reconstructs the critical free energy. A nested 65-point grid tests "
                "quadrature convergence using measurements already present on the fine "
                "grid.",
                "4",
            ),
            Paragraph(
                "This integration strategy is used because Monte Carlo directly estimates "
                "expectation values, not an absolute partition function. Anchoring at K=0 "
                "eliminates an unknown additive constant. The price is accumulated "
                "quadrature and sampling uncertainty. The nested-grid shift is compared "
                "with the bootstrap standard error; agreement indicates that additional "
                "K points would not materially improve the present central-charge "
                "precision."
            ),
            Equation(
                "g(L)/L = f_infinity - pi c/(6 L^2) + a/L^4",
                "The primary fit uses L_min=6. L=4 remains visible as a small-width "
                "diagnostic, and L_min=8 tests sensitivity after discarding more signal. "
                "The transfer and Monte Carlo routes use the same finite-size convention, "
                "so agreement simultaneously tests free-energy signs, normalization by "
                "site, and the regression coefficient that is converted into c.",
                "5",
            ),
            Callout(
                "Clean benchmark result",
                f"The transfer-matrix estimate is c={model.exact_estimate:.6f}. The "
                f"independent Wolff/integration estimate is c={model.estimate:.6f} with "
                f"SE={model.standard_error:.6f} and 95% CI "
                f"[{model.ci95[0]:.6f}, {model.ci95[1]:.6f}]. Both are consistent with "
                "the exact Ising value 0.5.",
                "result",
            ),
            *figures,
            _parameter_table(model),
            *_parameter_explanations(model),
            _gate_table(model),
            Paragraph(
                "The main statistical limitation is the thermodynamic-integration noise "
                "propagated through the finite-size slope. The exact route is much more "
                "precise, but it is not a replacement for Monte Carlo: the challenge is to "
                "verify a simulation architecture that can later operate when no transfer "
                "oracle is available. Agreement between methods is strongest when each "
                "route retains independent code and numerical assumptions."
            ),
        ),
    )


def _nishimori_section(model: ModelResult) -> Section:
    figures = _model_figures(model, _nishimori_captions())
    return Section(
        "Nishimori Random-Bond Ising Model",
        model.slug,
        (
            PageBreak(),
            Paragraph(
                "The Nishimori model assigns a sign tau_ij to every nearest-neighbor bond. "
                "A positive sign is ferromagnetic and a negative sign is antiferromagnetic. "
                "The negative-bond probability p creates frustration: no spin assignment "
                "can satisfy every bond around a plaquette with an odd product of negative "
                "signs. Disorder is quenched, so the thermal partition function is "
                "evaluated for a fixed bond history before logarithms are averaged across "
                "histories."
            ),
            Equation(
                "P(tau_ij=-1)=p,    K_N=(1/2) log((1-p)/p)",
                "The Nishimori line ties the coupling K_N to the disorder probability. "
                "At the chosen multicritical parameters, p=0.1092212 and "
                "K_N=1.049360476302568. This relation produces exact gauge identities that "
                "are valuable implementation checks.",
                "6",
            ),
            Paragraph(
                "The target in this report is the ordinary quenched effective central "
                "charge near 0.464. It must not be confused with a different Born-rule or "
                "higher-replica quantity near 0.522. Both numbers can arise in related "
                "literature, but they correspond to different ensemble weights. The "
                "implemented calculation averages log Z for ordinary quenched disorder; "
                "its data and gates were therefore designed to verify 0.464 rather than "
                "retrofit an estimate to 0.522."
            ),
            Paragraph(
                "For each random transfer row, Rust applies the horizontal and vertical "
                "bond factors to a vector over 2^L boundary spin states. L1 normalization "
                "after every row prevents overflow. The accumulated logarithms of the "
                "normalization factors converge to a leading Lyapunov exponent of the "
                "random transfer product. Dividing by row count and width produces the "
                "quenched log-partition density phi_L."
            ),
            CodeBlock(
                "Quenched transfer-product estimator",
                "for replica in disorder_replicas:\n"
                "    v = positive_initial_vector()\n"
                "    for row in burn_in + measured_rows:\n"
                "        tau = sample_bonds(xoshiro256pp)\n"
                "        v = apply_random_transfer(v, tau, K_N)\n"
                "        scale = l1_norm(v)\n"
                "        v /= scale\n"
                "        if measured: block_log_norm += log(scale)\n"
                "average block_log_norm/(rows*L) after each disorder history",
                "Normalization is not an arbitrary numerical trick: each removed log "
                "scale is precisely the incremental free-energy information needed by the "
                "Lyapunov estimator.",
            ),
            Paragraph(
                "A maximum-width random row is sliced into nested prefixes for all smaller "
                "widths. This common-disorder construction sharply reduces noise in the "
                "difference across L, which determines the Casimir slope. It also creates "
                "cross-width covariance. The bootstrap must therefore resample an entire "
                "width vector together. Resampling each width independently would destroy "
                "the designed covariance and misstate the uncertainty of c_eff."
            ),
            Equation(
                "phi_L = phi_infinity + pi c_eff/(6 L^2) + a/L^4",
                "The sign is positive because phi denotes a log-partition density rather "
                "than the conventional negative free energy. The fit includes L=4 through "
                "14 and an L^-4 correction. A frozen L_min=6 refit tests whether the "
                "smallest width drives the result.",
                "7",
            ),
            Paragraph(
                "Eight independent disorder replicas each contain 2,097,152 measured rows "
                "after 4,096 burn-in rows. Blocks contain 16,384 rows. Long blocks preserve "
                "short-range serial dependence within a transfer product, while multiple "
                "replicas reveal whether one disorder stream dominates. A paired "
                "bootstrap resamples replica-block units while keeping their vector of "
                "widths intact."
            ),
            Equation(
                "d phi/dK |_(K_N) = 2 tanh(K_N)",
                "The Nishimori energy identity is evaluated through a centered common-"
                "disorder finite difference with delta K=10^-4. Reusing exactly the same "
                "bond rows on both sides greatly reduces variance. Agreement checks the "
                "coupling convention, bond signs, transfer normalization, and the "
                "configured Nishimori relation at once.",
                "8",
            ),
            Callout(
                "Nishimori result",
                f"The ordinary quenched estimate is c_eff={model.estimate:.6f}, "
                f"SE={model.standard_error:.6f}, and 95% CI "
                f"[{model.ci95[0]:.6f}, {model.ci95[1]:.6f}]. The target 0.464 lies inside "
                "the interval, and all nine required validation gates pass.",
                "result",
            ),
            *figures,
            _parameter_table(model),
            *_parameter_explanations(model),
            _gate_table(model),
            Paragraph(
                "The dominant uncertainty is disorder sampling rather than thermal spin "
                "sampling, because the transfer operation sums thermal boundary states "
                "deterministically for each random row. Finite-width corrections remain a "
                "separate systematic concern. The paired fit-window interval contains "
                "zero, so the present data do not resolve a significant L_min shift, but "
                "that diagnostic does not prove that every higher-order correction is "
                "negligible."
            ),
        ),
    )


def _weak_section(model: ModelResult) -> Section:
    figures = _model_figures(model, _weak_captions())
    return Section(
        "Weak Self-Dual Majorana Network",
        model.slug,
        (
            PageBreak(),
            Paragraph(
                "The weak self-dual model is a monitored Majorana network rather than an "
                "equilibrium spin system. Its state is Gaussian, so it can be represented "
                "by a real antisymmetric covariance matrix Gamma instead of an exponentially "
                "large many-body wavefunction. A measurement layer alternates onsite and "
                "bond Majorana bilinears. At theta=pi/4 and equal weak couplings, a "
                "one-Majorana translation exchanges the electric and magnetic descriptions."
            ),
            Paragraph(
                "Gaussian covariance methods make the production widths feasible, but they "
                "must preserve physical constraints. For a pure state, Gamma is "
                "antisymmetric and Gamma squared is -I up to floating-point error. Weak "
                "measurement updates are fractional-linear transformations of Gamma. "
                "Periodic stabilization projects numerical drift back toward the pure "
                "Gaussian manifold, and the maximum invariant error is recorded rather "
                "than silently corrected."
            ),
            Equation(
                "P(s|Gamma) = [1 + s tanh(beta) <i gamma_a gamma_b>_Gamma]/2",
                "The binary outcome s is sampled from the current state, so outcomes are "
                "Born-correlated in space and time. Replacing them with independent fair "
                "signs would define a different disorder ensemble. With "
                "beta=asinh(1)=0.881373587019543, each probability depends on the measured "
                "bilinear expectation encoded by Gamma.",
                "9",
            ),
            Paragraph(
                "A direct Shannon estimator would accumulate the realized surprise "
                "-log P(s|Gamma). The implementation uses a Rao-Blackwellized alternative: "
                "before drawing s, it records the conditional binary entropy of that "
                "measurement. Averaging the conditional expectation removes the extra "
                "coin-flip variance while leaving the ensemble mean unchanged. This "
                "variance reduction made the target precision practical without changing "
                "the Born trajectory used to update the state."
            ),
            Equation(
                "H_2(q) = -q log q - (1-q) log(1-q)",
                "Here q is the conditional probability of one outcome. The entropy is "
                "summed over all measurements and normalized per measurement row. One "
                "circuit period contains two rows, onsite and bond. Forgetting this factor "
                "of two would rescale the extensive rate and its Casimir coefficient.",
                "10",
            ),
            CodeBlock(
                "Born-correlated Gaussian trajectory",
                "Gamma = vacuum_covariance(L)\n"
                "for layer in burn_in + measured_layers:\n"
                "    for measurement_row in [onsite, bond]:\n"
                "        for (a,b) in row_pairs:\n"
                "            q = born_probability(Gamma, a, b, beta)\n"
                "            if measured: entropy_sum += binary_entropy(q)\n"
                "            s = sample_bernoulli(q, xoshiro256pp)\n"
                "            Gamma = weak_gaussian_update(Gamma, a, b, s, beta)\n"
                "    periodically_stabilize_and_check(Gamma)",
                "The entropy record is Rao-Blackwellized, but the state update still uses "
                "the sampled outcome. Consequently the method reduces estimator variance "
                "without replacing the physical trajectory distribution.",
            ),
            Equation(
                "gamma_1(L) = f_infinity L - pi c_eff/(6 L) + a/L^3",
                "gamma_1 is an entropy or Shannon free-energy rate per longitudinal layer. "
                "It is extensive in circumference, so the universal term scales as 1/L "
                "instead of 1/L^2. Dividing the equation by L recovers the same structural "
                "Casimir scaling used in the other chapters.",
                "11",
            ),
            Paragraph(
                "The final refinement uses even widths 6 through 32, 128 independent "
                "streams per width, 20L burn-in layers, and 200L measured layers. Blocks "
                "contain 5L layers. Even widths preserve the network geometry and sector "
                "conventions. Increasing both length and stream count addresses two "
                "different uncertainties: longer streams stabilize time averages, while "
                "more streams improve independent-trajectory sampling and bootstrap "
                "reliability."
            ),
            Paragraph(
                "Self-duality is checked using electric and magnetic vortex densities "
                "computed from spacetime sign tiles. A one-edge defect creates adjacent "
                "vortices of the two species, providing a small exact geometry test. In "
                "production, the paired electric-minus-magnetic difference is divided by "
                "its standard error. The observed z score is -1.460, inside the declared "
                "two-sided 95% threshold."
            ),
            Callout(
                "Weak self-dual result",
                f"The estimate is c_eff={model.estimate:.6f}, "
                f"SE={model.standard_error:.6f}, and 95% CI "
                f"[{model.ci95[0]:.6f}, {model.ci95[1]:.6f}]. The target 0.447 is inside "
                "the interval, whose half-width is about 0.00837. All ten required gates "
                "pass.",
                "result",
            ),
            *figures,
            _parameter_table(model),
            *_parameter_explanations(model),
            _gate_table(model),
            Paragraph(
                "The strongest remaining systematic is finite-size model choice. The "
                "primary L^-3 correction, alternative minimum widths, a dropped large "
                "width, doubled blocks, and extra burn-in produce a systematic center "
                "spread of about 0.00553. The maximum paired shift is only 0.594 standard "
                "errors. These tests support stability at the claimed resolution while "
                "remaining honest about the difference between sampling error and fit "
                "model uncertainty."
            ),
        ),
    )


def _comparison(clean: ModelResult, nishimori: ModelResult, weak: ModelResult) -> Section:
    models = (clean, nishimori, weak)
    rows = tuple(
        (
            model.name,
            _observable(model.slug),
            _sampler(model.slug),
            _oracle(model.slug),
            f"{(model.estimate-model.target)/model.standard_error:+.2f}",
        )
        for model in models
    )
    return Section(
        "Cross-Model Comparison",
        "cross-model-comparison",
        (
            Paragraph(
                "The most useful comparison is a map from a universal idea to three "
                "model-specific realizations. In every case, a long cylinder or strip has "
                "an extensive bulk contribution plus a circumference-dependent Casimir "
                "term. The central charge is inferred from the coefficient of that small "
                "term. What changes is the object whose logarithm or information rate is "
                "accumulated and the probability measure under which it is averaged."
            ),
            Table(
                "Estimator and validation comparison",
                ("Model", "Finite-size observable", "Sampled randomness", "Strong oracle", "Target z"),
                rows,
                "Target z is (estimate-target)/SE and is shown only as a normalized "
                "summary. The fitted datasets, correction models, and error structures "
                "differ, so equal z values would not imply equal evidential strength.",
            ),
            Paragraph(
                "In clean Ising, Monte Carlo samples thermal spin configurations and "
                "thermodynamic integration reconstructs an absolute free energy from an "
                "exact anchor. In Nishimori Ising, the transfer step sums thermal boundary "
                "spins while Monte Carlo samples quenched bonds; log normalization factors "
                "give a disorder-averaged Lyapunov rate. In the weak self-dual network, "
                "Monte Carlo samples state-dependent Born outcomes and covariance updates "
                "carry memory from one measurement to the next."
            ),
            Paragraph(
                "The error bars are therefore not interchangeable. The clean result "
                "propagates correlated energy estimates across a coupling grid. The "
                "Nishimori result must preserve covariance across widths created by common "
                "disorder. The weak self-dual result must capture autocorrelation within "
                "streams and heterogeneity across independent trajectories. Bootstrap "
                "resampling is used in all three analyses, but the resampling unit follows "
                "the data-generating process rather than a universal recipe."
            ),
            Figure(
                Path("generated/target-deviation.png"),
                "Normalized deviation of each central-charge estimate from its benchmark.",
                "Each point is the estimate-minus-target difference divided by its reported "
                "standard error. The reference band makes statistical consistency easy to "
                "read without hiding the absolute intervals.",
                "A small normalized deviation cannot diagnose shared model bias, incorrect "
                "ensemble choice, or underestimated systematic uncertainty.",
            ),
            Figure(
                Path("generated/precision-runtime.png"),
                "Separate panels compare confidence-interval half-width and recorded runtime.",
                "Precision and runtime are displayed on separate axes and panels to avoid a "
                "dual-axis visual correlation. The chart describes these frozen runs.",
                "Runtime depends on algorithms, widths, sample budgets, compilation, and "
                "hardware; it is not a universal complexity benchmark.",
            ),
            Figure(
                Path("generated/validation-gates.png"),
                "Matrix of required validation gates for the three model workflows.",
                "Green cells represent passed required checks; neutral cells indicate that "
                "a model uses a different oracle rather than lacking validation.",
                "Counting gates does not rank scientific quality because one strong exact "
                "oracle may constrain more failure modes than several narrow diagnostics.",
            ),
            Callout(
                "Shared implementation principle",
                "Estimate the small universal term only after validating the much larger "
                "bulk calculation. Exact identities, symmetry checks, replay tests, and "
                "invariant bounds are designed to fail when the model or normalization is "
                "wrong, even if a flexible finite-size fit could still land near the "
                "literature value.",
                "principle",
            ),
            Paragraph(
                "The progression also explains why variance reduction changes form. Wolff "
                "updates attack critical slowing down in configuration space. Common "
                "disorder attacks variance in finite-size differences. Rao-Blackwellization "
                "removes conditional measurement noise. Each method exploits structure in "
                "its probability model; applying it outside that structure could bias the "
                "answer."
            ),
        ),
    )


def _errors(clean: ModelResult, nishimori: ModelResult, weak: ModelResult) -> Section:
    return Section(
        "Error and Sensitivity Analysis",
        "error-analysis",
        (
            Paragraph(
                "Uncertainty is separated into sampling, numerical, finite-size, and model "
                "components. A single confidence interval usually quantifies only part of "
                "this hierarchy. Reporting one number without identifying its resampling "
                "unit can be actively misleading: treating correlated blocks as independent "
                "shrinks error bars, while treating common-width disorder as independent "
                "throws away useful covariance and can inflate them."
            ),
            Paragraph(
                "Autocorrelation reduces the amount of independent information in a time "
                "series. Blocking replaces many closely related measurements with fewer "
                "block summaries whose between-block variation is more informative. The "
                "weak self-dual analysis additionally estimates effective sample size. Its "
                "minimum ESS exceeds 4,500, comfortably above the declared gate of 100. "
                "That large margin supports the bootstrap but does not remove finite-size "
                "systematics."
            ),
            Paragraph(
                "The clean workflow contains a distinct quadrature error because free "
                "energy is reconstructed by integrating mean energy over K. Simpson's rule "
                "has high deterministic order for smooth functions, but the integrand is "
                "itself noisy. The nested-grid difference is therefore interpreted relative "
                "to the bootstrap variation, not as an exact truncation error. Measurements "
                "on shared K nodes are kept aligned during resampling."
            ),
            Paragraph(
                "The Nishimori workflow's major challenge is quenched heterogeneity. A rare "
                "disorder region can affect a long product of transfer operators. First-"
                "versus-second-half and leave-one-replica-out fits test whether the result "
                "depends on time position or one stream. The negative-bond frequency checks "
                "the input distribution, and the energy identity checks a derivative of "
                "the output. Passing both constrains different ends of the computation."
            ),
            Paragraph(
                "The weak self-dual workflow adds floating-point manifold error. Covariance "
                "updates involve matrix inverses or equivalent low-rank formulas whose "
                "roundoff can accumulate. Antisymmetry, purity, probability bounds, and "
                "dense small-system trajectory agreement are tested. The maximum production "
                "invariant error, about 2.54e-13, is far below the 1e-9 gate and too small "
                "to explain the central-charge uncertainty."
            ),
            Table(
                "Headline statistical precision",
                ("Model", "SE", "95% half-width", "|estimate-target|", "|difference|/SE"),
                tuple(
                    (
                        model.name,
                        f"{model.standard_error:.6f}",
                        f"{(model.ci95[1]-model.ci95[0])/2:.6f}",
                        f"{abs(model.estimate-model.target):.6f}",
                        f"{abs(model.estimate-model.target)/model.standard_error:.3f}",
                    )
                    for model in (clean, nishimori, weak)
                ),
                "Bootstrap percentile intervals need not be exactly symmetric around the "
                "reported mean, so the half-width is descriptive rather than a substitute "
                "for the stored endpoints.",
            ),
            Paragraph(
                "Finite-size bias is probed by changing L_min and correction terms. This is "
                "not an invitation to choose the fit closest to a target. The primary fit "
                "is frozen, and alternatives are diagnostics. For weak self-duality, paired "
                "shifts exploit common underlying blocks. For Nishimori, the paired "
                "bootstrap interval for the L_min difference must contain zero. For clean "
                "Ising, both exact and Monte Carlo windows remain visible."
            ),
            Paragraph(
                "A 95% confidence interval has a repeated-sampling interpretation under the "
                "analysis assumptions. It does not assign a 95% probability that a fixed "
                "true value lies inside the realized interval, and it does not include "
                "unknown model misspecification. The report therefore says that a target is "
                "consistent with the data, not that the target has been proved."
            ),
            Callout(
                "Error-budget discipline",
                "More samples primarily reduce stochastic uncertainty. Larger widths and "
                "better correction models primarily address asymptotic bias. Exact oracles "
                "address implementation error. These remedies are not substitutes: a very "
                "long run of the wrong model produces a precise wrong answer.",
                "warning",
            ),
        ),
    )


def _implementation() -> Section:
    return Section(
        "Implementation and Reproducibility",
        "implementation",
        (
            Paragraph(
                "The code is organized around narrow scientific interfaces. Configuration "
                "parsers validate widths, sample budgets, tolerances, and fixed critical "
                "constants before output directories are populated. Geometry modules know "
                "which degrees of freedom interact. Numerical kernels update a lattice, "
                "transfer vector, or covariance matrix. Samplers own stream state and emit "
                "block records. Schema modules serialize records. Python loaders reject "
                "incompatible artifacts before fitting."
            ),
            Paragraph(
                "Resumability is stream based. A completed stream artifact includes its "
                "schema version, full configuration, stream identity, and estimate blocks. "
                "A manifest stores its SHA-256 digest. On restart, compatible artifacts are "
                "reused byte for byte; a mismatched digest or configuration stops the run. "
                "This is safer than appending to one giant file because interruption cannot "
                "leave an ambiguous half-record that later analysis accepts."
            ),
            CodeBlock(
                "Analysis data flow",
                "manifest, blocks, oracles = validate_and_load(run_dir)\n"
                "summary = aggregate_with_model_specific_covariance(blocks)\n"
                "fits = fit_finite_size_family(summary)\n"
                "bootstrap = resample_declared_independent_units(blocks)\n"
                "gates = evaluate_predeclared_checks(fits, oracles, diagnostics)\n"
                "write_processed_tables_plots_and_report(summary, fits, gates)",
                "The model-specific covariance step is intentionally explicit. A generic "
                "row-wise bootstrap would be shorter code but scientifically incorrect for "
                "at least one of the three datasets.",
            ),
            Paragraph(
                "Small exact tests have disproportionate value. The clean transfer action "
                "can be compared with a dense matrix at tiny L. The Nishimori disorder "
                "generator can be checked against configured bond probabilities and a "
                "small transfer product. The Majorana covariance update can be compared "
                "with dense Hilbert-space evolution across every short Born trajectory. "
                "These tests establish signs and normalizations before production-scale "
                "statistics make failures difficult to localize."
            ),
            Paragraph(
                "Production gates are data, not hidden conditions in prose. Each gate stores "
                "a name, criterion, observed value, required flag, and pass status. The "
                "analysis exits nonzero when a required gate fails, while diagnostic "
                "configurations can explicitly mark gates as non-production. The report "
                "lists every gate, which prevents a favorable headline result from hiding "
                "failed sampling or physics checks."
            ),
            Table(
                "Implementation principles",
                ("Principle", "Concrete mechanism", "Failure prevented"),
                (
                    ("Determinism", "Keyed Xoshiro256++ streams", "Thread scheduling changes the sample"),
                    ("Atomicity", "Temporary file followed by replacement", "Partial artifact appears valid"),
                    ("Compatibility", "Schema and full-configuration equality", "Mixed runs are analyzed together"),
                    ("Integrity", "SHA-256 artifact manifest", "Silent file corruption or replacement"),
                    ("Separation", "Rust sampling; Python analysis", "Exploratory plotting contaminates kernels"),
                    ("Predeclaration", "Frozen primary fit and required gates", "Selecting favorable diagnostics"),
                    ("Independent oracles", "Exact identities and dense small systems", "Correct-looking output from wrong equations"),
                ),
                "These principles are implementation choices because each blocks a known "
                "path to a scientifically misleading result.",
            ),
            Paragraph(
                "Reproduction begins with the frozen configurations and lock files. The "
                "Rust test suite should run before any production command. Python analysis "
                "tests should then validate loaders, fits, bootstraps, and report fields. "
                "A production rerun is expensive and is not necessary to regenerate this "
                "integrated report: its inputs are the already validated processed files "
                "and charts, whose hashes appear in the appendix."
            ),
            Callout(
                "Language boundary",
                "Rust owns random draws and numerical state evolution. Python owns data "
                "processing and visualization. The integrated report generator performs no "
                "Monte Carlo sampling, so rebuilding HTML or PDF cannot change a scientific "
                "estimate.",
                "principle",
            ),
        ),
    )


def _open_research(result: LearningMitResult) -> Section:
    evidence_rows = tuple(
        (f"{phi:.2f}", f"{score:.6f}", "exploratory")
        for phi, score in result.diii_evidence
    )
    return Section(
        "Open Research: Learning-Induced Metal-Insulator Transition",
        "learning-induced-mit",
        (
            PageBreak(),
            Callout(
                "Exploratory result—not a fourth benchmark card",
                "This chapter is deliberately separated from the three verified central-"
                "charge benchmarks. Its frozen status is "
                f"{result.status}. The XY validation gate passed, but the generic DIII "
                "scan was inconclusive under the predeclared phase-persistence rule.",
                "warning",
            ),
            Paragraph(
                "The open question is whether changing the physical measurement axis in "
                "a monitored surface-code tensor network drives a transition between "
                "extended, metal-like Majorana correlations and localized, insulator-like "
                "correlations. Unlike the preceding benchmark chapters, no target DIII "
                "central charge was supplied. The calculation must first reproduce a known "
                "transition on the special XY line and only then search a generic symmetry-"
                "class-DIII cut without selecting a favorable point after seeing the data."
            ),
            Equation(
                "sigma(theta,phi) = sin(theta) cos(phi) X + sin(theta) sin(phi) Y + cos(theta) Z",
                "The XY validation line fixes theta/pi=0.5. The exploratory generic cut "
                f"fixes theta/pi={result.diii_theta_pi:.2f}; nonzero polar and azimuthal "
                "components remove the special class-D block decomposition.",
                "25",
            ),
            Equation(
                "S_L(ell) = (c_eff^S(L)/3) log[(L/pi) sin(pi ell/L)] + b_L + q_L cos(2 pi ell/L)/L^2",
                "The entanglement estimator fits only the central interval "
                "1/4 <= ell/L <= 3/4, where endpoint and lattice effects are smaller. "
                "Each width has its own offset and oscillatory correction; the fitted "
                "c_eff^S(L) values are then extrapolated linearly in 1/L^2.",
                "26",
            ),
            Equation(
                "gamma(L) = f_bulk L + A/L + B/L^3; c_eff^C = 6 A alpha / pi",
                "The independent Casimir route isolates the 1/L curvature of the frozen "
                "free-energy-rate proxy gamma. The anisotropy calibration alpha converts "
                "temporal and spatial units. The 1/L^3 term absorbs the leading declared "
                "finite-size correction rather than forcing it into A.",
                "27",
            ),
            Paragraph(
                "Rust generated every conditional Born outcome with Xoshiro256++ and "
                "evolved a real antisymmetric Gaussian covariance matrix. Rational "
                "measurement updates were followed by outcome-dependent orthogonal "
                "rotations. An orthogonal polar projection after each period removed "
                "floating-point drift in Gamma^2=-I. Python read only frozen block data, "
                "compared entanglement-arc models, evaluated phase evidence, and rendered "
                "the reports; it performed no Monte Carlo evolution."
            ),
            CodeBlock(
                "Predeclared two-stage decision",
                "run_xy_validation(theta_pi=0.50)\n"
                "if xy_bracket overlaps reference_window:\n"
                "    scan_generic_diii(theta_pi=0.45)\n"
                "    publish_candidate_only_if_adjacent_phase_evidence_persists\n"
                "else:\n"
                "    status = validation_failed",
                "The branch structure prevents a generic-DIII claim when the known XY "
                "transition is not reproduced. A missing DIII bracket is retained as an "
                "inconclusive exploratory result rather than repaired by post hoc scans.",
            ),
            Table(
                "Frozen open-research decision",
                ("Quantity", "Frozen value", "Claim class"),
                (
                    (
                        "XY bracket phi/pi",
                        f"[{result.xy_bracket[0]:.2f}, {result.xy_bracket[1]:.2f}]",
                        "validation",
                    ),
                    (
                        "XY reference window",
                        f"[{result.xy_reference_window[0]:.2f}, "
                        f"{result.xy_reference_window[1]:.2f}]",
                        "predeclared validation",
                    ),
                    ("DIII bracket", "none", "exploratory / inconclusive"),
                    (
                        "candidate phi/pi",
                        f"{result.candidate_phi_pi:.2f}",
                        result.candidate_status,
                    ),
                    (
                        "entanglement c_eff",
                        f"{result.entanglement_c_eff:.6f} "
                        f"[{result.entanglement_interval[0]:.6f}, "
                        f"{result.entanglement_interval[1]:.6f}]",
                        "exploratory / not published",
                    ),
                    (
                        "Casimir-anisotropy c_eff",
                        f"{result.casimir_c_eff:.6f} "
                        f"[{result.casimir_interval[0]:.6f}, "
                        f"{result.casimir_interval[1]:.6f}]",
                        "exploratory / not published",
                    ),
                    (
                        "anisotropy alpha",
                        f"{result.alpha:.6f}" if result.alpha is not None else "unavailable",
                        "unstable / not published",
                    ),
                    (
                        "failed claim gates",
                        ", ".join(result.claim_reasons),
                        result.claim_status,
                    ),
                    (
                        "runtime",
                        f"{result.elapsed_s:.3f} s",
                        f"reserve used; below {result.hard_stop_s:.0f} s hard stop",
                    ),
                ),
                "Both numerical estimates are shown because they exist, but neither is a "
                "published universal constant. Failed gates remain part of the result.",
            ),
            Figure(
                result.figures["en"][0],
                "Chord-length entropy fit at the selected exploratory angle.",
                "The central-interval entropy data are compared with the conformal chord "
                "form used to obtain c_eff^S(L).",
                "A visually smooth chord fit does not remove cross-width extrapolation "
                "uncertainty or establish a DIII critical point.",
            ),
            Figure(
                result.figures["en"][1],
                "Finite-size extrapolation of the entanglement effective central charge.",
                f"The intercept is {result.entanglement_c_eff:.6f}, with 95% interval "
                f"[{result.entanglement_interval[0]:.6f}, "
                f"{result.entanglement_interval[1]:.6f}].",
                "The interval is broad because individual-width slopes are noisy and "
                "strongly finite-size dependent.",
            ),
            Figure(
                result.figures["en"][2],
                "Casimir fit of the free-energy-rate proxy across seven widths.",
                "The bulk, 1/L Casimir, and 1/L^3 correction terms are fitted together.",
                "The Casimir amplitude becomes an effective central charge only after the "
                "separately estimated anisotropy factor is applied.",
            ),
            Figure(
                result.figures["en"][3],
                "Residuals of the declared Casimir finite-size model.",
                "Residual structure tests whether the selected correction family absorbs "
                "the measured width dependence.",
                "Small residuals alone cannot rescue an unstable anisotropy calibration.",
            ),
            Figure(
                result.figures["en"][4],
                "Anisotropy stability under the declared analysis windows.",
                f"The frozen alpha estimate is {result.alpha:.6f}; the stability gate "
                f"passed={result.alpha_stable}.",
                "Window sensitivity propagates directly into c_eff^C and is therefore a "
                "required publication gate.",
            ),
            Figure(
                result.figures["en"][5],
                "Direct comparison of the two effective-central-charge estimators.",
                f"Entanglement gives {result.entanglement_c_eff:.6f}, whereas the "
                f"Casimir-anisotropy route gives {result.casimir_c_eff:.6f}.",
                "Their uncertainty bands do not satisfy the predeclared agreement test; "
                "the discrepancy is reported rather than averaged away.",
            ),
            Table(
                "Exploratory DIII evidence scan",
                ("phi/pi (exploratory)", "evidence score (exploratory)", "label"),
                evidence_rows,
                "All values in this table are exploratory diagnostics. They are not "
                "published transition coordinates or universal quantities.",
            ),
            Paragraph(
                "The physical Born and deliberately nonphysical IID-sign controls differ "
                f"strongly: their frozen means are {result.born_mean:.6f} and "
                f"{result.iid_mean:.6f}, with z={result.negative_control_z:.2f}. This "
                "confirms that unconditional random signs cannot replace state-conditioned "
                "Born draws. Scientific oracles passed, all "
                f"{len(result.widths)} widths {result.widths} and {result.streams} streams "
                f"per point completed. Runtime {result.elapsed_s:.3f} s exceeded the "
                f"{result.ordinary_stop_s:.0f} s ordinary stop only under the predeclared "
                "largest-width reserve and remained below the hard stop."
            ),
            Callout(
                "What remains unresolved",
                "The present data produce two exploratory effective-central-charge "
                f"estimates but do not publish either one. The failed gates are "
                f"{', '.join(result.claim_reasons)}. A future study should first secure an "
                "adjacent phase bracket, then stabilize alpha with additional temporal "
                "and spatial windows, and finally demand estimator agreement on new "
                "independent streams. Inconclusive does not mean that a transition is absent.",
                "principle",
            ),
        ),
    )


def _conclusions(clean: ModelResult, nishimori: ModelResult, weak: ModelResult) -> Section:
    return Section(
        "Conclusions",
        "conclusions",
        (
            Paragraph(
                "The clean Ising calculation recovers the expected c=1/2 through two "
                "independent numerical routes. The transfer result "
                f"{clean.exact_estimate:.6f} demonstrates that the finite-size coefficient "
                "and sign conventions are correct, while the Monte Carlo result "
                f"{clean.estimate:.6f} demonstrates that cluster sampling and "
                "thermodynamic integration reproduce the same physics within uncertainty."
            ),
            Paragraph(
                "The Nishimori calculation verifies the ordinary quenched target 0.464, "
                f"obtaining {nishimori.estimate:.6f}. The result is not the approximately "
                "0.522 quantity associated with a different replica or Born weighting. "
                "Common-disorder width vectors, paired bootstrap analysis, the Nishimori "
                "energy identity, and the bond-frequency audit collectively support the "
                "ensemble interpretation."
            ),
            Paragraph(
                "The weak self-dual calculation obtains "
                f"{weak.estimate:.6f}, consistent with 0.447 at a 95% half-width below "
                "0.01. Gaussian covariance oracles, Born trajectory enumeration, "
                "self-duality diagnostics, ESS, residual tests, and fit variants all pass. "
                "Rao-Blackwellization is central to the achieved precision because it "
                "removes conditional outcome noise without changing state evolution."
            ),
            Paragraph(
                "Across all three models, central-charge verification is best understood "
                "as a chain of controlled reductions. Microscopic dynamics produce block "
                "observables; blocks produce finite-size estimates with the correct "
                "covariance; scaling fits isolate a small universal term; resampling "
                "quantifies stochastic variation; alternative fits expose sensitivity; "
                "and independent oracles test the chain at points where agreement with a "
                "target cannot."
            ),
            Callout(
                "Final assessment",
                "The frozen evidence supports all three declared benchmarks at its stated "
                "resolution. The strongest conclusion is methodological: exact baselines, "
                "ensemble-aware resampling, structural oracles, and transparent systematic "
                "checks make central-charge estimates auditable rather than merely close.",
                "result",
            ),
        ),
    )


def _appendices(clean: ModelResult, nishimori: ModelResult, weak: ModelResult) -> Section:
    glossary_rows = (
        ("L", "Cylinder or strip circumference; the finite-size scaling variable"),
        ("M", "Longitudinal size of a torus or strip"),
        ("K, K_c", "Dimensionless coupling and clean critical coupling"),
        ("p, K_N", "Negative-bond probability and Nishimori-line coupling"),
        ("phi_L", "Quenched log-partition density at width L"),
        ("Gamma", "Real antisymmetric Majorana covariance matrix"),
        ("gamma_1(L)", "Weak self-dual Shannon free-energy rate"),
        ("c", "Central charge in the clean unitary benchmark"),
        ("c_eff", "Effective Casimir coefficient in disordered or monitored ensembles"),
        ("SE", "Estimated standard error of an estimator"),
        ("95% CI", "Bootstrap confidence interval with nominal 95% coverage"),
        ("ESS", "Effective sample size after accounting for correlation"),
        ("a", "Leading finite-size correction coefficient"),
        ("R", "Number of replicas or independent streams, according to model"),
    )
    provenance_rows = []
    for model in (clean, nishimori, weak):
        provenance_rows.extend(
            (model.name, path, digest) for path, digest in model.provenance.items()
        )
    reference_rows = (
        ("Finite-size CFT", "H. W. J. Bloete, J. L. Cardy, and M. P. Nightingale, Phys. Rev. Lett. 56, 742 (1986)."),
        ("Finite-size CFT", "I. Affleck, Phys. Rev. Lett. 56, 746 (1986)."),
        ("Ising solution", "L. Onsager, Phys. Rev. 65, 117 (1944)."),
        ("Nishimori line", "H. Nishimori, Prog. Theor. Phys. 66, 1169 (1981)."),
        ("Challenge reference", "Open quantum criticality benchmark, arXiv:2502.14034 and Quantum Harness issue #122."),
    )
    return Section(
        "Appendices",
        "appendices",
        (
            PageBreak(),
            Paragraph(
                "The appendices collect definitions and audit information so that the main "
                "chapters can remain readable. Parameter meanings are given in the model "
                "chapters; the glossary standardizes symbols that recur across different "
                "normalization conventions. Provenance hashes bind every displayed input "
                "to an exact byte sequence."
            ),
            Table(
                "Equation and notation glossary",
                ("Symbol", "Meaning"),
                glossary_rows,
                "A symbol can denote a model-specific observable only where its chapter "
                "defines the convention. In particular, phi_L and gamma_1(L) are not the "
                "same microscopic quantity.",
            ),
            Table(
                "Selected primary references",
                ("Topic", "Reference"),
                reference_rows,
                "References identify the standard finite-size arguments and model context. "
                "All numerical claims in this report are taken from the frozen local "
                "artifacts listed below.",
            ),
            Table(
                "Frozen-input provenance",
                ("Model", "Relative path", "SHA-256"),
                tuple(provenance_rows),
                "Hashes are calculated by the report loader. A changed byte changes the "
                "digest and therefore invalidates an otherwise identical-looking report "
                "build.",
            ),
            Paragraph(
                "A reproducibility audit should begin by checking these digests, then run "
                "the report test suite, and finally inspect both output formats. Re-running "
                "the expensive simulations is a separate operation. If it is performed, "
                "the new run must receive a new result directory and must not overwrite "
                "the frozen evidence used here."
            ),
        ),
    )


def _parameter_table(model: ModelResult) -> Table:
    return Table(
        f"{model.name} production parameters",
        ("Symbol", "Value", "Meaning", "Sensitivity"),
        model.parameters,
        "Values come from the frozen production manifest or the recorded algorithm "
        "contract. Sensitivity describes the main scientific role rather than a "
        "dimensionless derivative.",
    )


def _parameter_explanations(model: ModelResult) -> Tuple[Paragraph, ...]:
    paragraphs = []
    for symbol, value, meaning, sensitivity in model.parameters:
        paragraphs.append(
            Paragraph(
                f"Parameter {symbol} is set to {value}. It represents {meaning.lower()}. "
                f"Its principal role is that it {sensitivity.lower()}. This value is not "
                "a post-fit adjustment: it belongs to the frozen simulation contract. "
                "Changing it can alter computational cost, sampling correlation, "
                "finite-size bias, or even the physical ensemble, depending on the "
                "parameter. A valid sensitivity study would create a separately identified "
                "run and compare paired observables where possible rather than editing the "
                "record after inspecting the central-charge estimate."
            )
        )
    return tuple(paragraphs)


def _gate_table(model: ModelResult) -> Table:
    return Table(
        f"{model.name} validation gates",
        ("Gate", "Criterion", "Observed value", "Required", "Status"),
        tuple(
            (
                gate.name,
                gate.criterion,
                _format_value(gate.value),
                "yes" if gate.required else "no",
                "PASS" if gate.passed else "FAIL",
            )
            for gate in model.gates
        ),
        "A required failure stops the production analysis. Gate counts should not be "
        "used to rank models because the checks constrain different failure modes.",
    )


def _model_figures(model: ModelResult, captions: dict) -> Tuple[Figure, ...]:
    figures = []
    for path in model.figures:
        key = path.name
        caption, inference_limit = captions.get(
            key,
            (
                f"Recorded diagnostic for {model.name}.",
                "This diagnostic must be interpreted together with the stored numerical gates.",
            ),
        )
        figures.append(
            Figure(
                path,
                f"{model.name}: {key.replace('-', ' ').replace('_', ' ').removesuffix('.png')}.",
                caption,
                inference_limit,
            )
        )
    return tuple(figures)


def _clean_captions() -> dict:
    return {
        "central_charge_comparison.png": (
            "Independent transfer-matrix and Monte Carlo estimates are compared with c=1/2 across declared fit windows.",
            "Agreement does not by itself test thermalization or quadrature convergence; those appear in separate diagnostics.",
        ),
        "energy_vs_k.png": (
            "Measured energy density across the thermodynamic-integration grid for every width.",
            "Smooth curves support numerical integration but do not quantify correlation between measurements.",
        ),
        "fit_stability.png": (
            "Central-charge estimates for L_min=4, 6, and 8 expose sensitivity to the fit window.",
            "The plot is diagnostic; the primary L_min=6 window is not selected after viewing it.",
        ),
        "free_energy_scaling.png": (
            "Critical free-energy density versus 1/L^2 for exact and Monte Carlo routes, with the fitted Casimir curvature.",
            "A close fit cannot rule out still higher finite-size corrections outside the simulated widths.",
        ),
        "integration_convergence.png": (
            "Nested 65- and 129-point integration grids are compared on shared nodes.",
            "This tests grid resolution at current sampling precision, not exact quadrature error.",
        ),
        "replica_diagnostics.png": (
            "Half-chain drift and pairwise replica discrepancies are compared with predeclared thresholds.",
            "Passing finite diagnostics cannot prove a chain has sampled every exponentially rare configuration.",
        ),
    }


def _nishimori_captions() -> dict:
    return {
        "central_charge_bootstrap.png": (
            "Hierarchical paired-bootstrap distribution of the Nishimori effective central charge.",
            "The interval assumes the chosen replica-block units adequately represent disorder fluctuations.",
        ),
        "fit_window_stability.png": (
            "Primary L_min=4 and diagnostic L_min=6 fits are compared using paired resampling.",
            "Two windows do not exhaust all possible irrelevant-operator corrections.",
        ),
        "free_energy_fit.png": (
            "Quenched log-partition density versus 1/L^2 with the L^-4 corrected finite-size fit.",
            "Small residuals alone cannot validate the quenched ensemble or bond generator.",
        ),
        "negative_bond_frequency.png": (
            "Observed negative-bond frequency is compared with configured p using a z score.",
            "The marginal frequency does not test every spatial or temporal correlation of the RNG stream.",
        ),
        "nishimori_energy_identity.png": (
            "A common-disorder centered derivative is compared with the exact Nishimori identity.",
            "One identity strongly tests conventions but cannot identify every possible transfer-kernel defect.",
        ),
        "sampling_stability.png": (
            "First/second-half and leave-one-replica-out estimates reveal time or replica dominance.",
            "These diagnostics have finite power against rare-disorder tails.",
        ),
    }


def _weak_captions() -> dict:
    return {
        "convergence-ess.png": (
            "Effective sample size and lag-one correlation summarize trajectory convergence by width.",
            "ESS diagnoses sampling precision, not finite-size model bias.",
        ),
        "finite-size-scaling.png": (
            "The Shannon free-energy rate gamma_1(L) is fitted to an extensive term plus 1/L Casimir and 1/L^3 correction.",
            "The visual scale is dominated by the bulk term; residual and fit-variant plots are needed to judge the Casimir coefficient.",
        ),
        "fit-stability.png": (
            "Paired fit variants change minimum width, burn-in, block length, and included widths.",
            "The tested variants bound declared sensitivities but not every conceivable correction model.",
        ),
        "residuals.png": (
            "Studentized residuals and their trend against inverse width expose unresolved structure.",
            "Unstructured residuals support the fit but do not prove the asymptotic expansion is unique.",
        ),
        "self-duality.png": (
            "Electric and magnetic vortex densities are compared through their paired difference.",
            "Ensemble-level self-duality does not require equality on each individual trajectory.",
        ),
    }


def _observable(slug: str) -> str:
    return {
        "clean-ising": "Thermodynamically integrated free-energy density",
        "nishimori-ising": "Quenched transfer Lyapunov density",
        "weak-self-dual": "Born Shannon free-energy rate",
    }[slug]


def _sampler(slug: str) -> str:
    return {
        "clean-ising": "Thermal Wolff clusters",
        "nishimori-ising": "Quenched bond rows",
        "weak-self-dual": "State-conditioned Born outcomes",
    }[slug]


def _oracle(slug: str) -> str:
    return {
        "clean-ising": "Exact transfer matrix and c=1/2",
        "nishimori-ising": "Nishimori energy identity",
        "weak-self-dual": "Dense Gaussian/Born trajectory agreement",
    }[slug]


def _format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    return str(value)
