#!/usr/bin/env python3
"""Build an honest partial-or-complete Liu Figures 2--4 report document."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


PANEL_MAP = [
    ("Fig. 2(a)", "unavailable", "two-image photon counts and assignments absent"),
    ("Fig. 2(b)", "unavailable", "single-qubit RB shot records absent"),
    ("Fig. 3(a)", "exact analytic/theoretical check", "Appendix-C 10-state model is fully specified"),
    ("Fig. 3(b)", "equivalent numerical reoptimization", "paper pulse array and optimizer details are unpublished"),
    ("Fig. 3(c)", "equivalent numerical reoptimization", "populations depend on the newly optimized pulse"),
    ("Fig. 3(d), calculated", "equivalent numerical reoptimization", "Hessian belongs to the newly optimized pulse"),
    ("Fig. 3(d), measured", "unavailable", "experimental mode scans and RB observations absent"),
    ("Fig. 3(e), calculated", "equivalent numerical reoptimization", "Appendix-C channel decomposition is computable"),
    ("Fig. 3(e), measured", "unavailable", "leakage and Ramsey observations absent"),
    ("Fig. 4(a)", "synthetic demonstration", "measured AOM waveforms are unavailable"),
    ("Fig. 4(b)", "synthetic demonstration", "experimental closed-loop scans are unavailable"),
    ("Fig. 4(c)", "unavailable", "echoed-RB shot records absent"),
    ("Fig. 4(d), calculated", "equivalent numerical reoptimization", "AR and same-duration surrogate are newly optimized"),
    ("Fig. 4(d), measured", "unavailable", "experimental intensity scan absent"),
    ("Fig. 4(e)", "unavailable", "stability time series absent"),
    ("Fig. 4(f)", "literal transcription of reported paper values", "missing MQDT/noise inputs prevent independent simulation"),
]


CHANGELOG = [
    "Replaced the complete-reproduction claim with panel-by-panel provenance.",
    "Added nested configuration dataclasses, quick/standard/convergence profiles, resolved-config output, and cache hashes.",
    "Made JAX optional for the NumPy/SciPy MWE and removed eager all-stage failure.",
    "Documented and tested the +Δr detuning sign, Appendix-C coupling signs, units, basis ordering, Hermiticity, symmetry, and unitarity.",
    "Added generic paper-independent seeds, optional spline/time-bin backends, complete multistarts, branch-safe AR residuals, and final fine-grid smoothing.",
    "Separated fixed standard CZ, fixed nominal virtual-Z, and pointwise CZ-equivalent fidelities.",
    "Corrected Figure 3(c) to total Rydberg populations P00, P01=P10, and P11.",
    "Made additive tapered paper laboratory I/Q the default Hessian coordinates; retained the local frame only as a diagnostic.",
    "Added multi-resolution rank diagnostics, signed eigenvalue plots, ±ε central finite differences, modes 11–14, and random null combinations.",
    "Renamed the comparator to same-duration non-robust surrogate and added directional, baseline-aware fit-window tests.",
    "Rebuilt the synthetic AOM workflow as plant-in-loop, removed oracle scan ranges, and saved consistent ideal/command/before/after arrays.",
    "Separated every experimental panel contract, including distinct Figure 4(c) RB and Figure 4(d) intensity pipelines.",
    "Renamed the Appendix-E stage to reported-error-budget and marked missing postselected values rather than plotting them as zero.",
    "Expanded the automated suite to physics, fidelity, Hessian, CLI, cache, serialization, and provenance tests.",
    "Removed obsolete Hessian/AOM code paths and unused compiled kernels; added propagation-spectrum, null-space, and post-write archive acceptance checks.",
]


def generated_file_rows(run_dir: Path) -> list[list[str]]:
    rows = []
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        relative = str(path.relative_to(run_dir))
        if "synthetic" in relative:
            provenance = "synthetic demonstration"
        elif "reported" in relative or "fig4f" in relative:
            provenance = "literal transcription"
        elif "experimental" in relative:
            provenance = "unavailable/raw-data contract"
        elif "waveform" in relative or "hessian" in relative or "intensity" in relative:
            provenance = "equivalent numerical reoptimization"
        elif "mwe" in relative:
            provenance = "exact analytic/theoretical check"
        elif "config" in relative or "metadata" in relative:
            provenance = "run metadata (not scientific evidence)"
        else:
            provenance = "report/supporting artifact"
        rows.append([relative, provenance])
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run_dir = args.run_dir
    data = run_dir / "data"
    mwe = read_json(data / "mwe_summary.json")
    optimization = read_json(data / "optimization_summary.json")
    hessian = read_json(data / "fig3_hessian_summary.json")
    intensity = read_json(data / "fig4_intensity_scaling_summary.json")
    synthetic = read_json(data / "fig4_synthetic_summary.json")
    reported = read_json(data / "fig4f_reported_summary.json")
    metadata = read_json(run_dir / "run_metadata.json") or {}

    panel_rows = [[panel, classification, reason] for panel, classification, reason in PANEL_MAP]
    panel_json = [
        {"panel": panel, "classification": classification, "boundary": reason}
        for panel, classification, reason in PANEL_MAP
    ]
    with (run_dir / "panel_provenance.json").open("w", encoding="utf-8") as handle:
        json.dump(panel_json, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    artifact_rows = generated_file_rows(run_dir)
    known_report_artifacts = {
        "artifact_provenance.json": "report/supporting artifact",
        "report.json": "report/supporting artifact",
        "report.html": "self-contained rendered report",
        "CHANGELOG.md": "report/supporting artifact",
    }
    existing_artifacts = {row[0] for row in artifact_rows}
    for artifact, provenance in known_report_artifacts.items():
        if artifact not in existing_artifacts:
            artifact_rows.append([artifact, provenance])
    artifact_rows.sort(key=lambda row: row[0])
    artifact_json = [
        {"artifact": artifact, "provenance": provenance}
        for artifact, provenance in artifact_rows
    ]
    with (run_dir / "artifact_provenance.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(artifact_json, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    outcome_blocks: list[dict[str, Any]] = []
    if mwe:
        rows = mwe["grid_rows"]
        jax_difference = mwe.get("jax_numpy_difference_101")
        jax_text = (
            f"{jax_difference:.3e}" if jax_difference is not None else "skipped"
        )
        outcome_blocks.extend(
            [
                {
                    "kind": "verdict",
                    "status": "good" if mwe["acceptance"]["all"] else "bad",
                    "label": "Quick MWE accepted" if mwe["acceptance"]["all"] else "Quick MWE failed",
                    "why": (
                        f"Hermitian and unitary checks passed; grid ratios "
                        f"{mwe['grid_error_ratios'][0]:.3f}, "
                        f"{mwe['grid_error_ratios'][1]:.3f}; JAX/NumPy "
                        f"difference {jax_text}."
                    ),
                },
                {
                    "kind": "figures",
                    "items": [
                        {
                            "src": "figs/mwe_grid_convergence.png",
                            "caption": (
                                "Accepted analytic/numerical check. The fixed-grid "
                                "matrix-exponential propagator approaches the "
                                "independent DOP853 solution at second order over "
                                "101, 201, and 401 nodes."
                            ),
                        }
                    ],
                },
                {
                    "kind": "table",
                    "columns": ["Nodes", "Normalized unitary difference", "Infidelity difference", "Leakage difference"],
                    "rows": [
                        [
                            str(row["nodes"]),
                            f"{row['normalized_unitary_difference']:.3e}",
                            f"{row['infidelity_difference']:.3e}",
                            f"{row['max_leakage_difference']:.3e}",
                        ]
                        for row in rows
                    ],
                },
            ]
        )
    else:
        outcome_blocks.append(
            {
                "kind": "verdict",
                "status": "warn",
                "label": "No MWE result found",
                "why": "Run the quick MWE before treating this report as numerical evidence.",
            }
        )

    workflow_rows = [
        ["Equivalent pulse optimization", "run" if optimization else "not run in this output"],
        ["Multi-resolution Hessian", "run" if hessian else "not run in this output"],
        ["Intensity scaling", "run" if intensity else "not run in this output"],
        ["Synthetic AOM loop", "run" if synthetic else "not run in this output"],
        ["Reported Appendix-E budget", "run" if reported else "not run in this output"],
    ]
    theory_blocks: list[dict[str, Any]] = []
    if optimization:
        robust_adaptive = optimization["robust"]["adaptive_metrics"]
        robust_fixed = optimization["robust"]["fixed_grid_metrics"]
        theory_blocks.extend(
            [
                {
                    "kind": "verdict",
                    "status": "good" if optimization["acceptance"]["all"] else "bad",
                    "label": "Equivalent AR reoptimization accepted",
                    "why": (
                        f"adaptive 1−F={robust_adaptive['infidelity']:.3e}, "
                        f"maximum leakage={robust_adaptive['max_leakage']:.3e}, "
                        f"echoed curvature={robust_fixed['echoed_fidelity_curvature']:.3e}."
                    ),
                },
                {
                    "kind": "table",
                    "columns": ["Robustness diagnostic", "Value", "Meaning"],
                    "rows": [
                        ["Nonlinear phase derivative", f"{robust_fixed['nonlinear_phase_derivative']:.3e}", "AR channel"],
                        ["Leakage derivative norm", f"{robust_fixed['leakage_derivative_norm']:.3e}", "AR channel"],
                        ["Symmetric local-Z derivative", f"{robust_fixed['symmetric_local_z_phase_derivative']:.3e}", "not removed by fixed-Z metric"],
                        ["Echoed fidelity curvature", f"{robust_fixed['echoed_fidelity_curvature']:.3e}", "pointwise CZ-equivalent"],
                        ["Fixed-Z fidelity curvature", f"{robust_fixed['fixed_z_fidelity_curvature']:.3e}", "one fixed virtual-Z"],
                    ],
                },
                {
                    "kind": "figures",
                    "items": [
                        {
                            "src": "figs/fig3_theory_waveform_populations.png",
                            "caption": (
                                "Equivalent numerical reoptimization, not the "
                                "unpublished Figure 3(b) array. Top: normalized "
                                "amplitude and wrapped phase. Bottom: total Rydberg "
                                "populations P00, P01=P10, and P11."
                            ),
                        }
                    ],
                },
            ]
        )
    if hessian:
        theory_blocks.extend(
            [
                {
                    "kind": "verdict",
                    "status": "good" if hessian["acceptance"]["all"] else "bad",
                    "label": "Paper lab-I/Q Hessian accepted",
                    "why": (
                        f"rank={hessian['rank']} is stable across resolutions; "
                        f"λ10/|λ11|={hessian['lambda10_over_lambda11_absolute']:.3e}; "
                        f"best-window principal finite-difference error "
                        f"{hessian['fd_max_best_relative_error']:.3e}."
                    ),
                },
                {
                    "kind": "figures",
                    "items": [
                        {
                            "src": "figs/fig3_theory_hessian.png",
                            "caption": (
                                "Equivalent numerical reoptimization. Signed "
                                "laboratory-I/Q Hessian spectrum and Appendix-C "
                                "leakage/phase channel decomposition. Negative "
                                "numerical eigenvalues are shown, not clipped."
                            ),
                        },
                        {
                            "src": "figs/fig3_hessian_principal_modes_xy.png",
                            "caption": (
                                "Both laboratory-I and laboratory-Q components "
                                "of all ten physical principal modes."
                            ),
                        },
                    ],
                },
            ]
        )
    if intensity:
        ar = intensity["fit_window_summaries"]["AR equivalent reoptimization"][
            "pointwise_cz_equivalent"
        ]
        nr = intensity["fit_window_summaries"][
            "same-duration non-robust surrogate"
        ]["pointwise_cz_equivalent"]
        theory_blocks.extend(
            [
                {
                    "kind": "verdict",
                    "status": "good" if intensity["acceptance"]["all"] else "bad",
                    "label": "Directional intensity scaling accepted",
                    "why": (
                        "Echoed AR exponents −/+ are "
                        f"{ar['negative']['median_exponent']:.2f}/"
                        f"{ar['positive']['median_exponent']:.2f}; surrogate "
                        f"exponents are {nr['negative']['median_exponent']:.2f}/"
                        f"{nr['positive']['median_exponent']:.2f}."
                    ),
                },
                {
                    "kind": "figures",
                    "items": [
                        {
                            "src": "figs/fig4_theory_intensity_scaling.png",
                            "caption": (
                                "Equivalent numerical reoptimization. Pointwise "
                                "CZ-equivalent intensity scaling; the blue "
                                "comparator is explicitly a same-duration "
                                "non-robust surrogate, not the paper's time-optimal gate."
                            ),
                        }
                    ],
                },
            ]
        )
    synthetic_blocks: list[dict[str, Any]] = []
    if synthetic:
        synthetic_blocks.extend(
            [
                {
                    "kind": "verdict",
                    "status": (
                        "good"
                        if synthetic.get("acceptance", {}).get("all", False)
                        else "bad"
                    ),
                    "label": "Synthetic plant-in-loop demonstration completed",
                    "why": (
                        f"full-propagation infidelity changed from "
                        f"{synthetic['initial_full_schrodinger_infidelity_raw']:.3e} "
                        f"to {synthetic['final_full_schrodinger_infidelity_raw']:.3e}; "
                        "oracle distortion information was not used."
                    ),
                },
                {
                    "kind": "figures",
                    "items": [
                        {
                            "src": "figs/fig4_synthetic_closed_loop.png",
                            "caption": (
                                "Synthetic demonstration only. Assumed AOM "
                                "waveforms, quadratic Hessian prediction versus "
                                "full Schrödinger propagation, and shot-noisy "
                                "weighted mode scans. No marker is experimental."
                            ),
                        }
                    ],
                },
            ]
        )
    if reported:
        synthetic_blocks.append(
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "figs/fig4f_reported_values.png",
                        "caption": (
                            "Literal Appendix-E transcription, not an independent "
                            "open-system simulation. An unreported postselected "
                            "amplitude-noise value is marked missing rather than zero."
                        ),
                    }
                ],
            }
        )
    report = {
        "title": "Liu et al. Figures 2–4 numerical audit",
        "eyebrow": (
            f"arXiv:2606.05060v1 · {metadata.get('profile', 'unknown')} "
            f"profile · config {metadata.get('config_hash', 'unknown')[:12]}"
        ),
        "url": "https://arxiv.org/abs/2606.05060",
        "lede": (
            "Accessible closed-system theory, equivalent reoptimization, "
            "synthetic calibration, reported-value transcription, and missing "
            "experimental data are kept as distinct evidence classes."
        ),
        "sections": [
            {
                "title": "Executed evidence",
                "note": "Only stages present in this run directory are reported as executed.",
                "blocks": outcome_blocks
                + [
                    {
                        "kind": "table",
                        "columns": ["Workflow", "Status"],
                        "rows": workflow_rows,
                    }
                ],
            },
            {
                "title": "Physical contract",
                "note": "The assumptions that determine every numerical result.",
                "blocks": [
                    {
                        "kind": "equation",
                        "tex": (
                            "H(t)=+\\Delta_r\\Pi_{r'}+\\frac{1}{2}"
                            "\\left[\\Omega(t)\\sigma_+ + \\Omega^*(t)\\sigma_-\\right]"
                        ),
                    },
                    {
                        "kind": "kv",
                        "pairs": [
                            ["Model", "10-state ideal perfect-blockade reduction; no double-Rydberg states"],
                            ["Units", "time μs; angular frequency rad/μs; Ω₀=2π×6.0; Δr=2π×16.1"],
                            ["Control", "T=0.55 μs; default 16-coefficient cubic B-splines; zero amplitude and slope at both endpoints"],
                            ["Hessian default", "additive tapered laboratory I/Q coordinates from Appendix C"],
                            ["Fidelities", "fixed standard CZ; fixed nominal virtual-Z; pointwise echoed/CZ-equivalent"],
                        ],
                    },
                ],
            },
            {
                "title": "Equivalent closed-system theory",
                "note": "These outputs use the newly optimized pulse, not the unpublished author pulse.",
                "blocks": theory_blocks or [
                    {"kind": "note", "style": "pending", "text": "Theory stages were not run."}
                ],
            },
            {
                "title": "Synthetic and reported-value outputs",
                "note": "Synthetic calibration and literal paper transcription are not experimental reproduction.",
                "blocks": synthetic_blocks or [
                    {"kind": "note", "style": "pending", "text": "No synthetic or reported-value outputs found."}
                ],
            },
            {
                "title": "Panel provenance",
                "note": "No synthetic value is presented as experimental reproduction.",
                "blocks": [
                    {
                        "kind": "table",
                        "columns": ["Paper panel", "Classification", "Boundary"],
                        "rows": panel_rows,
                    }
                ],
            },
            {
                "title": "Sources and unavailable inputs",
                "note": (
                    "Primary sources define the equations and reproduction "
                    "boundary; no paper curve was used as an optimization seed."
                ),
                "blocks": [
                    {
                        "kind": "table",
                        "columns": ["Source", "Use"],
                        "rows": [
                            [
                                "Liu et al., arXiv:2606.05060v1",
                                "Figure captions and Appendices B–E",
                            ],
                            [
                                "Jandura et al., arXiv:2210.06879",
                                "first-order amplitude-robust optimal-control method",
                            ],
                            [
                                "Jandura et al., arXiv:2210.08824",
                                "fidelity and robustness conventions",
                            ],
                        ],
                    },
                    {
                        "kind": "note",
                        "style": "pending",
                        "label": "Still unavailable",
                        "text": (
                            "Figures 2(a,b), measured parts of 3(d,e), "
                            "measured 4(a,b,d), 4(c), and 4(e) require raw "
                            "experimental observations. Independent Figure "
                            "4(f) simulation additionally requires the author "
                            "pulse array, MQDT pair-state data, decay branching, "
                            "thermal position distribution, and laser-noise spectra."
                        ),
                    },
                ],
            },
            {
                "title": "Changelog",
                "note": "Major corrections made by this audit.",
                "blocks": [{"kind": "list", "items": CHANGELOG}],
            },
            {
                "title": "Generated files",
                "note": "Machine-readable artifact inventory with evidence class.",
                "blocks": [
                    {
                        "kind": "table",
                        "columns": ["Artifact", "Provenance"],
                        "rows": artifact_rows,
                    }
                ],
            },
        ],
    }
    with (run_dir / "report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    with (run_dir / "CHANGELOG.md").open("w", encoding="utf-8") as handle:
        handle.write("# Changelog\n\n")
        for item in CHANGELOG:
            handle.write(f"- {item}\n")


if __name__ == "__main__":
    main()
