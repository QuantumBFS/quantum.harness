import json

from analysis.finalize_runtime import finalize
from analysis.report_builder import build_report_document
from analysis.tests.helpers import make_synthetic_run


def test_report_contains_the_scientific_contract():
    summary = {
        "central_charge": 0.447,
        "central_charge_standard_error": 0.002,
        "central_charge_ci95": [0.443, 0.451],
        "widths": list(range(6, 32, 2)),
        "gamma": [1.0] * 13,
        "gamma_standard_error": [0.01] * 13,
        "primary_fit": {"central_charge": 0.447},
        "fit_stability": {"systematic_spread": 0.002},
        "self_duality": {"electric_density": 0.375, "magnetic_density": 0.375, "z_score": 0.0},
        "sampling_diagnostics": {"6": {"effective_sample_size": 200}},
        "gates": {"all_required_pass": True, "gates": []},
        "bootstrap_seed": 447122,
        "bootstrap_samples": 4000,
    }
    manifest = {
        "config": {
            "production_gates": True,
            "widths": list(range(6, 32, 2)),
            "beta": 0.881373587019543,
            "sampling": {"streams_per_width": 8},
        },
        "commands": [],
        "rust_version": "rustc test",
        "python_version": "3",
        "schema_version": 1,
    }
    report = build_report_document(summary, manifest)
    text = json.dumps(report)
    for required in ["Born-correlated", "Xoshiro256++", "W=+1", "0.447", "fit stability"]:
        assert required in text


def test_runtime_finalizer_updates_manifest_and_renders(tmp_path):
    run = make_synthetic_run(
        tmp_path, widths=tuple(range(6, 32, 2)), streams=4, blocks=8
    )
    from analysis.run_analysis import analyze_run

    analyze_run(run, bootstrap_samples=50, bootstrap_seed=447122)
    renderer = tmp_path / "renderer.py"
    renderer.write_text(
        "import pathlib,sys\n"
        "pathlib.Path(sys.argv[1], 'report.html').write_text('<html>ok</html>')\n"
    )
    finalize(run, 12.5, renderer)
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["total_elapsed_s"] == 12.5
    assert (run / "report.html").exists()
