"""Build the generic document consumed by the harness report renderer."""


def build_report_document(summary: dict, manifest: dict) -> dict:
    config = manifest["config"]
    fit = summary["primary_fit"]
    interval = summary["central_charge_ci95"]
    gates = summary["gates"]
    required = bool(config["production_gates"])
    overall = gates["all_required_pass"]
    verdict_word = "PASS" if overall else "FAIL"
    if not required:
        verdict_word = "DIAGNOSTIC"

    return {
        "title": "Nishimori central-charge verification",
        "eyebrow": "Challenge #122 · Team 卧龙凤雏",
        "url": "https://github.com/QuantumBFS/quantum.harness/issues/122",
        "lede": (
            f"The ordinary quenched ±J Ising model gives c_eff={summary['central_charge']:.6f} "
            f"± {summary['central_charge_standard_error']:.6f}, with 95% interval "
            f"[{interval[0]:.6f}, {interval[1]:.6f}]. "
            f"Verification status: {verdict_word}."
        ),
        "sections": [
            _setup_section(config),
            _method_section(summary),
            _result_section(summary),
            _diagnostics_section(summary),
            _verification_section(summary, manifest),
            _reproduction_section(summary, manifest),
        ],
    }


def _setup_section(config: dict) -> dict:
    disorder = config["disorder"]
    return {
        "title": "Setup",
        "note": (
            "This is the ordinary quenched (replica-limit R→1) Nishimori benchmark "
            "near 0.464, not the Born-rule/higher-replica value near 0.522."
        ),
        "blocks": [
            {
                "kind": "kv",
                "pairs": [
                    ["Model", "Square-lattice ±J random-bond Ising model"],
                    [
                        "Antiferromagnetic probability",
                        f"p = {config['antiferromagnetic_probability']:.7f}",
                    ],
                    ["Nishimori coupling", f"K_N = {config['nishimori_k']:.16f}"],
                    ["Widths", ", ".join(str(value) for value in config["widths"])],
                    ["Replicas", str(disorder["replicas"])],
                    [
                        "Rows per replica",
                        f"{disorder['burn_in_rows']:,} burn-in + "
                        f"{disorder['measurement_rows']:,} measured",
                    ],
                    ["Random generator", "rand_xoshiro 0.8.1 · Xoshiro256++"],
                ],
            },
            {
                "kind": "equation",
                "tex": (
                    r"P(\tau_{ij}=-1)=p,\qquad "
                    r"K_N=\frac{1}{2}\log\frac{1-p}{p}"
                ),
            },
        ],
    }


def _method_section(summary: dict) -> dict:
    return {
        "title": "Quenched transfer product",
        "note": (
            "Rust sums the thermal spins exactly and samples only quenched bond disorder; "
            "each maximum-width row is sliced into nested prefixes for every width."
        ),
        "blocks": [
            {
                "kind": "equation",
                "tex": (
                    r"v_{r+1}(s')=e^{K\sum_i\tau^h_i s'_i s'_{i+1}}"
                    r"\sum_s e^{K\sum_i\tau^v_i s_i s'_i}v_r(s)"
                ),
            },
            {
                "kind": "text",
                "text": (
                    "The matrix-free operator costs $O(L2^L)$ per disorder row. "
                    "L1 normalization after every row turns accumulated log norms into "
                    "$\\phi_L=\\mathbb{E}[\\ln Z]/(ML)$ without overflow."
                ),
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "figures/free_energy_fit.png",
                        "caption": (
                            "Finite-size signal. Quenched free energy per site is plotted "
                            "against 1/L² with joint-block standard errors; the curved line is "
                            "the predeclared L⁻²+L⁻⁴ fit whose Casimir coefficient gives c_eff."
                        ),
                    }
                ],
            },
            {
                "kind": "table",
                "columns": ["L", "φ_L", "SE(φ_L)"],
                "rows": [
                    [str(width), f"{phi:.10f}", f"{error:.3e}"]
                    for width, phi, error in zip(
                        summary["widths"],
                        summary["phi"],
                        summary["phi_standard_error"],
                    )
                ],
                "numeric": [True, True, True],
            },
        ],
    }


def _result_section(summary: dict) -> dict:
    fit = summary["primary_fit"]
    diagnostic = summary["diagnostic_fit"]
    interval = summary["central_charge_ci95"]
    target_gate = next(
        gate for gate in summary["gates"]["gates"] if gate["name"] == "target_agreement"
    )
    return {
        "title": "Central charge",
        "note": (
            "The primary fit uses all six widths (L_min=4); L_min=6 is a frozen "
            "finite-size diagnostic."
        ),
        "blocks": [
            {
                "kind": "equation",
                "tex": r"\phi_L=\phi_\infty+\frac{\pi c_{\rm eff}}{6L^2}+\frac{a}{L^4}",
            },
            _verdict(
                target_gate["passed"],
                (
                    f"c_eff={summary['central_charge']:.6f}, SE="
                    f"{summary['central_charge_standard_error']:.6f}, 95% interval "
                    f"[{interval[0]:.6f}, {interval[1]:.6f}]; target 0.464."
                ),
            ),
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "figures/central_charge_bootstrap.png",
                        "caption": (
                            "Sampling distribution. Hierarchical resampling keeps each width "
                            "vector intact, preserving the common-disorder covariance that "
                            "controls the finite-size slope."
                        ),
                    },
                    {
                        "src": "figures/fit_window_stability.png",
                        "caption": (
                            f"Window check. L_min=4 gives {fit['central_charge']:.6f}; "
                            f"L_min=6 gives {diagnostic['central_charge']:.6f}. Error bars are "
                            "bootstrap standard errors and the dashed line is 0.464."
                        ),
                    },
                ],
            },
        ],
    }


def _diagnostics_section(summary: dict) -> dict:
    identity = summary["nishimori_energy_identity"]
    bond = summary["bond_frequency"]
    stability = summary["stability"]
    return {
        "title": "Scientific diagnostics",
        "note": "Independent identities test the model, disorder stream, and sampling stability.",
        "blocks": [
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "figures/sampling_stability.png",
                        "caption": (
                            "Sampling stability. First/second measurement halves and every "
                            "leave-one-replica-out refit remain visible; their discrepancies are "
                            "evaluated against the predeclared four-sigma limits."
                        ),
                    },
                    {
                        "src": "figures/nishimori_energy_identity.png",
                        "caption": (
                            "Nishimori identity. A centered common-disorder K derivative gives "
                            f"{identity['derivative']:.8f}, versus 2 tanh(K_N)="
                            f"{identity['expected']:.8f}; absolute error "
                            f"{identity['absolute_error']:.3g}."
                        ),
                    },
                    {
                        "src": "figures/negative_bond_frequency.png",
                        "caption": (
                            "Disorder audit. The observed negative-bond fraction "
                            f"{bond['observed_probability']:.8f} is compared with configured "
                            f"p={bond['expected_probability']:.7f}; z={bond['z_score']:.3f}."
                        ),
                    },
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["Half-run stability z", f"{stability['half_stability_z']:.3f}"],
                    [
                        "Maximum replica-deletion z",
                        f"{stability['replica_stability_z']:.3f}",
                    ],
                    ["Energy-identity error", f"{identity['absolute_error']:.6g}"],
                    ["Bond-frequency z", f"{bond['z_score']:.3f}"],
                ],
            },
        ],
    }


def _verification_section(summary: dict, manifest: dict) -> dict:
    blocks = [
        _verdict(gate["passed"], f"{gate['name']}: {gate['criterion']}; value={gate['value']}")
        for gate in summary["gates"]["gates"]
    ]
    blocks.append(
        {
            "kind": "table",
            "columns": ["Stage", "Seconds"],
            "rows": [
                ["Oracles", _seconds(manifest.get("oracle_elapsed_s"))],
                ["Rust simulation", _seconds(manifest.get("simulation_elapsed_s"))],
                ["Python analysis", _seconds(manifest.get("analysis_elapsed_s"))],
                ["End to end", _seconds(manifest.get("total_elapsed_s"))],
            ],
            "numeric": [False, True],
        }
    )
    return {
        "title": "Verification",
        "note": "All nine scientific, stability, and runtime gates are reported without selection.",
        "blocks": blocks,
    }


def _reproduction_section(summary: dict, manifest: dict) -> dict:
    return {
        "title": "Reproduction",
        "note": "Raw replica files are atomic, resumable, and SHA-256 recorded in the manifest.",
        "blocks": [
            {
                "kind": "code",
                "title": "Complete workflow",
                "text": "make setup\nmake test\nmake run",
            },
            {
                "kind": "code",
                "title": "Recorded Rust commands",
                "text": "\n".join(manifest.get("commands", [])),
            },
            {
                "kind": "kv",
                "pairs": [
                    ["Rust", manifest.get("rust_version", "")],
                    ["Python", manifest.get("python_version", "")],
                    ["Bootstrap seed", str(summary["bootstrap_seed"])],
                    ["Bootstrap samples", f"{summary['bootstrap_samples']:,}"],
                    ["Schema version", str(manifest.get("schema_version", 1))],
                ],
            },
        ],
    }


def _verdict(passed: bool, why: str) -> dict:
    return {
        "kind": "verdict",
        "status": "good" if passed else "bad",
        "label": "PASS" if passed else "FAIL",
        "why": why,
    }


def _seconds(value) -> str:
    return "pending" if value is None else f"{float(value):.3f}"
