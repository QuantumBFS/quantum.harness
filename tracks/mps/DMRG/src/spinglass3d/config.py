"""Immutable, fail-closed configuration for the confirmed Hard Goal design."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
import tomllib
from typing import Any

from vmcrg_ref.artifacts import canonical_json_bytes, sha256_bytes


_ALLOWED_DISTRIBUTIONS = frozenset({"iid_pm1", "exact_half_pm1"})
_ALLOWED_ROUTES = frozenset({"A", "B", "C"})
_ALLOWED_RANKS = frozenset({2, 4, 8, 16})


def _is_real(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(float(value))


@dataclass(frozen=True)
class ModelSpec:
    """Confirmed cubic Edwards-Anderson model and unit conventions."""

    distribution: str
    coupling_scale: float
    periodic: bool
    external_field: float
    hamiltonian_sign: int
    lattice: str = "cubic"
    dimensions: int = 3
    boltzmann_constant: float = 1.0
    inverse_temperature: str = "beta=1/T"

    def __post_init__(self) -> None:
        if self.distribution not in _ALLOWED_DISTRIBUTIONS:
            raise ValueError(f"unknown disorder distribution: {self.distribution!r}")
        if not _is_real(self.coupling_scale) or float(self.coupling_scale) != 1.0:
            raise ValueError("coupling scale must be |J|=1")
        if type(self.periodic) is not bool or not self.periodic:
            raise ValueError("periodic cubic boundaries are required")
        if not _is_real(self.external_field) or float(self.external_field) != 0.0:
            raise ValueError("external field must be zero")
        if type(self.hamiltonian_sign) is not int or self.hamiltonian_sign != -1:
            raise ValueError("Hamiltonian sign must be -1")
        if self.lattice != "cubic" or type(self.dimensions) is not int:
            raise ValueError("the lattice must be three-dimensional cubic")
        if self.dimensions != 3:
            raise ValueError("the lattice must be three-dimensional cubic")
        if (
            not _is_real(self.boltzmann_constant)
            or float(self.boltzmann_constant) != 1.0
        ):
            raise ValueError("Boltzmann constant must be k_B=1")
        if self.inverse_temperature != "beta=1/T":
            raise ValueError("inverse-temperature convention must be beta=1/T")

    def validate_length(self, length: int) -> None:
        if type(length) is not int:
            raise ValueError("length must be an integer")
        if length < 2:
            raise ValueError("length must be at least two")
        if self.distribution == "exact_half_pm1" and 3 * length**3 % 2:
            raise ValueError(
                "exact-half disorder is impossible for an odd bond count"
            )


@dataclass(frozen=True)
class RGSpec:
    """Renormalization, representation-route, and TT-rank contract."""

    block_shape: tuple[int, int, int]
    default_levels: int
    target_distribution: str
    second_level_requires: str
    routes: tuple[str, ...]
    main_route: str
    fallback_route: str
    ablation_route: str
    mandatory_ranks: tuple[int, ...]
    extension_ranks: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.block_shape != (3, 3, 3):
            raise ValueError("RG block shape must be 3x3x3")
        if type(self.default_levels) is not int or self.default_levels != 1:
            raise ValueError("exactly one RG level must be enabled by default")
        if self.target_distribution != "uniform_independent":
            raise ValueError("RG target distribution must be uniform and independent")
        if self.second_level_requires != "first_rg_pass_manifest":
            raise ValueError("second RG requires a first-RG pass manifest")

        if not isinstance(self.routes, tuple) or not self.routes:
            raise ValueError("routes must be a nonempty immutable sequence")
        unknown_routes = set(self.routes) - _ALLOWED_ROUTES
        if unknown_routes:
            raise ValueError(f"unknown route names: {sorted(unknown_routes)!r}")
        if len(set(self.routes)) != len(self.routes):
            raise ValueError("duplicate routes are not allowed")
        roles = (self.main_route, self.fallback_route, self.ablation_route)
        if roles != ("C", "B", "A") or self.routes != roles:
            raise ValueError("route roles must be C main, B fallback, A ablation")

        all_ranks = self.mandatory_ranks + self.extension_ranks
        if any(type(rank) is not int for rank in all_ranks):
            raise ValueError("TT ranks must be integers")
        unknown_ranks = set(all_ranks) - _ALLOWED_RANKS
        if unknown_ranks:
            raise ValueError(f"unsupported TT rank: {sorted(unknown_ranks)!r}")
        if len(set(all_ranks)) != len(all_ranks):
            raise ValueError("duplicate TT ranks are not allowed")
        if self.mandatory_ranks != (2, 4, 8) or self.extension_ranks != (16,):
            raise ValueError("TT ranks must be 2/4/8 mandatory and 16 extension")


@dataclass(frozen=True)
class EvidenceSpec:
    """Independent finite-size and RG evidence contract."""

    fss_sampling: str
    primary_observables: tuple[str, ...]
    observables: tuple[str, ...]
    rg_compatibility: str

    def __post_init__(self) -> None:
        if self.fss_sampling != "independent_unbiased":
            raise ValueError("finite-size evidence must use independent unbiased sampling")
        if self.primary_observables != ("xi_L/L", "Binder"):
            raise ValueError("primary FSS observables must be xi_L/L and Binder")
        if not isinstance(self.observables, tuple) or len(set(self.observables)) != len(
            self.observables
        ):
            raise ValueError("observable names must be an immutable unique sequence")
        if not set(self.primary_observables).issubset(self.observables):
            raise ValueError("primary observables must be included in observables")
        if self.rg_compatibility != "independent":
            raise ValueError("RG compatibility evidence must be independent")


@dataclass(frozen=True)
class HardGoalDesign:
    """Fully validated contract passed to all three-dimensional workflows."""

    model: ModelSpec
    rg: RGSpec
    evidence: EvidenceSpec
    sizes: tuple[int, ...]
    schema_version: int = 1

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported hard-goal design schema version")
        if not isinstance(self.sizes, tuple) or not self.sizes:
            raise ValueError("sizes must be a nonempty immutable sequence")
        if any(type(length) is not int for length in self.sizes):
            raise ValueError("sizes must contain integers")
        if len(set(self.sizes)) != len(self.sizes):
            raise ValueError("duplicate sizes are not allowed")
        if any(length % 3 for length in self.sizes):
            raise ValueError("all production sizes must be divisible by three")
        if 45 not in self.sizes:
            raise ValueError("the production design must include L=45")
        for length in self.sizes:
            self.model.validate_length(length)
        if self.sizes != tuple(sorted(self.sizes)):
            raise ValueError("sizes must be strictly increasing")

    def canonical_content(self) -> dict[str, Any]:
        """Return the semantic dataclass projection used for artifact hashes."""

        return asdict(self)

    @property
    def sha256(self) -> str:
        return sha256_bytes(canonical_json_bytes(self.canonical_content()))


def _require_table(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"missing or invalid [{key}] section")
    return value


def _require_exact_keys(
    raw: dict[str, Any], expected: frozenset[str], section: str
) -> None:
    actual = set(raw)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise ValueError(f"missing keys in {section}: {sorted(missing)!r}")
    if unknown:
        raise ValueError(f"unknown keys in {section}: {sorted(unknown)!r}")


def _require_string(raw: dict[str, Any], key: str, section: str) -> str:
    value = raw[key]
    if type(value) is not str:
        raise ValueError(f"{section}.{key} must be a string")
    return value


def _require_bool(raw: dict[str, Any], key: str, section: str) -> bool:
    value = raw[key]
    if type(value) is not bool:
        raise ValueError(f"{section}.{key} must be a boolean")
    return value


def _require_int(raw: dict[str, Any], key: str, section: str) -> int:
    value = raw[key]
    if type(value) is not int:
        raise ValueError(f"{section}.{key} must be an integer")
    return value


def _require_float(raw: dict[str, Any], key: str, section: str) -> float:
    value = raw[key]
    if not _is_real(value):
        raise ValueError(f"{section}.{key} must be a finite number")
    return float(value)


def _require_tuple(
    raw: dict[str, Any], key: str, section: str, item_type: type
) -> tuple[Any, ...]:
    value = raw[key]
    if not isinstance(value, list):
        raise ValueError(f"{section}.{key} must be an array")
    if any(type(item) is not item_type for item in value):
        raise ValueError(f"{section}.{key} contains an invalid value type")
    return tuple(value)


def load_design(path: str | Path) -> HardGoalDesign:
    """Load and validate the complete Hard Goal TOML contract."""

    source = Path(path)
    with source.open("rb") as handle:
        raw = tomllib.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("design document must contain a TOML table")

    _require_exact_keys(
        raw,
        frozenset({"schema_version", "sizes", "model", "rg", "evidence"}),
        "top level",
    )
    model_raw = _require_table(raw, "model")
    rg_raw = _require_table(raw, "rg")
    evidence_raw = _require_table(raw, "evidence")
    _require_exact_keys(
        model_raw,
        frozenset(
            {
                "distribution",
                "coupling_scale",
                "periodic",
                "external_field",
                "hamiltonian_sign",
                "lattice",
                "dimensions",
                "boltzmann_constant",
                "inverse_temperature",
            }
        ),
        "model",
    )
    _require_exact_keys(
        rg_raw,
        frozenset(
            {
                "block_shape",
                "default_levels",
                "target_distribution",
                "second_level_requires",
                "routes",
                "main_route",
                "fallback_route",
                "ablation_route",
                "mandatory_ranks",
                "extension_ranks",
            }
        ),
        "rg",
    )
    _require_exact_keys(
        evidence_raw,
        frozenset(
            {
                "fss_sampling",
                "primary_observables",
                "observables",
                "rg_compatibility",
            }
        ),
        "evidence",
    )

    model = ModelSpec(
        distribution=_require_string(model_raw, "distribution", "model"),
        coupling_scale=_require_float(model_raw, "coupling_scale", "model"),
        periodic=_require_bool(model_raw, "periodic", "model"),
        external_field=_require_float(model_raw, "external_field", "model"),
        hamiltonian_sign=_require_int(model_raw, "hamiltonian_sign", "model"),
        lattice=_require_string(model_raw, "lattice", "model"),
        dimensions=_require_int(model_raw, "dimensions", "model"),
        boltzmann_constant=_require_float(
            model_raw, "boltzmann_constant", "model"
        ),
        inverse_temperature=_require_string(
            model_raw, "inverse_temperature", "model"
        ),
    )
    rg = RGSpec(
        block_shape=_require_tuple(rg_raw, "block_shape", "rg", int),
        default_levels=_require_int(rg_raw, "default_levels", "rg"),
        target_distribution=_require_string(
            rg_raw, "target_distribution", "rg"
        ),
        second_level_requires=_require_string(
            rg_raw, "second_level_requires", "rg"
        ),
        routes=_require_tuple(rg_raw, "routes", "rg", str),
        main_route=_require_string(rg_raw, "main_route", "rg"),
        fallback_route=_require_string(rg_raw, "fallback_route", "rg"),
        ablation_route=_require_string(rg_raw, "ablation_route", "rg"),
        mandatory_ranks=_require_tuple(rg_raw, "mandatory_ranks", "rg", int),
        extension_ranks=_require_tuple(rg_raw, "extension_ranks", "rg", int),
    )
    evidence = EvidenceSpec(
        fss_sampling=_require_string(
            evidence_raw, "fss_sampling", "evidence"
        ),
        primary_observables=_require_tuple(
            evidence_raw, "primary_observables", "evidence", str
        ),
        observables=_require_tuple(evidence_raw, "observables", "evidence", str),
        rg_compatibility=_require_string(
            evidence_raw, "rg_compatibility", "evidence"
        ),
    )
    return HardGoalDesign(
        model=model,
        rg=rg,
        evidence=evidence,
        sizes=_require_tuple(raw, "sizes", "top level", int),
        schema_version=_require_int(raw, "schema_version", "top level"),
    )
