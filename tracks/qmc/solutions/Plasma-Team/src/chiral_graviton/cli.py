"""Command-line interface for ED, projected NQS, and result validation."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

from . import __version__
from .basis import SphereSystem
from .chirality import chiral_graviton_response
from .ed import interaction_pair_table, neutral_gap, solve_fixed_l
from .independent_oracle import oracle_neutral_gap
from .nqs import SharedProjectedMLP
from .nqs_chirality import train_nqs_chirality
from .observables import multiplet_report
from .provenance import collect_provenance
from .scalable_nqs import SparseProjectedMLP


EXIT_QUALITY_FAILURE = 3
EXIT_NONFINITE = 4
EXIT_INVALID_RESULT = 6

# The largest accepted N=9 sparse result has variance 4.53e-12 and projection
# residual 1.93e-10.  These gates leave more than three orders of magnitude of
# numerical headroom while rejecting the audited max_iterations=0 result
# (variance about 3.6e-4).
MAX_NQS_VARIANCE = 1e-8
MAX_NQS_RESIDUAL = 1e-4
MAX_ED_RESIDUAL = 1e-8
MAX_SYMMETRY_ERROR = 1e-7
MAX_PROJECTION_RESIDUAL = 1e-7


def _write_json(path: str | Path, payload: dict) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _nonfinite_paths(value: Any, path: str = "result") -> list[str]:
    """Return JSON-style paths containing NaN or infinity."""

    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            paths.extend(_nonfinite_paths(child, f"{path}.{key}"))
        return paths
    if isinstance(value, (list, tuple)):
        paths = []
        for index, child in enumerate(value):
            paths.extend(_nonfinite_paths(child, f"{path}[{index}]"))
        return paths
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return [path]
    return []


def _nqs_quality_errors(payload: dict, *, require_residuals: bool) -> list[str]:
    """Apply the common fail-closed NQS convergence and accuracy gates."""

    errors: list[str] = []
    if payload.get("optimizer_success") is not True:
        errors.append(
            "CG007: optimizer did not converge: "
            f"{payload.get('optimizer_message', 'no optimizer message')}"
        )

    for label in ("l0", "l2"):
        variance_key = f"variance_{label}"
        residual_key = f"residual_{label}"
        if variance_key not in payload:
            errors.append(f"CG006: missing NQS metric: {variance_key}")
            continue
        variance = float(payload[variance_key])
        if variance < 0.0:
            errors.append(f"CG006: negative variance: {variance_key}={variance:.6g}")
        elif variance > MAX_NQS_VARIANCE:
            errors.append(
                f"CG009: {variance_key}={variance:.6g} exceeds "
                f"{MAX_NQS_VARIANCE:.1e}"
            )

        if residual_key in payload:
            residual = float(payload[residual_key])
        elif require_residuals:
            errors.append(f"CG006: missing NQS metric: {residual_key}")
            continue
        else:
            # Schema-v1 result files predate explicit residual fields.  Their
            # eigen-residual is exactly sqrt(variance), so they remain fully
            # checkable instead of being invalidated by the schema extension.
            residual = math.sqrt(max(variance, 0.0))
        if residual < 0.0:
            errors.append(f"CG006: negative residual: {residual_key}={residual:.6g}")
        elif residual > MAX_NQS_RESIDUAL:
            errors.append(
                f"CG009: {residual_key}={residual:.6g} exceeds "
                f"{MAX_NQS_RESIDUAL:.1e}"
            )

    symmetry_key = (
        "projected_irrep_error"
        if "projected_irrep_error" in payload
        else "rotation_equivariance_error" if "rotation_equivariance_error" in payload
        else "irrep_error"
    )
    symmetry_error = payload.get(symmetry_key)
    if symmetry_error is not None and float(symmetry_error) > MAX_SYMMETRY_ERROR:
        errors.append(
            f"CG009: {symmetry_key}={float(symmetry_error):.6g} exceeds "
            f"{MAX_SYMMETRY_ERROR:.1e}"
        )

    certificates = payload.get("projection_certificate", {})
    if isinstance(certificates, dict):
        for label, certificate in certificates.items():
            if not isinstance(certificate, dict) or "raising_residual" not in certificate:
                continue
            residual = float(certificate["raising_residual"])
            if residual > MAX_PROJECTION_RESIDUAL:
                errors.append(
                    f"CG009: projection_certificate.{label}.raising_residual="
                    f"{residual:.6g} exceeds {MAX_PROJECTION_RESIDUAL:.1e}"
                )
    return errors


def _finish_result(path: str | Path, payload: dict, errors: list[str]) -> int:
    """Write a finite result and return a fail-closed process status."""

    nonfinite = _nonfinite_paths(payload)
    if nonfinite:
        print(f"CG008: non-finite values at: {nonfinite}", file=sys.stderr)
        return EXIT_NONFINITE
    payload["status"] = "failed" if errors else "complete"
    if errors:
        payload["quality_errors"] = list(errors)
    _write_json(path, payload)
    print(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        if any("CG006:" in error for error in errors):
            return EXIT_INVALID_RESULT
        return EXIT_QUALITY_FAILURE
    return 0


def _fit_metrics(fitted: Any) -> dict:
    """Extract fit diagnostics before any sampling or observable post-processing."""

    return {
        "e_l0": fitted.ground.energy,
        "e_l2": fitted.graviton.energy,
        "gap": fitted.gap,
        "l2_ground": fitted.ground.l2_expectation,
        "l2_excited": fitted.graviton.l2_expectation,
        "variance_l0": fitted.ground.variance,
        "variance_l2": fitted.graviton.variance,
        "residual_l0": fitted.ground.residual_norm,
        "residual_l2": fitted.graviton.residual_norm,
    }


def _reject_nonfinite_fit(fitted: Any) -> int | None:
    nonfinite = _nonfinite_paths(_fit_metrics(fitted), "fit")
    if not nonfinite:
        return None
    print(f"CG008: non-finite values at: {nonfinite}", file=sys.stderr)
    return EXIT_NONFINITE


def _metadata(seed: int, **run_config: Any) -> dict:
    config = {"seed": seed, **run_config}
    tolerances = {
        "max_nqs_variance": MAX_NQS_VARIANCE,
        "max_nqs_residual": MAX_NQS_RESIDUAL,
        "max_ed_residual": MAX_ED_RESIDUAL,
        "max_symmetry_error": MAX_SYMMETRY_ERROR,
        "max_projection_residual": MAX_PROJECTION_RESIDUAL,
    }
    return {
        "schema_version": 2,
        "seed": seed,
        "software": {"chiral_graviton": __version__, "numpy": np.__version__},
        "provenance": collect_provenance(config, tolerances),
        "conventions": {
            "flux": "2Q=3(N-1)",
            "geometry": "Haldane sphere",
            "interaction_distance": "3D chord",
            "background_constant": "excluded; cancels in same-N gap",
        },
    }


def command_ed(args: argparse.Namespace) -> int:
    system = SphereSystem.from_electron_count(args.n)
    result = neutral_gap(system, args.interaction).to_dict()
    result.update(_metadata(args.seed, command="ed", n=args.n, interaction=args.interaction))
    result["method"] = "ed"
    errors = []
    for label in ("l0", "l2"):
        residual = float(result[f"residual_{label}"])
        if residual > MAX_ED_RESIDUAL:
            errors.append(
                f"CG009: residual_{label}={residual:.6g} exceeds {MAX_ED_RESIDUAL:.1e}"
            )
    return _finish_result(args.output, result, errors)


def command_oracle(args: argparse.Namespace) -> int:
    """Run the independent first-quantized Coulomb oracle for N<=4."""

    result = oracle_neutral_gap(
        args.n,
        x_order=args.x_order,
        phi_points=args.phi_points,
    )
    payload = {
        **_metadata(
            args.seed,
            command="oracle",
            n=args.n,
            x_order=args.x_order,
            phi_points=args.phi_points,
        ),
        **result.to_dict(),
        "interaction": "coulomb",
        "l2_ground": 0.0,
        "l2_excited": 6.0,
    }
    errors = []
    for label in ("l0", "l2"):
        residual = float(payload[f"residual_{label}"])
        if residual > MAX_ED_RESIDUAL:
            errors.append(
                f"CG009: independent residual_{label}={residual:.6g} exceeds "
                f"{MAX_ED_RESIDUAL:.1e}"
            )
    if result.hermiticity_error > 1e-12:
        errors.append("CG009: independent pair Hamiltonian is not Hermitian")
    if result.pair_completeness_error > 1e-10:
        errors.append("CG009: independent pair projector is incomplete")
    return _finish_result(args.output, payload, errors)


def command_nqs(args: argparse.Namespace) -> int:
    system = SphereSystem.from_electron_count(args.n)
    model_class = SparseProjectedMLP if args.projection == "sparse" else SharedProjectedMLP
    model = model_class.build(
        system, args.interaction, hidden_width=args.hidden_width, seed=args.seed
    )
    fitted = model.fit(max_iterations=args.max_iterations)
    rejected = _reject_nonfinite_fit(fitted)
    if rejected is not None:
        return rejected
    core_payload = {
        **_metadata(
            args.seed,
            command="nqs",
            n=args.n,
            interaction=args.interaction,
            hidden_width=args.hidden_width,
            max_iterations=args.max_iterations,
            samples=args.samples,
            projection=args.projection,
        ),
        "method": f"symmetry_projected_mlp_nqs_{args.projection}",
        "n_electrons": args.n,
        "two_q": system.two_q,
        "interaction": args.interaction,
        "energy_unit": "e^2/(epsilon*l_B)",
        **_fit_metrics(fitted),
        "optimizer_success": fitted.success,
        "optimizer_message": fitted.message,
        "optimizer_iterations": fitted.iterations,
        "hidden_width": args.hidden_width,
        "projection": args.projection,
    }
    fit_errors = _nqs_quality_errors(core_payload, require_residuals=True)
    if fit_errors:
        # Sampling and symmetry post-processing are deliberately skipped when
        # the optimizer or energy-quality contract has already failed.
        return _finish_result(args.output, core_payload, fit_errors)
    sampled_ground = model.sample_energy(
        fitted.parameters, 0, n_samples=args.samples, seed=args.seed
    )
    sampled_graviton = model.sample_energy(
        fitted.parameters, 2, n_samples=args.samples, seed=args.seed + 1
    )
    sampled_gap = sampled_graviton.mean - sampled_ground.mean
    sampled_gap_error = float(
        np.hypot(sampled_ground.standard_error, sampled_graviton.standard_error)
    )
    payload = {
        **core_payload,
        "sample_count": args.samples,
        "sampled_e_l0": sampled_ground.mean,
        "sampled_e_l0_error": sampled_ground.standard_error,
        "sampled_e_l2": sampled_graviton.mean,
        "sampled_e_l2_error": sampled_graviton.standard_error,
        "sampled_gap": sampled_gap,
        "sampled_gap_error": sampled_gap_error,
        "projected_irrep_error": model.irrep_error(fitted.parameters),
    }
    if args.projection == "sparse":
        certificates = {
            label: model.projection_certificate(fitted.parameters, label)
            for label in (0, 2)
        }
        payload["projection_certificate"] = {
            f"l{label}": {
                "raising_residual": certificate.raising_residual,
                "l2_excess": certificate.l2_excess,
                "cg_iterations": certificate.cg_iterations,
                "refinement_steps": certificate.refinement_steps,
                "kernel_dimension": model.sectors[label].projector.kernel_dimension,
                "sparse_storage_bytes": (
                    model.sectors[label].projector.sparse_storage_bytes
                ),
                "avoided_dense_basis_bytes": (
                    model.sectors[label].projector.avoided_dense_basis_bytes
                ),
            }
            for label, certificate in certificates.items()
        }
    return _finish_result(
        args.output,
        payload,
        _nqs_quality_errors(payload, require_residuals=True),
    )


def command_multiplet(args: argparse.Namespace) -> int:
    """Construct all five members of the lowest L=2 ED multiplet."""

    system = SphereSystem.from_electron_count(args.n)
    pair_table = interaction_pair_table(system, args.interaction)
    highest = solve_fixed_l(
        system, 2, args.interaction, pair_table=pair_table
    )
    report = multiplet_report(
        highest.basis, highest.vector, highest.total_l, pair_table
    )
    payload = {
        **_metadata(args.seed, command="multiplet", n=args.n, interaction=args.interaction),
        "method": "ed_ladder_multiplet",
        "n_electrons": args.n,
        "two_q": system.two_q,
        "interaction": args.interaction,
        "energy_unit": "e^2/(epsilon*l_B)",
        "total_l": report.total_l,
        "m_values": report.m_values,
        "energies": report.energies,
        "l2_expectations": report.l2_expectations,
        "energy_spread": report.energy_spread,
        "rotation_equivariance_error": report.rotation_equivariance_error,
        "highest_weight_residual": highest.residual_norm,
    }
    errors = []
    if report.energy_spread >= 1e-9:
        errors.append("CG009: multiplet energy spread exceeds 1.0e-9")
    if report.rotation_equivariance_error >= 1e-9:
        errors.append("CG009: rotation equivariance error exceeds 1.0e-9")
    if highest.residual_norm > MAX_ED_RESIDUAL:
        errors.append("CG009: highest-weight ED residual exceeds 1.0e-8")
    return _finish_result(args.output, payload, errors)


def command_chirality(args: argparse.Namespace) -> int:
    """Measure integrated parent-channel bright and dark metric weights."""

    system = SphereSystem.from_electron_count(args.n)
    pair_table = interaction_pair_table(system, args.interaction)
    ground = solve_fixed_l(system, 0, args.interaction, pair_table=pair_table)
    graviton = solve_fixed_l(system, 2, args.interaction, pair_table=pair_table)
    response = chiral_graviton_response(
        ground.basis, ground.vector, graviton.basis, graviton.vector
    )
    weights = response.integrated
    ratio = None if weights.dark_plus == 0.0 else weights.bright_to_dark
    payload = {
        **_metadata(args.seed, command="chirality", n=args.n, interaction=args.interaction),
        "method": "rank2_parent_channel_chirality",
        "n_electrons": args.n,
        "two_q": system.two_q,
        "interaction": args.interaction,
        "operator_convention": {
            "bright_minus": "m_rel=3 to 1, q=-2",
            "dark_plus": "m_rel=1 to 3, q=+2",
            "normalization": "common unit reduced matrix element",
        },
        "bright_minus_weight": weights.bright_minus,
        "dark_plus_weight": weights.dark_plus,
        "bright_to_dark_ratio": ratio,
        "lowest_l2_gap": graviton.energy - ground.energy,
        "bright_lowest_l2_weight": response.bright_graviton_weight,
        "dark_lowest_l2_weight": response.dark_graviton_weight,
        "bright_lowest_l2_fraction": response.bright_graviton_fraction,
        "dark_lowest_l2_fraction": response.dark_graviton_fraction,
        "lowest_l2_bright_to_dark_ratio": (
            None
            if response.dark_graviton_weight == 0.0
            else response.graviton_bright_to_dark
        ),
        "l2_excited": graviton.l2_expectation,
        "dark_exact_zero": weights.dark_plus == 0.0,
        "ground_residual": ground.residual_norm,
        "caveat": (
            "Laughlin parent-channel anisotropic pseudopotential probe; "
            "not the full finite-sphere Coulomb metric derivative"
        ),
    }
    errors = []
    if ground.residual_norm > MAX_ED_RESIDUAL:
        errors.append("CG009: chirality ground-state ED residual exceeds 1.0e-8")
    if args.interaction == "v1":
        if not (weights.dark_plus < 1e-20 and weights.bright_minus > 0.0):
            errors.append("CG009: V1 chirality acceptance condition failed")
    elif not (weights.bright_minus > weights.dark_plus > 0.0):
        errors.append("CG009: Coulomb chirality acceptance condition failed")
    return _finish_result(args.output, payload, errors)


def command_nqs_equivariance(args: argparse.Namespace) -> int:
    """Train projected NQS and verify SO(3) rotation equivariance of the output states.

    Two independent checks are performed:

    1. **Scalar invariance** (L=0): verifies the L=0 ground state is annihilated
       by L_-, confirming it is a true SO(3) scalar and not merely a
       highest-weight state with hidden L>0 content.
    2. **Multiplet rotation** (L=2): constructs the full five-member L=2
       multiplet from the NQS highest-weight state via exact lowering, then
       applies a finite rotation and compares against the expected spin-2
       Wigner-D transformation.

    These tests verify that the quantum state produced by the NQS transforms
    correctly under SO(3), even though the neural architecture does not
    encode input equivariance as a structural constraint.
    """

    system = SphereSystem.from_electron_count(args.n)
    model_class = SparseProjectedMLP if args.projection == "sparse" else SharedProjectedMLP
    build_options = {"hidden_width": args.hidden_width, "seed": args.seed}
    if args.projection == "sparse":
        build_options.update(solver_tolerance=2e-14, certificate_tolerance=1e-12)
    model = model_class.build(system, args.interaction, **build_options)
    fitted = model.fit(max_iterations=args.max_iterations)
    rejected = _reject_nonfinite_fit(fitted)
    if rejected is not None:
        return rejected

    core_payload = {
        **_metadata(
            args.seed,
            command="nqs-equivariance",
            n=args.n,
            interaction=args.interaction,
            hidden_width=args.hidden_width,
            max_iterations=args.max_iterations,
            projection=args.projection,
        ),
        "method": f"projected_nqs_rotation_equivariance_{args.projection}",
        "n_electrons": args.n,
        "two_q": system.two_q,
        "interaction": args.interaction,
        "energy_unit": "e^2/(epsilon*l_B)",
        "projection": args.projection,
        "hidden_width": args.hidden_width,
        **_fit_metrics(fitted),
        "optimizer_success": fitted.success,
        "optimizer_message": fitted.message,
        "optimizer_iterations": fitted.iterations,
        "irrep_error_l0": abs(fitted.ground.l2_expectation - 0.0),
        "irrep_error_l2": abs(fitted.graviton.l2_expectation - 6.0),
    }

    fit_errors = _nqs_quality_errors(core_payload, require_residuals=True)
    if fit_errors:
        return _finish_result(args.output, core_payload, fit_errors)

    # Scalar invariance: L_- |psi_0> should vanish for a genuine L=0 state.
    scalar_error = model.scalar_rotation_error(fitted.parameters)

    # Multiplet rotation: build the five L=2 components and compare the
    # finite-rotation result against the spin-2 Wigner-D matrix.
    multiplet_error = model.multiplet_rotation_error(fitted.parameters)

    payload = {
        **core_payload,
        "scalar_invariance_error": scalar_error,
        "multiplet_rotation_error": multiplet_error,
        "rotation_axis": [1.0, 2.0, 3.0],
        "rotation_angle_rad": 0.371,
        "caveat": (
            "These metrics verify that the output quantum state transforms "
            "correctly under SO(3). They do not imply the neural architecture "
            "is input-equivariant — symmetry is enforced by exact projection "
            "onto ker(L_+) followed by ladder-operator construction of the "
            "full multiplet, not by network weight constraints."
        ),
    }

    errors: list[str] = []
    if scalar_error >= MAX_PROJECTION_RESIDUAL:
        errors.append(
            f"CG009: scalar invariance error {scalar_error:.3e} exceeds "
            f"{MAX_PROJECTION_RESIDUAL:.1e}"
        )
    if multiplet_error >= MAX_PROJECTION_RESIDUAL:
        errors.append(
            f"CG009: multiplet rotation error {multiplet_error:.3e} exceeds "
            f"{MAX_PROJECTION_RESIDUAL:.1e}"
        )

    return _finish_result(args.output, payload, errors)


def command_nqs_multiplet(args: argparse.Namespace) -> int:
    """Train the NQS and rotate its L=2 head through the full multiplet."""

    system = SphereSystem.from_electron_count(args.n)
    model_class = SparseProjectedMLP if args.projection == "sparse" else SharedProjectedMLP
    build_options = {"hidden_width": args.hidden_width, "seed": args.seed}
    if args.projection == "sparse":
        build_options.update(solver_tolerance=2e-14, certificate_tolerance=1e-12)
    model = model_class.build(system, args.interaction, **build_options)
    fitted = model.fit(max_iterations=args.max_iterations)
    rejected = _reject_nonfinite_fit(fitted)
    if rejected is not None:
        return rejected
    core_payload = {
        **_metadata(
            args.seed,
            command="nqs-multiplet",
            n=args.n,
            interaction=args.interaction,
            hidden_width=args.hidden_width,
            max_iterations=args.max_iterations,
            projection=args.projection,
        ),
        "method": f"nqs_ladder_multiplet_{args.projection}",
        "n_electrons": args.n,
        "two_q": system.two_q,
        "interaction": args.interaction,
        "energy_unit": "e^2/(epsilon*l_B)",
        "projection": args.projection,
        "nqs_gap": fitted.gap,
        "e_l0": fitted.ground.energy,
        "e_l2": fitted.graviton.energy,
        "gap": fitted.gap,
        "variance_l0": fitted.ground.variance,
        "variance_l2": fitted.graviton.variance,
        "residual_l0": fitted.ground.residual_norm,
        "residual_l2": fitted.graviton.residual_norm,
        "l2_ground": fitted.ground.l2_expectation,
        "l2_excited": fitted.graviton.l2_expectation,
        "optimizer_success": fitted.success,
        "optimizer_message": fitted.message,
        "optimizer_iterations": fitted.iterations,
    }
    fit_errors = _nqs_quality_errors(core_payload, require_residuals=True)
    if fit_errors:
        return _finish_result(args.output, core_payload, fit_errors)
    pair_table = interaction_pair_table(system, args.interaction)
    sector = model.sectors[2]
    report = multiplet_report(
        sector.basis, model.vector(fitted.parameters, 2), 2, pair_table
    )
    payload = {
        **core_payload,
        "nqs_variance_l2": fitted.graviton.variance,
        "projected_irrep_error": model.irrep_error(fitted.parameters),
        "m_values": report.m_values,
        "energies": report.energies,
        "l2_expectations": report.l2_expectations,
        "energy_spread": report.energy_spread,
        "rotation_equivariance_error": report.rotation_equivariance_error,
    }
    errors = _nqs_quality_errors(payload, require_residuals=True)
    if report.energy_spread >= 1e-8:
        errors.append("CG009: NQS multiplet energy spread exceeds 1.0e-8")
    if report.rotation_equivariance_error >= 1e-8:
        errors.append("CG009: NQS rotation equivariance error exceeds 1.0e-8")
    return _finish_result(args.output, payload, errors)


def command_nqs_chirality(args: argparse.Namespace) -> int:
    """Train projected NQS states and evaluate their parent-channel response."""

    system = SphereSystem.from_electron_count(args.n)
    metadata = _metadata(
        args.seed,
        command="nqs-chirality",
        n=args.n,
        interaction=args.interaction,
        hidden_width=args.hidden_width,
        max_iterations=args.max_iterations,
        projection=args.projection,
    )
    try:
        result = train_nqs_chirality(
            system,
            args.interaction,
            projection=args.projection,
            hidden_width=args.hidden_width,
            seed=args.seed,
            max_iterations=args.max_iterations,
            maximum_variance=MAX_NQS_VARIANCE,
        )
    except RuntimeError as error:
        failed_payload = {
            **metadata,
            "method": f"nqs_rank2_parent_channel_chirality_{args.projection}",
            "state_source": "trained_projected_nqs",
            "n_electrons": args.n,
            "two_q": system.two_q,
            "interaction": args.interaction,
            "energy_unit": "e^2/(epsilon*l_B)",
            "failure_stage": "nqs_training",
        }
        return _finish_result(args.output, failed_payload, [str(error)])
    fitted = result.training
    response = result.response
    weights = response.integrated
    payload = {
        **metadata,
        "method": f"nqs_rank2_parent_channel_chirality_{args.projection}",
        "state_source": "trained_projected_nqs",
        "n_electrons": args.n,
        "two_q": system.two_q,
        "interaction": args.interaction,
        "energy_unit": "e^2/(epsilon*l_B)",
        "projection": args.projection,
        "hidden_width": args.hidden_width,
        **_fit_metrics(fitted),
        "projected_irrep_error": result.irrep_error,
        "optimizer_success": fitted.success,
        "optimizer_message": fitted.message,
        "optimizer_iterations": fitted.iterations,
        "operator_convention": {
            "bright_minus": "m_rel=3 to 1, q=-2",
            "dark_plus": "m_rel=1 to 3, q=+2",
            "normalization": "common unit reduced matrix element",
        },
        "bright_minus_weight": weights.bright_minus,
        "dark_plus_weight": weights.dark_plus,
        "bright_to_dark_ratio": (
            None if weights.dark_plus == 0.0 else weights.bright_to_dark
        ),
        "bright_lowest_l2_weight": response.bright_graviton_weight,
        "dark_lowest_l2_weight": response.dark_graviton_weight,
        "bright_lowest_l2_fraction": response.bright_graviton_fraction,
        "dark_lowest_l2_fraction": response.dark_graviton_fraction,
        "lowest_l2_bright_to_dark_ratio": (
            None
            if response.dark_graviton_weight == 0.0
            else response.graviton_bright_to_dark
        ),
        "caveat": (
            "NQS states with the Laughlin m_rel=1<->3 parent-channel proxy; "
            "not the full finite-sphere Coulomb metric derivative"
        ),
    }
    return _finish_result(
        args.output,
        payload,
        _nqs_quality_errors(payload, require_residuals=True),
    )


def command_validate(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.result).read_text(encoding="utf-8"))
    if payload.get("status", "complete") != "complete":
        print(f"CG006: result status is {payload.get('status')!r}, not 'complete'", file=sys.stderr)
        return EXIT_INVALID_RESULT
    required = {
        "schema_version",
        "method",
        "n_electrons",
        "two_q",
        "e_l0",
        "e_l2",
        "gap",
        "l2_excited",
        "energy_unit",
    }
    missing = sorted(required - payload.keys())
    if missing:
        print(f"CG006: missing result keys: {missing}", file=sys.stderr)
        return EXIT_INVALID_RESULT
    nonfinite = _nonfinite_paths(payload)
    if nonfinite:
        print(f"CG008: non-finite values at: {nonfinite}", file=sys.stderr)
        return EXIT_NONFINITE
    if payload["two_q"] != 3 * (payload["n_electrons"] - 1):
        print("CG001: invalid Laughlin flux", file=sys.stderr)
        return EXIT_QUALITY_FAILURE
    if abs(payload["gap"] - (payload["e_l2"] - payload["e_l0"])) > 1e-10:
        print("CG006: inconsistent gap", file=sys.stderr)
        return EXIT_INVALID_RESULT
    if abs(payload["l2_excited"] - 6.0) > 1e-7:
        print("CG006: excited state is not clean L=2", file=sys.stderr)
        return EXIT_QUALITY_FAILURE
    if payload["energy_unit"] != "e^2/(epsilon*l_B)":
        print("CG006: unexpected energy unit", file=sys.stderr)
        return EXIT_INVALID_RESULT

    method = str(payload["method"])
    if "nqs" in method:
        nqs_required = {"optimizer_success", "variance_l0", "variance_l2"}
        missing_nqs = sorted(nqs_required - payload.keys())
        if missing_nqs:
            print(f"CG006: missing NQS keys: {missing_nqs}", file=sys.stderr)
            return EXIT_INVALID_RESULT
        errors = _nqs_quality_errors(payload, require_residuals=False)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return (
                EXIT_INVALID_RESULT
                if any("CG006:" in error for error in errors)
                else EXIT_QUALITY_FAILURE
            )
    elif method == "ed":
        residual_keys = {"residual_l0", "residual_l2"}
        missing_residuals = sorted(residual_keys - payload.keys())
        if missing_residuals:
            print(f"CG006: missing ED residuals: {missing_residuals}", file=sys.stderr)
            return EXIT_INVALID_RESULT
        for key in sorted(residual_keys):
            residual = float(payload[key])
            if residual < 0.0:
                print(f"CG006: negative ED residual: {key}", file=sys.stderr)
                return EXIT_INVALID_RESULT
            if residual > MAX_ED_RESIDUAL:
                print(
                    f"CG009: {key}={residual:.6g} exceeds {MAX_ED_RESIDUAL:.1e}",
                    file=sys.stderr,
                )
                return EXIT_QUALITY_FAILURE
    print("valid")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chiral-graviton")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler in (("ed", command_ed), ("nqs", command_nqs)):
        sub = subparsers.add_parser(name)
        sub.add_argument("--n", type=int, required=True)
        sub.add_argument("--interaction", choices=("v1", "coulomb"), default="coulomb")
        sub.add_argument("--seed", type=int, default=1729)
        sub.add_argument("--output", required=True)
        if name == "nqs":
            sub.add_argument("--hidden-width", type=int, default=24)
            sub.add_argument("--max-iterations", type=int, default=400)
            sub.add_argument("--samples", type=int, default=50_000)
            sub.add_argument("--projection", choices=("dense", "sparse"), default="dense")
        sub.set_defaults(handler=handler)

    oracle = subparsers.add_parser("oracle")
    oracle.add_argument("--n", type=int, choices=(2, 3, 4), required=True)
    oracle.add_argument("--x-order", type=int, default=64)
    oracle.add_argument("--phi-points", type=int, default=256)
    oracle.add_argument("--seed", type=int, default=1729)
    oracle.add_argument("--output", required=True)
    oracle.set_defaults(handler=command_oracle)

    validate = subparsers.add_parser("validate")
    validate.add_argument("result")
    validate.set_defaults(handler=command_validate)

    multiplet = subparsers.add_parser("multiplet")
    multiplet.add_argument("--n", type=int, required=True)
    multiplet.add_argument("--interaction", choices=("v1", "coulomb"), default="coulomb")
    multiplet.add_argument("--seed", type=int, default=1729)
    multiplet.add_argument("--output", required=True)
    multiplet.set_defaults(handler=command_multiplet)

    chirality = subparsers.add_parser("chirality")
    chirality.add_argument("--n", type=int, required=True)
    chirality.add_argument("--interaction", choices=("v1", "coulomb"), default="coulomb")
    chirality.add_argument("--seed", type=int, default=1729)
    chirality.add_argument("--output", required=True)
    chirality.set_defaults(handler=command_chirality)

    nqs_multiplet = subparsers.add_parser("nqs-multiplet")
    nqs_multiplet.add_argument("--n", type=int, required=True)
    nqs_multiplet.add_argument(
        "--interaction", choices=("v1", "coulomb"), default="coulomb"
    )
    nqs_multiplet.add_argument("--seed", type=int, default=1729)
    nqs_multiplet.add_argument("--hidden-width", type=int, default=24)
    nqs_multiplet.add_argument("--max-iterations", type=int, default=400)
    nqs_multiplet.add_argument("--projection", choices=("dense", "sparse"), default="sparse")
    nqs_multiplet.add_argument("--output", required=True)
    nqs_multiplet.set_defaults(handler=command_nqs_multiplet)

    nqs_equivariance = subparsers.add_parser("nqs-equivariance")
    nqs_equivariance.add_argument("--n", type=int, required=True)
    nqs_equivariance.add_argument(
        "--interaction", choices=("v1", "coulomb"), default="coulomb"
    )
    nqs_equivariance.add_argument("--seed", type=int, default=1729)
    nqs_equivariance.add_argument("--hidden-width", type=int, default=24)
    nqs_equivariance.add_argument("--max-iterations", type=int, default=400)
    nqs_equivariance.add_argument(
        "--projection", choices=("dense", "sparse"), default="sparse"
    )
    nqs_equivariance.add_argument("--output", required=True)
    nqs_equivariance.set_defaults(handler=command_nqs_equivariance)

    nqs_chirality = subparsers.add_parser("nqs-chirality")
    nqs_chirality.add_argument("--n", type=int, required=True)
    nqs_chirality.add_argument(
        "--interaction", choices=("v1", "coulomb"), default="coulomb"
    )
    nqs_chirality.add_argument("--seed", type=int, default=1729)
    nqs_chirality.add_argument("--hidden-width", type=int, default=24)
    nqs_chirality.add_argument("--max-iterations", type=int, default=400)
    nqs_chirality.add_argument(
        "--projection", choices=("dense", "sparse"), default="dense"
    )
    nqs_chirality.add_argument("--output", required=True)
    nqs_chirality.set_defaults(handler=command_nqs_chirality)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (FloatingPointError, OverflowError) as error:
        print(f"CG008: non-finite numerical failure: {error}", file=sys.stderr)
        return EXIT_NONFINITE
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return EXIT_QUALITY_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
