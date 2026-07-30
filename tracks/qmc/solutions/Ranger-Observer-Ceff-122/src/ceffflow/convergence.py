"""Fail-closed particle-number convergence analysis for degraded records."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from .analysis import (
    _fit_charge_samples,
    _is_analytic_endpoint,
    _result_root,
    _verified_blocks,
)
from .schema import CellConfig


def summarize_particle_samples(
    samples_by_particles: dict[int, np.ndarray],
    *,
    absolute_tolerance: float,
    confidence_z: float,
) -> dict[str, Any]:
    """Test 128-versus-256 equivalence using paired block samples.

    The 64-particle level is retained as a pre-asymptotic diagnostic.  The
    declared production gate is the upper confidence bound on the absolute
    128-to-256 shift, which must lie inside ``absolute_tolerance``.
    """
    if set(samples_by_particles) != {64, 128, 256}:
        raise ValueError("particle convergence requires levels 64, 128, and 256")
    if absolute_tolerance <= 0.0 or confidence_z <= 0.0:
        raise ValueError("convergence thresholds must be positive")
    samples = {
        particles: np.asarray(values, dtype=float)
        for particles, values in samples_by_particles.items()
    }
    shapes = {values.shape for values in samples.values()}
    if len(shapes) != 1 or next(iter(shapes))[0] < 2:
        raise ValueError("particle samples must contain aligned replicate vectors")
    if any(values.ndim != 1 or not np.all(np.isfinite(values)) for values in samples.values()):
        raise ValueError("particle samples must be finite one-dimensional vectors")

    levels = {
        str(particles): {
            "central_charge": float(np.mean(values)),
            "standard_error": float(
                np.std(values, ddof=1) / np.sqrt(values.size)
            ),
            "samples": int(values.size),
        }
        for particles, values in sorted(samples.items())
    }
    comparisons: dict[str, dict[str, float | bool]] = {}
    for lower, higher in ((64, 128), (128, 256)):
        differences = samples[higher] - samples[lower]
        shift = float(np.mean(differences))
        paired_standard_error = float(
            np.std(differences, ddof=1) / np.sqrt(differences.size)
        )
        upper_bound = abs(shift) + confidence_z * paired_standard_error
        comparisons[f"{lower}_to_{higher}"] = {
            "higher_minus_lower": shift,
            "paired_standard_error": paired_standard_error,
            "absolute_shift_upper_confidence_bound": upper_bound,
            "inside_absolute_tolerance": bool(
                upper_bound <= absolute_tolerance
            ),
        }
    production_passed = bool(
        comparisons["128_to_256"]["inside_absolute_tolerance"]
    )
    return {
        "levels": levels,
        "comparisons": comparisons,
        "production_gate_passed": production_passed,
    }


def summarize_particle_pair(
    samples_by_particles: dict[int, np.ndarray],
    *,
    lower_particles: int,
    higher_particles: int,
    absolute_tolerance: float,
    confidence_z: float,
) -> dict[str, Any]:
    """Apply the same paired equivalence rule to one particle-count pair."""
    if lower_particles <= 0 or higher_particles <= lower_particles:
        raise ValueError("particle levels must be positive and increasing")
    if set(samples_by_particles) != {lower_particles, higher_particles}:
        raise ValueError("particle pair samples do not match the declared levels")
    if absolute_tolerance <= 0.0 or confidence_z <= 0.0:
        raise ValueError("convergence thresholds must be positive")
    samples = {
        particles: np.asarray(values, dtype=float)
        for particles, values in samples_by_particles.items()
    }
    shapes = {values.shape for values in samples.values()}
    if len(shapes) != 1 or next(iter(shapes))[0] < 2:
        raise ValueError("particle samples must contain aligned replicate vectors")
    if any(
        values.ndim != 1 or not np.all(np.isfinite(values))
        for values in samples.values()
    ):
        raise ValueError("particle samples must be finite one-dimensional vectors")
    levels = {
        str(particles): {
            "central_charge": float(np.mean(values)),
            "standard_error": float(
                np.std(values, ddof=1) / np.sqrt(values.size)
            ),
            "samples": int(values.size),
        }
        for particles, values in sorted(samples.items())
    }
    differences = samples[higher_particles] - samples[lower_particles]
    shift = float(np.mean(differences))
    paired_standard_error = float(
        np.std(differences, ddof=1) / np.sqrt(differences.size)
    )
    upper_bound = abs(shift) + confidence_z * paired_standard_error
    comparison = f"{lower_particles}_to_{higher_particles}"
    passed = bool(upper_bound <= absolute_tolerance)
    return {
        "levels": levels,
        "comparisons": {
            comparison: {
                "higher_minus_lower": shift,
                "paired_standard_error": paired_standard_error,
                "absolute_shift_upper_confidence_bound": upper_bound,
                "inside_absolute_tolerance": passed,
            }
        },
        "production_gate_passed": passed,
    }


def _load_particle_blocks(
    spec_path: Path,
    allowed_particles: set[int],
) -> tuple[
    dict[tuple[str, float, int], dict[int, np.ndarray]],
    dict[tuple[str, float, int], CellConfig],
    dict[tuple[str, float, int], set[str]],
]:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    root = _result_root(spec_path, spec)
    blocks: dict[tuple[str, float, int], dict[int, np.ndarray]] = {}
    configs: dict[tuple[str, float, int], CellConfig] = {}
    provenance: dict[tuple[str, float, int], set[str]] = {}
    for cell in spec["cells"]:
        settings = CellConfig.model_validate(cell["settings"])
        if (
            settings.model != "self_dual"
            or settings.channel.kind == "identity"
            or _is_analytic_endpoint(settings)
            or settings.particles not in allowed_particles
        ):
            continue
        cell_id = str(cell["cell_id"])
        manifest, cell_blocks = _verified_blocks(root / cell_id)
        config = manifest.settings
        key = (
            config.channel.kind,
            float(config.channel.parameter),
            config.particles,
        )
        if config.seed in blocks.setdefault(key, {}):
            raise ValueError(f"duplicate seed {config.seed} for {key}")
        blocks[key][config.seed] = cell_blocks
        configs[key] = config
        provenance.setdefault(key, set()).add(
            manifest.provenance.get("git_commit", "unknown")
        )
    return blocks, configs, provenance


def analyze_particle_convergence(
    reference_run_spec: str | Path,
    candidate_run_spec: str | Path,
    output_path: str | Path,
    *,
    absolute_tolerance: float = 0.05,
    confidence_z: float = 1.96,
) -> dict[str, Any]:
    """Compare production 128-particle cells with new 64/256-particle cells."""
    reference_path = Path(reference_run_spec)
    candidate_path = Path(candidate_run_spec)
    reference = _load_particle_blocks(reference_path, {128})
    candidate = _load_particle_blocks(candidate_path, {64, 256})
    all_blocks = {**reference[0], **candidate[0]}
    all_configs = {**reference[1], **candidate[1]}
    all_provenance = {**reference[2], **candidate[2]}

    resolutions = sorted(
        {(channel, parameter) for channel, parameter, _ in reference[0]}
    )
    if not resolutions:
        raise ValueError("reference run has no 128-particle degraded cells")
    rows: list[dict[str, Any]] = []
    for channel, parameter in resolutions:
        keys = [(channel, parameter, particles) for particles in (64, 128, 256)]
        missing = [key for key in keys if key not in all_blocks]
        if missing:
            raise ValueError(f"missing particle convergence cells: {missing}")
        seed_sets = [set(all_blocks[key]) for key in keys]
        if any(seed_set != seed_sets[0] for seed_set in seed_sets[1:]):
            raise ValueError(
                f"particle levels do not share seeds for {channel}/{parameter}"
            )
        ordered_seeds = sorted(seed_sets[0])
        samples_by_particles: dict[int, np.ndarray] = {}
        replicate_shape: tuple[int, ...] | None = None
        reference_config = all_configs[keys[0]]
        for key in keys:
            config = all_configs[key]
            comparable = (
                config.lengths,
                config.steps,
                config.burn_in,
                config.block_size,
                config.channel,
            )
            reference_settings = (
                reference_config.lengths,
                reference_config.steps,
                reference_config.burn_in,
                reference_config.block_size,
                reference_config.channel,
            )
            if comparable != reference_settings:
                raise ValueError(f"incompatible particle settings for {key}")
            arrays = [all_blocks[key][seed] for seed in ordered_seeds]
            shapes = {array.shape for array in arrays}
            if len(shapes) != 1:
                raise ValueError(f"unaligned block shapes for {key}")
            shape = next(iter(shapes))
            if replicate_shape is None:
                replicate_shape = shape
            elif shape != replicate_shape:
                raise ValueError(
                    f"particle levels do not share block shape for {channel}/{parameter}"
                )
            samples_by_particles[key[2]] = _fit_charge_samples(
                config, np.concatenate(arrays, axis=0)
            )
        row = summarize_particle_samples(
            samples_by_particles,
            absolute_tolerance=absolute_tolerance,
            confidence_z=confidence_z,
        )
        rows.append(
            {
                "channel": channel,
                "parameter": parameter,
                "information_loss": (
                    parameter if channel == "confusion" else 1.0 - parameter
                ),
                "seeds": ordered_seeds,
                "source_commits": {
                    str(key[2]): sorted(all_provenance[key]) for key in keys
                },
                **row,
            }
        )

    summary: dict[str, Any] = {
        "schema_version": "1.0",
        "reference_run_spec": str(reference_path.resolve()),
        "candidate_run_spec": str(candidate_path.resolve()),
        "criteria": {
            "production_comparison": "128_to_256",
            "absolute_central_charge_tolerance": absolute_tolerance,
            "confidence_z": confidence_z,
            "rule": (
                "abs(mean paired shift) + z * paired standard error <= tolerance"
            ),
            "multiple_resolution_rule": "all interior resolutions must pass",
        },
        "resolution_points": rows,
        "all_resolutions_passed": bool(
            rows and all(row["production_gate_passed"] for row in rows)
        ),
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def analyze_particle_pair_run(
    run_spec: str | Path,
    output_path: str | Path,
    *,
    lower_particles: int,
    higher_particles: int,
    absolute_tolerance: float = 0.05,
    confidence_z: float = 1.96,
) -> dict[str, Any]:
    """Analyze a same-run high-statistics particle-count pair."""
    spec_path = Path(run_spec)
    blocks, configs, provenance = _load_particle_blocks(
        spec_path, {lower_particles, higher_particles}
    )
    resolutions = sorted(
        {
            (channel, parameter)
            for channel, parameter, particles in blocks
            if particles == lower_particles
        }
    )
    if not resolutions:
        raise ValueError("run has no degraded cells at the lower particle level")
    rows: list[dict[str, Any]] = []
    for channel, parameter in resolutions:
        keys = [
            (channel, parameter, lower_particles),
            (channel, parameter, higher_particles),
        ]
        missing = [key for key in keys if key not in blocks]
        if missing:
            raise ValueError(f"missing particle convergence cells: {missing}")
        seed_sets = [set(blocks[key]) for key in keys]
        if seed_sets[0] != seed_sets[1]:
            raise ValueError(
                f"particle levels do not share seeds for {channel}/{parameter}"
            )
        ordered_seeds = sorted(seed_sets[0])
        samples_by_particles: dict[int, np.ndarray] = {}
        replicate_shape: tuple[int, ...] | None = None
        reference = configs[keys[0]]
        for key in keys:
            config = configs[key]
            comparable = (
                config.lengths,
                config.steps,
                config.burn_in,
                config.block_size,
                config.channel,
            )
            expected = (
                reference.lengths,
                reference.steps,
                reference.burn_in,
                reference.block_size,
                reference.channel,
            )
            if comparable != expected:
                raise ValueError(f"incompatible particle settings for {key}")
            arrays = [blocks[key][seed] for seed in ordered_seeds]
            shapes = {array.shape for array in arrays}
            if len(shapes) != 1:
                raise ValueError(f"unaligned block shapes for {key}")
            shape = next(iter(shapes))
            if replicate_shape is None:
                replicate_shape = shape
            elif shape != replicate_shape:
                raise ValueError(
                    f"particle levels do not share block shape for {channel}/{parameter}"
                )
            samples_by_particles[key[2]] = _fit_charge_samples(
                config, np.concatenate(arrays, axis=0)
            )
        row = summarize_particle_pair(
            samples_by_particles,
            lower_particles=lower_particles,
            higher_particles=higher_particles,
            absolute_tolerance=absolute_tolerance,
            confidence_z=confidence_z,
        )
        rows.append(
            {
                "channel": channel,
                "parameter": parameter,
                "information_loss": (
                    parameter if channel == "confusion" else 1.0 - parameter
                ),
                "seeds": ordered_seeds,
                "source_commits": {
                    str(key[2]): sorted(provenance[key]) for key in keys
                },
                **row,
            }
        )
    comparison = f"{lower_particles}_to_{higher_particles}"
    summary: dict[str, Any] = {
        "schema_version": "1.0",
        "run_spec": str(spec_path.resolve()),
        "criteria": {
            "production_comparison": comparison,
            "absolute_central_charge_tolerance": absolute_tolerance,
            "confidence_z": confidence_z,
            "rule": (
                "abs(mean paired shift) + z * paired standard error <= tolerance"
            ),
            "multiple_resolution_rule": "all interior resolutions must pass",
        },
        "resolution_points": rows,
        "all_resolutions_passed": bool(
            rows and all(row["production_gate_passed"] for row in rows)
        ),
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
