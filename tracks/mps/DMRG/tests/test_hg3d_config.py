from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path

import pytest

from spinglass3d import HardGoalDesign, load_design
from vmcrg_ref.artifacts import canonical_json_bytes


def write_design(
    directory: Path,
    *,
    distribution: str = "iid_pm1",
    periodic: bool = True,
    external_field: float = 0.0,
    sizes: tuple[int, ...] = (6, 9, 12, 15, 18, 24, 27, 45),
    routes: tuple[str, ...] = ("C", "B", "A"),
    ranks: tuple[int, ...] = (2, 4, 8),
    extra: str = "",
) -> Path:
    path = directory / "design.toml"
    path.write_text(
        f"""
schema_version = 1
sizes = {list(sizes)!r}

[model]
distribution = {distribution!r}
coupling_scale = 1.0
periodic = {str(periodic).lower()}
external_field = {external_field}
hamiltonian_sign = -1
lattice = "cubic"
dimensions = 3
boltzmann_constant = 1.0
inverse_temperature = "beta=1/T"

[rg]
block_shape = [3, 3, 3]
default_levels = 1
target_distribution = "uniform_independent"
second_level_requires = "first_rg_pass_manifest"
routes = {list(routes)!r}
main_route = "C"
fallback_route = "B"
ablation_route = "A"
mandatory_ranks = {list(ranks)!r}
extension_ranks = [16]

[evidence]
fss_sampling = "independent_unbiased"
primary_observables = ["xi_L/L", "Binder"]
observables = ["q^2", "q^4", "chi_SG(0)", "chi_SG(k_min)", "xi_L", "xi_L/L", "Binder"]
rg_compatibility = "independent"
{extra}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def test_confirmed_design_is_iid_pm1() -> None:
    design = load_design("config/hard_goal/design_v1.toml")
    assert isinstance(design, HardGoalDesign)
    assert design.model.distribution == "iid_pm1"
    assert design.model.hamiltonian_sign == -1
    assert design.model.periodic is True
    assert design.rg.block_shape == (3, 3, 3)
    assert design.rg.main_route == "C"
    assert design.rg.fallback_route == "B"
    assert design.rg.ablation_route == "A"
    assert design.rg.mandatory_ranks == (2, 4, 8)
    assert design.rg.extension_ranks == (16,)
    assert design.rg.default_levels == 1
    assert design.evidence.primary_observables == ("xi_L/L", "Binder")
    assert design.sizes == (6, 9, 12, 15, 18, 24, 27, 45)


def test_exact_half_is_rejected_for_l45(tmp_path: Path) -> None:
    path = write_design(tmp_path, distribution="exact_half_pm1")
    with pytest.raises(ValueError, match="odd bond count"):
        load_design(path)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"distribution": "gaussian"}, "distribution"),
        ({"periodic": False}, "periodic"),
        ({"external_field": 0.25}, "external field"),
        ({"sizes": (6, 9, 45, 45)}, "duplicate"),
        ({"sizes": (6, 10, 45)}, "divisible by three"),
        ({"sizes": (6, 9, 12)}, "L=45"),
        ({"routes": ("C", "D", "A")}, "route"),
        ({"ranks": (2, 3, 8)}, "rank"),
    ],
)
def test_invalid_contract_values_fail_closed(
    tmp_path: Path,
    override: dict[str, object],
    message: str,
) -> None:
    path = write_design(tmp_path, **override)
    with pytest.raises(ValueError, match=message):
        load_design(path)


def test_unknown_keys_fail_closed(tmp_path: Path) -> None:
    path = write_design(tmp_path, extra='surprise = "not accepted"')
    with pytest.raises(ValueError, match="unknown.*evidence"):
        load_design(path)


def test_design_is_immutable_and_hashes_canonical_content() -> None:
    design = load_design("config/hard_goal/design_v1.toml")
    expected = hashlib.sha256(canonical_json_bytes(design.canonical_content())).hexdigest()
    assert design.sha256 == expected
    assert len(design.sha256) == 64
    with pytest.raises(FrozenInstanceError):
        design.sizes = (45,)  # type: ignore[misc]


def test_success_contract_records_all_terminal_outcomes() -> None:
    payload = json.loads(
        Path("config/hard_goal/success_contract_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(payload["success_clauses"]) == 10
    assert payload["allowed_terminal_classes"] == [
        "PASS",
        "SCIENTIFIC_NEGATIVE",
        "EQUILIBRATION_FAILURE",
        "REPRESENTATION_FAILURE",
        "RESOURCE_NO_GO",
        "CORRECTNESS_FAILURE",
    ]
    assert payload["second_rg"]["requires_explicit_first_rg_pass_manifest"] is True
    assert payload["second_rg"]["required_first_rg_classification"] == "PASS"
