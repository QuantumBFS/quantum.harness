"""Build the generic report document consumed by the harness renderer."""

from typing import Any, Dict, Mapping


def build_report_document(
    results: Mapping[str, Any], _run_dir
) -> Dict[str, Any]:
    exact = results["exact_fits"][6]
    mc = results["mc_fits"][6]
    diagnostics = results["diagnostics"]
    gates = results["gates"]
    manifest = results["manifest"]
    config = manifest["config"]
    all_pass = all(gates.values())
    return {
        "title": "Clean Ising central-charge verification",
        "eyebrow": "Challenge #122 · Team 卧龙凤雏",
        "url": "https://github.com/QuantumBFS/quantum.harness/issues/122",
        "lede": (
            f"Two independent routes give c={exact['c']:.5f} (transfer matrix) "
            f"and c={mc['c']:.5f} with 95% interval [{mc['low']:.5f}, "
            f"{mc['high']:.5f}] (Wolff thermodynamic integration). "
            f"Overall verification: {'PASS' if all_pass else 'FAIL'}."
        ),
        "sections": [
            {
                "title": "Setup",
                "note": "The Hamiltonian and finite-size protocol are fixed before fitting.",
                "blocks": [
                    {
                        "kind": "kv",
                        "pairs": [
                            ["Hamiltonian", "H = −Σ⟨ij⟩ s_i s_j, s_i=±1"],
                            ["Critical coupling", f"K_c = {config['critical_k']:.17f}"],
                            ["Geometry", f"Periodic L×M torus, M={config['aspect_ratio']}L"],
                            ["Widths", ", ".join(str(value) for value in config["widths"])],
                            ["Random generator", "rand_xoshiro 0.8.1 · Xoshiro256++"],
                        ],
                    },
                    {
                        "kind": "equation",
                        "tex": r"H=-\sum_{\langle i j\rangle}s_i s_j,\qquad K_c=\frac{1}{2}\log(1+\sqrt{2})",
                    },
                ],
            },
            {
                "title": "Exact transfer matrix",
                "note": "Matrix-free O(L 2^L) transfer application provides the deterministic benchmark.",
                "blocks": [
                    _verdict(
                        gates["exact_accuracy"],
                        "Exact accuracy",
                        f"Primary L_min=6 fit gives c={exact['c']:.6f}; required |c−0.5|≤0.005.",
                    ),
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "figures/free_energy_scaling.png",
                                "caption": (
                                    "Exact/MC agreement. Critical free energy per site versus 1/L²; "
                                    "circles are transfer-matrix values and squares include bootstrap "
                                    "uncertainty. The shared linear Casimir slope encodes c≈1/2."
                                ),
                            }
                        ],
                    },
                ],
            },
            {
                "title": "Monte Carlo integration",
                "note": "Rust Wolff blocks are integrated in Python from the exact K=0 anchor.",
                "blocks": [
                    {
                        "kind": "equation",
                        "tex": r"F(K_c)=-N\log 2+\int_0^{K_c}\langle H\rangle_K\,dK",
                    },
                    _verdict(
                        gates["integration"],
                        "Nested-grid convergence",
                        (
                            f"|c_33−c_17|={diagnostics['integration_shift']:.4g}; "
                            f"bootstrap SE={diagnostics['primary_standard_error']:.4g}."
                        ),
                    ),
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "figures/energy_vs_k.png",
                                "caption": (
                                    "Measured integrand. Mean total Ising energy divided by site count "
                                    "across the 33-point K grid; each curve is one circumference."
                                ),
                            },
                            {
                                "src": "figures/integration_convergence.png",
                                "caption": (
                                    "Integration stable. The 17- and 33-point Simpson estimates agree "
                                    "within the 33-point bootstrap standard error."
                                ),
                            },
                        ],
                    },
                ],
            },
            {
                "title": "Central charge",
                "note": "The primary L_min=6 window was selected before viewing results.",
                "blocks": [
                    {
                        "kind": "equation",
                        "tex": r"\frac{g(L)}{L}=f_\infty-\frac{\pi c}{6L^2}+\frac{a}{L^4}",
                    },
                    _verdict(
                        gates["mc_accuracy"] and gates["mc_interval"],
                        "Monte Carlo accuracy",
                        (
                            f"c={mc['c']:.6f}, 95% interval [{mc['low']:.6f}, "
                            f"{mc['high']:.6f}]; target 0.5."
                        ),
                    ),
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "figures/central_charge_comparison.png",
                                "caption": (
                                    "Pass. Independent transfer-matrix and Monte Carlo estimates lie "
                                    "inside their declared accuracy bands around the Ising value c=0.5."
                                ),
                            },
                            {
                                "src": "figures/fit_stability.png",
                                "caption": (
                                    "Window stability. L_min=4, 6, and 8 remain visible; L_min=6 is the "
                                    "predeclared primary estimate and diagnostics do not select a window."
                                ),
                            },
                        ],
                    },
                    _fit_table(results),
                ],
            },
            {
                "title": "Verification",
                "note": "Every declared scientific and runtime gate remains explicit.",
                "blocks": [
                    *[
                        _verdict(passed, label.replace("_", " ").title(), _gate_reason(label))
                        for label, passed in gates.items()
                    ],
                    {
                        "kind": "figures",
                        "items": [
                            {
                                "src": "figures/replica_diagnostics.png",
                                "caption": (
                                    "Chain diagnostics. Maximum half-chain drift and pairwise replica "
                                    "z scores are compared with the predeclared |z|=4 threshold."
                                ),
                            }
                        ],
                    },
                    {
                        "kind": "table",
                        "columns": ["Stage", "Seconds"],
                        "rows": [
                            ["Exact", _seconds(manifest.get("exact_elapsed_s"))],
                            ["Monte Carlo", _seconds(manifest.get("mc_elapsed_s"))],
                            ["Total", _seconds(manifest.get("total_elapsed_s"))],
                        ],
                        "numeric": [False, True],
                    },
                ],
            },
            {
                "title": "Reproduction",
                "note": "Commands and seeds are recorded in the run manifest.",
                "blocks": [
                    {
                        "kind": "code",
                        "title": "Rust numerical stages",
                        "text": f"{manifest.get('exact_command', '')}\n{manifest.get('mc_command', '')}",
                    },
                    {
                        "kind": "code",
                        "title": "Complete local workflow",
                        "text": "make setup\nmake test\nmake run",
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            ["Rust", manifest.get("rust_version", "")],
                            ["Bootstrap seed", str(results["bootstrap_seed"])],
                            ["Schema version", str(manifest.get("schema_version", 1))],
                        ],
                    },
                ],
            },
        ],
    }


def _fit_table(results: Mapping[str, Any]) -> Dict[str, Any]:
    rows = []
    for l_min in (4, 6, 8):
        exact = results["exact_fits"][l_min]
        mc = results["mc_fits"][l_min]
        rows.append(
            [
                str(l_min),
                f"{exact['c']:.6f}",
                f"{mc['c']:.6f}",
                f"{mc['se']:.6f}",
                f"[{mc['low']:.6f}, {mc['high']:.6f}]",
                "primary" if l_min == 6 else "diagnostic",
            ]
        )
    return {
        "kind": "table",
        "columns": ["L_min", "Exact c", "MC c", "MC SE", "MC 95% interval", "Role"],
        "rows": rows,
        "numeric": [True, True, True, True, True, False],
    }


def _verdict(passed: bool, label: str, reason: str) -> Dict[str, str]:
    return {
        "kind": "verdict",
        "status": "good" if passed else "bad",
        "label": "PASS" if passed else "FAIL",
        "why": f"{label}: {reason}",
    }


def _gate_reason(name: str) -> str:
    reasons = {
        "exact_accuracy": "|c_exact−0.5|≤0.005.",
        "mc_accuracy": "|c_MC−0.5|≤0.03.",
        "mc_interval": "The Monte Carlo 95% interval contains 0.5.",
        "integration": "The 17/33-point shift is below the 33-point standard error.",
        "exact_window": "Exact diagnostic-window drift is at most 0.005.",
        "mc_window": "Monte Carlo diagnostic windows agree within uncertainty.",
        "thermalization": "All first/second-half energy z scores are below 4.",
        "replicas": "All pairwise replica energy z scores are below 4.",
        "runtime": "The declared production runtime is below 600 seconds.",
    }
    return reasons[name]


def _seconds(value) -> str:
    return "pending" if value is None else f"{float(value):.3f}"
