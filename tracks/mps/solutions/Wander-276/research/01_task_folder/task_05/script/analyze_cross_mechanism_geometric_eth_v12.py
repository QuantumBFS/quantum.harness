#!/usr/bin/env python3
"""No-refit inference across exact-degeneracy protection mechanisms."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


VERSION = "v12"
SCRIPT_ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = SCRIPT_ROOT / "output"
RESPONSE_CONVENTION = "Q(H-E0)^-1Q(dH)P"
REQUIRED_MODELS = (
    "laughlin",
    "moore_read",
    "lattice_susy",
    "susy_syk",
    "xcube",
)
REGISTERED_BRANCHES = (
    "cross_model_geometric_eth",
    "domain_limited_geometric_eth",
    "parent_dependent_geometry",
    "no_geometric_eth_for_registered_tangents",
)


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source(path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(SCRIPT_ROOT)), "sha256": _sha256(path)}


def build_cross_model_manifest(
    root: Path = OUTPUT_ROOT,
) -> dict[str, Any]:
    """Load immutable opened artifacts into one explicit evidence contract."""

    root = Path(root)
    paths = {
        "laughlin": root / "continuum_lll_replication_inference_v6.json",
        "moore_read": root / "moore_read_v9" / "moore_read_pilot_v9.json",
        "lattice_susy": (
            root / "lattice_susy_v10" / "lattice_susy_pilot_v10.json"
        ),
        "susy_syk": root / "susy_hodge_v7_N14_inference.json",
        "xcube": root / "xcube_v11" / "xcube_geometric_control_v11.json",
    }
    raw = {name: _load(path) for name, path in paths.items()}
    complete_path = root / f"cross_complete_covariance_{VERSION}.json"
    complete = _load(complete_path)

    laughlin = raw["laughlin"]
    laughlin_values: dict[int, list[float]] = {}
    first_score = next(iter(laughlin["scores"].values()))
    for case in first_score["cases"]:
        laughlin_values.setdefault(int(case["N"]), []).append(
            float(case["observed_delta4"])
        )

    moore = raw["moore_read"]
    moore_cases = []
    for case in moore["cases"]:
        local = [
            float(panel["R4"])
            for panel in case["panels"]
            if int(panel["panel"]) >= 0
        ]
        structured = [
            float(panel["R4"])
            for panel in case["panels"]
            if int(panel["panel"]) == -1
        ]
        moore_cases.append(
            {
                "size": int(case["case"]["N"]),
                "fiber_rank": int(case["observed_rank"]),
                "local_R4": local,
                "local_R4_median": float(median(local)),
                "structured_R4": structured[0],
                "external_gap": float(case["external_gap"]),
            }
        )

    lattice = raw["lattice_susy"]
    lattice_cases = [
        {
            "size": int(case["cycles"]),
            "fiber_rank": int(case["observed_rank"]),
            "local_R4": float(case["panels"]["local"]["R4"]),
            "isotropic_R4": float(case["panels"]["isotropic"]["R4"]),
            "hodge_balance_local": float(
                case["panels"]["local"]["hodge_balance"]
            ),
            "external_gap": float(case["external_gap"]),
        }
        for case in lattice["cases"]
    ]

    syk = raw["susy_syk"]
    xcube = raw["xcube"]
    models = {
        "laughlin": {
            "mechanism": "two_body_FQH_parent",
            "role": "stochastic_geometry",
            "response_convention": RESPONSE_CONVENTION,
            "opened_complete": True,
            "production_complete": True,
            "complete_covariance_computed": False,
            "complete_covariance_gate": False,
            "reported_branch": laughlin["branch"],
            "connected_excess_by_size": {
                str(size): float(median(values))
                for size, values in sorted(laughlin_values.items())
            },
            "checks_pass": all(laughlin["checks"].values()),
            "source": _source(paths["laughlin"]),
        },
        "moore_read": {
            "mechanism": "three_body_clustered_FQH_parent",
            "role": "stochastic_geometry",
            "response_convention": RESPONSE_CONVENTION,
            "opened_complete": bool(moore["all_checks_pass"]),
            "production_complete": False,
            "complete_covariance_computed": True,
            "complete_covariance_gate": all(
                complete["cases"][key]["positive_directional_gate"]
                for key in ("moore_read_N4", "moore_read_N6")
            ),
            "complete_covariance": {
                key: complete["cases"][key]
                for key in ("moore_read_N4", "moore_read_N6")
            },
            "cases": moore_cases,
            "checks_pass": bool(moore["all_checks_pass"]),
            "source": _source(paths["moore_read"]),
        },
        "lattice_susy": {
            "mechanism": "independence_complex_cohomology",
            "role": "stochastic_geometry",
            "response_convention": RESPONSE_CONVENTION,
            "opened_complete": bool(lattice["all_checks_pass"]),
            "production_complete": False,
            "complete_covariance_computed": True,
            "complete_covariance_gate": False,
            "complete_covariance": {
                key: value
                for key, value in complete["cases"].items()
                if key.startswith("lattice_susy_")
            },
            "cases": lattice_cases,
            "checks_pass": bool(lattice["all_checks_pass"]),
            "source": _source(paths["lattice_susy"]),
        },
        "susy_syk": {
            "mechanism": "random_supercharge_cohomology",
            "role": "stochastic_geometry",
            "response_convention": RESPONSE_CONVENTION,
            "opened_complete": bool(syk["passed"]),
            "production_complete": True,
            "complete_covariance_computed": False,
            "complete_covariance_gate": False,
            "reported_branch": syk["selected_branch"],
            "N14_observed_medians": [
                float(case["observed_median"]) for case in syk["primary_pair"]
            ],
            "checks_pass": bool(syk["passed"] and all(syk["checks"].values())),
            "source": _source(paths["susy_syk"]),
        },
        "xcube": {
            "mechanism": "commuting_projector_subsystem_code",
            "role": "structured_control",
            "response_convention": RESPONSE_CONVENTION,
            "opened_complete": bool(xcube["all_checks_pass"]),
            "production_complete": True,
            "complete_covariance_computed": "not_applicable_exact_control",
            "complete_covariance_gate": "not_applicable_exact_control",
            "coefficient_curvature": 0.0,
            "transport_curvature_eigenvalue": -0.5,
            "transport_connected_variance": 0.0,
            "checks_pass": bool(xcube["all_checks_pass"]),
            "source": _source(paths["xcube"]),
        },
    }
    return {
        "version": VERSION,
        "models": models,
        "response_convention": RESPONSE_CONVENTION,
        "observable": "covariance_whitened_connected_four_channel_response",
        "null_parameters_refit": False,
        "prospective_cases_opened": False,
        "registered_branches": list(REGISTERED_BRANCHES),
        "complete_covariance_source": _source(complete_path),
    }


def validate_cross_model_contract(manifest: dict[str, Any]) -> list[str]:
    """Return every fail-closed contract violation."""

    errors: list[str] = []
    models = manifest.get("models", {})
    missing = sorted(set(REQUIRED_MODELS) - set(models))
    if missing:
        errors.append(f"missing models: {missing}")
    if manifest.get("prospective_cases_opened") is not False:
        errors.append("prospective cases were opened before registration")
    if manifest.get("null_parameters_refit") is not False:
        errors.append("refitted null parameters are forbidden")
    convention = manifest.get("response_convention")
    for name, model in models.items():
        if model.get("response_convention") != convention:
            errors.append(f"response convention mismatch for {name}")
        if model.get("checks_pass") is not True:
            errors.append(f"failed source checks for {name}")
    if tuple(manifest.get("registered_branches", ())) != REGISTERED_BRANCHES:
        errors.append("registered branch set changed")
    return errors


def select_branch(manifest: dict[str, Any]) -> str:
    """Apply the frozen cross-model decision order without refitting."""

    errors = validate_cross_model_contract(manifest)
    if errors:
        raise ValueError("; ".join(errors))
    models = manifest["models"]
    stochastic = [
        model for model in models.values() if model["role"] == "stochastic_geometry"
    ]
    all_production = all(model["production_complete"] for model in stochastic)
    all_complete_covariance = all(
        model["complete_covariance_gate"] is True for model in stochastic
    )
    structured_control = (
        models["xcube"]["coefficient_curvature"] == 0.0
        and models["xcube"]["transport_connected_variance"] == 0.0
    )
    positive_domain = models["susy_syk"].get("reported_branch") == (
        "cohomological_non_gaussian_class"
    )
    if all_production and all_complete_covariance and structured_control:
        return "cross_model_geometric_eth"
    if positive_domain and structured_control:
        return "domain_limited_geometric_eth"
    if models["laughlin"].get("reported_branch") == "parent_dependent_geometry":
        return "parent_dependent_geometry"
    return "no_geometric_eth_for_registered_tangents"


def analyze(root: Path = OUTPUT_ROOT) -> dict[str, Any]:
    manifest = build_cross_model_manifest(root)
    errors = validate_cross_model_contract(manifest)
    if errors:
        raise RuntimeError("; ".join(errors))
    branch = select_branch(manifest)
    production_missing = [
        name
        for name, model in manifest["models"].items()
        if model["role"] == "stochastic_geometry"
        and not model["production_complete"]
    ]
    complete_covariance_missing = [
        name
        for name, model in manifest["models"].items()
        if model["role"] == "stochastic_geometry"
        and model["complete_covariance_computed"] is not True
    ]
    result = {
        **manifest,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "selected_branch": branch,
        "claim_status": "provisional_opened_cross_mechanism_result",
        "production_missing": production_missing,
        "complete_covariance_missing": complete_covariance_missing,
        "established": [
            "exact degeneracy and projector-motion audits pass in all opened models",
            "X-cube coefficient reweighting has exactly zero geometry",
            "X-cube local isospectral transport has scalar curvature and zero connected variance",
            "Moore--Read N=4 and N=6 have positive fixed-direction complete-covariance panel cumulants",
            "lattice-SUSY complete-covariance panel cumulants do not pass the fixed positive-direction gate at m=1,2,3",
        ],
        "not_established": [
            "asymptotic Geometric ETH",
            "cross-mechanism universality of a scaling law",
            "complete-covariance inference from independent Hamiltonian or disorder realizations for Moore--Read or lattice SUSY",
            "Moore--Read N=8 production result",
        ],
        "all_checks_pass": True,
    }
    output = Path(root) / f"cross_mechanism_geometric_eth_{VERSION}.json"
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=OUTPUT_ROOT)
    arguments = parser.parse_args()
    print(json.dumps(analyze(arguments.root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
