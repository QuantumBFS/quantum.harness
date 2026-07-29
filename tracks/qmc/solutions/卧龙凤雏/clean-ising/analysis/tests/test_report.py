import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from analysis.plots import FIGURE_NAMES, build_all_figures
from analysis.report_builder import build_report_document


def test_report_contains_required_sections_and_embeds_all_figures(tmp_path):
    results = synthetic_results()
    build_all_figures(results, tmp_path / "figures")
    document = build_report_document(results, tmp_path)
    report_text = json.dumps(document, ensure_ascii=False)
    assert "c_65−c_33" in report_text
    assert "65-point K grid" in report_text
    assert "33- and 65-point Simpson estimates" in report_text
    assert "c_33−c_17" not in report_text
    assert "17-point" not in report_text
    titles = [section["title"] for section in document["sections"]]
    assert titles == [
        "Setup",
        "Exact transfer matrix",
        "Monte Carlo integration",
        "Central charge",
        "Verification",
        "Reproduction",
    ]
    figure_sources = {
        item["src"]
        for section in document["sections"]
        for block in section["blocks"]
        if block["kind"] == "figures"
        for item in block["items"]
    }
    assert "figures/central_charge_comparison.png" in figure_sources
    assert figure_sources == {f"figures/{name}" for name in FIGURE_NAMES}

    (tmp_path / "report.json").write_text(
        json.dumps(document, indent=2),
        encoding="utf-8",
    )
    repository_root = Path(__file__).resolve().parents[7]
    renderer = repository_root / "skills" / "report" / "render_report.py"
    subprocess.run(
        [sys.executable, str(renderer), str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert html.count("data:image/png;base64,") == len(FIGURE_NAMES)
    assert not re.search(r'<(?:script|img)\b[^>]+\bsrc=["\']https?://', html)
    assert not re.search(r'<link\b[^>]+\bhref=["\']https?://', html)


def synthetic_results():
    widths = np.array([4.0, 6.0, 8.0, 10.0, 12.0, 16.0])
    k_values = np.linspace(0.0, 0.44068679350977147, 65)
    exact_g = -0.9297 * widths - np.pi * 0.5 / (6.0 * widths)
    mc_g = exact_g + np.array([0.0010, -0.0005, 0.0003, -0.0002, 0.0001, 0.0002])
    mean_energy = np.asarray(
        [
            -2.0 * (8.0 * width**2) * (k_values / k_values[-1])
            for width in widths
        ]
    )
    return {
        "widths": widths,
        "aspect_ratio": 8,
        "k_values": k_values,
        "mean_energy": mean_energy,
        "exact_g": exact_g,
        "mc_g": mc_g,
        "mc_g_se": np.full(widths.size, 0.001),
        "exact_fits": {
            4: {"c": 0.5008},
            6: {"c": 0.5002},
            8: {"c": 0.4997},
        },
        "mc_fits": {
            4: {"c": 0.506, "se": 0.012, "low": 0.483, "high": 0.529},
            6: {"c": 0.503, "se": 0.014, "low": 0.477, "high": 0.530},
            8: {"c": 0.498, "se": 0.020, "low": 0.460, "high": 0.537},
        },
        "mc_c_nested": 0.501,
        "primary_grid_points": 65,
        "nested_grid_points": 33,
        "diagnostics": {
            "max_half_z": 1.8,
            "max_replica_z": 2.1,
            "integration_shift": 0.002,
            "primary_standard_error": 0.014,
        },
        "gates": {
            "exact_accuracy": True,
            "mc_accuracy": True,
            "mc_interval": True,
            "integration": True,
            "exact_window": True,
            "mc_window": True,
            "thermalization": True,
            "replicas": True,
            "runtime": True,
        },
        "manifest": {
            "config": {
                "widths": [4, 6, 8, 10, 12, 16],
                "aspect_ratio": 8,
                "critical_k": 0.44068679350977147,
                "production_gates": True,
                "mc": {
                    "replicas": 4,
                    "grid_intervals": 32,
                    "thermal_sweeps": 200,
                    "measurement_sweeps": 800,
                    "block_sweeps": 20,
                },
            },
            "rust_version": "rustc test",
            "exact_command": "clean-ising exact --config configs/quick.toml",
            "mc_command": "clean-ising mc --config configs/quick.toml",
            "exact_elapsed_s": 0.2,
            "mc_elapsed_s": 42.0,
            "total_elapsed_s": 45.0,
        },
        "bootstrap_seed": 20260729,
    }
