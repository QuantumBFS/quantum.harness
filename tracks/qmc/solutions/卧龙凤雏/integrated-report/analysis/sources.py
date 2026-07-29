"""Load and validate the frozen artifacts used by the integrated report."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Gate:
    name: str
    criterion: str
    value: object
    passed: bool
    required: bool = True


@dataclass(frozen=True)
class SourceSpec:
    slug: str
    name: str
    relative_dir: Path
    target: float


@dataclass(frozen=True)
class ModelResult:
    slug: str
    name: str
    result_dir: Path
    target: float
    estimate: float
    exact_estimate: Optional[float]
    standard_error: float
    ci95: Tuple[float, float]
    runtime_s: float
    parameters: Tuple[Tuple[str, str, str, str], ...]
    gates: Tuple[Gate, ...]
    figures: Tuple[Path, ...]
    tables: Mapping[str, Tuple[Mapping[str, str], ...]]
    provenance: Mapping[str, str]


def source_specs(repo_root: Path) -> Tuple[SourceSpec, ...]:
    del repo_root
    return (
        SourceSpec(
            "clean-ising",
            "Clean Ising",
            Path("tracks/qmc/results/clean-ising-20260729-120302"),
            0.5,
        ),
        SourceSpec(
            "nishimori-ising",
            "Nishimori random-bond Ising",
            Path("tracks/qmc/results/nishimori-ising-20260729-refinement1"),
            0.464,
        ),
        SourceSpec(
            "weak-self-dual",
            "Weak self-dual Majorana network",
            Path("tracks/qmc/results/weak-self-dual-20260729-154737"),
            0.447,
        ),
    )


def load_all_models(repo_root: Path) -> Tuple[ModelResult, ...]:
    root = Path(repo_root).resolve()
    return tuple(load_model(spec, root) for spec in source_specs(root))


def load_model(spec: SourceSpec, repo_root: Path) -> ModelResult:
    run_dir = repo_root / spec.relative_dir
    if not run_dir.is_dir():
        raise ValueError(f"{spec.slug}: missing frozen result directory {run_dir}")
    if spec.slug == "clean-ising":
        model = _load_clean(spec, run_dir, repo_root)
    elif spec.slug == "nishimori-ising":
        model = _load_nishimori(spec, run_dir, repo_root)
    elif spec.slug == "weak-self-dual":
        model = _load_weak(spec, run_dir, repo_root)
    else:
        raise ValueError(f"unsupported source model {spec.slug}")
    _validate_model(model)
    return model


def _load_clean(spec: SourceSpec, run_dir: Path, repo_root: Path) -> ModelResult:
    manifest_path = run_dir / "manifest.json"
    metadata_path = run_dir / "processed/analysis_metadata.json"
    fits_path = run_dir / "processed/central_charge_fits.csv"
    diagnostics_path = run_dir / "processed/diagnostics.csv"
    energies_path = run_dir / "processed/free_energies.csv"
    manifest = _read_json(manifest_path, spec.slug)
    metadata = _read_json(metadata_path, spec.slug)
    fit_rows = _read_csv(fits_path, spec.slug)
    primary = {
        row["method"]: row
        for row in fit_rows
        if row["role"] == "primary" and int(row["L_min"]) == 6
    }
    try:
        exact = float(primary["transfer_matrix"]["c"])
        mc = float(primary["monte_carlo"]["c"])
        se = float(primary["monte_carlo"]["standard_error"])
        interval = (
            float(primary["monte_carlo"]["ci_low"]),
            float(primary["monte_carlo"]["ci_high"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{spec.slug}: malformed primary central-charge fits") from error

    config = manifest["config"]
    mc_config = config["mc"]
    gate_labels = {
        "exact_accuracy": "transfer-matrix estimate agrees with c=1/2",
        "mc_accuracy": "Monte Carlo estimate agrees with c=1/2",
        "mc_interval": "Monte Carlo 95% CI contains c=1/2",
        "integration": "nested thermodynamic-integration grids agree",
        "exact_window": "exact fit is stable to L_min",
        "mc_window": "Monte Carlo fit is stable to L_min",
        "thermalization": "half-chain drift is below threshold",
        "replicas": "replica disagreement is below threshold",
        "runtime": "runtime is below the declared limit",
    }
    gates = tuple(
        Gate(name, gate_labels[name], passed, bool(passed), True)
        for name, passed in metadata["gates"].items()
    )
    parameters = (
        ("K_c", f"{config['critical_k']:.16f}", "Exact square-lattice critical coupling", "Fixes the evaluation point"),
        ("L", _join(config["widths"]), "Periodic cylinder circumference", "Controls finite-size bias"),
        ("M/L", str(config["aspect_ratio"]), "Torus aspect ratio", "Suppresses longitudinal finite-size effects"),
        ("N_K", str(mc_config["grid_intervals"] + 1), "Thermodynamic-integration grid points", "Controls quadrature error"),
        ("R", str(mc_config["replicas"]), "Independent Monte Carlo replicas", "Supports between-chain diagnostics"),
        ("N_therm", str(mc_config["thermal_sweeps"]), "Discarded Wolff sweeps", "Controls initialization bias"),
        ("N_meas", str(mc_config["measurement_sweeps"]), "Measured Wolff sweeps per grid point", "Controls statistical precision"),
        ("N_block", str(mc_config["block_sweeps"]), "Sweeps per stored block", "Reduces autocorrelation"),
        ("RNG", "Xoshiro256++", "Deterministic pseudo-random generator", "Enables reproducible independent streams"),
    )
    used = (manifest_path, metadata_path, fits_path, diagnostics_path, energies_path)
    return ModelResult(
        slug=spec.slug,
        name=spec.name,
        result_dir=run_dir,
        target=spec.target,
        estimate=mc,
        exact_estimate=exact,
        standard_error=se,
        ci95=interval,
        runtime_s=float(manifest["total_elapsed_s"]),
        parameters=parameters,
        gates=gates,
        figures=_figures(run_dir, 6, spec.slug),
        tables={
            "central_charge_fits": tuple(fit_rows),
            "diagnostics": tuple(_read_csv(diagnostics_path, spec.slug)),
            "free_energies": tuple(_read_csv(energies_path, spec.slug)),
        },
        provenance=_provenance((*used, *_figures(run_dir, 6, spec.slug)), repo_root),
    )


def _load_nishimori(spec: SourceSpec, run_dir: Path, repo_root: Path) -> ModelResult:
    manifest_path = run_dir / "manifest.json"
    summary_path = run_dir / "processed/summary.json"
    gates_path = run_dir / "processed/gates.json"
    free_energy_path = run_dir / "processed/free_energy.csv"
    bootstrap_path = run_dir / "processed/central_charge_bootstrap.csv"
    manifest = _read_json(manifest_path, spec.slug)
    summary = _read_json(summary_path, spec.slug)
    gate_doc = _read_json(gates_path, spec.slug)
    _validate_target(spec, summary.get("target_central_charge"), gate_doc.get("target_central_charge"))
    config = manifest["config"]
    disorder = config["disorder"]
    parameters = (
        ("p", f"{config['antiferromagnetic_probability']:.7f}", "Probability of a negative bond", "Defines the disorder distribution"),
        ("K_N", f"{config['nishimori_k']:.15f}", "Nishimori-line coupling", "Locks thermal and disorder weights"),
        ("L", _join(config["widths"]), "Transfer-strip widths", "Controls finite-size bias"),
        ("R", str(disorder["replicas"]), "Independent disorder replicas", "Controls disorder-sampling error"),
        ("N_burn", f"{disorder['burn_in_rows']:,}", "Discarded transfer rows", "Suppresses initial-vector bias"),
        ("N_meas", f"{disorder['measurement_rows']:,}", "Measured rows per replica", "Controls free-energy precision"),
        ("N_block", f"{disorder['block_rows']:,}", "Rows per bootstrap block", "Preserves serial dependence"),
        ("delta K", f"{disorder['identity_delta_k']:.1e}", "Centered finite-difference step", "Controls energy-identity truncation"),
        ("RNG", "Xoshiro256++", "Deterministic disorder generator", "Preserves reproducible common-disorder streams"),
    )
    figures = _figures(run_dir, 6, spec.slug)
    used = (manifest_path, summary_path, gates_path, free_energy_path, bootstrap_path)
    return ModelResult(
        slug=spec.slug,
        name=spec.name,
        result_dir=run_dir,
        target=spec.target,
        estimate=float(summary["central_charge"]),
        exact_estimate=None,
        standard_error=float(summary["central_charge_standard_error"]),
        ci95=_interval(summary["central_charge_ci95"], spec.slug),
        runtime_s=float(summary["runtime_s"]),
        parameters=parameters,
        gates=_load_gates(gate_doc, spec.slug),
        figures=figures,
        tables={
            "finite_size": tuple(_read_csv(free_energy_path, spec.slug)),
            "bootstrap": tuple(_read_csv(bootstrap_path, spec.slug)),
        },
        provenance=_provenance((*used, *figures), repo_root),
    )


def _load_weak(spec: SourceSpec, run_dir: Path, repo_root: Path) -> ModelResult:
    manifest_path = run_dir / "manifest.json"
    summary_path = run_dir / "processed/summary.json"
    gates_path = run_dir / "processed/gates.json"
    finite_size_path = run_dir / "processed/finite_size.csv"
    variants_path = run_dir / "processed/fit_variants.csv"
    manifest = _read_json(manifest_path, spec.slug)
    summary = _read_json(summary_path, spec.slug)
    gate_doc = _read_json(gates_path, spec.slug)
    _validate_target(spec, summary.get("target_central_charge"), gate_doc.get("target_central_charge"))
    config = manifest["config"]
    sampling = config["sampling"]
    parameters = (
        ("theta", "pi/4", "Self-dual circuit angle", "Fixes the isotropic weak self-dual point"),
        ("beta", f"{config['beta']:.15f}", "Weak-measurement coupling", "Sets Born update strength"),
        ("L", _join(config["widths"]), "Majorana cylinder circumference", "Controls finite-size bias"),
        ("R", str(sampling["streams_per_width"]), "Independent trajectory streams per width", "Controls trajectory variance"),
        ("N_burn/L", str(sampling["burn_in_layers_per_width"]), "Burn-in layers per width", "Suppresses boundary transients"),
        ("N_meas/L", str(sampling["measurement_layers_per_width"]), "Measured layers per width", "Controls entropy-rate precision"),
        ("N_block/L", str(sampling["block_layers_per_width"]), "Layers per stored block", "Supports autocorrelation estimates"),
        ("N_stab", str(sampling["stabilize_every_layers"]), "Layers between covariance stabilization", "Controls invariant drift"),
        ("epsilon_Gamma", f"{sampling['invariant_tolerance']:.0e}", "Gaussian invariant tolerance", "Rejects numerically invalid trajectories"),
        ("RNG", "Xoshiro256++", "Deterministic Born sampler", "Enables replayable trajectory streams"),
    )
    figures = _figures(run_dir, 5, spec.slug)
    used = (manifest_path, summary_path, gates_path, finite_size_path, variants_path)
    return ModelResult(
        slug=spec.slug,
        name=spec.name,
        result_dir=run_dir,
        target=spec.target,
        estimate=float(summary["central_charge"]),
        exact_estimate=None,
        standard_error=float(summary["central_charge_standard_error"]),
        ci95=_interval(summary["central_charge_ci95"], spec.slug),
        runtime_s=float(summary["runtime_s"]),
        parameters=parameters,
        gates=_load_gates(gate_doc, spec.slug),
        figures=figures,
        tables={
            "finite_size": tuple(_read_csv(finite_size_path, spec.slug)),
            "fit_variants": tuple(_read_csv(variants_path, spec.slug)),
        },
        provenance=_provenance((*used, *figures), repo_root),
    )


def _validate_model(model: ModelResult) -> None:
    numbers = (model.target, model.estimate, model.standard_error, *model.ci95, model.runtime_s)
    if not all(math.isfinite(value) for value in numbers):
        raise ValueError(f"{model.slug}: non-finite headline value")
    if model.standard_error <= 0 or model.runtime_s <= 0:
        raise ValueError(f"{model.slug}: standard error and runtime must be positive")
    if not model.ci95[0] <= model.estimate <= model.ci95[1]:
        raise ValueError(f"{model.slug}: confidence interval excludes its estimate")
    failed = [gate.name for gate in model.gates if gate.required and not gate.passed]
    if failed:
        raise ValueError(f"{model.slug}: required scientific gates failed: {', '.join(failed)}")


def _validate_target(spec: SourceSpec, *values: object) -> None:
    for value in values:
        if value is None or not math.isclose(float(value), spec.target, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError(f"{spec.slug}: target value conflicts with frozen source")


def _load_gates(document: Mapping[str, object], slug: str) -> Tuple[Gate, ...]:
    try:
        rows = document["gates"]
        return tuple(
            Gate(
                str(row["name"]),
                str(row["criterion"]),
                row.get("value"),
                bool(row["passed"]),
                bool(row.get("required", True)),
            )
            for row in rows
        )
    except (KeyError, TypeError) as error:
        raise ValueError(f"{slug}: malformed validation gates") from error


def _interval(value: Sequence[object], slug: str) -> Tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{slug}: confidence interval must contain two endpoints")
    interval = (float(value[0]), float(value[1]))
    if not interval[0] < interval[1]:
        raise ValueError(f"{slug}: confidence interval endpoints are unordered")
    return interval


def _figures(run_dir: Path, minimum: int, slug: str) -> Tuple[Path, ...]:
    figures = tuple(sorted((run_dir / "figures").glob("*.png")))
    if len(figures) < minimum:
        raise ValueError(f"{slug}: expected at least {minimum} source figures")
    for path in figures:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"{slug}: unreadable source figure {path}")
    return figures


def _read_json(path: Path, slug: str) -> Dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{slug}: failed to read JSON {path}") from error


def _read_csv(path: Path, slug: str) -> Tuple[Mapping[str, str], ...]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = tuple(dict(row) for row in csv.DictReader(handle))
    except OSError as error:
        raise ValueError(f"{slug}: failed to read CSV {path}") from error
    if not rows:
        raise ValueError(f"{slug}: CSV is empty: {path}")
    return rows


def _provenance(paths: Sequence[Path], repo_root: Path) -> Mapping[str, str]:
    return {
        str(path.relative_to(repo_root)): _sha256(path)
        for path in paths
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _join(values: Sequence[object]) -> str:
    return ", ".join(str(value) for value in values)
