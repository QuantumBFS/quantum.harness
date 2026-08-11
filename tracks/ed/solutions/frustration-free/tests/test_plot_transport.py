from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from scripts import plot_transport


def _write_typical_traces(path: Path) -> None:
    arrays: dict[str, np.ndarray] = {}
    for _, token in plot_transport.TYPICAL:
        arrays[f"{token}_phi_ad"] = np.array([0.0, np.pi, 2.0 * np.pi])
        arrays[f"{token}_polarization"] = np.array([0.25, 1.25, 2.25])
        arrays[f"{token}_phi_grid"] = np.array([0.0, np.pi])
        arrays[f"{token}_e0_torus"] = np.zeros((1, 2))
        arrays[f"{token}_gap_torus"] = np.ones((1, 2))
        for period in (2.0, 10.0, 50.0):
            arrays[f"{token}_T{period:g}_times"] = np.array([0.0, period])
            arrays[f"{token}_T{period:g}_cumulative"] = np.array([0.0, 2.0])
    np.savez(path, **arrays)


def test_typical_cycles_use_topological_polarization_not_fixed_twist(
    tmp_path: Path,
    monkeypatch,
):
    traces = tmp_path / "traces.npz"
    fixed_root = tmp_path / "fixed"
    output = tmp_path / "figures"
    fixed_root.mkdir()
    output.mkdir()
    _write_typical_traces(traces)
    for U, _ in plot_transport.TYPICAL:
        np.savez(
            fixed_root / f"center_U_{plot_transport._local_token(U)}.npz",
            phi=np.array([0.0, 2.0 * np.pi]),
            cumulative_charge=np.array([0.0, 13.0]),
        )

    captured = {}
    original_subplots = plt.subplots

    def capture_subplots(*args, **kwargs):
        fig, axes = original_subplots(*args, **kwargs)
        captured["axes"] = axes
        return fig, axes

    monkeypatch.setattr(plot_transport.plt, "subplots", capture_subplots)
    monkeypatch.setattr(plot_transport.plt, "close", lambda figure: None)

    plot_transport.plot_typical_cycles(traces, output, fixed_root)

    for axis in captured["axes"][0]:
        np.testing.assert_allclose(axis.lines[0].get_ydata(), [0.0, 1.0, 2.0])
        assert axis.lines[0].get_label() == r"$Q_{\rm ad}(\phi)$"


def test_path_cycles_use_wilson_polarization_for_every_path(
    tmp_path: Path,
    monkeypatch,
):
    traces = tmp_path / "traces.npz"
    paths_root = tmp_path / "paths"
    output = tmp_path / "figures"
    for directory in (paths_root / "fixed_adiabatic", paths_root / "static", paths_root / "realtime", output):
        directory.mkdir(parents=True, exist_ok=True)
    _write_typical_traces(traces)

    for U, _ in plot_transport.TYPICAL:
        token = plot_transport._local_token(U)
        np.savez(
            paths_root / "fixed_adiabatic" / f"center_U_{token}.npz",
            phi=np.array([0.0, 2.0 * np.pi]),
            cumulative_charge=np.array([0.0, 13.0]),
        )
        for path_id in plot_transport.PATH_IDS:
            np.savez(
                paths_root / "fixed_adiabatic" / f"{path_id}_U_{token}.npz",
                phi=np.array([0.0, 2.0 * np.pi]),
                cumulative_charge=np.array([0.0, 13.0]),
            )
            np.savez(
                paths_root / "static" / f"{path_id}_U_{token}.npz",
                phi=np.array([0.0, np.pi, 2.0 * np.pi]),
                polarization=np.array([0.5, 1.0, 1.5]),
            )
            np.savez(
                paths_root / "realtime" / f"{path_id}_U_{token}_T_{plot_transport._local_token(10.0)}.npz",
                times=np.array([0.0, 10.0]),
                cumulative_charge=np.array([0.0, 1.0]),
            )

    captured = {}
    original_subplots = plt.subplots

    def capture_subplots(*args, **kwargs):
        fig, axes = original_subplots(*args, **kwargs)
        captured["axes"] = axes
        return fig, axes

    monkeypatch.setattr(plot_transport.plt, "subplots", capture_subplots)
    monkeypatch.setattr(plot_transport.plt, "close", lambda figure: None)

    plot_transport.plot_path_charge_cycles(traces, paths_root, output)

    for axis in captured["axes"].ravel():
        np.testing.assert_allclose(axis.lines[0].get_ydata(), [0.0, 1.0, 2.0])
        for line_index in (2, 4, 6):
            np.testing.assert_allclose(
                axis.lines[line_index].get_ydata(),
                [0.0, 0.5, 1.0],
            )
        assert all("theta=0" not in line.get_label() for line in axis.lines)


def test_typical_cycles_prefer_saved_center_wilson_loop(
    tmp_path: Path,
    monkeypatch,
):
    traces = tmp_path / "traces.npz"
    paths_root = tmp_path / "paths"
    static_root = paths_root / "static"
    output = tmp_path / "figures"
    static_root.mkdir(parents=True)
    output.mkdir()
    _write_typical_traces(traces)
    for U, _ in plot_transport.TYPICAL:
        np.savez(
            static_root / f"center_U_{plot_transport._local_token(U)}.npz",
            phi=np.array([0.0, np.pi, 2.0 * np.pi]),
            polarization=np.array([0.4, 1.15, 1.9]),
        )

    captured = {}
    original_subplots = plt.subplots

    def capture_subplots(*args, **kwargs):
        fig, axes = original_subplots(*args, **kwargs)
        captured["axes"] = axes
        return fig, axes

    monkeypatch.setattr(plot_transport.plt, "subplots", capture_subplots)
    monkeypatch.setattr(plot_transport.plt, "close", lambda figure: None)

    plot_transport.plot_typical_cycles(traces, output, paths_root)

    for axis in captured["axes"][0]:
        np.testing.assert_allclose(axis.lines[0].get_ydata(), [0.0, 0.75, 1.5])
