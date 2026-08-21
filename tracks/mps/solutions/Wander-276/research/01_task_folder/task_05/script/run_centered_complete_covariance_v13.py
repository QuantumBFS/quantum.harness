#!/usr/bin/env python3
"""Population-centered frozen-split complete-covariance inference for Paper I.

This additive v13 calculation repairs the mean/whitening mismatch identified in
the v12 panel analysis.  The population mean is evaluated from the finite
registered tangent ensemble rather than estimated from twelve training panels.
Panels 0--11 determine only a channel-whitening transformation; panels 12--23
are the only units used by the primary U-statistic.  The reverse split is
reported descriptively and is never pooled with the primary result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy.stats import t as student_t

from lgeth.full_wick_ustat import ResponseFactors
from lgeth.continuum_lll_parent import phase_space_generator
from lgeth.lattice_susy_parent import (
    lattice_susy_response,
    normalized_cycle_couplings,
    project_component_tangents,
    solve_cycle_union_frame,
)
from lgeth.moore_read_parent import build_continuum_moore_read_parent
from lgeth.protected_generator_response import analytic_protected_generator_response
from run_cross_complete_covariance_v12 import (
    complete_covariance_summary,
    lattice_susy_panel_ensemble,
)
from run_moore_read_geometric_eth_v9 import (
    REGISTERED_PANEL_SIZE as MOORE_PANEL_SIZE,
)
from run_moore_read_geometric_eth_v9 import (
    REGISTERED_PANELS as MOORE_PANEL_COUNT,
)
from run_moore_read_geometric_eth_v9 import REGISTERED_SEED as MOORE_SEED
from run_moore_read_geometric_eth_v9 import (
    OPERATOR_CLASS as MOORE_OPERATOR_CLASS,
    _load_kernel,
    case_for_particle_number,
    prepare_kernel,
    run_panel,
)
from run_lattice_susy_geometric_eth_v10 import REGISTERED_SEED as LATTICE_SEED


VERSION = "v13"
SCRIPT_ROOT = Path(__file__).resolve().parent
PAPER1_OUTPUT_ROOT = SCRIPT_ROOT / "output" / "paper1_prb_v13"
OUTPUT_PATH = PAPER1_OUTPUT_ROOT / "centered_complete_covariance_v13.json"
MOORE_CHECKPOINT_ROOT = (
    PAPER1_OUTPUT_ROOT / "centered_covariance_v13_checkpoints" / "moore_read"
)
PRIMARY_TRAIN = tuple(range(12))
PRIMARY_INFERENCE = tuple(range(12, 24))
REVERSE_TRAIN = PRIMARY_INFERENCE
REVERSE_INFERENCE = PRIMARY_TRAIN
LABEL_COUNT = 2
SUPPORT_RTOL = 1.0e-10


@dataclass(frozen=True)
class FrozenSplit:
    """Inference samples transformed by statistics frozen on disjoint panels."""

    inference_samples: tuple[ResponseFactors, ...]
    audit: dict[str, Any]


@dataclass(frozen=True)
class CalibratedEnsemble:
    """Registered panels with an exact mean for their finite sampling law."""

    samples: tuple[ResponseFactors, ...]
    population_mean: np.ndarray
    mean_provenance: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _array_sha256(values: np.ndarray) -> str:
    array = np.ascontiguousarray(np.asarray(values, dtype=np.complex128))
    return hashlib.sha256(array.view(np.uint8)).hexdigest()


def _complex_matrix(values: np.ndarray) -> dict[str, list[list[float]]]:
    matrix = np.asarray(values, dtype=complex)
    return {
        "real": matrix.real.tolist(),
        "imag": matrix.imag.tolist(),
    }


def _channel_gram(values: np.ndarray) -> np.ndarray:
    """Return C_mn = E[sum_i,a z_{m i a} z^*_{n i a}]/rank."""

    channels = np.asarray(values, dtype=complex)
    if channels.ndim != 4 or channels.shape[1] != LABEL_COUNT:
        raise RuntimeError("channel panels must have shape (unit, 2, ambient, rank)")
    count = channels.shape[0]
    rank = channels.shape[-1]
    gram = np.einsum(
        "rmai,rnai->mn",
        channels,
        channels.conj(),
        optimize=True,
    ) / (count * rank)
    return 0.5 * (gram + gram.conj().T)


def _validate_samples(samples: Sequence[ResponseFactors]) -> tuple[ResponseFactors, ...]:
    records = tuple(samples)
    if len(records) != 24:
        raise RuntimeError("centered v13 inference requires exactly 24 panels")
    reference = records[0]
    if reference.label_count != LABEL_COUNT:
        raise RuntimeError("centered v13 inference requires exactly two channels")
    for record in records:
        if (
            record.label_count != LABEL_COUNT
            or record.ambient_dimension != reference.ambient_dimension
            or record.target_rank != reference.target_rank
            or record.frame.shape != reference.frame.shape
            or not np.allclose(record.frame, reference.frame, atol=2e-12, rtol=2e-12)
        ):
            raise RuntimeError("panels do not share one fixed common fiber")
    return records


def _validate_split_indices(
    training_indices: Sequence[int], inference_indices: Sequence[int]
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    training = tuple(int(index) for index in training_indices)
    inference = tuple(int(index) for index in inference_indices)
    if len(training) != 12 or len(inference) != 12:
        raise RuntimeError("frozen split requires 12 training and 12 inference panels")
    if set(training) & set(inference) or set(training) | set(inference) != set(range(24)):
        raise RuntimeError("frozen split must partition panels 0 through 23")
    return training, inference


def frozen_center_whiten_split(
    samples: Sequence[ResponseFactors],
    training_indices: Sequence[int],
    inference_indices: Sequence[int],
    *,
    population_mean: np.ndarray,
    mean_provenance: str,
    support_rtol: float = SUPPORT_RTOL,
) -> FrozenSplit:
    """Center by an exact finite-ensemble mean and fit whitening on training."""

    records = _validate_samples(samples)
    training, inference = _validate_split_indices(training_indices, inference_indices)
    raw = np.asarray([record.channels for record in records], dtype=complex)
    training_raw = raw[np.asarray(training)]
    inference_raw = raw[np.asarray(inference)]
    entrywise_mean = np.asarray(population_mean, dtype=complex)
    if entrywise_mean.shape != raw.shape[1:] or not (
        np.all(np.isfinite(entrywise_mean.real))
        and np.all(np.isfinite(entrywise_mean.imag))
    ):
        raise RuntimeError("population mean has incompatible shape or values")
    provenance = str(mean_provenance).strip()
    if not provenance:
        raise RuntimeError("population mean provenance is required")
    centered_training = training_raw - entrywise_mean[None, ...]
    centered_inference = inference_raw - entrywise_mean[None, ...]
    gram = _channel_gram(centered_training)
    eigenvalues, eigenvectors = np.linalg.eigh(gram)
    largest = float(eigenvalues[-1])
    smallest = float(eigenvalues[0])
    threshold = float(support_rtol) * largest
    if (
        not np.all(np.isfinite(eigenvalues))
        or largest <= np.finfo(float).tiny
        or smallest <= threshold
    ):
        raise RuntimeError(
            "ill-conditioned channel support: "
            f"eigenvalues={eigenvalues.tolist()}, threshold={threshold}"
        )
    # With C_mn = E[z_m z_n^*], left-channel mixing z' = W z gives
    # C' = W C W^\dagger.  The Hermitian inverse square root below therefore
    # has the required orientation; applying W^T or conjugating the einsum
    # operands would implement a different covariance convention.
    whitener = (
        eigenvectors * (eigenvalues ** -0.5)[None, :]
    ) @ eigenvectors.conj().T
    whitened_training = np.einsum(
        "mn,rnai->rmai", whitener, centered_training, optimize=True
    )
    whitened_inference = np.einsum(
        "mn,rnai->rmai", whitener, centered_inference, optimize=True
    )
    training_gram = _channel_gram(whitened_training)
    inference_gram = _channel_gram(whitened_inference)
    identity_error = float(np.linalg.norm(training_gram - np.eye(LABEL_COUNT)))
    if identity_error > 2e-9:
        raise RuntimeError(
            f"training channel whitening failed: identity error {identity_error}"
        )

    raw_rms = float(np.sqrt(np.mean(np.abs(training_raw) ** 2)))
    raw_mean_rms = float(np.sqrt(np.mean(np.abs(entrywise_mean) ** 2)))
    inference_mean = np.mean(whitened_inference, axis=0)
    inference_rms = float(np.sqrt(np.mean(np.abs(whitened_inference) ** 2)))
    inference_mean_rms = float(np.sqrt(np.mean(np.abs(inference_mean) ** 2)))
    reference = records[0]
    transformed = tuple(
        ResponseFactors(frame=reference.frame, channels=channels)
        for channels in whitened_inference
    )
    audit = {
        "training_indices": list(training),
        "inference_indices": list(inference),
        "training_count": len(training),
        "inference_count": len(inference),
        "support_rank": LABEL_COUNT,
        "support_rtol": float(support_rtol),
        "population_mean_provenance": provenance,
        "population_mean_exact_for_registered_finite_ensemble": True,
        "population_mean_relative_rms": raw_mean_rms / raw_rms,
        "training_sample_mean_relative_rms": float(
            np.sqrt(np.mean(np.abs(np.mean(training_raw, axis=0)) ** 2)) / raw_rms
        ),
        "training_centered_channel_gram": _complex_matrix(gram),
        "training_centered_channel_gram_eigenvalues": eigenvalues.tolist(),
        "training_channel_condition_number": largest / smallest,
        "training_whitened_channel_gram": _complex_matrix(training_gram),
        "training_whitened_gram_identity_error": identity_error,
        "inference_whitened_channel_gram": _complex_matrix(inference_gram),
        "inference_whitened_relative_mean_rms": inference_mean_rms / inference_rms,
        "population_mean_sha256": _array_sha256(entrywise_mean),
        "channel_whitener_sha256": _array_sha256(whitener),
        "centering_not_estimated_from_training_panels": True,
        "channel_whitener_fitted_only_on_training": True,
    }
    return FrozenSplit(inference_samples=transformed, audit=audit)


def _summary(
    samples: Sequence[ResponseFactors], *, oracle: bool = False
) -> dict[str, Any]:
    records = tuple(samples)
    return complete_covariance_summary(
        records,
        block_size=max(2, min(64, records[0].target_rank)),
        oracle=bool(oracle),
    )


def _sign_provenance() -> dict[str, Any]:
    return {
        "kato_projector_derivative": "X_a=-Q[Q(H-E0)Q]^-1Q(dH)P",
        "source_registry_unsigned_resolvent": "Q(H-E0)^-1Q(dH)P",
        "stored_channel_interpretation": "stored_channels=-X_a_when_source_omits_Kato_minus",
        "even_contractions_invariant_under_global_channel_sign": True,
    }


def analyze_model(
    samples: Sequence[ResponseFactors],
    *,
    model_id: str,
    population_mean: np.ndarray,
    mean_provenance: str,
) -> dict[str, Any]:
    """Return raw v12 and corrected frozen-split statistics without aliasing."""

    records = _validate_samples(samples)
    raw_summary = _summary(records, oracle=str(model_id) == "lattice_susy_m1")
    primary = frozen_center_whiten_split(
        records,
        PRIMARY_TRAIN,
        PRIMARY_INFERENCE,
        population_mean=population_mean,
        mean_provenance=mean_provenance,
    )
    reverse = frozen_center_whiten_split(
        records,
        REVERSE_TRAIN,
        REVERSE_INFERENCE,
        population_mean=population_mean,
        mean_provenance=mean_provenance,
    )
    primary_summary = _summary(primary.inference_samples)
    reverse_summary = _summary(reverse.inference_samples)
    return {
        "model_id": str(model_id),
        "response_sign_provenance": _sign_provenance(),
        "raw_v12_residual": {
            "statistic": "uncentered_unwhitened_raw_moment_residual",
            "claim_eligible": False,
            "summary": raw_summary,
        },
        "centered_whitened_complete_cumulant": {
            "statistic": "centered_whitened_complete_cumulant",
            "primary": {
                "inferential_role": "primary_frozen_12_12_split",
                "claim_eligible": True,
                "transform_audit": primary.audit,
                "summary": primary_summary,
                "nominal_positive_directional_gate": primary_summary[
                    "positive_directional_gate"
                ],
                "gate_for_claim": None,
            },
            "reverse_descriptive": {
                "inferential_role": "descriptive_replication_not_pooled",
                "claim_eligible": False,
                "transform_audit": reverse.audit,
                "summary": reverse_summary,
                "gate_for_claim": None,
            },
        },
    }


def _lattice_population_mean(cycles: int) -> np.ndarray:
    """Enumerate the exact channel marginals of the local-panel protocol."""

    count = int(cycles)
    couplings = normalized_cycle_couplings(count, int(LATTICE_SEED) + count)
    frame = solve_cycle_union_frame(count, couplings)
    tangent_pairs: list[np.ndarray] = []
    if count == 1:
        for first in range(6):
            for second in range(6):
                if first == second:
                    continue
                candidates = np.eye(6, dtype=complex)[[first, second]]
                tangent_pairs.append(
                    project_component_tangents(couplings, candidates, count)
                )
    else:
        identity = np.eye(6 * count, dtype=complex)
        for first in range(6):
            for second in range(6):
                candidates = np.stack([identity[first], identity[6 + second]])
                tangent_pairs.append(
                    project_component_tangents(couplings, candidates, count)
                )
    responses = [
        lattice_susy_response(frame, couplings, tangents).total
        for tangents in tangent_pairs
    ]
    return np.mean(np.asarray(responses, dtype=complex), axis=0)


def _lattice_ensemble(cycles: int) -> CalibratedEnsemble:
    count = int(cycles)
    samples = lattice_susy_panel_ensemble(count, count=24)
    return CalibratedEnsemble(
        samples=samples,
        population_mean=_lattice_population_mean(count),
        mean_provenance=(
            "exact_enumeration_of_ordered_local_coordinate_channel_marginals"
        ),
    )


def _moore_paths(root: Path, particles: int) -> tuple[Path, tuple[Path, ...]]:
    case = case_for_particle_number(int(particles))
    label = f"N{case.N}_flux{case.n_flux}"
    kernel = Path(root) / "kernels" / f"{label}_v9.npz"
    panels = tuple(
        Path(root) / "panels" / f"{label}_panel{index:02d}_v9.npz"
        for index in range(MOORE_PANEL_COUNT)
    )
    return kernel, panels


def _moore_ensemble(particles: int) -> CalibratedEnsemble:
    case = case_for_particle_number(int(particles))
    root = MOORE_CHECKPOINT_ROOT / f"N{case.N}_flux{case.n_flux}"
    prepare_kernel(case, root, seed=MOORE_SEED, force=False)
    for panel in range(MOORE_PANEL_COUNT):
        run_panel(
            case,
            panel,
            root,
            panels=MOORE_PANEL_COUNT,
            panel_size=MOORE_PANEL_SIZE,
            seed=MOORE_SEED,
            save_channels=True,
            force=False,
        )
    kernel_path, panel_paths = _moore_paths(root, particles)
    if not kernel_path.is_file() or any(not path.is_file() for path in panel_paths):
        raise RuntimeError("v13-local Moore--Read checkpoint generation is incomplete")
    with np.load(kernel_path, allow_pickle=False) as arrays:
        frame = np.asarray(arrays["frame"], dtype=complex)
    records: list[ResponseFactors] = []
    for path in panel_paths:
        with np.load(path, allow_pickle=False) as arrays:
            if "response_channels" not in arrays:
                raise RuntimeError(f"v13-local Moore--Read panel lacks channels: {path}")
            channels = np.asarray(arrays["response_channels"], dtype=complex)
        records.append(ResponseFactors(frame=frame, channels=channels[:LABEL_COUNT]))
    kernel, _ = _load_kernel(case, root, seed=MOORE_SEED)
    average_generator = np.mean(
        np.asarray(
            [
                phase_space_generator(
                    case.n_flux,
                    (x, y),
                    MOORE_OPERATOR_CLASS,
                )
                for y in range(case.n_flux)
                for x in range(case.n_flux)
            ],
            dtype=complex,
        ),
        axis=0,
    )
    system = build_continuum_moore_read_parent(case.N, case.n_flux)
    mean_response = analytic_protected_generator_response(
        system,
        kernel,
        average_generator[None, ...],
    ).channels[0]
    population_mean = np.repeat(
        mean_response[None, ...], LABEL_COUNT, axis=0
    )
    return CalibratedEnsemble(
        samples=tuple(records),
        population_mean=population_mean,
        mean_provenance=(
            "exact_uniform_average_over_all_torus_guiding_density_anchors"
        ),
    )


def _source_hashes() -> dict[str, str]:
    paths = {
        "run_centered_complete_covariance_v13.py": Path(__file__).resolve(),
        "run_cross_complete_covariance_v12.py": SCRIPT_ROOT
        / "run_cross_complete_covariance_v12.py",
        "run_moore_read_geometric_eth_v9.py": SCRIPT_ROOT
        / "run_moore_read_geometric_eth_v9.py",
        "lgeth/full_wick_ustat.py": SCRIPT_ROOT / "lgeth" / "full_wick_ustat.py",
        "lgeth/cumulant_inference.py": SCRIPT_ROOT / "lgeth" / "cumulant_inference.py",
    }
    return {name: _sha256(path) for name, path in sorted(paths.items())}


def canonical_scientific_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"


def build_payload(model_ids: Sequence[str]) -> dict[str, Any]:
    loaders = {
        "lattice_susy_m1": lambda: _lattice_ensemble(1),
        "lattice_susy_m2": lambda: _lattice_ensemble(2),
        "lattice_susy_m3": lambda: _lattice_ensemble(3),
        "moore_read_N4": lambda: _moore_ensemble(4),
        "moore_read_N6": lambda: _moore_ensemble(6),
    }
    requested = tuple(str(model) for model in model_ids)
    if not requested or len(set(requested)) != len(requested):
        raise RuntimeError("model selection must be nonempty and unique")
    unknown = sorted(set(requested) - set(loaders))
    if unknown:
        raise RuntimeError(f"unknown centered covariance models: {unknown}")
    models = {}
    for model_id in requested:
        ensemble = loaders[model_id]()
        models[model_id] = analyze_model(
            ensemble.samples,
            model_id=model_id,
            population_mean=ensemble.population_mean,
            mean_provenance=ensemble.mean_provenance,
        )
    family_alpha = 0.05
    per_case_alpha = family_alpha / len(models)
    inference_count = len(PRIMARY_INFERENCE)
    degrees_of_freedom = inference_count - 1
    family_critical = float(
        student_t.ppf(1.0 - per_case_alpha, df=degrees_of_freedom)
    )
    for model in models.values():
        primary = model["centered_whitened_complete_cumulant"]["primary"]
        summary = primary["summary"]
        t_score = float(
            summary["directional_estimate"] / summary["standard_error"]
        )
        student_p = float(student_t.sf(t_score, df=degrees_of_freedom))
        family_low = float(
            summary["directional_estimate"]
            - family_critical * summary["standard_error"]
        )
        family_gate = bool(
            student_p < per_case_alpha and family_low > 0.0
        )
        primary["familywise_method"] = (
            "Bonferroni_over_registered_primary_cases_with_Student_t11"
        )
        primary["family_alpha"] = family_alpha
        primary["per_case_alpha"] = per_case_alpha
        primary["student_t_degrees_of_freedom"] = degrees_of_freedom
        primary["student_t_score"] = t_score
        primary["student_t_one_sided_p_value"] = student_p
        primary["familywise_one_sided_interval_low"] = family_low
        primary["gate_for_claim"] = family_gate
    gates = {
        model_id: model[
            "centered_whitened_complete_cumulant"
        ]["primary"]["gate_for_claim"]
        for model_id, model in models.items()
    }
    payload = {
        "version": VERSION,
        "schema": "paper1_centered_complete_covariance_v13",
        "protocol": {
            "panel_count": 24,
            "primary_training_indices": list(PRIMARY_TRAIN),
            "primary_inference_indices": list(PRIMARY_INFERENCE),
            "reverse_split_role": "descriptive_replication_not_pooled",
            "entrywise_mean": "exact_registered_finite_ensemble_population_mean",
            "channel_whitening": "training_2x2_Gram_only",
            "complete_wick_pairings": 3,
            "inference_unit": "fixed-base_exchangeable_complete_tangent_panel",
            "primary_case_family_size": len(models),
            "familywise_method": "Bonferroni",
            "finite_sample_reference": "Student_t",
            "student_t_degrees_of_freedom": degrees_of_freedom,
            "family_alpha": family_alpha,
            "per_case_alpha": per_case_alpha,
        },
        "models": models,
        "corrected_primary_positive_directional_gate": gates,
        "claim_boundary": (
            "Primary gates use exact finite-ensemble population centering and are "
            "conditional on the frozen 12/12 channel-whitening split; the reverse "
            "split is descriptive and no panels are pooled."
        ),
        "source_hashes": _source_hashes(),
    }
    encoded = canonical_scientific_json(payload).encode("utf-8")
    payload["scientific_payload_sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(canonical_scientific_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o644)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        default=(
            "lattice_susy_m1,lattice_susy_m2,lattice_susy_m3,"
            "moore_read_N4,moore_read_N6"
        ),
        help="Comma-separated registered model IDs.",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    arguments = parser.parse_args()
    model_ids = tuple(item.strip() for item in arguments.models.split(",") if item.strip())
    payload = build_payload(model_ids)
    _write_atomic(arguments.output, payload)
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
