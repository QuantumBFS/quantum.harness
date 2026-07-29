import csv
import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT = (
    Path(__file__).parents[2]
    / "tracks/mps/solutions/reproduction/floquet_spin_boson/scripts/plot_results.py"
)


def _plot_module():
    spec = importlib.util.spec_from_file_location("floquet_plot_results", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fig3_drive_windows_apply_to_spectrum_and_delta_axes() -> None:
    """Catch clipping the two rows differently or retaining the broad 0–15 view."""
    module = _plot_module()

    class Axis:
        def __init__(self) -> None:
            self.limits = None

        def set_xlim(self, left: float, right: float) -> None:
            self.limits = (left, right)

    for drive, expected in (
        ("longitudinal", (0.0, 10.0)),
        ("transversal", (0.0, 4.0)),
    ):
        spectrum = Axis()
        delta = Axis()
        module._apply_fig3_xlim((spectrum, delta), drive)
        assert spectrum.limits == expected
        assert delta.limits == expected


def _write_csv(path: Path, header: tuple[str, ...], rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def _write_fig3_point(root: Path, drive: str, frequency: float) -> None:
    point = root / drive / str(frequency)
    _write_csv(
        point / "continuous_heat_current.csv",
        ("omega", "current"),
        [(0.005, 0.01), (0.010, 0.02), (0.015, 0.01)],
    )
    _write_csv(
        point / "delta_peaks.csv",
        ("n", "omega", "c_n", "spectral_density", "integrated_weight"),
        [(1, frequency, 0.2, 0.1, 0.02)],
    )


def _write_fig3_reference(root: Path, drive: str, frequency: float) -> None:
    root.mkdir(parents=True, exist_ok=True)
    name = (
        f"heat_current_{drive}_Ω_1_ϵ_d_1_ω_d_{frequency:g}_"
        "α_0.05_ω_c_2.5_bond_dim_235_dt_0.052.csv"
    )
    (root / name).write_text("0.011\n0.019\n0.012\n", encoding="utf-8")


def test_fig3_validation_subset_writes_real_png(tmp_path: Path) -> None:
    """Catch a plot command that cannot visualize a completed validation point."""
    ours = tmp_path / "ours"
    reference = tmp_path / "reference"
    _write_fig3_point(ours, "transversal", 1.0)
    _write_fig3_reference(reference, "transversal", 1.0)
    output = tmp_path / "fig3.png"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "fig3",
            "--allow-validation-subset",
            "--result-root",
            str(ours),
            "--reference-root",
            str(reference),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert output.stat().st_size > 1_000


def test_fig3_complete_plot_rejects_a_missing_paper_point(tmp_path: Path) -> None:
    """Catch silently labeling a partial frequency set as complete Fig. 3."""
    ours = tmp_path / "ours"
    reference = tmp_path / "reference"
    _write_fig3_point(ours, "transversal", 1.0)
    _write_fig3_reference(reference, "transversal", 1.0)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "fig3",
            "--result-root",
            str(ours),
            "--reference-root",
            str(reference),
            "--output",
            str(tmp_path / "fig3.png"),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "missing Fig. 3 point" in completed.stderr


def test_fig3_validation_subset_ignores_an_empty_point_directory(
    tmp_path: Path,
) -> None:
    """Catch treating a created directory without numerical artifacts as complete."""
    ours = tmp_path / "ours"
    reference = tmp_path / "reference"
    (ours / "transversal" / "1.0").mkdir(parents=True)
    _write_fig3_point(ours, "transversal", 1.5)
    _write_fig3_reference(reference, "transversal", 1.5)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "fig3",
            "--allow-validation-subset",
            "--result-root",
            str(ours),
            "--reference-root",
            str(reference),
            "--output",
            str(tmp_path / "fig3.png"),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_fig5_plot_rejects_noncomplete_scan_rows(tmp_path: Path) -> None:
    """Catch interpolating missing or failed Fig. 5 points into a smooth curve."""
    ours = tmp_path / "ours"
    reference = tmp_path / "reference"
    _write_csv(
        ours / "total_current_longitudinal.csv",
        (
            "omega_d",
            "status",
            "total_current",
            "period_averaged_power",
            "energy_balance_error",
        ),
        [(0.5, "complete", 0.1, 0.1, 0.0), (0.55, "failed", "", "", "")],
    )
    _write_csv(
        ours / "total_current_transversal.csv",
        (
            "omega_d",
            "status",
            "total_current",
            "period_averaged_power",
            "energy_balance_error",
        ),
        [(0.5, "complete", 0.08, 0.08, 0.0), (0.55, "complete", 0.07, 0.07, 0.0)],
    )
    reference.mkdir(parents=True)
    (reference / "total_heat_current_longitudinal.csv").write_text(
        "0.1\n0.09\n", encoding="utf-8"
    )
    (reference / "total_heat_current_transversal.csv").write_text(
        "0.08\n0.07\n", encoding="utf-8"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "fig5",
            "--result-root",
            str(ours),
            "--reference-root",
            str(reference),
            "--output",
            str(tmp_path / "fig5.png"),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode != 0
    assert "non-complete Fig. 5 point" in completed.stderr


def test_fig5_validation_subset_selects_exact_author_grid_points(
    tmp_path: Path,
) -> None:
    """Catch requiring a sparse validation scan to have all 191 author points."""
    ours = tmp_path / "ours"
    reference = tmp_path / "reference"
    frequencies = (1.0, 2.5, 5.0)
    for drive, scale in (("longitudinal", 1.0), ("transversal", 0.5)):
        _write_csv(
            ours / f"total_current_{drive}.csv",
            (
                "omega_d",
                "status",
                "total_current",
                "period_averaged_power",
                "energy_balance_error",
            ),
            [(value, "complete", scale * value, scale * value, 0.0)
             for value in frequencies],
        )
        reference.mkdir(parents=True, exist_ok=True)
        author_grid = [0.5 + 0.05 * index for index in range(191)]
        (reference / f"total_heat_current_{drive}.csv").write_text(
            "\n".join(str(scale * value) for value in author_grid) + "\n",
            encoding="utf-8",
        )

    output = tmp_path / "fig5.png"
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "fig5",
            "--result-root",
            str(ours),
            "--reference-root",
            str(reference),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert output.stat().st_size > 1_000


def test_fig2_plot_writes_two_frequency_checkpoint(tmp_path: Path) -> None:
    """Catch losing either slow- or fast-drive evidence from the Fig. 2 plot."""
    result = tmp_path / "fig2"
    result.mkdir()
    rows = "0.0\t1.0\t1.0\n0.1\t0.8\t0.79\n0.2\t0.5\t0.48\n"
    (result / "ours_omega_d_2.5.csv").write_text(rows, encoding="utf-8")
    (result / "ours_omega_d_10.0.csv").write_text(rows, encoding="utf-8")
    output = tmp_path / "fig2.png"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "fig2",
            "--result-root",
            str(result),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert output.stat().st_size > 1_000
