"""Build the generic document consumed by the harness report renderer."""


def build_report_document(summary: dict, manifest: dict) -> dict:
    config = manifest["config"]
    interval = summary["central_charge_ci95"]
    required = bool(config["production_gates"])
    overall = summary["gates"]["all_required_pass"]
    verdict = "PASS" if overall else "FAIL"
    if not required:
        verdict = "DIAGNOSTIC"
    return {
        "title": "Weak self-dual central-charge verification",
        "eyebrow": "Challenge #122 · Team 卧龙凤雏",
        "url": "https://github.com/QuantumBFS/quantum.harness/issues/122",
        "lede": (
            f"Born-correlated Majorana trajectories give c_eff={summary['central_charge']:.6f} "
            f"± {summary['central_charge_standard_error']:.6f}, with 95% interval "
            f"[{interval[0]:.6f}, {interval[1]:.6f}]. Status: {verdict}."
        ),
        "sections": [
            _setup(config),
            _method(summary),
            _result(summary),
            _diagnostics(summary),
            _verification(summary),
            _reproduction(summary, manifest),
        ],
    }


def _setup(config):
    return {
        "title": "Physical setup",
        "note": "The W=+1, P=+1 vacuum sector is simulated at the isotropic weak self-dual point.",
        "blocks": [
            {
                "kind": "kv",
                "pairs": [
                    ["Critical angle", "θ = π/4"],
                    ["Coupling", f"β = β′ = {config['beta']:.15f}"],
                    ["Widths", ", ".join(str(value) for value in config["widths"])],
                    ["Random generator", "rand_xoshiro 0.8.1 · Xoshiro256++"],
                    ["Disorder", "Sequential state-conditioned Born sampling"],
                ],
            },
            {
                "kind": "equation",
                "tex": r"P(s|\Gamma)=\frac{1+s\tanh(\beta)\langle i\gamma_a\gamma_b\rangle_\Gamma}{2}",
            },
        ],
    }


def _method(summary):
    return {
        "title": "Born-correlated Gaussian evolution",
        "note": (
            "Rust samples every binary outcome from the current covariance matrix. "
            "The accumulated Born surprise is the vacuum Lyapunov/free-energy estimator."
        ),
        "blocks": [
            {
                "kind": "equation",
                "tex": r"\gamma_1(L)=f_\infty L-\frac{\pi c_{\rm eff}}{6L}+\frac{a}{L^3}",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "figures/finite-size-scaling.png",
                        "caption": "Finite-size scaling of the Born Shannon free energy per cylinder layer.",
                    },
                    {
                        "src": "figures/residuals.png",
                        "caption": "Studentized residuals expose unresolved finite-width trends.",
                    },
                ],
            },
            {
                "kind": "table",
                "columns": ["L", "γ₁(L)", "SE"],
                "rows": [
                    [str(width), f"{value:.10f}", f"{error:.3e}"]
                    for width, value, error in zip(
                        summary["widths"],
                        summary["gamma"],
                        summary["gamma_standard_error"],
                    )
                ],
                "numeric": [True, True, True],
            },
        ],
    }


def _result(summary):
    interval = summary["central_charge_ci95"]
    return {
        "title": "Central charge and fit stability",
        "note": (
            f"Primary c_eff={summary['central_charge']:.6f}; 95% interval "
            f"[{interval[0]:.6f}, {interval[1]:.6f}]."
        ),
        "blocks": [
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "figures/fit-stability.png",
                        "caption": (
                            "The predeclared fit stability suite changes Lmin, burn-in, "
                            "block length, and the largest included width."
                        ),
                    }
                ],
            },
            {
                "kind": "text",
                "text": (
                    f"The systematic fit stability spread is "
                    f"{summary['fit_stability']['systematic_spread']:.6g}."
                ),
            },
        ],
    }


def _diagnostics(summary):
    dual = summary["self_duality"]
    return {
        "title": "Sampling and self-duality diagnostics",
        "note": (
            f"Electric and magnetic vortex densities are {dual['electric_density']:.6f} "
            f"and {dual['magnetic_density']:.6f}; paired z={dual['z_score']:.3f}."
        ),
        "blocks": [
            {
                "kind": "figures",
                "items": [
                    {"src": "figures/convergence-ess.png", "caption": "ESS and autocorrelation by width."},
                    {"src": "figures/self-duality.png", "caption": "Electric–magnetic self-duality check."},
                ],
            }
        ],
    }


def _verification(summary):
    return {
        "title": "Verification",
        "note": "Every immutable scientific and statistical gate remains visible.",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good" if gate["passed"] else "bad",
                "label": "PASS" if gate["passed"] else "FAIL",
                "why": f"{gate['name']}: {gate['criterion']}; value={gate['value']}",
            }
            for gate in summary["gates"]["gates"]
        ],
    }


def _reproduction(summary, manifest):
    return {
        "title": "Reproduction",
        "note": "Raw streams are atomic, resumable, seed-recorded, and SHA-256 audited.",
        "blocks": [
            {"kind": "code", "title": "Complete workflow", "text": "make setup\nmake test\nmake run"},
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
                ],
            },
        ],
    }
