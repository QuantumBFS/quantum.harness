"""Tests for scripts/scaling_fit.py."""

import csv
import importlib.util
import os
import sys

import numpy as np
import pytest

# Load the script as a module (it lives in scripts/, not an installed package).
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(_HERE, "..", "scaling_fit.py")
_spec = importlib.util.spec_from_file_location("scaling_fit", _SCRIPT)
sf = importlib.util.module_from_spec(_spec)
sys.modules["scaling_fit"] = sf
_spec.loader.exec_module(sf)


def _write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def _read_params(path):
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            out[row["parameter"]] = row["value"]
    return out


# --------------------------------------------------------------------------- #
# Synthetic-data generators (seeded)
# --------------------------------------------------------------------------- #
def make_power_law(tmp_path, A=2.0, alpha=0.5, seed=1):
    rng = np.random.default_rng(seed)
    L = np.array([8, 16, 24, 32, 48, 64], dtype=float)
    err = 0.002 * np.ones_like(L)
    y = A * L ** (-alpha) + rng.normal(0, err)
    path = tmp_path / "power.csv"
    _write_csv(path, ["L", "obs", "err"], zip(L, y, err))
    return str(path)


def make_log_L(tmp_path, A=1.5, B=0.3, seed=2):
    rng = np.random.default_rng(seed)
    L = np.array([8, 16, 24, 32, 48, 64], dtype=float)
    err = 0.005 * np.ones_like(L)
    y = A * np.log(L) + B + rng.normal(0, err)
    path = tmp_path / "log.csv"
    _write_csv(path, ["L", "obs", "err"], zip(L, y, err))
    return str(path)


def make_poly(tmp_path, c0=-0.44, c1=0.8, c2=-1.2, seed=3):
    rng = np.random.default_rng(seed)
    L = np.array([8, 16, 24, 32, 48, 64], dtype=float)
    inv = 1.0 / L
    err = 0.001 * np.ones_like(L)
    y = c0 + c1 * inv + c2 * inv**2 + rng.normal(0, err)
    path = tmp_path / "poly.csv"
    _write_csv(path, ["L", "obs", "err"], zip(L, y, err))
    return str(path)


def make_collapse(tmp_path, h_c=2.0, nu=1.0, gov=0.25, seed=4):
    """A scaling function obs = g(L^(1/nu)(h-h_c)) / L^(gov) so that
    obs * L^gov collapses onto g(x). Use a smooth Gaussian for g."""
    rng = np.random.default_rng(seed)
    Ls = [8, 16, 32]
    hs = np.linspace(1.6, 2.4, 9)
    rows = []
    err_val = 1e-4
    for L in Ls:
        for h in hs:
            x = (L ** (1.0 / nu)) * (h - h_c)
            g = np.exp(-(x**2) / 50.0)
            obs = g * (L ** (-gov)) + rng.normal(0, err_val)
            rows.append((L, h, obs, err_val))
    path = tmp_path / "collapse.csv"
    _write_csv(path, ["L", "h", "obs", "err"], rows)
    return str(path)


# --------------------------------------------------------------------------- #
# Form-recovery tests
# --------------------------------------------------------------------------- #
def test_power_law_recovers(tmp_path):
    data = make_power_law(tmp_path, A=2.0, alpha=0.5)
    out_csv = tmp_path / "p.csv"
    out_png = tmp_path / "p.png"
    rc = sf.main(
        [
            data,
            "--form",
            "power-law",
            "--bootstrap",
            "100",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(out_png),
        ]
    )
    assert rc == 0
    params = _read_params(out_csv)
    assert abs(float(params["alpha"]) - 0.5) < 0.05
    assert abs(float(params["A"]) - 2.0) < 0.1
    assert out_csv.exists() and out_png.exists()


def test_log_L_recovers(tmp_path):
    data = make_log_L(tmp_path, A=1.5, B=0.3)
    out_csv = tmp_path / "l.csv"
    out_png = tmp_path / "l.png"
    sf.main(
        [
            data,
            "--form",
            "log-L",
            "--bootstrap",
            "100",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(out_png),
        ]
    )
    params = _read_params(out_csv)
    assert abs(float(params["A"]) - 1.5) < 0.05
    assert abs(float(params["B"]) - 0.3) < 0.1
    assert "chi2_per_dof" in params


def test_polynomial_recovers(tmp_path):
    data = make_poly(tmp_path, c0=-0.44, c1=0.8, c2=-1.2)
    out_csv = tmp_path / "poly.csv"
    out_png = tmp_path / "poly.png"
    sf.main(
        [
            data,
            "--form",
            "polynomial",
            "--degree",
            "2",
            "--bootstrap",
            "100",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(out_png),
        ]
    )
    params = _read_params(out_csv)
    # c0 is the L->inf extrapolation (constant term).
    assert abs(float(params["c0"]) - (-0.44)) < 0.01


def test_data_collapse_recovers(tmp_path):
    data = make_collapse(tmp_path, h_c=2.0, nu=1.0, gov=0.25)
    out_csv = tmp_path / "c.csv"
    out_png = tmp_path / "c.png"
    rc = sf.main(
        [
            data,
            "--form",
            "data-collapse",
            "--param-col",
            "h",
            "--bootstrap",
            "30",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(out_png),
        ]
    )
    assert rc == 0
    params = _read_params(out_csv)
    assert abs(float(params["h_c"]) - 2.0) < 0.1
    assert abs(float(params["nu"]) - 1.0) < 0.3
    assert "collapse_residual" in params
    assert out_png.exists()


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def test_missing_column_blocks(tmp_path, capsys):
    path = tmp_path / "bad.csv"
    _write_csv(path, ["L", "obs"], [(8, 1.0), (16, 0.5)])  # no err col
    with pytest.raises(SystemExit) as exc:
        sf.main([str(path), "--form", "power-law"])
    assert exc.value.code != 0
    assert "blocked: err" in capsys.readouterr().out


def test_empty_cell_blocks(tmp_path, capsys):
    path = tmp_path / "empty.csv"
    _write_csv(path, ["L", "obs", "err"], [(8, 1.0, 0.01), (16, 0.5, "")])
    with pytest.raises(SystemExit) as exc:
        sf.main([str(path), "--form", "power-law"])
    assert exc.value.code != 0
    assert "blocked: err" in capsys.readouterr().out


def test_empty_table_blocks(tmp_path, capsys):
    path = tmp_path / "head.csv"
    _write_csv(path, ["L", "obs", "err"], [])
    with pytest.raises(SystemExit):
        sf.main([str(path), "--form", "power-law"])
    assert "blocked: empty data table" in capsys.readouterr().out


def test_data_collapse_requires_param_col(tmp_path, capsys):
    data = make_power_law(tmp_path)
    with pytest.raises(SystemExit):
        sf.main([data, "--form", "data-collapse"])
    assert "param-col" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Pinned-value path
# --------------------------------------------------------------------------- #
def test_pin_power_law(tmp_path):
    data = make_power_law(tmp_path, A=2.0, alpha=0.5)
    out_csv = tmp_path / "pin.csv"
    sf.main(
        [
            data,
            "--form",
            "power-law",
            "--pin",
            "A=2.0",
            "--bootstrap",
            "50",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(tmp_path / "pin.png"),
        ]
    )
    params = _read_params(out_csv)
    assert float(params["A"]) == 2.0  # pinned exactly
    assert abs(float(params["alpha"]) - 0.5) < 0.05


def test_pin_log_L(tmp_path):
    data = make_log_L(tmp_path, A=1.5, B=0.3)
    out_csv = tmp_path / "pinlog.csv"
    sf.main(
        [
            data,
            "--form",
            "log-L",
            "--pin",
            "B=0.3",
            "--bootstrap",
            "50",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(tmp_path / "pinlog.png"),
        ]
    )
    params = _read_params(out_csv)
    assert float(params["B"]) == 0.3
    assert abs(float(params["A"]) - 1.5) < 0.05


def test_pin_polynomial(tmp_path):
    data = make_poly(tmp_path)
    out_csv = tmp_path / "pinpoly.csv"
    sf.main(
        [
            data,
            "--form",
            "polynomial",
            "--pin",
            "c0=-0.44",
            "--bootstrap",
            "30",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(tmp_path / "pinpoly.png"),
        ]
    )
    params = _read_params(out_csv)
    assert float(params["c0"]) == -0.44


def test_pin_data_collapse(tmp_path):
    data = make_collapse(tmp_path, h_c=2.0, nu=1.0, gov=0.25)
    out_csv = tmp_path / "pinc.csv"
    sf.main(
        [
            data,
            "--form",
            "data-collapse",
            "--param-col",
            "h",
            "--pin",
            "h_c=2.0",
            "--bootstrap",
            "20",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(tmp_path / "pinc.png"),
        ]
    )
    params = _read_params(out_csv)
    assert float(params["h_c"]) == 2.0


def test_unknown_pin_blocks(tmp_path, capsys):
    data = make_power_law(tmp_path)
    with pytest.raises(SystemExit):
        sf.main([data, "--form", "power-law", "--pin", "zzz=1.0"])
    assert "unknown pin" in capsys.readouterr().out


def test_bad_pin_format_blocks(tmp_path, capsys):
    data = make_power_law(tmp_path)
    with pytest.raises(SystemExit):
        sf.main([data, "--form", "power-law", "--pin", "noequals"])
    assert "bad pin" in capsys.readouterr().out


def test_unknown_pin_log_L_blocks(tmp_path, capsys):
    data = make_log_L(tmp_path)
    with pytest.raises(SystemExit):
        sf.main([data, "--form", "log-L", "--pin", "zzz=1.0"])
    assert "unknown pin" in capsys.readouterr().out


def test_unknown_pin_polynomial_blocks(tmp_path, capsys):
    data = make_poly(tmp_path)
    with pytest.raises(SystemExit):
        sf.main([data, "--form", "polynomial", "--pin", "zzz=1.0"])
    assert "unknown pin" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# Bootstrap reporting
# --------------------------------------------------------------------------- #
def test_bootstrap_ci_and_failed_reported(tmp_path):
    data = make_power_law(tmp_path)
    out_csv = tmp_path / "b.csv"
    sf.main(
        [
            data,
            "--form",
            "power-law",
            "--bootstrap",
            "100",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(tmp_path / "b.png"),
        ]
    )
    rows = {}
    with open(out_csv, newline="") as f:
        for row in csv.DictReader(f):
            rows[row["parameter"]] = row
    # CI columns populated for the fitted alpha
    assert rows["alpha"]["ci_lo"] != ""
    assert rows["alpha"]["ci_hi"] != ""
    assert float(rows["alpha"]["ci_lo"]) <= float(rows["alpha"]["ci_hi"])
    # failed_resamples row present and is an int
    assert "failed_resamples" in rows
    int(rows["failed_resamples"]["value"])


def test_report_no_physics_label(tmp_path, capsys):
    data = make_power_law(tmp_path)
    sf.main(
        [
            data,
            "--form",
            "power-law",
            "--bootstrap",
            "20",
            "--out-csv",
            str(tmp_path / "r.csv"),
            "--out-png",
            str(tmp_path / "r.png"),
        ]
    )
    out = capsys.readouterr().out.lower()
    # Generic labels only: no universality-class words.
    for forbidden in ("universality", "ising", "critical exponent", "correlation-length exponent"):
        assert forbidden not in out


def test_collapse_residual_inf_on_degenerate():
    L = np.array([8.0, 16.0])
    param = np.array([1.0, 2.0])
    obs = np.array([1.0, 1.0])
    # nu == 0 -> inf guard
    assert sf.collapse_residual(1.0, 0.0, 0.0, L, param, obs) == np.inf


def test_failed_resamples_counted(tmp_path, monkeypatch):
    """Force collapse fits to fail and confirm they are counted, not dropped."""
    data = make_collapse(tmp_path)
    out_csv = tmp_path / "f.csv"
    table = sf.load_table(str(data), "L", "obs", "err", "h")

    calls = {"n": 0}
    real = sf.fit_data_collapse

    def flaky(L, param, obs, pins, p0=None):
        calls["n"] += 1
        if calls["n"] > 1:  # first call (point estimate) succeeds; resamples fail
            raise RuntimeError("forced failure")
        return real(L, param, obs, pins, p0)

    monkeypatch.setattr(sf, "fit_data_collapse", flaky)
    sf.main(
        [
            str(data),
            "--form",
            "data-collapse",
            "--param-col",
            "h",
            "--bootstrap",
            "10",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(tmp_path / "f.png"),
        ]
    )
    params = _read_params(out_csv)
    assert int(params["failed_resamples"]) == 10
    assert table["L"].size > 0


def test_pin_all_params(tmp_path):
    """Pinning every parameter exercises the no-free-parameter branches."""
    data = make_power_law(tmp_path, A=2.0, alpha=0.5)
    out_csv = tmp_path / "allp.csv"
    sf.main(
        [
            data,
            "--form",
            "power-law",
            "--pin",
            "A=2.0",
            "--pin",
            "alpha=0.5",
            "--bootstrap",
            "5",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(tmp_path / "allp.png"),
        ]
    )
    params = _read_params(out_csv)
    assert float(params["A"]) == 2.0 and float(params["alpha"]) == 0.5


def test_pin_all_params_log_L(tmp_path):
    data = make_log_L(tmp_path, A=1.5, B=0.3)
    out_csv = tmp_path / "alll.csv"
    sf.main(
        [
            data,
            "--form",
            "log-L",
            "--pin",
            "A=1.5",
            "--pin",
            "B=0.3",
            "--bootstrap",
            "5",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(tmp_path / "alll.png"),
        ]
    )
    params = _read_params(out_csv)
    assert float(params["A"]) == 1.5 and float(params["B"]) == 0.3


def test_pin_all_params_collapse(tmp_path):
    data = make_collapse(tmp_path)
    out_csv = tmp_path / "allc.csv"
    sf.main(
        [
            data,
            "--form",
            "data-collapse",
            "--param-col",
            "h",
            "--pin",
            "h_c=2.0",
            "--pin",
            "nu=1.0",
            "--pin",
            "gamma_over_nu=0.25",
            "--bootstrap",
            "5",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(tmp_path / "allc.png"),
        ]
    )
    params = _read_params(out_csv)
    assert float(params["nu"]) == 1.0


def test_quantile_ci_empty():
    lo, hi = sf.quantile_ci(np.asarray([]))
    assert np.isnan(lo) and np.isnan(hi)


def test_main_module_entry(tmp_path):
    """Smoke test the parser default out paths get created (custom dir)."""
    data = make_power_law(tmp_path)
    sub = tmp_path / "nested" / "dir"
    out_csv = sub / "x.csv"
    out_png = sub / "x.png"
    sf.main(
        [
            data,
            "--form",
            "power-law",
            "--bootstrap",
            "10",
            "--out-csv",
            str(out_csv),
            "--out-png",
            str(out_png),
        ]
    )
    assert out_csv.exists() and out_png.exists()
