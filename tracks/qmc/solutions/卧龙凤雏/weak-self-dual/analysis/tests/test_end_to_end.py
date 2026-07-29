from analysis.run_analysis import analyze_run
from analysis.tests.helpers import make_synthetic_run


def test_analysis_writes_required_processed_data_and_figures(tmp_path):
    run = make_synthetic_run(
        tmp_path,
        widths=tuple(range(6, 32, 2)),
        streams=4,
        blocks=8,
    )
    summary = analyze_run(run, bootstrap_samples=100, bootstrap_seed=447122)
    assert abs(summary["central_charge"] - 0.447) < 0.01
    for relative in [
        "processed/summary.json",
        "processed/gates.json",
        "processed/finite_size.csv",
        "processed/fit_variants.csv",
        "figures/finite-size-scaling.png",
        "figures/residuals.png",
        "figures/fit-stability.png",
        "figures/convergence-ess.png",
        "figures/self-duality.png",
        "report.json",
    ]:
        assert (run / relative).exists()
